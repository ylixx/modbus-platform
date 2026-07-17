"""SMS models."""
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey, func
)
from app.core.database import Base
import enum


class SmsStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class SmsContact(Base):
    __tablename__ = "sms_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    phone = Column(String(20), nullable=False, unique=True)
    department = Column(String(128), default="")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class SmsPushRule(Base):
    __tablename__ = "sms_push_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")

    # Filter conditions
    device_ids = Column(Text, default="")       # JSON array of device IDs, empty = all
    alarm_levels = Column(Text, default="")     # JSON array of levels, empty = all
    time_start = Column(String(5), default="00:00")  # HH:MM
    time_end = Column(String(5), default="23:59")

    # Recipients
    contact_ids = Column(Text, nullable=False)  # JSON array of contact IDs

    # Control
    enabled = Column(Boolean, default=True)
    cooldown_minutes = Column(Integer, default=30)  # 同一报警规则的短信冷却时间
    created_at = Column(DateTime, server_default=func.now())


class SmsRecord(Base):
    __tablename__ = "sms_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_record_id = Column(Integer, ForeignKey("alarm_records.id"), nullable=True)
    contact_id = Column(Integer, ForeignKey("sms_contacts.id"), nullable=False)
    phone = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)

    status = Column(String(20), default=SmsStatus.PENDING)
    provider = Column(String(20), default="")
    provider_msg_id = Column(String(128), default="")
    error_message = Column(Text, default="")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
