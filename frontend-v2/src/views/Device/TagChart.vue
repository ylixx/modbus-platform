<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { EChartsOption } from 'echarts'
import { Echart } from '@/components/Echart'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTag,
  ElTabs,
  ElTabPane,
  ElRadioGroup,
  ElRadioButton,
  ElDatePicker,
  ElSelect,
  ElOption,
  ElSwitch,
  ElSkeleton,
  ElMessage,
  ElEmpty
} from 'element-plus'
import { getDevice, getDeviceLive, getHistory, unwrap } from '@/api/modbus'
import { useWsStore } from '@/store/modules/websocket'
import { wsManager } from '@/utils/websocket'
import type { WsLiveValue } from '@/utils/websocket'

defineOptions({ name: 'TagChart' })

const route = useRoute()
const router = useRouter()
const wsStore = useWsStore()
const deviceId = route.params.id as string
const tagId = route.params.tagId as string

const wsConnected = computed(() => wsStore.connected)

// ── 点位元信息 ──
const tagInfo = ref<any>(null)
const deviceName = ref<string>('')
const loadingTag = ref(false)

// ── 模式 ──
const activeTab = ref<'realtime' | 'history'>('realtime')
const autoRefresh = ref(true)

// 实时数据缓冲
const realtimePoints = ref<{ ts: number; value: number | null; quality?: string }[]>([])
// 历史数据缓冲
const historyPoints = ref<any[]>([])
const maxRealtimePoints = 2000

// 实时初始/裁剪窗口
const realtimeRange = ref<'15m' | '1h' | '6h' | '24h'>('1h')
const rangeMsMap: Record<string, number> = {
  '15m': 15 * 60 * 1000,
  '1h': 60 * 60 * 1000,
  '6h': 6 * 60 * 60 * 1000,
  '24h': 24 * 60 * 60 * 1000
}

// 历史查询条件
const historyRange = ref<'15m' | '1h' | '6h' | '24h' | '7d'>('24h')
const historyRangeMsMap: Record<string, number> = {
  '15m': 15 * 60 * 1000,
  '1h': 60 * 60 * 1000,
  '6h': 6 * 60 * 60 * 1000,
  '24h': 24 * 60 * 60 * 1000,
  '7d': 7 * 24 * 60 * 60 * 1000
}
const customRange = ref<[Date, Date] | null>(null)
const aggInterval = ref<'raw' | '1m' | '5m' | '15m' | '1h' | '1d'>('raw')
const loadingHistory = ref(false)

const unit = computed(() => tagInfo.value?.unit || '')
const baseName = computed(() => tagInfo.value?.name || `点位#${tagId}`)

// 当前展示的数据源
const srcPoints = computed(() =>
  activeTab.value === 'realtime' ? realtimePoints.value : historyPoints.value
)

// ── 统计 ──
const stats = computed(() => {
  const pts = srcPoints.value
  const vals = pts.map((p) => p.value).filter((v) => v != null) as number[]
  if (!vals.length) {
    return { current: null, max: null, min: null, avg: null, count: 0, lastTime: null }
  }
  const max = Math.max(...vals)
  const min = Math.min(...vals)
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length
  const last = pts[pts.length - 1]
  return {
    current: last.value ?? null,
    max,
    min,
    avg,
    count: vals.length,
    lastTime: last.ts ?? null
  }
})

