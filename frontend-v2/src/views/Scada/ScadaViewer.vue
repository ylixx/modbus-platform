<script setup lang="ts">
/**
 * SCADA 运行查看器 - FUXA 风格 SVG 画布
 * - 加载 SVG 画布配置并渲染
 * - 通过 WebSocket 接收实时数据并更新绑定图元
 * - 全屏模式
 * - 管道流动动画 + 旋转动画
 */
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElBadge, ElMessage, ElDrawer } from 'element-plus'
import { getScadaPage, getScadaPages, getHistory, unwrap, writeDevice } from '@/api/modbus'
import SvgCanvas from './SvgCanvas.vue'
import { useWsStore } from '@/store/modules/websocket'
import { wsManager } from '@/utils/websocket'
import type { WsLiveValue } from '@/utils/websocket'

defineOptions({ name: 'ScadaViewer' })

const route = useRoute()
const router = useRouter()
const wsStore = useWsStore()
const id = route.params.id as string
const page = ref<any>({ name: '', config_json: '{}' })
const canvasRef = ref<InstanceType<typeof SvgCanvas>>()
const isFullscreen = ref(false)
const pagesList = ref<any[]>([])
const drawerVisible = ref(false)
let unsubFns: (() => void)[] = []

const wsConnected = computed(() => wsStore.connected)

// ── 页面加载（支持切换画面） ──
const loadPage = async (pid: number) => {
  const body = unwrap(await getScadaPage(pid))
  page.value = body || {}
  await nextTick()

  const config = body?.config_json
  if (config) {
    try {
      const json = typeof config === 'string' ? JSON.parse(config) : config
      await canvasRef.value?.loadFromJSON(json)
    } catch (e) {
      console.warn('Failed to load SCADA config:', e)
    }
  }
  // 重启流动动画（DOM 已重建）
  canvasRef.value?.stopFlowAnimation()
  canvasRef.value?.startFlowAnimation()

  // 回放 WS 缓存中的最近值（打开画面立即显示，不等下一次推送）
  for (const [signalId, v] of Object.entries(wsStore.liveData)) {
    canvasRef.value?.applySignalValueToCanvas(signalId, v.value)
  }

  // M4: 为趋势图元加载历史数据
  const trends = canvasRef.value?.getTrendTargets() || []
  for (const t of trends) {
    getHistory({ device_id: t.deviceId, tag_id: t.tagId, interval: 'raw', page_size: 300 })
      .then((res: any) => {
        try {
          const body = unwrap(res)
          const series = (body?.data || []).map((d: any) => Number(d.value))
          if (series.length > 0) canvasRef.value?.loadTrendData(t.elementId, series)
        } catch {
          // history may be empty
        }
      })
      .catch(() => {
        // history read error -> trend shows live only
      })
  }
}

const fetchPagesList = async () => {
  try {
    const body = unwrap(await getScadaPages())
    pagesList.value = Array.isArray(body) ? body : []
  } catch {
    pagesList.value = []
  }
}

const switchPage = (pid: number) => {
  drawerVisible.value = false
  if (Number(pid) !== Number(route.params.id)) {
    router.push(`/scada/view/${pid}`)
  }
}

watch(
  () => route.params.id,
  (n) => {
    if (n) loadPage(Number(n))
  }
)

// ── WebSocket 实时数据更新（v2 引擎：signalId = deviceId:tagName） ──
/** 最近值缓存（供 toggle 事件判断当前状态） */
const lastValues = new Map<string, number>()

const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d || !canvasRef.value) return
  const signalId = `${d.device_id}:${d.tag_name}`
  if (typeof d.value === 'number') lastValues.set(signalId, d.value)
  canvasRef.value.applySignalValueToCanvas(signalId, d.value)
}

