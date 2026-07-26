/**
 * 内置工业 SCADA 图元定义
 * 使用 Fabric.js 基本图形组合绘制
 */

export interface BuiltinWidget {
  type: string
  name: string
  category: string
  icon: string
  defaultWidth: number
  defaultHeight: number
  /** 创建 Fabric.js 对象的工厂函数（序列化为 JSON 存储） */
  createFabric: (opts?: any) => any
}

// ── 辅助：创建 Fabric JSON 对象 ──

function rect(opts: any = {}) {
  return {
    type: 'rect',
    left: opts.left || 0,
    top: opts.top || 0,
    width: opts.width || 100,
    height: opts.height || 100,
    fill: opts.fill || '#2a5a8a',
    stroke: opts.stroke || '#3a8fd4',
    strokeWidth: opts.strokeWidth || 2,
    rx: opts.rx || 0,
    ry: opts.ry || 0,
    selectable: true,
    ...opts
  }
}

function circle(opts: any = {}) {
  return {
    type: 'circle',
    left: opts.left || 0,
    top: opts.top || 0,
    radius: opts.radius || 30,
    fill: opts.fill || '#2a5a8a',
    stroke: opts.stroke || '#3a8fd4',
    strokeWidth: opts.strokeWidth || 2,
    selectable: true,
    ...opts
  }
}

function text(str: string, opts: any = {}) {
  return {
    type: 'textbox',
    text: str,
    left: opts.left || 0,
    top: opts.top || 0,
    width: opts.width || 100,
    fontSize: opts.fontSize || 14,
    fill: opts.fill || '#e0e0e0',
    fontFamily: 'Arial',
    textAlign: 'center',
    originX: 'center',
    originY: 'center',
    selectable: false,
    evented: false,
    ...opts
  }
}

function line(points: number[], opts: any = {}) {
  return {
    type: 'line',
    x1: points[0],
    y1: points[1],
    x2: points[2],
    y2: points[3],
    stroke: opts.stroke || '#3a8fd4',
    strokeWidth: opts.strokeWidth || 3,
    selectable: false,
    evented: false,
    ...opts
  }
}

// ── 内置图元列表 ──

