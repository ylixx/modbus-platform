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
  ElButtonGroup
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
import { svgWidgets, svgWidgetCategories, getSvgWidgetsByCategory, genId } from './widgets/svg-widgets'
import type { SvgWidgetDef } from './widgets/svg-widgets'

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
const deviceTags = ref<any[]>([])

// ── 右侧属性面板 ──
const selectedObj = ref<SVGElement | null>(null)
const selectedProps = reactive<any>({
  left: 0,
  top: 0,
  opacity: 1
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

// ── 绑定配置 ──
const bindDialogVisible = ref(false)
const bindForm = reactive({
  target: '',
  deviceId: undefined as number | undefined,
  tagId: undefined as number | undefined,
  tagName: '',
  prop: 'text'
})

// ── FUXA 风格值处理配置 ──
const valueProcessDialogVisible = ref(false)
const valueProcessForm = reactive({
  bitMask: 0,
  ranges: [] as Array<{ min: number; max: number; color: string; label: string }>,
  actions: [] as Array<{ condition: string; value: string; actionType: string; targetId: string }>
})

const openValueProcessDialog = () => {
  // 从当前选中图元读取已有的值处理配置
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
  valueProcessForm.ranges.push({ min: 0, max: 100, color: '#4ac080', label: '' })
}

const removeRange = (index: number) => {
  valueProcessForm.ranges.splice(index, 1)
}

const addAction = () => {
  valueProcessForm.actions.push({ condition: 'eq', value: '1', actionType: 'show', targetId: '' })
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
  // 清理空值
  if (!vp.bitMask) delete vp.bitMask
  if (!vp.ranges?.length) delete vp.ranges
  if (!vp.actions?.length) delete vp.actions

  selectedObj.value.setAttribute('data-value-process', JSON.stringify(vp))
  valueProcessDialogVisible.value = false
  markDirty()
  ElMessage.success('值处理配置已保存')
}

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

// ── 保存 ──
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
      selectedProps.left = Math.round(transform.x)
      selectedProps.top = Math.round(transform.y)
      selectedProps.opacity = transform.opacity
    }
    isLockedState.value = canvasRef.value?.isLocked() ?? false
  }
}

const onObjectDeselected = () => {
  selectedObj.value = null
}

