<script setup lang="ts">
/**
 * SCADA 可视化编辑器
 *
 * 布局：左侧图元面板 | 中间画布 | 右侧属性面板
 */
import { ref, reactive, onMounted, nextTick, onUnmounted } from 'vue'
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
import ScadaCanvas from './ScadaCanvas.vue'
import { builtinWidgets, widgetCategories, getWidgetsByCategory } from './widgets/builtin'

defineOptions({ name: 'ScadaEditor' })

const route = useRoute()
const router = useRouter()
const id = route.params.id as string

// ── 画布数据 ──
const page = ref<any>({ name: '', config_json: '[]', width: 1920, height: 1080, background: '#1a1a2e' })
const saving = ref(false)
const canvasRef = ref<InstanceType<typeof ScadaCanvas>>()

// ── 缩放状态 ──
const zoomLevel = ref(100) // 百分比

// ── 网格状态 ──
const gridSize = ref(0) // 0 = 不显示

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
const selectedObj = ref<any>(null)
const selectedProps = reactive<any>({
  left: 0,
  top: 0,
  scaleX: 1,
  scaleY: 1,
  angle: 0,
  opacity: 1
})

// ── 绑定配置 ──
const bindDialogVisible = ref(false)
const bindForm = reactive({
  target: '', // bindTarget (如 'value', 'state', 'level')
  deviceId: undefined as number | undefined,
  tagId: undefined as number | undefined,
  tagName: '',
  prop: 'text' // 绑定到哪个属性
})

