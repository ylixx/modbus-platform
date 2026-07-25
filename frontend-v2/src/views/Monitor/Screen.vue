<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElRow, ElCol, ElEmpty } from 'element-plus'
import { getDashboardSummary, getAllDevices, unwrap, unwrapList } from '@/api/modbus'

defineOptions({ name: 'Screen' })

const summary = ref<any>({ devices: {}, tags: {}, alarms: {}, sms: {} })
const devices = ref<any[]>([])
const now = ref('')
let timer: any = null

const statusColor = (s?: string) =>
  s === 'online' ? '#22d3ee' : s === 'error' ? '#f87171' : '#64748b'

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
  timer = setInterval(fetchData, 5000)
})
onUnmounted(() => timer && clearInterval(timer))
</script>

<template>
  <div class="screen">
    <div class="screen-header">
      <div class="screen-title">Modbus 工控数据监控大屏</div>
      <div class="screen-time">{{ now }}</div>
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
</style>
