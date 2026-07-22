"""Audit log API."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.common import PageResponse
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/audit", tags=["操作审计"])


@router.get("/logs")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str = None,
    resource_type: str = None,
    username: str = None,
    start_time: str = None,
    end_time: str = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit.read")),
):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action.contains(action))
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)
    if username:
        q = q.filter(AuditLog.username.contains(username))
    if start_time:
        q = q.filter(AuditLog.created_at >= start_time)
    if end_time:
        q = q.filter(AuditLog.created_at <= end_time)

    total = q.count()
    items = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return PageResponse(
        total=total, page=page, page_size=page_size,
        data=[{
            "id": i.id, "user_id": i.user_id, "username": i.username,
            "action": i.action, "resource_type": i.resource_type,
            "resource_id": i.resource_id, "resource_name": i.resource_name,
            "detail": i.detail, "ip_address": i.ip_address,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        } for i in items],
    )
