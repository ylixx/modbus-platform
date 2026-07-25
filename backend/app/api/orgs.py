"""Organization structure API — 组织架构（厂-区-班组-位置 灵活树）."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.device import Device
from app.models.org import OrgNode
from app.services.org_service import expand_org_subtree, get_user_org_scope

router = APIRouter(prefix="/orgs", tags=["组织架构"])

NODE_TYPES = {"factory", "area", "team", "location", "other"}


# ── Schemas ──

class OrgNodeCreate(BaseModel):
    name: str
    node_type: str = "other"
    parent_id: Optional[int] = None
    sort_order: int = 0
    description: str = ""


class OrgNodeUpdate(BaseModel):
    name: Optional[str] = None
    node_type: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    description: Optional[str] = None


class OrgNodeOut(BaseModel):
    id: int
    name: str
    node_type: str
    parent_id: Optional[int]
    sort_order: int
    description: str
    device_count: int = 0

    class Config:
        from_attributes = True


# ── Helpers ──

def _device_counts(db: Session) -> dict:
    rows = (
        db.query(Device.org_node_id, Device.id)
        .filter(Device.org_node_id.isnot(None))
        .all()
    )
    counts: dict = {}
    for org_id, _ in rows:
        counts[org_id] = counts.get(org_id, 0) + 1
    return counts


def _build_tree(nodes: List[OrgNode], counts: dict, visible: Optional[set]) -> List[dict]:
    """构建树形结构；visible 非 None 时只保留可见节点。"""
    node_map = {}
    for n in nodes:
        if visible is not None and n.id not in visible:
            continue
        node_map[n.id] = {
            "id": n.id,
            "name": n.name,
            "node_type": n.node_type or "other",
            "parent_id": n.parent_id,
            "sort_order": n.sort_order or 0,
            "description": n.description or "",
            "device_count": counts.get(n.id, 0),
            "children": [],
        }
    roots: List[dict] = []
    for item in node_map.values():
        pid = item["parent_id"]
        if pid and pid in node_map:
            node_map[pid]["children"].append(item)
        else:
            roots.append(item)

    def sort_rec(items: List[dict]):
        items.sort(key=lambda x: (x["sort_order"], x["id"]))
        for it in items:
            sort_rec(it["children"])

    sort_rec(roots)
    return roots


# ── APIs ──

@router.get("/tree")
def get_org_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("org.read")),
):
    """组织架构树（按当前用户组织范围裁剪）。"""
    nodes = db.query(OrgNode).all()
    counts = _device_counts(db)
    visible = get_user_org_scope(db, current_user)
    return _build_tree(nodes, counts, visible)


@router.get("", response_model=List[OrgNodeOut])
def list_org_nodes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("org.read")),
):
    """平铺列表（按当前用户组织范围裁剪）。"""
    nodes = db.query(OrgNode).order_by(OrgNode.sort_order, OrgNode.id).all()
    counts = _device_counts(db)
    visible = get_user_org_scope(db, current_user)
    result = []
    for n in nodes:
        if visible is not None and n.id not in visible:
            continue
        out = OrgNodeOut.model_validate(n)
        out.device_count = counts.get(n.id, 0)
        result.append(out)
    return result


@router.post("", response_model=OrgNodeOut)
def create_org_node(
    req: OrgNodeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("org.write")),
):
    if req.node_type not in NODE_TYPES:
        raise HTTPException(status_code=400, detail=f"无效节点类型: {req.node_type}")
    if req.parent_id is not None:
        parent = db.query(OrgNode).filter(OrgNode.id == req.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父节点不存在")
    dup = db.query(OrgNode).filter(
        OrgNode.parent_id == req.parent_id, OrgNode.name == req.name
    ).first()
    if dup:
        raise HTTPException(status_code=400, detail="同级下已存在同名节点")
    node = OrgNode(**req.model_dump())
    db.add(node)
    db.commit()
    db.refresh(node)
    return OrgNodeOut.model_validate(node)


@router.put("/{node_id}", response_model=OrgNodeOut)
def update_org_node(
    node_id: int,
    req: OrgNodeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("org.write")),
):
    node = db.query(OrgNode).filter(OrgNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    data = req.model_dump(exclude_unset=True)
    if "node_type" in data and data["node_type"] not in NODE_TYPES:
        raise HTTPException(status_code=400, detail=f"无效节点类型: {data['node_type']}")
    # 防止把节点移动到自己的子树里造成环
    if "parent_id" in data and data["parent_id"] is not None:
        if data["parent_id"] == node_id:
            raise HTTPException(status_code=400, detail="不能把节点设为自己的父节点")
        subtree = expand_org_subtree(db, {node_id})
        if data["parent_id"] in subtree:
            raise HTTPException(status_code=400, detail="不能移动到自己的子节点下")
        if not db.query(OrgNode).filter(OrgNode.id == data["parent_id"]).first():
            raise HTTPException(status_code=404, detail="父节点不存在")
    for k, v in data.items():
        setattr(node, k, v)
    db.commit()
    db.refresh(node)
    return OrgNodeOut.model_validate(node)


@router.delete("/{node_id}")
def delete_org_node(
    node_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("org.write")),
):
    node = db.query(OrgNode).filter(OrgNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    subtree = expand_org_subtree(db, {node_id})
    device_count = db.query(Device).filter(Device.org_node_id.in_(subtree)).count()
    if device_count > 0 and not force:
        raise HTTPException(
            status_code=400,
            detail=f"该节点及子节点下还有 {device_count} 台设备，请先移走设备或使用强制删除",
        )
    # 解除设备归属，再删除整个子树
    if device_count:
        db.query(Device).filter(Device.org_node_id.in_(subtree)).update(
            {"org_node_id": None}, synchronize_session=False
        )
    db.query(OrgNode).filter(OrgNode.id.in_(subtree)).delete(synchronize_session=False)
    db.commit()
    return {"message": "删除成功", "removed_nodes": len(subtree), "detached_devices": device_count}


@router.post("/{node_id}/move-devices")
def move_devices_to_node(
    node_id: int,
    device_ids: List[int],
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("org.write")),
):
    """批量把设备挂到指定组织节点。"""
    node = db.query(OrgNode).filter(OrgNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")
    updated = (
        db.query(Device)
        .filter(Device.id.in_(device_ids))
        .update({"org_node_id": node_id}, synchronize_session=False)
    )
    db.commit()
    return {"message": "移动成功", "updated": updated}
