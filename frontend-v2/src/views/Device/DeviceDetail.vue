<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElDescriptions,
  ElDescriptionsItem,
  ElTag,
  ElTable,
  ElTableColumn,
  ElEmpty,
  ElSwitch,
  ElBadge,
  ElMessage,
  ElMessageBox
} from 'element-plus'
import { getDevice, getDeviceLive, writeDevice, unwrap } from '@/api/modbus'
import { deviceStatusType, deviceStatusText } from '@/utils/modbus'
import { useWsStore } from '@/store/modules/websocket'
import { wsManager } from '@/utils/websocket'
import type { WsLiveValue } from '@/utils/websocket'

defineOptions({ name: 'DeviceDetail' })

const route = useRoute()
const router = useRouter()
const wsStore = useWsStore()
const id = route.params.id as string
const device = ref<any>({})
const liveRows = ref<any[]>([])
const liveLoading = ref(false)
const autoRefresh = ref(true)
const writing = ref(false)
let pollTimer: any = null
let unsubFns: (() => void)[] = []

const wsConnected = computed(() => wsStore.connected)
const writableCount = computed(() => liveRows.value.filter((r) => r.writable).length)
// 点位 id -> 行，供「回读值」列按 readback_tag_id 引用回读寄存器的最新实时值
const tagRowMap = computed<Record<number, any>>(() => {
  const m: Record<number, any> = {}
  for (const r of liveRows.value) m[r.id] = r
  return m
})

// statusType / statusText 已从 @/utils/modbus 导入，添加别名以匹配模板
const statusType = deviceStatusType
const statusText = deviceStatusText

// 把实时字典（按 tag_id 索引）合并进 tags 基准行，保证「所有点位」始终显示
const mergeLive = (tags: any[], values: Record<number, any> = {}) => {
  return (tags || []).map((t) => {
    const lv = values?.[t.id]
    return {
      id: t.id,
      name: t.name,
      address: t.address,
      data_type: t.data_type,
      unit: t.unit,
      description: t.description,
      writable: t.writable,
      readback_tag_id: t.readback_tag_id ?? null,
      // 实时字段：无实时数据时 value=null、quality=unknown
      value: lv?.value ?? null,
      quality: lv?.quality ?? 'unknown',
      time: lv?.time ?? null
    }
  })
}

const fetchDevice = async () => {
  device.value = unwrap(await getDevice(id)) || {}
}

const fetchLive = async () => {
  const tags = device.value?.tags || []
  liveLoading.value = true
  try {
    const body = unwrap(await getDeviceLive(id))
    const values = (body && typeof body === 'object' && !Array.isArray(body) && body.values) || {}
    liveRows.value = mergeLive(tags, values)
  } catch (e) {
    liveRows.value = mergeLive(tags)
  } finally {
    liveLoading.value = false
  }
}

// WebSocket 实时数据更新
const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d || d.device_id !== Number(id)) return
  const idx = liveRows.value.findIndex((r: any) => r.id === d.tag_id || r.name === d.tag_name)
  if (idx !== -1) {
    const updated = [...liveRows.value]
    updated[idx] = { ...updated[idx], value: d.value, quality: d.quality ?? 'good', time: new Date().toISOString() }
    liveRows.value = updated
  }
}

// WebSocket 设备状态变更
const onDeviceStatus = (msg: any) => {
  const d = msg.data
  if (d && d.device_id === Number(id)) {
    device.value = { ...device.value, status: d.status }
  }
}

const setupPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  if (autoRefresh.value && !wsConnected.value) {
    pollTimer = setInterval(fetchLive, 3000)
  }
}

// 写值操作（仅 writable 点位可用）
const writeValue = async (row: any) => {
  try {
    const { value } = (await ElMessageBox.prompt(
      `请输入要写入「${row.name}」的值`,
      '写值操作',
      {
        inputPattern: /^-?\d+(\.\d+)?$/,
        inputErrorMessage: '请输入合法数字（支持负数与小数）',
        confirmButtonText: '写入',
        cancelButtonText: '取消'
      }
    )) as any
    if (value === '' || value == null) return
    writing.value = true
    const res: any = await writeDevice(Number(id), { tag_id: row.id, value: Number(value) })
    const body = res?.data || res || {}
    ElMessage.success(
      body.readback_value != null
        ? `写值成功，回读值：${body.readback_value}${row.unit || ''}`
        : '写值成功'
    )
    // 写后刷新实时数据：回读值列会同步回读寄存器最新值（WS/轮询亦持续更新）
    fetchLive()
    // 乐观更新该行，立即反馈写入结果
    const idx = liveRows.value.findIndex((r) => r.id === row.id)
    if (idx !== -1) {
      const updated = [...liveRows.value]
      updated[idx] = { ...updated[idx], value: Number(value), quality: 'good', time: new Date().toISOString() }
      liveRows.value = updated
    }
  } catch (e: any) {
    if (e === 'cancel' || e?.action === 'cancel') return
    const msg = e?.response?.data?.message || e?.message || '未知错误'
    ElMessage.error('写值失败：' + msg)
  } finally {
    writing.value = false
  }
}

