<script setup lang="ts">
/**
 * ScadaCanvas - Fabric.js SCADA 画布组件
 *
 * 功能：
 * - 加载/渲染 Fabric.js JSON 配置
 * - 图元拖放放置
 * - 图元选中/移动/缩放/旋转/删除
 * - 对齐/分布（6对齐 + 2分布）
 * - 缩放/平移画布
 * - 撤销/重做
 * - 层级调整 / 锁定/解锁 / 复制/粘贴
 * - 网格/吸附
 * - 画布序列化（保存）
 * - 数据绑定模式（运行时）
 * - 蚂蚁线流动动画
 */
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as fabric from 'fabric'

const props = withDefaults(
  defineProps<{
    width?: number
    height?: number
    background?: string
    /** 是否为运行模式（不可编辑，只显示） */
    runtime?: boolean
    /** 网格大小，0 表示不显示网格 */
    gridSize?: number
  }>(),
  {
    width: 1920,
    height: 1080,
    background: '#1a1a2e',
    runtime: false,
    gridSize: 0
  }
)

const emit = defineEmits<{
  (e: 'object:selected', obj: any): void
  (e: 'object:deselected'): void
  (e: 'canvas:changed'): void
  (e: 'ready'): void
  (e: 'zoom:changed', zoom: number): void
}>()

const canvasEl = ref<HTMLCanvasElement>()
let canvas: fabric.Canvas | null = null

// ── 撤销/重做 ──
let undoStack: string[] = []
let redoStack: string[] = []
let isLoadingState = false
let skipNextSnapshot = false

const snapshot = () => {
  if (!canvas || isLoadingState || props.runtime) return
  const json = JSON.stringify(canvas.toJSON(['_widgetType', '_bindable', '_bindTarget', '_bindProp', '_bindDeviceId', '_bindTagId', '_bindTagName', 'lockMovementX', 'lockMovementY', 'lockScalingX', 'lockScalingY', 'lockRotation', 'hasControls', 'selectable', 'evented']))
  undoStack.push(json)
  if (undoStack.length > 50) undoStack.shift()
  redoStack = []
}

const undo = () => {
  if (!canvas || undoStack.length <= 1) return
  isLoadingState = true
  const current = undoStack.pop()!
  redoStack.push(current)
  const prev = undoStack[undoStack.length - 1]
  canvas.loadFromJSON(prev).then(() => {
    canvas!.renderAll()
    isLoadingState = false
  })
}

const redo = () => {
  if (!canvas || redoStack.length === 0) return
  isLoadingState = true
  const next = redoStack.pop()!
  undoStack.push(next)
  canvas.loadFromJSON(next).then(() => {
    canvas!.renderAll()
    isLoadingState = false
  })
}

const canUndo = () => undoStack.length > 1
const canRedo = () => redoStack.length > 0

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
  canvas.on('selection:created', () => {
    if (props.runtime) return
    emit('object:selected', canvas?.getActiveObject())
  })
  canvas.on('selection:updated', () => {
    if (props.runtime) return
    emit('object:selected', canvas?.getActiveObject())
  })
  canvas.on('selection:cleared', () => {
    emit('object:deselected')
  })

  // 对象修改事件
  canvas.on('object:modified', () => {
    if (!props.runtime) { snapshot(); emit('canvas:changed') }
  })
  canvas.on('object:added', () => {
    if (!props.runtime && !isLoadingState) { emit('canvas:changed') }
  })
  canvas.on('object:removed', () => {
    if (!props.runtime && !isLoadingState) { emit('canvas:changed') }
  })

  // 缩放（鼠标滚轮）
  canvas.on('mouse:wheel', (opt) => {
    if (props.runtime) return
    const delta = (opt.e as any).deltaY
    let zoom = canvas!.getZoom()
    zoom *= 0.999 ** delta
    if (zoom > 3) zoom = 3
    if (zoom < 0.1) zoom = 0.1
    canvas!.zoomToPoint(new fabric.Point((opt.e as any).offsetX, (opt.e as any).offsetY), zoom)
    opt.e.preventDefault()
    opt.e.stopPropagation()
    emit('zoom:changed', zoom)
  })

  // 平移（中键/空格+左键）
  let isPanning = false
  let lastPosX = 0
  let lastPosY = 0
  canvas.on('mouse:down', (opt) => {
    if (props.runtime) return
    const e = opt.e as any
    if (e.button === 1 || (e.altKey && e.button === 0)) {
      isPanning = true
      lastPosX = e.clientX
      lastPosY = e.clientY
      canvas!.selection = false
    }
  })
  canvas.on('mouse:move', (opt) => {
    if (!isPanning) return
    const e = opt.e as any
    const vpt = canvas!.viewportTransform!
    vpt[4] += e.clientX - lastPosX
    vpt[5] += e.clientY - lastPosY
    lastPosX = e.clientX
    lastPosY = e.clientY
    canvas!.requestRenderAll()
  })
  canvas.on('mouse:up', () => {
    isPanning = false
    if (canvas) canvas.selection = !props.runtime
  })

  // 初始快照
  snapshot()
  emit('ready')
})

