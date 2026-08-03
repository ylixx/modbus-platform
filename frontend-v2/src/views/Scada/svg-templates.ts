/**
 * SVG 图元模板系统 — 照搬 FUXA 架构
 *
 * 每种图元定义：
 * - TypeTag: SVG type 属性前缀（如 'svg-ext-value'）
 * - LabelTag: UI 显示名称
 * - Category: 所属分类
 * - createSvg(id, x, y, w, h): 生成 SVG 字符串
 * - defaultWidth / defaultHeight: 默认尺寸
 */

export interface GaugeTypeDef {
  typeTag: string // SVG type 属性，如 'svg-ext-value'
  label: string // UI 显示名
  category: string // 分类：basic / controls / pipes / charts / media
  icon: string // 工具箱图标（emoji 或 SVG path）
  defaultWidth: number
  defaultHeight: number
  /** 生成 SVG 字符串 */
  createSvg: (id: string, x: number, y: number, w: number, h: number) => string
}

// ── 工具函数 ──

function gWrap(
  id: string,
  type: string,
  x: number,
  y: number,
  _w: number,
  _h: number,
  inner: string
): string {
  return `<g id="${id}" type="${type}" transform="translate(${x}, ${y})" style="cursor:default">${inner}</g>`
}

function rectBody(w: number, h: number, fill = '#374151', stroke = '#6b7280', rx = 2): string {
  return `<rect width="${w}" height="${h}" fill="${fill}" stroke="${stroke}" stroke-width="1" rx="${rx}"/>`
}

function textCenter(w: number, h: number, text: string, fill = '#e5e7eb', size = 14): string {
  return `<text x="${w / 2}" y="${h / 2}" text-anchor="middle" dominant-baseline="central" fill="${fill}" font-size="${size}" font-family="monospace">${text}</text>`
}

// ── 1. Value 文本输出 ──

const ValueDef: GaugeTypeDef = {
  typeTag: 'svg-ext-value',
  label: '数值显示',
  category: 'basic',
  icon: '🔢',
  defaultWidth: 120,
  defaultHeight: 40,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-value',
      x,
      y,
      w,
      h,
      `${rectBody(w, h, '#1e293b', '#334155')}
     ${textCenter(w, h, '0.0')}`
    )
}

// ── 2. Input 输入框 ──

const InputDef: GaugeTypeDef = {
  typeTag: 'svg-ext-input',
  label: '输入框',
  category: 'controls',
  icon: '✏️',
  defaultWidth: 120,
  defaultHeight: 40,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-input',
      x,
      y,
      w,
      h,
      `${rectBody(w, h, '#1e293b', '#3b82f6', 4)}
     ${textCenter(w, h, '输入...', '#64748b')}`
    )
}

// ── 3. Button 按钮 ──

const ButtonDef: GaugeTypeDef = {
  typeTag: 'svg-ext-button',
  label: '按钮',
  category: 'controls',
  icon: '🔘',
  defaultWidth: 100,
  defaultHeight: 44,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-button',
      x,
      y,
      w,
      h,
      `${rectBody(w, h, '#3b82f6', '#2563eb', 4)}
     ${textCenter(w, h, '按钮', '#ffffff')}`
    )
}

// ── 4. Gauge 仪表盘 ──

const GaugeDef: GaugeTypeDef = {
  typeTag: 'svg-ext-gauge',
  label: '仪表盘',
  category: 'charts',
  icon: '📊',
  defaultWidth: 160,
  defaultHeight: 120,
  createSvg: (id, x, y, w, h) => {
    const cx = w / 2,
      cy = h * 0.7,
      r = Math.min(w, h) * 0.38
    const startAngle = (-225 * Math.PI) / 180
    const endAngle = (45 * Math.PI) / 180
    const x1 = cx + r * Math.cos(startAngle),
      y1 = cy + r * Math.sin(startAngle)
    const x2 = cx + r * Math.cos(endAngle),
      y2 = cy + r * Math.sin(endAngle)
    return gWrap(
      id,
      'svg-ext-gauge',
      x,
      y,
      w,
      h,
      `<circle cx="${cx}" cy="${cy}" r="${r + 8}" fill="none" stroke="#334155" stroke-width="12" stroke-dasharray="${Math.PI * (r + 8) * 0.75} ${Math.PI * (r + 8) * 0.25}" transform="rotate(135, ${cx}, ${cy})"/>
       <path d="M${x1},${y1} A${r},${r} 0 1 1 ${x2},${y2}" fill="none" stroke="#3b82f6" stroke-width="6" stroke-linecap="round"/>
       <text x="${cx}" y="${cy - 5}" text-anchor="middle" fill="#e5e7eb" font-size="22" font-family="monospace">0.0</text>
       <text x="${cx}" y="${cy + 18}" text-anchor="middle" fill="#6b7280" font-size="10">单位</text>`
    )
  }
}

