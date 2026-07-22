"""User management API (admin only)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.schemas.common import ResponseModel, PageResponse

router = APIRouter(prefix="/users", tags=["用户管理"])
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
def create_user(req: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
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
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, req: UserUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    return {"message": "删除成功"}


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, new_password: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少 6 位")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.hashed_password = pwd_context.hash(new_password)
    db.commit()
    return {"message": "密码已重置"}
