<script setup lang="ts">
/**
 * SvgCanvas v3 — 完全照搬 FUXA/SVG-Edit 架构
 *
 * 核心：
 * - 画布 = SVG 文档，图元 = SVG DOM 元素（`<g>` 嵌套 SVG 子元素）
 * - SVG.js 仅用于运行时 adopt/attr 操作，编辑器核心交互自研
 * - 选中框/缩放句柄/旋转手柄参照 SVG-Edit selector.js
 * - 存储格式：SVG 字符串 + items 字典（FUXA 双层存储）
 *
 * 编辑模式：点击选中 | 拖拽移动 | 缩放句柄调整 | 旋转手柄 | 橡皮筋多选 | Delete删除 | Ctrl+Z/Y撤销重做
 * 运行模式：innerHTML注入SVG → SVG.adopt → processValue链路
 */

import { ref, onMounted, onUnmounted, watch } from 'vue'
import { SVG } from '@svgdotjs/svg.js'
import type { View } from './hmi'
import { genId, createGaugeSettings, defaultProfile } from './hmi'
import {
  scanAndBindFromDOM,
  handleSignal,
  bindGaugeEvents,
  cleanupAll,
  clearAllSignalMappings
} from './gauges-manager'

// ── Props & Emits ──

const props = withDefaults(
  defineProps<{
    width?: number
    height?: number
    background?: string
    runtime?: boolean
    gridSize?: number
  }>(),
  {
    width: 1920,
    height: 1080,
    background: '#1a1a2e',
    runtime: false,
    gridSize: 20
  }
)

const emit = defineEmits<{
  (e: 'object:selected', obj: SVGElement | null): void
  (e: 'object:deselected'): void
  (e: 'canvas:changed'): void
  (e: 'ready'): void
}>()

// ── 核心状态 ──

const svgContainer = ref<HTMLElement>()
let svgDraw: any = null // SVG.js 画布实例
let svgRoot: SVGSVGElement | null = null
let svgMainGroup: SVGGElement | null = null
let selectorGroup: SVGGElement | null = null
let gridGroup: SVGGElement | null = null

// ── View 数据（FUXA 双层存储） ──

let viewData: View = {
  id: genId('v'),
  name: '',
  profile: defaultProfile(),
  svgcontent: '',
  items: {},
  type: 'svg'
}

// ── 选中状态 ──

let selectedElement: SVGElement | null = null
let selectedElements: SVGElement[] = []

// ── 拖拽状态 ──

let isDragging = false
let dragStartX = 0
let dragStartY = 0
let dragElementStartX = 0
let dragElementStartY = 0

// ── 缩放句柄状态 ──

let isResizing = false
let resizeHandleDir = ''
let resizeStartX = 0
let resizeStartY = 0
let resizeStartBox = { x: 0, y: 0, w: 0, h: 0 }

// ── 旋转状态 ──

let isRotating = false
let rotateStartAngle = 0
let rotateElementStartAngle = 0

// ── 橡皮筋选择 ──

let isRubberBand = false
let rubberBandRect: SVGRectElement | null = null
let rubberBandStartX = 0
let rubberBandStartY = 0
let rubberBandEndX = 0
let rubberBandEndY = 0

// ── 平移状态 ──

let isPanning = false
let panStartX = 0
let panStartY = 0
let panStartOffsetX = 0
let panStartOffsetY = 0
let panOffset = { x: 0, y: 0 }

// ── 缩放 ──

const zoomLevel = ref(1)

// ── 撤销/重做 ──

let undoStack: any[] = []
let redoStack: any[] = []
const canUndoState = ref(false)
const canRedoState = ref(false)

// ══════════════════════════════════
// 辅助函数
// ══════════════════════════════════

function getBBox(el: SVGElement): DOMRect {
  try {
    return (el as SVGGElement).getBBox()
  } catch {
    return new DOMRect(0, 0, 0, 0)
  }
}

function getTranslate(el: SVGElement): { x: number; y: number } {
  const t = el.getAttribute('transform') || ''
  const m = t.match(/translate\(([-\d.]+),\s*([-\d.]+)\)/)
  if (m) return { x: parseFloat(m[1]), y: parseFloat(m[2]) }
  return { x: 0, y: 0 }
}

function setTranslate(el: SVGElement, x: number, y: number): void {
  const t = el.getAttribute('transform') || ''
  const rest = t.replace(/translate\([^)]+\)/, '').trim()
  el.setAttribute('transform', `translate(${x}, ${y})${rest ? ' ' + rest : ''}`)
}

function setTranslateRotate(el: SVGElement, x: number, y: number, angle: number | undefined): void {
  const parts: string[] = [`translate(${x}, ${y})`]
  if (angle !== undefined && angle !== 0) parts.push(`rotate(${angle})`)
  el.setAttribute('transform', parts.join(' '))
}

