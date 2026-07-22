<template>
  <div>
    <div class="page-header">
      <h2>实时数据</h2>
      <p>所有设备采集点位实时值，WebSocket 自动刷新</p>
    </div>

    <!-- Filters -->
    <el-card style="margin-bottom: 16px">
      <el-row :gutter="12" align="middle">
        <el-col :span="4">
          <el-select v-model="filterDevice" placeholder="设备" clearable filterable @change="fetchAll">
            <el-option v-for="d in allDevices" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="filterFactory" placeholder="厂区" clearable @change="fetchAll">
            <el-option v-for="f in locations.factories" :key="f" :label="f" :value="f" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="filterWorkshop" placeholder="车间" clearable @change="fetchAll">
            <el-option v-for="w in locations.workshops" :key="w" :label="w" :value="w" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="filterProtocol" placeholder="协议" clearable @change="fetchAll">
            <el-option label="Modbus TCP" value="modbus_tcp" />
            <el-option label="MQTT" value="mqtt" />
            <el-option label="OPC-UA" value="opc_ua" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="filterStatus" placeholder="设备状态" clearable @change="fetchAll">
            <el-option label="在线" value="online" />
            <el-option label="离线" value="offline" />
            <el-option label="异常" value="error" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-input v-model="searchTag" placeholder="搜索点位名称" clearable prefix-icon="Search" @input="applyLocalFilter" />
        </el-col>
        <el-col :span="4" style="text-align:right">
          <el-tag :type="wsConnected ? 'success' : 'info'" size="small">
            {{ wsConnected ? '● 实时连接' : '○ 离线' }}
          </el-tag>
          <el-button size="small" style="margin-left:8px" @click="fetchAll"><el-icon><Refresh /></el-icon></el-button>
          <el-dropdown trigger="click" style="margin-left:4px">
            <el-button size="small"><el-icon><Download /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="exportCSV"><el-icon><Document /></el-icon> 导出 CSV</el-dropdown-item>
                <el-dropdown-item @click="exportJSON"><el-icon><Tickets /></el-icon> 导出 JSON</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </el-col>
      </el-row>
    </el-card>

    <!-- Summary -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6">
        <div class="mini-stat"><span class="num">{{ totalTags }}</span><span class="lbl">总点位</span></div>
      </el-col>
      <el-col :span="6">
        <div class="mini-stat green"><span class="num">{{ goodCount }}</span><span class="lbl">数据正常</span></div>
      </el-col>
      <el-col :span="6">
        <div class="mini-stat orange"><span class="num">{{ staleCount }}</span><span class="lbl">数据过期</span></div>
      </el-col>
      <el-col :span="6">
        <div class="mini-stat red"><span class="num">{{ offlineCount }}</span><span class="lbl">设备离线</span></div>
      </el-col>
    </el-row>

    <!-- Data Table -->
    <el-card>
      <el-table
        :data="filteredRows"
        stripe
        size="small"
        :row-class-name="rowClassName"
        :default-sort="{ prop: 'device_name', order: 'ascending' }"
        max-height="calc(100vh - 340px)"
      >
        <el-table-column prop="device_name" label="设备" width="160" fixed sortable>
          <template #default="{ row }">
            <span class="status-dot" :class="row.device_status"></span>
            <span style="font-weight:500">{{ row.device_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="protocol" label="协议" width="100" sortable>
          <template #default="{ row }">
            <el-tag :type="protoType(row.protocol)" size="small">{{ protoLabel(row.protocol) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="位置" width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.location || '-' }}</template>
        </el-table-column>
        <el-table-column prop="tag_name" label="点位名称" width="160" fixed sortable />
        <el-table-column prop="unit" label="单位" width="70" />
        <el-table-column prop="value" label="当前值" width="120" sortable :sort-method="sortByValue">
          <template #default="{ row }">
            <span class="value-cell" :class="valueClass(row)">
              {{ formatValue(row.value) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="quality" label="质量" width="80">
          <template #default="{ row }">
            <el-tag :type="row.quality === 'good' ? 'success' : 'danger'" size="small">{{ row.quality }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="time" label="更新时间" width="170" sortable>
          <template #default="{ row }">
            <span :class="{ 'stale': isStale(row.time) }">{{ formatTime(row.time) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="趋势" width="100">
          <template #default="{ row }">
            <el-button size="small" text @click="viewHistory(row)">
              <el-icon><TrendCharts /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../../api/request'
import dayjs from 'dayjs'

const router = useRouter()

// Data
const allDevices = ref([])
const allTags = ref([])       // [{device, tag}]
const liveValues = ref(/** @type {Record<string, {value: number, quality: string, time: string}>} */ ({}))
const locations = ref({ factories: /** @type {string[]} */ ([]), workshops: /** @type {string[]} */ ([]) })
const wsConnected = ref(false)
const tableLoading = ref(false)

// Filters
const filterDevice = ref(null)
const filterFactory = ref(null)
const filterWorkshop = ref(null)
const filterProtocol = ref(null)
const filterStatus = ref(null)
const searchTag = ref('')

// Build rows
const allRows = computed(() => {
  return allTags.value.map(({ device, tag }) => {
    const key = `${device.id}_${tag.id}`
    const live = liveValues.value[key]
    return {
      device_id: device.id,
      device_name: device.name,
      device_status: device.status,
      protocol: device.protocol,
      location: [device.factory, device.workshop, device.production_line].filter(Boolean).join('/') || '',
      tag_id: tag.id,
      tag_name: tag.name,
      unit: tag.unit || '',
      value: live?.value ?? null,
      quality: live?.quality ?? 'unknown',
      time: live?.time ?? null,
    }
  })
})

const filteredRows = computed(() => {
  let rows = allRows.value
  if (filterDevice.value) rows = rows.filter(r => r.device_id === filterDevice.value)
  if (filterFactory.value) rows = rows.filter(r => r.device_status !== 'offline' || true).filter(r => {
    const dev = allDevices.value.find(d => d.id === r.device_id)
    return dev?.factory === filterFactory.value
  })
  if (filterWorkshop.value) rows = rows.filter(r => {
    const dev = allDevices.value.find(d => d.id === r.device_id)
    return dev?.workshop === filterWorkshop.value
  })
  if (filterProtocol.value) rows = rows.filter(r => r.protocol === filterProtocol.value)
  if (filterStatus.value) rows = rows.filter(r => r.device_status === filterStatus.value)
  if (searchTag.value) {
    const q = searchTag.value.toLowerCase()
    rows = rows.filter(r => r.tag_name.toLowerCase().includes(q) || r.device_name.toLowerCase().includes(q))
  }
  return rows
})

// Stats
const totalTags = computed(() => filteredRows.value.length)
const goodCount = computed(() => filteredRows.value.filter(r => r.quality === 'good' && !isStale(r.time)).length)
const staleCount = computed(() => filteredRows.value.filter(r => r.quality === 'good' && isStale(r.time)).length)
const offlineCount = computed(() => filteredRows.value.filter(r => r.device_status === 'offline' || r.quality !== 'good').length)

// Helpers
const protoLabel = (p) => ({ modbus_tcp: 'Modbus', mqtt: 'MQTT', opc_ua: 'OPC-UA' }[p] || p)
const protoType = (p) => ({ modbus_tcp: '', mqtt: 'success', opc_ua: 'warning' }[p] || 'info')
const formatTime = (t) => t ? dayjs(t).format('HH:mm:ss') : '-'
const formatValue = (v) => v === null || v === undefined ? '--' : typeof v === 'number' ? v.toFixed(2) : String(v)
const sortByValue = (a, b) => (a.value ?? -Infinity) - (b.value ?? -Infinity)

function isStale(time) {
  if (!time) return true
  return dayjs().diff(dayjs(time), 'second') > 30
}

function valueClass(row) {
  if (row.quality !== 'good') return 'bad'
  if (isStale(row.time)) return 'stale'
  return 'ok'
}

function rowClassName({ row }) {
  if (row.device_status === 'offline') return 'row-offline'
  if (row.quality !== 'good') return 'row-bad'
  return ''
}

function applyLocalFilter() { /* computed handles it */ }

function viewHistory(row) {
  router.push(`/history?device=${row.device_id}&tag=${row.tag_id}`)
}

function exportCSV() {
  const rows = filteredRows.value
  if (!rows.length) return
  const headers = ['设备', '协议', '位置', '点位名称', '当前值', '单位', '质量', '更新时间']
  const csvRows = rows.map(r => [
    r.device_name, protoLabel(r.protocol), r.location, r.tag_name,
    formatValue(r.value), r.unit, r.quality, formatTime(r.time),
  ])
  const csv = [headers, ...csvRows].map(row => row.map(c => `"${String(c).replace(/"/g, '""') }"`).join(',')).join('\n')
  download(csv, `realtime_${dayjs().format('YYYYMMDD_HHmmss')}.csv`, 'text/csv;charset=utf-8;')
}

function exportJSON() {
  const rows = filteredRows.value.map(r => ({
    device: r.device_name, protocol: protoLabel(r.protocol), location: r.location,
    tag: r.tag_name, value: r.value, unit: r.unit, quality: r.quality, time: r.time,
  }))
  download(JSON.stringify(rows, null, 2), `realtime_${dayjs().format('YYYYMMDD_HHmmss')}.json`, 'application/json')
}

function download(content, filename, type) {
  const blob = new Blob(['\ufeff' + content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

// Fetch
async function fetchAll() {
  tableLoading.value = true
  const [devRes, locRes] = await Promise.all([
    api.get('/devices/all'),
    api.get('/devices/locations'),
  ])
  allDevices.value = devRes.data
  locations.value = locRes.data

  // Fetch tags for all devices
  const tagList = []
  for (const d of allDevices.value) {
    try {
      const res = await api.get(`/devices/${d.id}/tags`)
      for (const t of res.data) {
        tagList.push({ device: d, tag: t })
      }
    } catch {}
  }
  allTags.value = tagList
  tableLoading.value = false

  // Fetch live values
  for (const d of allDevices.value) {
    try {
      const res = await api.get(`/devices/${d.id}/live`)
      const values = res.data.values || {}
      for (const [tagId, val] of Object.entries(values)) {
        liveValues.value[`${d.id}_${tagId}`] = val
      }
    } catch {}
  }
}

// WebSocket
let ws = null
function connectWs() {
  const token = localStorage.getItem('token')
  if (!token) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${token}`)
  ws.onopen = () => { wsConnected.value = true }
  ws.onclose = () => {
    wsConnected.value = false
    setTimeout(connectWs, 3000)
  }
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'live_value') {
        const d = msg.data
        const key = `${d.device_id}_${d.tag_id}`
        liveValues.value[key] = {
          value: d.value,
          quality: d.quality,
          time: d.time,
        }
      } else if (msg.type === 'device_status') {
        const dev = allDevices.value.find(d => d.id === msg.data.device_id)
        if (dev) dev.status = msg.data.status
      }
    } catch {}
  }
}

let refreshTimer = null
onMounted(() => {
  fetchAll()
  connectWs()
  refreshTimer = setInterval(fetchAll, 60000)  // full refresh every 60s
})
onUnmounted(() => {
  ws?.close()
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.mini-stat {
  background: #fff; border-radius: 8px; padding: 16px; text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  .num { display: block; font-size: 28px; font-weight: 700; color: #1890ff; }
  .lbl { font-size: 13px; color: #888; }
  &.green .num { color: #52c41a; }
  &.orange .num { color: #faad14; }
  &.red .num { color: #f5222d; }
}
.value-cell {
  font-weight: 700; font-family: monospace; font-size: 15px;
  &.ok { color: #52c41a; }
  &.stale { color: #faad14; }
  &.bad { color: #f5222d; }
}
.stale { color: #999; }
:deep(.row-offline) { opacity: 0.5; }
:deep(.row-bad .value-cell) { color: #f5222d; }
</style>
