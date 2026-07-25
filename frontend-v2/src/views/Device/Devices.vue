<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElInput,
  ElPagination,
  ElDialog,
  ElForm,
  ElFormItem,
  ElSelect,
  ElOption,
  ElTree,
  ElTreeSelect,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElDivider,
  ElSwitch
} from 'element-plus'
import {
  getDevices,
  createDevice,
  updateDevice,
  deleteDevice,
  duplicateDevice,
  getOrgTree,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'Devices' })

const router = useRouter()
const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '', org_node_id: null as number | null })
const orgTree = ref<any[]>([])
const orgNodeName = ref('')

const statusType = (s?: string) => {
  if (s === 'online') return 'success'
  if (s === 'error') return 'danger'
  return 'info'
}
const statusText = (s?: string) => {
  if (s === 'online') return '在线'
  if (s === 'error') return '异常'
  return '离线'
}

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getDevices({
      page: query.page,
      page_size: query.page_size,
      keyword: query.keyword || undefined,
      org_node_id: query.org_node_id ?? undefined
    })
    const { list: l, total: t } = unwrapList(res)
    list.value = l
    total.value = t
  } finally {
    loading.value = false
  }
}

const fetchOrgTree = async () => {
  const res = await getOrgTree()
  orgTree.value = res?.data || []
}

const onOrgClick = (data: any) => {
  query.org_node_id = data.id
  orgNodeName.value = data.name
  query.page = 1
  fetchList()
}
const clearOrgFilter = () => {
  query.org_node_id = null
  orgNodeName.value = ''
  query.page = 1
  fetchList()
}

// ── 协议选项 ──
const protocols = [
  { value: 'modbus_tcp', label: 'Modbus TCP', icon: '🔌' },
  { value: 'modbus_rtu', label: 'Modbus RTU', icon: '🔌' },
  { value: 'mqtt', label: 'MQTT', icon: '📡' },
  { value: 'opcua', label: 'OPC-UA', icon: '🔗' }
]

const protocolLabel = (p?: string) => protocols.find((pr) => pr.value === p)?.label || p || '—'

// ── 表单 ──
const dialogVisible = ref(false)
const dialogTitle = ref('新增设备')
const formRef = ref()
const form = reactive<any>({
  id: null,
  name: '',
  protocol: 'modbus_tcp',
  // Modbus TCP
  host: '',
  port: 502,
  slave_id: 1,
  // Modbus RTU
  serial_port: '',
  baudrate: 9600,
  parity: 'none',
  data_bits: 8,
  stop_bits: 1,
  // MQTT
  broker_url: '',
  mqtt_topic: '',
  mqtt_username: '',
  mqtt_password: '',
  mqtt_client_id: '',
  mqtt_qos: 0,
  // OPC-UA
  endpoint_url: '',
  node_id: '',
  opc_security_mode: 'None',
  // 通用
  org_node_id: null as number | null,
  poll_interval: 5,
  has_lab_data: false,
  description: ''
})
const rules = {
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  protocol: [{ required: true, message: '请选择协议', trigger: 'change' }]
}

// 根据协议显示不同字段
const isModbusTcp = computed(() => form.protocol === 'modbus_tcp')
const isModbusRtu = computed(() => form.protocol === 'modbus_rtu')
const isMqtt = computed(() => form.protocol === 'mqtt')
const isOpcua = computed(() => form.protocol === 'opcua')
const isModbus = computed(() => isModbusTcp.value || isModbusRtu.value)

