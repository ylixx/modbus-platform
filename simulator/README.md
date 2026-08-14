# 协议模拟器（Modbus-TCP / OPC-UA / MQTT）

独立工具，模拟三类协议的服务端 + 内置拟真数据，用于**全面测试平台**的采集、入库、
WebSocket 推送、报警、写值回读、数据转发等功能。平台作为客户端去连本模拟器。

## 运行环境
- 复用后端虚拟环境 `backend/.venv`（已含 pymodbus / asyncua / paho-mqtt）。
- 仅需额外安装：`pip install amqtt`（Windows 免 docker 内置 MQTT broker）。

```bash
cd simulator
../backend/.venv/Scripts/python.exe -m pip install amqtt PyYAML
../backend/.venv/Scripts/python.exe run_simulator.py
```

## 一键启动（默认启动全部 3 类协议设备）
```bash
python run_simulator.py
python run_simulator.py --only SIM_MODBUS_PLC     # 只起某一台
```

## 把设备导入平台（二选一）
1. **自动**：`python seed/seed_platform.py`（默认 admin/admin123，连本机 8000）。
2. **手动**：照 `seed/PLATFORM_IMPORT.md` 的字段逐台添加设备/点位。

## 场景控制（另开终端）
```bash
python scenario_ctl.py fault SIM_MODBUS_PLC temperature spike     # 越限/故障注入
python scenario_ctl.py set   SIM_MQTT_SENSOR target_temp 25      # 强制置值
python scenario_ctl.py stop  SIM_MQTT_SENSOR                    # 模拟离线
python scenario_ctl.py start SIM_MQTT_SENSOR
python scenario_ctl.py clear SIM_MODBUS_PLC temperature
```

## 目录结构
```
simulator/
├── run_simulator.py          # 一键启动入口
├── scenarios.yaml            # 模拟设备 + 点位 + 生成器定义（数据驱动）
├── config.py / modbus_codec_local.py
├── generators/signals.py     # 正弦/随机游走/方波/常量/斜坡 + 故障注入
├── servers/                  # modbus_slave / opcua_server / mqtt_broker / mqtt_device
├── seed/seed_platform.py     # 自动导入平台
├── seed/PLATFORM_IMPORT.md   # 手动导入字段清单
└── scenario_ctl.py           # 场景控制 CLI
```

> 你可用专业 Modbus/OPC-UA/MQTT 客户端连本模拟器，对比平台采集与发布结果。
