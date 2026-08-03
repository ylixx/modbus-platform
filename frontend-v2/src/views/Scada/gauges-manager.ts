/**
 * GaugesManager — 照搬 FUXA 架构的图元引擎
 *
 * 核心职责：
 * 1. 信号-Gauge 映射管理（哪个信号绑定到哪些图元）
 * 2. processValue 分发（信号到达 → 查找图元 → 按类型分发处理）
 * 3. 运行时事件绑定（click → openPage / setValue 等）
 * 4. Actions 执行（blink / rotate / move / hide / show / color）
 */

import { SVG } from '@svgdotjs/svg.js'
import type { GaugeSettings, GaugeRangeProperty, GaugeAction, DictionaryGaugeSettings } from './hmi'

// ── 信号变量 ──

export interface Variable {
  id: string
  value: any
}

// ── 图元运行状态 ──

export interface GaugeStatus {
  variablesValue: Record<string, any>
  blinkTimer: ReturnType<typeof setInterval> | null
  rotationAngle: number
  isVisible: boolean
}

function createGaugeStatus(): GaugeStatus {
  return { variablesValue: {}, blinkTimer: null, rotationAngle: 0, isVisible: true }
}

// ── 信号-Gauge 映射 ──

// { [signalId]: GaugeSettings[] }
const signalGaugeMap: Record<string, GaugeSettings[]> = {}

// { [gaugeId]: GaugeStatus }
const gaugeStatusMap: Record<string, GaugeStatus> = {}

// ── 映射管理 ──

export function bindSignalToGauge(signalId: string, gauge: GaugeSettings): void {
  if (!signalGaugeMap[signalId]) signalGaugeMap[signalId] = []
  if (!signalGaugeMap[signalId].find((g) => g.id === gauge.id)) {
    signalGaugeMap[signalId].push(gauge)
  }
  if (!gaugeStatusMap[gauge.id]) gaugeStatusMap[gauge.id] = createGaugeStatus()
}

export function unbindSignalFromGauge(signalId: string, gaugeId: string): void {
  if (signalGaugeMap[signalId]) {
    signalGaugeMap[signalId] = signalGaugeMap[signalId].filter((g) => g.id !== gaugeId)
  }
}

export function clearAllSignalMappings(): void {
  for (const key of Object.keys(signalGaugeMap)) {
    delete signalGaugeMap[key]
  }
  for (const key of Object.keys(gaugeStatusMap)) {
    const st = gaugeStatusMap[key]
    if (st.blinkTimer) clearInterval(st.blinkTimer)
    delete gaugeStatusMap[key]
  }
}

export function getGaugesBySignal(signalId: string): GaugeSettings[] {
  return signalGaugeMap[signalId] || []
}

// ── DOM 扫描绑定 ──
// 照搬 FUXA loadWatch 逻辑：从 items 字典 + SVG DOM 扫描绑定

export function scanAndBindFromDOM(
  svgRootElement: SVGGElement,
  items: DictionaryGaugeSettings
): number {
  let count = 0
  for (const key in items) {
    const ga = items[key]
    if (!ga.property?.variableId) continue
    const el = svgRootElement.querySelector(`#${CSS.escape(key)}`)
    if (el) {
      bindSignalToGauge(ga.property.variableId, ga)
      count++
    }
  }
  return count
}

// ── SVG 元素查找 ──
// 照搬 FUXA getSvgElements：用 SVG.adopt 包装 DOM

export function getSvgElement(svgId: string): any | null {
  const el = document.getElementById(svgId)
  if (el && el instanceof SVGElement) {
    try {
      return (SVG as any).adopt(el)
    } catch {
      return null
    }
  }
  return null
}

// ── 位掩码检查 ──

export function checkBitmask(bitmask: number, value: number): number {
  if (bitmask > 0) {
    return (value >> (bitmask - 1)) & 1
  }
  return value
}

// ── 范围匹配 ──

export function evaluateRanges(
  value: number,
  ranges: GaugeRangeProperty[]
): { color?: string; stroke?: string; text?: string } | null {
  if (!ranges || ranges.length === 0) return null
  for (const range of ranges) {
    if (value >= range.min && value <= range.max) {
      return { color: range.color, stroke: range.stroke, text: range.text }
    }
  }
  return null
}

// ── DOM 属性遍历设置 ──

export function walkTreeNodeToSetAttribute(el: SVGElement, attr: string, value: string): void {
  const current = el.getAttribute(attr)
  if (current && current !== 'none' && current !== 'inherit') {
    el.setAttribute(attr, value)
  }
  for (let i = 0; i < el.children.length; i++) {
    const child = el.children[i]
    if (child instanceof SVGElement) {
      walkTreeNodeToSetAttribute(child, attr, value)
    }
  }
}

// ── processValue 核心分发 ──
// 照搬 FUXA GaugesManager.processValue

