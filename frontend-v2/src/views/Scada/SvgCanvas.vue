<script setup lang="ts">
/**
 * SvgCanvas - FUXA 风格 SVG 画布组件 v2
 *
 * 架构参照 FUXA（基于 SVG-Edit）:
 * 1. 画布 = SVG 文档，图元 = SVG DOM 元素
 * 2. SVG.js 提供底层 DOM 操作便利
 * 3. 选中/缩放句柄参照 SVG-Edit 的 selector.js
 * 4. 撤销/重做基于命令模式
 * 5. 网格吸附参照 SVG-Edit 的 grid snapping
 *
 * 编辑模式交互：
 * - 点击选中图元（显示8个缩放句柄 + 旋转手柄）
 * - 拖拽移动图元（支持网格吸附）
 * - 缩放句柄调整尺寸
 * - Rubber-band 多选
 * - 键盘 Delete 删除
 * - Ctrl+Z/Ctrl+Y 撤销重做
 *
 * 运行模式交互：
 * - 数据绑定（processValue 链路）
 * - 管道动画
 */

import { ref, onMounted, onUnmounted, watch } from 'vue'
import { SVG } from '@svgdotjs/svg.js'
import { convertFabricToSvg, isFabricJson } from './fabric-to-svg'
import {
  scanAndBindFromDOM,
  handleSignalChange,
  cleanupAll,
  clearAllSignalMappings,
  walkTreeNodeToSetAttribute,
  type SignalValue
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
    gridSize: 0
  }
)

const emit = defineEmits<{
  (e: 'object:selected', obj: SVGElement | null): void
  (e: 'object:deselected'): void
  (e: 'canvas:changed'): void
  (e: 'ready'): void
  (e: 'zoom:changed', zoom: number): void
}>()

// ── DOM 引用 ──
const svgContainer = ref<HTMLDivElement>()

// SVG.js 实例和核心 DOM
let svgDraw: any = null          // SVG.js 绘制实例
let svgRoot: SVGSVGElement | null = null
let svgMainGroup: SVGGElement | null = null

// ── 画布状态 ──
const zoomLevel = ref(1)
let panOffset = { x: 0, y: 0 }

// ── 选中系统（参照 SVG-Edit selector.js） ──
let selectedElement: SVGElement | null = null
let selectedElements: SVGElement[] = []  // 多选
let selectorGroup: SVGGElement | null = null  // 选中框+句柄的 <g>
let resizeHandles: Map<string, SVGCircleElement> = new Map()  // 8个缩放句柄
let rotationHandle: SVGCircleElement | null = null  // 旋转手柄

// ── 拖拽状态 ──
let isDragging = false
let dragStartX = 0
let dragStartY = 0
let dragElementStartX = 0
let dragElementStartY = 0

// ── 缩放句柄拖拽状态 ──
let isResizing = false
let resizeHandleDir = ''  // 'nw','n','ne','e','se','s','sw','w'
let resizeStartBox = { x: 0, y: 0, w: 0, h: 0 }
let resizeStartX = 0
let resizeStartY = 0

// ── 旋转状态 ──
let isRotating = false
let rotateStartAngle = 0
let rotateElementStartAngle = 0

// ── 橡皮筋选择（Rubber-band selection） ──
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

// ── 撤销/重做 ──
interface UndoCommand {
  type: 'add' | 'remove' | 'transform' | 'attribute' | 'multi'
  data: any
}
let undoStack: UndoCommand[] = []
let redoStack: UndoCommand[] = []
const MAX_UNDO = 50

// ── 网格吸附 ──
const snapToGrid = (val: number): number => {
  if (props.gridSize > 0) return Math.round(val / props.gridSize) * props.gridSize
  return val
}

// ── 辅助函数 ──

/** 获取元素在 SVG 坐标系中的 BBox */
function getBBox(el: SVGElement): DOMRect {
  try {
    return (el as SVGGElement).getBBox()
  } catch {
    return new DOMRect(0, 0, 0, 0)
  }
}

/** 获取元素的 transform translate 值 */
function getTranslate(el: SVGElement): { x: number; y: number } {
  const t = el.getAttribute('transform') || ''
  const m = t.match(/translate\(([-\d.]+),\s*([-\d.]+)\)/)
  if (m) return { x: parseFloat(m[1]), y: parseFloat(m[2]) }
  return { x: 0, y: 0 }
}

