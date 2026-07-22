"""System config service — get/set runtime config from database."""
import json
from loguru import logger
from app.core.database import SessionLocal
from app.models.system_config import SystemConfig


def get_config(key: str, default=None):
    """Get a config value by key."""
    db = SessionLocal()
    try:
        cfg = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if cfg and cfg.value:
            try:
                return json.loads(cfg.value)
            except (json.JSONDecodeError, TypeError):
                return cfg.value
        return default
    finally:
        db.close()


def set_config(key: str, value, description: str = ""):
    """Set a config value by key."""
    db = SessionLocal()
    try:
        cfg = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        serialized = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        if cfg:
            cfg.value = serialized
            if description:
                cfg.description = description
        else:
            cfg = SystemConfig(key=key, value=serialized, description=description)
            db.add(cfg)
        db.commit()
    except Exception as e:
        logger.error(f"Set config error: {e}")
        db.rollback()
    finally:
        db.close()


def get_all_configs() -> dict:
    """Get all configs as a dict."""
    db = SessionLocal()
    try:
        configs = db.query(SystemConfig).all()
        result = {}
        for cfg in configs:
            try:
                result[cfg.key] = json.loads(cfg.value)
            except (json.JSONDecodeError, TypeError):
                result[cfg.key] = cfg.value
        return result
    finally:
        db.close()


# ── Archive retention defaults & helpers ──

ARCHIVE_KEYS = {
    "archive.history_days": {"default": 7, "label": "历史数据保留天数", "desc": "原始采集数据"},
    "archive.alarm_days": {"default": 365, "label": "报警记录保留天数", "desc": "已消除的报警记录"},
    "archive.sms_days": {"default": 90, "label": "短信记录保留天数", "desc": "短信发送记录"},
    "archive.audit_days": {"default": 365, "label": "审计日志保留天数", "desc": "操作审计日志"},
    "archive.enabled": {"default": True, "label": "启用自动归档", "desc": "每天凌晨3点自动清理"},
}


def get_archive_config() -> dict:
    """Get all archive retention settings."""
    result = {}
    for key, meta in ARCHIVE_KEYS.items():
        val = get_config(key)
        result[key] = {
            "value": val if val is not None else meta["default"],
            "label": meta["label"],
            "desc": meta["desc"],
            "default": meta["default"],
        }
    return result


def get_retention_days(table: str) -> int:
    """Get retention days for a specific table."""
    key = f"archive.{table}_days"
    meta = ARCHIVE_KEYS.get(key, {})
    default = meta.get("default", 30)
    val = get_config(key)
    return int(val) if val is not None else default
