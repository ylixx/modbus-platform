"""Dashboard API."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.device import Device, DeviceTag
from app.models.alarm import AlarmRecord, AlarmStatus
from app.models.sms import SmsRecord

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    total_devices = db.query(sql_func.count()).select_from(Device).scalar()
    online_devices = db.query(sql_func.count()).select_from(Device).filter(Device.status == "online").scalar()
    offline_devices = db.query(sql_func.count()).select_from(Device).filter(Device.status == "offline").scalar()
    error_devices = db.query(sql_func.count()).select_from(Device).filter(Device.status == "error").scalar()
    total_tags = db.query(sql_func.count()).select_from(DeviceTag).scalar()

    active_alarms = db.query(sql_func.count()).select_from(AlarmRecord).filter(AlarmRecord.status == AlarmStatus.ACTIVE).scalar()
    acked_alarms = db.query(sql_func.count()).select_from(AlarmRecord).filter(AlarmRecord.status == AlarmStatus.ACKNOWLEDGED).scalar()

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
def get_device_status_distribution(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(Device.status, sql_func.count()).group_by(Device.status).all()
    return {status: count for status, count in rows}


@router.get("/alarm-trend")
def get_alarm_trend(days: int = 7, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from datetime import datetime, timedelta
    from sqlalchemy import text

    start = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        text("DATE(triggered_at) as date"),
        AlarmRecord.alarm_level,
        sql_func.count().label("count"),
    ).filter(
        AlarmRecord.triggered_at >= start
    ).group_by(text("date"), AlarmRecord.alarm_level).order_by(text("date")).all()

    result = {}
    for row in rows:
        date_str = str(row.date)
        if date_str not in result:
            result[date_str] = {}
        result[date_str][row.alarm_level] = row.count
    return result
