"""Device schemas — supports Modbus / MQTT / OPC-UA."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Device Group ──

class GroupCreate(BaseModel):
    name: str
    description: str = ""
    parent_id: Optional[int] = None
    sort_order: int = 0


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


class GroupOut(BaseModel):
    id: int
    name: str
    description: str
    parent_id: Optional[int]
    sort_order: int
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True


# ── Device Tag ──

class TagCreate(BaseModel):
    device_id: int
    name: str
    description: str = ""
    unit: str = ""

    # Modbus
    function_code: str = ""
    address: int = 0
    data_type: str = "uint16"
    byte_order: str = "big_endian"
    bit_index: Optional[int] = None
    register_count: int = 1

    # MQTT
    mqtt_topic: str = ""
    mqtt_json_path: str = ""
    mqtt_value_type: str = "float64"
    mqtt_publish_topic: str = ""
    mqtt_retain: bool = False

    # OPC-UA
    opc_node_id: str = ""
    opc_node_type: str = "float64"

    # Common
    scale_factor: float = 1.0
    offset: float = 0.0
    decimal_places: int = 2
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    script_id: Optional[int] = None
    writable: bool = False
    sort_order: int = 0
    enabled: bool = True


class TagUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None

    function_code: Optional[str] = None
    address: Optional[int] = None
    data_type: Optional[str] = None
    byte_order: Optional[str] = None
    bit_index: Optional[int] = None
    register_count: Optional[int] = None

    mqtt_topic: Optional[str] = None
    mqtt_json_path: Optional[str] = None
    mqtt_value_type: Optional[str] = None
    mqtt_publish_topic: Optional[str] = None
    mqtt_retain: Optional[bool] = None

    opc_node_id: Optional[str] = None
    opc_node_type: Optional[str] = None

    scale_factor: Optional[float] = None
    offset: Optional[float] = None
    decimal_places: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    script_id: Optional[int] = None
    writable: Optional[bool] = None
    sort_order: Optional[int] = None
    enabled: Optional[bool] = None


class TagOut(BaseModel):
    id: int
    device_id: int
    name: str
    description: str
    unit: str

    function_code: str
    address: int
    data_type: str
    byte_order: str
    bit_index: Optional[int]
    register_count: int

    mqtt_topic: str
    mqtt_json_path: str
    mqtt_value_type: str
    mqtt_publish_topic: str
    mqtt_retain: bool

    opc_node_id: str
    opc_node_type: str

    scale_factor: float
    offset: float
    decimal_places: int
    min_value: Optional[float]
    max_value: Optional[float]
    script_id: Optional[int]
    writable: bool
    sort_order: int
    enabled: bool
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True


# ── Device ──

class DeviceCreate(BaseModel):
    name: str
    description: str = ""
    group_id: Optional[int] = None
    org_node_id: Optional[int] = None
    protocol: str = "modbus_tcp"  # modbus_tcp | mqtt | opc_ua

    # Location
    factory: str = ""
    workshop: str = ""
    production_line: str = ""
    installation: str = ""
    longitude: Optional[float] = None
    latitude: Optional[float] = None

    # Modbus
    host: str = ""
    port: int = 502
    slave_id: int = 1
    timeout: float = 3.0
    retries: int = 3

    # MQTT
    mqtt_broker: str = ""
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_client_id: str = ""
    mqtt_topic_prefix: str = ""
    mqtt_use_tls: bool = False
    mqtt_ca_cert: str = ""
    mqtt_publish_enabled: bool = False
    mqtt_publish_topic: str = ""
    mqtt_publish_qos: int = 0
    mqtt_publish_interval: float = 5.0
    mqtt_payload_format: str = "json"    # plain | json | thingsboard
    mqtt_payload_template: str = ""      # 自定义发布模板
    mqtt_is_gateway: bool = False

    # OPC-UA
    opc_endpoint: str = ""
    opc_security_mode: str = "None"
    opc_username: str = ""
    opc_password: str = ""
    opc_certificate: str = ""
    opc_private_key: str = ""
    opc_namespace: int = 2

    # Common
    poll_interval: float = 5.0
    enabled: bool = True
    has_lab_data: bool = False


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    group_id: Optional[int] = None
    org_node_id: Optional[int] = None
    protocol: Optional[str] = None

    factory: Optional[str] = None
    workshop: Optional[str] = None
    production_line: Optional[str] = None
    installation: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None

    host: Optional[str] = None
    port: Optional[int] = None
    slave_id: Optional[int] = None
    timeout: Optional[float] = None
    retries: Optional[int] = None

    mqtt_broker: Optional[str] = None
    mqtt_port: Optional[int] = None
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_client_id: Optional[str] = None
    mqtt_topic_prefix: Optional[str] = None
    mqtt_use_tls: Optional[bool] = None
    mqtt_ca_cert: Optional[str] = None
    mqtt_publish_enabled: Optional[bool] = None
    mqtt_publish_topic: Optional[str] = None
    mqtt_publish_qos: Optional[int] = None
    mqtt_publish_interval: Optional[float] = None
    mqtt_payload_format: Optional[str] = None
    mqtt_payload_template: Optional[str] = None
    mqtt_is_gateway: Optional[bool] = None

    opc_endpoint: Optional[str] = None
    opc_security_mode: Optional[str] = None
    opc_username: Optional[str] = None
    opc_password: Optional[str] = None
    opc_certificate: Optional[str] = None
    opc_private_key: Optional[str] = None
    opc_namespace: Optional[int] = None

    poll_interval: Optional[float] = None
    enabled: Optional[bool] = None
    has_lab_data: Optional[bool] = None


class DeviceOut(BaseModel):
    id: int
    name: str
    description: str
    group_id: Optional[int]
    org_node_id: Optional[int] = None
    protocol: str

    factory: str
    workshop: str
    production_line: str
    installation: str
    longitude: Optional[float]
    latitude: Optional[float]

    host: str
    port: int
    slave_id: int
    timeout: float
    retries: int

    mqtt_broker: str
    mqtt_port: int
    mqtt_client_id: str
    mqtt_topic_prefix: str
    mqtt_use_tls: bool
    mqtt_publish_enabled: bool
    mqtt_publish_topic: str
    mqtt_publish_qos: int
    mqtt_publish_interval: float
    mqtt_payload_format: str
    mqtt_payload_template: str
    mqtt_is_gateway: bool

    opc_endpoint: str
    opc_security_mode: str
    opc_namespace: int

    status: str
    last_poll_at: Optional[datetime]
    last_error: Optional[str]
    poll_interval: float = 5.0
    enabled: bool = True
    has_lab_data: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True


class DeviceDetailOut(DeviceOut):
    tags: List[TagOut] = []


# ── Write request ──

class WriteRequest(BaseModel):
    tag_id: int
    value: float | bool | int | str
