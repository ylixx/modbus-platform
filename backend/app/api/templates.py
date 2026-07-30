"""Device & alarm rule templates API."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.device import Device, DeviceTag
from app.models.alarm import AlarmRule
from app.services.device_templates import get_all_templates, get_template
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/templates", tags=["设备模板"])

logger = logging.getLogger(__name__)


@router.get("/devices")
def list_device_templates(_: User = Depends(require_permission("template.read"))):
    """List all device templates."""
    return get_all_templates()


@router.get("/devices/{template_id}")
def get_device_template(template_id: str, _: User = Depends(require_permission("template.read"))):
    """Get a specific device template."""
    tpl = get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    return tpl


@router.post("/devices/{template_id}/create")
def create_device_from_template(
    template_id: str,
    name: str = "",
    host: str = "",
    factory: str = "",
    workshop: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("template.write")),
):
    """Create a device from a template with pre-configured tags."""
    tpl = get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")

    # Create device
    device = Device(
        name=name or tpl["name"],
        protocol=tpl["protocol"],
        host=host or tpl.get("host", ""),
        port=tpl.get("port", 502),
        slave_id=tpl.get("slave_id", 1),
        poll_interval=tpl.get("poll_interval", 5),
        mqtt_broker=tpl.get("mqtt_broker", host or ""),
        mqtt_port=tpl.get("mqtt_port", 1883),
        mqtt_payload_format=tpl.get("mqtt_payload_format", "json"),
        mqtt_is_gateway=tpl.get("mqtt_is_gateway", False),
        mqtt_topic_prefix=tpl.get("mqtt_topic_prefix", ""),
        opc_endpoint=tpl.get("opc_endpoint", ""),
        opc_namespace=tpl.get("opc_namespace", 2),
        factory=factory,
        workshop=workshop,
        enabled=True,
    )
    db.add(device)
    db.flush()

    # Create tags
    tag_count = 0
    for tag_def in tpl.get("tags", []):
        tag = DeviceTag(
            device_id=device.id,
            name=tag_def.get("name", ""),
            function_code=tag_def.get("function_code", ""),
            address=tag_def.get("address", 0),
            data_type=tag_def.get("data_type", "uint16"),
            byte_order=tag_def.get("byte_order", "big_endian"),
            scale_factor=tag_def.get("scale_factor", 1.0),
            offset=tag_def.get("offset", 0),
            decimal_places=tag_def.get("decimal_places", 2),
            unit=tag_def.get("unit", ""),
            writable=tag_def.get("writable", False),
            description=tag_def.get("description", ""),
            mqtt_topic=tag_def.get("mqtt_topic", ""),
            mqtt_value_type=tag_def.get("mqtt_value_type", "float64"),
            opc_node_id=tag_def.get("opc_node_id", ""),
            opc_node_type=tag_def.get("opc_node_type", "float64"),
            enabled=True,
        )
        db.add(tag)
        tag_count += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")

    # Start engine
    try:
        from app.engine.protocol_router import protocol_router
        protocol_router.reload_device(device.id, device.protocol)
    except Exception:
        pass

    return {
        "message": f"从模板创建成功：设备 '{device.name}'，{tag_count} 个点位",
        "device_id": device.id,
        "tag_count": tag_count,
    }


# ── Alarm Rule Templates ──

ALARM_RULE_TEMPLATES = [
    {
        "id": "temp_high",
        "name": "温度超限报警",
        "alarm_type": "threshold_high",
        "alarm_level": "warning",
        "high_limit": 80,
        "deadband": 2,
        "delay_seconds": 10,
        "description": "温度超过80℃持续10秒触发",
    },
    {
        "id": "temp_critical",
        "name": "温度危险报警",
        "alarm_type": "threshold_high",
        "alarm_level": "critical",
        "high_limit": 100,
        "deadband": 5,
        "delay_seconds": 5,
        "description": "温度超过100℃持续5秒触发",
    },
    {
        "id": "pressure_high",
        "name": "压力超限报警",
        "alarm_type": "threshold_high",
        "alarm_level": "warning",
        "high_limit": 1.0,
        "deadband": 0.05,
        "delay_seconds": 5,
        "description": "压力超过1.0MPa触发",
    },
    {
        "id": "level_low",
        "name": "液位过低报警",
        "alarm_type": "threshold_low",
        "alarm_level": "warning",
        "low_limit": 20,
        "deadband": 2,
        "delay_seconds": 30,
        "description": "液位低于20%持续30秒触发",
    },
    {
        "id": "vibration_change",
        "name": "振动异常报警",
        "alarm_type": "rate_of_change",
        "alarm_level": "warning",
        "rate_limit": 5.0,
        "delay_seconds": 0,
        "description": "振动变化率超过5/s触发",
    },
    {
        "id": "device_disconnect",
        "name": "设备离线报警",
        "alarm_type": "disconnect",
        "alarm_level": "critical",
        "delay_seconds": 0,
        "description": "设备连续3次采集失败触发",
    },
]


@router.get("/alarm-rules")
def list_alarm_rule_templates(_: User = Depends(require_permission("template.read"))):
    return ALARM_RULE_TEMPLATES