const openCreate = () => {
  dialogTitle.value = '新增设备'
  Object.assign(form, {
    id: null,
    name: '',
    protocol: 'modbus_tcp',
    host: '',
    port: 502,
    slave_id: 1,
    serial_port: '',
    baudrate: 9600,
    parity: 'none',
    data_bits: 8,
    stop_bits: 1,
    broker_url: '',
    mqtt_topic: '',
    mqtt_username: '',
    mqtt_password: '',
    mqtt_client_id: '',
    mqtt_qos: 0,
    endpoint_url: '',
    node_id: '',
    opc_security_mode: 'None',
    org_node_id: query.org_node_id ?? null,
    poll_interval: 5,
    has_lab_data: false,
    description: ''
  })
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑设备'
  Object.assign(form, {
    id: row.id,
    name: row.name,
    protocol: row.protocol || 'modbus_tcp',
    host: row.host || '',
    port: row.port ?? 502,
    slave_id: row.slave_id ?? 1,
    serial_port: row.serial_port || '',
    baudrate: row.baudrate ?? 9600,
    parity: row.parity || 'none',
    data_bits: row.data_bits ?? 8,
    stop_bits: row.stop_bits ?? 1,
    broker_url: row.broker_url || '',
    mqtt_topic: row.mqtt_topic || '',
    mqtt_username: row.mqtt_username || '',
    mqtt_password: row.mqtt_password || '',
    mqtt_client_id: row.mqtt_client_id || '',
    mqtt_qos: row.mqtt_qos ?? 0,
    endpoint_url: row.endpoint_url || '',
    node_id: row.node_id || '',
    opc_security_mode: row.opc_security_mode || 'None',
    org_node_id: row.org_node_id ?? null,
    poll_interval: row.poll_interval ?? 5,
    has_lab_data: !!row.has_lab_data,
    description: row.description || ''
  })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  const payload: any = {
    name: form.name,
    protocol: form.protocol,
    org_node_id: form.org_node_id ?? null,
    poll_interval: form.poll_interval,
    has_lab_data: form.has_lab_data,
    description: form.description
  }

  // 根据协议附加不同字段
  if (isModbusTcp.value) {
    payload.host = form.host
    payload.port = form.port
    payload.slave_id = form.slave_id
  } else if (isModbusRtu.value) {
    payload.serial_port = form.serial_port
    payload.baudrate = form.baudrate
    payload.parity = form.parity
    payload.data_bits = form.data_bits
    payload.stop_bits = form.stop_bits
    payload.slave_id = form.slave_id
  } else if (isMqtt.value) {
    payload.broker_url = form.broker_url
    payload.mqtt_topic = form.mqtt_topic
    payload.mqtt_username = form.mqtt_username
    payload.mqtt_password = form.mqtt_password
    payload.mqtt_client_id = form.mqtt_client_id
    payload.mqtt_qos = form.mqtt_qos
  } else if (isOpcua.value) {
    payload.endpoint_url = form.endpoint_url
    payload.node_id = form.node_id
    payload.opc_security_mode = form.opc_security_mode
  }

  if (form.id) {
    await updateDevice(form.id, payload)
    ElMessage.success('更新成功')
  } else {
    await createDevice(payload)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchList()
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除设备「${row.name}」？`, '提示', { type: 'warning' })
  await deleteDevice(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

// ── 设备复制 ──
const dupDialogVisible = ref(false)
const dupForm = reactive({ id: 0, name: '', copyTags: true, sourceName: '' })

const openDuplicate = (row: any) => {
  dupForm.id = row.id
  dupForm.name = row.name + ' 副本'
  dupForm.copyTags = true
  dupForm.sourceName = row.name
  dupDialogVisible.value = true
}
const doDuplicate = async () => {
  if (!dupForm.name.trim()) {
    ElMessage.warning('请输入新设备名称')
    return
  }
  try {
    const res: any = await duplicateDevice(dupForm.id, dupForm.name.trim(), dupForm.copyTags)
    const body = res?.data || res
    ElMessage.success(body?.message || '复制成功')
    dupDialogVisible.value = false
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '复制失败')
  }
}

onMounted(() => {
  fetchList()
  fetchOrgTree()
})
</script>

<template>
  <ContentWrap title="设备管理">
    <div class="flex items-start">
      <!-- 左侧组织架构树 -->
      <div class="w-260px mr-16px shrink-0 border-r border-solid border-gray-200 pr-12px">
        <div class="flex items-center justify-between mb-8px">
          <span class="text-14px font-bold">组织架构</span>
          <ElButton v-if="query.org_node_id != null" link type="primary" size="small" @click="clearOrgFilter"
            >查看全部</ElButton
          >
        </div>
        <ElTree
          v-loading="!orgTree.length"
          :data="orgTree"
          node-key="id"
          :props="{ label: 'name', children: 'children' }"
          highlight-current
          :expand-on-click-node="false"
          default-expand-all
          @node-click="onOrgClick"
        />
        <div v-if="query.org_node_id != null" class="mt-8px text-12px text-gray-500">
          已按「{{ orgNodeName }}」及其下级筛选
        </div>
      </div>

      <!-- 右侧设备列表 -->
      <div class="flex-1 min-w-0">
        <div class="flex-grow flex justify-end mb-12px">
          <ElInput
            v-model="query.keyword"
            placeholder="搜索设备名称"
            clearable
            class="!w-200px mr-10px"
            @keyup.enter="((query.page = 1), fetchList())"
          />
          <ElButton type="primary" @click="((query.page = 1), fetchList())">查询</ElButton>
          <ElButton v-hasPermi="['device.write']" type="success" class="ml-10px" @click="openCreate"
            >新增设备</ElButton
          >
        </div>

        <ElTable v-loading="loading" :data="list" border stripe>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn prop="name" label="设备名称" min-width="160" show-overflow-tooltip />
          <ElTableColumn label="协议" width="110">
            <template #default="{ row }">
              <ElTag size="small">{{ protocolLabel(row.protocol) }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="连接" min-width="180">
            <template #default="{ row }">
              <span v-if="row.protocol === 'modbus_tcp'">{{ row.host }}:{{ row.port }} / #{{ row.slave_id }}</span>
              <span v-else-if="row.protocol === 'modbus_rtu'">{{ row.serial_port }} / {{ row.baudrate }}bps</span>
              <span v-else-if="row.protocol === 'mqtt'">{{ row.broker_url || '—' }}</span>
              <span v-else-if="row.protocol === 'opcua'">{{ row.endpoint_url || '—' }}</span>
              <span v-else>—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="90">
            <template #default="{ row }">
              <ElTag :type="statusType(row.status)">{{ statusText(row.status) }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="description" label="描述" min-width="160" show-overflow-tooltip />
          <ElTableColumn label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <ElButton link type="primary" @click="router.push(`/device/detail/${row.id}`)"
                >详情</ElButton
              >
              <ElButton v-hasPermi="['device.write']" link type="primary" @click="openEdit(row)"
                >编辑</ElButton
              >
              <ElButton v-hasPermi="['device.write']" link type="primary" @click="openDuplicate(row)"
                >复制</ElButton
              >
              <ElButton v-hasPermi="['device.write']" link type="danger" @click="remove(row)"
                >删除</ElButton
              >
            </template>
          </ElTableColumn>
        </ElTable>

        <div class="flex justify-end mt-16px">
          <ElPagination
            v-model:current-page="query.page"
            v-model:page-size="query.page_size"
            :total="total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @current-change="fetchList"
            @size-change="((query.page = 1), fetchList())"
          />
        </div>
      </div>
    </div>

    <!-- 新增/编辑对话框 -->
    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="660px" top="5vh">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="100px">
        <!-- 基本信息 -->
        <ElFormItem label="设备名称" prop="name">
          <ElInput v-model="form.name" placeholder="请输入设备名称" />
        </ElFormItem>
        <ElFormItem label="协议" prop="protocol">
          <ElSelect v-model="form.protocol" class="w-full" :disabled="!!form.id">
            <ElOption
              v-for="p in protocols"
              :key="p.value"
              :label="`${p.icon} ${p.label}`"
              :value="p.value"
            />
          </ElSelect>
        </ElFormItem>

        <!-- Modbus TCP -->
        <template v-if="isModbusTcp">
          <ElDivider content-position="left">Modbus TCP 连接</ElDivider>
          <ElFormItem label="主机地址">
            <ElInput v-model="form.host" placeholder="192.168.1.100" />
          </ElFormItem>
          <ElFormItem label="端口">
            <ElInputNumber v-model="form.port" :min="1" :max="65535" class="w-full" />
          </ElFormItem>
          <ElFormItem label="从站地址">
            <ElInputNumber v-model="form.slave_id" :min="0" :max="255" class="w-full" />
          </ElFormItem>
        </template>

        <!-- Modbus RTU -->
        <template v-if="isModbusRtu">
          <ElDivider content-position="left">Modbus RTU 连接</ElDivider>
          <ElFormItem label="串口">
            <ElInput v-model="form.serial_port" placeholder="/dev/ttyUSB0 或 COM3" />
          </ElFormItem>
          <ElFormItem label="波特率">
            <ElSelect v-model="form.baudrate" class="w-full">
              <ElOption :label="1200" :value="1200" />
              <ElOption :label="2400" :value="2400" />
              <ElOption :label="4800" :value="4800" />
              <ElOption :label="9600" :value="9600" />
              <ElOption :label="19200" :value="19200" />
              <ElOption :label="38400" :value="38400" />
              <ElOption :label="57600" :value="57600" />
              <ElOption :label="115200" :value="115200" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="校验位">
            <ElSelect v-model="form.parity" class="w-full">
              <ElOption label="无 (None)" value="none" />
              <ElOption label="偶校验 (Even)" value="even" />
              <ElOption label="奇校验 (Odd)" value="odd" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="数据位">
            <ElSelect v-model="form.data_bits" class="w-full">
              <ElOption :label="7" :value="7" />
              <ElOption :label="8" :value="8" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="停止位">
            <ElSelect v-model="form.stop_bits" class="w-full">
              <ElOption :label="1" :value="1" />
              <ElOption :label="2" :value="2" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="从站地址">
            <ElInputNumber v-model="form.slave_id" :min="0" :max="255" class="w-full" />
          </ElFormItem>
        </template>

        <!-- MQTT -->
        <template v-if="isMqtt">
          <ElDivider content-position="left">MQTT 连接</ElDivider>
          <ElFormItem label="Broker 地址">
            <ElInput v-model="form.broker_url" placeholder="mqtt://192.168.1.100:1883" />
          </ElFormItem>
          <ElFormItem label="订阅 Topic">
            <ElInput v-model="form.mqtt_topic" placeholder="devices/sensor/telemetry" />
          </ElFormItem>
          <ElFormItem label="Client ID">
            <ElInput v-model="form.mqtt_client_id" placeholder="留空自动生成" />
          </ElFormItem>
          <ElFormItem label="用户名">
            <ElInput v-model="form.mqtt_username" placeholder="可选" />
          </ElFormItem>
          <ElFormItem label="密码">
            <ElInput v-model="form.mqtt_password" type="password" placeholder="可选" show-password />
          </ElFormItem>
          <ElFormItem label="QoS">
            <ElSelect v-model="form.mqtt_qos" class="w-full">
              <ElOption label="0 - 最多一次" :value="0" />
              <ElOption label="1 - 至少一次" :value="1" />
              <ElOption label="2 - 恰好一次" :value="2" />
            </ElSelect>
          </ElFormItem>
        </template>

        <!-- OPC-UA -->
        <template v-if="isOpcua">
          <ElDivider content-position="left">OPC-UA 连接</ElDivider>
          <ElFormItem label="Endpoint URL">
            <ElInput v-model="form.endpoint_url" placeholder="opc.tcp://192.168.1.100:4840" />
          </ElFormItem>
          <ElFormItem label="Node ID">
            <ElInput v-model="form.node_id" placeholder="ns=2;s=Temperature" />
          </ElFormItem>
          <ElFormItem label="安全模式">
            <ElSelect v-model="form.opc_security_mode" class="w-full">
              <ElOption label="None" value="None" />
              <ElOption label="Basic256" value="Basic256" />
              <ElOption label="Basic256Sha256" value="Basic256Sha256" />
            </ElSelect>
          </ElFormItem>
        </template>

        <!-- 通用设置 -->
        <ElDivider content-position="left">通用设置</ElDivider>
        <ElFormItem label="采集间隔(秒)">
          <ElInputNumber v-model="form.poll_interval" :min="1" :max="3600" class="w-full" />
        </ElFormItem>
        <ElFormItem label="化验对比">
          <ElSwitch v-model="form.has_lab_data" />
          <span class="text-12px text-gray-400 ml-8px">启用后可录入化验数据并与采集值对比</span>
        </ElFormItem>
        <ElFormItem label="归属组织">
          <ElTreeSelect
            v-model="form.org_node_id"
            :data="orgTree"
            node-key="id"
            :props="{ label: 'name', children: 'children' }"
            check-strictly
            clearable
            placeholder="请选择设备所属组织节点"
            class="w-full"
          />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="form.description" type="textarea" :rows="2" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>

    <!-- 设备复制对话框 -->
    <ElDialog v-model="dupDialogVisible" title="复制设备" width="480px">
      <ElAlert
        :title="`从「${dupForm.sourceName}」复制，设备配置和点位将一并复制`"
        type="info"
        :closable="false"
        class="mb-16px"
      />
      <ElForm label-width="100px">
        <ElFormItem label="新设备名称">
          <ElInput v-model="dupForm.name" placeholder="请输入新设备名称" />
        </ElFormItem>
        <ElFormItem label="复制点位">
          <ElSwitch v-model="dupForm.copyTags" />
          <span class="text-12px text-gray-400 ml-8px">复制全部采集点位配置</span>
        </ElFormItem>
        <ElFormItem label="状态">
          <span class="text-12px text-gray-500">新设备默认禁用，确认无误后手动启用</span>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dupDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="doDuplicate">确认复制</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
