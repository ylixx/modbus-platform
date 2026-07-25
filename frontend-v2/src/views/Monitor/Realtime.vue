<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import { ElSelect, ElOption, ElTable, ElTableColumn, ElTag, ElSwitch, ElEmpty, ElBadge } from 'element-plus'
import { getAllDevices, getDeviceLive, unwrap, unwrapList } from '@/api/modbus'
import { useWsStore } from '@/store/modules/websocket'
import { wsManager } from '@/utils/websocket'
import type { WsLiveValue } from '@/utils/websocket'

defineOptions({ name: 'Realtime' })

const wsStore = useWsStore()

const devices = ref<any[]>([])
const currentDevice = ref<number | undefined>(undefined)
const rows = ref<any[]>([])
const autoRefresh = ref(true)
const useWs = ref(true) // 优先使用 WebSocket
const updatedAt = ref('')
let pollTimer: any = null
let unsubFns: (() => void)[] = []

const wsConnected = computed(() => wsStore.connected)

const fetchDevices = async () => {
  devices.value = unwrapList(await getAllDevices()).list
  if (devices.value.length) {
    currentDevice.value = devices.value[0].id
    fetchLive()
  }
}

const fetchLive = async () => {
  if (currentDevice.value == null) return
  try {
    const res = await getDeviceLive(currentDevice.value)
    const body = unwrap(res)
    rows.value = Array.isArray(body) ? body : body?.tags || body?.data || []
    updatedAt.value = new Date().toLocaleTimeString()
  } catch (e) {
    // ignore
  }
}

const onDeviceChange = () => {
  fetchLive()
  // 切换设备时，用 WS 缓存的数据更新
  applyWsData()
}

// 将 WebSocket 推送的实时数据合并到当前表格
const applyWsData = () => {
  if (!currentDevice.value) return
  const deviceId = currentDevice.value
  const updated = rows.value.map((row: any) => {
    const wsVal = wsStore.getLiveValue(deviceId, row.name)
    if (wsVal) {
      return { ...row, value: wsVal.value, quality: wsVal.quality }
    }
    return row
  })
  rows.value = updated
}

// 监听 WebSocket 实时数据
const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d || d.device_id !== currentDevice.value) return
  applyLiveValue(d)
}

const onBatchLive = (msg: any) => {
  const items = msg.data as WsLiveValue[]
  if (!Array.isArray(items)) return
  for (const d of items) {
    if (d.device_id === currentDevice.value) {
      applyLiveValue(d)
    }
  }
}

const applyLiveValue = (d: WsLiveValue) => {
  const idx = rows.value.findIndex((r: any) => r.tag_name === d.tag_name || r.name === d.tag_name)
  if (idx !== -1) {
    const updated = [...rows.value]
    updated[idx] = { ...updated[idx], value: d.value, quality: d.quality }
    rows.value = updated
  }
  updatedAt.value = new Date().toLocaleTimeString()
}

const setupPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  // 仅在 WebSocket 不可用时轮询
  if (autoRefresh.value && !useWs.value) {
    pollTimer = setInterval(fetchLive, 3000)
  }
}

onMounted(() => {
  fetchDevices()

  // 监听 WebSocket 实时数据
  unsubFns.push(wsManager.on('live_value', onLiveValue))
  unsubFns.push(wsManager.on('batch_live', onBatchLive))

  // 兜底轮询（WebSocket 未连接时降级）
  setupPolling()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  unsubFns.forEach((fn) => fn())
})

// WebSocket 连接状态变化时，切换轮询/WS 模式
watch(wsConnected, (connected) => {
  if (connected) {
    // WS 连上了，停止轮询
    if (pollTimer) clearInterval(pollTimer)
  } else {
    // WS 断了，降级轮询
    setupPolling()
  }
})
</script>

<template>
  <ContentWrap title="实时数据">
    <template #header>
      <div class="flex-grow flex justify-end items-center">
        <ElBadge :type="wsConnected ? 'success' : 'danger'" is-dot class="mr-8px">
          <span class="text-12px text-gray-400">
            {{ wsConnected ? 'WS 实时' : '轮询模式' }}
          </span>
        </ElBadge>
        <span class="text-12px text-gray-400 mr-12px" v-if="updatedAt">更新于 {{ updatedAt }}</span>
        <span class="text-13px text-gray-500 mr-6px">自动刷新</span>
        <ElSwitch v-model="autoRefresh" class="mr-14px" @change="setupPolling" />
        <ElSelect v-model="currentDevice" class="!w-200px" @change="onDeviceChange">
          <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
        </ElSelect>
      </div>
    </template>

    <ElEmpty v-if="!rows.length" description="暂无实时数据" />
    <ElTable v-else :data="rows" border stripe>
      <ElTableColumn prop="name" label="点位名称" min-width="160" show-overflow-tooltip />
      <ElTableColumn prop="address" label="地址" width="90" />
      <ElTableColumn label="当前值" min-width="120">
        <template #default="{ row }">
          <span
            class="text-16px font-700"
            :class="{
              'text-green-500': row.quality !== 'bad' && !row.error,
              'text-red-500': row.quality === 'bad' || row.error,
              'text-gray-400': row.value == null
            }"
          >
            {{ row.value ?? '—' }}
          </span>
          <span class="text-12px text-gray-400 ml-4px">{{ row.unit || '' }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="data_type" label="类型" width="110" />
      <ElTableColumn label="状态" width="100">
        <template #default="{ row }">
          <ElTag :type="row.quality === 'bad' || row.error ? 'danger' : 'success'">
            {{ row.quality === 'bad' || row.error ? '异常' : '正常' }}
          </ElTag>
        </template>
      </ElTableColumn>
    </ElTable>
  </ContentWrap>
</template>
