/**
 * GaugesManager - FUXA 风格图元引擎
 *
 * 核心职责（参照 FUXA gauges.component.ts）：
 * 1. 图元类型注册与识别（通过 SVG 元素的 type 属性）
 * 2. 信号绑定（Signal → GaugeSettings 映射）
 * 3. 值处理路由（processValue：位掩码 → 范围颜色 → 动作执行）
 * 4. DOM 操作（walkTreeNode 设置 fill/stroke/transform 等）
 */

// (SvgWidgetProperty/SvgWidgetRange/SvgWidgetAction are type-only used by svg-widgets.ts, not imported here)

// ── 类型定义 ──

export interface GaugeSettings {
  id: string
  type: string
  name: string
  label: string
  property: GaugeProperty
  hide: boolean
  lock: boolean
}

export interface GaugeProperty {
  variableId: string
  variableValue: string
  bitmask: number
  ranges: GaugeRangeProperty[]
  events: GaugeEvent[]
  actions: GaugeAction[]
  readonly: boolean
}

export interface GaugeRangeProperty {
  min: number
  max: number
  fillColor: string
  strokeColor: string
}

export interface GaugeEvent {
  type: 'click' | 'dblclick' | 'change'
  action: string
  param?: any
}

export interface GaugeAction {
  type: 'hide' | 'show' | 'blink' | 'clockwise' | 'anticlockwise' | 'rotate' | 'move' | 'stop'
  targetId?: string
  min?: number
  max?: number
  angle?: number
  toX?: number
  toY?: number
}

export interface SignalValue {
  id: string
  value: number | string | boolean
  timestamp: number
}

// ── 图元类型注册表 ──

const GAUGE_TYPE_PREFIX = 'svg-ext-'

/**
 * 检查元素是否为图元
 * FUXA: GaugesManager.isGauge(type) → type.startsWith('svg-ext-')
 */
export const isGauge = (element: SVGElement): boolean => {
  const type = element.getAttribute('type') || ''
  return type.startsWith(GAUGE_TYPE_PREFIX)
}

/**
 * 获取图元类型标签
 */
export const getGaugeType = (element: SVGElement): string => {
  return element.getAttribute('type') || ''
}

// ── 位掩码处理 ──

/**
 * 检查位掩码（FUXA: GaugeBaseComponent.checkBitmask）
 * @param bitmask 位掩码值（0 表示不使用掩码）
 * @param value 原始值
 * @returns 处理后的值
 */
export const checkBitmask = (bitmask: number, value: number): number => {
  if (!bitmask || bitmask === 0) return value
  // 提取指定位的值
  const bitPosition = Math.log2(bitmask)
  if (Number.isInteger(bitPosition)) {
    return (value >> bitPosition) & 1
  }
  return (value & bitmask) !== 0 ? 1 : 0
}

// ── 范围颜色映射 ──

/**
 * 计算范围颜色映射（FUXA: ShapesComponent.processValue → ranges loop）
 * @param value 当前值
 * @param ranges 范围定义
 * @returns 匹配的填充色和描边色，null 表示无匹配
 */
export const evaluateRanges = (
  value: number,
  ranges: GaugeRangeProperty[]
): { fillColor: string; strokeColor: string } | null => {
  if (!ranges || ranges.length === 0) return null

  for (const range of ranges) {
    if (value >= range.min && value <= range.max) {
      return {
        fillColor: range.fillColor,
        strokeColor: range.strokeColor
      }
    }
  }
  return null
}

// ── DOM 树遍历设置属性 ──

/**
 * 遍历 SVG DOM 树设置属性（FUXA: GaugeBaseComponent.walkTreeNodeToSetAttribute）
 * @param node SVG 元素节点
 * @param attributeName 属性名（如 fill、stroke）
 * @param value 属性值
 * @param stopId 停止遍历的元素 ID（可选）
 */
export const walkTreeNodeToSetAttribute = (
  node: SVGElement,
  attributeName: string,
  value: string,
  stopId?: string
) => {
  // 跳过有 data-bind-target 的子元素（避免覆盖绑定值）
  if (node.getAttribute('data-bind-target') && node !== node) {
    return
  }

  // 不覆盖 currentColor 等特殊值
  const currentVal = node.getAttribute(attributeName)
  if (currentVal && currentVal !== 'none' && currentVal !== 'transparent') {
    node.setAttribute(attributeName, value)
  }

  // 递归子节点
  const children = node.children
  for (let i = 0; i < children.length; i++) {
    const child = children[i] as SVGElement
    if (stopId && child.getAttribute('id') === stopId) continue
    walkTreeNodeToSetAttribute(child, attributeName, value, stopId)
  }
}

