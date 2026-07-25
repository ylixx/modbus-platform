<script setup lang="ts">
/**
 * 化验数据管理 & 对比分析
 *
 * 功能：
 * 1. 录入化验数据（设备 + 点位 + 化验值 + 采样时间）
 * 2. 化验值 vs 采集均值对比表
 * 3. 偏差分析（正常/偏差/异常）
 * 4. 对比时间窗口可调
 */
import { ref, reactive, onMounted, computed } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElSelect,
  ElOption,
  ElInput,
  ElInputNumber,
  ElDatePicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElMessage,
  ElMessageBox,
  ElEmpty,
  ElAlert,
  ElDescriptions,
  ElDescriptionsItem
} from 'element-plus'
import {
  getAllDevices,
  getDeviceTags,
  getLabData,
  createLabData,
  deleteLabData,
  compareLabData,
  unwrap,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'LabCompare' })

// ── 设备/点位 ──
const devices = ref<any[]>([])
const labDevices = computed(() => devices.value.filter((d) => d.has_lab_data))
const tags = ref<any[]>([])
const currentDevice = ref<number | undefined>(undefined)
const currentTag = ref<number | undefined>(undefined)
const loading = ref(false)

const fetchDevices = async () => {
  devices.value = unwrapList(await getAllDevices()).list
}
const onDeviceChange = async (deviceId: number) => {
  currentTag.value = undefined
  tags.value = []
  if (!deviceId) return
  const res = await getDeviceTags(deviceId)
  const body = unwrap(res)
  tags.value = Array.isArray(body) ? body : unwrapList(res).list
}

// ── 对比数据 ──
const compareWindow = ref(86400) // 默认日均对比
const compareData = ref<any[]>([])
const compareLoading = ref(false)

const windowOptions = [
  { label: '时均对比（1小时）', value: 3600 },
  { label: '日均对比（24小时）', value: 86400 },
  { label: '12小时对比', value: 43200 },
  { label: '2小时对比', value: 7200 },
  { label: '30分钟对比', value: 1800 }
]

const fetchCompare = async () => {
  if (!currentDevice.value) {
    ElMessage.warning('请先选择设备')
    return
  }
  compareLoading.value = true
  try {
    const res = await compareLabData({
      device_id: currentDevice.value,
      tag_id: currentTag.value || undefined,
      compare_window: compareWindow.value
    })
    const body = (res as any)?.data || res
    compareData.value = body?.data || []
  } catch (e: any) {
    ElMessage.error(e?.message || '查询失败')
  } finally {
    compareLoading.value = false
  }
}

const statusTag = (s: string) => {
  if (s === 'normal') return { type: 'success', text: '正常' }
  if (s === 'warning') return { type: 'warning', text: '偏差' }
  if (s === 'abnormal') return { type: 'danger', text: '异常' }
  return { type: 'info', text: '无数据' }
}

// ── 录入化验数据 ──
const entryDialogVisible = ref(false)
const entryFormRef = ref()
const entryForm = reactive({
  device_id: null as number | null,
  tag_id: null as number | null,
  lab_name: '',
  lab_value: null as number | null,
  unit: '',
  sample_time: '',
  operator: '',
  remark: ''
})
const entryRules = {
  device_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  lab_name: [{ required: true, message: '请输入化验项目名', trigger: 'blur' }],
  lab_value: [{ required: true, message: '请输入化验值', trigger: 'blur' }],
  sample_time: [{ required: true, message: '请选择采样时间', trigger: 'change' }]
}

const openEntry = () => {
  Object.assign(entryForm, {
    device_id: currentDevice.value || null,
    tag_id: currentTag.value || null,
    lab_name: '', lab_value: null, unit: '',
    sample_time: '', operator: '', remark: ''
  })
  entryDialogVisible.value = true
}

const submitEntry = async () => {
  await entryFormRef.value?.validate()
  await createLabData({
    device_id: entryForm.device_id,
    tag_id: entryForm.tag_id || null,
    lab_name: entryForm.lab_name,
    lab_value: entryForm.lab_value,
    unit: entryForm.unit,
    sample_time: entryForm.sample_time,
    operator: entryForm.operator,
    remark: entryForm.remark
  })
  ElMessage.success('化验数据录入成功')
  entryDialogVisible.value = false
  fetchCompare()
}

const removeEntry = async (row: any) => {
  await ElMessageBox.confirm('确认删除此化验记录？', '提示', { type: 'warning' })
  await deleteLabData(row.id)
  ElMessage.success('删除成功')
  fetchCompare()
}

// ── 统计 ──
const stats = computed(() => {
  const total = compareData.value.length
  const normal = compareData.value.filter((d) => d.status === 'normal').length
  const warning = compareData.value.filter((d) => d.status === 'warning').length
  const abnormal = compareData.value.filter((d) => d.status === 'abnormal').length
  return { total, normal, warning, abnormal }
})

onMounted(fetchDevices)
</script>

