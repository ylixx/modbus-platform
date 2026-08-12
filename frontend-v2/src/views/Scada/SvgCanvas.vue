<script setup lang="ts">
/**
 * SvgCanvas - FUXA 风格 SVG 画布组件
 *
 * 核心原理（参照 FUXA 架构）：
 * 1. 画布 = SVG 文档，图元 = SVG DOM 元素
 * 2. 视图内容 = SVG 字符串（innerHTML 注入渲染）
 * 3. 运行时通过 DOM API 操作 SVG 元素实现数据绑定
 * 4. 图元通过 type 属性识别类型
 * 5. 绑定信息存储在 data-* 自定义属性中
 *
 * 功能：
 * - SVG 画布渲染（innerHTML 注入）
 * - 图元拖放放置
 * - 图元选中/移动/缩放/删除（编辑模式）
 * - 缩放/平移画布
 * - 撤销/重做
 * - 网格/吸附
 * - 画布序列化（SVG 字符串保存）
 * - 运行时数据绑定（processValue）
 * - 管道流动动画（CSS 动画驱动）
 */

import { ref, onMounted, onUnmounted, watch } from 'vue'
import type { BindingDef, DictionaryGaugeSettings, GaugeSettings } from './hmi'
import { createGaugeSettings, createDefaultBinding, formatValue } from './hmi'
import { applySignalValue, applyStaticValues, buildSignalIndex } from './gauges-manager'
import type { BoundTarget, RuntimeContext } from './gauges-manager'

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
  (e: 'object:selected', obj: SVGElement | null): void
  (e: 'object:deselected'): void
  (e: 'canvas:changed'): void
  (e: 'ready'): void
  (e: 'zoom:changed', zoom: number): void
  (e: 'widget:interact', payload: { elementId: string; eventType: string; events: any[]; value?: any }): void
}>()

// ── DOM 引用 ──
const svgContainer = ref<HTMLDivElement>()
let svgRoot: SVGSVGElement | null = null
let svgMainGroup: SVGGElement | null = null

// ── 状态 ──
const zoomLevel = ref(1)
let panOffset = { x: 0, y: 0 }
let isPanning = false
let panStart = { x: 0, y: 0 }

// ── 选中状态 ──
let selectedElement: SVGElement | null = null
let selectionBox: SVGGElement | null = null

// ── 多选集合（Shift 点击追加；selectedElement = 集合中最后选中项） ──
let selectedSet = new Set<SVGElement>()

const getSelectedElements = (): SVGElement[] => {
  const arr = Array.from(selectedSet)
  return arr
}

// ── 拖拽移动 ──
let isDragging = false
let dragStart = { x: 0, y: 0 }
let dragElementStart: {
  x: number
  y: number
  set: Map<SVGElement, ElTransform>
} = { x: 0, y: 0, set: new Map() }

// ── 撤销/重做 ──
interface Snapshot {
  svg: string
  items: DictionaryGaugeSettings
}
let undoStack: Snapshot[] = []
let redoStack: Snapshot[] = []
let isLoadingState = false

// ── 图元配置（items 字典） ──
let itemsState: DictionaryGaugeSettings = {}
/** 运行时信号索引：signalId → 绑定目标 */
let signalIndex: Map<string, BoundTarget[]> | null = null

const cloneItems = <T>(items: T): T => {
  return JSON.parse(JSON.stringify(items))
}

const snapshot = () => {
  if (!svgRoot || !svgMainGroup || isLoadingState || props.runtime) return
  // 选择框不在快照内（去掉再放回，避免 undo 状态里混入框/手柄）
  const boxEl = selectionBox
  if (boxEl) boxEl.remove()
  const content = svgMainGroup.innerHTML
  if (boxEl) svgMainGroup.appendChild(boxEl)
  const items = cloneItems(itemsState)
  undoStack.push({ svg: content, items })
  if (undoStack.length > 50) undoStack.shift()
  redoStack = []
}

const restoreSnapshot = (snap: Snapshot) => {
  if (!svgRoot || !svgMainGroup) return
  // 记录当前选中的图元 id，restore 后按 id 重建选中（旧 DOM 引用已失效）
  const selIds = getSelectedElements().map((el) => el.getAttribute('id')).filter(Boolean) as string[]
  if (selectionBox) {
    selectionBox.remove()
    selectionBox = null
  }
  svgMainGroup.innerHTML = snap.svg
  itemsState = cloneItems(snap.items)
  signalIndex = buildSignalIndex(itemsState)
  bindElementEvents()
  const found: SVGElement[] = []
  for (const id of selIds) {
    const el = svgMainGroup.querySelector(`g[id="${id}"]`) as SVGElement | null
    if (el) found.push(el)
  }
  clearSelectionClasses()
  selectedSet = new Set(found)
  selectedElement = found.length ? found[found.length - 1] : null
  found.forEach((el) => el.classList.add('svg-selected'))
  if (found.length) createSelectionBox(getGroupBBox(found))
}

const undo = () => {
  if (!svgRoot || undoStack.length <= 1) return
  isLoadingState = true
  const current = undoStack.pop()!
  redoStack.push(current)
  const prev = undoStack[undoStack.length - 1]
  restoreSnapshot(prev)
  isLoadingState = false
}

const redo = () => {
  if (!svgRoot || redoStack.length === 0) return
  isLoadingState = true
  const next = redoStack.pop()!
  undoStack.push(next)
  restoreSnapshot(next)
  isLoadingState = false
}

const canUndo = () => undoStack.length > 1
const canRedo = () => redoStack.length > 0

// ── 初始化 SVG 画布 ──

const initSvgCanvas = () => {
  if (!svgContainer.value) return

  // 创建 SVG 根元素
  svgRoot = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svgRoot.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  svgRoot.setAttribute('width', String(props.width))
  svgRoot.setAttribute('height', String(props.height))
  svgRoot.setAttribute('viewBox', `0 0 ${props.width} ${props.height}`)
  svgRoot.style.background = props.background
  svgRoot.style.display = 'block'

  // 创建主图层
  svgMainGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g')
  svgMainGroup.setAttribute('id', 'main-layer')
  svgRoot.appendChild(svgMainGroup)

  svgContainer.value.appendChild(svgRoot)

  // 绑定画布事件
  bindCanvasEvents()

  // 初始快照
  snapshot()
  emit('ready')
}

// ── 画布级事件 ──

const bindCanvasEvents = () => {
  if (!svgRoot) return

  // 点击空白区域取消选中
  svgRoot.addEventListener('mousedown', (e: MouseEvent) => {
    if (props.runtime) return
    const target = e.target as SVGElement

    // 中键或 Alt+左键 → 平移
    if (e.button === 1 || (e.altKey && e.button === 0)) {
      isPanning = true
      panStart = { x: e.clientX, y: e.clientY }
      e.preventDefault()
      return
    }

    // 左键点击空白
    if (e.button === 0 && (target === svgRoot || target === svgMainGroup)) {
      deselectAll()
    }
  })

  svgRoot.addEventListener('mousemove', (e: MouseEvent) => {
    // 平移
    if (isPanning) {
      const dx = e.clientX - panStart.x
      const dy = e.clientY - panStart.y
      panOffset.x += dx
      panOffset.y += dy
      panStart = { x: e.clientX, y: e.clientY }
      applyTransform()
      return
    }

    // 拖拽移动图元（含多选集合）
    if (isDragging && dragElementStart.set.size > 0) {
      const dx = (e.clientX - dragStart.x) / zoomLevel.value
      const dy = (e.clientY - dragStart.y) / zoomLevel.value

      let snapDx = dx
      let snapDy = dy
      // 网格吸附（基于集合内首个元素原位置）
      if (props.gridSize > 0) {
        const first = dragElementStart.set.keys().next().value as SVGElement | undefined
        if (first) {
          const t0 = dragElementStart.set.get(first)!
          snapDx = Math.round((t0.x + dx) / props.gridSize) * props.gridSize - t0.x
          snapDy = Math.round((t0.y + dy) / props.gridSize) * props.gridSize - t0.y
        }
      }

      for (const [el, t] of dragElementStart.set) {
        setElTransform(el, { ...t, x: t.x + snapDx, y: t.y + snapDy })
      }
      updateSelectionBox()
    }
  })

  svgRoot.addEventListener('mouseup', () => {
    if (isPanning) {
      isPanning = false
      return
    }
    if (isDragging) {
      isDragging = false
      snapshot()
      emit('canvas:changed')
    }
  })

  // 滚轮缩放
  svgRoot.addEventListener('wheel', (e: WheelEvent) => {
    if (props.runtime) return
    e.preventDefault()
    const delta = e.deltaY > 0 ? -0.1 : 0.1
    let newZoom = zoomLevel.value + delta
    if (newZoom > 3) newZoom = 3
    if (newZoom < 0.1) newZoom = 0.1
    zoomLevel.value = newZoom
    applyTransform()
    emit('zoom:changed', newZoom)
  })
}

