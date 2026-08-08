import { ref, onMounted } from 'vue'
import { unwrapList } from '@/api/modbus'

interface PaginationOptions {
  /**
   * 初始化时是否自动请求第一页，默认 true
   */
  immediate?: boolean
  /**
   * 默认每页条数，默认 20
   */
  pageSize?: number
}

/**
 * 列表页「加载 + 分页 + 搜索」通用组合逻辑。
 *
 * 封装各列表页重复的 loading / list / total / page / pageSize + fetch + 翻页 + unwrapList 样板。
 *
 * @example
 * const { list, total, loading, query, fetchList, onPageChange, onSizeChange, resetPage } =
 *   usePagination(async (q) => getDevices(q))
 * onMounted(fetchList)
 *
 * 或使用内置 fetch 绑定：
 * const page = usePagination(async (q) => getDevices(q), { pageSize: 50 })
 */
export function usePagination(
  fetcher: (query: { page: number; page_size: number }) => Promise<any>,
  options: PaginationOptions = {}
) {
  const { immediate = true, pageSize = 20 } = options

  const loading = ref(false)
  const list = ref<any[]>([])
  const total = ref(0)
  const page = ref(1)
  const page_size = ref(pageSize)

  /** 执行一次加载（含翻页、搜索、重置后调用） */
  const fetchList = async () => {
    loading.value = true
    try {
      const res = await fetcher({ page: page.value, page_size: page_size.value })
      const { list: l, total: t } = unwrapList(res)
      list.value = l
      total.value = t
    } catch {
      /* 由页面 fetcher 内部决定是否提示错误，此处仅确保 loading 复位 */
    } finally {
      loading.value = false
    }
  }

  /** 翻页 */
  const onPageChange = (p: number) => {
    page.value = p
    fetchList()
  }

  /** 每页条数变化：回到第一页再加载 */
  const onSizeChange = (s: number) => {
    page_size.value = s
    page.value = 1
    fetchList()
  }

  /** 重置到第一页（搜索/筛选变化后调用） */
  const resetPage = () => {
    page.value = 1
    fetchList()
  }

  onMounted(() => {
    if (immediate) fetchList()
  })

  return { list, total, loading, page, page_size, fetchList, onPageChange, onSizeChange, resetPage }
}
