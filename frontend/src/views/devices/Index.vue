<template>
  <div>
    <div class="page-header">
      <h2>设备管理</h2>
      <p>管理 Modbus TCP / MQTT / OPC-UA 设备</p>
    </div>

    <el-card style="margin-bottom: 16px">
      <el-row :gutter="16" align="middle">
        <el-col :span="5">
          <el-input v-model="search" placeholder="搜索设备名称/IP" clearable prefix-icon="Search" @clear="fetchDevices" @keyup.enter="fetchDevices" />
        </el-col>
        <el-col :span="3">
          <el-select v-model="filterFactory" placeholder="厂级" clearable @change="fetchDevices">
            <el-option v-for="f in locationOptions.factories" :key="f" :label="f" :value="f" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="filterWorkshop" placeholder="区级" clearable @change="fetchDevices">
            <el-option v-for="w in locationOptions.workshops" :key="w" :label="w" :value="w" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="filterGroup" placeholder="分组" clearable @change="fetchDevices">
            <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="filterProtocol" placeholder="协议" clearable @change="fetchDevices">
            <el-option label="Modbus TCP" value="modbus_tcp" />
            <el-option label="MQTT" value="mqtt" />
            <el-option label="OPC-UA" value="opc_ua" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="filterStatus" placeholder="状态" clearable @change="fetchDevices">
            <el-option label="在线" value="online" />
            <el-option label="离线" value="offline" />
            <el-option label="异常" value="error" />
          </el-select>
        </el-col>
        <el-col :span="4" style="text-align: right">
          <el-button type="primary" @click="showDialog()"><el-icon><Plus /></el-icon> 新增设备</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card>
      <el-table :data="devices" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="设备名称" width="150" />
        <el-table-column prop="protocol" label="协议" width="120">
          <template #default="{ row }">
            <el-tag :type="protoTagType(row.protocol)" size="small">{{ protoLabel(row.protocol) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="连接信息" width="260">
          <template #default="{ row }">
            <span v-if="row.protocol === 'modbus_tcp'">{{ row.host }}:{{ row.port }} (ID:{{ row.slave_id }})</span>
            <span v-else-if="row.protocol === 'mqtt'">{{ row.mqtt_broker }}:{{ row.mqtt_port }}<el-tag v-if="row.mqtt_payload_format==='thingsboard'" size="small" type="warning" style="margin-left:4px">TB</el-tag></span>
            <span v-else>{{ row.opc_endpoint }}</span>
          </template>
        </el-table-column>
        <el-table-column label="位置" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ [row.factory, row.workshop, row.production_line].filter(Boolean).join(' / ') || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <span class="status-dot" :class="row.status"></span>{{ statusLabel(row.status) }}
          </template>
        </el-table-column>
        <el-table-column prop="poll_interval" label="采集周期" width="100">
          <template #default="{ row }">{{ row.poll_interval }}s</template>
        </el-table-column>
        <el-table-column prop="enabled" label="启用" width="70">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_poll_at" label="最后采集" width="170">
          <template #default="{ row }">{{ formatTime(row.last_poll_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push(`/devices/${row.id}`)">详情</el-button>
            <el-button size="small" type="primary" @click="showDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @current-change="fetchDevices"
      />
    </el-card>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑设备' : '新增设备'" width="780px" top="3vh" destroy-on-close>
      <el-scrollbar max-height="75vh">
        <el-form :model="form" label-width="100px" style="padding-right: 20px">

          <!-- 基本信息 -->
          <el-divider content-position="left">基本信息</el-divider>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="设备名称" required>
                <el-input v-model="form.name" placeholder="请输入设备名称" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="通信协议" required>
                <el-select v-model="form.protocol" style="width:100%">
                  <el-option label="Modbus TCP" value="modbus_tcp" />
                  <el-option label="MQTT" value="mqtt" />
                  <el-option label="OPC-UA" value="opc_ua" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="设备分组">
                <el-select v-model="form.group_id" clearable style="width:100%">
                  <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="采集周期(秒)">
                <el-input-number v-model="form.poll_interval" :min="1" :max="3600" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="启用">
                <el-switch v-model="form.enabled" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="描述">
            <el-input v-model="form.description" type="textarea" :rows="2" placeholder="设备描述（选填）" />
          </el-form-item>

          <!-- 位置信息 -->
          <el-divider content-position="left">位置信息</el-divider>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="厂级"><el-input v-model="form.factory" placeholder="e.g. 一号厂级" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="区级"><el-input v-model="form.workshop" placeholder="e.g. A区级" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="班级"><el-input v-model="form.production_line" placeholder="e.g. 1号线" /></el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="安装位置"><el-input v-model="form.installation" placeholder="e.g. 3号机组东侧" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="经度"><el-input-number v-model="form.longitude" :step="0.0001" :precision="6" :controls="false" style="width:100%" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="纬度"><el-input-number v-model="form.latitude" :step="0.0001" :precision="6" :controls="false" style="width:100%" /></el-form-item>
            </el-col>
          </el-row>

          <!-- Modbus TCP -->
          <template v-if="form.protocol === 'modbus_tcp'">
            <el-divider content-position="left">Modbus TCP 连接</el-divider>
            <el-row :gutter="16">
              <el-col :span="10">
                <el-form-item label="主机地址" required><el-input v-model="form.host" placeholder="192.168.1.100" /></el-form-item>
              </el-col>
              <el-col :span="7">
                <el-form-item label="端口">
                  <el-input-number v-model="form.port" :min="1" :max="65535" :controls="false" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="7">
                <el-form-item label="从站ID">
                  <el-input-number v-model="form.slave_id" :min="1" :max="247" :controls="false" style="width:100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="超时(秒)">
                  <el-input-number v-model="form.timeout" :min="0.5" :max="30" :step="0.5" :controls="false" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="重试次数">
                  <el-input-number v-model="form.retries" :min="0" :max="10" :controls="false" style="width:100%" />
                </el-form-item>
              </el-col>
            </el-row>
          </template>

          <!-- MQTT -->
          <template v-if="form.protocol === 'mqtt'">
            <el-divider content-position="left">MQTT 连接</el-divider>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="Broker地址" required><el-input v-model="form.mqtt_broker" placeholder="192.168.1.100" /></el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="端口">
                  <el-input-number v-model="form.mqtt_port" :min="1" :max="65535" :controls="false" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="QoS">
                  <el-select v-model="form.mqtt_publish_qos" style="width:100%">
                    <el-option label="0 - 最多一次" :value="0" />
                    <el-option label="1 - 至少一次" :value="1" />
                    <el-option label="2 - 恰好一次" :value="2" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="用户名"><el-input v-model="form.mqtt_username" placeholder="选填" /></el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="密码"><el-input v-model="form.mqtt_password" type="password" show-password placeholder="选填" /></el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="Client ID"><el-input v-model="form.mqtt_client_id" placeholder="自动生成" /></el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="TLS 加密"><el-switch v-model="form.mqtt_use_tls" /></el-form-item>
              </el-col>
            </el-row>

            <el-divider content-position="left">Payload 格式</el-divider>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="数据格式">
                  <el-select v-model="form.mqtt_payload_format" style="width:100%">
                    <el-option label="标准 JSON" value="json" />
                    <el-option label="ThingsBoard 遥测" value="thingsboard" />
                    <el-option label="纯数值" value="plain" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12" v-if="form.mqtt_payload_format === 'thingsboard'">
                <el-form-item label="网关模式">
                  <el-switch v-model="form.mqtt_is_gateway" />
                  <span style="font-size:12px;color:#999;margin-left:8px">一个连接管理多个设备</span>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item :label="form.mqtt_payload_format === 'thingsboard' ? (form.mqtt_is_gateway ? '网关订阅Topic' : '设备Topic') : 'Topic前缀'">
              <el-input v-model="form.mqtt_topic_prefix"
                :placeholder="form.mqtt_payload_format === 'thingsboard' ? 'v1/gateway/telemetry' : 'e.g. factory/line1'" />
              <div v-if="form.mqtt_payload_format === 'thingsboard' && !form.mqtt_is_gateway" style="font-size:12px;color:#999;margin-top:4px">
                ThingsBoard 格式下，子设备通过 JSON 中的设备名键自动路由
              </div>
            </el-form-item>

            <el-divider content-position="left">数据发布 (可选)</el-divider>
            <el-row :gutter="16">
              <el-col :span="6">
                <el-form-item label="启用发布"><el-switch v-model="form.mqtt_publish_enabled" /></el-form-item>
              </el-col>
              <el-col :span="10">
                <el-form-item label="发布Topic"><el-input v-model="form.mqtt_publish_topic" :disabled="!form.mqtt_publish_enabled" placeholder="发布数据的Topic" /></el-form-item>
              </el-col>
              <el-col :span="4">
                <el-form-item label="QoS">
                  <el-select v-model="form.mqtt_publish_qos" :disabled="!form.mqtt_publish_enabled" style="width:100%">
                    <el-option label="0" :value="0" /><el-option label="1" :value="1" /><el-option label="2" :value="2" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="4">
                <el-form-item label="周期(秒)"><el-input-number v-model="form.mqtt_publish_interval" :min="1" :disabled="!form.mqtt_publish_enabled" style="width:100%" /></el-form-item>
              </el-col>
            </el-row>
          </template>

          <!-- OPC-UA -->
          <template v-if="form.protocol === 'opc_ua'">
            <el-divider content-position="left">OPC-UA 连接</el-divider>
            <el-row :gutter="16">
              <el-col :span="16">
                <el-form-item label="Endpoint" required>
                  <el-input v-model="form.opc_endpoint" placeholder="opc.tcp://192.168.1.100:4840" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="命名空间"><el-input-number v-model="form.opc_namespace" :min="0" style="width:100%" /></el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="安全模式">
                  <el-select v-model="form.opc_security_mode" style="width:100%">
                    <el-option label="None" value="None" />
                    <el-option label="Basic256Sha256" value="Basic256Sha256" />
                    <el-option label="Basic256" value="Basic256" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="用户名"><el-input v-model="form.opc_username" placeholder="选填" /></el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="密码"><el-input v-model="form.opc_password" type="password" show-password placeholder="选填" /></el-form-item>
              </el-col>
            </el-row>
          </template>

        </el-form>
      </el-scrollbar>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/request'
import dayjs from 'dayjs'

const devices = ref([])
const groups = ref([])
const loading = ref(false)
const saving = ref(false)
const search = ref('')
const filterGroup = ref(null)
const filterProtocol = ref(null)
const filterStatus = ref(null)
const filterFactory = ref(null)
const filterWorkshop = ref(null)
const locationOptions = ref({ factories: [], workshops: [], production_lines: [] })
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const dialogVisible = ref(false)
const editingId = ref(null)

const defaultForm = {
  name: '', description: '', group_id: null, protocol: 'modbus_tcp',
  factory: '', workshop: '', production_line: '', installation: '',
  longitude: null, latitude: null,
  host: '', port: 502, slave_id: 1, timeout: 3.0, retries: 3,
  mqtt_broker: '', mqtt_port: 1883, mqtt_username: '', mqtt_password: '',
  mqtt_client_id: '', mqtt_topic_prefix: '', mqtt_use_tls: false,
  mqtt_payload_format: 'json', mqtt_is_gateway: false,
  mqtt_publish_enabled: false, mqtt_publish_topic: '', mqtt_publish_qos: 0, mqtt_publish_interval: 5.0,
  opc_endpoint: '', opc_security_mode: 'None', opc_username: '', opc_password: '', opc_namespace: 2,
  poll_interval: 5.0, enabled: true,
}
const form = reactive({ ...defaultForm })

const protoLabel = (p) => ({ modbus_tcp: 'Modbus TCP', mqtt: 'MQTT', opc_ua: 'OPC-UA' }[p] || p)
const protoTagType = (p) => ({ modbus_tcp: '', mqtt: 'success', opc_ua: 'warning' }[p] || 'info')
const statusLabel = (s) => ({ online: '在线', offline: '离线', error: '异常', maintenance: '维护' }[s] || s)
const formatTime = (t) => t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '-'

function onProtocolChange() {}

async function fetchDevices() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (search.value) params.search = search.value
    if (filterGroup.value) params.group_id = filterGroup.value
    if (filterProtocol.value) params.protocol = filterProtocol.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterFactory.value) params.factory = filterFactory.value
    if (filterWorkshop.value) params.workshop = filterWorkshop.value
    const res = await api.get('/devices', { params })
    devices.value = res.data.data
    total.value = res.data.total
  } finally { loading.value = false }
}