export function processValue(
  ga: GaugeSettings,
  svgele: any,
  sig: Variable,
  gaugeStatus: GaugeStatus
): void {
  gaugeStatus.variablesValue[sig.id] = sig.value
  const pro = ga.property
  let value = checkBitmask(pro.bitmask, Number(sig.value))

  // 1. 基于图元类型分发
  const type = ga.type

  if (type.startsWith('svg-ext-value') || type.startsWith('svg-ext-shapes-text')) {
    // Value / Text → 更新文本
    const displayValue = typeof value === 'number' ? value.toFixed(1) : String(sig.value)
    const textNodes = svgele.node?.querySelectorAll('text, tspan') || []
    if (textNodes.length > 0) {
      textNodes.forEach((t: SVGElement) => {
        t.textContent = displayValue
      })
    } else if (svgele.node) {
      const txt = svgele.node.querySelector('text') || svgele.node
      txt.textContent = displayValue
    }
  } else if (type.startsWith('svg-ext-led') || type.startsWith('svg-ext-semaphore')) {
    // LED / Semaphore → 更新颜色
    processRanges(svgele, value, pro.ranges)
  } else if (type.startsWith('svg-ext-gauge')) {
    // Gauge → 更新仪表盘数值
    const displayValue = typeof value === 'number' ? value.toFixed(1) : String(sig.value)
    const textNode = svgele.node?.querySelector('text')
    if (textNode) textNode.textContent = displayValue
  } else if (type.startsWith('svg-ext-progress')) {
    // Progress → 更新进度宽度
    processRanges(svgele, value, pro.ranges)
    const pct = Math.max(0, Math.min(100, Number(sig.value)))
    const bar = svgele.node?.querySelector('rect:nth-child(2)')
    if (bar) {
      const totalW = parseFloat(
        bar.parentElement?.getAttribute('width') || bar.getAttribute('width') || '200'
      )
      bar.setAttribute('width', String((totalW * pct) / 100))
    }
  } else if (type.startsWith('svg-ext-pipe')) {
    // Pipe → 流动动画控制
    const pipeEl = svgele.node?.querySelector('.pipe-flow')
    if (pipeEl) {
      pipeEl.setAttribute('stroke', value > 0 ? '#3b82f6' : '#4b5563')
    }
  } else if (type.startsWith('svg-ext-switch')) {
    // Switch → 切换状态
    const knob = svgele.node?.querySelector('circle')
    if (knob) {
      const w = parseFloat(svgele.node?.getAttribute('width') || '60')
      knob.setAttribute('cx', value > 0 ? String(w * 0.75) : String(w * 0.25))
      const bg = svgele.node?.querySelector('rect')
      if (bg) bg.setAttribute('fill', value > 0 ? '#3b82f6' : '#374151')
    }
  } else {
    // 默认：Shapes 通用图元 → 处理 ranges + actions
    processRanges(svgele, value, pro.ranges)
  }

  // 2. 处理 actions（数据驱动动作）
  if (pro.actions && pro.actions.length > 0) {
    processActions(ga, svgele, sig, gaugeStatus)
  }
}

// ── 范围颜色/文本映射 ──

function processRanges(svgele: any, value: number, ranges: GaugeRangeProperty[]): void {
  if (!ranges || ranges.length === 0) return
  const match = evaluateRanges(value, ranges)
  if (match) {
    if (match.color) {
      walkTreeNodeToSetAttribute(svgele.node || svgele, 'fill', match.color)
    }
    if (match.stroke) {
      svgele.node?.setAttribute('stroke', match.stroke)
    }
    if (match.text) {
      const textNode = svgele.node?.querySelector('text') || svgele.node
      if (textNode) textNode.textContent = match.text
    }
  }
}

// ── Actions 处理 ──

