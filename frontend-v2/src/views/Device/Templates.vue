<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElRow,
  ElCol,
  ElCard,
  ElButton,
  ElTag,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElInputNumber,
  ElMessage,
  ElMessageBox,
  ElEmpty,
  ElTable,
  ElTableColumn,
  ElSwitch,
  ElCheckbox,
  ElTabs,
  ElTabPane,
  ElTreeSelect,
  ElTooltip
} from 'element-plus'
import {
  getDeviceTemplates,
  getDeviceTemplate,
  createDeviceTemplate,
  updateDeviceTemplate,
  deleteDeviceTemplate,
  duplicateDeviceTemplate,
  createFromTemplate,
  unwrapList,
  unwrap
} from '@/api/modbus'
import { getOrgTree } from '@/api/modbus'

defineOptions({ name: 'Templates' })

const loading = ref(false)
const list = ref<any[]>([])
const fetchList = async () => {
  loading.value = true
  try {
    const { list: l } = unwrapList(await getDeviceTemplates())
    list.value = l
  } finally {
    loading.value = false
  }
}

const PROTOCOLS = ['modbus_tcp', 'modbus_rtu', 'mqtt', 'opc_ua']
const PROTOCOL_LABEL: Record<string, string> = {
  modbus_tcp: 'Modbus TCP',
  modbus_rtu: 'Modbus RTU',
  mqtt: 'MQTT',
  opc_ua: 'OPC-UA'
}

// 连接参数默认值（与 Device 模型字段同名；创建/同步时按此覆盖设备）
interface ConnField {
  key: string
  label: string
  type: 'string' | 'number' | 'bool' | 'select'
  options?: { label: string; value: string | number }[]
  placeholder?: string
}
const CONN_DEFS: Record<string, ConnField[]> = {
  modbus_tcp: [
    { key: 'host', label: '主机地址', type: 'string', placeholder: '如：192.168.1.100' },
    { key: 'port', label: '端口', type: 'number' },
    { key: 'slave_id', label: '从站地址', type: 'number' },
    { key: 'timeout', label: '超时(秒)', type: 'number' },
    { key: 'retries', label: '重试次数', type: 'number' },
    { key: 'poll_interval', label: '轮询间隔(秒)', type: 'number' }
  ],
  modbus_rtu: [
    { key: 'serial_port', label: '串口', type: 'string', placeholder: '如：COM1' },
    { key: 'baudrate', label: '波特率', type: 'number' },
    {
      key: 'parity',
      label: '校验位',
      type: 'select',
      options: [
        { label: '无', value: 'none' },
        { label: '偶校验', value: 'even' },
        { label: '奇校验', value: 'odd' }
      ]
    },
    { key: 'data_bits', label: '数据位', type: 'number' },
    { key: 'stop_bits', label: '停止位', type: 'number' },
    { key: 'timeout', label: '超时(秒)', type: 'number' },
    { key: 'retries', label: '重试次数', type: 'number' },
    { key: 'poll_interval', label: '轮询间隔(秒)', type: 'number' }
  ],
  mqtt: [
    { key: 'mqtt_broker', label: 'Broker', type: 'string', placeholder: '如：127.0.0.1:1883' },
    { key: 'mqtt_port', label: '端口', type: 'number' },
    { key: 'mqtt_username', label: '用户名', type: 'string' },
    { key: 'mqtt_password', label: '密码', type: 'string' },
    { key: 'mqtt_client_id', label: 'Client ID', type: 'string' },
    { key: 'mqtt_topic_prefix', label: '主题前缀', type: 'string', placeholder: '如：factory/device1' },
    { key: 'mqtt_use_tls', label: '使用 TLS', type: 'bool' },
    { key: 'mqtt_publish_enabled', label: '启用发布', type: 'bool' },
    { key: 'mqtt_publish_topic', label: '发布主题', type: 'string' },
    { key: 'mqtt_publish_qos', label: '发布 QoS', type: 'number' },
    { key: 'mqtt_publish_interval', label: '发布间隔(秒)', type: 'number' },
    {
      key: 'mqtt_payload_format',
      label: '载荷格式',
      type: 'select',
      options: [
        { label: 'plain', value: 'plain' },
        { label: 'json', value: 'json' },
        { label: 'thingsboard', value: 'thingsboard' }
      ]
    },
    { key: 'mqtt_is_gateway', label: '网关模式', type: 'bool' }
  ],
  opc_ua: [
    { key: 'opc_endpoint', label: 'OPC 端点', type: 'string', placeholder: '如：opc.tcp://127.0.0.1:4840' },
    {
      key: 'opc_security_mode',
      label: '安全模式',
      type: 'select',
      options: [
        { label: 'None', value: 'None' },
        { label: 'Basic256Sha256', value: 'Basic256Sha256' },
        { label: 'Basic256', value: 'Basic256' },
        { label: 'Basic128Rsa15', value: 'Basic128Rsa15' }
      ]
    },
    { key: 'opc_username', label: '用户名', type: 'string' },
    { key: 'opc_password', label: '密码', type: 'string' },
    { key: 'opc_namespace', label: '命名空间', type: 'string' }
  ]
}

