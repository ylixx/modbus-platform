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


# ── Runtime module switches (protocol engines & features) ──

RUNTIME_DEFAULTS = {
    "engines": {
        "modbus": {"default": True, "label": "Modbus 采集引擎", "desc": "Modbus TCP/RTU 设备轮询采集"},
        "mqtt": {"default": True, "label": "MQTT 采集引擎", "desc": "MQTT 标准设备/网关设备订阅采集"},
        "opcua": {"default": True, "label": "OPC-UA 采集引擎", "desc": "OPC-UA 节点订阅/轮询采集"},
    },
    "features": {
        "data_forward": {"default": True, "label": "数据转发", "desc": "规则化转发采集数据到外部 MQTT Broker"},
        "device_publish": {"default": True, "label": "设备上云发布", "desc": "设备按周期将实时值发布到 MQTT"},
        "alarm_mqtt": {"default": True, "label": "报警 MQTT 推送", "desc": "报警事件推送外部 MQTT（可带 ThingsBoard 格式）"},
        "redis_broadcast": {"default": False, "label": "Redis 跨进程广播", "desc": "多 worker 部署时 WebSocket 消息经 Redis pub/sub 广播，单进程部署无需开启"},
    },
}

_RUNTIME_KEY = "runtime_config"


def get_runtime_config() -> dict:
    """Get engine/feature switches with defaults and metadata."""
    saved = get_config(_RUNTIME_KEY) or {}
    result = {"engines": {}, "features": {}}
    for group in ("engines", "features"):
        for key, meta in RUNTIME_DEFAULTS[group].items():
            enabled = saved.get(group, {}).get(key)
            result[group][key] = {
                "enabled": enabled if isinstance(enabled, bool) else meta["default"],
                "label": meta["label"],
                "desc": meta["desc"],
                "default": meta["default"],
            }
    return result


def set_runtime_config(data: dict) -> None:
    """Persist engine/feature switches. Missing keys keep previous values."""
    current = get_runtime_config()
    saved = {"engines": {}, "features": {}}
    for group in ("engines", "features"):
        for key, meta in RUNTIME_DEFAULTS[group].items():
            group_data = data.get(group, {})
            val = group_data.get(key)
            if isinstance(val, bool):
                saved[group][key] = val
            else:
                saved[group][key] = current[group][key]["enabled"]
    set_config(_RUNTIME_KEY, saved, "协议引擎与功能模块开关配置（重启后端生效）")


def is_feature_enabled(feature: str) -> bool:
    """Quick check whether a feature switch is on."""
    cfg = get_config(_RUNTIME_KEY) or {}
    val = cfg.get("features", {}).get(feature)
    if isinstance(val, bool):
        return val
    meta = RUNTIME_DEFAULTS["features"].get(feature)
    return meta["default"] if meta else False


def is_engine_enabled(engine: str) -> bool:
    """Quick check whether a protocol engine switch is on."""
    cfg = get_config(_RUNTIME_KEY) or {}
    val = cfg.get("engines", {}).get(engine)
    if isinstance(val, bool):
        return val
    meta = RUNTIME_DEFAULTS["engines"].get(engine)
    return meta["default"] if meta else False
