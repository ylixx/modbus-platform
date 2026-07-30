"""Hierarchy configuration API."""
import json, logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.hierarchy import HierarchyConfig
from app.models.device import Device
from app.schemas.common import ResponseModel
from app.services.org_service import apply_device_org_filter
from app.schemas.hierarchy import (
    HierarchyConfigCreate, HierarchyConfigUpdate, HierarchyConfigOut, HierarchyLevel,
)

router = APIRouter(prefix="/hierarchy", tags=["层级配置"])

logger = logging.getLogger(__name__)


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
    try:
        db.commit()
        db.refresh(cfg)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
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
    try:
        db.commit()
        db.refresh(cfg)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
    return _parse_levels(cfg)


@router.delete("/configs/{config_id}")
def delete_config(config_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("hierarchy.write"))):
    cfg = db.query(HierarchyConfig).filter(HierarchyConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    db.delete(cfg)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
    return ResponseModel(message="删除成功")


# ── Tree data API ──

@router.get("/tree")
def get_hierarchy_tree(
    config_id: int = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("hierarchy.read")),
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

    devices = apply_device_org_filter(
        db.query(Device).filter(Device.enabled == True), db, user
    ).order_by(Device.id).all()

    tree = _build_tree(devices, levels)
    return {"config": _parse_levels(cfg), "tree": tree}


# ── Org cascade (关联列表框) ──

@router.get("/org-tree")
def get_org_cascade_tree(
    with_devices: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("hierarchy.read")),
):
    """组织架构级联数据（关联列表框）：厂区 → 班 → 站 → 位置 → 设备名称。

    返回嵌套树，前端可将其逐层展开为多个关联列表框，并在最后一级列出设备名称。

    - with_devices=true（默认）：设备作为叶子节点返回，便于纵览整体结构（演示/详情页用）。
    - with_devices=false：仅返回层级结构（厂区/班/站/位置），不带设备，负载小；设备由前端按层级
      范围单独查询 /devices 填充下拉框，避免设备量大时一次性加载全部。
    """
    levels = [
        {"key": "factory",         "label": "厂区", "field": "factory",         "icon": "🏭"},
        {"key": "workshop",        "label": "区/站", "field": "workshop",        "icon": "📍"},
        {"key": "production_line", "label": "班",   "field": "production_line", "icon": "👷"},
        {"key": "installation",    "label": "位置", "field": "installation",    "icon": "📌"},
        {"key": "device",          "label": "设备名称", "field": "_device",     "icon": "📡"},
    ]
    if with_devices:
        # 组织架构展示设备，按用户组织权限过滤
        devices = apply_device_org_filter(
            db.query(Device), db, user
        ).order_by(Device.id).all()
        tree = _build_tree(devices, levels)
    else:
        # 仅层级结构：用 DISTINCT 取 厂区/区/班/位置 的组合，按用户组织权限过滤
        q = db.query(Device.factory, Device.workshop, Device.production_line, Device.installation)
        q = apply_device_org_filter(q, db, user)
        rows = q.distinct().all()
        row_dicts = [
            {
                "factory": r[0] or "",
                "workshop": r[1] or "",
                "production_line": r[2] or "",
                "installation": r[3] or "",
            }
            for r in rows
        ]
        tree = _build_hierarchy_only(row_dicts, levels[:-1])
    return {"levels": levels, "tree": tree}


# ── Available fields ──

@router.get("/fields")
def get_available_fields(_: User = Depends(require_permission("hierarchy.read"))):
    """Return all device fields that can be used as hierarchy levels."""
    return [
        {"field": "factory",         "label": "厂级",      "type": "string"},
        {"field": "workshop",        "label": "区级",      "type": "string"},
        {"field": "production_line", "label": "班级",      "type": "string"},
        {"field": "installation",    "label": "安装位置",  "type": "string"},
        {"field": "group",           "label": "设备分组",  "type": "string"},
        {"field": "protocol",        "label": "通信协议",  "type": "enum"},
        {"field": "status",          "label": "设备状态",  "type": "enum"},
        {"field": "_device",         "label": "设备(叶子)", "type": "leaf"},
    ]


def _create_default(db: Session) -> HierarchyConfig:
    default_levels = [
        {"key": "factory",         "label": "厂级",   "field": "factory",         "icon": "🏭"},
        {"key": "workshop",        "label": "区级",   "field": "workshop",        "icon": "🏢"},
        {"key": "production_line", "label": "班级",   "field": "production_line", "icon": "🔧"},
        {"key": "device",          "label": "设备",   "field": "_device",         "icon": "📡"},
    ]
    cfg = HierarchyConfig(
        name="默认", description="厂级→区级→班级→设备",
        levels_json=json.dumps(default_levels, ensure_ascii=False),
        is_default=True,
    )
    db.add(cfg)
    try:
        db.commit()
        db.refresh(cfg)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
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


def _build_hierarchy_only(rows: list, levels: list) -> list:
    """仅层级结构：根据 (厂区, 班, 站, 位置) 字典列表递归构建分组节点，不带设备叶子。"""
    if not levels or not rows:
        return []

    level = levels[0]
    field = level["field"]
    remaining = levels[1:]
    icon = level.get("icon", "")

    groups: dict[str, list] = {}
    for r in rows:
        value = r.get(field) or ""
        if not value:
            value = f"未设置{level['label']}"
        groups.setdefault(value, []).append(r)

    result = []
    for group_name, subgroup in sorted(groups.items()):
        children = _build_hierarchy_only(subgroup, remaining) if remaining else []
        result.append(
            {
                "label": group_name,
                "type": "level",
                "level_key": level["key"],
                "icon": icon,
                "children": children,
            }
        )
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
