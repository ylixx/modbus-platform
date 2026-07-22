"""History data API."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.history import TagHistory
from app.schemas.common import PageResponse
from typing import Optional
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/history", tags=["历史数据"])


@router.get("")
def query_history(
    device_id: int,
    tag_id: int,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    interval: str = "raw",  # raw | 1m | 5m | 15m | 1h | 1d
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("history.read")),
):
    """Query historical data with optional aggregation."""
    q = db.query(TagHistory).filter(
        TagHistory.device_id == device_id,
        TagHistory.tag_id == tag_id,
    )
    if start_time:
        q = q.filter(TagHistory.recorded_at >= start_time)
    else:
        q = q.filter(TagHistory.recorded_at >= datetime.now(timezone.utc) - timedelta(hours=24))
    if end_time:
        q = q.filter(TagHistory.recorded_at <= end_time)

    if interval == "raw":
        total = q.count()
        items = q.order_by(TagHistory.recorded_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return {
            "device_id": device_id,
            "tag_id": tag_id,
            "interval": interval,
            "total": total,
            "data": [
                {
                    "value": i.value,
                    "raw_value": i.raw_value,
                    "quality": i.quality,
                    "time": i.recorded_at.isoformat() if i.recorded_at else None,
                }
                for i in reversed(items)
            ],
        }
    else:
        # Aggregated query
        interval_map = {
            "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400,
        }
        secs = interval_map.get(interval, 60)

        # Use time-bucket aggregation (MySQL compatible)
        from sqlalchemy import text
        bucket_expr = text(
            f"FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(recorded_at) / {secs}) * {secs})"
        )
        rows = db.query(
            bucket_expr.label("bucket"),
            sql_func.min(TagHistory.value).label("min_val"),
            sql_func.max(TagHistory.value).label("max_val"),
            sql_func.avg(TagHistory.value).label("avg_val"),
            sql_func.count().label("count"),
        ).filter(
            TagHistory.device_id == device_id,
            TagHistory.tag_id == tag_id,
        )
        if start_time:
            rows = rows.filter(TagHistory.recorded_at >= start_time)
        else:
            rows = rows.filter(TagHistory.recorded_at >= datetime.now(timezone.utc) - timedelta(hours=24))
        if end_time:
            rows = rows.filter(TagHistory.recorded_at <= end_time)

        rows = rows.group_by(text("bucket")).order_by(text("bucket")).limit(2000).all()

        return {
            "device_id": device_id,
            "tag_id": tag_id,
            "interval": interval,
            "data": [
                {
                    "time": r.bucket.isoformat() if r.bucket else None,
                    "min": round(r.min_val, 4) if r.min_val is not None else None,
                    "max": round(r.max_val, 4) if r.max_val is not None else None,
                    "avg": round(r.avg_val, 4) if r.avg_val is not None else None,
                    "count": r.count,
                }
                for r in rows
            ],
        }


@router.get("/latest")
def get_latest_values(
    device_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("history.read")),
):
    """Get the latest value for each tag of a device."""
    from sqlalchemy import text
    subq = db.query(
        TagHistory.tag_id,
        sql_func.max(TagHistory.id).label("max_id"),
    ).filter(TagHistory.device_id == device_id).group_by(TagHistory.tag_id).subquery()

    rows = db.query(TagHistory).join(
        subq, TagHistory.id == subq.c.max_id
    ).all()

    return {
        "device_id": device_id,
        "values": [
            {
                "tag_id": r.tag_id,
                "tag_name": r.tag_name,
                "value": r.value,
                "quality": r.quality,
                "time": r.recorded_at.isoformat() if r.recorded_at else None,
            }
            for r in rows
        ],
    }
