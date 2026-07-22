<template>
  <div>
    <div class="page-header">
      <h2>历史数据</h2>
      <p>查看采集点位的历史趋势</p>
    </div>

    <el-card style="margin-bottom: 16px">
      <el-row :gutter="16" align="middle">
        <el-col :span="4">
          <el-select v-model="selectedDevice" placeholder="选择设备" @change="onDeviceChange">
            <el-option v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="selectedTag" placeholder="选择点位" @change="fetchHistory">
            <el-option v-for="t in tags" :key="t.id" :label="`${t.name} (${t.unit || '-'})`" :value="t.id" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="interval" @change="fetchHistory">
            <el-option label="原始数据" value="raw" />
            <el-option label="1分钟" value="1m" />
            <el-option label="5分钟" value="5m" />
            <el-option label="15分钟" value="15m" />
            <el-option label="1小时" value="1h" />
            <el-option label="1天" value="1d" />
          </el-select>
        </el-col>
        <el-col :span="8">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
            @change="fetchHistory"
          />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="fetchHistory" :loading="loading">
            <el-icon><Search /></el-icon> 查询
          </el-button>
          <el-button @click="exportData"><el-icon><Download /></el-icon> 导出</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- Chart -->
    <el-card style="margin-bottom: 16px">
      <div ref="chartRef" style="height: 400px"></div>
      <el-empty v-if="!chartData.length && !loading" description="请选择设备和点位查看历史数据" />
    </el-card>

    <!-- Data Table -->
    <el-card header="数据明细">
      <el-table :data="tableData" stripe size="small" max-height="400">
        <el-table-column prop="time" label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.time) }}</template>
        </el-table-column>
        <el-table-column v-if="interval === 'raw'" prop="value" label="值" width="120" />
        <el-table-column v-if="interval === 'raw'" prop="quality" label="质量" width="100">
          <template #default="{ row }">
            <el-tag :type="row.quality === 'good' ? 'success' : 'danger'" size="small">{{ row.quality }}</el-tag>
          </template>
        </el-table-column>
        <template v-if="interval !== 'raw'">
          <el-table-column prop="min" label="最小值" width="120" />
          <el-table-column prop="max" label="最大值" width="120" />
          <el-table-column prop="avg" label="平均值" width="120" />
          <el-table-column prop="count" label="采样数" width="100" />
        </template>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '../../api/request'
import dayjs from 'dayjs'

const devices = ref([])
const tags = ref([])
const selectedDevice = ref(null)
const selectedTag = ref(null)
const interval = ref('1m')
const timeRange = ref([])
const loading = ref(false)
const chartData = ref([])
const tableData = ref([])
const chartRef = ref(null)
let chart = null

const formatTime = (t) => t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '-'

async function fetchDevices() {
  const res = await api.get('/devices/all')
  devices.value = res.data
}

async function onDeviceChange() {
  selectedTag.value = null
  if (selectedDevice.value) {
    const res = await api.get(`/devices/${selectedDevice.value}/tags`)
    tags.value = res.data
  } else {
    tags.value = []
  }
}

async function fetchHistory() {
  if (!selectedDevice.value || !selectedTag.value) return
  loading.value = true
  try {
    const params = {
      device_id: selectedDevice.value,
      tag_id: selectedTag.value,
      interval: interval.value,
    }
    if (timeRange.value?.length === 2) {
      params.start_time = timeRange.value[0]
      params.end_time = timeRange.value[1]
    }
    const res = await api.get('/history', { params })
    const data = res.data.data || []
    tableData.value = data

    // Build chart
    if (interval.value === 'raw') {
      chartData.value = data.map(d => [d.time, d.value])
      renderChart('raw')
    } else {
      chartData.value = data.map(d => [d.time, d.min, d.max, d.avg])
      renderChart('aggregated')
    }
  } finally {
    loading.value = false
  }
}

function renderChart(type) {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)

  const tag = tags.value.find(t => t.id === selectedTag.value)
  const tagLabel = tag ? `${tag.name} (${tag.unit || ''})` : ''

  if (type === 'raw') {
    chart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: chartData.value.map(d => dayjs(d[0]).format('HH:mm:ss')) },
      yAxis: { type: 'value', name: tagLabel },
      series: [{
        type: 'line', data: chartData.value.map(d => d[1]),
        smooth: true, lineStyle: { width: 2 }, areaStyle: { opacity: 0.1 },
      }],
      dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    })
  } else {
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['最小值', '最大值', '平均值'] },
      xAxis: { type: 'category', data: chartData.value.map(d => dayjs(d[0]).format('MM-DD HH:mm')) },
      yAxis: { type: 'value', name: tagLabel },
      series: [
        { name: '最小值', type: 'line', data: chartData.value.map(d => d[1]), lineStyle: { type: 'dashed' } },
        { name: '最大值', type: 'line', data: chartData.value.map(d => d[2]), lineStyle: { type: 'dashed' } },
        { name: '平均值', type: 'line', data: chartData.value.map(d => d[3]), smooth: true, areaStyle: { opacity: 0.1 } },
      ],
      dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    })
  }
  chart.resize()
}

function exportData() {
  if (!tableData.value.length) return
  const headers = interval.value === 'raw'
    ? ['时间', '值', '质量']
    : ['时间', '最小值', '最大值', '平均值', '采样数']
  const rows = tableData.value.map(d =>
    interval.value === 'raw'
      ? [d.time, d.value, d.quality]
      : [d.time, d.min, d.max, d.avg, d.count]
  )
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `history_${selectedDevice.value}_${selectedTag.value}_${dayjs().format('YYYYMMDD_HHmmss')}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  fetchDevices()
  window.addEventListener('resize', () => chart?.resize())
})
</script>