function getRotation(el: SVGElement): number {
  const t = el.getAttribute('transform') || ''
  const m = t.match(/rotate\(([-\d.]+)/)
  return m ? parseFloat(m[1]) : 0
}

function snapToGrid(val: number): number {
  const gs = props.gridSize
  return gs > 0 ? Math.round(val / gs) * gs : val
}

function clientToSvg(clientX: number, clientY: number): { x: number; y: number } {
  const svg = svgRoot
  if (!svg) return { x: 0, y: 0 }
  const pt = svg.createSVGPoint()
  pt.x = clientX
  pt.y = clientY
  const ctm = svg.getScreenCTM()
  if (!ctm) return { x: 0, y: 0 }
  const svgPt = pt.matrixTransform(ctm.inverse())
  return { x: svgPt.x - panOffset.x, y: svgPt.y - panOffset.y }
}

// ══════════════════════════════════
// SVG 画布初始化
// ══════════════════════════════════

function initSvgCanvas(): void {
  if (!svgContainer.value) return

  svgDraw = SVG().size(props.width, props.height)
  svgRoot = svgDraw.node as SVGSVGElement
  svgContainer.value.appendChild(svgRoot)

  // 设置 SVG 属性
  svgRoot.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  svgRoot.setAttribute('width', '100%')
  svgRoot.setAttribute('height', '100%')
  svgRoot.style.background = props.background

  // 背景矩形
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
  bg.setAttribute('width', String(props.width))
  bg.setAttribute('height', String(props.height))
  bg.setAttribute('fill', props.background)
  bg.setAttribute('data-bg', 'true')
  bg.id = 'svg-background'

  // 网格组
  gridGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g')
  gridGroup.id = 'svg-grid-group'

  // 主内容组
  svgMainGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g')
  svgMainGroup.id = 'svg-main-group'

  // 选择框组
  selectorGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g')
  selectorGroup.id = 'svg-selector-group'

  svgRoot.appendChild(bg)
  svgRoot.appendChild(gridGroup)
  svgRoot.appendChild(svgMainGroup)
  svgRoot.appendChild(selectorGroup)

  drawGrid()

  // 绑定编辑模式事件
  if (!props.runtime) {
    svgRoot.addEventListener('mousedown', onMouseDown)
    svgRoot.addEventListener('mousemove', onMouseMove)
    svgRoot.addEventListener('mouseup', onMouseUp)
    svgRoot.addEventListener('wheel', onWheel, { passive: false })
    document.addEventListener('keydown', onKeyDown)
  }

  emit('ready')
}

// ── 网格 ──

function drawGrid(): void {
  if (!gridGroup || !svgRoot) return
  gridGroup.innerHTML = ''
  if (props.gridSize <= 0) return

  const gs = props.gridSize
  const w = props.width
  const h = props.height

  for (let x = gs; x < w; x += gs) {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line')
    line.setAttribute('x1', String(x))
    line.setAttribute('y1', '0')
    line.setAttribute('x2', String(x))
    line.setAttribute('y2', String(h))
    line.setAttribute('stroke', '#ffffff')
    line.setAttribute('stroke-opacity', '0.06')
    gridGroup.appendChild(line)
  }
  for (let y = gs; y < h; y += gs) {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line')
    line.setAttribute('x1', '0')
    line.setAttribute('y1', String(y))
    line.setAttribute('x2', String(w))
    line.setAttribute('y2', String(y))
    line.setAttribute('stroke', '#ffffff')
    line.setAttribute('stroke-opacity', '0.06')
    gridGroup.appendChild(line)
  }
}

// ── 变换（平移 + 缩放） ──

function applyTransform(): void {
  if (!svgMainGroup || !selectorGroup || !gridGroup) return
  const t = `translate(${panOffset.x}, ${panOffset.y}) scale(${zoomLevel.value})`
  svgMainGroup.setAttribute('transform', t)
  selectorGroup.setAttribute('transform', t)
  gridGroup.setAttribute(
    'transform',
    `translate(${panOffset.x}, ${panOffset.y}) scale(${zoomLevel.value})`
  )
}

// ══════════════════════════════════
// 选中框（参照 SVG-Edit selector.js）
// ══════════════════════════════════

function clearSelection(): void {
  if (selectorGroup) selectorGroup.innerHTML = ''
  selectedElement = null
  selectedElements = []
}

function drawSelectionBox(el: SVGElement | null): void {
  if (!selectorGroup || !el) return
  selectorGroup.innerHTML = ''

  const bbox = getBBox(el)
  const t = getTranslate(el)
  const x = t.x + bbox.x
  const y = t.y + bbox.y
  const w = bbox.width
  const h = bbox.height
  const pad = 4

  // 选中框边框
  const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
  rect.setAttribute('x', String(x - pad))
  rect.setAttribute('y', String(y - pad))
  rect.setAttribute('width', String(w + pad * 2))
  rect.setAttribute('height', String(h + pad * 2))
  rect.setAttribute('fill', 'none')
  rect.setAttribute('stroke', '#4a9eff')
  rect.setAttribute('stroke-width', '1.5')
  rect.setAttribute('stroke-dasharray', '4,2')
  rect.setAttribute('pointer-events', 'none')
  selectorGroup.appendChild(rect)

  // 8 个缩放句柄
  const handles = [
    { dir: 'nw', hx: x - pad, hy: y - pad },
    { dir: 'n', hx: x + w / 2, hy: y - pad },
    { dir: 'ne', hx: x + w + pad, hy: y - pad },
    { dir: 'e', hx: x + w + pad, hy: y + h / 2 },
    { dir: 'se', hx: x + w + pad, hy: y + h + pad },
    { dir: 's', hx: x + w / 2, hy: y + h + pad },
    { dir: 'sw', hx: x - pad, hy: y + h + pad },
    { dir: 'w', hx: x - pad, hy: y + h / 2 }
  ]
  for (const h of handles) {
    const handle = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
    handle.setAttribute('x', String(h.hx - 4))
    handle.setAttribute('y', String(h.hy - 4))
    handle.setAttribute('width', '8')
    handle.setAttribute('height', '8')
    handle.setAttribute('fill', '#4a9eff')
    handle.setAttribute('stroke', '#2563eb')
    handle.setAttribute('rx', '1')
    handle.setAttribute('data-resize', h.dir)
    handle.style.cursor = `${h.dir}-resize`
    selectorGroup.appendChild(handle)
  }

  // 旋转手柄
  const rotY = y - pad - 24
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'line')
  line.setAttribute('x1', String(x + w / 2))
  line.setAttribute('y1', String(y - pad))
  line.setAttribute('x2', String(x + w / 2))
  line.setAttribute('y2', String(rotY))
  line.setAttribute('stroke', '#4a9eff')
  line.setAttribute('stroke-width', '1')
  line.setAttribute('pointer-events', 'none')
  selectorGroup.appendChild(line)

  const rotHandle = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
  rotHandle.setAttribute('cx', String(x + w / 2))
  rotHandle.setAttribute('cy', String(rotY))
  rotHandle.setAttribute('r', '5')
  rotHandle.setAttribute('fill', '#4a9eff')
  rotHandle.setAttribute('stroke', '#2563eb')
  rotHandle.setAttribute('data-rotate', 'true')
  rotHandle.style.cursor = 'crosshair'
  selectorGroup.appendChild(rotHandle)
}

