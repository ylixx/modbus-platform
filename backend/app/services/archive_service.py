"""Data archival service — periodic cleanup with user-configurable retention."""
from datetime import datetime, timedelta, timezone
from loguru import logger
from sqlalchemy import text
from app.core.database import SessionLocal
from app.services.config_service import get_retention_days, get_config

# SQLite-compatible batch delete: use subquery with LIMIT inside an IN clause.
# SQLite requires the LIMIT inside a subquery when used with IN.
_BATCH_SIZE = 10000


def archive_history(retention_days: int = None):
    """Delete old raw history data."""
    days = retention_days or get_retention_days("history")
    if days < 1:
        logger.warning(f"archive_history called with retention_days={days}, skipping (must be >= 1)")
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        # Use subquery with LIMIT for SQLite compatibility
        result = db.execute(text(
            "DELETE FROM tag_history WHERE id IN "
            "(SELECT id FROM tag_history WHERE recorded_at < :cutoff LIMIT :limit)"
        ), {"cutoff": cutoff, "limit": _BATCH_SIZE})
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
    if days < 1:
        logger.warning(f"archive_alarm_records called with retention_days={days}, skipping (must be >= 1)")
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        result = db.execute(text(
            "DELETE FROM alarm_records WHERE id IN "
            "(SELECT id FROM alarm_records WHERE triggered_at < :cutoff AND status = 'cleared' LIMIT :limit)"
        ), {"cutoff": cutoff, "limit": 5000})
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
    if days < 1:
        logger.warning(f"archive_sms_records called with retention_days={days}, skipping (must be >= 1)")
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        result = db.execute(text(
            "DELETE FROM sms_records WHERE id IN "
            "(SELECT id FROM sms_records WHERE created_at < :cutoff LIMIT :limit)"
        ), {"cutoff": cutoff, "limit": 5000})
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
    if days < 1:
        logger.warning(f"archive_audit_logs called with retention_days={days}, skipping (must be >= 1)")
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        result = db.execute(text(
            "DELETE FROM audit_logs WHERE id IN "
            "(SELECT id FROM audit_logs WHERE created_at < :cutoff LIMIT :limit)"
        ), {"cutoff": cutoff, "limit": 5000})
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
