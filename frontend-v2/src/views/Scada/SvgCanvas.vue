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

import { ref, onMounted, onUnmounted } from 'vue'
import { convertFabricToSvg, isFabricJson } from './fabric-to-svg'

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

// ── 拖拽移动 ──
let isDragging = false
let dragStart = { x: 0, y: 0 }
let dragElementStart = { x: 0, y: 0 }

// ── 缩放拖拽（预留，resize-handle 功能待实现） ──

// ── 撤销/重做 ──
let undoStack: string[] = []
let redoStack: string[] = []
let isLoadingState = false

const snapshot = () => {
  if (!svgRoot || isLoadingState || props.runtime) return
  const content = svgRoot.innerHTML
  undoStack.push(content)
  if (undoStack.length > 50) undoStack.shift()
  redoStack = []
}

const undo = () => {
  if (!svgRoot || undoStack.length <= 1) return
  isLoadingState = true
  const current = undoStack.pop()!
  redoStack.push(current)
  const prev = undoStack[undoStack.length - 1]
  svgRoot.innerHTML = prev
  bindElementEvents()
  isLoadingState = false
}

const redo = () => {
  if (!svgRoot || redoStack.length === 0) return
  isLoadingState = true
  const next = redoStack.pop()!
  undoStack.push(next)
  svgRoot.innerHTML = next
  bindElementEvents()
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

    // 拖拽移动图元
    if (isDragging && selectedElement) {
      const dx = (e.clientX - dragStart.x) / zoomLevel.value
      const dy = (e.clientY - dragStart.y) / zoomLevel.value

      let newX = dragElementStart.x + dx
      let newY = dragElementStart.y + dy

      // 网格吸附
      if (props.gridSize > 0) {
        newX = Math.round(newX / props.gridSize) * props.gridSize
        newY = Math.round(newY / props.gridSize) * props.gridSize
      }

      selectedElement.setAttribute('transform', `translate(${newX},${newY})`)
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
}

// ── 图元选中逻辑 ──

const deselectAll = () => {
  if (selectionBox) {
    selectionBox.remove()
    selectionBox = null
  }
  if (selectedElement) {
    selectedElement.classList.remove('svg-selected')
    selectedElement = null
  }
  emit('object:deselected')
}

const selectElement = (el: SVGElement) => {
  if (props.runtime) return
  deselectAll()
  selectedElement = el
  el.classList.add('svg-selected')
  createSelectionBox(el)
  emit('object:selected', el)
}

const createSelectionBox = (el: SVGElement) => {
  if (!svgMainGroup) return
  // 移除旧选框
  if (selectionBox) selectionBox.remove()

  const bbox = getTransformedBBox(el)
  if (!bbox) return

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

  // 8个缩放手柄
  const handleSize = 8
  const positions = [
    { x: bbox.x - 4 - handleSize / 2, y: bbox.y - 4 - handleSize / 2, cursor: 'nw-resize' },
    { x: bbox.x + bbox.width / 2 - handleSize / 2, y: bbox.y - 4 - handleSize / 2, cursor: 'n-resize' },
    { x: bbox.x + bbox.width + 4 - handleSize / 2, y: bbox.y - 4 - handleSize / 2, cursor: 'ne-resize' },
    { x: bbox.x + bbox.width + 4 - handleSize / 2, y: bbox.y + bbox.height / 2 - handleSize / 2, cursor: 'e-resize' },
    { x: bbox.x + bbox.width + 4 - handleSize / 2, y: bbox.y + bbox.height + 4 - handleSize / 2, cursor: 'se-resize' },
    { x: bbox.x + bbox.width / 2 - handleSize / 2, y: bbox.y + bbox.height + 4 - handleSize / 2, cursor: 's-resize' },
    { x: bbox.x - 4 - handleSize / 2, y: bbox.y + bbox.height + 4 - handleSize / 2, cursor: 'sw-resize' },
    { x: bbox.x - 4 - handleSize / 2, y: bbox.y + bbox.height / 2 - handleSize / 2, cursor: 'w-resize' }
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
    handle.setAttribute('pointer-events', 'all')
    handle.setAttribute('cursor', pos.cursor)
    handle.setAttribute('class', 'resize-handle')
    selectionBox!.appendChild(handle)
  })

  svgMainGroup.appendChild(selectionBox)
}

