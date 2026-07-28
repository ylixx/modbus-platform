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
  ElTreeSelect,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElDivider,
  ElSwitch,
  ElAlert
} from 'element-plus'
import {
  getDevices,
  createDevice,
  updateDevice,
  deleteDevice,
  duplicateDevice,
  getOrgTree,
  unwrapList,
  exportDevicesCsv,
  getImportTemplateDevices,
  importDevices
} from '@/api/modbus'
import OrgCascadeSelect from '@/components/OrgCascadeSelect.vue'
import { saveBlob, deviceStatusType, deviceStatusText, concurrentRun } from '@/utils/modbus'

defineOptions({ name: 'Devices' })

const router = useRouter()
const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const query = reactive({
  page: 1,
  page_size: 30,
  org_node_id: null as number | null,
  ids: null as number[] | null
})
const orgTree = ref<any[]>([])

// 关联列表框：层级路径筛选 + 多选设备
const cascadeRef = ref()
// 级联选择结果：{ org_node_id, labels }（org_node_id 用于按组织架构子树筛选设备）
const orgPath = ref<{ org_node_id: number | null; labels: string[] } | null>(null)
const selectedIds = ref<number[]>([]) // 设备名称框（远程搜索）选中的设备
const checkedIds = ref<number[]>([]) // 设备表格行勾选选中的设备
// 两种选择方式合并后用于批量操作
const effectiveIds = computed(() => Array.from(new Set([...selectedIds.value, ...checkedIds.value])))
const tableRef = ref()
// 表格行勾选变化
const onTableSelection = (rows: any[]) => {
  checkedIds.value = rows.map((r) => r.id)
}
const onPathChange = (p: { org_node_id: number | null; labels: string[] } | null) => {
  query.org_node_id = p?.org_node_id ?? null
  query.page = 1
  // 层级筛选变化：清空表格勾选，避免跨范围残留选中
  tableRef.value?.clearSelection()
}

const statusType = deviceStatusType
const statusText = deviceStatusText

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getDevices({
      page: query.page,
      page_size: query.page_size,
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

const clearOrgFilter = () => {
  query.org_node_id = null
  query.page = 1
  fetchList()
}

// ── 批量操作（基于关联列表框多选） ──
const batchBusy = ref(false)

const batchEnable = async (enabled: boolean) => {
  if (!effectiveIds.value.length) return
  await ElMessageBox.confirm(
    `确认${enabled ? '启用' : '禁用'}选中的 ${effectiveIds.value.length} 台设备？`,
    '批量操作',
    { type: 'warning' }
  )
  batchBusy.value = true
  try {
    await concurrentRun(effectiveIds.value, (id) => updateDevice(id, { enabled }))
    ElMessage.success(`已${enabled ? '启用' : '禁用'} ${effectiveIds.value.length} 台设备`)
    clearAllSelection()
    fetchList()
  } finally {
    batchBusy.value = false
  }
}
const batchDelete = async () => {
  if (!effectiveIds.value.length) return
  await ElMessageBox.confirm(
    `确认删除选中的 ${effectiveIds.value.length} 台设备？此操作不可恢复`,
    '批量删除',
    { type: 'warning' }
  )
  batchBusy.value = true
  try {
    await concurrentRun(effectiveIds.value, (id) => deleteDevice(id))
    ElMessage.success(`已删除 ${effectiveIds.value.length} 台设备`)
    clearAllSelection()
    fetchList()
  } finally {
    batchBusy.value = false
  }
}
const clearAllSelection = () => {
  selectedIds.value = []
  checkedIds.value = []
  tableRef.value?.clearSelection()
  cascadeRef.value?.clearSelection()
}
// 「全选当前」：针对表格——勾选当前页全部设备行（跨页通过 reserve-selection 保留，可累计）
const selectAllCurrent = () => {
  if (!list.value.length) return
  list.value.forEach((row) => tableRef.value?.toggleRowSelection(row, true))
}

// ── 导入 / 导出 ──
const exporting = ref(false)
const doExport = async () => {
  exporting.value = true
  try {
    const res: any = await exportDevicesCsv()
    saveBlob(res, `devices_${new Date().toISOString().slice(0, 10)}.csv`)
    ElMessage.success('导出成功')
  } finally {
    exporting.value = false
  }
}

const importDialogVisible = ref(false)
const importing = ref(false)
const importFile = ref<File | null>(null)
const importResult = ref<{ created: number; errors: string[] } | null>(null)
const fileInputRef = ref<HTMLInputElement>()

const openImport = () => {
  importFile.value = null
  importResult.value = null
  importDialogVisible.value = true
}
const onFilePick = (e: Event) => {
  const f = (e.target as HTMLInputElement).files?.[0] || null
  importFile.value = f
  importResult.value = null
}
const downloadTemplate = async () => {
  const res: any = await getImportTemplateDevices()
  saveBlob(res, 'device_template.csv')
}
const doImport = async () => {
  if (!importFile.value) {
    ElMessage.warning('请先选择 CSV 文件')
    return
  }
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    const res: any = await importDevices(fd)
    const body = res?.data || res
    importResult.value = { created: body?.created ?? 0, errors: body?.errors ?? [] }
    ElMessage.success(body?.message || '导入完成')
    if (fileInputRef.value) fileInputRef.value.value = ''
    importFile.value = null
    fetchList()
    fetchOrgTree()
  } finally {
    importing.value = false
  }
}

// ── 协议选项 ──
const protocols = [
  { value: 'modbus_tcp', label: 'Modbus TCP', icon: '🔌' },
  { value: 'modbus_rtu', label: 'Modbus RTU', icon: '🔌' },
  { value: 'mqtt', label: 'MQTT', icon: '📡' },
  { value: 'opc_ua', label: 'OPC-UA', icon: '🔗' }
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
  // MQTT (field names match backend Device model: mqtt_broker, mqtt_topic_prefix, etc.)
  mqtt_broker: '',
  mqtt_topic_prefix: '',
  mqtt_username: '',
  mqtt_password: '',
  mqtt_client_id: '',
  mqtt_publish_qos: 0,
  mqtt_payload_template: '',
  // OPC-UA (field names match backend Device model: opc_endpoint, etc.)
  opc_endpoint: '',
  opc_namespace: 2,
  opc_security_mode: 'None',
  // 通用
  org_node_id: null as number | null,
  poll_interval: 5,
  has_lab_data: false,
  description: ''
})
// 根据协议显示不同字段
const isModbusTcp = computed(() => form.protocol === 'modbus_tcp')
const isModbusRtu = computed(() => form.protocol === 'modbus_rtu')
const isMqtt = computed(() => form.protocol === 'mqtt')
const isOpcua = computed(() => form.protocol === 'opc_ua')
const isModbus = computed(() => isModbusTcp.value || isModbusRtu.value)

