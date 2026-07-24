<template>
  <div class="screen-container">
    <div class="screen-header">
      <h1>📊 数据监控大屏</h1>
      <div class="header-time">{{ currentTime }}</div>
    </div>

    <div class="screen-body">
      <!-- Top Stats Row -->
      <div class="stats-row">
        <div class="stat-box blue">
          <div class="stat-num">{{ stats.devices?.total || 0 }}</div>
          <div class="stat-label">设备总数</div>
        </div>
        <div class="stat-box green">
          <div class="stat-num">{{ stats.devices?.online || 0 }}</div>
          <div class="stat-label">在线</div>
        </div>
        <div class="stat-box red">
          <div class="stat-num">{{ stats.devices?.error || 0 }}</div>
          <div class="stat-label">异常</div>
        </div>
        <div class="stat-box orange">
          <div class="stat-num">{{ stats.alarms?.active || 0 }}</div>
          <div class="stat-label">活跃报警</div>
        </div>
        <div class="stat-box cyan">
          <div class="stat-num">{{ stats.tags?.total || 0 }}</div>
          <div class="stat-label">采集点位</div>
        </div>
        <div class="stat-box purple">
          <div class="stat-num">{{ wsStatus === 'connected' ? '● 已连接' : '○ 断开' }}</div>
          <div class="stat-label">实时通道</div>
        </div>
      </div>

      <!-- Main Charts Row -->
      <div class="charts-row">
        <div class="chart-box">
          <h3>设备状态分布</h3>
          <div ref="statusChartRef" class="chart-area"></div>
        </div>
        <div class="chart-box wide">
          <h3>报警趋势 (24h)</h3>
          <div ref="trendChartRef" class="chart-area"></div>
        </div>
        <div class="chart-box">
          <h3>报警等级分布</h3>
          <div ref="levelChartRef" class="chart-area"></div>
        </div>
      </div>

      <!-- Bottom Row -->
      <div class="bottom-row">
        <!-- Active Alarms -->
        <div class="bottom-box wide">
          <h3>🚨 活跃报警</h3>
          <div class="alarm-scroll">
            <div v-for="a in activeAlarms" :key="a.id" class="alarm-item" :class="a.alarm_level">
              <span class="alarm-level">{{ levelLabel(a.alarm_level) }}</span>
              <span class="alarm-msg">{{ a.alarm_message }}</span>
              <span class="alarm-time">{{ formatTime(a.triggered_at) }}</span>
            </div>
            <el-empty v-if="!activeAlarms.length" description="暂无活跃报警" :image-size="60" />
          </div>
        </div>

        <!-- Live Feed -->
        <div class="bottom-box">
          <h3>📡 实时数据流</h3>
          <div class="live-scroll">
            <div v-for="(item, idx) in liveFeed" :key="idx" class="live-item">
              <span class="live-name">{{ item.tag_name }}</span>
              <span class="live-value" :class="item.quality">{{ item.value }}</span>
              <span class="live-time">{{ item.time_str }}</span>
            </div>
            <div v-if="!liveFeed.length" style="color:#666;text-align:center;padding:20px">等待数据...</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'Screen' })
import { ref, onMounted, onUnmounted, computed } from 'vue'
import * as echarts from 'echarts'
import api from '../../api/request'
import dayjs from 'dayjs'

const stats = ref({})
const activeAlarms = ref([])
const liveFeed = ref([])
const currentTime = ref('')
const wsStatus = ref('disconnected')

const statusChartRef = ref(null)
const trendChartRef = ref(null)
const levelChartRef = ref(null)
let statusChart = null, trendChart = null, levelChart = null

const levelLabel = (l) => ({ info: '提示', warning: '警告', critical: '严重', emergency: '紧急' }[l] || l)
const formatTime = (t) => t ? dayjs(t).format('HH:mm:ss') : ''