const updateSelectionBox = () => {
  if (!selectedElement) return
  createSelectionBox(selectedElement)
}

/** 获取元素经过 transform 后的边界框 */
const getTransformedBBox = (el: SVGElement): DOMRect | null => {
  try {
    // 使用 SVG 方法获取 bbox（考虑 transform）
    const svgEl = el as SVGGElement
    const bbox = svgEl.getBBox()
    // getBBox 不包含 transform，需要手动计算
    const transform = el.getAttribute('transform') || ''
    const translateMatch = transform.match(/translate\(([^,]+),([^)]+)\)/)
    const tx = translateMatch ? parseFloat(translateMatch[1]) : 0
    const ty = translateMatch ? parseFloat(translateMatch[2]) : 0

    return {
      x: bbox.x + tx,
      y: bbox.y + ty,
      width: bbox.width,
      height: bbox.height,
      top: bbox.y + ty,
      right: bbox.x + tx + bbox.width,
      bottom: bbox.y + ty + bbox.height,
      left: bbox.x + tx,
      toJSON: () => ({})
    } as DOMRect
  } catch {
    return null
  }
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

    // 选中事件
    svgEl.addEventListener('mousedown', (e: MouseEvent) => {
      if (props.runtime) return
      if (e.button !== 0) return
      e.stopPropagation()

      selectElement(svgEl)

      // 开始拖拽
      isDragging = true
      dragStart = { x: e.clientX, y: e.clientY }
      const transform = svgEl.getAttribute('transform') || ''
      const match = transform.match(/translate\(([^,]+),([^)]+)\)/)
      dragElementStart = {
        x: match ? parseFloat(match[1]) : 0,
        y: match ? parseFloat(match[2]) : 0
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
      bindElementEvents()
      snapshot()
      emit('canvas:changed')
    }
  }
}

/** 删除选中图元 */
const deleteSelected = () => {
  if (!selectedElement || !svgMainGroup || props.runtime) return
  selectedElement.remove()
  deselectAll()
  snapshot()
  emit('canvas:changed')
}

/** 清空画布 */
const clear = () => {
  if (!svgMainGroup) return
  svgMainGroup.innerHTML = ''
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

// ── 层级调整 ──

const bringForward = () => {
  if (!selectedElement || !svgMainGroup) return
  const next = selectedElement.nextElementSibling
  if (next && next !== selectionBox) {
    svgMainGroup.insertBefore(next, selectedElement)
    snapshot()
  }
}

const sendBackward = () => {
  if (!selectedElement || !svgMainGroup) return
  const prev = selectedElement.previousElementSibling
  if (prev) {
    svgMainGroup.insertBefore(selectedElement, prev)
    snapshot()
  }
}

const bringToFront = () => {
  if (!selectedElement || !svgMainGroup) return
  svgMainGroup.appendChild(selectedElement)
  snapshot()
}

const sendToBack = () => {
  if (!selectedElement || !svgMainGroup) return
  svgMainGroup.insertBefore(selectedElement, svgMainGroup.firstChild)
  snapshot()
}

// ── 锁定/解锁 ──

const lockSelected = () => {
  if (!selectedElement || props.runtime) return
  selectedElement.setAttribute('data-locked', 'true')
  selectedElement.style.cursor = 'default'
  snapshot()
}

const unlockSelected = () => {
  if (!selectedElement || props.runtime) return
  selectedElement.removeAttribute('data-locked')
  selectedElement.style.cursor = 'move'
  snapshot()
}

const isLocked = () => {
  return selectedElement ? selectedElement.getAttribute('data-locked') === 'true' : false
}

// ── 复制 ──

const copySelected = () => {
  if (!selectedElement || !svgMainGroup || props.runtime) return
  const clone = selectedElement.cloneNode(true) as SVGElement
  // 修改 ID 避免冲突
  const oldId = clone.getAttribute('id') || ''
  const newId = oldId.replace(/_\d+$/, '') + '_' + Date.now()
  clone.setAttribute('id', newId)
  // 偏移位置
  const transform = clone.getAttribute('transform') || ''
  const match = transform.match(/translate\(([^,]+),([^)]+)\)/)
  if (match) {
    const nx = parseFloat(match[1]) + 20
    const ny = parseFloat(match[2]) + 20
    clone.setAttribute('transform', `translate(${nx},${ny})`)
  }
  svgMainGroup.appendChild(clone)
  selectElement(clone)
  snapshot()
}

