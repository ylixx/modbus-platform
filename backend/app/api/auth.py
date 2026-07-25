"""Authentication API."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.core.database import get_db
from app.core.deps import create_access_token, get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, LoginRequest, TokenResponse, UserUpdate
from app.schemas.common import ResponseModel

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
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
def update_me(req: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(current_user, k, v)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password")
def change_password(old_password: str, new_password: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not pwd_context.verify(old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    current_user.hashed_password = pwd_context.hash(new_password)
    db.commit()
    return {"message": "密码修改成功"}
