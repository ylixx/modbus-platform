<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
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
  ElMessageBox
} from 'element-plus'
import {
  getDevices,
  getDevice,
  getDeviceLive,
  writeDevice,
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

defineOptions({ name: 'Realtime' })

const wsStore = useWsStore()

interface DeviceRow {
  id: number
  device: any
  orgPath: string
  status: string
  onlineCount: number
  totalCount: number
  updatedAt: string
  live: Record<string, any> | null
  tags: any[]
  tagsLoaded: boolean
  loadingLive: boolean
}

const deviceRows = ref<DeviceRow[]>([])
const autoRefresh = ref(true)
const useWs = ref(true)
const updatedAt = ref('')
let pollTimer: any = null
let unsubFns: (() => void)[] = []

// 关联列表框（组织架构级联 + 设备多选），与设备列表页一致
const cascadeRef = ref()
const orgPath = ref<{ org_node_id: number | null; labels: string[] } | null>(null)
const selectedIds = ref<number[]>([])

// 查看实时点位对话框
const detailVisible = ref(false)
const detailDevice = ref<any>(null)
const detailRows = ref<any[]>([])
const detailLoading = ref(false)

const wsConnected = computed(() => wsStore.connected)

const STATUS_TEXT: Record<string, string> = {
  online: '在线',
  offline: '离线',
  error: '异常',
  maintenance: '维护',
  disabled: '已禁用'
}
const STATUS_TYPE: Record<string, any> = {
  online: 'success',
  offline: 'info',
  error: 'danger',
  maintenance: 'warning',
  disabled: 'info'
}

const buildOrgPath = (d: any) =>
  [d.factory, d.production_line, d.workshop, d.installation].filter(Boolean).join(' / ')

// 按级联筛选拉取设备（org_node_id 子树 + 设备多选 ids）
const fetchDevices = async () => {
  const params: any = { page: 1, page_size: 100 }
  if (orgPath.value?.org_node_id) params.org_node_id = orgPath.value.org_node_id
  if (selectedIds.value.length) params.ids = selectedIds.value.join(',')
  const list: any[] = []
  while (true) {
    const res = await getDevices(params)
    const { list: l, total } = unwrapList(res)
    list.push(...l)
    if (list.length >= total || l.length < params.page_size) break
    params.page += 1
  }
  // 即使没有实时数据，设备也要作为行显示（初始 0/0、状态取自设备本身）
  deviceRows.value = list.map((d: any) => ({
    id: d.id,
    device: d,
    orgPath: buildOrgPath(d),
    status: d.status || 'offline',
    onlineCount: 0,
    totalCount: 0,
    updatedAt: d.last_poll_at ? new Date(d.last_poll_at).toLocaleString() : '—',
    live: null,
    tags: [],
    tagsLoaded: false,
    loadingLive: false
  }))
  updatedAt.value = new Date().toLocaleTimeString()
  // 拉取每台设备的实时值（读共享缓冲，成本低）
  await refreshLiveForAll()
}

const refreshLiveForRow = async (row: DeviceRow) => {
  try {
    const res = await getDeviceLive(row.device.id)
    const body = unwrap(res)
    const values = body?.values || {}
    const ids = Object.keys(values)
    let online = 0
    for (const k of ids) {
      if (values[k]?.quality === 'good') online += 1
    }
    row.totalCount = ids.length
    row.onlineCount = online
    row.live = values
  } catch (e) {
    row.onlineCount = 0
    row.totalCount = 0
  }
}

const refreshLiveForAll = async () => {
  await Promise.all(deviceRows.value.map((row) => refreshLiveForRow(row)))
  updatedAt.value = new Date().toLocaleTimeString()
}

// 展开行：懒加载该设备的点位定义，并刷新实时值（与对话框一致）
const onExpand = async (row: DeviceRow, expandedRows: any[]) => {
  const expanded = Array.isArray(expandedRows) && expandedRows.includes(row)
  if (!expanded || row.tagsLoaded || row.loadingLive) return
  row.loadingLive = true
  try {
    const [devRes, liveRes] = await Promise.all([
      getDevice(row.device.id),
      getDeviceLive(row.device.id)
    ])
    const body = unwrap(devRes)
    row.tags = body?.tags || (Array.isArray(body) ? body : []) || []
    row.tagsLoaded = true
    const values = unwrap(liveRes)?.values || {}
    row.live = values
    const ids = Object.keys(values)
    row.totalCount = ids.length
    row.onlineCount = ids.filter((k) => values[k]?.quality === 'good').length
  } finally {
    row.loadingLive = false
  }
}

const expandRows = (row: DeviceRow) =>
  (row.tags || []).map((t: any) => {
    const lv = row.live?.[t.id]
    return {
      tag_id: t.id,
      name: t.name,
      address: t.address,
      data_type: t.data_type,
      unit: t.unit,
      value: lv?.value ?? null,
      quality: lv?.quality ?? (row.live ? 'unknown' : 'pending')
    }
  })

// 查看实时点位对话框
const openDetail = async (row: DeviceRow) => {
  detailDevice.value = row.device
  detailVisible.value = true
  detailLoading.value = true
  try {
    const [devRes, liveRes] = await Promise.all([
      getDevice(row.device.id),
      getDeviceLive(row.device.id)
    ])
    const body = unwrap(devRes)
    const tags = body?.tags || (Array.isArray(body) ? body : []) || []
    const values = unwrap(liveRes)?.values || {}
    detailRows.value = tags.map((t: any) => {
      const lv = values[t.id]
      return {
        tag_id: t.id,
        name: t.name,
        address: t.address,
        data_type: t.data_type,
        unit: t.unit,
        writable: !!t.writable,
        value: lv?.value ?? null,
        quality: lv?.quality ?? (lv ? 'good' : 'unknown')
      }
    })
  } finally {
    detailLoading.value = false
  }
}

// 写值（仅 writable 点位）
const writeValue = async (row: any) => {
  try {
    const { value } = await ElMessageBox.prompt(`写入点位「${row.name}」`, '远程写值', {
      inputPattern: /^-?\d+(\.\d+)?$/,
      inputErrorMessage: '请输入数字',
      confirmButtonText: '写入',
      cancelButtonText: '取消'
    })
    const num = Number(value)
    await writeDevice(detailDevice.value.id, { tag_id: row.tag_id, value: num })
    ElMessage.success(`已下发写值：${row.name} = ${num}`)
    // 刷新对话框实时值
    const liveRes = await getDeviceLive(detailDevice.value.id)
    const values = unwrap(liveRes)?.values || {}
    detailRows.value = detailRows.value.map((r: any) => {
      const lv = values[r.tag_id]
      return { ...r, value: lv?.value ?? r.value, quality: lv?.quality ?? r.quality }
    })
    if (detailVisible.value) updatedAt.value = new Date().toLocaleTimeString()
  } catch (e: any) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(
        e?.response?.data?.message || e?.response?.data?.detail || e?.message || '写入失败'
      )
    }
  }
}

