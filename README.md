# Modbus 数据采集平台

通用工业设备数据采集、监控、报警预警及短信推送平台。支持 **Modbus TCP / MQTT / OPC-UA** 三种协议。

## 功能特性

### 1. 多协议数据采集

#### Modbus TCP
- **功能码**: Coil (FC01/05/15), Discrete Input (FC02), Input Register (FC04), Holding Register (FC03/06/16)
- **数据类型**: BOOL, INT16, UINT16, INT32, UINT32, FLOAT32, FLOAT64, STRING, BCD
- **字节序**: Big Endian, Little Endian, Big Endian Swap, Little Endian Swap
- 自动合并连续地址批量读取，减少通信次数

#### MQTT
- 订阅设备 Topic，接收实时数据
- 支持 JSON payload 解析（dot-notation 路径提取）
- 支持纯数值、字符串等多种 payload 格式
- **数据发布**: 将采集到的数据聚合后发布到指定 Topic
- TLS/SSL 加密连接
- 可配置 QoS 等级 (0/1/2)
- 每个 Tag 可配置独立的订阅/发布 Topic

#### OPC-UA
- 连接 OPC-UA 服务器，支持匿名/用户名密码认证
- 安全模式: None / Basic256 / Basic256Sha256
- 通过 Node ID 配置数据点（ns=2;s=Temperature 或 i=1001）
- 支持读写操作
- 命名空间可配置

### 2. 设备管理平台
- 设备 CRUD，支持分组和标签管理
- 按协议类型过滤设备
- 采集点位 (Tag) 配置：地址/Topic/NodeID、数据类型、缩放系数、单位
- 采集频率可按设备独立配置
- 实时数据展示
- 历史数据存储与时序查询（支持原始/1m/5m/15m/1h/1d 聚合）
- CSV 数据导出

### 3. 报警预警系统
- **报警类型**: 上限报警、下限报警、区间报警、变化率报警、状态报警、设备离线报警
- **报警等级**: 提示 / 警告 / 严重 / 紧急
- **报警延迟**: 持续 N 秒后才触发，防误报
- **死区设置**: 防止阈值附近抖动
- **处理流程**: 活跃 → 确认 → 消除
- 报警历史记录与统计
- 仪表盘实时展示

### 4. 短信推送
- **多供应商**: 阿里云短信、腾讯云短信、自建 HTTP 短信网关
- **推送规则**: 按设备、报警等级、时间段过滤
- **冷却机制**: 同一规则 N 分钟内不重复发送
- 完整发送记录 + 测试功能

### 5. 远程控制
- **Modbus**: Coil 写入（启停控制）、Holding Register 写入（数值设定）
- **MQTT**: 向 Tag 发布 Topic 发送控制指令
- **OPC-UA**: 向可写 Node 写入值
- 操作二次确认机制

## 技术栈

| 组件 | 技术 |
|------|------|
| 前端 | Vue 3 + Element Plus + ECharts |
| 后端 | Python FastAPI + SQLAlchemy |
| Modbus | pymodbus 3.x |
| MQTT | paho-mqtt 1.6 |
| OPC-UA | asyncua 0.40 |
| 数据库 | MySQL 8.0 + Redis |
| 短信 | 阿里云/腾讯云/自建网关 |

## 快速开始

### 方式一：本地运行

```bash
# 1. 准备 MySQL 数据库
mysql -u root -p -e "CREATE DATABASE modbus_platform CHARACTER SET utf8mb4;"

# 2. 启动后端
cd backend
cp .env.example .env  # 编辑配置
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. 启动前端
cd frontend
npm install
npm run dev
```

### 方式二：Docker Compose

```bash
cd docker
docker-compose up -d
```

### 方式三：一键脚本

```bash
chmod +x scripts/*.sh
./scripts/start.sh
```

## 访问地址

- **前端**: http://localhost:3000
- **后端 API**: http://localhost:8000
- **API 文档 (Swagger)**: http://localhost:8000/docs
- **默认账号**: admin / admin123

## MQTT 配置示例

