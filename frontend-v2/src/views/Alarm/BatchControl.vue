<script setup lang="ts">
/**
 * 批量远程控制
 *
 * 功能：
 * 1. 编辑指令列表（每条：设备 + 点位 + 值）
 * 2. 从模板快速添加（同一点位 → 多设备）
 * 3. 一键执行全部指令，实时显示每条结果
 * 4. 保存/加载常用指令组
 */
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElSelect,
  ElOption,
  ElInput,
  ElDialog,
  ElForm,
  ElFormItem,
  ElMessage,
  ElMessageBox,
  ElAlert,
  ElSwitch,
  ElEmpty,
  ElProgress,
  ElCard
} from 'element-plus'
import {
  getAllDevices,
  getDeviceTags,
  getDeviceLive,
  batchWriteDevices,
  unwrap,
  unwrapList
} from '@/api/modbus'
import OrgCascadeSelect from '@/components/OrgCascadeSelect.vue'

defineOptions({ name: 'BatchControl' })

// ── 设备/点位数据 ──
const devicesLoading = ref(false)
const devices = ref<any[]>([])
const allTags = ref<Record<number, any[]>>({}) // deviceId -> tags

const fetchDevices = async () => {
  devicesLoading.value = true
  try {
    devices.value = unwrapList(await getAllDevices()).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取设备列表失败')
  } finally {
    devicesLoading.value = false
  }
}

const fetchTags = async (deviceId: number) => {
  if (allTags.value[deviceId]) return
  try {
    const res = await getDeviceTags(deviceId)
    const body = unwrap(res)
    allTags.value[deviceId] = Array.isArray(body) ? body : unwrapList(res).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取点位列表失败')
  }
}

const getWritableTags = (deviceId: number) => {
  return (allTags.value[deviceId] || []).filter((t) => t.writable)
}

// 实时值缓存：deviceId -> { tagId: { value, quality, time } }，用于「当前值 / 回读值」列
const liveMap = ref<Record<number, Record<number, any>>>({})

const fetchLiveForDevices = async (ids: number[]) => {
  await Promise.all(
    ids.map(async (id) => {
      try {
        const body = unwrap(await getDeviceLive(id))
        const values =
          body && typeof body === 'object' && !Array.isArray(body) && body.values
            ? body.values
            : {}
        liveMap.value[id] = values
      } catch {
        // 实时拉取失败（如设备离线）：保留已有值，不阻塞界面
        if (!liveMap.value[id]) liveMap.value[id] = {}
      }
    })
  )
}

// 在已加载点位中查找某 tag
const findTag = (deviceId: number | null, tagId: number | null) => {
  if (!deviceId || !tagId) return null
  return (allTags.value[deviceId] || []).find((t) => t.id === tagId) || null
}

// 返回某点位绑定的「回读寄存器」tag（未配置则返回 null）
const readbackTagOf = (deviceId: number | null, tagId: number | null) => {
  const t = findTag(deviceId, tagId)
  if (!t || !t.readback_tag_id) return null
  return findTag(deviceId, t.readback_tag_id)
}

// 组织架构级联筛选（同实时数据页）：选中设备后自动拉取其可写点位
const selectedIds = ref<number[]>([])
const orgPath = ref<{ org_node_id: number | null; labels: string[] } | null>(null)

// 当前加载范围：级联未选 -> 全部设备；级联选中 -> 仅选中设备
const targetDeviceIds = computed(() => {
  if (selectedIds.value.length) return selectedIds.value
  return devices.value.map((d) => d.id)
})

// 仅含可写点位的设备（无写点位的设备自动排除，不显示/不被搜索）
const writableDeviceIds = computed(() => {
  const set = new Set<number>()
  for (const [id, tags] of Object.entries(allTags.value)) {
    if (Array.isArray(tags) && tags.some((t) => t.writable)) set.add(Number(id))
  }
  return set
})
const writableDevices = computed(() => devices.value.filter((d) => writableDeviceIds.value.has(d.id)))

const scopeLabel = computed(() => {
  return selectedIds.value.length
    ? `已选 ${selectedIds.value.length} 台设备`
    : `全部 ${writableDevices.value.length} 台设备（均含可写点位）`
})