const updateProp = (prop: string, value: any) => {
  if (!selectedObj.value) return
  canvasRef.value?.setSelectedTransform(prop, value)
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

const resetBindForm = () => {
  bindForm.target = ''
  bindForm.deviceId = undefined
  bindForm.tagId = undefined
  bindForm.tagName = ''
  bindForm.prop = 'text'
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
  canvasRef.value?.setBinding(elementId, bindForm.target, bindForm.deviceId!, bindForm.tagId!, bindForm.tagName, bindForm.prop)
  bindDialogVisible.value = false
  ElMessage.success(`已绑定到 ${bindForm.tagName} → ${bindForm.target}`)
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
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedObj.value && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
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
        <ElTabs v-model="leftTab" class="h-full">
          <ElTabPane label="内置图元" name="builtin">
            <div class="widget-list">
              <ElCollapse>
                <ElCollapseItem
                  v-for="cat in svgWidgetCategories()"
                  :key="cat"
                  :title="cat"
                  :name="cat"
                >
                  <div
                    v-for="w in getSvgWidgetsByCategory(cat)"
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
            </div>
          </ElTabPane>
          <ElTabPane label="自定义图元" name="custom">
            <div class="widget-list">
              <div
                v-for="w in customWidgets"
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
                v-if="!customWidgets.length"
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

        <template v-if="selectedObj">
          <div class="mb-8px">
            <span class="text-12px text-gray-400">ID:</span>
            <span class="text-12px ml-4px">{{ selectedWidgetId }}</span>
          </div>
          <div class="mb-8px">
            <span class="text-12px text-gray-400">类型:</span>
            <ElTag size="small" class="ml-4px">{{ selectedWidgetType }}</ElTag>
          </div>

          <ElForm label-width="70px" size="small">
            <ElFormItem label="X">
              <ElInputNumber
                v-model="selectedProps.left"
                :step="1"
                @change="updateProp('left', $event)"
                class="w-full"
              />
            </ElFormItem>
            <ElFormItem label="Y">
              <ElInputNumber
                v-model="selectedProps.top"
                :step="1"
                @change="updateProp('top', $event)"
                class="w-full"
              />
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
          </ElForm>

          <ElDivider />

          <div class="flex justify-between items-center mb-8px">
            <span class="text-13px font-600">数据绑定</span>
            <ElButton size="small" type="primary" @click="openBindDialog">绑定点位</ElButton>
          </div>

          <!-- 显示当前图元的绑定信息 -->
          <div class="binding-info" v-if="selectedObj">
            <div v-for="child in Array.from(selectedObj.querySelectorAll('[data-bind-target]') as NodeListOf<Element>)" :key="child.id || child.getAttribute('data-bind-target') || ''" class="text-12px mb-4px">
              <span class="text-green-400">{{ child.getAttribute('data-bind-target') }}</span>
              <span class="text-gray-400 ml-4px">→ {{ child.getAttribute('data-bind-tag-name') || '未绑定' }}</span>
              <span class="text-gray-500 ml-4px">({{ child.getAttribute('data-bind-prop') }})</span>
            </div>
          </div>

          <ElDivider />

          <div class="flex justify-between items-center mb-8px">
            <span class="text-13px font-600">值处理</span>
            <ElButton size="small" type="warning" @click="openValueProcessDialog">配置</ElButton>
          </div>

          <!-- 显示当前值处理配置摘要 -->
          <div class="value-process-summary" v-if="selectedObj?.getAttribute('data-value-process')">
            <div v-if="JSON.parse(selectedObj.getAttribute('data-value-process') || '{}').bitMask" class="text-12px mb-4px">
              <span class="text-gray-400">位掩码:</span>
              <span class="text-yellow-400 ml-4px">0x{{ JSON.parse(selectedObj.getAttribute('data-value-process') || '{}').bitMask.toString(16) }}</span>
            </div>
            <div v-if="JSON.parse(selectedObj.getAttribute('data-value-process') || '{}').ranges?.length" class="text-12px mb-4px">
              <span class="text-gray-400">颜色映射:</span>
              <span class="text-blue-400 ml-4px">{{ JSON.parse(selectedObj.getAttribute('data-value-process') || '{}').ranges.length }} 条规则</span>
            </div>
            <div v-if="JSON.parse(selectedObj.getAttribute('data-value-process') || '{}').actions?.length" class="text-12px mb-4px">
              <span class="text-gray-400">动作:</span>
              <span class="text-orange-400 ml-4px">{{ JSON.parse(selectedObj.getAttribute('data-value-process') || '{}').actions.length }} 条规则</span>
            </div>
          </div>
          <div v-else class="text-11px text-gray-500">未配置值处理</div>
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

    <!-- 绑定对话框 -->
    <ElDialog v-model="bindDialogVisible" title="数据绑定" width="480px" @close="resetBindForm">
      <ElForm label-width="90px">
        <ElFormItem label="绑定目标">
          <ElSelect v-model="bindForm.target" class="w-full" placeholder="选择绑定属性">
            <ElOption label="值 (value)" value="value" />
            <ElOption label="状态 (state)" value="state" />
            <ElOption label="液位 (level)" value="level" />
            <ElOption label="温度 (temperature)" value="temperature" />
            <ElOption label="文本 (text)" value="text" />
            <ElOption label="填充色 (fill)" value="fill" />
            <ElOption label="红色灯 (red)" value="red" />
            <ElOption label="黄色灯 (yellow)" value="yellow" />
            <ElOption label="绿色灯 (green)" value="green" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="绑定属性">
          <ElSelect v-model="bindForm.prop" class="w-full" placeholder="选择更新方式">
            <ElOption label="文本内容" value="text" />
            <ElOption label="填充色" value="fill" />
            <ElOption label="描边色" value="stroke" />
            <ElOption label="宽度" value="width" />
            <ElOption label="高度" value="height" />
            <ElOption label="旋转" value="rotate" />
            <ElOption label="透明度" value="opacity" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="设备">
          <ElSelect
            v-model="bindForm.deviceId"
            class="w-full"
            placeholder="选择设备"
            @change="onDeviceSelect"
          >
            <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="点位">
          <ElSelect
            v-model="bindForm.tagId"
            class="w-full"
            placeholder="选择点位"
            :disabled="!bindForm.deviceId"
            @change="
              (val: number) => {
                const tag = deviceTags.find((t) => t.id === val)
                bindForm.tagName = tag?.name || ''
              }
            "
          >
            <ElOption
              v-for="t in deviceTags"
              :key="t.id"
              :label="`${t.name} (${t.address})`"
              :value="t.id"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="bindDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="confirmBind">确认绑定</ElButton>
      </template>
    </ElDialog>

    <!-- FUXA 风格值处理配置对话框 -->
    <ElDialog v-model="valueProcessDialogVisible" title="值处理配置" width="600px">
      <ElCollapse>
        <!-- 位掩码 -->
        <ElCollapseItem title="位掩码 (Bit Mask)" name="bitmask">
          <div class="text-12px text-gray-400 mb-8px">
            对采集值进行位与运算（value &amp; bitMask），用于提取特定位的状态
          </div>
          <ElFormItem label="掩码值" label-width="70px" size="small">
            <ElInputNumber v-model="valueProcessForm.bitMask" :min="0" :max="65535" :step="1" class="w-full" />
          </ElFormItem>
        </ElCollapseItem>

        <!-- 范围颜色映射 -->
        <ElCollapseItem title="范围颜色映射 (Ranges)" name="ranges">
          <div class="text-12px text-gray-400 mb-8px">
            根据数值范围设置颜色，FUXA 风格的 ranges 配置
          </div>
          <div v-for="(range, idx) in valueProcessForm.ranges" :key="idx" class="flex items-center gap-4px mb-8px">
            <ElInputNumber v-model="range.min" :step="1" size="small" controls-position="right" style="width:80px" />
            <span class="text-gray-400">~</span>
            <ElInputNumber v-model="range.max" :step="1" size="small" controls-position="right" style="width:80px" />
            <ElColorPicker v-model="range.color" size="small" />
            <ElInput v-model="range.label" placeholder="标签" size="small" style="width:80px" />
            <ElButton size="small" type="danger" circle @click="removeRange(idx)">×</ElButton>
          </div>
          <ElButton size="small" @click="addRange">+ 添加范围</ElButton>
        </ElCollapseItem>

        <!-- 动作执行 -->
        <ElCollapseItem title="动作执行 (Actions)" name="actions">
          <div class="text-12px text-gray-400 mb-8px">
            根据值触发动作：显示/隐藏/闪烁/旋转/移动目标图元
          </div>
          <div v-for="(act, idx) in valueProcessForm.actions" :key="idx" class="flex items-center gap-4px mb-8px">
            <ElSelect v-model="act.condition" size="small" style="width:70px">
              <ElOption label="=" value="eq" />
              <ElOption label="!=" value="ne" />
              <ElOption label=">" value="gt" />
              <ElOption label="<" value="lt" />
              <ElOption label=">=" value="ge" />
              <ElOption label="<=" value="le" />
            </ElSelect>
            <ElInput v-model="act.value" size="small" placeholder="值" style="width:60px" />
            <ElSelect v-model="act.actionType" size="small" style="width:70px">
              <ElOption label="显示" value="show" />
              <ElOption label="隐藏" value="hide" />
              <ElOption label="闪烁" value="blink" />
              <ElOption label="旋转" value="rotate" />
              <ElOption label="移动" value="move" />
            </ElSelect>
            <ElInput v-model="act.targetId" size="small" placeholder="目标ID" style="width:100px" />
            <ElButton size="small" type="danger" circle @click="removeAction(idx)">×</ElButton>
          </div>
          <ElButton size="small" @click="addAction">+ 添加动作</ElButton>
        </ElCollapseItem>
      </ElCollapse>

      <template #footer>
        <ElButton @click="valueProcessDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="confirmValueProcess">保存配置</ElButton>
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