// ══════════════════════════════════
// 鼠标事件
// ══════════════════════════════════

function onMouseDown(e: MouseEvent): void {
  if (!svgMainGroup || !svgRoot) return
  const pos = clientToSvg(e.clientX, e.clientY)
  const target = (e.target as HTMLElement).closest(
    'svg, g, rect, circle, line, text, path, ellipse, image, polygon, polyline'
  )

  // 右键忽略
  if (e.button === 2) return

  // 检查是否点击了缩放句柄
  const resizeDir = (e.target as SVGElement).getAttribute('data-resize')
  if (resizeDir && selectedElement) {
    isResizing = true
    resizeHandleDir = resizeDir
    resizeStartX = pos.x
    resizeStartY = pos.y
    const bbox = getBBox(selectedElement)
    const t = getTranslate(selectedElement)
    resizeStartBox = { x: t.x + bbox.x, y: t.y + bbox.y, w: bbox.width, h: bbox.height }
    e.preventDefault()
    return
  }

  // 检查是否点击了旋转手柄
  if ((e.target as SVGElement).getAttribute('data-rotate') === 'true' && selectedElement) {
    isRotating = true
    const bbox = getBBox(selectedElement)
    const t = getTranslate(selectedElement)
    const cx = t.x + bbox.x + bbox.width / 2
    const cy = t.y + bbox.y + bbox.height / 2
    rotateStartAngle = Math.atan2(pos.y - cy, pos.x - cx)
    rotateElementStartAngle = getRotation(selectedElement)
    e.preventDefault()
    return
  }

  // Alt+左键或中键平移
  if (e.altKey || e.button === 1) {
    isPanning = true
    panStartX = e.clientX
    panStartY = e.clientY
    panStartOffsetX = panOffset.x
    panStartOffsetY = panOffset.y
    e.preventDefault()
    return
  }

  // 检查点击的元素是否在主内容组中
  const isMainGroupChild = target && target.closest && target.closest('#svg-main-group')

  if (
    isMainGroupChild &&
    target !== svgMainGroup &&
    !(target as SVGElement).hasAttribute('data-bg')
  ) {
    // 选中图元 — 找到最近的带 id 的子元素
    let targetEl = target as SVGElement
    while (targetEl && targetEl !== svgMainGroup && !targetEl.getAttribute('id')) {
      targetEl = targetEl.parentElement as unknown as SVGElement
    }

    if (targetEl && targetEl !== svgMainGroup) {
      // Shift 多选
      if (e.shiftKey && selectedElement) {
        if (!selectedElements.includes(targetEl)) {
          selectedElements.push(targetEl)
        }
      } else {
        selectedElement = targetEl
        selectedElements = [targetEl]
      }

      drawSelectionBox(selectedElement)
      emit('object:selected', selectedElement)

      // 准备拖拽
      isDragging = true
      dragStartX = pos.x
      dragStartY = pos.y
      const t = getTranslate(selectedElement)
      dragElementStartX = t.x
      dragElementStartY = t.y

      e.preventDefault()
      return
    }
  }

  // 点击空白 → 取消选中 + 启动橡皮筋选择
  if (
    target === svgMainGroup ||
    (target as SVGElement).hasAttribute('data-bg') ||
    target === svgRoot
  ) {
    if (!e.shiftKey) {
      clearSelection()
      emit('object:deselected')
    }

    // 启动橡皮筋选择
    isRubberBand = true
    rubberBandStartX = pos.x
    rubberBandStartY = pos.y
    rubberBandEndX = pos.x
    rubberBandEndY = pos.y

    rubberBandRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
    rubberBandRect.setAttribute('fill', 'rgba(74,158,255,0.15)')
    rubberBandRect.setAttribute('stroke', '#4a9eff')
    rubberBandRect.setAttribute('stroke-width', '1')
    rubberBandRect.setAttribute('stroke-dasharray', '4,2')
    rubberBandRect.setAttribute('x', String(pos.x))
    rubberBandRect.setAttribute('y', String(pos.y))
    rubberBandRect.setAttribute('width', '0')
    rubberBandRect.setAttribute('height', '0')
    if (selectorGroup) selectorGroup.appendChild(rubberBandRect)
  }
}

