<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElDescriptions,
  ElDescriptionsItem,
  ElTag,
  ElTable,
  ElTableColumn,
  ElEmpty
} from 'element-plus'
import { getDevice, getDeviceLive, unwrap } from '@/api/modbus'

defineOptions({ name: 'DeviceDetail' })

const route = useRoute()
const router = useRouter()
const id = route.params.id as string
const device = ref<any>({})
const liveRows = ref<any[]>([])
let timer: any = null

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

onMounted(() => {
  fetchDevice()
  fetchLive()
  timer = setInterval(fetchLive, 3000)
})
onUnmounted(() => timer && clearInterval(timer))
</script>

<template>
  <div>
    <ContentWrap title="设备详情">
      <template #header>
        <div class="flex-grow flex justify-end">
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
      <ElEmpty v-if="!liveRows.length" description="暂无实时数据" />
      <ElTable v-else :data="liveRows" border stripe>
        <ElTableColumn prop="name" label="点位名称" min-width="160" show-overflow-tooltip />
        <ElTableColumn prop="address" label="地址" width="90" />
        <ElTableColumn label="当前值" min-width="120">
          <template #default="{ row }">{{ row.value ?? '—' }}{{ row.unit || '' }}</template>
        </ElTableColumn>
        <ElTableColumn prop="data_type" label="类型" width="110" />
      </ElTable>
    </ContentWrap>
  </div>
</template>
