/**
 * GaugesManager - FUXA 风格图元运行时引擎（v2，items 字典驱动）
 *
 * 核心职责（参照 FUXA gauges.component.ts）：
 * 1. 信号索引：signalId("deviceId:tagName") → 绑定的 (图元, 绑定域, 配置)
 * 2. 值处理：位掩码 → 范围匹配 → 格式化 → 应用 DOM
 * 3. 静态值：未绑定域用 variableValue 渲染
 *
 * 绑定域 = SVG 内带 [data-bind-target] 的子元素；应用方式由 data-bind-prop 决定
 */
import type { BindingDef, DictionaryGaugeSettings, GaugeRangeProperty } from './hmi'
import { formatValue } from './hmi'

// ── 位掩码处理 ──

/**
 * 检查位掩码（FUXA: GaugeBaseComponent.checkBitmask）
 * @param bitmask 位掩码值（0 表示不使用掩码）
 * @param value 原始值
 * @returns 处理后的值
 */
export const checkBitmask = (bitmask: number, value: number): number => {
  if (!bitmask || bitmask === 0) return value
  const bitPosition = Math.log2(bitmask)
  if (Number.isInteger(bitPosition)) {
    return (value >> bitPosition) & 1
  }
  return (value & bitmask) !== 0 ? 1 : 0
}

// ── 范围匹配 ──

/**
 * 匹配值域范围（FUXA: ShapesComponent.processValue → ranges loop）
 * @param value 当前值
 * @param ranges 范围定义
 * @returns 第一个匹配的范围，无匹配返回 null
 */
export const matchRange = (value: number, ranges: GaugeRangeProperty[]): GaugeRangeProperty | null => {
  if (!ranges || ranges.length === 0) return null
  for (const range of ranges) {
    if (value >= range.min && value <= range.max) {
      return range
    }
  }
  return null
}

// ── DOM 原子应用 ──

/**
 * 将值应用到单个 SVG 元素（FUXA processValue 核心逻辑）
 * @param prop data-bind-prop：text/fill/stroke/width/height/cx/cy/r/rotate/pointer-rotate/opacity
 */
export const applyValueToElement = (el: SVGElement, prop: string, value: any) => {
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
      // 表盘指针旋转：映射 value 到角度范围
      const parentG = el.parentElement
      if (parentG) {
        try {
          const bbox = (parentG as unknown as SVGGElement).getBBox()
          const cx = bbox.x + bbox.width / 2
          const cy = bbox.y + bbox.height / 2
          const numVal = Number(value) || 0
          const angle = -135 + numVal * 270
          el.setAttribute('transform', `rotate(${angle}, ${cx}, ${cy})`)
        } catch {
          // fallback
        }
      }
      break
    }
    case 'opacity': {
      el.setAttribute('opacity', String(value))
      break
    }
  }
}

// ── 绑定应用 ──

export interface RuntimeContext {
  svgRoot: SVGGElement
  items: DictionaryGaugeSettings
  index: Map<string, BoundTarget[]> | null
}

export interface BoundTarget {
  elementId: string
  target: string
  def: BindingDef
}

/**
 * 构建信号索引：signalId("deviceId:tagName") → 绑定目标列表
 */
export const buildSignalIndex = (items: DictionaryGaugeSettings): Map<string, BoundTarget[]> => {
  const index = new Map<string, BoundTarget[]>()
  for (const gauge of Object.values(items)) {
    for (const [target, def] of Object.entries(gauge.bindings || {})) {
      if (!def.variableId) continue
      const list = index.get(def.variableId) || []
      list.push({ elementId: gauge.id, target, def })
      index.set(def.variableId, list)
    }
  }
  return index
}

/**
 * 应用一个绑定域到图元 DOM
 * @param raw 原始值（数字/字符串/undefined=无值不更新文本）
 * @param trendHandler prop=trend 时的回调（趋势图元缓冲）
 */
export const applyBinding = (
  svgRoot: SVGGElement,
  elementId: string,
  target: string,
  def: BindingDef,
  raw: number | string | boolean | undefined,
  trendHandler?: (elementId: string, raw: number) => void
) => {
  const group = svgRoot.querySelector(`#${elementId}`)
  if (!group) return

  const els = group.querySelectorAll(`[data-bind-target="${target}"]`)
  if (els.length === 0) return

  const num = typeof raw === 'number' ? raw : parseFloat(String(raw ?? ''))
  const v = checkBitmask(def.bitmask, Number.isNaN(num) ? 0 : num)
  const range = matchRange(v, def.ranges)

  els.forEach((el) => {
    const svgEl = el as SVGElement
    const prop = svgEl.getAttribute('data-bind-prop') || 'text'

    if (prop === 'trend') {
      if (trendHandler && !Number.isNaN(v)) trendHandler(elementId, v)
      return
    }
    if (prop === 'text') {
      if (range && range.text) {
        svgEl.textContent = range.text
      } else if (raw !== undefined) {
        svgEl.textContent = formatValue(raw, def.format)
      }
      return
    }
    if (prop === 'fill') {
      if (range && range.color) svgEl.setAttribute('fill', range.color)
      return
    }
    if (prop === 'stroke') {
      if (range && range.stroke) svgEl.setAttribute('stroke', range.stroke)
      return
    }
    // 数值型绑定（rotate/width/height/cx/cy/r/opacity/pointer-rotate）
    applyValueToElement(svgEl, prop, v)
  })
}

/**
 * 处理信号值并更新所有绑定图元（FUXA: GaugesManager.processValue）
 */
export const applySignalValue = (
  ctx: RuntimeContext,
  signalId: string,
  raw: number | string | boolean,
  trendHandler?: (elementId: string, raw: number) => void
) => {
  const targets = ctx.index?.get(signalId) || []
  for (const t of targets) {
    applyBinding(ctx.svgRoot, t.elementId, t.target, t.def, raw, trendHandler)
  }
}

/**
 * 渲染未绑定域的静态值（variableValue）
 * 运行时加载完成后调用
 */
export const applyStaticValues = (
  ctx: RuntimeContext,
  trendHandler?: (elementId: string, raw: number) => void
) => {
  for (const gauge of Object.values(ctx.items)) {
    for (const [target, def] of Object.entries(gauge.bindings || {})) {
      if (def.variableId || def.variableValue === '') continue
      applyBinding(ctx.svgRoot, gauge.id, target, def, def.variableValue, trendHandler)
    }
  }
}