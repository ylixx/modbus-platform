"""Alarm evaluation and notification service."""
import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional
from loguru import logger
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.alarm import AlarmRule, AlarmRecord, AlarmStatus, AlarmType, AlarmLevel
from app.models.sms import SmsPushRule, SmsRecord, SmsContact
from app.models.device import DeviceTag, Device
from app.services.sms_service import sms_service


class AlarmService:
    """Evaluates alarm rules and triggers notifications."""

    # Cleanup threshold: remove entries older than this many seconds
    _CLEANUP_AGE_SECONDS = 3600  # 1 hour
    _CLEANUP_INTERVAL = 300       # run cleanup every 5 minutes
    _last_cleanup = 0.0

    def __init__(self):
        self._last_values: dict[str, tuple[float, float]] = {}  # key -> (value, timestamp)
        self._trigger_timers: dict[int, tuple[datetime, datetime]] = {}  # rule_id -> (start_time, now)
        self._sms_cooldowns: dict[int, tuple[datetime, datetime]] = {}  # rule_id -> (sent_time, now)
        self._active_rules: set[int] = set()  # rule_ids currently in an alarm state (for hysteresis)
        self._lock = threading.Lock()

    def _maybe_cleanup(self):
        """Periodically purge stale entries from in-memory dicts to prevent leaks."""
        import time as _time
        now = _time.time()
        if now - self._last_cleanup < self._CLEANUP_INTERVAL:
            return
        self._last_cleanup = now

        cutoff = now - self._CLEANUP_AGE_SECONDS
        with self._lock:
            # Clean _last_values: stored as (value, timestamp)
            stale_keys = [k for k, v in self._last_values.items() if v[1] < cutoff]
            for k in stale_keys:
                del self._last_values[k]

            # Clean _trigger_timers / _sms_cooldowns: stored as datetime tuples
            cutoff_dt = datetime.now(timezone.utc) - timedelta(seconds=self._CLEANUP_AGE_SECONDS)
            for store in (self._trigger_timers, self._sms_cooldowns):
                stale = [k for k, v in store.items() if v[1] < cutoff_dt]
                for k in stale:
                    del store[k]

    def evaluate(self, device_id: int, tag_id: int, tag_name: str, value: float):
        """Evaluate all alarm rules for a given tag value."""
        self._maybe_cleanup()
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
                    r.cleared_at = datetime.now(timezone.utc)
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

        active = rule.id in self._active_rules
        deadband = rule.deadband if rule.deadband is not None else 0.0

        if rule.alarm_type == AlarmType.THRESHOLD_HIGH:
            if rule.high_limit is not None:
                threshold = rule.high_limit
                if active:
                    # Release only when value drops back below the limit
                    if value > threshold:
                        triggered = True
                        message = f"[上限报警] {tag_name} = {value} > {threshold}"
                else:
                    # Trigger when value exceeds limit by the deadband
                    if value > threshold + deadband:
                        triggered = True
                        message = f"[上限报警] {tag_name} = {value} > {threshold}"

        elif rule.alarm_type == AlarmType.THRESHOLD_LOW:
            if rule.low_limit is not None:
                threshold = rule.low_limit
                if active:
                    # Release only when value rises back above the limit
                    if value < threshold:
                        triggered = True
                        message = f"[下限报警] {tag_name} = {value} < {threshold}"
                else:
                    if value < threshold - deadband:
                        triggered = True
                        message = f"[下限报警] {tag_name} = {value} < {threshold}"

        elif rule.alarm_type == AlarmType.THRESHOLD_RANGE:
            if rule.high_limit is not None and rule.low_limit is not None:
                if active:
                    # Release only when back inside the limits
                    if value > rule.high_limit:
                        triggered = True
                        threshold = rule.high_limit
                        message = f"[上限报警] {tag_name} = {value} > {threshold}"
                    elif value < rule.low_limit:
                        triggered = True
                        threshold = rule.low_limit
                        message = f"[下限报警] {tag_name} = {value} < {threshold}"
                else:
                    if value > rule.high_limit + deadband:
                        triggered = True
                        threshold = rule.high_limit
                        message = f"[上限报警] {tag_name} = {value} > {threshold}"
                    elif value < rule.low_limit - deadband:
                        triggered = True
                        threshold = rule.low_limit
                        message = f"[下限报警] {tag_name} = {value} < {threshold}"

        elif rule.alarm_type == AlarmType.RATE_OF_CHANGE:
            if rule.rate_limit is not None:
                key = f"{tag_id}"
                import time as _time
                now_ts = _time.time()
                with self._lock:
                    last_val = self._last_values.get(key)
                    self._last_values[key] = (value, now_ts)
                if last_val is not None:
                    # 计算真实变化速率（差值/时间间隔）
                    time_diff = now_ts - last_val[1]
                    if time_diff > 0:
                        rate = abs(value - last_val[0]) / time_diff
                    else:
                        rate = 0.0
                    if rate > rule.rate_limit:
                        triggered = True
                        threshold = rule.rate_limit
                        message = f"[变化率报警] {tag_name} 变化率 {rate:.2f}/s > {threshold}/s"

        elif rule.alarm_type == AlarmType.STATUS:
            if rule.status_value is not None:
                if abs(value - rule.status_value) <= 1e-9:
                    triggered = True
                    threshold = rule.status_value
                    message = f"[状态报警] {tag_name} = {value} (目标值: {threshold})"

        # Handle delay: only start counting when triggered becomes True
        if triggered and rule.delay_seconds > 0:
            key = rule.id
            with self._lock:
                if key not in self._trigger_timers:
                    # First trigger — start the delay timer
                    self._trigger_timers[key] = (datetime.now(timezone.utc), datetime.now(timezone.utc))
                    self._active_rules.add(key)
                    return  # Don't trigger yet, wait for delay
                elapsed = (datetime.now(timezone.utc) - self._trigger_timers[key][0]).total_seconds()
                if elapsed < rule.delay_seconds:
                    # Still within delay window
                    self._trigger_timers[key] = (self._trigger_timers[key][0], datetime.now(timezone.utc))
                    return
                # Delay elapsed — remove timer and allow trigger
                del self._trigger_timers[key]
        elif not triggered:
            # Value returned to normal — clear any pending delay timer
            with self._lock:
                self._trigger_timers.pop(rule.id, None)
                self._active_rules.discard(rule.id)
        else:
            # No delay configured — track active state for hysteresis
            with self._lock:
                self._active_rules.add(rule.id)

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
        self._handle_notification(record)

        # MQTT publish
        self._handle_mqtt_publish("triggered", record, db)

        # Real-time push to WebSocket clients.
        try:
            from app.engine.ws_broadcast import broadcast_alarm_event
            broadcast_alarm_event("triggered", self._record_to_dict(record))
        except Exception:
            pass

    def _record_to_dict(self, record: AlarmRecord) -> dict:
        return {
            "id": record.id,
            "rule_id": record.rule_id,
            "device_id": record.device_id,
            "tag_id": record.tag_id,
            "alarm_type": record.alarm_type,
            "alarm_level": record.alarm_level,
            "alarm_message": record.alarm_message,
            "trigger_value": record.trigger_value,
            "threshold_value": record.threshold_value,
            "status": record.status,
            "triggered_at": record.triggered_at.isoformat() if record.triggered_at else None,
        }

    def _clear_alarm(self, db: Session, rule_id: int, device_id: int):
        record = db.query(AlarmRecord).filter(
            AlarmRecord.rule_id == rule_id,
            AlarmRecord.device_id == device_id,
            AlarmRecord.status == AlarmStatus.ACTIVE,
        ).first()
        if record:
            record.status = AlarmStatus.CLEARED
            record.cleared_at = datetime.now(timezone.utc)
            try:
                from app.engine.ws_broadcast import broadcast_alarm_event
                broadcast_alarm_event("cleared", self._record_to_dict(record))
            except Exception:
                pass
            # MQTT publish
            self._handle_mqtt_publish("cleared", record, db)

    def _handle_sms(self, db: Session, rule: AlarmRule, record: AlarmRecord):
        if not rule.sms_enabled:
            return

        # Check cooldown (per rule)
        with self._lock:
            last_sms = self._sms_cooldowns.get(rule.id)
            if last_sms:
                push_rules = db.query(SmsPushRule).filter(SmsPushRule.enabled == True).all()
                cooldown = 30  # default minutes
                for pr in push_rules:
                    if pr.cooldown_minutes < cooldown:
                        cooldown = pr.cooldown_minutes
                if (datetime.now(timezone.utc) - last_sms[0]).total_seconds() < cooldown * 60:
                    return

        # Find matching push rules
        push_rules = db.query(SmsPushRule).filter(SmsPushRule.enabled == True).all()
        now_time = datetime.now(timezone.utc).strftime("%H:%M")

        for pr in push_rules:
            # Check time window (supports cross-midnight, e.g. 22:00~06:00)
            if pr.time_start <= pr.time_end:
                in_window = pr.time_start <= now_time <= pr.time_end
            else:
                # Cross-midnight: valid if now >= start OR now <= end
                in_window = now_time >= pr.time_start or now_time <= pr.time_end
            if not in_window:
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

                content = f"【报警通知】{record.alarm_message}\n等级: {record.alarm_level}\n时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
                success = sms_service.send_sms(contact.phone, content)

                sms_record = SmsRecord(
                    alarm_record_id=record.id,
                    contact_id=contact.id,
                    phone=contact.phone,
                    content=content,
                    status="sent" if success else "failed",
                    provider=settings.SMS_PROVIDER if success else "",
                    sent_at=datetime.now(timezone.utc) if success else None,
                )
                db.add(sms_record)

        with self._lock:
            self._sms_cooldowns[rule.id] = (datetime.now(timezone.utc), datetime.now(timezone.utc))

    def _handle_notification(self, record: AlarmRecord):
        """Send alarm via DingTalk/WeChat/Email."""
        try:
            from app.services.notification_service import notification_service
            db = SessionLocal()
            try:
                device = db.query(Device).filter(Device.id == record.device_id).first()
                device_name = device.name if device else f"Device#{record.device_id}"
            finally:
                db.close()
            notification_service.send_alarm(record.alarm_message, record.alarm_level, device_name)
        except Exception as e:
            logger.error(f"Notification error: {e}")

    def _handle_mqtt_publish(self, event: str, record: AlarmRecord, db: Session):
        """Publish alarm event to external MQTT brokers (async, non-blocking)."""
        from app.services.config_service import is_feature_enabled
        if not is_feature_enabled("alarm_mqtt"):
            return
        try:
            from app.services.alarm_mqtt_publisher import alarm_mqtt_publisher
            # Enrich alarm data with device/tag names for template rendering
            device = db.query(Device).filter(Device.id == record.device_id).first()
            tag = db.query(DeviceTag).filter(DeviceTag.id == record.tag_id).first() if record.tag_id else None
            alarm_data = self._record_to_dict(record)
            alarm_data["device_name"] = device.name if device else f"Device#{record.device_id}"
            alarm_data["tag_name"] = tag.name if tag else ""
            alarm_mqtt_publisher.publish_alarm(event, alarm_data)
        except Exception as e:
            logger.error(f"Alarm MQTT publish error: {e}")


# Global instance
alarm_service = AlarmService()

# Import settings at module level for SMS provider
from app.core.config import settings
