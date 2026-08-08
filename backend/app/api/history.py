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
from app.services.org_service import check_device_visible
from fastapi import HTTPException, status as http_status

router = APIRouter(prefix="/history", tags=["历史数据"])


def _parse_time(time_str: str, param_name: str) -> datetime:
    """解析 ISO 时间字符串，支持多种格式。"""
    if not time_str:
        raise HTTPException(status_code=400, detail=f"{param_name} 不能为空")
    # 优先尝试完整 ISO 格式（含时区偏移 / Z），避免丢失时区信息
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass
    # 无时区标记时，回退到常见格式，并统一视为 UTC
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail=f"{param_name} 格式无效，请使用 ISO 格式如 2026-01-01T00:00:00")


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
    current_user: User = Depends(require_permission("history.read")),
):
    """Query historical data with optional aggregation."""
    if not check_device_visible(db, current_user, device_id):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="无权访问该设备历史数据（超出组织数据范围）")
    q = db.query(TagHistory).filter(
        TagHistory.device_id == device_id,
        TagHistory.tag_id == tag_id,
    )
    if start_time:
        start_dt = _parse_time(start_time, 'start_time')
        q = q.filter(TagHistory.recorded_at >= start_dt)
    else:
        q = q.filter(TagHistory.recorded_at >= datetime.now(timezone.utc) - timedelta(hours=24))
    if end_time:
        end_dt = _parse_time(end_time, 'end_time')
        q = q.filter(TagHistory.recorded_at <= end_dt)

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
        # Aggregated query — use SQL GROUP BY for efficiency instead of loading all rows.
        interval_map = {
            "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400,
        }
        secs = interval_map.get(interval, 60)

        from sqlalchemy import literal_column
        # Compute bucket key in SQL: FLOOR(UNIX_TIMESTAMP(recorded_at) / secs) * secs
        # Works for MySQL/PostgreSQL; for SQLite use STRFTIME-based approach.
        bucket_expr = sql_func.floor(sql_func.extract('epoch', TagHistory.recorded_at) / secs) * secs

        base_filter = [
            TagHistory.device_id == device_id,
            TagHistory.tag_id == tag_id,
        ]
        if start_time:
            start_dt = _parse_time(start_time, 'start_time')
            base_filter.append(TagHistory.recorded_at >= start_dt)
        else:
            base_filter.append(TagHistory.recorded_at >= datetime.now(timezone.utc) - timedelta(hours=24))
        if end_time:
            end_dt = _parse_time(end_time, 'end_time')
            base_filter.append(TagHistory.recorded_at <= end_dt)

        try:
            # Try SQL-based aggregation (works on PostgreSQL/MySQL with extract)
            rows = db.query(
                bucket_expr.label('bucket'),
                sql_func.min(TagHistory.value).label('min_val'),
                sql_func.max(TagHistory.value).label('max_val'),
                sql_func.avg(TagHistory.value).label('avg_val'),
                sql_func.count(TagHistory.value).label('cnt'),
            ).filter(*base_filter).group_by(bucket_expr).order_by(bucket_expr).all()

            data = [
                {
                    "time": datetime.fromtimestamp(r.bucket, tz=timezone.utc).isoformat() if r.bucket else None,
                    "min": round(r.min_val, 4) if r.min_val is not None else None,
                    "max": round(r.max_val, 4) if r.max_val is not None else None,
                    "avg": round(float(r.avg_val), 4) if r.avg_val is not None else None,
                    "count": r.cnt,
                }
                for r in rows
            ]
        except Exception:
            # Fallback: Python-based aggregation for SQLite or other DBs without extract()
            raw_q = db.query(TagHistory.value, TagHistory.recorded_at).filter(*base_filter).order_by(TagHistory.recorded_at.asc())
            buckets = {}
            for value, recorded_at in raw_q.yield_per(1000):
                if recorded_at is None or value is None:
                    continue
                ts = recorded_at if recorded_at.tzinfo else recorded_at.replace(tzinfo=timezone.utc)
                bucket_key = (int(ts.timestamp()) // secs) * secs
                buckets.setdefault(bucket_key, []).append(value)

            data = [
                {
                    "time": datetime.fromtimestamp(bk, tz=timezone.utc).isoformat(),
                    "min": round(min(vals), 4),
                    "max": round(max(vals), 4),
                    "avg": round(sum(vals) / len(vals), 4),
                    "count": len(vals),
                }
                for bk, vals in sorted(buckets.items())
            ]

        return {
            "device_id": device_id,
            "tag_id": tag_id,
            "interval": interval,
            "data": data,
        }


@router.get("/latest")
def get_latest_values(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("history.read")),
):
    """Get the latest value for each tag of a device."""
    if not check_device_visible(db, current_user, device_id):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="无权访问该设备历史数据（超出组织数据范围）")
    from sqlalchemy import text
    subq = db.query(
        TagHistory.tag_id,
        sql_func.max(TagHistory.id).label("max_id"),
    ).filter(TagHistory.device_id == device_id).group_by(TagHistory.tag_id).subquery()

    rows = db.query(TagHistory).join(
        subq, TagHistory.id == subq.c.max_id
    ).limit(500).all()

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