// ── 交互写值（M2：按钮/开关/滑块/输入框） ──
const onWidgetInteract = async (payload: {
  elementId: string
  eventType: string
  events: any[]
  value?: any
}) => {
  const { elementId, events, value } = payload
  if (!canvasRef.value || events.length === 0) return

  const gauge = canvasRef.value.getGaugeSettings(elementId)
  const ev = events[0]
  if (!ev) return

  const o = ev.actoptions || {}

  // M3: 画面跳转事件
  if (ev.action === 'onpage') {
    if (o.pageId && Number(o.pageId) !== Number(route.params.id)) {
      router.push(`/scada/view/${o.pageId}`)
    }
    return
  }

  if (!o.deviceId || !o.tagId) {
    ElMessage.warning(`${gauge?.name || elementId}: 事件未配置目标点位`)
    return
  }

  let writeVal: number | undefined
  if (ev.action === 'onToggleValue') {
    const cur = lastValues.get(`${o.deviceId}:${o.tagName}`)
    writeVal = cur === o.offValue ? o.onValue : o.offValue
  } else if (ev.action === 'onSetValue') {
    if (o.valueType === 'input') {
      writeVal = Number(value)
    } else if (o.valueType === 'slider') {
      writeVal = Number(value)
    } else {
      writeVal = Number(o.fixedValue)
    }
  }
  if (writeVal === undefined || Number.isNaN(writeVal)) {
    ElMessage.warning('请输入有效的数值')
    return
  }

  try {
    await writeDevice(o.deviceId, { tag_id: o.tagId, value: writeVal })
    lastValues.set(`${o.deviceId}:${o.tagName}`, writeVal)
    ElMessage.success(`${o.tagName} = ${writeVal}`)
  } catch (e: any) {
    ElMessage.error(e?.message || '写入失败')
  }
}

const viewerContainer = ref<HTMLElement>()
const toggleFullscreen = async () => {
  const el = viewerContainer.value
  if (!el) return
  try {
    if (!document.fullscreenElement) {
      await el.requestFullscreen()
      isFullscreen.value = true
    } else {
      await document.exitFullscreen()
      isFullscreen.value = false
    }
  } catch (e) {
    console.warn('Fullscreen API error:', e)
    isFullscreen.value = !isFullscreen.value
  }
}
const onFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}

onMounted(() => {
  loadPage(Number(route.params.id))
  fetchPagesList()
  unsubFns.push(wsManager.on('live_value', onLiveValue))
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onUnmounted(() => {
  unsubFns.forEach((fn) => fn())
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  canvasRef.value?.stopFlowAnimation()
})
</script>

<template>
  <div ref="viewerContainer" :class="['viewer-container', { fullscreen: isFullscreen }]">
    <div class="viewer-toolbar">
      <div class="flex items-center">
        <span class="text-16px font-600 mr-12px">{{ page.name || 'SCADA 运行' }}</span>
        <ElBadge :type="wsConnected ? 'success' : 'danger'" is-dot>
          <span class="text-12px text-gray-400">
            {{ wsConnected ? '实时数据' : '离线' }}
          </span>
        </ElBadge>
      </div>
      <div class="flex items-center gap-8px">
        <ElButton size="small" @click="drawerVisible = true">画面列表</ElButton>
        <ElButton size="small" @click="toggleFullscreen">
          {{ isFullscreen ? '退出全屏' : '全屏' }}
        </ElButton>
        <ElButton
          size="small"
          type="primary"
          @click="router.push(`/scada/editor/${id}`)"
        >
          编辑
        </ElButton>
        <ElButton size="small" @click="router.push('/scada/pages')">返回</ElButton>
      </div>
    </div>

    <!-- 画面切换抽屉 -->
    <ElDrawer v-model="drawerVisible" title="画面列表" size="280px">
      <div
        v-for="p in pagesList"
        :key="p.id"
        class="page-item"
        :class="{ active: Number(p.id) === Number(route.params.id) }"
        @click="switchPage(p.id)"
      >
        <div class="page-name">
          {{ p.name }}<span v-if="p.id === page.id" class="text-green-400"> ●</span>
        </div>
        <div class="page-meta">
          {{ p.id }} · {{ p.width }}×{{ p.height }}{{ p.description ? ' · ' + p.description : '' }}
        </div>
      </div>
      <div v-if="pagesList.length === 0" class="text-12px text-gray-400">
        暂无其他画面
      </div>
    </ElDrawer>

    <div class="viewer-canvas">
      <SvgCanvas
        ref="canvasRef"
        :width="page.width || 1920"
        :height="page.height || 1080"
        :background="page.background || '#1a1a2e'"
        :runtime="true"
        @widget:interact="onWidgetInteract"
      />
    </div>
  </div>
</template>

<style scoped>
.viewer-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
}
.viewer-container.fullscreen {
  position: fixed;
  inset: 0;
  z-index: 9999;
  height: 100vh;
  background: #0a0a1a;
}
.viewer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid var(--el-border-color);
  background: var(--el-fill-color-blank);
  flex-shrink: 0;
}
.viewer-canvas {
  flex: 1;
  overflow: auto;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 16px;
  background: #0d1117;
}
.page-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.15s;
}
.page-item:hover {
  background: var(--el-fill-color-light);
}
.page-item.active {
  background: var(--el-color-primary-light-9);
}
.page-name {
  font-size: 13px;
  font-weight: 600;
}
.page-meta {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}
</style>