// ── 动作执行 ──

/** 活跃的动画/闪烁定时器 */
const activeTimers = new Map<string, ReturnType<typeof setInterval>>()

/**
 * 执行图元动作（FUXA: processAction）
 * @param action 动作定义
 * @param svgElement SVG 图元元素
 * @param value 当前信号值
 */
export const processAction = (
  action: GaugeAction,
  svgElement: SVGElement,
  value: number
) => {
  const gaugeId = svgElement.getAttribute('id') || ''
  const timerKey = `${gaugeId}_${action.type}`

  switch (action.type) {
    case 'hide': {
      svgElement.setAttribute('visibility', 'hidden')
      break
    }
    case 'show': {
      svgElement.setAttribute('visibility', 'visible')
      break
    }
    case 'blink': {
      // 闪烁：在原始颜色和警告色之间交替
      let isOriginal = true
      const originalFill = svgElement.getAttribute('fill') || '#2a5a8a'
      const blinkFill = '#ffff00'

      // 清除已有定时器
      if (activeTimers.has(timerKey)) {
        clearInterval(activeTimers.get(timerKey)!)
      }

      const timer = setInterval(() => {
        if (isOriginal) {
          walkTreeNodeToSetAttribute(svgElement, 'fill', blinkFill)
        } else {
          walkTreeNodeToSetAttribute(svgElement, 'fill', originalFill)
        }
        isOriginal = !isOriginal
      }, 500)

      activeTimers.set(timerKey, timer)
      break
    }
    case 'clockwise': {
      // 顺时针旋转（CSS 动画）
      svgElement.style.animation = 'spin-cw 3s linear infinite'
      break
    }
    case 'anticlockwise': {
      svgElement.style.animation = 'spin-ccw 3s linear infinite'
      break
    }
    case 'rotate': {
      // 按值范围映射到角度
      const min = action.min ?? 0
      const max = action.max ?? 100
      const angle = action.angle ?? 360
      const clampedValue = Math.max(min, Math.min(max, value))
      const ratio = (clampedValue - min) / (max - min)
      const deg = ratio * angle
      try {
        const bbox = (svgElement as SVGGElement).getBBox()
        const cx = bbox.x + bbox.width / 2
        const cy = bbox.y + bbox.height / 2
        svgElement.setAttribute('transform', `rotate(${deg}, ${cx}, ${cy})`)
      } catch {
        svgElement.setAttribute('transform', `rotate(${deg})`)
      }
      break
    }
    case 'move': {
      // 移动到指定位置
      if (action.toX !== undefined && action.toY !== undefined) {
        svgElement.setAttribute('transform', `translate(${action.toX},${action.toY})`)
      }
      break
    }
    case 'stop': {
      // 停止所有动画
      svgElement.style.animation = ''
      if (activeTimers.has(timerKey)) {
        clearInterval(activeTimers.get(timerKey)!)
        activeTimers.delete(timerKey)
      }
      break
    }
  }
}

/**
 * 清理图元的所有活跃定时器
 */
export const cleanupGauge = (gaugeId: string) => {
  for (const [key, timer] of activeTimers.entries()) {
    if (key.startsWith(gaugeId)) {
      clearInterval(timer)
      activeTimers.delete(key)
    }
  }
}

/**
 * 清理所有活跃定时器
 */
export const cleanupAll = () => {
  for (const timer of activeTimers.values()) {
    clearInterval(timer)
  }
  activeTimers.clear()
}

// ── processValue 核心 ──

/**
 * 处理信号值并更新图元（FUXA: GaugesManager.processValue）
 *
 * 处理链路：位掩码 → 范围颜色映射 → 动作执行
 *
 * @param svgElement SVG 图元元素
 * @param gaugeType 图元类型标签
 * @param property 图元属性（含 ranges 和 actions）
 * @param signalValue 信号值
 */
export const processValue = (
  svgElement: SVGElement,
  _gaugeType: string,
  property: GaugeProperty | null,
  signalValue: SignalValue
) => {
  if (!property) return

  let value = typeof signalValue.value === 'number'
    ? signalValue.value
    : parseFloat(String(signalValue.value)) || 0

  // 1. 位掩码处理
  value = checkBitmask(property.bitmask, value)

  // 2. 范围颜色映射
  if (property.ranges && property.ranges.length > 0) {
    const colors = evaluateRanges(value, property.ranges)
    if (colors) {
      walkTreeNodeToSetAttribute(svgElement, 'fill', colors.fillColor)
      walkTreeNodeToSetAttribute(svgElement, 'stroke', colors.strokeColor)
    }
  }

  // 3. 动作执行
  if (property.actions && property.actions.length > 0) {
    for (const action of property.actions) {
      processAction(action, svgElement, value)
    }
  }
}

