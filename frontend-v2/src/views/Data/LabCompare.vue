<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
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
  ElPagination,
  ElBadge
} from 'element-plus'
import OrgCascadeSelect from '@/components/OrgCascadeSelect.vue'
import type { OrgPath } from '@/api/hierarchy'
import {
  getDevices,
  getDeviceTags,
  getLabData,
  createLabData,
  deleteLabData,
  compareLabData,
  unwrap,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'LabCompare' })

// ── 组织级联筛选 ──
const cascadeRef = ref()
const orgPath = ref<OrgPath | null>(null)
const onPathChange = (path: OrgPath | null) => {
  orgPath.value = path
  // 组织变化 → 重置设备/点位 → 重新加载数据
  currentDevice.value = undefined
  currentTag.value = undefined
  tags.value = []
  allPage.value = 1
  fetchAllLabData()
}

// ── 设备/点位 ──
const deviceOptions = ref<any[]>([])
const loadingDevices = ref(false)
const tags = ref<any[]>([])
const currentDevice = ref<number | undefined>(undefined)
const currentTag = ref<number | undefined>(undefined)

// 设备远程搜索（替代预读 500 条）
const remoteSearchDevices = async (query: string) => {
  loadingDevices.value = true
  try {
    const params: any = { page: 1, page_size: 50, has_lab_data: true }
    if (orgPath.value?.org_node_id) params.org_node_id = orgPath.value.org_node_id
    if (query) params.search = query
    const res = await getDevices(params)
    deviceOptions.value = unwrapList(res).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取设备列表失败')
  } finally {
    loadingDevices.value = false
  }
}

const onDeviceChange = async (deviceId: number) => {
  currentTag.value = undefined
  tags.value = []
  if (!deviceId) return
  try {
    const res = await getDeviceTags(deviceId)
    const body = unwrap(res)
    tags.value = Array.isArray(body) ? body : unwrapList(res).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取点位列表失败')
  }
}

// ── 默认列表（所有化验数据，按设备分组 + 分页） ──
const listMode = ref<'all' | 'compare'>('all')
const allLoading = ref(false)
const allData = ref<any[]>([])
const allTotal = ref(0)
const allPage = ref(1)
const allPageSize = ref(30)

const fetchAllLabData = async () => {
  allLoading.value = true
  try {
    const params: any = { page: allPage.value, page_size: allPageSize.value, compare_window: compareWindow.value }
    if (orgPath.value?.org_node_id) params.org_node_id = orgPath.value.org_node_id
    if (currentDevice.value != null) params.device_id = currentDevice.value
    const res = await getLabData(params)
    const body = unwrap(res)
    allTotal.value = body?.total ?? 0
    allData.value = body?.data ?? []
  } catch (e: any) {
    ElMessage.error(e?.message || '加载化验数据失败')
  } finally {
    allLoading.value = false
  }
}

const groupedData = computed(() => {
  const map = new Map<number, any>()
  for (const item of allData.value) {
    const key = item.device_id
    if (!map.has(key)) {
      map.set(key, {
        device_id: key,
        device_name: item.device_name,
        children: []
      })
    }
    const parent = map.get(key)!
    parent.children.push({
      ...item,
      rowKey: `lab-${item.id}`
    })
  }

  const result: any[] = []
  for (const [key, group] of map) {
    if (group.children.length <= 1) {
      const child = group.children[0]
      if (child) {
        result.push({
          ...child,
          device_name: group.device_name,
          rowKey: `flat-${key}`,
          isDevice: false,
          isFlat: true
        })
      }
    } else {
      const first = group.children[0]
      result.push({
        ...first,
        rowKey: `device-${key}`,
        device_id: key,
        device_name: group.device_name,
        isDevice: true,
        isFlat: false,
        showFirst: true,
        children: group.children.map((c: any) => ({
          ...c,
          isDevice: false,
          isFlat: false
        }))
      })
    }
  }
  return result
})

const onAllPageChange = (page: number) => {
  allPage.value = page
  fetchAllLabData()
}

const onAllPageSizeChange = (size: number) => {
  allPageSize.value = size
  allPage.value = 1
  fetchAllLabData()
}

// ── 对比数据 ──
const compareWindow = ref(86400)
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
  listMode.value = 'compare'
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

const backToAll = () => {
  listMode.value = 'all'
  compareData.value = []
  allPage.value = 1
  fetchAllLabData()
}

const statusTag = (s: string): { type: 'success' | 'warning' | 'danger' | 'info'; text: string } => {
  if (s === 'normal') return { type: 'success', text: '正常' }
  if (s === 'warning') return { type: 'warning', text: '偏差' }
  if (s === 'abnormal') return { type: 'danger', text: '异常' }
  return { type: 'info', text: '无数据' }
}

