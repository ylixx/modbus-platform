"""Alarm MQTT publish configuration schemas."""
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

AlarmMqttPresetLiteral = Literal["standard", "thingsboard_device", "thingsboard_gateway"]


class AlarmMqttConfigCreate(BaseModel):
    name: str
    preset_mode: AlarmMqttPresetLiteral = "standard"
    broker: str = ""
    port: int = 1883
    username: str = ""
    password: str = ""
    use_tls: bool = False
    # ThingsBoard 专属
    tb_device_token: str = ""
    tb_gateway_name: str = ""
    # 主题 & 格式模板
    topic_template: str = "alarms/${device_name}/${alarm_level}"
    payload_template: str = ""
    qos: int = 0
    # 过滤
    alarm_levels: str = ""
    alarm_events: str = ""
    device_ids: str = ""
    enabled: bool = True


class AlarmMqttConfigUpdate(BaseModel):
    name: Optional[str] = None
    preset_mode: Optional[AlarmMqttPresetLiteral] = None
    broker: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: Optional[bool] = None
    tb_device_token: Optional[str] = None
    tb_gateway_name: Optional[str] = None
    topic_template: Optional[str] = None
    payload_template: Optional[str] = None
    qos: Optional[int] = None
    alarm_levels: Optional[str] = None
    alarm_events: Optional[str] = None
    device_ids: Optional[str] = None
    enabled: Optional[bool] = None


class AlarmMqttConfigOut(BaseModel):
    id: int
    name: str
    preset_mode: str
    broker: str
    port: int
    username: str
    password: str
    use_tls: bool
    tb_device_token: str
    tb_gateway_name: str
    topic_template: str
    payload_template: str
    qos: int
    alarm_levels: str
    alarm_events: str
    device_ids: str
    enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
