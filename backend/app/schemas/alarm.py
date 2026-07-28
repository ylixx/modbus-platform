"""Alarm schemas."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class AlarmRuleCreate(BaseModel):
    name: str
    description: str = ""
    device_id: int
    tag_id: Optional[int] = None
    alarm_type: str  # threshold_high | threshold_low | threshold_range | rate_of_change | status | disconnect
    alarm_level: str = "warning"
    high_limit: Optional[float] = None
    low_limit: Optional[float] = None
    deadband: float = 0.0
    rate_limit: Optional[float] = None
    status_value: Optional[float] = None
    delay_seconds: int = 0
    auto_clear: bool = True
    enabled: bool = True
    sms_enabled: bool = False


class AlarmRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    alarm_type: Optional[str] = None
    alarm_level: Optional[str] = None
    high_limit: Optional[float] = None
    low_limit: Optional[float] = None
    deadband: Optional[float] = None
    rate_limit: Optional[float] = None
    status_value: Optional[float] = None
    delay_seconds: Optional[int] = None
    auto_clear: Optional[bool] = None
    enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None


class AlarmRuleOut(BaseModel):
    id: int
    name: str
    description: str
    device_id: int
    tag_id: Optional[int]
    alarm_type: str
    alarm_level: str
    high_limit: Optional[float]
    low_limit: Optional[float]
    deadband: float
    rate_limit: Optional[float]
    status_value: Optional[float]
    delay_seconds: int
    auto_clear: bool
    enabled: bool
    sms_enabled: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlarmRecordOut(BaseModel):
    id: int
    rule_id: int
    device_id: int
    tag_id: Optional[int]
    alarm_type: str
    alarm_level: str
    alarm_message: str
    trigger_value: Optional[float]
    threshold_value: Optional[float]
    status: str
    triggered_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    cleared_at: Optional[datetime]
    acknowledged_by: Optional[str]
    ack_comment: str = ""
    # Joined fields
    device_name: str = ""
    tag_name: str = ""

    class Config:
        from_attributes = True


class AlarmAckRequest(BaseModel):
    comment: str = ""


class AlarmStats(BaseModel):
    total_active: int = 0
    total_acknowledged: int = 0
    total_cleared: int = 0
    by_level: dict = {}
    by_device: dict = {}
    recent: List[AlarmRecordOut] = []
