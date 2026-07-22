<template>
  <div class="scada-editor">
    <!-- Top Toolbar -->
    <div class="editor-toolbar">
      <el-button text @click="$router.push('/scada')"><el-icon><ArrowLeft /></el-icon></el-button>
      <el-divider direction="vertical" />
      <el-input v-model="pageName" style="width:200px" size="small" placeholder="画面名称" />
      <el-divider direction="vertical" />
      <el-button-group size="small">
        <el-button @click="zoomIn"><el-icon><ZoomIn /></el-icon></el-button>
        <el-button @click="zoomOut"><el-icon><ZoomOut /></el-icon></el-button>
        <el-button @click="zoomReset">100%</el-button>
      </el-button-group>
      <el-divider direction="vertical" />
      <el-button size="small" @click="bringForward"><el-icon><Top /></el-icon></el-button>
      <el-button size="small" @click="sendBackward"><el-icon><Bottom /></el-icon></el-button>
      <el-button size="small" type="danger" @click="deleteSelected"><el-icon><Delete /></el-icon></el-button>
      <div style="flex:1" />
      <el-button size="small" @click="previewVisible = true"><el-icon><View /></el-icon> 预览</el-button>
      <el-button size="small" type="primary" @click="savePage"><el-icon><Check /></el-icon> 保存</el-button>
    </div>

    <div class="editor-body">
      <!-- Left: Widget Palette -->
      <WidgetPalette
        :custom-widgets="customWidgets"
        @drag-start="onWidgetDragStart"
        @manage-widgets="$router.push('/scada/widgets')"
      />

      <!-- Center: Canvas -->
      <div class="canvas-area" @drop.prevent="onCanvasDrop" @dragover.prevent>
        <canvas ref="canvasRef"></canvas>
      </div>

      <!-- Right: Property Panel -->
      <PropertyPanel
        :selected-object="selectedObject"
        :devices="allDevices"
        :tags="bindingTags"
        :binding="{ deviceId: bindingDeviceId, tagId: bindingTagId, field: bindingField }"
        :bindable-fields="widgetMeta?.bindable || []"
        :part-fill="propFill"
        @update-prop="updateProp"
        @update-text="updateTextValue"
        @update-part-fill="updatePartFill"
        @binding-change="onBindingChange"
      />
    </div>

    <!-- Preview Dialog -->
    <el-dialog v-model="previewVisible" fullscreen :show-close="true" title="画面预览">
      <ScadaViewer v-if="previewVisible" :page-id="pageId" :preview="true" :config="canvasToJson()" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as fabric from 'fabric'
import api from '../../api/request'
import WidgetPalette from '../../components/scada/WidgetPalette.vue'
import PropertyPanel from '../../components/scada/PropertyPanel.vue'
import ScadaViewer from './Viewer.vue'

const route = useRoute()
const pageId = route.params.id
const canvasRef = ref(null)
let fc = null

const pageName = ref('')
const allDevices = ref([])
const customWidgets = ref([])
const bindingTags = ref([])
const previewVisible = ref(false)
const selectedObject = ref(null)
const propFill = ref('#2a4a6b')

// Data binding
const bindingDeviceId = ref(null)
const bindingTagId = ref(null)
const bindingField = ref('text')

const widgetMeta = computed(() => {
  if (!selectedObject.value) return null
  const st = selectedObject.value.scadaType || selectedObject.value._objects?.[0]?.scadaType
  const allWidgets = require('../../components/scada/widgets.js').WIDGETS
  return allWidgets.find(w => w.create().scadaType === st) || null
})

// ── Canvas init ──

