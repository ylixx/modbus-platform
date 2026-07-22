"""WebSocket API endpoint."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError
from app.core.config import settings
from app.engine.websocket_manager import ws_manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    """WebSocket endpoint. Connect with: ws://host/ws?token=<jwt>"""
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if user_id is None:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except JWTError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            # Keep alive, receive pings or client messages
            data = await websocket.receive_text()
            # Echo or handle client commands if needed
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, user_id)
    except Exception:
        await ws_manager.disconnect(websocket, user_id)