const ALARM_TYPES: { label: string; value: string }[] = [
  { label: '高限报警', value: 'threshold_high' },
  { label: '低限报警', value: 'threshold_low' },
  { label: '区间报警', value: 'threshold_range' },
  { label: '变化率报警', value: 'rate_of_change' },
  { label: '状态报警', value: 'status' },
  { label: '断连报警', value: 'disconnect' }
]
const ALARM_LEVELS: { label: string; value: string }[] = [
  { label: '信息', value: 'info' },
  { label: '警告', value: 'warning' },
  { label: '严重', value: 'critical' },
  { label: '紧急', value: 'emergency' }
]

// ── 新建/编辑 ──
const editVisible = ref(false)
const editMode = ref<'create' | 'edit'>('create')
const editSaving = ref(false)
const editFormRef = ref()
const editTab = ref('basic')
const editForm = reactive<any>({
  id: null,
  name: '',
  category: '',
  description: '',
  protocol: 'modbus_tcp',
  config: {},
  tags: [],
  alarm_rules: []
})
const editRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }]
}

const emptyTag = () => ({
  name: '',
  description: '',
  unit: '',
  function_code: 'holding_register',
  address: 0,
  data_type: 'uint16',
  byte_order: 'big_endian',
  bit_index: null,
  register_count: 1,
  scale_factor: 1.0,
  offset: 0.0,
  decimal_places: 2,
  writable: false,
  sort_order: 0,
  enabled: true
})

const connForm = reactive<Record<string, any>>({})
const initConnForm = (protocol: string, config: Record<string, any>) => {
  for (const k of Object.keys(connForm)) delete connForm[k]
  for (const f of CONN_DEFS[protocol] || []) {
    connForm[f.key] = config?.[f.key] ?? (f.type === 'bool' ? false : f.type === 'number' ? null : '')
  }
}

const emptyAlarmRule = () => ({
  name: '',
  tag_name: '',
  description: '',
  alarm_type: 'threshold_high',
  alarm_level: 'warning',
  high_limit: null,
  low_limit: null,
  deadband: 0,
  rate_limit: null,
  status_value: null,
  delay_seconds: 0,
  auto_clear: true,
  sms_enabled: false,
  enabled: true
})

const openCreate = () => {
  editMode.value = 'create'
  Object.assign(editForm, {
    id: null,
    name: '',
    category: '',
    description: '',
    protocol: 'modbus_tcp',
    config: {},
    tags: [],
    alarm_rules: []
  })
  initConnForm('modbus_tcp', {})
  editTab.value = 'basic'
  editVisible.value = true
}

const openEdit = async (tpl: any) => {
  if (tpl.is_system) {
    ElMessage.warning('内置模板只读，可复制为普通模板后编辑')
    return
  }
  const detail = unwrap(await getDeviceTemplate(tpl.id))
  editMode.value = 'edit'
  Object.assign(editForm, {
    id: detail.id,
    name: detail.name,
    category: detail.category,
    description: detail.description,
    protocol: detail.protocol,
    config: detail.config || {},
    tags: (detail.tags || []).length ? detail.tags.map((t: any) => ({ ...t })) : [emptyTag()],
    alarm_rules: (detail.alarm_rules || []).map((r: any) => ({ ...r }))
  })
  initConnForm(detail.protocol, detail.config || {})
  editTab.value = 'basic'
  editVisible.value = true
}

const addTagRow = () => editForm.tags.push(emptyTag())
const removeTagRow = (idx: number) => editForm.tags.splice(idx, 1)

const addAlarmRule = () => editForm.alarm_rules.push(emptyAlarmRule())
const removeAlarmRule = (idx: number) => editForm.alarm_rules.splice(idx, 1)

