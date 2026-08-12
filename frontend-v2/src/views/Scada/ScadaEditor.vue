<script setup lang="ts">
/**
 * SCADA 可视化编辑器 - FUXA 风格 SVG 画布
 *
 * 布局：左侧图元面板（SVG缩略图） | 中间SVG画布 | 右侧属性面板
 * 画布引擎：原生 SVG DOM（参照 FUXA 架构）
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
  ElSwitch,
  ElTag
} from 'element-plus'
import {
  getScadaPage,
  updateScadaPage,
  getScadaWidgets,
  getDeviceTags,
  getAllDevices,
  getScadaPages,
  unwrap,
  unwrapList
} from '@/api/modbus'
import SvgCanvas from './SvgCanvas.vue'
import { svgWidgets, svgWidgetCategories, getSvgWidgetsByCategory, genId } from './widgets/svg-widgets'
import type { SvgWidgetDef } from './widgets/svg-widgets'
void svgWidgetCategories
void getSvgWidgetsByCategory

defineOptions({ name: 'ScadaEditor' })

const route = useRoute()
const router = useRouter()
const id = route.params.id as string

// ── 画布数据 ──
const page = ref<any>({ name: '', config_json: '{}', width: 1920, height: 1080, background: '#1a1a2e' })
const saving = ref(false)
const canvasRef = ref<InstanceType<typeof SvgCanvas>>()

// ── 缩放状态 ──
const zoomLevel = ref(100)

// ── 网格状态 ──
const gridSize = ref(0)

// ── 撤销/重做状态 ──
const canUndoState = ref(false)
const canRedoState = ref(false)

// ── 锁定状态 ──
const isLockedState = ref(false)

// ── 更新撤销/重做状态 ──
const refreshUndoRedoState = () => {
  canUndoState.value = canvasRef.value?.canUndo() ?? false
  canRedoState.value = canvasRef.value?.canRedo() ?? false
}

// ── 未保存变更追踪 & 自动保存 ──
const hasUnsavedChanges = ref(false)
let autoSaveTimer: ReturnType<typeof setInterval> | null = null

const markDirty = () => { hasUnsavedChanges.value = true; refreshUndoRedoState() }

const autoSave = async () => {
  if (!hasUnsavedChanges.value) return
  await save()
  hasUnsavedChanges.value = false
}

const onBeforeUnload = (e: BeforeUnloadEvent) => {
  if (hasUnsavedChanges.value) {
    e.preventDefault()
  }
}

// ── 左侧面板 ──
const leftTab = ref('builtin')
const customWidgets = ref<any[]>([])
const devices = ref<any[]>([])
const widgetKeyword = ref('')

const filteredBuiltin = computed(() => {
  const kw = widgetKeyword.value.trim().toLowerCase()
  if (!kw) return svgWidgets
  return svgWidgets.filter((w) => w.name.toLowerCase().includes(kw) || w.typeTag.toLowerCase().includes(kw))
})
const filteredBuiltinCategories = computed(() => {
  return [...new Set(filteredBuiltin.value.map((w) => w.category))]
})
const filteredCustom = computed(() => {
  const kw = widgetKeyword.value.trim().toLowerCase()
  if (!kw) return customWidgets.value
  return customWidgets.value.filter(
    (w) => (w.name || '').toLowerCase().includes(kw) || (w.category || '').toLowerCase().includes(kw)
  )
})

// ── 右侧属性面板 ──
const selectedObj = ref<SVGElement | null>(null)
const selectedCount = ref(0)
const selectedProps = reactive<any>({
  left: 0,
  top: 0,
  w: 0,
  h: 0,
  angle: 0,
  opacity: 1
})
const selectedStyle = reactive<any>({
  fill: '',
  stroke: '',
  strokeWidth: 1,
  fontSize: 14,
  rx: 0,
  text: ''
})
const widgetName = ref('')
const isTextBound = computed(() => {
  if (!selectedObj.value) return false
  const textEl = selectedObj.value.querySelector('text[data-bind-target]')
  const target = textEl?.getAttribute('data-bind-target')
  const id = selectedWidgetId.value
  const def = target && id ? canvasRef.value?.getGaugeSettings(id)?.bindings?.[target] : undefined
  return !!def?.variableId
})

// ── 选中图元的类型信息 ──
const selectedWidgetType = computed(() => {
  if (!selectedObj.value) return ''
  return selectedObj.value.getAttribute('type') || ''
})

const selectedWidgetId = computed(() => {
  if (!selectedObj.value) return ''
  return selectedObj.value.getAttribute('id') || ''
})

// ── 绑定配置（v2 多属性域） ──
const bindDialogVisible = ref(false)
const bindForm = reactive<{
  deviceId: number | undefined
  tagId: number | undefined
  tagName: string
  events: Array<{
    id: string
    type: string
    action: string
    deviceId: number | undefined
    tagId: number | undefined
    tagName: string
    tags: any[]
    pageId: number | undefined
    valueType: string
    fixedValue: string
    onValue: number
    offValue: number
    min: number
    max: number
  }>
  domains: Record<
    string,
    {
      bindEnabled: boolean
      variableId: string
      deviceId: number | undefined
      tagId: number | undefined
      tagName: string
      tags: any[]
      variableValue: string
      bitmask: number
      format: string
      ranges: Array<{ min: number; max: number; text: string; color: string; stroke: string }>
    }
  >
}>({
  deviceId: undefined,
  tagId: undefined,
  tagName: '',
  events: [],
  domains: {}
})

// 画面列表（onpage 事件目标）
const pagesList = ref<any[]>([])

const fetchScadaPagesList = async () => {
  try {
    const body = unwrap(await getScadaPages())
    pagesList.value = Array.isArray(body) ? body : unwrapList(await getScadaPages()).list
  } catch {
    pagesList.value = []
  }
}

const selectedBindings = computed<Array<{ target: string; tagName: string; hasRanges: boolean; bound: boolean }>>(() => {
  const id = selectedWidgetId.value
  if (!id || !canvasRef.value) return []
  return (canvasRef.value.getBindingDefs(id) || []).map(({ target, def }) => ({
    target,
    tagName: def.variableId || '',
    hasRanges: (def.ranges || []).length > 0,
    bound: !!def.variableId
  }))
})

// ── 加载页面数据 ──
const fetchPage = async () => {
  try {
    const body = unwrap(await getScadaPage(Number(id)))
    page.value = body || {}
    await nextTick()
    // 加载画布配置
    const config = body?.config_json
    if (config) {
      try {
        const json = typeof config === 'string' ? JSON.parse(config) : config
        page.value.__engine = json?.__engine || 'svg'
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
    devices.value = unwrapList(await getAllDevices({ enabled: true })).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取设备列表失败')
  }
}

const fetchTags = async (deviceId: number): Promise<any[]> => {
  try {
    const res = await getDeviceTags(deviceId)
    const body = unwrap(res)
    return Array.isArray(body) ? body : unwrapList(res).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取点位列表失败')
    return []
  }
}

/** 为单个绑定域加载点位列表（每域独立） */
const onDomainDeviceSelect = async (domain: any) => {
  domain.tags = []
  domain.tagId = undefined
  domain.tagName = ''
  if (domain.deviceId) {
    domain.tags = await fetchTags(domain.deviceId)
  }
}

