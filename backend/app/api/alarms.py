"""Alarm management API."""
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status as http_status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sql_func
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.alarm import AlarmRule, AlarmRecord, AlarmAck, AlarmStatus, AlarmLevel
from app.models.device import Device, DeviceTag
from app.models.system_config import SystemConfig
from app.services.audit_service import log_action
from app.schemas.alarm import (
    AlarmRuleCreate, AlarmRuleUpdate, AlarmRuleOut,
    AlarmRecordOut, AlarmAckRequest, AlarmStats,
)
from app.schemas.common import ResponseModel, PageResponse
from typing import List, Dict
from datetime import datetime, timezone
from app.services.org_service import get_visible_device_ids, check_device_visible

router = APIRouter(prefix="/alarms", tags=["报警管理"])


def _alarm_record_out(record: AlarmRecord, device_name_map: dict = None, tag_name_map: dict = None) -> AlarmRecordOut:
    """Convert AlarmRecord to AlarmRecordOut with device_name/tag_name populated."""
    out = AlarmRecordOut.model_validate(record)
    if device_name_map is not None:
        out.device_name = device_name_map.get(record.device_id, "")
    if tag_name_map is not None:
        out.tag_name = tag_name_map.get(record.tag_id, "")
    return out


def _load_name_maps(db: Session, records: list) -> tuple[dict, dict]:
    """Batch-load device and tag names for a list of AlarmRecord."""
    device_ids = {r.device_id for r in records if r.device_id}
    tag_ids = {r.tag_id for r in records if r.tag_id}
    device_map = {}
    tag_map = {}
    if device_ids:
        for d in db.query(Device.id, Device.name).filter(Device.id.in_(device_ids)).all():
            device_map[d.id] = d.name
    if tag_ids:
        for t in db.query(DeviceTag.id, DeviceTag.name).filter(DeviceTag.id.in_(tag_ids)).all():
            tag_map[t.id] = t.name
    return device_map, tag_map


def _apply_alarm_org_filter(q, db: Session, user: User, device_col=None):
    """按用户组织数据范围过滤报警/规则查询（基于可见设备集合）。

    device_col 为可空列（如 AlarmRecord.device_id / AlarmRule.device_id），
    不传时默认按 AlarmRecord.device_id 处理。
    """
    if device_col is None:
        device_col = AlarmRecord.device_id
    visible = get_visible_device_ids(db, user)
    if visible is None:
        return q
    if not visible:
        return q.filter(device_col == -1)  # 空结果
    return q.filter(device_col.in_(visible))


# ============ Alarm Rules ============

