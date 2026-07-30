"""User management API (admin only)."""
import json, logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.services.audit_service import log_action
from app.schemas.user import UserCreate, UserOut, UserUpdate, ResetPasswordRequest
from app.schemas.common import ResponseModel, PageResponse

router = APIRouter(prefix="/users", tags=["用户管理"])

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("", response_model=PageResponse)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(User)
    if search:
        q = q.filter(User.username.contains(search) | User.display_name.contains(search))
    total = q.count()
    items = q.order_by(User.id).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(total=total, page=page, page_size=page_size, data=[UserOut.model_validate(i) for i in items])


@router.post("", response_model=UserOut)
def create_user(req: UserCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=req.username,
        hashed_password=pwd_context.hash(req.password),
        display_name=req.display_name,
        phone=req.phone,
        email=req.email,
        role=req.role,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="创建失败，请稍后重试")
    log_action(action="user.create", resource_type="user", resource_id=user.id,
               resource_name=user.username, detail=json.dumps({"display_name": user.display_name, "role": user.role}, ensure_ascii=False),
               user_id=admin.id, username=admin.username, ip_address=request.client.host if request.client else "")
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, req: UserUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    # Only allow updating fields defined in UserUpdate (exclude sensitive fields like hashed_password)
    changed = {}
    for k, v in req.model_dump(exclude_unset=True).items():
        if k in ("display_name", "phone", "email", "role", "is_active"):
            changed[k] = v
            setattr(user, k, v)
    log_action(action="user.update", resource_type="user", resource_id=user.id,
               resource_name=user.username, detail=json.dumps(changed, ensure_ascii=False, default=str),
               user_id=admin.id, username=admin.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="更新失败，请稍后重试")
    return user


@router.delete("/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    db.delete(user)
    log_action(action="user.delete", resource_type="user", resource_id=user.id,
               resource_name=user.username, detail="",
               user_id=admin.id, username=admin.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="删除失败，请稍后重试")
    return ResponseModel(message="删除成功")


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, req: ResetPasswordRequest, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.hashed_password = pwd_context.hash(req.new_password)
    log_action(action="user.reset_password", resource_type="user", resource_id=user.id,
               resource_name=user.username, detail="密码已重置",
               user_id=admin.id, username=admin.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="重置失败，请稍后重试")
    return ResponseModel(message="密码已重置")
