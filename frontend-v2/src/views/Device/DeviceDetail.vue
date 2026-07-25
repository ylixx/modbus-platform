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
  ElBadge
} from 'element-plus'
import { getDevice, getDeviceLive, unwrap } from '@/api/modbus'
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
const autoRefresh = ref(true)
let pollTimer: any = null
let unsubFns: (() => void)[] = []

const wsConnected = computed(() => wsStore.connected)

const statusType = (s?: string) => (s === 'online' ? 'success' : s === 'error' ? 'danger' : 'info')
const statusText = (s?: string) => (s === 'online' ? '在线' : s === 'error' ? '异常' : '离线')

const fetchDevice = async () => {
  device.value = unwrap(await getDevice(id)) || {}
}
const fetchLive = async () => {
  try {
    const body = unwrap(await getDeviceLive(id))
    liveRows.value = Array.isArray(body) ? body : body?.tags || body?.data || []
  } catch (e) {
    // ignore
  }
}

// WebSocket 实时数据更新
const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d || d.device_id !== Number(id)) return

  const idx = liveRows.value.findIndex((r: any) => r.tag_name === d.tag_name || r.name === d.tag_name)
  if (idx !== -1) {
    const updated = [...liveRows.value]
    updated[idx] = { ...updated[idx], value: d.value, quality: d.quality }
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

onMounted(() => {
  fetchDevice()
  fetchLive()

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
          <span class="text-13px text-gray-500 mr-6px">轮询</span>
          <ElSwitch v-model="autoRefresh" @change="setupPolling" />
        </div>
      </template>
      <ElEmpty v-if="!liveRows.length" description="暂无实时数据" />
      <ElTable v-else :data="liveRows" border stripe>
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
      </ElTable>
    </ContentWrap>
  </div>
</template>
