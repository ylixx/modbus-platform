"""SMS schemas."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class SmsContactCreate(BaseModel):
    name: str
    phone: str
    department: str = ""
    enabled: bool = True


class SmsContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    enabled: Optional[bool] = None


class SmsContactOut(BaseModel):
    id: int
    name: str
    phone: str
    department: str
    enabled: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SmsPushRuleCreate(BaseModel):
    name: str
    description: str = ""
    device_ids: str = ""       # JSON array string
    alarm_levels: str = ""     # JSON array string
    time_start: str = "00:00"
    time_end: str = "23:59"
    contact_ids: str           # JSON array string
    enabled: bool = True
    cooldown_minutes: int = 30


class SmsPushRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    device_ids: Optional[str] = None
    alarm_levels: Optional[str] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    contact_ids: Optional[str] = None
    enabled: Optional[bool] = None
    cooldown_minutes: Optional[int] = None


class SmsPushRuleOut(BaseModel):
    id: int
    name: str
    description: str
    device_ids: str
    alarm_levels: str
    time_start: str
    time_end: str
    contact_ids: str
    enabled: bool
    cooldown_minutes: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SmsRecordOut(BaseModel):
    id: int
    alarm_record_id: Optional[int]
    contact_id: int
    phone: str
    content: str
    status: str
    provider: str
    error_message: str
    retry_count: int
    sent_at: Optional[datetime]
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SmsTestRequest(BaseModel):
    phone: str
    content: str = "【测试】Modbus平台短信测试，请忽略此消息。"
