"""Data export API — CSV / Excel reports."""
import io
import csv
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.device import Device, DeviceTag
from app.models.history import TagHistory
from app.models.alarm import AlarmRecord
from app.models.sms import SmsRecord

router = APIRouter(prefix="/export", tags=["数据导出"])


@router.get("/history/csv")
def export_history_csv(
    device_id: int,
    tag_id: int = None,
    start_time: str = None,
    end_time: str = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("export.download")),
):
    """Export tag history as CSV."""
    q = db.query(TagHistory).filter(TagHistory.device_id == device_id)
    if tag_id:
        q = q.filter(TagHistory.tag_id == tag_id)
    if start_time:
        q = q.filter(TagHistory.recorded_at >= start_time)
    else:
        q = q.filter(TagHistory.recorded_at >= datetime.now(timezone.utc) - timedelta(days=7))
    if end_time:
        q = q.filter(TagHistory.recorded_at <= end_time)

    rows = q.order_by(TagHistory.recorded_at.desc()).limit(50000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["时间", "设备ID", "点位ID", "点位名称", "值", "原始值", "质量"])
    for r in rows:
        writer.writerow([
            r.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if r.recorded_at else "",
            r.device_id, r.tag_id, r.tag_name,
            r.value, r.raw_value, r.quality,
        ])

    content = "\ufeff" + output.getvalue()  # BOM for Excel
    filename = f"history_{device_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/alarms/csv")
def export_alarms_csv(
    device_id: int = None,
    alarm_level: str = None,
    start_time: str = None,
    end_time: str = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("export.download")),
):
    """Export alarm records as CSV."""
    q = db.query(AlarmRecord)
    if device_id:
        q = q.filter(AlarmRecord.device_id == device_id)
    if alarm_level:
        q = q.filter(AlarmRecord.alarm_level == alarm_level)
    if start_time:
        q = q.filter(AlarmRecord.triggered_at >= start_time)
    else:
        q = q.filter(AlarmRecord.triggered_at >= datetime.now(timezone.utc) - timedelta(days=30))
    if end_time:
        q = q.filter(AlarmRecord.triggered_at <= end_time)

    rows = q.order_by(AlarmRecord.triggered_at.desc()).limit(50000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "规则ID", "设备ID", "点位ID", "类型", "等级", "信息", "触发值", "阈值", "状态", "触发时间", "确认时间", "消除时间", "确认人"])
    for r in rows:
        writer.writerow([
            r.id, r.rule_id, r.device_id, r.tag_id,
            r.alarm_type, r.alarm_level, r.alarm_message,
            r.trigger_value, r.threshold_value, r.status,
            r.triggered_at.strftime("%Y-%m-%d %H:%M:%S") if r.triggered_at else "",
            r.acknowledged_at.strftime("%Y-%m-%d %H:%M:%S") if r.acknowledged_at else "",
            r.cleared_at.strftime("%Y-%m-%d %H:%M:%S") if r.cleared_at else "",
            r.acknowledged_by or "",
        ])

    content = "\ufeff" + output.getvalue()
    filename = f"alarms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/devices/csv")
def export_devices_csv(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("export.download")),
):
    """Export device list as CSV."""
    devices = db.query(Device).order_by(Device.id).all()
    tags = db.query(DeviceTag).order_by(DeviceTag.device_id, DeviceTag.sort_order).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Devices sheet
    writer.writerow(["=== 设备列表 ==="])
    writer.writerow(["ID", "名称", "协议", "厂区", "车间", "产线", "安装位置", "连接信息", "状态", "采集周期", "启用"])
    for d in devices:
        conn = ""
        if d.protocol == "modbus_tcp":
            conn = f"{d.host}:{d.port} (ID:{d.slave_id})"
        elif d.protocol == "mqtt":
            conn = f"{d.mqtt_broker}:{d.mqtt_port}"
        else:
            conn = d.opc_endpoint
        writer.writerow([
            d.id, d.name, d.protocol, d.factory, d.workshop, d.production_line,
            d.installation, conn, d.status, d.poll_interval, d.enabled,
        ])

    writer.writerow([])
    writer.writerow(["=== 采集点位 ==="])
    writer.writerow(["设备ID", "点位ID", "名称", "数据源", "类型", "系数", "偏移", "单位", "可写"])
    for t in tags:
        source = ""
        dev = next((d for d in devices if d.id == t.device_id), None)
        if dev:
            if dev.protocol == "modbus_tcp":
                source = f"{t.function_code}@{t.address}"
            elif dev.protocol == "mqtt":
                source = t.mqtt_topic or f"prefix/{t.name}"
            else:
                source = t.opc_node_id
        writer.writerow([
            t.device_id, t.id, t.name, source,
            t.data_type or t.mqtt_value_type or t.opc_node_type,
            t.scale_factor, t.offset, t.unit, t.writable,
        ])

    content = "\ufeff" + output.getvalue()
    filename = f"devices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/report/daily")
def daily_report(
    date: str = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("export.download")),
):
    """Generate a daily summary report."""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day_start = f"{date} 00:00:00"
    day_end = f"{date} 23:59:59"

    # Device stats
    total_devices = db.query(sql_func.count()).select_from(Device).scalar()
    online_devices = db.query(sql_func.count()).select_from(Device).filter(Device.status == "online").scalar()

    # Alarm stats
    alarm_count = db.query(sql_func.count()).select_from(AlarmRecord).filter(
        AlarmRecord.triggered_at >= day_start, AlarmRecord.triggered_at <= day_end
    ).scalar()
    alarms_by_level = dict(db.query(
        AlarmRecord.alarm_level, sql_func.count()
    ).filter(
        AlarmRecord.triggered_at >= day_start, AlarmRecord.triggered_at <= day_end
    ).group_by(AlarmRecord.alarm_level).all())

    # SMS stats
    sms_sent = db.query(sql_func.count()).select_from(SmsRecord).filter(
        SmsRecord.sent_at >= day_start, SmsRecord.sent_at <= day_end
    ).scalar()

    return {
        "date": date,
        "devices": {"total": total_devices, "online": online_devices},
        "alarms": {"total": alarm_count, "by_level": alarms_by_level},
        "sms": {"sent": sms_sent},
    }
