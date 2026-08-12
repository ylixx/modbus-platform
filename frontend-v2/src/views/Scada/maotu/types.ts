/**
 * maotu 引擎页面 JSON 类型（存储于 scada_pages.config_json）
 * 结构 = maotu IExportJson + 顶层 __engine 标记，旧版渲染器忽略多余字段
 */

export interface MtCanvasCfg {
  width: number
  height: number
  scale: number
  color: string
  img: string
  guide: boolean
  adsorp: boolean
  adsorp_diff: number
  transform_origin: { x: number; y: number }
  drag_offset: { x: number; y: number }
}

export interface MtGridCfg {
  enabled: boolean
  align: boolean
  size: number
}

export interface MtItemBInfo {
  left: number
  top: number
  width: number
  height: number
  angle: number
}

export interface MtItemEvent {
  id: string
  type: 'click' | 'dblclick' | 'mouseover' | 'mouseout'
  action?: 'changeAttr' | 'customCode'
  change_attr?: { id: string; target_id: string; target_attr?: string; target_value: any }[]
  custom_code?: string
  trigger_rule?: { trigger_id?: string; trigger_attr?: string; operator?: string; value?: any }
}

/** 平台扩展：点位绑定（存 item 顶层字段，maotu 序列化时保留） */
export interface MtDeviceBind {
  signalId?: string
  attr?: string
}

export interface MtItem {
  id: string
  title?: string
  type: string
  tag?: string
  binfo: MtItemBInfo
  props: Record<string, any>
  resize?: boolean
  rotate?: boolean
  lock?: boolean
  hide?: boolean
  active?: boolean
  events?: MtItemEvent[]
  children?: MtItem[]
  device_bind?: MtDeviceBind
  [key: string]: any
}

export interface MtExportJson {
  canvasCfg: MtCanvasCfg
  gridCfg: MtGridCfg
  json: MtItem[]
}

export type MtPageConfig = MtExportJson & { __engine?: 'maotu' }

export const MT_ENGINE = 'maotu'

export const isMtPageConfig = (v: any): v is MtPageConfig => {
  return !!v && typeof v === 'object' && v.__engine === MT_ENGINE && Array.isArray(v.json)
}

export const defaultMtPageConfig = (width = 1920, height = 1080, background = '#10141d'): MtPageConfig => ({
  __engine: MT_ENGINE,
  canvasCfg: {
    width,
    height,
    scale: 1,
    color: background,
    img: '',
    guide: true,
    adsorp: true,
    adsorp_diff: 3,
    transform_origin: { x: 0, y: 0 },
    drag_offset: { x: 0, y: 0 }
  },
  gridCfg: { enabled: true, align: true, size: 10 },
  json: []
})