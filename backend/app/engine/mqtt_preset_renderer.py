"""Unified MQTT preset renderer.

Renders topic and payload for three preset modes:
  - standard:         User-defined topic/payload templates with placeholders
  - thingsboard_device: TB device access  → v1/devices/me/telemetry + telemetry format
  - thingsboard_gateway: TB gateway access → v1/gateway/telemetry + aggregated format

Used by:
  - alarm_mqtt_publisher.py  (alarm events)
  - data_forward_service.py (telemetry data)
  - mqtt_session._render_payload() (device-level publish)
"""
import json
import time
from datetime import datetime, timezone
from typing import Optional


class MqttPresetRenderer:
    """Stateless renderer — all methods are pure functions."""

    # ── Topic rendering ──

    @staticmethod
    def render_topic(preset_mode: str, custom_topic: str = "", context: Optional[dict] = None) -> str:
        """Render the MQTT topic based on preset mode.

        For ThingsBoard modes, the topic is fixed and custom_topic is ignored.
        For standard mode, placeholder substitution is applied.
        """
        if preset_mode == "thingsboard_device":
            return "v1/devices/me/telemetry"
        if preset_mode == "thingsboard_gateway":
            return "v1/gateway/telemetry"

        # Standard mode: render custom template
        topic = custom_topic or "alarms/default"
        if context:
            for key, val in context.items():
                topic = topic.replace(f"${{{{{key}}}}}", str(val))
        # MQTT topic cannot contain these chars
        topic = topic.replace("\n", "").replace("\r", "").replace("+", "").replace("#", "")
        return topic or "alarms/default"

    # ── Payload rendering ──

    @staticmethod
    def render_payload(
        preset_mode: str,
        data: dict,
        custom_template: str = "",
        context: Optional[dict] = None,
    ) -> bytes:
        """Render the MQTT payload based on preset mode.

        data: dict containing the domain-specific fields.
          For alarm:     alarm_event, alarm_level, alarm_type, alarm_message, trigger_value, ...
          For telemetry: device_name, values (dict), ...

        custom_template: user-defined JSON template (standard mode only).
        context: additional placeholder context for standard template rendering.
        """
        if preset_mode == "thingsboard_device":
            return MqttPresetRenderer._render_tb_device_payload(data)
        if preset_mode == "thingsboard_gateway":
            return MqttPresetRenderer._render_tb_gateway_payload(data)

        # Standard mode
        if custom_template and custom_template.strip():
            return MqttPresetRenderer._render_custom_template(custom_template, data, context)
        else:
            return MqttPresetRenderer._render_default_payload(data)

    # ────────────── ThingsBoard Device ──────────────

    @staticmethod
    def _render_tb_device_payload(data: dict) -> bytes:
        """TB device access: {"ts": ms, "values": {...}}"""
        ts = data.get("ts") or int(time.time() * 1000)
        values = data.get("values", {})
        # If values is empty, use the data itself as telemetry keys
        if not values and "telemetry" in data:
            values = data["telemetry"]
        if not values:
            # Fallback: use all non-meta fields as telemetry
            meta_keys = {"ts", "device_name", "device_id", "event", "preset_mode"}
            values = {k: v for k, v in data.items() if k not in meta_keys and v is not None}

        payload = {"ts": ts, "values": values}
        return json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")

    # ────────────── ThingsBoard Gateway ──────────────

    @staticmethod
    def _render_tb_gateway_payload(data: dict) -> bytes:
        """TB gateway access: { "device_name": [{ "ts": ms, "values": {...} }] }"""
        ts = data.get("ts") or int(time.time() * 1000)
        device_name = data.get("device_name", "unknown_device")
        values = data.get("values", {})
        if not values and "telemetry" in data:
            values = data["telemetry"]
        if not values:
            meta_keys = {"ts", "device_name", "device_id", "event", "preset_mode"}
            values = {k: v for k, v in data.items() if k not in meta_keys and v is not None}

        gateway_payload = {
            device_name: [
                {"ts": ts, "values": values}
            ]
        }
        return json.dumps(gateway_payload, ensure_ascii=False, default=str).encode("utf-8")

    # ────────────── Standard Custom Template ──────────────

    @staticmethod
    def _render_custom_template(template: str, data: dict, context: Optional[dict] = None) -> bytes:
        """Render user-defined template with ${key} placeholder substitution."""
        result = template
        # Merge data and context for placeholder resolution
        all_vars = dict(data)
        if context:
            all_vars.update(context)

        for key, val in all_vars.items():
            result = result.replace(f"${{{{{key}}}}}", str(val))
        return result.encode("utf-8")

    # ────────────── Default Payload ──────────────

    @staticmethod
    def _render_default_payload(data: dict) -> bytes:
        """Default JSON payload — just dump the data dict as-is with a published_at timestamp."""
        payload = dict(data)
        if "published_at" not in payload:
            payload["published_at"] = datetime.now(timezone.utc).isoformat()
        return json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")

    # ────────────── Convenience: build alarm context ──────────────

    @staticmethod
    def build_alarm_context(event: str, alarm_data: dict) -> dict:
        """Build placeholder context dict for alarm events."""
        return {
            "device_name": alarm_data.get("device_name", ""),
            "device_id": str(alarm_data.get("device_id", "")),
            "tag_name": alarm_data.get("tag_name", ""),
            "tag_id": str(alarm_data.get("tag_id", "")),
            "alarm_type": alarm_data.get("alarm_type", ""),
            "alarm_level": alarm_data.get("alarm_level", ""),
            "alarm_message": alarm_data.get("alarm_message", ""),
            "trigger_value": str(alarm_data.get("trigger_value", "")),
            "threshold_value": str(alarm_data.get("threshold_value", "")),
            "status": event,
            "triggered_at": alarm_data.get("triggered_at", ""),
        }

    @staticmethod
    def build_alarm_data(event: str, alarm_data: dict) -> dict:
        """Build the data dict for alarm payload rendering."""
        return {
            "event": event,
            "device_id": alarm_data.get("device_id"),
            "device_name": alarm_data.get("device_name", ""),
            "tag_id": alarm_data.get("tag_id"),
            "tag_name": alarm_data.get("tag_name", ""),
            "alarm_type": alarm_data.get("alarm_type", ""),
            "alarm_level": alarm_data.get("alarm_level", ""),
            "alarm_message": alarm_data.get("alarm_message", ""),
            "trigger_value": alarm_data.get("trigger_value"),
            "threshold_value": alarm_data.get("threshold_value"),
            "triggered_at": alarm_data.get("triggered_at", ""),
        }

    # ────────────── Convenience: build telemetry context ──────────────

    @staticmethod
    def build_telemetry_data(device_id: int, device_name: str, values: dict, ts_ms: Optional[int] = None) -> dict:
        """Build the data dict for telemetry payload rendering."""
        return {
            "ts": ts_ms or int(time.time() * 1000),
            "device_id": device_id,
            "device_name": device_name,
            "values": values,
        }

    @staticmethod
    def build_telemetry_context(device_id: int, device_name: str, values_simple: dict,
                                  values_detail: dict, timestamp: str, timestamp_ms: int) -> dict:
        """Build placeholder context for custom telemetry templates."""
        first_key = next(iter(values_simple)) if values_simple else ""
        first_val = values_simple.get(first_key) if first_key else None
        return {
            "device_id": str(device_id),
            "device_name": device_name,
            "timestamp": timestamp,
            "timestamp_ms": str(timestamp_ms),
            "values_json": json.dumps(values_simple),
            "values_detail": json.dumps(values_detail),
            "value": json.dumps(first_val) if first_val is not None else "null",
            "tag_name": first_key,
        }


# Global singleton (stateless, but convenient import target)
preset_renderer = MqttPresetRenderer()
