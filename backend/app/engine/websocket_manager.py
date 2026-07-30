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

    HEARTBEAT_TIMEOUT = 60  # seconds — close connections that haven't responded

    def __init__(self):
        self._connections: dict[int, list[WebSocket]] = {}  # user_id -> [ws]
        self._all: list[WebSocket] = []
        self._ws_last_active: dict[int, float] = {}  # ws id -> last activity timestamp
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        await self._register(websocket, user_id)

    async def register(self, websocket: WebSocket, user_id: int):
        """Register an already-accepted websocket (e.g., after message-based auth)."""
        await self._register(websocket, user_id)

    async def _register(self, websocket: WebSocket, user_id: int):
        async with self._lock:
            self._connections.setdefault(user_id, []).append(websocket)
            self._all.append(websocket)
            self._ws_last_active[id(websocket)] = time.time()
        logger.info(f"WS connected: user_id={user_id}, total={len(self._all)}")

    async def disconnect(self, websocket: WebSocket, user_id: int):
        async with self._lock:
            conns = self._connections.get(user_id, [])
            if websocket in conns:
                conns.remove(websocket)
            if websocket in self._all:
                self._all.remove(websocket)
            self._ws_last_active.pop(id(websocket), None)
            if not conns:
                self._connections.pop(user_id, None)
        logger.info(f"WS disconnected: user_id={user_id}, total={len(self._all)}")

    async def broadcast(self, message: dict):
        """Send to all connected clients."""
        payload = json.dumps(message, default=str)
        async with self._lock:
            all_ws = list(self._all)
        dead = []
        for ws in all_ws:
            try:
                await ws.send_text(payload)
                self._ws_last_active[id(ws)] = time.time()
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self._remove_ws_full(ws)

    async def send_to_user(self, user_id: int, message: dict):
        """Send to a specific user."""
        payload = json.dumps(message, default=str)
        async with self._lock:
            conns = list(self._connections.get(user_id, []))
        dead = []
        for ws in conns:
            try:
                await ws.send_text(payload)
                self._ws_last_active[id(ws)] = time.time()
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self._remove_ws_full(ws)

    async def _remove_ws(self, ws: WebSocket):
        """Remove a websocket from all tracking structures."""
        try:
            self._all.remove(ws)
        except ValueError:
            pass
        self._ws_last_active.pop(id(ws), None)

    async def _remove_ws_full(self, ws: WebSocket):
        """Remove a websocket from all tracking structures (including user connection map)."""
        async with self._lock:
            try:
                self._all.remove(ws)
            except ValueError:
                pass
            self._ws_last_active.pop(id(ws), None)
            # Also remove from user connection map
            for uid, conns in self._connections.items():
                if ws in conns:
                    conns.remove(ws)
                    break

    async def check_heartbeats(self):
        """Close connections that haven't had activity within the timeout window.
        
        Should be called periodically (e.g. every 30s) from the app lifespan.
        """
        now = time.time()
        dead = []
        for ws in self._all:
            last = self._ws_last_active.get(id(ws), 0)
            if now - last > self.HEARTBEAT_TIMEOUT:
                dead.append(ws)
        for ws in dead:
            try:
                await ws.close(code=1000, reason="heartbeat timeout")
            except Exception:
                pass
            await self._remove_ws(ws)
        if dead:
            logger.warning(f"WS heartbeat cleanup: closed {len(dead)} stale connections")

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