onMounted(async () => {
  fc = new fabric.Canvas(canvasRef.value, {
    width: 1200, height: 700, backgroundColor: '#1a1a2e', selection: true,
  })
  fc.on('selection:created', onSelect)
  fc.on('selection:updated', onSelect)
  fc.on('selection:cleared', () => { selectedObject.value = null })
  fc.on('object:modified', onSelect)

  const devRes = await api.get('/devices/all')
  allDevices.value = devRes.data

  try { customWidgets.value = (await api.get('/scada/widgets')).data } catch {}

  if (pageId && pageId !== 'new') {
    const res = await api.get(`/scada/pages/${pageId}`)
    pageName.value = res.data.name
    loadCanvasFromJson(res.data.config_json)
  }
  window.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => { fc?.dispose(); window.removeEventListener('keydown', onKeyDown) })

function onKeyDown(e) {
  if ((e.key === 'Delete' || e.key === 'Backspace') && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
    deleteSelected()
  }
}

// ── Selection ──

function onSelect() {
  const obj = fc.getActiveObject()
  if (!obj) return
  selectedObject.value = obj
  const binding = obj.tagBinding || obj._objects?.[0]?.tagBinding
  if (binding) {
    bindingDeviceId.value = binding.deviceId || null
    bindingTagId.value = binding.tagId || null
    bindingField.value = binding.field || 'text'
    if (bindingDeviceId.value) loadBindingTags()
  } else {
    bindingDeviceId.value = null; bindingTagId.value = null
  }
}

// ── Property updates ──

function updateProp(key, val) {
  const obj = fc.getActiveObject()
  if (!obj) return
  obj.set(key, val); obj.setCoords(); fc.renderAll()
}

function updateTextValue(val) {
  const obj = fc.getActiveObject()
  if (obj && (obj.type === 'textbox' || obj.type === 'text')) {
    obj.set('text', val); fc.renderAll()
  }
}

function updatePartFill(color) {
  const obj = fc.getActiveObject()
  if (!obj?._objects) return
  for (const o of obj._objects) {
    if (o.scadaPart === 'body' || o.scadaPart === 'light') o.set('fill', color)
  }
  fc.renderAll()
}

// ── Widget drag & drop ──

let dragWidget = null
function onWidgetDragStart(e, widget) { dragWidget = widget; e.dataTransfer.setData('text/plain', widget.name) }

function onCanvasDrop(e) {
  if (!dragWidget) return
  const widget = dragWidget; dragWidget = null
  const rect = canvasRef.value.getBoundingClientRect()
  createFabricObject(widget.create(), e.clientX - rect.left, e.clientY - rect.top)
}

function createFabricObject(def, x, y) {
  if (def.type === 'image' && def.src) {
    const imgEl = new Image()
    imgEl.onload = () => {
      const imgObj = new fabric.Image(imgEl, { left: x, top: y, scaleX: (def.width || 100) / imgEl.width, scaleY: (def.height || 100) / imgEl.height })
      imgObj.scadaType = def.scadaType; imgObj.customId = def.customId; imgObj.tagBinding = null
      fc.add(imgObj); fc.setActiveObject(imgObj); fc.renderAll(); onSelect()
    }
    imgEl.src = def.src; return
  }

  let obj
  if (def.type === 'group' && def.objects) {
    obj = new fabric.Group(def.objects.map(c => createSingleObject(c)), { left: x, top: y })
  } else {
    obj = createSingleObject(def); obj.set({ left: x, top: y })
  }
  obj.tagBinding = null; obj.scadaType = def.scadaType
  fc.add(obj); fc.setActiveObject(obj); fc.renderAll(); onSelect()
}

function createSingleObject(def) {
  const { type, scadaPart, scadaType, bindable, ...props } = def
  switch (type) {
    case 'rect': return new fabric.Rect(props)
    case 'circle': return new fabric.Circle(props)
    case 'ellipse': return new fabric.Ellipse(props)
    case 'textbox': return new fabric.Textbox(props.text || '', props)
    case 'text': return new fabric.Text(props.text || '', props)
    case 'path': return new fabric.Path(props.path, props)
    case 'line': return new fabric.Line(props.points || [0, 0, 100, 0], props)
    default: return new fabric.Rect({ width: 50, height: 50, fill: '#333' })
  }
}

// ── Data binding ──

async function loadBindingTags() {
  if (bindingDeviceId.value) {
    bindingTags.value = (await api.get(`/devices/${bindingDeviceId.value}/tags`)).data
  } else { bindingTags.value = [] }
}

function onBindingChange(field, val) {
  if (field === 'deviceId') { bindingDeviceId.value = val; bindingTagId.value = null; loadBindingTags() }
  else if (field === 'tagId') { bindingTagId.value = val }
  else if (field === 'bindingField') { bindingField.value = val }

  const obj = fc.getActiveObject()
  if (obj) {
    obj.tagBinding = { deviceId: bindingDeviceId.value, tagId: bindingTagId.value, field: bindingField.value }
    ElMessage.success('绑定已设置')
  }
}

// ── Canvas operations ──

function deleteSelected() { const obj = fc.getActiveObject(); if (obj) { fc.remove(obj); selectedObject.value = null; fc.renderAll() } }
function bringForward() { const obj = fc.getActiveObject(); if (obj) { fc.bringObjectForward(obj); fc.renderAll() } }
function sendBackward() { const obj = fc.getActiveObject(); if (obj) { fc.sendObjectBackwards(obj); fc.renderAll() } }
function zoomIn() { fc.setZoom(fc.getZoom() * 1.1); fc.renderAll() }
function zoomOut() { fc.setZoom(fc.getZoom() / 1.1); fc.renderAll() }
function zoomReset() { fc.setZoom(1); fc.renderAll() }

// ── Save / Load ──

function canvasToJson() { return JSON.stringify(fc.toJSON(['scadaType', 'tagBinding', 'scadaPart', 'actionValue'])) }

function loadCanvasFromJson(json) {
  try { const data = typeof json === 'string' ? JSON.parse(json) : json; fc.loadFromJSON(data).then(() => fc.renderAll()) }
  catch (e) { console.error('Load canvas error:', e) }
}

async function savePage() {
  const payload = { name: pageName.value || '未命名画面', config_json: canvasToJson(), width: fc.getWidth(), height: fc.getHeight(), background: fc.backgroundColor }
  if (pageId && pageId !== 'new') { await api.put(`/scada/pages/${pageId}`, payload) }
  else { const res = await api.post('/scada/pages', payload); window.history.replaceState(null, '', `/scada/editor/${res.data.id}`) }
  ElMessage.success('保存成功')
}
</script>

<style scoped lang="scss">
.scada-editor { height: 100vh; display: flex; flex-direction: column; background: #0d1117; }
.editor-toolbar {
  display: flex; align-items: center; gap: 8px; padding: 6px 12px;
  background: #161b22; border-bottom: 1px solid #30363d;
}
.editor-body { display: flex; flex: 1; overflow: hidden; }
.canvas-area {
  flex: 1; display: flex; align-items: center; justify-content: center;
  background: #0d1117; overflow: auto;
}
</style>
