"""WebSocket manager for real-time push.

Pushes:
- Live tag value updates
- Alarm status changes
- Device status changes
- Operation log events

Clients connect to ws://host/ws?token=<jwt>
Messages are JSON: {"type": "...", "data": {...}}
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Optional
from loguru import logger
from fastapi import WebSocket, WebSocketDisconnect
from jose import jwt, JWTError


class ConnectionManager:
    """Manages all WebSocket connections."""

    def __init__(self):
        self._connections: dict[int, list[WebSocket]] = {}  # user_id -> [ws]
        self._all: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(user_id, []).append(websocket)
            self._all.append(websocket)
        logger.info(f"WS connected: user_id={user_id}, total={len(self._all)}")

    async def disconnect(self, websocket: WebSocket, user_id: int):
        async with self._lock:
            conns = self._connections.get(user_id, [])
            if websocket in conns:
                conns.remove(websocket)
            if websocket in self._all:
                self._all.remove(websocket)
            if not conns:
                self._connections.pop(user_id, None)
        logger.info(f"WS disconnected: user_id={user_id}, total={len(self._all)}")

    async def broadcast(self, message: dict):
        """Send to all connected clients."""
        payload = json.dumps(message, default=str)
        dead = []
        for ws in self._all:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            try:
                self._all.remove(ws)
            except ValueError:
                pass

    async def send_to_user(self, user_id: int, message: dict):
        """Send to a specific user."""
        payload = json.dumps(message, default=str)
        conns = self._connections.get(user_id, [])
        dead = []
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            conns.remove(ws)

    @property
    def connection_count(self) -> int:
        return len(self._all)


# Global instance
ws_manager = ConnectionManager()


# ── Event pushers (called by engines / services) ──

async def push_live_value(device_id: int, tag_id: int, tag_name: str, value: float, quality: str = "good"):
    """Push a live value update to all clients (supports multi-worker via Redis)."""
    from app.engine.ws_broadcast import broadcast_live_value
    broadcast_live_value(device_id, tag_id, tag_name, value, quality)


async def push_alarm_event(event_type: str, alarm: dict):
    """Push alarm event (supports multi-worker via Redis)."""
    from app.engine.ws_broadcast import broadcast_alarm_event
    broadcast_alarm_event(event_type, alarm)


async def push_device_status(device_id: int, device_name: str, status: str, error: str = None):
    """Push device status change (supports multi-worker via Redis)."""
    from app.engine.ws_broadcast import broadcast_device_status
    broadcast_device_status(device_id, device_name, status, error)


async def push_operation_log(log: dict):
    """Push operation audit log (supports multi-worker via Redis)."""
    from app.engine.ws_broadcast import broadcast_operation_log
    broadcast_operation_log(log)
