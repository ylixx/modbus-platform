"""Alarm evaluation and notification service."""
import json
import threading
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.alarm import AlarmRule, AlarmRecord, AlarmStatus, AlarmType, AlarmLevel
from app.models.sms import SmsPushRule, SmsRecord, SmsContact
from app.models.device import DeviceTag
from app.services.sms_service import sms_service


class AlarmService:
    """Evaluates alarm rules and triggers notifications."""

    def __init__(self):
        self._last_values: dict[str, float] = {}  # key: f"{tag_id}" -> last value
        self._trigger_timers: dict[int, datetime] = {}  # rule_id -> first trigger time
        self._sms_cooldowns: dict[int, datetime] = {}  # rule_id -> last sms sent time
        self._lock = threading.Lock()

    def evaluate(self, device_id: int, tag_id: int, tag_name: str, value: float):
        """Evaluate all alarm rules for a given tag value."""
        db = SessionLocal()
        try:
            rules = db.query(AlarmRule).filter(
                AlarmRule.device_id == device_id,
                AlarmRule.enabled == True,
            ).all()

            for rule in rules:
                # If rule is tag-specific, check tag match
                if rule.tag_id is not None and rule.tag_id != tag_id:
                    continue
                # For device-level disconnect rules
                if rule.alarm_type == AlarmType.DISCONNECT:
                    continue

                self._evaluate_rule(db, rule, tag_id, tag_name, value)
            db.commit()
        except Exception as e:
            logger.error(f"Alarm evaluate error: {e}")
            db.rollback()
        finally:
            db.close()

    def evaluate_disconnect(self, device_id: int, device_name: str):
        """Trigger disconnect alarms for a device."""
        db = SessionLocal()
        try:
            rules = db.query(AlarmRule).filter(
                AlarmRule.device_id == device_id,
                AlarmRule.alarm_type == AlarmType.DISCONNECT,
                AlarmRule.enabled == True,
            ).all()

            for rule in rules:
                existing = db.query(AlarmRecord).filter(
                    AlarmRecord.rule_id == rule.id,
                    AlarmRecord.status == AlarmStatus.ACTIVE,
                ).first()
                if not existing:
                    record = AlarmRecord(
                        rule_id=rule.id,
                        device_id=device_id,
                        alarm_type=rule.alarm_type,
                        alarm_level=rule.alarm_level,
                        alarm_message=f"设备 {device_name} 离线",
                        trigger_value=0,
                        threshold_value=0,
                        status=AlarmStatus.ACTIVE,
                    )
                    db.add(record)
                    db.flush()
                    self._handle_sms(db, rule, record)
            db.commit()
        except Exception as e:
            logger.error(f"Disconnect alarm error: {e}")
            db.rollback()
        finally:
            db.close()

    def clear_disconnect(self, device_id: int):
        """Clear disconnect alarms when device comes back online."""
        db = SessionLocal()
        try:
            records = db.query(AlarmRecord).filter(
                AlarmRecord.device_id == device_id,
                AlarmRecord.alarm_type == AlarmType.DISCONNECT,
                AlarmRecord.status == AlarmStatus.ACTIVE,
            ).all()
            for r in records:
                if r.rule and r.rule.auto_clear:
                    r.status = AlarmStatus.CLEARED
                    r.cleared_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            logger.error(f"Clear disconnect error: {e}")
            db.rollback()
        finally:
            db.close()

    def _evaluate_rule(self, db: Session, rule: AlarmRule, tag_id: int, tag_name: str, value: float):
        triggered = False
        threshold = 0.0
        message = ""

        if rule.alarm_type == AlarmType.THRESHOLD_HIGH:
            if rule.high_limit is not None:
                threshold = rule.high_limit
                if value > threshold + rule.deadband:
                    triggered = True
                    message = f"[上限报警] {tag_name} = {value} > {threshold}"

        elif rule.alarm_type == AlarmType.THRESHOLD_LOW:
            if rule.low_limit is not None:
                threshold = rule.low_limit
                if value < threshold - rule.deadband:
                    triggered = True
                    message = f"[下限报警] {tag_name} = {value} < {threshold}"

        elif rule.alarm_type == AlarmType.THRESHOLD_RANGE:
            if rule.high_limit is not None and rule.low_limit is not None:
                if value > rule.high_limit + rule.deadband:
                    triggered = True
                    threshold = rule.high_limit
                    message = f"[上限报警] {tag_name} = {value} > {threshold}"
                elif value < rule.low_limit - rule.deadband:
                    triggered = True
                    threshold = rule.low_limit
                    message = f"[下限报警] {tag_name} = {value} < {threshold}"

        elif rule.alarm_type == AlarmType.RATE_OF_CHANGE:
            if rule.rate_limit is not None:
                key = f"{tag_id}"
                with self._lock:
                    last_val = self._last_values.get(key)
                    self._last_values[key] = value
                if last_val is not None:
                    rate = abs(value - last_val)
                    if rate > rule.rate_limit:
                        triggered = True
                        threshold = rule.rate_limit
                        message = f"[变化率报警] {tag_name} 变化率 {rate:.2f}/s > {threshold}/s"

        elif rule.alarm_type == AlarmType.STATUS:
            if rule.status_value is not None:
                if value == rule.status_value:
                    triggered = True
                    threshold = rule.status_value
                    message = f"[状态报警] {tag_name} = {value} (目标值: {threshold})"

        # Handle delay
        if triggered and rule.delay_seconds > 0:
            key = rule.id
            with self._lock:
                if key not in self._trigger_timers:
                    self._trigger_timers[key] = datetime.utcnow()
                    return  # Start timer, don't trigger yet
                elapsed = (datetime.utcnow() - self._trigger_timers[key]).total_seconds()
                if elapsed < rule.delay_seconds:
                    return  # Still waiting
                del self._trigger_timers[key]
        elif not triggered:
            with self._lock:
                self._trigger_timers.pop(rule.id, None)

        if triggered:
            self._create_or_update_alarm(db, rule, tag_id, tag_name, value, threshold, message)
        elif rule.auto_clear:
            self._clear_alarm(db, rule.id, device_id=rule.device_id)

    def _create_or_update_alarm(
        self, db: Session, rule: AlarmRule, tag_id: int, tag_name: str,
        value: float, threshold: float, message: str,
    ):
        existing = db.query(AlarmRecord).filter(
            AlarmRecord.rule_id == rule.id,
            AlarmRecord.status == AlarmStatus.ACTIVE,
        ).first()

        if existing:
            # Update trigger value
            existing.trigger_value = value
            return

        record = AlarmRecord(
            rule_id=rule.id,
            device_id=rule.device_id,
            tag_id=tag_id,
            alarm_type=rule.alarm_type,
            alarm_level=rule.alarm_level,
            alarm_message=message,
            trigger_value=value,
            threshold_value=threshold,
            status=AlarmStatus.ACTIVE,
        )
        db.add(record)
        db.flush()

        logger.warning(f"ALARM: {message}")
        self._handle_sms(db, rule, record)

    def _clear_alarm(self, db: Session, rule_id: int, device_id: int):
        record = db.query(AlarmRecord).filter(
            AlarmRecord.rule_id == rule_id,
            AlarmRecord.device_id == device_id,
            AlarmRecord.status == AlarmStatus.ACTIVE,
        ).first()
        if record:
            record.status = AlarmStatus.CLEARED
            record.cleared_at = datetime.utcnow()

    def _handle_sms(self, db: Session, rule: AlarmRule, record: AlarmRecord):
        if not rule.sms_enabled:
            return

        # Check cooldown
        with self._lock:
            last_sms = self._sms_cooldowns.get(rule.id)
            if last_sms:
                # Get cooldown from push rules
                push_rules = db.query(SmsPushRule).filter(SmsPushRule.enabled == True).all()
                cooldown = 30  # default minutes
                for pr in push_rules:
                    if pr.cooldown_minutes < cooldown:
                        cooldown = pr.cooldown_minutes
                if (datetime.utcnow() - last_sms).total_seconds() < cooldown * 60:
                    return

        # Find matching push rules
        push_rules = db.query(SmsPushRule).filter(SmsPushRule.enabled == True).all()
        now_time = datetime.utcnow().strftime("%H:%M")

        for pr in push_rules:
            # Check time window
            if not (pr.time_start <= now_time <= pr.time_end):
                continue

            # Check alarm level filter
            if pr.alarm_levels:
                try:
                    levels = json.loads(pr.alarm_levels)
                    if record.alarm_level not in levels:
                        continue
                except json.JSONDecodeError:
                    pass

            # Check device filter
            if pr.device_ids:
                try:
                    device_ids = json.loads(pr.device_ids)
                    if record.device_id not in device_ids:
                        continue
                except json.JSONDecodeError:
                    pass

            # Send to all contacts
            try:
                contact_ids = json.loads(pr.contact_ids)
            except json.JSONDecodeError:
                continue

            for cid in contact_ids:
                contact = db.query(SmsContact).filter(SmsContact.id == cid, SmsContact.enabled == True).first()
                if not contact:
                    continue

                content = f"【报警通知】{record.alarm_message}\n等级: {record.alarm_level}\n时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
                success = sms_service.send_sms(contact.phone, content)

                sms_record = SmsRecord(
                    alarm_record_id=record.id,
                    contact_id=contact.id,
                    phone=contact.phone,
                    content=content,
                    status="sent" if success else "failed",
                    provider=settings.SMS_PROVIDER if success else "",
                    sent_at=datetime.utcnow() if success else None,
                )
                db.add(sms_record)

        with self._lock:
            self._sms_cooldowns[rule.id] = datetime.utcnow()


# Global instance
alarm_service = AlarmService()

# Import settings at module level for SMS provider
from app.core.config import settings
