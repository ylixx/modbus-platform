<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSwitch,
  ElSelect,
  ElOption,
  ElMessage,
  ElMessageBox,
  ElAlert,
  ElEmpty,
  ElDivider,
  ElTooltip
} from 'element-plus'
import {
  getAlarmMqttConfigs,
  createAlarmMqttConfig,
  updateAlarmMqttConfig,
  deleteAlarmMqttConfig,
  testAlarmMqttConfig,
  unwrap
} from '@/api/modbus'

defineOptions({ name: 'AlarmMqtt' })

const list = ref<any[]>([])
const loading = ref(false)

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getAlarmMqttConfigs()
    list.value = unwrap(res) || []
  } catch (e: any) {
    ElMessage.error(e?.message || '获取配置失败')
  } finally {
    loading.value = false
  }
}

// ── 预设模式 ──
const PRESET_MODES = [
  { label: '标准MQTT', value: 'standard', desc: '自定义主题模板和JSON格式，适用于通用MQTT Broker' },
  { label: 'ThingsBoard 设备接入', value: 'thingsboard_device', desc: '设备直接接入ThingsBoard，使用AccessToken认证，遥测格式自动生成' },
  { label: 'ThingsBoard 网关接入', value: 'thingsboard_gateway', desc: '通过网关接入ThingsBoard，支持多子设备，遥测自动聚合' }
]

const PRESET_LABEL_MAP: Record<string, string> = {
  standard: '标准MQTT',
  thingsboard_device: 'TB设备接入',
  thingsboard_gateway: 'TB网关接入'
}

// ── 对话框 ──
const dialogVisible = ref(false)
const dialogTitle = ref('新增配置')
const formRef = ref()
const emptyForm = () => ({
  id: null as number | null,
  name: '',
  preset_mode: 'standard',
  broker: '',
  port: 1883,
  username: '',
  password: '',
  use_tls: false,
  tb_device_token: '',
  tb_gateway_name: '',
  topic_template: 'alarms/${device_name}/${alarm_level}',
  payload_template: '',
  qos: 0,
  alarm_levels: '' as any,
  alarm_events: '' as any,
  device_ids: '',
  enabled: true
})
const form = reactive<any>(emptyForm())

// 模式切换时自动填充
watch(() => form.preset_mode, (mode: string) => {
  if (mode === 'thingsboard_device') {
    form.topic_template = 'v1/devices/me/telemetry'
    form.payload_template = ''
    form.port = 1883
  } else if (mode === 'thingsboard_gateway') {
    form.topic_template = 'v1/gateway/telemetry'
    form.payload_template = ''
    form.port = 1883
  } else {
    form.topic_template = 'alarms/${device_name}/${alarm_level}'
    form.payload_template = ''
  }
})

const isThingsBoard = computed(() => form.preset_mode !== 'standard')

const ALARM_LEVELS = [
  { label: '提示 info', value: 'info' },
  { label: '警告 warning', value: 'warning' },
  { label: '严重 critical', value: 'critical' },
  { label: '紧急 emergency', value: 'emergency' }
]
const ALARM_EVENTS = [
  { label: '报警触发', value: 'triggered' },
  { label: '报警消除', value: 'cleared' }
]

const rules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  broker: [{ required: true, message: '请输入Broker地址', trigger: 'blur' }],
  topic_template: [{ required: true, message: '请输入主题模板', trigger: 'blur' }]
}

