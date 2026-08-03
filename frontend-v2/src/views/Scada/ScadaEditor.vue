<script setup lang="ts">
/**
 * SCADA 可视化编辑器 — 照搬 FUXA editor.component.ts
 *
 * 布局：左侧图元面板 | 中间SVG画布 | 右侧属性面板
 * 存储格式：SVG字符串 + items字典（FUXA双层存储）
 *
 * 属性面板三段式结构（照搬 FUXA gauge-property）：
 * 1. Interactivity（ID/类型/名称）
 * 2. Transform（X/Y/透明度）
 * 3. Fill/Stroke（填充色/描边色/线宽）
 * 4. Data Binding（信号绑定）
 * 5. Value Processing（位掩码/范围颜色映射/动作执行）
 * 6. Events（鼠标事件→页面/对话/值设置等）
 */
import { ref, reactive, onMounted, nextTick, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElButton,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElDialog,
  ElForm,
  ElFormItem,
  ElSelect,
  ElOption,
  ElTabs,
  ElTabPane,
  ElCollapse,
  ElCollapseItem,
  ElColorPicker,
  ElInputNumber,
  ElSlider,
  ElDivider,
  ElTooltip,
  ElButtonGroup,
  ElTag
} from 'element-plus'
import {
  getScadaPage,
  updateScadaPage,
  getScadaWidgets,
  getDeviceTags,
  getAllDevices,
  unwrap,
  unwrapList
} from '@/api/modbus'
import SvgCanvas from './SvgCanvas.vue'
import { GAUGE_CATEGORIES, getGaugeDef } from './svg-templates'
import type { GaugeTypeDef } from './svg-templates'
import {
  genId,
  type GaugeRangeProperty,
  type GaugeAction,
  type GaugeActionType,
  type GaugeEventType,
  type GaugeEventActionType,
  type GaugeEvent
} from './hmi'

defineOptions({ name: 'ScadaEditor' })

const route = useRoute()
const router = useRouter()
const id = route.params.id as string

// ── 画布数据 ──
const page = ref<any>({ name: '', config_json: '{}' })
const saving = ref(false)
const canvasRef = ref<InstanceType<typeof SvgCanvas>>()

// ── 缩放 ──
const zoomLevel = ref(100)

// ── 网格 ──
const gridSize = ref(20)

// ── 撤销/重做 ──
const canUndoState = ref(false)
const canRedoState = ref(false)

const refreshUndoRedoState = () => {
  canUndoState.value = canvasRef.value?.canUndo() ?? false
  canRedoState.value = canvasRef.value?.canRedo() ?? false
}

// ── 未保存变更追踪 ──
const hasUnsavedChanges = ref(false)
let autoSaveTimer: ReturnType<typeof setInterval> | null = null
const markDirty = () => {
  hasUnsavedChanges.value = true
  refreshUndoRedoState()
}
const autoSave = async () => {
  if (hasUnsavedChanges.value) {
    await save()
    hasUnsavedChanges.value = false
  }
}
const onBeforeUnload = (e: BeforeUnloadEvent) => {
  if (hasUnsavedChanges.value) e.preventDefault()
}

// ── 左侧面板 ──
const leftTab = ref('basic')
const customWidgets = ref<any[]>([])
const devices = ref<any[]>([])
const deviceTags = ref<any[]>([])

// ── 右侧属性面板 ──
const selectedObj = ref<SVGElement | null>(null)
const selectedProps = reactive<any>({
  left: 0,
  top: 0,
  opacity: 1,
  fill: '#ffffff',
  stroke: '#000000',
  strokeWidth: 1
})

const selectedWidgetType = computed(() => selectedObj.value?.getAttribute('type') || '')
const selectedWidgetId = computed(() => selectedObj.value?.getAttribute('id') || '')

// ── 数据绑定配置 ──
const bindDialogVisible = ref(false)
const bindForm = reactive({
  target: '',
  deviceId: undefined as number | undefined,
  tagId: undefined as number | undefined,
  tagName: '',
  prop: 'text'
})

