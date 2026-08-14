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
    db=None,
):
    """Write an audit log entry (fire-and-forget safe).

    db: 可选。若传入一个已开启事务的 Session，则把审计记录加入该事务并 flush
    （不自行 commit），由调用方统一提交。这在「同一个请求内既要改业务数据又要写审计」
    的场景下能避免开启第二个写连接 —— 否则 SQLite 单写者模型下两个连接互相等待
    对方释放写锁会死锁，直到 busy_timeout 耗尽（表现为删除/更新接口 ~30s 卡死）。
    不传 db 时行为不变（独立会话、自行提交）。
    """
    own_session = db is None
    if own_session:
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
        if own_session:
            db.commit()
        else:
            # 复用调用方事务：flush 以生成主键，供 WS 推送使用
            db.flush()

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
        if own_session:
            db.rollback()
        raise
    finally:
        if own_session:
            db.close()