function onMouseMove(e: MouseEvent): void {
  if (!svgMainGroup) return
  const pos = clientToSvg(e.clientX, e.clientY)

  // 拖拽移动
  if (isDragging && selectedElement) {
    const dx = pos.x - dragStartX
    const dy = pos.y - dragStartY
    const newX = snapToGrid(dragElementStartX + dx)
    const newY = snapToGrid(dragElementStartY + dy)
    const rot = getRotation(selectedElement)
    setTranslateRotate(selectedElement, newX, newY, rot || undefined)
    drawSelectionBox(selectedElement)
    return
  }

  // 缩放句柄拖拽
  if (isResizing && selectedElement) {
    const dx = pos.x - resizeStartX
    const dy = pos.y - resizeStartY
    let { x, y, w, h } = resizeStartBox

    if (resizeHandleDir.includes('w')) {
      x += dx
      w -= dx
    }
    if (resizeHandleDir.includes('e')) {
      w += dx
    }
    if (resizeHandleDir.includes('n')) {
      y += dy
      h -= dy
    }
    if (resizeHandleDir.includes('s')) {
      h += dy
    }

    if (w < 10) w = 10
    if (h < 10) h = 10

    setTranslate(selectedElement, x, y)
    drawSelectionBox(selectedElement)
    return
  }

  // 旋转手柄拖拽
  if (isRotating && selectedElement) {
    const cx = resizeStartBox.x + resizeStartBox.w / 2
    const cy = resizeStartBox.y + resizeStartBox.h / 2
    const angle = Math.atan2(pos.y - cy, pos.x - cx)
    const delta = (angle - rotateStartAngle) * (180 / Math.PI)
    const newAngle = Math.round(rotateElementStartAngle + delta)
    const snappedAngle = Math.round(newAngle / 5) * 5
    const t = getTranslate(selectedElement)
    setTranslateRotate(selectedElement, t.x, t.y, snappedAngle)
    drawSelectionBox(selectedElement)
    return
  }

  // 橡皮筋选择
  if (isRubberBand && rubberBandRect) {
    rubberBandEndX = pos.x
    rubberBandEndY = pos.y
    const x = Math.min(rubberBandStartX, pos.x)
    const y = Math.min(rubberBandStartY, pos.y)
    const w = Math.abs(pos.x - rubberBandStartX)
    const h = Math.abs(pos.y - rubberBandStartY)
    rubberBandRect.setAttribute('x', String(x))
    rubberBandRect.setAttribute('y', String(y))
    rubberBandRect.setAttribute('width', String(w))
    rubberBandRect.setAttribute('height', String(h))
    return
  }

  // 平移
  if (isPanning) {
    const dx = (e.clientX - panStartX) / zoomLevel.value
    const dy = (e.clientY - panStartY) / zoomLevel.value
    panOffset = { x: panStartOffsetX + dx, y: panStartOffsetY + dy }
    applyTransform()
  }
}

