"""Alarm management API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.alarm import AlarmRule, AlarmRecord, AlarmAck, AlarmStatus, AlarmLevel
from app.schemas.alarm import (
    AlarmRuleCreate, AlarmRuleUpdate, AlarmRuleOut,
    AlarmRecordOut, AlarmAckRequest, AlarmStats,
)
from app.schemas.common import ResponseModel, PageResponse
from typing import List
from datetime import datetime, timezone
from app.services.org_service import get_visible_device_ids, check_device_visible

router = APIRouter(prefix="/alarms", tags=["报警管理"])


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
    return PageResponse(total=total, page=page, page_size=page_size, data=[AlarmRuleOut.model_validate(i) for i in items])


@router.get("/rules/all", response_model=List[AlarmRuleOut])
def list_all_rules(db: Session = Depends(get_db), current_user: User = Depends(require_permission("alarm.read"))):
    q = db.query(AlarmRule)
    q = _apply_alarm_org_filter(q, db, current_user, AlarmRule.device_id)
    return q.order_by(AlarmRule.id).all()


@router.post("/rules", response_model=AlarmRuleOut)
def create_rule(req: AlarmRuleCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("alarm.write"))):
    rule = AlarmRule(**req.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=AlarmRuleOut)
def update_rule(rule_id: int, req: AlarmRuleUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("alarm.write"))):
    rule = db.query(AlarmRule).filter(AlarmRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("alarm.write"))):
    rule = db.query(AlarmRule).filter(AlarmRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(rule)
    db.commit()
    return {"message": "删除成功"}


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
    return PageResponse(total=total, page=page, page_size=page_size, data=[AlarmRecordOut.model_validate(i) for i in items])


@router.get("/records/active", response_model=List[AlarmRecordOut])
def list_active_alarms(db: Session = Depends(get_db), current_user: User = Depends(require_permission("alarm.read"))):
    """Get all currently active (unacknowledged) alarms."""
    q = db.query(AlarmRecord).filter(AlarmRecord.status == AlarmStatus.ACTIVE)
    q = _apply_alarm_org_filter(q, db, current_user)
    return q.order_by(AlarmRecord.triggered_at.desc()).limit(200).all()


@router.post("/records/{record_id}/acknowledge", response_model=AlarmRecordOut)
def acknowledge_alarm(
    record_id: int,
    req: AlarmAckRequest,
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
    db.commit()
    db.refresh(record)
    return record


@router.post("/records/{record_id}/clear", response_model=AlarmRecordOut)
def clear_alarm(record_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("alarm.clear"))):
    record = db.query(AlarmRecord).filter(AlarmRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="报警记录不存在")
    if not check_device_visible(db, current_user, record.device_id):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="无权操作该报警（超出组织数据范围）")
    record.status = AlarmStatus.CLEARED
    record.cleared_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record


# ============ Alarm Stats ============

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

    return AlarmStats(
        total_active=active,
        total_acknowledged=acked,
        total_cleared=cleared,
        by_level={l: c for l, c in level_counts},
        by_device={str(d): c for d, c in device_counts},
        recent=[AlarmRecordOut.model_validate(r) for r in recent],
    )