// 自动拉取设备的可写点位，生成为指令行展示（按设备+点位去重）
// 级联为空默认列出全部设备的可写点位；级联选中则只列选中设备
const loadWritablePoints = async () => {
  const ids = targetDeviceIds.value
  if (!ids.length) {
    ElMessage.info('当前没有可控制的设备')
    return
  }
  try {
  // 并发拉取所有目标设备点位
  await Promise.all(ids.map((id) => fetchTags(id)))

  if (selectedIds.value.length) {
    // 级联选中时：清掉不在选中设备集合内的旧指令，让表格精确反映筛选范围
    instructions.value = instructions.value.filter((i) =>
      selectedIds.value.includes(i.device_id as number)
    )
  } else {
    // 默认范围（全部设备）：清掉残留的占位/无效空行，按范围重建，避免空设备行
    instructions.value = instructions.value.filter((i) => i.device_id && i.tag_id)
  }

  let added = 0
  for (const deviceId of ids) {
    for (const t of getWritableTags(deviceId)) {
      const exists = instructions.value.some(
        (i) => i.device_id === deviceId && i.tag_id === t.id
      )
      if (!exists) {
        instructions.value.push({
          id: genId(),
          device_id: deviceId,
          tag_id: t.id,
          value: '',
          status: 'pending'
        })
        added++
      }
    }
  }

  executed.value = false
  const validCount = instructions.value.filter((i) => i.device_id && i.tag_id).length
  if (!validCount) {
    // 当前范围内确实没有可写点位：保留一条占位行，方便用户手动添加
    instructions.value = [
      { id: genId(), device_id: null, tag_id: null, value: '', status: 'pending' }
    ]
    ElMessage.warning('当前范围内没有可写点位，可手动添加指令')
    fetchLiveForDevices(ids).catch(() => {})
    return
  }
  ElMessage.success(
    `已加载可写点位：${scopeLabel.value}，共 ${validCount} 条（新增 ${added} 条）`
  )
  // 同步刷新实时值，保证「当前值 / 回读值」列随筛选范围更新
  fetchLiveForDevices(ids).catch(() => {})
  } catch (e: any) {
    ElMessage.error(e?.message || '加载可写点位失败')
  }
}

// 级联选择变化时自动按新范围刷新列表
watch(selectedIds, () => {
  loadWritablePoints()
})

// ── 指令列表 ──
interface Instruction {
  id: string
  device_id: number | null
  tag_id: number | null
  value: string
  // 执行结果
  status?: 'pending' | 'success' | 'error' | 'skipped'
  resultMsg?: string
  // 写后即时回读值（来自写接口返回，作为首屏即时反馈；随后由实时刷新接管）
  readbackValue?: any
}

let nextId = 1
const genId = () => `inst_${nextId++}`

const instructions = ref<Instruction[]>([])

const stopOnError = ref(false)
const executing = ref(false)
const executed = ref(false)

// 添加指令
const addInstruction = () => {
  instructions.value.push({
    id: genId(),
    device_id: null,
    tag_id: null,
    value: '',
    status: 'pending'
  })
}

// 从选中设备批量添加（同一点位）
const batchDialogVisible = ref(false)
const batchForm = reactive({
  device_ids: [] as number[],
  tag_id: undefined as number | undefined,
  value: ''
})
const batchTagOptions = ref<any[]>([])

const openBatchAdd = () => {
  batchForm.device_ids = []
  batchForm.tag_id = undefined
  batchForm.value = ''
  batchTagOptions.value = []
  batchDialogVisible.value = true
}

const onBatchDeviceChange = async () => {
  if (!batchForm.device_ids.length) {
    batchTagOptions.value = []
    return
  }
  try {
  // 用第一个设备的点位作为参考（假设同类型设备点位一致）
  const firstDeviceId = batchForm.device_ids[0]
  await fetchTags(firstDeviceId)
  batchTagOptions.value = getWritableTags(firstDeviceId)
  } catch (e: any) {
    ElMessage.error(e?.message || '获取点位列表失败')
  }
}

const confirmBatchAdd = () => {
  if (!batchForm.device_ids.length || !batchForm.tag_id) {
    ElMessage.warning('请选择设备和点位')
    return
  }
  for (const deviceId of batchForm.device_ids) {
    instructions.value.push({
      id: genId(),
      device_id: deviceId,
      tag_id: batchForm.tag_id,
      value: batchForm.value,
      status: 'pending'
    })
  }
  batchDialogVisible.value = false
  ElMessage.success(`已添加 ${batchForm.device_ids.length} 条指令`)
}

const resetBatchForm = () => {
  batchForm.device_ids = []
  batchForm.tag_id = undefined
  batchForm.value = ''
  batchTagOptions.value = []
}

// 删除指令
const removeInstruction = async (idx: number) => {
  try {
    await ElMessageBox.confirm('确认删除该指令？', '提示', { type: 'warning' })
    instructions.value.splice(idx, 1)
  } catch {
    // cancelled
  }
}

// 清空指令
const clearInstructions = () => {
  instructions.value = [{ id: genId(), device_id: null, tag_id: null, value: '', status: 'pending' }]
  executed.value = false
}

