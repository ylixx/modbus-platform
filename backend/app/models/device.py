"""Device, DeviceGroup, DeviceTag models — supports Modbus / MQTT / OPC-UA."""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class ProtocolType(str, enum.Enum):
    MODBUS_TCP = "modbus_tcp"
    MQTT = "mqtt"
    OPC_UA = "opc_ua"


class DeviceStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    MAINTENANCE = "maintenance"


# ── Modbus specific ──

class FunctionCode(str, enum.Enum):
    COIL = "coil"
    DISCRETE_INPUT = "discrete_input"
    INPUT_REGISTER = "input_register"
    HOLDING_REGISTER = "holding_register"


class DataType(str, enum.Enum):
    BOOL = "bool"
    INT16 = "int16"
    UINT16 = "uint16"
    INT32 = "int32"
    UINT32 = "uint32"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    STRING = "string"
    BCD = "bcd"


class ByteOrder(str, enum.Enum):
    BIG_ENDIAN = "big_endian"
    LITTLE_ENDIAN = "little_endian"
    BIG_ENDIAN_SWAP = "big_endian_swap"
    LITTLE_ENDIAN_SWAP = "little_endian_swap"


# ── MQTT specific ──

class MqttQos(int, enum.Enum):
    QOS_0 = 0
    QOS_1 = 1
    QOS_2 = 2


# ── OPC-UA specific ──

class OpcSecurity(str, enum.Enum):
    NONE = "None"
    BASIC256SHA256 = "Basic256Sha256"
    BASIC256 = "Basic256"
    BASIC128RSA15 = "Basic128Rsa15"


# ─────────────────── Models ───────────────────

class DeviceGroup(Base):
    __tablename__ = "device_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(Text, default="")
    parent_id = Column(Integer, ForeignKey("device_groups.id"), nullable=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    children = relationship("DeviceGroup", backref="parent", remote_side=[id], lazy="select")
    devices = relationship("Device", back_populates="group", lazy="select")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(Text, default="")
    group_id = Column(Integer, ForeignKey("device_groups.id"), nullable=True)
    # 组织架构归属（厂-区-班组-位置 灵活树，可挂任意节点）
    org_node_id = Column(Integer, ForeignKey("org_nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    protocol = Column(String(20), default=ProtocolType.MODBUS_TCP)  # modbus_tcp | mqtt | opc_ua

    # ── Location fields ──
    factory = Column(String(128), default="")          # 厂级
    workshop = Column(String(128), default="")          # 区级
    production_line = Column(String(128), default="")   # 班级
    installation = Column(String(256), default="")      # 安装位置描述, e.g. "3号机组东侧"
    longitude = Column(Float, nullable=True)             # 经度
    latitude = Column(Float, nullable=True)              # 纬度

    # ── Modbus TCP fields ──
    host = Column(String(256), default="")
    port = Column(Integer, default=502)
    slave_id = Column(Integer, default=1)
    timeout = Column(Float, default=3.0)
    retries = Column(Integer, default=3)

    # ── MQTT fields ──
    mqtt_broker = Column(String(256), default="")
    mqtt_port = Column(Integer, default=1883)
    mqtt_username = Column(String(128), default="")
    mqtt_password = Column(String(256), default="")
    mqtt_client_id = Column(String(128), default="")
    mqtt_topic_prefix = Column(String(256), default="")
    mqtt_use_tls = Column(Boolean, default=False)
    mqtt_ca_cert = Column(Text, default="")
    mqtt_publish_enabled = Column(Boolean, default=False)   # enable data publish
    mqtt_publish_topic = Column(String(256), default="")    # topic to publish values
    mqtt_publish_qos = Column(Integer, default=0)
    mqtt_publish_interval = Column(Float, default=5.0)      # publish cycle in seconds
    mqtt_payload_format = Column(String(20), default="json")   # plain | json | thingsboard
    mqtt_payload_template = Column(Text, default="")  # 自定义发布模板，留空用默认格式
    mqtt_is_gateway = Column(Boolean, default=False)            # ThingsBoard gateway mode

    # ── OPC-UA fields ──
    opc_endpoint = Column(String(512), default="")           # opc.tcp://host:port
    opc_security_mode = Column(String(32), default="None")
    opc_username = Column(String(128), default="")
    opc_password = Column(String(256), default="")
    opc_certificate = Column(Text, default="")
    opc_private_key = Column(Text, default="")
    opc_namespace = Column(Integer, default=2)

    # ── Common fields ──
    status = Column(String(20), default=DeviceStatus.OFFLINE)
    last_poll_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    poll_interval = Column(Float, default=5.0)
    enabled = Column(Boolean, default=True)
    has_lab_data = Column(Boolean, default=False)  # 是否启用化验数据对比功能
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    group = relationship("DeviceGroup", back_populates="devices", lazy="select")
    tags = relationship("DeviceTag", back_populates="device", cascade="all,delete-orphan", lazy="select")


class DeviceTag(Base):
    __tablename__ = "device_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    unit = Column(String(32), default="")

    # ── Modbus fields ──
    function_code = Column(String(32), default="")
    address = Column(Integer, default=0)
    data_type = Column(String(20), default=DataType.UINT16)
    byte_order = Column(String(32), default=ByteOrder.BIG_ENDIAN)
    bit_index = Column(Integer, nullable=True)
    register_count = Column(Integer, default=1)

    # ── MQTT fields ──
    mqtt_topic = Column(String(512), default="")            # subscribe topic (overrides device prefix)
    mqtt_json_path = Column(String(256), default="")        # JSONPath expression, e.g. "sensors.temp"
    mqtt_value_type = Column(String(20), default="float64") # expected value type after parse
    mqtt_publish_topic = Column(String(512), default="")    # per-tag publish topic (overrides device)
    mqtt_retain = Column(Boolean, default=False)

    # ── OPC-UA fields ──
    opc_node_id = Column(String(512), default="")           # ns=2;s=Temperature or i=1001
    opc_node_type = Column(String(20), default="float64")   # expected type

    # ── Value processing (shared) ──
    scale_factor = Column(Float, default=1.0)
    offset = Column(Float, default=0.0)
    decimal_places = Column(Integer, default=2)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)

    # Script processing
    script_id = Column(Integer, ForeignKey("scripts.id"), nullable=True)

    writable = Column(Boolean, default=False)
    # 回读寄存器：本可写点位写入后，应从哪个 tag（同一设备的另一个采集点位）读回实际值。
    # 回读寄存器本身已是设备的一个已配置采集点位（writable=False）。
    readback_tag_id = Column(
        Integer,
        ForeignKey("device_tags.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sort_order = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    device = relationship("Device", back_populates="tags")
