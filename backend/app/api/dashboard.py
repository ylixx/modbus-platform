"""Dashboard API."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.device import Device, DeviceTag
from app.models.alarm import AlarmRecord, AlarmStatus
from app.models.sms import SmsRecord
from app.services.org_service import get_visible_device_ids

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


def _device_count(db: Session, visible, *filters):
    """按组织数据范围统计设备数量。"""
    if visible is not None and not visible:
        return 0
    q = db.query(sql_func.count()).select_from(Device)
    if visible is not None:
        q = q.filter(Device.id.in_(visible))
    for f in filters:
        q = q.filter(f)
    return q.scalar()


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db), current_user: User = Depends(require_permission("dashboard.read"))):
    visible = get_visible_device_ids(db, current_user)
    total_devices = _device_count(db, visible)
    online_devices = _device_count(db, visible, Device.status == "online")
    offline_devices = _device_count(db, visible, Device.status == "offline")
    error_devices = _device_count(db, visible, Device.status == "error")

    total_tags = db.query(sql_func.count()).select_from(DeviceTag)
    if visible is not None:
        if not visible:
            total_tags = total_tags.filter(DeviceTag.device_id == -1)
        else:
            total_tags = total_tags.filter(DeviceTag.device_id.in_(visible))
    total_tags = total_tags.scalar()

    alarm_filter = None
    if visible is not None:
        alarm_filter = AlarmRecord.device_id.in_(visible) if visible else AlarmRecord.device_id == -1

    active_alarms = db.query(sql_func.count()).select_from(AlarmRecord)
    acked_alarms = db.query(sql_func.count()).select_from(AlarmRecord)
    if alarm_filter is not None:
        active_alarms = active_alarms.filter(alarm_filter)
        acked_alarms = acked_alarms.filter(alarm_filter)
    active_alarms = active_alarms.filter(AlarmRecord.status == AlarmStatus.ACTIVE).scalar()
    acked_alarms = acked_alarms.filter(AlarmRecord.status == AlarmStatus.ACKNOWLEDGED).scalar()

    total_sms = db.query(sql_func.count()).select_from(SmsRecord).scalar()
    failed_sms = db.query(sql_func.count()).select_from(SmsRecord).filter(SmsRecord.status == "failed").scalar()

    return {
        "devices": {
            "total": total_devices,
            "online": online_devices,
            "offline": offline_devices,
            "error": error_devices,
        },
        "tags": {"total": total_tags},
        "alarms": {
            "active": active_alarms,
            "acknowledged": acked_alarms,
        },
        "sms": {
            "total": total_sms,
            "failed": failed_sms,
        },
    }


@router.get("/device-status")
def get_device_status_distribution(db: Session = Depends(get_db), current_user: User = Depends(require_permission("dashboard.read"))):
    visible = get_visible_device_ids(db, current_user)
    q = db.query(Device.status, sql_func.count())
    if visible is not None:
        if not visible:
            return {}
        q = q.filter(Device.id.in_(visible))
    rows = q.group_by(Device.status).all()
    return {status: count for status, count in rows}


@router.get("/alarm-trend")
def get_alarm_trend(days: int = Query(7, ge=1, le=365), db: Session = Depends(get_db), current_user: User = Depends(require_permission("dashboard.read"))):
    from datetime import datetime, timedelta, timezone

    visible = get_visible_device_ids(db, current_user)
    start = datetime.now(timezone.utc) - timedelta(days=days)

    # 用 Python 端聚合代替 DATE()，兼容 SQLite / MySQL / PostgreSQL
    base_q = db.query(AlarmRecord.triggered_at, AlarmRecord.alarm_level).filter(
        AlarmRecord.triggered_at >= start
    )
    if visible is not None:
        if not visible:
            return {}
        base_q = base_q.filter(AlarmRecord.device_id.in_(visible))

    rows = base_q.order_by(AlarmRecord.triggered_at.asc()).all()

    result = {}
    for triggered_at, alarm_level in rows:
        if triggered_at is None:
            continue
        # 统一用 UTC 日期字符串做 key（兼容所有数据库）
        date_str = triggered_at.strftime("%Y-%m-%d")
        if date_str not in result:
            result[date_str] = {}
        result[date_str][alarm_level] = result[date_str].get(alarm_level, 0) + 1
    return result
