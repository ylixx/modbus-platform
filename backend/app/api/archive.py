"""Archive management API — stats, config, manual trigger."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from app.core.deps import require_permission, get_current_user
from app.models.user import User
from app.schemas.common import ResponseModel
from app.services.archive_service import (
    run_full_archive, get_archive_stats,
    archive_history, archive_alarm_records, archive_sms_records, archive_audit_logs,
)
from app.services.config_service import get_archive_config, set_config, ARCHIVE_KEYS
from app.services.audit_service import log_action
import json

router = APIRouter(prefix="/archive", tags=["数据归档"])


def _require_admin(user: User):
    """归档操作属于全局管理，限制只有管理员可执行。"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="归档管理仅限管理员操作")


@router.get("/stats")
def stats(user: User = Depends(require_permission("archive.read"))):
    """Get data volume and oldest record dates."""
    _require_admin(user)
    return get_archive_stats()


@router.get("/config")
def get_config_api(user: User = Depends(require_permission("archive.read"))):
    """Get all archive retention settings."""
    _require_admin(user)
    return get_archive_config()


class ConfigUpdate(BaseModel):
    key: str
    value: int | bool | str

@router.put("/config")
def update_config(req: ConfigUpdate, user: User = Depends(require_permission("archive.write")), request: Request = None):
    """Update a single archive config."""
    if req.key not in ARCHIVE_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown config key: {req.key}")
    meta = ARCHIVE_KEYS[req.key]
    set_config(req.key, req.value, meta["label"])
    log_action(action="archive.update_config", resource_type="archive_config", resource_id=req.key,
               resource_name=meta["label"], detail=json.dumps({"key": req.key, "value": str(req.value), "label": meta["label"]}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return ResponseModel(message=f"{meta['label']} 已更新为 {req.value}")


class BatchConfigUpdate(BaseModel):
    history_days: Optional[int] = None
    alarm_days: Optional[int] = None
    sms_days: Optional[int] = None
    audit_days: Optional[int] = None
    enabled: Optional[bool] = None

@router.put("/config/batch")
def update_batch_config(req: BatchConfigUpdate, user: User = Depends(require_permission("archive.write")), request: Request = None):
    """Update multiple archive configs at once."""
    updated = []
    if req.history_days is not None:
        if req.history_days < 1:
            raise HTTPException(status_code=400, detail="历史数据保留天数必须 >= 1")
        set_config("archive.history_days", req.history_days, "历史数据保留天数")
        updated.append(f"历史数据: {req.history_days}天")
    if req.alarm_days is not None:
        if req.alarm_days < 1:
            raise HTTPException(status_code=400, detail="报警记录保留天数必须 >= 1")
        set_config("archive.alarm_days", req.alarm_days, "报警记录保留天数")
        updated.append(f"报警记录: {req.alarm_days}天")
    if req.sms_days is not None:
        if req.sms_days < 1:
            raise HTTPException(status_code=400, detail="短信记录保留天数必须 >= 1")
        set_config("archive.sms_days", req.sms_days, "短信记录保留天数")
        updated.append(f"短信记录: {req.sms_days}天")
    if req.audit_days is not None:
        if req.audit_days < 1:
            raise HTTPException(status_code=400, detail="审计日志保留天数必须 >= 1")
        set_config("archive.audit_days", req.audit_days, "审计日志保留天数")
        updated.append(f"审计日志: {req.audit_days}天")
    if req.enabled is not None:
        set_config("archive.enabled", req.enabled, "启用自动归档")
        updated.append(f"自动归档: {'启用' if req.enabled else '禁用'}")
    log_action(action="archive.batch_update_config", resource_type="archive_config", resource_id="batch",
               resource_name="批量更新归档配置", detail=json.dumps({"updated": updated}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return ResponseModel(message="更新成功", data={"updated": updated})


@router.post("/run")
def run_archive(user: User = Depends(require_permission("archive.write")), request: Request = None):
    """Manually trigger full archival."""
    deleted = run_full_archive()
    log_action(action="archive.run", resource_type="archive", resource_id="manual",
               resource_name="手动归档", detail=json.dumps({"deleted": deleted}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return ResponseModel(message=f"归档完成，共清理 {deleted} 条记录", data={"deleted": deleted})


class CleanRequest(BaseModel):
    table: str  # history | alarm | sms | audit
    retention_days: int

    def model_post_init(self, __context):
        if self.retention_days < 1:
            raise ValueError('retention_days 必须 >= 1，防止误删全部数据')

@router.post("/clean")
def clean_table(req: CleanRequest, user: User = Depends(require_permission("archive.write")), request: Request = None):
    """Clean a specific table with custom retention."""
    if req.retention_days < 1:
        raise HTTPException(status_code=400, detail="retention_days 必须 >= 1，防止误删全部数据")
    func_map = {
        "history": archive_history,
        "alarm": archive_alarm_records,
        "sms": archive_sms_records,
        "audit": archive_audit_logs,
    }
    func = func_map.get(req.table)
    if not func:
        raise HTTPException(status_code=400, detail=f"Unknown table: {req.table}")
    deleted = func(req.retention_days)
    log_action(action="archive.clean", resource_type="archive", resource_id=req.table,
               resource_name=f"清理{req.table}", detail=json.dumps({"table": req.table, "retention_days": req.retention_days, "deleted": deleted}, ensure_ascii=False, default=str),
               user_id=user.id, username=user.username, ip_address=request.client.host if request.client else "")
    return ResponseModel(message=f"清理 {req.table} 完成，删除 {deleted} 条", data={"deleted": deleted})
