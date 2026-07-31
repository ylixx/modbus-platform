<script setup lang="ts">
/**
 * SCADA 运行查看器 - FUXA 风格 SVG 画布
 * - 加载 SVG 画布配置并渲染
 * - 通过 WebSocket 接收实时数据并更新绑定图元
 * - 全屏模式
 * - 管道流动动画 + 旋转动画
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

// ── 绑定信息缓存 ──
interface BindingInfo {
  elementId: string
  bindTarget: string
  deviceId: number
  tagId: number
  tagName: string
  prop: string
}

const parseBindingsFromCanvas = (): BindingInfo[] => {
  if (!canvasRef.value) return []
  return canvasRef.value.getAllBindings()
}

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
}

// ── WebSocket 实时数据更新 ──
const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d) return

  const bindings = parseBindingsFromCanvas()

  for (const binding of bindings) {
    if (binding.deviceId === d.device_id && binding.tagName === d.tag_name) {
      let updateValue: any = d.value

      // 根据绑定目标决定更新方式（FUXA processValue 风格）
      if (binding.bindTarget === 'state') {
        // 状态绑定：根据值映射颜色
        updateValue = d.value > 0 ? '#00ff00' : '#ff0000'
        canvasRef.value?.updateBoundValue(binding.elementId, 'state', updateValue, 'fill')
      } else if (['fill', 'stroke'].includes(binding.prop)) {
        canvasRef.value?.updateBoundValue(binding.elementId, binding.bindTarget, updateValue, binding.prop)
      } else if (binding.bindTarget === 'level') {
        // 液位绑定
        canvasRef.value?.updateBoundValue(binding.elementId, 'level', d.value, 'height')
        // 同时更新数值文本
        canvasRef.value?.updateBoundValue(binding.elementId, 'level', d.value.toFixed(1), 'text')
      } else if (binding.bindTarget === 'value') {
        const displayValue = typeof d.value === 'number' ? d.value.toFixed(1) : String(d.value)
        canvasRef.value?.updateBoundValue(binding.elementId, 'value', displayValue, 'text')
      } else if (['red', 'yellow', 'green'].includes(binding.bindTarget)) {
        // 信号灯颜色绑定
        updateValue = d.value > 0 ? '#00ff00' : '#003a00'
        if (binding.bindTarget === 'red') updateValue = d.value > 0 ? '#ff0000' : '#3a0000'
        if (binding.bindTarget === 'yellow') updateValue = d.value > 0 ? '#ffff00' : '#3a3a00'
        if (binding.bindTarget === 'green') updateValue = d.value > 0 ? '#00ff00' : '#003a00'
        canvasRef.value?.updateBoundValue(binding.elementId, binding.bindTarget, updateValue, 'fill')
      } else {
        const displayValue = typeof d.value === 'number' ? d.value.toFixed(1) : String(d.value)
        canvasRef.value?.updateBoundValue(binding.elementId, binding.bindTarget, displayValue, 'text')
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
    // 加载完成后启动动画
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
          <span class="text-12px text-gray-400">
            {{ wsConnected ? '实时数据' : '离线' }}
          </span>
        </ElBadge>
      </div>
      <div class="flex items-center gap-8px">
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
