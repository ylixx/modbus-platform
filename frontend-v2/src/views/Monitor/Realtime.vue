<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElTable,
  ElTableColumn,
  ElTag,
  ElSwitch,
  ElEmpty,
  ElBadge,
  ElButton,
  ElDialog,
  ElAlert,
  ElMessage,
  ElPagination
} from 'element-plus'
import {
  getDeviceLive,
  getAllTags,
  unwrap,
  unwrapList,
  exportDevicesCsv,
  getImportTemplateDevices,
  importDevices
} from '@/api/modbus'
import OrgCascadeSelect from '@/components/OrgCascadeSelect.vue'
import { useWsStore } from '@/store/modules/websocket'
import { wsManager } from '@/utils/websocket'
import type { WsLiveValue } from '@/utils/websocket'
import { saveBlob } from '@/utils/modbus'

defineOptions({ name: 'Realtime' })

const wsStore = useWsStore()
const router = useRouter()

// ── 点位扁平列表 + 分页 ──
interface TagRow {
  id: number
  device_id: number
  device_name: string
  name: string
  unit: string
  function_code: string
  address: number
  data_type: string
  writable: boolean
  enabled: boolean
  // 实时值（来自 live API / WS）
  value: any
  quality: string
  updatedAt: string
}

const tagRows = ref<TagRow[]>([])
const loading = ref(false)
const autoRefresh = ref(true)
const useWs = ref(true)
const updatedAt = ref('')
let pollTimer: any = null
let unsubFns: (() => void)[] = []

// 分页
const currentPage = ref(1)
const pageSize = ref(50)
const total = ref(0)

// 搜索
const searchKeyword = ref('')

// 关联列表框（组织架构级联 + 设备多选）
const orgPath = ref<{ org_node_id: number | null; labels: string[] } | null>(null)
const selectedIds = ref<number[]>([])

const wsConnected = computed(() => wsStore.connected)

// ── 拉取全局点位列表（分页） ──
const fetchTags = async () => {
  loading.value = true
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (orgPath.value?.org_node_id) params.org_node_id = orgPath.value.org_node_id
    if (searchKeyword.value.trim()) params.search = searchKeyword.value.trim()
    const res = await getAllTags(params)
    const { list, total: t } = unwrapList(res)
    total.value = t
    tagRows.value = list.map((t: any) => ({
      id: t.id,
      device_id: t.device_id,
      device_name: t.device_name,
      name: t.name,
      unit: t.unit || '',
      function_code: t.function_code || '',
      address: t.address,
      data_type: t.data_type || '',
      writable: t.writable,
      enabled: t.enabled,
      value: null,
      quality: 'pending',
      updatedAt: '—'
    }))
    updatedAt.value = new Date().toLocaleTimeString()
    // 拉取实时值
    await refreshLiveForAll()
  } finally {
    loading.value = false
  }
}

// ── 实时值批量刷新：按设备分组，并发拉取 /live ──
const deviceLiveMap = ref<Record<number, Record<string, any>>>({})

const refreshLiveForAll = async () => {
  // 收集当前页涉及的所有设备 ID
  const deviceIds = [...new Set(tagRows.value.map((r) => r.device_id))]
  const concurrency = 6
  let idx = 0
  const next = async (): Promise<void> => {
    const i = idx++
    if (i >= deviceIds.length) return
    const did = deviceIds[i]
    try {
      const res = await getDeviceLive(did)
      const body = unwrap(res)
      const values = body?.values || {}
      deviceLiveMap.value[did] = values
      // 更新 tagRows 中对应设备的点位实时值
      for (const row of tagRows.value) {
        if (row.device_id !== did) continue
        const lv = values[row.id]
        if (lv) {
          row.value = lv.value ?? null
          row.quality = lv.quality || 'unknown'
          row.updatedAt = lv.time
            ? new Date(lv.time).toLocaleString()
            : new Date().toLocaleString()
        }
      }
    } catch {
      // 静默忽略
    }
    await next()
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, deviceIds.length) }, () => next()))
  updatedAt.value = new Date().toLocaleTimeString()
}

// 分页/搜索变化
const onCurrentChange = (p: number) => {
  currentPage.value = p
  fetchTags()
}
const onSizeChange = (s: number) => {
  pageSize.value = s
  currentPage.value = 1
  fetchTags()
}
// searchKeyword 变化时重新查询（防抖由父组件或后续优化）
// const onSearch = () => { ... }

// 级联筛选变化
const onCascadeSearch = () => {
  currentPage.value = 1
  fetchTags()
}

// 跳转到设备详情
const goDetail = (row: TagRow) => {
  router.push(`/device/detail/${row.device_id}`)
}

