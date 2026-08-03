/**
 * HMI 数据模型 — 照搬 FUXA 架构
 *
 * 核心设计："SVG字符串 + items字典"双层存储
 * - svgcontent: 完整 SVG XML（所有图元的视觉表现：位置、大小、形状、颜色）
 * - items: { [svgElementId]: GaugeSettings } 字典（数据绑定、事件、动作等元数据）
 *
 * SVG 元素通过 id 属性与 items 字典关联
 */

// ── 唯一 ID 生成 ──

let _idCounter = 0
export function genId(prefix = 'svg'): string {
  return `${prefix}_${Date.now().toString(36)}_${(++_idCounter).toString(36)}`
}

// ── 画面规格 ──

export interface DocProfile {
  width: number
  height: number
  bkcolor: string // 背景色，如 '#1a1a2eff' (RGBA)
  gridType: 'none' | 'fixed' | 'responsive'
  gridSize: number // 网格大小，0=无
  viewRenderDelay: number
}

export function defaultProfile(): DocProfile {
  return {
    width: 1920,
    height: 1080,
    bkcolor: '#1a1a2e',
    gridType: 'fixed',
    gridSize: 20,
    viewRenderDelay: 0
  }
}

// ── View 画面 ──

export interface View {
  id: string
  name: string
  profile: DocProfile
  svgcontent: string // 🔑 核心：完整SVG字符串
  items: DictionaryGaugeSettings // 🔑 核心：图元配置字典
  type: 'svg' // 画面类型
}

export function createView(name: string): View {
  return {
    id: genId('v'),
    name,
    profile: defaultProfile(),
    svgcontent: '',
    items: {},
    type: 'svg'
  }
}

// ── GaugeSettings 图元配置 ──

export interface GaugeSettings {
  id: string // = SVG元素的 id 属性
  type: string // 图元类型标签，如 'svg-ext-value', 'svg-ext-button'
  name: string // 图元实例名称
  property: GaugeProperty // 数据绑定属性
  label: string // 显示标签
  hide: boolean
  lock: boolean
}

// ── GaugeProperty 数据绑定基类 ──

export interface GaugeProperty {
  variableId: string // 绑定的Tag/信号ID
  variableValue: string // 静态初始值
  bitmask: number // 位掩码
  ranges: GaugeRangeProperty[] // 值域范围映射
  events: GaugeEvent[] // 鼠标/键盘事件
  actions: GaugeAction[] // 数据驱动动作
  readonly: boolean
}

// ── 值域范围映射 ──

export interface GaugeRangeProperty {
  min: number
  max: number
  text: string // 范围内显示文本
  color: string // 范围内填充色
  stroke: string // 范围内描边色
}

// ── 数据驱动动作 ──

export enum GaugeActionType {
  hide = 'hide',
  show = 'show',
  blink = 'blink',
  color = 'color',
  stop = 'stop',
  clockwise = 'clockwise',
  anticlockwise = 'anticlockwise',
  rotate = 'rotate',
  downup = 'downup',
  move = 'move',
  moveByTags = 'moveByTags',
  monitor = 'monitor',
  refreshImage = 'refreshImage',
  loadImage = 'loadImage',
  start = 'start',
  pause = 'pause',
  reset = 'reset'
}

export interface GaugeAction {
  variableId: string // 关联信号ID（空则使用父property的variableId）
  bitmask: number
  range: { min: number; max: number }
  type: GaugeActionType
  options: GaugeActionOptions
}

// 动作参数联合类型
export interface GaugeActionOptions {
  // blink
  fillA?: string
  fillB?: string
  strokeA?: string
  strokeB?: string
  interval?: number
  // color
  fill?: string
  stroke?: string
  // rotate
  minAngle?: number
  maxAngle?: number
  delay?: number
  // move
  toX?: number
  toY?: number
  duration?: number
  // moveByTags
  axis?: 'x' | 'y'
  valueMin?: number
  valueMax?: number
  positionMin?: number
  positionMax?: number
}

// ── 事件 ──

export enum GaugeEventType {
  click = 'click',
  dblclick = 'dblclick',
  mousedown = 'mousedown',
  mouseup = 'mouseup',
  mouseover = 'mouseover',
  mouseout = 'mouseout',
  onLoad = 'onLoad'
}

export enum GaugeEventActionType {
  onpage = 'onpage',
  onwindow = 'onwindow',
  onOpenTab = 'onOpenTab',
  ondialog = 'ondialog',
  oniframe = 'oniframe',
  oncard = 'oncard',
  onSetValue = 'onSetValue',
  onToggleValue = 'onToggleValue',
  onSetInput = 'onSetInput',
  onclose = 'onclose',
  onRunScript = 'onRunScript',
  onViewToPanel = 'onViewToPanel',
  onMonitor = 'onMonitor'
}

export interface GaugeEvent {
  type: GaugeEventType
  action: GaugeEventActionType
  actparam: string // 动作参数（如 view 名称、URL、脚本 ID）
  actoptions?: any // 动作选项
}

// ── 类型别名 ──

export interface DictionaryGaugeSettings {
  [svgElementId: string]: GaugeSettings
}

// ── 创建默认 GaugeSettings ──

export function createGaugeSettings(id: string, type: string, name?: string): GaugeSettings {
  return {
    id,
    type,
    name: name || `${type}_${id.split('_').pop()}`,
    label: type,
    hide: false,
    lock: false,
    property: createDefaultProperty()
  }
}

export function createDefaultProperty(): GaugeProperty {
  return {
    variableId: '',
    variableValue: '',
    bitmask: 0,
    ranges: [],
    events: [],
    actions: [],
    readonly: false
  }
}

// ── 存储格式（用于后端 API 交互） ──

export interface ScadaPageDTO {
  id: number
  name: string
  description?: string
  width: number
  height: number
  background: string
  config_json: string // JSON.stringify({ svgcontent, items, profile })
}

/** 将内部 View 转为后端 config_json */
export function viewToConfigJson(view: View): string {
  return JSON.stringify({
    svgcontent: view.svgcontent,
    items: view.items,
    profile: view.profile
  })
}

/** 从后端 config_json 解析为内部数据 */
export function configJsonToView(
  id: string,
  name: string,
  dto: { config_json: string; width: number; height: number; background: string }
): View {
  let svgcontent = ''
  let items: DictionaryGaugeSettings = {}
  let profile = defaultProfile()

  if (dto.config_json) {
    try {
      const json =
        typeof dto.config_json === 'string' ? JSON.parse(dto.config_json) : dto.config_json
      if (json.svgcontent) svgcontent = json.svgcontent
      if (json.items) items = json.items
      if (json.profile) profile = { ...profile, ...json.profile }
    } catch {
      // 可能是旧版 Fabric JSON，svgcontent 留空
    }
  }

  profile.width = dto.width || profile.width
  profile.height = dto.height || profile.height
  profile.bkcolor = dto.background || profile.bkcolor

  return { id, name, profile, svgcontent, items, type: 'svg' }
}
