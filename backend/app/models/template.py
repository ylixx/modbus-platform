"""DeviceTemplate & template binding models.

模板 = 一类通用设备：协议 + 连接参数默认值 + 点位定义（JSON）。
设备可绑定模板（device_template_bindings），模板改动后可同步到绑定设备。
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class DeviceTemplate(Base):
    """设备模板（内置模板 is_system=True 只读，可复制为普通模板）。"""

    __tablename__ = "device_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True, index=True)
    category = Column(String(64), default="")          # PLC / 传感器 / 仪表 / 网关 ...
    description = Column(Text, default="")

    protocol = Column(String(20), default="modbus_tcp")  # modbus_tcp | modbus_rtu | mqtt | opc_ua

    # 连接参数默认值（JSON）：port / slave_id / poll_interval / mqtt_* / opc_* 等，
    # 与 Device 模型字段同名，创建设备时预填、同步时覆盖。
    config = Column(JSON, default=dict)

    # 点位定义（JSON 数组）：与 DeviceTag 语义一致的对象数组
    # [{name, unit, function_code, address, data_type, byte_order, bit_index,
    #   register_count, scale_factor, offset, decimal_places, min_value, max_value,
    #   writable, mqtt_topic, mqtt_json_path, mqtt_value_type, mqtt_publish_topic,
    #   mqtt_retain, opc_node_id, opc_node_type, enabled, sort_order, description}]
    tags = Column(JSON, default=list)

    # 可选：模板携带的默认告警规则定义（JSON 数组）
    # [{name, alarm_type, alarm_level, high_limit, low_limit, deadband,
    #   rate_limit, status_value, delay_seconds, auto_clear, sms_enabled,
    #   tag_name(关联点位名，创建时解析为该设备的 tag_id)}]
    alarm_rules = Column(JSON, default=list)

    is_system = Column(Boolean, default=False)          # 内置模板不可编辑/删除
    version = Column(Integer, default=1)                # 每次内容变更 +1（同步判断依据）
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    org_node_id = Column(Integer, ForeignKey("org_nodes.id", ondelete="SET NULL"), nullable=True)  # 模板归属组织（空=公共）
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    bindings = relationship("DeviceTemplateBinding", back_populates="template", cascade="all,delete-orphan", lazy="select")


class DeviceTemplateBinding(Base):
    """设备与模板的绑定关系（同步状态记录）。"""

    __tablename__ = "device_template_bindings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    template_id = Column(Integer, ForeignKey("device_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    template_version = Column(Integer, default=1)       # 设备最后一次同步的模板版本
    synced_at = Column(DateTime, nullable=True)         # 最后同步时间
    created_at = Column(DateTime, server_default=func.now())

    template = relationship("DeviceTemplate", back_populates="bindings", lazy="select")
    device = relationship("Device", back_populates="template_binding", lazy="select")