// ── 对齐 ──

const alignLeft = () => { /* TODO: SVG 对齐逻辑 */ }
const alignRight = () => { /* TODO */ }
const alignTop = () => { /* TODO */ }
const alignBottom = () => { /* TODO */ }
const alignCenterH = () => { /* TODO */ }
const alignCenterV = () => { /* TODO */ }

// ── 运行时数据绑定 ──

/**
 * 更新绑定图元的值
 * 参照 FUXA GaugesManager.processValue 架构
 */
const updateBoundValue = (
  elementId: string,
  bindTarget: string,
  newValue: any,
  prop: string = 'text'
) => {
  if (!svgMainGroup) return

  // 查找目标图元
  const target = elementId ? svgMainGroup.querySelector(`#${elementId}`) : svgMainGroup
  if (!target) return

  // 遍历所有带 data-bind-target 的子元素
  const bindableElements = target.querySelectorAll(`[data-bind-target="${bindTarget}"]`)
  bindableElements.forEach((el) => {
    const bindProp = el.getAttribute('data-bind-prop') || prop
    applyValueToElement(el as SVGElement, bindProp, newValue)
  })

  // 也检查顶层元素
  if (target.getAttribute('data-bind-target') === bindTarget) {
    const bindProp = target.getAttribute('data-bind-prop') || prop
    applyValueToElement(target as SVGElement, bindProp, newValue)
  }
}

/**
 * 将值应用到 SVG 元素（FUXA processValue 核心逻辑）
 */
const applyValueToElement = (el: SVGElement, prop: string, value: any) => {
  switch (prop) {
    case 'text': {
      if (el.tagName === 'text' || el.tagName === 'tspan') {
        el.textContent = String(value)
      }
      break
    }
    case 'fill': {
      el.setAttribute('fill', String(value))
      break
    }
    case 'stroke': {
      el.setAttribute('stroke', String(value))
      break
    }
    case 'width': {
      if (el.tagName === 'rect') {
        el.setAttribute('width', String(Math.max(0, Number(value))))
      }
      break
    }
    case 'height': {
      if (el.tagName === 'rect') {
        el.setAttribute('height', String(Math.max(0, Number(value))))
      }
      break
    }
    case 'cx': {
      if (el.tagName === 'circle') {
        el.setAttribute('cx', String(value))
      }
      break
    }
    case 'cy': {
      if (el.tagName === 'circle') {
        el.setAttribute('cy', String(value))
      }
      break
    }
    case 'r': {
      if (el.tagName === 'circle') {
        el.setAttribute('r', String(Math.max(0, Number(value))))
      }
      break
    }
    case 'rotate': {
      // 获取元素中心点，绕中心旋转
      const parent = el.parentElement
      if (parent) {
        try {
          const bbox = (parent as unknown as SVGGElement).getBBox()
          const cx = bbox.x + bbox.width / 2
          const cy = bbox.y + bbox.height / 2
          el.setAttribute('transform', `rotate(${value}, ${cx}, ${cy})`)
        } catch {
          el.setAttribute('transform', `rotate(${value})`)
        }
      }
      break
    }
    case 'pointer-rotate': {
      // 表盘指针旋转
      const parentG = el.parentElement
      if (parentG) {
        try {
          const bbox = (parentG as unknown as SVGGElement).getBBox()
          const cx = bbox.x + bbox.width / 2
          const cy = bbox.y + bbox.height / 2
          // 映射 value (0~1) 到角度 (-135~135)
          const numVal = Number(value) || 0
          const angle = -135 + numVal * 270
          el.setAttribute('transform', `rotate(${angle}, ${cx}, ${cy})`)
        } catch {
          // fallback
        }
      }
      break
    }
    case 'animate': {
      // 管道流动动画 - 由 startFlowAnimation() 驱动 CSS
      break
    }
    case 'opacity': {
      el.setAttribute('opacity', String(value))
      break
    }
  }
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

const getSelectedTransform = () => {
  if (!selectedElement) return { x: 0, y: 0, scaleX: 1, scaleY: 1, angle: 0, opacity: 1 }
  const transform = selectedElement.getAttribute('transform') || ''
  const match = transform.match(/translate\(([^,]+),([^)]+)\)/)
  return {
    x: match ? parseFloat(match[1]) : 0,
    y: match ? parseFloat(match[2]) : 0,
    scaleX: 1,
    scaleY: 1,
    angle: 0,
    opacity: parseFloat(selectedElement.getAttribute('opacity') || '1')
  }
}

