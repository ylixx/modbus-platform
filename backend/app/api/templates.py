"""Device template management API.

模板 = 一类通用设备：协议 + 连接参数默认值 + 点位定义（+ 可选默认告警规则）。
支持：模板 CRUD / 复制 / 设备转模板 / 模板创建设备（绑定）/ 差异预览 / 同步。
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.models.device import Device, DeviceTag
from app.models.alarm import AlarmRule
from app.models.template import DeviceTemplate, DeviceTemplateBinding
from app.schemas.common import ResponseModel
from app.services.device_templates import (
    BUILTIN_TEMPLATES, CONN_FIELDS, TAG_FIELDS,
    serialize_tag, diff_tags, diff_conn, device_tag_map,
)
from app.services.org_service import check_device_visible

router = APIRouter(prefix="/templates", tags=["设备模板"])

logger = logging.getLogger(__name__)

TAG_DEFAULT = {
    "name": "", "description": "", "unit": "", "function_code": "holding_register",
    "address": 0, "data_type": "uint16", "byte_order": "big_endian",
    "bit_index": None, "register_count": 1, "mqtt_topic": "", "mqtt_json_path": "",
    "mqtt_value_type": "float64", "mqtt_publish_topic": "", "mqtt_retain": False,
    "opc_node_id": "", "opc_node_type": "float64", "scale_factor": 1.0,
    "offset": 0.0, "decimal_places": 2, "min_value": None, "max_value": None,
    "writable": False, "sort_order": 0, "enabled": True,
}


# ── Schemas ──

class TemplateTagIn(BaseModel):
    name: str
    description: str = ""
    unit: str = ""
    function_code: str = "holding_register"
    address: int = 0
    data_type: str = "uint16"
    byte_order: str = "big_endian"
    bit_index: Optional[int] = None
    register_count: int = 1
    mqtt_topic: str = ""
    mqtt_json_path: str = ""
    mqtt_value_type: str = "float64"
    mqtt_publish_topic: str = ""
    mqtt_retain: bool = False
    opc_node_id: str = ""
    opc_node_type: str = "float64"
    scale_factor: float = 1.0
    offset: float = 0.0
    decimal_places: int = 2
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    writable: bool = False
    sort_order: int = 0
    enabled: bool = True


class TemplateAlarmRuleIn(BaseModel):
    name: str
    tag_name: str = ""          # 关联点位名（创建/同步时解析为 tag_id）
    description: str = ""
    alarm_type: str = "threshold_high"
    alarm_level: str = "warning"
    high_limit: Optional[float] = None
    low_limit: Optional[float] = None
    deadband: float = 0.0
    rate_limit: Optional[float] = None
    status_value: Optional[float] = None
    delay_seconds: int = 0
    auto_clear: bool = True
    sms_enabled: bool = False
    enabled: bool = True


class TemplateCreate(BaseModel):
    name: str
    category: str = ""
    description: str = ""
    protocol: str = "modbus_tcp"
    config: dict = Field(default_factory=dict)          # 连接参数默认值
    tags: List[TemplateTagIn] = Field(default_factory=list)
    alarm_rules: List[TemplateAlarmRuleIn] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    protocol: Optional[str] = None
    config: Optional[dict] = None
    tags: Optional[List[TemplateTagIn]] = None
    alarm_rules: Optional[List[TemplateAlarmRuleIn]] = None


class DeviceFromTemplate(BaseModel):
    name: str = ""
    host: str = ""                      # Modbus TCP
    serial_port: str = ""               # Modbus RTU
    mqtt_broker: str = ""               # MQTT
    opc_endpoint: str = ""              # OPC-UA
    org_node_id: Optional[int] = None
    factory: str = ""
    workshop: str = ""
    production_line: str = ""
    installation: str = ""
    description: str = ""
    config: dict = Field(default_factory=dict)      # 覆盖模板的连接参数默认值（按字段）
    bind: bool = True                                # 是否绑定模板（跟随同步）
    include_alarm_rules: bool = True                 # 是否一并生成模板默认告警规则


class SaveAsTemplate(BaseModel):
    name: str
    category: str = ""
    description: str = ""
    org_node_id: Optional[int] = None


class SyncRequest(BaseModel):
    device_ids: List[int]
    sync_conn: bool = True          # 是否同步连接参数（仅覆盖有差异字段）
    include_add: bool = True        # 新增点位
    include_update: bool = True     # 修改点位
    include_delete: bool = True     # 删除点位（设备上不存在于模板的点位）
    include_alarm_rules: bool = True  # 同步模板告警规则（name 匹配更新/新增，不删除设备自定义规则）
    create_alarm_for_added: bool = True  # 新增点位时同步创建其默认告警规则


# ── Helpers ──

def _clean_tag(t: dict) -> dict:
    return {k: t.get(k, TAG_DEFAULT.get(k)) for k in TAG_FIELDS}


def _clean_alarm_rule(r) -> dict:
    if isinstance(r, TemplateAlarmRuleIn):
        return r.model_dump()
    keys = ["name", "tag_name", "description", "alarm_type", "alarm_level",
            "high_limit", "low_limit", "deadband", "rate_limit", "status_value",
            "delay_seconds", "auto_clear", "sms_enabled", "enabled"]
    return {k: r.get(k) for k in keys}


def _template_out(tpl: DeviceTemplate, bind_count: int = 0) -> dict:
    return {
        "id": tpl.id,
        "name": tpl.name,
        "category": tpl.category,
        "description": tpl.description,
        "protocol": tpl.protocol,
        "config": tpl.config or {},
        "tags": tpl.tags or [],
        "alarm_rules": tpl.alarm_rules or [],
        "is_system": tpl.is_system,
        "version": tpl.version,
        "org_node_id": tpl.org_node_id,
        "created_at": tpl.created_at.isoformat() if tpl.created_at else None,
        "updated_at": tpl.updated_at.isoformat() if tpl.updated_at else None,
        "bind_count": bind_count,
    }


def _merge_tags_to_device(db: Session, device: Device, tag_defs: list):
    """按 (name, function_code, address) 合并点位：新增或更新字段。"""
    existing = {(t.name, t.function_code, t.address): t for t in device.tags}
    for tdef in tag_defs:
        key = (tdef.get("name"), tdef.get("function_code"), tdef.get("address"))
        tag = existing.get(key)
        data = _clean_tag(tdef)
        if tag is None:
            tag = DeviceTag(device_id=device.id, **data)
            db.add(tag)
            existing[key] = tag
        else:
            for k, v in data.items():
                if hasattr(tag, k):
                    setattr(tag, k, v)


def _sync_alarm_rules(db: Session, device: Device, rules: list):
    """按 规则名+点位名 匹配同步告警规则：新增/更新，不删除设备自定义规则。"""
    tag_by_name = {t.name: t for t in db.query(DeviceTag).filter(DeviceTag.device_id == device.id).all()}
    for rdef in rules:
        data = _clean_alarm_rule(rdef)
        tag = tag_by_name.get(data.get("tag_name") or "")
        if tag is None:
            continue
        rule = (
            db.query(AlarmRule)
            .filter(AlarmRule.device_id == device.id, AlarmRule.tag_id == tag.id,
                    AlarmRule.name == data["name"], AlarmRule.alarm_type == data["alarm_type"])
            .first()
        )
        create_kwargs = {k: v for k, v in data.items() if k != "tag_name" and hasattr(AlarmRule, k)}
        if rule is None:
            db.add(AlarmRule(device_id=device.id, tag_id=tag.id, **create_kwargs))
        else:
            for k, v in create_kwargs.items():
                setattr(rule, k, v)


def _reload_device(device_id: int, protocol: str):
    try:
        from app.engine.protocol_router import protocol_router
        protocol_router.reload_device(device_id, protocol)
    except Exception:
        pass


def seed_builtin_templates(db: Session):
    """内置模板入库（幂等：按 name 跳过）。"""
    from app.models.template import DeviceTemplate
    for tpl in BUILTIN_TEMPLATES:
        exists = db.query(DeviceTemplate).filter(DeviceTemplate.name == tpl["name"]).first()
        if exists:
            continue
        db.add(DeviceTemplate(
            name=tpl["name"],
            category=tpl.get("category", ""),
            description=tpl.get("description", ""),
            protocol=tpl.get("protocol", "modbus_tcp"),
            config=tpl.get("config", {}),
            tags=[_clean_tag(t) for t in tpl.get("tags", [])],
            alarm_rules=[_clean_alarm_rule(r) for r in tpl.get("alarm_rules", [])],
            is_system=True,
        ))
    db.commit()


# ── Template CRUD ──

@router.get("/devices")
def list_templates(
    category: str = Query(""),
    search: str = Query(""),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("template.read")),
):
    """模板列表（含绑定设备数）。内置模板只读，用户模板可编辑。"""
    q = db.query(DeviceTemplate)
    if category:
        q = q.filter(DeviceTemplate.category == category)
    if search:
        q = q.filter(DeviceTemplate.name.ilike(f"%{search}%"))
    tpls = q.order_by(DeviceTemplate.is_system.desc(), DeviceTemplate.id).all()
    bind_counts = dict(
        db.query(DeviceTemplateBinding.template_id, func.count(DeviceTemplateBinding.id))
        .group_by(DeviceTemplateBinding.template_id).all()
    ) if tpls else {}
    return [_template_out(t, bind_counts.get(t.id, 0)) for t in tpls]


@router.get("/devices/{template_id}")
def get_template_detail(template_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("template.read"))):
    tpl = db.query(DeviceTemplate).filter(DeviceTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    bind_count = db.query(DeviceTemplateBinding).filter(DeviceTemplateBinding.template_id == template_id).count()
    return _template_out(tpl, bind_count)


@router.post("/devices")
def create_template(
    req: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("template.write")),
):
    """新建模板。"""
    if db.query(DeviceTemplate).filter(DeviceTemplate.name == req.name).first():
        raise HTTPException(status_code=400, detail="模板名称已存在")
    tpl = DeviceTemplate(
        name=req.name.strip(),
        category=req.category,
        description=req.description,
        protocol=req.protocol,
        config=req.config,
        tags=[_clean_tag(t.model_dump() if hasattr(t, "model_dump") else t) for t in req.tags],
        alarm_rules=[_clean_alarm_rule(r) for r in req.alarm_rules],
        created_by=current_user.id,
    )
    db.add(tpl)
    try:
        db.commit()
        db.refresh(tpl)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建失败: {e}")
    logger.info(json.dumps({"action": "template.create", "template_id": tpl.id, "name": tpl.name}, ensure_ascii=False))
    return _template_out(tpl)


@router.put("/devices/{template_id}")
def update_template(template_id: int, req: TemplateUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("template.write"))):
    """编辑模板（内置模板只读）。变更后 version+1，绑定设备进入『待更新』状态。"""
    tpl = db.query(DeviceTemplate).filter(DeviceTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    if tpl.is_system:
        raise HTTPException(status_code=400, detail="内置模板只读，可复制为普通模板后编辑")
    data = req.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        data["name"] = data["name"].strip()
        dup = db.query(DeviceTemplate).filter(DeviceTemplate.name == data["name"], DeviceTemplate.id != template_id).first()
        if dup:
            raise HTTPException(status_code=400, detail="模板名称已存在")
    if "tags" in data and data["tags"] is not None:
        data["tags"] = [_clean_tag(t.model_dump() if hasattr(t, "model_dump") else t) for t in data["tags"]]
    if "alarm_rules" in data and data["alarm_rules"] is not None:
        data["alarm_rules"] = [_clean_alarm_rule(r) for r in data["alarm_rules"]]
    for k, v in data.items():
        setattr(tpl, k, v)
    tpl.version = (tpl.version or 0) + 1
    try:
        db.commit()
        db.refresh(tpl)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")
    bind_count = db.query(DeviceTemplateBinding).filter(DeviceTemplateBinding.template_id == template_id).count()
    logger.info(json.dumps({"action": "template.update", "template_id": tpl.id, "version": tpl.version}, ensure_ascii=False))
    return _template_out(tpl, bind_count)


@router.post("/devices/{template_id}/duplicate")
def duplicate_template(template_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("template.write"))):
    """复制模板（内置模板 → 可编辑副本）。"""
    tpl = db.query(DeviceTemplate).filter(DeviceTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    name = f"{tpl.name} 副本"
    i = 1
    while db.query(DeviceTemplate).filter(DeviceTemplate.name == name).first():
        i += 1
        name = f"{tpl.name} 副本{i}"
    new_tpl = DeviceTemplate(
        name=name, category=tpl.category, description=tpl.description,
        protocol=tpl.protocol, config=tpl.config or {},
        tags=tpl.tags or [], alarm_rules=tpl.alarm_rules or [],
        is_system=False,
    )
    db.add(new_tpl)
    db.commit()
    db.refresh(new_tpl)
    return _template_out(new_tpl)


@router.delete("/devices/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("template.write"))):
    """删除模板（内置禁止；有绑定设备时需先解绑）。"""
    tpl = db.query(DeviceTemplate).filter(DeviceTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    if tpl.is_system:
        raise HTTPException(status_code=400, detail="内置模板不可删除")
    bind_count = db.query(DeviceTemplateBinding).filter(DeviceTemplateBinding.template_id == template_id).count()
    if bind_count:
        raise HTTPException(status_code=400, detail=f"模板正被 {bind_count} 台设备绑定，请先在设备侧解除绑定")
    db.delete(tpl)
    db.commit()
    return ResponseModel(message="删除成功")


# ── 设备 ↔ 模板 ──

@router.post("/devices/{device_id}/save-as-template")
def save_device_as_template(
    device_id: int,
    req: SaveAsTemplate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("template.write")),
):
    """现有设备 → 模板（吸取连接参数 + 全部启用点位 + 可选告警规则）。"""
    if not check_device_visible(db, current_user, device_id):
        raise HTTPException(status_code=403, detail="无权访问该设备")
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if db.query(DeviceTemplate).filter(DeviceTemplate.name == req.name.strip()).first():
        raise HTTPException(status_code=400, detail="模板名称已存在")
    conn = {k: getattr(device, k, None) for k in CONN_FIELDS if getattr(device, k, None) is not None}
    conn["protocol"] = device.protocol
    tags = [serialize_tag(t) for t in device.tags if t.enabled]
    rules = [{
        "name": r.name, "tag_name": (r.tag.name if r.tag else ""),
        "description": r.description, "alarm_type": r.alarm_type,
        "alarm_level": r.alarm_level, "high_limit": r.high_limit,
        "low_limit": r.low_limit, "deadband": r.deadband,
        "rate_limit": r.rate_limit, "status_value": r.status_value,
        "delay_seconds": r.delay_seconds, "auto_clear": r.auto_clear,
        "sms_enabled": r.sms_enabled, "enabled": r.enabled,
    } for r in db.query(AlarmRule).filter(AlarmRule.device_id == device_id).all()]
    tpl = DeviceTemplate(
        name=req.name.strip(), category=req.category, description=req.description or device.description,
        protocol=device.protocol, config=conn, tags=tags, alarm_rules=rules,
        created_by=current_user.id, org_node_id=req.org_node_id,
    )
    db.add(tpl)
    try:
        db.commit()
        db.refresh(tpl)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"保存模板失败: {e}")
    logger.info(json.dumps({"action": "template.save_as", "device_id": device_id, "template_id": tpl.id}, ensure_ascii=False))
    return _template_out(tpl)


@router.post("/devices/{template_id}/create")
def create_device_from_template(
    template_id: int,
    req: DeviceFromTemplate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("template.write")),
):
    """从模板创建设备：预填连接参数 + 生成点位（+ 绑定 + 默认告警规则）。"""
    tpl = db.query(DeviceTemplate).filter(DeviceTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")

    name = req.name.strip() or f"{tpl.name} 设备"
    if db.query(Device).filter(Device.name == name).first():
        raise HTTPException(status_code=400, detail=f"设备名「{name}」已存在")

    conf = dict(tpl.config or {})
    conf.update({k: v for k, v in req.config.items() if v is not None})

    # 按模板协议装配连接参数；用户显式传入的连接信息优先
    mapping = {
        "modbus_tcp": {"host": req.host},
        "modbus_rtu": {"serial_port": req.serial_port},
        "mqtt": {"mqtt_broker": req.mqtt_broker},
        "opc_ua": {"opc_endpoint": req.opc_endpoint},
    }
    for k, v in mapping.get(tpl.protocol, {}).items():
        if v:
            conf[k] = v

    device = Device(name=name, description=req.description, protocol=tpl.protocol)
    for k, v in conf.items():
        if k in CONN_FIELDS and hasattr(device, k):
            setattr(device, k, v)
    device.org_node_id = req.org_node_id
    device.factory = req.factory
    device.workshop = req.workshop
    device.production_line = req.production_line
    device.installation = req.installation
    db.add(device)
    db.flush()

    _merge_tags_to_device(db, device, tpl.tags or [])
    db.flush()  # 确保新点位已落库，_sync_alarm_rules 按 device.tags 关联才能找到

    if req.include_alarm_rules and tpl.alarm_rules:
        _sync_alarm_rules(db, device, tpl.alarm_rules)

    if req.bind:
        db.add(DeviceTemplateBinding(
            device_id=device.id, template_id=tpl.id,
            template_version=tpl.version, synced_at=func.now(),
        ))

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("从模板创建设备失败")
        raise HTTPException(status_code=500, detail=f"创建失败: {e}")

    _reload_device(device.id, tpl.protocol)
    logger.info(json.dumps({
        "action": "device.create_from_template", "template_id": template_id,
        "device_id": device.id, "device_name": device.name,
        "tag_count": len(tpl.tags or []), "bound": req.bind,
    }, ensure_ascii=False))
    return {
        "message": f"从模板创建设备成功：'{device.name}'，点位 {len(tpl.tags or [])} 个",
        "device_id": device.id,
        "tag_count": len(tpl.tags or []),
        "bound": req.bind,
    }


class BindRequest(BaseModel):
    template_id: int = 0


@router.post("/devices/{device_id}/bind")
def bind_device(
    device_id: int,
    req: BindRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("template.write")),
):
    """绑定/解绑模板（解绑不删点位）。"""
    template_id = req.template_id
    if not check_device_visible(db, current_user, device_id):
        raise HTTPException(status_code=403, detail="无权访问该设备")
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    binding = db.query(DeviceTemplateBinding).filter(DeviceTemplateBinding.device_id == device_id).first()
    if template_id <= 0:
        # 解绑
        if binding:
            db.delete(binding)
            db.commit()
        return ResponseModel(message="已解除模板绑定")
    tpl = db.query(DeviceTemplate).filter(DeviceTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    if binding:
        if binding.template_id == template_id:
            return ResponseModel(message="设备已绑定该模板")
        binding.template_id = template_id
        binding.template_version = tpl.version
        binding.synced_at = func.now()
    else:
        db.add(DeviceTemplateBinding(device_id=device_id, template_id=template_id, template_version=tpl.version, synced_at=func.now()))
    db.commit()
    return ResponseModel(message=f"已绑定模板「{tpl.name}」")


@router.get("/devices/{device_id}/template-status")
def template_status(device_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("device.read"))):
    """设备模板绑定状态：绑定信息、差异预览（点位 + 连接参数 + 告警规则）。"""
    if not check_device_visible(db, current_user, device_id):
        raise HTTPException(status_code=403, detail="无权访问该设备")
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    binding = db.query(DeviceTemplateBinding).filter(DeviceTemplateBinding.device_id == device_id).first()
    if not binding:
        return {"bound": False, "template": None, "up_to_date": True, "diff": None}
    tpl = binding.template
    tag_map = device_tag_map(device)
    tag_diff = diff_tags(tpl.tags or [], tag_map)
    conn_diff = diff_conn(tpl.config or {}, {k: getattr(device, k, None) for k in CONN_FIELDS})
    # 告警规则差异：与同步逻辑一致，按 (name, alarm_type, tag_id) 匹配；
    # 仅当已存在规则内容有差异时列为 update，否则视为已同步
    rule_name_id = {t.name: t.id for t in device.tags}
    rule_add, rule_update = [], []
    RULE_CMP_KEYS = ["description", "alarm_level", "high_limit", "low_limit", "deadband",
                     "rate_limit", "status_value", "delay_seconds", "auto_clear",
                     "sms_enabled", "enabled"]
    for r in (tpl.alarm_rules or []):
        tag_id = rule_name_id.get(r.get("tag_name"))
        if tag_id is None:
            continue
        exists = db.query(AlarmRule).filter(
            AlarmRule.device_id == device_id,
            AlarmRule.tag_id == tag_id,
            AlarmRule.name == r.get("name"),
            AlarmRule.alarm_type == r.get("alarm_type"),
        ).first()
        if exists is None:
            rule_add.append(r)
            continue
        dirty = any(getattr(exists, k, None) != r.get(k) for k in RULE_CMP_KEYS)
        if dirty:
            rule_update.append(r)
    rule_diff = {"add": rule_add, "update": rule_update}
    pending = (
        binding.template_version < tpl.version
        or len(tag_diff["add"]) or len(tag_diff["update"]) or len(tag_diff["delete"])
        or len(conn_diff) or len(rule_diff["add"]) or len(rule_diff["update"])
    )
    return {
        "bound": True,
        "template": {"id": tpl.id, "name": tpl.name, "version": tpl.version},
        "device_version": binding.template_version,
        "synced_at": binding.synced_at.isoformat() if binding.synced_at else None,
        "up_to_date": not pending,
        "diff": {
            "tags": {
                "add": tag_diff["add"],
                "update": [{"name": u["tag"].get("name"), "device_tag_id": u["device_tag_id"],
                            "differing": u["differing"]} for u in tag_diff["update"]],
                "delete": tag_diff["delete"],
            },
            "conn": conn_diff,
            "alarm_rules": rule_diff,
        },
    }


@router.post("/sync")
def sync_devices_from_template(
    req: SyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("template.write")),
):
    """将绑定设备的点位/连接参数/告警规则同步到模板定义（差异预览后由前端确认调用）。"""
    result = {"total": len(req.device_ids), "success": 0, "failed": 0, "details": []}
    for device_id in req.device_ids:
        try:
            if not check_device_visible(db, current_user, device_id):
                raise HTTPException(status_code=403, detail="无权访问该设备")
            device = db.query(Device).filter(Device.id == device_id).first()
            if not device:
                raise HTTPException(status_code=404, detail="设备不存在")
            binding = db.query(DeviceTemplateBinding).filter(DeviceTemplateBinding.device_id == device_id).first()
            if not binding:
                raise HTTPException(status_code=400, detail="设备未绑定模板")
            tpl = binding.template
            tag_map = device_tag_map(device)
            tag_diff = diff_tags(tpl.tags or [], tag_map)

            # 点位同步
            if req.include_add:
                for tdef in tag_diff["add"]:
                    tag = DeviceTag(device_id=device.id, **_clean_tag(tdef))
                    db.add(tag)
            if req.include_update:
                for u in tag_diff["update"]:
                    tag = db.query(DeviceTag).filter(DeviceTag.id == u["device_tag_id"]).first()
                    if tag:
                        for k, v in _clean_tag(u["tag"]).items():
                            if hasattr(tag, k):
                                setattr(tag, k, v)
            if req.include_delete:
                del_ids = [d["device_tag_id"] for d in tag_diff["delete"]]
                if del_ids:
                    db.query(DeviceTag).filter(DeviceTag.id.in_(del_ids)).delete(synchronize_session=False)

            # 连接参数同步（覆盖有差异字段）
            if req.sync_conn and tpl.config:
                for k, v in (tpl.config or {}).items():
                    if k in CONN_FIELDS and hasattr(device, k) and getattr(device, k) != v:
                        setattr(device, k, v)

            # 告警规则同步
            if req.include_alarm_rules and tpl.alarm_rules:
                _sync_alarm_rules(db, device, tpl.alarm_rules)

            binding.template_version = tpl.version
            binding.synced_at = func.now()
            db.commit()
            _reload_device(device.id, device.protocol)
            result["success"] += 1
            result["details"].append({
                "device_id": device_id, "device_name": device.name,
                "message": f"同步完成（新增 {len(tag_diff['add'])} / 修改 {len(tag_diff['update'])} / 删除 {len(tag_diff['delete'])} 点位）",
            })
        except Exception as e:
            db.rollback()
            result["failed"] += 1
            result["details"].append({"device_id": device_id, "message": str(e)})
    return result


# ── Alarm rule templates（保留兼容） ──

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
