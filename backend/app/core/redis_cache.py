"""Redis 缓存薄封装（缓存库）。

可选组件：未配置或 Redis 不可用时自动退化为 no-op，调用方逻辑不受影响。
默认 decode_responses=True，value 以 JSON 存取。
"""
import json
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("redis_cache")

_client = None
_available: Optional[bool] = None


def _get_client():
    global _client, _available
    if _available is not None:
        return _client if _available else None
    try:
        import redis

        _client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=1,
        )
        _client.ping()
        _available = True
        logger.info("Redis 缓存客户端已连接")
        return _client
    except Exception as e:
        _available = False
        logger.warning(f"Redis 不可用，缓存退化为 no-op: {e}")
        return None


def cache_set(key: str, value, ttl: int = 300):
    c = _get_client()
    if c is None:
        return
    try:
        payload = json.dumps(value) if not isinstance(value, str) else value
        c.set(key, payload, ex=ttl)
    except Exception as e:
        logger.warning(f"cache_set 失败 {key}: {e}")


def cache_get(key: str):
    c = _get_client()
    if c is None:
        return None
    try:
        raw = c.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception:
        return None


def cache_delete(key: str):
    c = _get_client()
    if c is None:
        return
    try:
        c.delete(key)
    except Exception:
        pass
