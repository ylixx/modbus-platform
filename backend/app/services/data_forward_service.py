"""Data forward service — push collected telemetry to external MQTT brokers.

Reads live values from the protocol engines, applies per-rule filters and
aggregation, then publishes via MqttPresetRenderer + MqttConnectionPool.

Lifecycle:
  - start(): loads enabled rules from DB, starts per-rule publish threads
  - stop(): stops all threads, releases pool connections
  - reload_rule(): hot-reload a single rule after config change
"""
import json
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from app.engine.mqtt_connection_pool import mqtt_pool
from app.engine.mqtt_preset_renderer import preset_renderer


class DataForwardService:
    """Manages all data forward rule executions."""

    def __init__(self):
        self._rules: dict[int, dict] = {}  # rule_id -> {config, stop_event, thread, pool_key}
        self._lock = threading.Lock()
        self._started = False

    # ────────────── Lifecycle ──────────────

    def start(self):
        """Load enabled rules and start publish loops."""
        if self._started:
            return
        self._started = True
        self._load_rules()
        logger.info(f"DataForwardService started with {len(self._rules)} rules")

    def stop(self):
        """Stop all publish loops and release pool connections."""
        self._started = False
        with self._lock:
            rule_ids = list(self._rules.keys())

        for rule_id in rule_ids:
            self._stop_rule(rule_id)

        logger.info("DataForwardService stopped")

    def reload_rule(self, rule_id: int):
        """Hot-reload a rule: stop the old thread, re-read from DB."""
        self._stop_rule(rule_id)
        if not self._started:
            return
        self._start_rule(rule_id)

    def remove_rule(self, rule_id: int):
        """Stop and remove a rule (after deletion)."""
        self._stop_rule(rule_id)

    # ────────────── Internal ──────────────

    def _load_rules(self):
        from app.core.database import SessionLocal
        from app.models.data_forward import DataForwardRule

        db = SessionLocal()
        try:
            rules = db.query(DataForwardRule).filter(DataForwardRule.enabled == True).all()
        finally:
            db.close()

        for rule in rules:
            self._start_rule(rule.id, config=rule)

    def _start_rule(self, rule_id: int, config=None):
        if not config:
            from app.core.database import SessionLocal
            from app.models.data_forward import DataForwardRule
            db = SessionLocal()
            try:
                config = db.query(DataForwardRule).filter(DataForwardRule.id == rule_id).first()
            finally:
                db.close()

        if not config or not config.enabled:
            return

        mode = config.preset_mode or "standard"
        broker = config.broker
        port = config.port or 1883
        username = config.username or ""
        password = config.password or ""

        # ThingsBoard: token as username
        if mode == "thingsboard_device":
            token = config.tb_device_token or config.username
            username = token
            password = ""
        elif mode == "thingsboard_gateway":
            token = config.tb_device_token or config.username
            username = token
            password = ""

        # Acquire pool connection
        pool_key, _ = mqtt_pool.acquire(
            broker=broker,
            port=port,
            username=username,
            password=password,
            client_id=f"forward_{rule_id}",
            use_tls=config.use_tls,
        )

        stop_event = threading.Event()

        entry = {
            "config": config,
            "stop_event": stop_event,
            "pool_key": pool_key,
        }

        with self._lock:
            self._rules[rule_id] = entry

        thread = threading.Thread(
            target=self._publish_loop,
            args=(rule_id,),
            daemon=True,
            name=f"forward-pub-{rule_id}",
        )
        entry["thread"] = thread
        thread.start()

        logger.info(f"DataForward: started rule '{config.name}' (id={rule_id}, mode={mode})")

    def _stop_rule(self, rule_id: int):
        with self._lock:
            entry = self._rules.pop(rule_id, None)

        if not entry:
            return

        entry["stop_event"].set()
        pool_key = entry.get("pool_key")
        if pool_key:
            mqtt_pool.release(pool_key)

        logger.info(f"DataForward: stopped rule id={rule_id}")

    # ────────────── Publish Loop ──────────────

    def _publish_loop(self, rule_id: int):
        with self._lock:
            entry = self._rules.get(rule_id)
        if not entry:
            return

        config = entry["config"]
        stop_event = entry["stop_event"]
        pool_key = entry["pool_key"]
        interval = config.publish_interval or 10.0

        while not stop_event.is_set():
            try:
                self._publish_one_cycle(config, pool_key)
            except Exception as e:
                logger.error(f"DataForward: publish error rule={rule_id}: {e}")
            stop_event.wait(interval)

    def _publish_one_cycle(self, config, pool_key: str):
        """Fetch live values, apply filters, aggregate, and publish."""
        from app.core.database import SessionLocal
        from app.models.device import Device, DeviceTag
        from app.engine.protocol_router import protocol_router

        mode = config.preset_mode or "standard"
        aggregate = config.aggregate_mode or "per_device"

        # Parse filters
        device_filter = set()
        if config.device_ids:
            try:
                device_filter = set(json.loads(config.device_ids))
            except (json.JSONDecodeError, TypeError):
                pass

        tag_filter = set()
        if config.tag_ids:
            try:
                tag_filter = set(json.loads(config.tag_ids))
            except (json.JSONDecodeError, TypeError):
                pass

        # Collect live values from all engines
        db = SessionLocal()
        try:
            devices = db.query(Device).filter(Device.enabled == True).all()
            if device_filter:
                devices = [d for d in devices if d.id in device_filter]

            # Per-device values: {device_id: {tag_name: value}}
            device_values = {}
            for dev in devices:
                live = protocol_router.get_live_values(dev.id)
                if not live:
                    continue
                values = {}
                for tag_id, val in live.items():
                    if tag_filter and tag_id not in tag_filter:
                        continue
                    tag = db.query(DeviceTag).filter(DeviceTag.id == tag_id).first()
                    tag_name = tag.name if tag else str(tag_id)
                    values[tag_name] = val.get("value")
                if values:
                    device_values[dev.id] = {
                        "name": dev.name,
                        "values": values,
                    }
        finally:
            db.close()

        if not device_values:
            return

        # Dispatch by aggregate mode
        if aggregate == "single":
            # Each tag in a separate message
            for dev_id, dev_data in device_values.items():
                for tag_name, value in dev_data["values"].items():
                    self._do_publish(
                        pool_key, config, mode,
                        device_name=dev_data["name"],
                        tag_name=tag_name,
                        values={tag_name: value},
                    )
        elif aggregate == "all_in_one":
            # All devices aggregated into one message
            all_values = {}
            for dev_id, dev_data in device_values.items():
                all_values[dev_data["name"]] = dev_data["values"]

            if mode == "thingsboard_gateway":
                # TB gateway: each device as a sub-device
                for dev_name, vals in all_values.items():
                    self._do_publish(
                        pool_key, config, mode,
                        device_name=dev_name,
                        values=vals,
                    )
            else:
                self._do_publish(
                    pool_key, config, mode,
                    device_name="all_devices",
                    values={"devices": all_values},
                )
        else:
            # per_device (default): each device in a separate message
            for dev_id, dev_data in device_values.items():
                self._do_publish(
                    pool_key, config, mode,
                    device_name=dev_data["name"],
                    values=dev_data["values"],
                )

    def _do_publish(self, pool_key: str, config, mode: str,
                     device_name: str, values: dict, tag_name: str = ""):
        """Render and publish a single message."""
        # Build telemetry data
        data = preset_renderer.build_telemetry_data(
            device_id=0,
            device_name=device_name,
            values=values,
        )

        # For ThingsBoard gateway, inject gateway device name
        if mode == "thingsboard_gateway":
            data["device_name"] = config.tb_gateway_name or device_name

        # Build context for template rendering
        now = datetime.now(timezone.utc)
        context = {
            "device_name": device_name,
            "tag_name": tag_name,
            "timestamp": now.isoformat(),
            "timestamp_ms": str(int(now.timestamp() * 1000)),
            "values_json": json.dumps(values, default=str),
        }

        # Render topic and payload
        topic = preset_renderer.render_topic(mode, config.topic_template, context)
        payload = preset_renderer.render_payload(
            preset_mode=mode,
            data=data,
            custom_template=config.payload_template,
            context=context,
        )

        # Publish via pool
        ok = mqtt_pool.publish(pool_key, topic, payload, qos=config.qos or 0)
        if not ok:
            logger.warning(f"DataForward: publish failed rule={config.id} topic={topic}")


# Global singleton
data_forward_service = DataForwardService()