function onMouseUp(_e: MouseEvent): void {
  // 结束拖拽
  if (isDragging) {
    isDragging = false
    if (selectedElement) {
      pushUndo({
        type: 'transform',
        id: selectedElement.getAttribute('id'),
        transform: selectedElement.getAttribute('transform')
      })
    }
    emit('canvas:changed')
  }

  // 结束缩放
  if (isResizing) {
    isResizing = false
    resizeHandleDir = ''
    if (selectedElement) {
      pushUndo({
        type: 'transform',
        id: selectedElement.getAttribute('id'),
        transform: selectedElement.getAttribute('transform')
      })
    }
    emit('canvas:changed')
  }

  // 结束旋转
  if (isRotating) {
    isRotating = false
    if (selectedElement) {
      pushUndo({
        type: 'transform',
        id: selectedElement.getAttribute('id'),
        transform: selectedElement.getAttribute('transform')
      })
    }
    emit('canvas:changed')
  }

  // 结束橡皮筋选择
  if (isRubberBand) {
    isRubberBand = false
    const rbX = Math.min(rubberBandStartX, rubberBandEndX)
    const rbY = Math.min(rubberBandStartY, rubberBandEndY)
    const rbW = Math.abs(rubberBandEndX - rubberBandStartX)
    const rbH = Math.abs(rubberBandEndY - rubberBandStartY)

    if (rubberBandRect) {
      rubberBandRect.remove()
      rubberBandRect = null
    }

    // 只在框面积足够大时执行多选
    if (rbW > 5 && rbH > 5 && svgMainGroup) {
      const selected: SVGElement[] = []
      const children = svgMainGroup.children
      for (let i = 0; i < children.length; i++) {
        const child = children[i] as SVGElement
        if (!child.getAttribute('id')) continue
        try {
          const bbox = getBBox(child)
          const t = getTranslate(child)
          const cx = t.x + bbox.x + bbox.width / 2
          const cy = t.y + bbox.y + bbox.height / 2
          if (cx >= rbX && cx <= rbX + rbW && cy >= rbY && cy <= rbY + rbH) {
            selected.push(child)
          }
        } catch {
          /* ignore */
        }
      }

      if (selected.length > 0) {
        selectedElements = selected
        selectedElement = selected[0]
        drawSelectionBox(selectedElement)
        emit('object:selected', selectedElement)
      }
    }
  }

  isPanning = false
}

// ── 滚轮缩放 ──

function onWheel(e: WheelEvent): void {
  e.preventDefault()
  const delta = e.deltaY > 0 ? -0.1 : 0.1
  const newZoom = Math.max(0.1, Math.min(5, zoomLevel.value + delta))
  zoomLevel.value = Math.round(newZoom * 100) / 100
  applyTransform()
}

// ── 键盘快捷键 ──

function onKeyDown(e: KeyboardEvent): void {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
  if (!selectedElement) return

  const step = e.shiftKey ? 10 : 1
  const t = getTranslate(selectedElement)

  switch (e.key) {
    case 'Delete':
    case 'Backspace':
      deleteSelected()
      break
    case 'ArrowUp':
      e.preventDefault()
      setTranslate(selectedElement, t.x, t.y - step)
      drawSelectionBox(selectedElement)
      emit('canvas:changed')
      break
    case 'ArrowDown':
      e.preventDefault()
      setTranslate(selectedElement, t.x, t.y + step)
      drawSelectionBox(selectedElement)
      emit('canvas:changed')
      break
    case 'ArrowLeft':
      e.preventDefault()
      setTranslate(selectedElement, t.x - step, t.y)
      drawSelectionBox(selectedElement)
      emit('canvas:changed')
      break
    case 'ArrowRight':
      e.preventDefault()
      setTranslate(selectedElement, t.x + step, t.y)
      drawSelectionBox(selectedElement)
      emit('canvas:changed')
      break
    case 'z':
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault()
        undo()
      }
      break
    case 'y':
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault()
        redo()
      }
      break
  }
}

// ══════════════════════════════════
// 撤销/重做
// ══════════════════════════════════

function snapshot(): void {
  undoStack.push(getSvgContent())
  redoStack = []
  if (undoStack.length > 50) undoStack.shift()
  refreshUndoRedoState()
}

function pushUndo(cmd: any): void {
  undoStack.push(cmd)
  redoStack = []
  if (undoStack.length > 50) undoStack.shift()
  refreshUndoRedoState()
}

function undo(): void {
  if (undoStack.length === 0) return
  redoStack.push(undoStack.pop())
  refreshUndoRedoState()
  emit('canvas:changed')
}

function redo(): void {
  if (redoStack.length === 0) return
  undoStack.push(redoStack.pop())
  refreshUndoRedoState()
  emit('canvas:changed')
}

function canUndo(): boolean {
  return undoStack.length > 0
}
function canRedo(): boolean {
  return redoStack.length > 0
}

function refreshUndoRedoState(): void {
  canUndoState.value = canUndo()
  canRedoState.value = canRedo()
}

// ══════════════════════════════════
// 公共 API（供 ScadaEditor/ScadaViewer 调用）
// ══════════════════════════════════

