<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, triggerRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElCard,
  ElRow,
  ElCol,
  ElTag,
  ElEmpty,
  ElBadge,
  ElSelect,
  ElOption,
  ElButton,
  ElSwitch,
  ElInput,
  ElCollapse,
  ElCollapseItem,
  ElPagination
} from 'element-plus'
import { getDevices, getDeviceLive, getDeviceTags, unwrap, unwrapList } from '@/api/modbus'
import { useWsStore } from '@/store/modules/websocket'
import { wsManager } from '@/utils/websocket'
import type { WsLiveValue } from '@/utils/websocket'
import type { WsDeviceStatus } from '@/utils/websocket'

defineOptions({ name: 'LiveDashboard' })

const router = useRouter()
const wsStore = useWsStore()

// ── 数据 ──
interface TagMeta {
  id: number
  name: string
  address: string
  data_type: string
  unit: string
}
interface DeviceBlock {
  id: number
  name: string
  protocol: string
  status: string
  tags: TagMeta[]
  live: Record<string, { value: any; quality: string; time: string }>
}
const devices = ref<DeviceBlock[]>([])
const loading = ref(false)
const updatedAt = ref('')

// ── 分页（不再一次加载全部设备，避免设备量大时全量加载）──
const page = ref(1)
const pageSize = ref(10)
const totalDevices = ref(0)

// ── 筛选 ──
const filterQuality = ref('all') // all | good | bad | unknown
const searchKey = ref('')

// ── 刷新 ──
const autoRefresh = ref(true)
const refreshInterval = ref(30) // 秒
let pollTimer: any = null
let unsubFns: (() => void)[] = []

const wsConnected = computed(() => wsStore.connected)

// ── 质量映射 ──
const QUALITY_MAP: Record<string, { text: string; type: string; color: string }> = {
  good: { text: '正常', type: 'success', color: '#67c23a' },
  unknown: { text: '未知', type: 'warning', color: '#e6a23c' },
  stale: { text: '过期', type: 'danger', color: '#f56c6c' },
  bad: { text: '异常', type: 'danger', color: '#f56c6c' }
}

// ── 获取数据 ──
const fetchAll = async (showLoading = true) => {
  if (showLoading) loading.value = true
  try {
    // 分页拉取当前页设备（服务端搜索 + 分页），不再一次全量
    const res = await getDevices({
      page: page.value,
      page_size: pageSize.value,
      search: searchKey.value || undefined
    })
    const { list, total } = unwrapList(res)
    totalDevices.value = total ?? list.length
    const blocks: DeviceBlock[] = []
    // 并发加载当前页每台设备的点位和实时值
    const concurrency = 6
    let idx = 0
    const next = async (): Promise<void> => {
      const i = idx++
      if (i >= list.length) return
      const d = list[i]
      const block: DeviceBlock = {
        id: d.id,
        name: d.name,
        protocol: d.protocol || 'modbus',
        status: d.status || 'offline',
        tags: [],
        live: {}
      }
      blocks.push(block)
      try {
        const [tagRes, liveRes] = await Promise.all([
          getDeviceTags(d.id, { page: 1, page_size: 500 }),
          getDeviceLive(d.id)
        ])
        const tagBody = unwrap(tagRes)
        block.tags = Array.isArray(tagBody)
          ? tagBody.map((t: any) => ({ id: t.id, name: t.name, address: t.address, data_type: t.data_type, unit: t.unit || '' }))
          : (tagBody?.data || []).map((t: any) => ({ id: t.id, name: t.name, address: t.address, data_type: t.data_type, unit: t.unit || '' }))
        const liveBody = unwrap(liveRes)
        const vals = liveBody?.values || {}
        for (const [k, v] of Object.entries(vals)) {
          block.live[k] = v as any
        }
      } catch (e) {
        // 忽略单台设备错误
      }
      await next()
    }
    await Promise.all(Array.from({ length: Math.min(concurrency, list.length) }, () => next()))
    devices.value = blocks
    updatedAt.value = new Date().toLocaleTimeString()
  } finally {
    if (showLoading) loading.value = false
  }
}

