"""Device template service.

模板 = 一类通用设备：协议 + 连接参数默认值 + 点位定义 + 可选告警规则。
- 内置模板（is_system=True）只读，可复制为普通模板再编辑
- 设备可绑定模板，模板改动（version+1）后可差异预览并同步到绑定设备
"""

# ── 内置模板定义（seed 时入库，is_system=True） ──

BUILTIN_TEMPLATES = [
    {
        "name": "西门子 S7-1200",
        "category": "PLC",
        "description": "西门子 S7-1200 系列 PLC (Modbus TCP)",
        "protocol": "modbus_tcp",
        "config": {"port": 502, "slave_id": 1, "poll_interval": 5},
        "tags": [
            {"name": "运行状态", "function_code": "coil", "address": 0, "data_type": "bool", "unit": "", "description": "设备运行状态"},
            {"name": "故障报警", "function_code": "coil", "address": 1, "data_type": "bool", "unit": "", "description": "故障报警标志"},
            {"name": "温度", "function_code": "input_register", "address": 0, "data_type": "float32", "scale_factor": 0.1, "unit": "°C"},
            {"name": "压力", "function_code": "input_register", "address": 2, "data_type": "float32", "scale_factor": 0.01, "unit": "MPa"},
            {"name": "流量", "function_code": "input_register", "address": 4, "data_type": "float32", "scale_factor": 0.1, "unit": "m³/h"},
            {"name": "设定温度", "function_code": "holding_register", "address": 0, "data_type": "float32", "scale_factor": 0.1, "unit": "°C", "writable": True},
            {"name": "启动停止", "function_code": "holding_register", "address": 10, "data_type": "uint16", "unit": "", "writable": True},
        ],
        "alarm_rules": [
            {"name": "温度超限", "alarm_type": "threshold_high", "alarm_level": "warning", "high_limit": 80, "deadband": 2, "delay_seconds": 10, "tag_name": "温度"},
            {"name": "压力超限", "alarm_type": "threshold_high", "alarm_level": "warning", "high_limit": 1.0, "deadband": 0.05, "delay_seconds": 5, "tag_name": "压力"},
        ],
    },
    {
        "name": "三菱 FX5U",
        "category": "PLC",
        "description": "三菱 FX5U 系列 PLC (Modbus TCP)",
        "protocol": "modbus_tcp",
        "config": {"port": 502, "slave_id": 1, "poll_interval": 5},
        "tags": [
            {"name": "运行中", "function_code": "coil", "address": 0, "data_type": "bool"},
            {"name": "故障", "function_code": "coil", "address": 1, "data_type": "bool"},
            {"name": "温度1", "function_code": "input_register", "address": 0, "data_type": "int16", "scale_factor": 0.1, "unit": "°C"},
            {"name": "温度2", "function_code": "input_register", "address": 1, "data_type": "int16", "scale_factor": 0.1, "unit": "°C"},
            {"name": "转速", "function_code": "input_register", "address": 2, "data_type": "uint16", "unit": "RPM"},
            {"name": "电压", "function_code": "input_register", "address": 3, "data_type": "uint16", "scale_factor": 0.1, "unit": "V"},
            {"name": "电流", "function_code": "input_register", "address": 4, "data_type": "uint16", "scale_factor": 0.01, "unit": "A"},
        ],
    },
    {
        "name": "温湿度传感器 (Modbus RTU/TCP)",
        "category": "传感器",
        "description": "通用 Modbus 温湿度传感器",
        "protocol": "modbus_tcp",
        "config": {"port": 502, "slave_id": 1, "poll_interval": 10},
        "tags": [
            {"name": "温度", "function_code": "input_register", "address": 0, "data_type": "int16", "scale_factor": 0.1, "unit": "°C"},
            {"name": "湿度", "function_code": "input_register", "address": 1, "data_type": "int16", "scale_factor": 0.1, "unit": "%RH"},
        ],
    },
    {
        "name": "多功能电力仪表",
        "category": "仪表",
        "description": "通用 Modbus 电力参数采集仪表",
        "protocol": "modbus_tcp",
        "config": {"port": 502, "slave_id": 1, "poll_interval": 5},
        "tags": [
            {"name": "A相电压", "function_code": "input_register", "address": 0, "data_type": "float32", "unit": "V"},
            {"name": "B相电压", "function_code": "input_register", "address": 2, "data_type": "float32", "unit": "V"},
            {"name": "C相电压", "function_code": "input_register", "address": 4, "data_type": "float32", "unit": "V"},
            {"name": "A相电流", "function_code": "input_register", "address": 6, "data_type": "float32", "unit": "A"},
            {"name": "B相电流", "function_code": "input_register", "address": 8, "data_type": "float32", "unit": "A"},
            {"name": "C相电流", "function_code": "input_register", "address": 10, "data_type": "float32", "unit": "A"},
            {"name": "总有功功率", "function_code": "input_register", "address": 12, "data_type": "float32", "unit": "kW"},
            {"name": "总无功功率", "function_code": "input_register", "address": 14, "data_type": "float32", "unit": "kVar"},
            {"name": "功率因数", "function_code": "input_register", "address": 16, "data_type": "float32", "unit": ""},
            {"name": "频率", "function_code": "input_register", "address": 18, "data_type": "float32", "unit": "Hz"},
            {"name": "总有功电度", "function_code": "input_register", "address": 20, "data_type": "float32", "unit": "kWh"},
        ],
    },
    {
        "name": "ThingsBoard 网关",
        "category": "网关",
        "description": "ThingsBoard 遥测数据网关 (MQTT)",
        "protocol": "mqtt",
        "config": {"mqtt_port": 1883, "mqtt_payload_format": "thingsboard", "mqtt_is_gateway": True, "mqtt_topic_prefix": "v1/gateway/telemetry", "poll_interval": 5},
        "tags": [],
    },
    {
        "name": "OPC-UA 西门子 PLC",
        "category": "PLC",
        "description": "通过 OPC-UA 连接西门子 PLC",
        "protocol": "opc_ua",
        "config": {"opc_endpoint": "opc.tcp://127.0.0.1:4840", "opc_namespace": 2, "poll_interval": 5},
        "tags": [
            {"name": "Temperature", "opc_node_id": "ns=2;s=Temperature", "opc_node_type": "float64", "unit": "°C"},
            {"name": "Pressure", "opc_node_id": "ns=2;s=Pressure", "opc_node_type": "float64", "unit": "bar"},
            {"name": "MotorStatus", "opc_node_id": "ns=2;s=MotorStatus", "opc_node_type": "bool", "unit": ""},
        ],
    },
    {
        "name": "MQTT 传感器节点",
        "category": "传感器",
        "description": "标准 JSON 格式的 MQTT 传感器",
        "protocol": "mqtt",
        "config": {"mqtt_port": 1883, "mqtt_payload_format": "json", "mqtt_topic_prefix": "sensors/node1", "poll_interval": 10},
        "tags": [
            {"name": "temperature", "mqtt_topic": "sensors/node1/temperature", "mqtt_value_type": "float64", "unit": "°C"},
            {"name": "humidity", "mqtt_topic": "sensors/node1/humidity", "mqtt_value_type": "float64", "unit": "%"},
            {"name": "pressure", "mqtt_topic": "sensors/node1/pressure", "mqtt_value_type": "float64", "unit": "hPa"},
        ],
    },
]