// ── 信号→图元映射管理 ──

/**
 * 信号映射表（FUXA: hmiService.gaugesMap）
 * key: signalId (格式: "deviceId:tagName")
 * value: 图元设置列表
 */
const signalGaugeMap = new Map<string, GaugeSettings[]>()

/**
 * 注册信号到图元的映射
 */
export const bindSignalToGauge = (signalId: string, gauge: GaugeSettings) => {
  const existing = signalGaugeMap.get(signalId) || []
  if (!existing.find(g => g.id === gauge.id)) {
    existing.push(gauge)
  }
  signalGaugeMap.set(signalId, existing)
}

/**
 * 移除信号映射
 */
export const unbindSignalFromGauge = (signalId: string, gaugeId: string) => {
  const existing = signalGaugeMap.get(signalId)
  if (existing) {
    const filtered = existing.filter(g => g.id !== gaugeId)
    if (filtered.length === 0) {
      signalGaugeMap.delete(signalId)
    } else {
      signalGaugeMap.set(signalId, filtered)
    }
  }
}

/**
 * 获取信号绑定的所有图元
 */
export const getGaugesBySignal = (signalId: string): GaugeSettings[] => {
  return signalGaugeMap.get(signalId) || []
}

/**
 * 清空所有信号映射
 */
export const clearAllSignalMappings = () => {
  signalGaugeMap.clear()
}

/**
 * 处理信号变更（FUXA: handleSignal）
 * 当 WebSocket 收到数据更新时调用
 */
export const handleSignalChange = (
  signalId: string,
  signalValue: SignalValue,
  svgRootElement: SVGGElement
) => {
  const gauges = getGaugesBySignal(signalId)
  for (const gauge of gauges) {
    const svgEl = svgRootElement.querySelector(`#${gauge.id}`)
    if (svgEl) {
      processValue(svgEl as SVGElement, gauge.type, gauge.property, signalValue)
    }
  }
}

// ── 从 SVG DOM 自动扫描绑定 ──

/**
 * 从 SVG DOM 中的 data-* 属性自动构建 GaugeSettings
 * 扫描所有带 data-bind-target 的元素，自动注册信号映射
 *
 * @param svgRootElement SVG 主组元素
 * @returns 注册的图元数量
 */
export const scanAndBindFromDOM = (svgRootElement: SVGGElement): number => {
  let count = 0
  const elements = svgRootElement.querySelectorAll('[data-bind-target]')
  elements.forEach((el) => {
    const svgEl = el as SVGElement
    const id = svgEl.getAttribute('id')
    if (!id) return

    const target = svgEl.getAttribute('data-bind-target') || ''
    const tagName = svgEl.getAttribute('data-bind-tag-name') || ''
    const deviceId = svgEl.getAttribute('data-bind-device-id') || ''
    const tagId = svgEl.getAttribute('data-bind-tag-id') || ''
    const gaugeType = svgEl.getAttribute('type') || ''

    // 解析 data-value-process 属性
    let property: GaugeProperty = {
      variableId: `${deviceId}:${tagId}`,
      variableValue: '',
      bitmask: 0,
      ranges: [],
      events: [],
      actions: [],
      readonly: false
    }

    const vpStr = svgEl.getAttribute('data-value-process')
    if (vpStr) {
      try {
        const vp = JSON.parse(vpStr)
        property.bitmask = vp.bitMask ?? 0
        property.ranges = (vp.ranges || []).map((r: any) => ({
          min: r.min ?? 0,
          max: r.max ?? 100,
          fillColor: r.color ?? '#4ac080',
          strokeColor: r.color ?? '#4ac080'
        }))
        property.actions = (vp.actions || []).map((a: any) => ({
          type: a.actionType || 'show',
          targetId: a.targetId || ''
        }))
      } catch {
        // 忽略解析错误
      }
    }

    const gauge: GaugeSettings = {
      id,
      type: gaugeType,
      name: target,
      label: tagName,
      property,
      hide: false,
      lock: false
    }

    // 注册信号映射
    const signalId = `${deviceId}:${tagName}`
    bindSignalToGauge(signalId, gauge)
    count++
  })
  return count
}