const openCreate = () => {
  dialogTitle.value = '新增配置'
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

const openEdit = (row: any) => {
  dialogTitle.value = '编辑配置'
  Object.assign(form, emptyForm(), {
    id: row.id,
    name: row.name,
    preset_mode: row.preset_mode || 'standard',
    broker: row.broker,
    port: row.port,
    username: row.username,
    password: row.password,
    use_tls: row.use_tls,
    tb_device_token: row.tb_device_token || '',
    tb_gateway_name: row.tb_gateway_name || '',
    topic_template: row.topic_template,
    payload_template: row.payload_template,
    qos: row.qos,
    alarm_levels: row.alarm_levels ? JSON.parse(row.alarm_levels) : [],
    alarm_events: row.alarm_events ? JSON.parse(row.alarm_events) : [],
    device_ids: row.device_ids || '',
    enabled: row.enabled
  })
  dialogVisible.value = true
}

const submit = async () => {
  await formRef.value?.validate()
  const payload = { ...form }
  delete payload.id
  // 数组字段转 JSON 字符串
  payload.alarm_levels = Array.isArray(payload.alarm_levels) ? JSON.stringify(payload.alarm_levels) : payload.alarm_levels
  payload.alarm_events = Array.isArray(payload.alarm_events) ? JSON.stringify(payload.alarm_events) : payload.alarm_events
  try {
    if (form.id) {
      await updateAlarmMqttConfig(form.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createAlarmMqttConfig(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '保存失败'
    ElMessage.error(msg)
  }
}

const remove = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除配置「${row.name}」？`, '提示', { type: 'warning' })
    await deleteAlarmMqttConfig(row.id)
    ElMessage.success('删除成功')
    fetchList()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}

const testSend = async (row: any) => {
  try {
    await testAlarmMqttConfig(row.id)
    ElMessage.success('测试消息已发送，请检查Broker')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '测试发送失败')
  }
}

onMounted(fetchList)
</script>

<template>
  <ContentWrap title="报警MQTT推送">
    <ElAlert type="info" :closable="false" class="mb-12px">
      <template #default>
        <div>
          配置报警事件通过MQTT向外发布。支持标准MQTT和ThingsBoard两种预设模式。
          <br />
          <b>标准MQTT</b>：自定义主题模板和JSON格式模板。
          <br />
          <b>ThingsBoard</b>：自动适配ThingsBoard遥测协议（设备接入/网关接入），主题和格式自动生成，只需填Token即可。
        </div>
      </template>
    </ElAlert>

    <div class="flex items-center mb-12px">
      <span class="flex-grow" />
      <ElButton type="success" @click="openCreate">新增配置</ElButton>
    </div>

    <ElTable v-loading="loading" :data="list" border stripe>
      <ElTableColumn prop="id" label="ID" width="60" />
      <ElTableColumn prop="name" label="名称" min-width="120" show-overflow-tooltip />
      <ElTableColumn label="预设模式" width="130">
        <template #default="{ row }">
          <ElTag :type="row.preset_mode === 'standard' ? 'info' : 'warning'" size="small">
            {{ PRESET_LABEL_MAP[row.preset_mode] || row.preset_mode }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="broker" label="Broker" min-width="140" show-overflow-tooltip />
      <ElTableColumn prop="port" label="端口" width="70" />
      <ElTableColumn prop="topic_template" label="主题模板" min-width="200" show-overflow-tooltip />
      <ElTableColumn label="等级过滤" width="120">
        <template #default="{ row }">
          <template v-if="row.alarm_levels">
            <ElTag v-for="l in (JSON.parse(row.alarm_levels) || [])" :key="l" size="small" class="mr-4px">{{ l }}</ElTag>
          </template>
          <span v-else class="text-gray-400">全部</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="事件过滤" width="100">
        <template #default="{ row }">
          <template v-if="row.alarm_events">
            <ElTag v-for="e in (JSON.parse(row.alarm_events) || [])" :key="e" size="small" class="mr-4px">{{ e === 'triggered' ? '触发' : '消除' }}</ElTag>
          </template>
          <span v-else class="text-gray-400">全部</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="启用" width="70">
        <template #default="{ row }">
          <ElTag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '是' : '否' }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <ElButton link type="primary" @click="openEdit(row)">编辑</ElButton>
          <ElButton link type="success" @click="testSend(row)">测试</ElButton>
          <ElButton link type="danger" @click="remove(row)">删除</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>

    <ElEmpty v-if="!loading && !list.length" description="暂无MQTT推送配置" />

    <!-- 新增/编辑对话框 -->
    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="720px" @close="formRef?.resetFields()">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="120px">

        <!-- ── 基本信息区 ── -->
        <ElFormItem label="配置名称" prop="name">
          <ElInput v-model="form.name" placeholder="如：生产环境MQTT推送" />
        </ElFormItem>

        <ElFormItem label="预设模式" prop="preset_mode">
          <ElSelect v-model="form.preset_mode" style="width: 100%">
            <ElOption v-for="m in PRESET_MODES" :key="m.value" :label="m.label" :value="m.value">
              <div>
                <div>{{ m.label }}</div>
                <div style="font-size: 12px; color: var(--el-text-color-secondary);">{{ m.desc }}</div>
              </div>
            </ElOption>
          </ElSelect>
        </ElFormItem>

        <!-- ── ThingsBoard 专属提示 ── -->
        <ElAlert v-if="form.preset_mode === 'thingsboard_device'" type="warning" :closable="false" class="mb-12px" show-icon>
          <template #title>ThingsBoard 设备接入模式</template>
          主题自动设为 <code>v1/devices/me/telemetry</code>，格式自动生成。请填写设备 AccessToken，将作为 MQTT 认证的用户名。
        </ElAlert>
        <ElAlert v-if="form.preset_mode === 'thingsboard_gateway'" type="warning" :closable="false" class="mb-12px" show-icon>
          <template #title>ThingsBoard 网关接入模式</template>
          主题自动设为 <code>v1/gateway/telemetry</code>，格式自动聚合。请填写网关 AccessToken 和网关设备名。
        </ElAlert>

        <!-- ── ThingsBoard Token（设备/网关接入共用） ── -->
        <ElFormItem v-if="isThingsBoard" label="AccessToken" prop="tb_device_token">
          <ElInput v-model="form.tb_device_token" placeholder="ThingsBoard 设备/网关的 AccessToken" show-password />
          <div class="text-12px text-gray-400 mt-4px">
            在 ThingsBoard → 设备 → 设备凭证 中获取 AccessToken。此 Token 将作为 MQTT 连接的用户名，密码留空。
          </div>
        </ElFormItem>

        <!-- ── 网关设备名（仅网关模式） ── -->
        <ElFormItem v-if="form.preset_mode === 'thingsboard_gateway'" label="网关设备名" prop="tb_gateway_name">
          <ElInput v-model="form.tb_gateway_name" placeholder="ThingsBoard 中网关设备的名称" />
          <div class="text-12px text-gray-400 mt-4px">
            报警将作为该网关下的子设备遥测推送，格式：{"设备名":[{"ts":ms,"values":{...}}]}
          </div>
        </ElFormItem>

        <ElDivider content-position="left">MQTT Broker 连接</ElDivider>

        <div class="flex gap-8px">
          <ElFormItem label="Broker地址" prop="broker" class="flex-grow">
            <ElInput v-model="form.broker" placeholder="如：192.168.1.100 或 thingsboard.example.com" />
          </ElFormItem>
          <ElFormItem label="端口" class="!w-160px">
            <ElInputNumber v-model="form.port" :min="1" :max="65535" :controls="false" class="!w-full" />
          </ElFormItem>
        </div>

        <!-- 标准 MQTT 才显示用户名密码；ThingsBoard 模式下用 Token 认证 -->
        <template v-if="!isThingsBoard">
          <div class="flex gap-8px">
            <ElFormItem label="用户名" class="flex-grow">
              <ElInput v-model="form.username" placeholder="可选" />
            </ElFormItem>
            <ElFormItem label="密码" class="flex-grow">
              <ElInput v-model="form.password" type="password" show-password placeholder="可选" />
            </ElFormItem>
          </div>
        </template>

        <ElFormItem label="启用TLS">
          <ElSwitch v-model="form.use_tls" />
        </ElFormItem>

        <ElDivider content-position="left">主题与格式</ElDivider>

        <ElFormItem label="主题模板" prop="topic_template">
          <ElInput v-model="form.topic_template" :disabled="isThingsBoard" placeholder="如：alarms/${device_name}/${alarm_level}" />
          <div v-if="!isThingsBoard" class="text-12px text-gray-400 mt-4px">
            支持占位符：${device_name} ${alarm_level} ${alarm_type} ${status}
          </div>
          <div v-else class="text-12px text-gray-400 mt-4px">
            ThingsBoard 模式下主题自动生成，无需修改
          </div>
        </ElFormItem>

        <ElFormItem label="JSON模板">
          <ElInput
            v-model="form.payload_template"
            type="textarea"
            :rows="6"
            :disabled="isThingsBoard"
            placeholder='留空使用默认格式，或输入自定义JSON模板'
          />
          <div v-if="!isThingsBoard" class="text-12px text-gray-400 mt-4px">
            支持占位符：${device_name} ${device_id} ${tag_name} ${tag_id} ${alarm_type} ${alarm_level} ${alarm_message} ${trigger_value} ${threshold_value} ${status} ${triggered_at}
          </div>
          <div v-else class="text-12px text-gray-400 mt-4px">
            ThingsBoard 模式下格式自动生成，无需手动填写
          </div>
        </ElFormItem>

        <ElDivider content-position="left">过滤与控制</ElDivider>

        <ElFormItem label="QoS">
          <ElSelect v-model="form.qos" style="width: 120px">
            <ElOption label="0 - 最多一次" :value="0" />
            <ElOption label="1 - 至少一次" :value="1" />
            <ElOption label="2 - 恰好一次" :value="2" />
          </ElSelect>
        </ElFormItem>

        <ElFormItem label="等级过滤">
          <ElSelect v-model="form.alarm_levels" multiple clearable placeholder="空=全部等级" style="width: 100%">
            <ElOption v-for="l in ALARM_LEVELS" :key="l.value" :label="l.label" :value="l.value" />
          </ElSelect>
        </ElFormItem>

        <ElFormItem label="事件过滤">
          <ElSelect v-model="form.alarm_events" multiple clearable placeholder="空=全部事件" style="width: 100%">
            <ElOption v-for="e in ALARM_EVENTS" :key="e.value" :label="e.label" :value="e.value" />
          </ElSelect>
        </ElFormItem>

        <ElFormItem label="设备ID过滤">
          <ElInput v-model="form.device_ids" placeholder="如：1,2,3（逗号分隔，空=全部设备）" />
        </ElFormItem>

        <ElFormItem label="启用">
          <ElSwitch v-model="form.enabled" />
        </ElFormItem>
      </ElForm>

      <template #footer>
        <ElButton @click="dialogVisible.value = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
