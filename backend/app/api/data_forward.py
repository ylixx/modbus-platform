"""Data forward rule API — CRUD + test publish."""
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.models.data_forward import DataForwardRule
from app.schemas.data_forward import DataForwardRuleCreate, DataForwardRuleUpdate, DataForwardRuleOut
from app.schemas.common import ResponseModel
from app.services.audit_service import log_action
from app.services.data_forward_service import data_forward_service
from typing import List

router = APIRouter(prefix="/data-forward", tags=["数据转发"])


@router.get("", response_model=List[DataForwardRuleOut])
def list_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("device.read")),
):
    """列出所有数据转发规则。"""
    return db.query(DataForwardRule).order_by(DataForwardRule.id).all()


@router.post("", response_model=DataForwardRuleOut)
def create_rule(
    req: DataForwardRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("device.write")),
):
    """创建数据转发规则。"""
    rule = DataForwardRule(**req.model_dump())
    db.add(rule)
    try:
        db.commit()
        db.refresh(rule)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建失败: {e}")
    log_action(action="data_forward.create", resource_type="data_forward_rule", resource_id=rule.id,
               resource_name=rule.name, detail="",
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    # Start the rule's publish loop
    data_forward_service.reload_rule(rule.id)
    return rule


@router.put("/{rule_id}", response_model=DataForwardRuleOut)
def update_rule(
    rule_id: int,
    req: DataForwardRuleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("device.write")),
):
    """更新数据转发规则。"""
    rule = db.query(DataForwardRule).filter(DataForwardRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    changed = req.model_dump(exclude_unset=True)
    for k, v in changed.items():
        setattr(rule, k, v)
    log_action(action="data_forward.update", resource_type="data_forward_rule", resource_id=rule.id,
               resource_name=rule.name, detail=json.dumps(changed, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
        db.refresh(rule)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")
    # Hot-reload the rule
    data_forward_service.reload_rule(rule_id)
    return rule


@router.delete("/{rule_id}")
def delete_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("device.write")),
):
    """删除数据转发规则。"""
    rule = db.query(DataForwardRule).filter(DataForwardRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(rule)
    log_action(action="data_forward.delete", resource_type="data_forward_rule", resource_id=rule.id,
               resource_name=rule.name, detail="",
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    data_forward_service.remove_rule(rule_id)
    return ResponseModel(message="删除成功")


@router.post("/{rule_id}/test")
def test_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("device.write")),
):
    """测试数据转发规则（立即发布一条当前快照）。"""
    rule = db.query(DataForwardRule).filter(DataForwardRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    from app.engine.mqtt_connection_pool import mqtt_pool
    from app.engine.mqtt_preset_renderer import preset_renderer

    mode = rule.preset_mode or "standard"
    broker = rule.broker
    port = rule.port or 1883
    username = rule.username or ""
    password = rule.password or ""

    if mode == "thingsboard_device":
        token = rule.tb_device_token or rule.username
        username = token
        password = ""
    elif mode == "thingsboard_gateway":
        token = rule.tb_device_token or rule.username
        username = token
        password = ""

    pool_key, _ = mqtt_pool.acquire(
        broker=broker, port=port, username=username, password=password,
        client_id=f"forward_test_{rule_id}", use_tls=rule.use_tls,
    )

    try:
        # Build test data
        test_values = {"test_tag": 42.0}
        data = preset_renderer.build_telemetry_data(
            device_id=0, device_name="test_device", values=test_values
        )
        if mode == "thingsboard_gateway":
            data["device_name"] = rule.tb_gateway_name or "test_device"

        context = {
            "device_name": "test_device",
            "tag_name": "test_tag",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "timestamp_ms": str(int(time.time() * 1000)),
            "values_json": json.dumps(test_values),
        }
        from datetime import datetime, timezone
        import time

        topic = preset_renderer.render_topic(mode, rule.topic_template, context)
        payload = preset_renderer.render_payload(
            preset_mode=mode, data=data,
            custom_template=rule.payload_template, context=context,
        )
        ok = mqtt_pool.publish(pool_key, topic, payload, qos=rule.qos or 0)
    finally:
        mqtt_pool.release(pool_key)

    if ok:
        return ResponseModel(message="测试消息已发送，请检查Broker")
    else:
        raise HTTPException(status_code=500, detail="测试发送失败，请检查Broker连接")
