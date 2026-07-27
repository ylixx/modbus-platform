"""Device management API."""
import json
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.device import Device, DeviceGroup, DeviceTag
from app.schemas.device import (
    DeviceCreate, DeviceUpdate, DeviceOut, DeviceDetailOut,
    GroupCreate, GroupUpdate, GroupOut,
    TagCreate, TagUpdate, TagOut,
    WriteRequest,
)
from app.schemas.common import ResponseModel, PageResponse
from app.services.org_service import apply_device_org_filter, check_device_visible
from typing import List
from fastapi import status as http_status

router = APIRouter(prefix="/devices", tags=["设备管理"])


def _ensure_device_visible(db: Session, user: User, device_id: int):
    if not check_device_visible(db, user, device_id):
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="无权访问该设备（超出组织数据范围）")


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
    page_size: int = Query(30, ge=1, le=100),
    group_id: int = None,
    org_node_id: int = None,
    protocol: str = None,
    status: str = None,
    factory: str = None,
    workshop: str = None,
    production_line: str = None,
    installation: str = None,
    ids: str = Query(None, description="按设备 ID 列表精确筛选，逗号分隔（关联列表框多选）"),
    search: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("device.read")),
):
    q = apply_device_org_filter(db.query(Device), db, current_user)
    if org_node_id is not None:
        from app.services.org_service import expand_org_subtree
        subtree = expand_org_subtree(db, {org_node_id})
        q = q.filter(Device.org_node_id.in_(subtree))
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
    if production_line:
        q = q.filter(Device.production_line == production_line)
    if installation:
        q = q.filter(Device.installation == installation)
    if ids:
        try:
            id_list = [int(x) for x in ids.split(',') if x.strip()]
            if id_list:
                q = q.filter(Device.id.in_(id_list))
        except ValueError:
            pass
    if search:
        q = q.filter(Device.name.contains(search) | Device.host.contains(search))
    total = q.count()
    items = q.order_by(Device.id).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(total=total, page=page, page_size=page_size, data=[DeviceOut.model_validate(i) for i in items])


@router.get("/all", response_model=List[DeviceOut])
def list_all_devices(db: Session = Depends(get_db), current_user: User = Depends(require_permission("device.read"))):
    q = apply_device_org_filter(db.query(Device), db, current_user)
    return q.order_by(Device.id).all()


@router.get("/{device_id}", response_model=DeviceDetailOut)
def get_device(device_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("device.read"))):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    _ensure_device_visible(db, current_user, device_id)
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


@router.post("/{device_id}/duplicate")
def duplicate_device(
    device_id: int,
    new_name: str = Query(..., description="新设备名称"),
    copy_tags: bool = Query(True, description="是否复制点位"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("device.write")),
):
    """Duplicate a device and optionally all its tags."""
    src = db.query(Device).filter(Device.id == device_id).first()
    if not src:
        raise HTTPException(404, "设备不存在")

    if db.query(Device).filter(Device.name == new_name).first():
        raise HTTPException(400, f"设备名 '{new_name}' 已存在")

    # Copy device fields
    new_device = Device(
        name=new_name,
        protocol=src.protocol,
        host=src.host,
        port=src.port,
        slave_id=src.slave_id,
        serial_port=src.serial_port,
        baudrate=src.baudrate,
        parity=src.parity,
        data_bits=src.data_bits,
        stop_bits=src.stop_bits,
        broker_url=src.broker_url,
        mqtt_topic=src.mqtt_topic,
        mqtt_username=src.mqtt_username,
        mqtt_password=src.mqtt_password,
        mqtt_client_id=src.mqtt_client_id,
        mqtt_qos=src.mqtt_qos,
        endpoint_url=src.endpoint_url,
        node_id=src.node_id,
        opc_security_mode=src.opc_security_mode,
        poll_interval=src.poll_interval,
        factory=src.factory,
        workshop=src.workshop,
        production_line=src.production_line,
        installation=src.installation,
        org_node_id=src.org_node_id,
        description=f"复制自: {src.name}" if not src.description else src.description,
        enabled=False,  # 新设备默认禁用，确认后再启用
    )
    db.add(new_device)
    db.flush()  # Get new_device.id

    tag_count = 0
    if copy_tags:
        src_tags = db.query(DeviceTag).filter(DeviceTag.device_id == device_id).all()
        for st in src_tags:
            new_tag = DeviceTag(
                device_id=new_device.id,
                name=st.name,
                function_code=st.function_code,
                address=st.address,
                data_type=st.data_type,
                byte_order=st.byte_order,
                scale_factor=st.scale_factor,
                offset=st.offset,
                decimal_places=st.decimal_places,
                unit=st.unit,
                writable=st.writable,
                description=st.description,
                sort_order=st.sort_order,
                enabled=st.enabled,
            )
            db.add(new_tag)
            tag_count += 1

    db.commit()
    db.refresh(new_device)

    return {
        "message": f"设备复制成功，已复制 {tag_count} 个点位",
        "device": {
            "id": new_device.id,
            "name": new_device.name,
            "protocol": new_device.protocol,
            "enabled": new_device.enabled,
        },
        "tag_count": tag_count,
    }


