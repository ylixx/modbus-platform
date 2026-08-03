/**
 * Fabric.js JSON → SVG 转换器
 *
 * 将旧版 Fabric.js 序列化的 config_json 转换为 SVG 字符串，
 * 使旧的 SCADA 画面数据能在新版 SVG 画布上渲染。
 *
 * 支持转换的 Fabric 对象类型：
 * - Group → <g> 包含子元素
 * - Rect → <rect>
 * - Circle/Ellipse → <circle>/<ellipse>
 * - Line → <line>
 * - Textbox/Text/IText → <text>
 * - Path → <path>
 * - ActiveSelection → <g>（忽略选择框本身，转换子对象）
 */

interface FabricObject {
  type: string
  left?: number
  top?: number
  width?: number
  height?: number
  scaleX?: number
  scaleY?: number
  angle?: number
  opacity?: number
  fill?: string | null
  stroke?: string | null
  strokeWidth?: number
  strokeDashArray?: number[] | null
  rx?: number
  ry?: number
  radius?: number
  visible?: boolean
  flipX?: boolean
  flipY?: boolean
  originX?: string
  originY?: string
  objects?: FabricObject[]
  text?: string
  fontSize?: number
  fontFamily?: string
  fontWeight?: string
  fontStyle?: string
  textAlign?: string
  x1?: number
  y1?: number
  x2?: number
  y2?: number
  path?: string | any[]
  sourcePath?: string
  backgroundColor?: string
}

/** 生成唯一 ID */
let _idCounter = 0
function genUid(): string {
  return `mig-${++_idCounter}`
}

/** 处理颜色值（Fabric 可能返回 'rgb(r,g,b)' 或 '#hex' 或 null） */
function normalizeColor(c: string | null | undefined): string | null {
  if (!c || c === 'transparent' || c === 'null') return null
  // Fabric 的 'rgb(0,0,0)' 格式保持原样，SVG 支持此格式
  return c
}

/** 转换 strokeDashArray → SVG stroke-dasharray */
function dashArray(arr: number[] | null | undefined): string {
  if (!arr || arr.length === 0) return ''
  return arr.join(',')
}

/** 计算变换（位移+旋转+缩放） */
function buildTransform(obj: FabricObject, cx: number = 0, cy: number = 0): string {
  const parts: string[] = []
  const sx = obj.scaleX ?? 1
  const sy = obj.scaleY ?? 1
  const angle = obj.angle ?? 0

  // 位移
  const left = obj.left ?? 0
  const top = obj.top ?? 0
  parts.push(`translate(${left},${top})`)

  // 旋转（如果有）
  if (angle !== 0) {
    parts.push(`rotate(${angle},${cx},${cy})`)
  }

  // 缩放（如果不是 1:1）
  if (sx !== 1 || sy !== 1) {
    parts.push(`scale(${sx},${sy})`)
  }

  // 翻转
  if (obj.flipX || obj.flipY) {
    const fx = obj.flipX ? -1 : 1
    const fy = obj.flipY ? -1 : 1
    parts.push(`scale(${fx},${fy})`)
  }

  return parts.join(' ')
}