/** 设置元素的 translate */
function setTranslate(el: SVGElement, x: number, y: number) {
  const existing = el.getAttribute('transform') || ''
  // 保留 rotate/scale，只替换 translate
  let newTransform = `translate(${x},${y})`
  const rotateMatch = existing.match(/rotate\([^)]+\)/)
  const scaleMatch = existing.match(/scale\([^)]+\)/)
  if (rotateMatch) newTransform += ` ${rotateMatch[0]}`
  if (scaleMatch) newTransform += ` ${scaleMatch[0]}`
  el.setAttribute('transform', newTransform)
}

/** 客户端坐标 → SVG 坐标 */
function clientToSVG(clientX: number, clientY: number): { x: number; y: number } {
  if (!svgRoot) return { x: 0, y: 0 }
  const pt = svgRoot.createSVGPoint()
  pt.x = clientX
  pt.y = clientY
  const ctm = svgRoot.getScreenCTM()
  if (!ctm) return { x: 0, y: 0 }
  const svgPt = pt.matrixTransform(ctm.inverse())
  return { x: svgPt.x, y: svgPt.y }
}

// ── 初始化 SVG 画布 ──

const initSvgCanvas = () => {
  if (!svgContainer.value) return

  // 创建 SVG 文档结构
  const container = svgContainer.value
  container.innerHTML = ''

  svgDraw = SVG().size(props.width, props.height)
  svgRoot = svgDraw.node as SVGSVGElement
  svgRoot.setAttribute('xmlns', 'http://www.w3.org/2000/svg')

  // 背景
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
  bg.setAttribute('width', '100%')
  bg.setAttribute('height', '100%')
  bg.setAttribute('fill', props.background)
  bg.setAttribute('data-bg', 'true')
  svgRoot.appendChild(bg)

  // 主内容组
  svgMainGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g')
  svgMainGroup.setAttribute('id', 'svg-main-group')
  svgRoot.appendChild(svgMainGroup)

  // 选中框组（最上层）
  selectorGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g')
  selectorGroup.setAttribute('id', 'svg-selector-group')
  selectorGroup.style.pointerEvents = 'none'
  svgRoot.appendChild(selectorGroup)

  // 应用初始视图变换
  applyTransform()

  // 编辑模式事件绑定
  if (!props.runtime) {
    bindEditorEvents()
  }

  // 绘制网格
  drawGrid()

  emit('ready')
}

// ── 选中框和缩放句柄（参照 SVG-Edit selector.js） ──

/** 清除选中框 */
const clearSelection = () => {
  if (selectorGroup) selectorGroup.innerHTML = ''
  resizeHandles.clear()
  rotationHandle = null
  selectedElement = null
  selectedElements = []
}

