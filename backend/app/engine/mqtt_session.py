"""MQTT standard device session — uses shared connection pool.

One device session maps to one subscription set on a shared paho.Client
(via MqttConnectionPool). Publish also goes through the pool.
"""
import json
import threading
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag
from app.engine.mqtt_connection_pool import mqtt_pool, MqttConnectionPool
from app.engine.mqtt_preset_renderer import preset_renderer
from app.engine.mqtt_utils import (
    MqttPayloadFormat, resolve_json_path, is_thingsboard_format,
    process_tag_value, update_device_status, ts_to_datetime,
)


class MqttDeviceSession:
    """Manages one device's subscribe/publish lifecycle via the shared connection pool."""

    def __init__(self, device: Device):
        self.device_id = device.id
        self.device_name = device.name
        self._broker = device.mqtt_broker
        self._port = device.mqtt_port
        self._username = device.mqtt_username or ""
        self._password = device.mqtt_password or ""
        self._client_id = device.mqtt_client_id or ""
        self._topic_prefix = device.mqtt_topic_prefix
        self._use_tls = device.mqtt_use_tls
        self._ca_cert = device.mqtt_ca_cert
        self._payload_format = device.mqtt_payload_format or MqttPayloadFormat.JSON

        self._publish_enabled = device.mqtt_publish_enabled
        self._publish_topic = device.mqtt_publish_topic
        self._publish_qos = device.mqtt_publish_qos or 0
        self._publish_interval = device.mqtt_publish_interval or 5.0
        self._publish_template = (device.mqtt_payload_template or "").strip()

        self._stop_event = threading.Event()
        self._publish_thread: Optional[threading.Thread] = None
        self._connected = False
        self._topic_tags: dict[str, list[DeviceTag]] = {}
        self._live_values: dict[int, dict] = {}

        # Pool key — will be set on start()
        self._pool_key: Optional[str] = None

    def start(self, tags: list[DeviceTag]):
        self._build_topic_map(tags)

        # Acquire a shared connection from the pool
        self._pool_key, entry = mqtt_pool.acquire(
            broker=self._broker,
            port=self._port,
            username=self._username,
            password=self._password,
            client_id=self._client_id or f"dev_{self.device_id}",
            use_tls=self._use_tls,
            ca_cert=self._ca_cert or "",
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
        )

        # Subscribe all topics through the pool
        for topic in self._topic_tags:
            mqtt_pool.subscribe(self._pool_key, topic, callback=self._on_message, qos=1)

        if self._publish_enabled and self._publish_topic:
            self._publish_thread = threading.Thread(
                target=self._publish_loop, daemon=True, name=f"mqtt-pub-{self.device_id}"
            )
            self._publish_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._pool_key:
            # Unsubscribe all topics
            for topic in self._topic_tags:
                mqtt_pool.unsubscribe(self._pool_key, topic, callback=self._on_message)
            # Release the pool connection
            mqtt_pool.release(self._pool_key)
            self._pool_key = None
        self._connected = False

    def write_value(self, tag: DeviceTag, value) -> bool:
        if not self._pool_key:
            return False
        topic = tag.mqtt_publish_topic or f"{self._topic_prefix}/{tag.name}/set"
        payload = json.dumps({"value": value}) if not isinstance(value, str) else str(value)
        return mqtt_pool.publish(self._pool_key, topic, payload, qos=self._publish_qos, retain=tag.mqtt_retain)

    def get_live_values(self) -> dict:
        return self._live_values

    # ── internals ──

    def _build_topic_map(self, tags: list[DeviceTag]):
        self._topic_tags.clear()
        for tag in tags:
            topic = tag.mqtt_topic or f"{self._topic_prefix}/{tag.name}"
            self._topic_tags.setdefault(topic, []).append(tag)

    def _on_connect(self, client, rc):
        """Called via pool's on_connect callback."""
        if rc == 0:
            self._connected = True
            update_device_status(self.device_id, "online", None)
            logger.info(f"MQTT device '{self.device_name}' connected via pool")
        else:
            logger.error(f"MQTT connect failed for '{self.device_name}': rc={rc}")
            update_device_status(self.device_id, "error", f"MQTT connect rc={rc}")

    def _on_disconnect(self, client, rc):
        """Called via pool's on_disconnect callback."""
        self._connected = False
        if rc != 0:
            logger.warning(f"MQTT device '{self.device_name}' disconnected: rc={rc}")
            update_device_status(self.device_id, "offline", "connection lost")

    def _on_message(self, client, msg):
        """Called by the pool when a message arrives on a subscribed topic."""
        try:
            payload_str = msg.payload.decode("utf-8", errors="replace")
            tags = self._topic_tags.get(msg.topic, [])

            json_obj = None
            try:
                json_obj = json.loads(payload_str)
            except (json.JSONDecodeError, ValueError):
                pass

            # ThingsBoard gateway format
            if json_obj is not None and isinstance(json_obj, dict) and is_thingsboard_format(json_obj):
                self._handle_thingsboard(json_obj)
                return

            # Standard per-tag processing
            for tag in tags:
                raw_value = None
                if json_obj is not None and isinstance(json_obj, dict) and tag.mqtt_json_path:
                    raw_value = resolve_json_path(json_obj, tag.mqtt_json_path)
                elif json_obj is not None and isinstance(json_obj, (int, float)):
                    raw_value = json_obj
                else:
                    try:
                        raw_value = float(payload_str)
                    except ValueError:
                        raw_value = payload_str

                live = process_tag_value(self.device_id, tag, raw_value)
                if live is not None:
                    self._live_values[tag.id] = live

        except Exception as e:
            logger.error(f"MQTT message error on {msg.topic}: {e}")

    def _handle_thingsboard(self, json_obj: dict):
        device_data = json_obj.get(self.device_name)
        if device_data is None:
            for key in json_obj:
                if key.strip().lower() == self.device_name.strip().lower():
                    device_data = json_obj[key]
                    break
        if device_data is None:
            return
        self._process_tb_batches(device_data)

    def _process_tb_batches(self, batches: list):
        db = SessionLocal()
        try:
            tags = db.query(DeviceTag).filter(DeviceTag.device_id == self.device_id, DeviceTag.enabled == True).all()
        finally:
            db.close()

        tag_by_name = {t.name: t for t in tags}

        for batch in batches:
            if not isinstance(batch, dict):
                continue
            ts_ms = batch.get("ts")
            values = batch.get("values", {})
            ts_dt = ts_to_datetime(ts_ms) if ts_ms else datetime.now(timezone.utc)

            for key, raw_value in values.items():
                tag = tag_by_name.get(key)
                if tag is None:
                    continue
                live = process_tag_value(self.device_id, tag, raw_value, ts_dt)
                if live is not None:
                    self._live_values[tag.id] = live

    def _publish_loop(self):
        while not self._stop_event.is_set():
            if self._connected and self._live_values:
                payload = self._render_payload()
                mqtt_pool.publish(self._pool_key, self._publish_topic, payload, qos=self._publish_qos)
            self._stop_event.wait(self._publish_interval)

    def _render_payload(self) -> bytes:
        """Render publish payload using MqttPresetRenderer."""
        now = datetime.now(timezone.utc)
        timestamp_ms = int(now.timestamp() * 1000)

        # Build values dicts
        values_simple = {}
        values_detail = {}
        db = SessionLocal()
        try:
            for tag_id, val in self._live_values.items():
                tag = db.query(DeviceTag).filter(DeviceTag.id == tag_id).first()
                key = tag.name if tag else str(tag_id)
                values_simple[key] = val.get("value")
                values_detail[key] = {
                    "value": val.get("value"),
                    "quality": val.get("quality", "good"),
                    "raw_value": val.get("raw_value"),
                }
        finally:
            db.close()

        # Use preset renderer for telemetry data
        data = preset_renderer.build_telemetry_data(
            self.device_id, self.device_name, values_simple, timestamp_ms
        )
        context = preset_renderer.build_telemetry_context(
            self.device_id, self.device_name, values_simple, values_detail,
            now.isoformat(), timestamp_ms,
        )

        return preset_renderer.render_payload(
            preset_mode="standard",  # Device-level publish is always standard mode
            data=data,
            custom_template=self._publish_template,
            context=context,
        )
