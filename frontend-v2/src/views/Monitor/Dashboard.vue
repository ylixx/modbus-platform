<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import { ElRow, ElCol, ElCard, ElTag, ElEmpty, ElBadge } from 'element-plus'
import { Icon } from '@/components/Icon'
import { getDashboardSummary, getAlarmTrend, unwrap } from '@/api/modbus'
import { useWsStore } from '@/store/modules/websocket'
import { wsManager } from '@/utils/websocket'

defineOptions({ name: 'Dashboard' })

const wsStore = useWsStore()

const summary = ref<any>({
  devices: { total: 0, online: 0, offline: 0, error: 0 },
  tags: { total: 0 },
  alarms: { active: 0, acknowledged: 0 },
  sms: { total: 0, failed: 0 }
})
const trend = ref<any>({})
const lastUpdate = ref('')
let pollTimer: any = null
let unsubFns: (() => void)[] = []

const cards = computed(() => {
  const s = summary.value
  return [
    {
      label: '设备总数',
      value: s.devices?.total ?? 0,
      icon: 'vi-ant-design:hdd-outlined',
      color: '#409eff',
      sub: `在线 ${s.devices?.online ?? 0} / 离线 ${s.devices?.offline ?? 0}`
    },
    {
      label: '采集点位',
      value: s.tags?.total ?? 0,
      icon: 'vi-ant-design:api-outlined',
      color: '#67c23a',
      sub: '监测中的寄存器点位'
    },
    {
      label: '活动报警',
      value: s.alarms?.active ?? 0,
      icon: 'vi-ant-design:alert-outlined',
      color: '#f56c6c',
      sub: `已确认 ${s.alarms?.acknowledged ?? 0}`
    },
    {
      label: '短信发送',
      value: s.sms?.total ?? 0,
      icon: 'vi-ant-design:message-outlined',
      color: '#e6a23c',
      sub: `失败 ${s.sms?.failed ?? 0}`
    }
  ]
})

const wsConnected = computed(() => wsStore.connected)

// HTTP 轮询刷新（兜底，低频）
const fetchData = async () => {
  try {
    const res = await getDashboardSummary()
    summary.value = unwrap(res) || summary.value
    lastUpdate.value = new Date().toLocaleTimeString()
  } catch (e) {
    // ignore
  }
  try {
    const res2 = await getAlarmTrend()
    trend.value = unwrap(res2) || {}
  } catch (e) {
    // ignore
  }
}

// WebSocket 实时更新：设备状态变更时刷新 summary
const onDeviceStatus = () => {
  // 设备状态变更，延迟 500ms 刷新 summary（等后端统计更新）
  setTimeout(fetchData, 500)
}

// WebSocket 实时更新：报警事件时刷新 summary
const onAlarmEvent = () => {
  setTimeout(fetchData, 500)
}

onMounted(() => {
  fetchData()
  // 降级轮询：30s 刷新一次（WebSocket 推送为主，轮询为兜底）
  pollTimer = setInterval(fetchData, 30000)

  // 监听 WebSocket 事件
  unsubFns.push(wsManager.on('device_status', onDeviceStatus))
  unsubFns.push(wsManager.on('alarm_created', onAlarmEvent))
  unsubFns.push(wsManager.on('alarm_acknowledged', onAlarmEvent))
  unsubFns.push(wsManager.on('alarm_cleared', onAlarmEvent))
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  unsubFns.forEach((fn) => fn())
})
</script>

<template>
  <div>
    <!-- WebSocket 连接状态指示 -->
    <div class="flex items-center justify-end mb-8px">
      <ElBadge :type="wsConnected ? 'success' : 'danger'" is-dot class="mr-6px">
        <span class="text-12px text-gray-400">
          {{ wsConnected ? '实时连接' : '离线（轮询模式）' }}
        </span>
      </ElBadge>
      <span v-if="lastUpdate" class="text-12px text-gray-400 ml-12px">
        更新于 {{ lastUpdate }}
      </span>
    </div>

    <ElRow :gutter="16">
      <ElCol v-for="c in cards" :key="c.label" :xs="24" :sm="12" :md="6" class="mb-16px">
        <ElCard shadow="hover" class="h-full">
          <div class="flex items-center">
            <div
              class="w-56px h-56px rounded-8px flex items-center justify-center mr-14px"
              :style="{ background: c.color + '1a' }"
            >
              <Icon :icon="c.icon" :size="28" :color="c.color" />
            </div>
            <div>
              <div class="text-28px font-700 leading-none">{{ c.value }}</div>
              <div class="text-14px text-gray-500 mt-6px">{{ c.label }}</div>
            </div>
          </div>
          <div class="text-12px text-gray-400 mt-12px">{{ c.sub }}</div>
        </ElCard>
      </ElCol>
    </ElRow>

    <ElRow :gutter="16">
      <ElCol :xs="24" :md="12" class="mb-16px">
        <ContentWrap title="设备状态分布">
          <div class="flex flex-wrap gap-16px py-8px">
            <ElTag type="success" size="large">在线 {{ summary.devices?.online ?? 0 }}</ElTag>
            <ElTag type="info" size="large">离线 {{ summary.devices?.offline ?? 0 }}</ElTag>
            <ElTag type="danger" size="large">异常 {{ summary.devices?.error ?? 0 }}</ElTag>
            <ElTag size="large">总计 {{ summary.devices?.total ?? 0 }}</ElTag>
          </div>
        </ContentWrap>
      </ElCol>
      <ElCol :xs="24" :md="12" class="mb-16px">
        <ContentWrap title="报警趋势">
          <ElEmpty
            v-if="!trend || !Object.keys(trend).length"
            description="暂无报警趋势数据"
            :image-size="80"
          />
          <div v-else class="py-8px">
            <div
              v-for="(v, k) in trend"
              :key="k"
              class="flex justify-between py-4px border-b border-gray-100"
            >
              <span class="text-gray-500">{{ k }}</span>
              <span class="font-600">{{ v }}</span>
            </div>
          </div>
        </ContentWrap>
      </ElCol>
    </ElRow>
  </div>
</template>
