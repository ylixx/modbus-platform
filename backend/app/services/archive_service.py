"""Data archival service — periodic cleanup with user-configurable retention."""
from datetime import datetime, timedelta, timezone
from loguru import logger
from sqlalchemy import text
from app.core.database import SessionLocal
from app.services.config_service import get_retention_days, get_config


def archive_history(retention_days: int = None):
    """Delete old raw history data."""
    days = retention_days or get_retention_days("history")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        result = db.execute(text("DELETE FROM tag_history WHERE recorded_at < :cutoff LIMIT 10000"), {"cutoff": cutoff})
        deleted = result.rowcount
        db.commit()
        if deleted > 0:
            logger.info(f"Archived {deleted} history records older than {days} days")
        return deleted
    except Exception as e:
        logger.error(f"Archive history error: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def archive_alarm_records(retention_days: int = None):
    days = retention_days or get_retention_days("alarm")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        result = db.execute(text("DELETE FROM alarm_records WHERE triggered_at < :cutoff AND status = 'cleared' LIMIT 5000"), {"cutoff": cutoff})
        deleted = result.rowcount
        db.commit()
        if deleted > 0:
            logger.info(f"Archived {deleted} alarm records older than {days} days")
        return deleted
    except Exception as e:
        logger.error(f"Archive alarm records error: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def archive_sms_records(retention_days: int = None):
    days = retention_days or get_retention_days("sms")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        result = db.execute(text("DELETE FROM sms_records WHERE created_at < :cutoff LIMIT 5000"), {"cutoff": cutoff})
        deleted = result.rowcount
        db.commit()
        if deleted > 0:
            logger.info(f"Archived {deleted} SMS records older than {days} days")
        return deleted
    except Exception as e:
        logger.error(f"Archive SMS records error: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def archive_audit_logs(retention_days: int = None):
    days = retention_days or get_retention_days("audit")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        result = db.execute(text("DELETE FROM audit_logs WHERE created_at < :cutoff LIMIT 5000"), {"cutoff": cutoff})
        deleted = result.rowcount
        db.commit()
        if deleted > 0:
            logger.info(f"Archived {deleted} audit logs older than {days} days")
        return deleted
    except Exception as e:
        logger.error(f"Archive audit logs error: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def run_full_archive():
    """Run all archival tasks if enabled."""
    enabled = get_config("archive.enabled")
    if enabled is False:
        logger.info("Auto-archive is disabled, skipping")
        return 0

    logger.info("Starting full archival...")
    total = 0
    total += archive_history()
    total += archive_alarm_records()
    total += archive_sms_records()
    total += archive_audit_logs()
    logger.info(f"Archival complete. Total deleted: {total}")
    return total


def get_archive_stats():
    db = SessionLocal()
    try:
        stats = {}
        for table in ["tag_history", "alarm_records", "sms_records", "audit_logs"]:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            stats[table] = result.scalar()
        for table, col in [("tag_history", "recorded_at"), ("alarm_records", "triggered_at"), ("audit_logs", "created_at")]:
            result = db.execute(text(f"SELECT MIN({col}) FROM {table}"))
            stats[f"{table}_oldest"] = str(result.scalar() or "N/A")
        return stats
    except Exception as e:
        logger.error(f"Get archive stats error: {e}")
        return {}
    finally:
        db.close()