// ── 导入 / 导出（与设备列表页一致） ──
const saveBlob = (res: any, fallbackName: string) => {
  const blob = res?.data instanceof Blob ? res.data : new Blob([res?.data ?? res])
  const cd: string = res?.headers?.['content-disposition'] || ''
  const m = cd.match(/filename="?([^";]+)"?/)
  const name = m?.[1] || fallbackName
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

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
    fetchDevices()
  } finally {
    importing.value = false
  }
}

// ── WebSocket 实时数据 ──
const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d) return
  const row = deviceRows.value.find((r) => r.id === d.device_id)
  if (row) {
    if (!row.live) row.live = {}
    row.live = {
      ...row.live,
      [d.tag_id]: { value: d.value, quality: d.quality, time: new Date().toISOString() }
    }
    const ids = Object.keys(row.live)
    row.onlineCount = ids.filter((k) => row.live![k]?.quality === 'good').length
    row.totalCount = ids.length
  }
  if (detailVisible.value && detailDevice.value?.id === d.device_id) {
    const idx = detailRows.value.findIndex((r) => r.tag_id === d.tag_id)
    if (idx !== -1) {
      const upd = [...detailRows.value]
      upd[idx] = { ...upd[idx], value: d.value, quality: d.quality }
      detailRows.value = upd
    }
  }
  updatedAt.value = new Date().toLocaleTimeString()
}

const onBatchLive = (msg: any) => {
  const items = msg.data as WsLiveValue[]
  if (!Array.isArray(items)) return
  for (const d of items) onLiveValue({ data: d } as any)
}

