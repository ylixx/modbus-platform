<script setup lang="ts">
/**
 * ScadaCanvas - Fabric.js SCADA 画布组件
 *
 * 功能：
 * - 加载/渲染 Fabric.js JSON 配置
 * - 图元拖放放置
 * - 图元选中/移动/缩放/旋转/删除
 * - 画布序列化（保存）
 * - 数据绑定模式（运行时）
 */
import { ref, onMounted, onUnmounted } from 'vue'
import * as fabric from 'fabric'

const props = withDefaults(
  defineProps<{
    width?: number
    height?: number
    background?: string
    /** 是否为运行模式（不可编辑，只显示） */
    runtime?: boolean
  }>(),
  {
    width: 1920,
    height: 1080,
    background: '#1a1a2e',
    runtime: false
  }
)

const emit = defineEmits<{
  (e: 'object:selected', obj: any): void
  (e: 'object:deselected'): void
  (e: 'canvas:changed'): void
  (e: 'ready'): void
}>()

const canvasEl = ref<HTMLCanvasElement>()
let canvas: fabric.Canvas | null = null

// ── 初始化画布 ──

onMounted(() => {
  if (!canvasEl.value) return

  canvas = new fabric.Canvas(canvasEl.value, {
    width: props.width,
    height: props.height,
    backgroundColor: props.background,
    selection: !props.runtime,
    preserveObjectStacking: true
  })

  if (props.runtime) {
    canvas.forEachObject((obj) => {
      obj.selectable = false
      obj.evented = false
    })
  }

  // 选中事件
  canvas.on('selection:created', (_e) => {
    if (props.runtime) return
    const obj = canvas?.getActiveObject()
    emit('object:selected', obj)
  })
  canvas.on('selection:updated', (_e) => {
    if (props.runtime) return
    const obj = canvas?.getActiveObject()
    emit('object:selected', obj)
  })
  canvas.on('selection:cleared', () => {
    emit('object:deselected')
  })

  // 对象修改事件（用于跟踪变更）
  canvas.on('object:modified', () => {
    emit('canvas:changed')
  })
  canvas.on('object:added', () => {
    if (!props.runtime) emit('canvas:changed')
  })
  canvas.on('object:removed', () => {
    if (!props.runtime) emit('canvas:changed')
  })

  emit('ready')
})

onUnmounted(() => {
  canvas?.dispose()
  canvas = null
})

// ── 公共方法 ──

/** 加载 Fabric JSON */
const loadFromJSON = async (json: string | object): Promise<void> => {
  if (!canvas) return
  const data = typeof json === 'string' ? json : JSON.stringify(json)
  return new Promise((resolve) => {
    canvas!.loadFromJSON(data).then(() => {
      canvas!.renderAll()
      if (props.runtime) {
        canvas!.forEachObject((obj) => {
          obj.selectable = false
          obj.evented = false
        })
      }
      resolve()
    })
  })
}

/** 导出 Fabric JSON */
const toJSON = (): object => {
  return canvas?.toJSON(['_widgetType', '_bindable', '_bindTarget', '_bindProp', '_bindDeviceId', '_bindTagId', '_bindTagName']) || {}
}

/** 添加图元对象（直接传入 Fabric 实例或 JSON 对象） */
const addWidget = (fabricObj: any, left?: number, top?: number) => {
  if (!canvas) return

  // 如果已经是 Fabric 实例（有 constructor.name 含 Fabric），直接用
  const isFabricInstance = fabricObj && typeof fabricObj.set === 'function' && fabricObj.canvas !== undefined

  const doAdd = (obj: any) => {
    if (left != null) obj.set({ left })
    if (top != null) obj.set({ top })
    canvas!.add(obj)
    canvas!.setActiveObject(obj)
    canvas!.renderAll()
  }

  if (isFabricInstance) {
    doAdd(fabricObj)
  } else {
    // JSON 序列化对象：用 enlivenObjects 反序列化
    const arr = Array.isArray(fabricObj) ? fabricObj : [fabricObj]
    const result = fabric.util.enlivenObjects(arr)
    if (result instanceof Promise) {
      result.then((objects: any[]) => {
        objects.forEach((o: any) => doAdd(o))
      })
    }
  }
}