# ── 字段清单（用于设备↔模板、连接参数同步） ──

# 连接参数：创建设备时预填、同步时覆盖（点位之外的设备属性）
CONN_FIELDS = [
    "protocol", "host", "port", "slave_id", "timeout", "retries",
    "serial_port", "baudrate", "parity", "data_bits", "stop_bits",
    "mqtt_broker", "mqtt_port", "mqtt_username", "mqtt_password", "mqtt_client_id",
    "mqtt_topic_prefix", "mqtt_use_tls", "mqtt_ca_cert",
    "mqtt_publish_enabled", "mqtt_publish_topic", "mqtt_publish_qos",
    "mqtt_publish_interval", "mqtt_payload_format", "mqtt_payload_template",
    "mqtt_is_gateway",
    "opc_endpoint", "opc_security_mode", "opc_username", "opc_password",
    "opc_certificate", "opc_private_key", "opc_namespace",
    "poll_interval",
]

# 点位关键字段：参与差异比较与复制
TAG_FIELDS = [
    "name", "description", "unit", "function_code", "address", "data_type",
    "byte_order", "bit_index", "register_count", "mqtt_topic", "mqtt_json_path",
    "mqtt_value_type", "mqtt_publish_topic", "mqtt_retain", "opc_node_id",
    "opc_node_type", "scale_factor", "offset", "decimal_places", "min_value",
    "max_value", "writable", "sort_order", "enabled",
]


# ── 序列化辅助 ──

def serialize_tag(tag) -> dict:
    """DeviceTag ORM → 模板点位定义 dict（剔除关联 id 类字段）。"""
    return {k: getattr(tag, k, None) for k in TAG_FIELDS}


def serialize_binding(binding) -> dict:
    """绑定关系 → 同步状态 dict。"""
    return {
        "device_id": binding.device_id,
        "device_name": binding.device.name if binding.device else "",
        "template_id": binding.template_id,
        "template_name": binding.template.name if binding.template else "",
        "template_version": binding.template_version,
        "synced_at": binding.synced_at.isoformat() if binding.synced_at else None,
        "up_to_date": binding.template is not None and binding.template_version >= binding.template.version,
    }


# ── 差异计算 ──

def diff_tags(template_tags: list, device_tags: dict) -> dict:
    """计算模板点位与设备点位的差异。

    device_tags: {匹配键: tag_dict}，匹配键 = (name, function_code, address)
    返回: {"add": [tag_def...], "update": [{"tag": 模板定义, "device_tag_id": id}...],
           "delete": [{"device_tag_id": id, "name": 名称}...]}
    """
    result = {"add": [], "update": [], "delete": []}
    matched = set()
    for tdef in template_tags:
        key = (tdef.get("name"), tdef.get("function_code"), tdef.get("address"))
        existing = device_tags.get(key)
        if existing is None:
            result["add"].append(tdef)
        else:
            matched.add(key)
            differing = [
                k for k in TAG_FIELDS
                if existing.get(k) != tdef.get(k)
            ]
            if differing:
                result["update"].append({"tag": tdef, "device_tag_id": existing["id"], "differing": differing})
    for key, tag_dict in device_tags.items():
        if key not in matched:
            result["delete"].append({"device_tag_id": tag_dict["id"], "name": tag_dict["name"]})
    return result


def diff_conn(template_config: dict, device: dict) -> list:
    """连接参数差异：返回有差异的字段名列表（同步时仅覆盖这些字段）。"""
    return [k for k in CONN_FIELDS if k in template_config and device.get(k) != template_config[k]]


def _tag_key(tag) -> tuple:
    return (tag.get("name"), tag.get("function_code"), tag.get("address"))


def device_tag_map(device) -> dict:
    """设备的已采集点位 → {匹配键: {id, name, 各字段}}，跳过 disabled 点位。"""
    m = {}
    for t in device.tags:
        if not getattr(t, "enabled", True):
            continue
        d = serialize_tag(t)
        d["id"] = t.id
        m[_tag_key(d)] = d
    return m