// ── 导入 / 导出（设备级） ──
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
    fetchTags()
  } finally {
    importing.value = false
  }
}

const resetImportState = () => {
  importFile.value = null
  importResult.value = null
  if (fileInputRef.value) fileInputRef.value.value = ''
}

// ── WebSocket 实时数据 ──
const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d) return
  // 找到当前页中匹配的点位行
  const row = tagRows.value.find((r) => r.id === d.tag_id && r.device_id === d.device_id)
  if (row) {
    row.value = d.value ?? null
    row.quality = d.quality || 'unknown'
    row.updatedAt = new Date().toLocaleString()
  }
  updatedAt.value = new Date().toLocaleTimeString()
}

const onBatchLive = (msg: any) => {
  const items = msg.data as WsLiveValue[]
  if (!Array.isArray(items)) return
  for (const d of items) onLiveValue({ data: d } as any)
}

// ── 轮询兜底 ──
const setupPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  if (autoRefresh.value && (!wsConnected.value || !useWs.value)) {
    pollTimer = setInterval(refreshLiveForAll, 5000)
  }
}

onMounted(() => {
  fetchTags()
  unsubFns.push(wsManager.on('live_value', onLiveValue))
  unsubFns.push(wsManager.on('batch_live', onBatchLive))
  setupPolling()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  unsubFns.forEach((fn) => fn())
})

watch(wsConnected, (connected) => {
  if (connected) {
    if (pollTimer) clearInterval(pollTimer)
  } else {
    setupPolling()
  }
})
</script>

<template>
  <ContentWrap title="实时数据">
    <template #header>
      <div class="flex-grow flex justify-end items-center">
        <ElBadge :type="wsConnected ? 'success' : 'danger'" is-dot class="mr-8px">
          <span class="text-12px text-gray-400">
            {{ wsConnected ? 'WS 实时' : '轮询模式' }}
          </span>
        </ElBadge>
        <span class="text-12px text-gray-400 mr-12px" v-if="updatedAt">更新于 {{ updatedAt }}</span>
        <ElButton size="small" @click="refreshLiveForAll">刷新</ElButton>
        <span class="text-13px text-gray-500 mr-6px ml-6px">自动刷新</span>
        <ElSwitch v-model="autoRefresh" class="mr-4px" @change="setupPolling" />
        <ElButton size="small" type="primary" plain @click="openImport">导入</ElButton>
        <ElButton size="small" plain :loading="exporting" @click="doExport">导出</ElButton>
      </div>
    </template>

    <!-- 组织架构级联筛选 + 搜索 -->
    <div class="mb-16px">
      <OrgCascadeSelect v-model="selectedIds" v-model:path="orgPath" @search="onCascadeSearch" />
    </div>

    <!-- 扁平点位列表 -->
    <ElTable v-loading="loading" :data="tagRows" row-key="id" border stripe>
      <ElTableColumn prop="device_name" label="设备名称" min-width="120" show-overflow-tooltip />
      <ElTableColumn prop="name" label="点位名称" min-width="120" show-overflow-tooltip />
      <ElTableColumn prop="address" label="地址" width="80" />
      <ElTableColumn prop="data_type" label="数据类型" width="100" />
      <ElTableColumn label="当前值" min-width="140">
        <template #default="{ row }">
          <span
            class="text-15px font-700"
            :class="{
              'text-green-500': row.quality === 'good',
              'text-red-500': row.quality === 'bad',
              'text-gray-400': row.value == null
            }"
          >
            {{ row.value ?? '—' }}
          </span>
          <span class="text-12px text-gray-400 ml-4px">{{ row.unit }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="质量" width="90">
        <template #default="{ row }">
          <ElTag
            :type="row.quality === 'good' ? 'success' : row.quality === 'bad' ? 'danger' : 'info'"
          >
            {{ row.quality === 'good' ? '正常' : row.quality === 'bad' ? '异常' : '—' }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="updatedAt" label="更新时间" min-width="160" show-overflow-tooltip />
      <ElTableColumn label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <ElButton type="primary" link @click="goDetail(row)">设备详情</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>

    <!-- 分页 -->
    <div class="flex justify-between items-center mt-12px" v-if="total > 0">
      <span class="text-13px text-gray-400">共 {{ total }} 条</span>
      <ElPagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100, 200]"
        layout="sizes, prev, pager, next, jumper"
        @current-change="onCurrentChange"
        @size-change="onSizeChange"
      />
    </div>

    <ElEmpty v-if="!loading && !tagRows.length" description="当前筛选条件下没有点位数据" />

    <!-- 批量导入设备 -->
    <ElDialog v-model="importDialogVisible" title="批量导入设备" width="520px" @close="resetImportState">
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
  </ContentWrap>
</template>
