"""MQTT acquisition & publishing engine.

Supports three payload formats:
  1. Plain value        → 42, 3.14, "hello"
  2. Standard JSON      → {"temperature": 42}  (with json_path)
  3. ThingsBoard        → {"Device A": [{"ts": 1483228800000, "values": {"temp": 42}}]}

ThingsBoard gateway mode:
  - A single MQTT device object acts as the "gateway" connection.
  - It subscribes to one shared topic (e.g. v1/gateway/telemetry).
  - Incoming JSON keys are matched against *device name*.
  - The matched device's tags are then resolved from `values`.
  - All platform MQTT devices sharing the same broker/topic can
    coexist through a single gateway session.
"""
import json
import ssl
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

import paho.mqtt.client as mqtt

from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag, ProtocolType
from app.models.history import TagHistory


# ─── Payload format enum ───

class MqttPayloadFormat:
    PLAIN = "plain"
    JSON = "json"
    THINGSBOARD = "thingsboard"


# ─── Helpers ───

def _resolve_json_path(obj: dict, path: str):
    """Dot-notation: 'a.b.c' → obj['a']['b']['c']."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _cast_value(raw, target_type: str):
    try:
        if target_type in ("float64", "float32"):
            return float(raw)
        elif target_type in ("int16", "uint16", "int32", "uint32"):
            return int(float(raw))
        elif target_type == "bool":
            if isinstance(raw, str):
                return 1 if raw.lower() in ("1", "true", "on") else 0
            return int(bool(raw))
        elif target_type == "string":
            return str(raw)
        return float(raw)
    except (ValueError, TypeError):
        return None


def _ts_to_datetime(ts_ms: int) -> datetime:
    """Convert epoch milliseconds to UTC datetime."""
    try:
        return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    except (OSError, ValueError, OverflowError):
        return datetime.utcnow()


def _is_thingsboard_format(obj: dict) -> bool:
    """Heuristic: top-level values are lists of {ts, values} dicts."""
    if not isinstance(obj, dict) or not obj:
        return False
    for v in obj.values():
        if isinstance(v, list) and len(v) > 0:
            first = v[0]
            if isinstance(first, dict) and "ts" in first and "values" in first:
                return True
    return False


# ─── Per-tag processing (shared by all formats) ───

def _process_tag_value(device_id: int, tag: DeviceTag, raw_value, ts: Optional[datetime] = None):
    """Cast, scale, store history, evaluate alarms for a single tag value."""
    casted = _cast_value(raw_value, tag.mqtt_value_type or "float64")
    if casted is None:
        return None

    processed = casted * tag.scale_factor + tag.offset
    if tag.decimal_places is not None and isinstance(processed, float):
        processed = round(processed, tag.decimal_places)

    now = ts or datetime.utcnow()
    live = {
        "value": processed,
        "raw_value": str(casted),
        "quality": "good",
        "time": now.isoformat(),
    }

    # History
    db = SessionLocal()
    try:
        db.add(TagHistory(
            device_id=device_id,
            tag_id=tag.id,
            tag_name=tag.name,
            value=processed,
            raw_value=str(casted),
            quality="good",
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    # Alarm
    from app.services.alarm_service import alarm_service
    alarm_service.evaluate(device_id, tag.id, tag.name, processed)

    return live


# ──────────────────────────────────────────────
#  Standard session  (plain / json per-device)
# ──────────────────────────────────────────────

class MqttDeviceSession:
    """One MQTT connection for a single device (standard / json mode)."""

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

        # Publish
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
            client_id=self._client_id,
            protocol=mqtt.MQTTv311,
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
            self._update_status("error", str(e))

        if self._publish_enabled and self._publish_topic:
            self._publish_thread = threading.Thread(
                target=self._publish_loop, daemon=True, name=f"mqtt-pub-{self.device_id}")
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
            self._update_status("online", None)
            logger.info(f"MQTT device '{self.device_name}' connected")
            for topic in self._topic_tags:
                client.subscribe(topic, qos=1)
                logger.debug(f"  subscribed: {topic}")
        else:
            logger.error(f"MQTT connect failed for '{self.device_name}': rc={rc}")
            self._update_status("error", f"MQTT connect rc={rc}")

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self._connected = False
        if rc != 0:
            logger.warning(f"MQTT device '{self.device_name}' disconnected: rc={rc}")
            self._update_status("offline", "connection lost")

    def _on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode("utf-8", errors="replace")
            tags = self._topic_tags.get(msg.topic, [])

            json_obj = None
            try:
                json_obj = json.loads(payload_str)
            except (json.JSONDecodeError, ValueError):
                pass

            # ── ThingsBoard gateway format ──
            if json_obj is not None and isinstance(json_obj, dict) and _is_thingsboard_format(json_obj):
                self._handle_thingsboard(json_obj)
                return

            # ── Standard per-tag processing ──
            for tag in tags:
                raw_value = None
                if json_obj is not None and isinstance(json_obj, dict) and tag.mqtt_json_path:
                    raw_value = _resolve_json_path(json_obj, tag.mqtt_json_path)
                elif json_obj is not None and isinstance(json_obj, (int, float)):
                    raw_value = json_obj
                else:
                    try:
                        raw_value = float(payload_str)
                    except ValueError:
                        raw_value = payload_str

                live = _process_tag_value(self.device_id, tag, raw_value)
                if live is not None:
                    self._live_values[tag.id] = live

        except Exception as e:
            logger.error(f"MQTT message error on {msg.topic}: {e}")

    def _handle_thingsboard(self, json_obj: dict):
        """Parse ThingsBoard telemetry JSON and route values.

        If the current device name appears as a key, process its data.
        Otherwise skip silently (gateway session handles routing).
        """
        device_data = json_obj.get(self.device_name)
        if device_data is None:
            # Also try case-insensitive / trimmed match
            for key in json_obj:
                if key.strip().lower() == self.device_name.strip().lower():
                    device_data = json_obj[key]
                    break
        if device_data is None:
            return  # Not for this device

        self._process_tb_batches(device_data)

    def _process_tb_batches(self, batches: list):
        """Process a list of ThingsBoard telemetry batches."""
        # Build tag name → tag map
        db = SessionLocal()
        try:
            tags = db.query(DeviceTag).filter(
                DeviceTag.device_id == self.device_id,
                DeviceTag.enabled == True,
            ).all()
        finally:
            db.close()

        tag_by_name = {t.name: t for t in tags}
        # Also match mqtt_json_path as alias (some users configure path as tag key)
        tag_by_alias = {}
        for t in tags:
            if t.mqtt_json_path:
                tag_by_alias[t.mqtt_json_path] = t

        for batch in batches:
            if not isinstance(batch, dict):
                continue
            ts_ms = batch.get("ts")
            values = batch.get("values", {})
            ts_dt = _ts_to_datetime(ts_ms) if ts_ms else datetime.utcnow()

            for key, raw_value in values.items():
                tag = tag_by_name.get(key) or tag_by_alias.get(key)
                if tag is None:
                    continue
                live = _process_tag_value(self.device_id, tag, raw_value, ts_dt)
                if live is not None:
                    self._live_values[tag.id] = live

    def _publish_loop(self):
        while not self._stop_event.is_set():
            if self._connected and self._live_values:
                payload = {
                    "device_id": self.device_id,
                    "device_name": self.device_name,
                    "timestamp": datetime.utcnow().isoformat(),
                    "values": {},
                }
                db = SessionLocal()
                try:
                    for tag_id, val in self._live_values.items():
                        tag = db.query(DeviceTag).filter(DeviceTag.id == tag_id).first()
                        key = tag.name if tag else str(tag_id)
                        payload["values"][key] = val.get("value")
                finally:
                    db.close()

                self._client.publish(
                    self._publish_topic,
                    json.dumps(payload),
                    qos=self._publish_qos,
                )
            self._stop_event.wait(self._publish_interval)

    def _update_status(self, status: str, error: Optional[str]):
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == self.device_id).first()
            if device:
                device.status = status
                device.last_error = error
                device.last_poll_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


# ──────────────────────────────────────────────
#  ThingsBoard Gateway session
# ──────────────────────────────────────────────

class MqttGatewaySession:
    """Single MQTT connection acting as a ThingsBoard gateway.

    One connection, one topic, routes incoming telemetry to
    multiple platform devices by matching JSON key → device name.
    """

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

        # Publish config from gateway device
        self._publish_enabled = gateway_device.mqtt_publish_enabled
        self._publish_topic = gateway_device.mqtt_publish_topic
        self._publish_qos = gateway_device.mqtt_publish_qos or 0
        self._publish_interval = gateway_device.mqtt_publish_interval or 5.0

        # Subscribe topic (gateway device's topic_prefix is the shared topic)
        self._subscribe_topic = gateway_device.mqtt_topic_prefix or "v1/gateway/telemetry"

        # Managed devices: name → {device, tags, live_values}
        self._managed: dict[str, dict] = {}
        for dev in managed_devices:
            db = SessionLocal()
            try:
                tags = db.query(DeviceTag).filter(
                    DeviceTag.device_id == dev.id, DeviceTag.enabled == True
                ).all()
            finally:
                db.close()
            self._managed[dev.name.strip().lower()] = {
                "device": dev,
                "tags": tags,
                "tag_by_name": {t.name: t for t in tags},
                "live_values": {},
            }

        self._client: Optional[mqtt.Client] = None
        self._stop_event = threading.Event()
        self._connected = False
        self._publish_thread: Optional[threading.Thread] = None

    def start(self):
        self._client = mqtt.Client(
            client_id=self._client_id,
            protocol=mqtt.MQTTv311,
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
            logger.info(
                f"TB Gateway '{self._gateway_name}' connecting to {self._broker}:{self._port}, "
                f"subscribing to '{self._subscribe_topic}', managing {len(self._managed)} devices"
            )
        except Exception as e:
            logger.error(f"TB Gateway connect error: {e}")
            self._update_gateway_status("error", str(e))

        if self._publish_enabled and self._publish_topic:
            self._publish_thread = threading.Thread(
                target=self._publish_loop, daemon=True, name=f"tb-gw-pub-{self._gateway_id}")
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
        """Write via ThingsBoard gateway RPC/attributes topic."""
        if not self._client or not self._connected:
            return False
        # Publish to gateway's shared publish topic as a set command
        topic = tag.mqtt_publish_topic or self._publish_topic or f"v1/gateway/telemetry"
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
            self._update_gateway_status("online", None)
            client.subscribe(self._subscribe_topic, qos=1)
            logger.info(f"TB Gateway connected, subscribed to '{self._subscribe_topic}'")
            # Mark all managed devices online
            for entry in self._managed.values():
                self._update_device_status(entry["device"].id, "online", None)
        else:
            logger.error(f"TB Gateway connect failed: rc={rc}")
            self._update_gateway_status("error", f"rc={rc}")

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self._connected = False
        if rc != 0:
            logger.warning(f"TB Gateway disconnected: rc={rc}")
            self._update_gateway_status("offline", "connection lost")

    def _on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode("utf-8", errors="replace")
            json_obj = json.loads(payload_str)
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"TB Gateway: non-JSON payload ignored: {e}")
            return

        if not isinstance(json_obj, dict):
            return

        # Route each device key
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
                ts_dt = _ts_to_datetime(ts_ms) if ts_ms else datetime.utcnow()

                for key, raw_value in values.items():
                    tag = tags.get(key)
                    if tag is None:
                        continue
                    result = _process_tag_value(dev.id, tag, raw_value, ts_dt)
                    if result is not None:
                        live[tag.id] = result

        # Update gateway device last_poll
        self._update_gateway_status("online", None)

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
                        self._client.publish(
                            self._publish_topic,
                            json.dumps(msg),
                            qos=self._publish_qos,
                        )
            self._stop_event.wait(self._publish_interval)

    def _update_gateway_status(self, status: str, error: Optional[str]):
        db = SessionLocal()
        try:
            dev = db.query(Device).filter(Device.id == self._gateway_id).first()
            if dev:
                dev.status = status
                dev.last_error = error
                dev.last_poll_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _update_device_status(self, device_id: int, status: str, error: Optional[str]):
        db = SessionLocal()
        try:
            dev = db.query(Device).filter(Device.id == device_id).first()
            if dev:
                dev.status = status
                dev.last_error = error
                dev.last_poll_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


# ──────────────────────────────────────────────
#  Global MQTT engine
# ──────────────────────────────────────────────

class MqttEngine:
    """Manages all MQTT sessions (standard + ThingsBoard gateway)."""

    def __init__(self):
        self._sessions: dict[int, MqttDeviceSession] = {}      # standard
        self._gateways: dict[int, MqttGatewaySession] = {}      # TB gateway
        self._device_to_gateway: dict[int, int] = {}            # device_id → gateway_device_id
        self._lock = threading.Lock()

    def start(self):
        logger.info("MQTT engine starting...")
        db = SessionLocal()
        try:
            devices = db.query(Device).filter(
                Device.protocol == ProtocolType.MQTT,
                Device.enabled == True,
            ).all()

            # Split: gateway devices vs standard devices
            gateway_devices = []
            standard_devices = []
            for d in devices:
                if d.mqtt_payload_format == MqttPayloadFormat.THINGSBOARD and d.mqtt_is_gateway:
                    gateway_devices.append(d)
                else:
                    standard_devices.append(d)

            # For each gateway, find its managed devices (same broker, TB format, not gateway itself)
            for gw in gateway_devices:
                managed = [
                    d for d in devices
                    if d.id != gw.id
                    and d.mqtt_broker == gw.mqtt_broker
                    and d.mqtt_payload_format == MqttPayloadFormat.THINGSBOARD
                    and not d.mqtt_is_gateway
                ]
                session = MqttGatewaySession(gw, managed)
                session.start()
                self._gateways[gw.id] = session
                for md in managed:
                    self._device_to_gateway[md.id] = gw.id

            # Start standard sessions (skip devices already managed by a gateway)
            for d in standard_devices:
                if d.id not in self._device_to_gateway:
                    self._start_standard(d)
        finally:
            db.close()

    def stop(self):
        logger.info("MQTT engine stopping...")
        for s in self._sessions.values():
            s.stop()
        for s in self._gateways.values():
            s.stop()
        self._sessions.clear()
        self._gateways.clear()
        self._device_to_gateway.clear()

    def reload_device(self, device_id: int):
        # Stop old session
        self._sessions.pop(device_id, None)
        gw_id = self._device_to_gateway.pop(device_id, None)
        if gw_id and gw_id in self._gateways:
            self._gateways[gw_id].stop()
            del self._gateways[gw_id]

        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device and device.enabled and device.protocol == ProtocolType.MQTT:
                if device.mqtt_payload_format == MqttPayloadFormat.THINGSBOARD and device.mqtt_is_gateway:
                    managed = [
                        d for d in db.query(Device).filter(
                            Device.protocol == ProtocolType.MQTT,
                            Device.enabled == True,
                            Device.mqtt_payload_format == MqttPayloadFormat.THINGSBOARD,
                            Device.mqtt_is_gateway == False,
                        ).all()
                        if d.mqtt_broker == device.mqtt_broker
                    ]
                    session = MqttGatewaySession(device, managed)
                    session.start()
                    self._gateways[device.id] = session
                else:
                    self._start_standard(device)
        finally:
            db.close()

    def _start_standard(self, device: Device):
        with self._lock:
            if device.id in self._sessions:
                return
            tags = [t for t in device.tags if t.enabled]
            session = MqttDeviceSession(device)
            session.start(tags)
            self._sessions[device.id] = session
            logger.info(f"MQTT session started for device '{device.name}'")

    def write_value(self, device_id: int, tag: DeviceTag, value) -> bool:
        # Check if managed by gateway
        gw_id = self._device_to_gateway.get(device_id)
        if gw_id and gw_id in self._gateways:
            return self._gateways[gw_id].write_value(device_id, tag, value)
        session = self._sessions.get(device_id)
        if session:
            return session.write_value(tag, value)
        return False

    def get_live_values(self, device_id: int) -> dict:
        gw_id = self._device_to_gateway.get(device_id)
        if gw_id and gw_id in self._gateways:
            return self._gateways[gw_id].get_live_values(device_id)
        session = self._sessions.get(device_id)
        if session:
            return session.get_live_values()
        return {}


# Global instance
mqtt_engine = MqttEngine()
