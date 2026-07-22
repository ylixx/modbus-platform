"""MQTT ThingsBoard gateway session — one connection manages multiple devices."""
import json
import ssl
import threading
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
import paho.mqtt.client as mqtt

from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag
from app.engine.mqtt_utils import (
    process_tag_value, update_device_status, ts_to_datetime,
)


class MqttGatewaySession:
    """Single MQTT connection acting as a ThingsBoard gateway."""

    def __init__(self, gateway_device: Device, managed_devices: list[Device]):
        self._gateway_id = gateway_device.id
        self._gateway_name = gateway_device.name
        self._broker = gateway_device.mqtt_broker
        self._port = gateway_device.mqtt_port
        self._username = gateway_device.mqtt_username or None
        self._password = gateway_device.mqtt_password or None
        self._client_id = gateway_device.mqtt_client_id or f"tb_gateway_{gateway_device.id}"
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

        self._client: Optional[mqtt.Client] = None
        self._stop_event = threading.Event()
        self._connected = False
        self._publish_thread: Optional[threading.Thread] = None

    def start(self):
        self._client = mqtt.Client(
            client_id=self._client_id, protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        if self._username:
            self._client.username_pw_set(self._username, self._password)
        if self._use_tls:
            ctx = ssl.create_default_context()
            if self._ca_cert:
                import tempfile, os
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                tmp.write(self._ca_cert.encode())
                tmp.close()
                ctx.load_verify_locations(tmp.name)
                os.unlink(tmp.name)
            else:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            self._client.tls_set_context(ctx)

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

        try:
            self._client.connect(self._broker, self._port, keepalive=60)
            self._client.loop_start()
            logger.info(f"TB Gateway '{self._gateway_name}' connecting to {self._broker}:{self._port}, managing {len(self._managed)} devices")
        except Exception as e:
            logger.error(f"TB Gateway connect error: {e}")
            update_device_status(self._gateway_id, "error", str(e))

        if self._publish_enabled and self._publish_topic:
            self._publish_thread = threading.Thread(target=self._publish_loop, daemon=True, name=f"tb-gw-pub-{self._gateway_id}")
            self._publish_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
        self._connected = False

    def write_value(self, device_id: int, tag: DeviceTag, value) -> bool:
        if not self._client or not self._connected:
            return False
        topic = tag.mqtt_publish_topic or self._publish_topic or "v1/gateway/telemetry"
        msg = {tag.name: value}
        info = self._client.publish(topic, json.dumps(msg), qos=self._publish_qos, retain=tag.mqtt_retain)
        return info.rc == mqtt.MQTT_ERR_SUCCESS

    def get_live_values(self, device_id: int) -> dict:
        for entry in self._managed.values():
            if entry["device"].id == device_id:
                return entry["live_values"]
        return {}

    # ── internals ──

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self._connected = True
            update_device_status(self._gateway_id, "online", None)
            client.subscribe(self._subscribe_topic, qos=1)
            logger.info(f"TB Gateway connected, subscribed to '{self._subscribe_topic}'")
            for entry in self._managed.values():
                update_device_status(entry["device"].id, "online", None)
        else:
            logger.error(f"TB Gateway connect failed: rc={rc}")
            update_device_status(self._gateway_id, "error", f"rc={rc}")

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self._connected = False
        if rc != 0:
            logger.warning(f"TB Gateway disconnected: rc={rc}")
            update_device_status(self._gateway_id, "offline", "connection lost")

    def _on_message(self, client, userdata, msg):
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
                        msg = {entry["device"].name: [{"values": values}]}
                        self._client.publish(self._publish_topic, json.dumps(msg), qos=self._publish_qos)
            self._stop_event.wait(self._publish_interval)