/** 添加图元 SVG 片段到画布 */
const addWidgetSVG = (svgFragment: string, x: number, y: number): void => {
  if (!svgMainGroup) return
  const temp = document.createElement('div')
  temp.innerHTML = svgFragment

  const svgEl = temp.querySelector('svg') || temp.querySelector('g')
  if (!svgEl) return

  // 如果没有 id，自动生成
  if (!svgEl.getAttribute('id')) {
    svgEl.setAttribute('id', genId('svg'))
  }

  // 设置位置
  setTranslate(svgEl as SVGElement, x, y)
  svgMainGroup.appendChild(document.importNode(svgEl, true))

  // 创建对应的 GaugeSettings（照搬 FUXA onElementAdded）
  const elId = svgEl.getAttribute('id')!
  const elType = svgEl.getAttribute('type') || 'svg-ext-shapes'
  if (!viewData.items[elId]) {
    viewData.items[elId] = createGaugeSettings(elId, elType)
  }

  snapshot()
  emit('canvas:changed')
}

/** 删除选中图元 */
const deleteSelected = (): void => {
  if (!selectedElement || !svgMainGroup) return
  const id = selectedElement.getAttribute('id')
  if (id) delete viewData.items[id]

  selectedElement.remove()
  clearSelection()
  emit('object:deselected')
  snapshot()
  emit('canvas:changed')
}

/** 清空画布 */
const clear = (): void => {
  if (!svgMainGroup) return
  svgMainGroup.innerHTML = ''
  viewData.items = {}
  viewData.svgcontent = ''
  clearSelection()
  emit('object:deselected')
  snapshot()
  emit('canvas:changed')
}

/** 获取 SVG 内容字符串 */
const getSvgContent = (): string => {
  if (!svgMainGroup) return ''
  // 克隆主组，去掉选择框等辅助元素
  const clone = svgMainGroup.cloneNode(true) as SVGGElement
  return clone.innerHTML
}

/** 加载 SVG 字符串 */
const loadFromSVG = (svgContent: string): Promise<void> => {
  if (!svgMainGroup) return Promise.resolve()

  return new Promise((resolve) => {
    if (svgMainGroup) svgMainGroup.innerHTML = ''
    const temp = document.createElement('div')
    temp.innerHTML = svgContent

    const svgEl = temp.querySelector('svg')
    const source = svgEl || temp

    Array.from(source.children).forEach((child) => {
      if (
        child instanceof SVGElement &&
        child.tagName !== 'defs' &&
        !child.hasAttribute('data-bg')
      ) {
        svgMainGroup!.appendChild(document.importNode(child, true))
      }
    })

    // 重建 items 字典（从 SVG DOM 中扫描已有 id/type 的元素）
    rebuildItemsFromDOM()

    snapshot()
    resolve()
  })
}

/** 从 SVG DOM 重建 items 字典 */
function rebuildItemsFromDOM(): void {
  if (!svgMainGroup) return
  const elements = svgMainGroup.querySelectorAll('[id][type]')
  elements.forEach((el) => {
    const svgEl = el as SVGElement
    const id = svgEl.getAttribute('id')!
    const type = svgEl.getAttribute('type') || 'svg-ext-shapes'
    if (!viewData.items[id]) {
      viewData.items[id] = createGaugeSettings(id, type)
    }
  })
}

/** 加载后端 JSON 配置 */
const loadFromJSON = async (json: any): Promise<void> => {
  if (!svgMainGroup) return

  // 新版 FUXA 格式：{ svgcontent, items, profile }
  if (json && json.svgcontent !== undefined) {
    viewData.items = json.items || {}
    return loadFromSVG(json.svgcontent)
  }

  // 旧版格式兼容
  if (json && json.objects) {
    // 旧 Fabric 格式 - 生成空 SVG
    viewData.items = {}
    return loadFromSVG('')
  }

  // 纯字符串
  if (typeof json === 'string') {
    return loadFromSVG(json)
  }
}

/** 导出为 JSON（FUXA 双层存储格式） */
const toJSON = (): any => {
  return {
    svgcontent: getSvgContent(),
    items: viewData.items,
    profile: viewData.profile
  }
}

/** 导出 SVG 字符串 */
const toSVGString = (): string => {
  const content = getSvgContent()
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${props.width}" height="${props.height}">\n${content}\n</svg>`
}

/** 获取/设置选中元素 transform */
const setSelectedTransform = (prop: string, value: any): void => {
  if (!selectedElement) return
  const t = getTranslate(selectedElement)
  switch (prop) {
    case 'left':
      setTranslate(selectedElement, value, t.y)
      break
    case 'top':
      setTranslate(selectedElement, t.x, value)
      break
    case 'opacity':
      selectedElement.setAttribute('opacity', String(value))
      break
  }
  drawSelectionBox(selectedElement)
  emit('canvas:changed')
}

