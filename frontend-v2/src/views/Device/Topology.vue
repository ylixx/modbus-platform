<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import { ElEmpty, ElTag } from 'element-plus'
import { getAllDevices, unwrapList } from '@/api/modbus'
import { deviceStatusType, deviceStatusText } from '@/utils/modbus'

defineOptions({ name: 'Topology' })

const router = useRouter()
const devices = ref<any[]>([])
const loading = ref(false)
const filter = ref<'all' | 'online' | 'offline' | 'error' | 'no-data'>('all')
let timer: any = null

// ── 状态相关 ──
// statusText / deviceStatusType 已从 @/utils/modbus 导入
const statusTagType = deviceStatusType
const statusText = deviceStatusText
const statusClass = (s?: string) =>
  s === 'online' ? 'online' : s === 'error' ? 'error' : s === 'no-data' ? 'no-data' : 'offline'

const protoLabel = (p?: string) =>
  p === 'modbus_tcp' ? 'Modbus TCP' : p === 'modbus_rtu' ? 'Modbus RTU' : p === 'mqtt' ? 'MQTT' : p === 'opc_ua' ? 'OPC-UA' : p || '—'

const filteredDevices = computed(() =>
  filter.value === 'all' ? devices.value : devices.value.filter((d) => statusClass(d.status) === filter.value)
)

const onlineCount = computed(() => devices.value.filter((d) => d.status === 'online').length)
const noDataCount = computed(() => devices.value.filter((d) => d.status === 'no-data').length)
const offlineCount = computed(() => devices.value.filter((d) => d.status === 'offline' || d.status === 'maintenance').length)
const errorCount = computed(() => devices.value.filter((d) => d.status === 'error').length)

// ── SVG 拓扑连线 ──
const containerRef = ref<HTMLElement | null>(null)
const gatewayRef = ref<HTMLElement | null>(null)
const links = ref<{ d: string }[]>([])

const updateLinks = () => {
  nextTick(() => {
    const container = containerRef.value
    const gw = gatewayRef.value
    if (!container || !gw) return
    const cRect = container.getBoundingClientRect()
    const gRect = gw.getBoundingClientRect()
    const gx = gRect.left + gRect.width / 2 - cRect.left
    const gy = gRect.bottom - cRect.top
    const nodes = container.querySelectorAll('.topo-node')
    const arr: { d: string }[] = []
    nodes.forEach((n) => {
      const r = (n as HTMLElement).getBoundingClientRect()
      const nx = r.left + r.width / 2 - cRect.left
      const ny = r.top - cRect.top
      const midY = (gy + ny) / 2
      arr.push({ d: `M ${gx} ${gy} C ${gx} ${midY}, ${nx} ${midY}, ${nx} ${ny}` })
    })
    links.value = arr
  })
}

const openDetail = (d: any) => router.push(`/device/detail/${d.id}`)

const fetchData = async () => {
  loading.value = true
  try {
    devices.value = unwrapList(await getAllDevices()).list
  } catch (e) {
    // 忽略单次刷新失败，保留上次数据
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
  timer = setInterval(fetchData, 8000)
  window.addEventListener('resize', updateLinks)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
  window.removeEventListener('resize', updateLinks)
})

watch([devices, filter], updateLinks, { flush: 'post' })
</script>