const setSelectedTransform = (prop: string, value: any) => {
  if (!selectedElement) return
  if (prop === 'left' || prop === 'top') {
    const current = getSelectedTransform()
    if (prop === 'left') current.x = value
    if (prop === 'top') current.y = value
    selectedElement.setAttribute('transform', `translate(${current.x},${current.y})`)
    updateSelectionBox()
  } else if (prop === 'opacity') {
    selectedElement.setAttribute('opacity', String(value))
  }
}

// ── 绑定信息读写 ──

/** 设置图元的绑定信息 */
const setBinding = (elementId: string, bindTarget: string, deviceId: number, tagId: number, tagName: string, prop: string) => {
  if (!svgMainGroup) return
  const el = svgMainGroup.querySelector(`#${elementId}`)
  if (!el) return
  el.setAttribute('data-bind-target', bindTarget)
  el.setAttribute('data-bind-prop', prop)
  el.setAttribute('data-bind-device-id', String(deviceId))
  el.setAttribute('data-bind-tag-id', String(tagId))
  el.setAttribute('data-bind-tag-name', tagName)
  snapshot()
}

/** 获取画布中所有绑定信息 */
const getAllBindings = (): Array<{
  elementId: string
  bindTarget: string
  deviceId: number
  tagId: number
  tagName: string
  prop: string
}> => {
  if (!svgMainGroup) return []
  const bindings: Array<any> = []
  const elements = svgMainGroup.querySelectorAll('[data-bind-target]')
  elements.forEach((el) => {
    const svgEl = el as SVGElement
    const parentGroup = svgEl.closest('g[type]') || svgEl
    bindings.push({
      elementId: parentGroup.getAttribute('id') || svgEl.getAttribute('id') || '',
      bindTarget: svgEl.getAttribute('data-bind-target') || '',
      deviceId: parseInt(svgEl.getAttribute('data-bind-device-id') || '0'),
      tagId: parseInt(svgEl.getAttribute('data-bind-tag-id') || '0'),
      tagName: svgEl.getAttribute('data-bind-tag-name') || '',
      prop: svgEl.getAttribute('data-bind-prop') || 'text'
    })
  })
  return bindings
}

// ── 序列化（兼容旧版 Fabric JSON 格式） ──

/** 导出为 JSON 格式（兼容后端 config_json 字段） */
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

/** 从 JSON 加载（兼容旧版 Fabric JSON 和新版 SVG JSON） */
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

// ── 生命周期 ──

onMounted(() => {
  initSvgCanvas()
})

onUnmounted(() => {
  stopFlowAnimation()
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
  updateBoundValue,
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
  getSelectedTransform,
  setSelectedTransform,
  setBinding,
  getAllBindings,
  alignLeft,
  alignRight,
  alignTop,
  alignBottom,
  alignCenterH,
  alignCenterV,
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
