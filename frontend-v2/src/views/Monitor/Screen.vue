<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElRow, ElCol, ElEmpty, ElBadge } from 'element-plus'
import { getDashboardSummary, getAllDevices, unwrap, unwrapList } from '@/api/modbus'
import { useWsStore } from '@/store/modules/websocket'
import { wsManager } from '@/utils/websocket'

defineOptions({ name: 'Screen' })

const wsStore = useWsStore()

const summary = ref<any>({ devices: {}, tags: {}, alarms: {}, sms: {} })
const devices = ref<any[]>([])
const now = ref('')
let pollTimer: any = null
let unsubFns: (() => void)[] = []

const wsConnected = computed(() => wsStore.connected)
const recentAlarms = computed(() => wsStore.recentAlarms.slice(0, 10))

const statusColor = (s?: string) =>
  s === 'online' ? '#22d3ee' : s === 'error' ? '#f87171' : s === 'no-data' ? '#e6a23c' : '#64748b'

const fetchData = async () => {
  try {
    summary.value = unwrap(await getDashboardSummary()) || summary.value
  } catch (e) {
    // ignore
  }
  try {
    devices.value = unwrapList(await getAllDevices()).list
  } catch (e) {
    // ignore
  }
  now.value = new Date().toLocaleString()
}

onMounted(() => {
  fetchData()
  // 降级轮询 30s（WebSocket 推送为主）
  pollTimer = setInterval(fetchData, 30000)

  // WebSocket 设备状态变更时刷新
  unsubFns.push(wsManager.on('device_status', () => setTimeout(fetchData, 500)))
  unsubFns.push(wsManager.on('alarm_created', () => setTimeout(fetchData, 500)))
  // 更新时间
  const timeTimer = setInterval(() => { now.value = new Date().toLocaleString() }, 1000)
  unsubFns.push(() => clearInterval(timeTimer))
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  unsubFns.forEach((fn) => fn())
})
</script>

<template>
  <div class="screen">
    <div class="screen-header">
      <div class="screen-title">Modbus 工控数据监控大屏</div>
      <div class="flex items-center">
        <ElBadge :type="wsConnected ? 'success' : 'danger'" is-dot class="mr-12px">
          <span class="screen-time">{{ wsConnected ? '实时连接' : '离线模式' }}</span>
        </ElBadge>
        <div class="screen-time">{{ now }}</div>
      </div>
    </div>

    <ElRow :gutter="16" class="mb-16px">
      <ElCol :span="6">
        <div class="metric">
          <div class="metric-value" style="color: #22d3ee">{{ summary.devices?.total ?? 0 }}</div>
          <div class="metric-label">设备总数</div>
        </div>
      </ElCol>
      <ElCol :span="6">
        <div class="metric">
          <div class="metric-value" style="color: #4ade80">{{ summary.devices?.online ?? 0 }}</div>
          <div class="metric-label">在线设备</div>
        </div>
      </ElCol>
      <ElCol :span="6">
        <div class="metric">
          <div class="metric-value" style="color: #facc15">{{ summary.tags?.total ?? 0 }}</div>
          <div class="metric-label">采集点位</div>
        </div>
      </ElCol>
      <ElCol :span="6">
        <div class="metric">
          <div class="metric-value" style="color: #f87171">{{ summary.alarms?.active ?? 0 }}</div>
          <div class="metric-label">活动报警</div>
        </div>
      </ElCol>
    </ElRow>

    <ElRow :gutter="16">
      <ElCol :span="16">
        <div class="panel">
          <div class="panel-title">设备运行状态</div>
          <ElEmpty v-if="!devices.length" description="暂无设备" />
          <ElRow v-else :gutter="12">
            <ElCol v-for="d in devices" :key="d.id" :xs="12" :sm="8" :md="6" class="mb-12px">
              <div class="dev-card">
                <span class="dot" :style="{ background: statusColor(d.status) }"></span>
                <div class="dev-name">{{ d.name }}</div>
                <div class="dev-sub">{{ d.host || '—' }}</div>
              </div>
            </ElCol>
          </ElRow>
        </div>
      </ElCol>
      <ElCol :span="8">
        <div class="panel">
          <div class="panel-title">实时报警</div>
          <div v-if="!recentAlarms.length" class="text-gray-500 text-13px py-16px text-center">
            暂无报警
          </div>
          <div v-else class="alarm-scroll">
            <div v-for="a in recentAlarms" :key="a.id || a._time" class="alarm-item">
              <span
                class="alarm-dot"
                :style="{
                  background:
                    a.level === 'critical' || a.level === 'emergency'
                      ? '#f87171'
                      : a.level === 'warning'
                        ? '#facc15'
                        : '#38bdf8'
                }"
              ></span>
              <div class="alarm-text">
                <div class="alarm-msg">{{ a.message || a.tag_name || '报警' }}</div>
                <div class="alarm-dev">{{ a.device_name || '' }}</div>
              </div>
            </div>
          </div>
        </div>
      </ElCol>
    </ElRow>
  </div>
</template>

<style scoped>
.screen {
  min-height: calc(100vh - 140px);
  background: linear-gradient(180deg, #0b1e3a 0%, #071427 100%);
  border-radius: 8px;
  padding: 20px;
  color: #e2e8f0;
}
.screen-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  border-bottom: 1px solid rgba(56, 189, 248, 0.25);
  padding-bottom: 12px;
}
.screen-title {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #38bdf8;
}
.screen-time {
  font-size: 14px;
  color: #94a3b8;
}
.metric {
  background: rgba(30, 58, 95, 0.5);
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
}
.metric-value {
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
}
.metric-label {
  margin-top: 10px;
  font-size: 14px;
  color: #94a3b8;
}
.panel {
  background: rgba(30, 58, 95, 0.35);
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 8px;
  padding: 16px;
  height: 100%;
}
.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: #38bdf8;
  margin-bottom: 14px;
}
.dev-card {
  background: rgba(15, 39, 71, 0.6);
  border: 1px solid rgba(56, 189, 248, 0.15);
  border-radius: 6px;
  padding: 12px;
  position: relative;
}
.dot {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.dev-name {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 16px;
}
.dev-sub {
  font-size: 12px;
  color: #64748b;
  margin-top: 6px;
}
.alarm-scroll {
  max-height: 400px;
  overflow-y: auto;
}
.alarm-item {
  display: flex;
  align-items: flex-start;
  padding: 8px 0;
  border-bottom: 1px solid rgba(56, 189, 248, 0.1);
}
.alarm-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
  margin-right: 10px;
  flex-shrink: 0;
}
.alarm-text {
  flex: 1;
  min-width: 0;
}
.alarm-msg {
  font-size: 13px;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.alarm-dev {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}
</style>