const getSelectedTransform = (): { x: number; y: number; opacity: number } | null => {
  if (!selectedElement) return null
  const t = getTranslate(selectedElement)
  const opacity = parseFloat(selectedElement.getAttribute('opacity') || '1')
  return { x: t.x, y: t.y, opacity }
}

/** 设置数据绑定（照搬 FUXA setGaugeSettings） */
const setBinding = (
  elementId: string,
  target: string,
  deviceId: number,
  tagId: number,
  tagName: string,
  prop: string
): void => {
  let ga = viewData.items[elementId]
  if (!ga) {
    ga = createGaugeSettings(elementId, 'svg-ext-shapes')
    viewData.items[elementId] = ga
  }
  ga.property.variableId = `${deviceId}:${tagName}`
  // 在 SVG 元素上存储绑定信息（供运行时读取）
  const el = svgMainGroup?.querySelector(`#${CSS.escape(elementId)}`) as SVGElement | null
  if (el) {
    el.setAttribute('data-bind-target', target)
    el.setAttribute('data-bind-device-id', String(deviceId))
    el.setAttribute('data-bind-tag-id', String(tagId))
    el.setAttribute('data-bind-tag-name', tagName)
    el.setAttribute('data-bind-prop', prop)
  }
  snapshot()
  emit('canvas:changed')
}

/** 获取所有绑定信息（供 ScadaViewer 运行时用） */
const getAllBindings = (): Array<{
  elementId: string
  bindTarget: string
  deviceId: number
  tagId: number
  tagName: string
  prop: string
}> => {
  const bindings: any[] = []
  if (!svgMainGroup) return bindings
  const elements = svgMainGroup.querySelectorAll('[data-bind-target]')
  elements.forEach((el) => {
    const svgEl = el as SVGElement
    const target = svgEl.getAttribute('data-bind-target')
    if (!target) return
    bindings.push({
      elementId: svgEl.getAttribute('id') || '',
      bindTarget: target,
      deviceId: parseInt(svgEl.getAttribute('data-bind-device-id') || '0', 10),
      tagId: parseInt(svgEl.getAttribute('data-bind-tag-id') || '0', 10),
      tagName: svgEl.getAttribute('data-bind-tag-name') || '',
      prop: svgEl.getAttribute('data-bind-prop') || 'text'
    })
  })
  return bindings
}

/** 运行时更新绑定值 */
const updateBoundValue = (
  elementId: string,
  _bindTarget: string,
  value: any,
  prop: string
): void => {
  if (!svgMainGroup) return
  const el = svgMainGroup.querySelector(`#${CSS.escape(elementId)}`)
  if (!el) return
  const svgEl = el as SVGElement
  if (prop === 'fill') {
    svgEl.setAttribute('fill', String(value))
  } else if (prop === 'stroke') {
    svgEl.setAttribute('stroke', String(value))
  } else if (prop === 'text') {
    const texts = svgEl.querySelectorAll('text, tspan')
    if (texts.length > 0) {
      texts.forEach((t) => {
        t.textContent = String(value)
      })
    } else if (svgEl.tagName === 'text' || svgEl.tagName === 'tspan') {
      svgEl.textContent = String(value)
    }
  } else if (prop === 'height') {
    svgEl.setAttribute('height', String(Math.max(0, parseFloat(String(value)))))
  } else if (prop === 'transform') {
    svgEl.setAttribute('transform', String(value))
  }
}

// ── 层级操作 ──

const bringForward = (): void => {
  if (!selectedElement || !selectedElement.nextElementSibling || !svgMainGroup) return
  svgMainGroup.insertBefore(selectedElement.nextElementSibling, selectedElement)
  emit('canvas:changed')
}

const sendBackward = (): void => {
  if (!selectedElement || !selectedElement.previousElementSibling || !svgMainGroup) return
  svgMainGroup.insertBefore(selectedElement, selectedElement.previousElementSibling)
  emit('canvas:changed')
}

const bringToFront = (): void => {
  if (!selectedElement || !svgMainGroup) return
  svgMainGroup.appendChild(selectedElement)
  emit('canvas:changed')
}

const sendToBack = (): void => {
  if (!selectedElement || !svgMainGroup || !svgMainGroup.firstElementChild) return
  svgMainGroup.insertBefore(selectedElement, svgMainGroup.firstElementChild)
  emit('canvas:changed')
}

// ── 锁定/解锁 ──

const lockSelected = (): void => {
  if (selectedElement) selectedElement.setAttribute('data-locked', 'true')
}

const unlockSelected = (): void => {
  if (selectedElement) selectedElement.removeAttribute('data-locked')
}

const isLocked = (): boolean => {
  return selectedElement?.getAttribute('data-locked') === 'true'
}

// ── 复制 ──

