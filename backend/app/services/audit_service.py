"""Audit logging service."""
import json
from datetime import datetime, timezone
from typing import Optional
from app.core.database import SessionLocal
from app.models.audit import AuditLog


def log_action(
    action: str,
    resource_type: str = "",
    resource_id: int = None,
    resource_name: str = "",
    detail: str = "",
    user_id: int = None,
    username: str = "",
    ip_address: str = "",
):
    """Write an audit log entry (fire-and-forget safe)."""
    db = SessionLocal()
    try:
        entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            detail=detail,
            ip_address=ip_address,
        )
        db.add(entry)
        db.commit()

        # Push via WebSocket
        import asyncio
        from app.engine.websocket_manager import push_operation_log
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(push_operation_log({
                    "id": entry.id,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "resource_name": resource_name,
                    "username": username,
                    "time": datetime.now(timezone.utc).isoformat(),
                }))
        except RuntimeError:
            pass  # No event loop running
    except Exception:
        db.rollback()
    finally:
        db.close()
