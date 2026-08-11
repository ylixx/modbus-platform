<script setup lang="ts">
/**
 * 批量远程控制（可写点位操作面板）
 *
 * 参照「采集点位」页设计：以点位为表格行、组织级联+关键词筛选、
 * 行多选+工具栏批量操作。控制的是设备的点位，故不再让用户逐行选设备+点位。
 *
 * - 单独控制：表格行内「写入值」输入框 + 行尾「写入」按钮
 * - 批量控制：勾选多行 → 工具栏统一填写值 → 「执行所选/执行全部」
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElAlert,
  ElSwitch,
  ElEmpty,
  ElProgress,
  ElCard,
  ElPagination,
  ElTooltip,
  ElSelect,
  ElOption
} from 'element-plus'
import { getAllTags, getDeviceLive, writeDevice, batchWriteDevices, unwrap, unwrapList } from '@/api/modbus'
import OrgCascadeSelect from '@/components/OrgCascadeSelect.vue'
import type { WsLiveValue } from '@/utils/websocket'
import { wsManager } from '@/utils/websocket'

defineOptions({ name: 'BatchControl' })

// ── 组织级联范围 + 关键词 ──
const selectedIds = ref<number[]>([])
const orgPath = ref<{ org_node_id: number | null; labels: string[] } | null>(null)
const searchKeyword = ref('')

const scopeLabel = computed(() => {
  if (orgPath.value?.labels?.length) return orgPath.value.labels.join(' / ')
  return selectedIds.value.length ? `已选 ${selectedIds.value.length} 台设备` : '全部设备'
})

// ── 点位列表（分页） ──
const loading = ref(false)
const rows = ref<any[]>([]) // 点位行：扩展 value / status / resultMsg / readbackValue
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)

const fetchRows = async () => {
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      page_size: pageSize.value,
      writable: true,
      device_enabled: true
    }
    if (orgPath.value?.org_node_id) params.org_node_id = orgPath.value.org_node_id
    if (selectedIds.value.length) params.device_ids = selectedIds.value.join(',')
    if (searchKeyword.value.trim()) params.search = searchKeyword.value.trim()
    const res = await getAllTags(params)
    const { list: l, total: t } = unwrapList(res)
    rows.value = l
      .filter((tag: any) => tag.writable)
      .map((tag: any) => ({
      ...tag,
      value: '',
      status: 'pending',
      resultMsg: '',
      readbackValue: undefined,
      readbackTagId: tag.readback_tag_id,
      readbackTagName: tag.readback_tag_name || ''
    }))
    total.value = t
    // 拉完点位立刻刷新实时值
    refreshLive()
  } catch (e: any) {
    ElMessage.error(e?.message || '获取可写点位失败')
  } finally {
    loading.value = false
  }
}

const onPageChange = (p: number) => {
  page.value = p
  fetchRows()
}
const onSizeChange = (s: number) => {
  pageSize.value = s
  page.value = 1
  fetchRows()
}

// 级联 / 搜索变化 → 回到第一页刷新
watch(selectedIds, () => {
  page.value = 1
  fetchRows()
})
const onPathChange = (_path: { org_node_id: number | null; labels: string[] } | null) => {
  page.value = 1
  fetchRows()
}
const onKeywordSearch = () => {
  page.value = 1
  fetchRows()
}

// ── 实时值（当前值列） ──
const liveMap = ref<Record<number, Record<number, { value: any; quality: string; time: string }>>>({})

const refreshLive = async () => {
  const deviceIds = [...new Set(rows.value.map((r) => r.device_id))]
  await Promise.all(
    deviceIds.map(async (id) => {
      try {
        const body = unwrap(await getDeviceLive(id))
        const values =
          body && typeof body === 'object' && !Array.isArray(body) && body.values ? body.values : {}
        liveMap.value[id] = values
      } catch {
        if (!liveMap.value[id]) liveMap.value[id] = {}
      }
    })
  )
}

const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d) return
  if (!liveMap.value[d.device_id]) liveMap.value[d.device_id] = {}
  liveMap.value[d.device_id][d.tag_id] = {
    value: d.value,
    quality: d.quality,
    time: new Date().toISOString()
  }
}

// ── 行操作：单独控制 ──
const writingRow = ref<number | null>(null) // 正在写入的行 id

const writeRow = async (row: any) => {
  if (row.value === '' || row.value == null) {
    ElMessage.warning('请先填写写入值')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认向「${row.device_name}」的点位「${row.name}」写入值 ${row.value}${row.unit ? ' ' + row.unit : ''}？`,
      '写入确认',
      { type: 'warning', confirmButtonText: '确认写入' }
    )
  } catch {
    return
  }
  writingRow.value = row.id
  row.status = 'pending'
  row.resultMsg = ''
  row.readbackValue = undefined
  try {
    const res: any = await writeDevice(row.device_id, { tag_id: row.id, value: Number(row.value) })
    row.status = 'success'
    row.resultMsg = '写入成功'
    const body = res?.data || res
    if (body?.readback_tag_id != null) {
      row.readbackTagId = body.readback_tag_id
      row.readbackTagName = body.readback_tag_name || row.readbackTagName || ''
    }
    if (body?.readback_value != null) {
      row.readbackValue = body.readback_value
      row.resultMsg += `，回读 ${body.readback_value}`
    }
    row.value = ''
    refreshLive()
  } catch (e: any) {
    row.status = 'error'
    row.resultMsg = e?.message || '写入失败'
  } finally {
    writingRow.value = null
  }
}

// ── 批量控制 ──
const selectedRows = ref<any[]>([])
const onSelectionChange = (rowsSel: any[]) => {
  selectedRows.value = rowsSel
}
const batchValue = ref('')

// 统一值应用到所选行
const applyBatchValue = () => {
  if (!selectedRows.value.length) {
    ElMessage.warning('请先勾选点位')
    return
  }
  if (batchValue.value === '') {
    ElMessage.warning('请先输入要写入的值')
    return
  }
  selectedRows.value.forEach((row) => {
    row.value = batchValue.value
  })
  ElMessage.success(`已应用到 ${selectedRows.value.length} 个点位`)
}

// 执行：默认执行全部已填值的行；若勾选则只执行勾选行
const execute = async (scope: 'selected' | 'all') => {
  let targets: any[]
  if (scope === 'selected') {
    if (!selectedRows.value.length) {
      ElMessage.warning('请先勾选点位')
      return
    }
    targets = selectedRows.value
  } else {
    targets = rows.value
  }
  const valid = targets.filter((r) => r.value !== '' && r.value != null)
  if (!valid.length) {
    ElMessage.warning('没有已填写值的点位')
    return
  }
  const title = scope === 'selected' ? '批量执行确认（所选点位）' : '批量执行确认（全部已填值点位）'
  const detail = valid
    .slice(0, 10)
    .map((r) => `· ${r.device_name} / ${r.name} → ${r.value}`)
    .join('\n')
  const overflow = valid.length > 10 ? `\n...及其余 ${valid.length - 10} 个点位` : ''
  try {
    await ElMessageBox.confirm(
      `确认向 ${valid.length} 个点位下发写入指令？\n\n${detail}${overflow}`,
      title,
      {
        type: 'warning',
        confirmButtonText: '确认执行',
        cancelButtonText: '取消',
        center: false
      }
    )
  } catch {
    return
  }

  executing.value = true

  const items = valid.map((r) => ({
    device_id: r.device_id,
    tag_id: r.id,
    value: Number(r.value)
  }))

  // 重置状态
  valid.forEach((r) => {
    r.status = 'pending'
    r.resultMsg = ''
    r.readbackValue = undefined
  })

  try {
    const res: any = await batchWriteDevices({ items, stop_on_error: stopOnError.value })
    const body = res?.data || res
    const results = body?.results || []
    for (const r of results) {
      const target = valid[r.index]
      if (target) {
        target.status = r.success ? 'success' : 'error'
        target.resultMsg = r.message
        if (r.success) target.value = ''
        if (r.readback_tag_id != null) target.readbackTagId = r.readback_tag_id
        if (r.readback_value != null) {
          target.readbackValue = r.readback_value
          target.resultMsg += `，回读 ${r.readback_value}`
        }
      }
    }
    refreshLive()
    const successCount = body?.success ?? 0
    const failCount = body?.failed ?? 0
    if (failCount === 0) {
      ElMessage.success(`全部 ${successCount} 条指令执行成功`)
    } else {
      ElMessage.warning(`执行完成：成功 ${successCount}，失败 ${failCount}`)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '批量执行失败')
    valid.forEach((r) => {
      if (r.status === 'pending') {
        r.status = 'error'
        r.resultMsg = '请求失败'
      }
    })
  } finally {
    executing.value = false
  }
}

const clearValues = () => {
  rows.value.forEach((r) => {
    r.value = ''
    r.status = 'pending'
    r.resultMsg = ''
  })
  selectedRows.value.forEach((r) => {
    r.value = ''
    r.status = 'pending'
    r.resultMsg = ''
  })
  batchValue.value = ''
}

const stopOnError = ref(false)
const executing = ref(false)

const stats = computed(() => {
  const totalValid = rows.value.filter((r) => r.value !== '' && r.value != null).length
  const success = rows.value.filter((r) => r.status === 'success').length
  const error = rows.value.filter((r) => r.status === 'error').length
  return { totalValid, success, error }
})

// 自动刷新（可选）
const REFRESH_OPTIONS = [
  { label: '5秒', value: 5 },
  { label: '10秒', value: 10 },
  { label: '30秒', value: 30 },
  { label: '关闭', value: 0 }
]
const refreshInterval = ref(10)
let refreshTimer: ReturnType<typeof setInterval> | null = null
const setupAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  if (refreshInterval.value > 0) {
    refreshTimer = setInterval(() => refreshLive(), refreshInterval.value * 1000)
  }
}

onMounted(() => {
  fetchRows()
  wsManager.on('live_value', onLiveValue)
  setupAutoRefresh()
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<template>
  <ContentWrap title="批量远程控制">
    <ElAlert
      title="控制的是设备的可写点位：表格中填写「写入值」后执行。可单行写入，也可勾选多行批量写入。"
      type="warning"
      :closable="false"
      class="mb-16px"
    />

    <!-- 组织架构级联筛选（同采集点位页） -->
    <div class="mb-12px">
      <OrgCascadeSelect
        v-model="selectedIds"
        v-model:path="orgPath"
        :writable-only="true"
        :enabled-only="true"
        @search="onKeywordSearch"
        @update:path="onPathChange"
      />
    </div>

    <!-- 工具栏：搜索 + 批量操作 -->
    <div class="flex items-center mb-12px flex-wrap gap-8px">
      <ElInput
        v-model="searchKeyword"
        placeholder="搜索设备名/点位名"
        clearable
        style="max-width: 220px"
        @keyup.enter="onKeywordSearch"
        @clear="onKeywordSearch"
      />
      <ElButton type="primary" @click="onKeywordSearch">搜索</ElButton>
      <span class="text-12px text-gray-500 ml-4px">当前范围：{{ scopeLabel }}</span>

      <span class="flex-grow" />

      <!-- 批量写入区（勾选行后出现） -->
      <template v-if="selectedRows.length">
        <span class="text-12px text-gray-500">已选 {{ selectedRows.length }} 项</span>
        <ElInput
          v-model="batchValue"
          placeholder="统一写入值"
          style="width: 120px"
          size="small"
          @keyup.enter="applyBatchValue"
        />
        <ElButton size="small" type="primary" plain @click="applyBatchValue">应用</ElButton>
        <ElButton size="small" type="danger" @click="execute('selected')">执行所选</ElButton>
        <span class="text-gray-300 mx-4px">|</span>
      </template>

      <span class="text-13px text-gray-500">遇错停止</span>
      <ElSwitch v-model="stopOnError" />
      <ElButton type="danger" :loading="executing" @click="execute('all')">▶ 执行全部</ElButton>
      <ElButton @click="clearValues">清空</ElButton>

      <!-- 自动刷新 -->
      <span class="text-13px text-gray-500 ml-8px">刷新</span>
      <ElSelect v-model="refreshInterval" style="width: 90px" @change="setupAutoRefresh">
        <ElOption v-for="opt in REFRESH_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
      </ElSelect>
      <ElButton link @click="refreshLive">
        <ElTooltip content="立即刷新实时值" placement="top">
          <span style="font-size: 16px">↻</span>
        </ElTooltip>
      </ElButton>
    </div>

    <!-- 执行结果统计 -->
    <ElCard v-if="stats.success > 0 || stats.error > 0" shadow="never" class="mb-12px">
      <div class="flex items-center gap-24px">
        <div>
          <span class="text-12px text-gray-500">已填值</span>
          <div class="text-20px font-700">{{ stats.totalValid }}</div>
        </div>
        <div>
          <span class="text-12px text-gray-500">成功</span>
          <div class="text-20px font-700 text-green-500">{{ stats.success }}</div>
        </div>
        <div>
          <span class="text-12px text-gray-500">失败</span>
          <div class="text-20px font-700 text-red-500">{{ stats.error }}</div>
        </div>
        <ElProgress
          v-if="stats.totalValid > 0"
          :percentage="Math.round((stats.success / stats.totalValid) * 100)"
          :status="stats.error > 0 ? 'exception' : 'success'"
          class="flex-1"
        />
      </div>
    </ElCard>

    <!-- 可写点位表格 -->
    <ElTable v-loading="loading" :data="rows" border stripe @selection-change="onSelectionChange">
      <template #empty><ElEmpty description="当前筛选条件下没有可写点位" :image-size="80" /></template>
      <ElTableColumn type="selection" width="45" />
      <ElTableColumn sortable prop="device_name" label="设备" min-width="130" show-overflow-tooltip />
      <ElTableColumn sortable prop="name" label="点位" min-width="120" show-overflow-tooltip />
      <ElTableColumn label="地址" width="80">
        <template #default="{ row }">{{ row.address ?? '—' }}</template>
      </ElTableColumn>
      <ElTableColumn label="单位" width="70">
        <template #default="{ row }">{{ row.unit || '—' }}</template>
      </ElTableColumn>
      <ElTableColumn label="当前值" width="150" align="center">
        <template #default="{ row }">
          <template v-if="liveMap[row.device_id] && liveMap[row.device_id][row.id] != null">
            <span class="text-15px font-700 tabular-nums">{{ liveMap[row.device_id][row.id].value }}</span>
          </template>
          <span v-else class="text-12px text-gray-400">—</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="写入值" width="140">
        <template #default="{ row }">
          <ElInput
            v-model="row.value"
            placeholder="数值"
            size="default"
            @keyup.enter="writeRow(row)"
          />
        </template>
      </ElTableColumn>
      <ElTableColumn label="状态" width="90">
        <template #default="{ row }">
          <ElTag v-if="row.status === 'success'" type="success" size="small">✓ 成功</ElTag>
          <ElTag v-else-if="row.status === 'error'" type="danger" size="small">✗ 失败</ElTag>
          <ElTag v-else type="info" size="small">待执行</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="回读确认" min-width="170" show-overflow-tooltip>
        <template #default="{ row }">
          <template v-if="row.readbackTagName">
            <div class="text-12px text-gray-400">{{ row.readbackTagName }}</div>
            <span
              v-if="row.readbackValue != null"
              class="text-15px font-700 text-green-600 tabular-nums"
              >{{ row.readbackValue }}</span
            >
            <span
              v-else-if="liveMap[row.device_id] && liveMap[row.device_id][row.readbackTagId] != null"
              class="text-13px tabular-nums"
              >{{ liveMap[row.device_id][row.readbackTagId].value }}</span
            >
            <span v-else class="text-12px text-gray-400">—</span>
          </template>
          <span v-else class="text-12px text-gray-400">未关联</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="结果" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="row.status === 'success' ? 'text-green-500' : row.status === 'error' ? 'text-red-500' : 'text-gray-400'">
            {{ row.resultMsg || '' }}
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <ElButton link type="primary" :loading="writingRow === row.id" @click="writeRow(row)"
            >写入</ElButton
          >
        </template>
      </ElTableColumn>
    </ElTable>

    <div class="flex justify-end mt-12px">
      <ElPagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, sizes, prev, pager, next"
        :page-sizes="[20, 50, 100, 200]"
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>
  </ContentWrap>
</template>