const copySelected = (): void => {
  if (!selectedElement || !svgMainGroup) return
  const clone = selectedElement.cloneNode(true) as SVGElement
  const newId = genId('svg')
  clone.setAttribute('id', newId)
  const t = getTranslate(selectedElement)
  setTranslate(clone, t.x + 20, t.y + 20)
  svgMainGroup.appendChild(clone)

  // 深拷贝 GaugeSettings（照搬 FUXA onCopyAndPaste）
  if (viewData.items[selectedElement.getAttribute('id')!]) {
    viewData.items[newId] = JSON.parse(
      JSON.stringify(viewData.items[selectedElement.getAttribute('id')!])
    )
    viewData.items[newId].id = newId
  } else {
    viewData.items[newId] = createGaugeSettings(
      newId,
      clone.getAttribute('type') || 'svg-ext-shapes'
    )
  }

  snapshot()
  emit('canvas:changed')
}

// ── 缩放控制 ──

const setZoom = (z: number): void => {
  zoomLevel.value = Math.max(0.1, Math.min(5, z))
  applyTransform()
}

const getZoom = (): number => zoomLevel.value

const zoomFit = (): void => {
  zoomLevel.value = 0.8
  applyTransform()
}

const zoomReset = (): void => {
  zoomLevel.value = 1
  panOffset = { x: 0, y: 0 }
  applyTransform()
}

// ── 运行时方法 ──

const initRuntimeBindings = (): void => {
  if (!svgMainGroup || !props.runtime) return
  const count = scanAndBindFromDOM(svgMainGroup, viewData.items)
  console.log(`[SvgCanvas] 运行时绑定: 扫描到 ${count} 个绑定图元`)

  // 绑定事件（照搬 FUXA loadWatch）
  bindGaugeEvents(svgMainGroup, viewData.items, (action, param, options) => {
    console.log(`[SvgCanvas] 事件触发: ${action} → ${param}`, options)
  })
}

const processRuntimeSignal = (signalId: string, value: any): void => {
  if (!svgMainGroup || !props.runtime) return
  handleSignal(signalId, value, svgMainGroup)
}

// ── 管道动画 ──

let flowAnimationId: number | null = null
let flowOffset = 0

const startFlowAnimation = (): void => {
  if (!svgMainGroup || !props.runtime) return
  const animate = () => {
    flowOffset += 0.8
    if (svgMainGroup) {
      const pipes = svgMainGroup.querySelectorAll('.pipe-flow')
      pipes.forEach((pipe) => {
        ;(pipe as SVGElement).setAttribute('stroke-dashoffset', String(-flowOffset))
      })
    }
    flowAnimationId = requestAnimationFrame(animate)
  }
  animate()
}

const stopFlowAnimation = (): void => {
  if (flowAnimationId) {
    cancelAnimationFrame(flowAnimationId)
    flowAnimationId = null
  }
}

// ── 获取 View 数据 ──

const getViewData = (): View => viewData

const setViewData = (view: View): void => {
  viewData = view
}

// ══════════════════════════════════
// 生命周期
// ══════════════════════════════════

onMounted(() => {
  initSvgCanvas()
  if (props.runtime) {
    startFlowAnimation()
  }
})

onUnmounted(() => {
  stopFlowAnimation()
  cleanupAll()
  clearAllSignalMappings()
  if (svgRoot) {
    svgRoot.remove()
    svgRoot = null
    svgMainGroup = null
  }
  undoStack = []
  redoStack = []
  if (!props.runtime) {
    document.removeEventListener('keydown', onKeyDown)
  }
})

// ── 监听 props 变化 ──

watch(
  () => props.gridSize,
  () => {
    if (gridGroup) gridGroup.innerHTML = ''
    drawGrid()
  }
)

watch(
  () => props.background,
  (newBg) => {
    if (svgRoot) svgRoot.style.background = newBg
    const bg = svgRoot?.querySelector('[data-bg]')
    if (bg) bg.setAttribute('fill', newBg)
  }
)

// ── 导出方法 ──

defineExpose({
  // 数据
  loadFromSVG,
  loadFromJSON,
  toJSON,
  toSVGString,
  getSvgContent,
  getViewData,
  setViewData,
  // 图元操作
  addWidgetSVG,
  deleteSelected,
  clear,
  // 选中/变换
  setSelectedTransform,
  getSelectedTransform,
  setBinding,
  lockSelected,
  unlockSelected,
  isLocked,
  // 层级
  bringForward,
  sendBackward,
  bringToFront,
  sendToBack,
  // 复制
  copySelected,
  // 缩放
  setZoom,
  getZoom,
  zoomFit,
  zoomReset,
  // 撤销/重做
  undo,
  redo,
  canUndo,
  canRedo,
  // 运行时
  initRuntimeBindings,
  processRuntimeSignal,
  getAllBindings,
  updateBoundValue,
  startFlowAnimation,
  stopFlowAnimation
})
</script>

<template>
  <div ref="svgContainer" class="svg-canvas-container"></div>
</template>

<style scoped>
.svg-canvas-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
  position: relative;
  background: #1a1a2e;
}
.svg-canvas-container :deep(svg) {
  display: block;
}
</style>
