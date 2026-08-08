<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElTable,
  ElTableColumn,
  ElTag,
  ElButton,
  ElEmpty,
  ElTooltip,
  ElSelect,
  ElOption,
  ElBadge
} from 'element-plus'
import { getDevicePublishStatus, triggerDevicePublish, unwrap } from '@/api/modbus'
import { ElMessage } from 'element-plus'

defineOptions({ name: 'DevicePublish' })

const list = ref<any[]>([])
const loading = ref(false)
const triggerBusy = ref<Set<number>>(new Set())
let timer: any = null
const refreshInterval = ref(10)

const protocolLabel = (p?: string) => {
  const map: Record<string, string> = {
    modbus_tcp: 'Modbus TCP',
    modbus_rtu: 'Modbus RTU',
    mqtt: 'MQTT',
    opc_ua: 'OPC-UA'
  }
  return map[p || ''] || p || '—'
}

const modeLabel = (m?: string) => {
  const map: Record<string, string> = {
    standard: '标准',
    thingsboard_device: 'TB设备',
    thingsboard_gateway: 'TB网关'
  }
  return map[m || ''] || m || '—'
}

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getDevicePublishStatus()
    list.value = unwrap(res) || []
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}

const handleTrigger = async (deviceId: number) => {
  triggerBusy.value.add(deviceId)
  try {
    await triggerDevicePublish(deviceId)
    ElMessage.success('触发成功')
    // Refresh immediately to show updated status
    await fetchList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '触发失败')
  } finally {
    triggerBusy.value.delete(deviceId)
  }
}

const formatTime = (iso?: string) => {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

onMounted(() => {
  fetchList()
  timer = setInterval(fetchList, refreshInterval.value * 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

// Watch refresh interval change
import { watch } from 'vue'
watch(refreshInterval, (val) => {
  if (timer) clearInterval(timer)
  timer = setInterval(fetchList, val * 1000)
})
</script>

<template>
  <ContentWrap title="设备MQTT发布状态">
    <div class="flex items-center justify-between mb-12px">
      <div class="flex items-center gap-8px text-13px text-gray-500">
        <span>已启用发布的设备：共 <b class="text-primary">{{ list.length }}</b> 台</span>
        <span class="ml-12px">运行中：<b class="text-green-500">{{ list.filter(i => i.running).length }}</b></span>
        <span class="ml-8px">断开：<b class="text-orange-500">{{ list.filter(i => i.running && !i.connected).length }}</b></span>
      </div>
      <div class="flex items-center gap-8px">
        <span class="text-12px text-gray-400">刷新间隔</span>
        <ElSelect v-model="refreshInterval" style="width: 100px" size="small">
          <ElOption label="5秒" :value="5" />
          <ElOption label="10秒" :value="10" />
          <ElOption label="30秒" :value="30" />
          <ElOption label="1分钟" :value="60" />
        </ElSelect>
        <ElButton size="small" @click="fetchList">刷新</ElButton>
      </div>
    </div>

    <ElTable v-loading="loading" :data="list" border stripe>
      <ElTableColumn sortable prop="device_id" label="设备ID" width="80" />
      <ElTableColumn prop="device_name" label="设备名称" min-width="150" show-overflow-tooltip />
      <ElTableColumn label="协议" width="110">
        <template #default="{ row }">
          <ElTag size="small">{{ protocolLabel(row.protocol) }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="Broker" min-width="160">
        <template #default="{ row }">
          <span>{{ row.broker }}:{{ row.port }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="topic" label="Topic" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="font-mono text-12px">{{ row.topic || '—' }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="模式" width="90">
        <template #default="{ row }">
          <ElTag size="small" :type="row.mode === 'standard' ? 'info' : ''">{{ modeLabel(row.mode) }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="interval" label="间隔(秒)" width="85" align="center" />
      <ElTableColumn label="运行状态" width="90">
        <template #default="{ row }">
          <ElTag v-if="row.running" :type="row.connected ? 'success' : 'warning'" size="small">
            {{ row.connected ? '正常' : '断开' }}
          </ElTag>
          <ElTag v-else type="info" size="small">停止</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="发布统计" width="130">
        <template #default="{ row }">
          <span class="text-green-500">{{ row.publish_count }}</span>
          <span class="text-gray-300 mx-4px">/</span>
          <ElTooltip v-if="row.publish_fail_count > 0" :content="`失败 ${row.publish_fail_count} 次`" placement="top">
            <span class="text-red-500 cursor-pointer">{{ row.publish_fail_count }}</span>
          </ElTooltip>
          <span v-else class="text-gray-400">0</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="最后发布" width="170">
        <template #default="{ row }">
          <ElTooltip v-if="row.last_error" :content="row.last_error" placement="top">
            <span class="text-red-500 text-12px">{{ formatTime(row.last_publish_time) }}</span>
          </ElTooltip>
          <span v-else class="text-12px">{{ formatTime(row.last_publish_time) }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <ElButton
            link
            type="primary"
            size="small"
            :loading="triggerBusy.has(row.device_id)"
            @click="handleTrigger(row.device_id)"
          >
            手动触发
          </ElButton>
        </template>
      </ElTableColumn>
    </ElTable>

    <ElEmpty v-if="!loading && !list.length" description="暂无启用MQTT发布的设备">
      <template #image>
        <div style="font-size: 48px; color: #c0c4cc;">📡</div>
      </template>
    </ElEmpty>
  </ContentWrap>
</template>
