"""Device-level MQTT publish API — status monitoring & manual trigger."""
from fastapi import APIRouter, Depends, HTTPException
from app.models.user import User
from app.core.deps import require_permission

router = APIRouter(prefix="/device-publish", tags=["设备发布"])


@router.get("/status")
def get_publish_status(
    current_user: User = Depends(require_permission("device.read")),
):
    """获取所有已启用MQTT发布的设备的运行状态。"""
    from app.services.device_publish_service import device_publish_service
    return device_publish_service.get_status()


@router.post("/{device_id}/trigger")
def trigger_publish(
    device_id: int,
    current_user: User = Depends(require_permission("device.write")),
):
    """手动触发一次设备MQTT数据发布（用于调试/测试）。"""
    from app.services.device_publish_service import device_publish_service
    ok = device_publish_service.trigger(device_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"设备 {device_id} 未启用MQTT发布或发布失败，请检查配置",
        )
    return {"message": "触发成功", "device_id": device_id}