// 设备选择变更
const onDeviceChange = async (idx: number, deviceId: number) => {
  instructions.value[idx].tag_id = null
  instructions.value[idx].status = 'pending'
  instructions.value[idx].resultMsg = ''
  try {
    if (deviceId) await fetchTags(deviceId)
  } catch (e: any) {
    ElMessage.error(e?.message || '获取点位列表失败')
  }
}

// ── 执行 ──
const executeAll = async () => {
  // 校验
  const validInstructions = instructions.value.filter(
    (inst) => inst.device_id && inst.tag_id && inst.value !== '' && inst.value != null
  )
  if (!validInstructions.length) {
    ElMessage.warning('没有有效的指令')
    return
  }

  await ElMessageBox.confirm(
    `确认执行 ${validInstructions.length} 条控制指令？`,
    '批量控制确认',
    { type: 'warning', confirmButtonText: '确认执行' }
  )

  executing.value = true
  executed.value = true

  // 重置状态
  instructions.value.forEach((inst) => {
    inst.status = 'pending'
    inst.resultMsg = ''
    inst.readbackValue = undefined
  })

  try {
    const items = validInstructions.map((inst) => ({
      device_id: inst.device_id!,
      tag_id: inst.tag_id!,
      value: Number(inst.value)
    }))

    const res: any = await batchWriteDevices({
      items,
      stop_on_error: stopOnError.value
    })

    const body = res?.data || res
    const results = body?.results || []

    // 回填结果
    for (const r of results) {
      const inst = validInstructions[r.index]
      if (inst) {
        inst.status = r.success ? 'success' : 'error'
        inst.resultMsg = r.message
        if (r.readback_value != null) inst.readbackValue = r.readback_value
      }
    }

    // 执行后刷新所有相关设备的实时值：回读列同步回读寄存器最新状态（WS/轮询亦持续更新）
    await fetchLiveForDevices(validInstructions.map((i) => i.device_id as number))

    const successCount = body?.success ?? 0
    const failCount = body?.failed ?? 0
    if (failCount === 0) {
      ElMessage.success(`全部 ${successCount} 条指令执行成功`)
    } else {
      ElMessage.warning(`执行完成：成功 ${successCount}，失败 ${failCount}`)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '批量执行失败')
    instructions.value.forEach((inst) => {
      if (inst.status === 'pending') {
        inst.status = 'error'
        inst.resultMsg = '请求失败'
      }
    })
  } finally {
    executing.value = false
  }
}

// 统计
const stats = computed(() => {
  const total = instructions.value.filter(
    (i) => i.device_id && i.tag_id && i.value !== ''
  ).length
  const success = instructions.value.filter((i) => i.status === 'success').length
  const error = instructions.value.filter((i) => i.status === 'error').length
  return { total, success, error }
})

onMounted(async () => {
  try {
    await fetchDevices()
    // 级联未选时默认列出全部设备的可写点位
    await loadWritablePoints()
    // 初始拉取实时值，让「当前值 / 回读值」列首屏即有数据
    await fetchLiveForDevices(targetDeviceIds.value)
  } catch (e: any) {
    ElMessage.error(e?.message || '初始化失败')
  }
})
</script>

