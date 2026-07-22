"""FastAPI dependencies — auth + RBAC + data scope."""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User

security = HTTPBearer()
ALGORITHM = "HS256"


def create_access_token(data: dict) -> str:
    from datetime import datetime, timedelta, timezone
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")
    return user


# ── RBAC: permission check ──

def require_permission(permission_code: str):
    """Dependency factory: require a specific permission."""
    def _check(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        from app.services.permission_service import get_user_permissions, has_permission
        perms = get_user_permissions(db, current_user)
        if not has_permission(perms, permission_code):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"需要权限: {permission_code}")
        return current_user
    return _check


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Legacy admin check (backward compat)."""
    from app.services.permission_service import get_user_permissions
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        perms = get_user_permissions(db, current_user)
        if "*" not in perms and "system.admin" not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    finally:
        db.close()
    return current_user


# ── Data scope filter ──

def get_scoped_device_query(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns a function that applies data scope to Device queries."""
    from app.models.device import Device
    from app.services.permission_service import apply_data_scope_filter
    base_query = db.query(Device)
    return apply_data_scope_filter(base_query, Device, db, current_user)
