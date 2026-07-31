<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, triggerRef } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElSelect,
  ElOption,
  ElTag,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSwitch,
  ElMessage,
  ElMessageBox,
  ElEmpty,
  ElPagination,
  ElTooltip,
  ElTabs,
  ElTabPane,
  ElCheckbox
} from 'element-plus'
import {
  getDevices,
  getAllDevices,
  getAllTags,
  getDeviceTags,
  getDeviceLive,
  createTag,
  updateTag,
  deleteTag,
  exportTagsCsv,
  importTags,
  unwrap,
  unwrapList
} from '@/api/modbus'
import { wsManager } from '@/utils/websocket'
import type { WsLiveValue } from '@/utils/websocket'
import OrgCascadeSelect from '@/components/OrgCascadeSelect.vue'

defineOptions({ name: 'Tags' })

const activeTab = ref('config') // config | monitor
const devices = ref<any[]>([])
const loading = ref(false)
const list = ref<any[]>([])

// ── 批量选择 ──
const selectedRows = ref<any[]>([])
const batchUnit = ref('')
const batchWritable = ref<boolean | null>(null)
const batchLoading = ref(false)
const onSelectionChange = (rows: any[]) => { selectedRows.value = rows }

// ── 实时数据 ──
const liveData = ref<Record<number, { value: any; quality: string; time: string }>>({})
const liveLoading = ref(false)

// ── 自动刷新 ──
const REFRESH_OPTIONS = [
  { label: '10秒', value: 10 },
  { label: '30秒', value: 30 },
  { label: '1分钟', value: 60 },
  { label: '5分钟', value: 300 },
  { label: '关闭', value: 0 }
]
const refreshInterval = ref(60) // 默认1分钟
let refreshTimer: ReturnType<typeof setInterval> | null = null

const QUALITY_MAP: Record<string, { text: string; type: string }> = {
  good: { text: '正常', type: 'success' },
  unknown: { text: '未知', type: 'warning' },
  stale: { text: '过期', type: 'danger' },
  bad: { text: '异常', type: 'danger' }
}

const fetchLiveData = async (showLoading = false) => {
  if (!list.value.length) return
  if (showLoading) liveLoading.value = true
  try {
    // 按设备分组，批量取每台设备的实时值
    const deviceIds = [...new Set(list.value.map((t: any) => t.device_id))]
    // 并发请求，最多8个
    const concurrency = 8
    let idx = 0
    const fetchNext = async (): Promise<void> => {
      const i = idx++
      if (i >= deviceIds.length) return
      try {
        const res = await getDeviceLive(deviceIds[i])
        const body = unwrap(res)
        const values = body?.values || {}
        // 逐条精准更新，避免整表重渲染闪屏
        for (const [tagId, info] of Object.entries(values)) {
          const v = info as any
          liveData.value[Number(tagId)] = {
            value: v.value,
            quality: v.quality || 'unknown',
            time: v.time || ''
          }
        }
        // 显式触发 ref 依赖更新，确保模板重渲染
        triggerRef(liveData)
      } catch { /* ignore */ }
      await fetchNext()
    }
    await Promise.all(Array.from({ length: Math.min(concurrency, deviceIds.length) }, () => fetchNext()))
  } finally {
    if (showLoading) liveLoading.value = false
  }
}

const setupAutoRefresh = () => {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  if (refreshInterval.value > 0) {
    refreshTimer = setInterval(() => fetchLiveData(false), refreshInterval.value * 1000)
  }
}

const onRefreshIntervalChange = () => {
  setupAutoRefresh()
}

// WebSocket 实时推送（精准更新单个tag，避免闪屏）
const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d) return
  liveData.value[d.tag_id] = { value: d.value, quality: d.quality, time: new Date().toISOString() }
  triggerRef(liveData)
}

const onBatchLive = (msg: any) => {
  const items = msg.data as WsLiveValue[]
  if (!Array.isArray(items)) return
  for (const d of items) onLiveValue({ data: d } as any)
}

// ── 分页 ──
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)