// ── 时间格式化 ──
const pad = (n: number) => String(n).padStart(2, '0')
const fmtTime = (ts: number) => {
  const d = new Date(ts)
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// ── 阈值线 ──
const markLineData = computed(() => {
  const data: any[] = []
  const t = tagInfo.value
  if (t?.min_value != null) {
    data.push({ yAxis: t.min_value, name: '下限', lineStyle: { color: '#f56c6c', type: 'dashed' } })
  }
  if (t?.max_value != null) {
    data.push({ yAxis: t.max_value, name: '上限', lineStyle: { color: '#f56c6c', type: 'dashed' } })
  }
  return data
})

// ── 图表配置 ──
const chartOption = computed<EChartsOption>(() => {
  const pts = srcPoints.value
  const isAgg = activeTab.value === 'history' && aggInterval.value !== 'raw'
  const mainName = baseName.value
  const mainData = pts.map((p) => [p.ts, p.value] as [number, number | null])
  const series: any[] = [
    {
      name: mainName,
      type: 'line',
      showSymbol: false,
      smooth: true,
      data: mainData,
      lineStyle: { width: 2 },
      itemStyle: { color: '#409eff' },
      areaStyle: { opacity: 0.12, color: '#409eff' },
      markLine: markLineData.value.length
        ? { silent: true, symbol: 'none', data: markLineData.value }
        : undefined
    }
  ]
  if (isAgg) {
    series.push({
      name: '最小',
      type: 'line',
      showSymbol: false,
      data: pts.map((p) => [p.ts, p.min ?? null]),
      lineStyle: { width: 1, type: 'dashed' },
      itemStyle: { color: '#67c23a' }
    })
    series.push({
      name: '最大',
      type: 'line',
      showSymbol: false,
      data: pts.map((p) => [p.ts, p.max ?? null]),
      lineStyle: { width: 1, type: 'dashed' },
      itemStyle: { color: '#e6a23c' }
    })
  }
  const legendData = isAgg ? [mainName, '最小', '最大'] : [mainName]

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const arr = Array.isArray(params) ? params : [params]
        if (!arr.length) return ''
        const ts = arr[0].value[0]
        let s = `${fmtTime(ts)}\n`
        arr.forEach((pp: any) => {
          const v = pp.value?.[1]
          s += `${pp.marker}${pp.seriesName}: ${v == null ? '—' : v}${unit.value || ''}\n`
        })
        return s
      }
    },
    legend: { data: legendData, top: 4 },
    grid: { left: 56, right: 24, top: 44, bottom: 72 },
    xAxis: {
      type: 'time',
      axisLabel: {
        formatter: (value: number) => {
          const d = new Date(value)
          return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
        }
      }
    },
    yAxis: { type: 'value', name: unit.value || '值', scale: true },
    dataZoom: [
      { type: 'inside', filterMode: 'none' },
      { type: 'slider', height: 22, bottom: 12, filterMode: 'none' }
    ],
    toolbox: {
      right: 12,
      feature: {
        saveAsImage: { title: '保存图片' },
        restore: { title: '还原' },
        dataZoom: { title: { zoom: '缩放', back: '还原缩放' } }
      }
    },
    series
  }
})

// ── 实时：拉取初始历史 + 追加 ──
const appendRealtimePoint = (value: number | null, ts: number, quality?: string) => {
  const arr = realtimePoints.value.slice()
  arr.push({ ts, value, quality })
  if (arr.length > maxRealtimePoints) arr.shift()
  realtimePoints.value = arr
}

const loadRealtimeSeed = async () => {
  const end = Date.now()
  const start = end - (rangeMsMap[realtimeRange.value] || rangeMsMap['1h'])
  try {
    const body = unwrap(
      await getHistory({
        device_id: Number(deviceId),
        tag_id: Number(tagId),
        start_time: new Date(start).toISOString(),
        end_time: new Date(end).toISOString(),
        interval: 'raw',
        page: 1,
        page_size: 1000
      })
    )
    const list = (body?.data || []).map((i: any) => ({
      ts: i.time ? new Date(i.time).getTime() : 0,
      value: i.value == null ? null : Number(i.value)
    }))
    realtimePoints.value = list.filter((p: any) => p.ts && p.value != null)
  } catch (e) {
    // 无历史数据不阻断实时追加
  }
}

// ── 实时：WS 订阅 + 轮询兜底 ──
const onLive = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d || d.device_id !== Number(deviceId) || d.tag_id !== Number(tagId)) return
  const ts = d.time ? new Date(d.time).getTime() : Date.now()
  appendRealtimePoint(d.value == null ? null : Number(d.value), ts, d.quality)
}
let unsub: (() => void) | null = null
let pollTimer: any = null

const pollRealtime = async () => {
  try {
    const body = unwrap(await getDeviceLive(deviceId))
    const v = body?.values?.[Number(tagId)]
    if (v) {
      const ts = v.time ? new Date(v.time).getTime() : Date.now()
      appendRealtimePoint(v.value == null ? null : Number(v.value), ts, v.quality)
    }
  } catch (e) {
    // ignore
  }
}

const setupPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
  if (activeTab.value === 'realtime' && autoRefresh.value && !wsConnected.value) {
    pollTimer = setInterval(pollRealtime, 2000)
  }
}

// ── 历史查询 ──
const buildHistoryRange = (): { start: number; end: number } => {
  const end = Date.now()
  if (customRange.value && customRange.value.length === 2) {
    return { start: customRange.value[0].getTime(), end: customRange.value[1].getTime() }
  }
  const span = historyRangeMsMap[historyRange.value] || historyRangeMsMap['24h']
  return { start: end - span, end }
}

