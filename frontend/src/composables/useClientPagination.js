/**
 * useClientPagination — client-side pagination over an in-memory array.
 *
 * Mirrors the pattern used in dashboard/Realtime.vue so every list page has a
 * consistent pagination experience (default 30 / page, sizes 10–100).
 *
 * The source must be a ref or computed ref holding the FULL dataset
 * (usually fetched once from a `.../all` or non-paginated endpoint).
 *
 * @param {import('vue').Ref|import('vue').ComputedRef} source  reactive array of rows
 * @param {{ defaultPageSize?: number }} [options]
 */
import { ref, computed } from 'vue'

export function useClientPagination(source, options = {}) {
  const pageSize = ref(options.defaultPageSize || 30)
  const currentPage = ref(1)

  const total = computed(() => source.value?.length || 0)

  const pagedRows = computed(() => {
    const arr = source.value || []
    const start = (currentPage.value - 1) * pageSize.value
    return arr.slice(start, start + pageSize.value)
  })

  function onSizeChange(sz) {
    pageSize.value = sz
    currentPage.value = 1
  }
  function onPageChange(p) {
    currentPage.value = p
  }
  function resetPage() {
    currentPage.value = 1
  }

  return { pageSize, currentPage, total, pagedRows, onSizeChange, onPageChange, resetPage }
}
