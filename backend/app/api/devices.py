"""Device management API."""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.device import Device, DeviceGroup, DeviceTag
from app.schemas.device import (
    DeviceCreate, DeviceUpdate, DeviceOut, DeviceDetailOut,
    GroupCreate, GroupUpdate, GroupOut,
    TagCreate, TagUpdate, TagOut,
    WriteRequest,
)
from app.schemas.common import ResponseModel, PageResponse
from typing import List

router = APIRouter(prefix="/devices", tags=["设备管理"])


# ============ Device Groups ============

@router.get("/groups", response_model=List[GroupOut])
def list_groups(db: Session = Depends(get_db), _: User = Depends(require_permission("group.read"))):
    return db.query(DeviceGroup).order_by(DeviceGroup.sort_order, DeviceGroup.id).all()


@router.post("/groups", response_model=GroupOut)
def create_group(req: GroupCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("group.write"))):
    if db.query(DeviceGroup).filter(DeviceGroup.name == req.name).first():
        raise HTTPException(status_code=400, detail="分组名已存在")
    group = DeviceGroup(**req.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.put("/groups/{group_id}", response_model=GroupOut)
def update_group(group_id: int, req: GroupUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("group.write"))):
    group = db.query(DeviceGroup).filter(DeviceGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(group, k, v)
    db.commit()
    db.refresh(group)
    return group


@router.delete("/groups/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("group.write"))):
    group = db.query(DeviceGroup).filter(DeviceGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    db.delete(group)
    db.commit()
    return {"message": "删除成功"}


# ============ Locations ============

@router.get("/locations")
def get_locations(db: Session = Depends(get_db), _: User = Depends(require_permission("device.read"))):
    """Get distinct factory/workshop/line values for filter dropdowns."""
    factories = [r[0] for r in db.query(Device.factory).filter(Device.factory != "").distinct().all()]
    workshops = [r[0] for r in db.query(Device.workshop).filter(Device.workshop != "").distinct().all()]
    lines = [r[0] for r in db.query(Device.production_line).filter(Device.production_line != "").distinct().all()]
    return {"factories": factories, "workshops": workshops, "production_lines": lines}


# ============ Devices ============

@router.get("", response_model=PageResponse)
def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    group_id: int = None,
    protocol: str = None,
    status: str = None,
    factory: str = None,
    workshop: str = None,
    search: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("device.read")),
):
    q = db.query(Device)
    if group_id is not None:
        q = q.filter(Device.group_id == group_id)
    if protocol:
        q = q.filter(Device.protocol == protocol)
    if status:
        q = q.filter(Device.status == status)
    if factory:
        q = q.filter(Device.factory == factory)
    if workshop:
        q = q.filter(Device.workshop == workshop)
    if search:
        q = q.filter(Device.name.contains(search) | Device.host.contains(search))
    total = q.count()
    items = q.order_by(Device.id).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(total=total, page=page, page_size=page_size, data=[DeviceOut.model_validate(i) for i in items])


@router.get("/all", response_model=List[DeviceOut])
def list_all_devices(db: Session = Depends(get_db), _: User = Depends(require_permission("device.read"))):
    return db.query(Device).order_by(Device.id).all()


@router.get("/{device_id}", response_model=DeviceDetailOut)
def get_device(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("device.read"))):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device


@router.post("", response_model=DeviceOut)
def create_device(req: DeviceCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("device.write"))):
    device = Device(**req.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    # Auto-start engine for new device
    try:
        from app.engine.protocol_router import protocol_router
        protocol_router.reload_device(device.id, device.protocol)
    except Exception:
        pass
    return device


@router.put("/{device_id}", response_model=DeviceOut)
def update_device(device_id: int, req: DeviceUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("device.write"))):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    old_protocol = device.protocol
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(device, k, v)
    db.commit()
    db.refresh(device)
    # Reload engine with updated config
    try:
        from app.engine.protocol_router import protocol_router
        protocol_router.reload_device(device.id, device.protocol)
    except Exception:
        pass
    return device


@router.delete("/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("device.write"))):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    device_id_val = device.id
    device_protocol = device.protocol
    db.delete(device)
    db.commit()
    # Stop engine for deleted device
    try:
        from app.engine.protocol_router import protocol_router
        protocol_router.stop_device(device_id_val, device_protocol)
    except Exception:
        pass
    return {"message": "删除成功"}


# ============ Tags ============

@router.get("/{device_id}/tags", response_model=List[TagOut])
def list_tags(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("tag.read"))):
    return db.query(DeviceTag).filter(DeviceTag.device_id == device_id).order_by(DeviceTag.sort_order, DeviceTag.id).all()


@router.post("/tags", response_model=TagOut)
def create_tag(req: TagCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("tag.write"))):
    if not db.query(Device).filter(Device.id == req.device_id).first():
        raise HTTPException(status_code=404, detail="设备不存在")
    tag = DeviceTag(**req.model_dump())
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.put("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, req: TagUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("tag.write"))):
    tag = db.query(DeviceTag).filter(DeviceTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(tag, k, v)
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("tag.write"))):
    tag = db.query(DeviceTag).filter(DeviceTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag不存在")
    db.delete(tag)
    db.commit()
    return {"message": "删除成功"}


@router.post("/tags/batch", response_model=List[TagOut])
def batch_create_tags(tags: List[TagCreate], db: Session = Depends(get_db), _: User = Depends(require_permission("tag.write"))):
    result = []
    for req in tags:
        tag = DeviceTag(**req.model_dump())
        db.add(tag)
        result.append(tag)
    db.commit()
    for t in result:
        db.refresh(t)
    return result


# ============ Write (remote control) ============

@router.post("/{device_id}/write")
def write_tag_value(device_id: int, req: WriteRequest, db: Session = Depends(get_db), _: User = Depends(require_permission("device.control"))):
    """Write a value to a writable tag (any protocol)."""
    tag = db.query(DeviceTag).filter(DeviceTag.id == req.tag_id, DeviceTag.device_id == device_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag不存在")
    if not tag.writable:
        raise HTTPException(status_code=400, detail="该Tag不可写")

    device = db.query(Device).filter(Device.id == device_id).first()
    from app.engine.protocol_router import protocol_router
    success = protocol_router.write_value(device_id, tag, req.value, device.protocol)
    if not success:
        raise HTTPException(status_code=500, detail="写入失败，请检查设备连接")
    return {"message": "写入成功", "tag_id": tag.id, "value": req.value}


# ============ Live values ============

@router.get("/{device_id}/live")
def get_device_live_values(device_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("device.read"))):
    """Get current live values for all tags of a device."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    from app.engine.protocol_router import protocol_router
    values = protocol_router.get_live_values(device_id, device.protocol)
    return {"device_id": device_id, "values": values}