const queryHistory = async () => {
  loadingHistory.value = true
  try {
    const { start, end } = buildHistoryRange()
    const params: any = {
      device_id: Number(deviceId),
      tag_id: Number(tagId),
      interval: aggInterval.value,
      start_time: new Date(start).toISOString(),
      end_time: new Date(end).toISOString()
    }
    const all: any[] = []
    if (aggInterval.value === 'raw') {
      // 分页拉全量
      let page = 1
      while (true) {
        const body = unwrap(
          await getHistory({ ...params, page, page_size: 1000 })
        )
        const data = body?.data || []
        all.push(...data)
        if (data.length < 1000 || all.length > 5000) break
        page += 1
      }
    } else {
      const body = unwrap(await getHistory({ ...params, page: 1, page_size: 1000 }))
      all.push(...(body?.data || []))
    }
    historyPoints.value = all
      .map((i: any) =>
        aggInterval.value === 'raw'
          ? {
              ts: i.time ? new Date(i.time).getTime() : 0,
              value: i.value == null ? null : Number(i.value),
              quality: i.quality
            }
          : {
              ts: i.time ? new Date(i.time).getTime() : 0,
              value: i.avg == null ? null : Number(i.avg),
              min: i.min == null ? null : Number(i.min),
              max: i.max == null ? null : Number(i.max),
              avg: i.avg == null ? null : Number(i.avg)
            }
      )
      .filter((p: any) => p.ts && p.value != null)
    if (!historyPoints.value.length) {
      ElMessage.info('该时间范围内没有历史数据')
    }
  } catch (e: any) {
    ElMessage.error('历史数据查询失败：' + (e?.response?.data?.message || e?.message || '未知错误'))
  } finally {
    loadingHistory.value = false
  }
}

// 历史自动刷新
let historyTimer: any = null
const setupHistoryRefresh = () => {
  if (historyTimer) clearInterval(historyTimer)
  historyTimer = null
  if (activeTab.value === 'history' && autoRefresh.value) {
    historyTimer = setInterval(queryHistory, 15000)
  }
}

// 切换自定义范围时清空快捷
watch(customRange, (v) => {
  if (v && v.length === 2) {
    // 保持自定义优先
  }
})

watch(activeTab, (tab) => {
  if (tab === 'realtime') {
    setupPolling()
    if (!historyTimer) setupHistoryRefresh()
  } else {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = null
    setupHistoryRefresh()
  }
})
watch(wsConnected, () => setupPolling())
watch(autoRefresh, () => {
  setupPolling()
  setupHistoryRefresh()
})
watch(realtimeRange, () => loadRealtimeSeed())
watch([historyRange, customRange, aggInterval], () => {
  // 条件变化后用户点查询；若已查过则自动刷新
  if (activeTab.value === 'history' && historyPoints.value.length) queryHistory()
})

const goBack = () => router.push(`/device/detail/${deviceId}`)

onMounted(async () => {
  loadingTag.value = true
  try {
    const d = unwrap(await getDevice(deviceId)) || {}
    deviceName.value = d.name || ''
    tagInfo.value = (d.tags || []).find((t: any) => String(t.id) === String(tagId)) || null
  } catch (e) {
    ElMessage.error('加载点位信息失败')
  } finally {
    loadingTag.value = false
  }
  // 实时模式：先拉初始历史，再订阅 WS
  await loadRealtimeSeed()
  unsub = wsManager.on('live_value', onLive)
  setupPolling()
})

onUnmounted(() => {
  unsub?.()
  if (pollTimer) clearInterval(pollTimer)
  if (historyTimer) clearInterval(historyTimer)
})
</script>

