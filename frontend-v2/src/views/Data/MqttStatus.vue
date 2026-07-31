<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import { ElTable, ElTableColumn, ElTag, ElButton, ElEmpty } from 'element-plus'
import { getMqttHealth, unwrap } from '@/api/modbus'

defineOptions({ name: 'MqttStatus' })

const list = ref<any[]>([])
const loading = ref(false)
let timer: any = null

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getMqttHealth()
    list.value = unwrap(res) || []
  } catch {
    // silent
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchList()
  timer = setInterval(fetchList, 10000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <ContentWrap title="MQTT连接状态">
    <ElTable v-loading="loading" :data="list" border stripe>
      <ElTableColumn prop="broker" label="Broker" min-width="180" />
      <ElTableColumn prop="port" label="端口" width="80" />
      <ElTableColumn prop="username" label="用户名" min-width="120" show-overflow-tooltip />
      <ElTableColumn label="连接状态" width="100">
        <template #default="{ row }">
          <ElTag :type="row.connected ? 'success' : 'danger'" size="small">
            {{ row.connected ? '已连接' : '断开' }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="ref_count" label="引用数" width="80" />
      <ElTableColumn prop="publish_count" label="发布数" width="100" />
      <ElTableColumn prop="publish_fail_count" label="发布失败" width="100">
        <template #default="{ row }">
          <ElTag v-if="row.publish_fail_count > 0" type="danger" size="small">{{ row.publish_fail_count }}</ElTag>
          <span v-else class="text-gray-400">0</span>
        </template>
      </ElTableColumn>
    </ElTable>

    <ElEmpty v-if="!loading && !list.length" description="暂无活跃的MQTT连接" />
    <div class="text-12px text-gray-400 mt-8px">每10秒自动刷新</div>
  </ContentWrap>
</template>
