<script setup lang="ts">
/**
 * SCADA 运行查看器 — 照搬 FUXA fuxa-view.component.ts
 *
 * 核心流程（FUXA 运行时链路）：
 * 1. innerHTML = svgcontent → SVG 注入 DOM
 * 2. SVG.adopt → DOM 元素转为 SVG.js 对象
 * 3. loadWatch → 遍历 items，绑定信号和事件
 * 4. handleSignal → 信号到达 → 查找绑定图元 → processValue
 */
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElBadge } from 'element-plus'
import { getScadaPage, unwrap } from '@/api/modbus'
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
let unsubFns: (() => void)[] = []

const wsConnected = computed(() => wsStore.connected)

// ── 加载画面 ──
const fetchPage = async () => {
  const body = unwrap(await getScadaPage(Number(id)))
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

  // 加载完成后初始化运行时绑定（照搬 FUXA loadWatch）
  canvasRef.value?.initRuntimeBindings()
}

// ── WebSocket 实时数据（照搬 FUXA handleSignal） ──
const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d) return

  const bindings = canvasRef.value?.getAllBindings() || []

  for (const binding of bindings) {
    if (binding.deviceId === d.device_id && binding.tagName === d.tag_name) {
      let updateValue: any = d.value

      if (binding.bindTarget === 'state') {
        updateValue = d.value > 0 ? '#00ff00' : '#ff0000'
        canvasRef.value?.updateBoundValue(binding.elementId, 'state', updateValue, 'fill')
      } else if (['fill', 'stroke'].includes(binding.prop)) {
        canvasRef.value?.updateBoundValue(
          binding.elementId,
          binding.bindTarget,
          updateValue,
          binding.prop
        )
      } else if (binding.bindTarget === 'level') {
        canvasRef.value?.updateBoundValue(binding.elementId, 'level', d.value, 'height')
        canvasRef.value?.updateBoundValue(binding.elementId, 'level', d.value.toFixed(1), 'text')
      } else if (binding.bindTarget === 'value') {
        const displayValue = typeof d.value === 'number' ? d.value.toFixed(1) : String(d.value)
        canvasRef.value?.updateBoundValue(binding.elementId, 'value', displayValue, 'text')
      } else if (['red', 'yellow', 'green'].includes(binding.bindTarget)) {
        if (binding.bindTarget === 'red') updateValue = d.value > 0 ? '#ff0000' : '#3a0000'
        if (binding.bindTarget === 'yellow') updateValue = d.value > 0 ? '#ffff00' : '#3a3a00'
        if (binding.bindTarget === 'green') updateValue = d.value > 0 ? '#00ff00' : '#003a00'
        canvasRef.value?.updateBoundValue(
          binding.elementId,
          binding.bindTarget,
          updateValue,
          'fill'
        )
      } else {
        const displayValue = typeof d.value === 'number' ? d.value.toFixed(1) : String(d.value)
        canvasRef.value?.updateBoundValue(
          binding.elementId,
          binding.bindTarget,
          displayValue,
          'text'
        )
      }
    }
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
  fetchPage().then(() => {
    canvasRef.value?.startFlowAnimation()
  })
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
          <span class="text-12px text-gray-400">{{ wsConnected ? '实时数据' : '离线' }}</span>
        </ElBadge>
      </div>
      <div class="flex items-center gap-8px">
        <ElButton size="small" @click="toggleFullscreen">{{
          isFullscreen ? '退出全屏' : '全屏'
        }}</ElButton>
        <ElButton size="small" type="primary" @click="router.push(`/scada/editor/${id}`)"
          >编辑</ElButton
        >
        <ElButton size="small" @click="router.push('/scada/pages')">返回</ElButton>
      </div>
    </div>
    <div class="viewer-canvas">
      <SvgCanvas
        ref="canvasRef"
        :width="page.width || 1920"
        :height="page.height || 1080"
        :background="page.background || '#1a1a2e'"
        :runtime="true"
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
</style>
