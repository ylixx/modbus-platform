<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import { ElSelect, ElOption, ElTable, ElTableColumn, ElTag, ElSwitch, ElEmpty } from 'element-plus'
import { getAllDevices, getDeviceLive, unwrap, unwrapList } from '@/api/modbus'

defineOptions({ name: 'Realtime' })

const devices = ref<any[]>([])
const currentDevice = ref<number | undefined>(undefined)
const rows = ref<any[]>([])
const autoRefresh = ref(true)
const updatedAt = ref('')
let timer: any = null

const fetchDevices = async () => {
  devices.value = unwrapList(await getAllDevices()).list
  if (devices.value.length) {
    currentDevice.value = devices.value[0].id
    fetchLive()
  }
}
const fetchLive = async () => {
  if (currentDevice.value == null) return
  try {
    const res = await getDeviceLive(currentDevice.value)
    const body = unwrap(res)
    rows.value = Array.isArray(body) ? body : body?.tags || body?.data || []
    updatedAt.value = new Date().toLocaleTimeString()
  } catch (e) {
    // ignore
  }
}
const onDeviceChange = () => fetchLive()

const setupTimer = () => {
  if (timer) clearInterval(timer)
  if (autoRefresh.value) timer = setInterval(fetchLive, 3000)
}

onMounted(() => {
  fetchDevices()
  setupTimer()
})
onUnmounted(() => timer && clearInterval(timer))
</script>

<template>
  <ContentWrap title="实时数据">
    <template #header>
      <div class="flex-grow flex justify-end items-center">
        <span class="text-12px text-gray-400 mr-12px" v-if="updatedAt">更新于 {{ updatedAt }}</span>
        <span class="text-13px text-gray-500 mr-6px">自动刷新</span>
        <ElSwitch v-model="autoRefresh" class="mr-14px" @change="setupTimer" />
        <ElSelect v-model="currentDevice" class="!w-200px" @change="onDeviceChange">
          <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
        </ElSelect>
      </div>
    </template>

    <ElEmpty v-if="!rows.length" description="暂无实时数据" />
    <ElTable v-else :data="rows" border stripe>
      <ElTableColumn prop="name" label="点位名称" min-width="160" show-overflow-tooltip />
      <ElTableColumn prop="address" label="地址" width="90" />
      <ElTableColumn label="当前值" min-width="120">
        <template #default="{ row }">
          <span class="text-16px font-700 text-primary">{{ row.value ?? '—' }}</span>
          <span class="text-12px text-gray-400 ml-4px">{{ row.unit || '' }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="data_type" label="类型" width="110" />
      <ElTableColumn label="状态" width="100">
        <template #default="{ row }">
          <ElTag :type="row.quality === 'bad' || row.error ? 'danger' : 'success'">
            {{ row.quality === 'bad' || row.error ? '异常' : '正常' }}
          </ElTag>
        </template>
      </ElTableColumn>
    </ElTable>
  </ContentWrap>
</template>

<style scoped>
.text-primary {
  color: var(--el-color-primary);
}
</style>
