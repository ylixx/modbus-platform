"""Alarm MQTT publish configuration API."""
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.models.alarm_mqtt import AlarmMqttConfig
from app.schemas.alarm_mqtt import AlarmMqttConfigCreate, AlarmMqttConfigUpdate, AlarmMqttConfigOut
from app.schemas.common import ResponseModel
from app.services.audit_service import log_action
from app.services.alarm_mqtt_publisher import alarm_mqtt_publisher
from typing import List

router = APIRouter(prefix="/alarms/mqtt", tags=["报警MQTT推送"])


@router.get("", response_model=List[AlarmMqttConfigOut])
def list_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("alarm.read")),
):
    """列出所有 MQTT 推送配置。"""
    return db.query(AlarmMqttConfig).order_by(AlarmMqttConfig.id).all()


@router.post("", response_model=AlarmMqttConfigOut)
def create_config(
    req: AlarmMqttConfigCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alarm.write")),
):
    """创建 MQTT 推送配置。"""
    config = AlarmMqttConfig(**req.model_dump())
    db.add(config)
    try:
        db.commit()
        db.refresh(config)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建失败: {e}")
    log_action(action="alarm_mqtt.create", resource_type="alarm_mqtt_config", resource_id=config.id,
               resource_name=config.name, detail="",
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return config


@router.put("/{config_id}", response_model=AlarmMqttConfigOut)
def update_config(
    config_id: int,
    req: AlarmMqttConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alarm.write")),
):
    """更新 MQTT 推送配置。"""
    config = db.query(AlarmMqttConfig).filter(AlarmMqttConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    changed = req.model_dump(exclude_unset=True)
    for k, v in changed.items():
        setattr(config, k, v)
    log_action(action="alarm_mqtt.update", resource_type="alarm_mqtt_config", resource_id=config.id,
               resource_name=config.name, detail=json.dumps(changed, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
        db.refresh(config)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")
    # 配置变更后清理旧客户端连接
    alarm_mqtt_publisher.cleanup(config_id)
    return config


@router.delete("/{config_id}")
def delete_config(
    config_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("alarm.write")),
):
    """删除 MQTT 推送配置。"""
    config = db.query(AlarmMqttConfig).filter(AlarmMqttConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    db.delete(config)
    log_action(action="alarm_mqtt.delete", resource_type="alarm_mqtt_config", resource_id=config.id,
               resource_name=config.name, detail="",
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    alarm_mqtt_publisher.cleanup(config_id)
    return ResponseModel(message="删除成功")


@router.post("/{config_id}/test")
def test_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("alarm.write")),
):
    """测试 MQTT 推送配置（发送一条测试消息）。"""
    config = db.query(AlarmMqttConfig).filter(AlarmMqttConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    alarm_data = {
        "device_id": 0,
        "device_name": "测试设备",
        "tag_id": 0,
        "tag_name": "测试点位",
        "alarm_type": "threshold_high",
        "alarm_level": "warning",
        "alarm_message": "这是一条MQTT推送测试消息",
        "trigger_value": 99.9,
        "threshold_value": 80.0,
        "triggered_at": "2026-01-01T00:00:00",
    }
    try:
        alarm_mqtt_publisher._publish_one(config, "triggered", alarm_data)
        return ResponseModel(message="测试消息已发送，请检查Broker是否收到")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试发送失败: {e}")
