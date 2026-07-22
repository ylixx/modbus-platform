/**
 * useTable composable — inspired by yudao's useTable pattern.
 *
 * Encapsulates: loading, pagination, data fetching, search params,
 * delete confirmation, export, and refresh.
 *
 * Usage:
 *   const { tableData, loading, total, page, pageSize, fetchList, handleDelete, handleExport } = useTable({
 *     listApi: (params) => api.get('/devices', { params }),
 *     deleteApi: (id) => api.delete(`/devices/${id}`),
 *     exportApi: (params) => api.get('/export/devices/csv', { params, responseType: 'blob' }),
 *     defaultPageSize: 20,
 *   })
 */
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { downloadBlob, timestampFilename } from '../utils'

export function useTable(options = {}) {
  const {
    listApi,
    deleteApi,
    exportApi,
    defaultPageSize = 20,
    defaultParams = {},
    immediate = true,
    onSuccess,
    onDeleteSuccess,
    exportFilename,
  } = options

  const tableData = ref([])
  const loading = ref(false)
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(defaultPageSize)

  // Search/filter params (reactive, caller can bind to form)
  const searchParams = reactive({ ...defaultParams })

  /**
   * Fetch list data
   */
  async function fetchList() {
    if (!listApi) return
    loading.value = true
    try {
      const params = {
        page: page.value,
        page_size: pageSize.value,
        ...cleanParams(searchParams),
      }
      const res = await listApi(params)
      // Support both { data: [...] } and { data: { data: [...], total: N } } formats
      if (Array.isArray(res.data)) {
        tableData.value = res.data
        total.value = res.data.length
      } else {
        tableData.value = res.data.data || res.data.list || []
        total.value = res.data.total || 0
      }
      onSuccess?.(tableData.value)
    } catch (e) {
      console.error('fetchList error:', e)
    } finally {
      loading.value = false
    }
  }

  /**
   * Delete with confirmation
   */
  async function handleDelete(row, nameKey = 'name') {
    const name = row[nameKey] || row.id
    await ElMessageBox.confirm(`确定删除 "${name}"？`, '确认删除', { type: 'warning' })
    if (deleteApi) {
      await deleteApi(row.id)
      ElMessage.success('删除成功')
      onDeleteSuccess?.(row)
      fetchList()
    }
  }

  /**
   * Export data
   */
  async function handleExport(filename) {
    if (exportApi) {
      const params = { ...cleanParams(searchParams) }
      const res = await exportApi(params)
      downloadBlob(res.data, filename || exportFilename || timestampFilename('export'))
      ElMessage.success('导出成功')
    }
  }

  /**
   * Page change handler
   */
  function handlePageChange(val) {
    page.value = val
    fetchList()
  }

  function handleSizeChange(val) {
    pageSize.value = val
    page.value = 1
    fetchList()
  }

  /**
   * Reset search and re-fetch
   */
  function handleReset() {
    Object.keys(searchParams).forEach(key => {
      searchParams[key] = defaultParams[key] ?? null
    })
    page.value = 1
    fetchList()
  }

  /**
   * Search (reset to page 1)
   */
  function handleSearch() {
    page.value = 1
    fetchList()
  }

  // Remove null/undefined/empty values
  function cleanParams(params) {
    const cleaned = {}
    for (const [k, v] of Object.entries(params)) {
      if (v !== null && v !== undefined && v !== '') {
        cleaned[k] = v
      }
    }
    return cleaned
  }

  if (immediate) {
    onMounted(fetchList)
  }

  return {
    tableData,
    loading,
    total,
    page,
    pageSize,
    searchParams,
    fetchList,
    handleDelete,
    handleExport,
    handlePageChange,
    handleSizeChange,
    handleReset,
    handleSearch,
  }
}