<template>
  <ContentWrap title="设备拓扑" message="以采集网关为中心展示设备连接拓扑与实时状态，点击设备可穿透查看详情">
    <!-- 状态统计 + 筛选 -->
    <div class="topo-bar">
      <div class="stats">
        <span class="stat"><i class="dot online"></i>在线 <b>{{ onlineCount }}</b></span>
        <span class="stat"><i class="dot no-data"></i>在线无数据 <b>{{ noDataCount }}</b></span>
        <span class="stat"><i class="dot offline"></i>离线 <b>{{ offlineCount }}</b></span>
        <span class="stat"><i class="dot error"></i>异常 <b>{{ errorCount }}</b></span>
      </div>
      <div class="filters">
        <button :class="['fbtn', { active: filter === 'all' }]" @click="filter = 'all'">全部</button>
        <button :class="['fbtn', { active: filter === 'online' }]" @click="filter = 'online'">在线</button>
        <button :class="['fbtn', { active: filter === 'no-data' }]" @click="filter = 'no-data'">在线无数据</button>
        <button :class="['fbtn', { active: filter === 'offline' }]" @click="filter = 'offline'">离线</button>
        <button :class="['fbtn', { active: filter === 'error' }]" @click="filter = 'error'">异常</button>
      </div>
    </div>

    <ElEmpty v-if="!filteredDevices.length" :description="devices.length ? '当前筛选无设备' : '暂无设备'" />

    <div v-else ref="containerRef" v-loading="loading" class="topo-canvas">
      <svg class="links">
        <path v-for="(l, i) in links" :key="i" :d="l.d" />
      </svg>

      <!-- 中心采集网关 -->
      <div ref="gatewayRef" class="gateway">
        <div class="gw-icon">GW</div>
        <div class="gw-label">采集网关</div>
      </div>

      <!-- 设备节点 -->
      <div class="nodes">
        <div
          v-for="d in filteredDevices"
          :key="d.id"
          class="topo-node"
          :class="statusClass(d.status)"
          @click="openDetail(d)"
        >
          <span class="node-dot" :class="statusClass(d.status)"></span>
          <div class="node-name" :title="d.name">{{ d.name }}</div>
          <div class="node-meta">
            <ElTag :type="statusTagType(d.status)" size="small">{{ statusText(d.status) }}</ElTag>
            <span class="proto">{{ protoLabel(d.protocol) }}</span>
          </div>
          <div class="node-host" :title="d.host">{{ d.host || '—' }}</div>
          <div class="node-org" :title="d.org_path">{{ d.org_path || '未分组' }}</div>
          <div class="node-go">查看详情 ›</div>
        </div>
      </div>
    </div>
  </ContentWrap>
</template>

<style scoped>
.topo-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.stats {
  display: flex;
  gap: 18px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.stat b {
  margin-left: 2px;
  font-size: 15px;
}
.dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
}
.dot.online { background: #67c23a; }
.dot.no-data { background: #e6a23c; }
.dot.offline { background: #909399; }
.dot.error { background: #f56c6c; }

.filters {
  display: flex;
  gap: 6px;
}
.fbtn {
  border: 1px solid var(--el-border-color);
  background: var(--el-bg-color);
  color: var(--el-text-color-regular);
  padding: 5px 14px;
  border-radius: 14px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.fbtn:hover { border-color: var(--el-color-primary); }
.fbtn.active {
  background: var(--el-color-primary);
  border-color: var(--el-color-primary);
  color: #fff;
}

.topo-canvas {
  position: relative;
  padding: 24px 0 8px;
  min-height: 320px;
}
.links {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}
.links path {
  fill: none;
  stroke: var(--el-border-color);
  stroke-width: 1.5;
  stroke-dasharray: 4 4;
}

.gateway {
  position: relative;
  z-index: 1;
  text-align: center;
  margin: 0 auto 36px;
}
.gw-icon {
  width: 68px;
  height: 68px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  font-weight: 700;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  box-shadow: 0 4px 14px rgba(64, 158, 255, 0.45);
}
.gw-label {
  margin-top: 8px;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.nodes {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  justify-content: center;
}
.topo-node {
  width: 168px;
  border: 1px solid var(--el-border-color);
  border-radius: 10px;
  padding: 14px 14px 10px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  background: var(--el-bg-color);
}
.topo-node:hover {
  border-color: var(--el-color-primary);
  transform: translateY(-3px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
}
.topo-node.offline { opacity: 0.78; }
.topo-node.error { border-color: #f56c6c; }

.node-dot {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.node-dot.online { background: #67c23a; }
.node-dot.no-data { background: #e6a23c; }
.node-dot.offline { background: #909399; }
.node-dot.error { background: #f56c6c; }

.node-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 0 12px;
}
.node-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 8px;
}
.proto {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.node-host {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.node-org {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  opacity: 0.85;
}
.node-go {
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-color-primary);
  opacity: 0;
  transition: opacity 0.2s;
}
.topo-node:hover .node-go { opacity: 1; }
</style>