// 跳转到该点位的实时曲线页
const goChart = (row: any) => {
  router.push(`/device/detail/${id}/tag/${row.id}/chart`)
}

onMounted(async () => {
  await fetchDevice()
  await fetchLive()

  unsubFns.push(wsManager.on('live_value', onLiveValue))
  unsubFns.push(wsManager.on('device_status', onDeviceStatus))
  setupPolling()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  unsubFns.forEach((fn) => fn())
})
</script>

<template>
  <div>
    <ContentWrap title="设备详情">
      <template #header>
        <div class="flex-grow flex justify-end items-center">
          <ElBadge :type="wsConnected ? 'success' : 'danger'" is-dot class="mr-12px">
            <span class="text-12px text-gray-400">
              {{ wsConnected ? 'WS 实时' : '轮询模式' }}
            </span>
          </ElBadge>
          <ElButton @click="router.push('/device/list')">返回列表</ElButton>
        </div>
      </template>
      <ElDescriptions :column="3" border>
        <ElDescriptionsItem label="设备名称">{{ device.name }}</ElDescriptionsItem>
        <ElDescriptionsItem label="协议">{{ device.protocol }}</ElDescriptionsItem>
        <ElDescriptionsItem label="状态">
          <ElTag :type="statusType(device.status)">{{ statusText(device.status) }}</ElTag>
        </ElDescriptionsItem>
        <ElDescriptionsItem label="主机">{{ device.host || '—' }}</ElDescriptionsItem>
        <ElDescriptionsItem label="端口">{{ device.port || '—' }}</ElDescriptionsItem>
        <ElDescriptionsItem label="从站地址">{{ device.slave_id ?? '—' }}</ElDescriptionsItem>
        <ElDescriptionsItem label="厂级">{{ device.factory || '—' }}</ElDescriptionsItem>
        <ElDescriptionsItem label="车间">{{ device.workshop || '—' }}</ElDescriptionsItem>
        <ElDescriptionsItem label="产线">{{ device.production_line || '—' }}</ElDescriptionsItem>
        <ElDescriptionsItem label="描述" :span="3">{{
          device.description || '—'
        }}</ElDescriptionsItem>
      </ElDescriptions>
    </ContentWrap>

    <ContentWrap title="实时点位数据" class="mt-16px">
      <template #header>
        <div class="flex-grow flex justify-end items-center">
          <span class="text-13px text-gray-500 mr-6px">
            共 {{ liveRows.length }} 个点位 · {{ writableCount }} 个可写
          </span>
          <span class="text-13px text-gray-500 mr-6px">轮询</span>
          <ElSwitch v-model="autoRefresh" @change="setupPolling" />
        </div>
      </template>
      <ElEmpty v-if="!liveRows.length" description="该设备暂未配置点位" />
      <ElTable v-else v-loading="liveLoading" :data="liveRows" border stripe max-height="520">
        <ElTableColumn sortable prop="name" label="点位名称" min-width="160" show-overflow-tooltip />
        <ElTableColumn sortable prop="address" label="地址" width="90" />
        <ElTableColumn sortable prop="data_type" label="类型" width="110" />
        <ElTableColumn label="当前值" min-width="120">
          <template #default="{ row }">
            <span
              class="text-16px font-700"
              :class="{
                'text-green-500': row.quality !== 'bad' && row.quality !== 'unknown' && !row.error,
                'text-red-500': row.quality === 'bad' || row.error,
                'text-gray-400': row.value == null
              }"
            >
              {{ row.value ?? '—' }}
            </span>
            <span class="text-12px text-gray-400 ml-4px">{{ row.unit || '' }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="质量" width="90">
          <template #default="{ row }">
            <ElTag
              v-if="row.quality && row.quality !== 'unknown'"
              :type="row.quality === 'bad' ? 'danger' : 'success'"
              size="small"
            >
              {{ row.quality === 'bad' ? '错误' : '正常' }}
            </ElTag>
            <span v-else class="text-12px text-gray-400">未采集</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="回读值" min-width="120">
          <template #default="{ row }">
            <template v-if="row.readback_tag_id && tagRowMap[row.readback_tag_id]">
              <span
                class="text-15px font-700"
                :class="{
                  'text-green-500': tagRowMap[row.readback_tag_id].quality === 'good',
                  'text-gray-400': tagRowMap[row.readback_tag_id].value == null
                }"
              >
                {{ tagRowMap[row.readback_tag_id].value ?? '—' }}
              </span>
              <span class="text-12px text-gray-400 ml-4px">{{
                tagRowMap[row.readback_tag_id].unit || ''
              }}</span>
            </template>
            <span v-else class="text-12px text-gray-400">—</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <ElButton
              v-if="row.writable"
              type="primary"
              link
              size="small"
              :loading="writing"
              @click="writeValue(row)"
            >
              写值
            </ElButton>
            <ElTag v-if="!row.writable" type="info" size="small" effect="plain">只读</ElTag>
            <ElButton type="success" link size="small" @click="goChart(row)">实时曲线</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </ContentWrap>
  </div>
</template>
