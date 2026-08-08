<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import OrgCascadeSelect from '@/components/OrgCascadeSelect.vue'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElInputNumber,
  ElSwitch,
  ElMessage,
  ElMessageBox,
  ElDivider,
  ElPagination,
  ElTabs,
  ElTabPane
} from 'element-plus'
import {
  getAlarmRules,
  createAlarmRule,
  updateAlarmRule,
  deleteAlarmRule,
  getEscalationConfig,
  updateEscalationConfig,
  getDeviceTags,
  unwrap,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'AlarmRules' })

const activeTab = ref('rules')
const loading = ref(false)
const list = ref<any[]>([])
const deviceTags = ref<any[]>([])

// ── 分页 ──
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// ── 报警类型选项 ──
const alarmTypes = [
  { value: 'threshold_high', label: '上限报警', desc: '值超过高限时触发' },
  { value: 'threshold_low', label: '下限报警', desc: '值低于低限时触发' },
  { value: 'threshold_range', label: '区间报警', desc: '值超出高低限区间时触发' },
  { value: 'rate_of_change', label: '变化率报警', desc: '值变化速率超限时触发' },
  { value: 'status', label: '状态报警', desc: '值等于目标值时触发' },
  { value: 'disconnect', label: '设备离线', desc: '设备离线时触发' }
]

const alarmLevels = [
  { value: 'info', label: '提示', type: 'info' },
  { value: 'warning', label: '警告', type: 'warning' },
  { value: 'critical', label: '严重', type: 'danger' },
  { value: 'emergency', label: '紧急', type: 'danger' }
]

const alarmTypeLabel = (t?: string) => alarmTypes.find((a) => a.value === t)?.label || t || '—'
const alarmLevelType = (l?: string) => alarmLevels.find((a) => a.value === l)?.type || 'info'
const alarmLevelLabel = (l?: string) => alarmLevels.find((a) => a.value === l)?.label || l || '—'

const fetchList = async () => {
  loading.value = true
  try {
    const res = unwrapList(await getAlarmRules({ page: page.value, page_size: pageSize.value }))
    list.value = res.list
    total.value = res.total
  } catch (e: any) {
    ElMessage.error(e?.message || '获取报警规则失败')
  } finally {
    loading.value = false
  }
}
const onPageChange = (p: number) => {
  page.value = p
  fetchList()
}
const onSizeChange = (s: number) => {
  pageSize.value = s
  page.value = 1
  fetchList()
}

// ── 设备 → 点位联动 ──
const onFormDeviceChange = async (deviceId: number) => {
  form.tag_id = null
  deviceTags.value = []
  if (!deviceId) return
  try {
    const res = await getDeviceTags(deviceId)
    const body = unwrap(res)
    deviceTags.value = Array.isArray(body) ? body : unwrapList(res).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取点位列表失败')
  }
}