/** 添加 SVG 字符串 */
const addSVG = (svgString: string, left?: number, top?: number) => {
  if (!canvas) return
  fabric.loadSVGFromString(svgString).then((result) => {
    const group = fabric.util.groupSVGElements(result.objects, result.options)
    if (left != null) group.set({ left })
    if (top != null) group.set({ top })
    group.set({ scaleX: 1, scaleY: 1 })
    canvas!.add(group)
    canvas!.setActiveObject(group)
    canvas!.renderAll()
  })
}

/** 添加图片（base64/dataURI） */
const addImage = (src: string, left?: number, top?: number, w?: number, h?: number) => {
  if (!canvas) return
  const imgEl = new Image()
  imgEl.onload = () => {
    const img = new fabric.FabricImage(imgEl, {
      left: left || 0,
      top: top || 0,
      scaleX: w ? w / imgEl.width : 1,
      scaleY: h ? h / imgEl.height : 1
    })
    canvas!.add(img)
    canvas!.setActiveObject(img)
    canvas!.renderAll()
  }
  imgEl.src = src
}

/** 删除选中对象 */
const deleteSelected = () => {
  if (!canvas || props.runtime) return
  const active = canvas.getActiveObjects()
  active.forEach((obj) => canvas!.remove(obj))
  canvas.discardActiveObject()
  canvas.renderAll()
}

/** 清空画布 */
const clear = () => {
  canvas?.clear()
  canvas?.setBackgroundColor(props.background || '#1a1a2e', () => {})
}

/** 更新对象的绑定数据（运行时）
 *  fabricId: 图元的 name/id（用于精确定位），为空则匹配所有
 */
const updateBoundValue = (
  fabricId: string,
  bindTarget: string,
  newValue: any,
  prop: string = 'text'
) => {
  if (!canvas) return
  const applyToChild = (child: any) => {
    if (child._bindTarget === bindTarget) {
      // 如果指定了 fabricId，只匹配该图元
      if (fabricId && child.name !== fabricId && child.id !== fabricId) return
      if (prop === 'text' && child.type === 'textbox') {
        child.set({ text: String(newValue) })
      } else if (prop === 'fill') {
        child.set({ fill: newValue })
      } else if (prop === 'width' || prop === 'height') {
        child.set({ [prop]: Number(newValue) })
      }
    }
  }
  canvas.forEachObject((obj) => {
    // 顶层对象自身可能有绑定
    if (obj._bindTarget === bindTarget) {
      if (!fabricId || obj.name === fabricId || obj.id === fabricId) {
        if (prop === 'text' && (obj as any).type === 'textbox') {
          ;(obj as any).set({ text: String(newValue) })
        } else if (prop === 'fill') {
          obj.set({ fill: newValue })
        } else if (prop === 'width' || prop === 'height') {
          obj.set({ [prop]: Number(newValue) })
        }
      }
    }
    // group 内子对象
    if (obj.type === 'group') {
      const group = obj as fabric.Group
      const objects = group.getObjects()
      objects.forEach((child: any) => {
        applyToChild(child)
      })
    }
  })
  canvas.renderAll()
}

/** 获取画布数据 URL（截图） */
const toDataURL = (): string => {
  return canvas?.toDataURL({ format: 'png', quality: 0.8 }) || ''
}

/** 缩放画布 */
const setZoom = (zoom: number) => {
  if (!canvas) return
  canvas.setZoom(zoom)
  canvas.setWidth(props.width * zoom)
  canvas.setHeight(props.height * zoom)
}

/** 全选 */
const selectAll = () => {
  if (!canvas || props.runtime) return
  canvas.discardActiveObject()
  const sel = new fabric.ActiveSelection(canvas.getObjects(), { canvas })
  canvas.setActiveObject(sel)
  canvas.renderAll()
}

// 导出方法给父组件
defineExpose({
  loadFromJSON,
  toJSON,
  addWidget,
  addSVG,
  addImage,
  deleteSelected,
  clear,
  updateBoundValue,
  toDataURL,
  setZoom,
  selectAll,
  getCanvas: () => canvas
})
</script>

<template>
  <div class="scada-canvas-wrapper" :style="{ width: width + 'px', height: height + 'px' }">
    <canvas ref="canvasEl"></canvas>
  </div>
</template>

<style scoped>
.scada-canvas-wrapper {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  overflow: auto;
  background: #0a0a1a;
}
.scada-canvas-wrapper canvas {
  display: block;
}
</style>
