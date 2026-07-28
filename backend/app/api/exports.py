"""Data export API — CSV / Excel reports."""
import io
import csv
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query, Response, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.device import Device, DeviceTag
from app.models.history import TagHistory
from app.models.alarm import AlarmRecord
from app.models.sms import SmsRecord
from app.services.audit_service import log_action
import json

router = APIRouter(prefix="/export", tags=["数据导出"])


@router.get("/history/csv")
def export_history_csv(
    device_id: int,
    tag_id: int = None,
    start_time: str = None,
    end_time: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("export.download")),
    request: Request = None,
):
    """Export tag history as CSV."""
    from app.services.org_service import check_device_visible
    if not check_device_visible(db, current_user, device_id):
        raise HTTPException(status_code=403, detail="无权导出该设备数据（超出组织数据范围）")
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
    log_action(action="export.history_csv", resource_type="export", resource_id=str(device_id),
               resource_name=f"导出历史数据-设备{device_id}", detail=json.dumps({"device_id": device_id, "tag_id": tag_id, "start_time": start_time, "end_time": end_time}, ensure_ascii=False, default=str),
               user_id=current_user.id, username=current_user.username, ip_address=request.client.host if request.client else "")
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
    current_user: User = Depends(require_permission("export.download")),
    request: Request = None,
):
    """Export alarm records as CSV."""
    from app.services.org_service import get_visible_device_ids
    visible = get_visible_device_ids(db, current_user)
    q = db.query(AlarmRecord)
    if visible is not None:
        if not visible:
            raise HTTPException(status_code=403, detail="无权导出数据（超出组织数据范围）")
        q = q.filter(AlarmRecord.device_id.in_(visible))
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
    log_action(action="export.alarms_csv", resource_type="export", resource_id="alarms",
               resource_name="导出报警数据", detail=json.dumps({"device_id": device_id, "alarm_level": alarm_level, "start_time": start_time, "end_time": end_time}, ensure_ascii=False, default=str),
               user_id=current_user.id, username=current_user.username, ip_address=request.client.host if request.client else "")
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/devices/csv")
def export_devices_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("export.download")),
    request: Request = None,
):
    """Export device list as CSV."""
    from app.services.org_service import apply_device_org_filter
    base_q = apply_device_org_filter(db.query(Device), db, current_user)
    devices = base_q.order_by(Device.id).all()
    visible_ids = {d.id for d in devices}
    tags = db.query(DeviceTag).filter(DeviceTag.device_id.in_(visible_ids)).order_by(DeviceTag.device_id, DeviceTag.sort_order).all() if visible_ids else []

    output = io.StringIO()
    writer = csv.writer(output)

    # Devices sheet
    writer.writerow(["=== 设备列表 ==="])
    writer.writerow(["ID", "名称", "协议", "厂级", "区级", "班级", "安装位置", "连接信息", "状态", "采集周期", "启用"])
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
    log_action(action="export.devices_csv", resource_type="export", resource_id="devices",
               resource_name="导出设备数据", detail=json.dumps({"device_count": len(devices)}, ensure_ascii=False, default=str),
               user_id=current_user.id, username=current_user.username, ip_address=request.client.host if request.client else "")
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/tags/csv")
def export_tags_csv(
    device_id: int = Query(..., description="设备ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("export.download")),
):
    """Export tags of a specific device as CSV (for import-compatible format)."""
    from app.services.org_service import check_device_visible
    if not check_device_visible(db, current_user, device_id):
        raise HTTPException(status_code=403, detail="无权导出该设备数据（超出组织数据范围）")
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(404, "设备不存在")

    tags = db.query(DeviceTag).filter(DeviceTag.device_id == device_id).order_by(DeviceTag.sort_order, DeviceTag.id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    # 与导入模板格式一致：device_name, name, function_code, address, data_type, byte_order, scale_factor, offset, decimal_places, unit, writable, description
    writer.writerow(["device_name", "name", "function_code", "address", "data_type", "byte_order", "scale_factor", "offset", "decimal_places", "unit", "writable", "description"])
    for t in tags:
        writer.writerow([
            device.name, t.name, t.function_code or "holding_register", t.address,
            t.data_type or "uint16", t.byte_order or "big_endian",
            t.scale_factor or 1, t.offset or 0, t.decimal_places or 2,
            t.unit or "", "true" if t.writable else "false", t.description or "",
        ])

    content = "\ufeff" + output.getvalue()
    filename = f"tags_{device.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/report/daily")
def daily_report(
    date: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("export.download")),
    request: Request = None,
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

    log_action(action="export.daily_report", resource_type="export", resource_id="daily_report",
               resource_name="导出日报", detail=json.dumps({"date": date, "total_devices": total_devices, "online_devices": online_devices, "alarm_count": alarm_count, "sms_sent": sms_sent}, ensure_ascii=False, default=str),
               user_id=current_user.id, username=current_user.username, ip_address=request.client.host if request.client else "")

    return {
        "date": date,
        "devices": {"total": total_devices, "online": online_devices},
        "alarms": {"total": alarm_count, "by_level": alarms_by_level},
        "sms": {"sent": sms_sent},
    }
