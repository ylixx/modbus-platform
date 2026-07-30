/**
 * Modbus 平台公共工具函数
 */
import { ref } from 'vue'
import { getDevices, unwrapList } from '@/api/modbus'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.extend(utc)
dayjs.extend(timezone)

/** Format UTC ISO string to local time. Default format: YYYY-MM-DD HH:mm:ss */
export const formatTime = (val?: string | null, fmt = 'YYYY-MM-DD HH:mm:ss') => {
  if (!val) return '—'
  return dayjs(val).format(fmt)
}

/** 下载 Blob 响应为文件 */
export const saveBlob = (res: any, fallbackName: string) => {
  const blob = res?.data instanceof Blob ? res.data : new Blob([res?.data ?? res])
  const cd: string = res?.headers?.['content-disposition'] || ''
  const m = cd.match(/filename="?([^";]+)"?/)
  const name = m ? decodeURIComponent(m[1]) : fallbackName
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

/** 设备状态 → Tag 类型 */
export const deviceStatusType = (s?: string) => {
  if (s === 'online') return 'success'
  if (s === 'error') return 'danger'
  if (s === 'no-data') return 'warning'
  return 'info'
}

/** 设备状态 → 中文文本 */
export const deviceStatusText = (s?: string) => {
  if (s === 'online') return '在线'
  if (s === 'error') return '异常'
  if (s === 'no-data') return '在线无数据'
  return '离线'
}

/** 并发限制执行器：最多同时 CONCURRENCY 个请求 */
export async function concurrentRun<T>(
  items: T[],
  fn: (item: T) => Promise<any>,
  concurrency = 5
): Promise<void> {
  const executing: Promise<any>[] = []
  for (const item of items) {
    const p = fn(item).then(() => { executing.splice(executing.indexOf(p), 1) })
    executing.push(p)
    if (executing.length >= concurrency) await Promise.race(executing)
  }
  await Promise.all(executing)
}

/**
 * 公共设备选项组合逻辑
 * 复用 fetchDevices + unwrapList 模式，被 8+ 个页面重复使用
 *
 * @example
 * const { devices, fetchDevices, onDeviceChange } = useDeviceOptions()
 * onMounted(fetchDevices)
 */
export function useDeviceOptions() {
  const devices = ref<any[]>([])
  const fetchDevices = async () => {
    devices.value = unwrapList(await getDevices()).list
  }
  const onDeviceChange = (deviceId: number, tags: any[], setTags: (t: any[]) => void) => {
    const d = devices.value.find((d: any) => d.id === deviceId)
    if (d) setTags([])
  }
  return { devices, fetchDevices, onDeviceChange }
}
