import { ref, watch } from 'vue'
import { getDeviceTags, unwrap, unwrapList } from '@/api/modbus'

/**
 * 设备 → 点位联动加载组合逻辑。
 *
 * 封装「选设备 → getDeviceTags → unwrap/Array.isArray 分支 → 填点位」的重复样板，
 * 被 Control / AlarmRules / History / BatchControl / LabCompare 等多个页面使用。
 *
 * @example
 * const { tags, tagsLoading, loadTags } = useDeviceTags()
 * watch(deviceId, (id) => loadTags(id))
 */
export function useDeviceTags() {
  const tags = ref<any[]>([])
  const tagsLoading = ref(false)

  /**
   * 加载指定设备的点位列表。deviceId 为空时清空并返回。
   * 返回 true 表示加载成功且有数据源；false 表示设备为空。
   */
  const loadTags = async (deviceId: number | null | undefined) => {
    tags.value = []
    if (deviceId == null) return false
    tagsLoading.value = true
    try {
      const res = await getDeviceTags(deviceId)
      const body = unwrap(res)
      tags.value = Array.isArray(body) ? body : unwrapList(res).list
      return true
    } finally {
      tagsLoading.value = false
    }
  }

  /** 便捷：监听设备 id 变化自动加载点位 */
  const watchDevice = (deviceId: () => number | null | undefined) => {
    watch(deviceId, (id) => loadTags(id))
  }

  return { tags, tagsLoading, loadTags, watchDevice }
}
