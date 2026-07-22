"""Operation confirmation service for remote control.

Provides a two-step confirmation flow:
  1. User initiates write → server generates a confirmation code
  2. User submits confirmation code → server executes the write

Confirmation codes expire after 60 seconds.
"""
import random
import string
import time
from loguru import logger
from app.services.audit_service import log_action


# In-memory store: code -> {device_id, tag_id, value, user_id, expire_at}
_pending: dict[str, dict] = {}

CODE_EXPIRE_SECONDS = 60


def create_confirmation(device_id: int, tag_id: int, value, user_id: int, username: str) -> str:
    """Create a pending confirmation, return the code."""
    code = ''.join(random.choices(string.digits, k=6))
    _pending[code] = {
        "device_id": device_id,
        "tag_id": tag_id,
        "value": value,
        "user_id": user_id,
        "username": username,
        "expire_at": time.time() + CODE_EXPIRE_SECONDS,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    log_action(
        action="control.initiate",
        resource_type="device",
        resource_id=device_id,
        resource_name=f"tag_id={tag_id}",
        detail=f"Write value={value}, confirmation code generated",
        user_id=user_id,
        username=username,
    )

    logger.info(f"Confirmation code created: {code} for device={device_id}, tag={tag_id}, value={value}")
    return code


def execute_confirmation(code: str, user_id: int, username: str) -> tuple[bool, str]:
    """Execute a pending confirmation. Returns (success, message)."""
    pending = _pending.get(code)
    if not pending:
        return False, "确认码无效或已过期"

    if time.time() > pending["expire_at"]:
        del _pending[code]
        return False, "确认码已过期，请重新发起操作"

    # Execute the write
    from app.engine.protocol_router import protocol_router
    from app.core.database import SessionLocal
    from app.models.device import DeviceTag

    db = SessionLocal()
    try:
        tag = db.query(DeviceTag).filter(DeviceTag.id == pending["tag_id"]).first()
        if not tag:
            return False, "点位不存在"

        device = db.query(Device).filter(Device.id == pending["device_id"]).first()
        success = protocol_router.write_value(
            pending["device_id"], tag, pending["value"],
            device.protocol if device else None,
        )

        if success:
            log_action(
                action="control.execute",
                resource_type="device",
                resource_id=pending["device_id"],
                resource_name=f"tag={tag.name}",
                detail=f"Write value={pending['value']} confirmed by {username}",
                user_id=user_id,
                username=username,
            )
            del _pending[code]
            return True, "写入成功"
        else:
            return False, "写入失败，请检查设备连接"
    finally:
        db.close()


def cancel_confirmation(code: str) -> bool:
    """Cancel a pending confirmation."""
    if code in _pending:
        del _pending[code]
        return True
    return False


def cleanup_expired():
    """Remove expired confirmations."""
    now = time.time()
    expired = [k for k, v in _pending.items() if now > v["expire_at"]]
    for k in expired:
        del _pending[k]
    return len(expired)


from datetime import datetime, timezone