<template>
  <div>
    <ContentWrap :title="`点位曲线 — ${baseName}`">
      <template #header>
        <div class="flex-grow flex justify-end items-center">
          <ElTag :type="wsConnected ? 'success' : 'info'" size="small" class="mr-12px">
            {{ wsConnected ? 'WS 已连接' : '轮询模式' }}
          </ElTag>
          <ElButton size="small" @click="goBack">返回设备详情</ElButton>
        </div>
      </template>

      <ElSkeleton :loading="loadingTag" animated>
        <div v-if="!tagInfo" class="text-center text-gray-400 py-40px">未找到该点位（设备 {{ deviceId }} / 点位 {{ tagId }}）</div>

        <div v-else>
          <!-- 点位信息 -->
          <div class="flex flex-wrap items-center gap-16px mb-12px text-13px text-gray-500">
            <span>设备：<b class="text-gray-700">{{ deviceName }}</b></span>
            <span>类型：{{ tagInfo.data_type }}</span>
            <span>单位：{{ tagInfo.unit || '—' }}</span>
            <span v-if="tagInfo.min_value != null || tagInfo.max_value != null">
              阈值：{{ tagInfo.min_value ?? '—' }} ~ {{ tagInfo.max_value ?? '—' }}
            </span>
            <span v-if="tagInfo.description">说明：{{ tagInfo.description }}</span>
          </div>

          <!-- 统计卡片 -->
          <div class="grid grid-cols-2 md:grid-cols-5 gap-12px mb-12px">
            <div class="border border-gray-100 rounded-2px px-12px py-8px">
              <div class="text-12px text-gray-400">最新值</div>
              <div class="text-18px font-700 text-blue-500">
                {{ stats.current == null ? '—' : stats.current }}<span class="text-12px text-gray-400 ml-2px">{{ unit }}</span>
              </div>
            </div>
            <div class="border border-gray-100 rounded-2px px-12px py-8px">
              <div class="text-12px text-gray-400">最大值</div>
              <div class="text-18px font-700 text-red-500">
                {{ stats.max == null ? '—' : stats.max }}<span class="text-12px text-gray-400 ml-2px">{{ unit }}</span>
              </div>
            </div>
            <div class="border border-gray-100 rounded-2px px-12px py-8px">
              <div class="text-12px text-gray-400">最小值</div>
              <div class="text-18px font-700 text-green-500">
                {{ stats.min == null ? '—' : stats.min }}<span class="text-12px text-gray-400 ml-2px">{{ unit }}</span>
              </div>
            </div>
            <div class="border border-gray-100 rounded-2px px-12px py-8px">
              <div class="text-12px text-gray-400">平均值</div>
              <div class="text-18px font-700 text-gray-700">
                {{ stats.avg == null ? '—' : stats.avg.toFixed(2) }}<span class="text-12px text-gray-400 ml-2px">{{ unit }}</span>
              </div>
            </div>
            <div class="border border-gray-100 rounded-2px px-12px py-8px">
              <div class="text-12px text-gray-400">采样点 / 时间</div>
              <div class="text-14px font-700 text-gray-700">{{ stats.count }}</div>
              <div class="text-11px text-gray-400">{{ stats.lastTime ? fmtTime(stats.lastTime) : '—' }}</div>
            </div>
          </div>

          <ElTabs v-model="activeTab">
            <!-- 实时 -->
            <ElTabPane label="实时曲线" name="realtime">
              <div class="flex flex-wrap items-center gap-12px mb-12px">
                <span class="text-13px text-gray-500">时间窗：</span>
                <ElRadioGroup v-model="realtimeRange" size="small">
                  <ElRadioButton label="15m">15分钟</ElRadioButton>
                  <ElRadioButton label="1h">1小时</ElRadioButton>
                  <ElRadioButton label="6h">6小时</ElRadioButton>
                  <ElRadioButton label="24h">24小时</ElRadioButton>
                </ElRadioGroup>
                <span class="text-13px text-gray-500 ml-8px">自动刷新</span>
                <ElSwitch v-model="autoRefresh" />
                <span class="text-12px text-gray-400">（WS 实时推送，未连时轮询兜底）</span>
              </div>
              <Echart :options="chartOption" height="460px" />
            </ElTabPane>

            <!-- 历史 -->
            <ElTabPane label="历史曲线" name="history">
              <div class="flex flex-wrap items-center gap-12px mb-12px">
                <span class="text-13px text-gray-500">范围：</span>
                <ElRadioGroup v-model="historyRange" size="small">
                  <ElRadioButton label="15m">15分钟</ElRadioButton>
                  <ElRadioButton label="1h">1小时</ElRadioButton>
                  <ElRadioButton label="6h">6小时</ElRadioButton>
                  <ElRadioButton label="24h">24小时</ElRadioButton>
                  <ElRadioButton label="7d">7天</ElRadioButton>
                </ElRadioGroup>
                <ElDatePicker
                  v-model="customRange"
                  type="datetimerange"
                  size="small"
                  range-separator="至"
                  start-placeholder="开始"
                  end-placeholder="结束"
                  :clearable="true"
                  style="width: 360px"
                />
                <span class="text-13px text-gray-500 ml-8px">聚合：</span>
                <ElSelect v-model="aggInterval" size="small" style="width: 110px">
                  <ElOption label="原始" value="raw" />
                  <ElOption label="1分钟" value="1m" />
                  <ElOption label="5分钟" value="5m" />
                  <ElOption label="15分钟" value="15m" />
                  <ElOption label="1小时" value="1h" />
                  <ElOption label="1天" value="1d" />
                </ElSelect>
                <ElButton type="primary" size="small" :loading="loadingHistory" @click="queryHistory">
                  查询
                </ElButton>
                <span class="text-13px text-gray-500 ml-8px">自动刷新</span>
                <ElSwitch v-model="autoRefresh" />
              </div>
              <ElSkeleton :loading="loadingHistory" animated>
                <ElEmpty v-if="!historyPoints.length" description="请选择范围后点击「查询」" />
                <EChart v-else :options="chartOption" height="460px" />
              </ElSkeleton>
            </ElTabPane>
          </ElTabs>
        </div>
      </ElSkeleton>
    </ContentWrap>
  </div>
</template>
