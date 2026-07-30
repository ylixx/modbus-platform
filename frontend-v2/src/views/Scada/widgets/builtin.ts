/**
 * 内置工业 SCADA 图元定义
 * 使用 Fabric.js 类直接构造实例（非序列化 JSON）
 */

import * as fabric from 'fabric'

export interface BuiltinWidget {
  type: string
  name: string
  category: string
  icon: string
  defaultWidth: number
  defaultHeight: number
  /** 创建 Fabric.js 对象实例的工厂函数 */
  createFabric: (opts?: any) => any
}

// ── 辅助：创建 Fabric 对象实例 ──

function rect(opts: any = {}): fabric.Rect {
  return new fabric.Rect({
    width: 100,
    height: 100,
    fill: '#2a5a8a',
    stroke: '#3a8fd4',
    strokeWidth: 2,
    rx: 0,
    ry: 0,
    ...opts
  })
}

function circle(opts: any = {}): fabric.Circle {
  return new fabric.Circle({
    radius: 30,
    fill: '#2a5a8a',
    stroke: '#3a8fd4',
    strokeWidth: 2,
    originX: 'center',
    originY: 'center',
    ...opts
  })
}

function textbox(str: string, opts: any = {}): fabric.Textbox {
  return new fabric.Textbox(str, {
    width: 100,
    fontSize: 14,
    fill: '#e0e0e0',
    fontFamily: 'Arial',
    textAlign: 'center',
    originX: 'center',
    originY: 'center',
    selectable: false,
    evented: false,
    ...opts
  })
}

function line(points: number[], opts: any = {}): fabric.Line {
  return new fabric.Line(points as [number, number, number, number], {
    stroke: '#3a8fd4',
    strokeWidth: 3,
    selectable: false,
    evented: false,
    ...opts
  })
}

