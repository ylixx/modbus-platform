"""Authentication API."""
import json
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.core.database import get_db
from app.core.deps import create_access_token, get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, LoginRequest, TokenResponse, UserUpdate, ChangePasswordRequest
from app.schemas.common import ResponseModel
from app.services.audit_service import log_action

router = APIRouter(prefix="/auth", tags=["认证"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _aggregate_permissions(user: User) -> list[str]:
    """聚合用户所有角色的权限码（User -> UserRole -> Role -> RolePermission -> Permission.code）。"""
    perms: set[str] = set()
    for ur in user.roles:
        for rp in ur.role.permissions:
            if rp.permission:
                perms.add(rp.permission.code)
    return sorted(perms)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not pwd_context.verify(req.password, user.hashed_password):
        # 记录登录失败审计日志
        log_action(action="auth.login_failed", resource_type="user", resource_id=0,
                   resource_name=req.username, detail="用户名或密码错误", user_id=0, username=req.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        log_action(action="auth.login_disabled", resource_type="user", resource_id=user.id,
                   resource_name=user.username, detail="账号已禁用", user_id=0, username=req.username)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
    token = create_access_token({"sub": str(user.id)})
    user_out = UserOut.model_validate(user)
    user_out.permissions = _aggregate_permissions(user)
    return TokenResponse(access_token=token, user=user_out)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    user_out = UserOut.model_validate(current_user)
    user_out.permissions = _aggregate_permissions(current_user)
    return user_out


@router.put("/me", response_model=UserOut)
def update_me(req: UserUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    changed = req.model_dump(exclude_unset=True)
    for k, v in changed.items():
        if k in ("display_name", "phone", "email"):
            setattr(current_user, k, v)
    log_action(action="user.update_profile", resource_type="user", resource_id=current_user.id,
               resource_name=current_user.username, detail=json.dumps(changed, ensure_ascii=False, default=str),
               user_id=current_user.id, username=current_user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
        db.refresh(current_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")
    user_out = UserOut.model_validate(current_user)
    user_out.permissions = _aggregate_permissions(current_user)
    return user_out


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not pwd_context.verify(req.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    current_user.hashed_password = pwd_context.hash(req.new_password)
    log_action(action="user.change_password", resource_type="user", resource_id=current_user.id,
               resource_name=current_user.username, detail="用户自行修改密码",
               user_id=current_user.id, username=current_user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"密码修改失败: {e}")
    return {"message": "密码修改成功"}
