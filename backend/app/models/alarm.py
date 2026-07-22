"""Alarm models."""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class AlarmLevel(str, enum.Enum):
    INFO = "info"          # 提示
    WARNING = "warning"    # 警告
    CRITICAL = "critical"  # 严重
    EMERGENCY = "emergency"  # 紧急


class AlarmType(str, enum.Enum):
    THRESHOLD_HIGH = "threshold_high"       # 上限报警
    THRESHOLD_LOW = "threshold_low"         # 下下限报警
    THRESHOLD_RANGE = "threshold_range"     # 区间报警
    RATE_OF_CHANGE = "rate_of_change"       # 变化率报警
    STATUS = "status"                       # 状态报警（等于某值）
    DISCONNECT = "disconnect"               # 设备离线报警


class AlarmStatus(str, enum.Enum):
    ACTIVE = "active"           # 报警中
    ACKNOWLEDGED = "acknowledged"  # 已确认
    CLEARED = "cleared"         # 已消除


class AlarmRule(Base):
    __tablename__ = "alarm_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("device_tags.id", ondelete="CASCADE"), nullable=True, index=True)

    # Alarm definition
    alarm_type = Column(String(32), nullable=False)
    alarm_level = Column(String(20), default=AlarmLevel.WARNING)

    # Threshold parameters
    high_limit = Column(Float, nullable=True)
    low_limit = Column(Float, nullable=True)
    deadband = Column(Float, default=0.0)         # 死区，防抖动
    rate_limit = Column(Float, nullable=True)      # 变化率限制 (unit/sec)
    status_value = Column(Float, nullable=True)    # 状态报警的目标值

    # Timing
    delay_seconds = Column(Integer, default=0)     # 报警延迟（持续N秒后才触发）
    auto_clear = Column(Boolean, default=True)     # 条件不满足时自动消除

    # Control
    enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=False)   # 是否发送短信
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    device = relationship("Device", lazy="select")
    tag = relationship("DeviceTag", lazy="select")
    records = relationship("AlarmRecord", back_populates="rule", lazy="select")


class AlarmRecord(Base):
    __tablename__ = "alarm_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("alarm_rules.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("device_tags.id"), nullable=True)

    # Alarm info
    alarm_type = Column(String(32), nullable=False)
    alarm_level = Column(String(20), nullable=False)
    alarm_message = Column(Text, default="")
    trigger_value = Column(Float, nullable=True)    # 触发时的值
    threshold_value = Column(Float, nullable=True)  # 触发的阈值

    # Status
    status = Column(String(20), default=AlarmStatus.ACTIVE)
    triggered_at = Column(DateTime, server_default=func.now())
    acknowledged_at = Column(DateTime, nullable=True)
    cleared_at = Column(DateTime, nullable=True)

    # Ack info
    acknowledged_by = Column(String(64), nullable=True)
    ack_comment = Column(Text, default="")

    rule = relationship("AlarmRule", back_populates="records")


class AlarmAck(Base):
    """Alarm acknowledgement log."""
    __tablename__ = "alarm_acks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_record_id = Column(Integer, ForeignKey("alarm_records.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    username = Column(String(64), default="")
    comment = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