function processActions(
  ga: GaugeSettings,
  svgele: any,
  sig: Variable,
  gaugeStatus: GaugeStatus
): void {
  const pro = ga.property
  for (const act of pro.actions) {
    const actValue = checkBitmask(act.bitmask || 0, Number(sig.value))
    const inRange = actValue >= act.range.min && actValue <= act.range.max

    switch (act.type) {
      case 'hide':
        if (inRange) runActionHide(svgele, gaugeStatus)
        else runActionShow(svgele, gaugeStatus)
        break
      case 'show':
        if (inRange) runActionShow(svgele, gaugeStatus)
        else runActionHide(svgele, gaugeStatus)
        break
      case 'blink':
        checkActionBlink(svgele, act, gaugeStatus, inRange)
        break
      case 'color':
        if (inRange) {
          if (act.options?.fill)
            walkTreeNodeToSetAttribute(svgele.node || svgele, 'fill', act.options.fill)
          if (act.options?.stroke) svgele.node?.setAttribute('stroke', act.options.stroke)
        }
        break
      case 'rotate': {
        const minA = act.options?.minAngle || 0
        const maxA = act.options?.maxAngle || 360
        const range = act.range.max - act.range.min || 1
        const angle = minA + ((actValue - act.range.min) / range) * (maxA - minA)
        try {
          svgele.rotate(angle)
        } catch {
          /* ignore */
        }
        break
      }
      case 'clockwise':
        if (inRange) startRotation(svgele, gaugeStatus, 3)
        else stopRotation(svgele, gaugeStatus)
        break
      case 'anticlockwise':
        if (inRange) startRotation(svgele, gaugeStatus, -3)
        else stopRotation(svgele, gaugeStatus)
        break
      case 'move':
        if (inRange && act.options) {
          try {
            svgele
              .animate(act.options.duration || 500, 0, 'now')
              .move(act.options.toX || 0, act.options.toY || 0)
          } catch {
            /* fallback */
          }
        }
        break
      case 'stop':
        if (inRange) {
          stopRotation(svgele, gaugeStatus)
          if (gaugeStatus.blinkTimer) {
            clearInterval(gaugeStatus.blinkTimer)
            gaugeStatus.blinkTimer = null
          }
        }
        break
    }
  }
}

// ── Action 实现函数 ──

function runActionHide(svgele: any, status: GaugeStatus): void {
  try {
    svgele.hide()
    status.isVisible = false
  } catch {
    /* ignore */
  }
}

function runActionShow(svgele: any, status: GaugeStatus): void {
  try {
    svgele.show()
    status.isVisible = true
  } catch {
    /* ignore */
  }
}

function checkActionBlink(
  svgele: any,
  act: GaugeAction,
  status: GaugeStatus,
  inRange: boolean
): void {
  if (status.blinkTimer) {
    clearInterval(status.blinkTimer)
    status.blinkTimer = null
  }
  if (inRange) {
    let toggle = false
    const fillA = act.options?.fillA || '#ff0000'
    const fillB = act.options?.fillB || '#000000'
    const interval = act.options?.interval || 500
    status.blinkTimer = setInterval(() => {
      toggle = !toggle
      const color = toggle ? fillA : fillB
      walkTreeNodeToSetAttribute(svgele.node || svgele, 'fill', color)
    }, interval)
  }
}

function startRotation(svgele: any, status: GaugeStatus, speed: number): void {
  status.rotationAngle = (status.rotationAngle || 0) + speed
  try {
    svgele.rotate(status.rotationAngle)
  } catch {
    /* ignore */
  }
}

function stopRotation(_svgele: any, _status: GaugeStatus): void {
  // Rotation stops naturally when not called
}

// ── 事件系统 ──

export interface RuntimeEventCallback {
  (action: string, param: string, options?: any): void
}

export function bindGaugeEvents(
  svgRootElement: SVGGElement,
  items: DictionaryGaugeSettings,
  callback: RuntimeEventCallback
): void {
  for (const key in items) {
    const ga = items[key]
    if (!ga.property?.events || ga.property.events.length === 0) continue

    const el = svgRootElement.querySelector(`#${CSS.escape(key)}`) as SVGElement | null
    if (!el) continue

    for (const event of ga.property.events) {
      const handler = (ev: Event) => {
        ev.stopPropagation()
        callback(event.action, event.actparam, event.actoptions)
      }

      switch (event.type) {
        case 'click':
          el.addEventListener('click', handler)
          break
        case 'dblclick':
          el.addEventListener('dblclick', handler)
          break
        case 'mousedown':
          el.addEventListener('mousedown', handler)
          break
        case 'mouseover':
          el.addEventListener('mouseover', handler)
          break
      }
    }
  }
}

// ── 信号处理入口 ──
// 照搬 FUXA handleSignal 链路

export function handleSignal(signalId: string, value: any, svgRootElement: SVGGElement): void {
  const gas = getGaugesBySignal(signalId)
  if (!gas || gas.length === 0) return

  const sig: Variable = { id: signalId, value }

  for (const ga of gas) {
    const status = gaugeStatusMap[ga.id] || createGaugeStatus()
    gaugeStatusMap[ga.id] = status

    // 检查值是否变化
    if (status.variablesValue[signalId] === value) continue
    status.variablesValue[signalId] = value

    // 获取 SVG 元素
    const el = svgRootElement.querySelector(`#${CSS.escape(ga.id)}`)
    if (!el) continue

    const svgele = getSvgElement(ga.id)
    if (svgele) {
      processValue(ga, svgele, sig, status)
    }
  }
}

// ── 清理 ──

export function cleanupAll(): void {
  for (const key of Object.keys(gaugeStatusMap)) {
    const st = gaugeStatusMap[key]
    if (st.blinkTimer) clearInterval(st.blinkTimer)
    delete gaugeStatusMap[key]
  }
}