// ── 应用缩放+平移变换 ──

const applyTransform = () => {
  if (!svgRoot || !svgMainGroup) return
  // 使用 viewBox 模拟缩放+平移
  const z = zoomLevel.value
  const w = props.width / z
  const h = props.height / z
  const x = -panOffset.x / z
  const y = -panOffset.y / z
  svgRoot.setAttribute('viewBox', `${x} ${y} ${w} ${h}`)
  // 缩放/平移后刷新选择框坐标（getCTM 不含 viewBox，必须换算）
  if (selectedSet.size > 0) refreshSelectionBox()
}

// ── 画布网格（pattern 背景，随 zoom 缩放） ──

let gridRectEl: SVGRectElement | null = null

const renderGrid = () => {
  if (!svgRoot) return
  if (props.gridSize > 0) {
    const ns = 'http://www.w3.org/2000/svg'
    if (!gridRectEl) {
      let defs = svgRoot.querySelector('defs') as SVGDefsElement | null
      if (!defs) {
        defs = document.createElementNS(ns, 'defs')
        svgRoot.appendChild(defs)
      }
      let pattern = svgRoot.querySelector('#svg-grid-pattern') as SVGPatternElement | null
      if (!pattern) {
        pattern = document.createElementNS(ns, 'pattern')
        pattern.setAttribute('id', 'svg-grid-pattern')
        pattern.setAttribute('patternUnits', 'userSpaceOnUse')
        defs.appendChild(pattern)
      }
      pattern.innerHTML = ''
      const line = document.createElementNS(ns, 'path')
      line.setAttribute('d', `M ${props.gridSize} 0 L 0 0 0 ${props.gridSize}`)
      line.setAttribute('fill', 'none')
      line.setAttribute('stroke', 'rgba(120,140,180,0.16)')
      line.setAttribute('stroke-width', '1')
      pattern.appendChild(line)

      gridRectEl = document.createElementNS(ns, 'rect')
      gridRectEl.setAttribute('class', 'svg-grid-rect')
      gridRectEl.setAttribute('width', '100%')
      gridRectEl.setAttribute('height', '100%')
      gridRectEl.setAttribute('fill', 'url(#svg-grid-pattern)')
      gridRectEl.setAttribute('pointer-events', 'none')
      svgRoot.insertBefore(gridRectEl, svgMainGroup)
    }
    const pattern = svgRoot.querySelector('#svg-grid-pattern') as SVGPatternElement | null
    pattern?.setAttribute('width', String(props.gridSize))
    pattern?.setAttribute('height', String(props.gridSize))
  } else if (gridRectEl) {
    gridRectEl.remove()
    gridRectEl = null
    svgRoot.querySelector('#svg-grid-pattern')?.remove()
  }
}

/** 为图形元素加 non-scaling-stroke，使缩放时节线宽保持不变 */
const ensureNonScalingStroke = () => {
  if (!svgMainGroup) return
  svgMainGroup.querySelectorAll('rect,circle,ellipse,path,polyline,polygon,line').forEach((el) => {
    const e = el as SVGElement
    if (!e.getAttribute('vector-effect')) {
      e.setAttribute('vector-effect', 'non-scaling-stroke')
    }
  })
}

// ── 图元选中逻辑（支持 Shift 多选） ──

const clearSelectionClasses = () => {
  for (const el of selectedSet) el.classList.remove('svg-selected')
}

const deselectAll = () => {
  if (selectionBox) {
    selectionBox.remove()
    selectionBox = null
  }
  if (selectedSet.size > 0) {
    clearSelectionClasses()
    selectedSet = new Set()
    selectedElement = null
  }
  emit('object:deselected')
}

const refreshSelectionBox = () => {
  if (selectedSet.size === 0) return
  createSelectionBox(getGroupBBox(getSelectedElements()))
}

const selectElement = (el: SVGElement, additive = false) => {
  if (props.runtime) return
  if (selectionBox) {
    selectionBox.remove()
    selectionBox = null
  }
  if (additive) {
    // Shift 点击：切换该图元的选中状态
    if (selectedSet.has(el)) {
      selectedSet.delete(el)
      el.classList.remove('svg-selected')
      if (selectedElement === el) selectedElement = selectedSet.size ? getSelectedElements()[selectedSet.size - 1] : null
    } else {
      selectedSet.add(el)
      el.classList.add('svg-selected')
      selectedElement = el
    }
    if (selectedSet.size === 0) {
      emit('object:deselected')
      return
    }
  } else {
    clearSelectionClasses()
    selectedSet = new Set([el])
    el.classList.add('svg-selected')
    selectedElement = el
  }
  createSelectionBox(getGroupBBox(getSelectedElements()))
  emit('object:selected', selectedElement)
}

// ── 选择框（含 8 向缩放手柄 + 旋转手柄） ──

