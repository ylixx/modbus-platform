"""Configuration export/import API.

Export all platform configuration as a single JSON file:
  - Device groups
  - Devices (without status/live data)
  - Device tags (with script bindings)
  - Alarm rules
  - Scripts
  - SMS contacts and push rules
  - Hierarchy configs
  - Custom widgets

Import: restore from exported JSON.
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.device import Device, DeviceGroup, DeviceTag
from app.models.alarm import AlarmRule
from app.models.sms import SmsContact, SmsPushRule
from app.models.script import Script
from app.models.hierarchy import HierarchyConfig
from app.models.scada import ScadaPage, CustomWidget

router = APIRouter(prefix="/config", tags=["配置导出"])


@router.get("/export")
def export_config(db: Session = Depends(get_db), _: User = Depends(require_permission("config.read"))):
    """Export all platform configuration as JSON."""
    data = {
        "version": "1.0.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "device_groups": [],
        "devices": [],
        "tags": [],
        "alarm_rules": [],
        "scripts": [],
        "sms_contacts": [],
        "sms_push_rules": [],
        "hierarchy_configs": [],
        "scada_pages": [],
        "custom_widgets": [],
    }

    # Device groups
    for g in db.query(DeviceGroup).order_by(DeviceGroup.id).all():
        data["device_groups"].append({
            "name": g.name, "description": g.description,
            "parent_id": g.parent_id, "sort_order": g.sort_order,
        })

    # Devices
    for d in db.query(Device).order_by(Device.id).all():
        data["devices"].append({
            "name": d.name, "description": d.description, "protocol": d.protocol,
            "host": d.host, "port": d.port, "slave_id": d.slave_id,
            "timeout": d.timeout, "retries": d.retries, "poll_interval": d.poll_interval,
            "factory": d.factory, "workshop": d.workshop,
            "production_line": d.production_line, "installation": d.installation,
            "longitude": d.longitude, "latitude": d.latitude,
            "mqtt_broker": d.mqtt_broker, "mqtt_port": d.mqtt_port,
            "mqtt_username": d.mqtt_username, "mqtt_client_id": d.mqtt_client_id,
            "mqtt_topic_prefix": d.mqtt_topic_prefix, "mqtt_use_tls": d.mqtt_use_tls,
            "mqtt_payload_format": d.mqtt_payload_format, "mqtt_is_gateway": d.mqtt_is_gateway,
            "mqtt_publish_enabled": d.mqtt_publish_enabled, "mqtt_publish_topic": d.mqtt_publish_topic,
            "mqtt_publish_qos": d.mqtt_publish_qos, "mqtt_publish_interval": d.mqtt_publish_interval,
            "opc_endpoint": d.opc_endpoint, "opc_security_mode": d.opc_security_mode,
            "opc_namespace": d.opc_namespace,
            "group_name": d.group.name if d.group else None,
            "enabled": False,  # imported devices start disabled
        })

    # Tags
    for t in db.query(DeviceTag).order_by(DeviceTag.device_id, DeviceTag.id).all():
        device = db.query(Device).filter(Device.id == t.device_id).first()
        data["tags"].append({
            "device_name": device.name if device else "",
            "name": t.name, "description": t.description, "unit": t.unit,
            "function_code": t.function_code, "address": t.address,
            "data_type": t.data_type, "byte_order": t.byte_order,
            "bit_index": t.bit_index, "register_count": t.register_count,
            "mqtt_topic": t.mqtt_topic, "mqtt_json_path": t.mqtt_json_path,
            "mqtt_value_type": t.mqtt_value_type, "mqtt_publish_topic": t.mqtt_publish_topic,
            "mqtt_retain": t.mqtt_retain,
            "opc_node_id": t.opc_node_id, "opc_node_type": t.opc_node_type,
            "scale_factor": t.scale_factor, "offset": t.offset,
            "decimal_places": t.decimal_places, "writable": t.writable,
            "script_name": t.script_id,  # will resolve by name on import
            "sort_order": t.sort_order, "enabled": t.enabled,
        })

    # Alarm rules
    for r in db.query(AlarmRule).order_by(AlarmRule.id).all():
        device = db.query(Device).filter(Device.id == r.device_id).first()
        tag = db.query(DeviceTag).filter(DeviceTag.id == r.tag_id).first() if r.tag_id else None
        data["alarm_rules"].append({
            "name": r.name, "description": r.description,
            "device_name": device.name if device else "",
            "tag_name": tag.name if tag else None,
            "alarm_type": r.alarm_type, "alarm_level": r.alarm_level,
            "high_limit": r.high_limit, "low_limit": r.low_limit,
            "deadband": r.deadband, "rate_limit": r.rate_limit,
            "status_value": r.status_value, "delay_seconds": r.delay_seconds,
            "auto_clear": r.auto_clear, "enabled": r.enabled, "sms_enabled": r.sms_enabled,
        })

    # Scripts
    for s in db.query(Script).filter(Script.is_template == False).order_by(Script.id).all():
        data["scripts"].append({
            "name": s.name, "description": s.description, "language": s.language,
            "code": s.code, "default_params": s.default_params,
            "timeout_ms": s.timeout_ms, "max_history": s.max_history, "enabled": s.enabled,
        })

    # SMS contacts
    for c in db.query(SmsContact).order_by(SmsContact.id).all():
        data["sms_contacts"].append({
            "name": c.name, "phone": c.phone, "department": c.department, "enabled": c.enabled,
        })

    # SMS push rules
    for r in db.query(SmsPushRule).order_by(SmsPushRule.id).all():
        data["sms_push_rules"].append({
            "name": r.name, "description": r.description,
            "device_ids": r.device_ids, "alarm_levels": r.alarm_levels,
            "time_start": r.time_start, "time_end": r.time_end,
            "contact_ids": r.contact_ids, "enabled": r.enabled,
            "cooldown_minutes": r.cooldown_minutes,
        })

    # Hierarchy configs
    for h in db.query(HierarchyConfig).order_by(HierarchyConfig.id).all():
        data["hierarchy_configs"].append({
            "name": h.name, "description": h.description,
            "levels_json": h.levels_json, "is_default": h.is_default,
        })

    # SCADA pages
    for p in db.query(ScadaPage).order_by(ScadaPage.id).all():
        data["scada_pages"].append({
            "name": p.name, "description": p.description,
            "width": p.width, "height": p.height, "background": p.background,
            "config_json": p.config_json, "device_ids": p.device_ids,
        })

    # Custom widgets
    for w in db.query(CustomWidget).order_by(CustomWidget.id).all():
        data["custom_widgets"].append({
            "name": w.name, "category": w.category, "description": w.description,
            "source_type": w.source_type, "source_data": w.source_data,
            "thumbnail": w.thumbnail, "default_width": w.default_width,
            "default_height": w.default_height, "bindable": w.bindable,
        })

    content = json.dumps(data, ensure_ascii=False, indent=2)
    filename = f"modbus_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_config(
    file: UploadFile = File(...),
    overwrite: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("config.write")),
):
    """Import configuration from JSON file."""
    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON file"}

    stats = {"groups": 0, "devices": 0, "tags": 0, "rules": 0, "scripts": 0, "errors": []}

    try:
        # Device groups
        for g in data.get("device_groups", []):
            existing = db.query(DeviceGroup).filter(DeviceGroup.name == g["name"]).first()
            if existing and not overwrite:
                continue
            if not existing:
                existing = DeviceGroup(name=g["name"])
                db.add(existing)
            existing.description = g.get("description", "")
            existing.sort_order = g.get("sort_order", 0)
            stats["groups"] += 1
        db.flush()

        # Devices
        group_map = {g.name: g.id for g in db.query(DeviceGroup).all()}
        for d in data.get("devices", []):
            existing = db.query(Device).filter(Device.name == d["name"]).first()
            if existing and not overwrite:
                continue
            if not existing:
                existing = Device(name=d["name"])
                db.add(existing)
            for key in ["description", "protocol", "host", "port", "slave_id", "timeout", "retries",
                        "poll_interval", "factory", "workshop", "production_line", "installation",
                        "mqtt_broker", "mqtt_port", "mqtt_username", "mqtt_client_id",
                        "mqtt_topic_prefix", "mqtt_use_tls", "mqtt_payload_format", "mqtt_is_gateway",
                        "mqtt_publish_enabled", "mqtt_publish_topic", "mqtt_publish_qos", "mqtt_publish_interval",
                        "opc_endpoint", "opc_security_mode", "opc_namespace"]:
                if key in d:
                    setattr(existing, key, d[key])
            existing.group_id = group_map.get(d.get("group_name"))
            existing.enabled = d.get("enabled", False)
            stats["devices"] += 1
        db.flush()

        # Tags
        device_map = {d.name: d.id for d in db.query(Device).all()}
        script_map = {s.name: s.id for s in db.query(Script).all()}
        for t in data.get("tags", []):
            device_id = device_map.get(t.get("device_name"))
            if not device_id:
                continue
            existing = db.query(DeviceTag).filter(
                DeviceTag.device_id == device_id, DeviceTag.name == t["name"]
            ).first()
            if existing and not overwrite:
                continue
            if not existing:
                existing = DeviceTag(device_id=device_id, name=t["name"])
                db.add(existing)
            for key in ["description", "unit", "function_code", "address", "data_type", "byte_order",
                        "bit_index", "register_count", "mqtt_topic", "mqtt_json_path", "mqtt_value_type",
                        "mqtt_publish_topic", "mqtt_retain", "opc_node_id", "opc_node_type",
                        "scale_factor", "offset", "decimal_places", "writable", "sort_order", "enabled"]:
                if key in t:
                    setattr(existing, key, t[key])
            # Resolve script
            if t.get("script_name") and isinstance(t["script_name"], str):
                existing.script_id = script_map.get(t["script_name"])
            stats["tags"] += 1
        db.flush()

        # Alarm rules
        for r in data.get("alarm_rules", []):
            device_id = device_map.get(r.get("device_name"))
            if not device_id:
                continue
            existing = db.query(AlarmRule).filter(
                AlarmRule.device_id == device_id, AlarmRule.name == r["name"]
            ).first()
            if existing and not overwrite:
                continue
            if not existing:
                existing = AlarmRule(device_id=device_id, name=r["name"])
                db.add(existing)
            for key in ["description", "alarm_type", "alarm_level", "high_limit", "low_limit",
                        "deadband", "rate_limit", "status_value", "delay_seconds",
                        "auto_clear", "enabled", "sms_enabled"]:
                if key in r:
                    setattr(existing, key, r[key])
            stats["rules"] += 1

        # Scripts
        for s in data.get("scripts", []):
            existing = db.query(Script).filter(Script.name == s["name"]).first()
            if existing and not overwrite:
                continue
            if not existing:
                existing = Script(name=s["name"])
                db.add(existing)
            for key in ["description", "language", "code", "default_params", "timeout_ms", "max_history", "enabled"]:
                if key in s:
                    setattr(existing, key, s[key])
            stats["scripts"] += 1

        db.commit()
        return {
            "message": "导入完成",
            "stats": stats,
        }
    except Exception as e:
        db.rollback()
        return {"error": f"Import failed: {str(e)}"}