const submitEdit = async () => {
  await editFormRef.value?.validate()
  editSaving.value = true
  try {
    // 连接参数：显式编辑过的字段覆盖，其余保留原值（避免丢字段）
    const configPayload: Record<string, any> = { ...editForm.config }
    for (const f of CONN_DEFS[editForm.protocol] || []) {
      const v = connForm[f.key]
      if (f.type === 'bool') {
        configPayload[f.key] = !!v
      } else if (v !== null && v !== '' && v !== undefined) {
        configPayload[f.key] = v
      }
    }
    const payload = {
      name: editForm.name,
      category: editForm.category,
      description: editForm.description,
      protocol: editForm.protocol,
      config: configPayload,
      tags: editForm.tags.filter((t: any) => t.name),
      alarm_rules: editForm.alarm_rules.filter((r: any) => r.name)
    }
    if (editMode.value === 'create') {
      await createDeviceTemplate(payload)
      ElMessage.success('模板已创建')
    } else {
      await updateDeviceTemplate(editForm.id, payload)
      ElMessage.success('模板已更新，绑定设备进入待同步状态')
    }
    editVisible.value = false
    fetchList()
  } finally {
    editSaving.value = false
  }
}

// ── 复制 / 删除 ──
const duplicate = async (tpl: any) => {
  await ElMessageBox.confirm(`确认复制模板「${tpl.name}」？`, '复制模板', { type: 'info' })
  await duplicateDeviceTemplate(tpl.id)
  ElMessage.success('已复制为可编辑副本')
  fetchList()
}

const remove = async (tpl: any) => {
  await ElMessageBox.confirm(
    `确认删除模板「${tpl.name}」？${tpl.bind_count ? `（有 ${tpl.bind_count} 台设备绑定，需先解绑）` : ''}`,
    '删除模板',
    { type: 'warning' }
  )
  try {
    await deleteDeviceTemplate(tpl.id)
    ElMessage.success('已删除')
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

// ── 从模板创建设备 ──
const useVisible = ref(false)
const useSaving = ref(false)
const useFormRef = ref()
const useForm = reactive<any>({
  name: '',
  host: '',
  port: 502,
  slave_id: 1,
  serial_port: '',
  baudrate: 9600,
  mqtt_broker: '',
  mqtt_topic_prefix: '',
  opc_endpoint: '',
  org_node_id: null,
  description: '',
  bind: true,
  include_alarm_rules: true
})
const useRules = {
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }]
}
const currentTpl = ref<any>(null)

const openUse = async (tpl: any) => {
  currentTpl.value = tpl
  const detail = unwrap(await getDeviceTemplate(tpl.id))
  const cfg = detail.config || {}
  Object.assign(useForm, {
    name: `${detail.name} 设备`,
    host: cfg.host || '192.168.1.100',
    port: cfg.port || 502,
    slave_id: cfg.slave_id ?? 1,
    serial_port: cfg.serial_port || 'COM1',
    baudrate: cfg.baudrate || 9600,
    mqtt_broker: cfg.mqtt_broker || '',
    mqtt_topic_prefix: cfg.mqtt_topic_prefix || '',
    opc_endpoint: cfg.opc_endpoint || '',
    org_node_id: null,
    description: '',
    bind: true,
    include_alarm_rules: true
  })
  useVisible.value = true
}

const submitUse = async () => {
  await useFormRef.value?.validate()
  useSaving.value = true
  try {
    const base: any = {
      name: useForm.name,
      org_node_id: useForm.org_node_id,
      description: useForm.description,
      bind: useForm.bind,
      include_alarm_rules: useForm.include_alarm_rules
    }
    if (currentTpl.value.protocol === 'modbus_tcp') {
      base.host = useForm.host
      base.config = { port: useForm.port, slave_id: useForm.slave_id }
    } else if (currentTpl.value.protocol === 'modbus_rtu') {
      base.serial_port = useForm.serial_port
      base.config = { baudrate: useForm.baudrate }
    } else if (currentTpl.value.protocol === 'mqtt') {
      base.mqtt_broker = useForm.mqtt_broker
      base.config = { mqtt_topic_prefix: useForm.mqtt_topic_prefix }
    } else if (currentTpl.value.protocol === 'opc_ua') {
      base.opc_endpoint = useForm.opc_endpoint
    }
    const res = unwrap(await createFromTemplate(currentTpl.value.id, base))
    ElMessage.success(res?.message || '设备创建成功')
    useVisible.value = false
  } finally {
    useSaving.value = false
  }
}