// ── 5. Progress 进度条 ──

const ProgressDef: GaugeTypeDef = {
  typeTag: 'svg-ext-progress',
  label: '进度条',
  category: 'charts',
  icon: '📈',
  defaultWidth: 200,
  defaultHeight: 30,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-progress',
      x,
      y,
      w,
      h,
      `<rect width="${w}" height="${h}" fill="#1e293b" stroke="#334155" rx="4"/>
     <rect width="${w * 0.5}" height="${h}" fill="#3b82f6" rx="4"/>
     <text x="${w / 2}" y="${h / 2}" text-anchor="middle" dominant-baseline="central" fill="#e5e7eb" font-size="12" font-family="monospace">50%</text>`
    )
}

// ── 6. LED 信号灯 ──

const LedDef: GaugeTypeDef = {
  typeTag: 'svg-ext-led',
  label: '信号灯',
  category: 'basic',
  icon: '🟢',
  defaultWidth: 40,
  defaultHeight: 40,
  createSvg: (id, x, y, w, h) => {
    const cx = w / 2,
      cy = h / 2,
      r = Math.min(w, h) * 0.38
    return gWrap(
      id,
      'svg-ext-led',
      x,
      y,
      w,
      h,
      `<circle cx="${cx}" cy="${cy}" r="${r + 3}" fill="#1e293b" stroke="#334155"/>
       <circle cx="${cx}" cy="${cy}" r="${r}" fill="#003a00"/>
       <circle cx="${cx - 2}" cy="${cy - 2}" r="${r * 0.3}" fill="rgba(255,255,255,0.15)"/>`
    )
  }
}

// ── 7. Semaphore 三色灯 ──

const SemaphoreDef: GaugeTypeDef = {
  typeTag: 'svg-ext-semaphore',
  label: '三色灯',
  category: 'basic',
  icon: '🚦',
  defaultWidth: 40,
  defaultHeight: 120,
  createSvg: (id, x, y, w, h) => {
    const cx = w / 2,
      r = w * 0.3
    return gWrap(
      id,
      'svg-ext-semaphore',
      x,
      y,
      w,
      h,
      `<rect width="${w}" height="${h}" fill="#1e293b" stroke="#334155" rx="6"/>
       <circle cx="${cx}" cy="${h * 0.2}" r="${r}" fill="#3a0000"/>
       <circle cx="${cx}" cy="${h * 0.5}" r="${r}" fill="#3a3a00"/>
       <circle cx="${cx}" cy="${h * 0.8}" r="${r}" fill="#003a00"/>`
    )
  }
}

// ── 8. Shapes 通用形状 ──

const ShapesDef: GaugeTypeDef = {
  typeTag: 'svg-ext-shapes',
  label: '矩形',
  category: 'basic',
  icon: '⬜',
  defaultWidth: 100,
  defaultHeight: 60,
  createSvg: (id, x, y, w, h) =>
    gWrap(id, 'svg-ext-shapes', x, y, w, h, rectBody(w, h, '#374151', '#6b7280', 2))
}

// ── 9. Circle 圆形 ──

const CircleDef: GaugeTypeDef = {
  typeTag: 'svg-ext-shapes-circle',
  label: '圆形',
  category: 'basic',
  icon: '⚪',
  defaultWidth: 60,
  defaultHeight: 60,
  createSvg: (id, x, y, w, h) => {
    const cx = w / 2,
      cy = h / 2,
      r = Math.min(w, h) * 0.45
    return gWrap(
      id,
      'svg-ext-shapes-circle',
      x,
      y,
      w,
      h,
      `<circle cx="${cx}" cy="${cy}" r="${r}" fill="#374151" stroke="#6b7280" stroke-width="1"/>`
    )
  }
}

// ── 10. Line 线条 ──

