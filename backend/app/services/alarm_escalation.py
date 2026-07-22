"""Alarm escalation service.

If an alarm is active and unacknowledged for N minutes:
  1. Upgrade its alarm_level (info→warning→critical→emergency)
  2. Send SMS to escalation contacts
  3. Log the escalation

Runs periodically via scheduler or heartbeat.
"""
from datetime import datetime, timedelta, timezone
from loguru import logger
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.alarm import AlarmRecord, AlarmStatus, AlarmLevel
from app.models.sms import SmsContact, SmsPushRule
from app.services.sms_service import sms_service


LEVEL_ORDER = ["info", "warning", "critical", "emergency"]

# Escalation config: if alarm at level X is unacknowledged for N minutes, escalate
DEFAULT_ESCALATION = {
    "info": 30,       # info → warning after 30min
    "warning": 15,    # warning → critical after 15min
    "critical": 10,   # critical → emergency after 10min
    "emergency": 0,   # no further escalation
}


def check_escalations():
    """Check all active alarms and escalate if needed."""
    db = SessionLocal()
    escalated = 0
    try:
        active_alarms = db.query(AlarmRecord).filter(
            AlarmRecord.status == AlarmStatus.ACTIVE,
        ).all()

        now = datetime.now(timezone.utc)

        for alarm in active_alarms:
            if not alarm.triggered_at:
                continue

            elapsed = (now - alarm.triggered_at).total_seconds() / 60
            current_level = alarm.alarm_level
            threshold = DEFAULT_ESCALATION.get(current_level, 0)

            if threshold <= 0:
                continue  # No escalation for this level

            if elapsed >= threshold:
                # Escalate
                new_level = _next_level(current_level)
                if new_level and new_level != current_level:
                    old_level = alarm.alarm_level
                    alarm.alarm_level = new_level
                    alarm.alarm_message = f"[升级] {alarm.alarm_message} (从{old_level}升级到{new_level})"
                    db.commit()
                    escalated += 1

                    logger.warning(
                        f"Alarm escalated: id={alarm.id}, device={alarm.device_id}, "
                        f"{old_level} → {new_level} after {elapsed:.0f}min"
                    )

                    # Send escalation SMS
                    _send_escalation_sms(db, alarm, old_level, new_level)

        if escalated > 0:
            logger.info(f"Escalation check complete: {escalated} alarms escalated")
        return escalated

    except Exception as e:
        logger.error(f"Escalation check error: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def _next_level(current: str) -> str | None:
    try:
        idx = LEVEL_ORDER.index(current)
        if idx < len(LEVEL_ORDER) - 1:
            return LEVEL_ORDER[idx + 1]
    except ValueError:
        pass
    return None


def _send_escalation_sms(db: Session, alarm: AlarmRecord, old_level: str, new_level: str):
    """Send SMS notification for alarm escalation."""
    try:
        # Find push rules that match the new level
        push_rules = db.query(SmsPushRule).filter(SmsPushRule.enabled == True).all()
        import json

        for pr in push_rules:
            # Check level filter
            if pr.alarm_levels:
                try:
                    levels = json.loads(pr.alarm_levels)
                    if new_level not in levels:
                        continue
                except (json.JSONDecodeError, TypeError):
                    continue

            # Check time window
            now_time = datetime.now(timezone.utc).strftime("%H:%M")
            if not (pr.time_start <= now_time <= pr.time_end):
                continue

            # Send to contacts
            try:
                contact_ids = json.loads(pr.contact_ids)
            except (json.JSONDecodeError, TypeError):
                continue

            for cid in contact_ids:
                contact = db.query(SmsContact).filter(
                    SmsContact.id == cid, SmsContact.enabled == True
                ).first()
                if not contact:
                    continue

                content = (
                    f"【报警升级】\n"
                    f"原等级: {old_level} → 新等级: {new_level}\n"
                    f"信息: {alarm.alarm_message}\n"
                    f"时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
                )
                sms_service.send_sms(contact.phone, content)

    except Exception as e:
        logger.error(f"Escalation SMS error: {e}")
