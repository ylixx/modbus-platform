# 平台侧设备/点位导入指南

模拟器在 `simulator/scenarios.yaml` 里定义了 3 台模拟设备。你可以**手动**在平台添加，也
可以运行自动导入：`python simulator/seed/seed_platform.py`（默认连 `http://127.0.0.1:8000`，
账号 `admin / admin123`）。下面给出手动添加时需要的**精确字段值**。

> 通用：点位 `scale_factor=1`、`offset=0`、`decimal_places=2`、`enabled=true`。
> 可写点位（`writable=true`）的「回读点位」填它**自己**（readback_tag_id = 该点位 id）。

---

## 1) SIM_MODBUS_PLC（Modbus-TCP 从机）

设备字段：
| 字段 | 值 |
|---|---|
| name | `SIM_MODBUS_PLC` |
| protocol | `modbus_tcp` |
| host | `127.0.0.1` |
| port | `15021` |
| slave_id | `1` |
| poll_interval | `5` |

点位（function_code / address / data_type / byte_order）：
| 点位名 | 单位 | function_code | address | data_type | byte_order | writable |
|---|---|---|---|---|---|---|
| temperature | °C | holding_register | 0 | float32 | big_endian | |
| pressure | bar | holding_register | 2 | uint16 | big_endian | |
| setpoint | °C | holding_register | 4 | float32 | big_endian | ✅ |
| flow_rate | m3/h | input_register | 0 | float32 | big_endian | |
| pump_running | | coil | 0 | bool | | ✅ |
| alarm_di | | discrete_input | 0 | bool | | |

---

## 2) SIM_OPC_TANK（OPC-UA 服务端）

设备字段：
| 字段 | 值 |
|---|---|
| name | `SIM_OPC_TANK` |
| protocol | `opc_ua` |
| opc_endpoint | `opc.tcp://127.0.0.1:4840` |
| opc_namespace | `2` |
| opc_security_mode | `None` |
| poll_interval | `5` |

点位（opc_node_id / opc_node_type）：
| 点位名 | 单位 | opc_node_id | opc_node_type | writable |
|---|---|---|---|---|
| tank_level | % | ns=2;s=TankLevel | float64 | |
| tank_temp | °C | ns=2;s=TankTemp | float64 | |
| pump_status | | ns=2;s=PumpStatus | bool | |
| valve_setpoint | % | ns=2;s=ValveSetpoint | float64 | ✅ |

---

## 3) SIM_MQTT_SENSOR（MQTT 设备，自连内置 broker）

设备字段：
| 字段 | 值 |
|---|---|
| name | `SIM_MQTT_SENSOR` |
| protocol | `mqtt` |
| mqtt_broker | `127.0.0.1` |
| mqtt_port | `1883` |
| mqtt_topic_prefix | `sim` |
| mqtt_payload_format | `json` |
| poll_interval | `5` |

点位（mqtt_json_path / mqtt_value_type；订阅/发布主题均为 `sim/<点位名>`）：
| 点位名 | 单位 | mqtt_json_path | mqtt_value_type | writable |
|---|---|---|---|---|
| humidity | % | value | float64 | |
| co2 | ppm | value | float64 | |
| online | | value | bool | |
| target_temp | °C | value | float64 | ✅ |

> MQTT 设备发布的 JSON 形如 `{"value": 55.3, "quality": "good", "timestamp": 1700000000000}`，
> 平台用 `mqtt_json_path = value` 解析。平台写命令会发到 `sim/<点位名>/set`（`{"value": x}`），
> 模拟器收到后回写，下一帧遥测即反映新值（即回读验证）。

---

## 验证要点（全面自测）
- 实时采集 & 入库：三协议同时出数，平台 `tag_history` / `tag_aggregate` 落点。
- WebSocket 实时推送：改值后前端/WS 即时刷新。
- 报警：运行 `python simulator/scenario_ctl.py fault SIM_MODBUS_PLC temperature spike` 越限触发阈值报警；
  运行 `stop SIM_MQTT_SENSOR` 触发离线报警。
- 写值 + 回读：在平台对可写点位写值，观察回读是否同步。
- 数据转发：平台配置 MQTT 转发规则，内置 broker 应能收到 `data/<设备名>` 类消息。
