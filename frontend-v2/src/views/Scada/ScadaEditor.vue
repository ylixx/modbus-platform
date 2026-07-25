<script setup lang="ts">
/**
 * SCADA 可视化编辑器
 *
 * 布局：左侧图元面板 | 中间画布 | 右侧属性面板
 */
import { ref, reactive, onMounted, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElButton,
  ElInput,
  ElMessage,
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
  ElSwitch,
  ElSlider,
  ElUpload,
  ElDivider
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

// ── 左侧面板 ──
const leftTab = ref('builtin')
const customWidgets = ref<any[]>([])
const devices = ref<any[]>([])
const selectedDevice = ref<number | undefined>(undefined)
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
}

const fetchCustomWidgets = async () => {
  try {
    customWidgets.value = unwrapList(await getScadaWidgets()).list
  } catch {
    customWidgets.value = []
  }
}

const fetchDevices = async () => {
  devices.value = unwrapList(await getAllDevices()).list
}

const fetchTags = async (deviceId: number) => {
  const res = await getDeviceTags(deviceId)
  const body = unwrap(res)
  deviceTags.value = Array.isArray(body) ? body : unwrapList(res).list
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
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// ── 图元拖放 ──

/** 拖拽开始 */
const dragStart = (e: DragEvent, widget: any) => {
  e.dataTransfer?.setData('application/json', JSON.stringify(widget))
}

/** 画布放置 */
const onCanvasDrop = (e: DragEvent) => {
  e.preventDefault()
  const data = e.dataTransfer?.getData('application/json')
  if (!data) return
  try {
    const widget = JSON.parse(data)
    const fabricObj = widget.createFabric ? widget.createFabric() : widget.fabric_json ? JSON.parse(widget.fabric_json) : null
    if (fabricObj) {
      // 计算放置位置（相对于画布）
      const rect = (e.target as HTMLElement).closest('.scada-canvas-wrapper')?.getBoundingClientRect()
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
  }
}

onMounted(() => {
  fetchPage()
  fetchCustomWidgets()
  fetchDevices()
  window.addEventListener('keydown', onKeyDown)
})

import { onUnmounted } from 'vue'
onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <div class="editor-layout" @dragover="onCanvasDragOver" @drop="onCanvasDrop">
    <!-- 顶栏 -->
    <div class="editor-toolbar">
      <div class="flex items-center">
        <ElButton @click="router.push('/scada/pages')" size="small">← 返回</ElButton>
        <ElDivider direction="vertical" />
        <span class="text-14px font-600">{{ page.name || 'SCADA 编辑器' }}</span>
      </div>
      <div class="flex items-center gap-8px">
        <ElButton size="small" @click="canvasRef?.deleteSelected()" :disabled="!selectedObj">
          删除
        </ElButton>
        <ElButton size="small" @click="canvasRef?.selectAll()">全选</ElButton>
        <ElButton size="small" type="warning" @click="canvasRef?.clear()">清空</ElButton>
        <ElDivider direction="vertical" />
        <ElButton size="small" type="primary" :loading="saving" @click="save">
          💾 保存 (Ctrl+S)
        </ElButton>
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
    <ElDialog v-model="bindDialogVisible" title="数据绑定" width="480px">
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