// ── 级联筛选 ──
const selectedIds = ref<number[]>([])
const orgPath = ref<{ org_node_id: number | null; labels: string[] } | null>(null)

// ── 关键词搜索 ──
const searchKeyword = ref('')

// ── 对话框中归属设备选择 ──
const dialogDeviceId = ref<number | undefined>(undefined)
const dialogDeviceOptions = ref<any[]>([])

// 当前协议（用于对话框表单字段显示，由对话框中选中的设备决定）
const currentProtocol = computed(() => {
  const targetId = dialogDeviceId.value
  // 优先从对话框选项中查找
  let d = dialogDeviceOptions.value.find((x: any) => x.id === targetId)
  // 回退到全局设备列表
  if (!d) d = devices.value.find((x: any) => x.id === targetId)
  return d?.protocol || 'modbus_tcp'
})
const isModbus = computed(() => ['modbus_tcp', 'modbus_rtu'].includes(currentProtocol.value))
const isMqtt = computed(() => currentProtocol.value === 'mqtt')
const isOpc = computed(() => currentProtocol.value === 'opc_ua')

// 回读寄存器下拉：从后端获取该设备全量点位（排除自身）
const allDeviceTags = ref<any[]>([])
const readbackOptions = computed(() => allDeviceTags.value.filter((t) => t.id !== form.id))
const fetchAllDeviceTags = async (deviceId?: number) => {
  const id = deviceId
  if (!id) { allDeviceTags.value = []; return }
  try {
    const res = await getDeviceTags(id, { page: 1, page_size: 500 })
    const body = unwrap(res)
    allDeviceTags.value = Array.isArray(body) ? body : unwrapList(res).list
  } catch { allDeviceTags.value = [] }
}

// ── 获取设备列表（用于对话框设备搜索、导出等） ──
const fetchDevices = async () => {
  try {
    devices.value = unwrapList(await getAllDevices()).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取设备列表失败')
  }
}

// ── 全局点位列表（跨设备分页） ──
const fetchTags = async () => {
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      page_size: pageSize.value
    }
    if (orgPath.value?.org_node_id) params.org_node_id = orgPath.value.org_node_id
    if (selectedIds.value.length) params.device_ids = selectedIds.value.join(',')
    if (searchKeyword.value.trim()) params.search = searchKeyword.value.trim()
    const res = await getAllTags(params)
    const { list: l, total: t } = unwrapList(res)
    list.value = l
    total.value = t
    // 加载完点位后立刻刷新实时数据（首次加loading）
    fetchLiveData(true)
  } catch (e: any) {
    ElMessage.error(e?.message || '获取点位列表失败')
  } finally {
    loading.value = false
  }
}

const onPageChange = (p: number) => {
  page.value = p
  fetchTags()
}
const onSizeChange = (s: number) => {
  pageSize.value = s
  page.value = 1
  fetchTags()
}

// 级联框搜索
const onCascadeSearch = () => {
  page.value = 1
  fetchTags()
}
// 级联框选中的设备变化 → 自动刷新点位列表
watch(selectedIds, () => {
  page.value = 1
  fetchTags()
})

// 关键词搜索
const onKeywordSearch = () => {
  page.value = 1
  fetchTags()
}
// 清空关键词也自动刷新
const onKeywordClear = () => {
  searchKeyword.value = ''
  page.value = 1
  fetchTags()
}

// ── 对话框：设备搜索（已改用本地 filterable，保留备用） ──
const remoteSearchDialogDevices = async (query: string) => {
  try {
    const params: any = { page: 1, page_size: 50 }
    if (query) params.search = query
    dialogDeviceOptions.value = unwrapList(await getDevices(params)).list
  } catch {
    dialogDeviceOptions.value = []
  }
}

// 对话框中选择设备变化时的显式处理
const onDialogDeviceChange = (_deviceId: number) => {
  // dialogDeviceId 已通过 v-model 自动更新
  // currentProtocol 是 computed，依赖 dialogDeviceId，会自动更新
  // 不再需要额外处理，本地 filterable 模式下选项始终完整
}

