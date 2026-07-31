"""Alarm MQTT publisher service — uses shared connection pool + preset renderer.

Supports three preset modes (via MqttPresetRenderer):
  - standard:         User-defined topic/payload templates
  - thingsboard_device: TB device access (token auth, v1/devices/me/telemetry)
  - thingsboard_gateway: TB gateway access (v1/gateway/telemetry, aggregated format)

Connections are managed by MqttConnectionPool — same broker/port/username
are automatically shared across device sessions and alarm publishers.
"""
import json
from typing import Optional
from loguru import logger

from app.engine.mqtt_connection_pool import mqtt_pool, MqttConnectionPool
from app.engine.mqtt_preset_renderer import preset_renderer


class AlarmMqttPublisher:
    """Publish alarm events to external MQTT brokers via the shared connection pool."""

    def __init__(self):
        self._pool_keys: dict[int, str] = {}  # config_id -> pool_key

    def publish_alarm(self, event: str, alarm_data: dict):
        """Called when an alarm event occurs (triggered / cleared).

        event: "triggered" | "cleared"
        alarm_data: dict with keys matching template placeholders
        """
        from app.core.database import SessionLocal
        from app.models.alarm_mqtt import AlarmMqttConfig

        db = SessionLocal()
        try:
            configs = db.query(AlarmMqttConfig).filter(AlarmMqttConfig.enabled == True).all()
        finally:
            db.close()

        if not configs:
            return

        for config in configs:
            try:
                self._publish_one(config, event, alarm_data)
            except Exception as e:
                logger.error(f"AlarmMqtt: publish failed for config {config.id} ({config.name}): {e}")

    def _publish_one(self, config, event: str, alarm_data: dict):
        """Check filters and publish a single alarm event to one MQTT config."""
        # ── Common filters ──
        if config.alarm_events:
            try:
                events = json.loads(config.alarm_events)
                if isinstance(events, list) and events and event not in events:
                    return
            except json.JSONDecodeError:
                pass

        if config.alarm_levels:
            try:
                levels = json.loads(config.alarm_levels)
                if isinstance(levels, list) and levels:
                    if alarm_data.get("alarm_level", "") not in levels:
                        return
            except json.JSONDecodeError:
                pass

        if config.device_ids:
            try:
                dev_ids = json.loads(config.device_ids)
                if isinstance(dev_ids, list) and dev_ids:
                    if alarm_data.get("device_id") not in dev_ids:
                        return
            except json.JSONDecodeError:
                pass

        # ── Resolve preset mode ──
        mode = getattr(config, "preset_mode", "standard") or "standard"

        # ── Determine broker credentials ──
        # ThingsBoard modes: use token as username
        broker = config.broker
        port = config.port or 1883
        username = config.username or ""
        password = config.password or ""

        if mode == "thingsboard_device":
            token = config.tb_device_token or config.username
            username = token
            password = ""
        elif mode == "thingsboard_gateway":
            token = config.tb_device_token or config.username
            username = token
            password = ""

        # ── Acquire / reuse pool connection ──
        cfg_id = config.id
        pool_key = self._pool_keys.get(cfg_id)
        if not pool_key:
            pool_key, _ = mqtt_pool.acquire(
                broker=broker,
                port=port,
                username=username,
                password=password,
                client_id=f"alarm_{cfg_id}",
                use_tls=config.use_tls,
            )
            self._pool_keys[cfg_id] = pool_key

        # ── Render topic and payload via preset renderer ──
        context = preset_renderer.build_alarm_context(event, alarm_data)
        data = preset_renderer.build_alarm_data(event, alarm_data)

        # For ThingsBoard gateway, inject device name
        if mode == "thingsboard_gateway":
            data["device_name"] = config.tb_gateway_name or alarm_data.get("device_name", "unknown_device")

        topic = preset_renderer.render_topic(mode, config.topic_template, context)
        payload = preset_renderer.render_payload(
            preset_mode=mode,
            data=data,
            custom_template=config.payload_template,
            context=context,
        )

        # ── Publish ──
        ok = mqtt_pool.publish(pool_key, topic, payload, qos=config.qos or 0)
        if ok:
            logger.info(f"AlarmMqtt: published to {topic} (config={cfg_id}, mode={mode})")
        else:
            logger.warning(f"AlarmMqtt: publish failed config={cfg_id}")

    def cleanup(self, config_id: int):
        """Release pool connection for a deleted/disabled config."""
        pool_key = self._pool_keys.pop(config_id, None)
        if pool_key:
            mqtt_pool.release(pool_key)

    def shutdown(self):
        """Release all pool connections (app shutdown)."""
        for cfg_id, pool_key in self._pool_keys.items():
            mqtt_pool.release(pool_key)
        self._pool_keys.clear()


# Global singleton
alarm_mqtt_publisher = AlarmMqttPublisher()