onUnmounted(() => {
  canvas?.dispose()
  canvas = null
  undoStack = []
  redoStack = []
})

// ── 网格 ──

const drawGrid = () => {
  const wrapper = canvasEl.value?.closest('.scada-canvas-wrapper') as HTMLElement
  if (!wrapper) return
  if (props.gridSize <= 0) {
    // 清除网格
    wrapper.style.backgroundImage = ''
    wrapper.style.backgroundSize = ''
    return
  }
  // 通过 CSS background 实现网格线（不污染画布对象）
  wrapper.style.backgroundImage = `
    linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)
  `
  wrapper.style.backgroundSize = `${props.gridSize}px ${props.gridSize}px`
}

watch(() => props.gridSize, drawGrid)

// ── 公共方法 ──

/** 加载 Fabric JSON */
const loadFromJSON = async (json: string | object): Promise<void> => {
  if (!canvas) return
  const data = typeof json === 'string' ? json : JSON.stringify(json)
  isLoadingState = true
  return canvas.loadFromJSON(data).then(() => {
    canvas!.renderAll()
    if (props.runtime) {
      canvas!.forEachObject((obj) => {
        obj.selectable = false
        obj.evented = false
      })
    }
    isLoadingState = false
    undoStack = []
    redoStack = []
    snapshot()
  })
}

/** 导出 Fabric JSON */
const toJSON = (): object => {
  return canvas?.toJSON(['_widgetType', '_bindable', '_bindTarget', '_bindProp', '_bindDeviceId', '_bindTagId', '_bindTagName', 'lockMovementX', 'lockMovementY', 'lockScalingX', 'lockScalingY', 'lockRotation', 'hasControls', 'selectable', 'evented']) || {}
}

/** 添加图元对象（直接传入 Fabric 实例或 JSON 对象） */
const addWidget = (fabricObj: any, left?: number, top?: number) => {
  if (!canvas) return

  const isFabricInstance = fabricObj && typeof fabricObj.set === 'function' && typeof fabricObj.type === 'string'

  const doAdd = (obj: any) => {
    if (left != null) obj.set({ left })
    if (top != null) obj.set({ top })
    // 吸附到网格
    if (props.gridSize > 0) {
      const gs = props.gridSize
      const l = obj.left || 0
      const t = obj.top || 0
      obj.set({ left: Math.round(l / gs) * gs, top: Math.round(t / gs) * gs })
    }
    obj.setCoords()
    canvas!.add(obj)
    canvas!.setActiveObject(obj)
    canvas!.requestRenderAll()
    snapshot()
  }

  if (isFabricInstance) {
    doAdd(fabricObj)
  } else {
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
    snapshot()
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
    snapshot()
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
  snapshot()
}

/** 清空画布 */
const clear = () => {
  canvas?.clear()
  canvas?.setBackgroundColor(props.background || '#1a1a2e', () => {})
  snapshot()
}

// ── 对齐/分布 ──

/** 获取所有选中对象，至少需要 1 个 */
const getActiveObjects = () => {
  if (!canvas) return []
  const active = canvas.getActiveObject()
  if (!active) return []
  if (active.type === 'activeSelection') {
    return (active as fabric.ActiveSelection).getObjects()
  }
  return [active]
}

/** 获取画布宽度/高度（不含缩放） */
const getCanvasSize = () => ({ w: props.width, h: props.height })

/**
 * 对齐逻辑：
 * - 多选（ActiveSelection）：选中对象之间互相对齐
 * - 单选：相对于画布边界对齐
 */
const alignLeft = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (!active) return
  if (active.type === 'activeSelection') {
    const targets = (active as fabric.ActiveSelection).getObjects()
    if (targets.length < 2) return
    const minLeft = Math.min(...targets.map(o => o.left || 0))
    targets.forEach(o => { o.set({ left: minLeft }); o.setCoords() })
  } else {
    // 单选 → 对齐到画布左边
    active.set({ left: 0 }); active.setCoords()
  }
  canvas.requestRenderAll()
  snapshot()
}

const alignRight = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (!active) return
  if (active.type === 'activeSelection') {
    const targets = (active as fabric.ActiveSelection).getObjects()
    if (targets.length < 2) return
    const maxRight = Math.max(...targets.map(o => (o.left || 0) + o.getScaledWidth()))
    targets.forEach(o => { o.set({ left: maxRight - o.getScaledWidth() }); o.setCoords() })
  } else {
    const { w } = getCanvasSize()
    active.set({ left: w - active.getScaledWidth() }); active.setCoords()
  }
  canvas.requestRenderAll()
  snapshot()
}

