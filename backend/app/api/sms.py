"""SMS management API."""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.sms import SmsContact, SmsPushRule, SmsRecord
from app.schemas.sms import (
    SmsContactCreate, SmsContactUpdate, SmsContactOut,
    SmsPushRuleCreate, SmsPushRuleUpdate, SmsPushRuleOut,
    SmsRecordOut, SmsTestRequest,
)
from app.schemas.common import ResponseModel, PageResponse
from typing import List

router = APIRouter(prefix="/sms", tags=["短信管理"])


# ============ Contacts ============

@router.get("/contacts", response_model=List[SmsContactOut])
def list_contacts(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(SmsContact).order_by(SmsContact.id).all()


@router.post("/contacts", response_model=SmsContactOut)
def create_contact(req: SmsContactCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if db.query(SmsContact).filter(SmsContact.phone == req.phone).first():
        raise HTTPException(status_code=400, detail="手机号已存在")
    contact = SmsContact(**req.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.put("/contacts/{contact_id}", response_model=SmsContactOut)
def update_contact(contact_id: int, req: SmsContactUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    contact = db.query(SmsContact).filter(SmsContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="联系人不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(contact, k, v)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    contact = db.query(SmsContact).filter(SmsContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="联系人不存在")
    db.delete(contact)
    db.commit()
    return {"message": "删除成功"}


# ============ Push Rules ============

@router.get("/rules", response_model=List[SmsPushRuleOut])
def list_push_rules(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(SmsPushRule).order_by(SmsPushRule.id).all()


@router.post("/rules", response_model=SmsPushRuleOut)
def create_push_rule(req: SmsPushRuleCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rule = SmsPushRule(**req.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=SmsPushRuleOut)
def update_push_rule(rule_id: int, req: SmsPushRuleUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rule = db.query(SmsPushRule).filter(SmsPushRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_push_rule(rule_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rule = db.query(SmsPushRule).filter(SmsPushRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(rule)
    db.commit()
    return {"message": "删除成功"}


# ============ SMS Records ============

@router.get("/records", response_model=PageResponse)
def list_sms_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(SmsRecord)
    if status:
        q = q.filter(SmsRecord.status == status)
    total = q.count()
    items = q.order_by(SmsRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(total=total, page=page, page_size=page_size, data=[SmsRecordOut.model_validate(i) for i in items])


# ============ Test SMS ============

@router.post("/test")
def test_sms(req: SmsTestRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from app.services.sms_service import sms_service
    success = sms_service.send_sms(req.phone, req.content)
    if success:
        return {"message": "短信发送成功"}
    raise HTTPException(status_code=500, detail="短信发送失败，请检查短信配置")