// ── 新增/编辑/删除 ──
const dialogVisible = ref(false)
const dialogTitle = ref('新增点位')
const formRef = ref()
const emptyForm = () => ({
  id: null,
  name: '',
  function_code: '',
  address: 0,
  data_type: 'uint16',
  mqtt_topic: '',
  mqtt_json_path: '',
  mqtt_value_type: 'float64',
  opc_node_id: '',
  opc_node_type: 'float64',
  unit: '',
  scale_factor: 1,
  writable: false,
  readback_tag_id: null
})
const form = reactive<any>(emptyForm())
const rules = computed(() => ({
  name: [{ required: true, message: '请输入点位名称', trigger: 'blur' }],
  ...(isModbus.value
    ? { function_code: [{ required: true, message: '请选择功能码', trigger: 'change' }] }
    : {}),
  ...(isMqtt.value
    ? { mqtt_topic: [{ required: true, message: '请输入订阅主题', trigger: 'blur' }] }
    : {}),
  ...(isOpc.value
    ? { opc_node_id: [{ required: true, message: '请输入节点ID', trigger: 'blur' }] }
    : {})
}))

const openCreate = () => {
  dialogTitle.value = '新增点位'
  Object.assign(form, emptyForm())
  // 默认归属设备：筛选框选中的第一个设备
  dialogDeviceId.value = selectedIds.value.length ? selectedIds.value[0] : undefined
  dialogDeviceOptions.value = [...devices.value]
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑点位'
  Object.assign(form, emptyForm(), {
    id: row.id,
    name: row.name,
    function_code: row.function_code || '',
    address: row.address ?? 0,
    data_type: row.data_type || 'uint16',
    mqtt_topic: row.mqtt_topic || '',
    mqtt_json_path: row.mqtt_json_path || '',
    mqtt_value_type: row.mqtt_value_type || 'float64',
    opc_node_id: row.opc_node_id || '',
    opc_node_type: row.opc_node_type || 'float64',
    unit: row.unit || '',
    scale_factor: row.scale_factor ?? 1,
    writable: !!row.writable,
    readback_tag_id: row.readback_tag_id ?? null
  })
  dialogDeviceId.value = row.device_id
  dialogDeviceOptions.value = [...devices.value]
  // 确保选中设备在选项中（devices 最多500条，编辑的设备可能不在分页结果中）
  const hasSelected = dialogDeviceOptions.value.some((x: any) => x.id === row.device_id)
  if (!hasSelected && row.device_name) {
    dialogDeviceOptions.value.unshift({ id: row.device_id, name: row.device_name, protocol: row.protocol || 'modbus_tcp' })
  }
  dialogVisible.value = true
}