const rules = computed(() => {
  const base: Record<string, any[]> = {
    name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }, { max: 100, message: '名称不能超过100个字符', trigger: 'blur' }],
    protocol: [{ required: true, message: '请选择协议', trigger: 'change' }]
  }
  if (isModbusTcp.value) {
    base.host = [{ required: true, message: '请输入主机地址', trigger: 'blur' }]
    base.port = [{ required: true, message: '请输入端口', trigger: 'blur' }]
    base.slave_id = [{ required: true, message: '请输入从站地址', trigger: 'blur' }]
  } else if (isModbusRtu.value) {
    base.serial_port = [{ required: true, message: '请输入串口', trigger: 'blur' }]
    base.slave_id = [{ required: true, message: '请输入从站地址', trigger: 'blur' }]
  } else if (isMqtt.value) {
    base.mqtt_broker = [{ required: true, message: '请输入 Broker 地址', trigger: 'blur' }]
  } else if (isOpcua.value) {
    base.opc_endpoint = [{ required: true, message: '请输入 Endpoint URL', trigger: 'blur' }]
  }
  return base
})

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
    mqtt_broker: '',
    mqtt_topic_prefix: '',
    mqtt_username: '',
    mqtt_password: '',
    mqtt_client_id: '',
    mqtt_publish_qos: 0,
    mqtt_payload_template: '',
    opc_endpoint: '',
    opc_namespace: 2,
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
    mqtt_broker: row.mqtt_broker || '',
    mqtt_topic_prefix: row.mqtt_topic_prefix || '',
    mqtt_username: row.mqtt_username || '',
    mqtt_password: row.mqtt_password || '',
    mqtt_client_id: row.mqtt_client_id || '',
    mqtt_publish_qos: row.mqtt_publish_qos ?? 0,
    mqtt_payload_template: row.mqtt_payload_template || '',
    opc_endpoint: row.opc_endpoint || '',
    opc_namespace: row.opc_namespace ?? 2,
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
    payload.mqtt_broker = form.mqtt_broker
    payload.mqtt_topic_prefix = form.mqtt_topic_prefix
    payload.mqtt_username = form.mqtt_username
    payload.mqtt_password = form.mqtt_password
    payload.mqtt_client_id = form.mqtt_client_id
    payload.mqtt_publish_qos = form.mqtt_publish_qos
    payload.mqtt_payload_template = form.mqtt_payload_template
  } else if (isOpcua.value) {
    payload.opc_endpoint = form.opc_endpoint
    payload.opc_namespace = form.opc_namespace
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
    <!-- 关联列表框筛选器（厂区/班/站/位置/设备名称 + 多选） -->
    <OrgCascadeSelect
      ref="cascadeRef"
      :show-device-actions="false"
      v-model="selectedIds"
      v-model:path="orgPath"
      @update:path="onPathChange"
      @search="fetchList"
      class="mb-12px"
    />

    <!-- 搜索 + 新增 + 批量操作（统一同一排，按钮高度与「搜索/重置」一致，批量删除不重复） -->
    <div class="flex items-center justify-between mb-12px">
      <div class="flex items-center gap-10px">
        <ElButton
          v-if="orgPath"
          link
          type="primary"
          @click="(cascadeRef?.clearPath(), fetchList())"
          >清除层级筛选</ElButton
        >
        <span v-if="effectiveIds.length" class="text-13px"
          >已选 <b class="text-primary">{{ effectiveIds.length }}</b> 台设备</span
        >
      </div>
      <div class="flex items-center gap-10px">
        <ElButton v-hasPermi="['device.write']" type="success" @click="openCreate"
          >新增设备</ElButton
        >
        <ElButton v-hasPermi="['device.write']" type="primary" plain @click="openImport"
          >导入</ElButton
        >
        <ElButton v-hasPermi="['export.download']" :loading="exporting" plain @click="doExport">导出</ElButton>
        <ElButton
          :disabled="!list.length"
          title="勾选当前表格页全部设备行（跨页保留，翻页后可累计）"
          @click="selectAllCurrent"
          >全选当前</ElButton
        >
        <ElButton
          :disabled="!effectiveIds.length"
          @click="clearAllSelection"
          >清空选择</ElButton
        >
        <ElButton
          :loading="batchBusy"
          :disabled="!effectiveIds.length"
          @click="batchEnable(true)"
          >批量启用</ElButton
        >
        <ElButton
          :loading="batchBusy"
          :disabled="!effectiveIds.length"
          @click="batchEnable(false)"
          >批量禁用</ElButton
        >
        <ElButton
          type="danger"
          :loading="batchBusy"
          :disabled="!effectiveIds.length"
          @click="batchDelete"
          >批量删除</ElButton
        >
      </div>
    </div>

    <ElTable ref="tableRef" v-loading="loading" :data="list" row-key="id" border stripe @selection-change="onTableSelection">
      <template #empty>
        <div class="py-20px text-center text-gray-400">暂无设备数据</div>
      </template>
      <ElTableColumn type="selection" width="50" :reserve-selection="true" />
      <ElTableColumn prop="id" label="ID" width="70" />
      <ElTableColumn prop="name" label="设备名称" min-width="160" show-overflow-tooltip />
      <ElTableColumn label="层级" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="text-gray-500">{{
            row.org_path ||
            [row.factory, row.workshop, row.production_line, row.installation]
              .filter(Boolean)
              .join(' / ') ||
            '—'
          }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="协议" width="110">
        <template #default="{ row }">
          <ElTag size="small">{{ protocolLabel(row.protocol) }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="连接" min-width="180">
        <template #default="{ row }">
          <span v-if="row.protocol === 'modbus_tcp'"
            >{{ row.host }}:{{ row.port }} / #{{ row.slave_id }}</span
          >
          <span v-else-if="row.protocol === 'modbus_rtu'"
            >{{ row.serial_port }} / {{ row.baudrate }}bps</span
          >
          <span v-else-if="row.protocol === 'mqtt'">{{ row.mqtt_broker || '—' }}</span>
          <span v-else-if="row.protocol === 'opc_ua'">{{ row.opc_endpoint || '—' }}</span>
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
        :page-sizes="[10, 20, 30, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList"
        @size-change="((query.page = 1), fetchList())"
      />
    </div>

    <!-- 新增/编辑对话框 -->
    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="660px" top="5vh" @close="formRef?.resetFields()">
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
          <ElFormItem label="主机地址" prop="host">
            <ElInput v-model="form.host" placeholder="192.168.1.100" />
          </ElFormItem>
          <ElFormItem label="端口" prop="port">
            <ElInputNumber v-model="form.port" :min="1" :max="65535" class="w-full" />
          </ElFormItem>
          <ElFormItem label="从站地址" prop="slave_id">
            <ElInputNumber v-model="form.slave_id" :min="0" :max="255" class="w-full" />
          </ElFormItem>
        </template>

        <!-- Modbus RTU -->
        <template v-if="isModbusRtu">
          <ElDivider content-position="left">Modbus RTU 连接</ElDivider>
          <ElFormItem label="串口" prop="serial_port">
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
          <ElFormItem label="从站地址" prop="slave_id">
            <ElInputNumber v-model="form.slave_id" :min="0" :max="255" class="w-full" />
          </ElFormItem>
        </template>

        <!-- MQTT -->
        <template v-if="isMqtt">
          <ElDivider content-position="left">MQTT 连接</ElDivider>
          <ElFormItem label="Broker 地址" prop="mqtt_broker">
            <ElInput v-model="form.mqtt_broker" placeholder="mqtt://192.168.1.100:1883" />
          </ElFormItem>
          <ElFormItem label="订阅 Topic">
            <ElInput v-model="form.mqtt_topic_prefix" placeholder="devices/sensor/telemetry" />
          </ElFormItem>
          <ElFormItem label="Client ID">
            <ElInput v-model="form.mqtt_client_id" placeholder="留空自动生成" />
          </ElFormItem>
          <ElFormItem label="用户名">
            <ElInput v-model="form.mqtt_username" placeholder="可选" />
          </ElFormItem>
          <ElFormItem label="密码">
            <ElInput
              v-model="form.mqtt_password"
              type="password"
              placeholder="可选"
              show-password
            />
          </ElFormItem>
          <ElFormItem label="QoS">
            <ElSelect v-model="form.mqtt_publish_qos" class="w-full">
              <ElOption label="0 - 最多一次" :value="0" />
              <ElOption label="1 - 至少一次" :value="1" />
              <ElOption label="2 - 恰好一次" :value="2" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="发布模板">
            <ElInput
              v-model="form.mqtt_payload_template"
              type="textarea"
              :rows="6"
              placeholder="留空使用默认格式。支持占位符：${device_id} ${device_name} ${timestamp} ${timestamp_ms} ${values_json} ${values_detail} ${value} ${tag_name}"
              class="font-mono"
            />
            <div class="text-12px text-gray-400 mt-4px">
              占位符：${device_id} ${device_name} ${timestamp} ${timestamp_ms} ${values_json}
              ${values_detail}
            </div>
          </ElFormItem>
        </template>

        <!-- OPC-UA -->
        <template v-if="isOpcua">
          <ElDivider content-position="left">OPC-UA 连接</ElDivider>
          <ElFormItem label="Endpoint URL" prop="opc_endpoint">
            <ElInput v-model="form.opc_endpoint" placeholder="opc.tcp://192.168.1.100:4840" />
          </ElFormItem>
          <ElFormItem label="Node ID">
            <ElInput v-model="form.opc_namespace" placeholder="ns=2 (namespace number)" />
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

    <!-- 设备导入对话框 -->
    <ElDialog v-model="importDialogVisible" title="批量导入设备" width="520px" @close="importFile = null, importResult = null">
      <ElAlert
        title="请使用 CSV 模板格式填写设备数据后上传，重名设备会被跳过"
        type="info"
        :closable="false"
        class="mb-16px"
      />
      <div class="flex items-center gap-10px mb-16px">
        <ElButton link type="primary" @click="downloadTemplate">下载导入模板 (CSV)</ElButton>
      </div>
      <div class="mb-16px">
        <input
          ref="fileInputRef"
          type="file"
          accept=".csv,text/csv"
          @change="onFilePick"
          class="text-13px"
        />
      </div>
      <div v-if="importFile" class="text-13px text-gray-500 mb-8px">
        已选择：{{ importFile.name }}（{{ (importFile.size / 1024).toFixed(1) }} KB）
      </div>
      <div v-if="importResult" class="mt-8px">
        <ElAlert
          :title="`导入完成：成功 ${importResult.created} 条${importResult.errors.length ? `，失败 ${importResult.errors.length} 条` : ''}`"
          :type="importResult.errors.length ? 'warning' : 'success'"
          :closable="false"
        />
        <div
          v-if="importResult.errors.length"
          class="mt-8px max-h-160px overflow-auto text-12px text-red-500 leading-20px"
        >
          <div v-for="(err, i) in importResult.errors" :key="i">{{ err }}</div>
        </div>
      </div>
      <template #footer>
        <ElButton @click="importDialogVisible = false">关闭</ElButton>
        <ElButton type="primary" :loading="importing" :disabled="!importFile" @click="doImport"
          >开始导入</ElButton
        >
      </template>
    </ElDialog>

    <!-- 设备复制对话框 -->
    <ElDialog v-model="dupDialogVisible" title="复制设备" width="480px" @close="dupForm.name = '', dupForm.copyTags = true">
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