<template>
  <ContentWrap title="批量远程控制">
    <ElAlert
      title="批量控制可同时向多个设备下发写入指令。请仔细核对每条指令的设备、点位和数值。"
      type="warning"
      :closable="false"
      class="mb-16px"
    />

    <!-- 组织架构级联筛选（与实时数据页一致）：选择被控制的设备 -->
    <div class="mb-16px flex items-center gap-12px flex-wrap">
      <OrgCascadeSelect v-model="selectedIds" v-model:path="orgPath" :writable-only="true" @search="loadWritablePoints" />
      <ElTag type="info" effect="plain">当前范围：{{ scopeLabel }}</ElTag>
    </div>

    <!-- 操作栏 -->
    <div class="flex items-center justify-between mb-12px">
      <div class="flex items-center gap-8px">
        <ElButton type="primary" @click="loadWritablePoints">加载可写点位（按当前范围）</ElButton>
        <ElButton type="primary" plain @click="addInstruction">+ 添加指令</ElButton>
        <ElButton @click="openBatchAdd">批量添加（同点多设备）</ElButton>
        <ElButton type="danger" plain @click="clearInstructions">清空</ElButton>
      </div>
      <div class="flex items-center gap-12px">
        <span class="text-13px text-gray-500">遇错停止</span>
        <ElSwitch v-model="stopOnError" />
        <ElButton
          type="danger"
          :loading="executing"
          :disabled="!instructions.length"
          @click="executeAll"
        >
          ▶ 执行全部指令
        </ElButton>
      </div>
    </div>

    <!-- 执行结果统计 -->
    <div v-if="executed" class="mb-12px">
      <ElCard shadow="never">
        <div class="flex items-center gap-24px">
          <div>
            <span class="text-12px text-gray-500">有效指令</span>
            <div class="text-20px font-700">{{ stats.total }}</div>
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
            v-if="stats.total > 0"
            :percentage="Math.round((stats.success / stats.total) * 100)"
            :status="stats.error > 0 ? 'exception' : 'success'"
            class="flex-1"
          />
        </div>
      </ElCard>
    </div>

    <!-- 指令列表 -->
    <ElTable v-loading="devicesLoading" :data="instructions" border stripe>
      <template #empty><ElEmpty description="暂无数据" :image-size="80" /></template>
      <ElTableColumn label="#" width="50" type="index" />
      <ElTableColumn label="设备" min-width="180">
        <template #default="{ row, $index }">
          <ElSelect
            v-model="row.device_id"
            class="w-full"
            placeholder="选择设备"
            filterable
            @change="onDeviceChange($index, $event)"
          >
            <ElOption v-for="d in writableDevices" :key="d.id" :label="d.name" :value="d.id" />
          </ElSelect>
        </template>
      </ElTableColumn>
      <ElTableColumn label="可写点位" min-width="180">
        <template #default="{ row }">
          <ElSelect
            v-model="row.tag_id"
            class="w-full"
            placeholder="选择点位"
            filterable
            :disabled="!row.device_id"
          >
            <ElOption
              v-for="t in getWritableTags(row.device_id)"
              :key="t.id"
              :label="`${t.name} (${t.address})`"
              :value="t.id"
            />
          </ElSelect>
        </template>
      </ElTableColumn>
      <ElTableColumn label="写入值" width="150">
        <template #default="{ row }">
          <ElInput v-model="row.value" placeholder="数值" />
        </template>
      </ElTableColumn>
      <ElTableColumn label="状态" width="120">
        <template #default="{ row }">
          <ElTag v-if="row.status === 'success'" type="success" size="small">✓ 成功</ElTag>
          <ElTag v-else-if="row.status === 'error'" type="danger" size="small">✗ 失败</ElTag>
          <ElTag v-else-if="row.status === 'skipped'" type="info" size="small">跳过</ElTag>
          <ElTag v-else type="info" size="small">待执行</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="结果" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="row.status === 'success' ? 'text-green-500' : 'text-red-500'">
            {{ row.resultMsg || '' }}
          </span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="当前值" min-width="110">
        <template #default="{ row }">
          <template v-if="row.device_id && row.tag_id && liveMap[row.device_id] && liveMap[row.device_id][row.tag_id] != null">
            <span class="text-15px font-700">
              {{ liveMap[row.device_id][row.tag_id].value }}
            </span>
            <span class="text-12px text-gray-400 ml-2px">{{ findTag(row.device_id, row.tag_id)?.unit || '' }}</span>
          </template>
          <span v-else class="text-12px text-gray-400">—</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="回读值" min-width="140">
        <template #default="{ row }">
          <template v-if="row.device_id && row.tag_id">
            <template v-if="readbackTagOf(row.device_id, row.tag_id)">
              <span class="text-15px font-700 text-blue-500">
                {{ (liveMap[row.device_id] && liveMap[row.device_id][readbackTagOf(row.device_id, row.tag_id).id] != null)
                  ? liveMap[row.device_id][readbackTagOf(row.device_id, row.tag_id).id].value
                  : (row.readbackValue ?? '—') }}
              </span>
              <div class="text-12px text-gray-400">← {{ readbackTagOf(row.device_id, row.tag_id).name }}</div>
            </template>
            <span v-else class="text-12px text-gray-400">未配置</span>
          </template>
          <span v-else class="text-12px text-gray-400">—</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="70" fixed="right">
        <template #default="{ $index }">
          <ElButton link type="danger" @click="removeInstruction($index)">删除</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>

    <!-- 批量添加对话框 -->
    <ElDialog v-model="batchDialogVisible" title="批量添加指令（同点多设备）" width="560px" @close="resetBatchForm">
      <ElForm label-width="90px">
        <ElFormItem label="目标设备">
          <ElSelect
            v-model="batchForm.device_ids"
            class="w-full"
            multiple
            filterable
            placeholder="选择多个设备"
            @change="onBatchDeviceChange"
          >
            <ElOption v-for="d in writableDevices" :key="d.id" :label="d.name" :value="d.id" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="可写点位">
          <ElSelect
            v-model="batchForm.tag_id"
            class="w-full"
            filterable
            placeholder="选择点位（取第一个设备的点位列表）"
            :disabled="!batchForm.device_ids.length"
          >
            <ElOption
              v-for="t in batchTagOptions"
              :key="t.id"
              :label="`${t.name} (地址 ${t.address})`"
              :value="t.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="写入值">
          <ElInput v-model="batchForm.value" placeholder="要写入的值" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="batchDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="confirmBatchAdd">添加</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
