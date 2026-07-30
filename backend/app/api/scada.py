"""SCADA page + custom widget API."""
import json, logging, base64
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.core.database import get_db
from app.core.deps import get_current_user, require_permission
from app.models.user import User
from app.models.scada import ScadaPage, CustomWidget
from app.schemas.common import ResponseModel
from app.services.audit_service import log_action

# 上传文件大小限制（5MB）
MAX_UPLOAD_SIZE = 5 * 1024 * 1024

router = APIRouter(prefix="/scada", tags=["SCADA"])

logger = logging.getLogger(__name__)


# ═══════════════════ SCADA Pages ═══════════════════

class ScadaPageCreate(BaseModel):
    name: str = Field(max_length=100)
    description: str = Field("", max_length=500)
    width: int = 1920
    height: int = 1080
    background: str = "#1a1a2e"
    config_json: str = "[]"
    device_ids: List[int] = []

class ScadaPageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    background: Optional[str] = None
    config_json: Optional[str] = None
    device_ids: Optional[List[int]] = None


def _parse_page(page: ScadaPage) -> dict:
    try:
        device_ids = json.loads(page.device_ids) if page.device_ids else []
    except (json.JSONDecodeError, TypeError):
        device_ids = []
    return {
        "id": page.id, "name": page.name, "description": page.description,
        "width": page.width, "height": page.height, "background": page.background,
        "config_json": page.config_json or "[]", "device_ids": device_ids,
        "sort_order": page.sort_order, "is_default": page.is_default,
        "created_at": page.created_at, "updated_at": page.updated_at,
    }


@router.get("/pages")
def list_pages(db: Session = Depends(get_db), user: User = Depends(require_permission("scada.read"))):
    from app.services.org_service import get_visible_device_ids
    visible = get_visible_device_ids(db, user)
    pages = db.query(ScadaPage).order_by(ScadaPage.sort_order, ScadaPage.id).all()
    if visible is not None:
        # 过滤：只返回包含可见设备的画面（或 device_ids 为空的画面）
        result = []
        for p in pages:
            try:
                p_dids = set(json.loads(p.device_ids)) if p.device_ids else set()
            except (json.JSONDecodeError, TypeError):
                p_dids = set()
            if not p_dids or p_dids & visible:
                result.append(p)
        return [_parse_page(p) for p in result]
    return [_parse_page(p) for p in pages]

@router.get("/pages/{page_id}")
def get_page(page_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("scada.read"))):
    from app.services.org_service import get_visible_device_ids
    page = db.query(ScadaPage).filter(ScadaPage.id == page_id).first()
    if not page: raise HTTPException(404, "画面不存在")
    visible = get_visible_device_ids(db, user)
    if visible is not None:
        try:
            p_dids = set(json.loads(page.device_ids)) if page.device_ids else set()
        except (json.JSONDecodeError, TypeError):
            p_dids = set()
        if p_dids and not (p_dids & visible):
            raise HTTPException(403, "无权查看此画面")
    return _parse_page(page)

