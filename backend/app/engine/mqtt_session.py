"""MQTT standard device session — one connection per device."""
import json
import ssl
import threading
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
import paho.mqtt.client as mqtt

from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag
from app.models.history import TagHistory
from app.engine.mqtt_utils import (
    MqttPayloadFormat, resolve_json_path, is_thingsboard_format,
    process_tag_value, update_device_status, ts_to_datetime,
)


class MqttDeviceSession:
    """Manages one MQTT connection for a single device."""

    def __init__(self, device: Device):
        self.device_id = device.id
        self.device_name = device.name
        self._broker = device.mqtt_broker
        self._port = device.mqtt_port
        self._username = device.mqtt_username or None
        self._password = device.mqtt_password or None
        self._client_id = device.mqtt_client_id or f"modbus_platform_{device.id}"
        self._topic_prefix = device.mqtt_topic_prefix
        self._use_tls = device.mqtt_use_tls
        self._ca_cert = device.mqtt_ca_cert
        self._payload_format = device.mqtt_payload_format or MqttPayloadFormat.JSON

        self._publish_enabled = device.mqtt_publish_enabled
        self._publish_topic = device.mqtt_publish_topic
        self._publish_qos = device.mqtt_publish_qos or 0
        self._publish_interval = device.mqtt_publish_interval or 5.0

        self._client: Optional[mqtt.Client] = None
        self._stop_event = threading.Event()
        self._publish_thread: Optional[threading.Thread] = None
        self._connected = False
        self._topic_tags: dict[str, list[DeviceTag]] = {}
        self._live_values: dict[int, dict] = {}

    def start(self, tags: list[DeviceTag]):
        self._build_topic_map(tags)
        self._client = mqtt.Client(
            client_id=self._client_id, protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        if self._username:
            self._client.username_pw_set(self._username, self._password)
        if self._use_tls:
            self._apply_tls()

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

        try:
            self._client.connect(self._broker, self._port, keepalive=60)
            self._client.loop_start()
            logger.info(f"MQTT device '{self.device_name}' connecting to {self._broker}:{self._port}")
        except Exception as e:
            logger.error(f"MQTT connect error for '{self.device_name}': {e}")
            update_device_status(self.device_id, "error", str(e))

        if self._publish_enabled and self._publish_topic:
            self._publish_thread = threading.Thread(target=self._publish_loop, daemon=True, name=f"mqtt-pub-{self.device_id}")
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

    def write_value(self, tag: DeviceTag, value) -> bool:
        if not self._client or not self._connected:
            return False
        topic = tag.mqtt_publish_topic or f"{self._topic_prefix}/{tag.name}/set"
        payload = json.dumps({"value": value}) if not isinstance(value, str) else str(value)
        info = self._client.publish(topic, payload, qos=self._publish_qos, retain=tag.mqtt_retain)
        return info.rc == mqtt.MQTT_ERR_SUCCESS

    def get_live_values(self) -> dict:
        return self._live_values

    # ── internals ──

    def _apply_tls(self):
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

    def _build_topic_map(self, tags: list[DeviceTag]):
        self._topic_tags.clear()
        for tag in tags:
            topic = tag.mqtt_topic or f"{self._topic_prefix}/{tag.name}"
            self._topic_tags.setdefault(topic, []).append(tag)

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self._connected = True
            update_device_status(self.device_id, "online", None)
            logger.info(f"MQTT device '{self.device_name}' connected")
            for topic in self._topic_tags:
                client.subscribe(topic, qos=1)
        else:
            logger.error(f"MQTT connect failed for '{self.device_name}': rc={rc}")
            update_device_status(self.device_id, "error", f"MQTT connect rc={rc}")

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self._connected = False
        if rc != 0:
            logger.warning(f"MQTT device '{self.device_name}' disconnected: rc={rc}")
            update_device_status(self.device_id, "offline", "connection lost")

    def _on_message(self, client, userdata, msg):
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
                payload = {"device_id": self.device_id, "device_name": self.device_name, "timestamp": datetime.now(timezone.utc).isoformat(), "values": {}}
                db = SessionLocal()
                try:
                    for tag_id, val in self._live_values.items():
                        tag = db.query(DeviceTag).filter(DeviceTag.id == tag_id).first()
                        key = tag.name if tag else str(tag_id)
                        payload["values"][key] = val.get("value")
                finally:
                    db.close()
                self._client.publish(self._publish_topic, json.dumps(payload), qos=self._publish_qos)
            self._stop_event.wait(self._publish_interval)
