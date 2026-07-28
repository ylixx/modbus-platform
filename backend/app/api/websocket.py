"""WebSocket API endpoint."""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError
from app.core.config import settings
from app.engine.websocket_manager import ws_manager

router = APIRouter(tags=["WebSocket"])


async def _authenticate(websocket: WebSocket, token: str | None) -> int | None:
    """Validate JWT and return user_id, or None on failure."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    """WebSocket endpoint.

    支持两种认证方式：
    1. URL query 参数：ws://host/ws?token=<jwt>（向后兼容）
    2. 首条消息认证：连接后发送 {"type":"auth","token":"<jwt>"}

    优先使用 query 参数，若缺失则等待首条 auth 消息。
    """
    user_id = await _authenticate(websocket, token)

    # URL 中无 token → 等待首条 auth 消息
    if user_id is None:
        try:
            # 先 accept 再读取消息（FastAPI 要求）
            await websocket.accept()
            auth_msg = await asyncio_wait_for_auth(websocket)
            if auth_msg and auth_msg.get("type") == "auth":
                user_id = await _authenticate(websocket, auth_msg.get("token"))
            if user_id is None:
                await websocket.close(code=4001, reason="Invalid token")
                return
            # 已 accept，直接注册到 manager
            await ws_manager.register(websocket, user_id)
        except Exception:
            try:
                await websocket.close(code=4001, reason="Auth timeout")
            except Exception:
                pass
            return
    else:
        # 通过 query 参数认证：正常 accept + connect 流程
        await ws_manager.connect(websocket, user_id)

    try:
        while True:
            # Keep alive, receive pings or client messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text('{"type":"pong"}')
                    # Record activity for heartbeat tracking
                    from app.engine.websocket_manager import ws_manager
                    ws_manager._ws_last_active[id(websocket)] = _time.time()
                # auth 消息在认证阶段已处理，忽略后续
            except json.JSONDecodeError:
                if data == "ping":
                    await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, user_id)
    except Exception:
        await ws_manager.disconnect(websocket, user_id)


import asyncio
import time as _time

AUTH_TIMEOUT = 10  # seconds


async def asyncio_wait_for_auth(websocket: WebSocket) -> dict | None:
    """等待客户端发送 auth 消息，超时返回 None。"""
    try:
        data = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT)
        return json.loads(data)
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
        return None