const onDomainTagSelect = (domain: any) => {
  const tag = domain.tags.find((t: any) => t.id === domain.tagId)
  domain.tagName = tag?.name || ''
}

// ── 保存 ──
const save = async () => {
  // 保护：maotu 引擎页面禁止用经典编辑器覆盖
  if (page.value.__engine === 'maotu') {
    ElMessage.warning('该画面由 maotu 组态引擎创建，请在「maotu 编辑器」中编辑')
    router.push(`/scada/m-editor/${id}`)
    return
  }
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

/** 拖拽开始 — 传递图元定义的 typeTag 和名称 */
const dragStart = (e: DragEvent, widget: SvgWidgetDef) => {
  e.dataTransfer?.setData('application/json', JSON.stringify({
    typeTag: widget.typeTag,
    name: widget.name,
    _isSvgWidget: true
  }))
}

/** 自定义图元放置 */
const dragStartCustom = (e: DragEvent, widget: any) => {
  e.dataTransfer?.setData('application/json', JSON.stringify({
    _isCustomWidget: true,
    id: widget.id,
    name: widget.name,
    source_type: widget.source_type,
    source_data: widget.source_data
  }))
}

/** 画布放置 */
const onCanvasDrop = (e: DragEvent) => {
  e.preventDefault()
  const data = e.dataTransfer?.getData('application/json')
  if (!data) return
  try {
    const widgetInfo = JSON.parse(data)

    // 计算放置位置（相对于画布容器）
    const canvasWrapper = (e.target as HTMLElement).closest('.editor-canvas')
      || document.querySelector('.editor-canvas')
    const rect = canvasWrapper?.getBoundingClientRect()
    const left = rect ? e.clientX - rect.left - 16 : 100  // -16 补偿 padding
    const top = rect ? e.clientY - rect.top - 16 : 100

    if (widgetInfo._isSvgWidget) {
      // 内置 SVG 图元
      const widgetDef = svgWidgets.find(w => w.typeTag === widgetInfo.typeTag && w.name === widgetInfo.name)
      if (widgetDef) {
        const uid = genId('w')
        const svgFragment = widgetDef.createSvg(uid, left, top, widgetDef.defaultWidth, widgetDef.defaultHeight)
        canvasRef.value?.addWidgetSVG(svgFragment, left, top)
        markDirty()
      }
    } else if (widgetInfo._isCustomWidget) {
      // 自定义图元：如果 source_data 是 SVG 字符串
      if (widgetInfo.source_type === 'svg' && widgetInfo.source_data) {
        canvasRef.value?.addWidgetSVG(widgetInfo.source_data, left, top)
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

/** 自定义图元点击放置 */
const addCustomWidget = (widget: any) => {
  if (widget.source_type === 'svg' && widget.source_data) {
    canvasRef.value?.addWidgetSVG(widget.source_data, 200, 200)
    markDirty()
  }
}

// ── 选中/属性 ──

const onObjectSelected = (el: SVGElement | null) => {
  selectedObj.value = el
  if (el) {
    const transform = canvasRef.value?.getSelectedTransform()
    if (transform) {
      selectedProps.left = transform.x
      selectedProps.top = transform.y
      selectedProps.w = transform.w
      selectedProps.h = transform.h
      selectedProps.angle = transform.angle
      selectedProps.opacity = transform.opacity
    }
    refreshSelectedStyle()
    widgetName.value = canvasRef.value?.getGaugeName(selectedWidgetId.value) || ''
    selectedCount.value = canvasRef.value?.getSelectedCount() || 1
    isLockedState.value = canvasRef.value?.isLocked() ?? false
  }
}

const refreshSelectedStyle = () => {
  if (!selectedObj.value) return
  selectedStyle.fill = canvasRef.value?.getShapeStyle('fill') || ''
  selectedStyle.stroke = canvasRef.value?.getShapeStyle('stroke') || ''
  selectedStyle.strokeWidth = parseFloat(canvasRef.value?.getShapeStyle('stroke-width') || '') || 0
  selectedStyle.fontSize = parseFloat(canvasRef.value?.getShapeStyle('font-size') || '') || 0
  const rectEl = selectedObj.value.querySelector('rect')
  selectedStyle.rx = rectEl ? parseFloat(rectEl.getAttribute('rx') || '0') || 0 : 0
  const textEl = selectedObj.value.querySelector('text') as SVGElement | null
  selectedStyle.text = textEl?.textContent || ''
}

const onObjectDeselected = () => {
  selectedObj.value = null
}

const updateProp = (prop: string, value: any) => {
  if (!selectedObj.value) return
  canvasRef.value?.setSelectedTransform(prop, value)
  markDirty()
}

const applyStyle = (prop: 'fill' | 'stroke' | 'stroke-width' | 'rx' | 'font-size', value: any) => {
  if (!selectedObj.value || value === undefined || value === null) return
  canvasRef.value?.applyShapeStyle(prop, String(value))
  markDirty()
}

const onTextInput = (value: string) => {
  if (!selectedObj.value) return
  canvasRef.value?.setFirstTextContent(String(value))
  markDirty()
}

const onNameInput = (value: string) => {
  if (!selectedObj.value) return
  canvasRef.value?.setGaugeName(selectedWidgetId.value, value)
  markDirty()
}

// ── 对齐 / 分布 ──
const getAligned = (_mode: string, _dist = false) => {
  canvasRef.value?.alignSelected(_mode as any)
  markDirty()
}
const getDistributed = (mode: 'horizontal' | 'vertical') => {
  if (selectedCount.value < 3) {
    ElMessage.info('分布需要至少选中 3 个图元')
    return
  }
  canvasRef.value?.distributeSelected(mode)
  markDirty()
}

// ── 数据绑定（v2 多属性域） ──

const FORMAT_OPTIONS = [
  { label: '原始值', value: '' },
  { label: '整数', value: '0' },
  { label: '1 位小数', value: '1' },
  { label: '2 位小数', value: '2' },
  { label: '3 位小数', value: '3' },
  { label: '4 位小数', value: '4' },
  { label: '十六进制', value: 'HEX' },
  { label: '二进制', value: 'BIN' }
]

const openBindDialog = () => {
  const id = selectedWidgetId.value
  if (!id || !canvasRef.value) return
  const defs = canvasRef.value.getBindingDefs(id)
  bindForm.deviceId = undefined
  bindForm.tagId = undefined
  bindForm.tagName = ''
  bindForm.events = []
  bindForm.domains = {}
  // 载入交互事件（M2）
  const events = canvasRef.value.getGaugeEvents(id)
  for (const ev of events) {
    const o = ev.actoptions || {}
    bindForm.events.push({
      id: `ev_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      type: ev.type || 'click',
      action: ev.action || 'onSetValue',
      deviceId: o.deviceId,
      tagId: o.tagId,
      tagName: o.tagName || '',
      tags: [],
      pageId: o.pageId,
      valueType: o.valueType || 'fixed',
      fixedValue: String(o.fixedValue ?? 1),
      onValue: Number(o.onValue ?? 1),
      offValue: Number(o.offValue ?? 0),
      min: Number(o.min ?? 0),
      max: Number(o.max ?? 100)
    })
    if (o.deviceId) fetchTags(o.deviceId)
  }
  fetchScadaPagesList()
  for (const { target, def } of defs) {
    const [devId, tagName] = (def.variableId || '').split(':')
    bindForm.domains[target] = {
      bindEnabled: !!def.variableId,
      variableId: def.variableId,
      deviceId: devId ? Number(devId) : undefined,
      tagId: def.tagId,
      tagName: tagName || '',
      tags: [],
      variableValue: def.variableValue,
      bitmask: def.bitmask || 0,
      format: def.format || '',
      ranges: (def.ranges || []).map((r) => ({
        min: r.min,
        max: r.max,
        text: r.text || '',
        color: r.color || '',
        stroke: r.stroke || ''
      }))
    }
    if (devId) onDomainDeviceSelect(bindForm.domains[target])
  }
  bindDialogVisible.value = true
}

const resetBindForm = () => {
  bindForm.domains = {}
  bindForm.events = []
}

const addRange = (target: string) => {
  const domain = bindForm.domains[target]
  if (!domain) return
  const last = domain.ranges[domain.ranges.length - 1]
  domain.ranges.push({
    min: last ? last.max + 0.01 : 0,
    max: last ? last.max + 1 : 1,
    text: '',
    color: '',
    stroke: ''
  })
}

const removeRange = (target: string, index: number) => {
  const domain = bindForm.domains[target]
  if (domain) domain.ranges.splice(index, 1)
}

// ── 交互事件编辑（M2） ──

const addEvent = () => {
  bindForm.events.push({
    id: `ev_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    type: 'click',
    action: 'onSetValue',
    deviceId: undefined,
    tagId: undefined,
    tagName: '',
    tags: [],
    pageId: undefined,
    valueType: 'fixed',
    fixedValue: '1',
    onValue: 1,
    offValue: 0,
    min: 0,
    max: 100
  })
}

const removeEvent = (id: string) => {
  const idx = bindForm.events.findIndex((e) => e.id === id)
  if (idx >= 0) bindForm.events.splice(idx, 1)
}

const onEventDeviceSelect = async (ev: any) => {
  ev.tagId = undefined
  ev.tagName = ''
  ev.tags = []
  if (!ev.deviceId) return
  try {
    const res = await getDeviceTags(ev.deviceId)
    const body = unwrap(res)
    ev.tags = Array.isArray(body) ? body : unwrapList(res).list
  } catch {
    ev.tags = []
  }
}

const onEventTagSelect = (ev: any) => {
  const tag = ev.tags.find((t: any) => t.id === ev.tagId)
  ev.tagName = tag?.name || ''
}

const confirmBind = () => {
  if (!selectedObj.value) return
  const elementId = selectedWidgetId.value
  if (!elementId || !canvasRef.value) return

  for (const [target, domain] of Object.entries(bindForm.domains)) {
    // 绑定 Tag 或使用静态值；两者皆空则移除该域
    const def = {
      variableId: domain.bindEnabled && domain.deviceId && domain.tagName
        ? `${domain.deviceId}:${domain.tagName}`
        : '',
      tagId: domain.bindEnabled && domain.tagId ? domain.tagId : undefined,
      variableValue: domain.variableValue,
      bitmask: domain.bitmask || 0,
      format: domain.format || '',
      ranges: domain.ranges.map((r) => ({
        min: r.min,
        max: r.max,
        text: r.text,
        color: r.color,
        stroke: r.stroke
      })),
      readonly: false
    }
    const isEmpty =
      !def.variableId && def.variableValue === '' && def.ranges.length === 0
    canvasRef.value.setBindingDef(elementId, target, isEmpty ? null : def)
  }
  // 交互事件（M2/M3）
  const events = bindForm.events
    .filter((ev) => (ev.action === 'onpage' ? ev.pageId : ev.deviceId && ev.tagId))
    .map((ev) => ({
      type: ev.type,
      action: ev.action,
      actoptions: ev.action === 'onpage'
        ? { pageId: ev.pageId, pageName: pagesList.value.find((p: any) => p.id === ev.pageId)?.name || '' }
        : {
            deviceId: ev.deviceId,
            tagId: ev.tagId,
            tagName: ev.tagName,
            valueType: ev.action === 'onToggleValue' ? 'toggle' : ev.valueType,
            fixedValue: ev.valueType === 'fixed' ? ev.fixedValue : undefined,
            onValue: ev.action === 'onToggleValue' ? ev.onValue : undefined,
            offValue: ev.action === 'onToggleValue' ? ev.offValue : undefined,
            min: ev.valueType === 'slider' ? ev.min : undefined,
            max: ev.valueType === 'slider' ? ev.max : undefined
          }
    }))
  canvasRef.value.setGaugeEvents(elementId, events)
  bindDialogVisible.value = false
  ElMessage.success('绑定配置已保存')
  markDirty()
}

// ── 清空画布（带确认） ──
const handleClear = async () => {
  try {
    await ElMessageBox.confirm('确认清空画布？此操作不可撤销。', '清空画布', { type: 'warning' })
    canvasRef.value?.clear()
    markDirty()
    ElMessage.success('画布已清空')
  } catch {
    // cancelled
  }
}

// ── 缩放操作 ──
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

// ── 层级操作 ──
const handleBringForward = () => { canvasRef.value?.bringForward(); markDirty() }
const handleSendBackward = () => { canvasRef.value?.sendBackward(); markDirty() }
const handleBringToFront = () => { canvasRef.value?.bringToFront(); markDirty() }
const handleSendToBack = () => { canvasRef.value?.sendToBack(); markDirty() }

// ── 锁定/解锁 ──
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
  const inInput = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedObj.value && !inInput) {
      canvasRef.value?.deleteSelected()
      markDirty()
    }
  }
  // 方向键微调位置（1px，Shift=10px）
  if (selectedObj.value && !inInput && (e.key.startsWith('Arrow'))) {
    const step = e.shiftKey ? 10 : 1
    const t = canvasRef.value?.getSelectedTransform()
    if (!t) return
    e.preventDefault()
    if (e.key === 'ArrowLeft') canvasRef.value?.setSelectedTransform('left', t.x - step)
    else if (e.key === 'ArrowRight') canvasRef.value?.setSelectedTransform('left', t.x + step)
    else if (e.key === 'ArrowUp') canvasRef.value?.setSelectedTransform('top', t.y - step)
    else if (e.key === 'ArrowDown') canvasRef.value?.setSelectedTransform('top', t.y + step)
    markDirty()
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
    <!-- 顶栏 -->
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <ElButton @click="router.push('/scada/pages')" size="small">← 返回</ElButton>
        <ElDivider direction="vertical" />
        <span class="text-14px font-600">{{ page.name || 'SCADA 编辑器' }}</span>
        <ElTag size="small" type="info" class="ml-8px">SVG</ElTag>
      </div>
      <div class="toolbar-center">
        <!-- 撤销/重做 -->
        <ElButtonGroup size="small">
          <ElTooltip content="撤销 (Ctrl+Z)" placement="bottom">
            <ElButton :disabled="!canUndoState" @click="handleUndo">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z"/></svg>
            </ElButton>
          </ElTooltip>
          <ElTooltip content="重做 (Ctrl+Y)" placement="bottom">
            <ElButton :disabled="!canRedoState" @click="handleRedo">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M18.4 10.6C16.55 8.99 14.15 8 11.5 8c-4.65 0-8.58 3.03-9.96 7.22L3.9 16c1.05-3.19 4.05-5.5 7.6-5.5 1.95 0 3.73.72 5.12 1.88L13 16h9V7l-3.6 3.6z"/></svg>
            </ElButton>
          </ElTooltip>
        </ElButtonGroup>

        <ElDivider direction="vertical" />

        <!-- 缩放控件 -->
        <ElButtonGroup size="small">
          <ElTooltip content="缩小" placement="bottom">
            <ElButton @click="setZoomFromSlider(Math.max(10, zoomLevel - 10))">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14zM7 9h5v1H7z"/></svg>
            </ElButton>
          </ElTooltip>
          <ElButton class="zoom-display" @click="handleZoomReset" style="min-width: 52px; font-size: 12px">
            {{ zoomLevel }}%
          </ElButton>
          <ElTooltip content="放大" placement="bottom">
            <ElButton @click="setZoomFromSlider(Math.min(300, zoomLevel + 10))">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14zm-.5-7h2v2.5H14v1h-2V11H9.5v-1H12V7z"/></svg>
            </ElButton>
          </ElTooltip>
        </ElButtonGroup>
        <ElButtonGroup size="small">
          <ElTooltip content="适应画布" placement="bottom">
            <ElButton @click="handleZoomFit">适应</ElButton>
          </ElTooltip>
        </ElButtonGroup>

        <ElDivider direction="vertical" />

        <!-- 层级 -->
        <ElButtonGroup size="small">
          <ElTooltip content="上移一层" placement="bottom">
            <ElButton :disabled="!selectedObj" @click="handleBringForward">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M2 2h20v20H2V2zm2 2v16h16V4H4z"/></svg>
            </ElButton>
          </ElTooltip>
          <ElTooltip content="下移一层" placement="bottom">
            <ElButton :disabled="!selectedObj" @click="handleSendBackward">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M2 2h20v20H2V2z"/></svg>
            </ElButton>
          </ElTooltip>
          <ElTooltip content="置顶" placement="bottom">
            <ElButton :disabled="!selectedObj" @click="handleBringToFront">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M2 2h20v4H2V2zm0 6h20v4H2V8zm0 6h20v4H2v-4zm0 6h20v2H2v-2z"/></svg>
            </ElButton>
          </ElTooltip>
          <ElTooltip content="置底" placement="bottom">
            <ElButton :disabled="!selectedObj" @click="handleSendToBack">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M2 2h20v2H2V2zm0 4h20v4H2V6zm0 6h20v4H2v-4zm0 6h20v4H2v-4z"/></svg>
            </ElButton>
          </ElTooltip>
        </ElButtonGroup>
      </div>
      <div class="toolbar-right">
        <!-- 锁定/解锁 -->
        <ElTooltip :content="isLockedState ? '解锁' : '锁定'" placement="bottom">
          <ElButton size="small" :disabled="!selectedObj" @click="isLockedState ? handleUnlock() : handleLock()">
            <svg v-if="isLockedState" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zM9 8V6c0-1.66 1.34-3 3-3s3 1.34 3 3v2H9z"/></svg>
            <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 17c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm6-9h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h1.9c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10z"/></svg>
          </ElButton>
        </ElTooltip>
        <!-- 复制 -->
        <ElTooltip content="复制 (Ctrl+D)" placement="bottom">
          <ElButton size="small" :disabled="!selectedObj" @click="handleCopy">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
          </ElButton>
        </ElTooltip>
        <!-- 网格 -->
        <ElTooltip :content="gridSize > 0 ? '关闭网格' : '显示网格 (20px)'" placement="bottom">
          <ElButton size="small" @click="toggleGrid" :type="gridSize > 0 ? 'primary' : ''">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM8 20H4v-4h4v4zm0-6H4v-4h4v4zm0-6H4V4h4v4zm6 12h-4v-4h4v4zm0-6h-4v-4h4v4zm0-6h-4V4h4v4zm6 12h-4v-4h4v4zm0-6h-4v-4h4v4zm0-6h-4V4h4v4z"/></svg>
          </ElButton>
        </ElTooltip>

        <ElDivider direction="vertical" />

        <ElButton size="small" @click="canvasRef?.deleteSelected()" :disabled="!selectedObj">
          删除
        </ElButton>
        <ElButton size="small" type="warning" @click="handleClear">清空</ElButton>
        <ElDivider direction="vertical" />
        <ElButton size="small" type="primary" :loading="saving" @click="save">
          保存 (Ctrl+S)
        </ElButton>
        <span v-if="hasUnsavedChanges" class="text-12px text-orange-400 ml-4px">● 未保存</span>
      </div>
    </div>

    <div class="editor-body">
      <!-- 左侧：图元面板（SVG 缩略图） -->
      <div class="editor-sidebar">
        <div class="p-8px">
          <ElInput
            v-model="widgetKeyword"
            size="small"
            placeholder="搜索图元..."
            clearable
          />
        </div>
        <ElTabs v-model="leftTab" class="h-full">
          <ElTabPane label="内置图元" name="builtin">
            <div class="widget-list">
              <ElCollapse>
                <ElCollapseItem
                  v-for="cat in filteredBuiltinCategories"
                  :key="cat"
                  :title="cat"
                  :name="cat"
                >
                  <div
                    v-for="w in filteredBuiltin.filter((x) => x.category === cat)"
                    :key="w.name"
                    class="widget-item"
                    draggable="true"
                    @dragstart="dragStart($event, w)"
                  >
                    <span class="widget-thumb" v-html="w.thumbnail" />
                    <span class="widget-name">{{ w.name }}</span>
                    <span class="widget-type-tag text-10px text-gray-400">{{ w.typeTag }}</span>
                  </div>
                </ElCollapseItem>
              </ElCollapse>
              <div
                v-if="!filteredBuiltin.length"
                class="text-12px text-gray-400 text-center py-16px"
              >
                未找到匹配的图元
              </div>
            </div>
          </ElTabPane>
          <ElTabPane label="自定义图元" name="custom">
            <div class="widget-list">
              <div
                v-for="w in filteredCustom"
                :key="w.id"
                class="widget-item"
                draggable="true"
                @dragstart="dragStartCustom($event, w)"
                @click="addCustomWidget(w)"
              >
                <img
                  v-if="w.thumbnail"
                  :src="w.thumbnail"
                  class="w-28px h-28px object-contain mr-6px"
                />
                <span class="widget-name">{{ w.name }}</span>
              </div>
              <div
                v-if="!filteredCustom.length"
                class="text-12px text-gray-400 text-center py-16px"
              >
                暂无自定义图元
              </div>
            </div>
          </ElTabPane>
        </ElTabs>
      </div>

      <!-- 中间：SVG 画布 -->
      <div class="editor-canvas">
        <SvgCanvas
          ref="canvasRef"
          :width="page.width || 1920"
          :height="page.height || 1080"
          :background="page.background || '#1a1a2e'"
          :runtime="false"
          :grid-size="gridSize"
          @object:selected="onObjectSelected"
          @object:deselected="onObjectDeselected"
          @canvas:changed="markDirty"
          @zoom:changed="onZoomChange"
        />
      </div>

      <!-- 右侧：属性面板 -->
      <div class="editor-props">
        <div class="text-14px font-600 mb-12px">属性面板</div>

        <template v-if="selectedObj && selectedCount > 1">
          <div class="mb-8px text-13px font-600">
            已选 {{ selectedCount }} 个对象
            <ElTag size="small" type="warning" class="ml-4px">多选</ElTag>
          </div>
          <div class="text-12px text-gray-400 mb-12px">
            Shift+点击切换选择；拖动可整体移动
          </div>

          <div class="text-13px font-600 mb-6px">对齐</div>
          <div class="grid grid-cols-4 gap-4px mb-12px">
            <ElButton size="small" @click="getAligned('left')">左对齐</ElButton>
            <ElButton size="small" @click="getAligned('centerH')">水平居中</ElButton>
            <ElButton size="small" @click="getAligned('right')">右对齐</ElButton>
            <ElButton size="small" @click="getAligned('top')">顶对齐</ElButton>
            <ElButton size="small" @click="getAligned('centerV')">垂直居中</ElButton>
            <ElButton size="small" @click="getAligned('bottom')">底对齐</ElButton>
          </div>

          <div class="text-13px font-600 mb-6px">分布</div>
          <div class="grid grid-cols-2 gap-4px mb-12px">
            <ElButton size="small" @click="getDistributed('horizontal')">水平分布</ElButton>
            <ElButton size="small" @click="getDistributed('vertical')">垂直分布</ElButton>
          </div>

          <ElDivider />

          <div class="flex items-center gap-6px mb-8px">
            <ElButton size="small" @click="handleCopy">复制</ElButton>
            <ElButton size="small" @click="canvasRef?.deleteSelected(); markDirty()">删除</ElButton>
            <ElButton size="small" @click="handleBringToFront">置顶</ElButton>
            <ElButton size="small" @click="handleSendToBack">置底</ElButton>
          </div>
        </template>

        <template v-else-if="selectedObj">
          <div class="mb-8px">
            <span class="text-12px text-gray-400">ID:</span>
            <span class="text-12px ml-4px">{{ selectedWidgetId }}</span>
          </div>
          <div class="mb-8px flex items-center">
            <span class="text-12px text-gray-400">类型:</span>
            <ElTag size="small" class="ml-4px">{{ selectedWidgetType }}</ElTag>
          </div>

          <ElForm label-width="70px" size="small">
            <ElFormItem label="名称">
              <ElInput v-model="widgetName" @change="onNameInput($event)" placeholder="图元名称" />
            </ElFormItem>
          </ElForm>

          <ElDivider content-position="left">位置与尺寸</ElDivider>
          <ElForm label-width="70px" size="small">
            <div class="flex gap-6px">
              <ElFormItem label="X" class="flex-1">
                <ElInputNumber
                  v-model="selectedProps.left"
                  :step="1"
                  @change="updateProp('left', $event)"
                  class="w-full"
                />
              </ElFormItem>
              <ElFormItem label="Y" class="flex-1">
                <ElInputNumber
                  v-model="selectedProps.top"
                  :step="1"
                  @change="updateProp('top', $event)"
                  class="w-full"
                />
              </ElFormItem>
            </div>
            <div class="flex gap-6px">
              <ElFormItem label="宽" class="flex-1">
                <ElInputNumber
                  v-model="selectedProps.w"
                  :min="1"
                  :step="1"
                  @change="updateProp('width', $event)"
                  class="w-full"
                />
              </ElFormItem>
              <ElFormItem label="高" class="flex-1">
                <ElInputNumber
                  v-model="selectedProps.h"
                  :min="1"
                  :step="1"
                  @change="updateProp('height', $event)"
                  class="w-full"
                />
              </ElFormItem>
            </div>
            <ElFormItem label="旋转">
              <div class="flex items-center gap-6px w-full">
                <ElInputNumber
                  v-model="selectedProps.angle"
                  :min="-360"
                  :max="360"
                  :step="5"
                  @change="updateProp('angle', $event)"
                  class="flex-1"
                />
                <ElButton size="small" @click="updateProp('angle', 0)">归零</ElButton>
              </div>
            </ElFormItem>
            <ElFormItem label="透明度">
              <ElSlider
                v-model="selectedProps.opacity"
                :min="0"
                :max="1"
                :step="0.05"
                @change="updateProp('opacity', $event)"
              />
            </ElFormItem>
            <ElFormItem label="翻转">
              <div class="flex gap-6px">
                <ElButton size="small" @click="updateProp('flipX', true)">水平翻转</ElButton>
                <ElButton size="small" @click="updateProp('flipY', true)">垂直翻转</ElButton>
              </div>
            </ElFormItem>
          </ElForm>

          <ElDivider content-position="left">外观</ElDivider>
          <ElForm label-width="70px" size="small">
            <ElFormItem label="填充">
              <div class="flex items-center gap-6px w-full">
                <ElColorPicker
                  v-model="selectedStyle.fill"
                  @change="applyStyle('fill', $event)"
                  class="flex-1"
                />
                <ElInput
                  v-model="selectedStyle.fill"
                  size="small"
                  class="flex-1"
                  placeholder="#2a5a8a"
                  @change="applyStyle('fill', $event)"
                />
              </div>
            </ElFormItem>
            <ElFormItem label="描边">
              <div class="flex items-center gap-6px w-full">
                <ElColorPicker
                  v-model="selectedStyle.stroke"
                  @change="applyStyle('stroke', $event)"
                  class="flex-1"
                />
                <ElInput
                  v-model="selectedStyle.stroke"
                  size="small"
                  class="flex-1"
                  placeholder="none"
                  @change="applyStyle('stroke', $event)"
                />
              </div>
            </ElFormItem>
            <ElFormItem label="线宽">
              <ElInputNumber
                v-model="selectedStyle.strokeWidth"
                :min="0"
                :max="20"
                :step="0.5"
                @change="applyStyle('stroke-width', $event)"
                class="w-full"
              />
            </ElFormItem>
            <template v-if="selectedWidgetType === 'svg-ext-shapes'">
              <ElFormItem label="圆角">
                <ElInputNumber
                  v-model="selectedStyle.rx"
                  :min="0"
                  :max="100"
                  :step="1"
                  @change="applyStyle('rx', $event)"
                  class="w-full"
                />
              </ElFormItem>
            </template>
            <ElFormItem label="字号">
              <ElInputNumber
                v-model="selectedStyle.fontSize"
                :min="4"
                :max="200"
                :step="1"
                @change="applyStyle('font-size', $event)"
                class="w-full"
              />
            </ElFormItem>
            <ElFormItem label="文本">
              <ElInput
                v-model="selectedStyle.text"
                :disabled="isTextBound"
                :placeholder="isTextBound ? '已绑定数据点位' : '双击图元也可编辑'"
                @change="onTextInput($event)"
              />
            </ElFormItem>
          </ElForm>

          <ElDivider />

          <div class="text-13px font-600 mb-6px">对齐（单选对齐画布）</div>
          <div class="grid grid-cols-4 gap-4px mb-12px">
            <ElButton size="small" @click="getAligned('left')">左</ElButton>
            <ElButton size="small" @click="getAligned('centerH')">中</ElButton>
            <ElButton size="small" @click="getAligned('right')">右</ElButton>
            <ElButton size="small" @click="getAligned('top')">顶</ElButton>
            <ElButton size="small" @click="getAligned('centerV')">中</ElButton>
            <ElButton size="small" @click="getAligned('bottom')">底</ElButton>
          </div>

          <ElDivider />

          <div class="flex justify-between items-center mb-8px">
            <span class="text-13px font-600">数据绑定</span>
            <ElButton size="small" type="primary" @click="openBindDialog">编辑绑定</ElButton>
          </div>

          <!-- 显示当前图元的绑定域列表 -->
          <div class="binding-info" v-if="selectedBindings.length">
            <div
              v-for="b in selectedBindings"
              :key="b.target"
              class="text-12px mb-4px flex justify-between"
            >
              <span>
                <span class="text-green-400">{{ b.target }}</span>
                <span class="text-gray-400 ml-4px">→ {{ b.bound ? b.tagName : '未绑定' }}</span>
              </span>
              <span v-if="b.hasRanges" class="text-yellow-500 text-10px">⦿ ranges</span>
            </div>
          </div>
          <div v-else class="text-12px text-gray-400 mb-4px">该图元无可绑定域</div>
        </template>

        <div v-else class="text-13px text-gray-400 text-center py-40px">
          点击画布上的图元查看/编辑属性
        </div>

        <ElDivider />

        <div class="text-14px font-600 mb-12px">画布设置</div>
        <ElForm label-width="70px" size="small">
          <ElFormItem label="名称">
            <ElInput v-model="page.name" />
          </ElFormItem>
          <ElFormItem label="宽度">
            <ElInputNumber v-model="page.width" :min="800" :max="3840" :step="100" class="w-full" />
          </ElFormItem>
          <ElFormItem label="高度">
            <ElInputNumber v-model="page.height" :min="600" :max="2160" :step="100" class="w-full" />
          </ElFormItem>
          <ElFormItem label="背景色">
            <ElColorPicker v-model="page.background" />
          </ElFormItem>
        </ElForm>
      </div>
    </div>

    <!-- 绑定对话框（v2 多属性域） -->
    <ElDialog
      v-model="bindDialogVisible"
      title="数据绑定"
      width="640px"
      :close-on-click-modal="false"
      @close="resetBindForm"
    >
      <div v-if="Object.keys(bindForm.domains).length === 0" class="text-13px text-gray-400 py-20px text-center">
        该图元无绑定域（SVG 中没有 data-bind-target 元素）
      </div>

      <ElCollapse v-for="(domain, target) in bindForm.domains" :key="target" class="mb-12px">
        <ElCollapseItem :title="`绑定域: ${target}`">
          <ElForm label-width="80px" size="small">
            <ElFormItem label="启用绑定">
              <ElSwitch v-model="domain.bindEnabled" />
            </ElFormItem>
            <template v-if="domain.bindEnabled">
              <ElFormItem label="设备">
                <ElSelect
                  v-model="domain.deviceId"
                  class="w-full"
                  placeholder="选择设备"
                  @change="onDomainDeviceSelect(domain)"
                >
                  <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
                </ElSelect>
              </ElFormItem>
              <ElFormItem label="点位">
                <ElSelect
                  v-model="domain.tagId"
                  class="w-full"
                  placeholder="选择点位"
                  :disabled="!domain.tags.length"
                  @change="onDomainTagSelect(domain)"
                >
                  <ElOption
                    v-for="t in domain.tags"
                    :key="t.id"
                    :label="`${t.name} (${t.address})`"
                    :value="t.id"
                  />
                </ElSelect>
              </ElFormItem>
            </template>
            <template v-else>
              <ElFormItem label="静态值">
                <ElInput v-model="domain.variableValue" placeholder="未绑定时的显示值" />
              </ElFormItem>
            </template>
            <ElFormItem label="位掩码">
              <ElInputNumber v-model="domain.bitmask" :min="0" :step="1" class="w-full" />
            </ElFormItem>
            <ElFormItem label="格式化">
              <ElSelect v-model="domain.format" class="w-full">
                <ElOption
                  v-for="f in FORMAT_OPTIONS"
                  :key="f.value"
                  :label="f.label"
                  :value="f.value"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem label="范围映射">
              <div class="w-full">
                <div
                  v-for="(r, idx) in domain.ranges"
                  :key="idx"
                  class="flex items-center gap-4px mb-6px"
                >
                  <ElInputNumber v-model="r.min" :step="0.1" controls-position="right" class="flex-1" placeholder="min" />
                  <span class="text-gray-400">~</span>
                  <ElInputNumber v-model="r.max" :step="0.1" controls-position="right" class="flex-1" placeholder="max" />
                  <ElInput v-model="r.text" placeholder="文本" class="flex-1" />
                  <ElColorPicker v-model="r.color" size="small" />
                  <ElButton size="small" text type="danger" @click="removeRange(target, idx)">
                    ✕
                  </ElButton>
                </div>
                <ElButton size="small" text type="primary" @click="addRange(target)">
                  + 添加范围
                </ElButton>
              </div>
            </ElFormItem>
          </ElForm>
        </ElCollapseItem>
      </ElCollapse>

      <ElDivider content-position="left" class="mt-16px">
        交互事件（写值控制）
      </ElDivider>

      <div v-if="bindForm.events.length === 0" class="text-12px text-gray-400 mb-8px">
        无交互事件，点击按钮/开关/滑块/输入框时不会写值
      </div>

      <div
        v-for="ev in bindForm.events"
        :key="ev.id"
        class="event-row mb-8px border rounded p-8px"
      >
        <div class="flex items-center gap-6px mb-6px">
          <ElSelect v-model="ev.type" size="small" class="w-100px">
            <ElOption label="点击" value="click" />
            <ElOption label="变更" value="change" />
          </ElSelect>
          <ElSelect v-model="ev.action" size="small" class="w-140px">
            <ElOption label="写固定值 (onSetValue)" value="onSetValue" />
            <ElOption label="切换值 (onToggleValue)" value="onToggleValue" />
            <ElOption label="跳转画面 (onpage)" value="onpage" />
          </ElSelect>
          <ElButton size="small" text type="danger" @click="removeEvent(ev.id)">✕</ElButton>
        </div>
        <div class="flex items-center gap-6px mb-6px">
          <ElSelect
            v-model="ev.deviceId"
            size="small"
            class="flex-1"
            placeholder="目标设备"
            @change="onEventDeviceSelect(ev)"
          >
            <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
          </ElSelect>
          <ElSelect
            v-model="ev.tagId"
            size="small"
            class="flex-1"
            placeholder="目标点位"
            :disabled="!ev.deviceId"
            @change="onEventTagSelect(ev)"
          >
            <ElOption
              v-for="t in ev.tags"
              :key="t.id"
              :label="`${t.name} (${t.address})`"
              :value="t.id"
            />
          </ElSelect>
        </div>
        <div v-if="ev.action === 'onpage'" class="flex items-center gap-6px">
          <ElSelect v-model="ev.pageId" size="small" class="flex-1" placeholder="目标画面">
            <ElOption
              v-for="p in pagesList"
              :key="p.id"
              :label="`${p.name}${p.id === Number(id) ? ' (当前)' : ''}`"
              :value="p.id"
            />
          </ElSelect>
        </div>
        <div v-else-if="ev.action === 'onToggleValue'" class="flex items-center gap-6px">
          <span class="text-12px text-gray-400 w-48px">开值</span>
          <ElInputNumber v-model="ev.onValue" size="small" :step="1" class="flex-1" />
          <span class="text-12px text-gray-400 w-48px">关值</span>
          <ElInputNumber v-model="ev.offValue" size="small" :step="1" class="flex-1" />
        </div>
        <div v-else class="flex items-center gap-6px">
          <ElSelect v-model="ev.valueType" size="small" class="w-120px">
            <ElOption label="固定值" value="fixed" />
            <ElOption label="输入框内容" value="input" />
            <ElOption label="滑块范围" value="slider" />
          </ElSelect>
          <template v-if="ev.valueType === 'fixed'">
            <ElInput v-model="ev.fixedValue" size="small" class="flex-1" placeholder="固定值，如 1 或 0" />
          </template>
          <template v-else-if="ev.valueType === 'slider'">
            <span class="text-12px text-gray-400">min</span>
            <ElInputNumber v-model="ev.min" size="small" :step="1" class="flex-1" />
            <span class="text-12px text-gray-400">max</span>
            <ElInputNumber v-model="ev.max" size="small" :step="1" class="flex-1" />
          </template>
          <span v-else class="text-12px text-gray-400">运行时输入框内容将直接下发</span>
        </div>
      </div>

      <ElButton size="small" type="primary" plain @click="addEvent">+ 添加事件</ElButton>

      <template #footer>
        <ElButton @click="bindDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="confirmBind">保存绑定</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.editor-layout {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
  background: var(--el-bg-color);
}
.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid var(--el-border-color);
  background: var(--el-fill-color-blank);
  flex-shrink: 0;
  gap: 12px;
}
.toolbar-left {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.toolbar-center {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: center;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.editor-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}
.editor-sidebar {
  width: 240px;
  border-right: 1px solid var(--el-border-color);
  overflow-y: auto;
  flex-shrink: 0;
}
.editor-canvas {
  flex: 1;
  overflow: auto;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  padding: 16px;
  background: #0d1117;
}
.editor-props {
  width: 260px;
  border-left: 1px solid var(--el-border-color);
  overflow-y: auto;
  padding: 12px;
  flex-shrink: 0;
}
.widget-list {
  padding: 8px;
}
.widget-item {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  margin-bottom: 2px;
  border-radius: 6px;
  cursor: grab;
  transition: background 0.15s;
  font-size: 13px;
}
.widget-item:hover {
  background: var(--el-fill-color-light);
}
.widget-item:active {
  cursor: grabbing;
}
.widget-thumb {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;
  flex-shrink: 0;
}
.widget-thumb :deep(svg) {
  max-width: 36px;
  max-height: 36px;
}
.widget-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.widget-type-tag {
  flex-shrink: 0;
  margin-left: 4px;
}
.binding-info {
  max-height: 200px;
  overflow-y: auto;
}
</style>