@router.get("/rules", response_model=PageResponse)
def list_alarm_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    device_id: int = None,
    enabled: bool = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("alarm.read")),
):
    q = db.query(AlarmRule)
    q = _apply_alarm_org_filter(q, db, current_user, AlarmRule.device_id)
    if device_id is not None:
        q = q.filter(AlarmRule.device_id == device_id)
    if enabled is not None:
        q = q.filter(AlarmRule.enabled == enabled)
    total = q.count()
    items = q.order_by(AlarmRule.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    device_map, tag_map = _load_name_maps(db, items)
    out = []
    for i in items:
        o = AlarmRuleOut.model_validate(i)
        o.device_name = device_map.get(i.device_id, "")
        o.tag_name = tag_map.get(i.tag_id, "")
        out.append(o)
    return PageResponse(total=total, page=page, page_size=page_size, data=out)


@router.get("/rules/all", response_model=List[AlarmRuleOut])
def list_all_rules(db: Session = Depends(get_db), current_user: User = Depends(require_permission("alarm.read"))):
    q = db.query(AlarmRule)
    q = _apply_alarm_org_filter(q, db, current_user, AlarmRule.device_id)
    return q.order_by(AlarmRule.id).limit(500).all()


@router.post("/rules", response_model=AlarmRuleOut)
def create_rule(req: AlarmRuleCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("alarm.write"))):
    rule = AlarmRule(**req.model_dump())
    db.add(rule)
    try:
        db.commit()
        db.refresh(rule)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建失败: {e}")
    log_action(action="alarm.rule.create", resource_type="alarm_rule", resource_id=rule.id,
               resource_name=rule.name, detail=json.dumps({"device_id": rule.device_id, "alarm_type": rule.alarm_type, "alarm_level": rule.alarm_level}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return rule


@router.put("/rules/{rule_id}", response_model=AlarmRuleOut)
def update_rule(rule_id: int, req: AlarmRuleUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("alarm.write"))):
    rule = db.query(AlarmRule).filter(AlarmRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    changed = req.model_dump(exclude_unset=True)
    for k, v in changed.items():
        setattr(rule, k, v)
    log_action(action="alarm.rule.update", resource_type="alarm_rule", resource_id=rule.id,
               resource_name=rule.name, detail=json.dumps(changed, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
        db.refresh(rule)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("alarm.write"))):
    rule = db.query(AlarmRule).filter(AlarmRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(rule)
    log_action(action="alarm.rule.delete", resource_type="alarm_rule", resource_id=rule.id,
               resource_name=rule.name, detail="",
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    return ResponseModel(message="删除成功")


# ============ Alarm Records ============

@router.get("/records", response_model=PageResponse)
def list_alarm_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    device_id: int = None,
    alarm_level: str = None,
    status: str = None,
    start_time: str = None,
    end_time: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("alarm.read")),
):
    q = db.query(AlarmRecord)
    q = _apply_alarm_org_filter(q, db, current_user)
    if device_id is not None:
        q = q.filter(AlarmRecord.device_id == device_id)
    if alarm_level:
        q = q.filter(AlarmRecord.alarm_level == alarm_level)
    if status:
        q = q.filter(AlarmRecord.status == status)
    if start_time:
        q = q.filter(AlarmRecord.triggered_at >= start_time)
    if end_time:
        q = q.filter(AlarmRecord.triggered_at <= end_time)
    total = q.count()
    items = q.order_by(AlarmRecord.triggered_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    device_map, tag_map = _load_name_maps(db, items)
    return PageResponse(total=total, page=page, page_size=page_size, data=[_alarm_record_out(i, device_map, tag_map) for i in items])


@router.get("/records/active", response_model=List[AlarmRecordOut])
def list_active_alarms(
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("alarm.read")),
):
    """Get all currently active (unacknowledged) alarms."""
    q = db.query(AlarmRecord).filter(AlarmRecord.status == AlarmStatus.ACTIVE)
    q = _apply_alarm_org_filter(q, db, current_user)
    items = q.order_by(AlarmRecord.triggered_at.desc()).limit(limit).all()
    device_map, tag_map = _load_name_maps(db, items)
    return [_alarm_record_out(i, device_map, tag_map) for i in items]


@router.post("/records/{record_id}/acknowledge", response_model=AlarmRecordOut)
def acknowledge_alarm(
    record_id: int,
    req: AlarmAckRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("alarm.ack")),
):
    record = db.query(AlarmRecord).filter(AlarmRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="报警记录不存在")
    if not check_device_visible(db, current_user, record.device_id):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="无权操作该报警（超出组织数据范围）")
    if record.status != AlarmStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="该报警已被处理")

    record.status = AlarmStatus.ACKNOWLEDGED
    record.acknowledged_at = datetime.now(timezone.utc)
    record.acknowledged_by = current_user.username
    record.ack_comment = req.comment

    ack = AlarmAck(
        alarm_record_id=record.id,
        user_id=current_user.id,
        username=current_user.username,
        comment=req.comment,
    )
    db.add(ack)
    log_action(action="alarm.acknowledge", resource_type="alarm_record", resource_id=record.id,
               resource_name=f"device_id={record.device_id}", detail=json.dumps({"ack_comment": req.comment or ""}, ensure_ascii=False),
               user_id=current_user.id, username=current_user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
        db.refresh(record)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"确认失败: {e}")
    return record


@router.post("/records/{record_id}/clear", response_model=AlarmRecordOut)
def clear_alarm(record_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_permission("alarm.clear"))):
    record = db.query(AlarmRecord).filter(AlarmRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="报警记录不存在")
    if not check_device_visible(db, current_user, record.device_id):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="无权操作该报警（超出组织数据范围）")
    if record.status == AlarmStatus.CLEARED:
        raise HTTPException(status_code=400, detail="该报警已被清除")
    record.status = AlarmStatus.CLEARED
    record.cleared_at = datetime.now(timezone.utc)
    log_action(action="alarm.clear", resource_type="alarm_record", resource_id=record.id,
               resource_name=f"device_id={record.device_id}", detail="",
               user_id=current_user.id, username=current_user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
        db.refresh(record)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"消除失败: {e}")
    return record


