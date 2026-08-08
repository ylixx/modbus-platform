# Modbus 数据采集平台

通用工业设备数据采集、监控、报警预警及短信推送平台。支持 Modbus TCP / MQTT / OPC-UA 三种协议。

---

## 目录

- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [快速部署](#快速部署)
- [功能详解](#功能详解)
- [API 接口文档](#api-接口文档)
- [配置说明](#配置说明)
- [架构说明](#架构说明)
- [常见问题](#常见问题)
- [最近修复](#最近修复)

---

## 最近修复

`master` 分支已落地一批安全与稳定性修复（完整清单见 [FIX_PROGRESS.md](./FIX_PROGRESS.md)）：

- **后端 API 全量接入 RBAC**：`device/tag/group/alarm/sms/history/export/audit` 及新增的 `config/scada/script/import/hierarchy/template/dashboard` 共约 50 个端点已用 `require_permission("模块.read|write")` 守卫；权限码在 `app/services/seed_permissions.py` 中播种并分配给 admin/engineer/operator/viewer。
- **脚本沙箱加固**：移除 `SAFE_BUILTINS` 中的 `type`，新增 AST 校验拦截 dunder 属性访问与危险调用（`().__class__.__subclasses__()` 等逃逸路径已封），缓存键改用 `hashlib.sha256`。
- **modbus_codec 小端解码修复**：`decode_32bit/decode_float32/decode_float64` 的 `LITTLE_ENDIAN` 分支字节序写反（pre-existing bug），已修正并补回归测试。
- **WebSocket 实时推送链路接通**：轮询/报警事件现经主事件循环正确广播。
- **其他**：默认 `SECRET_KEY` 启动告警 + `DISABLE_DEFAULT_ADMIN` 开关；CORS 改为白名单；`reset_password` 清除默认弱口令；限流字典内存泄漏修复；`datetime.utcnow()` 全量替换为 `datetime.now(timezone.utc)`。

> ⚠️ 生产部署请务必在 `.env` 中将 `SECRET_KEY` 改为强随机值，并配置真实数据库（MySQL）与 Redis（多 worker 时）。

---

## 功能特性

### 多协议数据采集

| 协议 | 能力 |
|------|------|
| **Modbus TCP** | FC01-16 全功能码；9 种数据类型（BOOL/INT16/UINT16/INT32/UINT32/FLOAT32/FLOAT64/STRING/BCD）；4 种字节序；自动合并连续地址批量读取；Coil + Holding Register 写入 |
| **MQTT** | 订阅采集 + 数据发布；标准 JSON / ThingsBoard 遥测格式 / 网关模式；JSON dot-path 提取；TLS 加密；QoS 0/1/2；Retain |
| **OPC-UA** | 匿名/用户名密码/证书认证；Node ID 配置；轮询读取 + 写入；安全模式 None/Basic256/Basic256Sha256 |

### 设备管理

- 设备 CRUD，支持分组、标签管理
- 位置信息：厂级、区级、班级、安装位置、经纬度 GPS
- 自定义拓扑层级：用户可配置树形结构（如 厂级→区级→班级→设备 或 区域→楼栋→楼层→设备），多方案切换
- 采集点位（Tag）配置：地址/Topic/NodeID、数据类型、字节序、缩放系数、偏移、单位、可写标记
- 采集频率按设备独立配置
- 设备状态：在线/离线/异常/维护，自动检测
- 从模板快速创建设备（7 个预定义模板）
- CSV 批量导入设备和点位

### 脚本算法

- 自定义数据处理脚本（Python 语法）
- 脚本沙箱：限制 import，禁止 os/sys/io，超时强制终止
- 8 个预设模板：线性标定、滑动平均、中值滤波、变化率、累计器、死区滤波、量程映射、阈值报警
- 脚本测试运行：输入原始值查看输出
- 一个脚本可绑定多个点位

### SCADA 画面

- 原生 SVG 画布编辑器（FUXA 风格），拖拽放置工业组件
- 20+ 内置组件：储罐/立式罐/球阀/蝶阀/电机/离心泵/管道/表盘/温度计/进度条/指示灯/报警灯/按钮/开关
- 自定义图元上传（SVG/PNG），批量上传
- 数据绑定：Tag → 组件属性实时刷新
- 运行时查看器，WebSocket 实时更新
- 全屏展示模式

### 实时数据

- 所有设备 Tag 扁平表格，WebSocket 实时刷新
- 6 个筛选器：设备/厂级/区级/协议/状态/搜索
- 值着色：正常(绿)/过期(黄)/异常(红)
- 30 秒过期检测
- CSV/JSON 导出

### 报警预警

- 6 种报警类型：上限、下限、区间、变化率、状态、设备离线
- 4 级报警等级：提示 / 警告 / 严重 / 紧急
- 报警延迟（持续 N 秒后触发，防误报）
- 死区设置（防阈值附近抖动）
- 处理流程：活跃 → 确认 → 消除
- 告警升级：未确认自动升级等级（info→warning→critical→emergency）
- 报警统计：按等级/设备分布，趋势柱状图

### 通知推送

- **短信**：阿里云 / 腾讯云 / 自建 HTTP 网关
- **钉钉**：Webhook 机器人
- **企业微信**：Webhook 机器人
- **邮件**：SMTP
- 推送规则：按设备、报警等级、时间段过滤
- 冷却机制：同一规则 N 分钟内不重复发送
- 报警触发时自动推送到所有已配置通道

### 远程控制

- Coil 写入（启停控制）
- Holding Register 写入（数值设定）
- MQTT Topic 发布
- OPC-UA Node 写入
- 操作二次确认（弹窗 + 确认码）

### 权限管理（RBAC）

- 权限点：覆盖 device / tag / group / alarm / sms / history / export / audit / config / scada / script / import / hierarchy / template / dashboard / system 等模块（API 层已全部接入 `require_permission` 校验）
- 4 个预置角色：admin / engineer / operator / viewer
- 数据范围：全部 / 指定厂级 / 指定区级 / 仅自己
- 动态菜单：按权限过滤侧边栏
- 按钮级权限守卫

### 其他

- 操作审计日志（全量记录，WebSocket 实时推送）
- 数据导出（历史/报警/设备清单 CSV，每日汇总 JSON）
- 数据归档策略（用户可配置保留天数，定时自动清理）
- 历史数据查询（原始/1m/5m/15m/1h/1d 多粒度聚合）
- ECharts 趋势图表
- 数据大屏（深色全屏，实时数据流）

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Element Plus + ECharts 5 + SVG 画布（frontend-v2） |
| 后端 | Python FastAPI + SQLAlchemy |
| Modbus | pymodbus 3.7 |
| MQTT | paho-mqtt 1.6 |
| OPC-UA | asyncua 0.40 |
| 数据库 | SQLite（开发/演示）/ MySQL 8.0（生产）+ Redis（多 worker 广播） |
| 认证 | JWT (python-jose) |
| 短信 | 阿里云/腾讯云/自建网关 |
| 部署 | Docker Compose / 本地 |

---

## 快速部署

### 方式零：极简启动（SQLite，推荐首次试用）

无需安装 MySQL / Redis，开箱即跑（开发/演示用）。本仓库自带的 `backend/.env` 已指向本地 SQLite。

#### 1. 环境要求

- Python 3.10+
- Node.js 18+

#### 2. 后端

```bash
cd modbus-platform/backend

# 安装依赖（首次）
pip install -r requirements.txt
# 注意：若安装后运行 init_db.py 报
#   "ValueError: password cannot be longer than 72 bytes"
# 说明 passlib 与新版 bcrypt 不兼容，请锁定：
pip install "bcrypt==4.0.1"

# 初始化数据库（建表 + admin + 权限 + 示例数据）
# 默认 .env 的 DATABASE_URL 已是 sqlite:///./modbus_platform.db
python ../scripts/init_db.py

# 启动后端（开发模式热重载）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> 未配置 Redis 时，WebSocket 自动降级为单进程内广播（单 worker 正常），多 worker 才需要 Redis。

#### 3. 前端（V2）

```bash
cd modbus-platform/frontend-v2

pnpm install   # 首次
pnpm dev       # Vite 默认 http://localhost:3000
```

#### 4. 访问

- 前端界面：http://localhost:3000
- API 文档（Swagger）：http://localhost:8000/docs
- 默认账号：**admin / admin123**
- 登录接口：`POST /api/v1/auth/login`

> 所有 API 均需 `Authorization: Bearer <token>`，未带令牌返回 403（FastAPI 默认行为）。

---

### 方式一：本地部署（MySQL + Redis，生产向）

#### 1. 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Redis 7+（可选，多 worker 时需要）

#### 2. 创建数据库

```sql
CREATE DATABASE modbus_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

#### 3. 后端

```bash
cd modbus-platform/backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填写数据库连接信息

# 初始化数据库
python ../scripts/init_db.py

# 启动后端
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 4. 前端（V2）

```bash
cd modbus-platform/frontend-v2

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```

#### 5. 访问

- 前端：http://localhost:3000
- API 文档：http://localhost:8000/docs
- 默认账号：admin / admin123

### 方式二：Docker Compose

```bash
cd modbus-platform/docker
docker-compose up -d
```

### 方式三：一键脚本

```bash
chmod +x scripts/*.sh
./scripts/start.sh
```

### 数据库初始化脚本

```bash
cd modbus-platform/backend

# 首次部署（建表 + admin + 权限 + 示例数据）
python ../scripts/init_db.py

# 重置数据库（删表重建）
python ../scripts/init_db.py --reset

# 仅播种数据（表已存在）
python ../scripts/init_db.py --seed-only

# 正式部署（跳过示例数据）
python ../scripts/init_db.py --no-sample
```

初始化后的默认数据：

| 数据 | 内容 |
|------|------|
| 管理员 | admin / admin123 |
| 角色 | admin(全部) / engineer(配置+管理) / operator(操作) / viewer(只读) |
| 权限点 | 约 35 个，覆盖全部功能模块（含 config/scada/script/import/hierarchy/template/dashboard） |
| 示例设备 | 1 台温湿度传感器（禁用状态） |

---

## 功能详解

### 设备管理

#### 添加设备

1. 进入「设备管理」→ 点击「新增设备」
2. 选择通信协议（Modbus TCP / MQTT / OPC-UA）
3. 填写连接信息
4. 填写位置信息（厂级/区级/班级/安装位置）
5. 点击保存，设备自动开始采集

#### 从模板创建

1. 进入「设备模板」
2. 选择模板（如「西门子 S7-1200」）
3. 填写设备名称和连接信息
4. 点击「创建设备」，自动生成全部采集点位

#### 批量导入

1. 进入「批量导入」
2. 下载 CSV 模板
3. 按模板格式填写数据
4. 上传 CSV 文件

#### 采集点位配置

每个设备可添加多个采集点位（Tag），配置项：

| 字段 | 说明 |
|------|------|
| 名称 | 点位名称，如「温度」 |
| 功能码 | Modbus: Coil/Discrete Input/Input Register/Holding Register |
| 地址 | Modbus 寄存器地址 |
| 数据类型 | BOOL/INT16/UINT16/INT32/UINT32/FLOAT32/FLOAT64/STRING/BCD |
| 字节序 | Big/Little Endian + Swap |
| 缩放系数 | 原始值 × 系数 |
| 偏移量 | 原始值 + 偏移 |
| 单位 | 如 °C、%、MPa |
| 可写 | 是否支持远程写入 |
| 脚本 | 绑定数据处理脚本 |

### 脚本算法

#### 创建脚本

1. 进入「脚本算法」→ 点击「新建」或从模板导入
2. 编写 Python 脚本，定义 `process` 函数：

```python
def process(raw_value, history, tag, context):
    """
    参数:
        raw_value — 原始采集值（已缩放偏移）
        history   — 最近 N 个处理后的值列表
        tag       — {name, unit, scale_factor, offset, params}
        context   — {device_id, tag_id, timestamp}
    
    返回:
        float — 处理后的值
        dict  — {value, quality, alarm}
    """
    # 线性标定
    a = tag['params'].get('a', 1.0)
    b = tag['params'].get('b', 0.0)
    return raw_value * a + b
```

3. 点击「测试运行」验证
4. 保存后，在设备详情的 Tag 编辑中绑定脚本

#### 预设模板

| 模板 | 用途 | 代码示例 |
|------|------|---------|
| 线性标定 | y = raw × a + b | `return raw_value * a + b` |
| 滑动平均 | 消除波动 | `return sum(values) / len(values)` |
| 滑动中值 | 消除尖峰 | `return sorted(values)[len(values)//2]` |
| 变化率 | 每秒变化量 | `return raw_value - history[-1]` |
| 累计器 | 流量累计 | `return history[-1] + raw_value` |
| 死区滤波 | 小变化忽略 | `if abs(raw - last) < deadband: return last` |
| 量程映射 | 4-20mA → 0-100% | `(raw - in_min) * (out_max - out_min) / (in_max - in_min) + out_min` |
| 阈值报警 | 超限返回报警 | `return {'value': raw, 'quality': 'bad', 'alarm': '过高'}` |

### SCADA 画面

#### 创建画面

1. 进入「SCADA 画面」→ 点击「新建画面」
2. 进入编辑器
3. 从左侧面板拖拽组件到画布
4. 点击组件 → 右侧绑定设备点位
5. 保存 → 点击「运行」查看实时效果

#### 自定义图元

1. 进入「SCADA 画面」→ 点击「自定义图元」
2. 上传 SVG 或 PNG 文件
3. 设置名称和分类
4. 在编辑器的「自定义」分类中使用

### 报警管理

#### 创建报警规则

1. 进入「报警管理」→「报警规则」→ 点击「新增规则」
2. 选择设备和关联点位
3. 选择报警类型和等级
4. 设置阈值参数
5. 配置是否发送短信/通知

#### 报警处理流程

```
报警触发 → 活跃状态 → 确认 → 消除
                    ↓
              超时未确认 → 自动升级等级
                    ↓
              发送通知（短信/钉钉/微信/邮件）
```

### 短信/通知配置

#### 短信

在 `.env` 中配置：

```env
# 阿里云短信
SMS_PROVIDER=aliyun
ALIYUN_SMS_ACCESS_KEY=***
ALIYUN_SMS_ACCESS_SECRET=***
ALIYUN_SMS_SIGN_NAME=your_sign
ALIYUN_SMS_TEMPLATE_CODE=SMS_123456

# 腾讯云短信
SMS_PROVIDER=tencent
TENCENT_SMS_SECRET_ID=your_id
TENCENT_SMS_SECRET_KEY=***

# 自建网关
SMS_PROVIDER=custom
CUSTOM_SMS_URL=https://your-sms-gateway.com/api/send
```

#### 钉钉

```env
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=***
```

#### 企业微信

```env
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=***
```

#### 邮件

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=alert@example.com
SMTP_PASSWORD=***
ALARM_EMAIL_TO=admin@example.com
```

### 数据归档

1. 进入「数据归档」
2. 配置保留天数：
   - 原始数据：默认 7 天
   - 报警记录：默认 365 天
   - 短信记录：默认 90 天
   - 审计日志：默认 365 天
3. 开启/关闭自动归档（每天凌晨 3:00 执行）
4. 可手动点击「立即执行归档」

### 权限管理

#### 角色说明

| 角色 | 权限范围 | 数据范围 |
|------|---------|---------|
| admin | 全部 21 个权限 | 全部数据 |
| engineer | 设备配置 + 报警管理 + 数据查看 | 可限定厂级/区级 |
| operator | 设备查看 + 报警确认 + 远程控制 | 可限定厂级/区级 |
| viewer | 只读：设备/报警/历史 | 可限定厂级/区级 |

#### 数据范围

分配角色时可绑定数据范围：

| 范围 | 说明 |
|------|------|
| 全部 | 看所有设备 |
| 指定厂级 | 只看指定厂级的设备 |
| 指定区级 | 只看指定区级的设备 |
| 仅自己 | 只看自己创建的设备 |

### 配置导出/迁移

#### 导出

进入「系统」→「配置导出」→ 点击「导出配置」

导出的 JSON 文件包含：
- 设备分组、设备、采集点位
- 报警规则、脚本
- 短信联系人、推送规则
- 层级配置、SCADA 画面、自定义图元

#### 导入

1. 在目标环境进入「配置导出」
2. 上传导出的 JSON 文件
3. 选择是否覆盖同名数据

---

## API 接口文档

### 认证

所有 API 需要 Bearer Token 认证。

```
POST /api/v1/auth/login
Body: {"username": "admin", "password": "admin123"}
Response: {"access_token": "***", "token_type": "bearer", "user": {...}}
```

请求头：`Authorization: Bearer <token>`

### 设备管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/devices` | 设备列表（支持分页/筛选） |
| GET | `/api/v1/devices/all` | 全部设备（不分页） |
| GET | `/api/v1/devices/{id}` | 设备详情（含 Tags） |
| POST | `/api/v1/devices` | 创建设备 |
| PUT | `/api/v1/devices/{id}` | 更新设备 |
| DELETE | `/api/v1/devices/{id}` | 删除设备 |
| GET | `/api/v1/devices/groups` | 设备分组列表 |
| POST | `/api/v1/devices/groups` | 创建分组 |
| GET | `/api/v1/devices/locations` | 获取厂级/区级/班级列表 |
| GET | `/api/v1/devices/{id}/tags` | 设备点位列表 |
| POST | `/api/v1/devices/tags` | 创建点位 |
| PUT | `/api/v1/devices/tags/{id}` | 更新点位 |
| POST | `/api/v1/devices/{id}/write` | 远程写入 |
| GET | `/api/v1/devices/{id}/live` | 实时数据 |

### 报警管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/alarms/rules` | 报警规则列表 |
| POST | `/api/v1/alarms/rules` | 创建规则 |
| PUT | `/api/v1/alarms/rules/{id}` | 更新规则 |
| DELETE | `/api/v1/alarms/rules/{id}` | 删除规则 |
| GET | `/api/v1/alarms/records` | 报警记录列表 |
| GET | `/api/v1/alarms/records/active` | 活跃报警 |
| POST | `/api/v1/alarms/records/{id}/acknowledge` | 确认报警 |
| POST | `/api/v1/alarms/records/{id}/clear` | 消除报警 |
| GET | `/api/v1/alarms/stats` | 报警统计 |

### 短信管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/sms/contacts` | 联系人列表 |
| POST | `/api/v1/sms/contacts` | 创建联系人 |
| GET | `/api/v1/sms/rules` | 推送规则列表 |
| POST | `/api/v1/sms/rules` | 创建规则 |
| GET | `/api/v1/sms/records` | 发送记录 |
| POST | `/api/v1/sms/test` | 测试发送 |

### 历史数据

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/history` | 查询历史（支持聚合） |
| GET | `/api/v1/history/latest` | 最新值 |

查询参数：
- `device_id`: 设备 ID
- `tag_id`: 点位 ID
- `start_time`: 开始时间
- `end_time`: 结束时间
- `interval`: 聚合粒度（raw/1m/5m/15m/1h/1d）

### 脚本算法

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/scripts` | 脚本列表 |
| POST | `/api/v1/scripts` | 创建脚本 |
| PUT | `/api/v1/scripts/{id}` | 更新脚本 |
| DELETE | `/api/v1/scripts/{id}` | 删除脚本 |
| POST | `/api/v1/scripts/test` | 测试运行 |
| POST | `/api/v1/scripts/assign` | 绑定到点位 |
| GET | `/api/v1/scripts/templates/all` | 预设模板 |

### SCADA 画面

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/scada/pages` | 画面列表 |
| POST | `/api/v1/scada/pages` | 创建画面 |
| PUT | `/api/v1/scada/pages/{id}` | 更新画面 |
| DELETE | `/api/v1/scada/pages/{id}` | 删除画面 |
| GET | `/api/v1/scada/widgets` | 自定义图元列表 |
| POST | `/api/v1/scada/widgets/upload` | 上传图元 |

### 权限管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/rbac/roles` | 角色列表 |
| POST | `/api/v1/rbac/roles` | 创建角色 |
| GET | `/api/v1/rbac/permissions` | 权限点列表 |
| POST | `/api/v1/rbac/users/{id}/roles` | 分配角色 |
| GET | `/api/v1/rbac/me/permissions` | 当前用户权限 |

### 数据归档

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/archive/stats` | 数据量统计 |
| GET | `/api/v1/archive/config` | 归档配置 |
| PUT | `/api/v1/archive/config` | 更新配置 |
| POST | `/api/v1/archive/run` | 手动执行归档 |

### 配置导出

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/config/export` | 导出配置 |
| POST | `/api/v1/config/import` | 导入配置 |

### 批量导入

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/import/devices` | 导入设备 |
| POST | `/api/v1/import/tags` | 导入点位 |
| GET | `/api/v1/import/template/devices` | 下载设备模板 |
| GET | `/api/v1/import/template/tags` | 下载点位模板 |

### 设备模板

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/templates/devices` | 模板列表 |
| POST | `/api/v1/templates/devices/{id}/create` | 从模板创建 |

### WebSocket

```
ws://host/ws?token=<jwt>
```

推送事件类型：
- `live_value`: 实时数据更新
- `alarm_triggered`: 报警触发
- `alarm_acknowledged`: 报警确认
- `alarm_cleared`: 报警消除
- `device_status`: 设备状态变更
- `operation_log`: 操作审计

### 仪表盘

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/dashboard/summary` | 汇总统计 |
| GET | `/api/v1/dashboard/device-status` | 设备状态分布 |
| GET | `/api/v1/dashboard/alarm-trend` | 报警趋势 |

### 数据导出

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/export/history/csv` | 历史数据 CSV |
| GET | `/api/v1/export/alarms/csv` | 报警记录 CSV |
| GET | `/api/v1/export/devices/csv` | 设备清单 CSV |
| GET | `/api/v1/export/report/daily` | 每日汇总 JSON |

### 操作审计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/audit/logs` | 审计日志 |

### 层级配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/hierarchy/configs` | 层级方案列表 |
| POST | `/api/v1/hierarchy/configs` | 创建方案 |
| GET | `/api/v1/hierarchy/tree` | 获取拓扑树 |
| GET | `/api/v1/hierarchy/fields` | 可用字段列表 |

### 用户管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/users` | 用户列表 |
| POST | `/api/v1/users` | 创建用户 |
| PUT | `/api/v1/users/{id}` | 更新用户 |
| DELETE | `/api/v1/users/{id}` | 删除用户 |

---

## 配置说明

### 环境变量 (.env)

```bash
# ── 数据库 ──
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=***
DB_NAME=modbus_platform

# ── Redis（可选，多worker时需要）──
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# ── 安全 ──
SECRET_KEY=change-me-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=480

# ── Modbus ──
MODBUS_POLL_INTERVAL=5.0
MODBUS_TIMEOUT=3.0
MODBUS_RETRIES=3

# ── 短信 ──
SMS_PROVIDER=aliyun  # aliyun | tencent | custom

# ── 钉钉 ──
DINGTALK_WEBHOOK_URL=

# ── 企业微信 ──
WECHAT_WEBHOOK_URL=

# ── 邮件 ──
SMTP_HOST=
SMTP_PORT=465
SMTP_USER=
SMTP_PASSWORD=
ALARM_EMAIL_TO=

# ── 报警 ──
ALARM_CHECK_INTERVAL=2.0
MAX_SMS_PER_HOUR=50
```

### 多 Worker 部署

```bash
# 启动多个 worker
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 需要 Redis 支持 WebSocket 跨进程广播
# 配置 REDIS_HOST 等环境变量
```

---

## 架构说明

### 项目结构

```
modbus-platform/
├── backend/
│   ├── app/
│   │   ├── api/                # API 路由（18 个模块）
│   │   ├── core/               # 配置/数据库/认证/异常/限流
│   │   ├── engine/             # 协议引擎
│   │   │   ├── modbus_engine.py    # Modbus TCP 轮询
│   │   │   ├── modbus_codec.py     # Modbus 编解码
│   │   │   ├── mqtt_engine.py      # MQTT 编排器
│   │   │   ├── mqtt_session.py     # MQTT 标准会话
│   │   │   ├── mqtt_gateway.py     # MQTT ThingsBoard 网关
│   │   │   ├── mqtt_utils.py       # MQTT 工具函数
│   │   │   ├── opcua_engine.py     # OPC-UA 引擎
│   │   │   ├── script_engine.py    # 脚本沙箱
│   │   │   ├── protocol_router.py  # 协议路由器
│   │   │   ├── websocket_manager.py# WebSocket 管理
│   │   │   └── ws_broadcast.py     # Redis 广播
│   │   ├── models/             # 数据模型
│   │   ├── schemas/            # Pydantic 模式
│   │   ├── services/           # 业务服务
│   │   └── main.py             # 应用入口
│   ├── tests/                  # 单元测试
│   ├── requirements.txt
│   └── .env.example
├── frontend-v2/
│   ├── src/
│   │   ├── api/                # HTTP 请求
│   │   ├── components/         # 公共组件
│   │   ├── composables/        # 组合函数
│   │   ├── layouts/            # 布局
│   │   ├── router/             # 路由
│   │   ├── stores/             # 状态管理
│   │   ├── utils/              # 工具函数
│   │   └── views/              # 页面（Device/Alarm/Monitor/Scada/Data/System 等模块）
├── scripts/                    # 启停脚本/初始化
├── docker/                     # Docker 配置
└── README.md
```

### 数据流程

```
设备 → 协议引擎 → 脚本处理 → 存储/报警/通知
                        ↓
                   WebSocket 推送 → 前端实时刷新
```

### 认证流程

```
登录 → 获取 JWT Token → 请求带 Bearer Token → 验证 → 权限检查 → 数据范围过滤
```

---

## 常见问题

### Q: 设备添加后不采集？

A: 检查：
1. 设备是否启用（enabled=true）
2. 连接信息是否正确（IP/端口/从站ID）
3. 网络是否可达
4. 查看后端日志：`logs/app_日期.log`

### Q: 数据大屏 WebSocket 断开？

A: WebSocket 自动重连（3 秒间隔）。如果持续断开：
1. 检查网络
2. 检查 Token 是否过期
3. 多 worker 部署需配置 Redis

### Q: 短信发送失败？

A: 检查：
1. `.env` 中短信配置是否正确
2. 短信模板是否已审核通过
3. 联系人手机号是否正确
4. 查看「短信管理」→「发送记录」中的错误信息

### Q: 如何备份？

A: 
```bash
# 导出配置（不含历史数据）
curl -H "Authorization: Bearer ***" http://localhost:8000/api/v1/config/export > backup.json

# 导出历史数据
curl -H "Authorization: Bearer ***" "http://localhost:8000/api/v1/export/history/csv?device_id=1" > history.csv

# 数据库备份
mysqldump -u root -p modbus_platform > backup.sql
```

### Q: 如何升级？

A:
```bash
# 1. 备份
# 2. 拉取新代码
git pull

# 3. 更新依赖
cd backend && pip install -r requirements.txt
cd ../frontend-v2 && pnpm install

# 4. 重启服务
# 5. 如有新表，运行 python ../scripts/init_db.py
```

### Q: 如何添加新的通知渠道？

A: 在 `backend/app/services/notification_service.py` 中添加新的 `_send_xxx` 方法，并在 `.env` 中添加配置项。
