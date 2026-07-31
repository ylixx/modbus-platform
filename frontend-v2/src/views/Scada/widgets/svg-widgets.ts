/**
 * SVG 图元定义体系
 *
 * 设计原则（参照 FUXA 架构）：
 * 1. 图元 = SVG 字符串（与 FUXA 的 View.svgcontent 一致）
 * 2. 图元通过 type 属性标识（如 type="svg-ext-shapes"）
 * 3. 绑定信息存储在 SVG 元素的自定义 data-* 属性中
 * 4. 渲染时 innerHTML 注入，运行时 DOM API 操作
 */

export interface SvgWidgetProperty {
  /** 绑定的变量/Tag ID */
  variableId?: string
  /** 初始值 */
  variableValue?: string
  /** 位掩码 */
  bitmask?: number
  /** 范围颜色映射 */
  ranges?: SvgWidgetRange[]
  /** 事件定义 */
  events?: SvgWidgetEvent[]
  /** 动作定义 */
  actions?: SvgWidgetAction[]
  /** 只读 */
  readonly?: boolean
}

export interface SvgWidgetRange {
  min: number
  max: number
  color: string
  stroke?: string
}

export interface SvgWidgetEvent {
  type: 'click' | 'dblclick' | 'change'
  action: string
}

export interface SvgWidgetAction {
  type: 'hide' | 'show' | 'blink' | 'clockwise' | 'anticlockwise' | 'rotate' | 'move' | 'stop'
  targetId?: string
  min?: number
  max?: number
  /** 旋转角度 */
  angle?: number
  /** 移动目标 X */
  toX?: number
  /** 移动目标 Y */
  toY?: number
}

/** 图元定义（FUXA GaugesManager.Gauges 风格） */
export interface SvgWidgetDef {
  /** 类型标签（映射到 SVG 元素的 type 属性） */
  typeTag: string
  /** 显示名称 */
  name: string
  /** 分类 */
  category: string
  /** 默认宽度 */
  defaultWidth: number
  /** 默认高度 */
  defaultHeight: number
  /** 可绑定的属性列表 */
  bindableProps: string[]
  /** 生成 SVG 字符串的工厂函数 */
  createSvg: (id: string, x?: number, y?: number, w?: number, h?: number) => string
  /** SVG 缩略图（用于工具栏展示） */
  thumbnail: string
}

// ── 辅助函数 ──

let _widgetCounter = 0
function genId(prefix: string): string {
  return `${prefix}_${Date.now()}_${++_widgetCounter}`
}

// ── SVG 图元定义列表 ──