const LineDef: GaugeTypeDef = {
  typeTag: 'svg-ext-shapes-line',
  label: '线条',
  category: 'basic',
  icon: '📏',
  defaultWidth: 100,
  defaultHeight: 2,
  createSvg: (id, x, y, w, _h) =>
    gWrap(
      id,
      'svg-ext-shapes-line',
      x,
      y,
      w,
      2,
      `<line x1="0" y1="1" x2="${w}" y2="1" stroke="#6b7280" stroke-width="2"/>`
    )
}

// ── 11. Text 文本 ──

const TextDef: GaugeTypeDef = {
  typeTag: 'svg-ext-shapes-text',
  label: '文本',
  category: 'basic',
  icon: '📝',
  defaultWidth: 100,
  defaultHeight: 30,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-shapes-text',
      x,
      y,
      w,
      h,
      `<text x="4" y="${h / 2}" dominant-baseline="central" fill="#e5e7eb" font-size="14">文本</text>`
    )
}

// ── 12. Pipe 管道 ──

const PipeDef: GaugeTypeDef = {
  typeTag: 'svg-ext-pipe',
  label: '管道',
  category: 'pipes',
  icon: '🔗',
  defaultWidth: 120,
  defaultHeight: 20,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-pipe',
      x,
      y,
      w,
      h,
      `<line x1="0" y1="${h / 2}" x2="${w}" y2="${h / 2}" stroke="#3b82f6" stroke-width="${h}" stroke-linecap="round" class="pipe-flow" stroke-dasharray="8 4"/>`
    )
}

// ── 13. Switch 开关 ──

const SwitchDef: GaugeTypeDef = {
  typeTag: 'svg-ext-switch',
  label: '开关',
  category: 'controls',
  icon: '🔀',
  defaultWidth: 60,
  defaultHeight: 30,
  createSvg: (id, x, y, w, h) => {
    const r = h * 0.38
    return gWrap(
      id,
      'svg-ext-switch',
      x,
      y,
      w,
      h,
      `<rect width="${w}" height="${h}" fill="#374151" stroke="#4b5563" rx="${h / 2}"/>
       <circle cx="${w * 0.25}" cy="${h / 2}" r="${r}" fill="#6b7280"/>`
    )
  }
}

// ── 14. Slider 滑块 ──

const SliderDef: GaugeTypeDef = {
  typeTag: 'svg-ext-slider',
  label: '滑块',
  category: 'controls',
  icon: '🎚️',
  defaultWidth: 200,
  defaultHeight: 30,
  createSvg: (id, x, y, w, h) => {
    const cy = h / 2
    return gWrap(
      id,
      'svg-ext-slider',
      x,
      y,
      w,
      h,
      `<rect x="10" y="${cy - 3}" width="${w - 20}" height="6" fill="#374151" rx="3"/>
       <circle cx="${w * 0.5}" cy="${cy}" r="10" fill="#3b82f6" stroke="#2563eb" stroke-width="2"/>`
    )
  }
}

// ── 15. Chart 趋势图 ──

const ChartDef: GaugeTypeDef = {
  typeTag: 'svg-ext-chart',
  label: '趋势图',
  category: 'charts',
  icon: '📉',
  defaultWidth: 300,
  defaultHeight: 200,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-chart',
      x,
      y,
      w,
      h,
      `${rectBody(w, h, '#1e293b', '#334155', 4)}
     <line x1="40" y1="${h - 30}" x2="${w - 10}" y2="${h - 30}" stroke="#334155"/>
     <line x1="40" y1="10" x2="40" y2="${h - 30}" stroke="#334155"/>
     <text x="${w / 2}" y="${h / 2}" text-anchor="middle" fill="#4b5563" font-size="12">Chart</text>`
    )
}

// ── 16. Select 下拉选择 ──

const SelectDef: GaugeTypeDef = {
  typeTag: 'svg-ext-select',
  label: '下拉选择',
  category: 'controls',
  icon: '📋',
  defaultWidth: 120,
  defaultHeight: 36,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-select',
      x,
      y,
      w,
      h,
      `${rectBody(w, h, '#1e293b', '#4b5563', 4)}
     ${textCenter(w * 0.85, h, '选择...', '#64748b')}
     <polygon points="${w - 18},${h / 2 - 4} ${w - 10},${h / 2 - 4} ${w - 14},${h / 2 + 4}" fill="#6b7280"/>`
    )
}

// ── 17. Image 图片 ──