### 订阅设备数据

设备配置:
- Broker: `192.168.1.100:1883`
- Topic 前缀: `factory/line1/machine1`

Tag 配置:
- 名称: `temperature`
- 订阅 Topic: `factory/line1/machine1/temperature`（可留空，自动拼接前缀）
- JSON 路径: `sensors.temp`（从 `{"sensors": {"temp": 25.5}}` 提取 25.5）
- 值类型: `float64`

### 发布采集数据

设备配置:
- 启用发布: `true`
- 发布 Topic: `platform/data/machine1`
- QoS: `1`
- 发布周期: `5s`

发布格式:
```json
{
  "device_id": 1,
  "device_name": "machine1",
  "timestamp": "2026-07-17T15:30:00Z",
  "values": {
    "temperature": 25.5,
    "pressure": 101.3,
    "status": 1
  }
}
```

## OPC-UA 配置示例

设备配置:
- Endpoint: `opc.tcp://192.168.1.100:4840`
- 安全模式: `None`
- 命名空间: `2`

Tag 配置:
- Node ID: `ns=2;s=Temperature` 或 `ns=2;i=1001`
- 值类型: `float64`

## 短信配置

### 阿里云短信
```env
SMS_PROVIDER=aliyun
ALIYUN_SMS_ACCESS_KEY=your_key
ALIYUN_SMS_ACCESS_SECRET=your_secret
ALIYUN_SMS_SIGN_NAME=your_sign
ALIYUN_SMS_TEMPLATE_CODE=SMS_123456
```

### 腾讯云短信
```env
SMS_PROVIDER=tencent
TENCENT_SMS_SECRET_ID=your_id
TENCENT_SMS_SECRET_KEY=your_secret
TENCENT_SMS_APP_ID=your_app_id
TENCENT_SMS_SIGN_NAME=your_sign
TENCENT_SMS_TEMPLATE_ID=your_template_id
```

### 自建短信网关
```env
SMS_PROVIDER=custom
CUSTOM_SMS_URL=https://your-sms-gateway.com/api/send
CUSTOM_SMS_METHOD=POST
CUSTOM_SMS_HEADERS={"Authorization": "Bearer token"}
```

## 项目结构

```
modbus-platform/
├── backend/
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 配置、数据库、依赖
│   │   ├── engine/         # 协议引擎
│   │   │   ├── modbus_engine.py    # Modbus TCP 引擎
│   │   │   ├── mqtt_engine.py      # MQTT 引擎
│   │   │   ├── opcua_engine.py     # OPC-UA 引擎
│   │   │   └── protocol_router.py  # 协议路由器
│   │   ├── models/         # 数据模型
│   │   ├── schemas/        # Pydantic 模式
│   │   ├── services/       # 报警 + 短信服务
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── dashboard/  # 仪表盘
│   │   │   ├── devices/    # 设备管理 + 详情
│   │   │   ├── tags/       # 采集点位
│   │   │   ├── alarms/     # 报警管理
│   │   │   ├── control/    # 远程控制
│   │   │   ├── history/    # 历史数据
│   │   │   └── sms/        # 短信管理
│   │   └── ...
├── docker/
├── scripts/
└── README.md
```

## API 接口

| 模块 | 路径 | 说明 |
|------|------|------|
| 认证 | POST /api/v1/auth/login | 登录 |
| 设备 | GET/POST /api/v1/devices | 设备 CRUD（支持 ?protocol=mqtt 过滤） |
| 写入 | POST /api/v1/devices/{id}/write | 远程写入（自动路由到正确协议） |
| 实时 | GET /api/v1/devices/{id}/live | 实时数据 |
| 历史 | GET /api/v1/history | 历史查询 |
| 报警 | GET/POST /api/v1/alarms/rules | 报警规则 |
| 短信 | GET/POST /api/v1/sms/contacts | 联系人管理 |
| 仪表盘 | GET /api/v1/dashboard/summary | 汇总统计 |

完整 API 文档: http://localhost:8000/docs

## License

MIT
