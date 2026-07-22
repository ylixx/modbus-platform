"""MQTT utilities — helpers shared by standard and gateway sessions."""
import json
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag
from app.models.history import TagHistory


class MqttPayloadFormat:
    PLAIN = "plain"
    JSON = "json"
    THINGSBOARD = "thingsboard"


def resolve_json_path(obj: dict, path: str):
    """Dot-notation: 'a.b.c' → obj['a']['b']['c']."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def cast_value(raw, target_type: str):
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


def ts_to_datetime(ts_ms: int) -> datetime:
    """Convert epoch milliseconds to UTC datetime."""
    try:
        return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    except (OSError, ValueError, OverflowError):
        return datetime.now(timezone.utc)


def is_thingsboard_format(obj: dict) -> bool:
    """Heuristic: top-level values are lists of {ts, values} dicts."""
    if not isinstance(obj, dict) or not obj:
        return False
    for v in obj.values():
        if isinstance(v, list) and len(v) > 0:
            first = v[0]
            if isinstance(first, dict) and "ts" in first and "values" in first:
                return True
    return False


def process_tag_value(device_id: int, tag: DeviceTag, raw_value, ts: Optional[datetime] = None):
    """Cast, scale, script process, store history, evaluate alarms for a single tag value."""
    casted = cast_value(raw_value, tag.mqtt_value_type or "float64")
    if casted is None:
        return None

    processed = casted * tag.scale_factor + tag.offset
    if tag.decimal_places is not None and isinstance(processed, float):
        processed = round(processed, tag.decimal_places)

    quality = "good"

    # Script processing
    if tag.script_id:
        db = SessionLocal()
        try:
            from app.models.script import Script
            from app.engine.script_engine import script_engine
            script = db.query(Script).filter(Script.id == tag.script_id, Script.enabled == True).first()
            if script:
                recent = db.query(TagHistory.value).filter(
                    TagHistory.device_id == device_id, TagHistory.tag_id == tag.id,
                ).order_by(TagHistory.recorded_at.desc()).limit(script.max_history).all()
                history = [r[0] for r in reversed(recent)]
                tag_cfg = {"name": tag.name, "unit": tag.unit, "scale_factor": tag.scale_factor, "offset": tag.offset, "params": {}}
                try:
                    tag_cfg["params"] = json.loads(script.default_params) if script.default_params else {}
                except Exception:
                    pass
                ctx = {"device_id": device_id, "tag_id": tag.id, "timestamp": datetime.now(timezone.utc).isoformat()}
                result, quality, _ = script_engine.execute(script.id, script.code, processed, history, tag_cfg, ctx, script.timeout_ms)
                if result is not None:
                    processed = result
        finally:
            db.close()

    now = ts or datetime.now(timezone.utc)
    live = {"value": processed, "raw_value": str(casted), "quality": quality, "time": now.isoformat()}

    # History
    db = SessionLocal()
    try:
        db.add(TagHistory(device_id=device_id, tag_id=tag.id, tag_name=tag.name, value=processed, raw_value=str(casted), quality=quality))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    # Alarm
    from app.services.alarm_service import alarm_service
    alarm_service.evaluate(device_id, tag.id, tag.name, processed)

    return live


def update_device_status(device_id: int, status: str, error: Optional[str]):
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.id == device_id).first()
        if device:
            device.status = status
            device.last_error = error
            device.last_poll_at = datetime.now(timezone.utc)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
