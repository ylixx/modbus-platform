"""MQTT health monitoring API — expose pool stats and connection status."""
from fastapi import APIRouter, Depends
from app.models.user import User
from app.core.deps import require_permission
from app.engine.mqtt_connection_pool import mqtt_pool

router = APIRouter(prefix="/mqtt-health", tags=["MQTT监控"])


@router.get("")
def get_mqtt_health(
    current_user: User = Depends(require_permission("device.read")),
):
    """获取所有 MQTT 连接池的状态和统计。"""
    stats = mqtt_pool.get_stats()
    # Convert to list for frontend consumption
    result = []
    for key, info in stats.items():
        parts = key.split(":")
        broker = parts[0] if len(parts) > 0 else ""
        port = int(parts[1]) if len(parts) > 1 else 0
        username = parts[2] if len(parts) > 2 else ""
        result.append({
            "key": key,
            "broker": broker,
            "port": port,
            "username": username,
            "connected": info["connected"],
            "ref_count": info["ref_count"],
            "publish_count": info["publish_count"],
            "publish_fail_count": info["publish_fail_count"],
        })
    return result
