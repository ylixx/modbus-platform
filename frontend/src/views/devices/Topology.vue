<template>
  <div>
    <div class="page-header">
      <h2>设备拓扑图</h2>
      <p>自定义层级结构，灵活组织设备视图</p>
    </div>

    <!-- Toolbar -->
    <el-card style="margin-bottom: 16px">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-select v-model="selectedConfigId" placeholder="选择层级方案" @change="fetchTree">
            <el-option v-for="c in configs" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-switch v-model="showOffline" active-text="显示离线" @change="fetchTree" />
        </el-col>
        <el-col :span="4">
          <el-radio-group v-model="viewMode" size="small" @change="onViewChange">
            <el-radio-button label="topology">拓扑</el-radio-button>
            <el-radio-button label="map">地图</el-radio-button>
          </el-radio-group>
        </el-col>
        <el-col :span="10" style="text-align:right">
          <el-button @click="showConfigDialog = true"><el-icon><Setting /></el-icon> 配置层级</el-button>
          <el-button @click="showNewConfigDialog"><el-icon><Plus /></el-icon> 新建方案</el-button>
          <el-button @click="fetchTree"><el-icon><Refresh /></el-icon> 刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16">
      <!-- Tree View -->
      <el-col :span="8">
        <el-card style="max-height:650px;overflow-y:auto">
          <template #header>
            <span>{{ currentConfig?.name || '拓扑树' }}</span>
            <el-tag size="small" style="margin-left:8px" v-if="currentConfig">
              {{ currentConfig.levels?.map(l => l.label).join(' → ') }}
            </el-tag>
          </template>
          <el-tree
            v-if="treeData.length"
            :data="treeData"
            :props="{ label: 'label', children: 'children' }"
            default-expand-all
            highlight-current
            @node-click="onNodeClick"
          >
            <template #default="{ node, data }">
              <span class="tree-node">
                <span>{{ data.icon || '📁' }}</span>
                <span>{{ node.label }}</span>
                <el-tag v-if="data.type === 'device'" :type="statusType(data.device?.status)" size="small" style="margin-left:8px">
                  {{ statusLabel(data.device?.status) }}
                </el-tag>
              </span>
            </template>
          </el-tree>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>

      <!-- Detail / Chart / Map -->
      <el-col :span="16">
        <!-- 地图视图：地图常驻，选中设备时详情显示在上方 -->
        <template v-if="viewMode === 'map'">
          <el-card v-if="selectedDevice" :header="`设备: ${selectedDevice.name}`" style="margin-bottom:16px">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="协议">{{ protoLabel(selectedDevice.protocol) }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <span class="status-dot" :class="selectedDevice.status"></span>{{ statusLabel(selectedDevice.status) }}
              </el-descriptions-item>
              <el-descriptions-item label="厂级">{{ selectedDevice.factory || '-' }}</el-descriptions-item>
              <el-descriptions-item label="区级">{{ selectedDevice.workshop || '-' }}</el-descriptions-item>
              <el-descriptions-item label="班级">{{ selectedDevice.production_line || '-' }}</el-descriptions-item>
              <el-descriptions-item label="安装位置">{{ selectedDevice.installation || '-' }}</el-descriptions-item>
              <el-descriptions-item label="经纬度">
                {{ selectedDevice.longitude != null ? selectedDevice.longitude : '-' }} ,
                {{ selectedDevice.latitude != null ? selectedDevice.latitude : '-' }}
              </el-descriptions-item>
            </el-descriptions>
            <el-button size="small" style="margin-top:12px" @click="$router.push(`/devices/${selectedDevice.id}`)">查看详情</el-button>
            <el-button size="small" style="margin-top:12px" @click="selectedDevice = null">取消选择</el-button>
          </el-card>

          <!-- 聚合标注卡片 -->
          <el-card v-else-if="selectedAgg" :header="`${aggLabel}：${selectedAgg.name}`" style="margin-bottom:16px">
            <el-descriptions :column="3" border size="small">
              <el-descriptions-item label="设备总数">{{ selectedAgg.count }}</el-descriptions-item>
              <el-descriptions-item label="在线"><span class="status-dot online"></span>{{ selectedAgg.online }}</el-descriptions-item>
              <el-descriptions-item label="离线/异常"><span class="status-dot offline"></span>{{ selectedAgg.offline }}</el-descriptions-item>
            </el-descriptions>
            <el-divider content-position="left">成员设备（点击地图标点也可查看）</el-divider>
            <el-table :data="selectedAgg.members" size="small" max-height="260" stripe>
              <el-table-column prop="name" label="名称" width="140" />
              <el-table-column label="状态" width="90">
                <template #default="{ row }"><el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag></template>
              </el-table-column>
              <el-table-column prop="factory" label="厂级" />
              <el-table-column prop="workshop" label="区级" />
            </el-table>
            <el-button size="small" style="margin-top:12px" @click="selectedAgg = null">取消选择</el-button>
          </el-card>

          <el-card>
            <template #header>
              <div style="display:flex;justify-content:space-between;align-items:center;width:100%">
                <span>设备分布地图（按经纬度标注）</span>
                <el-radio-group v-model="aggMode" size="small" @change="onAggChange">
                  <el-radio-button label="none">按设备</el-radio-button>
                  <el-radio-button label="factory">按厂级</el-radio-button>
                  <el-radio-button label="workshop">按区级</el-radio-button>
                </el-radio-group>
              </div>
            </template>
            <div ref="mapChartRef" style="height:550px"></div>
            <div style="margin-top:8px;color:#888;font-size:12px">
              已标注位置设备：{{ mapDevices.length }} / {{ allDevices.length }}
              <span v-if="aggMode !== 'none'">　|　聚合分组：{{ aggGroups.length }}</span>
              <span v-if="mapDevices.length === 0">（在「设备」页面填写 经度 / 纬度 后，即可在此地图显示）</span>
            </div>
          </el-card>
        </template>

        <!-- 拓扑视图：原逻辑 -->
        <template v-else>
          <el-card v-if="selectedDevice" :header="`设备: ${selectedDevice.name}`">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="协议">{{ protoLabel(selectedDevice.protocol) }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <span class="status-dot" :class="selectedDevice.status"></span>{{ statusLabel(selectedDevice.status) }}
              </el-descriptions-item>
              <el-descriptions-item label="厂级">{{ selectedDevice.factory || '-' }}</el-descriptions-item>
              <el-descriptions-item label="区级">{{ selectedDevice.workshop || '-' }}</el-descriptions-item>
              <el-descriptions-item label="班级">{{ selectedDevice.production_line || '-' }}</el-descriptions-item>
              <el-descriptions-item label="安装位置">{{ selectedDevice.installation || '-' }}</el-descriptions-item>
            </el-descriptions>
            <el-button size="small" style="margin-top:12px" @click="$router.push(`/devices/${selectedDevice.id}`)">查看详情</el-button>
          </el-card>

          <!-- Topology Chart when no device selected -->
          <el-card v-else header="拓扑总览">
            <div ref="topologyChartRef" style="height:550px"></div>
          </el-card>
        </template>
      </el-col>
    </el-row>

    <!-- Config Dialog -->
    <el-dialog v-model="showConfigDialog" title="层级方案管理" width="800px">
      <div v-if="configs.length">
        <el-table :data="configs" stripe size="small">
          <el-table-column prop="name" label="方案名称" width="120" />
          <el-table-column prop="description" label="描述" width="160" />
          <el-table-column label="层级结构">
            <template #default="{ row }">
              <el-tag v-for="l in row.levels" :key="l.key" size="small" style="margin:2px">
                {{ l.icon }} {{ l.label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="is_default" label="默认" width="70">
            <template #default="{ row }">
              <el-tag v-if="row.is_default" type="success" size="small">默认</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" @click="editConfig(row)">编辑</el-button>
              <el-button size="small" @click="setDefault(row)" v-if="!row.is_default">设为默认</el-button>
              <el-button size="small" type="danger" @click="deleteConfig(row)" v-if="!row.is_default">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-empty v-else description="暂无方案" />
    </el-dialog>

    <!-- Edit Config Dialog -->
    <el-dialog v-model="showEditDialog" :title="editingConfigId ? '编辑层级方案' : '新建层级方案'" width="700px">
      <el-form :model="configForm" label-width="80px">
        <el-form-item label="方案名称" required><el-input v-model="configForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="configForm.description" /></el-form-item>
        <el-form-item label="设为默认"><el-switch v-model="configForm.is_default" /></el-form-item>

        <el-divider content-position="left">层级定义（从上到下）</el-divider>
        <div v-for="(level, idx) in configForm.levels" :key="idx" style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <el-input v-model="level.icon" style="width:50px" placeholder="图标" />
          <el-input v-model="level.label" style="width:100px" placeholder="显示名" />
          <el-select v-model="level.field" style="width:160px" placeholder="映射字段">
            <el-option v-for="f in availableFields" :key="f.field" :label="f.label" :value="f.field" />
          </el-select>
          <el-input v-model="level.key" style="width:120px" placeholder="唯一key" />
          <el-button type="danger" :icon="Delete" circle size="small" @click="configForm.levels.splice(idx, 1)" />
          <el-button :icon="Top" circle size="small" v-if="idx > 0" @click="moveLevel(idx, -1)" />
          <el-button :icon="Bottom" circle size="small" v-if="idx < configForm.levels.length - 1" @click="moveLevel(idx, 1)" />
        </div>
        <el-button @click="addLevel" style="margin-top:8px"><el-icon><Plus /></el-icon> 添加层级</el-button>

        <el-divider content-position="left">可用字段</el-divider>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item v-for="f in availableFields" :key="f.field" :label="f.label">
            <code>{{ f.field }}</code> <span style="color:#999">({{ f.type }})</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Top, Bottom } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import chinaJson from '../../assets/china.json'
import api from '../../api/request'

// 国内地图（离线）：本地内置中国 GeoJSON，无需任何外部 API / 网络 / Key
echarts.registerMap('china', chinaJson)

const configs = ref([])
const currentConfig = ref(null)
const selectedConfigId = ref(null)
const treeData = ref([])
const selectedDevice = ref(null)
const showOffline = ref(true)
const showConfigDialog = ref(false)
const showEditDialog = ref(false)
const editingConfigId = ref(null)
const availableFields = ref([])
const topologyChartRef = ref(null)
let topoChart = null

// 地图视图（离线中国地图）
const viewMode = ref('topology')          // 'topology' | 'map'
const allDevices = ref([])
const mapDevices = computed(() => allDevices.value.filter(d => d.longitude != null && d.latitude != null))
const mapChartRef = ref(null)
let mapChart = null
const aggMode = ref('none')                 // 'none' | 'factory' | 'workshop'
const selectedAgg = ref(null)
const aggLabel = computed(() => aggMode.value === 'factory' ? '厂级' : aggMode.value === 'workshop' ? '区级' : '')
// 按厂级/区级聚合：取同组已标注设备的经纬度质心作为标点，附数量与在线/离线统计
const aggGroups = computed(() => {
  if (aggMode.value === 'none') return []
  const key = aggMode.value
  const groups = new Map()
  for (const d of mapDevices.value) {
    const g = (d[key] && String(d[key]).trim()) || '未分组'
    if (!groups.has(g)) groups.set(g, [])
    groups.get(g).push(d)
  }
  const out = []
  for (const [name, members] of groups.entries()) {
    const lats = members.map(m => m.latitude).filter(v => v != null)
    const lngs = members.map(m => m.longitude).filter(v => v != null)
    const clat = lats.length ? lats.reduce((a, b) => a + b, 0) / lats.length : 0
    const clng = lngs.length ? lngs.reduce((a, b) => a + b, 0) / lngs.length : 0
    out.push({
      name, value: [clng, clat], field: key, isAgg: true,
      count: members.length,
      online: members.filter(m => m.status === 'online').length,
      offline: members.filter(m => m.status !== 'online').length,
      members: members.map(m => m.id),
    })
  }
  return out.sort((a, b) => b.count - a.count)
})

const configForm = reactive({ name: '', description: '', is_default: false, levels: [] })

const statusLabel = (s) => ({ online: '在线', offline: '离线', error: '异常', maintenance: '维护' }[s] || s)
const statusType = (s) => ({ online: 'success', offline: 'info', error: 'danger', maintenance: 'warning' }[s] || 'info')
const protoLabel = (p) => ({ modbus_tcp: 'Modbus TCP', mqtt: 'MQTT', opc_ua: 'OPC-UA' }[p] || p)

async function fetchConfigs() {
  const res = await api.get('/hierarchy/configs')
  configs.value = res.data
  if (!selectedConfigId.value) {
    const def = res.data.find(c => c.is_default) || res.data[0]
    if (def) { selectedConfigId.value = def.id; currentConfig.value = def }
  }
}

async function fetchFields() {
  const res = await api.get('/hierarchy/fields')
  availableFields.value = res.data
}

async function fetchTree() {
  if (!selectedConfigId.value) return
  try {
    const res = await api.get('/hierarchy/tree', { params: { config_id: selectedConfigId.value } })
    currentConfig.value = res.data.config
    let data = res.data.tree || []
    if (!showOffline.value) {
      data = filterOffline(data)
    }
    treeData.value = data
    selectedDevice.value = null
    nextTick(renderTopologyChart)
  } catch (e) { console.error(e) }
}

function filterOffline(nodes) {
  return nodes.filter(n => {
    if (n.type === 'device') return n.device?.status !== 'offline'
    if (n.children) n.children = filterOffline(n.children)
    return true
  }).filter(n => n.type !== 'level' || (n.children && n.children.length > 0))
}

function onNodeClick(data) {
  if (data.type === 'device') {
    selectedDevice.value = data.device
  } else {
    selectedDevice.value = null
  }
}

// ── 地图数据（设备经纬度） ──
async function fetchDevices() {
  try {
    const res = await api.get('/devices/all')
    allDevices.value = res.data || []
  } catch (e) { console.error(e) }
}

function renderMap() {
  if (!mapChartRef.value) return
  if (!mapChart) {
    mapChart = echarts.init(mapChartRef.value)
    mapChart.on('click', onMapClick)
  }
  const isAgg = aggMode.value !== 'none'
  const data = isAgg
    ? aggGroups.value.map(g => ({
        name: g.name, value: g.value, isAgg: true,
        count: g.count, online: g.online, offline: g.offline, members: g.members,
      }))
    : mapDevices.value.map(d => ({
        name: d.name, value: [d.longitude, d.latitude], id: d.id, status: d.status,
      }))
  mapChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        if (!p.data) return ''
        if (p.data.isAgg) return `${p.data.name}<br/>设备数：${p.data.count}<br/>在线：${p.data.online}　离线：${p.data.offline}`
        return `${p.data.name}<br/>经度：${p.data.value[0]}<br/>纬度：${p.data.value[1]}`
      },
    },
    geo: {
      map: 'china', roam: true,
      label: { show: false },
      itemStyle: { areaColor: '#1f2d3d', borderColor: '#0a3d5c' },
      emphasis: { itemStyle: { areaColor: '#2a4d69' }, label: { show: false } },
    },
    series: [{
      name: isAgg ? '聚合分组' : '设备',
      type: 'scatter',
      coordinateSystem: 'geo',
      data,
      symbolSize: (val, params) => isAgg ? (12 + Math.min((params.data.count || 1) * 2, 26)) : 12,
      itemStyle: { color: isAgg ? '#1890ff' : '#ff4d4f', borderColor: '#fff', borderWidth: 1 },
      label: {
        show: true,
        formatter: (p) => isAgg ? `${p.data.name}(${p.data.count})` : p.data.name,
        position: 'right', color: '#cde', fontSize: 10,
      },
      emphasis: { scale: isAgg ? 1.2 : 1.4 },
    }],
  }, true)
}

