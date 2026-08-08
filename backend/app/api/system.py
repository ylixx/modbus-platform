"""System settings API — runtime module switches, notification channels, engine status."""
import json
import logging
from fastapi import APIRouter, Depends, Request
from typing import Dict
from app.core.deps import require_permission
from app.models.user import User

router = APIRouter(prefix="/system", tags=["系统设置"])

logger = logging.getLogger(__name__)


@router.get("/runtime-config")
def get_runtime_config(_: User = Depends(require_permission("config.read"))):
    from app.services.config_service import get_runtime_config as _get
    return {"code": 200, "message": "ok", "data": _get()}


@router.put("/runtime-config")
def put_runtime_config(req: Dict, request: Request, user: User = Depends(require_permission("config.write"))):
    from app.services.config_service import set_runtime_config
    set_runtime_config(req)
    from app.services.audit_service import log_action
    log_action(action="system.runtime_config", resource_type="system", resource_id=0,
               resource_name="协议引擎与功能开关",
               detail=json.dumps(req, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username,
               ip_address=request.client.host if request.client else "")
    return {"code": 200, "message": "已保存，重启后端后生效", "data": None}


@router.get("/engine-status")
def get_engine_status(_: User = Depends(require_permission("config.read"))):
    from app.engine.protocol_router import protocol_router
    return {"code": 200, "message": "ok", "data": protocol_router.get_status()}


@router.get("/notifications")
def get_notification_config(_: User = Depends(require_permission("config.read"))):
    from app.services.notification_service import _load_config
    return {"code": 200, "message": "ok", "data": _load_config()}


@router.put("/notifications")
def put_notification_config(req: Dict, request: Request, user: User = Depends(require_permission("config.write"))):
    from app.services.notification_service import save_config
    data = save_config(req)
    from app.services.audit_service import log_action
    log_action(action="system.notification_config", resource_type="system", resource_id=0,
               resource_name="报警通知通道配置",
               detail=json.dumps({k: list(v.keys()) for k, v in req.items()}, ensure_ascii=False),
               user_id=user.id, username=user.username,
               ip_address=request.client.host if request.client else "")
    return {"code": 200, "message": "已保存", "data": data}


@router.post("/notifications/test")
def test_notification(req: Dict, user: User = Depends(require_permission("config.write"))):
    """Send a test message through a channel: {channel: dingtalk|wechat|email}"""
    from app.services.notification_service import notification_service
    channel = (req or {}).get("channel", "")
    result = notification_service.test_send(channel)
    return {"code": 200 if result["success"] else 400,
            "message": result.get("message", ""), "data": None}
