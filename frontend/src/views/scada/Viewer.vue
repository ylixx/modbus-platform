<template>
  <div class="scada-viewer" :class="{ fullscreen: isFullscreen }">
    <div class="viewer-toolbar" v-if="!isFullscreen">
      <el-button text @click="$router.push('/scada')"><el-icon><ArrowLeft /></el-icon></el-button>
      <span class="page-title">{{ pageName }}</span>
      <div style="flex:1" />
      <el-tag type="success" size="small" v-if="wsConnected">实时连接</el-tag>
      <el-tag type="info" size="small" v-else>离线</el-tag>
      <el-button size="small" @click="toggleFullscreen"><el-icon><FullScreen /></el-icon></el-button>
    </div>
    <div class="viewer-canvas" ref="canvasWrapRef">
      <canvas ref="canvasRef"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as fabric from 'fabric'
import api from '../../api/request'

const props = defineProps({
  pageId: [String, Number],
  preview: Boolean,
  config: String,
})

const route = useRoute()
const actualPageId = props.pageId || route.params.id
const canvasRef = ref(null)
const canvasWrapRef = ref(null)
const pageName = ref('')
const wsConnected = ref(false)
const isFullscreen = ref(false)

let fc = null
let tagBindingMap = {}  // "deviceId_tagId" -> [{object, field}]
let ws = null
let liveValues = {}  // "tagId" -> value

onMounted(async () => {
  // Load page
  let configJson = props.config
  if (!configJson && actualPageId) {
    const res = await api.get(`/scada/pages/${actualPageId}`)
    pageName.value = res.data.name
    configJson = res.data.config_json
    nextTick(() => {
      if (canvasWrapRef.value) {
        fc.setDimensions({ width: res.data.width, height: res.data.height })
      }
    })
  }

  // Init canvas
  fc = new fabric.Canvas(canvasRef.value, {
    width: 1200,
    height: 700,
    backgroundColor: '#1a1a2e',
    selection: false,  // no selection in viewer mode
    interactive: false, // no interaction
  })

  // Load config
  if (configJson) {
    try {
      const data = typeof configJson === 'string' ? JSON.parse(configJson) : configJson
      await fc.loadFromJSON(data)
      fc.renderAll()
      buildBindingMap()
      connectWs()
    } catch (e) { console.error('Load error:', e) }
  }
})

onUnmounted(() => {
  ws?.close()
  fc?.dispose()
})

function buildBindingMap() {
  tagBindingMap = {}
  fc.getObjects().forEach(obj => {
    const binding = obj.tagBinding
    if (binding && binding.tagId) {
      const key = `${binding.tagId}`
      if (!tagBindingMap[key]) tagBindingMap[key] = []
      tagBindingMap[key].push({ obj, field: binding.field || 'text' })
    }
  })
}

function connectWs() {
  const token = localStorage.getItem('token')
  if (!token) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${token}`)
  ws.onopen = () => { wsConnected.value = true }
  ws.onclose = () => {
    wsConnected.value = false
    setTimeout(connectWs, 3000)
  }
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'live_value') {
        const d = msg.data
        liveValues[d.tag_id] = d.value
        updateBoundObjects(d.tag_id, d.value, d.quality)
      }
    } catch {}
  }
}

function updateBoundObjects(tagId, value, quality) {
  const bindings = tagBindingMap[String(tagId)]
  if (!bindings) return

  for (const { obj, field } of bindings) {
    try {
      if (field === 'text' || field === 'value') {
        // Update text content
        if (obj.type === 'textbox' || obj.type === 'text') {
          obj.set('text', formatValue(value))
        } else if (obj.type === 'group' && obj._objects) {
          // Find text child or value part
          for (const child of obj._objects) {
            if (child.type === 'text' || child.type === 'textbox') {
              if (child.scadaPart === 'value' || child.scadaPart === 'label' || !child.scadaPart) {
                child.set('text', formatValue(value))
                break
              }
            }
          }
        }
      }

      if (field === 'fill') {
        const color = value > 0 ? '#f5222d' : '#52c41a'
        if (obj.type === 'textbox' || obj.type === 'text') {
          obj.set('fill', color)
        }
      }

      if (field === 'state') {
        applyStateToWidget(obj, value)
      }

      if (field === 'liquidLevel') {
        applyLiquidLevel(obj, value)
      }
    } catch (e) { /* skip */ }
  }
  fc.renderAll()
}

function formatValue(v) {
  if (v === null || v === undefined) return '--'
  if (typeof v === 'number') return v.toFixed(2)
  return String(v)
}

function applyStateToWidget(obj, value) {
  if (!obj._objects) return
  const isOn = value > 0 || value === true || value === '1' || value === 'true'

  for (const child of obj._objects) {
    if (child.scadaPart === 'body') {
      child.set('fill', isOn ? '#13c2c2' : '#2a4a6b')
    }
    if (child.scadaPart === 'light') {
      if (obj.scadaType === 'alarm_lamp') {
        child.set('fill', isOn ? '#f5222d' : '#333')
      } else {
        child.set('fill', isOn ? '#52c41a' : '#333')
      }
    }
    if (child.scadaPart === 'track') {
      child.set('fill', isOn ? '#1890ff' : '#333')
    }
    if (child.scadaPart === 'thumb') {
      child.set('left', isOn ? 32 : 2)
      child.set('fill', isOn ? '#fff' : '#aaa')
    }
  }
}

function applyLiquidLevel(obj, value) {
  if (!obj._objects) return
  let ratio = 0
  if (typeof value === 'number') {
    ratio = Math.max(0, Math.min(1, value / 100))
  }
  for (const child of obj._objects) {
    if (child.scadaPart === 'liquid') {
      child.set('scaleY', ratio)
    }
  }
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
  nextTick(() => fc?.renderAll())
}
</script>

<style scoped lang="scss">
.scada-viewer { display: flex; flex-direction: column; background: #0d1117; min-height: 100vh; &.fullscreen { position: fixed; inset: 0; z-index: 9999; } }
.viewer-toolbar { display: flex; align-items: center; gap: 12px; padding: 8px 16px; background: #161b22; border-bottom: 1px solid #30363d; }
.page-title { font-size: 16px; font-weight: 600; color: #eee; }
.viewer-canvas { flex: 1; display: flex; align-items: center; justify-content: center; overflow: auto; padding: 20px; }
</style>