export const svgWidgets: SvgWidgetDef[] = [
  // ══════════ 基础图形 ══════════
  {
    typeTag: 'svg-ext-shapes',
    name: '矩形',
    category: '基础',
    defaultWidth: 120,
    defaultHeight: 80,
    bindableProps: ['fill', 'stroke', 'width', 'height', 'opacity'],
    thumbnail: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="8" width="32" height="24" rx="3" fill="#2a5a8a" stroke="#3a8fd4" stroke-width="2"/></svg>`,
    createSvg: (id, x = 0, y = 0, w = 120, h = 80) =>
      `<g id="${id}" type="svg-ext-shapes" transform="translate(${x},${y})">
  <rect width="${w}" height="${h}" rx="4" fill="#2a5a8a" stroke="#3a8fd4" stroke-width="2"/>
</g>`
  },
  {
    typeTag: 'svg-ext-shapes',
    name: '圆形',
    category: '基础',
    defaultWidth: 80,
    defaultHeight: 80,
    bindableProps: ['fill', 'stroke', 'radius', 'opacity'],
    thumbnail: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><circle cx="20" cy="20" r="16" fill="#2a5a8a" stroke="#3a8fd4" stroke-width="2"/></svg>`,
    createSvg: (id, x = 0, y = 0, w = 80, h = 80) =>
      `<g id="${id}" type="svg-ext-shapes" transform="translate(${x},${y})">
  <circle cx="${w / 2}" cy="${h / 2}" r="${Math.min(w, h) / 2 - 2}" fill="#2a5a8a" stroke="#3a8fd4" stroke-width="2"/>
</g>`
  },
  {
    typeTag: 'svg-ext-shapes',
    name: '三角形',
    category: '基础',
    defaultWidth: 100,
    defaultHeight: 86,
    bindableProps: ['fill', 'stroke', 'opacity'],
    thumbnail: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><polygon points="20,4 36,36 4,36" fill="#2a5a8a" stroke="#3a8fd4" stroke-width="2"/></svg>`,
    createSvg: (id, x = 0, y = 0, w = 100, h = 86) =>
      `<g id="${id}" type="svg-ext-shapes" transform="translate(${x},${y})">
  <polygon points="${w / 2},0 ${w},${h} 0,${h}" fill="#2a5a8a" stroke="#3a8fd4" stroke-width="2"/>
</g>`
  },
  {
    typeTag: 'svg-ext-value',
    name: '文本',
    category: '基础',
    defaultWidth: 120,
    defaultHeight: 30,
    bindableProps: ['text', 'fill', 'fontSize'],
    thumbnail: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><text x="20" y="26" text-anchor="middle" fill="#e0e0e0" font-size="14" font-family="Arial">T</text></svg>`,
    createSvg: (id, x = 0, y = 0, w = 120, h = 30) =>
      `<g id="${id}" type="svg-ext-value" transform="translate(${x},${y})">
  <text x="${w / 2}" y="${h / 2 + 5}" text-anchor="middle" fill="#e0e0e0" font-size="16" font-family="Arial" data-bind-prop="text">文本</text>
</g>`
  },
  {
    typeTag: 'svg-ext-shapes',
    name: '水平线',
    category: '基础',
    defaultWidth: 150,
    defaultHeight: 2,
    bindableProps: ['stroke', 'strokeWidth'],
    thumbnail: `<svg viewBox="0 0 40 10" xmlns="http://www.w3.org/2000/svg"><line x1="0" y1="5" x2="40" y2="5" stroke="#3a8fd4" stroke-width="2"/></svg>`,
    createSvg: (id, x = 0, y = 0, w = 150, h = 2) =>
      `<g id="${id}" type="svg-ext-shapes" transform="translate(${x},${y})">
  <line x1="0" y1="${h / 2}" x2="${w}" y2="${h / 2}" stroke="#3a8fd4" stroke-width="3"/>
</g>`
  },
  {
    typeTag: 'svg-ext-shapes',
    name: '垂直线',
    category: '基础',
    defaultWidth: 2,
    defaultHeight: 150,
    bindableProps: ['stroke', 'strokeWidth'],
    thumbnail: `<svg viewBox="0 0 10 40" xmlns="http://www.w3.org/2000/svg"><line x1="5" y1="0" x2="5" y2="40" stroke="#3a8fd4" stroke-width="2"/></svg>`,
    createSvg: (id, x = 0, y = 0, w = 2, h = 150) =>
      `<g id="${id}" type="svg-ext-shapes" transform="translate(${x},${y})">
  <line x1="${w / 2}" y1="0" x2="${w / 2}" y2="${h}" stroke="#3a8fd4" stroke-width="3"/>
</g>`
  },

  // ══════════ 容器类 ══════════
  {
    typeTag: 'svg-ext-shapes',
    name: '立式储罐',
    category: '容器',
    defaultWidth: 120,
    defaultHeight: 160,
    bindableProps: ['level', 'temperature', 'pressure'],
    thumbnail: `<svg viewBox="0 0 40 52" xmlns="http://www.w3.org/2000/svg">
  <rect x="6" y="6" width="28" height="36" rx="3" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="1.5"/>
  <rect x="4" y="2" width="32" height="6" rx="2" fill="#2a5a8a" stroke="#3a8fd4" stroke-width="1.5"/>
  <rect x="9" y="14" width="22" height="24" rx="2" fill="#1a6aaa" stroke="none" data-bind-target="level" data-bind-prop="height"/>
  <text x="20" y="28" text-anchor="middle" fill="#fff" font-size="7" font-family="Arial">罐</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 120, h = 160) => {
      const bodyH = h * 0.875
      const topH = h * 0.125
      const levelH = bodyH * 0.7
      return `<g id="${id}" type="svg-ext-shapes" transform="translate(${x},${y})">
  <rect width="${w}" height="${bodyH}" y="${topH}" rx="6" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="2"/>
  <rect x="${-w * 0.08}" width="${w * 1.16}" height="${topH}" rx="4" fill="#2a5a8a" stroke="#3a8fd4" stroke-width="2"/>
  <rect x="${w * 0.08}" y="${topH + bodyH * 0.15}" width="${w * 0.84}" height="${levelH}" rx="4" fill="#1a6aaa" stroke="none" data-bind-target="level" data-bind-prop="height"/>
  <text x="${w / 2}" y="${topH + bodyH * 0.5}" text-anchor="middle" fill="#ffffff" font-size="16" font-family="Arial" data-bind-target="label" data-bind-prop="text">储罐</text>
</g>`
    }
  },
  {
    typeTag: 'svg-ext-shapes',
    name: '卧式储罐',
    category: '容器',
    defaultWidth: 180,
    defaultHeight: 100,
    bindableProps: ['level', 'temperature'],
    thumbnail: `<svg viewBox="0 0 48 28" xmlns="http://www.w3.org/2000/svg">
  <rect x="2" y="4" width="44" height="20" rx="10" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="1.5"/>
  <rect x="6" y="8" width="36" height="12" rx="6" fill="#1a6aaa" stroke="none" data-bind-target="level" data-bind-prop="width"/>
  <text x="24" y="18" text-anchor="middle" fill="#fff" font-size="7" font-family="Arial">卧罐</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 180, h = 100) =>
      `<g id="${id}" type="svg-ext-shapes" transform="translate(${x},${y})">
  <rect width="${w}" height="${h}" rx="20" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="2"/>
  <rect x="${w * 0.06}" y="${h * 0.15}" width="${w * 0.88}" height="${h * 0.7}" rx="14" fill="#1a6aaa" stroke="none" data-bind-target="level" data-bind-prop="width"/>
  <text x="${w / 2}" y="${h / 2 + 4}" text-anchor="middle" fill="#ffffff" font-size="14" font-family="Arial" data-bind-target="label" data-bind-prop="text">卧式罐</text>
</g>`
  },
  {
    typeTag: 'svg-ext-shapes',
    name: '换热器',
    category: '容器',
    defaultWidth: 120,
    defaultHeight: 80,
    bindableProps: ['temperature', 'pressure'],
    thumbnail: `<svg viewBox="0 0 40 28" xmlns="http://www.w3.org/2000/svg">
  <rect x="2" y="2" width="36" height="24" rx="3" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="1.5"/>
  <line x1="8" y1="8" x2="32" y2="8" stroke="#4ac080" stroke-width="1.5"/>
  <line x1="8" y1="14" x2="32" y2="14" stroke="#4ac080" stroke-width="1.5"/>
  <line x1="8" y1="20" x2="32" y2="20" stroke="#4ac080" stroke-width="1.5"/>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 120, h = 80) =>
      `<g id="${id}" type="svg-ext-shapes" transform="translate(${x},${y})">
  <rect width="${w}" height="${h}" rx="6" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="2"/>
  <line x1="${w * 0.12}" y1="${h * 0.25}" x2="${w * 0.88}" y2="${h * 0.25}" stroke="#4ac080" stroke-width="2"/>
  <line x1="${w * 0.12}" y1="${h * 0.5}" x2="${w * 0.88}" y2="${h * 0.5}" stroke="#4ac080" stroke-width="2"/>
  <line x1="${w * 0.12}" y1="${h * 0.75}" x2="${w * 0.88}" y2="${h * 0.75}" stroke="#4ac080" stroke-width="2"/>
  <text x="${w / 2}" y="${h / 2 + 4}" text-anchor="middle" fill="#ffffff" font-size="12" font-family="Arial" data-bind-target="label" data-bind-prop="text">换热器</text>
</g>`
  },

  // ══════════ 阀门类 ══════════
  {
    typeTag: 'svg-ext-shapes',
    name: '球阀',
    category: '阀门',
    defaultWidth: 80,
    defaultHeight: 60,
    bindableProps: ['state', 'position'],
    thumbnail: `<svg viewBox="0 0 40 30" xmlns="http://www.w3.org/2000/svg">
  <line x1="0" y1="15" x2="12" y2="15" stroke="#3a8fd4" stroke-width="4"/>
  <circle cx="20" cy="15" r="10" fill="#2a5a8a" stroke="#3a8fd4" stroke-width="1.5"/>
  <line x1="20" y1="2" x2="20" y2="8" stroke="#f0a030" stroke-width="3"/>
  <line x1="28" y1="15" x2="40" y2="15" stroke="#3a8fd4" stroke-width="4"/>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 80, h = 60) => {
      const cx = w / 2
      const cy = h * 0.5
      const r = Math.min(w, h) * 0.35
      return `<g id="${id}" type="svg-ext-shapes" transform="translate(${x},${y})">
  <line x1="0" y1="${cy}" x2="${cx - r}" y2="${cy}" stroke="#3a8fd4" stroke-width="6" stroke-linecap="round"/>
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="#2a5a8a" stroke="#3a8fd4" stroke-width="2"/>
  <line x1="${cx}" y1="${cy - r - 2}" x2="${cx}" y2="${cy - r * 0.3}" stroke="#f0a030" stroke-width="4" stroke-linecap="round" data-bind-target="state" data-bind-prop="rotate"/>
  <line x1="${cx + r}" y1="${cy}" x2="${w}" y2="${cy}" stroke="#3a8fd4" stroke-width="6" stroke-linecap="round"/>
  <text x="${cx}" y="${h - 2}" text-anchor="middle" fill="#a0c0e0" font-size="11" font-family="Arial">球阀</text>
</g>`
    }
  },
  {
    typeTag: 'svg-ext-shapes',
    name: '蝶阀',
    category: '阀门',
    defaultWidth: 80,
    defaultHeight: 60,
    bindableProps: ['state', 'position'],
    thumbnail: `<svg viewBox="0 0 40 30" xmlns="http://www.w3.org/2000/svg">
  <line x1="0" y1="15" x2="12" y2="15" stroke="#4ac080" stroke-width="4"/>
  <circle cx="20" cy="15" r="10" fill="#2a4a3a" stroke="#4ac080" stroke-width="1.5"/>
  <line x1="13" y1="9" x2="27" y2="21" stroke="#4ac080" stroke-width="2"/>
  <line x1="28" y1="15" x2="40" y2="15" stroke="#4ac080" stroke-width="4"/>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 80, h = 60) => {
      const cx = w / 2
      const cy = h * 0.5
      const r = Math.min(w, h) * 0.35
      return `<g id="${id}" type="svg-ext-shapes" transform="translate(${x},${y})">
  <line x1="0" y1="${cy}" x2="${cx - r}" y2="${cy}" stroke="#4ac080" stroke-width="6" stroke-linecap="round"/>
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="#2a4a3a" stroke="#4ac080" stroke-width="2"/>
  <line x1="${cx - r * 0.6}" y1="${cy - r * 0.5}" x2="${cx + r * 0.6}" y2="${cy + r * 0.5}" stroke="#4ac080" stroke-width="3" data-bind-target="state" data-bind-prop="rotate"/>
  <line x1="${cx + r}" y1="${cy}" x2="${w}" y2="${cy}" stroke="#4ac080" stroke-width="6" stroke-linecap="round"/>
  <text x="${cx}" y="${h - 2}" text-anchor="middle" fill="#a0e0c0" font-size="11" font-family="Arial">蝶阀</text>
</g>`
    }
  },

  // ══════════ 动力设备 ══════════
  {
    typeTag: 'svg-ext-ape',
    name: '离心泵',
    category: '动力',
    defaultWidth: 80,
    defaultHeight: 90,
    bindableProps: ['state', 'speed', 'flow'],
    thumbnail: `<svg viewBox="0 0 40 44" xmlns="http://www.w3.org/2000/svg">
  <circle cx="20" cy="20" r="14" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="1.5"/>
  <line x1="20" y1="8" x2="14" y2="28" stroke="#f0a030" stroke-width="2.5"/>
  <line x1="20" y1="8" x2="26" y2="28" stroke="#f0a030" stroke-width="2.5"/>
  <line x1="14" y1="28" x2="26" y2="28" stroke="#f0a030" stroke-width="2"/>
  <circle cx="20" cy="20" r="3" fill="#4ac080"/>
  <line x1="0" y1="20" x2="6" y2="20" stroke="#3a8fd4" stroke-width="4"/>
  <line x1="34" y1="20" x2="40" y2="20" stroke="#3a8fd4" stroke-width="4"/>
  <text x="20" y="42" text-anchor="middle" fill="#a0c0e0" font-size="7">泵</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 80, h = 90) => {
      const cx = w / 2
      const cy = h * 0.44
      const r = Math.min(w, h) * 0.35
      return `<g id="${id}" type="svg-ext-ape" transform="translate(${x},${y})">
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="2"/>
  <g data-bind-target="state" data-bind-prop="rotate" class="ape-blade">
    <line x1="${cx}" y1="${cy - r + 4}" x2="${cx - r * 0.4}" y2="${cy + r * 0.5}" stroke="#f0a030" stroke-width="3"/>
    <line x1="${cx}" y1="${cy - r + 4}" x2="${cx + r * 0.4}" y2="${cy + r * 0.5}" stroke="#f0a030" stroke-width="3"/>
    <line x1="${cx - r * 0.4}" y1="${cy + r * 0.5}" x2="${cx + r * 0.4}" y2="${cy + r * 0.5}" stroke="#f0a030" stroke-width="2"/>
  </g>
  <circle cx="${cx}" cy="${cy}" r="${r * 0.15}" fill="#4ac080" stroke="none"/>
  <line x1="0" y1="${cy}" x2="${cx - r}" y2="${cy}" stroke="#3a8fd4" stroke-width="6" stroke-linecap="round"/>
  <line x1="${cx + r}" y1="${cy}" x2="${w}" y2="${cy}" stroke="#3a8fd4" stroke-width="6" stroke-linecap="round"/>
  <text x="${cx}" y="${h - 4}" text-anchor="middle" fill="#a0c0e0" font-size="11" font-family="Arial">泵</text>
</g>`
    }
  },
  {
    typeTag: 'svg-ext-ape',
    name: '电机',
    category: '动力',
    defaultWidth: 70,
    defaultHeight: 70,
    bindableProps: ['state', 'speed', 'current'],
    thumbnail: `<svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg">
  <rect x="4" y="6" width="24" height="20" rx="5" fill="#3a3a3a" stroke="#6a6a6a" stroke-width="1.5"/>
  <rect x="28" y="12" width="6" height="4" rx="1" fill="#8a8a8a"/>
  <text x="16" y="21" text-anchor="middle" fill="#ffffff" font-size="11" font-family="Arial" font-weight="bold">M</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 70, h = 70) =>
      `<g id="${id}" type="svg-ext-ape" transform="translate(${x},${y})">
  <rect x="0" y="${h * 0.14}" width="${w * 0.86}" height="${h * 0.72}" rx="10" fill="#3a3a3a" stroke="#6a6a6a" stroke-width="2"/>
  <rect x="${w * 0.86}" y="${h * 0.32}" width="${w * 0.14}" height="${h * 0.08}" rx="1" fill="#8a8a8a" stroke="none"/>
  <g data-bind-target="state" data-bind-prop="rotate" class="ape-blade">
    <text x="${w * 0.43}" y="${h * 0.55}" text-anchor="middle" fill="#ffffff" font-size="20" font-family="Arial" font-weight="bold">M</text>
  </g>
  <text x="${w * 0.43}" y="${h - 2}" text-anchor="middle" fill="#a0a0a0" font-size="11" font-family="Arial">电机</text>
</g>`
  },
  {
    typeTag: 'svg-ext-ape',
    name: '风机',
    category: '动力',
    defaultWidth: 80,
    defaultHeight: 90,
    bindableProps: ['state', 'speed'],
    thumbnail: `<svg viewBox="0 0 40 44" xmlns="http://www.w3.org/2000/svg">
  <circle cx="20" cy="20" r="14" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="1.5"/>
  <line x1="20" y1="8" x2="20" y2="14" stroke="#4ac080" stroke-width="3"/>
  <line x1="20" y1="26" x2="20" y2="32" stroke="#4ac080" stroke-width="3"/>
  <line x1="8" y1="20" x2="14" y2="20" stroke="#4ac080" stroke-width="3"/>
  <line x1="26" y1="20" x2="32" y2="20" stroke="#4ac080" stroke-width="3"/>
  <circle cx="20" cy="20" r="3" fill="#4ac080"/>
  <text x="20" y="42" text-anchor="middle" fill="#a0c0e0" font-size="7">风机</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 80, h = 90) => {
      const cx = w / 2
      const cy = h * 0.44
      const r = Math.min(w, h) * 0.35
      return `<g id="${id}" type="svg-ext-ape" transform="translate(${x},${y})">
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="2"/>
  <g data-bind-target="state" data-bind-prop="rotate" class="ape-blade">
    <line x1="${cx}" y1="${cy - r + 4}" x2="${cx}" y2="${cy - r * 0.3}" stroke="#4ac080" stroke-width="3"/>
    <line x1="${cx}" y1="${cy + r * 0.3}" x2="${cx}" y2="${cy + r - 4}" stroke="#4ac080" stroke-width="3"/>
    <line x1="${cx - r + 4}" y1="${cy}" x2="${cx - r * 0.3}" y2="${cy}" stroke="#4ac080" stroke-width="3"/>
    <line x1="${cx + r * 0.3}" y1="${cy}" x2="${cx + r - 4}" y2="${cy}" stroke="#4ac080" stroke-width="3"/>
  </g>
  <circle cx="${cx}" cy="${cy}" r="${r * 0.15}" fill="#4ac080" stroke="none"/>
  <text x="${cx}" y="${h - 4}" text-anchor="middle" fill="#a0c0e0" font-size="11" font-family="Arial">风机</text>
</g>`
    }
  },
  {
    typeTag: 'svg-ext-shapes',
    name: '压缩机',
    category: '动力',
    defaultWidth: 80,
    defaultHeight: 90,
    bindableProps: ['state', 'speed', 'pressure'],
    thumbnail: `<svg viewBox="0 0 40 44" xmlns="http://www.w3.org/2000/svg">
  <circle cx="20" cy="20" r="14" fill="#3a1a1a" stroke="#aa4040" stroke-width="1.5"/>
  <polygon points="14,10 26,20 14,30" fill="#f0a030"/>
  <line x1="0" y1="20" x2="6" y2="20" stroke="#3a8fd4" stroke-width="4"/>
  <line x1="34" y1="20" x2="40" y2="20" stroke="#3a8fd4" stroke-width="4"/>
  <text x="20" y="42" text-anchor="middle" fill="#aa4040" font-size="7">压缩机</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 80, h = 90) => {
      const cx = w / 2
      const cy = h * 0.44
      const r = Math.min(w, h) * 0.35
      return `<g id="${id}" type="svg-ext-shapes" transform="translate(${x},${y})">
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="#3a1a1a" stroke="#aa4040" stroke-width="2"/>
  <polygon points="${cx - r * 0.5},${cy - r * 0.7} ${cx + r * 0.5},${cy} ${cx - r * 0.5},${cy + r * 0.7}" fill="#f0a030" stroke="none"/>
  <line x1="0" y1="${cy}" x2="${cx - r}" y2="${cy}" stroke="#3a8fd4" stroke-width="6" stroke-linecap="round"/>
  <line x1="${cx + r}" y1="${cy}" x2="${w}" y2="${cy}" stroke="#3a8fd4" stroke-width="6" stroke-linecap="round"/>
  <text x="${cx}" y="${h - 4}" text-anchor="middle" fill="#aa4040" font-size="11" font-family="Arial">压缩机</text>
</g>`
    }
  },

  // ══════════ 管道类 ══════════
  {
    typeTag: 'svg-ext-pipe',
    name: '水平管道',
    category: '管道',
    defaultWidth: 150,
    defaultHeight: 20,
    bindableProps: ['flow', 'pressure'],
    thumbnail: `<svg viewBox="0 0 40 8" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="1" width="40" height="6" rx="2" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="1"/>
  <line x1="5" y1="4" x2="35" y2="4" stroke="#4ac080" stroke-width="1.5" stroke-dasharray="4 2"/>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 150, h = 20) =>
      `<g id="${id}" type="svg-ext-pipe" transform="translate(${x},${y})">
  <rect width="${w}" height="${h}" rx="4" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="1"/>
  <line x1="${w * 0.15}" y1="${h / 2}" x2="${w * 0.75}" y2="${h / 2}" stroke="#4ac080" stroke-width="2" stroke-dasharray="${w * 0.06} ${w * 0.04}" data-bind-target="flow" data-bind-prop="animate" class="pipe-flow"/>
  <polygon points="${w * 0.82},${h * 0.3} ${w * 0.92},${h / 2} ${w * 0.82},${h * 0.7}" fill="#4ac080"/>
</g>`
  },
  {
    typeTag: 'svg-ext-pipe',
    name: '垂直管道',
    category: '管道',
    defaultWidth: 20,
    defaultHeight: 150,
    bindableProps: ['flow', 'pressure'],
    thumbnail: `<svg viewBox="0 0 8 40" xmlns="http://www.w3.org/2000/svg">
  <rect x="1" y="0" width="6" height="40" rx="2" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="1"/>
  <line x1="4" y1="5" x2="4" y2="35" stroke="#4ac080" stroke-width="1.5" stroke-dasharray="4 2"/>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 20, h = 150) =>
      `<g id="${id}" type="svg-ext-pipe" transform="translate(${x},${y})">
  <rect width="${w}" height="${h}" rx="4" fill="#1a3a5a" stroke="#3a8fd4" stroke-width="1"/>
  <line x1="${w / 2}" y1="${h * 0.15}" x2="${w / 2}" y2="${h * 0.75}" stroke="#4ac080" stroke-width="2" stroke-dasharray="${h * 0.06} ${h * 0.04}" data-bind-target="flow" data-bind-prop="animate" class="pipe-flow"/>
  <polygon points="${w * 0.3},${h * 0.82} ${w / 2},${h * 0.92} ${w * 0.7},${h * 0.82}" fill="#4ac080"/>
</g>`
  },

  // ══════════ 仪表类 ══════════
  {
    typeTag: 'svg-ext-gauge',
    name: '表盘',
    category: '仪表',
    defaultWidth: 120,
    defaultHeight: 120,
    bindableProps: ['value', 'min', 'max'],
    thumbnail: `<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
  <circle cx="20" cy="20" r="16" fill="#1a1a2e" stroke="#3a8fd4" stroke-width="1.5"/>
  <circle cx="20" cy="20" r="12" fill="none" stroke="#2a4a6a" stroke-width="0.8"/>
  <line x1="20" y1="8" x2="20" y2="12" stroke="#6a8ab0" stroke-width="1.5"/>
  <line x1="32" y1="20" x2="28" y2="20" stroke="#6a8ab0" stroke-width="1.5"/>
  <line x1="20" y1="32" x2="20" y2="28" stroke="#6a8ab0" stroke-width="1.5"/>
  <line x1="8" y1="20" x2="12" y2="20" stroke="#6a8ab0" stroke-width="1.5"/>
  <line x1="20" y1="20" x2="28" y2="12" stroke="#f04040" stroke-width="2" stroke-linecap="round"/>
  <circle cx="20" cy="20" r="2" fill="#f04040"/>
  <text x="20" y="28" text-anchor="middle" fill="#4ac080" font-size="5" font-family="monospace">0.0</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 120, h = 120) => {
      const cx = w / 2
      const cy = h / 2
      const r = Math.min(w, h) / 2 - 5
      return `<g id="${id}" type="svg-ext-gauge" transform="translate(${x},${y})">
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="#1a1a2e" stroke="#3a8fd4" stroke-width="2"/>
  <circle cx="${cx}" cy="${cy}" r="${r * 0.8}" fill="transparent" stroke="#2a4a6a" stroke-width="1"/>
  <line x1="${cx}" y1="${cy - r + 5}" x2="${cx}" y2="${cy - r + 15}" stroke="#6a8ab0" stroke-width="2"/>
  <line x1="${cx + r - 5}" y1="${cy}" x2="${cx + r - 15}" y2="${cy}" stroke="#6a8ab0" stroke-width="2"/>
  <line x1="${cx}" y1="${cy + r - 5}" x2="${cx}" y2="${cy + r - 15}" stroke="#6a8ab0" stroke-width="2"/>
  <line x1="${cx - r + 5}" y1="${cy}" x2="${cx - r + 15}" y2="${cy}" stroke="#6a8ab0" stroke-width="2"/>
  <line x1="${cx}" y1="${cy}" x2="${cx + r * 0.55}" y2="${cy - r * 0.55}" stroke="#f04040" stroke-width="3" stroke-linecap="round" data-bind-target="value" data-bind-prop="pointer-rotate"/>
  <circle cx="${cx}" cy="${cy}" r="${r * 0.08}" fill="#f04040" stroke="none"/>
  <text x="${cx}" y="${cy + r * 0.5}" text-anchor="middle" fill="#4ac080" font-size="14" font-family="monospace" data-bind-target="value" data-bind-prop="text">0.0</text>
  <text x="${cx}" y="${cy + r * 0.7}" text-anchor="middle" fill="#6a8ab0" font-size="10" font-family="Arial">单位</text>
</g>`
    }
  },
  {
    typeTag: 'svg-ext-value',
    name: '数值显示',
    category: '仪表',
    defaultWidth: 100,
    defaultHeight: 50,
    bindableProps: ['value', 'unit', 'name'],
    thumbnail: `<svg viewBox="0 0 40 20" xmlns="http://www.w3.org/2000/svg">
  <rect x="1" y="1" width="38" height="18" rx="3" fill="#0a1a2a" stroke="#3a8fd4" stroke-width="1"/>
  <text x="20" y="8" text-anchor="middle" fill="#6a8ab0" font-size="5">温度</text>
  <text x="20" y="16" text-anchor="middle" fill="#4ac080" font-size="7" font-weight="bold" font-family="monospace">0.0</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 100, h = 50) =>
      `<g id="${id}" type="svg-ext-value" transform="translate(${x},${y})">
  <rect width="${w}" height="${h}" rx="6" fill="#0a1a2a" stroke="#3a8fd4" stroke-width="1"/>
  <text x="${w / 2}" y="${h * 0.28}" text-anchor="middle" fill="#6a8ab0" font-size="11" font-family="Arial" data-bind-target="name" data-bind-prop="text">名称</text>
  <text x="${w / 2}" y="${h * 0.72}" text-anchor="middle" fill="#4ac080" font-size="20" font-weight="bold" font-family="monospace" data-bind-target="value" data-bind-prop="text">0.0</text>
</g>`
  },
  {
    typeTag: 'svg-ext-progress',
    name: '进度条',
    category: '仪表',
    defaultWidth: 160,
    defaultHeight: 40,
    bindableProps: ['value', 'min', 'max'],
    thumbnail: `<svg viewBox="0 0 40 12" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="1" width="40" height="10" rx="2" fill="#1a1a2e" stroke="#3a5a7a" stroke-width="0.8"/>
  <rect x="2" y="3" width="20" height="6" rx="2" fill="#3a8fd4"/>
  <text x="20" y="8" text-anchor="middle" fill="#fff" font-size="5">50%</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 160, h = 40) =>
      `<g id="${id}" type="svg-ext-progress" transform="translate(${x},${y})">
  <rect width="${w}" height="${h * 0.75}" y="${h * 0.125}" rx="4" fill="#1a1a2e" stroke="#3a5a7a" stroke-width="1"/>
  <rect x="3" y="${h * 0.2}" width="${w * 0.5}" height="${h * 0.6}" rx="3" fill="#3a8fd4" stroke="none" data-bind-target="value" data-bind-prop="width"/>
  <text x="${w / 2}" y="${h * 0.55}" text-anchor="middle" fill="#ffffff" font-size="12" font-family="Arial" data-bind-target="value" data-bind-prop="text">50%</text>
</g>`
  },

  // ══════════ 指示灯 ══════════
  {
    typeTag: 'svg-ext-led',
    name: '指示灯',
    category: '指示',
    defaultWidth: 50,
    defaultHeight: 60,
    bindableProps: ['state'],
    thumbnail: `<svg viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">
  <circle cx="12" cy="12" r="9" fill="#2a2a2a" stroke="#4a4a4a" stroke-width="1.5"/>
  <circle cx="12" cy="12" r="6" fill="#00ff00" data-bind-target="state" data-bind-prop="fill"/>
  <text x="12" y="28" text-anchor="middle" fill="#a0a0a0" font-size="5">运行</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 50, h = 60) => {
      const cx = w / 2
      const cy = h * 0.4
      return `<g id="${id}" type="svg-ext-led" transform="translate(${x},${y})">
  <circle cx="${cx}" cy="${cy}" r="${Math.min(w, h) * 0.35}" fill="#2a2a2a" stroke="#4a4a4a" stroke-width="2"/>
  <circle cx="${cx}" cy="${cy}" r="${Math.min(w, h) * 0.25}" fill="#00ff00" stroke="none" data-bind-target="state" data-bind-prop="fill"/>
  <text x="${cx}" y="${h - 4}" text-anchor="middle" fill="#a0a0a0" font-size="11" font-family="Arial">运行</text>
</g>`
    }
  },
  {
    typeTag: 'svg-ext-led',
    name: '报警灯',
    category: '指示',
    defaultWidth: 50,
    defaultHeight: 70,
    bindableProps: ['state', 'level'],
    thumbnail: `<svg viewBox="0 0 24 34" xmlns="http://www.w3.org/2000/svg">
  <circle cx="12" cy="12" r="9" fill="#3a1a1a" stroke="#aa4040" stroke-width="1.5"/>
  <circle cx="12" cy="12" r="6" fill="#ff0000" data-bind-target="state" data-bind-prop="fill"/>
  <rect x="7" y="22" width="10" height="4" rx="1" fill="#4a4a4a" stroke="#6a6a6a" stroke-width="0.8"/>
  <text x="12" y="32" text-anchor="middle" fill="#aa4040" font-size="5">报警</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 50, h = 70) => {
      const cx = w / 2
      const cy = h * 0.35
      return `<g id="${id}" type="svg-ext-led" transform="translate(${x},${y})">
  <circle cx="${cx}" cy="${cy}" r="${Math.min(w, h) * 0.3}" fill="#3a1a1a" stroke="#aa4040" stroke-width="2"/>
  <circle cx="${cx}" cy="${cy}" r="${Math.min(w, h) * 0.2}" fill="#ff0000" stroke="none" data-bind-target="state" data-bind-prop="fill"/>
  <rect x="${cx - w * 0.3}" y="${cy + h * 0.32}" width="${w * 0.6}" height="${h * 0.08}" rx="2" fill="#4a4a4a" stroke="#6a6a6a" stroke-width="1"/>
  <text x="${cx}" y="${h - 4}" text-anchor="middle" fill="#aa4040" font-size="11" font-family="Arial">报警</text>
</g>`
    }
  },
  {
    typeTag: 'svg-ext-led',
    name: '信号灯',
    category: '指示',
    defaultWidth: 40,
    defaultHeight: 120,
    bindableProps: ['state', 'red', 'yellow', 'green'],
    thumbnail: `<svg viewBox="0 0 20 40" xmlns="http://www.w3.org/2000/svg">
  <rect x="2" y="0" width="16" height="40" rx="4" fill="#2a2a2a" stroke="#4a4a4a" stroke-width="1"/>
  <circle cx="10" cy="8" r="5" fill="#ff0000" data-bind-target="red" data-bind-prop="fill"/>
  <circle cx="10" cy="20" r="5" fill="#3a3a00"/>
  <circle cx="10" cy="32" r="5" fill="#003a00"/>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 40, h = 120) =>
      `<g id="${id}" type="svg-ext-led" transform="translate(${x},${y})">
  <rect width="${w}" height="${h}" rx="8" fill="#2a2a2a" stroke="#4a4a4a" stroke-width="2"/>
  <circle cx="${w / 2}" cy="${h * 0.2}" r="${w * 0.28}" fill="#ff0000" stroke="#6a0000" stroke-width="1" data-bind-target="red" data-bind-prop="fill"/>
  <circle cx="${w / 2}" cy="${h * 0.5}" r="${w * 0.28}" fill="#3a3a00" stroke="#6a6a00" stroke-width="1" data-bind-target="yellow" data-bind-prop="fill"/>
  <circle cx="${w / 2}" cy="${h * 0.8}" r="${w * 0.28}" fill="#003a00" stroke="#006a00" stroke-width="1" data-bind-target="green" data-bind-prop="fill"/>
</g>`
  },

  // ══════════ 控件类 ══════════
  {
    typeTag: 'svg-ext-button',
    name: '按钮',
    category: '控件',
    defaultWidth: 80,
    defaultHeight: 40,
    bindableProps: ['action', 'text'],
    thumbnail: `<svg viewBox="0 0 40 20" xmlns="http://www.w3.org/2000/svg">
  <rect x="1" y="1" width="38" height="18" rx="4" fill="#3a5a7a" stroke="#5a8ab0" stroke-width="1.5"/>
  <text x="20" y="13" text-anchor="middle" fill="#ffffff" font-size="8">按钮</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 80, h = 40) =>
      `<g id="${id}" type="svg-ext-button" transform="translate(${x},${y})">
  <rect width="${w}" height="${h}" rx="6" fill="#3a5a7a" stroke="#5a8ab0" stroke-width="2" cursor="pointer"/>
  <text x="${w / 2}" y="${h / 2 + 4}" text-anchor="middle" fill="#ffffff" font-size="14" font-family="Arial" pointer-events="none" data-bind-target="text" data-bind-prop="text">按钮</text>
</g>`
  },
  {
    typeTag: 'svg-ext-switch',
    name: '开关',
    category: '控件',
    defaultWidth: 70,
    defaultHeight: 40,
    bindableProps: ['state'],
    thumbnail: `<svg viewBox="0 0 36 20" xmlns="http://www.w3.org/2000/svg">
  <rect x="2" y="3" width="32" height="14" rx="7" fill="#2a2a2a" stroke="#4a6a8a" stroke-width="1"/>
  <circle cx="26" cy="10" r="5" fill="#3a8fd4" stroke="#5ab0ff" stroke-width="1" data-bind-target="state" data-bind-prop="cx"/>
  <text x="18" y="19" text-anchor="middle" fill="#a0a0a0" font-size="5">OFF</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 70, h = 40) =>
      `<g id="${id}" type="svg-ext-switch" transform="translate(${x},${y})">
  <rect x="${w * 0.07}" y="${h * 0.15}" width="${w * 0.86}" height="${h * 0.7}" rx="${h * 0.35}" fill="#2a2a2a" stroke="#4a6a8a" stroke-width="1"/>
  <circle cx="${w * 0.7}" cy="${h / 2}" r="${h * 0.25}" fill="#3a8fd4" stroke="#5ab0ff" stroke-width="1" data-bind-target="state" data-bind-prop="cx" cursor="pointer"/>
  <text x="${w / 2}" y="${h - 2}" text-anchor="middle" fill="#a0a0a0" font-size="11" font-family="Arial" data-bind-target="state" data-bind-prop="text">OFF</text>
</g>`
  },
  {
    typeTag: 'svg-ext-slider',
    name: '滑块控件',
    category: '控件',
    defaultWidth: 160,
    defaultHeight: 40,
    bindableProps: ['value', 'min', 'max'],
    thumbnail: `<svg viewBox="0 0 40 12" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="4" width="40" height="4" rx="2" fill="#2a2a2a" stroke="#4a6a8a" stroke-width="0.8"/>
  <rect x="0" y="4" width="20" height="4" rx="2" fill="#3a8fd4"/>
  <circle cx="20" cy="6" r="4" fill="#5ab0ff" stroke="#fff" stroke-width="1"/>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 160, h = 40) =>
      `<g id="${id}" type="svg-ext-slider" transform="translate(${x},${y})">
  <rect y="${h * 0.375}" width="${w}" height="${h * 0.25}" rx="${h * 0.125}" fill="#2a2a2a" stroke="#4a6a8a" stroke-width="1"/>
  <rect y="${h * 0.375}" width="${w * 0.5}" height="${h * 0.25}" rx="${h * 0.125}" fill="#3a8fd4" stroke="none" data-bind-target="value" data-bind-prop="width"/>
  <circle cx="${w * 0.5}" cy="${h / 2}" r="${h * 0.2}" fill="#5ab0ff" stroke="#ffffff" stroke-width="2" data-bind-target="value" data-bind-prop="cx" cursor="pointer"/>
  <text x="${w / 2}" y="${h - 2}" text-anchor="middle" fill="#a0a0a0" font-size="11" font-family="Arial" data-bind-target="value" data-bind-prop="text">50%</text>
</g>`
  },
  {
    typeTag: 'svg-ext-input',
    name: '输入框',
    category: '控件',
    defaultWidth: 120,
    defaultHeight: 36,
    bindableProps: ['value'],
    thumbnail: `<svg viewBox="0 0 40 16" xmlns="http://www.w3.org/2000/svg">
  <rect x="1" y="1" width="38" height="14" rx="3" fill="#1a1a2e" stroke="#3a8fd4" stroke-width="1"/>
  <text x="6" y="11" fill="#e0e0e0" font-size="7" font-family="Arial">输入值</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 120, h = 36) =>
      `<g id="${id}" type="svg-ext-input" transform="translate(${x},${y})">
  <foreignObject width="${w}" height="${h}">
    <div xmlns="http://www.w3.org/1999/xhtml" style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;">
      <input type="text" value="" placeholder="输入值" data-bind-target="value" data-bind-prop="value"
        style="width:90%;height:70%;background:#1a1a2e;color:#e0e0e0;border:1px solid #3a8fd4;border-radius:4px;padding:2px 8px;font-size:14px;outline:none;"/>
    </div>
  </foreignObject>
</g>`
  },

  // ══════════ 标注类 ══════════
  {
    typeTag: 'svg-ext-value',
    name: '文本标签',
    category: '标注',
    defaultWidth: 120,
    defaultHeight: 36,
    bindableProps: ['text', 'value'],
    thumbnail: `<svg viewBox="0 0 40 14" xmlns="http://www.w3.org/2000/svg">
  <rect x="1" y="1" width="38" height="12" rx="2" fill="none" stroke="#3a5a7a" stroke-width="1" stroke-dasharray="3 2"/>
  <text x="20" y="10" text-anchor="middle" fill="#e0e0e0" font-size="7">标签</text>
</svg>`,
    createSvg: (id, x = 0, y = 0, w = 120, h = 36) =>
      `<g id="${id}" type="svg-ext-value" transform="translate(${x},${y})">
  <rect width="${w}" height="${h}" rx="4" fill="transparent" stroke="#3a5a7a" stroke-width="1"/>
  <text x="${w / 2}" y="${h / 2 + 4}" text-anchor="middle" fill="#e0e0e0" font-size="14" font-family="Arial" data-bind-target="text" data-bind-prop="text">标签文字</text>
</g>`
  }
]

/** 获取图元分类列表 */
export const svgWidgetCategories = (): string[] => {
  return [...new Set(svgWidgets.map((w) => w.category))]
}

/** 按分类获取图元 */
export const getSvgWidgetsByCategory = (category: string): SvgWidgetDef[] => {
  return svgWidgets.filter((w) => w.category === category)
}

/** 按 typeTag 查找图元定义 */
export const getSvgWidgetByTypeTag = (typeTag: string): SvgWidgetDef | undefined => {
  return svgWidgets.find((w) => w.typeTag === typeTag && w.name !== undefined)
}

/** 生成唯一图元 ID */
export { genId }
