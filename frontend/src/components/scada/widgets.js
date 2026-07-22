/**
 * SCADA Industrial Widget Library
 * Each widget is a Fabric.js compatible object definition.
 * tagBinding: { deviceId, tagId, tagField } links to live data.
 */

export const WIDGET_CATEGORIES = [
  { key: 'basic', label: '基础', icon: '📝' },
  { key: 'tank', label: '容器', icon: '🪣' },
  { key: 'valve', label: '阀门', icon: '🔧' },
  { key: 'motor', label: '电机/泵', icon: '⚙️' },
  { key: 'pipe', label: '管道', icon: '📏' },
  { key: 'gauge', label: '仪表', icon: '🎛️' },
  { key: 'indicator', label: '指示', icon: '💡' },
  { key: 'button', label: '控件', icon: '🔘' },
]

// Helper: create Fabric Textbox
function textbox(label, opts = {}) {
  return {
    type: 'textbox',
    text: label,
    fontSize: 14,
    fill: '#eee',
    fontFamily: 'monospace',
    width: 120,
    ...opts,
  }
}

// Helper: create Fabric Rect
function rect(opts = {}) {
  return {
    type: 'rect',
    fill: '#2a4a6b',
    stroke: '#5b8abf',
    strokeWidth: 2,
    width: 100,
    height: 100,
    rx: 4, ry: 4,
    ...opts,
  }
}

// Helper: create Fabric Circle
function circle(opts = {}) {
  return {
    type: 'circle',
    fill: '#2a4a6b',
    stroke: '#5b8abf',
    strokeWidth: 2,
    radius: 40,
    ...opts,
  }
}

// Helper: create SVG path
function svgPath(path, opts = {}) {
  return {
    type: 'path',
    path: path,
    fill: 'transparent',
    stroke: '#5b8abf',
    strokeWidth: 3,
    ...opts,
  }
}