// ── 录入化验数据 ──
const entryDialogVisible = ref(false)
const entryFormRef = ref()
const entryForm = reactive({
  device_id: undefined as number | undefined,
  tag_id: undefined as number | undefined,
  lab_name: '',
  lab_value: undefined as number | undefined,
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
    device_id: currentDevice.value || undefined,
    tag_id: currentTag.value || undefined,
    lab_name: '', lab_value: undefined, unit: '',
    sample_time: '', operator: '', remark: ''
  })
  entryDialogVisible.value = true
}

const submitEntry = async () => {
  try {
    await entryFormRef.value?.validate()
    await createLabData({
      device_id: entryForm.device_id,
      tag_id: entryForm.tag_id || undefined,
      lab_name: entryForm.lab_name,
      lab_value: entryForm.lab_value,
      unit: entryForm.unit,
      sample_time: entryForm.sample_time,
      operator: entryForm.operator,
      remark: entryForm.remark
    })
    ElMessage.success('化验数据录入成功')
    entryDialogVisible.value = false
    if (listMode.value === 'compare') {
      fetchCompare()
    } else {
      fetchAllLabData()
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '录入失败')
  }
}

const removeEntry = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认删除此化验记录？', '提示', { type: 'warning' })
    await deleteLabData(row.id)
    ElMessage.success('删除成功')
    if (listMode.value === 'compare') {
      fetchCompare()
    } else {
      fetchAllLabData()
    }
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}

// ── 统计 ──
const stats = computed(() => {
  const data = listMode.value === 'compare' ? compareData.value : allData.value
  const total = data.length
  const normal = data.filter((d) => d.status === 'normal').length
  const warning = data.filter((d) => d.status === 'warning').length
  const abnormal = data.filter((d) => d.status === 'abnormal').length
  return { total, normal, warning, abnormal }
})

watch(compareWindow, () => {
  if (listMode.value === 'all' && allData.value.length > 0) {
    fetchAllLabData()
  }
})

onMounted(async () => {
  // 初始加载设备选项（供录入对话框使用）+ 化验数据
  remoteSearchDevices('')
  fetchAllLabData()
})
</script>

