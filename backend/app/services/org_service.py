"""Organization scope service.

统一的数据范围入口：
  get_user_org_scope(db, user)      -> None(不受限) | set[int](可见组织节点 id 集合，含子树)
  get_visible_device_ids(db, user)  -> None(不受限) | set[int](可见设备 id 集合)
  apply_device_org_filter(q, db, user) -> 对 Device 查询应用组织过滤

规则:
  - 传统 admin（user.role == 'admin'）不受限
  - 任一角色 data_scope == 'all' 不受限
  - 否则聚合所有角色绑定的组织节点，展开为子树节点集合
  - 无任何组织绑定的受限用户 => 空集合（什么都看不到）
  - 未归属任何组织节点的设备，仅不受限用户可见
"""
from typing import Optional, Set
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.device import Device
from app.models.permission import UserRole, Role
from app.models.org import OrgNode, RoleOrgScope


def expand_org_subtree(db: Session, root_ids: Set[int]) -> Set[int]:
    """展开组织节点集合为包含所有后代的完整集合（一次查询全表，内存展开）。"""
    if not root_ids:
        return set()
    rows = db.query(OrgNode.id, OrgNode.parent_id).all()
    children_map: dict = {}
    for nid, pid in rows:
        children_map.setdefault(pid, []).append(nid)

    result: Set[int] = set()
    stack = [rid for rid in root_ids]
    while stack:
        cur = stack.pop()
        if cur in result:
            continue
        result.add(cur)
        stack.extend(children_map.get(cur, []))
    return result


def get_user_org_scope(db: Session, user: User) -> Optional[Set[int]]:
    """返回用户可见的组织节点 id 集合（含子树）；None 表示不受限。"""
    if user.role == "admin":
        return None

    user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()
    if not user_roles:
        return set()

    root_ids: Set[int] = set()
    for ur in user_roles:
        role: Optional[Role] = ur.role
        if not role:
            continue
        if (role.data_scope or "all") == "all":
            return None  # 任一角色为全部数据 => 不受限
        for scope in role.org_scopes:
            root_ids.add(scope.org_node_id)

    return expand_org_subtree(db, root_ids)


def get_visible_device_ids(db: Session, user: User) -> Optional[Set[int]]:
    """返回用户可见设备 id 集合；None 表示不受限。"""
    org_ids = get_user_org_scope(db, user)
    if org_ids is None:
        return None
    if not org_ids:
        return set()
    rows = db.query(Device.id).filter(Device.org_node_id.in_(org_ids)).all()
    return {r[0] for r in rows}


def apply_device_org_filter(query, db: Session, user: User):
    """对 Device 查询应用组织数据范围过滤。"""
    org_ids = get_user_org_scope(db, user)
    if org_ids is None:
        return query
    if not org_ids:
        return query.filter(Device.id == -1)  # 空结果
    return query.filter(Device.org_node_id.in_(org_ids))


def check_device_visible(db: Session, user: User, device_id: int) -> bool:
    """单设备可见性校验（用于详情/控制/实时等单点接口）。"""
    ids = get_visible_device_ids(db, user)
    if ids is None:
        return True
    return device_id in ids