// ── 值处理配置（FUXA 风格） ──
const valueProcessDialogVisible = ref(false)
const valueProcessForm = reactive({
  bitMask: 0,
  ranges: [] as GaugeRangeProperty[],
  actions: [] as GaugeAction[]
})

// ── 事件配置（FUXA 风格） ──
const eventDialogVisible = ref(false)
const eventForm = reactive({
  events: [] as GaugeEvent[]
})

// ── 加载页面数据 ──
const fetchPage = async () => {
  try {
    const body = unwrap(await getScadaPage(Number(id)))
    page.value = body || {}
    await nextTick()
    const config = body?.config_json
    if (config) {
      try {
        const json = typeof config === 'string' ? JSON.parse(config) : config
        canvasRef.value?.loadFromJSON(json)
      } catch (e) {
        console.warn('Failed to parse SCADA config:', e)
      }
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '获取页面数据失败')
  }
}

const fetchCustomWidgets = async () => {
  try {
    customWidgets.value = unwrapList(await getScadaWidgets()).list
  } catch {
    customWidgets.value = []
  }
}

const fetchDevices = async () => {
  try {
    devices.value = unwrapList(await getAllDevices()).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取设备列表失败')
  }
}

const fetchTags = async (deviceId: number) => {
  try {
    const res = await getDeviceTags(deviceId)
    const body = unwrap(res)
    deviceTags.value = Array.isArray(body) ? body : unwrapList(res).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取点位列表失败')
  }
}