<template>
  <div>
    <ContentWrap title="化验数据对比">
      <!-- 组织级联 + 设备/点位筛选 -->
      <OrgCascadeSelect
        ref="cascadeRef"
        :show-device-select="false"
        :show-device-actions="false"
        v-model:path="orgPath"
        @update:path="onPathChange"
        class="mb-12px"
      />

      <ElAlert
        v-if="listMode === 'all'"
        title="默认展示所有开启了化验数据的设备，同一设备的化验记录自动折叠。点击「查询对比」可进入对比分析模式。"
        type="info"
        :closable="false"
        class="mb-16px"
      />
      <ElAlert
        v-else
        title="对比分析模式：化验值与自动采集均值对比。点击「返回全部」回到列表模式。"
        type="success"
        :closable="false"
        class="mb-16px"
      />

      <!-- 筛选条件 -->
      <div class="flex items-center gap-12px mb-16px flex-wrap">
        <span class="text-13px text-gray-500">设备：</span>
        <ElSelect
          v-model="currentDevice"
          class="!w-200px"
          placeholder="输入设备名搜索"
          filterable
          remote
          :remote-method="remoteSearchDevices"
          :loading="loadingDevices"
          clearable
          @change="onDeviceChange"
        >
          <ElOption v-for="d in deviceOptions" :key="d.id" :label="d.name" :value="d.id" />
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
        <ElButton v-if="listMode === 'compare'" @click="backToAll">返回全部</ElButton>
        <ElButton v-hasPermi="['history.write']" type="success" @click="openEntry">录入化验数据</ElButton>
      </div>

      <!-- 统计卡片 -->
      <div v-if="listMode === 'compare' && compareData.length" class="flex gap-16px mb-16px">
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

      <!-- 默认列表：按设备分组折叠 -->
      <template v-if="listMode === 'all'">
        <ElEmpty v-if="!allLoading && !groupedData.length" description="暂无化验数据，请录入或开启设备的化验数据功能" />
        <ElTable
          v-else
          v-loading="allLoading"
          :data="groupedData"
          row-key="rowKey"
          :tree-props="{ children: 'children' }"
          :default-expand-all="false"
          border
          stripe
        >
          <ElTableColumn label="设备 / 化验项目" min-width="220">
            <template #default="{ row }">
              <div v-if="row.isDevice" class="flex flex-col">
                <div class="flex items-center gap-8px">
                  <ElBadge :value="row.children.length" type="primary" :max="99" />
                  <span class="font-600 text-15px">{{ row.device_name }}</span>
                  <span class="text-12px text-gray-400">({{ row.children.length }} 条)</span>
                </div>
                <span v-if="row.showFirst && row.lab_name" class="text-12px text-gray-500 pl-32px">{{ row.lab_name }}</span>
              </div>
              <div v-else-if="row.isFlat" class="flex flex-col">
                <span class="font-600 text-14px">{{ row.device_name }}</span>
                <span class="text-12px text-gray-500">{{ row.lab_name }}</span>
              </div>
              <div v-else class="pl-24px text-13px">{{ row.lab_name }}</div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="点位" width="140">
            <template #default="{ row }">
              <span v-if="row.isDevice && !row.showFirst" class="text-gray-300">—</span>
              <span v-else>{{ row.tag_name || '—' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="化验值" width="120">
            <template #default="{ row }">
              <span v-if="row.isDevice && !row.showFirst" class="text-gray-300">—</span>
              <span v-else>
                <span class="font-700">{{ row.lab_value }}</span>
                <span class="text-12px text-gray-400 ml-2px">{{ row.unit }}</span>
              </span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="采集均值" width="110">
            <template #default="{ row }">
              <span v-if="row.isDevice && !row.showFirst" class="text-gray-300">—</span>
              <span v-else-if="row.collected_avg != null" class="font-700 text-blue-500">
                {{ row.collected_avg }}
              </span>
              <span v-else class="text-gray-400">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="偏差" width="90">
            <template #default="{ row }">
              <span v-if="row.isDevice && !row.showFirst" class="text-gray-300">—</span>
              <span v-else-if="row.deviation != null">{{ row.deviation }}</span>
              <span v-else class="text-gray-400">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="偏差率" width="100">
            <template #default="{ row }">
              <span v-if="row.isDevice && !row.showFirst" class="text-gray-300">—</span>
              <span
                v-else-if="row.deviation_pct != null"
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
              <span v-if="row.isDevice && !row.showFirst" class="text-gray-300">—</span>
              <ElTag v-else-if="row.status" :type="statusTag(row.status).type" size="small">
                {{ statusTag(row.status).text }}
              </ElTag>
              <span v-else class="text-gray-400">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn sortable prop="sample_time" label="采样时间" width="160">
            <template #default="{ row }">
              <span v-if="row.isDevice && !row.showFirst" class="text-gray-300">—</span>
              <span v-else>{{ row.sample_time?.replace('T', ' ').slice(0, 19) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn sortable prop="operator" label="化验员" width="90">
            <template #default="{ row }">
              <span v-if="row.isDevice && !row.showFirst" class="text-gray-300">—</span>
              <span v-else>{{ row.operator || '—' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn sortable prop="remark" label="备注" min-width="100" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.isDevice && !row.showFirst" class="text-gray-300">—</span>
              <span v-else>{{ row.remark || '—' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <ElButton
                v-if="!row.isDevice"
                v-hasPermi="['history.write']"
                link
                type="danger"
                @click="removeEntry(row)"
              >删除</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>

        <div class="flex justify-end mt-16px" v-if="allTotal > 0">
          <ElPagination
            v-model:current-page="allPage"
            :page-size="allPageSize"
            :total="allTotal"
            :page-sizes="[30, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @current-change="onAllPageChange"
            @size-change="onAllPageSizeChange"
          />
        </div>
      </template>

      <!-- 对比模式表格 -->
      <template v-else>
        <ElEmpty v-if="!compareLoading && !compareData.length" description="暂无对比数据，请选择设备并点击查询对比" />
        <ElTable v-else v-loading="compareLoading" :data="compareData" border stripe>
          <ElTableColumn sortable prop="sample_time" label="采样时间" width="170">
            <template #default="{ row }">{{ row.sample_time?.replace('T', ' ').slice(0, 19) }}</template>
          </ElTableColumn>
          <ElTableColumn sortable prop="lab_name" label="化验项目" width="120" />
          <ElTableColumn sortable prop="tag_name" label="对应点位" width="120" show-overflow-tooltip />
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
          <ElTableColumn sortable prop="operator" label="化验员" width="90" />
          <ElTableColumn label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <ElButton v-hasPermi="['history.write']" link type="danger" @click="removeEntry(row)"
                >删除</ElButton
              >
            </template>
          </ElTableColumn>
        </ElTable>
      </template>
    </ContentWrap>

    <!-- 录入对话框 -->
    <ElDialog v-model="entryDialogVisible" title="录入化验数据" width="500px" @close="entryFormRef?.resetFields()">
      <ElForm ref="entryFormRef" :model="entryForm" :rules="entryRules" label-width="100px">
        <ElFormItem label="设备" prop="device_id">
          <ElSelect
            v-model="entryForm.device_id"
            class="w-full"
            filterable
            remote
            :remote-method="remoteSearchDevices"
            :loading="loadingDevices"
            @change="(v: number) => { entryForm.tag_id = undefined; onDeviceChange(v) }"
          >
            <ElOption v-for="d in deviceOptions" :key="d.id" :label="d.name" :value="d.id" />
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