function group(objects: fabric.FabricObject[], opts: any = {}): fabric.Group {
  return new fabric.Group(objects, {
    originX: 'left',
    originY: 'top',
    ...opts
  })
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
    createFabric: () => {
      const tankBody = rect({ width: 120, height: 140, top: 20, fill: '#1a3a5a', stroke: '#3a8fd4', rx: 6, ry: 6 })
      const tankTop = rect({ width: 140, height: 20, left: -10, fill: '#2a5a8a', stroke: '#3a8fd4', rx: 4, ry: 4 })
      const level = rect({ left: 10, top: 40, width: 100, height: 100, fill: '#1a6aaa', stroke: 'transparent', rx: 4, ry: 4 })
      ;(level as any)._bindTarget = 'level'
      ;(level as any)._bindProp = 'height'
      const label = textbox('储罐', { left: 60, top: 80, fontSize: 16, fill: '#ffffff' })
      const g = group([tankBody, tankTop, level, label])
      ;(g as any)._widgetType = 'tank-vertical'
      ;(g as any)._bindable = ['level', 'temperature', 'pressure']
      return g
    }
  },
  {
    type: 'tank-horizontal',
    name: '卧式储罐',
    category: '容器',
    icon: '🛢️',
    defaultWidth: 180,
    defaultHeight: 100,
    createFabric: () => {
      const body = rect({ width: 180, height: 100, fill: '#1a3a5a', stroke: '#3a8fd4', rx: 20, ry: 20 })
      const level = rect({ left: 10, top: 15, width: 160, height: 70, fill: '#1a6aaa', stroke: 'transparent', rx: 14, ry: 14 })
      ;(level as any)._bindTarget = 'level'
      ;(level as any)._bindProp = 'width'
      const label = textbox('卧式罐', { left: 90, top: 50, fontSize: 14, fill: '#ffffff' })
      const g = group([body, level, label])
      ;(g as any)._widgetType = 'tank-horizontal'
      ;(g as any)._bindable = ['level', 'temperature']
      return g
    }
  },

  // ── 阀门类 ──
  {
    type: 'valve-ball',
    name: '球阀',
    category: '阀门',
    icon: '🔴',
    defaultWidth: 80,
    defaultHeight: 60,
    createFabric: () => {
      const body = circle({ left: 40, top: 30, radius: 25, fill: '#2a5a8a', stroke: '#3a8fd4', strokeWidth: 2 })
      const handle = line([40, 5, 40, 20], { stroke: '#f0a030', strokeWidth: 4 })
      const pipeL = line([0, 30, 15, 30], { stroke: '#3a8fd4', strokeWidth: 6 })
      const pipeR = line([65, 30, 80, 30], { stroke: '#3a8fd4', strokeWidth: 6 })
      const label = textbox('球阀', { left: 40, top: 65, fontSize: 11, fill: '#a0c0e0' })
      const g = group([body, handle, pipeL, pipeR, label])
      ;(g as any)._widgetType = 'valve-ball'
      ;(g as any)._bindable = ['state', 'position']
      return g
    }
  },
  {
    type: 'valve-butterfly',
    name: '蝶阀',
    category: '阀门',
    icon: '🟡',
    defaultWidth: 80,
    defaultHeight: 60,
    createFabric: () => {
      const body = circle({ left: 40, top: 30, radius: 25, fill: '#2a4a3a', stroke: '#4ac080', strokeWidth: 2 })
      const plate = line([25, 15, 55, 45], { stroke: '#4ac080', strokeWidth: 3 })
      const pipeL = line([0, 30, 15, 30], { stroke: '#4ac080', strokeWidth: 6 })
      const pipeR = line([65, 30, 80, 30], { stroke: '#4ac080', strokeWidth: 6 })
      const label = textbox('蝶阀', { left: 40, top: 65, fontSize: 11, fill: '#a0e0c0' })
      const g = group([body, plate, pipeL, pipeR, label])
      ;(g as any)._widgetType = 'valve-butterfly'
      ;(g as any)._bindable = ['state', 'position']
      return g
    }
  },

  // ── 泵/电机类 ──
  {
    type: 'pump-centrifugal',
    name: '离心泵',
    category: '动力',
    icon: '⚙️',
    defaultWidth: 80,
    defaultHeight: 80,
    createFabric: () => {
      const body = circle({ left: 40, top: 40, radius: 30, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 2 })
      const blade1 = line([40, 20, 25, 55], { stroke: '#f0a030', strokeWidth: 3 })
      const blade2 = line([40, 20, 55, 55], { stroke: '#f0a030', strokeWidth: 3 })
      const blade3 = line([25, 55, 55, 55], { stroke: '#f0a030', strokeWidth: 2 })
      const inlet = line([0, 40, 10, 40], { stroke: '#3a8fd4', strokeWidth: 6 })
      const outlet = line([70, 40, 80, 40], { stroke: '#3a8fd4', strokeWidth: 6 })
      const label = textbox('泵', { left: 40, top: 80, fontSize: 11, fill: '#a0c0e0' })
      const g = group([body, blade1, blade2, blade3, inlet, outlet, label])
      ;(g as any)._widgetType = 'pump-centrifugal'
      ;(g as any)._bindable = ['state', 'speed', 'flow']
      return g
    }
  },
  {
    type: 'motor',
    name: '电机',
    category: '动力',
    icon: '🔌',
    defaultWidth: 70,
    defaultHeight: 70,
    createFabric: () => {
      const shell = rect({ width: 70, height: 50, top: 10, fill: '#3a3a3a', stroke: '#6a6a6a', rx: 10, ry: 10 })
      const shaft = rect({ left: 60, top: 22, width: 10, height: 6, fill: '#8a8a8a', stroke: 'transparent' })
      const m = textbox('M', { left: 35, top: 35, fontSize: 20, fill: '#ffffff', fontWeight: 'bold' })
      const label = textbox('电机', { left: 35, top: 70, fontSize: 11, fill: '#a0a0a0' })
      const g = group([shell, shaft, m, label])
      ;(g as any)._widgetType = 'motor'
      ;(g as any)._bindable = ['state', 'speed', 'current']
      return g
    }
  },

  // ── 管道类 ──
  {
    type: 'pipe-horizontal',
    name: '水平管道',
    category: '管道',
    icon: '➖',
    defaultWidth: 150,
    defaultHeight: 20,
    createFabric: () => {
      const pipe = rect({ width: 150, height: 20, fill: '#2a5a8a', stroke: '#3a8fd4', strokeWidth: 1, rx: 4, ry: 4 })
      const arrow = line([30, 10, 120, 10], { stroke: '#4ac080', strokeWidth: 2 })
      const arrowH1 = line([110, 5, 120, 10], { stroke: '#4ac080', strokeWidth: 2 })
      const arrowH2 = line([110, 15, 120, 10], { stroke: '#4ac080', strokeWidth: 2 })
      const g = group([pipe, arrow, arrowH1, arrowH2])
      ;(g as any)._widgetType = 'pipe-horizontal'
      ;(g as any)._bindable = ['flow', 'pressure']
      return g
    }
  },
  {
    type: 'pipe-vertical',
    name: '垂直管道',
    category: '管道',
    icon: '↕️',
    defaultWidth: 20,
    defaultHeight: 150,
    createFabric: () => {
      const pipe = rect({ width: 20, height: 150, fill: '#2a5a8a', stroke: '#3a8fd4', strokeWidth: 1, rx: 4, ry: 4 })
      const arrow = line([10, 30, 10, 120], { stroke: '#4ac080', strokeWidth: 2 })
      const arrowH1 = line([5, 110, 10, 120], { stroke: '#4ac080', strokeWidth: 2 })
      const arrowH2 = line([15, 110, 10, 120], { stroke: '#4ac080', strokeWidth: 2 })
      const g = group([pipe, arrow, arrowH1, arrowH2])
      ;(g as any)._widgetType = 'pipe-vertical'
      ;(g as any)._bindable = ['flow', 'pressure']
      return g
    }
  },

  // ── 仪表类 ──
  {
    type: 'gauge',
    name: '表盘',
    category: '仪表',
    icon: '📊',
    defaultWidth: 120,
    defaultHeight: 120,
    createFabric: () => {
      const outer = circle({ left: 60, top: 60, radius: 55, fill: '#1a1a2e', stroke: '#3a8fd4', strokeWidth: 2 })
      const inner = circle({ left: 60, top: 60, radius: 45, fill: 'transparent', stroke: '#2a4a6a', strokeWidth: 1 })
      const tick1 = line([60, 15, 60, 25], { stroke: '#6a8ab0', strokeWidth: 2 })
      const tick2 = line([105, 60, 95, 60], { stroke: '#6a8ab0', strokeWidth: 2 })
      const tick3 = line([60, 105, 60, 95], { stroke: '#6a8ab0', strokeWidth: 2 })
      const tick4 = line([15, 60, 25, 60], { stroke: '#6a8ab0', strokeWidth: 2 })
      const pointer = line([60, 60, 85, 35], { stroke: '#f04040', strokeWidth: 3 })
      const center = circle({ left: 60, top: 60, radius: 5, fill: '#f04040', stroke: 'transparent' })
      const valText = textbox('0.0', { left: 60, top: 80, fontSize: 14, fill: '#4ac080' })
      ;(valText as any)._bindTarget = 'value'
      ;(valText as any)._bindProp = 'text'
      const unitText = textbox('单位', { left: 60, top: 98, fontSize: 10, fill: '#6a8ab0' })
      const g = group([outer, inner, tick1, tick2, tick3, tick4, pointer, center, valText, unitText])
      ;(g as any)._widgetType = 'gauge'
      ;(g as any)._bindable = ['value', 'min', 'max']
      return g
    }
  },
  {
    type: 'thermometer',
    name: '温度计',
    category: '仪表',
    icon: '🌡️',
    defaultWidth: 40,
    defaultHeight: 140,
    createFabric: () => {
      const tube = rect({ left: 12, top: 0, width: 16, height: 110, fill: 'transparent', stroke: '#6a8ab0', strokeWidth: 1, rx: 8, ry: 8 })
      const col = rect({ left: 15, top: 30, width: 10, height: 70, fill: '#f04040', stroke: 'transparent', rx: 5, ry: 5 })
      ;(col as any)._bindTarget = 'value'
      ;(col as any)._bindProp = 'height'
      const bulb = circle({ left: 20, top: 110, radius: 14, fill: '#f04040', stroke: '#6a8ab0', strokeWidth: 1 })
      const valText = textbox('0℃', { left: 20, top: 135, fontSize: 11, fill: '#e0e0e0' })
      ;(valText as any)._bindTarget = 'value'
      ;(valText as any)._bindProp = 'text'
      const g = group([tube, col, bulb, valText])
      ;(g as any)._widgetType = 'thermometer'
      ;(g as any)._bindable = ['value', 'unit']
      return g
    }
  },
  {
    type: 'progress-bar',
    name: '进度条',
    category: '仪表',
    icon: '📶',
    defaultWidth: 160,
    defaultHeight: 40,
    createFabric: () => {
      const bg = rect({ width: 160, height: 30, top: 5, fill: '#1a1a2e', stroke: '#3a5a7a', strokeWidth: 1, rx: 4, ry: 4 })
      const fill = rect({ left: 3, top: 8, width: 80, height: 24, fill: '#3a8fd4', stroke: 'transparent', rx: 3, ry: 3 })
      ;(fill as any)._bindTarget = 'value'
      ;(fill as any)._bindProp = 'width'
      const valText = textbox('50%', { left: 80, top: 20, fontSize: 12, fill: '#ffffff' })
      ;(valText as any)._bindTarget = 'value'
      ;(valText as any)._bindProp = 'text'
      const g = group([bg, fill, valText])
      ;(g as any)._widgetType = 'progress-bar'
      ;(g as any)._bindable = ['value', 'min', 'max']
      return g
    }
  },

  // ── 指示灯类 ──
  {
    type: 'indicator-light',
    name: '指示灯',
    category: '指示',
    icon: '💡',
    defaultWidth: 50,
    defaultHeight: 60,
    createFabric: () => {
      const outer = circle({ left: 25, top: 25, radius: 20, fill: '#2a2a2a', stroke: '#4a4a4a', strokeWidth: 2 })
      const inner = circle({ left: 25, top: 25, radius: 14, fill: '#00ff00', stroke: 'transparent' })
      ;(inner as any)._bindTarget = 'state'
      ;(inner as any)._bindProp = 'fill'
      const label = textbox('运行', { left: 25, top: 55, fontSize: 11, fill: '#a0a0a0' })
      const g = group([outer, inner, label])
      ;(g as any)._widgetType = 'indicator-light'
      ;(g as any)._bindable = ['state']
      return g
    }
  },
  {
    type: 'alarm-light',
    name: '报警灯',
    category: '指示',
    icon: '🚨',
    defaultWidth: 50,
    defaultHeight: 70,
    createFabric: () => {
      const dome = circle({ left: 25, top: 25, radius: 22, fill: '#3a1a1a', stroke: '#aa4040', strokeWidth: 2 })
      const core = circle({ left: 25, top: 25, radius: 15, fill: '#ff0000', stroke: 'transparent' })
      ;(core as any)._bindTarget = 'state'
      ;(core as any)._bindProp = 'fill'
      const base = rect({ left: 10, top: 48, width: 30, height: 10, fill: '#4a4a4a', stroke: '#6a6a6a', rx: 2, ry: 2 })
      const label = textbox('报警', { left: 25, top: 68, fontSize: 11, fill: '#aa4040' })
      const g = group([dome, core, base, label])
      ;(g as any)._widgetType = 'alarm-light'
      ;(g as any)._bindable = ['state', 'level']
      return g
    }
  },

  // ── 控件类 ──
  {
    type: 'push-button',
    name: '按钮',
    category: '控件',
    icon: '🔘',
    defaultWidth: 80,
    defaultHeight: 40,
    createFabric: () => {
      const bg = rect({ width: 80, height: 40, fill: '#3a5a7a', stroke: '#5a8ab0', strokeWidth: 2, rx: 6, ry: 6 })
      const label = textbox('按钮', { left: 40, top: 20, fontSize: 14, fill: '#ffffff' })
      const g = group([bg, label])
      ;(g as any)._widgetType = 'push-button'
      ;(g as any)._bindable = ['action']
      return g
    }
  },
  {
    type: 'switch',
    name: '开关',
    category: '控件',
    icon: '🔀',
    defaultWidth: 70,
    defaultHeight: 40,
    createFabric: () => {
      const track = rect({ width: 60, height: 28, left: 5, top: 6, fill: '#2a2a2a', stroke: '#4a6a8a', strokeWidth: 1, rx: 14, ry: 14 })
      const slider = circle({ left: 45, top: 20, radius: 10, fill: '#3a8fd4', stroke: '#5ab0ff', strokeWidth: 1 })
      ;(slider as any)._bindTarget = 'state'
      ;(slider as any)._bindProp = 'left'
      const label = textbox('OFF', { left: 35, top: 40, fontSize: 11, fill: '#a0a0a0' })
      ;(label as any)._bindTarget = 'state'
      ;(label as any)._bindProp = 'text'
      const g = group([track, slider, label])
      ;(g as any)._widgetType = 'switch'
      ;(g as any)._bindable = ['state']
      return g
    }
  },

  // ── 文本/标注类 ──
  {
    type: 'label',
    name: '文本标签',
    category: '标注',
    icon: '🏷️',
    defaultWidth: 120,
    defaultHeight: 36,
    createFabric: () => {
      const bg = rect({ width: 120, height: 36, fill: 'transparent', stroke: '#3a5a7a', strokeWidth: 1, rx: 4, ry: 4 })
      const label = textbox('标签文字', { left: 60, top: 18, fontSize: 14, fill: '#e0e0e0' })
      ;(label as any)._bindTarget = 'text'
      ;(label as any)._bindProp = 'text'
      const g = group([bg, label])
      ;(g as any)._widgetType = 'label'
      ;(g as any)._bindable = ['text', 'value']
      return g
    }
  },
  {
    type: 'value-display',
    name: '数值显示',
    category: '标注',
    icon: '🔢',
    defaultWidth: 100,
    defaultHeight: 50,
    createFabric: () => {
      const bg = rect({ width: 100, height: 50, fill: '#0a1a2a', stroke: '#3a8fd4', strokeWidth: 1, rx: 6, ry: 6 })
      const nameText = textbox('温度', { left: 50, top: 14, fontSize: 11, fill: '#6a8ab0' })
      const valText = textbox('0.0', { left: 50, top: 34, fontSize: 20, fill: '#4ac080', fontWeight: 'bold' })
      ;(valText as any)._bindTarget = 'value'
      ;(valText as any)._bindProp = 'text'
      const g = group([bg, nameText, valText])
      ;(g as any)._widgetType = 'value-display'
      ;(g as any)._bindable = ['value', 'unit', 'name']
      return g
    }
  },

  // ── 管道系统（蚂蚁线/流动动画） ──
  {
    type: 'pipe-flow-h',
    name: '水平流动管',
    category: '管道',
    icon: '➡️',
    defaultWidth: 200,
    defaultHeight: 24,
    createFabric: () => {
      const bg = rect({ width: 200, height: 24, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 1, rx: 4, ry: 4 })
      // 蚂蚁线（dash-offset 动画由运行时驱动）
      const dash = new fabric.Line([0, 12, 200, 12], {
        stroke: '#4ac080',
        strokeWidth: 3,
        strokeDashArray: [10, 6],
        selectable: false,
        evented: false
      })
      ;(dash as any)._bindTarget = 'flow'
      ;(dash as any)._bindProp = 'animate'
      const arrow = line([160, 12, 185, 12], { stroke: '#4ac080', strokeWidth: 2, selectable: false, evented: false })
      const arrowH1 = line([175, 7, 185, 12], { stroke: '#4ac080', strokeWidth: 2, selectable: false, evented: false })
      const arrowH2 = line([175, 17, 185, 12], { stroke: '#4ac080', strokeWidth: 2, selectable: false, evented: false })
      const g = group([bg, dash, arrow, arrowH1, arrowH2])
      ;(g as any)._widgetType = 'pipe-flow-h'
      ;(g as any)._bindable = ['flow', 'pressure']
      return g
    }
  },
  {
    type: 'pipe-flow-v',
    name: '垂直流动管',
    category: '管道',
    icon: '⬇️',
    defaultWidth: 24,
    defaultHeight: 200,
    createFabric: () => {
      const bg = rect({ width: 24, height: 200, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 1, rx: 4, ry: 4 })
      const dash = new fabric.Line([12, 0, 12, 200], {
        stroke: '#4ac080',
        strokeWidth: 3,
        strokeDashArray: [10, 6],
        selectable: false,
        evented: false
      })
      ;(dash as any)._bindTarget = 'flow'
      ;(dash as any)._bindProp = 'animate'
      const arrow = line([12, 160, 12, 185], { stroke: '#4ac080', strokeWidth: 2, selectable: false, evented: false })
      const arrowH1 = line([7, 175, 12, 185], { stroke: '#4ac080', strokeWidth: 2, selectable: false, evented: false })
      const arrowH2 = line([17, 175, 12, 185], { stroke: '#4ac080', strokeWidth: 2, selectable: false, evented: false })
      const g = group([bg, dash, arrow, arrowH1, arrowH2])
      ;(g as any)._widgetType = 'pipe-flow-v'
      ;(g as any)._bindable = ['flow', 'pressure']
      return g
    }
  },
  {
    type: 'pipe-elbow-rb',
    name: '弯管(右下)',
    category: '管道',
    icon: '↘️',
    defaultWidth: 60,
    defaultHeight: 60,
    createFabric: () => {
      const h = rect({ width: 30, height: 14, top: 0, left: 30, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 1 })
      const v = rect({ width: 14, height: 30, top: 30, left: 0, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 1 })
      const corner = rect({ width: 14, height: 14, top: 0, left: 0, fill: '#1a3a5a', stroke: 'transparent' })
      const dash = new fabric.Line([44, 7, 14, 7, 7, 14, 7, 53], {
        stroke: '#4ac080',
        strokeWidth: 2,
        strokeDashArray: [8, 5],
        selectable: false,
        evented: false
      })
      const g = group([h, v, corner, dash])
      ;(g as any)._widgetType = 'pipe-elbow-rb'
      return g
    }
  },
  {
    type: 'pipe-tee',
    name: '三通管',
    category: '管道',
    icon: '┬',
    defaultWidth: 100,
    defaultHeight: 100,
    createFabric: () => {
      const h = rect({ width: 100, height: 14, top: 43, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 1 })
      const v = rect({ width: 14, height: 50, top: 50, left: 43, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 1 })
      const dashH = new fabric.Line([0, 50, 100, 50], {
        stroke: '#4ac080',
        strokeWidth: 2,
        strokeDashArray: [8, 5],
        selectable: false,
        evented: false
      })
      const dashV = new fabric.Line([50, 50, 50, 100], {
        stroke: '#4ac080',
        strokeWidth: 2,
        strokeDashArray: [8, 5],
        selectable: false,
        evented: false
      })
      const g = group([h, v, dashH, dashV])
      ;(g as any)._widgetType = 'pipe-tee'
      return g
    }
  },
  {
    type: 'pipe-cross',
    name: '十字管',
    category: '管道',
    icon: '✚',
    defaultWidth: 100,
    defaultHeight: 100,
    createFabric: () => {
      const h = rect({ width: 100, height: 14, top: 43, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 1 })
      const v = rect({ width: 14, height: 100, top: 0, left: 43, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 1 })
      const dashH = new fabric.Line([0, 50, 100, 50], {
        stroke: '#4ac080',
        strokeWidth: 2,
        strokeDashArray: [8, 5],
        selectable: false,
        evented: false
      })
      const dashV = new fabric.Line([50, 0, 50, 100], {
        stroke: '#4ac080',
        strokeWidth: 2,
        strokeDashArray: [8, 5],
        selectable: false,
        evented: false
      })
      const g = group([h, v, dashH, dashV])
      ;(g as any)._widgetType = 'pipe-cross'
      return g
    }
  },

  // ── 基础图形 ──
  {
    type: 'basic-rect',
    name: '矩形',
    category: '基础',
    icon: '⬜',
    defaultWidth: 100,
    defaultHeight: 80,
    createFabric: () => {
      const r = rect({ width: 100, height: 80, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 2, rx: 4, ry: 4 })
      const g = group([r])
      ;(g as any)._widgetType = 'basic-rect'
      return g
    }
  },
  {
    type: 'basic-circle',
    name: '圆形',
    category: '基础',
    icon: '⭕',
    defaultWidth: 80,
    defaultHeight: 80,
    createFabric: () => {
      const c = circle({ left: 40, top: 40, radius: 35, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 2 })
      const g = group([c])
      ;(g as any)._widgetType = 'basic-circle'
      return g
    }
  },
  {
    type: 'basic-triangle',
    name: '三角形',
    category: '基础',
    icon: '🔺',
    defaultWidth: 100,
    defaultHeight: 86,
    createFabric: () => {
      const tri = new fabric.Polygon(
        [
          { x: 50, y: 0 },
          { x: 100, y: 86 },
          { x: 0, y: 86 }
        ],
        { fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 2 }
      )
      const g = group([tri])
      ;(g as any)._widgetType = 'basic-triangle'
      return g
    }
  },
  {
    type: 'basic-line-h',
    name: '水平线',
    category: '基础',
    icon: '➖',
    defaultWidth: 150,
    defaultHeight: 2,
    createFabric: () => {
      const l = line([0, 0, 150, 0], { stroke: '#3a8fd4', strokeWidth: 3, selectable: true, evented: true })
      const g = group([l])
      ;(g as any)._widgetType = 'basic-line-h'
      return g
    }
  },
  {
    type: 'basic-line-v',
    name: '垂直线',
    category: '基础',
    icon: '↕️',
    defaultWidth: 2,
    defaultHeight: 150,
    createFabric: () => {
      const l = line([0, 0, 0, 150], { stroke: '#3a8fd4', strokeWidth: 3, selectable: true, evented: true })
      const g = group([l])
      ;(g as any)._widgetType = 'basic-line-v'
      return g
    }
  },
  {
    type: 'basic-text',
    name: '文本',
    category: '基础',
    icon: '🔤',
    defaultWidth: 120,
    defaultHeight: 30,
    createFabric: () => {
      const t = new fabric.Textbox('文本', {
        width: 120,
        fontSize: 18,
        fill: '#e0e0e0',
        fontFamily: 'Arial',
        textAlign: 'left',
        selectable: false,
        evented: false
      })
      const g = group([t])
      ;(g as any)._widgetType = 'basic-text'
      ;(g as any)._bindable = ['text']
      return g
    }
  },

  // ── 动态符号（FUXA 风格） ──
  {
    type: 'fan',
    name: '风机',
    category: '动力',
    icon: '🌀',
    defaultWidth: 80,
    defaultHeight: 90,
    createFabric: () => {
      const body = circle({ left: 40, top: 40, radius: 35, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 2 })
      const blade1 = line([40, 10, 40, 35], { stroke: '#4ac080', strokeWidth: 3, selectable: false, evented: false })
      const blade2 = line([40, 45, 40, 70], { stroke: '#4ac080', strokeWidth: 3, selectable: false, evented: false })
      const blade3 = line([15, 40, 35, 40], { stroke: '#4ac080', strokeWidth: 3, selectable: false, evented: false })
      const blade4 = line([45, 40, 65, 40], { stroke: '#4ac080', strokeWidth: 3, selectable: false, evented: false })
      const center = circle({ left: 40, top: 40, radius: 5, fill: '#4ac080', stroke: 'transparent' })
      const label = textbox('风机', { left: 40, top: 85, fontSize: 11, fill: '#a0c0e0' })
      const g = group([body, blade1, blade2, blade3, blade4, center, label])
      ;(g as any)._widgetType = 'fan'
      ;(g as any)._bindable = ['state', 'speed']
      return g
    }
  },
  {
    type: 'compressor',
    name: '压缩机',
    category: '动力',
    icon: '💱',
    defaultWidth: 80,
    defaultHeight: 90,
    createFabric: () => {
      const shell = circle({ left: 40, top: 40, radius: 35, fill: '#3a1a1a', stroke: '#aa4040', strokeWidth: 2 })
      const tri = new fabric.Polygon(
        [
          { x: 25, y: 15 },
          { x: 55, y: 40 },
          { x: 25, y: 65 }
        ],
        { fill: '#f0a030', stroke: 'transparent' }
      )
      const inlet = line([0, 40, 5, 40], { stroke: '#3a8fd4', strokeWidth: 6, selectable: false, evented: false })
      const outlet = line([75, 40, 80, 40], { stroke: '#3a8fd4', strokeWidth: 6, selectable: false, evented: false })
      const label = textbox('压缩机', { left: 40, top: 85, fontSize: 11, fill: '#aa4040' })
      const g = group([shell, tri, inlet, outlet, label])
      ;(g as any)._widgetType = 'compressor'
      ;(g as any)._bindable = ['state', 'speed', 'pressure']
      return g
    }
  },
  {
    type: 'heat-exchanger',
    name: '换热器',
    category: '容器',
    icon: '🔄',
    defaultWidth: 120,
    defaultHeight: 80,
    createFabric: () => {
      const body = rect({ width: 120, height: 80, fill: '#1a3a5a', stroke: '#3a8fd4', strokeWidth: 2, rx: 6, ry: 6 })
      const tube1 = line([15, 20, 105, 20], { stroke: '#4ac080', strokeWidth: 2, selectable: false, evented: false })
      const tube2 = line([15, 40, 105, 40], { stroke: '#4ac080', strokeWidth: 2, selectable: false, evented: false })
      const tube3 = line([15, 60, 105, 60], { stroke: '#4ac080', strokeWidth: 2, selectable: false, evented: false })
      const label = textbox('换热器', { left: 60, top: 40, fontSize: 12, fill: '#ffffff' })
      const g = group([body, tube1, tube2, tube3, label])
      ;(g as any)._widgetType = 'heat-exchanger'
      ;(g as any)._bindable = ['temperature', 'pressure']
      return g
    }
  },
  {
    type: 'semaphore',
    name: '信号灯',
    category: '指示',
    icon: '🚦',
    defaultWidth: 40,
    defaultHeight: 120,
    createFabric: () => {
      const body = rect({ width: 40, height: 120, fill: '#2a2a2a', stroke: '#4a4a4a', strokeWidth: 2, rx: 8, ry: 8 })
      const red = circle({ left: 20, top: 25, radius: 12, fill: '#ff0000', stroke: '#6a0000', strokeWidth: 1 })
      ;(red as any)._bindTarget = 'red'
      ;(red as any)._bindProp = 'fill'
      const yellow = circle({ left: 20, top: 60, radius: 12, fill: '#3a3a00', stroke: '#6a6a00', strokeWidth: 1 })
      ;(yellow as any)._bindTarget = 'yellow'
      ;(yellow as any)._bindProp = 'fill'
      const green = circle({ left: 20, top: 95, radius: 12, fill: '#003a00', stroke: '#006a00', strokeWidth: 1 })
      ;(green as any)._bindTarget = 'green'
      ;(green as any)._bindProp = 'fill'
      const g = group([body, red, yellow, green])
      ;(g as any)._widgetType = 'semaphore'
      ;(g as any)._bindable = ['state', 'red', 'yellow', 'green']
      return g
    }
  },
  {
    type: 'slider-control',
    name: '滑块控件',
    category: '控件',
    icon: '🎚️',
    defaultWidth: 160,
    defaultHeight: 40,
    createFabric: () => {
      const track = rect({ width: 160, height: 10, top: 15, fill: '#2a2a2a', stroke: '#4a6a8a', strokeWidth: 1, rx: 5, ry: 5 })
      const fill = rect({ width: 80, height: 10, top: 15, fill: '#3a8fd4', stroke: 'transparent', rx: 5, ry: 5 })
      ;(fill as any)._bindTarget = 'value'
      ;(fill as any)._bindProp = 'width'
      const handle = circle({ left: 80, top: 20, radius: 8, fill: '#5ab0ff', stroke: '#ffffff', strokeWidth: 2 })
      ;(handle as any)._bindTarget = 'value'
      ;(handle as any)._bindProp = 'left'
      const label = textbox('50%', { left: 80, top: 38, fontSize: 11, fill: '#a0a0a0' })
      ;(label as any)._bindTarget = 'value'
      ;(label as any)._bindProp = 'text'
      const g = group([track, fill, handle, label])
      ;(g as any)._widgetType = 'slider-control'
      ;(g as any)._bindable = ['value', 'min', 'max']
      return g
    }
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