// ── 轮询兜底：WS 未连接或用户关闭 WS 时，按时刷新实时值 ──
const setupPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  if (autoRefresh.value && (!wsConnected.value || !useWs.value)) {
    pollTimer = setInterval(refreshLiveForAll, 5000)
  }
}

onMounted(() => {
  fetchDevices()
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

    <!-- 组织架构级联筛选（与设备列表页一致） -->
    <div class="mb-16px">
      <OrgCascadeSelect v-model="selectedIds" v-model:path="orgPath" @search="fetchDevices" />
    </div>

    <ElTable :data="deviceRows" row-key="id" border stripe @expand-change="onExpand">
      <ElTableColumn type="expand">
        <template #default="{ row }">
          <div v-if="row.loadingLive" class="text-12px text-gray-400 p-8px">加载点位中…</div>
          <ElTable v-else :data="expandRows(row)" border size="small">
            <ElTableColumn prop="name" label="点位名称" min-width="160" show-overflow-tooltip />
            <ElTableColumn prop="address" label="地址" width="80" />
            <ElTableColumn prop="data_type" label="类型" width="100" />
            <ElTableColumn label="当前值" min-width="120">
              <template #default="{ row: r }">
                <span
                  class="text-15px font-700"
                  :class="{
                    'text-green-500': r.quality === 'good',
                    'text-red-500': r.quality === 'bad',
                    'text-gray-400': r.value == null
                  }"
                >
                  {{ r.value ?? '—' }}
                </span>
                <span class="text-12px text-gray-400 ml-4px">{{ r.unit || '' }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn label="状态" width="90">
              <template #default="{ row: r }">
                <ElTag
                  :type="r.quality === 'good' ? 'success' : r.quality === 'bad' ? 'danger' : 'info'"
                >
                  {{ r.quality === 'good' ? '正常' : r.quality === 'bad' ? '异常' : '—' }}
                </ElTag>
              </template>
            </ElTableColumn>
          </ElTable>
        </template>
      </ElTableColumn>

      <ElTableColumn prop="device.name" label="设备名称" min-width="160" show-overflow-tooltip />
      <ElTableColumn prop="orgPath" label="层级" min-width="220" show-overflow-tooltip />
      <ElTableColumn label="状态" width="90">
        <template #default="{ row }">
          <ElTag :type="STATUS_TYPE[row.status] || 'info'">
            {{ STATUS_TEXT[row.status] || row.status }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="在线点位" width="100">
        <template #default="{ row }">
          <span :class="row.onlineCount > 0 ? 'text-green-500 font-700' : 'text-gray-400'">
            {{ row.onlineCount }} / {{ row.totalCount }}
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="updatedAt" label="最近更新" min-width="160" />
      <ElTableColumn label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <ElButton type="primary" link @click="openDetail(row)">查看实时点位</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>

    <ElEmpty v-if="!deviceRows.length" description="当前筛选条件下没有设备" />

    <!-- 实时点位详情 -->
    <ElDialog
      v-model="detailVisible"
      :title="`实时点位 — ${detailDevice?.name || ''}`"
      width="640px"
    >
      <ElTable v-loading="detailLoading" :data="detailRows" border stripe max-height="420">
        <ElTableColumn prop="name" label="点位名称" min-width="160" show-overflow-tooltip />
        <ElTableColumn prop="address" label="地址" width="80" />
        <ElTableColumn prop="data_type" label="类型" width="100" />
        <ElTableColumn label="当前值" min-width="120">
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
            <span class="text-12px text-gray-400 ml-4px">{{ row.unit || '' }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="90">
          <template #default="{ row }">
            <ElTag
              :type="row.quality === 'good' ? 'success' : row.quality === 'bad' ? 'danger' : 'info'"
            >
              {{ row.quality === 'good' ? '正常' : row.quality === 'bad' ? '异常' : '—' }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <ElButton v-if="row.writable" type="primary" link @click="writeValue(row)"
              >写值</ElButton
            >
            <span v-else class="text-12px text-gray-300">只读</span>
          </template>
        </ElTableColumn>
      </ElTable>
    </ElDialog>

    <!-- 批量导入设备（与设备列表页一致） -->
    <ElDialog v-model="importDialogVisible" title="批量导入设备" width="520px">
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