// ── 保存（FUXA 双层存储格式） ──
const save = async () => {
  saving.value = true
  try {
    const json = canvasRef.value?.toJSON()
    await updateScadaPage(Number(id), {
      name: page.value.name,
      description: page.value.description,
      width: page.value.width,
      height: page.value.height,
      background: page.value.background,
      config_json: JSON.stringify(json || {})
    })
    ElMessage.success('保存成功')
    hasUnsavedChanges.value = false
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// ── 图元拖放 ──
const dragStart = (e: DragEvent, widget: GaugeTypeDef) => {
  e.dataTransfer?.setData(
    'application/json',
    JSON.stringify({
      typeTag: widget.typeTag,
      name: widget.label,
      _isSvgWidget: true
    })
  )
}

const onCanvasDrop = (e: DragEvent) => {
  e.preventDefault()
  const data = e.dataTransfer?.getData('application/json')
  if (!data) return
  try {
    const widgetInfo = JSON.parse(data)
    const canvasWrapper =
      (e.target as HTMLElement).closest('.editor-canvas') ||
      document.querySelector('.editor-canvas')
    const rect = canvasWrapper?.getBoundingClientRect()
    const left = rect ? e.clientX - rect.left - 16 : 100
    const top = rect ? e.clientY - rect.top - 16 : 100

    if (widgetInfo._isSvgWidget) {
      const def = getGaugeDef(widgetInfo.typeTag)
      if (def) {
        const uid = genId('svg')
        const svgFragment = def.createSvg(uid, left, top, def.defaultWidth, def.defaultHeight)
        canvasRef.value?.addWidgetSVG(svgFragment, left, top)
        markDirty()
      }
    }
  } catch (err) {
    console.warn('Drop failed:', err)
  }
}

const onCanvasDragOver = (e: DragEvent) => {
  e.preventDefault()
}

// ── 选中/属性 ──
const onObjectSelected = (el: SVGElement | null) => {
  selectedObj.value = el
  if (el) {
    const transform = canvasRef.value?.getSelectedTransform()
    if (transform) {
      selectedProps.left = Math.round(transform.x)
      selectedProps.top = Math.round(transform.y)
      selectedProps.opacity = transform.opacity
    }
    selectedProps.fill = el.getAttribute('fill') || '#ffffff'
    selectedProps.stroke = el.getAttribute('stroke') || '#000000'
    selectedProps.strokeWidth = parseFloat(el.getAttribute('stroke-width') || '1')
  }
}

const onObjectDeselected = () => {
  selectedObj.value = null
}

const updateProp = (prop: string, value: any) => {
  if (!selectedObj.value) return
  canvasRef.value?.setSelectedTransform(prop, value)
}

// ── Fill/Stroke ──
const onFillChange = (color: string | null) => {
  if (!selectedObj.value) return
  selectedObj.value.setAttribute('fill', color || 'none')
  markDirty()
}

const onStrokeChange = (color: string | null) => {
  if (!selectedObj.value) return
  selectedObj.value.setAttribute('stroke', color || 'none')
  markDirty()
}

const onStrokeWidthChange = (width: number | undefined) => {
  if (!selectedObj.value) return
  selectedObj.value.setAttribute('stroke-width', String(width ?? 1))
  markDirty()
}

// ── 对齐 ──
const handleAlign = (direction: string) => {
  if (!selectedObj.value) return
  const pageW = page.value.width || 1920
  const pageH = page.value.height || 1080
  switch (direction) {
    case 'left':
      updateProp('left', 0)
      selectedProps.left = 0
      break
    case 'center':
      updateProp('left', Math.round(pageW / 2))
      selectedProps.left = Math.round(pageW / 2)
      break
    case 'right':
      updateProp('left', pageW - 100)
      selectedProps.left = pageW - 100
      break
    case 'top':
      updateProp('top', 0)
      selectedProps.top = 0
      break
    case 'middle':
      updateProp('top', Math.round(pageH / 2))
      selectedProps.top = Math.round(pageH / 2)
      break
    case 'bottom':
      updateProp('top', pageH - 50)
      selectedProps.top = pageH - 50
      break
  }
  markDirty()
}

// ── 数据绑定 ──
const openBindDialog = () => {
  bindForm.target = ''
  bindForm.deviceId = undefined
  bindForm.tagId = undefined
  bindForm.tagName = ''
  bindForm.prop = 'text'
  bindDialogVisible.value = true
}

const onDeviceSelect = (deviceId: number) => {
  fetchTags(deviceId)
}

const confirmBind = () => {
  if (!selectedObj.value || !bindForm.target) {
    ElMessage.warning('请选择绑定目标和点位')
    return
  }
  const elementId = selectedObj.value.getAttribute('id') || ''
  canvasRef.value?.setBinding(
    elementId,
    bindForm.target,
    bindForm.deviceId!,
    bindForm.tagId!,
    bindForm.tagName,
    bindForm.prop
  )
  bindDialogVisible.value = false
  ElMessage.success(`已绑定到 ${bindForm.tagName} → ${bindForm.target}`)
}

// ── 值处理配置 ──
const openValueProcessDialog = () => {
  if (selectedObj.value) {
    const vpStr = selectedObj.value.getAttribute('data-value-process')
    if (vpStr) {
      try {
        const vp = JSON.parse(vpStr)
        valueProcessForm.bitMask = vp.bitMask ?? 0
        valueProcessForm.ranges = vp.ranges ?? []
        valueProcessForm.actions = vp.actions ?? []
      } catch {
        valueProcessForm.bitMask = 0
        valueProcessForm.ranges = []
        valueProcessForm.actions = []
      }
    } else {
      valueProcessForm.bitMask = 0
      valueProcessForm.ranges = []
      valueProcessForm.actions = []
    }
  }
  valueProcessDialogVisible.value = true
}

const addRange = () => {
  valueProcessForm.ranges.push({ min: 0, max: 100, color: '#4ac080', stroke: '', text: '' })
}
const removeRange = (index: number) => {
  valueProcessForm.ranges.splice(index, 1)
}

const addAction = () => {
  valueProcessForm.actions.push({
    variableId: '',
    bitmask: 0,
    range: { min: 0, max: 100 },
    type: 'color' as GaugeActionType,
    options: { fill: '#ff0000', stroke: '' }
  })
}
const removeAction = (index: number) => {
  valueProcessForm.actions.splice(index, 1)
}

const confirmValueProcess = () => {
  if (!selectedObj.value) return
  const vp = {
    bitMask: valueProcessForm.bitMask || undefined,
    ranges: valueProcessForm.ranges.length ? valueProcessForm.ranges : undefined,
    actions: valueProcessForm.actions.length ? valueProcessForm.actions : undefined
  }
  if (!vp.bitMask) delete (vp as any).bitMask
  if (!vp.ranges?.length) delete (vp as any).ranges
  if (!vp.actions?.length) delete (vp as any).actions
  selectedObj.value.setAttribute('data-value-process', JSON.stringify(vp))
  valueProcessDialogVisible.value = false
  markDirty()
  ElMessage.success('值处理配置已保存')
}

// ── 事件配置 ──
const openEventDialog = () => {
  if (selectedObj.value) {
    const evtStr = selectedObj.value.getAttribute('data-events')
    if (evtStr) {
      try {
        eventForm.events = JSON.parse(evtStr)
      } catch {
        eventForm.events = []
      }
    } else {
      eventForm.events = []
    }
  }
  eventDialogVisible.value = true
}

const addEvent = () => {
  eventForm.events.push({
    type: 'click' as GaugeEventType,
    action: 'onpage' as GaugeEventActionType,
    actparam: ''
  })
}
const removeEvent = (index: number) => {
  eventForm.events.splice(index, 1)
}

const confirmEvents = () => {
  if (!selectedObj.value) return
  selectedObj.value.setAttribute('data-events', JSON.stringify(eventForm.events))
  eventDialogVisible.value = false
  markDirty()
  ElMessage.success('事件配置已保存')
}

// ── 清空画布 ──
const handleClear = async () => {
  try {
    await ElMessageBox.confirm('确认清空画布？此操作不可撤销。', '清空画布', { type: 'warning' })
    canvasRef.value?.clear()
    markDirty()
    ElMessage.success('画布已清空')
  } catch {
    /* cancelled */
  }
}

// ── 缩放 ──
const onZoomChange = (zoom: number) => {
  zoomLevel.value = Math.round(zoom * 100)
}
const setZoomFromSlider = (val: number) => {
  canvasRef.value?.setZoom(val / 100)
  zoomLevel.value = val
}
const handleZoomFit = () => {
  canvasRef.value?.zoomFit()
  nextTick(() => {
    zoomLevel.value = Math.round((canvasRef.value?.getZoom() ?? 1) * 100)
  })
}
const handleZoomReset = () => {
  canvasRef.value?.zoomReset()
  zoomLevel.value = 100
}

// ── 撤销/重做 ──
const handleUndo = () => {
  canvasRef.value?.undo()
  refreshUndoRedoState()
  markDirty()
}
const handleRedo = () => {
  canvasRef.value?.redo()
  refreshUndoRedoState()
  markDirty()
}

// ── 层级 ──
const handleBringForward = () => {
  canvasRef.value?.bringForward()
  markDirty()
}
const handleSendBackward = () => {
  canvasRef.value?.sendBackward()
  markDirty()
}
const handleBringToFront = () => {
  canvasRef.value?.bringToFront()
  markDirty()
}
const handleSendToBack = () => {
  canvasRef.value?.sendToBack()
  markDirty()
}

// ── 锁定 ──
const isLockedState = ref(false)
const handleLock = () => {
  canvasRef.value?.lockSelected()
  isLockedState.value = true
  markDirty()
}
const handleUnlock = () => {
  canvasRef.value?.unlockSelected()
  isLockedState.value = false
  markDirty()
}

// ── 复制 ──
const handleCopy = () => {
  canvasRef.value?.copySelected()
  markDirty()
}

// ── 网格开关 ──
const toggleGrid = () => {
  gridSize.value = gridSize.value > 0 ? 0 : 20
}

// ── 键盘快捷键 ──
const onKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (
      selectedObj.value &&
      !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)
    ) {
      canvasRef.value?.deleteSelected()
      markDirty()
    }
  }
  if (e.ctrlKey && e.key === 's') {
    e.preventDefault()
    save()
    hasUnsavedChanges.value = false
  }
  if (e.ctrlKey && e.key === 'z') {
    e.preventDefault()
    handleUndo()
  }
  if (e.ctrlKey && e.key === 'y') {
    e.preventDefault()
    handleRedo()
  }
  if (e.ctrlKey && e.key === 'd') {
    e.preventDefault()
    handleCopy()
  }
}

