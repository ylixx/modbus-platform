"""Permission & Role management API."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.permission import Permission, Role, RolePermission, UserRole
from app.models.org import RoleOrgScope
from app.schemas.common import ResponseModel
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/rbac", tags=["权限管理"])


# ── Schemas ──

class PermissionOut(BaseModel):
    id: int
    code: str
    name: str
    module: str
    description: str
    class Config:
        from_attributes = True

class RoleCreate(BaseModel):
    code: str
    name: str
    description: str = ""
    permission_ids: List[int] = []
    data_scope: str = "all"              # all | org
    org_node_ids: List[int] = []         # data_scope='org' 时绑定的组织节点

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None
    data_scope: Optional[str] = None     # all | org
    org_node_ids: Optional[List[int]] = None

class RoleOut(BaseModel):
    id: int
    code: str
    name: str
    description: str
    is_system: bool
    data_scope: str = "all"
    org_node_ids: List[int] = []
    permissions: List[PermissionOut] = []
    class Config:
        from_attributes = True

class UserRoleAssign(BaseModel):
    user_id: int
    role_id: int
    data_scope: str = "all"         # all | factory | workshop | self
    scope_values: List[str] = []    # e.g. ["区级A", "区级B"]

class UserRoleOut(BaseModel):
    id: int
    user_id: int
    role_id: int
    role_code: str = ""
    role_name: str = ""
    data_scope: str
    scope_values: List[str] = []


# ── Permissions ──

@router.get("/permissions", response_model=List[PermissionOut])
def list_permissions(
    module: str = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("rbac.read")),
):
    q = db.query(Permission)
    if module:
        q = q.filter(Permission.module == module)
    return q.order_by(Permission.module, Permission.code).all()


# ── Roles ──

def _role_out(role: Role) -> RoleOut:
    perms = [rp.permission for rp in role.permissions if rp.permission]
    org_ids = [s.org_node_id for s in role.org_scopes]
    return RoleOut(
        id=role.id, code=role.code, name=role.name, description=role.description,
        is_system=role.is_system, data_scope=role.data_scope or "all",
        org_node_ids=org_ids,
        permissions=[PermissionOut.model_validate(p) for p in perms],
    )


@router.get("/roles", response_model=List[RoleOut])
def list_roles(db: Session = Depends(get_db), _: User = Depends(require_permission("rbac.read"))):
    roles = db.query(Role).order_by(Role.id).all()
    return [_role_out(r) for r in roles]


@router.post("/roles", response_model=RoleOut)
def create_role(req: RoleCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("rbac.write"))):
    if db.query(Role).filter(Role.code == req.code).first():
        raise HTTPException(status_code=400, detail="角色代码已存在")
    if req.data_scope not in ("all", "org"):
        raise HTTPException(status_code=400, detail="无效数据范围，仅支持 all / org")
    role = Role(code=req.code, name=req.name, description=req.description, data_scope=req.data_scope)
    db.add(role)
    db.flush()
    for pid in req.permission_ids:
        db.add(RolePermission(role_id=role.id, permission_id=pid))
    if req.data_scope == "org":
        for nid in set(req.org_node_ids):
            db.add(RoleOrgScope(role_id=role.id, org_node_id=nid))
    db.commit()
    db.refresh(role)
    return _role_out(role)


@router.put("/roles/{role_id}", response_model=RoleOut)
def update_role(role_id: int, req: RoleUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("rbac.write"))):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if req.name is not None:
        role.name = req.name
    if req.description is not None:
        role.description = req.description
    if req.permission_ids is not None:
        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
        for pid in req.permission_ids:
            db.add(RolePermission(role_id=role_id, permission_id=pid))
    if req.data_scope is not None:
        if req.data_scope not in ("all", "org"):
            raise HTTPException(status_code=400, detail="无效数据范围，仅支持 all / org")
        if role.code == "admin":
            raise HTTPException(status_code=400, detail="admin 角色不可限制数据范围")
        role.data_scope = req.data_scope
    if req.org_node_ids is not None:
        db.query(RoleOrgScope).filter(RoleOrgScope.role_id == role_id).delete()
        if (role.data_scope or "all") == "org":
            for nid in set(req.org_node_ids):
                db.add(RoleOrgScope(role_id=role_id, org_node_id=nid))
    db.commit()
    db.refresh(role)
    return _role_out(role)


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("rbac.write"))):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统角色不可删除")
    db.delete(role)
    db.commit()
    return {"message": "删除成功"}


# ── User-Role assignment ──

@router.get("/users/{user_id}/roles", response_model=List[UserRoleOut])
def get_user_roles(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("rbac.read"))):
    urs = db.query(UserRole).filter(UserRole.user_id == user_id).all()
    result = []
    for ur in urs:
        try:
            vals = json.loads(ur.scope_values) if ur.scope_values else []
        except (json.JSONDecodeError, TypeError):
            vals = []
        result.append(UserRoleOut(
            id=ur.id, user_id=ur.user_id, role_id=ur.role_id,
            role_code=ur.role.code if ur.role else "", role_name=ur.role.name if ur.role else "",
            data_scope=ur.data_scope, scope_values=vals,
        ))
    return result


@router.post("/users/{user_id}/roles")
def assign_user_role(user_id: int, req: UserRoleAssign, db: Session = Depends(get_db), _: User = Depends(require_permission("rbac.write"))):
    # Check if already assigned
    existing = db.query(UserRole).filter(UserRole.user_id == user_id, UserRole.role_id == req.role_id).first()
    if existing:
        existing.data_scope = req.data_scope
        existing.scope_values = json.dumps(req.scope_values, ensure_ascii=False)
    else:
        ur = UserRole(
            user_id=user_id, role_id=req.role_id,
            data_scope=req.data_scope,
            scope_values=json.dumps(req.scope_values, ensure_ascii=False),
        )
        db.add(ur)
    db.commit()
    return {"message": "分配成功"}


@router.delete("/user-roles/{user_role_id}")
def remove_user_role(user_role_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("rbac.write"))):
    ur = db.query(UserRole).filter(UserRole.id == user_role_id).first()
    if not ur:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(ur)
    db.commit()
    return {"message": "移除成功"}


# ── Current user info ──

@router.get("/me/permissions")
def get_my_permissions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.services.permission_service import get_user_permissions, get_user_data_scope
    perms = get_user_permissions(db, current_user)
    scope = get_user_data_scope(db, current_user)
    roles = [ur.role.code for ur in current_user.roles if ur.role] if current_user.roles else [current_user.role]
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "roles": roles,
        "permissions": list(perms),
        "data_scope": scope,
    }