<template>
  <div>
    <ContentWrap title="化验数据对比">
      <ElAlert
        title="化验数据与自动采集数据对比分析。选择设备后查看化验记录与采集均值的偏差。"
        type="info"
        :closable="false"
        class="mb-16px"
      />

      <!-- 筛选条件 -->
      <div class="flex items-center gap-12px mb-16px flex-wrap">
        <span class="text-13px text-gray-500">设备：</span>
        <ElSelect
          v-model="currentDevice"
          class="!w-200px"
          placeholder="选择设备"
          filterable
          @change="onDeviceChange"
        >
          <ElOption v-for="d in labDevices" :key="d.id" :label="d.name" :value="d.id" />
        </ElSelect>

        <span class="text-13px text-gray-500">点位：</span>
        <ElSelect
          v-model="currentTag"
          class="!w-180px"
          clearable
          placeholder="全部点位"
          :disabled="!currentDevice"
        >
          <ElOption v-for="t in tags" :key="t.id" :label="t.name" :value="t.id" />
        </ElSelect>

        <span class="text-13px text-gray-500">对比方式：</span>
        <ElSelect v-model="compareWindow" class="!w-180px">
          <ElOption v-for="o in windowOptions" :key="o.value" :label="o.label" :value="o.value" />
        </ElSelect>

        <ElButton type="primary" :loading="compareLoading" @click="fetchCompare">查询对比</ElButton>
        <ElButton v-hasPermi="['history.write']" type="success" @click="openEntry">录入化验数据</ElButton>
      </div>

      <!-- 统计卡片 -->
      <div v-if="compareData.length" class="flex gap-16px mb-16px">
        <div class="flex-1 bg-gray-50 rounded p-12px text-center">
          <div class="text-20px font-700">{{ stats.total }}</div>
          <div class="text-12px text-gray-500">总记录</div>
        </div>
        <div class="flex-1 bg-green-50 rounded p-12px text-center">
          <div class="text-20px font-700 text-green-600">{{ stats.normal }}</div>
          <div class="text-12px text-gray-500">正常 (≤5%)</div>
        </div>
        <div class="flex-1 bg-yellow-50 rounded p-12px text-center">
          <div class="text-20px font-700 text-yellow-600">{{ stats.warning }}</div>
          <div class="text-12px text-gray-500">偏差 (5~15%)</div>
        </div>
        <div class="flex-1 bg-red-50 rounded p-12px text-center">
          <div class="text-20px font-700 text-red-600">{{ stats.abnormal }}</div>
          <div class="text-12px text-gray-500">异常 (>15%)</div>
        </div>
      </div>

      <!-- 对比表格 -->
      <ElEmpty v-if="!compareLoading && !compareData.length" description="暂无化验对比数据" />
      <ElTable v-else v-loading="compareLoading" :data="compareData" border stripe>
        <ElTableColumn prop="sample_time" label="采样时间" width="170">
          <template #default="{ row }">{{ row.sample_time?.replace('T', ' ').slice(0, 19) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="lab_name" label="化验项目" width="120" />
        <ElTableColumn prop="tag_name" label="对应点位" width="120" show-overflow-tooltip />
        <ElTableColumn label="化验值" width="100">
          <template #default="{ row }">
            <span class="font-700">{{ row.lab_value }}</span>
            <span class="text-12px text-gray-400 ml-2px">{{ row.unit }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="采集均值" width="110">
          <template #default="{ row }">
            <span v-if="row.collected_avg != null" class="font-700 text-blue-500">
              {{ row.collected_avg }}
            </span>
            <span v-else class="text-gray-400">—</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="偏差" width="100">
          <template #default="{ row }">
            <span v-if="row.deviation != null">{{ row.deviation }}</span>
            <span v-else class="text-gray-400">—</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="偏差率" width="100">
          <template #default="{ row }">
            <span
              v-if="row.deviation_pct != null"
              :class="{
                'text-green-600': row.status === 'normal',
                'text-yellow-600': row.status === 'warning',
                'text-red-600': row.status === 'abnormal'
              }"
            >
              {{ row.deviation_pct }}%
            </span>
            <span v-else class="text-gray-400">—</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="90">
          <template #default="{ row }">
            <ElTag :type="statusTag(row.status).type" size="small">
              {{ statusTag(row.status).text }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="operator" label="化验员" width="90" />
        <ElTableColumn label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <ElButton v-hasPermi="['history.write']" link type="danger" @click="removeEntry(row)"
              >删除</ElButton
            >
          </template>
        </ElTableColumn>
      </ElTable>
    </ContentWrap>

    <!-- 录入对话框 -->
    <ElDialog v-model="entryDialogVisible" title="录入化验数据" width="500px">
      <ElForm ref="entryFormRef" :model="entryForm" :rules="entryRules" label-width="100px">
        <ElFormItem label="设备" prop="device_id">
          <ElSelect v-model="entryForm.device_id" class="w-full" filterable @change="(v: number) => { entryForm.tag_id = null; onDeviceChange(v) }">
            <ElOption v-for="d in labDevices" :key="d.id" :label="d.name" :value="d.id" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="对应点位">
          <ElSelect v-model="entryForm.tag_id" class="w-full" clearable filterable :disabled="!entryForm.device_id">
            <ElOption v-for="t in tags" :key="t.id" :label="`${t.name} (${t.unit || ''})`" :value="t.id" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="化验项目" prop="lab_name">
          <ElInput v-model="entryForm.lab_name" placeholder="如 COD、氨氮、pH" />
        </ElFormItem>
        <ElFormItem label="化验值" prop="lab_value">
          <ElInputNumber v-model="entryForm.lab_value" :precision="4" class="w-full" />
        </ElFormItem>
        <ElFormItem label="单位">
          <ElInput v-model="entryForm.unit" placeholder="如 mg/L、℃" />
        </ElFormItem>
        <ElFormItem label="采样时间" prop="sample_time">
          <ElDatePicker
            v-model="entryForm.sample_time"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            class="w-full"
          />
        </ElFormItem>
        <ElFormItem label="化验员">
          <ElInput v-model="entryForm.operator" />
        </ElFormItem>
        <ElFormItem label="备注">
          <ElInput v-model="entryForm.remark" type="textarea" :rows="2" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="entryDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitEntry">录入</ElButton>
      </template>
    </ElDialog>
  </div>
</template>