/** 绘制选中框和缩放句柄 */
const drawSelectionBox = (el: SVGElement) => {
  if (!selectorGroup) return
  selectorGroup.innerHTML = ''
  resizeHandles.clear()

  const bbox = getBBox(el)
  const translate = getTranslate(el)
  const x = bbox.x + translate.x
  const y = bbox.y + translate.y
  const w = bbox.width
  const h = bbox.height

  // 选中框
  const selRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
  selRect.setAttribute('x', String(x - 1))
  selRect.setAttribute('y', String(y - 1))
  selRect.setAttribute('width', String(w + 2))
  selRect.setAttribute('height', String(h + 2))
  selRect.setAttribute('fill', 'none')
  selRect.setAttribute('stroke', '#4a9eff')
  selRect.setAttribute('stroke-width', '1')
  selRect.setAttribute('stroke-dasharray', '3,2')
  selectorGroup.appendChild(selRect)

  if (!props.runtime) {
    // 8个缩放句柄
    const handlePositions: Record<string, { hx: number; hy: number }> = {
      nw: { hx: x, hy: y },
      n:  { hx: x + w / 2, hy: y },
      ne: { hx: x + w, hy: y },
      e:  { hx: x + w, hy: y + h / 2 },
      se: { hx: x + w, hy: y + h },
      s:  { hx: x + w / 2, hy: y + h },
      sw: { hx: x, hy: y + h },
      w:  { hx: x, hy: y + h / 2 }
    }

    for (const [dir, pos] of Object.entries(handlePositions)) {
      const handle = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
      handle.setAttribute('x', String(pos.hx - 4))
      handle.setAttribute('y', String(pos.hy - 4))
      handle.setAttribute('width', '8')
      handle.setAttribute('height', '8')
      handle.setAttribute('fill', '#ffffff')
      handle.setAttribute('stroke', '#4a9eff')
      handle.setAttribute('stroke-width', '1.5')
      handle.setAttribute('rx', '1')
      handle.style.cursor = `${dir}-resize`
      handle.style.pointerEvents = 'all'
      handle.setAttribute('data-resize-dir', dir)
      selectorGroup.appendChild(handle)
      resizeHandles.set(dir, handle as unknown as SVGCircleElement)
    }

    // 旋转手柄
    const rotHandle = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
    rotHandle.setAttribute('cx', String(x + w / 2))
    rotHandle.setAttribute('cy', String(y - 25))
    rotHandle.setAttribute('r', '5')
    rotHandle.setAttribute('fill', '#4a9eff')
    rotHandle.setAttribute('stroke', '#ffffff')
    rotHandle.setAttribute('stroke-width', '1.5')
    rotHandle.style.cursor = 'crosshair'
    rotHandle.style.pointerEvents = 'all'
    selectorGroup.appendChild(rotHandle)
    rotationHandle = rotHandle as unknown as SVGCircleElement

    // 旋转连接线
    const rotLine = document.createElementNS('http://www.w3.org/2000/svg', 'line')
    rotLine.setAttribute('x1', String(x + w / 2))
    rotLine.setAttribute('y1', String(y))
    rotLine.setAttribute('x2', String(x + w / 2))
    rotLine.setAttribute('y2', String(y - 25))
    rotLine.setAttribute('stroke', '#4a9eff')
    rotLine.setAttribute('stroke-width', '1')
    rotLine.setAttribute('stroke-dasharray', '2,2')
    selectorGroup.insertBefore(rotLine, rotHandle)
  }
}

// ── 编辑器事件绑定 ──

const bindEditorEvents = () => {
  if (!svgRoot) return

  // 点击选中
  svgRoot.addEventListener('mousedown', onMouseDown)
  svgRoot.addEventListener('mousemove', onMouseMove)
  svgRoot.addEventListener('mouseup', onMouseUp)

  // 滚轮缩放
  svgRoot.addEventListener('wheel', onWheel, { passive: false })

  // 键盘
  document.addEventListener('keydown', onKeyDown)
}

// ── 鼠标事件处理（参照 SVG-Edit mouseEventHandler） ──

