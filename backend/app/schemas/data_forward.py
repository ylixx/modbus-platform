"""Data forward rule schemas."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DataForwardRuleCreate(BaseModel):
    name: str
    preset_mode: str = "standard"
    broker: str = ""
    port: int = 1883
    username: str = ""
    password: str = ""
    use_tls: bool = False
    tb_device_token: str = ""
    tb_gateway_name: str = ""
    topic_template: str = "data/${device_name}"
    payload_template: str = ""
    publish_interval: float = 10.0
    qos: int = 0
    device_ids: str = ""
    tag_ids: str = ""
    aggregate_mode: str = "per_device"
    enabled: bool = True


class DataForwardRuleUpdate(BaseModel):
    name: Optional[str] = None
    preset_mode: Optional[str] = None
    broker: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: Optional[bool] = None
    tb_device_token: Optional[str] = None
    tb_gateway_name: Optional[str] = None
    topic_template: Optional[str] = None
    payload_template: Optional[str] = None
    publish_interval: Optional[float] = None
    qos: Optional[int] = None
    device_ids: Optional[str] = None
    tag_ids: Optional[str] = None
    aggregate_mode: Optional[str] = None
    enabled: Optional[bool] = None


class DataForwardRuleOut(BaseModel):
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
    publish_interval: float
    qos: int
    device_ids: str
    tag_ids: str
    aggregate_mode: str
    enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