// ── 加载页面数据 ──
const fetchPage = async () => {
  try {
    const body = unwrap(await getScadaPage(Number(id)))
    page.value = body || {}
    await nextTick()
    // 加载画布配置
    const config = body?.config_json
    if (config && config !== '[]') {
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
      config_json: JSON.stringify(json || [])
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

/** 拖拽开始 — 只传 type 标识，避免 JSON 序列化丢失函数引用 */
const dragStart = (e: DragEvent, widget: any) => {
  e.dataTransfer?.setData('application/json', JSON.stringify({ type: widget.type, _isBuiltin: true }))
}

/** 画布放置 */
const onCanvasDrop = (e: DragEvent) => {
  e.preventDefault()
  const data = e.dataTransfer?.getData('application/json')
  if (!data) return
  try {
    const widgetInfo = JSON.parse(data)
    let fabricObj: any = null

    if (widgetInfo._isBuiltin) {
      // 内置图元：通过 type 查找定义并调用 createFabric
      const builtin = builtinWidgets.find((w) => w.type === widgetInfo.type)
      if (builtin) {
        fabricObj = builtin.createFabric()
      }
    } else if (widgetInfo.fabric_json) {
      fabricObj = JSON.parse(widgetInfo.fabric_json)
    }

    if (fabricObj) {
      // 计算放置位置（相对于画布容器）
      // 从 drop 事件目标向上查找画布包裹元素
      const canvasWrapper = (e.target as HTMLElement).closest('.scada-canvas-wrapper')
        || document.querySelector('.scada-canvas-wrapper')
      const rect = canvasWrapper?.getBoundingClientRect()
      const left = rect ? e.clientX - rect.left : 100
      const top = rect ? e.clientY - rect.top : 100
      canvasRef.value?.addWidget(fabricObj, left, top)
    }
  } catch (err) {
    console.warn('Drop failed:', err)
  }
}

const onCanvasDragOver = (e: DragEvent) => {
  e.preventDefault()
}

/** 自定义图元放置 */
const addCustomWidget = (widget: any) => {
  if (widget.source_type === 'svg') {
    canvasRef.value?.addSVG(widget.source_data, 200, 200)
  } else if (widget.source_type === 'png') {
    canvasRef.value?.addImage(widget.source_data, 200, 200, widget.default_width, widget.default_height)
  } else if (widget.fabric_json) {
    canvasRef.value?.addWidget(JSON.parse(widget.fabric_json), 200, 200)
  }
}

// ── 选中/属性 ──

const onObjectSelected = (obj: any) => {
  selectedObj.value = obj
  if (obj) {
    selectedProps.left = Math.round(obj.left || 0)
    selectedProps.top = Math.round(obj.top || 0)
    selectedProps.scaleX = obj.scaleX || 1
    selectedProps.scaleY = obj.scaleY || 1
    selectedProps.angle = Math.round(obj.angle || 0)
    selectedProps.opacity = obj.opacity ?? 1
  }
}

const onObjectDeselected = () => {
  selectedObj.value = null
}

const updateProp = (prop: string, value: any) => {
  if (!selectedObj.value) return
  selectedObj.value.set({ [prop]: value })
  canvasRef.value?.getCanvas()?.renderAll()
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
  // 在选中对象上设置绑定信息
  const obj = selectedObj.value
  obj.set({
    _bindTarget: bindForm.target,
    _bindDeviceId: bindForm.deviceId,
    _bindTagId: bindForm.tagId,
    _bindTagName: bindForm.tagName,
    _bindProp: bindForm.prop
  })
  canvasRef.value?.getCanvas()?.renderAll()
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

        <!-- 对齐/分布 -->
        <ElButtonGroup size="small">
          <ElTooltip content="左对齐" placement="bottom">
            <ElButton :disabled="!selectedObj" @click="canvasRef?.alignLeft()">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M13 6v12l-5-6 5-6zm-8 0v12H3V6h2z"/></svg>
            </ElButton>
          </ElTooltip>
          <ElTooltip content="右对齐" placement="bottom">
            <ElButton :disabled="!selectedObj" @click="canvasRef?.alignRight()">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M11 6v12l5-6-5-6zm8 0v12h-2V6h2z"/></svg>
            </ElButton>
          </ElTooltip>
          <ElTooltip content="顶对齐" placement="bottom">
            <ElButton :disabled="!selectedObj" @click="canvasRef?.alignTop()">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M6 13h12l-6 5-6-5zm0-8v2h12V5H6z"/></svg>
            </ElButton>
          </ElTooltip>
          <ElTooltip content="底对齐" placement="bottom">
            <ElButton :disabled="!selectedObj" @click="canvasRef?.alignBottom()">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M6 11h12l-6-5-6 5zm0 8v-2h12v2H6z"/></svg>
            </ElButton>
          </ElTooltip>
          <ElTooltip content="水平居中" placement="bottom">
            <ElButton :disabled="!selectedObj" @click="canvasRef?.alignCenterH()">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M7 5v14l5-4.5L17 19V5l-5 4.5L7 5z"/></svg>
            </ElButton>
          </ElTooltip>
          <ElTooltip content="垂直居中" placement="bottom">
            <ElButton :disabled="!selectedObj" @click="canvasRef?.alignCenterV()">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M5 7h14l-4.5 5L19 17H5l4.5-5L5 7z"/></svg>
            </ElButton>
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
            {{ isLockedState ? '🔓' : '🔒' }}
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
        <ElButton size="small" @click="canvasRef?.selectAll()">全选</ElButton>
        <ElButton size="small" type="warning" @click="handleClear">清空</ElButton>
        <ElDivider direction="vertical" />
        <ElButton size="small" type="primary" :loading="saving" @click="save">
          保存 (Ctrl+S)
        </ElButton>
        <span v-if="hasUnsavedChanges" class="text-12px text-orange-400 ml-4px">● 未保存</span>
      </div>
    </div>

    <div class="editor-body">
      <!-- 左侧：图元面板 -->
      <div class="editor-sidebar">
        <ElTabs v-model="leftTab" class="h-full">
          <ElTabPane label="内置图元" name="builtin">
            <div class="widget-list">
              <ElCollapse>
                <ElCollapseItem
                  v-for="cat in widgetCategories()"
                  :key="cat"
                  :title="cat"
                  :name="cat"
                >
                  <div
                    v-for="w in getWidgetsByCategory(cat)"
                    :key="w.type"
                    class="widget-item"
                    draggable="true"
                    @dragstart="dragStart($event, w)"
                  >
                    <span class="widget-icon">{{ w.icon }}</span>
                    <span class="widget-name">{{ w.name }}</span>
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

      <!-- 中间：画布 -->
      <div class="editor-canvas">
        <ScadaCanvas
          ref="canvasRef"
          :width="page.width || 1920"
          :height="page.height || 1080"
          :background="page.background || '#1a1a2e'"
          @object:selected="onObjectSelected"
          @object:deselected="onObjectDeselected"
          @canvas:changed="markDirty"
          @zoom:changed="onZoomChange"
          :grid-size="gridSize"
        />
      </div>

      <!-- 右侧：属性面板 -->
      <div class="editor-props">
        <div class="text-14px font-600 mb-12px">属性面板</div>

        <template v-if="selectedObj">
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
            <ElFormItem label="缩放X">
              <ElSlider
                v-model="selectedProps.scaleX"
                :min="0.1"
                :max="3"
                :step="0.1"
                @change="updateProp('scaleX', $event)"
              />
            </ElFormItem>
            <ElFormItem label="缩放Y">
              <ElSlider
                v-model="selectedProps.scaleY"
                :min="0.1"
                :max="3"
                :step="0.1"
                @change="updateProp('scaleY', $event)"
              />
            </ElFormItem>
            <ElFormItem label="旋转">
              <ElSlider
                v-model="selectedProps.angle"
                :min="0"
                :max="360"
                :step="1"
                @change="updateProp('angle', $event)"
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
          <div class="text-12px text-gray-400">
            图元类型: {{ selectedObj._widgetType || selectedObj.type || '未知' }}
          </div>
          <div v-if="selectedObj._bindTarget" class="text-12px mt-4px">
            <span class="text-green-400">已绑定:</span>
            {{ selectedObj._bindTagName || '' }} → {{ selectedObj._bindTarget }}
          </div>
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
  padding: 8px 10px;
  margin-bottom: 4px;
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
.widget-icon {
  margin-right: 8px;
  font-size: 18px;
}
.widget-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