const orgTree = ref<any[]>([])
const fetchOrgTree = async () => {
  const res = await getOrgTree()
  orgTree.value = res?.data || []
}

onMounted(() => {
  fetchList()
  fetchOrgTree()
})
</script>

<template>
  <ContentWrap title="设备模板" message="预定义设备类型：连接参数默认值 + 点位定义，一键创建设备并支持批量同步">
    <div class="mb-16px flex items-center justify-between">
      <div class="flex items-center gap-12px">
        <ElButton v-hasPermi="['template.write']" type="primary" @click="openCreate">新建模板</ElButton>
        <span class="text-13px text-gray-500">共 {{ list.length }} 个模板</span>
      </div>
    </div>

    <ElEmpty v-if="!loading && !list.length" description="暂无模板，点击右上角新建" />
    <ElRow v-loading="loading" :gutter="16">
      <ElCol v-for="tpl in list" :key="tpl.id" :xs="24" :sm="12" :md="8" :lg="6" class="mb-16px">
        <ElCard shadow="hover" class="h-full flex flex-col">
          <div class="mb-8px flex items-center justify-between">
            <span class="text-15px font-700">{{ tpl.name }}</span>
            <ElTag v-if="tpl.is_system" size="small" type="info">内置</ElTag>
          </div>
          <div class="mb-4px flex items-center gap-6px">
            <ElTag size="small" type="primary">{{ PROTOCOL_LABEL[tpl.protocol] || tpl.protocol }}</ElTag>
            <ElTag v-if="tpl.category" size="small">{{ tpl.category }}</ElTag>
          </div>
          <div class="text-13px text-gray-500 mb-12px min-h-40px">
            {{ tpl.description || '无描述' }}
          </div>
          <div class="mb-16px text-12px text-gray-400">
            点位 {{ (tpl.tags || []).length }} 个 · 绑定 {{ tpl.bind_count || 0 }} 台设备 ·
            v{{ tpl.version || 1 }}
          </div>
          <div class="mt-auto flex items-center gap-8px">
            <ElTooltip content="根据模板创建设备并绑定" placement="top">
              <ElButton v-hasPermi="['template.write']" type="primary" size="small" @click="openUse(tpl)">
                创建设备
              </ElButton>
            </ElTooltip>
            <ElButton v-if="!tpl.is_system" v-hasPermi="['template.write']" size="small" @click="openEdit(tpl)">
              编辑
            </ElButton>
            <ElButton
              v-hasPermi="['template.write']"
              size="small"
              @click="duplicate(tpl)"
              plain
            >
              复制
            </ElButton>
            <ElButton
              v-if="!tpl.is_system"
              v-hasPermi="['template.write']"
              size="small"
              type="danger"
              plain
              @click="remove(tpl)"
            >
              删除
            </ElButton>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>

    <!-- 新建 / 编辑模板 -->
    <ElDialog
      v-model="editVisible"
      :title="editMode === 'create' ? '新建模板' : '编辑模板'"
      width="860px"
      top="6vh"
      destroy-on-close
    >
      <ElForm ref="editFormRef" :model="editForm" :rules="editRules" label-width="90px">
        <ElTabs v-model="editTab">
          <ElTabPane label="基本信息" name="basic">
            <ElFormItem label="模板名称" prop="name">
              <ElInput v-model="editForm.name" placeholder="如：注塑机 (Modbus TCP)" />
            </ElFormItem>
            <ElFormItem label="分类">
              <ElInput v-model="editForm.category" placeholder="如：PLC / 传感器 / 仪器仪表" />
            </ElFormItem>
            <ElFormItem label="协议">
              <ElSelect
                v-model="editForm.protocol"
                style="width: 240px"
                @change="(p: string) => initConnForm(p, editForm.config)"
              >
                <ElOption v-for="p in PROTOCOLS" :key="p" :label="PROTOCOL_LABEL[p]" :value="p" />
              </ElSelect>
            </ElFormItem>
            <ElFormItem label="描述">
              <ElInput
                v-model="editForm.description"
                type="textarea"
                :rows="3"
                placeholder="模板用途、适用设备的说明"
              />
            </ElFormItem>
          </ElTabPane>
          <ElTabPane :label="`点位定义 (${editForm.tags.length})`" name="tags">
            <div class="mb-8px text-13px text-gray-500">
              点位将作为设备创建时的默认点位；勾选「可写」即为可写点位。
            </div>
            <ElTable :data="editForm.tags" size="small" style="width: 100%">
              <ElTableColumn label="点位名称" width="150">
                <template #default="{ row }">
                  <ElInput v-model="row.name" placeholder="如：温度" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="地址" width="90">
                <template #default="{ row }">
                  <ElInputNumber v-model="row.address" :controls="false" style="width: 100%" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="数据类型" width="130">
                <template #default="{ row }">
                  <ElSelect v-model="row.data_type" size="small">
                    <ElOption
                      v-for="d in ['bool', 'uint16', 'int16', 'uint32', 'int32', 'float32', 'float64']"
                      :key="d"
                      :label="d"
                      :value="d"
                    />
                  </ElSelect>
                </template>
              </ElTableColumn>
              <ElTableColumn label="功能码" width="120">
                <template #default="{ row }">
                  <ElSelect v-model="row.function_code" size="small">
                    <ElOption label="保持寄存器" value="holding_register" />
                    <ElOption label="输入寄存器" value="input_register" />
                    <ElOption label="线圈" value="coil" />
                    <ElOption label="离散输入" value="discrete_input" />
                  </ElSelect>
                </template>
              </ElTableColumn>
              <ElTableColumn label="单位" width="90">
                <template #default="{ row }">
                  <ElInput v-model="row.unit" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="可写" width="70" align="center">
                <template #default="{ row }">
                  <ElSwitch v-model="row.writable" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="启用" width="70" align="center">
                <template #default="{ row }">
                  <ElSwitch v-model="row.enabled" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="" width="60" align="center">
                <template #default="{ $index }">
                  <ElButton link type="danger" size="small" @click="removeTagRow($index)">删除</ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
            <ElButton class="mt-8px" size="small" @click="addTagRow">+ 添加点位</ElButton>
          </ElTabPane>
          <ElTabPane
            :label="`连接参数${editForm.protocol ? ' (' + PROTOCOL_LABEL[editForm.protocol] + ')' : ''}`"
            name="conn"
          >
            <div class="mb-8px text-13px text-gray-500">
              连接参数默认值：从模板创建设备时预填、同步时覆盖到绑定设备。
            </div>
            <ElRow :gutter="16">
              <ElCol v-for="f in CONN_DEFS[editForm.protocol] || []" :key="f.key" :xs="24" :sm="12" :md="8">
                <ElFormItem :label="f.label" class="conn-param">
                  <ElInput
                    v-if="f.type === 'string'"
                    v-model="connForm[f.key]"
                    :placeholder="f.placeholder"
                    clearable
                  />
                  <ElInputNumber
                    v-else-if="f.type === 'number'"
                    v-model="connForm[f.key]"
                    :controls="false"
                    style="width: 100%"
                    :placeholder="f.placeholder"
                  />
                  <ElSelect v-else-if="f.type === 'select'" v-model="connForm[f.key]" style="width: 100%"
                    ><ElOption
                      v-for="o in f.options || []"
                      :key="String(o.value)"
                      :label="o.label"
                      :value="o.value"
                    />
                  </ElSelect>
                  <ElSwitch v-else v-model="connForm[f.key]" />
                </ElFormItem>
              </ElCol>
            </ElRow>
          </ElTabPane>
          <ElTabPane :label="`告警规则 (${editForm.alarm_rules.length})`" name="alarmRules">
            <div class="mb-8px text-13px text-gray-500">
              告警规则通过「点位名称」关联上文定义的点位；从模板创建设备或同步时生成。
            </div>
            <ElTable :data="editForm.alarm_rules" size="small" style="width: 100%">
              <ElTableColumn label="规则名称" width="150">
                <template #default="{ row }">
                  <ElInput v-model="row.name" placeholder="如：温度超限" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="关联点位" width="140">
                <template #default="{ row }">
                  <ElSelect
                    v-model="row.tag_name"
                    style="width: 100%"
                    clearable
                    filterable
                    placeholder="选择点位"
                  >
                    <ElOption
                      v-for="t in editForm.tags.filter((x: any) => x.name)"
                      :key="t.name"
                      :label="t.name"
                      :value="t.name"
                    />
                  </ElSelect>
                </template>
              </ElTableColumn>
              <ElTableColumn label="类型" width="130">
                <template #default="{ row }">
                  <ElSelect v-model="row.alarm_type" style="width: 100%">
                    <ElOption v-for="a in ALARM_TYPES" :key="a.value" :label="a.label" :value="a.value" />
                  </ElSelect>
                </template>
              </ElTableColumn>
              <ElTableColumn label="级别" width="100">
                <template #default="{ row }">
                  <ElSelect v-model="row.alarm_level" style="width: 100%">
                    <ElOption v-for="l in ALARM_LEVELS" :key="l.value" :label="l.label" :value="l.value" />
                  </ElSelect>
                </template>
              </ElTableColumn>
              <ElTableColumn label="高限" width="90">
                <template #default="{ row }">
                  <ElInputNumber v-model="row.high_limit" :controls="false" style="width: 100%" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="低限" width="90">
                <template #default="{ row }">
                  <ElInputNumber v-model="row.low_limit" :controls="false" style="width: 100%" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="死区" width="90">
                <template #default="{ row }">
                  <ElInputNumber v-model="row.deadband" :controls="false" style="width: 100%" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="延时(秒)" width="90">
                <template #default="{ row }">
                  <ElInputNumber v-model="row.delay_seconds" :controls="false" style="width: 100%" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="短信" width="60" align="center">
                <template #default="{ row }">
                  <ElSwitch v-model="row.sms_enabled" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="启用" width="60" align="center">
                <template #default="{ row }">
                  <ElSwitch v-model="row.enabled" />
                </template>
              </ElTableColumn>
              <ElTableColumn label="" width="60" align="center">
                <template #default="{ $index }">
                  <ElButton link type="danger" size="small" @click="removeAlarmRule($index)">删除</ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
            <ElButton class="mt-8px" size="small" @click="addAlarmRule">+ 添加告警规则</ElButton>
          </ElTabPane>
        </ElTabs>
      </ElForm>
      <template #footer>
        <ElButton @click="editVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="editSaving" @click="submitEdit">保存</ElButton>
      </template>
    </ElDialog>

    <!-- 从模板创建设备 -->
    <ElDialog v-model="useVisible" title="根据模板创建设备" width="560px" destroy-on-close>
      <ElAlert
        v-if="currentTpl"
        type="info"
        :closable="false"
        :title="`模板：${currentTpl.name}（协议 ${PROTOCOL_LABEL[currentTpl.protocol] || currentTpl.protocol}，点位 ${(currentTpl.tags || []).length} 个）`"
        class="mb-16px"
      />
      <ElForm ref="useFormRef" :model="useForm" :rules="useRules" label-width="90px">
        <ElFormItem label="设备名称" prop="name">
          <ElInput v-model="useForm.name" />
        </ElFormItem>
        <template v-if="currentTpl && currentTpl.protocol === 'modbus_tcp'">
          <ElFormItem label="主机地址">
            <ElInput v-model="useForm.host" />
          </ElFormItem>
          <ElFormItem label="端口">
            <ElInputNumber v-model="useForm.port" :min="1" :max="65535" />
          </ElFormItem>
          <ElFormItem label="从站地址">
            <ElInputNumber v-model="useForm.slave_id" :min="1" :max="247" />
          </ElFormItem>
        </template>
        <template v-else-if="currentTpl && currentTpl.protocol === 'modbus_rtu'">
          <ElFormItem label="串口">
            <ElInput v-model="useForm.serial_port" />
          </ElFormItem>
          <ElFormItem label="波特率">
            <ElInputNumber v-model="useForm.baudrate" :min="300" :max="115200" />
          </ElFormItem>
        </template>
        <template v-else-if="currentTpl && currentTpl.protocol === 'mqtt'">
          <ElFormItem label="Broker">
            <ElInput v-model="useForm.mqtt_broker" placeholder="如：127.0.0.1:1883" />
          </ElFormItem>
          <ElFormItem label="主题前缀">
            <ElInput v-model="useForm.mqtt_topic_prefix" placeholder="如：factory/device1" />
          </ElFormItem>
        </template>
        <template v-else-if="currentTpl && currentTpl.protocol === 'opc_ua'">
          <ElFormItem label="OPC 端点">
            <ElInput v-model="useForm.opc_endpoint" placeholder="如：opc.tcp://127.0.0.1:4840" />
          </ElFormItem>
        </template>
        <ElFormItem label="组织">
          <ElTreeSelect
            v-model="useForm.org_node_id"
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
          <ElInput v-model="useForm.description" />
        </ElFormItem>
        <ElFormItem label="选项">
          <div class="flex flex-col gap-6px">
            <ElCheckbox v-model="useForm.bind">绑定模板（模板更新后可同步）</ElCheckbox>
            <ElCheckbox v-model="useForm.include_alarm_rules">同步生成模板默认告警规则</ElCheckbox>
          </div>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="useVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="useSaving" @click="submitUse">创建</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>