onMounted(() => {
  try {
    fetchPage()
    fetchCustomWidgets()
    fetchDevices()
  } catch (e: any) {
    ElMessage.error(e?.message || '初始化失败')
  }
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('beforeunload', onBeforeUnload)
  autoSaveTimer = setInterval(autoSave, 60_000)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('beforeunload', onBeforeUnload)
  if (autoSaveTimer) clearInterval(autoSaveTimer)
})
</script>

<template>
  <div class="editor-layout" @dragover="onCanvasDragOver" @drop="onCanvasDrop">
    <!-- ═══ 顶栏 ═══ -->
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <ElButton @click="router.push('/scada/pages')" size="small">← 返回</ElButton>
        <ElDivider direction="vertical" />
        <span class="text-14px font-600">{{ page.name || 'SCADA 编辑器' }}</span>
        <ElTag size="small" type="info" class="ml-8px">SVG</ElTag>
      </div>
      <div class="toolbar-center">
        <ElButtonGroup size="small">
          <ElTooltip content="撤销 (Ctrl+Z)" placement="bottom"
            ><ElButton :disabled="!canUndoState" @click="handleUndo">↶</ElButton></ElTooltip
          >
          <ElTooltip content="重做 (Ctrl+Y)" placement="bottom"
            ><ElButton :disabled="!canRedoState" @click="handleRedo">↷</ElButton></ElTooltip
          >
        </ElButtonGroup>
        <ElDivider direction="vertical" />
        <ElButtonGroup size="small">
          <ElTooltip content="复制 (Ctrl+D)" placement="bottom"
            ><ElButton @click="handleCopy">📋</ElButton></ElTooltip
          >
          <ElTooltip content="删除" placement="bottom"
            ><ElButton
              @click="
                canvasRef?.deleteSelected()
                markDirty()
              "
              >🗑️</ElButton
            ></ElTooltip
          >
        </ElButtonGroup>
        <ElDivider direction="vertical" />
        <ElButtonGroup size="small">
          <ElTooltip content="上移一层" placement="bottom"
            ><ElButton @click="handleBringForward">⬆</ElButton></ElTooltip
          >
          <ElTooltip content="下移一层" placement="bottom"
            ><ElButton @click="handleSendBackward">⬇</ElButton></ElTooltip
          >
          <ElTooltip content="置顶" placement="bottom"
            ><ElButton @click="handleBringToFront">⏫</ElButton></ElTooltip
          >
          <ElTooltip content="置底" placement="bottom"
            ><ElButton @click="handleSendToBack">⏬</ElButton></ElTooltip
          >
        </ElButtonGroup>
        <ElDivider direction="vertical" />
        <ElTooltip content="网格开关" placement="bottom"
          ><ElButton size="small" @click="toggleGrid">{{
            gridSize > 0 ? '⊞' : '⊡'
          }}</ElButton></ElTooltip
        >
        <ElTooltip content="锁定" placement="bottom"
          ><ElButton size="small" @click="isLockedState ? handleUnlock() : handleLock()">{{
            isLockedState ? '🔒' : '🔓'
          }}</ElButton></ElTooltip
        >
      </div>
      <div class="toolbar-right">
        <ElTooltip content="缩放" placement="bottom">
          <ElInputNumber
            v-model="zoomLevel"
            :min="10"
            :max="500"
            :step="10"
            size="small"
            style="width: 90px"
            @change="setZoomFromSlider"
          />%
        </ElTooltip>
        <ElButton size="small" @click="handleZoomFit">Fit</ElButton>
        <ElButton size="small" @click="handleZoomReset">1:1</ElButton>
        <ElDivider direction="vertical" />
        <ElButton type="danger" size="small" @click="handleClear">清空</ElButton>
        <ElButton type="primary" size="small" :loading="saving" @click="save">保存</ElButton>
      </div>
    </div>

    <!-- ═══ 主体 ═══ -->
    <div class="editor-body">
      <!-- ═══ 左侧图元面板 ═══ -->
      <div class="editor-left">
        <ElTabs v-model="leftTab" class="compact-tabs">
          <ElTabPane
            v-for="cat in GAUGE_CATEGORIES"
            :key="cat.key"
            :label="cat.label"
            :name="cat.key"
          >
            <div class="widget-grid">
              <div
                v-for="w in cat.defs"
                :key="w.typeTag"
                class="widget-item"
                draggable="true"
                @dragstart="dragStart($event, w)"
                :title="w.label"
              >
                <span class="widget-icon">{{ w.icon }}</span>
                <span class="widget-name">{{ w.label }}</span>
              </div>
            </div>
          </ElTabPane>
        </ElTabs>
      </div>

      <!-- ═══ 中间画布 ═══ -->
      <div class="editor-canvas">
        <SvgCanvas
          ref="canvasRef"
          :width="page.width || 1920"
          :height="page.height || 1080"
          :background="page.background || '#1a1a2e'"
          :grid-size="gridSize"
          @object:selected="onObjectSelected"
          @object:deselected="onObjectDeselected"
          @canvas:changed="markDirty"
          @zoom-change="onZoomChange"
        />
      </div>

      <!-- ═══ 右侧属性面板（FUXA 三段式） ═══ -->
      <div class="editor-right">
        <div v-if="!selectedObj" class="no-selection">
          <p>选择图元查看属性</p>
        </div>

        <div v-else class="prop-panel">
          <!-- ═══ Interactivity ═══ -->
          <div class="prop-section">
            <div class="prop-section-title">Interactivity</div>
            <ElForm label-width="50px" size="small" class="compact-form">
              <ElFormItem label="ID"
                ><ElInput :model-value="selectedWidgetId" disabled size="small"
              /></ElFormItem>
              <ElFormItem label="类型"
                ><ElInput :model-value="selectedWidgetType" disabled size="small"
              /></ElFormItem>
            </ElForm>
          </div>

          <!-- ═══ Transform ═══ -->
          <div class="prop-section">
            <div class="prop-section-title">Transform</div>
            <ElForm label-width="50px" size="small" class="compact-form">
              <ElFormItem label="X"
                ><ElInputNumber
                  v-model="selectedProps.left"
                  :step="1"
                  @change="updateProp('left', $event)"
                  class="w-full"
                  size="small"
              /></ElFormItem>
              <ElFormItem label="Y"
                ><ElInputNumber
                  v-model="selectedProps.top"
                  :step="1"
                  @change="updateProp('top', $event)"
                  class="w-full"
                  size="small"
              /></ElFormItem>
              <ElFormItem label="透明度"
                ><ElSlider
                  v-model="selectedProps.opacity"
                  :min="0"
                  :max="1"
                  :step="0.05"
                  @change="updateProp('opacity', $event)"
              /></ElFormItem>
            </ElForm>
          </div>

          <!-- ═══ Fill / Stroke ═══ -->
          <div class="prop-section">
            <div class="prop-section-title">Fill / Stroke</div>
            <ElForm label-width="50px" size="small" class="compact-form">
              <ElFormItem label="填充"
                ><ElColorPicker v-model="selectedProps.fill" @change="onFillChange" size="small"
              /></ElFormItem>
              <ElFormItem label="描边"
                ><ElColorPicker
                  v-model="selectedProps.stroke"
                  @change="onStrokeChange"
                  size="small"
              /></ElFormItem>
              <ElFormItem label="线宽"
                ><ElInputNumber
                  v-model="selectedProps.strokeWidth"
                  :min="0"
                  :max="20"
                  :step="0.5"
                  @change="onStrokeWidthChange"
                  class="w-full"
                  size="small"
              /></ElFormItem>
            </ElForm>
          </div>

          <!-- ═══ Align ═══ -->
          <div class="prop-section">
            <div class="prop-section-title">Align</div>
            <div class="flex gap-4px flex-wrap">
              <ElTooltip content="左对齐" placement="bottom"
                ><ElButton size="small" @click="handleAlign('left')">⫷</ElButton></ElTooltip
              >
              <ElTooltip content="水平居中" placement="bottom"
                ><ElButton size="small" @click="handleAlign('center')">⫿</ElButton></ElTooltip
              >
              <ElTooltip content="右对齐" placement="bottom"
                ><ElButton size="small" @click="handleAlign('right')">⫸</ElButton></ElTooltip
              >
              <ElTooltip content="上对齐" placement="bottom"
                ><ElButton size="small" @click="handleAlign('top')">⊤</ElButton></ElTooltip
              >
              <ElTooltip content="垂直居中" placement="bottom"
                ><ElButton size="small" @click="handleAlign('middle')">⊖</ElButton></ElTooltip
              >
              <ElTooltip content="下对齐" placement="bottom"
                ><ElButton size="small" @click="handleAlign('bottom')">⊥</ElButton></ElTooltip
              >
            </div>
          </div>

          <!-- ═══ Data Binding ═══ -->
          <div class="prop-section">
            <div class="prop-section-title">Data Binding</div>
            <ElButton size="small" type="primary" @click="openBindDialog" style="width: 100%"
              >配置信号绑定</ElButton
            >
          </div>

          <!-- ═══ Value Processing ═══ -->
          <div class="prop-section">
            <div class="prop-section-title">Value Processing</div>
            <ElButton size="small" @click="openValueProcessDialog" style="width: 100%"
              >位掩码/范围/动作</ElButton
            >
          </div>

          <!-- ═══ Events ═══ -->
          <div class="prop-section">
            <div class="prop-section-title">Events</div>
            <ElButton size="small" @click="openEventDialog" style="width: 100%"
              >配置事件动作</ElButton
            >
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ 绑定对话框 ═══ -->
    <ElDialog v-model="bindDialogVisible" title="数据绑定" width="500px">
      <ElForm label-width="80px">
        <ElFormItem label="绑定目标">
          <ElSelect v-model="bindForm.target" placeholder="选择目标" style="width: 100%">
            <ElOption label="值(value)" value="value" />
            <ElOption label="填充色(fill)" value="fill" />
            <ElOption label="描边色(stroke)" value="stroke" />
            <ElOption label="文本(text)" value="text" />
            <ElOption label="状态(state)" value="state" />
            <ElOption label="液位(level)" value="level" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="设备">
          <ElSelect
            v-model="bindForm.deviceId"
            placeholder="选择设备"
            style="width: 100%"
            @change="onDeviceSelect"
          >
            <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="点位">
          <ElSelect
            v-model="bindForm.tagName"
            placeholder="选择点位"
            filterable
            style="width: 100%"
          >
            <ElOption v-for="t in deviceTags" :key="t.id" :label="t.name" :value="t.name" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="属性">
          <ElSelect v-model="bindForm.prop" style="width: 100%">
            <ElOption label="文本" value="text" /><ElOption label="填充" value="fill" /><ElOption
              label="描边"
              value="stroke"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="bindDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="confirmBind">确定</ElButton>
      </template>
    </ElDialog>

    <!-- ═══ 值处理对话框 ═══ -->
    <ElDialog v-model="valueProcessDialogVisible" title="值处理配置" width="680px">
      <ElCollapse>
        <ElCollapseItem title="位掩码 (Bitmask)" name="bitmask">
          <ElInputNumber v-model="valueProcessForm.bitMask" :min="0" :max="32" :step="1" />
        </ElCollapseItem>

        <ElCollapseItem title="范围颜色映射 (Ranges)" name="ranges">
          <div v-for="(range, idx) in valueProcessForm.ranges" :key="idx" class="range-row">
            <ElInputNumber v-model="range.min" :step="1" size="small" style="width: 80px" />
            <span class="mx-4px">~</span>
            <ElInputNumber v-model="range.max" :step="1" size="small" style="width: 80px" />
            <ElColorPicker v-model="range.color" size="small" />
            <ElColorPicker v-model="range.stroke" size="small" />
            <ElInput v-model="range.text" placeholder="文本" size="small" style="width: 80px" />
            <ElButton size="small" type="danger" @click="removeRange(idx)">×</ElButton>
          </div>
          <ElButton size="small" @click="addRange">+ 添加范围</ElButton>
        </ElCollapseItem>

        <ElCollapseItem title="动作执行 (Actions)" name="actions">
          <div v-for="(act, idx) in valueProcessForm.actions" :key="idx" class="action-row">
            <ElSelect v-model="act.type" size="small" style="width: 100px">
              <ElOption
                v-for="at in [
                  'hide',
                  'show',
                  'blink',
                  'color',
                  'rotate',
                  'clockwise',
                  'anticlockwise',
                  'move',
                  'stop'
                ]"
                :key="at"
                :label="at"
                :value="at"
              />
            </ElSelect>
            <ElInputNumber v-model="act.range.min" size="small" style="width: 70px" />
            <span>~</span>
            <ElInputNumber v-model="act.range.max" size="small" style="width: 70px" />
            <ElButton size="small" type="danger" @click="removeAction(idx)">×</ElButton>
          </div>
          <ElButton size="small" @click="addAction">+ 添加动作</ElButton>
        </ElCollapseItem>
      </ElCollapse>
      <template #footer>
        <ElButton @click="valueProcessDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="confirmValueProcess">确定</ElButton>
      </template>
    </ElDialog>

    <!-- ═══ 事件配置对话框 ═══ -->
    <ElDialog v-model="eventDialogVisible" title="事件配置" width="600px">
      <div v-for="(evt, idx) in eventForm.events" :key="idx" class="event-row">
        <ElSelect v-model="evt.type" size="small" style="width: 100px">
          <ElOption
            v-for="t in ['click', 'dblclick', 'mousedown', 'mouseover']"
            :key="t"
            :label="t"
            :value="t"
          />
        </ElSelect>
        <span>→</span>
        <ElSelect v-model="evt.action" size="small" style="width: 120px">
          <ElOption
            v-for="a in [
              'onpage',
              'onwindow',
              'ondialog',
              'onSetValue',
              'onToggleValue',
              'onRunScript',
              'onclose'
            ]"
            :key="a"
            :label="a"
            :value="a"
          />
        </ElSelect>
        <ElInput v-model="evt.actparam" placeholder="参数" size="small" style="width: 120px" />
        <ElButton size="small" type="danger" @click="removeEvent(idx)">×</ElButton>
      </div>
      <ElButton size="small" @click="addEvent">+ 添加事件</ElButton>
      <template #footer>
        <ElButton @click="eventDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="confirmEvents">确定</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.editor-layout {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
  background: #0d1117;
}
.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  border-bottom: 1px solid #21262d;
  background: #161b22;
  flex-shrink: 0;
}
.toolbar-left,
.toolbar-center,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
}
.editor-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}
.editor-left {
  width: 180px;
  border-right: 1px solid #21262d;
  overflow-y: auto;
  background: #161b22;
  flex-shrink: 0;
}
.editor-canvas {
  flex: 1;
  overflow: auto;
  background: #0d1117;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 16px;
}
.editor-right {
  width: 260px;
  border-left: 1px solid #21262d;
  overflow-y: auto;
  background: #161b22;
  flex-shrink: 0;
}
.widget-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px;
  padding: 4px;
}
.widget-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px 4px;
  border-radius: 4px;
  border: 1px solid transparent;
  cursor: grab;
  transition: all 0.15s;
  font-size: 12px;
}
.widget-item:hover {
  border-color: #4a9eff;
  background: rgba(74, 158, 255, 0.1);
}
.widget-icon {
  font-size: 20px;
  line-height: 1;
}
.widget-name {
  margin-top: 2px;
  color: #9ca3af;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.prop-section {
  border-bottom: 1px solid #21262d;
  padding: 8px 10px;
}
.prop-section-title {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.no-selection {
  padding: 20px;
  text-align: center;
  color: #4b5563;
}
.compact-form :deep(.el-form-item) {
  margin-bottom: 4px;
}
.compact-form :deep(.el-form-item__label) {
  font-size: 11px;
}
.range-row,
.action-row,
.event-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.compact-tabs :deep(.el-tabs__header) {
  margin: 0;
}
.compact-tabs :deep(.el-tabs__item) {
  font-size: 11px;
  padding: 0 8px;
  height: 30px;
  line-height: 30px;
}
</style>