# ============ Alarm Stats ============

# ============ Escalation Config ============

ESCALATION_CONFIG_KEY = "alarm_escalation_config"
DEFAULT_ESCALATION = {"info": 30, "warning": 15, "critical": 10, "emergency": 0}

@router.get("/escalation-config")
def get_escalation_config(db: Session = Depends(get_db), current_user: User = Depends(require_permission("alarm.read"))):
    """获取报警升级配置。"""
    row = db.query(SystemConfig).filter(SystemConfig.key == ESCALATION_CONFIG_KEY).first()
    if row and row.value:
        try:
            return json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            pass
    return DEFAULT_ESCALATION


@router.put("/escalation-config")
def update_escalation_config(
    config: Dict[str, int],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("alarm.write")),
):
    """更新报警升级配置。"""
    # 验证键名
    valid_keys = {"info", "warning", "critical", "emergency"}
    cleaned = {}
    for k, v in config.items():
        if k not in valid_keys:
            raise HTTPException(status_code=400, detail=f"无效的报警等级: {k}")
        if not isinstance(v, int) or v < 0:
            raise HTTPException(status_code=400, detail=f"{k} 的超时必须为非负整数(分钟)")
        cleaned[k] = v
    # 确保包含所有等级
    for k in valid_keys:
        if k not in cleaned:
            cleaned[k] = DEFAULT_ESCALATION.get(k, 0)
    value_json = json.dumps(cleaned)
    row = db.query(SystemConfig).filter(SystemConfig.key == ESCALATION_CONFIG_KEY).first()
    if row:
        row.value = value_json
    else:
        db.add(SystemConfig(key=ESCALATION_CONFIG_KEY, value=value_json, description="报警升级超时配置(分钟)"))
    log_action(action="alarm.escalation_config.update", resource_type="system_config",
               resource_name=ESCALATION_CONFIG_KEY, detail=value_json,
               user_id=current_user.id, username=current_user.username,
               ip_address=request.client.host if request.client else "")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")
    return cleaned


@router.get("/stats", response_model=AlarmStats)
def get_alarm_stats(db: Session = Depends(get_db), current_user: User = Depends(require_permission("alarm.read"))):
    visible = get_visible_device_ids(db, current_user)
    device_filter = None
    if visible is not None:
        if not visible:
            device_filter = AlarmRecord.device_id == -1
        else:
            device_filter = AlarmRecord.device_id.in_(visible)

    def _count(status_val):
        q = db.query(sql_func.count()).filter(AlarmRecord.status == status_val)
        if device_filter is not None:
            q = q.filter(device_filter)
        return q.scalar()

    active = _count(AlarmStatus.ACTIVE)
    acked = _count(AlarmStatus.ACKNOWLEDGED)
    cleared = _count(AlarmStatus.CLEARED)

    # By level
    q_level = db.query(AlarmRecord.alarm_level, sql_func.count()).filter(AlarmRecord.status == AlarmStatus.ACTIVE)
    if device_filter is not None:
        q_level = q_level.filter(device_filter)
    level_counts = q_level.group_by(AlarmRecord.alarm_level).all()

    # By device
    q_dev = db.query(AlarmRecord.device_id, sql_func.count()).filter(AlarmRecord.status == AlarmStatus.ACTIVE)
    if device_filter is not None:
        q_dev = q_dev.filter(device_filter)
    device_counts = q_dev.group_by(AlarmRecord.device_id).all()

    q_recent = db.query(AlarmRecord)
    if device_filter is not None:
        q_recent = q_recent.filter(device_filter)
    recent = q_recent.order_by(AlarmRecord.triggered_at.desc()).limit(10).all()
    recent_device_map, recent_tag_map = _load_name_maps(db, recent)

    return AlarmStats(
        total_active=active,
        total_acknowledged=acked,
        total_cleared=cleared,
        by_level={l: c for l, c in level_counts},
        by_device={str(d): c for d, c in device_counts},
        recent=[_alarm_record_out(r, recent_device_map, recent_tag_map) for r in recent],
    )
