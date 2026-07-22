"""WebSocket broadcast via Redis pub/sub for multi-worker support.

When running multiple uvicorn workers, each process has its own
WebSocket connection pool. This module uses Redis pub/sub to
broadcast messages across all workers.

Architecture:
  Worker 1: alarm_service → publish to Redis channel
  Worker 2: ws_manager → receive from Redis → send to local clients
  Worker 3: ws_manager → receive from Redis → send to local clients
"""
import json
import asyncio
import threading
from typing import Optional
from loguru import logger


REDIS_CHANNEL = "modbus_ws_broadcast"
_redis_client = None
_subscriber_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
# The running event loop, captured at startup via set_main_loop().
# Broadcasts are fired from background threads; run_coroutine_threadsafe
# needs the *actual running* loop, not a fresh one.
_main_loop = None


def init_redis_broadcast():
    """Initialize Redis pub/sub subscriber in background thread."""
    global _redis_client
    try:
        import redis
        from app.core.config import settings
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB + 1,  # use different DB from cache
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )
        _redis_client.ping()
        logger.info(f"Redis broadcast initialized: {settings.REDIS_HOST}:{settings.REDIS_PORT}")

        _start_subscriber()
    except Exception as e:
        logger.warning(f"Redis broadcast not available (single worker mode): {e}")


def _start_subscriber():
    """Start background thread that subscribes to Redis channel."""
    global _subscriber_thread
    _stop_event.clear()
    _subscriber_thread = threading.Thread(target=_subscriber_loop, daemon=True, name="ws-redis-sub")
    _subscriber_thread.start()


def _subscriber_loop():
    """Listen for broadcast messages and forward to local WebSocket clients."""
    if not _redis_client:
        return

    pubsub = _redis_client.pubsub()
    pubsub.subscribe(REDIS_CHANNEL)
    logger.info(f"WS broadcast subscriber listening on '{REDIS_CHANNEL}'")

    for message in pubsub.listen():
        if _stop_event.is_set():
            break
        if message["type"] != "message":
            continue

        try:
            data = json.loads(message["data"])
            # Forward to local WebSocket clients
            asyncio.run_coroutine_threadsafe(
                _broadcast_local(data),
                _get_event_loop(),
            )
        except Exception as e:
            logger.error(f"WS broadcast error: {e}")


async def _broadcast_local(message: dict):
    """Broadcast message to all locally connected WebSocket clients."""
    from app.engine.websocket_manager import ws_manager
    await ws_manager.broadcast(message)


def set_main_loop(loop):
    """Store the running event loop (called from the app lifespan).

    Broadcasts are triggered from background threads (polling /
    alarm evaluation). ``asyncio.run_coroutine_threadsafe`` needs
    the *actual running* loop, not one we spin up locally (a loop
    that is never started would silently drop every broadcast).
    """
    global _main_loop
    _main_loop = loop


def _get_event_loop():
    """Return the running event loop for async operations.

    Prefers the loop captured at startup (``set_main_loop``); falls
    back to the current thread's loop only when none was stored.
    """
    if _main_loop is not None and not _main_loop.is_closed():
        return _main_loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def publish_event(event_type: str, data: dict):
    """Publish an event to all workers via Redis."""
    if not _redis_client:
        # Fallback: direct local broadcast (single worker mode)
        try:
            asyncio.run_coroutine_threadsafe(
                _broadcast_local({"type": event_type, "data": data}),
                _get_event_loop(),
            )
        except Exception:
            pass
        return

    try:
        message = json.dumps({"type": event_type, "data": data}, default=str)
        _redis_client.publish(REDIS_CHANNEL, message)
    except Exception as e:
        logger.error(f"Redis publish error: {e}")


def stop_broadcast():
    """Stop the subscriber thread."""
    _stop_event.clear()
    if _subscriber_thread:
        _subscriber_thread.join(timeout=3)


# ── Convenience functions for common events ──

def broadcast_live_value(device_id: int, tag_id: int, tag_name: str, value: float, quality: str = "good"):
    from datetime import datetime, timezone
    publish_event("live_value", {
        "device_id": device_id, "tag_id": tag_id, "tag_name": tag_name,
        "value": value, "quality": quality, "time": datetime.now(timezone.utc).isoformat(),
    })


def broadcast_alarm_event(event_type: str, alarm: dict):
    publish_event(f"alarm_{event_type}", alarm)


def broadcast_device_status(device_id: int, device_name: str, status: str, error: str = None):
    from datetime import datetime
    publish_event("device_status", {
        "device_id": device_id, "device_name": device_name,
        "status": status, "error": error, "time": datetime.now(timezone.utc).isoformat(),
    })


def broadcast_operation_log(log: dict):
    publish_event("operation_log", log)
