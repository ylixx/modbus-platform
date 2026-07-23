<template>
  <div>
    <div class="page-header">
      <h2>历史数据</h2>
      <p>查看采集点位的历史趋势（支持多设备对比同一指标）</p>
    </div>

    <el-card style="margin-bottom: 16px">
      <el-row :gutter="16" align="middle" style="margin-bottom:12px">
        <el-col :span="8">
          <el-select
            v-model="selectedDevices"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择设备（可多选对比）"
            style="width:100%"
            @change="onDevicesChange"
          >
            <el-option-group v-for="g in deviceGroups" :key="g.label" :label="g.label">
              <el-option v-for="d in g.options" :key="d.id" :label="d.name" :value="d.id" />
            </el-option-group>
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select
            v-model="selectedMetricKey"
            filterable
            placeholder="选择对比指标（点位）"
            :disabled="!selectedDevices.length"
            style="width:100%"
            @change="fetchHistory"
          >
            <el-option v-for="m in metrics" :key="m.key" :label="`${m.name} (${m.unit || '-'})`" :value="m.key" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="interval" @change="fetchHistory" style="width:100%">
            <el-option label="原始数据" value="raw" />
            <el-option label="1分钟" value="1m" />
            <el-option label="5分钟" value="5m" />
            <el-option label="15分钟" value="15m" />
            <el-option label="1小时" value="1h" />
            <el-option label="1天" value="1d" />
          </el-select>
        </el-col>
        <el-col :span="8">
          <el-button type="primary" @click="fetchHistory" :loading="loading">
            <el-icon><Search /></el-icon> 查询
          </el-button>
          <el-button @click="exportData"><el-icon><Download /></el-icon> 导出</el-button>
        </el-col>
      </el-row>
      <el-row :gutter="16" align="middle">
        <el-col :span="12">
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
        <el-col :span="12" style="color:#888;font-size:12px;line-height:32px">
          已选 {{ selectedDevices.length }} 台设备 · 设备按厂级分组、可搜索；对比同一指标时各设备绘一条曲线。
        </el-col>
      </el-row>
    </el-card>

    <!-- Chart -->
    <el-card style="margin-bottom: 16px">
      <div ref="chartRef" style="height:420px"></div>
      <el-empty v-if="!chartSeries.length && !loading" description="请选择设备与对比指标查看历史数据" />
    </el-card>

    <!-- Data Table -->
    <el-card header="数据明细">
      <el-table :data="pagedRows" stripe size="small" max-height="420">
        <el-table-column prop="device" label="设备" width="170" fixed />
        <el-table-column prop="time" label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.time) }}</template>
        </el-table-column>
        <template v-if="interval === 'raw'">
          <el-table-column prop="value" label="值" width="120" />
          <el-table-column prop="quality" label="质量" width="100">
            <template #default="{ row }">
              <el-tag :type="row.quality === 'good' ? 'success' : 'danger'" size="small">{{ row.quality }}</el-tag>
            </template>
          </el-table-column>
        </template>
        <template v-else>
          <el-table-column prop="min" label="最小值" width="110" />
          <el-table-column prop="max" label="最大值" width="110" />
          <el-table-column prop="avg" label="平均值" width="110" />
          <el-table-column prop="count" label="采样数" width="100" />
        </template>
      </el-table>
      <el-pagination
        style="margin-top:12px"
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        :page-sizes="[10,20,30,50,100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="onSizeChange"
        @current-change="onPageChange"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '../../api/request'
import dayjs from 'dayjs'
import { useClientPagination } from '../../composables/useClientPagination'

const devices = ref([])
const selectedDevices = ref([])            // 多选设备
const metrics = ref([])                     // 当前选中设备集合下的指标（去重）
const deviceTagsMap = ref({})              // deviceId -> [tags]
const selectedMetricKey = ref(null)        // `${name}__${unit}`
const interval = ref('1m')
const timeRange = ref([])
const loading = ref(false)
const chartSeries = ref([])
const tableData = ref([])
const chartRef = ref(null)
let chart = null

const formatTime = (t) => t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '-'