// WebSocket
let ws = null
function connectWs() {
  const token = localStorage.getItem('token')
  if (!token) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${token}`)
  ws.onopen = () => { wsStatus.value = 'connected' }
  ws.onclose = () => {
    wsStatus.value = 'disconnected'
    setTimeout(connectWs, 3000)
  }
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'live_value') {
        const d = msg.data
        liveFeed.value.unshift({
          tag_name: d.tag_name,
          value: d.value,
          quality: d.quality,
          time_str: dayjs(d.time).format('HH:mm:ss'),
        })
        if (liveFeed.value.length > 100) liveFeed.value.pop()
      } else if (msg.type === 'alarm_triggered') {
        activeAlarms.value.unshift(msg.data)
      } else if (msg.type === 'alarm_cleared') {
        activeAlarms.value = activeAlarms.value.filter(a => a.id !== msg.data.id)
      }
    } catch {}
  }
}

async function fetchData() {
  try {
    const [sumRes, alarmRes, statusRes, trendRes, levelRes] = await Promise.all([
      api.get('/dashboard/summary'),
      api.get('/alarms/records/active'),
      api.get('/dashboard/device-status'),
      api.get('/dashboard/alarm-trend?days=1'),
      api.get('/alarms/stats'),
    ])
    stats.value = sumRes.data
    activeAlarms.value = (alarmRes.data || []).slice(0, 20)
    renderStatusChart(statusRes.data)
    renderTrendChart(trendRes.data)
    renderLevelChart(levelRes.data)
  } catch (e) { console.error(e) }
}

function renderStatusChart(data) {
  if (!statusChartRef.value) return
  if (!statusChart) statusChart = echarts.init(statusChartRef.value)
  const names = { online: '在线', offline: '离线', error: '异常', maintenance: '维护' }
  const colors = { online: '#52c41a', offline: '#555', error: '#f5222d', maintenance: '#faad14' }
  statusChart.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data: Object.entries(data).map(([k, v]) => ({
        name: names[k] || k, value: v, itemStyle: { color: colors[k] || '#1890ff' }
      })),
      label: { color: '#fff', fontSize: 12 },
    }],
  })
}

function renderTrendChart(data) {
  if (!trendChartRef.value) return
  if (!trendChart) trendChart = echarts.init(trendChartRef.value)
  const dates = Object.keys(data).sort()
  const levels = ['info', 'warning', 'critical', 'emergency']
  const colors = { info: '#909399', warning: '#e6a23c', critical: '#f56c6c', emergency: '#f5222d' }
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#aaa' } },
    xAxis: { type: 'category', data: dates.map(d => d.slice(5)), axisLabel: { color: '#aaa' } },
    yAxis: { type: 'value', axisLabel: { color: '#aaa' }, splitLine: { lineStyle: { color: '#333' } } },
    series: levels.map(level => ({
      name: levelLabel(level), type: 'bar', stack: 'total',
      data: dates.map(d => data[d]?.[level] || 0),
      itemStyle: { color: colors[level] },
    })),
  })
}

function renderLevelChart(data) {
  if (!levelChartRef.value) return
  if (!levelChart) levelChart = echarts.init(levelChartRef.value)
  const byLevel = data.by_level || {}
  const colors = { info: '#909399', warning: '#e6a23c', critical: '#f56c6c', emergency: '#f5222d' }
  levelChart.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: '70%',
      data: Object.entries(byLevel).map(([k, v]) => ({
        name: levelLabel(k), value: v, itemStyle: { color: colors[k] || '#1890ff' }
      })),
      label: { color: '#fff', fontSize: 12 },
    }],
  })
}

function updateTime() {
  currentTime.value = dayjs().format('YYYY-MM-DD HH:mm:ss')
}

let timeTimer = null, dataTimer = null
onMounted(() => {
  connectWs()
  fetchData()
  updateTime()
  timeTimer = setInterval(updateTime, 1000)
  dataTimer = setInterval(fetchData, 30000)
  window.addEventListener('resize', () => {
    statusChart?.resize(); trendChart?.resize(); levelChart?.resize()
  })
})
onUnmounted(() => {
  clearInterval(timeTimer); clearInterval(dataTimer)
  ws?.close()
  statusChart?.dispose(); trendChart?.dispose(); levelChart?.dispose()
})
</script>

<style scoped lang="scss">
.screen-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #0a1628 0%, #1a2a4a 100%);
  color: #fff;
  padding: 16px;
  overflow-y: auto;
}
.screen-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 0 16px;
  h1 { font-size: 24px; letter-spacing: 2px; }
  .header-time { font-size: 18px; color: #5b9dff; font-family: monospace; }
}
.stats-row {
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 16px;
}
.stat-box {
  background: rgba(255,255,255,0.06); border-radius: 8px; padding: 20px; text-align: center;
  border-left: 4px solid #1890ff;
  &.blue { border-color: #1890ff; }
  &.green { border-color: #52c41a; }
  &.red { border-color: #f5222d; }
  &.orange { border-color: #faad14; }
  &.cyan { border-color: #13c2c2; }
  &.purple { border-color: #722ed1; }
  .stat-num { font-size: 32px; font-weight: 700; }
  .stat-label { font-size: 13px; color: #aaa; margin-top: 4px; }
}
.charts-row {
  display: grid; grid-template-columns: 1fr 2fr 1fr; gap: 12px; margin-bottom: 16px;
}
.chart-box {
  background: rgba(255,255,255,0.04); border-radius: 8px; padding: 12px;
  h3 { font-size: 14px; color: #aaa; margin-bottom: 8px; }
  .chart-area { height: 260px; }
}
.bottom-row {
  display: grid; grid-template-columns: 2fr 1fr; gap: 12px;
}
.bottom-box {
  background: rgba(255,255,255,0.04); border-radius: 8px; padding: 12px;
  h3 { font-size: 14px; color: #aaa; margin-bottom: 8px; }
}
.alarm-scroll { max-height: 260px; overflow-y: auto; }
.alarm-item {
  display: flex; align-items: center; gap: 12px; padding: 8px 4px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  &.warning .alarm-level { color: #e6a23c; }
  &.critical .alarm-level { color: #f56c6c; }
  &.emergency .alarm-level { color: #f5222d; font-weight: bold; }
}
.alarm-level { width: 50px; font-size: 12px; }
.alarm-msg { flex: 1; font-size: 13px; }
.alarm-time { font-size: 12px; color: #666; font-family: monospace; }
.live-scroll { max-height: 260px; overflow-y: auto; }
.live-item {
  display: flex; justify-content: space-between; padding: 6px 4px;
  border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 13px;
  .live-name { flex: 1; }
  .live-value { width: 100px; text-align: right; font-weight: bold; color: #52c41a; &.bad { color: #f5222d; } }
  .live-time { width: 80px; text-align: right; color: #666; font-family: monospace; }
}
</style>