export const builtinWidgets: BuiltinWidget[] = [
  // ── 容器类 ──
  {
    type: 'tank-vertical',
    name: '立式储罐',
    category: '容器',
    icon: '🏭',
    defaultWidth: 120,
    defaultHeight: 160,
    createFabric: () => ({
      type: 'group',
      objects: [
        // 罐体
        rect({ width: 120, height: 140, top: 20, fill: '#1a3a5a', stroke: '#3a8fd4', rx: 6, ry: 6 }),
        // 顶部
        rect({ width: 140, height: 20, left: -10, fill: '#2a5a8a', stroke: '#3a8fd4', rx: 4, ry: 4 }),
        // 液位指示（内部矩形，可绑定值）
        rect({ left: 10, top: 40, width: 100, height: 100, fill: '#1a6aaa', stroke: 'transparent', rx: 4, ry: 4, _bindTarget: 'level', _bindProp: 'height' }),
        // 标签
        text('储罐', { left: 60, top: 80, fontSize: 16, fill: '#ffffff' })
      ],
      _widgetType: 'tank-vertical',
      _bindable: ['level', 'temperature', 'pressure']
    })
  },
  {
    type: 'tank-horizontal',
    name: '卧式储罐',
    category: '容器',
    icon: '🛢️',
    defaultWidth: 180,
    defaultHeight: 100,
    createFabric: () => ({
      type: 'group',
      objects: [
        rect({ width: 180, height: 100, fill: '#1a3a5a', stroke: '#3a8fd4', rx: 20, ry: 20 }),
        rect({ left: 10, top: 15, width: 160, height: 70, fill: '#1a6aaa', stroke: 'transparent', rx: 14, ry: 14, _bindTarget: 'level', _bindProp: 'width' }),
        text('卧式罐', { left: 90, top: 50, fontSize: 14, fill: '#ffffff' })
      ],
      _widgetType: 'tank-horizontal',
      _bindable: ['level', 'temperature']
    })
  },

  // ── 阀门类 ──
  {
    type: 'valve-ball',
    name: '球阀',
    category: '阀门',
    icon: '🔴',
    defaultWidth: 80,
    defaultHeight: 60,
    createFabric: () => ({
      type: 'group',
      objects: [
        // 阀体（圆）
        { type: 'circle', left: 40, top: 30, radius: 25, fill: '#2a5a8a', stroke: '#3a8fd4', strokeWidth: 2 },
        // 手柄
        line([40, 5, 40, 20], { stroke: '#f0a030', strokeWidth: 4 }),
        // 左管
        line([0, 30, 15, 30], { stroke: '#3a8fd4', strokeWidth: 6 }),
        // 右管
        line([65, 30, 80, 30], { stroke: '#3a8fd4', strokeWidth: 6 }),
        text('球阀', { left: 40, top: 65, fontSize: 11, fill: '#a0c0e0' })
      ],
      _widgetType: 'valve-ball',
      _bindable: ['state', 'position']
    })
  },
  {
    type: 'valve-butterfly',
    name: '蝶阀',
    category: '阀门',
    icon: '🟡',
    defaultWidth: 80,
    defaultHeight: 60,
    createFabric: () => ({
      type: 'group',
      objects: [
        { type: 'circle', left: 40, top: 30, radius: 25, fill: '#2a4a3a', stroke: '#4ac080', strokeWidth: 2 },
        // 蝶板（斜线）
        line([25, 15, 55, 45], { stroke: '#4ac080', strokeWidth: 3 }),
        line([0, 30, 15, 30], { stroke: '#4ac080', strokeWidth: 6 }),
        line([65, 30, 80, 30], { stroke: '#4ac080', strokeWidth: 6 }),
        text('蝶阀', { left: 40, top: 65, fontSize: 11, fill: '#a0e0c0' })
      ],
      _widgetType: 'valve-butterfly',
      _bindable: ['state', 'position']
    })
  },

  // ── 泵/电机类 ──
  {
    type: 'pump-centrifugal',
    name: '离心泵',
    category: '动力',
    icon: '⚙️',
    defaultWidth: 80,
    defaultHeight: 80,
    createFabric: () => ({
      type: 'group',
      objects: [
        // 泵体（圆）
        { type: 'circle', left: 40, top: 40, radius: 30, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 2 },
        // 叶轮（三角形近似）
        line([40, 20, 25, 55], { stroke: '#f0a030', strokeWidth: 3 }),
        line([40, 20, 55, 55], { stroke: '#f0a030', strokeWidth: 3 }),
        line([25, 55, 55, 55], { stroke: '#f0a030', strokeWidth: 2 }),
        // 进口
        line([0, 40, 10, 40], { stroke: '#3a8fd4', strokeWidth: 6 }),
        // 出口
        line([70, 40, 80, 40], { stroke: '#3a8fd4', strokeWidth: 6 }),
        text('泵', { left: 40, top: 80, fontSize: 11, fill: '#a0c0e0' })
      ],
      _widgetType: 'pump-centrifugal',
      _bindable: ['state', 'speed', 'flow']
    })
  },
  {
    type: 'motor',
    name: '电机',
    category: '动力',
    icon: '🔌',
    defaultWidth: 70,
    defaultHeight: 70,
    createFabric: () => ({
      type: 'group',
      objects: [
        // 电机外壳（圆角矩形）
        rect({ width: 70, height: 50, top: 10, fill: '#3a3a3a', stroke: '#6a6a6a', rx: 10, ry: 10 }),
        // 轴
        rect({ left: 60, top: 22, width: 10, height: 6, fill: '#8a8a8a', stroke: 'transparent' }),
        // M 标志
        text('M', { left: 35, top: 35, fontSize: 20, fill: '#ffffff', fontWeight: 'bold' }),
        text('电机', { left: 35, top: 70, fontSize: 11, fill: '#a0a0a0' })
      ],
      _widgetType: 'motor',
      _bindable: ['state', 'speed', 'current']
    })
  },

  // ── 管道类 ──
  {
    type: 'pipe-horizontal',
    name: '水平管道',
    category: '管道',
    icon: '➖',
    defaultWidth: 150,
    defaultHeight: 20,
    createFabric: () => ({
      type: 'group',
      objects: [
        rect({ width: 150, height: 20, fill: '#2a5a8a', stroke: '#3a8fd4', strokeWidth: 1, rx: 4, ry: 4 }),
        // 流向箭头
        line([30, 10, 120, 10], { stroke: '#4ac080', strokeWidth: 2 }),
        line([110, 5, 120, 10], { stroke: '#4ac080', strokeWidth: 2 }),
        line([110, 15, 120, 10], { stroke: '#4ac080', strokeWidth: 2 })
      ],
      _widgetType: 'pipe-horizontal',
      _bindable: ['flow', 'pressure']
    })
  },
  {
    type: 'pipe-vertical',
    name: '垂直管道',
    category: '管道',
    icon: '↕️',
    defaultWidth: 20,
    defaultHeight: 150,
    createFabric: () => ({
      type: 'group',
      objects: [
        rect({ width: 20, height: 150, fill: '#2a5a8a', stroke: '#3a8fd4', strokeWidth: 1, rx: 4, ry: 4 }),
        line([10, 30, 10, 120], { stroke: '#4ac080', strokeWidth: 2 }),
        line([5, 110, 10, 120], { stroke: '#4ac080', strokeWidth: 2 }),
        line([15, 110, 10, 120], { stroke: '#4ac080', strokeWidth: 2 })
      ],
      _widgetType: 'pipe-vertical',
      _bindable: ['flow', 'pressure']
    })
  },

  // ── 仪表类 ──
  {
    type: 'gauge',
    name: '表盘',
    category: '仪表',
    icon: '📊',
    defaultWidth: 120,
    defaultHeight: 120,
    createFabric: () => ({
      type: 'group',
      objects: [
        // 表盘底座
        { type: 'circle', left: 60, top: 60, radius: 55, fill: '#1a1a2e', stroke: '#3a8fd4', strokeWidth: 2 },
        // 内圈
        { type: 'circle', left: 60, top: 60, radius: 45, fill: 'transparent', stroke: '#2a4a6a', strokeWidth: 1 },
        // 刻度线（简化为几条线）
        line([60, 15, 60, 25], { stroke: '#6a8ab0', strokeWidth: 2 }),
        line([105, 60, 95, 60], { stroke: '#6a8ab0', strokeWidth: 2 }),
        line([60, 105, 60, 95], { stroke: '#6a8ab0', strokeWidth: 2 }),
        line([15, 60, 25, 60], { stroke: '#6a8ab0', strokeWidth: 2 }),
        // 指针
        line([60, 60, 85, 35], { stroke: '#f04040', strokeWidth: 3 }),
        // 中心点
        { type: 'circle', left: 60, top: 60, radius: 5, fill: '#f04040', stroke: 'transparent' },
        // 数值显示
        text('0.0', { left: 60, top: 80, fontSize: 14, fill: '#4ac080', _bindTarget: 'value', _bindProp: 'text' }),
        text('单位', { left: 60, top: 98, fontSize: 10, fill: '#6a8ab0' })
      ],
      _widgetType: 'gauge',
      _bindable: ['value', 'min', 'max']
    })
  },
  {
    type: 'thermometer',
    name: '温度计',
    category: '仪表',
    icon: '🌡️',
    defaultWidth: 40,
    defaultHeight: 140,
    createFabric: () => ({
      type: 'group',
      objects: [
        // 外管
        rect({ left: 12, top: 0, width: 16, height: 110, fill: 'transparent', stroke: '#6a8ab0', strokeWidth: 1, rx: 8, ry: 8 }),
        // 液柱（可绑定温度值）
        rect({ left: 15, top: 30, width: 10, height: 70, fill: '#f04040', stroke: 'transparent', rx: 5, ry: 5, _bindTarget: 'value', _bindProp: 'height' }),
        // 底部圆球
        { type: 'circle', left: 20, top: 110, radius: 14, fill: '#f04040', stroke: '#6a8ab0', strokeWidth: 1 },
        // 数值
        text('0℃', { left: 20, top: 135, fontSize: 11, fill: '#e0e0e0', _bindTarget: 'value', _bindProp: 'text' })
      ],
      _widgetType: 'thermometer',
      _bindable: ['value', 'unit']
    })
  },
  {
    type: 'progress-bar',
    name: '进度条',
    category: '仪表',
    icon: '📶',
    defaultWidth: 160,
    defaultHeight: 40,
    createFabric: () => ({
      type: 'group',
      objects: [
        // 背景
        rect({ width: 160, height: 30, top: 5, fill: '#1a1a2e', stroke: '#3a5a7a', strokeWidth: 1, rx: 4, ry: 4 }),
        // 填充（可绑定值）
        rect({ left: 3, top: 8, width: 80, height: 24, fill: '#3a8fd4', stroke: 'transparent', rx: 3, ry: 3, _bindTarget: 'value', _bindProp: 'width' }),
        // 数值
        text('50%', { left: 80, top: 20, fontSize: 12, fill: '#ffffff', _bindTarget: 'value', _bindProp: 'text' })
      ],
      _widgetType: 'progress-bar',
      _bindable: ['value', 'min', 'max']
    })
  },

  // ── 指示灯类 ──
  {
    type: 'indicator-light',
    name: '指示灯',
    category: '指示',
    icon: '💡',
    defaultWidth: 50,
    defaultHeight: 60,
    createFabric: () => ({
      type: 'group',
      objects: [
        { type: 'circle', left: 25, top: 25, radius: 20, fill: '#2a2a2a', stroke: '#4a4a4a', strokeWidth: 2 },
        { type: 'circle', left: 25, top: 25, radius: 14, fill: '#00ff00', stroke: 'transparent', _bindTarget: 'state', _bindProp: 'fill' },
        text('运行', { left: 25, top: 55, fontSize: 11, fill: '#a0a0a0' })
      ],
      _widgetType: 'indicator-light',
      _bindable: ['state']
    })
  },
  {
    type: 'alarm-light',
    name: '报警灯',
    category: '指示',
    icon: '🚨',
    defaultWidth: 50,
    defaultHeight: 70,
    createFabric: () => ({
      type: 'group',
      objects: [
        // 灯罩
        { type: 'circle', left: 25, top: 25, radius: 22, fill: '#3a1a1a', stroke: '#aa4040', strokeWidth: 2 },
        // 灯芯
        { type: 'circle', left: 25, top: 25, radius: 15, fill: '#ff0000', stroke: 'transparent', _bindTarget: 'state', _bindProp: 'fill' },
        // 底座
        rect({ left: 10, top: 48, width: 30, height: 10, fill: '#4a4a4a', stroke: '#6a6a6a', rx: 2, ry: 2 }),
        text('报警', { left: 25, top: 68, fontSize: 11, fill: '#aa4040' })
      ],
      _widgetType: 'alarm-light',
      _bindable: ['state', 'level']
    })
  },

  // ── 控件类 ──
  {
    type: 'push-button',
    name: '按钮',
    category: '控件',
    icon: '🔘',
    defaultWidth: 80,
    defaultHeight: 40,
    createFabric: () => ({
      type: 'group',
      objects: [
        rect({ width: 80, height: 40, fill: '#3a5a7a', stroke: '#5a8ab0', strokeWidth: 2, rx: 6, ry: 6 }),
        text('按钮', { left: 40, top: 20, fontSize: 14, fill: '#ffffff' })
      ],
      _widgetType: 'push-button',
      _bindable: ['action']
    })
  },
  {
    type: 'switch',
    name: '开关',
    category: '控件',
    icon: '🔀',
    defaultWidth: 70,
    defaultHeight: 40,
    createFabric: () => ({
      type: 'group',
      objects: [
        // 轨道
        rect({ width: 60, height: 28, left: 5, top: 6, fill: '#2a2a2a', stroke: '#4a6a8a', strokeWidth: 1, rx: 14, ry: 14 }),
        // 滑块
        circle({ left: 45, top: 20, radius: 10, fill: '#3a8fd4', stroke: '#5ab0ff', strokeWidth: 1, _bindTarget: 'state', _bindProp: 'left' }),
        text('OFF', { left: 35, top: 40, fontSize: 11, fill: '#a0a0a0', _bindTarget: 'state', _bindProp: 'text' })
      ],
      _widgetType: 'switch',
      _bindable: ['state']
    })
  },

  // ── 文本/标注类 ──
  {
    type: 'label',
    name: '文本标签',
    category: '标注',
    icon: '🏷️',
    defaultWidth: 120,
    defaultHeight: 36,
    createFabric: () => ({
      type: 'group',
      objects: [
        rect({ width: 120, height: 36, fill: 'transparent', stroke: '#3a5a7a', strokeWidth: 1, rx: 4, ry: 4 }),
        text('标签文字', { left: 60, top: 18, fontSize: 14, fill: '#e0e0e0', _bindTarget: 'text', _bindProp: 'text' })
      ],
      _widgetType: 'label',
      _bindable: ['text', 'value']
    })
  },
  {
    type: 'value-display',
    name: '数值显示',
    category: '标注',
    icon: '🔢',
    defaultWidth: 100,
    defaultHeight: 50,
    createFabric: () => ({
      type: 'group',
      objects: [
        rect({ width: 100, height: 50, fill: '#0a1a2a', stroke: '#3a8fd4', strokeWidth: 1, rx: 6, ry: 6 }),
        text('温度', { left: 50, top: 14, fontSize: 11, fill: '#6a8ab0' }),
        text('0.0', { left: 50, top: 34, fontSize: 20, fill: '#4ac080', fontWeight: 'bold', _bindTarget: 'value', _bindProp: 'text' })
      ],
      _widgetType: 'value-display',
      _bindable: ['value', 'unit', 'name']
    })
  }
]

/** 按分类分组 */
export const widgetCategories = (): string[] => {
  return [...new Set(builtinWidgets.map((w) => w.category))]
}

/** 获取指定分类的图元 */
export const getWidgetsByCategory = (category: string): BuiltinWidget[] => {
  return builtinWidgets.filter((w) => w.category === category)
}
