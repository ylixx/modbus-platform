<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import { ElEmpty } from 'element-plus'
import { getAllDevices, unwrapList } from '@/api/modbus'

defineOptions({ name: 'Topology' })

const router = useRouter()
const devices = ref<any[]>([])
let timer: any = null

const statusColor = (s?: string) =>
  s === 'online' ? '#67c23a' : s === 'error' ? '#f56c6c' : '#909399'

const fetchData = async () => {
  devices.value = unwrapList(await getAllDevices()).list
}

onMounted(() => {
  fetchData()
  timer = setInterval(fetchData, 8000)
})
onUnmounted(() => timer && clearInterval(timer))
</script>

<template>
  <ContentWrap title="设备拓扑" message="以采集网关为中心展示设备连接拓扑">
    <ElEmpty v-if="!devices.length" description="暂无设备" />
    <div v-else class="topo">
      <div class="center-node">
        <div class="node-icon">GW</div>
        <div class="node-label">采集网关</div>
      </div>
      <div class="nodes">
        <div
          v-for="d in devices"
          :key="d.id"
          class="node"
          @click="router.push(`/device/detail/${d.id}`)"
        >
          <span class="node-dot" :style="{ background: statusColor(d.status) }"></span>
          <div class="node-name">{{ d.name }}</div>
          <div class="node-host">{{ d.host || '—' }}</div>
        </div>
      </div>
    </div>
  </ContentWrap>
</template>

<style scoped>
.topo {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 0;
}
.center-node {
  text-align: center;
  margin-bottom: 30px;
}
.node-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
}
.node-label {
  margin-top: 8px;
  font-size: 14px;
  color: var(--el-text-color-regular);
}
.nodes {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  justify-content: center;
}
.node {
  width: 150px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 14px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  background: var(--el-bg-color);
}
.node:hover {
  border-color: var(--el-color-primary);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.node-dot {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.node-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.node-host {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 6px;
}
</style>