// 分页 / 搜索变化时重新加载
watch(page, () => fetchAll(true))
watch(searchKey, () => {
  page.value = 1
  fetchAll(true)
})

// 仅刷新实时值（轻量，不重新加载点位定义）
const refreshLiveOnly = async () => {
  const rows = devices.value
  const concurrency = 8
  let idx = 0
  const next = async (): Promise<void> => {
    const i = idx++
    if (i >= rows.length) return
    const row = rows[i]
    try {
      const res = await getDeviceLive(row.id)
      const vals = unwrap(res)?.values || {}
      for (const [k, v] of Object.entries(vals)) {
        row.live[k] = v as any
      }
      triggerRef(devices)
    } catch (e) { /* ignore */ }
    await next()
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, rows.length) }, () => next()))
  updatedAt.value = new Date().toLocaleTimeString()
}

// ── WebSocket 实时推送 ──
const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d) return
  const dev = devices.value.find((r) => r.id === d.device_id)
  if (dev) {
    dev.live[d.tag_id] = { value: d.value, quality: d.quality, time: new Date().toISOString() }
    triggerRef(devices)
  }
  updatedAt.value = new Date().toLocaleTimeString()
}
const onBatchLive = (msg: any) => {
  const items = msg.data as WsLiveValue[]
  if (!Array.isArray(items)) return
  for (const d of items) onLiveValue({ data: d } as any)
}

const onDeviceStatus = (msg: any) => {
  const d = msg.data as WsDeviceStatus
  if (!d) return
  const dev = devices.value.find((r) => r.id === d.device_id)
  if (dev) {
    dev.status = d.status
  }
}

// ── 轮询管理 ──
const setupPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  if (autoRefresh.value && (!wsConnected.value || refreshInterval.value > 0)) {
    pollTimer = setInterval(refreshLiveOnly, refreshInterval.value * 1000)
  }
}

watch(wsConnected, (connected) => {
  if (connected) {
    if (pollTimer) clearInterval(pollTimer)
    if (autoRefresh.value) pollTimer = setInterval(refreshLiveOnly, refreshInterval.value * 1000)
  } else {
    setupPolling()
  }
})

// ── 计算属性：筛选后的设备列表 ──
const filteredDevices = computed(() => {
  return devices.value
    .filter((d) => {
      if (!searchKey.value) return true
      const key = searchKey.value.toLowerCase()
      return d.name.toLowerCase().includes(key) ||
        d.tags.some((t) => t.name.toLowerCase().includes(key) || t.address.toLowerCase().includes(key))
    })
    .map((d) => {
      const tags = d.tags.filter((t) => {
        const lv = d.live[t.id]
        if (filterQuality.value === 'all') return true
        if (!lv) return filterQuality.value === 'unknown'
        return lv.quality === filterQuality.value
      })
      return { ...d, tags }
    })
    .filter((d) => d.tags.length > 0 || filterQuality.value === 'all')
})

// ── 统计汇总 ──
const stats = computed(() => {
  let totalTags = 0
  let goodTags = 0
  let badTags = 0
  let unknownTags = 0
  for (const d of devices.value) {
    for (const t of d.tags) {
      totalTags++
      const q = d.live[t.id]?.quality
      if (q === 'good') goodTags++
      else if (q === 'bad' || q === 'stale') badTags++
      else unknownTags++
    }
  }
  return { totalTags, goodTags, badTags, unknownTags, deviceCount: devices.value.length }
})

// ── 值格式化 ──
const formatValue = (val: any, dataType: string) => {
  if (val == null) return '—'
  if (typeof val === 'number') {
    if (dataType === 'bool') return val ? 'ON' : 'OFF'
    if (Number.isInteger(val)) return val.toString()
    return val.toFixed(2)
  }
  return String(val)
}