const onMouseDown = (e: MouseEvent) => {
  if (props.runtime) return
  const target = e.target as SVGElement
  const pos = clientToSVG(e.clientX, e.clientY)

  // 检查是否点击了缩放句柄
  if (target.hasAttribute('data-resize-dir')) {
    isResizing = true
    resizeHandleDir = target.getAttribute('data-resize-dir') || ''
    resizeStartX = pos.x
    resizeStartY = pos.y
    if (selectedElement) {
      const bbox = getBBox(selectedElement)
      const t = getTranslate(selectedElement)
      resizeStartBox = { x: bbox.x + t.x, y: bbox.y + t.y, w: bbox.width, h: bbox.height }
    }
    e.preventDefault()
    e.stopPropagation()
    return
  }

  // 检查是否点击了旋转手柄
  if (target === rotationHandle) {
    isRotating = true
    if (selectedElement) {
      const bbox = getBBox(selectedElement)
      const t = getTranslate(selectedElement)
      const cx = bbox.x + t.x + bbox.width / 2
      const cy = bbox.y + t.y + bbox.height / 2
      rotateStartAngle = Math.atan2(pos.y - cy, pos.x - cx)
      const existing = selectedElement.getAttribute('transform') || ''
      const rm = existing.match(/rotate\(([-\d.]+)/)
      rotateElementStartAngle = rm ? parseFloat(rm[1]) : 0
    }
    e.preventDefault()
    e.stopPropagation()
    return
  }

  // 中键平移
  if (e.button === 1) {
    isPanning = true
    panStartX = e.clientX
    panStartY = e.clientY
    panStartOffsetX = panOffset.x
    panStartOffsetY = panOffset.y
    e.preventDefault()
    return
  }

  // 右键不处理
  if (e.button === 2) return

  // 检查点击的元素是否在主内容组中
  const isMainGroupChild = target.closest && target.closest('#svg-main-group')

  if (isMainGroupChild && target !== svgMainGroup && !target.hasAttribute('data-bg')) {
    // 选中图元 — 找到最近的带 id 的子元素
    let targetEl = target
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
  if (target === svgMainGroup || target.hasAttribute('data-bg') || target === svgRoot) {
    if (!e.shiftKey) {
      clearSelection()
      emit('object:deselected')
    }

    // 启动橡皮筋选择
    isRubberBand = true
    rubberBandStartX = pos.x
    rubberBandStartY = pos.y

    rubberBandRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
    rubberBandRect.setAttribute('fill', 'rgba(74,158,255,0.15)')
    rubberBandRect.setAttribute('stroke', '#4a9eff')
    rubberBandRect.setAttribute('stroke-width', '1')
    rubberBandRect.setAttribute('stroke-dasharray', '4,2')
    rubberBandRect.setAttribute('x', String(pos.x))
    rubberBandRect.setAttribute('y', String(pos.y))
    rubberBandRect.setAttribute('width', '0')
    rubberBandRect.setAttribute('height', '0')
    selectorGroup!.appendChild(rubberBandRect)
  }

  // Alt + 左键平移
  if (e.altKey) {
    isPanning = true
    panStartX = e.clientX
    panStartY = e.clientY
    panStartOffsetX = panOffset.x
    panStartOffsetY = panOffset.y
  }
}

const onMouseMove = (e: MouseEvent) => {
  const pos = clientToSVG(e.clientX, e.clientY)

  // 拖拽移动
  if (isDragging && selectedElement) {
    let dx = pos.x - dragStartX
    let dy = pos.y - dragStartY

    // 网格吸附
    let newX = snapToGrid(dragElementStartX + dx)
    let newY = snapToGrid(dragElementStartY + dy)

    setTranslate(selectedElement, newX, newY)
    drawSelectionBox(selectedElement)
    return
  }

  // 缩放句柄拖拽
  if (isResizing && selectedElement) {
    const dx = pos.x - resizeStartX
    const dy = pos.y - resizeStartY
    let { x, y, w, h } = resizeStartBox

    // 根据方向调整
    if (resizeHandleDir.includes('w')) { x += dx; w -= dx }
    if (resizeHandleDir.includes('e')) { w += dx }
    if (resizeHandleDir.includes('n')) { y += dy; h -= dy }
    if (resizeHandleDir.includes('s')) { h += dy }

    // 最小尺寸
    if (w < 10) w = 10
    if (h < 10) h = 10

    // 应用到元素
    if (selectedElement.tagName === 'rect') {
      selectedElement.setAttribute('x', String(snapToGrid(x)))
      selectedElement.setAttribute('y', String(snapToGrid(y)))
      selectedElement.setAttribute('width', String(snapToGrid(w)))
      selectedElement.setAttribute('height', String(snapToGrid(h)))
    } else {
      // 其他元素使用 transform: scale
      const origW = resizeStartBox.w || 1
      const origH = resizeStartBox.h || 1
      const sx = w / origW
      const sy = h / origH
      selectedElement.setAttribute('transform', `translate(${snapToGrid(x)},${snapToGrid(y)}) scale(${sx},${sy})`)
    }

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

    // 吸附到 5 度
    const snappedAngle = Math.round(newAngle / 5) * 5
    const existing = selectedElement.getAttribute('transform') || ''
    let newTransform = existing.replace(/rotate\([^)]+\)/, '').trim()
    newTransform += ` rotate(${snappedAngle},${cx},${cy})`
    selectedElement.setAttribute('transform', newTransform)
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

const onMouseUp = (_e: MouseEvent) => {
  // 结束拖拽
  if (isDragging) {
    isDragging = false
    if (selectedElement) {
      pushUndo({ type: 'transform', data: { id: selectedElement.getAttribute('id'), transform: selectedElement.getAttribute('transform') } })
    }
    emit('canvas:changed')
  }

  // 结束缩放
  if (isResizing) {
    isResizing = false
    resizeHandleDir = ''
    if (selectedElement) {
      pushUndo({ type: 'transform', data: { id: selectedElement.getAttribute('id'), transform: selectedElement.getAttribute('transform') } })
    }
    emit('canvas:changed')
  }

  // 结束旋转
  if (isRotating) {
    isRotating = false
    if (selectedElement) {
      pushUndo({ type: 'transform', data: { id: selectedElement.getAttribute('id'), transform: selectedElement.getAttribute('transform') } })
    }
    emit('canvas:changed')
  }

  // 结束橡皮筋选择
  if (isRubberBand) {
    isRubberBand = false
    // 计算橡皮筋矩形范围
    const rbX = Math.min(rubberBandStartX, rubberBandEndX)
    const rbY = Math.min(rubberBandStartY, rubberBandEndY)
    const rbW = Math.abs(rubberBandEndX - rubberBandStartX)
    const rbH = Math.abs(rubberBandEndY - rubberBandStartY)

    if (rubberBandRect) {
      rubberBandRect.remove()
      rubberBandRect = null
    }

    // 只在框面积足够大时执行多选（避免点击误触）
    if (rbW > 5 && rbH > 5 && svgMainGroup) {
      const selected: SVGElement[] = []
      const children = svgMainGroup.children
      for (let i = 0; i < children.length; i++) {
        const child = children[i] as SVGElement
        if (!child.getAttribute('id')) continue // 跳过无id元素
        try {
          const bbox = getBBox(child)
          const t = getTranslate(child)
          // 计算元素中心点
          const cx = t.x + bbox.x + bbox.width / 2
          const cy = t.y + bbox.y + bbox.height / 2
          // 检查中心点是否在橡皮筋矩形内
          if (cx >= rbX && cx <= rbX + rbW && cy >= rbY && cy <= rbY + rbH) {
            selected.push(child)
          }
        } catch { /* ignore getBBox errors */ }
      }

      if (selected.length > 0) {
        selectedElements = selected
        selectedElement = selected[0]
        drawSelectionBox(selectedElement)
        emit('object:selected', selectedElement)
      }
    }
  }

  // 结束平移
  if (isPanning) {
    isPanning = false
  }
}

// ── 滚轮缩放 ──

const onWheel = (e: WheelEvent) => {
  e.preventDefault()
  const delta = e.deltaY > 0 ? -0.1 : 0.1
  const newZoom = Math.max(0.1, Math.min(5, zoomLevel.value + delta))
  zoomLevel.value = Math.round(newZoom * 100) / 100
  applyTransform()
  emit('zoom:changed', zoomLevel.value)
}

// ── 键盘事件 ──

const onKeyDown = (e: KeyboardEvent) => {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

  // Delete 删除
  if ((e.key === 'Delete' || e.key === 'Backspace') && selectedElement) {
    deleteSelected()
    e.preventDefault()
  }

  // 方向键微移
  if (selectedElement && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
    const step = e.shiftKey ? 10 : 1
    const t = getTranslate(selectedElement)
    let { x, y } = t
    switch (e.key) {
      case 'ArrowUp': y -= step; break
      case 'ArrowDown': y += step; break
      case 'ArrowLeft': x -= step; break
      case 'ArrowRight': x += step; break
    }
    setTranslate(selectedElement, snapToGrid(x), snapToGrid(y))
    drawSelectionBox(selectedElement)
    emit('canvas:changed')
    e.preventDefault()
  }
}

// ── 变换 ──

const applyTransform = () => {
  if (svgMainGroup) {
    svgMainGroup.setAttribute('transform', `translate(${panOffset.x},${panOffset.y}) scale(${zoomLevel.value})`)
  }
  // 选中框也需要同样变换
  if (selectorGroup) {
    selectorGroup.setAttribute('transform', `translate(${panOffset.x},${panOffset.y}) scale(${zoomLevel.value})`)
  }
}

// ── 网格 ──

const drawGrid = () => {
  if (!svgRoot || props.gridSize <= 0) return
  let gridGroup = svgRoot.querySelector('#svg-grid-group')
  if (gridGroup) gridGroup.remove()

  gridGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g')
  gridGroup.setAttribute('id', 'svg-grid-group')
  gridGroup.setAttribute('opacity', '0.15')

  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs')
  const pattern = document.createElementNS('http://www.w3.org/2000/svg', 'pattern')
  pattern.setAttribute('id', 'grid-pattern')
  pattern.setAttribute('width', String(props.gridSize))
  pattern.setAttribute('height', String(props.gridSize))
  pattern.setAttribute('patternUnits', 'userSpaceOnUse')

  const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
  dot.setAttribute('cx', '0')
  dot.setAttribute('cy', '0')
  dot.setAttribute('r', '1')
  dot.setAttribute('fill', '#888888')
  pattern.appendChild(dot)
  defs.appendChild(pattern)
  gridGroup.appendChild(defs)

  const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
  rect.setAttribute('width', String(props.width))
  rect.setAttribute('height', String(props.height))
  rect.setAttribute('fill', 'url(#grid-pattern)')
  gridGroup.appendChild(rect)

  // 插入到主内容组前面
  svgRoot.insertBefore(gridGroup, svgMainGroup)
}

// ── 公共 API ──

/** 添加 SVG 图元片段 */
const addWidgetSVG = (svgFragment: string, _x: number = 0, _y: number = 0) => {
  if (!svgMainGroup) return

  // 解析 SVG 片段
  const tempDiv = document.createElement('div')
  tempDiv.innerHTML = svgFragment
  const svgEl = tempDiv.querySelector('svg') || tempDiv

  const children = Array.from(svgEl.children)
  const added: SVGElement[] = []

  children.forEach(child => {
    if (child instanceof SVGElement && child.tagName !== 'defs') {
      // 设置初始位置
      const existingTransform = child.getAttribute('transform') || ''
      if (!existingTransform.includes('translate')) {
        child.setAttribute('transform', `translate(${_x},${_y}) ${existingTransform}`)
      }
      svgMainGroup!.appendChild(child.cloneNode(true))
      added.push(child.cloneNode(true) as SVGElement)
    }
  })

  pushUndo({ type: 'add', data: { svgFragment, x: _x, y: _y } })
  snapshot()
  emit('canvas:changed')
}

/** 删除选中元素 */
const deleteSelected = () => {
  if (!selectedElement || !svgMainGroup) return
  const id = selectedElement.getAttribute('id')
  const outerHTML = selectedElement.outerHTML

  selectedElement.remove()
  clearSelection()
  emit('object:deselected')
  pushUndo({ type: 'remove', data: { id, outerHTML } })
  emit('canvas:changed')
}

/** 清空画布 */
const clear = () => {
  if (!svgMainGroup) return
  svgMainGroup.innerHTML = ''
  clearSelection()
  snapshot()
  emit('canvas:changed')
}

/** 设置选中元素的变换属性 */
const setSelectedTransform = (prop: string, value: any) => {
  if (!selectedElement) return
  const t = getTranslate(selectedElement)

  switch (prop) {
    case 'left':
      setTranslate(selectedElement, Number(value), t.y)
      break
    case 'top':
      setTranslate(selectedElement, t.x, Number(value))
      break
    case 'opacity':
      selectedElement.setAttribute('opacity', String(value))
      break
  }
  drawSelectionBox(selectedElement)
  emit('canvas:changed')
}

/** 获取选中元素的变换信息 */
const getSelectedTransform = () => {
  if (!selectedElement) return { x: 0, y: 0, opacity: 1 }
  const t = getTranslate(selectedElement)
  const opacity = parseFloat(selectedElement.getAttribute('opacity') || '1')
  return { x: t.x, y: t.y, opacity }
}

/** 设置数据绑定 */
const setBinding = (elementId: string, target: string, deviceId: number, tagId: number, tagName: string, prop: string) => {
  if (!svgMainGroup) return
  const el = svgMainGroup.querySelector(`#${elementId}`)
  if (el) {
    el.setAttribute('data-bind-target', target)
    el.setAttribute('data-bind-device-id', String(deviceId))
    el.setAttribute('data-bind-tag-id', String(tagId))
    el.setAttribute('data-bind-tag-name', tagName)
    el.setAttribute('data-bind-prop', prop)
  }
}

/** 锁定/解锁 */
const lockSelected = () => {
  if (selectedElement) selectedElement.setAttribute('data-locked', 'true')
}
const unlockSelected = () => {
  if (selectedElement) selectedElement.removeAttribute('data-locked')
}
const isLocked = (): boolean => selectedElement?.getAttribute('data-locked') === 'true'

/** 层级操作 */
const bringForward = () => { if (selectedElement?.nextElementSibling) svgMainGroup?.insertBefore(selectedElement.nextElementSibling, selectedElement); emit('canvas:changed') }
const sendBackward = () => { if (selectedElement?.previousElementSibling) svgMainGroup?.insertBefore(selectedElement, selectedElement.previousElementSibling); emit('canvas:changed') }
const bringToFront = () => { if (selectedElement && svgMainGroup) { svgMainGroup.appendChild(selectedElement) }; emit('canvas:changed') }
const sendToBack = () => { if (selectedElement && svgMainGroup) { svgMainGroup.insertBefore(selectedElement, svgMainGroup.firstChild) }; emit('canvas:changed') }

/** 复制选中 */
const copySelected = () => {
  if (!selectedElement || !svgMainGroup) return
  const clone = selectedElement.cloneNode(true) as SVGElement
  // 新 ID
  const newId = `w-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`
  clone.setAttribute('id', newId)
  // 偏移一点
  const t = getTranslate(selectedElement)
  setTranslate(clone, t.x + 20, t.y + 20)
  svgMainGroup.appendChild(clone)
  // 选中新元素
  selectedElement = clone
  drawSelectionBox(clone)
  pushUndo({ type: 'add', data: { svgFragment: clone.outerHTML } })
  emit('canvas:changed')
}

// ── 缩放 API ──

const setZoom = (z: number) => {
  zoomLevel.value = Math.max(0.1, Math.min(5, z))
  applyTransform()
  emit('zoom:changed', zoomLevel.value)
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
  applyTransform()
  emit('zoom:changed', 1)
}

// ── 撤销/重做 ──

const snapshot = () => {
  // 简易快照：保存当前 SVG 内容
}

const pushUndo = (cmd: UndoCommand) => {
  undoStack.push(cmd)
  if (undoStack.length > MAX_UNDO) undoStack.shift()
  redoStack = []
}

const canUndo = (): boolean => undoStack.length > 0
const canRedo = (): boolean => redoStack.length > 0

const undo = () => {
  const cmd = undoStack.pop()
  if (!cmd) return
  redoStack.push(cmd)
  // 简化：只支持 transform 撤销
  if (cmd.type === 'remove' && cmd.data.outerHTML) {
    const temp = document.createElement('div')
    temp.innerHTML = cmd.data.outerHTML
    const el = temp.firstElementChild as SVGElement
    if (el && svgMainGroup) svgMainGroup.appendChild(el)
  }
  emit('canvas:changed')
}

const redo = () => {
  const cmd = redoStack.pop()
  if (!cmd) return
  undoStack.push(cmd)
  emit('canvas:changed')
}

// ── 序列化 ──

const toSVGString = (): string => {
  if (!svgRoot) return ''
  // 克隆并移除选中框和网格
  const clone = svgRoot.cloneNode(true) as SVGSVGElement
  clone.querySelector('#svg-selector-group')?.remove()
  clone.querySelector('#svg-grid-group')?.remove()
  // 移除背景标记
  const bg = clone.querySelector('[data-bg]')
  if (bg) bg.remove()
  return clone.outerHTML
}

const toJSON = (): object => {
  return {
    version: '2.0',
    type: 'svg',
    svgContent: toSVGString(),
    width: props.width,
    height: props.height,
    background: props.background
  }
}

const loadFromSVG = (svgContent: string): Promise<void> => {
  if (!svgMainGroup) return Promise.resolve()

  return new Promise((resolve) => {
    if (svgMainGroup) svgMainGroup.innerHTML = ''
    const temp = document.createElement('div')
    temp.innerHTML = svgContent

    const svgEl = temp.querySelector('svg')
    const source = svgEl || temp

    // 复制内容到主组
    Array.from(source.children).forEach(child => {
      if (child instanceof SVGElement && child.tagName !== 'defs' && !child.hasAttribute('data-bg')) {
        svgMainGroup!.appendChild(document.importNode(child, true))
      }
    })

    snapshot()
    resolve()
  })
}

const loadFromJSON = async (json: any): Promise<void> => {
  if (!svgMainGroup) return

  // 新版 SVG 格式
  if (json && json.type === 'svg' && json.svgContent) {
    return loadFromSVG(json.svgContent)
  }

  // 兼容旧版：自动将 Fabric JSON 转换为 SVG
  if (isFabricJson(json)) {
    console.log('[SvgCanvas] 检测到旧版 Fabric JSON，正在自动转换为 SVG...')
    const svgString = convertFabricToSvg(json, props.width, props.height, props.background)
    return loadFromSVG(svgString)
  }

  // 字符串
  if (typeof json === 'string') {
    return loadFromSVG(json)
  }
}

// ── 运行时：数据绑定 ──

const initRuntimeBindings = () => {
  if (!svgMainGroup || !props.runtime) return
  const count = scanAndBindFromDOM(svgMainGroup)
  console.log(`[SvgCanvas] 运行时绑定: 扫描到 ${count} 个绑定图元`)
}

const processRuntimeSignal = (signalId: string, value: SignalValue) => {
  if (!svgMainGroup || !props.runtime) return
  handleSignalChange(signalId, value, svgMainGroup)
}

// ── 运行时：ScadaViewer 辅助方法 ──

interface BindingInfo {
  elementId: string
  bindTarget: string
  deviceId: number
  tagId: number
  tagName: string
  prop: string
}

const getAllBindings = (): BindingInfo[] => {
  const bindings: BindingInfo[] = []
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

const updateBoundValue = (elementId: string, _bindTarget: string, value: any, prop: string) => {
  if (!svgMainGroup) return
  const el = svgMainGroup.querySelector(`#${elementId}`)
  if (!el) return
  const svgEl = el as SVGElement
  if (prop === 'fill') {
    walkTreeNodeToSetAttribute(svgEl, 'fill', String(value))
  } else if (prop === 'stroke') {
    svgEl.setAttribute('stroke', String(value))
  } else if (prop === 'text') {
    const texts = svgEl.querySelectorAll('text, tspan')
    if (texts.length > 0) {
      texts.forEach((t) => { t.textContent = String(value) })
    } else if (svgEl.tagName === 'text' || svgEl.tagName === 'tspan') {
      svgEl.textContent = String(value)
    }
  } else if (prop === 'height') {
    const h = parseFloat(svgEl.getAttribute('height') || '0')
    if (h > 0) {
      svgEl.setAttribute('height', String(Math.max(0, parseFloat(String(value)))))
    }
  } else if (prop === 'transform') {
    svgEl.setAttribute('transform', String(value))
  }
}

// ── 管道动画 ──

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

  // 旋转动画
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
        } catch { /* ignore */ }
      }
    })
  }

  animate()
  startRotation()
}

const stopFlowAnimation = () => {
  if (flowAnimationId) {
    cancelAnimationFrame(flowAnimationId)
    flowAnimationId = null
  }
}

// ── 生命周期 ──

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
  document.removeEventListener('keydown', onKeyDown)
})

// ── 监听 props 变化 ──

watch(() => props.gridSize, () => {
  if (svgRoot) {
    const gridGroup = svgRoot.querySelector('#svg-grid-group')
    if (gridGroup) gridGroup.remove()
  }
  drawGrid()
})

watch(() => props.background, (newBg) => {
  if (svgRoot) {
    const bg = svgRoot.querySelector('[data-bg]')
    if (bg) bg.setAttribute('fill', newBg)
  }
})

// ── 导出方法 ──

defineExpose({
  loadFromSVG,
  loadFromJSON,
  toJSON,
  toSVGString,
  addWidgetSVG,
  deleteSelected,
  clear,
  setSelectedTransform,
  getSelectedTransform,
  setBinding,
  lockSelected,
  unlockSelected,
  isLocked,
  bringForward,
  sendBackward,
  bringToFront,
  sendToBack,
  copySelected,
  setZoom,
  getZoom,
  zoomFit,
  zoomReset,
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
