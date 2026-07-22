"""Hierarchy configuration API."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.hierarchy import HierarchyConfig
from app.models.device import Device
from app.schemas.hierarchy import (
    HierarchyConfigCreate, HierarchyConfigUpdate, HierarchyConfigOut, HierarchyLevel,
)

router = APIRouter(prefix="/hierarchy", tags=["层级配置"])


def _parse_levels(cfg: HierarchyConfig) -> HierarchyConfigOut:
    try:
        levels = json.loads(cfg.levels_json)
    except (json.JSONDecodeError, TypeError):
        levels = []
    return HierarchyConfigOut(
        id=cfg.id, name=cfg.name, description=cfg.description,
        levels=[HierarchyLevel(**l) for l in levels],
        is_default=cfg.is_default,
        created_at=cfg.created_at, updated_at=cfg.updated_at,
    )


@router.get("/configs")
def list_configs(db: Session = Depends(get_db), _: User = Depends(require_permission("hierarchy.read"))):
    rows = db.query(HierarchyConfig).order_by(HierarchyConfig.is_default.desc(), HierarchyConfig.id).all()
    return [_parse_levels(r) for r in rows]


@router.get("/configs/default")
def get_default_config(db: Session = Depends(get_db), _: User = Depends(require_permission("hierarchy.read"))):
    cfg = db.query(HierarchyConfig).filter(HierarchyConfig.is_default == True).first()
    if not cfg:
        cfg = db.query(HierarchyConfig).first()
    if not cfg:
        return _create_default(db)
    return _parse_levels(cfg)


@router.post("/configs", response_model=HierarchyConfigOut)
def create_config(req: HierarchyConfigCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("hierarchy.write"))):
    if req.is_default:
        db.query(HierarchyConfig).update({"is_default": False})
    cfg = HierarchyConfig(
        name=req.name, description=req.description,
        levels_json=json.dumps([l.model_dump() for l in req.levels], ensure_ascii=False),
        is_default=req.is_default,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return _parse_levels(cfg)


@router.put("/configs/{config_id}", response_model=HierarchyConfigOut)
def update_config(config_id: int, req: HierarchyConfigUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("hierarchy.write"))):
    cfg = db.query(HierarchyConfig).filter(HierarchyConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    if req.name is not None:
        cfg.name = req.name
    if req.description is not None:
        cfg.description = req.description
    if req.levels is not None:
        cfg.levels_json = json.dumps([l.model_dump() for l in req.levels], ensure_ascii=False)
    if req.is_default is not None:
        if req.is_default:
            db.query(HierarchyConfig).update({"is_default": False})
        cfg.is_default = req.is_default
    db.commit()
    db.refresh(cfg)
    return _parse_levels(cfg)


@router.delete("/configs/{config_id}")
def delete_config(config_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("hierarchy.write"))):
    cfg = db.query(HierarchyConfig).filter(HierarchyConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    db.delete(cfg)
    db.commit()
    return {"message": "删除成功"}


# ── Tree data API ──

@router.get("/tree")
def get_hierarchy_tree(
    config_id: int = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("hierarchy.read")),
):
    """Build tree data based on a hierarchy config."""
    if config_id:
        cfg = db.query(HierarchyConfig).filter(HierarchyConfig.id == config_id).first()
    else:
        cfg = db.query(HierarchyConfig).filter(HierarchyConfig.is_default == True).first()
        if not cfg:
            cfg = db.query(HierarchyConfig).first()

    if not cfg:
        cfg = _create_default(db)

    try:
        levels = json.loads(cfg.levels_json)
    except (json.JSONDecodeError, TypeError):
        levels = []

    devices = db.query(Device).filter(Device.enabled == True).order_by(Device.id).all()

    tree = _build_tree(devices, levels)
    return {"config": _parse_levels(cfg), "tree": tree}


# ── Available fields ──

@router.get("/fields")
def get_available_fields(_: User = Depends(require_permission("hierarchy.read"))):
    """Return all device fields that can be used as hierarchy levels."""
    return [
        {"field": "factory",         "label": "厂区",      "type": "string"},
        {"field": "workshop",        "label": "车间",      "type": "string"},
        {"field": "production_line", "label": "产线",      "type": "string"},
        {"field": "installation",    "label": "安装位置",  "type": "string"},
        {"field": "group",           "label": "设备分组",  "type": "string"},
        {"field": "protocol",        "label": "通信协议",  "type": "enum"},
        {"field": "status",          "label": "设备状态",  "type": "enum"},
        {"field": "_device",         "label": "设备(叶子)", "type": "leaf"},
    ]


def _create_default(db: Session) -> HierarchyConfig:
    default_levels = [
        {"key": "factory",         "label": "厂区",   "field": "factory",         "icon": "🏭"},
        {"key": "workshop",        "label": "车间",   "field": "workshop",        "icon": "🏢"},
        {"key": "production_line", "label": "产线",   "field": "production_line", "icon": "🔧"},
        {"key": "device",          "label": "设备",   "field": "_device",         "icon": "📡"},
    ]
    cfg = HierarchyConfig(
        name="默认", description="厂区→车间→产线→设备",
        levels_json=json.dumps(default_levels, ensure_ascii=False),
        is_default=True,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def _build_tree(devices: list, levels: list) -> list:
    """Recursively build tree based on level definitions."""
    if not levels or not devices:
        return []

    level = levels[0]
    field = level["field"]
    remaining = levels[1:]
    icon = level.get("icon", "")

    # Leaf level: return devices
    if field == "_device":
        return [
            {
                "label": d.name,
                "type": "device",
                "icon": "📡",
                "device": {
                    "id": d.id, "name": d.name, "protocol": d.protocol,
                    "status": d.status, "factory": d.factory, "workshop": d.workshop,
                    "production_line": d.production_line, "installation": d.installation,
                    "group_id": d.group_id, "host": d.host, "port": d.port,
                    "mqtt_broker": d.mqtt_broker, "opc_endpoint": d.opc_endpoint,
                },
            }
            for d in devices
        ]

    # Group devices by field value
    groups: dict[str, list] = {}
    for d in devices:
        value = _get_field_value(d, field)
        if not value:
            value = f"未设置{level['label']}"
        groups.setdefault(value, []).append(d)

    result = []
    for group_name, group_devices in sorted(groups.items()):
        children = _build_tree(group_devices, remaining)
        result.append({
            "label": f"{group_name} ({len(group_devices)})",
            "type": "level",
            "level_key": level["key"],
            "icon": icon,
            "children": children,
        })

    return result


def _get_field_value(device: Device, field: str) -> str:
    """Get a device's field value for grouping."""
    if field == "group":
        return device.group.name if device.group else ""
    if field == "protocol":
        return {"modbus_tcp": "Modbus TCP", "mqtt": "MQTT", "opc_ua": "OPC-UA"}.get(device.protocol, device.protocol)
    if field == "status":
        return {"online": "在线", "offline": "离线", "error": "异常", "maintenance": "维护"}.get(device.status, device.status)
    return getattr(device, field, "") or ""