// ── 表单 ──
const dialogVisible = ref(false)
const dialogTitle = ref('新增规则')
const formRef = ref()
const form = reactive<any>({
  id: null,
  name: '',
  description: '',
  device_id: null,
  tag_id: null,
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
const rules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  device_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  alarm_type: [{ required: true, message: '请选择报警类型', trigger: 'change' }],
  alarm_level: [{ required: true, message: '请选择报警级别', trigger: 'change' }]
}

// 根据报警类型显示/隐藏字段
const showHighLimit = computed(() => ['threshold_high', 'threshold_range'].includes(form.alarm_type))
const showLowLimit = computed(() => ['threshold_low', 'threshold_range'].includes(form.alarm_type))
const showRateLimit = computed(() => form.alarm_type === 'rate_of_change')
const showStatusValue = computed(() => form.alarm_type === 'status')
const showDeadband = computed(() =>
  ['threshold_high', 'threshold_low', 'threshold_range'].includes(form.alarm_type)
)

const openCreate = () => {
  dialogTitle.value = '新增规则'
  Object.assign(form, {
    id: null,
    name: '',
    description: '',
    device_id: null,
    tag_id: null,
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
  deviceTags.value = []
  dialogVisible.value = true
}
const openEdit = async (row: any) => {
  dialogTitle.value = '编辑规则'
  Object.assign(form, {
    id: row.id,
    name: row.name,
    description: row.description || '',
    device_id: row.device_id,
    tag_id: row.tag_id ?? null,
    alarm_type: row.alarm_type || 'threshold_high',
    alarm_level: row.alarm_level || 'warning',
    high_limit: row.high_limit ?? null,
    low_limit: row.low_limit ?? null,
    deadband: row.deadband ?? 0,
    rate_limit: row.rate_limit ?? null,
    status_value: row.status_value ?? null,
    delay_seconds: row.delay_seconds ?? 0,
    auto_clear: row.auto_clear !== false,
    sms_enabled: !!row.sms_enabled,
    enabled: row.enabled !== false
  })
  // 加载设备的点位列表
  if (form.device_id) {
    await onFormDeviceChange(form.device_id)
  }
  dialogVisible.value = true
}
const submit = async () => {
  try {
    await formRef.value?.validate()
    // 根据报警类型动态校验条件字段
    if (['threshold_high', 'threshold_range'].includes(form.alarm_type) && form.high_limit == null) {
      ElMessage.warning('上限报警类型必须填写上限值')
      return
    }
    if (['threshold_low', 'threshold_range'].includes(form.alarm_type) && form.low_limit == null) {
      ElMessage.warning('下限报警类型必须填写下限值')
      return
    }
    if (form.alarm_type === 'rate_of_change' && form.rate_limit == null) {
      ElMessage.warning('变化率报警类型必须填写变化率限制')
      return
    }
    const payload: any = {
      name: form.name,
      description: form.description,
      device_id: form.device_id,
      tag_id: form.tag_id || null,
      alarm_type: form.alarm_type,
      alarm_level: form.alarm_level,
      high_limit: form.high_limit,
      low_limit: form.low_limit,
      deadband: form.deadband || 0,
      rate_limit: form.rate_limit,
      status_value: form.status_value,
      delay_seconds: form.delay_seconds || 0,
      auto_clear: form.auto_clear,
      sms_enabled: form.sms_enabled,
      enabled: form.enabled !== false
    }
    if (form.id) {
      await updateAlarmRule(form.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createAlarmRule(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}
const remove = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除规则「${row.name}」？`, '提示', { type: 'warning' })
    await deleteAlarmRule(row.id)
    ElMessage.success('删除成功')
    fetchList()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}

// ── 升级配置 ──
const escalationConfig = reactive<any>({
  info: 30,
  warning: 15,
  critical: 10,
  emergency: 0
})
const escalationLoading = ref(false)

const fetchEscalationConfig = async () => {
  try {
    const res = unwrap(await getEscalationConfig())
    if (res && typeof res === 'object') {
      Object.assign(escalationConfig, res)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '获取升级配置失败')
  }
}

const saveEscalationConfig = async () => {
  escalationLoading.value = true
  try {
    const res = unwrap(await updateEscalationConfig({ ...escalationConfig }))
    if (res && typeof res === 'object') {
      Object.assign(escalationConfig, res)
    }
    ElMessage.success('升级配置已保存')
  } catch (e: any) {
    ElMessage.error(e?.message || '保存升级配置失败')
  } finally {
    escalationLoading.value = false
  }
}

const escalationItems = computed(() => [
  { key: 'info', label: '提示 → 警告', desc: '提示级别报警持续未确认后升级为警告' },
  { key: 'warning', label: '警告 → 严重', desc: '警告级别报警持续未确认后升级为严重' },
  { key: 'critical', label: '严重 → 紧急', desc: '严重级别报警持续未确认后升级为紧急' },
  { key: 'emergency', label: '紧急 (无升级)', desc: '紧急级别为最高等级，无法继续升级' }
])

onMounted(() => {
  fetchList()
  fetchEscalationConfig()
})
</script>

<template>
  <ContentWrap title="报警规则">
    <template #header>
      <div class="flex-grow flex justify-end">
        <ElButton v-hasPermi="['alarm.write']" type="success" @click="openCreate"
          >新增规则</ElButton
        >
      </div>
    </template>
    <ElTabs v-model="activeTab">
      <ElTabPane label="报警规则" name="rules">
    <ElTable v-loading="loading" :data="list" border stripe>
      <template #empty>
        <div class="py-20px text-center text-gray-400">暂无报警规则</div>
      </template>
      <ElTableColumn sortable prop="id" label="ID" width="60" />
      <ElTableColumn sortable prop="name" label="规则名称" min-width="140" show-overflow-tooltip />
      <ElTableColumn label="设备" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.device_name || `#${row.device_id}` }}
        </template>
      </ElTableColumn>
      <ElTableColumn label="点位" min-width="100" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.tag_id ? `#${row.tag_id}` : '全部' }}
        </template>
      </ElTableColumn>
      <ElTableColumn label="类型" width="100">
        <template #default="{ row }">
          <ElTag size="small">{{ alarmTypeLabel(row.alarm_type) }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="级别" width="80">
        <template #default="{ row }">
          <ElTag :type="(alarmLevelType(row.alarm_level) as any)" size="small">
            {{ alarmLevelLabel(row.alarm_level) }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="条件" min-width="140">
        <template #default="{ row }">
          <span v-if="row.high_limit != null">上限: {{ row.high_limit }}</span>
          <span v-if="row.low_limit != null"> 下限: {{ row.low_limit }}</span>
          <span v-if="row.rate_limit != null">变化率: {{ row.rate_limit }}/s</span>
          <span v-if="row.status_value != null">== {{ row.status_value }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="延迟" width="70">
        <template #default="{ row }">
          {{ row.delay_seconds || 0 }}s
        </template>
      </ElTableColumn>
      <ElTableColumn label="启用" width="70">
        <template #default="{ row }">
          <ElTag :type="row.enabled !== false ? 'success' : 'info'" size="small">{{
            row.enabled !== false ? '是' : '否'
          }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <ElButton v-hasPermi="['alarm.write']" link type="primary" @click="openEdit(row)"
            >编辑</ElButton
          >
          <ElButton v-hasPermi="['alarm.write']" link type="danger" @click="remove(row)"
            >删除</ElButton
          >
        </template>
      </ElTableColumn>
      </ElTable>
      <div class="flex justify-end mt-12px">
        <ElPagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
      </ElTabPane>

      <ElTabPane label="升级配置" name="escalation">
        <div class="mb-12px text-13px text-gray-400">
          配置各等级报警未确认时自动升级的超时时间（分钟）。超时后系统将自动将报警升级到更高等级并发送短信通知。
        </div>
        <ElForm label-width="160px" class="max-w-600px">
          <ElFormItem
            v-for="item in escalationItems"
            :key="item.key"
            :label="item.label"
          >
            <ElInputNumber
              v-model="escalationConfig[item.key]"
              :min="0"
              :max="1440"
              :step="5"
              :disabled="item.key === 'emergency'"
              class="w-200px"
            />
            <span class="text-12px text-gray-400 ml-8px">分钟</span>
            <div class="text-12px text-gray-400 ml-12px">{{ item.desc }}</div>
          </ElFormItem>
          <ElFormItem>
            <ElButton
              v-hasPermi="['alarm.write']"
              type="primary"
              :loading="escalationLoading"
              @click="saveEscalationConfig"
            >保存配置</ElButton>
          </ElFormItem>
        </ElForm>
      </ElTabPane>
    </ElTabs>

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="660px" top="5vh" @close="formRef?.resetFields()">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="100px">
        <!-- 基本信息 -->
        <ElFormItem label="规则名称" prop="name">
          <ElInput v-model="form.name" placeholder="如：1号炉温度上限" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="form.description" type="textarea" :rows="2" placeholder="可选描述" />
        </ElFormItem>

        <ElDivider content-position="left">监控目标</ElDivider>

        <ElFormItem label="设备" prop="device_id">
          <OrgCascadeSelect
            v-model="form.device_id"
            single
            :show-device-actions="false"
            :show-actions="false"
            class="w-full"
            placeholder="选择组织层级后搜索设备"
            @change="onFormDeviceChange"
          />
        </ElFormItem>
        <ElFormItem label="点位" prop="tag_id">
          <ElSelect
            v-model="form.tag_id"
            class="w-full"
            clearable
            placeholder="全部点位（不选则监控整个设备）"
            :disabled="!form.device_id"
          >
            <ElOption
              v-for="t in deviceTags"
              :key="t.id"
              :label="`${t.name} (地址 ${t.address})`"
              :value="t.id"
            />
          </ElSelect>
        </ElFormItem>

        <ElDivider content-position="left">报警定义</ElDivider>

        <ElFormItem label="报警类型" prop="alarm_type">
          <ElSelect v-model="form.alarm_type" class="w-full">
            <ElOption
              v-for="t in alarmTypes"
              :key="t.value"
              :label="t.label"
              :value="t.value"
            >
              <div>
                <span>{{ t.label }}</span>
                <span class="text-12px text-gray-400 ml-8px">{{ t.desc }}</span>
              </div>
            </ElOption>
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="报警级别" prop="alarm_level">
          <ElSelect v-model="form.alarm_level" class="w-full">
            <ElOption
              v-for="l in alarmLevels"
              :key="l.value"
              :label="l.label"
              :value="l.value"
            />
          </ElSelect>
        </ElFormItem>

        <!-- 条件参数（根据类型动态显示） -->
        <ElFormItem v-if="showHighLimit" label="上限值">
          <ElInputNumber v-model="form.high_limit" :step="0.1" class="w-full" placeholder="超过此值触发报警" />
        </ElFormItem>
        <ElFormItem v-if="showLowLimit" label="下限值">
          <ElInputNumber v-model="form.low_limit" :step="0.1" class="w-full" placeholder="低于此值触发报警" />
        </ElFormItem>
        <ElFormItem v-if="showRateLimit" label="变化率限制">
          <ElInputNumber v-model="form.rate_limit" :step="0.1" class="w-full" placeholder="单位/秒" />
        </ElFormItem>
        <ElFormItem v-if="showStatusValue" label="目标状态值">
          <ElInputNumber v-model="form.status_value" :step="1" class="w-full" placeholder="等于此值时触发" />
        </ElFormItem>
        <ElFormItem v-if="showDeadband" label="死区值">
          <ElInputNumber v-model="form.deadband" :min="0" :step="0.1" class="w-full" />
          <div class="text-12px text-gray-400 mt-4px">
            防抖动：值在阈值 ± 死区范围内不触发报警
          </div>
        </ElFormItem>

        <ElDivider content-position="left">高级设置</ElDivider>

        <ElFormItem label="报警延迟">
          <ElInputNumber v-model="form.delay_seconds" :min="0" :max="3600" class="w-full" />
          <div class="text-12px text-gray-400 mt-4px">
            条件持续满足 N 秒后才触发报警（防误报）
          </div>
        </ElFormItem>
        <ElFormItem label="自动消除">
          <ElSwitch v-model="form.auto_clear" />
          <span class="text-12px text-gray-400 ml-8px">条件不满足时自动消除报警</span>
        </ElFormItem>
        <ElFormItem label="短信通知">
          <ElSwitch v-model="form.sms_enabled" />
          <span class="text-12px text-gray-400 ml-8px">触发时发送短信通知</span>
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="form.enabled" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