const ImageDef: GaugeTypeDef = {
  typeTag: 'svg-ext-image',
  label: '图片',
  category: 'media',
  icon: '🖼️',
  defaultWidth: 120,
  defaultHeight: 80,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-image',
      x,
      y,
      w,
      h,
      `<rect width="${w}" height="${h}" fill="#1e293b" stroke="#334155" rx="2"/>
     <text x="${w / 2}" y="${h / 2}" text-anchor="middle" dominant-baseline="central" fill="#4b5563" font-size="24">📷</text>`
    )
}

// ── 18. Iframe 内嵌框架 ──

const IframeDef: GaugeTypeDef = {
  typeTag: 'svg-ext-iframe',
  label: '内嵌网页',
  category: 'media',
  icon: '🌐',
  defaultWidth: 320,
  defaultHeight: 240,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-iframe',
      x,
      y,
      w,
      h,
      `<rect width="${w}" height="${h}" fill="#1e293b" stroke="#334155" rx="2"/>
     <text x="${w / 2}" y="${h / 2}" text-anchor="middle" dominant-baseline="central" fill="#4b5563" font-size="14">URL</text>`
    )
}

// ── 19. Table 数据表格 ──

const TableDef: GaugeTypeDef = {
  typeTag: 'svg-ext-table',
  label: '数据表格',
  category: 'charts',
  icon: '📊',
  defaultWidth: 300,
  defaultHeight: 200,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-table',
      x,
      y,
      w,
      h,
      `${rectBody(w, h, '#1e293b', '#334155', 2)}
     <line x1="0" y1="30" x2="${w}" y2="30" stroke="#334155"/>
     <text x="${w / 2}" y="18" text-anchor="middle" fill="#6b7280" font-size="11">表头</text>
     <text x="${w / 2}" y="${h / 2}" text-anchor="middle" fill="#4b5563" font-size="12">Table</text>`
    )
}

// ── 20. Panel 面板 ──

const PanelDef: GaugeTypeDef = {
  typeTag: 'svg-ext-panel',
  label: '面板容器',
  category: 'basic',
  icon: '📦',
  defaultWidth: 300,
  defaultHeight: 200,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-panel',
      x,
      y,
      w,
      h,
      `<rect width="${w}" height="${h}" fill="rgba(30,41,59,0.8)" stroke="#334155" rx="4"/>
     <rect width="${w}" height="28" fill="#334155" rx="4"/>
     <rect y="24" width="${w}" height="4" fill="#334155"/>
     <text x="8" y="17" fill="#9ca3af" font-size="11">Panel</text>`
    )
}

// ── 21. ProcEng 工程形状 ──

const ProcEngDef: GaugeTypeDef = {
  typeTag: 'svg-ext-proceng',
  label: '工程图元',
  category: 'basic',
  icon: '⚙️',
  defaultWidth: 80,
  defaultHeight: 80,
  createSvg: (id, x, y, w, h) => {
    const cx = w / 2,
      cy = h / 2,
      r = Math.min(w, h) * 0.35
    return gWrap(
      id,
      'svg-ext-proceng',
      x,
      y,
      w,
      h,
      `<circle cx="${cx}" cy="${cy}" r="${r}" fill="#1e293b" stroke="#6b7280" stroke-width="2"/>
       <line x1="${cx}" y1="${cy - r}" x2="${cx}" y2="${cy + r}" stroke="#6b7280" stroke-width="1.5"/>
       <line x1="${cx - r}" y1="${cy}" x2="${cx + r}" y2="${cy}" stroke="#6b7280" stroke-width="1.5"/>
       <circle cx="${cx}" cy="${cy}" r="3" fill="#6b7280"/>`
    )
  }
}

// ── 22. APE 叶片形状（风机/泵） ──

const ApeDef: GaugeTypeDef = {
  typeTag: 'svg-ext-apeshapes',
  label: '风机/泵',
  category: 'basic',
  icon: '🌀',
  defaultWidth: 80,
  defaultHeight: 80,
  createSvg: (id, x, y, w, h) => {
    const cx = w / 2,
      cy = h / 2,
      r = Math.min(w, h) * 0.35
    return gWrap(
      id,
      'svg-ext-apeshapes',
      x,
      y,
      w,
      h,
      `<circle cx="${cx}" cy="${cy}" r="${r + 4}" fill="#1e293b" stroke="#4b5563" stroke-width="2"/>
       <g class="ape-blade">
         <line x1="${cx}" y1="${cy - r}" x2="${cx}" y2="${cy + r}" stroke="#3b82f6" stroke-width="2"/>
         <line x1="${cx - r}" y1="${cy}" x2="${cx + r}" y2="${cy}" stroke="#3b82f6" stroke-width="2"/>
       </g>
       <circle cx="${cx}" cy="${cy}" r="5" fill="#1e293b" stroke="#4b5563"/>`
    )
  }
}