const alignTop = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (!active) return
  if (active.type === 'activeSelection') {
    const targets = (active as fabric.ActiveSelection).getObjects()
    if (targets.length < 2) return
    const minTop = Math.min(...targets.map(o => o.top || 0))
    targets.forEach(o => { o.set({ top: minTop }); o.setCoords() })
  } else {
    active.set({ top: 0 }); active.setCoords()
  }
  canvas.requestRenderAll()
  snapshot()
}

const alignBottom = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (!active) return
  if (active.type === 'activeSelection') {
    const targets = (active as fabric.ActiveSelection).getObjects()
    if (targets.length < 2) return
    const maxBottom = Math.max(...targets.map(o => (o.top || 0) + o.getScaledHeight()))
    targets.forEach(o => { o.set({ top: maxBottom - o.getScaledHeight() }); o.setCoords() })
  } else {
    const { h } = getCanvasSize()
    active.set({ top: h - active.getScaledHeight() }); active.setCoords()
  }
  canvas.requestRenderAll()
  snapshot()
}

const alignCenterH = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (!active) return
  if (active.type === 'activeSelection') {
    const targets = (active as fabric.ActiveSelection).getObjects()
    if (targets.length < 2) return
    const centers = targets.map(o => (o.left || 0) + o.getScaledWidth() / 2)
    const avgCenter = centers.reduce((a, b) => a + b, 0) / centers.length
    targets.forEach(o => { o.set({ left: avgCenter - o.getScaledWidth() / 2 }); o.setCoords() })
  } else {
    const { w } = getCanvasSize()
    active.set({ left: (w - active.getScaledWidth()) / 2 }); active.setCoords()
  }
  canvas.requestRenderAll()
  snapshot()
}

const alignCenterV = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (!active) return
  if (active.type === 'activeSelection') {
    const targets = (active as fabric.ActiveSelection).getObjects()
    if (targets.length < 2) return
    const centers = targets.map(o => (o.top || 0) + o.getScaledHeight() / 2)
    const avgCenter = centers.reduce((a, b) => a + b, 0) / centers.length
    targets.forEach(o => { o.set({ top: avgCenter - o.getScaledHeight() / 2 }); o.setCoords() })
  } else {
    const { h } = getCanvasSize()
    active.set({ top: (h - active.getScaledHeight()) / 2 }); active.setCoords()
  }
  canvas.requestRenderAll()
  snapshot()
}

const distributeH = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (!active) return
  let targets: any[]
  if (active.type === 'activeSelection') {
    targets = (active as fabric.ActiveSelection).getObjects()
  } else {
    // 单选时无分布意义
    return
  }
  if (targets.length < 3) return
  const sorted = [...targets].sort((a, b) => (a.left || 0) - (b.left || 0))
  const firstLeft = sorted[0].left || 0
  const lastRight = (sorted[sorted.length - 1].left || 0) + sorted[sorted.length - 1].getScaledWidth()
  const totalWidth = sorted.reduce((s, o) => s + o.getScaledWidth(), 0)
  const gap = (lastRight - firstLeft - totalWidth) / (sorted.length - 1)
  let x = firstLeft
  sorted.forEach(o => {
    o.set({ left: x })
    o.setCoords()
    x += o.getScaledWidth() + gap
  })
  canvas.requestRenderAll()
  snapshot()
}

const distributeV = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (!active) return
  let targets: any[]
  if (active.type === 'activeSelection') {
    targets = (active as fabric.ActiveSelection).getObjects()
  } else {
    return
  }
  if (targets.length < 3) return
  const sorted = [...targets].sort((a, b) => (a.top || 0) - (b.top || 0))
  const firstTop = sorted[0].top || 0
  const lastBottom = (sorted[sorted.length - 1].top || 0) + sorted[sorted.length - 1].getScaledHeight()
  const totalHeight = sorted.reduce((s, o) => s + o.getScaledHeight(), 0)
  const gap = (lastBottom - firstTop - totalHeight) / (sorted.length - 1)
  let y = firstTop
  sorted.forEach(o => {
    o.set({ top: y })
    o.setCoords()
    y += o.getScaledHeight() + gap
  })
  canvas.requestRenderAll()
  snapshot()
}

// ── 缩放/平移 ──

const setZoom = (zoom: number) => {
  if (!canvas) return
  if (zoom > 3) zoom = 3
  if (zoom < 0.1) zoom = 0.1
  canvas.setZoom(zoom)
  canvas.setWidth(props.width * zoom)
  canvas.setHeight(props.height * zoom)
  emit('zoom:changed', zoom)
}

