"""Device-level MQTT publish service.

Any device (Modbus TCP/RTU, MQTT, OPC-UA) with mqtt_publish_enabled=True
will periodically publish its live values to the configured MQTT topic.

This is separate from:
  - DataForwardService (rule-based, cross-device aggregation)
  - MqttDeviceSession (protocol=Mqtt device subscription)

Lifecycle:
  - start(): scans DB for enabled devices, starts per-device publish threads
  - stop(): stops all threads, releases pool connections
  - reload_device(device_id): hot-reload after config change
"""
import json
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from app.engine.mqtt_connection_pool import mqtt_pool
from app.engine.mqtt_preset_renderer import preset_renderer


@dataclass
class DevicePublishStatus:
    """Per-device publish runtime status."""
    device_id: int
    device_name: str = ""
    protocol: str = ""
    broker: str = ""
    port: int = 1883
    topic: str = ""
    mode: str = "standard"
    interval: float = 5.0
    running: bool = False
    connected: bool = False
    publish_count: int = 0
    publish_fail_count: int = 0
    last_publish_time: Optional[str] = None
    last_publish_ok: Optional[bool] = None
    last_error: Optional[str] = None
    last_payload_preview: Optional[str] = None  # truncated preview


class DevicePublishService:
    """Per-device MQTT publish — works for ALL protocols."""

    MAX_PREVIEW_LEN = 500

    def __init__(self):
        self._devices: dict[int, dict] = {}  # device_id -> {pool_key, stop_event, thread, config}
        self._status: dict[int, DevicePublishStatus] = {}
        self._lock = threading.Lock()
        self._started = False

    # ────────────── Lifecycle ──────────────

    def start(self):
        if self._started:
            return
        self._started = True
        self._load_devices()
        logger.info(f"DevicePublishService started with {len(self._devices)} devices")

    def stop(self):
        self._started = False
        with self._lock:
            device_ids = list(self._devices.keys())
        for did in device_ids:
            self._stop_device(did)
        logger.info("DevicePublishService stopped")

    def reload_device(self, device_id: int):
        """Hot-reload a device: stop old, re-read config from DB."""
        self._stop_device(device_id)
        if not self._started:
            return
        self._start_device(device_id)

    def remove_device(self, device_id: int):
        """Stop and remove a device (after deletion or publish disabled)."""
        self._stop_device(device_id)
        with self._lock:
            self._status.pop(device_id, None)

    # ────────────── Status API ──────────────

    def get_status(self) -> list[dict]:
        """Return publish status for all known devices (including recently stopped)."""
        with self._lock:
            result = []
            for did, s in self._status.items():
                result.append({
                    "device_id": s.device_id,
                    "device_name": s.device_name,
                    "protocol": s.protocol,
                    "broker": s.broker,
                    "port": s.port,
                    "topic": s.topic,
                    "mode": s.mode,
                    "interval": s.interval,
                    "running": s.running,
                    "connected": s.connected,
                    "publish_count": s.publish_count,
                    "publish_fail_count": s.publish_fail_count,
                    "last_publish_time": s.last_publish_time,
                    "last_publish_ok": s.last_publish_ok,
                    "last_error": s.last_error,
                    "last_payload_preview": s.last_payload_preview,
                })
            return result

    def trigger(self, device_id: int) -> bool:
        """Manually trigger one publish cycle for a device. Returns True if published."""
        with self._lock:
            entry = self._devices.get(device_id)

        if not entry:
            return False

        config = entry["config"]
        pool_key = entry["pool_key"]
        mode = entry["mode"]
        try:
            self._publish_one(device_id, config, pool_key, mode)
            return True
        except Exception as e:
            logger.error(f"DevicePublish trigger error device={device_id}: {e}")
            with self._lock:
                s = self._status.get(device_id)
                if s:
                    s.last_error = str(e)
            return False

    # ────────────── Internal ──────────────

    def _load_devices(self):
        from app.core.database import SessionLocal
        from app.models.device import Device

        db = SessionLocal()
        try:
            devices = db.query(Device).filter(
                Device.enabled == True,
                Device.mqtt_publish_enabled == True,
            ).all()
        finally:
            db.close()

        for d in devices:
            self._start_device(d.id, config=d)

    def _start_device(self, device_id: int, config=None):
        from app.core.database import SessionLocal
        from app.models.device import Device

        if not config:
            db = SessionLocal()
            try:
                config = db.query(Device).filter(Device.id == device_id).first()
            finally:
                db.close()

        if not config or not config.enabled or not config.mqtt_publish_enabled:
            return

        # Extract publish config from device
        broker = config.mqtt_broker or ""
        port = config.mqtt_port or 1883
        username = config.mqtt_username or ""
        password = config.mqtt_password or ""

        # Determine preset mode from payload_format
        payload_format = config.mqtt_payload_format or "json"
        if payload_format == "thingsboard":
            if config.mqtt_is_gateway:
                mode = "thingsboard_gateway"
            else:
                mode = "thingsboard_device"
                # ThingsBoard device mode: token as username
                username = config.mqtt_username  # token
                password = ""
        else:
            mode = "standard"

        if not broker:
            logger.warning(f"DevicePublish: device {device_id} has no mqtt_broker, skipping")
            return

        pool_key, _ = mqtt_pool.acquire(
            broker=broker,
            port=port,
            username=username,
            password=password,
            client_id=f"devpub_{device_id}",
            use_tls=config.mqtt_use_tls or False,
            ca_cert=config.mqtt_ca_cert or "",
        )

        stop_event = threading.Event()
        entry = {
            "config": config,
            "stop_event": stop_event,
            "pool_key": pool_key,
            "mode": mode,
        }

        with self._lock:
            self._devices[device_id] = entry
            # Init status
            s = self._status.get(device_id)
            if not s:
                s = DevicePublishStatus(device_id=device_id)
                self._status[device_id] = s
            s.device_name = config.name
            s.protocol = config.protocol
            s.broker = broker
            s.port = port
            s.topic = config.mqtt_publish_topic or ""
            s.mode = mode
            s.interval = config.mqtt_publish_interval or 5.0
            s.running = True
            s.connected = False  # will be updated on first publish

        interval = config.mqtt_publish_interval or 5.0

        thread = threading.Thread(
            target=self._publish_loop,
            args=(device_id,),
            daemon=True,
            name=f"device-pub-{device_id}",
        )
        entry["thread"] = thread
        thread.start()

        logger.info(
            f"DevicePublish: started device '{config.name}' (id={device_id}, "
            f"mode={mode}, interval={interval}s)"
        )

    def _stop_device(self, device_id: int):
        with self._lock:
            entry = self._devices.pop(device_id, None)
            s = self._status.get(device_id)

        if not entry:
            return

        entry["stop_event"].set()
        pool_key = entry.get("pool_key")
        if pool_key:
            mqtt_pool.release(pool_key)

        if s:
            s.running = False
            s.connected = False

        logger.info(f"DevicePublish: stopped device id={device_id}")

    # ────────────── Publish Loop ──────────────

    def _publish_loop(self, device_id: int):
        with self._lock:
            entry = self._devices.get(device_id)
        if not entry:
            return

        config = entry["config"]
        stop_event = entry["stop_event"]
        pool_key = entry["pool_key"]
        mode = entry["mode"]
        interval = config.mqtt_publish_interval or 5.0

        while not stop_event.is_set():
            try:
                self._publish_one(device_id, config, pool_key, mode)
            except Exception as e:
                logger.error(f"DevicePublish: error device={device_id}: {e}")
                with self._lock:
                    s = self._status.get(device_id)
                    if s:
                        s.last_error = str(e)
            stop_event.wait(interval)

    def _publish_one(self, device_id: int, config, pool_key: str, mode: str):
        """Fetch live values for this device and publish."""
        from app.engine.protocol_router import protocol_router

        # Get live values from the appropriate engine
        live = protocol_router.get_live_values(device_id)
        if not live:
            with self._lock:
                s = self._status.get(device_id)
                if s:
                    s.last_error = "No live data available"
            return

        # Build {tag_name: value} map
        from app.core.database import SessionLocal
        from app.models.device import DeviceTag

        db = SessionLocal()
        try:
            values = {}
            for tag_id, val in live.items():
                tag = db.query(DeviceTag).filter(DeviceTag.id == tag_id).first()
                tag_name = tag.name if tag else str(tag_id)
                values[tag_name] = val.get("value")
        finally:
            db.close()

        if not values:
            with self._lock:
                s = self._status.get(device_id)
                if s:
                    s.last_error = "All tag values are None"
            return

        # Build telemetry data
        now = datetime.now(timezone.utc)
        data = preset_renderer.build_telemetry_data(
            device_id=device_id,
            device_name=config.name,
            values=values,
        )

        # Build context for template rendering
        context = {
            "device_id": device_id,
            "device_name": config.name,
            "timestamp": now.isoformat(),
            "timestamp_ms": str(int(now.timestamp() * 1000)),
            "values_json": json.dumps(values, default=str),
        }

        # Render topic
        topic_template = config.mqtt_publish_topic or ""
        topic = preset_renderer.render_topic(mode, topic_template, context)

        # Render payload
        custom_template = config.mqtt_payload_template or ""
        payload = preset_renderer.render_payload(
            preset_mode=mode,
            data=data,
            custom_template=custom_template if custom_template else None,
            context=context,
        )

        # Publish
        ok = mqtt_pool.publish(pool_key, topic, payload, qos=config.mqtt_publish_qos or 0)

        # Update status
        now_str = now.isoformat()
        preview = payload if len(payload) <= self.MAX_PREVIEW_LEN else payload[:self.MAX_PREVIEW_LEN] + "..."
        with self._lock:
            s = self._status.get(device_id)
            if s:
                s.last_publish_time = now_str
                s.last_publish_ok = ok
                s.topic = topic
                if ok:
                    s.publish_count += 1
                    s.last_error = None
                    s.connected = True
                else:
                    s.publish_fail_count += 1
                    s.last_error = "Publish failed (broker may be disconnected)"
                    s.connected = False
                s.last_payload_preview = preview

        if not ok:
            logger.warning(f"DevicePublish: publish failed device={device_id} topic={topic}")


# Global singleton
device_publish_service = DevicePublishService()