function onMapClick(params) {
  if (params.data?.isAgg) {
    const grp = aggGroups.value.find(g => g.name === params.data.name)
    if (grp) {
      selectedAgg.value = {
        name: grp.name, count: grp.count, online: grp.online, offline: grp.offline,
        field: grp.field,
        members: allDevices.value.filter(d => grp.members.includes(d.id)),
      }
      selectedDevice.value = null
    }
    return
  }
  if (params.data?.id) {
    const dev = allDevices.value.find(d => d.id === params.data.id)
    if (dev) { selectedDevice.value = dev; selectedAgg.value = null }
  }
}

function onAggChange() {
  selectedAgg.value = null
  selectedDevice.value = null
  nextTick(renderMap)
}

function onViewChange(val) {
  if (val === 'map') {
    fetchDevices()
    selectedAgg.value = null
    nextTick(renderMap)
  } else {
    nextTick(renderTopologyChart)
  }
}

function onResize() {
  topologyChart?.resize()
  mapChart?.resize()
}

function renderTopologyChart() {
  if (!topologyChartRef.value) return
  if (!topoChart) topoChart = echarts.init(topologyChartRef.value)
  const statusColors = { online: '#52c41a', offline: '#555', error: '#f5222d', maintenance: '#faad14' }
  const nodes = []
  const links = []
  nodes.push({ name: '平台', symbolSize: 50, itemStyle: { color: '#1890ff' }, label: { show: true } })

  function walk(items, parentName) {
    for (const item of items) {
      const id = item.type === 'device' ? `d_${item.device?.id}` : `n_${item.label}`
      const color = item.type === 'device' ? (statusColors[item.device?.status] || '#1890ff') : '#722ed1'
      const size = item.type === 'device' ? 20 : 30
      nodes.push({ name: id, symbolSize: size, itemStyle: { color }, label: { show: true, formatter: item.label?.split(' (')[0], fontSize: 10 } })
      links.push({ source: parentName, target: id })
      if (item.children) walk(item.children, id)
    }
  }
  walk(treeData.value, '平台')

  topoChart.setOption({
    tooltip: {},
    series: [{
      type: 'graph', layout: 'force', data: nodes, links,
      roam: true, draggable: true,
      force: { repulsion: 200, gravity: 0.1, edgeLength: 80 },
      lineStyle: { color: '#444', curveness: 0 },
      emphasis: { focus: 'adjacency' },
    }],
  })
}