@router.post("/pages")
def create_page(req: ScadaPageCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("scada.write")), request: Request = None):
    page = ScadaPage(name=req.name, description=req.description, width=req.width, height=req.height,
                     background=req.background, config_json=req.config_json,
                     device_ids=json.dumps(req.device_ids, ensure_ascii=False))
    db.add(page)
    try:
        db.commit()
        db.refresh(page)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
    log_action(action="scada.create_page", resource_type="scada_page", resource_id=page.id,
               resource_name=page.name or str(page.id), detail=json.dumps({"name": page.name, "width": page.width, "height": page.height}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return _parse_page(page)

@router.put("/pages/{page_id}")
def update_page(page_id: int, req: ScadaPageUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("scada.write")), request: Request = None):
    page = db.query(ScadaPage).filter(ScadaPage.id == page_id).first()
    if not page: raise HTTPException(404, "画面不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        if k == "device_ids": v = json.dumps(v, ensure_ascii=False)
        setattr(page, k, v)
    try:
        db.commit()
        db.refresh(page)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
    log_action(action="scada.update_page", resource_type="scada_page", resource_id=page.id,
               resource_name=page.name or str(page.id), detail=json.dumps({"name": page.name, "updated_fields": list(req.model_dump(exclude_unset=True).keys())}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return _parse_page(page)

@router.delete("/pages/{page_id}")
def delete_page(page_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("scada.write")), request: Request = None):
    page = db.query(ScadaPage).filter(ScadaPage.id == page_id).first()
    if not page: raise HTTPException(404, "画面不存在")
    log_action(action="scada.delete_page", resource_type="scada_page", resource_id=page.id,
               resource_name=page.name or str(page.id), detail=json.dumps({"name": page.name}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    db.delete(page)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
    return ResponseModel(message="删除成功")

@router.post("/pages/{page_id}/duplicate")
def duplicate_page(page_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission("scada.write")), request: Request = None):
    src = db.query(ScadaPage).filter(ScadaPage.id == page_id).first()
    if not src: raise HTTPException(404, "画面不存在")
    page = ScadaPage(name=f"{src.name} (副本)", description=src.description, width=src.width,
                     height=src.height, background=src.background, config_json=src.config_json, device_ids=src.device_ids)
    db.add(page)
    try:
        db.commit()
        db.refresh(page)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
    log_action(action="scada.duplicate_page", resource_type="scada_page", resource_id=page.id,
               resource_name=page.name or str(page.id), detail=json.dumps({"source_id": src.id, "source_name": src.name, "new_name": page.name}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return _parse_page(page)


# ═══════════════════ Custom Widgets ═══════════════════

def _parse_widget(w: CustomWidget) -> dict:
    return {
        "id": w.id, "name": w.name, "category": w.category, "description": w.description,
        "source_type": w.source_type, "source_data": w.source_data,
        "thumbnail": w.thumbnail,
        "default_width": w.default_width, "default_height": w.default_height,
        "bindable": json.loads(w.bindable) if w.bindable else [],
        "fabric_json": w.fabric_json,
        "enabled": w.enabled, "sort_order": w.sort_order,
        "created_at": w.created_at, "updated_at": w.updated_at,
    }


@router.get("/widgets")
def list_widgets(enabled_only: bool = True, db: Session = Depends(get_db), _: User = Depends(require_permission("scada.read"))):
    q = db.query(CustomWidget)
    if enabled_only:
        q = q.filter(CustomWidget.enabled == True)
    return [_parse_widget(w) for w in q.order_by(CustomWidget.category, CustomWidget.sort_order, CustomWidget.id).all()]


@router.post("/widgets/upload")
async def upload_widget(
    name: str = Form(...),
    category: str = Form("custom"),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("scada.write")),
):
    """Upload SVG or PNG file as a custom widget."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE // (1024*1024)}MB）")
    filename = file.filename.lower()

    if filename.endswith(".svg"):
        source_type = "svg"
        source_data = content.decode("utf-8", errors="replace")
        # Generate thumbnail: use the SVG itself
        thumbnail = f"data:image/svg+xml;base64,{base64.b64encode(content).decode()}"
    elif filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        source_type = "png"
        source_data = f"data:image/{filename.split('.')[-1]};base64,{base64.b64encode(content).decode()}"
        thumbnail = source_data
    else:
        raise HTTPException(400, "仅支持 SVG / PNG / JPG 文件")

    # Auto-detect size from SVG
    default_width = 100
    default_height = 100
    if source_type == "svg":
        import re
        vb = re.search(r'viewBox=["\']([^"\']+)["\']', source_data)
        if vb:
            parts = vb.group(1).split()
            if len(parts) == 4:
                default_width = int(float(parts[2]))
                default_height = int(float(parts[3]))
        else:
            w_match = re.search(r'width=["\'](\d+)', source_data)
            h_match = re.search(r'height=["\'](\d+)', source_data)
            if w_match: default_width = int(w_match.group(1))
            if h_match: default_height = int(h_match.group(1))

    widget = CustomWidget(
        name=name, category=category, description=description,
        source_type=source_type, source_data=source_data,
        thumbnail=thumbnail, default_width=default_width, default_height=default_height,
    )
    db.add(widget)
    try:
        db.commit()
        db.refresh(widget)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
    return _parse_widget(widget)


class WidgetCreate(BaseModel):
    name: str = Field(max_length=100)
    category: str = Field("custom", max_length=50)
    description: str = Field("", max_length=500)
    source_type: str = "svg"         # svg | png | fabric
    source_data: str = ""            # SVG string / base64 data URI / fabric JSON
    default_width: int = 100
    default_height: int = 100
    bindable: List[str] = ["text", "value", "state"]
    fabric_json: str = ""

@router.post("/widgets")
def create_widget(req: WidgetCreate, db: Session = Depends(get_db), _: User = Depends(require_permission("scada.write"))):
    widget = CustomWidget(
        name=req.name, category=req.category, description=req.description,
        source_type=req.source_type, source_data=req.source_data,
        default_width=req.default_width, default_height=req.default_height,
        bindable=json.dumps(req.bindable, ensure_ascii=False),
        fabric_json=req.fabric_json,
    )
    db.add(widget)
    try:
        db.commit()
        db.refresh(widget)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
    return _parse_widget(widget)


class WidgetUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    default_width: Optional[int] = None
    default_height: Optional[int] = None
    bindable: Optional[List[str]] = None
    enabled: Optional[bool] = None

@router.put("/widgets/{widget_id}")
def update_widget(widget_id: int, req: WidgetUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission("scada.write"))):
    w = db.query(CustomWidget).filter(CustomWidget.id == widget_id).first()
    if not w: raise HTTPException(404, "图元不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        if k == "bindable": v = json.dumps(v, ensure_ascii=False)
        setattr(w, k, v)
    try:
        db.commit()
        db.refresh(w)
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
    return _parse_widget(w)


@router.delete("/widgets/{widget_id}")
def delete_widget(widget_id: int, db: Session = Depends(get_db), _: User = Depends(require_permission("scada.write"))):
    w = db.query(CustomWidget).filter(CustomWidget.id == widget_id).first()
    if not w: raise HTTPException(404, "图元不存在")
    db.delete(w)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
    return ResponseModel(message="删除成功")


@router.post("/widgets/batch-upload")
async def batch_upload_widgets(
    category: str = Form("custom"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("scada.write")),
):
    """Batch upload multiple SVG/PNG files."""
    results = []
    for file in files:
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            continue  # 跳过超大文件
        filename = file.filename.lower()
        name = file.filename.rsplit(".", 1)[0]

        if filename.endswith(".svg"):
            source_type = "svg"
            source_data = content.decode("utf-8", errors="replace")
            thumbnail = f"data:image/svg+xml;base64,{base64.b64encode(content).decode()}"
        elif filename.endswith((".png", ".jpg", ".jpeg")):
            source_type = "png"
            ext = filename.split(".")[-1]
            source_data = f"data:image/{ext};base64,{base64.b64encode(content).decode()}"
            thumbnail = source_data
        else:
            continue

        widget = CustomWidget(
            name=name, category=category, source_type=source_type,
            source_data=source_data, thumbnail=thumbnail,
        )
        db.add(widget)
        results.append(name)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("数据库操作失败")
        raise HTTPException(status_code=500, detail="操作失败，请稍后重试")
    return ResponseModel(message="上传完成", data={"uploaded": results, "count": len(results)})