const submit = async () => {
  await formRef.value?.validate()
  const submitDeviceId = dialogDeviceId.value
  if (!submitDeviceId) {
    ElMessage.warning('请选择归属设备')
    return
  }
  const payload = { ...form, device_id: submitDeviceId }
  delete payload.id
  try {
    if (form.id) {
      await updateTag(form.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createTag(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchTags()
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.response?.data?.message || e?.message || '保存失败'
    ElMessage.error(msg)
  }
}
const remove = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除点位「${row.name}」？`, '提示', { type: 'warning' })
    await deleteTag(row.id)
    ElMessage.success('删除成功')
    fetchTags()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}

// ── 导出/导入 ──
import { saveBlob } from '@/utils/modbus'

const exportLoading = ref(false)
const doExport = async () => {
  // 优先导出级联选中的设备，否则提示选择
  if (!selectedIds.value.length) {
    ElMessage.warning('请先选择要导出的设备')
    return
  }
  exportLoading.value = true
  try {
    const did = selectedIds.value[0]
    const res: any = await exportTagsCsv(did)
    const deviceName = devices.value.find((d) => d.id === did)?.name || 'device'
    saveBlob(res, `tags_${deviceName}_${new Date().toISOString().slice(0, 10)}.csv`)
    ElMessage.success('导出成功')
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败')
  } finally {
    exportLoading.value = false
  }
}

const importDialogVisible = ref(false)
const importLoading = ref(false)
const importResult = ref<any>(null)

const openImport = () => {
  importResult.value = null
  importDialogVisible.value = true
}

const resetImportState = () => {
  importResult.value = null
  importLoading.value = false
}

const doImport = async (opt: any) => {
  importLoading.value = true
  importResult.value = null
  try {
    const fd = new FormData()
    fd.append('file', opt.file)
    const res: any = await importTags(fd)
    const body = res?.data || res
    importResult.value = body
    ElMessage.success(`导入完成：成功 ${body?.created ?? 0} 条`)
    fetchTags()
    opt.onSuccess?.(body)
  } catch (e: any) {
    ElMessage.error(e?.message || '导入失败')
    opt.onError?.(e)
  } finally {
    importLoading.value = false
  }
}

// 对话框内切换归属设备时，联动加载回读点位下拉
watch(dialogDeviceId, (newId) => {
  if (dialogVisible.value && newId) {
    fetchAllDeviceTags(newId)
  }
})

// ── 批量修改 ──
const batchModify = async () => {
  if (!selectedRows.value.length) {
    ElMessage.warning('请先勾选要修改的点位')
    return
  }
  const hasChange = batchUnit.value !== '' || batchWritable.value !== null
  if (!hasChange) {
    ElMessage.warning('请至少设置一项要修改的字段')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认批量修改 ${selectedRows.value.length} 个点位？`,
      '批量修改',
      { type: 'warning' }
    )
  } catch { return }

  batchLoading.value = true
  try {
    const promises = selectedRows.value.map((row) => {
      const payload: any = { ...row }
      if (batchUnit.value !== '') payload.unit = batchUnit.value
      if (batchWritable.value !== null) payload.writable = batchWritable.value
      delete payload.id
      return updateTag(row.id, payload)
    })
    await Promise.all(promises)
    ElMessage.success(`批量修改 ${selectedRows.value.length} 个点位成功`)
    batchUnit.value = ''
    batchWritable.value = null
    fetchTags()
  } catch (e: any) {
    ElMessage.error(e?.message || '批量修改失败')
  } finally {
    batchLoading.value = false
  }
}

