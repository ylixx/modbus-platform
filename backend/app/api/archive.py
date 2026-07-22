"""Archive management API — stats, config, manual trigger."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.deps import get_current_user
from app.models.user import User
from app.services.archive_service import (
    run_full_archive, get_archive_stats,
    archive_history, archive_alarm_records, archive_sms_records, archive_audit_logs,
)
from app.services.config_service import get_archive_config, set_config, ARCHIVE_KEYS

router = APIRouter(prefix="/archive", tags=["数据归档"])


@router.get("/stats")
def stats(_: User = Depends(get_current_user)):
    """Get data volume and oldest record dates."""
    return get_archive_stats()


@router.get("/config")
def get_config_api(_: User = Depends(get_current_user)):
    """Get all archive retention settings."""
    return get_archive_config()


class ConfigUpdate(BaseModel):
    key: str
    value: int | bool | str

@router.put("/config")
def update_config(req: ConfigUpdate, _: User = Depends(get_current_user)):
    """Update a single archive config."""
    if req.key not in ARCHIVE_KEYS:
        return {"error": f"Unknown config key: {req.key}"}
    meta = ARCHIVE_KEYS[req.key]
    set_config(req.key, req.value, meta["label"])
    return {"message": f"{meta['label']} 已更新为 {req.value}"}


class BatchConfigUpdate(BaseModel):
    history_days: Optional[int] = None
    alarm_days: Optional[int] = None
    sms_days: Optional[int] = None
    audit_days: Optional[int] = None
    enabled: Optional[bool] = None

@router.put("/config/batch")
def update_batch_config(req: BatchConfigUpdate, _: User = Depends(get_current_user)):
    """Update multiple archive configs at once."""
    updated = []
    if req.history_days is not None:
        set_config("archive.history_days", req.history_days, "历史数据保留天数")
        updated.append(f"历史数据: {req.history_days}天")
    if req.alarm_days is not None:
        set_config("archive.alarm_days", req.alarm_days, "报警记录保留天数")
        updated.append(f"报警记录: {req.alarm_days}天")
    if req.sms_days is not None:
        set_config("archive.sms_days", req.sms_days, "短信记录保留天数")
        updated.append(f"短信记录: {req.sms_days}天")
    if req.audit_days is not None:
        set_config("archive.audit_days", req.audit_days, "审计日志保留天数")
        updated.append(f"审计日志: {req.audit_days}天")
    if req.enabled is not None:
        set_config("archive.enabled", req.enabled, "启用自动归档")
        updated.append(f"自动归档: {'启用' if req.enabled else '禁用'}")
    return {"message": "更新成功", "updated": updated}


@router.post("/run")
def run_archive(_: User = Depends(get_current_user)):
    """Manually trigger full archival."""
    deleted = run_full_archive()
    return {"message": f"归档完成，共清理 {deleted} 条记录", "deleted": deleted}


class CleanRequest(BaseModel):
    table: str  # history | alarm | sms | audit
    retention_days: int

@router.post("/clean")
def clean_table(req: CleanRequest, _: User = Depends(get_current_user)):
    """Clean a specific table with custom retention."""
    func_map = {
        "history": archive_history,
        "alarm": archive_alarm_records,
        "sms": archive_sms_records,
        "audit": archive_audit_logs,
    }
    func = func_map.get(req.table)
    if not func:
        return {"error": f"Unknown table: {req.table}"}
    deleted = func(req.retention_days)
    return {"message": f"清理 {req.table} 完成，删除 {deleted} 条", "deleted": deleted}