const goDevice = (deviceId: number) => {
  router.push(`/device/detail/${deviceId}`)
}

const goTagChart = (deviceId: number, tagId: number) => {
  router.push(`/device/detail/${deviceId}/tag/${tagId}/chart`)
}

// ── 生命周期 ──
onMounted(() => {
  fetchAll()
  unsubFns.push(wsManager.on('live_value', onLiveValue))
  unsubFns.push(wsManager.on('batch_live', onBatchLive))
  unsubFns.push(wsManager.on('device_status', onDeviceStatus))
  setupPolling()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  unsubFns.forEach((fn) => fn())
})
</script>

<template>
  <ContentWrap title="实时监控看板">
    <template #header>
      <div class="flex-grow flex flex-wrap justify-end items-center gap-8px">
        <ElBadge :type="wsConnected ? 'success' : 'danger'" is-dot class="mr-4px">
          <span class="text-12px text-gray-400">{{ wsConnected ? 'WS 实时' : '轮询模式' }}</span>
        </ElBadge>
        <span v-if="updatedAt" class="text-12px text-gray-400">更新于 {{ updatedAt }}</span>
      </div>
    </template>

    <!-- 统计卡片 -->
    <ElRow :gutter="12" class="mb-16px">
      <ElCol :xs="12" :sm="6">
        <ElCard shadow="hover" class="stat-card">
          <div class="stat-value text-blue-500">{{ stats.deviceCount }}</div>
          <div class="stat-label">设备</div>
        </ElCard>
      </ElCol>
      <ElCol :xs="12" :sm="6">
        <ElCard shadow="hover" class="stat-card">
          <div class="stat-value text-green-500">{{ stats.goodTags }}</div>
          <div class="stat-label">正常点位</div>
        </ElCard>
      </ElCol>
      <ElCol :xs="12" :sm="6">
        <ElCard shadow="hover" class="stat-card">
          <div class="stat-value text-red-500">{{ stats.badTags }}</div>
          <div class="stat-label">异常点位</div>
        </ElCard>
      </ElCol>
      <ElCol :xs="12" :sm="6">
        <ElCard shadow="hover" class="stat-card">
          <div class="stat-value text-gray-500">{{ stats.unknownTags }}</div>
          <div class="stat-label">未知点位</div>
        </ElCard>
      </ElCol>
    </ElRow>

    <!-- 工具栏 -->
    <div class="flex flex-wrap items-center gap-8px mb-16px">
      <ElInput
        v-model="searchKey"
        placeholder="搜索设备名称（服务端检索）"
        clearable
        style="width: 220px"
        size="small"
      />
      <ElSelect v-model="filterQuality" size="small" style="width: 120px">
        <ElOption label="全部" value="all" />
        <ElOption label="正常" value="good" />
        <ElOption label="异常" value="bad" />
        <ElOption label="未知" value="unknown" />
      </ElSelect>
      <ElSelect v-model="refreshInterval" size="small" style="width: 110px" @change="setupPolling">
        <ElOption label="10秒" :value="10" />
        <ElOption label="30秒" :value="30" />
        <ElOption label="1分钟" :value="60" />
        <ElOption label="5分钟" :value="300" />
      </ElSelect>
      <span class="text-12px text-gray-400">自动刷新</span>
      <ElSwitch v-model="autoRefresh" @change="setupPolling" />
      <ElButton size="small" @click="refreshLiveOnly">手动刷新</ElButton>
      <ElButton size="small" type="primary" plain @click="fetchAll(true)">重新加载</ElButton>
      <span class="text-12px text-gray-400 ml-8px">共 {{ totalDevices }} 台</span>
    </div>

    <!-- 分页 -->
    <div class="flex justify-end mb-12px">
      <ElPagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="totalDevices"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchAll(true)"
        @size-change="page = 1; fetchAll(true)"
      />
    </div>

    <!-- 设备卡片列表 -->
    <div v-if="filteredDevices.length === 0 && !loading">
      <ElEmpty description="没有匹配的设备或点位" />
    </div>

    <ElCollapse v-else>
      <ElCollapseItem
        v-for="dev in filteredDevices"
        :key="dev.id"
        :name="dev.id"
      >
        <template #title>
          <div class="flex items-center gap-8px w-full">
            <ElTag
              :type="dev.status === 'online' ? 'success' : dev.status === 'error' ? 'danger' : 'info'"
              size="small"
            >
              {{ dev.status === 'online' ? '在线' : dev.status === 'error' ? '异常' : '离线' }}
            </ElTag>
            <span class="font-600 text-15px">{{ dev.name }}</span>
            <span class="text-12px text-gray-400 ml-8px">{{ dev.protocol }}</span>
            <span class="text-12px text-gray-400 ml-auto">
              {{ dev.tags.filter(t => dev.live[t.id]?.quality === 'good').length }}/{{ dev.tags.length }} 正常
            </span>
            <ElButton link type="primary" size="small" @click.stop="goDevice(dev.id)" class="ml-8px">
              详情
            </ElButton>
          </div>
        </template>

        <!-- 点位网格 -->
        <div class="tag-grid">
          <div
            v-for="tag in dev.tags"
            :key="tag.id"
            class="tag-tile"
            :class="{
              'tag-good': dev.live[tag.id]?.quality === 'good',
              'tag-bad': dev.live[tag.id]?.quality === 'bad' || dev.live[tag.id]?.quality === 'stale',
              'tag-unknown': !dev.live[tag.id] || dev.live[tag.id]?.quality === 'unknown'
            }"
            @click="goTagChart(dev.id, tag.id)"
          >
            <div class="tile-header">
              <span class="tile-name" :title="tag.name">{{ tag.name }}</span>
              <ElTag
                v-if="dev.live[tag.id]"
                :type="(QUALITY_MAP[dev.live[tag.id].quality]?.type as any) || 'info'"
                size="small"
                class="tile-quality"
              >
                {{ QUALITY_MAP[dev.live[tag.id].quality]?.text || '—' }}
              </ElTag>
            </div>
            <div class="tile-value">
              {{ formatValue(dev.live[tag.id]?.value, tag.data_type) }}
            </div>
            <div class="tile-footer">
              <span class="tile-unit">{{ tag.unit || '\u2003' }}</span>
              <span class="tile-time" v-if="dev.live[tag.id]?.time">
                {{ new Date(dev.live[tag.id].time).toLocaleTimeString() }}
              </span>
            </div>
            <div class="tile-meta">{{ tag.address }} · {{ tag.data_type }}</div>
          </div>
        </div>
      </ElCollapseItem>
    </ElCollapse>
  </ContentWrap>
</template>

<style scoped>
.stat-card {
  text-align: center;
}
.stat-card :deep(.el-card__body) {
  padding: 12px 16px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}
.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 6px;
}

.tag-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
  padding: 4px 0;
}

.tag-tile {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 8px 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}
.tag-tile:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transform: translateY(-1px);
}
.tag-tile.tag-good {
  border-left: 3px solid #67c23a;
}
.tag-tile.tag-bad {
  border-left: 3px solid #f56c6c;
  background: #fef0f0;
}
.tag-tile.tag-unknown {
  border-left: 3px solid #e6a23c;
  background: #fdf6ec;
}

.tile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.tile-name {
  font-size: 12px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 70%;
}
.tile-quality {
  transform: scale(0.8);
}

.tile-value {
  font-size: 20px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #303133;
  line-height: 1.3;
  text-align: right;
  min-height: 26px;
}

.tile-footer {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-top: 2px;
}
.tile-unit {
  font-size: 11px;
  color: #909399;
  min-width: 24px;
}
.tile-time {
  font-size: 10px;
  color: #c0c4cc;
}

.tile-meta {
  font-size: 10px;
  color: #c0c4cc;
  margin-top: 2px;
}
</style>
