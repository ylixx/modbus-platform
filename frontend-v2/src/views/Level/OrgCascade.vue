<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import { ElTag, ElEmpty } from 'element-plus'
import OrgCascadeSelect from '@/components/OrgCascadeSelect.vue'
import { getOrgTreeApi, OrgNode, OrgDevice } from '@/api/hierarchy'

// 已选设备 ID（与下拉组件双向绑定）
const selectedIds = ref<number[]>([])
// id -> { device, path } 映射，用于下方详情展示
const deviceMap = ref<Record<number, { device: OrgDevice; path: string[] }>>({})

function buildMap(
  nodes: OrgNode[],
  prefix: string[],
  map: Record<number, { device: OrgDevice; path: string[] }>
) {
  for (const n of nodes) {
    const p = [...prefix, n.label]
    if (n.type === 'device' && n.device) {
      map[n.device.id] = { device: n.device, path: p }
    } else if (n.children) {
      buildMap(n.children, p, map)
    }
  }
}

const selectedDevices = computed(() =>
  selectedIds.value
    .map((id) => deviceMap.value[id])
    .filter((x): x is { device: OrgDevice; path: string[] } => !!x)
)

const protocolMap: Record<string, string> = {
  modbus_tcp: 'Modbus TCP',
  modbus_rtu: 'Modbus RTU',
  mqtt: 'MQTT',
  opc_ua: 'OPC-UA'
}
const protocolOf = (p?: string) => protocolMap[p || ''] || p || '—'

const statusMap: Record<
  string,
  { label: string; type: 'success' | 'info' | 'danger' | 'warning' }
> = {
  online: { label: '在线', type: 'success' },
  offline: { label: '离线', type: 'info' },
  error: { label: '异常', type: 'danger' },
  maintenance: { label: '维护', type: 'warning' }
}
const statusOf = (s?: string) => statusMap[s || ''] || { label: s || '未知', type: 'info' as const }

const connectionOf = (d: OrgDevice) => {
  if (d.protocol === 'modbus_tcp') return `${d.host}:${d.port} / #${d.slave_id}`
  if (d.protocol === 'modbus_rtu') return `${d.serial_port} / ${d.baudrate}bps`
  if (d.protocol === 'mqtt') return d.mqtt_broker || '—'
  if (d.protocol === 'opc_ua') return d.opc_endpoint || '—'
  return '—'
}

onMounted(async () => {
  const res = await getOrgTreeApi()
  const map: Record<number, { device: OrgDevice; path: string[] }> = {}
  buildMap(res.data.tree, [], map)
  deviceMap.value = map
})
</script>

<template>
  <ContentWrap title="组织架构 · 关联下拉列表" :body-style="{ padding: '16px' }">
    <!-- 紧凑的级联下拉框：厂区/班/站/位置 + 设备名称(多选) + 搜索 -->
    <OrgCascadeSelect v-model="selectedIds" class="mb-12px" />

    <!-- 已选设备详情 -->
    <div class="detail-wrap">
      <div class="detail-head">已选设备（{{ selectedDevices.length }}）</div>
      <template v-if="selectedDevices.length">
        <div v-for="item in selectedDevices" :key="item.device.id" class="dev-card">
          <div class="dev-title">
            <span class="dot" :class="item.device.status" />
            {{ item.device.name }}
            <ElTag :type="statusOf(item.device.status).type" size="small">
              {{ statusOf(item.device.status).label }}
            </ElTag>
            <ElTag type="primary" size="small" effect="plain">{{
              protocolOf(item.device.protocol)
            }}</ElTag>
          </div>
          <div class="dev-meta">
            <span>层级：{{ item.path.slice(0, -1).join(' / ') || '—' }}</span>
            <span>连接：{{ connectionOf(item.device) }}</span>
          </div>
        </div>
      </template>
      <ElEmpty v-else description="请在上方下拉框中选择设备（可多选）" :image-size="60" />
    </div>
  </ContentWrap>
</template>

<style scoped>
.detail-wrap {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--el-fill-color-blank);
}
.detail-head {
  font-weight: 600;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color);
}
.dev-card {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  margin-bottom: 8px;
  background: var(--el-fill-color-light);
}
.dev-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}
.dev-meta {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}
.dot.online {
  background: #67c23a;
}
.dot.offline {
  background: #909399;
}
.dot.error {
  background: #f56c6c;
}
.dot.maintenance {
  background: #e6a23c;
}
</style>
