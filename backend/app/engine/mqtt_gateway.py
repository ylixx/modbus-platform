"""MQTT ThingsBoard gateway session — uses shared connection pool.

One gateway connection manages multiple sub-devices via a shared
paho.Client from MqttConnectionPool.
"""
import json
import threading
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag
from app.engine.mqtt_connection_pool import mqtt_pool
from app.engine.mqtt_preset_renderer import preset_renderer
from app.engine.mqtt_utils import (
    process_tag_value, update_device_status, ts_to_datetime,
)


class MqttGatewaySession:
    """Single MQTT connection acting as a ThingsBoard gateway, via the shared pool."""

    def __init__(self, gateway_device: Device, managed_devices: list[Device]):
        self._gateway_id = gateway_device.id
        self._gateway_name = gateway_device.name
        self._broker = gateway_device.mqtt_broker
        self._port = gateway_device.mqtt_port
        self._username = gateway_device.mqtt_username or ""
        self._password = gateway_device.mqtt_password or ""
        self._client_id = gateway_device.mqtt_client_id or ""
        self._use_tls = gateway_device.mqtt_use_tls
        self._ca_cert = gateway_device.mqtt_ca_cert

        self._publish_enabled = gateway_device.mqtt_publish_enabled
        self._publish_topic = gateway_device.mqtt_publish_topic
        self._publish_qos = gateway_device.mqtt_publish_qos or 0
        self._publish_interval = gateway_device.mqtt_publish_interval or 5.0

        self._subscribe_topic = gateway_device.mqtt_topic_prefix or "v1/gateway/telemetry"

        # Managed devices: name -> {device, tags, live_values}
        self._managed: dict[str, dict] = {}
        for dev in managed_devices:
            db = SessionLocal()
            try:
                tags = db.query(DeviceTag).filter(DeviceTag.device_id == dev.id, DeviceTag.enabled == True).all()
            finally:
                db.close()
            self._managed[dev.name.strip().lower()] = {
                "device": dev, "tags": tags,
                "tag_by_name": {t.name: t for t in tags},
                "live_values": {},
            }

        self._stop_event = threading.Event()
        self._connected = False
        self._publish_thread: Optional[threading.Thread] = None
        self._pool_key: Optional[str] = None

    def start(self):
        # Acquire a shared connection from the pool
        self._pool_key, entry = mqtt_pool.acquire(
            broker=self._broker,
            port=self._port,
            username=self._username,
            password=self._password,
            client_id=self._client_id or f"tb_gw_{self._gateway_id}",
            use_tls=self._use_tls,
            ca_cert=self._ca_cert or "",
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
        )

        # Subscribe the gateway topic through the pool
        mqtt_pool.subscribe(self._pool_key, self._subscribe_topic, callback=self._on_message, qos=1)

        if self._publish_enabled and self._publish_topic:
            self._publish_thread = threading.Thread(
                target=self._publish_loop, daemon=True, name=f"tb-gw-pub-{self._gateway_id}"
            )
            self._publish_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._pool_key:
            mqtt_pool.unsubscribe(self._pool_key, self._subscribe_topic, callback=self._on_message)
            mqtt_pool.release(self._pool_key)
            self._pool_key = None
        self._connected = False

    def write_value(self, device_id: int, tag: DeviceTag, value) -> bool:
        if not self._pool_key:
            return False
        topic = tag.mqtt_publish_topic or self._publish_topic or "v1/gateway/telemetry"
        msg = {tag.name: value}
        return mqtt_pool.publish(self._pool_key, topic, json.dumps(msg), qos=self._publish_qos, retain=tag.mqtt_retain)

    def get_live_values(self, device_id: int) -> dict:
        for entry in self._managed.values():
            if entry["device"].id == device_id:
                return entry["live_values"]
        return {}

    # ── internals ──

    def _on_connect(self, client, rc):
        """Called via pool's on_connect callback."""
        if rc == 0:
            self._connected = True
            update_device_status(self._gateway_id, "online", None)
            logger.info(f"TB Gateway '{self._gateway_name}' connected via pool")
            for entry in self._managed.values():
                update_device_status(entry["device"].id, "online", None)
        else:
            logger.error(f"TB Gateway connect failed: rc={rc}")
            update_device_status(self._gateway_id, "error", f"rc={rc}")

    def _on_disconnect(self, client, rc):
        """Called via pool's on_disconnect callback."""
        self._connected = False
        if rc != 0:
            logger.warning(f"TB Gateway disconnected: rc={rc}")
            update_device_status(self._gateway_id, "offline", "connection lost")

    def _on_message(self, client, msg):
        """Called by the pool when a message arrives on the gateway topic."""
        try:
            payload_str = msg.payload.decode("utf-8", errors="replace")
            json_obj = json.loads(payload_str)
        except (json.JSONDecodeError, ValueError):
            return

        if not isinstance(json_obj, dict):
            return

        for device_key, batches in json_obj.items():
            entry = self._managed.get(device_key.strip().lower())
            if entry is None:
                continue

            dev = entry["device"]
            tags = entry["tag_by_name"]
            live = entry["live_values"]

            if not isinstance(batches, list):
                continue

            for batch in batches:
                if not isinstance(batch, dict):
                    continue
                ts_ms = batch.get("ts")
                values = batch.get("values", {})
                ts_dt = ts_to_datetime(ts_ms) if ts_ms else datetime.now(timezone.utc)

                for key, raw_value in values.items():
                    tag = tags.get(key)
                    if tag is None:
                        continue
                    result = process_tag_value(dev.id, tag, raw_value, ts_dt)
                    if result is not None:
                        live[tag.id] = result

        update_device_status(self._gateway_id, "online", None)

    def _publish_loop(self):
        while not self._stop_event.is_set():
            if self._connected:
                for entry in self._managed.values():
                    live = entry["live_values"]
                    if not live:
                        continue
                    db = SessionLocal()
                    try:
                        values = {}
                        for tag_id, val in live.items():
                            tag = db.query(DeviceTag).filter(DeviceTag.id == tag_id).first()
                            key = tag.name if tag else str(tag_id)
                            values[key] = val.get("value")
                    finally:
                        db.close()
                    if values:
                        data = preset_renderer.build_telemetry_data(
                            entry["device"].id, entry["device"].name, values
                        )
                        payload = preset_renderer.render_payload(
                            preset_mode="thingsboard_gateway",
                            data=data,
                        )
                        mqtt_pool.publish(self._pool_key, self._publish_topic, payload, qos=self._publish_qos)
            self._stop_event.wait(self._publish_interval)