const createSelectionBox = (bbox: DOMRect) => {
  if (!svgMainGroup) return
  if (selectionBox) selectionBox.remove()

  const ns = 'http://www.w3.org/2000/svg'
  selectionBox = document.createElementNS(ns, 'g')
  selectionBox.setAttribute('class', 'selection-box')
  selectionBox.setAttribute('pointer-events', 'none')

  // 选中边框
  const rect = document.createElementNS(ns, 'rect')
  rect.setAttribute('x', String(bbox.x - 4))
  rect.setAttribute('y', String(bbox.y - 4))
  rect.setAttribute('width', String(bbox.width + 8))
  rect.setAttribute('height', String(bbox.height + 8))
  rect.setAttribute('fill', 'none')
  rect.setAttribute('stroke', '#3a8fd4')
  rect.setAttribute('stroke-width', '2')
  rect.setAttribute('stroke-dasharray', '6 3')
  selectionBox.appendChild(rect)

  const attachResize = (handle: SVGElement, mode: string) => {
    handle.setAttribute('pointer-events', 'all')
    handle.style.cursor = handle.getAttribute('cursor') || 'default'
    handle.addEventListener('pointerdown', (e: PointerEvent) => {
      e.preventDefault()
      e.stopPropagation()
      startResizeSession(mode, e.shiftKey)
    })
  }

  // 8个缩放手柄
  const handleSize = 8
  const positions = [
    { mode: 'nw', x: bbox.x - 4 - handleSize / 2, y: bbox.y - 4 - handleSize / 2, cursor: 'nw-resize' },
    { mode: 'n', x: bbox.x + bbox.width / 2 - handleSize / 2, y: bbox.y - 4 - handleSize / 2, cursor: 'n-resize' },
    { mode: 'ne', x: bbox.x + bbox.width + 4 - handleSize / 2, y: bbox.y - 4 - handleSize / 2, cursor: 'ne-resize' },
    { mode: 'e', x: bbox.x + bbox.width + 4 - handleSize / 2, y: bbox.y + bbox.height / 2 - handleSize / 2, cursor: 'e-resize' },
    { mode: 'se', x: bbox.x + bbox.width + 4 - handleSize / 2, y: bbox.y + bbox.height + 4 - handleSize / 2, cursor: 'se-resize' },
    { mode: 's', x: bbox.x + bbox.width / 2 - handleSize / 2, y: bbox.y + bbox.height + 4 - handleSize / 2, cursor: 's-resize' },
    { mode: 'sw', x: bbox.x - 4 - handleSize / 2, y: bbox.y + bbox.height + 4 - handleSize / 2, cursor: 'sw-resize' },
    { mode: 'w', x: bbox.x - 4 - handleSize / 2, y: bbox.y + bbox.height / 2 - handleSize / 2, cursor: 'w-resize' }
  ]
  positions.forEach((pos) => {
    const handle = document.createElementNS(ns, 'rect')
    handle.setAttribute('x', String(pos.x))
    handle.setAttribute('y', String(pos.y))
    handle.setAttribute('width', String(handleSize))
    handle.setAttribute('height', String(handleSize))
    handle.setAttribute('fill', '#3a8fd4')
    handle.setAttribute('stroke', '#ffffff')
    handle.setAttribute('stroke-width', '1')
    handle.setAttribute('class', 'resize-handle')
    handle.setAttribute('cursor', pos.cursor)
    attachResize(handle, pos.mode)
    selectionBox!.appendChild(handle)
  })

  // 旋转手柄（框上方圆点）
  const rotCx = bbox.x + bbox.width / 2
  const rotCy = bbox.y - 26
  const rotLine = document.createElementNS(ns, 'line')
  rotLine.setAttribute('x1', String(rotCx))
  rotLine.setAttribute('y1', String(bbox.y))
  rotLine.setAttribute('x2', String(rotCx))
  rotLine.setAttribute('y2', String(rotCy + 3))
  rotLine.setAttribute('stroke', '#3a8fd4')
  rotLine.setAttribute('stroke-width', '1')
  selectionBox.appendChild(rotLine)
  const rotHandle = document.createElementNS(ns, 'circle')
  rotHandle.setAttribute('cx', String(rotCx))
  rotHandle.setAttribute('cy', String(rotCy))
  rotHandle.setAttribute('r', '5')
  rotHandle.setAttribute('fill', '#3a8fd4')
  rotHandle.setAttribute('stroke', '#ffffff')
  rotHandle.setAttribute('stroke-width', '1')
  rotHandle.setAttribute('cursor', 'grab')
  rotHandle.setAttribute('pointer-events', 'all')
  rotHandle.setAttribute('class', 'rotate-handle')
  rotHandle.addEventListener('pointerdown', (e: PointerEvent) => {
    e.preventDefault()
    e.stopPropagation()
    startRotateSession(e)
  })
  selectionBox.appendChild(rotHandle)

  svgMainGroup.appendChild(selectionBox)
}

// ── 缩放会话（8 向手柄交互） ──

interface ResizeSession {
  els: SVGElement[]
  mode: string
  box: DOMRect
  starts: Map<SVGElement, ElTransform>
  keepRatio: boolean
}
let resizeSession: ResizeSession | null = null

