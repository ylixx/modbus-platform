"""Alarm MQTT publish configuration models."""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, func
)
from app.core.database import Base


class AlarmMqttConfig(Base):
    """报警 MQTT 推送配置：支持自定义主题模板和 JSON 格式模板。"""
    __tablename__ = "alarm_mqtt_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, comment="配置名称")

    # ── 预设模式 ──
    # standard: 自定义主题/JSON模板
    # thingsboard_device: ThingsBoard 设备接入（token认证，自动格式）
    # thingsboard_gateway: ThingsBoard 网关接入（自动聚合格式）
    preset_mode = Column(String(32), default="standard", comment="预设模式: standard / thingsboard_device / thingsboard_gateway")

    # ── ThingsBoard 专属 ──
    tb_device_token = Column(String(256), default="", comment="ThingsBoard 设备Token（设备接入模式用，填在username字段）")
    tb_gateway_name = Column(String(128), default="", comment="ThingsBoard 网关设备名（网关接入模式用）")

    # ── MQTT Broker 连接 ──
    broker = Column(String(256), nullable=False, comment="MQTT Broker 地址")
    port = Column(Integer, default=1883, comment="端口")
    username = Column(String(128), default="", comment="用户名")
    password = Column(String(256), default="", comment="密码")
    use_tls = Column(Boolean, default=False, comment="是否启用TLS")

    # ── 主题模板 ──
    # 支持占位符: ${device_name}, ${alarm_level}, ${alarm_type}, ${status}
    topic_template = Column(String(512), nullable=False, default="alarms/${device_name}/${alarm_level}",
                           comment="发布主题模板，支持占位符: ${device_name}, ${alarm_level}, ${alarm_type}, ${status}")

    # ── JSON 格式模板 ──
    # 支持占位符: ${device_name}, ${device_id}, ${tag_name}, ${tag_id},
    #   ${alarm_type}, ${alarm_level}, ${alarm_message}, ${trigger_value},
    #   ${threshold_value}, ${status}, ${triggered_at}
    payload_template = Column(Text, nullable=False, default="", comment="JSON格式模板，留空则使用默认格式")

    # ── QoS ──
    qos = Column(Integer, default=0, comment="QoS: 0/1/2")

    # ── 过滤条件 ──
    # 报警等级过滤，JSON 数组，如 ["warning","critical","emergency"]，空=全部
    alarm_levels = Column(Text, default="", comment="报警等级过滤，JSON数组，空=全部")
    # 报警事件过滤，JSON 数组，如 ["triggered","cleared"]，空=全部
    alarm_events = Column(Text, default="", comment="报警事件过滤，JSON数组，如[triggered,cleared]，空=全部")
    # 设备ID过滤，JSON 数组，空=全部
    device_ids = Column(Text, default="", comment="设备ID过滤，JSON数组，空=全部")

    # ── 控制 ──
    enabled = Column(Boolean, default=True, comment="是否启用")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