// 设备按厂级分组（解决设备多时下拉难选）
const deviceGroups = computed(() => {
  const map = new Map()
  for (const d of devices.value) {
    const g = d.factory || '未分组'
    if (!map.has(g)) map.set(g, [])
    map.get(g).push(d)
  }
  return Array.from(map.entries()).map(([label, options]) => ({ label, options }))
})

const currentMetric = computed(() => metrics.value.find(m => m.key === selectedMetricKey.value) || null)

const { pageSize, currentPage, total, pagedRows, onSizeChange, onPageChange, resetPage } =
  useClientPagination(tableData, { defaultPageSize: 30 })

async function fetchDevices() {
  const res = await api.get('/devices/all')
  devices.value = res.data
}

async function onDevicesChange() {
  metrics.value = []
  selectedMetricKey.value = null
  deviceTagsMap.value = {}
  if (!selectedDevices.value.length) return
  // 并行拉取选中设备的点位（对比场景一般只选少量，请求数可控）
  const results = await Promise.all(
    selectedDevices.value.map(id =>
      api.get(`/devices/${id}/tags`).then(r => ({ id, tags: r.data })).catch(() => ({ id, tags: [] }))
    )
  )
  const map = {}
  const metricSet = new Map()
  for (const { id, tags } of results) {
    map[id] = tags
    for (const t of tags) {
      const key = `${t.name}__${t.unit || ''}`
      if (!metricSet.has(key)) metricSet.set(key, { key, name: t.name, unit: t.unit || '' })
    }
  }
  deviceTagsMap.value = map
  metrics.value = Array.from(metricSet.values())
}

async function fetchHistory() {
  if (!selectedDevices.value.length || !selectedMetricKey.value) return
  loading.value = true
  try {
    const mkParams = (deviceId, tagId) => {
      const p = { device_id: deviceId, tag_id: tagId, interval: interval.value }
      if (timeRange.value?.length === 2) {
        p.start_time = timeRange.value[0]
        p.end_time = timeRange.value[1]
      }
      return p
    }
    const tasks = []
    for (const devId of selectedDevices.value) {
      const tag = (deviceTagsMap.value[devId] || []).find(t => `${t.name}__${t.unit || ''}` === selectedMetricKey.value)
      if (!tag) continue
      tasks.push(
        api.get('/history', { params: mkParams(devId, tag.id) })
          .then(r => ({ devId, data: r.data.data || [] }))
          .catch(() => ({ devId, data: [] }))
      )
    }
    const results = await Promise.all(tasks)
    const nameOf = id => (devices.value.find(d => d.id === id) || {}).name || String(id)

    // 多设备多线对比（x 轴用时间类型，自动对齐）
    const series = results.map(({ devId, data }) => ({
      name: nameOf(devId),
      type: 'line',
      showSymbol: false,
      smooth: true,
      lineStyle: { width: 1.5 },
      data: data.map(d => [dayjs(d.time).valueOf(), interval.value === 'raw' ? d.value : d.avg]),
    }))
    chartSeries.value = series
    renderChart()

    // 明细：每行带设备列
    const rows = []
    for (const { devId, data } of results) {
      const dn = nameOf(devId)
      for (const d of data) {
        rows.push(interval.value === 'raw'
          ? { device: dn, time: d.time, value: d.value, quality: d.quality }
          : { device: dn, time: d.time, min: d.min, max: d.max, avg: d.avg, count: d.count })
      }
    }
    tableData.value = rows
    resetPage()
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { type: 'scroll', top: 0 },
    grid: { top: 40, left: 56, right: 24, bottom: 64 },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', name: currentMetric.value ? `${currentMetric.value.name} (${currentMetric.value.unit || ''})` : '' },
    series: chartSeries.value,
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
  }, true)
  chart.resize()
}

function exportData() {
  if (!tableData.value.length) return
  const headers = interval.value === 'raw'
    ? ['设备', '时间', '值', '质量']
    : ['设备', '时间', '最小值', '最大值', '平均值', '采样数']
  const rows = tableData.value.map(d =>
    interval.value === 'raw'
      ? [d.device, d.time, d.value, d.quality]
      : [d.device, d.time, d.min, d.max, d.avg, d.count]
  )
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `history_${dayjs().format('YYYYMMDD_HHmmss')}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  fetchDevices()
  window.addEventListener('resize', () => chart?.resize())
})
</script>