const startResizeSession = (mode: string, keepRatio: boolean) => {
  const els = getSelectedElements()
  if (els.length === 0 || !svgRoot) return
  const box = getGroupBBox(els)
  const starts = new Map<SVGElement, ElTransform>()
  els.forEach((el) => starts.set(el, parseTransform(el)))
  resizeSession = { els, mode, box, starts, keepRatio: keepRatio || mode.length === 2 }

  const onMove = (e: PointerEvent) => {
    if (!resizeSession) return
    const { els: ses, mode: m, box: b, starts: st, keepRatio } = resizeSession
    const pt = screenToSvg(e.clientX, e.clientY)

    // 计算公共 box 的新宽高与锚点
    let newL = b.x
    let newT = b.y
    let newR = b.x + b.width
    let newB = b.y + b.height
    if (m.includes('e')) newR = Math.max(pt.x, b.x + 2)
    if (m.includes('w')) newL = Math.min(pt.x, b.x + b.width - 2)
    if (m.includes('s')) newB = Math.max(pt.y, b.y + 2)
    if (m.includes('n')) newT = Math.min(pt.y, b.y + b.height - 2)

    let newW = newR - newL
    let newH = newB - newT
    if (newW < 2) newW = 2
    if (newH < 2) newH = 2
    const factorX = newW / Math.max(b.width, 2)
    let factorY = newH / Math.max(b.height, 2)
    if (keepRatio) {
      const r = Math.max(b.width, 2) / Math.max(b.height, 2)
      factorY = factorX / r
    }

    for (const el of ses) {
      const t = st.get(el)!
      // 位置：沿被拉伸的方向按 factor 插值
      const nx = m.includes('w') ? newL + (t.x - b.x) * factorX : b.x + (t.x - b.x) * factorX
      const ny = m.includes('n') ? newT + (t.y - b.y) * factorY : b.y + (t.y - b.y) * factorY
      setElTransform(el, {
        x: nx,
        y: ny,
        scaleX: t.scaleX * factorX,
        scaleY: t.scaleY * factorY,
        angle: t.angle
      })
    }
    refreshSelectionBox()
  }
  const onUp = () => {
    resizeSession = null
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    refreshSelectionBox()
    snapshot()
    emit('canvas:changed')
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

// ── 旋转会话 ──

let rotateSession: {
  els: SVGElement[]
  startAngles: Map<SVGElement, number>
  box: DOMRect
  startDeg: number
} | null = null

const startRotateSession = (e: PointerEvent) => {
  const els = getSelectedElements()
  if (els.length === 0 || !svgRoot) return
  const box = getGroupBBox(els)
  const startAngles = new Map<SVGElement, number>()
  els.forEach((el) => startAngles.set(el, parseTransform(el).angle))
  const startPt = screenToSvg(e.clientX, e.clientY)
  const startDeg = (Math.atan2(startPt.y - box.y, startPt.x - box.x) * 180) / Math.PI

  const onMove = (ev: PointerEvent) => {
    if (!rotateSession) return
    const pt = screenToSvg(ev.clientX, ev.clientY)
    const curDeg = (Math.atan2(pt.y - rotateSession.box.y, pt.x - rotateSession.box.x) * 180) / Math.PI
    const delta = curDeg - rotateSession.startDeg
    for (const el of rotateSession.els) {
      const t = parseTransform(el)
      setElTransform(el, { ...t, angle: Math.round((rotateSession.startAngles.get(el)! + delta) * 10) / 10 })
    }
    refreshSelectionBox()
  }
  const onUp = () => {
    rotateSession = null
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    refreshSelectionBox()
    snapshot()
    emit('canvas:changed')
  }
  rotateSession = { els, startAngles, box, startDeg }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

const updateSelectionBox = () => {
  if (selectedSet.size === 0) return
  createSelectionBox(getGroupBBox(getSelectedElements()))
}

// ── 变换工具（translate + scale + rotate，左上角锚点） ──

interface ElTransform {
  x: number
  y: number
  scaleX: number
  scaleY: number
  angle: number
}

/** 解析图元 transform 属性 */
const parseTransform = (el: SVGElement): ElTransform => {
  const t = el.getAttribute('transform') || ''
  const read = (name: string): number[] | null => {
    const m = t.match(new RegExp(`${name}\\(([^)]+)\\)`))
    if (!m) return null
    return m[1].split(/[, ]+/).map((v) => parseFloat(v))
  }
  const tr = read('translate')
  const sc = read('scale')
  const rot = read('rotate')
  return {
    x: tr?.[0] ?? 0,
    y: tr?.[1] ?? 0,
    scaleX: sc?.[0] ?? 1,
    scaleY: sc && sc.length > 1 ? sc[1] : sc?.[0] ?? 1,
    angle: rot?.[0] ?? 0
  }
}

/** 序列化图元 transform 属性 */
const serializeTransform = (el: SVGElement, t: ElTransform) => {
  const parts: string[] = []
  if (t.x !== 0 || t.y !== 0) parts.push(`translate(${t.x},${t.y})`)
  if (t.scaleX !== 1 || t.scaleY !== 1) parts.push(`scale(${t.scaleX},${t.scaleY})`)
  if (t.angle) parts.push(`rotate(${t.angle})`)
  el.setAttribute('transform', parts.join(' '))
}

const setElTransform = (el: SVGElement, t: ElTransform) => {
  serializeTransform(el, t)
}

/** 获取元素经过完整 transform（含 rotate/scale）后的边界框（已在用户坐标空间） */
const getTransformedBBox = (el: SVGElement): DOMRect | null => {
  try {
    const svgEl = el as SVGGElement
    const bbox = svgEl.getBBox()
    const ctm = svgEl.getCTM()
    if (!ctm) return null
    // 解析 svg 的 viewBox（canvas 缩放/平移通过 viewBox 实现）
    const vb = (svgRoot?.getAttribute('viewBox') || '0 0 1280 720').split(/[\s,]+/).map(Number)
    const [vbX, vbY, vbW] = vb
    const scale = vbW > 0 ? Number(props.width) / vbW : 1
    const corners = [
      { x: bbox.x, y: bbox.y },
      { x: bbox.x + bbox.width, y: bbox.y },
      { x: bbox.x, y: bbox.y + bbox.height },
      { x: bbox.x + bbox.width, y: bbox.y + bbox.height }
    ].map((p) => {
      // getCTM 的返回值位于视口坐标系（不含 viewBox 变换），需映射回用户坐标
      const q = new DOMPoint(p.x, p.y).matrixTransform(ctm)
      return { x: vbX + q.x / scale, y: vbY + q.y / scale }
    })
    const xs = corners.map((c) => c.x)
    const ys = corners.map((c) => c.y)
    const minX = Math.min(...xs)
    const minY = Math.min(...ys)
    const maxX = Math.max(...xs)
    const maxY = Math.max(...ys)
    return {
      x: minX,
      y: minY,
      width: maxX - minX,
      height: maxY - minY,
      top: minY,
      right: maxX,
      bottom: maxY,
      left: minX,
      toJSON: () => ({})
    } as DOMRect
  } catch {
    return null
  }
}

/** 多选集合的公共边界框 */
const getGroupBBox = (els: SVGElement[]): DOMRect => {
  let box: DOMRect | null = null
  for (const el of els) {
    const b = getTransformedBBox(el)
    if (!b) continue
    if (!box) {
      box = b
      continue
    }
    const x0 = Math.min(box.x, b.x)
    const y0 = Math.min(box.y, b.y)
    const x1 = Math.max(box.x + box.width, b.x + b.width)
    const y1 = Math.max(box.y + box.height, b.y + b.height)
    box = {
      x: x0,
      y: y0,
      width: x1 - x0,
      height: y1 - y0,
      top: y0,
      right: x1,
      bottom: y1,
      left: x0,
      toJSON: () => ({})
    } as DOMRect
  }
  return box || ({ x: 0, y: 0, width: 0, height: 0 } as DOMRect)
}

/** 屏幕坐标 → SVG 坐标（当前 viewBox/缩放下） */
const screenToSvg = (clientX: number, clientY: number) => {
  const ctm = svgRoot?.getScreenCTM()
  if (!ctm) return { x: 0, y: 0 }
  const p = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse())
  return { x: p.x, y: p.y }
}

// ── 绑定图元元素事件 ──

const bindElementEvents = () => {
  if (!svgMainGroup || props.runtime) return

  // 遍历所有图元 group 并绑定事件
  const groups = svgMainGroup.querySelectorAll(':scope > g[type]')
  groups.forEach((el) => {
    const svgEl = el as SVGElement
    svgEl.style.cursor = 'move'
    svgEl.setAttribute('tabindex', '0')

    // 选中事件（Shift 多选）
    svgEl.addEventListener('mousedown', (e: MouseEvent) => {
      if (props.runtime) return
      if (e.button !== 0) return
      e.stopPropagation()

      selectElement(svgEl, e.shiftKey)

      // 开始拖拽（多选时拖动整个集合）
      isDragging = true
      dragStart = { x: e.clientX, y: e.clientY }
      dragElementStart = {
        x: 0,
        y: 0,
        set: new Map<SVGElement, ElTransform>()
      }
      for (const el of getSelectedElements()) {
        dragElementStart.set.set(el, parseTransform(el))
      }
    })

    // 双击编辑文本
    svgEl.addEventListener('dblclick', (e: MouseEvent) => {
      if (props.runtime) return
      e.stopPropagation()
      const textEl = svgEl.querySelector('text') as SVGElement | null
      if (!textEl) return
      const id = svgEl.getAttribute('id')
      const bound = textEl.getAttribute('data-bind-target')
      const def = id && bound ? itemsState[id]?.bindings?.[bound] : undefined
      if (def?.variableId) {
        window.alert('该文本已绑定数据点位，请在「数据绑定」中修改')
        return
      }
      const val = window.prompt('编辑文本内容', textEl.textContent || '')
      if (val !== null) {
        textEl.textContent = val
        snapshot()
        emit('canvas:changed')
      }
    })
  })
}

// ── 公共方法 ──

/** 从 SVG 字符串加载 */
const loadFromSVG = (svgContent: string): Promise<void> => {
  return new Promise((resolve) => {
    if (!svgMainGroup) { resolve(); return }

    isLoadingState = true

    if (!svgContent || svgContent === '[]') {
      svgMainGroup.innerHTML = ''
      isLoadingState = false
      undoStack = []
      redoStack = []
      snapshot()
      resolve()
      return
    }

    // 尝试解析为完整 SVG 文档
    if (svgContent.includes('<svg')) {
      const parser = new DOMParser()
      const doc = parser.parseFromString(svgContent, 'image/svg+xml')
      const svgEl = doc.querySelector('svg')
      if (svgEl) {
        // 提取 body 内容
        svgMainGroup.innerHTML = svgEl.innerHTML
      } else {
        svgMainGroup.innerHTML = svgContent
      }
    } else {
      // 直接作为 SVG 片段注入
      svgMainGroup.innerHTML = svgContent
    }

    bindElementEvents()
    ensureNonScalingStroke()
    isLoadingState = false
    undoStack = []
    redoStack = []
    snapshot()
    resolve()
  })
}

/** 导出 SVG 字符串 */
const toSVGString = (): string => {
  if (!svgMainGroup) return ''
  return svgMainGroup.innerHTML
}

/** 导出完整 SVG 文档 */
const toSVGDocument = (): string => {
  if (!svgRoot || !svgMainGroup) return ''
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${props.width}" height="${props.height}" viewBox="0 0 ${props.width} ${props.height}">
  <rect width="100%" height="100%" fill="${props.background}"/>
  ${svgMainGroup.innerHTML}
</svg>`
}

/** 添加 SVG 图元片段 */
const addWidgetSVG = (svgFragment: string, left?: number, top?: number) => {
  if (!svgMainGroup) return

  const tempDiv = document.createElement('div')
  tempDiv.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg">${svgFragment}</svg>`
  const tempSvg = tempDiv.querySelector('svg')

  if (tempSvg) {
    const fragment = document.createDocumentFragment()
    while (tempSvg.firstChild) {
      fragment.appendChild(tempSvg.firstChild)
    }

    const firstChild = fragment.firstChild as SVGElement | null
    if (firstChild) {
      const l = left ?? 100
      const t = top ?? 100
      // 更新 transform
      if (firstChild.nodeName === 'g') {
        firstChild.setAttribute('transform', `translate(${l},${t})`)
      }
      svgMainGroup.appendChild(fragment)
      // 为新图元初始化 items 条目（扫描 data-bind-target 建空绑定域）
      initItemsForElement(firstChild)
      bindElementEvents()
      ensureNonScalingStroke()
      signalIndex = buildSignalIndex(itemsState)
      snapshot()
      emit('canvas:changed')
    }
  }
}

/** 为单个图元初始化 items 条目 */
const initItemsForElement = (el: SVGElement) => {
  const id = el.getAttribute('id')
  if (!id || itemsState[id]) return
  const type = el.getAttribute('type') || 'svg-ext-shapes'
  const gauge = createGaugeSettings(id, type)
  const targets = new Set<string>()
  el.querySelectorAll('[data-bind-target]').forEach((child) => {
    const t = child.getAttribute('data-bind-target')
    if (t) targets.add(t)
  })
  for (const t of targets) {
    gauge.bindings[t] = createDefaultBinding()
  }
  // 交互控件预设默认事件（M2：onSetValue/onToggleValue）
  gauge.events = defaultEventsForType(type)
  itemsState[id] = gauge
}

/** 控件图元默认交互事件（无 target 时用户后续在绑定面板补全设备/点位） */
const defaultEventsForType = (type: string): any[] => {
  switch (type) {
    case 'svg-ext-button':
      return [{ type: 'click', action: 'onSetValue', actoptions: { valueType: 'fixed', fixedValue: 1 } }]
    case 'svg-ext-switch':
      return [{ type: 'click', action: 'onToggleValue', actoptions: { valueType: 'toggle', onValue: 1, offValue: 0 } }]
    case 'svg-ext-slider':
      return [{ type: 'change', action: 'onSetValue', actoptions: { valueType: 'slider', min: 0, max: 100 } }]
    case 'svg-ext-input':
      return [{ type: 'change', action: 'onSetValue', actoptions: { valueType: 'input' } }]
    default:
      return []
  }
}

/** 删除选中图元（支持多选） */
const deleteSelected = () => {
  const els = getSelectedElements()
  if (els.length === 0 || !svgMainGroup || props.runtime) return
  for (const el of els) {
    const id = el.getAttribute('id')
    el.remove()
    if (id) delete itemsState[id]
  }
  deselectAll()
  signalIndex = buildSignalIndex(itemsState)
  snapshot()
  emit('canvas:changed')
}

/** 清空画布 */
const clear = () => {
  if (!svgMainGroup) return
  svgMainGroup.innerHTML = ''
  itemsState = {}
  signalIndex = null
  deselectAll()
  snapshot()
  emit('canvas:changed')
}

// ── 缩放/平移 ──

const setZoom = (zoom: number) => {
  if (zoom > 3) zoom = 3
  if (zoom < 0.1) zoom = 0.1
  zoomLevel.value = zoom
  applyTransform()
  emit('zoom:changed', zoom)
}

const getZoom = () => zoomLevel.value

const zoomFit = () => {
  zoomLevel.value = 1
  panOffset = { x: 0, y: 0 }
  applyTransform()
  emit('zoom:changed', 1)
}

const zoomReset = () => {
  zoomLevel.value = 1
  panOffset = { x: 0, y: 0 }
  if (svgRoot) {
    svgRoot.setAttribute('viewBox', `0 0 ${props.width} ${props.height}`)
  }
  emit('zoom:changed', 1)
}

// ── 层级调整（多选按 DOM 顺序批量） ──

const bringForward = () => {
  if (!svgMainGroup) return
  const els = getSelectedElements().filter((el) => el.parentElement)
  if (els.length === 0) return
  const ordered = els.sort((a, b) => Array.from(svgMainGroup!.children).indexOf(a) - Array.from(svgMainGroup!.children).indexOf(b))
  for (const el of ordered) {
    let next = el.nextElementSibling
    while (next && ordered.includes(next as SVGElement)) next = next.nextElementSibling
    if (next) svgMainGroup.insertBefore(next, el)
  }
  snapshot()
}

const sendBackward = () => {
  if (!svgMainGroup) return
  const els = getSelectedElements().filter((el) => el.parentElement)
  if (els.length === 0) return
  const ordered = els.sort((a, b) => Array.from(svgMainGroup!.children).indexOf(a) - Array.from(svgMainGroup!.children).indexOf(b))
  for (let i = ordered.length - 1; i >= 0; i--) {
    const el = ordered[i]
    let prev = el.previousElementSibling
    while (prev && ordered.includes(prev as SVGElement)) prev = prev.previousElementSibling
    if (prev) svgMainGroup.insertBefore(el, prev)
  }
  snapshot()
}

const bringToFront = () => {
  if (!svgMainGroup) return
  const els = getSelectedElements().filter((el) => el.parentElement)
  if (els.length === 0) return
  const ordered = els.sort((a, b) => Array.from(svgMainGroup!.children).indexOf(a) - Array.from(svgMainGroup!.children).indexOf(b))
  for (const el of ordered) svgMainGroup.appendChild(el)
  snapshot()
}

const sendToBack = () => {
  if (!svgMainGroup) return
  const els = getSelectedElements().filter((el) => el.parentElement)
  if (els.length === 0) return
  const ordered = els.sort((a, b) => Array.from(svgMainGroup!.children).indexOf(a) - Array.from(svgMainGroup!.children).indexOf(b))
  for (let i = ordered.length - 1; i >= 0; i--) {
    svgMainGroup.insertBefore(ordered[i], svgMainGroup.firstChild)
  }
  snapshot()
}

// ── 锁定/解锁 ──

const lockSelected = () => {
  const els = getSelectedElements()
  if (els.length === 0 || props.runtime) return
  for (const el of els) {
    el.setAttribute('data-locked', 'true')
    el.style.cursor = 'default'
  }
  snapshot()
}

const unlockSelected = () => {
  const els = getSelectedElements()
  if (els.length === 0 || props.runtime) return
  for (const el of els) {
    el.removeAttribute('data-locked')
    el.style.cursor = 'move'
  }
  snapshot()
}

const isLocked = () => {
  return selectedElement ? selectedElement.getAttribute('data-locked') === 'true' : false
}

// ── 复制 ──

const copySelected = () => {
  const els = getSelectedElements()
  if (els.length === 0 || !svgMainGroup || props.runtime) return
  const clones: SVGElement[] = []
  for (const el of els) {
    const clone = el.cloneNode(true) as SVGElement
    const oldId = clone.getAttribute('id') || ''
    const newId = oldId.replace(/_\d+$/, '') + '_' + Date.now() + '_' + Math.random().toString(36).slice(2, 5)
    clone.setAttribute('id', newId)
    const t = parseTransform(clone)
    setElTransform(clone, { ...t, x: t.x + 20, y: t.y + 20 })
    svgMainGroup.appendChild(clone)
    if (oldId && itemsState[oldId]) {
      const copied = cloneItems(itemsState[oldId])
      copied.id = newId
      itemsState[newId] = copied
    } else {
      initItemsForElement(clone)
    }
    clones.push(clone)
  }
  // 选中克隆集合
  clearSelectionClasses()
  selectedSet = new Set(clones)
  selectedElement = clones[clones.length - 1]
  clones.forEach((c) => c.classList.add('svg-selected'))
  createSelectionBox(getGroupBBox(clones))
  emit('object:selected', selectedElement)
  signalIndex = buildSignalIndex(itemsState)
  snapshot()
  emit('canvas:changed')
}

// ── 对齐 ──

// ── 对齐 / 分布 ──

type AlignMode = 'left' | 'centerH' | 'right' | 'top' | 'centerV' | 'bottom'

/**
 * 对齐：单选 → 对齐到画布；多选 → 对齐到公共边界
 */
const alignSelected = (mode: AlignMode) => {
  const els = getSelectedElements()
  if (els.length === 0 || props.runtime) return
  const box = getGroupBBox(els)
  const W = props.width
  const H = props.height

  let tx = 0
  let ty = 0
  if (els.length === 1) {
    // 对齐到画布
    if (mode === 'left') tx = 0 - box.x
    if (mode === 'centerH') tx = W / 2 - box.width / 2 - box.x
    if (mode === 'right') tx = W - box.width - box.x
    if (mode === 'top') ty = 0 - box.y
    if (mode === 'centerV') ty = H / 2 - box.height / 2 - box.y
    if (mode === 'bottom') ty = H - box.height - box.y
  } else {
    // 对齐到公共边界（首个元素不动，其余按公共框对齐）
    const anchor = getTransformedBBox(els[0])!
    if (mode === 'left') tx = anchor.x - box.x
    if (mode === 'centerH') tx = anchor.x + anchor.width / 2 - box.width / 2 - box.x
    if (mode === 'right') tx = anchor.x + anchor.width - box.width - box.x
    if (mode === 'top') ty = anchor.y - box.y
    if (mode === 'centerV') ty = anchor.y + anchor.height / 2 - box.height / 2 - box.y
    if (mode === 'bottom') ty = anchor.y + anchor.height - box.height - box.y
  }

  for (const el of els) {
    const t = parseTransform(el)
    setElTransform(el, { ...t, x: t.x + tx, y: t.y + ty })
  }
  refreshSelectionBox()
  snapshot()
  emit('canvas:changed')
}

/**
 * 分布：按中心点均匀分布（需 ≥3 个图元）
 */
const distributeSelected = (mode: 'horizontal' | 'vertical') => {
  const els = getSelectedElements()
  if (els.length < 3 || props.runtime) return
  const entries = els
    .map((el) => ({ el, box: getTransformedBBox(el)! }))
    .sort((a, b) => (mode === 'horizontal' ? a.box.x - b.box.x : a.box.y - b.box.y))

  const min = mode === 'horizontal' ? entries[0].box.x : entries[0].box.y
  const lastBox = entries[entries.length - 1].box
  const max = (mode === 'horizontal' ? lastBox.x + lastBox.width : lastBox.y + lastBox.height) - min
  const sizes = entries.map((e) => (mode === 'horizontal' ? e.box.width : e.box.height))
  const total = sizes.reduce((a, b) => a + b, 0)
  const gap = (max - total) / (entries.length - 1)
  if (gap < 0) return

  let cursor = min
  for (const e of entries) {
    const t = parseTransform(e.el)
    if (mode === 'horizontal') setElTransform(e.el, { ...t, x: t.x + cursor - e.box.x })
    else setElTransform(e.el, { ...t, y: t.y + cursor - e.box.y })
    cursor += (mode === 'horizontal' ? e.box.width : e.box.height) + gap
  }
  refreshSelectionBox()
  snapshot()
  emit('canvas:changed')
}

// ── items 绑定配置（v2，多属性域） ──

/**
 * 设置图元某绑定域的配置（null = 移除该域）
 */
const setBindingDef = (elementId: string, target: string, def: BindingDef | null) => {
  const gauge = itemsState[elementId]
  if (!gauge) return
  if (def) {
    gauge.bindings = { ...gauge.bindings, [target]: def }
  } else {
    const next = { ...gauge.bindings }
    delete next[target]
    gauge.bindings = next
  }
  signalIndex = buildSignalIndex(itemsState)
  snapshot()
  emit('canvas:changed')
}

/** 获取图元所有绑定域配置 */
const getBindingDefs = (elementId: string): Array<{ target: string; def: BindingDef }> => {
  const gauge = itemsState[elementId]
  if (!gauge) return []
  return Object.entries(gauge.bindings).map(([target, def]) => ({ target, def }))
}

/** 获取图元完整配置 */
const getGaugeSettings = (elementId: string): GaugeSettings | null => {
  return itemsState[elementId] || null
}

// ── 交互事件（M2：写值控制） ──

/** 设置图元的交互事件列表 */
const setGaugeEvents = (elementId: string, events: any[]) => {
  const gauge = itemsState[elementId]
  if (!gauge) return
  gauge.events = events.map((e) => JSON.parse(JSON.stringify(e)))
  snapshot()
  emit('canvas:changed')
}

/** 获取图元交互事件列表 */
const getGaugeEvents = (elementId: string): any[] => {
  const gauge = itemsState[elementId]
  return gauge ? JSON.parse(JSON.stringify(gauge.events || [])) : []
}

// ── 运行时引擎（v2，信号索引驱动） ──

/** 运行时初始化：重建信号索引 + 渲染静态值 + 绑定交互事件 */
const initRuntime = () => {
  if (!svgMainGroup) return
  signalIndex = buildSignalIndex(itemsState)
  applyStaticValues(
    {
      svgRoot: svgMainGroup,
      items: itemsState,
      index: signalIndex
    } as RuntimeContext,
    trendHandler
  )
  bindInteractions()
}

/**
 * 应用信号值到所有绑定图元（FUXA: processValue）
 * @param signalId 信号ID，格式 "deviceId:tagName"
 */
const applySignalValueToCanvas = (signalId: string, value: number | string | boolean) => {
  if (!svgMainGroup || !signalIndex) return
  applySignalValue(
    { svgRoot: svgMainGroup, items: itemsState, index: signalIndex } as RuntimeContext,
    signalId,
    value,
    trendHandler
  )
}

/** 获取画面所有已绑定的信号ID */
const getBoundSignals = (): string[] => {
  return signalIndex ? Array.from(signalIndex.keys()) : []
}

// ── 趋势图元（M4） ──

interface ChartState {
  elementId: string
  points: number[]
  maxPoints: number
  fixedMin: number | null
  fixedMax: number | null
  w: number
  h: number
}
const charts = new Map<string, ChartState>()
const TREND_MAX_POINTS = 300

const initChart = (elementId: string): ChartState | null => {
  const group = svgMainGroup?.querySelector(`#${elementId}`)
  if (!group) return null
  let w = 320
  let h = 180
  try {
    const b = (group as SVGGElement).getBBox()
    if (b.width > 0) {
      w = b.width
      h = b.height
    }
  } catch {
    // keep defaults
  }
  // 固定 Y 轴范围（绑定域 ranges[0]）
  let fixedMin: number | null = null
  let fixedMax: number | null = null
  const gauge = itemsState[elementId]
  if (gauge && gauge.bindings) {
    const trendEl = group.querySelector('[data-bind-prop="trend"]')
    const target = trendEl?.getAttribute('data-bind-target')
    const def = target ? gauge.bindings[target] : undefined
    const r0 = def?.ranges?.[0]
    if (r0 && r0.max - r0.min > 0) {
      fixedMin = r0.min
      fixedMax = r0.max
    }
  }
  const state: ChartState = {
    elementId,
    points: [],
    maxPoints: TREND_MAX_POINTS,
    fixedMin,
    fixedMax,
    w,
    h
  }
  charts.set(elementId, state)
  return state
}

const redrawChart = (chart: ChartState) => {
  const polyline = svgMainGroup?.querySelector(`#${chart.elementId} [data-bind-prop="trend"]`)
  if (!polyline) return
  const pad = 10
  const innerH = Math.max(10, chart.h - pad * 2)

  let minY = chart.fixedMin
  let maxY = chart.fixedMax
  if (minY === null || maxY === null) {
    if (chart.points.length === 0) return
    minY = Math.min(...chart.points)
    maxY = Math.max(...chart.points)
    if (maxY - minY < 1e-9) {
      minY -= 1
      maxY += 1
    }
  }

  const n = chart.points.length
  const totalW = chart.w - pad * 2
  const pts = chart.points.map((v, i) => {
    const x = n <= 1 ? pad : pad + (i / (n - 1)) * totalW
    const y = pad + innerH - ((v - minY) / (maxY - minY)) * innerH
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  polyline.setAttribute('points', pts.join(' '))
}

/** 趋势值回调（applyBinding trend 域） */
const trendHandler = (elementId: string, raw: number) => {
  let chart = charts.get(elementId)
  if (!chart) {
    const created = initChart(elementId)
    if (!created) return
    chart = created
  }
  chart.points.push(raw)
  if (chart.points.length > chart.maxPoints) chart.points.shift()
  redrawChart(chart)
}

/** 清空趋势缓冲（画面重新加载时） */
const resetTrendCharts = () => {
  charts.clear()
}

/** 载入历史数据到趋势图元（viewer 页面加载后调用） */
const loadTrendData = (elementId: string, series: number[]) => {
  let chart = charts.get(elementId)
  if (!chart) {
    const created = initChart(elementId)
    if (!created) return
    chart = created
  }
  chart.points = series.slice(-chart.maxPoints)
  redrawChart(chart)
}

/** 获取所有趋势图元的信号绑定（含 tagId，供历史查询） */
const getTrendTargets = (): Array<{
  elementId: string
  deviceId: number
  tagId: number
  tagName: string
}> => {
  const targets: Array<{
    elementId: string
    deviceId: number
    tagId: number
    tagName: string
  }> = []
  if (!svgMainGroup) return targets
  for (const gauge of Object.values(itemsState)) {
    for (const [target, def] of Object.entries(gauge.bindings || {})) {
      if (!def.variableId || !def.tagId) continue
      const el = svgMainGroup.querySelector(`#${gauge.id} [data-bind-target="${target}"]`)
      if (el?.getAttribute('data-bind-prop') !== 'trend') continue
      const [deviceId, tagName] = def.variableId.split(':')
      targets.push({
        elementId: gauge.id,
        deviceId: Number(deviceId),
        tagId: def.tagId,
        tagName: tagName || ''
      })
    }
  }
  return targets
}

// ── 运行时交互（M2：点击/变更 → emit widget:interact） ──

let interactionCleanup: Array<() => void> = []
let sliderDrag: {
  group: SVGGElement
  knob: SVGElement
  fill: SVGElement | null
  text: SVGElement | null
  bbox: DOMRect
  localWidth: number
  max: number
  min: number
  events: any[]
} | null = null

const cleanupInteractions = () => {
  interactionCleanup.forEach((fn) => fn())
  interactionCleanup = []
  sliderDrag = null
}

/** 运行时绑定交互事件（runtime 模式，编辑模式跳过） */
const bindInteractions = () => {
  cleanupInteractions()
  if (!props.runtime || !svgMainGroup) return

  for (const gauge of Object.values(itemsState)) {
    const events = (gauge.events || []).filter(
      (e) => e.action === 'onSetValue' || e.action === 'onToggleValue'
    )
    if (events.length === 0) continue
    const group = svgMainGroup.querySelector(`#${gauge.id}`)
    if (!group) continue

    // click（按钮/开关）
    const clickEvents = events.filter((e) => e.type === 'click')
    if (clickEvents.length > 0) {
      const handler = () => {
        emit('widget:interact', {
          elementId: gauge.id,
          eventType: 'click',
          events: clickEvents
        })
      }
      group.addEventListener('click', handler)
      interactionCleanup.push(() => group.removeEventListener('click', handler))
    }

    // change（输入框 / 滑块拖动）
    const changeEvents = events.filter((e) => e.type === 'change')
    if (changeEvents.length > 0) {
      const input = group.querySelector('input[type="text"]') as HTMLInputElement | null
      if (input) {
        const onInput = () => {
          emit('widget:interact', {
            elementId: gauge.id,
            eventType: 'change',
            events: changeEvents,
            value: input.value
          })
        }
        input.addEventListener('change', onInput)
        interactionCleanup.push(() => input.removeEventListener('change', onInput))
      }

      // 滑块拖动（指针在圆点上按下后跟随）
      const knob = group.querySelector(
        'circle[data-bind-target="value"][data-bind-prop="cx"]'
      ) as SVGElement | null
      if (knob) {
        const options = changeEvents[0]?.actoptions || {}
        const onPointerDown = (e: PointerEvent) => {
          e.preventDefault()
          e.stopPropagation()
          const groupEl = group as SVGGElement
          const bbox = groupEl.getBoundingClientRect()
          sliderDrag = {
            group: groupEl,
            knob,
            fill: groupEl.querySelector('[data-bind-target="value"][data-bind-prop="width"]'),
            text: groupEl.querySelector('[data-bind-target="value"][data-bind-prop="text"]'),
            bbox,
            localWidth: (() => {
              try {
                return groupEl.getBBox().width
              } catch {
                return bbox.width
              }
            })(),
            min: Number(options.min ?? 0),
            max: Number(options.max ?? 100),
            events: changeEvents
          }
          knob.setPointerCapture(e.pointerId)
          updateSliderDrag(e.clientX)
        }
        const onPointerMove = (e: PointerEvent) => {
          if (sliderDrag && sliderDrag.knob === knob) updateSliderDrag(e.clientX)
        }
        const onPointerUp = (e: PointerEvent) => {
          if (sliderDrag && sliderDrag.knob === knob) {
            updateSliderDrag(e.clientX)
            emit('widget:interact', {
              elementId: gauge.id,
              eventType: 'change',
              events: sliderDrag.events,
              value: formatValue(currentSliderValue, '')
            })
            sliderDrag = null
          }
        }
        knob.addEventListener('pointerdown', onPointerDown)
        knob.addEventListener('pointermove', onPointerMove)
        knob.addEventListener('pointerup', onPointerUp)
        interactionCleanup.push(() => {
          knob.removeEventListener('pointerdown', onPointerDown)
          knob.removeEventListener('pointermove', onPointerMove)
          knob.removeEventListener('pointerup', onPointerUp)
        })
      }
    }
  }
}

let currentSliderValue = 0

/** 拖动中更新滑块位置与文本 */
const updateSliderDrag = (clientX: number) => {
  if (!sliderDrag) return
  const { bbox, localWidth, min, max, knob, fill, text } = sliderDrag
  const ratio = Math.max(0, Math.min(1, (clientX - bbox.left) / (bbox.width || 1)))
  const value = min + ratio * (max - min)
  currentSliderValue = Math.round(value * 100) / 100
  const localX = localWidth * ratio
  knob.setAttribute('cx', String(localX))
  fill?.setAttribute('width', String(localX))
  if (text) text.textContent = formatValue(currentSliderValue, '')
}

// ── 管道流动动画 ──

let flowAnimationId: number | null = null
let flowOffset = 0

const startFlowAnimation = () => {
  if (!svgMainGroup || !props.runtime) return

  const animate = () => {
    flowOffset += 0.8
    const pipes = svgMainGroup!.querySelectorAll('.pipe-flow')
    pipes.forEach((pipe) => {
      ;(pipe as SVGElement).setAttribute('stroke-dashoffset', String(-flowOffset))
    })
    flowAnimationId = requestAnimationFrame(animate)
  }

  // 旋转动画（ape-blade 类图元）
  const startRotation = () => {
    const blades = svgMainGroup!.querySelectorAll('.ape-blade')
    blades.forEach((blade) => {
      const parent = blade.parentElement
      if (parent) {
        try {
          const bbox = (parent as unknown as SVGGElement).getBBox()
          const cx = bbox.x + bbox.width / 2
          const cy = bbox.y + bbox.height / 2
          let angle = 0
          const rotate = () => {
            angle += 3
            blade.setAttribute('transform', `rotate(${angle}, ${cx}, ${cy})`)
            requestAnimationFrame(rotate)
          }
          rotate()
        } catch {
          // skip
        }
      }
    })
  }

  animate()
  startRotation()
}

const stopFlowAnimation = () => {
  if (flowAnimationId !== null) {
    cancelAnimationFrame(flowAnimationId)
    flowAnimationId = null
  }
}

// ── 选中对象信息 ──

const getSelectedElement = () => selectedElement

const getSelectedCount = () => selectedSet.size

const getSelectedTransform = () => {
  if (!selectedElement) return { x: 0, y: 0, w: 0, h: 0, scaleX: 1, scaleY: 1, angle: 0, opacity: 1, flipX: false, flipY: false }
  const t = parseTransform(selectedElement)
  const bbox = getTransformedBBox(selectedElement)
  return {
    x: Math.round(t.x),
    y: Math.round(t.y),
    w: Math.round(bbox?.width || 0),
    h: Math.round(bbox?.height || 0),
    scaleX: t.scaleX,
    scaleY: t.scaleY,
    angle: t.angle,
    opacity: parseFloat(selectedElement.getAttribute('opacity') || '1'),
    flipX: t.scaleX < 0,
    flipY: t.scaleY < 0
  }
}

const setSelectedTransform = (prop: string, value: any) => {
  const els = getSelectedElements()
  if (els.length === 0) return
  if (prop === 'opacity') {
    for (const el of els) el.setAttribute('opacity', String(value))
    return
  }
  // 以下为单主元素属性（多选时仅作用于主元素）
  if (!selectedElement) return
  const t = parseTransform(selectedElement)
  if (prop === 'left' || prop === 'top') {
    if (prop === 'left') t.x = value
    if (prop === 'top') t.y = value
    setElTransform(selectedElement, t)
  } else if (prop === 'angle') {
    setElTransform(selectedElement, { ...t, angle: value })
  } else if (prop === 'width' || prop === 'height') {
    const bbox = getTransformedBBox(selectedElement)
    if (!bbox || bbox.width === 0 || bbox.height === 0) return
    if (prop === 'width') {
      const target = Math.abs(value)
      const sign = t.scaleX < 0 ? -1 : 1
      t.scaleX = (target / bbox.width) * Math.abs(t.scaleX) * sign
    } else {
      const target = Math.abs(value)
      const sign = t.scaleY < 0 ? -1 : 1
      t.scaleY = (target / bbox.height) * Math.abs(t.scaleY) * sign
    }
    setElTransform(selectedElement, t)
  } else if (prop === 'flipX' || prop === 'flipY') {
    const bbox = getTransformedBBox(selectedElement)
    if (!bbox) return
    if (prop === 'flipX') t.scaleX = -Math.abs(t.scaleX)
    else t.scaleY = -Math.abs(t.scaleY)
    // 镜像时保持左上角锚点不变：翻转后 bbox 会越界，用 translate 补偿
    setElTransform(selectedElement, t)
    const after = getTransformedBBox(selectedElement)
    if (after && bbox) {
      const fix = parseTransform(selectedElement)
      if (prop === 'flipX') fix.x += bbox.x - after.x
      else fix.y += bbox.y - after.y
      setElTransform(selectedElement, fix)
    }
  }
  updateSelectionBox()
}

// ── 外观属性（批量应用于选中图元内部图形元素） ──

const SHAPE_SELECTOR = 'rect,circle,ellipse,path,polyline,polygon,line,text'

const applyShapeStyle = (prop: 'fill' | 'stroke' | 'stroke-width' | 'rx' | 'font-size', value: string) => {
  const els = getSelectedElements()
  if (els.length === 0) return
  for (const el of els) {
    el.querySelectorAll(SHAPE_SELECTOR).forEach((child) => {
      const c = child as SVGElement
      if (prop === 'fill' && (c.getAttribute('fill') === 'none' || c.getAttribute('fill') === null)) return
      if (prop === 'stroke' && (c.getAttribute('stroke') === 'none' || c.getAttribute('stroke') === null)) return
      if (prop === 'stroke-width' && !c.getAttribute('stroke')) return
      if (prop === 'rx' && c.tagName !== 'rect') return
      if (prop === 'font-size' && c.tagName !== 'text') return
      c.setAttribute(prop, value)
    })
  }
  snapshot()
  emit('canvas:changed')
}

/** 获取图元当前外观摘要（主元素） */
const getShapeStyle = (prop: 'fill' | 'stroke' | 'stroke-width' | 'font-size') => {
  if (!selectedElement) return ''
  const el = selectedElement.querySelector(SHAPE_SELECTOR) as SVGElement | null
  if (!el) return ''
  if (prop === 'fill') {
    const e = selectedElement.querySelector('rect:not([fill="none"]), circle:not([fill="none"]), path:not([fill="none"]), text') as SVGElement | null
    return e?.getAttribute('fill') || ''
  }
  return el.getAttribute(prop) || ''
}

/** 编辑第一个文本元素内容（未绑定时） */
const setFirstTextContent = (text: string) => {
  if (!selectedElement) return
  const textEl = selectedElement.querySelector('text') as SVGElement | null
  if (!textEl) return
  textEl.textContent = text
  snapshot()
  emit('canvas:changed')
}

/** 设置图元名称（GaugeSettings.name） */
const setGaugeName = (elementId: string, name: string) => {
  const gauge = itemsState[elementId]
  if (!gauge) return
  gauge.name = name
  snapshot()
  emit('canvas:changed')
}

/** 获取图元名称（GaugeSettings.name） */
const getGaugeName = (elementId: string): string => {
  return itemsState[elementId]?.name || ''
}

// ── 序列化（v2 格式） ──

/**
 * 导出为 JSON 格式（v2：svgcontent + items 字典）
 * 与 hmi.ts View / config_json 结构一致
 */
const toJSON = (): object => {
  return {
    version: 2,
    type: 'svg',
    svgcontent: toSVGString(),
    items: cloneItems(itemsState),
    profile: {
      width: props.width,
      height: props.height,
      bkcolor: props.background,
      gridType: 'fixed' as const,
      gridSize: 0,
      viewRenderDelay: 0
    }
  }
}

/** 从 JSON 加载（v2：svgcontent + items） */
const loadFromJSON = async (json: any): Promise<void> => {
  if (!svgMainGroup) return

  // v2 格式：svgcontent + items
  if (json && json.svgcontent) {
    itemsState = {}
    signalIndex = null
    resetTrendCharts()
    await loadFromSVG(json.svgcontent)
    itemsState = cloneItems(json.items || {})
    signalIndex = buildSignalIndex(itemsState)
    applyStaticValues(
      {
        svgRoot: svgMainGroup,
        items: itemsState,
        index: signalIndex
      } as RuntimeContext,
      trendHandler
    )
    bindInteractions()
    return
  }

  // 兼容旧版：纯 SVG 字符串
  if (typeof json === 'string') {
    itemsState = {}
    signalIndex = null
    return loadFromSVG(json)
  }

  // 其他格式（旧版 Fabric JSON）：画布空白，重建
  itemsState = {}
  signalIndex = null
  svgMainGroup.innerHTML = ''
  snapshot()
}

// ── 生命周期 ──

onMounted(() => {
  initSvgCanvas()
  watch(
    () => props.gridSize,
    () => renderGrid(),
    { flush: 'post' }
  )
})

onUnmounted(() => {
  stopFlowAnimation()
  cleanupInteractions()
  if (svgRoot) {
    svgRoot.remove()
    svgRoot = null
    svgMainGroup = null
  }
  undoStack = []
  redoStack = []
})

// ── 导出方法 ──

defineExpose({
  loadFromSVG,
  loadFromJSON,
  toJSON,
  toSVGString,
  toSVGDocument,
  addWidgetSVG,
  deleteSelected,
  clear,
  setZoom,
  getZoom,
  zoomFit,
  zoomReset,
  undo,
  redo,
  canUndo,
  canRedo,
  bringForward,
  sendBackward,
  bringToFront,
  sendToBack,
  lockSelected,
  unlockSelected,
  isLocked,
  copySelected,
  startFlowAnimation,
  stopFlowAnimation,
  getSelectedElement,
  getSelectedCount,
  getSelectedTransform,
  setSelectedTransform,
  applyShapeStyle,
  getShapeStyle,
  setFirstTextContent,
  setGaugeName,
  getGaugeName,
  alignSelected,
  distributeSelected,
  setBindingDef,
  getBindingDefs,
  getGaugeSettings,
  setGaugeEvents,
  getGaugeEvents,
  initRuntime,
  applySignalValueToCanvas,
  getBoundSignals,
  loadTrendData,
  getTrendTargets,
  deselectAll
})
</script>

<template>
  <div
    ref="svgContainer"
    class="svg-canvas-container"
    :style="{
      width: width + 'px',
      height: height + 'px',
      background: background
    }"
  />
</template>

<style scoped>
.svg-canvas-container {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.svg-canvas-container :deep(svg) {
  display: block;
}

.svg-canvas-container :deep(.svg-selected) {
  outline: 2px solid #3a8fd4;
  outline-offset: 2px;
}

.svg-canvas-container :deep(.resize-handle) {
  transition: fill 0.15s;
}
.svg-canvas-container :deep(.resize-handle:hover) {
  fill: #5ab0ff;
}
</style>