/** 转换单个 Fabric 对象为 SVG 元素字符串 */
function fabricObjToSvg(obj: FabricObject, indent: string = '  '): string {
  if (obj.visible === false) return ''

  const id = genUid()
  const opacityAttr =
    obj.opacity !== undefined && obj.opacity !== 1 ? ` opacity="${obj.opacity}"` : ''
  const stroke = normalizeColor(obj.stroke)
  const strokeAttr = stroke ? ` stroke="${stroke}"` : ' stroke="none"'
  const sw = obj.strokeWidth ?? (stroke ? 1 : 0)
  const swAttr = sw > 0 ? ` stroke-width="${sw}"` : ''
  const fill = normalizeColor(obj.fill)
  const fillAttr = fill ? ` fill="${fill}"` : ' fill="none"'
  const dash = dashArray(obj.strokeDashArray)
  const dashAttr = dash ? ` stroke-dasharray="${dash}"` : ''

  switch (obj.type) {
    case 'Rect': {
      const rx = obj.rx ? ` rx="${obj.rx}"` : ''
      const ry = obj.ry ? ` ry="${obj.ry}"` : ''
      const w = obj.width ?? 0
      const h = obj.height ?? 0
      // Fabric Rect 的 originX/originY 影响定位，默认 left/top 是左上角
      const ox = obj.originX === 'center' ? -w / 2 : 0
      const oy = obj.originY === 'center' ? -h / 2 : 0
      const transform = buildTransform(obj, w / 2 - ox, h / 2 - oy)
      return `${indent}<rect id="${id}" x="${ox}" y="${oy}" width="${w}" height="${h}"${rx}${ry}${fillAttr}${strokeAttr}${swAttr}${dashAttr}${opacityAttr} transform="${transform}"/>`
    }

    case 'Circle': {
      const r = obj.radius ?? 0
      const transform = buildTransform(obj, r, r)
      return `${indent}<circle id="${id}" cx="0" cy="0" r="${r}"${fillAttr}${strokeAttr}${swAttr}${dashAttr}${opacityAttr} transform="${transform}"/>`
    }

    case 'Ellipse': {
      const rx = obj.rx ?? 0
      const ry = obj.ry ?? 0
      const transform = buildTransform(obj, rx, ry)
      return `${indent}<ellipse id="${id}" cx="0" cy="0" rx="${rx}" ry="${ry}"${fillAttr}${strokeAttr}${swAttr}${dashAttr}${opacityAttr} transform="${transform}"/>`
    }

    case 'Line': {
      const x1 = obj.x1 ?? 0
      const y1 = obj.y1 ?? 0
      const x2 = obj.x2 ?? 0
      const y2 = obj.y2 ?? 0
      const transform = buildTransform(obj)
      return `${indent}<line id="${id}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"${strokeAttr}${swAttr}${dashAttr}${opacityAttr} transform="${transform}"/>`
    }

    case 'Textbox':
    case 'Text':
    case 'IText': {
      const text = obj.text ?? ''
      const fontSize = obj.fontSize ?? 16
      const fontFamily = obj.fontFamily ?? 'Arial'
      const fontWeight = obj.fontWeight ?? 'normal'
      const fontStyle = obj.fontStyle ?? 'normal'
      const textAlign = obj.textAlign ?? 'left'
      // Fabric Text 的坐标原点取决于 originX/originY
      const w = obj.width ?? 100
      const h = obj.height ?? fontSize
      let tx = 0
      let ty = fontSize * 0.35 // 基线偏移
      if (obj.originX === 'center') tx = -w / 2
      if (obj.originY === 'center') ty = ty - h / 2
      const anchor = textAlign === 'center' ? 'middle' : textAlign === 'right' ? 'end' : 'start'
      const transform = buildTransform(obj, w / 2, h / 2)
      return `${indent}<text id="${id}" x="${tx}" y="${ty}" font-size="${fontSize}" font-family="${fontFamily}" font-weight="${fontWeight}" font-style="${fontStyle}" text-anchor="${anchor}"${fillAttr}${opacityAttr} transform="${transform}">${escapeXml(text)}</text>`
    }

    case 'Path': {
      let d = ''
      if (typeof obj.path === 'string') {
        d = obj.path
      } else if (Array.isArray(obj.path)) {
        d = fabricPathToSvgD(obj.path)
      }
      const transform = buildTransform(obj)
      return `${indent}<path id="${id}" d="${d}"${fillAttr}${strokeAttr}${swAttr}${dashAttr}${opacityAttr} transform="${transform}"/>`
    }

    case 'Group':
    case 'ActiveSelection': {
      if (!obj.objects || obj.objects.length === 0) return ''
      const transform = buildTransform(obj)
      const children = obj.objects
        .map((child) => fabricObjToSvg(child, indent + '  '))
        .filter(Boolean)
        .join('\n')
      return `${indent}<g id="${id}" transform="${transform}">\n${children}\n${indent}</g>`
    }

    // 未知类型 — 跳过
    default:
      return ''
  }
}

/** Fabric path 数组 → SVG d 属性 */
function fabricPathToSvgD(segments: any[]): string {
  if (!Array.isArray(segments)) return ''
  return segments
    .map((seg) => {
      if (!Array.isArray(seg)) return ''
      const cmd = seg[0]
      switch (cmd) {
        case 'M':
          return `M${seg[1]},${seg[2]}`
        case 'L':
          return `L${seg[1]},${seg[2]}`
        case 'C':
          return `C${seg[1]},${seg[2]},${seg[3]},${seg[4]},${seg[5]},${seg[6]}`
        case 'Q':
          return `Q${seg[1]},${seg[2]},${seg[3]},${seg[4]}`
        case 'Z':
        case 'z':
          return 'Z'
        case 'H':
          return `H${seg[1]}`
        case 'V':
          return `V${seg[1]}`
        case 'm':
          return `m${seg[1]},${seg[2]}`
        case 'l':
          return `l${seg[1]},${seg[2]}`
        case 'h':
          return `h${seg[1]}`
        case 'v':
          return `v${seg[1]}`
        default:
          return seg.join(' ')
      }
    })
    .join(' ')
}

/** XML 特殊字符转义 */
function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * 主入口：将 Fabric.js 的 config_json 转换为 SVG 字符串
 *
 * @param configJson - 旧版 Fabric.js 的 config_json 对象（或其 objects 数组）
 * @param width - 画布宽度
 * @param height - 画布高度
 * @param background - 画布背景色
 * @returns SVG 字符串
 */
export function convertFabricToSvg(
  configJson: any,
  width: number = 1920,
  height: number = 1080,
  background: string = '#1a1a2e'
): string {
  _idCounter = 0

  // 提取 objects 数组
  let objects: FabricObject[] = []
  let bg = background

  if (configJson && Array.isArray(configJson.objects)) {
    objects = configJson.objects
    if (configJson.background) bg = configJson.background
  } else if (Array.isArray(configJson)) {
    objects = configJson
  } else {
    // 无法识别的格式，返回空画布
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">\n  <rect width="100%" height="100%" fill="${bg}"/>\n</svg>`
  }

  // 转换所有对象
  const svgContent = objects
    .map((obj) => fabricObjToSvg(obj, '  '))
    .filter(Boolean)
    .join('\n')

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <rect width="100%" height="100%" fill="${bg}"/>
${svgContent}
</svg>`
}

/**
 * 判断 config_json 是否为旧版 Fabric 格式
 */
export function isFabricJson(configJson: any): boolean {
  if (!configJson) return false
  if (configJson.type === 'svg' && configJson.svgContent) return false
  if (Array.isArray(configJson?.objects)) return true
  if (Array.isArray(configJson)) return true
  return false
}
