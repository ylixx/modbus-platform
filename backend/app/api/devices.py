"""Device management API."""
import json
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.device import Device, DeviceGroup, DeviceTag
from app.services.audit_service import log_action
from app.schemas.device import (
    DeviceCreate, DeviceUpdate, DeviceOut, DeviceDetailOut,
    GroupCreate, GroupUpdate, GroupOut,
    TagCreate, TagUpdate, TagOut, TagListOut,
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


def _org_path_map(db: Session) -> dict:
    """构建 {org_node_id: '厂 / 区 / 班 / 站 / 位置'} 全路径映射（一次查询，内存拼接）。"""
    from app.models.org import OrgNode
    nodes = db.query(OrgNode.id, OrgNode.name, OrgNode.parent_id).all()
    by_id = {n.id: (n.name, n.parent_id) for n in nodes}
    cache: dict = {}

    def build(nid, depth=0):
        if nid in cache:
            return cache[nid]
        info = by_id.get(nid)
        if info is None or depth > 20:  # 防环
            return ""
        name, pid = info
        parent = build(pid, depth + 1) if pid else ""
        path = f"{parent} / {name}" if parent else name
        cache[nid] = path
        return path

    return {nid: build(nid) for nid in by_id}


def _device_out(device: Device, pmap: dict) -> DeviceOut:
    out = DeviceOut.model_validate(device)
    if device.org_node_id:
        out.org_path = pmap.get(device.org_node_id, "")
    return out


# ============ Device Groups ============

@router.get("/groups", response_model=List[GroupOut])
def list_groups(db: Session = Depends(get_db), user: User = Depends(require_permission("group.read"))):
    # 非管理员只能看到包含可见设备的分组
    from app.services.org_service import get_visible_device_ids
    visible = get_visible_device_ids(db, user)
    groups = db.query(DeviceGroup).order_by(DeviceGroup.sort_order, DeviceGroup.id).all()
    if visible is not None:
        if not visible:
            return []
        # 过滤出包含可见设备的分组
        device_group_ids = set(db.query(Device.group_id).filter(Device.id.in_(visible), Device.group_id.isnot(None)).distinct().all())
        device_group_ids = {r[0] for r in device_group_ids}
        groups = [g for g in groups if g.id in device_group_ids]
    return groups


@router.post("/groups", response_model=GroupOut)
def create_group(req: GroupCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("group.write"))):
    if db.query(DeviceGroup).filter(DeviceGroup.name == req.name).first():
        raise HTTPException(status_code=400, detail="分组名已存在")
    group = DeviceGroup(**req.model_dump())
    db.add(group)
    try:
        db.commit()
        db.refresh(group)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建失败: {e}")
    return group