// ── 批量删除 ──
const batchRemove = async () => {
  if (!selectedRows.value.length) {
    ElMessage.warning('请先勾选要删除的点位')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认删除选中的 ${selectedRows.value.length} 个点位？此操作不可恢复。`,
      '批量删除',
      { type: 'warning' }
    )
  } catch { return }

  batchLoading.value = true
  try {
    await Promise.all(selectedRows.value.map((row) => deleteTag(row.id)))
    ElMessage.success(`批量删除 ${selectedRows.value.length} 个点位成功`)
    fetchTags()
  } catch (e: any) {
    ElMessage.error(e?.message || '批量删除失败')
  } finally {
    batchLoading.value = false
  }
}

onMounted(() => {
  fetchDevices()
  fetchTags()
  // 订阅 WebSocket 实时推送
  wsManager.on('live_value', onLiveValue)
  wsManager.on('batch_live', onBatchLive)
  // 启动自动刷新定时器
  setupAutoRefresh()
})

onUnmounted(() => {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
})
</script>

<template>
  <ContentWrap title="采集点位">
    <!-- Tab 切换：配置视图 / 监控视图 -->
    <ElTabs v-model="activeTab" class="mb-4px">
      <ElTabPane label="配置管理" name="config" />
      <ElTabPane label="实时监控" name="monitor" />
    </ElTabs>

    <!-- 组织架构级联筛选 -->
    <div class="mb-16px">
      <OrgCascadeSelect v-model="selectedIds" v-model:path="orgPath" @search="onCascadeSearch" />
    </div>

    <!-- 关键词搜索 + 操作工具栏 -->
    <div class="flex items-center mb-12px flex-wrap gap-8px">
      <ElInput
        v-model="searchKeyword"
        placeholder="搜索点位名称"
        clearable
        style="max-width: 220px"
        @keyup.enter="onKeywordSearch"
        @clear="onKeywordClear"
      />
      <ElButton type="primary" @click="onKeywordSearch">搜索</ElButton>
      <span class="flex-grow" />

      <!-- 配置视图工具栏 -->
      <template v-if="activeTab === 'config'">
        <!-- 批量操作区（选中行后出现） -->
        <template v-if="selectedRows.length">
          <span class="text-12px text-gray-500">已选 {{ selectedRows.length }} 项</span>
          <ElInput v-model="batchUnit" placeholder="批量改单位" style="width: 110px" size="small" />
          <ElSelect v-model="batchWritable" placeholder="批量改可写" style="width: 100px" size="small" clearable>
            <ElOption label="可写" :value="true" />
            <ElOption label="只读" :value="false" />
          </ElSelect>
          <ElButton size="small" type="warning" :loading="batchLoading" @click="batchModify">批量修改</ElButton>
          <ElButton size="small" type="danger" :loading="batchLoading" @click="batchRemove">批量删除</ElButton>
          <span class="text-gray-300 mx-4px">|</span>
        </template>
        <ElButton v-hasPermi="['import.write']" @click="openImport">导入点位</ElButton>
        <ElButton
          v-hasPermi="['export.download']"
          :loading="exportLoading"
          @click="doExport"
        >
          导出点位
        </ElButton>
        <ElButton
          v-hasPermi="['tag.write']"
          type="success"
          @click="openCreate"
        >
          新增点位
        </ElButton>
      </template>

      <!-- 监控视图工具栏 -->
      <template v-else>
        <div class="flex items-center gap-4px mr-8px">
          <span class="text-14px text-gray-500">数据刷新</span>
          <ElSelect v-model="refreshInterval" style="width: 100px" @change="onRefreshIntervalChange">
            <ElOption v-for="opt in REFRESH_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
          </ElSelect>
          <ElButton link :loading="liveLoading" @click="fetchLiveData(true)">
            <ElTooltip content="立即刷新数据" placement="top">
              <span style="font-size: 16px">↻</span>
            </ElTooltip>
          </ElButton>
        </div>
      </template>
    </div>

    <!-- ═══ 配置视图：纯配置表格 ═══ -->
    <template v-if="activeTab === 'config'">
      <ElTable v-loading="loading" :data="list" border stripe @selection-change="onSelectionChange">
        <ElTableColumn type="selection" width="45" />
        <ElTableColumn sortable prop="id" label="ID" width="70" />
        <ElTableColumn sortable prop="device_name" label="归属设备" min-width="120" show-overflow-tooltip />
        <ElTableColumn sortable prop="name" label="点位名称" min-width="120" show-overflow-tooltip />
        <ElTableColumn sortable prop="address" label="地址" width="80" />
        <ElTableColumn label="功能码" width="130">
          <template #default="{ row }">
            <ElTag v-if="row.function_code" size="small">{{
              (
                {
                  coil: '线圈 FC01',
                  discrete_input: '离散输入 FC02',
                  input_register: '输入寄存器 FC04',
                  holding_register: '保持寄存器 FC03'
                } as any
              )[row.function_code] || row.function_code
            }}</ElTag>
            <ElTag v-else type="info" size="small">{{ row.data_type || '—' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn sortable prop="data_type" label="数据类型" width="100" />
        <ElTableColumn prop="unit" label="单位" width="70" />
        <ElTableColumn label="可写" width="70">
          <template #default="{ row }">
            <ElTag :type="row.writable ? 'success' : 'info'" size="small">{{ row.writable ? '是' : '否' }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="缩放系数" width="80">
          <template #default="{ row }">
            <span class="text-12px">{{ row.scale_factor ?? 1 }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <ElButton v-hasPermi="['tag.write']" link type="primary" @click="openEdit(row)"
              >编辑</ElButton
            >
            <ElButton v-hasPermi="['tag.write']" link type="danger" @click="remove(row)"
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
          :page-sizes="[20, 50, 100, 200]"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </template>

    <!-- ═══ 监控视图：实时数据表格 ═══ -->
    <template v-else>
      <ElTable v-loading="loading" :data="list" border stripe>
        <ElTableColumn sortable prop="id" label="ID" width="70" />
        <ElTableColumn sortable prop="device_name" label="归属设备" min-width="120" show-overflow-tooltip />
        <ElTableColumn sortable prop="name" label="点位名称" min-width="120" show-overflow-tooltip />
        <ElTableColumn label="当前值" width="160" align="center">
          <template #default="{ row }">
            <template v-if="liveData[row.id]">
              <div class="flex items-center justify-center gap-4px">
                <span class="text-right tabular-nums" style="min-width: 60px" :class="liveData[row.id].quality === 'good' ? 'text-green-600 font-bold' : liveData[row.id].quality === 'bad' ? 'text-red-500' : 'text-yellow-600'">
                  {{ liveData[row.id].value != null ? liveData[row.id].value : '—' }}
                </span>
                <span class="text-12px text-gray-400 text-left" style="min-width: 36px">{{ row.unit || '&emsp;' }}</span>
              </div>
            </template>
            <span v-else class="text-gray-300">—</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="数据质量" width="90" align="center">
          <template #default="{ row }">
            <ElTag
              v-if="liveData[row.id]"
              :type="(QUALITY_MAP[liveData[row.id].quality]?.type || 'info') as any"
              size="small"
            >
              {{ QUALITY_MAP[liveData[row.id].quality]?.text || liveData[row.id].quality }}
            </ElTag>
            <span v-else class="text-gray-300 text-12px">—</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="更新时间" width="160">
          <template #default="{ row }">
            <template v-if="liveData[row.id]?.time">
              <span class="text-12px text-gray-500">{{ new Date(liveData[row.id].time).toLocaleString() }}</span>
            </template>
            <span v-else class="text-gray-300 text-12px">—</span>
          </template>
        </ElTableColumn>
        <ElTableColumn sortable prop="address" label="地址" width="80" />
        <ElTableColumn sortable prop="data_type" label="数据类型" width="100" />
      </ElTable>
      <div class="flex justify-end mt-12px">
        <ElPagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          :page-sizes="[20, 50, 100, 200]"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </template>

    <ElEmpty v-if="!loading && !list.length" description="当前筛选条件下没有点位" />

    <ElDrawer v-model="dialogVisible" :title="dialogTitle" size="500px" @close="formRef?.resetFields()">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="90px">
        <ElFormItem label="归属设备" prop="device_id">
          <ElSelect
            v-model="dialogDeviceId"
            class="w-full"
            placeholder="搜索设备名称"
            filterable
            @change="onDialogDeviceChange"
          >
            <ElOption v-for="d in dialogDeviceOptions" :key="d.id" :label="d.name" :value="d.id" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="点位名称" prop="name">
          <ElInput v-model="form.name" placeholder="请输入点位名称" />
        </ElFormItem>
        <!-- Modbus 专属：功能码必选 -->
        <template v-if="isModbus">
          <ElFormItem label="功能码" prop="function_code">
            <ElSelect v-model="form.function_code" class="w-full" placeholder="请选择功能码（必选）">
              <ElOption label="保持寄存器 Holding (FC03/06)" value="holding_register" />
              <ElOption label="输入寄存器 Input (FC04)" value="input_register" />
              <ElOption label="线圈 Coil (FC01/05)" value="coil" />
              <ElOption label="离散输入 Discrete (FC02)" value="discrete_input" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="地址">
            <ElInputNumber v-model="form.address" :min="0" :controls="false" class="!w-full" />
          </ElFormItem>
          <ElFormItem label="数据类型">
            <ElSelect v-model="form.data_type" class="w-full">
              <ElOption label="int16" value="int16" />
              <ElOption label="uint16" value="uint16" />
              <ElOption label="int32" value="int32" />
              <ElOption label="uint32" value="uint32" />
              <ElOption label="float32" value="float32" />
              <ElOption label="bool" value="bool" />
            </ElSelect>
          </ElFormItem>
        </template>
        <!-- MQTT 专属：订阅主题必填 -->
        <template v-else-if="isMqtt">
          <ElFormItem label="订阅主题" prop="mqtt_topic">
            <ElInput v-model="form.mqtt_topic" placeholder="如 factory/line1/temp（必填）" />
          </ElFormItem>
          <ElFormItem label="JSON路径">
            <ElInput v-model="form.mqtt_json_path" placeholder="如 data.temperature（留空取整个消息体）" />
          </ElFormItem>
          <ElFormItem label="值类型">
            <ElSelect v-model="form.mqtt_value_type" class="w-full">
              <ElOption label="float64" value="float64" />
              <ElOption label="int64" value="int64" />
              <ElOption label="bool" value="bool" />
              <ElOption label="string" value="string" />
            </ElSelect>
          </ElFormItem>
        </template>
        <!-- OPC UA 专属：节点ID必填 -->
        <template v-else-if="isOpc">
          <ElFormItem label="节点ID" prop="opc_node_id">
            <ElInput v-model="form.opc_node_id" placeholder="如 ns=2;s=Temperature 或 i=1001（必填）" />
          </ElFormItem>
          <ElFormItem label="节点类型">
            <ElSelect v-model="form.opc_node_type" class="w-full">
              <ElOption label="float64" value="float64" />
              <ElOption label="int64" value="int64" />
              <ElOption label="bool" value="bool" />
              <ElOption label="string" value="string" />
            </ElSelect>
          </ElFormItem>
        </template>
        <ElFormItem label="单位">
          <ElInput v-model="form.unit" placeholder="如 ℃ / kPa" />
        </ElFormItem>
        <ElFormItem label="缩放系数">
          <ElInputNumber v-model="form.scale_factor" :step="0.1" :controls="false" class="!w-full" />
        </ElFormItem>
        <ElFormItem label="可写">
          <ElSwitch v-model="form.writable" />
        </ElFormItem>
        <ElFormItem label="回读寄存器">
          <ElSelect
            v-model="form.readback_tag_id"
            class="w-full"
            clearable
            placeholder="绑定写操作后回读的寄存器（可选）"
          >
            <ElOption
              v-for="t in readbackOptions"
              :key="t.id"
              :label="`${t.name}（${t.address ?? '—'}）${t.writable ? ' · 可写' : ''}`"
              :value="t.id"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDrawer>

    <!-- 导入点位对话框 -->
    <ElDialog v-model="importDialogVisible" title="导入点位" width="500px" @close="resetImportState">
      <ElAlert
        title="导入说明"
        type="info"
        :closable="false"
        class="mb-16px"
      >
        <template #default>
          <div>
            <p>1. 先从已有设备「导出点位」获取 CSV 文件</p>
            <p>2. 修改 CSV 中的 device_name 为目标设备名称</p>
            <p>3. 按需修改点位名称、地址等信息</p>
            <p>4. 上传修改后的 CSV 文件</p>
          </div>
        </template>
      </ElAlert>
      <ElUpload
        :show-file-list="true"
        accept=".csv"
        :http-request="doImport"
        :loading="importLoading"
      >
        <ElButton type="primary" :loading="importLoading">选择 CSV 文件</ElButton>
        <template #tip>
          <div class="text-12px text-gray-400 mt-4px">
            CSV 格式: device_name, name, function_code, address, data_type, ...
          </div>
        </template>
      </ElUpload>
      <div v-if="importResult" class="mt-12px">
        <ElAlert
          :title="`导入完成：成功 ${importResult.created} 条`"
          :type="importResult.errors?.length ? 'warning' : 'success'"
          :closable="false"
        />
        <div v-if="importResult.errors?.length" class="mt-8px text-12px text-red-500">
          <div v-for="(err, i) in importResult.errors" :key="i">{{ err }}</div>
        </div>
      </div>
      <template #footer>
        <ElButton @click="importDialogVisible = false">关闭</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
