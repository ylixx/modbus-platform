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
import { ref, reactive, onMounted, computed } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElSelect,
  ElOption,
  ElInput,
  ElInputNumber,
  ElDialog,
  ElForm,
  ElFormItem,
  ElMessage,
  ElMessageBox,
  ElAlert,
  ElSwitch,
  ElDivider,
  ElEmpty,
  ElProgress,
  ElCard
} from 'element-plus'
import {
  getAllDevices,
  getDeviceTags,
  batchWriteDevices,
  unwrap,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'BatchControl' })

// ── 设备/点位数据 ──
const devices = ref<any[]>([])
const allTags = ref<Record<number, any[]>>({}) // deviceId -> tags

const fetchDevices = async () => {
  devices.value = unwrapList(await getAllDevices()).list
}

const fetchTags = async (deviceId: number) => {
  if (allTags.value[deviceId]) return
  const res = await getDeviceTags(deviceId)
  const body = unwrap(res)
  allTags.value[deviceId] = Array.isArray(body) ? body : unwrapList(res).list
}

const getWritableTags = (deviceId: number) => {
  return (allTags.value[deviceId] || []).filter((t) => t.writable)
}

// ── 指令列表 ──
interface Instruction {
  id: string
  device_id: number | null
  tag_id: number | null
  value: string
  // 执行结果
  status?: 'pending' | 'success' | 'error' | 'skipped'
  resultMsg?: string
}

let nextId = 1
const genId = () => `inst_${nextId++}`

const instructions = ref<Instruction[]>([
  { id: genId(), device_id: null, tag_id: null, value: '', status: 'pending' }
])

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
  tag_id: null as number | null,
  value: ''
})
const batchTagOptions = ref<any[]>([])

const openBatchAdd = () => {
  batchForm.device_ids = []
  batchForm.tag_id = null
  batchForm.value = ''
  batchTagOptions.value = []
  batchDialogVisible.value = true
}

const onBatchDeviceChange = async () => {
  if (!batchForm.device_ids.length) {
    batchTagOptions.value = []
    return
  }
  // 用第一个设备的点位作为参考（假设同类型设备点位一致）
  const firstDeviceId = batchForm.device_ids[0]
  await fetchTags(firstDeviceId)
  batchTagOptions.value = getWritableTags(firstDeviceId)
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

// 删除指令
const removeInstruction = (idx: number) => {
  instructions.value.splice(idx, 1)
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
  if (deviceId) await fetchTags(deviceId)
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
    { type: 'warning', confirmText: '确认执行' }
  )

  executing.value = true
  executed.value = true

  // 重置状态
  instructions.value.forEach((inst) => {
    inst.status = 'pending'
    inst.resultMsg = ''
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
      }
    }

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

onMounted(fetchDevices)
</script>

<template>
  <ContentWrap title="批量远程控制">
    <ElAlert
      title="批量控制可同时向多个设备下发写入指令。请仔细核对每条指令的设备、点位和数值。"
      type="warning"
      :closable="false"
      class="mb-16px"
    />

    <!-- 操作栏 -->
    <div class="flex items-center justify-between mb-12px">
      <div class="flex items-center gap-8px">
        <ElButton type="primary" @click="addInstruction">+ 添加指令</ElButton>
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
    <ElTable :data="instructions" border stripe>
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
            <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
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
      <ElTableColumn label="操作" width="70" fixed="right">
        <template #default="{ $index }">
          <ElButton link type="danger" @click="removeInstruction($index)">删除</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>

    <!-- 批量添加对话框 -->
    <ElDialog v-model="batchDialogVisible" title="批量添加指令（同点多设备）" width="560px">
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
            <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
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