@router.put("/groups/{group_id}", response_model=GroupOut)
def update_group(group_id: int, req: GroupUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("group.write"))):
    group = db.query(DeviceGroup).filter(DeviceGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(group, k, v)
    try:
        db.commit()
        db.refresh(group)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")
    return group


@router.delete("/groups/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("group.write"))):
    group = db.query(DeviceGroup).filter(DeviceGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    db.delete(group)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    return ResponseModel(message="删除成功")


# ============ Locations ============

@router.get("/locations")
def get_locations(db: Session = Depends(get_db), user: User = Depends(require_permission("device.read"))):
    """Get distinct factory/workshop/line values for filter dropdowns."""
    from app.services.org_service import apply_device_org_filter
    base_q = apply_device_org_filter(db.query(Device), db, user)
    factories = [r[0] for r in base_q.filter(Device.factory != "").with_entities(Device.factory).distinct().all()]
    workshops = [r[0] for r in apply_device_org_filter(db.query(Device), db, user).filter(Device.workshop != "").with_entities(Device.workshop).distinct().all()]
    lines = [r[0] for r in apply_device_org_filter(db.query(Device), db, user).filter(Device.production_line != "").with_entities(Device.production_line).distinct().all()]
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
    search: str = Query("", max_length=100),
    writable: bool = None,
    has_lab_data: bool = None,
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
    if writable is not None:
        # 仅返回「至少含一个可写点位」的设备（批量控制等场景使用）
        writable_subq = (
            db.query(DeviceTag.device_id)
            .filter(DeviceTag.writable == True)  # noqa: E712
            .distinct()
        )
        q = q.filter(Device.id.in_(writable_subq))
    if has_lab_data is not None:
        q = q.filter(Device.has_lab_data == has_lab_data)
    total = q.count()
    items = q.order_by(Device.id).offset((page - 1) * page_size).limit(page_size).all()
    pmap = _org_path_map(db)
    return PageResponse(total=total, page=page, page_size=page_size, data=[_device_out(i, pmap) for i in items])


@router.get("/all", response_model=List[DeviceOut])
def list_all_devices(db: Session = Depends(get_db), current_user: User = Depends(require_permission("device.read"))):
    q = apply_device_org_filter(db.query(Device), db, current_user)
    pmap = _org_path_map(db)
    return [_device_out(i, pmap) for i in q.order_by(Device.id).limit(500).all()]


# ============ Tags（必须在 /{device_id} 之前注册，否则 /tags/all 会被路径参数吞掉） ============

VALID_FUNCTION_CODES = {"coil", "discrete_input", "input_register", "holding_register"}


def _validate_tag_required(device: Device, function_code: str, mqtt_topic: str, opc_node_id: str, tag_name: str = ""):
    """按设备协议校验点位必填字段（Modbus 功能码 / MQTT 订阅主题 / OPC 节点ID）。"""
    prefix = f"点位「{tag_name}」" if tag_name else "点位"
    protocol = device.protocol
    if protocol in ("modbus_tcp", "modbus_rtu"):
        if not function_code:
            raise HTTPException(status_code=400, detail=f"{prefix}：功能码为必选项，请选择 线圈/离散输入/输入寄存器/保持寄存器")
        if function_code not in VALID_FUNCTION_CODES:
            raise HTTPException(status_code=400, detail=f"{prefix}：功能码 '{function_code}' 无效，可选值：{'/'.join(sorted(VALID_FUNCTION_CODES))}")
    elif protocol == "mqtt":
        # 点位 topic 可留空回退到 设备Topic前缀/点位名，两者都空才拒绝
        if not (mqtt_topic or "").strip() and not (getattr(device, "mqtt_topic_prefix", "") or "").strip():
            raise HTTPException(status_code=400, detail=f"{prefix}：MQTT 设备必须填写订阅主题 (mqtt_topic)，或先在设备上配置 Topic 前缀")
    elif protocol == "opc_ua":
        if not (opc_node_id or "").strip():
            raise HTTPException(status_code=400, detail=f"{prefix}：OPC UA 设备必须填写节点ID (opc_node_id)，如 ns=2;s=Temperature")


@router.get("/tags/all", response_model=PageResponse)
def list_all_tags(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    org_node_id: int = Query(None),
    device_ids: str = Query(""),
    search: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("tag.read")),
):
    """全局点位列表（跨设备，用于实时数据页扁平分页展示）。"""
    q = db.query(DeviceTag).join(Device, DeviceTag.device_id == Device.id)
    # 组织架构范围过滤
    if org_node_id:
        from app.services.org_service import get_descendant_ids
        ids = get_descendant_ids(db, org_node_id)
        q = q.filter(Device.org_node_id.in_(ids))
    # 指定设备 ID 列表过滤（逗号分隔）
    if device_ids and device_ids.strip():
        try:
            did_list = [int(x) for x in device_ids.split(",") if x.strip()]
            if did_list:
                q = q.filter(DeviceTag.device_id.in_(did_list))
        except ValueError:
            pass
    # 关键词搜索（设备名 or 点位名）
    if search and search.strip():
        kw = f"%{search.strip()}%"
        q = q.filter((Device.name.ilike(kw)) | (DeviceTag.name.ilike(kw)))
    total = q.count()
    items = q.order_by(DeviceTag.device_id, DeviceTag.sort_order, DeviceTag.id) \
             .offset((page - 1) * page_size).limit(page_size).all()
    # 构建 device_id → name 映射
    dids = list({t.device_id for t in items})
    dmap = {}
    if dids:
        for d in db.query(Device.id, Device.name).filter(Device.id.in_(dids)).all():
            dmap[d.id] = d.name
    out = []
    for t in items:
        o = TagListOut.model_validate(t)
        o.device_name = dmap.get(t.device_id, "")
        out.append(o)
    return PageResponse(total=total, page=page, page_size=page_size, data=out)


@router.get("/{device_id}/tags", response_model=PageResponse)
def list_tags(device_id: int, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), current_user: User = Depends(require_permission("tag.read"))):
    _ensure_device_visible(db, current_user, device_id)
    q = db.query(DeviceTag).filter(DeviceTag.device_id == device_id)
    total = q.count()
    items = q.order_by(DeviceTag.sort_order, DeviceTag.id).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(total=total, page=page, page_size=page_size, data=[TagOut.model_validate(i) for i in items])


@router.post("/tags", response_model=TagOut)
def create_tag(req: TagCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("tag.write"))):
    device = db.query(Device).filter(Device.id == req.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    _validate_tag_required(device, req.function_code, req.mqtt_topic, req.opc_node_id, req.name)
    tag = DeviceTag(**req.model_dump())
    db.add(tag)
    try:
        db.commit()
        db.refresh(tag)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建失败: {e}")
    return tag


@router.put("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, req: TagUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("tag.write"))):
    tag = db.query(DeviceTag).filter(DeviceTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(tag, k, v)
    device = db.query(Device).filter(Device.id == tag.device_id).first()
    if device:
        _validate_tag_required(device, tag.function_code, tag.mqtt_topic, tag.opc_node_id, tag.name)
    try:
        db.commit()
        db.refresh(tag)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")
    return tag


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("tag.write"))):
    tag = db.query(DeviceTag).filter(DeviceTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag不存在")
    db.delete(tag)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    return ResponseModel(message="删除成功")


@router.post("/tags/batch", response_model=List[TagOut])
def batch_create_tags(tags: List[TagCreate], db: Session = Depends(get_db), _: User = Depends(require_permission("tag.write"))):
    if len(tags) > 100:
        raise HTTPException(status_code=400, detail="批量创建点位最多支持 100 条")
    result = []
    device_cache: dict = {}
    for req in tags:
        if req.device_id not in device_cache:
            device_cache[req.device_id] = db.query(Device).filter(Device.id == req.device_id).first()
        device = device_cache[req.device_id]
        if not device:
            raise HTTPException(status_code=404, detail=f"点位「{req.name}」：设备 {req.device_id} 不存在")
        _validate_tag_required(device, req.function_code, req.mqtt_topic, req.opc_node_id, req.name)
        tag = DeviceTag(**req.model_dump())
        db.add(tag)
        result.append(tag)
    try:
        db.commit()
        for t in result:
            db.refresh(t)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量创建失败: {e}")
    return result


# ============ Devices (路径参数路由，放在固定路径之后) ============

@router.get("/{device_id}", response_model=DeviceDetailOut)
def get_device(device_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_permission("device.read"))):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    _ensure_device_visible(db, current_user, device_id)
    out = DeviceDetailOut.model_validate(device)
    if device.org_node_id:
        out.org_path = _org_path_map(db).get(device.org_node_id, "")
    return out


@router.post("", response_model=DeviceOut)
def create_device(req: DeviceCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("device.write"))):
    # 重复设备名校验（提前到 400 而非 500）
    if db.query(Device).filter(Device.name == req.name).first():
        raise HTTPException(status_code=400, detail=f"设备名 '{req.name}' 已存在")
    device = Device(**req.model_dump())
    db.add(device)
    try:
        db.commit()
        db.refresh(device)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建失败: {e}")
    log_action(action="device.create", resource_type="device", resource_id=device.id,
               resource_name=device.name, detail=json.dumps({"protocol": device.protocol, "host": device.host}, ensure_ascii=False),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    # Auto-start engine for new device
    try:
        from app.engine.protocol_router import protocol_router
        protocol_router.reload_device(device.id, device.protocol)
    except Exception as e:
        from loguru import logger
        logger.error(f"reload_device({device.id}) failed: {e}")
    # Reload device-level MQTT publish if enabled
    try:
        from app.services.device_publish_service import device_publish_service
        device_publish_service.reload_device(device.id)
    except Exception as e:
        from loguru import logger
        logger.error(f"device_publish_service.reload_device({device.id}) failed: {e}")
    return device


@router.put("/{device_id}", response_model=DeviceOut)
def update_device(device_id: int, req: DeviceUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("device.write"))):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    old_protocol = device.protocol
    data = req.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(device, k, v)
    # 显式禁用设备：立即将状态置为离线并广播，避免列表仍显示「在线」
    if data.get('enabled') is False:
        device.status = 'offline'
        device.last_error = '已手动禁用'
    log_action(action="device.update", resource_type="device", resource_id=device.id,
               resource_name=device.name, detail=json.dumps(data, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
        db.refresh(device)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")
    # Reload engine with updated config
    try:
        from app.engine.protocol_router import protocol_router
        protocol_router.reload_device(device.id, device.protocol)
    except Exception as e:
        from loguru import logger
        logger.error(f"reload_device({device.id}) failed: {e}")
    # Reload device-level MQTT publish (config may have changed)
    try:
        from app.services.device_publish_service import device_publish_service
        device_publish_service.reload_device(device.id)
    except Exception as e:
        from loguru import logger
        logger.error(f"device_publish_service.reload_device({device.id}) failed: {e}")
    # 禁用后推送状态变化（前端列表刷新即可看到离线，WS 实时推送更快）
    if data.get('enabled') is False:
        try:
            from app.engine.websocket_manager import push_device_status
            push_device_status(device.id, device.name, 'offline', '已手动禁用')
        except Exception as e:
            from loguru import logger
            logger.error(f"push_device_status(disabled {device.id}) failed: {e}")
    return device


@router.delete("/{device_id}")
def delete_device(device_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_permission("device.write"))):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    device_id_val = device.id
    device_protocol = device.protocol
    # 级联删除关联的报警规则
    from app.models.alarm import AlarmRule
    db.query(AlarmRule).filter(AlarmRule.device_id == device_id).delete()
    db.delete(device)
    log_action(action="device.delete", resource_type="device", resource_id=device_id_val,
               resource_name=device.name, detail=json.dumps({"protocol": device_protocol}, ensure_ascii=False),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    # Stop engine for deleted device
    try:
        from app.engine.protocol_router import protocol_router
        protocol_router.stop_device(device_id_val, device_protocol)
    except Exception:
        pass
    # Stop device-level MQTT publish for deleted device
    try:
        from app.services.device_publish_service import device_publish_service
        device_publish_service.remove_device(device_id_val)
    except Exception:
        pass
    return ResponseModel(message="删除成功")


@router.post("/{device_id}/duplicate")
def duplicate_device(
    device_id: int,
    request: Request,
    new_name: str = Query(..., max_length=100, description="新设备名称"),
    copy_tags: bool = Query(True, description="是否复制点位"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("device.write")),
):
    """Duplicate a device and optionally all its tags."""
    src = db.query(Device).filter(Device.id == device_id).first()
    if not src:
        raise HTTPException(404, "设备不存在")

    if db.query(Device).filter(Device.name == new_name).first():
        raise HTTPException(400, f"设备名 '{new_name}' 已存在")

    # Copy device fields (field names must match Device model exactly)
    new_device = Device(
        name=new_name,
        protocol=src.protocol,
        # Modbus TCP
        host=src.host,
        port=src.port,
        slave_id=src.slave_id,
        timeout=src.timeout,
        retries=src.retries,
        # MQTT
        mqtt_broker=src.mqtt_broker,
        mqtt_port=src.mqtt_port,
        mqtt_username=src.mqtt_username,
        mqtt_password=src.mqtt_password,
        mqtt_client_id=src.mqtt_client_id,
        mqtt_topic_prefix=src.mqtt_topic_prefix,
        mqtt_use_tls=src.mqtt_use_tls,
        mqtt_ca_cert=src.mqtt_ca_cert,
        mqtt_publish_enabled=src.mqtt_publish_enabled,
        mqtt_publish_topic=src.mqtt_publish_topic,
        mqtt_publish_qos=src.mqtt_publish_qos,
        mqtt_publish_interval=src.mqtt_publish_interval,
        mqtt_payload_format=src.mqtt_payload_format,
        mqtt_payload_template=src.mqtt_payload_template,
        mqtt_is_gateway=src.mqtt_is_gateway,
        # OPC-UA
        opc_endpoint=src.opc_endpoint,
        opc_security_mode=src.opc_security_mode,
        opc_username=src.opc_username,
        opc_password=src.opc_password,
        opc_certificate=src.opc_certificate,
        opc_private_key=src.opc_private_key,
        opc_namespace=src.opc_namespace,
        # Location
        factory=src.factory,
        workshop=src.workshop,
        production_line=src.production_line,
        installation=src.installation,
        longitude=src.longitude,
        latitude=src.latitude,
        org_node_id=src.org_node_id,
        # Common
        poll_interval=src.poll_interval,
        description=src.description if src.description else f"复制自: {src.name}",
        enabled=src.enabled,  # 保持与源设备相同的启用状态
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
                # Modbus
                function_code=st.function_code,
                address=st.address,
                data_type=st.data_type,
                byte_order=st.byte_order,
                bit_index=st.bit_index,
                register_count=st.register_count,
                # MQTT
                mqtt_topic=st.mqtt_topic,
                mqtt_json_path=st.mqtt_json_path,
                mqtt_value_type=st.mqtt_value_type,
                mqtt_publish_topic=st.mqtt_publish_topic,
                mqtt_retain=st.mqtt_retain,
                # OPC-UA
                opc_node_id=st.opc_node_id,
                opc_node_type=st.opc_node_type,
                # Value processing
                scale_factor=st.scale_factor,
                offset=st.offset,
                decimal_places=st.decimal_places,
                min_value=st.min_value,
                max_value=st.max_value,
                script_id=st.script_id,
                unit=st.unit,
                writable=st.writable,
                description=st.description,
                sort_order=st.sort_order,
                enabled=st.enabled,
            )
            db.add(new_tag)
            tag_count += 1

    log_action(action="device.duplicate", resource_type="device", resource_id=new_device.id,
               resource_name=new_name, detail=json.dumps({"source_id": device_id, "source_name": src.name, "copy_tags": copy_tags, "tag_count": tag_count}, ensure_ascii=False),
               user_id=user.id, username=user.username, ip_address=request.client.host if request and request.client else "")
    try:
        db.commit()
        db.refresh(new_device)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"设备复制失败: {e}")

    # Auto-start engine for duplicated device if enabled
    if new_device.enabled:
        try:
            from app.engine.protocol_router import protocol_router
            protocol_router.reload_device(new_device.id, new_device.protocol)
        except Exception as e:
            from loguru import logger
            logger.error(f"reload_device(duplicate {new_device.id}) failed: {e}")

    return ResponseModel(
        message=f"设备复制成功，已复制 {tag_count} 个点位",
        data={
            "device": {
                "id": new_device.id,
                "name": new_device.name,
                "protocol": new_device.protocol,
                "enabled": new_device.enabled,
            },
            "tag_count": tag_count,
        },
    )


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
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if not device.enabled:
        raise HTTPException(status_code=400, detail="设备已禁用，无法写入")
    if device.status not in ("online", None):
        raise HTTPException(status_code=400, detail=f"设备当前状态为 {device.status}，无法写入")
    from app.engine.protocol_router import protocol_router
    success = protocol_router.write_value(device_id, tag, req.value, device.protocol)
    if not success:
        raise HTTPException(status_code=500, detail="写入失败，请检查设备连接")

    # 写后尽力读回读寄存器（回读寄存器本身是设备的采集点位），作为即时反馈返回。
    # 若引擎缓存尚未刷新，readback_value 可能为 None，前端会靠 WS/轮询持续同步。
    readback_tag_id = None
    readback_value = None
    if tag.readback_tag_id:
        try:
            live = protocol_router.get_live_values(device_id, device.protocol) or {}
            rb = live.get(tag.readback_tag_id)
            if isinstance(rb, dict) and "value" in rb:
                readback_tag_id = tag.readback_tag_id
                readback_value = rb.get("value")
        except Exception:
            pass

    return {
        "message": "写入成功",
        "tag_id": tag.id,
        "value": req.value,
        "readback_tag_id": readback_tag_id,
        "readback_value": readback_value,
    }


# ============ Batch Write ============

class BatchWriteItem(BaseModel):
    device_id: int
    tag_id: int
    value: float | bool | int | str

class BatchWriteRequest(BaseModel):
    items: List[BatchWriteItem]  # max 50 items
    stop_on_error: bool = False  # 某条失败是否停止后续执行

    def model_post_init(self, __context):
        if len(self.items) > 50:
            raise ValueError("批量写入最多支持 50 条")


@router.post("/batch-write")
def batch_write_tag_values(
    req: BatchWriteRequest,
    request: Request,
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
                    # 写后尽力读回读寄存器，作为即时反馈
                    if tag.readback_tag_id:
                        try:
                            live = protocol_router.get_live_values(item.device_id, device.protocol) or {}
                            rb = live.get(tag.readback_tag_id)
                            if isinstance(rb, dict) and "value" in rb:
                                result["readback_tag_id"] = tag.readback_tag_id
                                result["readback_value"] = rb.get("value")
                        except Exception:
                            pass
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

    log_action(action="device.batch_write", resource_type="device", resource_id=0,
               resource_name=f"batch({len(req.items)})",
               detail=json.dumps({"total": len(req.items), "success": success_count, "failed": fail_count}, ensure_ascii=False),
               user_id=current_user.id, username=current_user.username, ip_address=request.client.host if request.client else "")
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
