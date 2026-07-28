"""Lab data CRUD + comparison API."""
import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.device import Device, DeviceTag
from app.models.lab_data import LabData, TagAggregate
from app.models.history import TagHistory
from app.services.audit_service import log_action

router = APIRouter(prefix="/lab-data", tags=["化验数据"])


# ═══════════════════ Schemas ═══════════════════

class LabDataCreate(BaseModel):
    device_id: int
    tag_id: Optional[int] = None
    lab_name: str
    lab_value: float
    unit: str = ""
    sample_time: str  # ISO datetime
    operator: str = ""
    remark: str = ""


class LabDataUpdate(BaseModel):
    lab_name: Optional[str] = None
    lab_value: Optional[float] = None
    unit: Optional[str] = None
    sample_time: Optional[str] = None
    operator: Optional[str] = None
    remark: Optional[str] = None


class AggregateQuery(BaseModel):
    device_id: int
    tag_id: int
    granularity: int = 3600  # 秒: 60=分钟, 300=5分钟, 3600=小时, 86400=天
    start_time: Optional[str] = None
    end_time: Optional[str] = None


# ═══════════════════ Lab Data CRUD ═══════════════════

@router.get("")
def list_lab_data(
    device_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    org_node_id: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    compare_window: int = Query(86400, description="对比时间窗口（秒），默认日均"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("history.read")),
):
    q = db.query(LabData)
    if device_id:
        q = q.filter(LabData.device_id == device_id)
    else:
        q = q.join(Device, LabData.device_id == Device.id).filter(Device.has_lab_data == True)
    if org_node_id is not None:
        from app.services.org_service import expand_org_subtree
        subtree = expand_org_subtree(db, {org_node_id})
        if device_id:
            q = q.join(Device, LabData.device_id == Device.id)
        q = q.filter(Device.org_node_id.in_(subtree))
    if tag_id:
        q = q.filter(LabData.tag_id == tag_id)
    if start_time:
        q = q.filter(LabData.sample_time >= start_time)
    if end_time:
        q = q.filter(LabData.sample_time <= end_time)

    total = q.count()
    items = q.order_by(LabData.sample_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

    device_ids = list({i.device_id for i in items})
    tag_ids = list({i.tag_id for i in items if i.tag_id})
    device_map = {}
    tag_map = {}
    if device_ids:
        for d in db.query(Device).filter(Device.id.in_(device_ids)).all():
            device_map[d.id] = d.name
    if tag_ids:
        for t in db.query(DeviceTag).filter(DeviceTag.id.in_(tag_ids)).all():
            tag_map[t.id] = t.name

    half_window = timedelta(seconds=compare_window / 2)

    data = []
    for i in items:
        collected_avg = None
        collected_count = 0
        deviation = None
        deviation_pct = None
        status = "no_data"

        if i.tag_id and i.sample_time:
            window_start = i.sample_time - half_window
            window_end = i.sample_time + half_window

            stats = db.query(
                sql_func.avg(TagHistory.value),
                sql_func.count(TagHistory.id),
            ).filter(
                TagHistory.device_id == i.device_id,
                TagHistory.tag_id == i.tag_id,
                TagHistory.recorded_at >= window_start,
                TagHistory.recorded_at <= window_end,
            ).first()

            if stats and stats[1] > 0:
                collected_avg = round(float(stats[0]), 4)
                collected_count = stats[1]
                if i.lab_value != 0:
                    deviation = round(abs(collected_avg - i.lab_value), 4)
                    deviation_pct = round(deviation / abs(i.lab_value) * 100, 2)
                    if deviation_pct <= 5:
                        status = "normal"
                    elif deviation_pct <= 15:
                        status = "warning"
                    else:
                        status = "abnormal"
                else:
                    status = "normal" if collected_avg == 0 else "abnormal"

        data.append({
            "id": i.id,
            "device_id": i.device_id,
            "device_name": device_map.get(i.device_id, ""),
            "tag_id": i.tag_id,
            "tag_name": tag_map.get(i.tag_id, "") if i.tag_id else "",
            "lab_name": i.lab_name,
            "lab_value": i.lab_value,
            "unit": i.unit,
            "sample_time": i.sample_time.isoformat() if i.sample_time else None,
            "operator": i.operator,
            "remark": i.remark,
            "created_at": i.created_at.isoformat() if i.created_at else None,
            "collected_avg": collected_avg,
            "collected_count": collected_count,
            "deviation": deviation,
            "deviation_pct": deviation_pct,
            "status": status,
        })

    return {
        "total": total,
        "data": data,
        "compare_window": compare_window,
    }


@router.post("")
def create_lab_data(
    req: LabDataCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("history.write")),
    request: Request = None,
):
    device = db.query(Device).filter(Device.id == req.device_id).first()
    if not device:
        raise HTTPException(404, "设备不存在")

    sample_dt = datetime.fromisoformat(req.sample_time.replace("Z", "+00:00"))

    lab = LabData(
        device_id=req.device_id,
        tag_id=req.tag_id,
        lab_name=req.lab_name,
        lab_value=req.lab_value,
        unit=req.unit,
        sample_time=sample_dt,
        operator=req.operator,
        remark=req.remark,
    )
    db.add(lab)
    try:
        db.commit()
        db.refresh(lab)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"操作失败: {e}")
    log_action(action="lab_data.create", resource_type="lab_data", resource_id=lab.id,
               resource_name=lab.lab_name or str(lab.id), detail=json.dumps({"device_id": req.device_id, "lab_name": req.lab_name, "lab_value": req.lab_value}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return {"message": "录入成功", "id": lab.id}


@router.put("/{lab_id}")
def update_lab_data(
    lab_id: int,
    req: LabDataUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("history.write")),
    request: Request = None,
):
    lab = db.query(LabData).filter(LabData.id == lab_id).first()
    if not lab:
        raise HTTPException(404, "化验记录不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        if k == "sample_time" and v:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        setattr(lab, k, v)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"操作失败: {e}")
    log_action(action="lab_data.update", resource_type="lab_data", resource_id=lab.id,
               resource_name=lab.lab_name or str(lab.id), detail=json.dumps({"updated_fields": list(req.model_dump(exclude_unset=True).keys())}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return {"message": "更新成功"}


@router.delete("/{lab_id}")
def delete_lab_data(
    lab_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("history.write")),
    request: Request = None,
):
    lab = db.query(LabData).filter(LabData.id == lab_id).first()
    if not lab:
        raise HTTPException(404, "化验记录不存在")
    log_action(action="lab_data.delete", resource_type="lab_data", resource_id=lab.id,
               resource_name=lab.lab_name or str(lab.id), detail=json.dumps({"lab_name": lab.lab_name, "device_id": lab.device_id}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    db.delete(lab)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"操作失败: {e}")
    return {"message": "删除成功"}


# ═══════════════════ 化验对比 ═══════════════════

@router.get("/compare")
def compare_lab_data(
    device_id: int,
    tag_id: Optional[int] = None,
    compare_window: int = Query(86400, description="对比时间窗口（秒），默认日均"),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("history.read")),
):
    """Compare lab data with aggregated collection data.

    For each lab record, find the aggregated avg value within
    [sample_time - compare_window/2, sample_time + compare_window/2].
    """
    q = db.query(LabData).filter(LabData.device_id == device_id)
    if tag_id:
        q = q.filter(LabData.tag_id == tag_id)
    if start_time:
        q = q.filter(LabData.sample_time >= start_time)
    if end_time:
        q = q.filter(LabData.sample_time <= end_time)

    lab_records = q.order_by(LabData.sample_time.desc()).limit(200).all()

    # 批量预查点位名称（避免 N+1 查询）
    lab_tag_ids = list({l.tag_id for l in lab_records if l.tag_id})
    tag_name_map = {}
    if lab_tag_ids:
        for t in db.query(DeviceTag.id, DeviceTag.name).filter(DeviceTag.id.in_(lab_tag_ids)).all():
            tag_name_map[t.id] = t.name

    results = []
    for lab in lab_records:
        collected_avg = None
        collected_count = 0
        deviation = None
        deviation_pct = None
        status = "no_data"

        if lab.tag_id and lab.sample_time:
            half_window = timedelta(seconds=compare_window / 2)
            window_start = lab.sample_time - half_window
            window_end = lab.sample_time + half_window

            # 从历史表聚合
            stats = db.query(
                sql_func.avg(TagHistory.value),
                sql_func.count(TagHistory.id),
                sql_func.min(TagHistory.value),
                sql_func.max(TagHistory.value),
            ).filter(
                TagHistory.device_id == lab.device_id,
                TagHistory.tag_id == lab.tag_id,
                TagHistory.recorded_at >= window_start,
                TagHistory.recorded_at <= window_end,
            ).first()

            if stats and stats[1] > 0:
                collected_avg = round(float(stats[0]), 4)
                collected_count = stats[1]
                if lab.lab_value != 0:
                    deviation = round(abs(collected_avg - lab.lab_value), 4)
                    deviation_pct = round(deviation / abs(lab.lab_value) * 100, 2)
                    if deviation_pct <= 5:
                        status = "normal"
                    elif deviation_pct <= 15:
                        status = "warning"
                    else:
                        status = "abnormal"
                else:
                    status = "normal" if collected_avg == 0 else "abnormal"

        # 使用预查的 tag_name_map 而非逐条查询
        tag_name = tag_name_map.get(lab.tag_id, "") if lab.tag_id else ""

        results.append({
            "id": lab.id,
            "tag_id": lab.tag_id,
            "tag_name": tag_name,
            "lab_name": lab.lab_name,
            "lab_value": lab.lab_value,
            "unit": lab.unit,
            "sample_time": lab.sample_time.isoformat() if lab.sample_time else None,
            "operator": lab.operator,
            "collected_avg": collected_avg,
            "collected_count": collected_count,
            "deviation": deviation,
            "deviation_pct": deviation_pct,
            "status": status,
        })

    return {"total": len(results), "data": results, "compare_window": compare_window}


# ═══════════════════ 聚合查询 ═══════════════════

@router.get("/aggregate")
def query_aggregate(
    device_id: int,
    tag_id: int,
    granularity: int = Query(3600, description="粒度（秒）: 60/300/900/3600/86400"),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("history.read")),
):
    """Query pre-aggregated data. Falls back to real-time calculation if no aggregate exists."""
    q = db.query(TagAggregate).filter(
        TagAggregate.device_id == device_id,
        TagAggregate.tag_id == tag_id,
        TagAggregate.granularity == granularity,
    )
    if start_time:
        q = q.filter(TagAggregate.bucket_time >= start_time)
    else:
        q = q.filter(TagAggregate.bucket_time >= datetime.now(timezone.utc) - timedelta(hours=24))
    if end_time:
        q = q.filter(TagAggregate.bucket_time <= end_time)

    items = q.order_by(TagAggregate.bucket_time.asc()).limit(1000).all()

    if items:
        return {
            "device_id": device_id,
            "tag_id": tag_id,
            "granularity": granularity,
            "source": "pre_aggregated",
            "data": [
                {
                    "time": i.bucket_time.isoformat() if i.bucket_time else None,
                    "min": i.min_value,
                    "max": i.max_value,
                    "avg": i.avg_value,
                    "count": i.count,
                    "first": i.first_value,
                    "last": i.last_value,
                }
                for i in items
            ],
        }

    # Fallback: real-time calculation from raw history
    raw_q = db.query(TagHistory.value, TagHistory.recorded_at).filter(
        TagHistory.device_id == device_id,
        TagHistory.tag_id == tag_id,
    )
    if start_time:
        raw_q = raw_q.filter(TagHistory.recorded_at >= start_time)
    else:
        raw_q = raw_q.filter(TagHistory.recorded_at >= datetime.now(timezone.utc) - timedelta(hours=24))
    if end_time:
        raw_q = raw_q.filter(TagHistory.recorded_at <= end_time)

    raw_data = raw_q.order_by(TagHistory.recorded_at.asc()).all()

    buckets = {}
    for value, recorded_at in raw_data:
        if recorded_at is None or value is None:
            continue
        ts = recorded_at if recorded_at.tzinfo else recorded_at.replace(tzinfo=timezone.utc)
        bucket_key = (int(ts.timestamp()) // granularity) * granularity
        buckets.setdefault(bucket_key, []).append(value)

    data = [
        {
            "time": datetime.fromtimestamp(bk, tz=timezone.utc).isoformat(),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
            "avg": round(sum(vals) / len(vals), 4),
            "count": len(vals),
            "first": round(vals[0], 4),
            "last": round(vals[-1], 4),
        }
        for bk, vals in sorted(buckets.items())
    ]

    return {
        "device_id": device_id,
        "tag_id": tag_id,
        "granularity": granularity,
        "source": "realtime_calc",
        "data": data,
    }