const getZoom = () => canvas?.getZoom() || 1

const zoomFit = () => {
  if (!canvas) return
  const wrapper = canvasEl.value?.closest('.editor-canvas') as HTMLElement
  if (!wrapper) return
  const ww = wrapper.clientWidth - 32
  const wh = wrapper.clientHeight - 32
  const scaleX = ww / props.width
  const scaleY = wh / props.height
  const zoom = Math.min(scaleX, scaleY, 1)
  setZoom(zoom)
}

const zoomReset = () => setZoom(1)

// ── 层级调整 ──

const bringForward = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (active) { canvas.bringObjectForward(active); canvas.renderAll(); snapshot() }
}

const sendBackward = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (active) { canvas.sendObjectBackwards(active); canvas.renderAll(); snapshot() }
}

const bringToFront = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (active) { canvas.bringObjectToFront(active); canvas.renderAll(); snapshot() }
}

const sendToBack = () => {
  if (!canvas) return
  const active = canvas.getActiveObject()
  if (active) { canvas.sendObjectToBack(active); canvas.renderAll(); snapshot() }
}

// ── 锁定/解锁 ──

const lockSelected = () => {
  if (!canvas || props.runtime) return
  const active = canvas.getActiveObject()
  if (active) {
    active.set({ lockMovementX: true, lockMovementY: true, lockScalingX: true, lockScalingY: true, lockRotation: true, hasControls: false })
    canvas.renderAll()
    snapshot()
  }
}

const unlockSelected = () => {
  if (!canvas || props.runtime) return
  const active = canvas.getActiveObject()
  if (active) {
    active.set({ lockMovementX: false, lockMovementY: false, lockScalingX: false, lockScalingY: false, lockRotation: false, hasControls: true })
    canvas.renderAll()
    snapshot()
  }
}

const isLocked = () => {
  const active = canvas?.getActiveObject()
  return active ? !!(active as any).lockMovementX : false
}

// ── 复制/粘贴 ──

const copySelected = () => {
  if (!canvas || props.runtime) return
  const active = canvas.getActiveObject()
  if (!active) return
  active.clone().then((cloned: any) => {
    cloned.set({ left: (cloned.left || 0) + 20, top: (cloned.top || 0) + 20 })
    canvas!.add(cloned)
    canvas!.setActiveObject(cloned)
    canvas!.renderAll()
    snapshot()
  })
}

// ── 全选 ──

const selectAll = () => {
  if (!canvas || props.runtime) return
  canvas.discardActiveObject()
  const sel = new fabric.ActiveSelection(canvas.getObjects(), { canvas })
  canvas.setActiveObject(sel)
  canvas.renderAll()
}

// ── 运行时数据绑定 ──

const updateBoundValue = (
  fabricId: string,
  bindTarget: string,
  newValue: any,
  prop: string = 'text'
) => {
  if (!canvas) return
  const applyToChild = (child: any) => {
    if (child._bindTarget === bindTarget) {
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
    if ((obj as any)._bindTarget === bindTarget) {
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
    if (obj.type === 'group') {
      const group = obj as fabric.Group
      group.getObjects().forEach((child: any) => applyToChild(child))
    }
  })
  canvas.renderAll()
}

/** 蚂蚁线流动动画（运行时调用） */
const startFlowAnimation = () => {
  if (!canvas) return
  let offset = 0
  const animate = () => {
    offset += 0.5
    canvas!.forEachObject((obj: any) => {
      if (obj.type === 'group') {
        const group = obj as fabric.Group
        group.getObjects().forEach((child: any) => {
          if (child.strokeDashArray && child.strokeDashArray.length > 0) {
            child.set({ strokeDashOffset: -offset })
          }
        })
      }
    })
    canvas!.renderAll()
    if (!props.runtime) return // 只在运行时持续动画
    requestAnimationFrame(animate)
  }
  if (props.runtime) animate()
}

const toDataURL = (): string => {
  return canvas?.toDataURL({ format: 'png', quality: 0.8 } as any) || ''
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
  getZoom,
  zoomFit,
  zoomReset,
  selectAll,
  // 对齐/分布
  alignLeft,
  alignRight,
  alignTop,
  alignBottom,
  alignCenterH,
  alignCenterV,
  distributeH,
  distributeV,
  // 撤销/重做
  undo,
  redo,
  canUndo,
  canRedo,
  // 层级
  bringForward,
  sendBackward,
  bringToFront,
  sendToBack,
  // 锁定
  lockSelected,
  unlockSelected,
  isLocked,
  // 复制
  copySelected,
  // 蚂蚁线动画
  startFlowAnimation,
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
