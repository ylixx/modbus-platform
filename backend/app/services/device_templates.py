"""Pre-defined device templates for quick device creation.

Each template contains:
  - Device connection defaults
  - Pre-configured tags with addresses, types, units
"""


DEVICE_TEMPLATES = [
    {
        "id": "siemens_s7_1200",
        "name": "西门子 S7-1200",
        "category": "PLC",
        "description": "西门子 S7-1200 系列 PLC (Modbus TCP)",
        "protocol": "modbus_tcp",
        "port": 502,
        "poll_interval": 5,
        "tags": [
            {"name": "运行状态", "function_code": "coil", "address": 0, "data_type": "bool", "unit": "", "description": "设备运行状态"},
            {"name": "故障报警", "function_code": "coil", "address": 1, "data_type": "bool", "unit": "", "description": "故障报警标志"},
            {"name": "温度", "function_code": "input_register", "address": 0, "data_type": "float32", "scale_factor": 0.1, "unit": "°C"},
            {"name": "压力", "function_code": "input_register", "address": 2, "data_type": "float32", "scale_factor": 0.01, "unit": "MPa"},
            {"name": "流量", "function_code": "input_register", "address": 4, "data_type": "float32", "scale_factor": 0.1, "unit": "m³/h"},
            {"name": "设定温度", "function_code": "holding_register", "address": 0, "data_type": "float32", "scale_factor": 0.1, "unit": "°C", "writable": True},
            {"name": "启动停止", "function_code": "holding_register", "address": 10, "data_type": "uint16", "unit": "", "writable": True},
        ],
    },
    {
        "id": "mitsubishi_fx5u",
        "name": "三菱 FX5U",
        "category": "PLC",
        "description": "三菱 FX5U 系列 PLC (Modbus TCP)",
        "protocol": "modbus_tcp",
        "port": 502,
        "poll_interval": 5,
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
        "id": "modbus_sensor_temp_humi",
        "name": "温湿度传感器 (Modbus RTU/TCP)",
        "category": "传感器",
        "description": "通用 Modbus 温湿度传感器",
        "protocol": "modbus_tcp",
        "port": 502,
        "slave_id": 1,
        "poll_interval": 10,
        "tags": [
            {"name": "温度", "function_code": "input_register", "address": 0, "data_type": "int16", "scale_factor": 0.1, "unit": "°C"},
            {"name": "湿度", "function_code": "input_register", "address": 1, "data_type": "int16", "scale_factor": 0.1, "unit": "%RH"},
        ],
    },
    {
        "id": "modbus_power_meter",
        "name": "多功能电力仪表",
        "category": "仪表",
        "description": "通用 Modbus 电力参数采集仪表",
        "protocol": "modbus_tcp",
        "port": 502,
        "poll_interval": 5,
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
        "id": "thingsboard_gateway",
        "name": "ThingsBoard 网关",
        "category": "网关",
        "description": "ThingsBoard 遥测数据网关 (MQTT)",
        "protocol": "mqtt",
        "mqtt_port": 1883,
        "mqtt_payload_format": "thingsboard",
        "mqtt_is_gateway": True,
        "mqtt_topic_prefix": "v1/gateway/telemetry",
        "poll_interval": 5,
        "tags": [],
    },
    {
        "id": "opc_ua_siemens",
        "name": "OPC-UA 西门子 PLC",
        "category": "PLC",
        "description": "通过 OPC-UA 连接西门子 PLC",
        "protocol": "opc_ua",
        "opc_endpoint": "opc.tcp://192.168.1.100:4840",
        "opc_namespace": 2,
        "poll_interval": 5,
        "tags": [
            {"name": "Temperature", "opc_node_id": "ns=2;s=Temperature", "opc_node_type": "float64", "unit": "°C"},
            {"name": "Pressure", "opc_node_id": "ns=2;s=Pressure", "opc_node_type": "float64", "unit": "bar"},
            {"name": "MotorStatus", "opc_node_id": "ns=2;s=MotorStatus", "opc_node_type": "bool", "unit": ""},
        ],
    },
    {
        "id": "mqtt_sensor",
        "name": "MQTT 传感器节点",
        "category": "传感器",
        "description": "标准 JSON 格式的 MQTT 传感器",
        "protocol": "mqtt",
        "mqtt_port": 1883,
        "mqtt_payload_format": "json",
        "mqtt_topic_prefix": "sensors/node1",
        "poll_interval": 10,
        "tags": [
            {"name": "temperature", "mqtt_topic": "sensors/node1/temperature", "mqtt_value_type": "float64", "unit": "°C"},
            {"name": "humidity", "mqtt_topic": "sensors/node1/humidity", "mqtt_value_type": "float64", "unit": "%"},
            {"name": "pressure", "mqtt_topic": "sensors/node1/pressure", "mqtt_value_type": "float64", "unit": "hPa"},
        ],
    },
]


def get_all_templates():
    return DEVICE_TEMPLATES


def get_template(template_id: str):
    for t in DEVICE_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None