# ============ Tags ============

@router.get("/{device_id}/tags", response_model=List[TagOut])
def list_tags(device_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("tag.read"))):
    _ensure_device_visible(db, current_user, device_id)
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
def write_tag_value(device_id: int, req: WriteRequest, db: Session = Depends(get_db), current_user: User = Depends(require_permission("device.control"))):
    """Write a value to a writable tag (any protocol)."""
    _ensure_device_visible(db, current_user, device_id)
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


# ============ Batch Write ============

class BatchWriteItem(BaseModel):
    device_id: int
    tag_id: int
    value: float | bool | int | str

class BatchWriteRequest(BaseModel):
    items: List[BatchWriteItem]
    stop_on_error: bool = False  # 某条失败是否停止后续执行


@router.post("/batch-write")
def batch_write_tag_values(
    req: BatchWriteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("device.control")),
):
    """Batch write values to multiple device tags.
    Each item specifies device_id, tag_id, and value.
    Returns per-item results.
    """
    results = []
    success_count = 0
    fail_count = 0

    for i, item in enumerate(req.items):
        result = {
            "index": i,
            "device_id": item.device_id,
            "tag_id": item.tag_id,
            "value": item.value,
            "success": False,
            "message": "",
        }

        try:
            _ensure_device_visible(db, current_user, item.device_id)
            tag = db.query(DeviceTag).filter(
                DeviceTag.id == item.tag_id, DeviceTag.device_id == item.device_id
            ).first()
            if not tag:
                result["message"] = "Tag不存在"
                fail_count += 1
            elif not tag.writable:
                result["message"] = "该Tag不可写"
                fail_count += 1
            else:
                device = db.query(Device).filter(Device.id == item.device_id).first()
                from app.engine.protocol_router import protocol_router
                ok = protocol_router.write_value(item.device_id, tag, item.value, device.protocol)
                if ok:
                    result["success"] = True
                    result["message"] = "写入成功"
                    success_count += 1
                else:
                    result["message"] = "写入失败，请检查设备连接"
                    fail_count += 1
        except Exception as e:
            result["message"] = str(e)
            fail_count += 1

        results.append(result)

        if req.stop_on_error and not result["success"]:
            # 标记剩余项为跳过
            for j in range(i + 1, len(req.items)):
                results.append({
                    "index": j,
                    "device_id": req.items[j].device_id,
                    "tag_id": req.items[j].tag_id,
                    "value": req.items[j].value,
                    "success": False,
                    "message": "已跳过（前序操作失败）",
                })
            break

    return {
        "total": len(req.items),
        "success": success_count,
        "failed": fail_count,
        "results": results,
    }


# ============ Live values ============

@router.get("/{device_id}/live")
def get_device_live_values(device_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("device.read"))):
    """Get current live values for all tags of a device."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    _ensure_device_visible(db, current_user, device_id)
    from app.engine.protocol_router import protocol_router
    values = protocol_router.get_live_values(device_id, device.protocol)
    return {"device_id": device_id, "values": values}