export const WIDGETS = [
  // ── Basic ──
  {
    name: '文本',
    category: 'basic',
    icon: '📝',
    create: () => textbox('文本标签', { fontSize: 16, width: 150 }),
    bindable: ['text'],
  },
  {
    name: '数值显示',
    category: 'basic',
    icon: '🔢',
    create: () => ({
      ...textbox('0.00', {
        fontSize: 28,
        fontWeight: 'bold',
        fill: '#52c41a',
        textAlign: 'center',
        width: 140,
        backgroundColor: 'rgba(0,0,0,0.3)',
        padding: 10,
      }),
      scadaType: 'value_display',
      bindable: ['text', 'fill'],
    }),
    bindable: ['text', 'fill'],
  },
  {
    name: '矩形',
    category: 'basic',
    icon: '⬜',
    create: () => rect({ width: 150, height: 80 }),
    bindable: [],
  },
  {
    name: '标签牌',
    category: 'basic',
    icon: '🏷️',
    create: () => ({
      ...rect({ width: 200, height: 40, fill: '#333', stroke: '#666' }),
      scadaType: 'label_plate',
    }),
    bindable: [],
  },

  // ── Tank ──
  {
    name: '储罐',
    category: 'tank',
    icon: '🪣',
    create: () => ({
      type: 'group',
      scadaType: 'tank',
      objects: [
        { type: 'rect', left: 0, top: 0, width: 100, height: 140, fill: '#1a3a5c', stroke: '#5b8abf', strokeWidth: 2, rx: 6, ry: 6 },
        { type: 'rect', left: 4, top: 4, width: 92, height: 132, fill: '#0d2137', rx: 4, ry: 4, scadaPart: 'liquid',
          scaleY: 0.6, originY: 1, top: 136 },
      ],
      bindable: ['liquidLevel'],
    }),
    bindable: ['liquidLevel'],
  },
  {
    name: '立式罐',
    category: 'tank',
    icon: '🛢️',
    create: () => ({
      type: 'group',
      scadaType: 'tank_v',
      objects: [
        { type: 'ellipse', left: 0, top: 0, rx: 50, ry: 15, fill: '#1a3a5c', stroke: '#5b8abf', strokeWidth: 2 },
        { type: 'rect', left: 0, top: 15, width: 100, height: 120, fill: '#1a3a5c', stroke: '#5b8abf', strokeWidth: 2 },
        { type: 'ellipse', left: 0, top: 120, rx: 50, ry: 15, fill: '#1a3a5c', stroke: '#5b8abf', strokeWidth: 2 },
        { type: 'rect', left: 5, top: 18, width: 90, height: 100, fill: '#0a4a8a', scadaPart: 'liquid',
          scaleY: 0.5, originY: 1, top: 118 },
      ],
      bindable: ['liquidLevel'],
    }),
    bindable: ['liquidLevel'],
  },

  // ── Valve ──
  {
    name: '球阀',
    category: 'valve',
    icon: '🔵',
    create: () => ({
      type: 'group',
      scadaType: 'valve_ball',
      objects: [
        { type: 'circle', left: 0, top: 0, radius: 25, fill: '#2a4a6b', stroke: '#5b8abf', strokeWidth: 2, scadaPart: 'body' },
        { type: 'rect', left: 20, top: -20, width: 10, height: 20, fill: '#5b8abf' },
        { type: 'line', points: [25, -20, 25, 5], stroke: '#5b8abf', strokeWidth: 3 },
      ],
      bindable: ['state'],
    }),
    bindable: ['state'],
  },
  {
    name: '蝶阀',
    category: 'valve',
    icon: '🟡',
    create: () => ({
      type: 'group',
      scadaType: 'valve_butterfly',
      objects: [
        { type: 'rect', left: 0, top: 0, width: 50, height: 50, fill: '#2a4a6b', stroke: '#5b8abf', strokeWidth: 2, rx: 4, scadaPart: 'body' },
        { type: 'circle', left: 10, top: 10, radius: 15, fill: 'transparent', stroke: '#5b8abf', strokeWidth: 2 },
        { type: 'line', points: [25, 10, 25, -15], stroke: '#5b8abf', strokeWidth: 3 },
      ],
      bindable: ['state'],
    }),
    bindable: ['state'],
  },

  // ── Motor / Pump ──
  {
    name: '电机',
    category: 'motor',
    icon: '⚙️',
    create: () => ({
      type: 'group',
      scadaType: 'motor',
      objects: [
        { type: 'circle', left: 0, top: 0, radius: 30, fill: '#2a4a6b', stroke: '#5b8abf', strokeWidth: 2, scadaPart: 'body' },
        { type: 'text', text: 'M', fontSize: 24, fill: '#eee', fontFamily: 'monospace', fontWeight: 'bold',
          left: 22, top: 18, originX: 'center', originY: 'center' },
      ],
      bindable: ['state', 'speed'],
    }),
    bindable: ['state', 'speed'],
  },
  {
    name: '离心泵',
    category: 'motor',
    icon: '🔄',
    create: () => ({
      type: 'group',
      scadaType: 'pump',
      objects: [
        { type: 'circle', left: 0, top: 0, radius: 28, fill: '#2a4a6b', stroke: '#5b8abf', strokeWidth: 2, scadaPart: 'body' },
        { type: 'path', path: 'M 28 28 L 56 14 L 56 42 Z', fill: '#5b8abf', stroke: '#5b8abf' },
      ],
      bindable: ['state'],
    }),
    bindable: ['state'],
  },

  // ── Pipe ──
  {
    name: '水平管道',
    category: 'pipe',
    icon: '➖',
    create: () => ({
      type: 'group',
      scadaType: 'pipe_h',
      objects: [
        { type: 'rect', left: 0, top: 0, width: 150, height: 16, fill: '#3a5a7c', stroke: '#5b8abf', strokeWidth: 1 },
        { type: 'rect', left: 0, top: 3, width: 150, height: 10, fill: '#2a4a6b' },
      ],
      bindable: ['flow'],
    }),
    bindable: ['flow'],
  },
  {
    name: '垂直管道',
    category: 'pipe',
    icon: '│',
    create: () => ({
      type: 'group',
      scadaType: 'pipe_v',
      objects: [
        { type: 'rect', left: 0, top: 0, width: 16, height: 150, fill: '#3a5a7c', stroke: '#5b8abf', strokeWidth: 1 },
        { type: 'rect', left: 3, top: 0, width: 10, height: 150, fill: '#2a4a6b' },
      ],
      bindable: ['flow'],
    }),
    bindable: ['flow'],
  },
  {
    name: '弯头',
    category: 'pipe',
    icon: '↩️',
    create: () => ({
      type: 'path',
      scadaType: 'pipe_elbow',
      path: 'M 0 50 Q 0 0 50 0',
      fill: 'transparent',
      stroke: '#5b8abf',
      strokeWidth: 16,
      strokeLineCap: 'round',
      bindable: ['flow'],
    }),
    bindable: ['flow'],
  },

  // ── Gauge ──
  {
    name: '表盘',
    category: 'gauge',
    icon: '🎛️',
    create: () => ({
      type: 'group',
      scadaType: 'gauge',
      objects: [
        { type: 'circle', left: 0, top: 0, radius: 50, fill: '#111', stroke: '#5b8abf', strokeWidth: 3 },
        { type: 'text', text: '0', fontSize: 22, fill: '#52c41a', fontFamily: 'monospace', fontWeight: 'bold',
          left: 45, top: 60, textAlign: 'center', originX: 'center' },
        { type: 'text', text: '', fontSize: 10, fill: '#888',
          left: 45, top: 80, textAlign: 'center', originX: 'center', scadaPart: 'unit' },
      ],
      bindable: ['value'],
    }),
    bindable: ['value'],
  },
  {
    name: '温度计',
    category: 'gauge',
    icon: '🌡️',
    create: () => ({
      type: 'group',
      scadaType: 'thermometer',
      objects: [
        { type: 'rect', left: 15, top: 0, width: 20, height: 100, rx: 10, fill: '#111', stroke: '#5b8abf', strokeWidth: 2 },
        { type: 'circle', left: 10, top: 80, radius: 15, fill: '#f5222d', stroke: '#5b8abf', strokeWidth: 2, scadaPart: 'bulb' },
        { type: 'rect', left: 20, top: 20, width: 10, height: 60, fill: '#f5222d', scadaPart: 'mercury',
          scaleY: 0.5, originY: 1, top: 80 },
      ],
      bindable: ['value'],
    }),
    bindable: ['value'],
  },
  {
    name: '进度条',
    category: 'gauge',
    icon: '📊',
    create: () => ({
      type: 'group',
      scadaType: 'progress',
      objects: [
        { type: 'rect', left: 0, top: 0, width: 200, height: 24, rx: 12, fill: '#111', stroke: '#333', strokeWidth: 1 },
        { type: 'rect', left: 2, top: 2, width: 196, height: 20, rx: 10, fill: '#1890ff', scadaPart: 'bar',
          scaleX: 0.5, originX: 0 },
        { type: 'text', text: '50%', fontSize: 12, fill: '#fff', fontFamily: 'monospace',
          left: 100, top: 12, originX: 'center', originY: 'center', scadaPart: 'label' },
      ],
      bindable: ['value'],
    }),
    bindable: ['value'],
  },

  // ── Indicator ──
  {
    name: '指示灯',
    category: 'indicator',
    icon: '💡',
    create: () => ({
      type: 'group',
      scadaType: 'lamp',
      objects: [
        { type: 'circle', left: 0, top: 0, radius: 18, fill: '#333', stroke: '#555', strokeWidth: 2, scadaPart: 'light' },
      ],
      bindable: ['state'],
    }),
    bindable: ['state'],
  },
  {
    name: '报警灯',
    category: 'indicator',
    icon: '🚨',
    create: () => ({
      type: 'group',
      scadaType: 'alarm_lamp',
      objects: [
        { type: 'circle', left: 0, top: 0, radius: 22, fill: '#333', stroke: '#f5222d', strokeWidth: 3, scadaPart: 'light' },
        { type: 'text', text: '!', fontSize: 20, fill: '#fff', fontWeight: 'bold',
          left: 18, top: 18, originX: 'center', originY: 'center' },
      ],
      bindable: ['state'],
    }),
    bindable: ['state'],
  },
  {
    name: '数字框',
    category: 'indicator',
    icon: '📋',
    create: () => ({
      type: 'group',
      scadaType: 'number_box',
      objects: [
        { type: 'rect', left: 0, top: 0, width: 100, height: 36, rx: 4, fill: '#0a1a2e', stroke: '#3a5a7c', strokeWidth: 1 },
        { type: 'text', text: '0.00', fontSize: 18, fill: '#52c41a', fontFamily: 'monospace', fontWeight: 'bold',
          left: 50, top: 18, originX: 'center', originY: 'center', scadaPart: 'value' },
      ],
      bindable: ['value'],
    }),
    bindable: ['value'],
  },

  // ── Button ──
  {
    name: '按钮',
    category: 'button',
    icon: '🔘',
    create: () => ({
      type: 'group',
      scadaType: 'button',
      objects: [
        { type: 'rect', left: 0, top: 0, width: 100, height: 40, rx: 6, fill: '#1890ff', stroke: '#40a9ff', strokeWidth: 1 },
        { type: 'text', text: '启动', fontSize: 14, fill: '#fff', fontWeight: 'bold',
          left: 50, top: 20, originX: 'center', originY: 'center' },
      ],
      bindable: ['action'],
    }),
    bindable: ['action'],
  },
  {
    name: '开关',
    category: 'button',
    icon: '🔀',
    create: () => ({
      type: 'group',
      scadaType: 'switch',
      objects: [
        { type: 'rect', left: 0, top: 0, width: 60, height: 30, rx: 15, fill: '#333', stroke: '#555', strokeWidth: 1, scadaPart: 'track' },
        { type: 'circle', left: 2, top: 2, radius: 13, fill: '#aaa', scadaPart: 'thumb' },
      ],
      bindable: ['state'],
    }),
    bindable: ['state'],
  },
]

// Widget runtime behaviors
export const WIDGET_STATES = {
  // Motor/Pump states
  motor_running: { body: { fill: '#13c2c2' } },
  motor_stopped: { body: { fill: '#2a4a6b' } },
  motor_error: { body: { fill: '#f5222d' } },

  // Valve states
  valve_open: { body: { fill: '#52c41a' } },
  valve_closed: { body: { fill: '#888' } },

  // Lamp states
  lamp_on: { light: { fill: '#52c41a' } },
  lamp_off: { light: { fill: '#333' } },
  lamp_alarm: { light: { fill: '#f5222d' } },

  // Alarm lamp
  alarm_active: { light: { fill: '#f5222d' } },
  alarm_normal: { light: { fill: '#333' } },
}

export default WIDGETS
