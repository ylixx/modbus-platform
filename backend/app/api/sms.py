"""SMS management API."""
import json, logging, logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.sms import SmsContact, SmsPushRule, SmsRecord
from app.services.audit_service import log_action
from app.schemas.sms import (
    SmsContactCreate, SmsContactUpdate, SmsContactOut,
    SmsPushRuleCreate, SmsPushRuleUpdate, SmsPushRuleOut,
    SmsRecordOut, SmsTestRequest,
)
from app.schemas.common import ResponseModel, PageResponse
from typing import List

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sms", tags=["短信管理"])


# ============ Contacts ============

@router.get("/contacts", response_model=PageResponse)
def list_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sms.read")),
):
    q = db.query(SmsContact)
    total = q.count()
    items = q.order_by(SmsContact.id).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(total=total, page=page, page_size=page_size, data=[SmsContactOut.model_validate(i) for i in items])


@router.post("/contacts", response_model=SmsContactOut)
def create_contact(req: SmsContactCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("sms.write"))):
    if db.query(SmsContact).filter(SmsContact.phone == req.phone).first():
        raise HTTPException(status_code=400, detail="手机号已存在")
    contact = SmsContact(**req.model_dump())
    db.add(contact)
    try:
        db.commit()
        db.refresh(contact)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="创建失败，请稍后重试")
    log_action(action="sms.contact.create", resource_type="sms_contact", resource_id=contact.id,
               resource_name=contact.name, detail=json.dumps({"phone": contact.phone}, ensure_ascii=False),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return contact


@router.put("/contacts/{contact_id}", response_model=SmsContactOut)
def update_contact(contact_id: int, req: SmsContactUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("sms.write"))):
    contact = db.query(SmsContact).filter(SmsContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="联系人不存在")
    changed = req.model_dump(exclude_unset=True)
    for k, v in changed.items():
        setattr(contact, k, v)
    log_action(action="sms.contact.update", resource_type="sms_contact", resource_id=contact.id,
               resource_name=contact.name, detail=json.dumps(changed, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
        db.refresh(contact)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="更新失败，请稍后重试")
    return contact


@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("sms.write"))):
    contact = db.query(SmsContact).filter(SmsContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="联系人不存在")
    db.delete(contact)
    log_action(action="sms.contact.delete", resource_type="sms_contact", resource_id=contact.id,
               resource_name=contact.name, detail="",
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="删除失败，请稍后重试")
    return ResponseModel(message="删除成功")


# ============ Push Rules ============

@router.get("/rules", response_model=PageResponse)
def list_push_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sms.read")),
):
    q = db.query(SmsPushRule)
    total = q.count()
    items = q.order_by(SmsPushRule.id).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(total=total, page=page, page_size=page_size, data=[SmsPushRuleOut.model_validate(i) for i in items])


@router.post("/rules", response_model=SmsPushRuleOut)
def create_push_rule(req: SmsPushRuleCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("sms.write"))):
    rule = SmsPushRule(**req.model_dump())
    db.add(rule)
    try:
        db.commit()
        db.refresh(rule)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="创建失败，请稍后重试")
    log_action(action="sms.push_rule.create", resource_type="sms_push_rule", resource_id=rule.id,
               resource_name=rule.name, detail=json.dumps({"alarm_levels": getattr(rule, 'alarm_levels', None)}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return rule


@router.put("/rules/{rule_id}", response_model=SmsPushRuleOut)
def update_push_rule(rule_id: int, req: SmsPushRuleUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("sms.write"))):
    rule = db.query(SmsPushRule).filter(SmsPushRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    changed = req.model_dump(exclude_unset=True)
    for k, v in changed.items():
        setattr(rule, k, v)
    log_action(action="sms.push_rule.update", resource_type="sms_push_rule", resource_id=rule.id,
               resource_name=rule.name, detail=json.dumps(changed, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
        db.refresh(rule)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="更新失败，请稍后重试")
    return rule


@router.delete("/rules/{rule_id}")
def delete_push_rule(rule_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("sms.write"))):
    rule = db.query(SmsPushRule).filter(SmsPushRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(rule)
    log_action(action="sms.push_rule.delete", resource_type="sms_push_rule", resource_id=rule.id,
               resource_name=rule.name, detail="",
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="删除失败，请稍后重试")
    return ResponseModel(message="删除成功")


# ============ SMS Records ============

@router.get("/records", response_model=PageResponse)
def list_sms_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sms.read")),
):
    q = db.query(SmsRecord)
    if status:
        q = q.filter(SmsRecord.status == status)
    total = q.count()
    items = q.order_by(SmsRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(total=total, page=page, page_size=page_size, data=[SmsRecordOut.model_validate(i) for i in items])


# ============ Test SMS ============

@router.post("/test")
def test_sms(req: SmsTestRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("sms.send"))):
    from app.services.sms_service import sms_service
    success = sms_service.send_sms(req.phone, req.content)
    log_action(action="sms.send_test", resource_type="sms_contact", resource_id=0,
               resource_name=req.phone, detail=json.dumps({"phone": req.phone, "success": success}, ensure_ascii=False),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    if success:
        return ResponseModel(message="短信发送成功")
    raise HTTPException(status_code=500, detail="短信发送失败，请检查短信配置")
