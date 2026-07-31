"""Data forward rule model — push collected telemetry to external MQTT brokers.

Unlike device-level publish (which is per-device and lives in the Device model),
forward rules are independent configurations that can aggregate data from
multiple devices/tags and push with preset modes (standard / ThingsBoard).
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, func
)
from app.core.database import Base


class DataForwardRule(Base):
    """数据转发规则：将采集到的遥测数据按规则推送到外部 MQTT Broker。"""
    __tablename__ = "data_forward_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, comment="规则名称")

    # ── 预设模式 ──
    # standard: 自定义主题/JSON模板
    # thingsboard_device: ThingsBoard 设备接入（token认证，固定topic+遥测格式）
    # thingsboard_gateway: ThingsBoard 网关接入（网关聚合格式）
    preset_mode = Column(String(32), default="standard", comment="预设模式")

    # ── ThingsBoard 专属 ──
    tb_device_token = Column(String(256), default="", comment="ThingsBoard 设备/网关 AccessToken")
    tb_gateway_name = Column(String(128), default="", comment="ThingsBoard 网关设备名")

    # ── MQTT Broker 连接 ──
    broker = Column(String(256), nullable=False, comment="MQTT Broker 地址")
    port = Column(Integer, default=1883, comment="端口")
    username = Column(String(128), default="", comment="用户名")
    password = Column(String(256), default="", comment="密码")
    use_tls = Column(Boolean, default=False, comment="是否启用TLS")

    # ── 主题和格式 ──
    topic_template = Column(String(512), nullable=False, default="data/${device_name}",
                            comment="发布主题模板")
    payload_template = Column(Text, nullable=False, default="", comment="JSON格式模板，留空使用默认")

    # ── 发布控制 ──
    publish_interval = Column(Float, default=10.0, comment="发布间隔(秒)")
    qos = Column(Integer, default=0, comment="QoS: 0/1/2")

    # ── 数据源过滤 ──
    # device_ids: JSON数组，空=全部设备，如 [1,2,3]
    device_ids = Column(Text, default="", comment="设备ID过滤，JSON数组，空=全部")
    # tag_ids: JSON数组，空=全部点位，如 [10,20,30]
    tag_ids = Column(Text, default="", comment="点位ID过滤，JSON数组，空=全部")
    # aggregate_mode: single / per_device / all_in_one
    #   single:      每个点位独立一条消息
    #   per_device:  每台设备的所有点位聚合为一条消息
    #   all_in_one:  所有设备的所有点位聚合为一条消息
    aggregate_mode = Column(String(32), default="per_device", comment="聚合模式: single / per_device / all_in_one")

    # ── 控制 ──
    enabled = Column(Boolean, default=True, comment="是否启用")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
