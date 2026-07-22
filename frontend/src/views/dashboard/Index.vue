<template>
  <div>
    <div class="page-header">
      <h2>仪表盘</h2>
      <p>系统运行状态概览</p>
    </div>

    <!-- Summary Cards -->
    <div class="card-grid">
      <div class="stat-card">
        <div class="stat-value">{{ summary.devices?.total || 0 }}</div>
        <div class="stat-label">设备总数</div>
      </div>
      <div class="stat-card success">
        <div class="stat-value">{{ summary.devices?.online || 0 }}</div>
        <div class="stat-label">在线设备</div>
      </div>
      <div class="stat-card danger">
        <div class="stat-value">{{ summary.devices?.error || 0 }}</div>
        <div class="stat-label">异常设备</div>
      </div>
      <div class="stat-card warning">
        <div class="stat-value">{{ summary.alarms?.active || 0 }}</div>
        <div class="stat-label">活跃报警</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ summary.tags?.total || 0 }}</div>
        <div class="stat-label">采集点位</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ summary.sms?.total || 0 }}</div>
        <div class="stat-label">短信发送</div>
      </div>
    </div>

    <!-- Charts Row -->
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card header="设备状态分布">
          <div ref="statusChartRef" style="height: 300px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="报警趋势 (近7天)">
          <div ref="alarmChartRef" style="height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Active Alarms -->
    <el-card header="最新活跃报警" style="margin-top: 20px">
      <el-table :data="activeAlarms" stripe size="small">
        <el-table-column prop="alarm_level" label="等级" width="100">
          <template #default="{ row }">
            <el-tag :type="levelTagType(row.alarm_level)" size="small">{{ levelLabel(row.alarm_level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="alarm_message" label="报警信息" />
        <el-table-column prop="trigger_value" label="触发值" width="100" />
        <el-table-column prop="triggered_at" label="触发时间" width="180">
          <template #default="{ row }">{{ formatTime(row.triggered_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import api from '../../api/request'
import dayjs from 'dayjs'

const summary = ref({})
const activeAlarms = ref([])
const statusChartRef = ref(null)
const alarmChartRef = ref(null)
let statusChart = null
let alarmChart = null

const levelMap = { info: '提示', warning: '警告', critical: '严重', emergency: '紧急' }
const levelLabel = (l) => levelMap[l] || l
const levelTagType = (l) => ({ info: 'info', warning: 'warning', critical: 'danger', emergency: 'danger' }[l] || 'info')
const formatTime = (t) => t ? dayjs(t).format('MM-DD HH:mm:ss') : '-'

async function fetchData() {
  try {
    const [sumRes, alarmRes, statusRes, trendRes] = await Promise.all([
      api.get('/dashboard/summary'),
      api.get('/alarms/records/active'),
      api.get('/dashboard/device-status'),
      api.get('/dashboard/alarm-trend'),
    ])
    summary.value = sumRes.data
    activeAlarms.value = (alarmRes.data || []).slice(0, 10)
    renderStatusChart(statusRes.data)
    renderAlarmChart(trendRes.data)
  } catch (e) {
    console.error(e)
  }
}

function renderStatusChart(data) {
  if (!statusChartRef.value) return
  if (!statusChart) statusChart = echarts.init(statusChartRef.value)
  const statusNames = { online: '在线', offline: '离线', error: '异常', maintenance: '维护' }
  const statusColors = { online: '#52c41a', offline: '#d9d9d9', error: '#f5222d', maintenance: '#faad14' }
  const chartData = Object.entries(data).map(([k, v]) => ({
    name: statusNames[k] || k, value: v, itemStyle: { color: statusColors[k] || '#1890ff' }
  }))
  statusChart.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data: chartData,
      label: { show: true, formatter: '{b}: {c}' },
    }],
  })
}

function renderAlarmChart(data) {
  if (!alarmChartRef.value) return
  if (!alarmChart) alarmChart = echarts.init(alarmChartRef.value)
  const dates = Object.keys(data).sort()
  const levels = ['info', 'warning', 'critical', 'emergency']
  const levelColors = { info: '#909399', warning: '#e6a23c', critical: '#f56c6c', emergency: '#f5222d' }
  const series = levels.map(level => ({
    name: levelMap[level],
    type: 'bar',
    stack: 'total',
    data: dates.map(d => data[d]?.[level] || 0),
    itemStyle: { color: levelColors[level] },
  }))
  alarmChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {},
    xAxis: { type: 'category', data: dates.map(d => d.slice(5)) },
    yAxis: { type: 'value' },
    series,
  })
}

let timer = null
onMounted(() => {
  fetchData()
  timer = setInterval(fetchData, 20000)
  window.addEventListener('resize', () => {
    statusChart?.resize()
    alarmChart?.resize()
  })
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
  statusChart?.dispose()
  alarmChart?.dispose()
})
</script>