// ── 23. Video 视频 ──

const VideoDef: GaugeTypeDef = {
  typeTag: 'svg-ext-video',
  label: '视频',
  category: 'media',
  icon: '🎥',
  defaultWidth: 320,
  defaultHeight: 240,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-video',
      x,
      y,
      w,
      h,
      `<rect width="${w}" height="${h}" fill="#000" stroke="#334155" rx="2"/>
     <polygon points="${w / 2 - 15},${h / 2 - 12} ${w / 2 - 15},${h / 2 + 12} ${w / 2 + 18},${h / 2}" fill="#4b5563"/>`
    )
}

// ── 24. Scheduler 调度器 ──

const SchedulerDef: GaugeTypeDef = {
  typeTag: 'svg-ext-scheduler',
  label: '调度器',
  category: 'charts',
  icon: '⏰',
  defaultWidth: 280,
  defaultHeight: 100,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-scheduler',
      x,
      y,
      w,
      h,
      `${rectBody(w, h, '#1e293b', '#334155', 4)}
     <text x="${w / 2}" y="${h / 2}" text-anchor="middle" dominant-baseline="central" fill="#4b5563" font-size="12">Schedule</text>`
    )
}

// ── 25. Tank 罐体 ──

const TankDef: GaugeTypeDef = {
  typeTag: 'svg-ext-tank',
  label: '罐体',
  category: 'basic',
  icon: '🛢️',
  defaultWidth: 80,
  defaultHeight: 120,
  createSvg: (id, x, y, w, h) =>
    gWrap(
      id,
      'svg-ext-tank',
      x,
      y,
      w,
      h,
      `<rect x="8" y="0" width="${w - 16}" height="${h}" fill="#1e293b" stroke="#4b5563" rx="2"/>
     <ellipse cx="${w / 2}" cy="4" rx="${(w - 16) / 2}" ry="4" fill="#374151" stroke="#4b5563"/>
     <rect x="8" y="${h * 0.4}" width="${w - 16}" height="${h * 0.6}" fill="#3b82f680" rx="0"/>`
    )
}

// ── 注册所有图元 ──

export const GAUGE_DEFS: GaugeTypeDef[] = [
  ValueDef,
  InputDef,
  ButtonDef,
  GaugeDef,
  ProgressDef,
  LedDef,
  SemaphoreDef,
  ShapesDef,
  CircleDef,
  LineDef,
  TextDef,
  PipeDef,
  SwitchDef,
  SliderDef,
  ChartDef,
  SelectDef,
  ImageDef,
  IframeDef,
  TableDef,
  PanelDef,
  ProcEngDef,
  ApeDef,
  VideoDef,
  SchedulerDef,
  TankDef
]

export const GAUGE_DEF_MAP = new Map(GAUGE_DEFS.map((d) => [d.typeTag, d]))

// ── 分类 ──

export interface GaugeCategory {
  key: string
  label: string
  defs: GaugeTypeDef[]
}

export const GAUGE_CATEGORIES: GaugeCategory[] = [
  {
    key: 'basic',
    label: '基础图元',
    defs: [
      ValueDef,
      TextDef,
      ShapesDef,
      CircleDef,
      LineDef,
      LedDef,
      SemaphoreDef,
      PanelDef,
      ProcEngDef,
      ApeDef,
      TankDef
    ]
  },
  { key: 'controls', label: '控件', defs: [InputDef, ButtonDef, SwitchDef, SliderDef, SelectDef] },
  { key: 'pipes', label: '管道', defs: [PipeDef] },
  { key: 'charts', label: '图表', defs: [GaugeDef, ProgressDef, ChartDef, TableDef, SchedulerDef] },
  { key: 'media', label: '媒体', defs: [ImageDef, IframeDef, VideoDef] }
]

/** 通过 typeTag 查找图元定义 */
export function getGaugeDef(typeTag: string): GaugeTypeDef | undefined {
  return GAUGE_DEF_MAP.get(typeTag) || GAUGE_DEFS.find((d) => typeTag.startsWith(d.typeTag))
}