async function fetchGroups() {
  const res = await api.get('/devices/groups')
  groups.value = res.data
}

async function fetchLocations() {
  try {
    const res = await api.get('/devices/locations')
    locationOptions.value = res.data
  } catch { /* ignore */ }
}

function showDialog(device) {
  if (device) {
    editingId.value = device.id
    Object.assign(form, { ...defaultForm, ...device })
  } else {
    editingId.value = null
    Object.assign(form, defaultForm)
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.name) { ElMessage.warning('请填写设备名称'); return }
  if (form.protocol === 'modbus_tcp' && !form.host) { ElMessage.warning('请填写主机地址'); return }
  if (form.protocol === 'mqtt' && !form.mqtt_broker) { ElMessage.warning('请填写MQTT Broker地址'); return }
  if (form.protocol === 'opc_ua' && !form.opc_endpoint) { ElMessage.warning('请填写OPC-UA Endpoint'); return }
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/devices/${editingId.value}`, form)
      ElMessage.success('更新成功')
    } else {
      await api.post('/devices', form)
      ElMessage.success('创建成功，设备将自动开始采集')
    }
    dialogVisible.value = false
    fetchDevices()
  } finally { saving.value = false }
}

async function handleDelete(device) {
  await ElMessageBox.confirm(`确定删除设备 "${device.name}"？删除后将停止采集。`, '确认')
  await api.delete(`/devices/${device.id}`)
  ElMessage.success('删除成功，已停止采集')
  fetchDevices()
}

onMounted(() => { fetchDevices(); fetchGroups(); fetchLocations() })
</script>