// Config CRUD
function showNewConfigDialog() {
  editingConfigId.value = null
  Object.assign(configForm, {
    name: '', description: '', is_default: false,
    levels: [
      { key: 'factory', label: '厂级', field: 'factory', icon: '🏭' },
      { key: 'workshop', label: '区级', field: 'workshop', icon: '🏢' },
      { key: 'production_line', label: '班级', field: 'production_line', icon: '🔧' },
      { key: 'device', label: '设备', field: '_device', icon: '📡' },
    ],
  })
  showEditDialog.value = true
}

function editConfig(cfg) {
  editingConfigId.value = cfg.id
  Object.assign(configForm, {
    name: cfg.name, description: cfg.description, is_default: cfg.is_default,
    levels: cfg.levels.map(l => ({ ...l })),
  })
  showEditDialog.value = true
}

function addLevel() {
  configForm.levels.splice(configForm.levels.length - 1, 0, {
    key: `level_${Date.now()}`, label: '', field: '', icon: '📁',
  })
}

function moveLevel(idx, dir) {
  const arr = configForm.levels
  const target = idx + dir
  if (target < 0 || target >= arr.length) return
  ;[arr[idx], arr[target]] = [arr[target], arr[idx]]
}

async function saveConfig() {
  if (!configForm.name) { ElMessage.warning('请输入方案名称'); return }
  if (!configForm.levels.length) { ElMessage.warning('至少添加一个层级'); return }

  if (editingConfigId.value) {
    await api.put(`/hierarchy/configs/${editingConfigId.value}`, configForm)
  } else {
    await api.post('/hierarchy/configs', configForm)
  }
  ElMessage.success('保存成功')
  showEditDialog.value = false
  fetchConfigs()
  fetchTree()
}

async function setDefault(cfg) {
  await api.put(`/hierarchy/configs/${cfg.id}`, { is_default: true })
  ElMessage.success('已设为默认')
  fetchConfigs()
}

async function deleteConfig(cfg) {
  await ElMessageBox.confirm(`确定删除方案 "${cfg.name}"？`)
  await api.delete(`/hierarchy/configs/${cfg.id}`)
  ElMessage.success('已删除')
  fetchConfigs()
}

onMounted(() => {
  fetchConfigs()
  fetchFields()
  fetchTree()
  fetchDevices()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => { topoChart?.dispose(); mapChart?.dispose() })
</script>

<style scoped>
.tree-node { display: flex; align-items: center; gap: 6px; font-size: 14px; }
</style>
