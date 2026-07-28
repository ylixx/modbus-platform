<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElSelect,
  ElOption,
  ElPagination,
  ElMessage,
  ElNotification,
  ElBadge,
  ElMessageBox
} from 'element-plus'
import { getAlarmRecords, ackAlarm, clearAlarm, unwrapList } from '@/api/modbus'
import { formatTime } from '@/utils/modbus'
import { useWsStore } from '@/store/modules/websocket'
import { wsManager } from '@/utils/websocket'

defineOptions({ name: 'Alarms' })

const wsStore = useWsStore()
const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, status: '' })
let unsubFns: (() => void)[] = []

const wsConnected = computed(() => wsStore.connected)
const unreadAlarms = computed(() => wsStore.unreadAlarms)

const levelType = (l?: string) => {
  if (l === 'critical' || l === 'high' || l === 'emergency') return 'danger'
  if (l === 'warning' || l === 'medium') return 'warning'
  return 'info'
}
const statusType = (s?: string) => {
  if (s === 'active') return 'danger'
  if (s === 'acknowledged') return 'warning'
  return 'success'
}
const statusText = (s?: string) =>
  ({ active: '活动', acknowledged: '已确认', cleared: '已清除' })[s || ''] || s || '—'

const levelLabel = (l?: string) =>
  ({ info: '提示', warning: '警告', critical: '严重', emergency: '紧急' })[l || ''] || l || '—'

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getAlarmRecords({
      page: query.page,
      page_size: query.page_size,
      status: query.status || undefined
    })
    const { list: l, total: t } = unwrapList(res)
    list.value = l
    total.value = t
  } catch (e: any) {
    ElMessage.error(e?.message || '获取报警记录失败')
  } finally {
    loading.value = false
  }
}
const doAck = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认该报警？', '报警确认', { type: 'warning' })
    await ackAlarm(row.id)
    ElMessage.success('已确认')
    fetchList()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '操作失败')
    }
  }
}
const doClear = async (row: any) => {
  try {
    await ElMessageBox.confirm('清除该报警？', '报警清除', { type: 'warning' })
    await clearAlarm(row.id)
    ElMessage.success('已清除')
    fetchList()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '操作失败')
    }
  }
}

// WebSocket 实时报警通知
const onAlarmCreated = (msg: any) => {
  const alarm = msg.data
  if (!alarm) return

  // 弹窗通知
  const level = alarm.level || 'info'
  ElNotification({
    title: '新报警',
    message: `${alarm.device_name || '设备'} - ${alarm.tag_name || ''}: ${alarm.message || ''}`,
    type: level === 'critical' || level === 'emergency' ? 'error' : level === 'warning' ? 'warning' : 'info',
    duration: level === 'emergency' ? 0 : 5000 // 紧急报警不自动关闭
  })

  // 如果当前在第一页且无状态筛选，自动刷新列表
  if (query.page === 1 && !query.status) {
    fetchList()
  }
}

const clearUnread = () => {
  wsStore.clearUnreadAlarms()
}

onMounted(() => {
  fetchList()

  // 监听 WebSocket 报警事件
  unsubFns.push(wsManager.on('alarm_created', onAlarmCreated))
  unsubFns.push(wsManager.on('alarm_acknowledged', () => {
    if (query.page === 1) fetchList()
  }))
  unsubFns.push(wsManager.on('alarm_cleared', () => {
    if (query.page === 1) fetchList()
  }))
})

onUnmounted(() => {
  unsubFns.forEach((fn) => fn())
})
</script>

<template>
  <ContentWrap title="报警管理">
    <template #header>
      <div class="flex-grow flex justify-end items-center">
        <ElBadge :type="wsConnected ? 'success' : 'danger'" is-dot class="mr-8px">
          <span class="text-12px text-gray-400">
            {{ wsConnected ? '实时监控中' : '离线' }}
          </span>
        </ElBadge>
        <ElBadge v-if="unreadAlarms > 0" :value="unreadAlarms" class="mr-12px">
          <ElButton size="small" @click="clearUnread">清除未读</ElButton>
        </ElBadge>
        <ElSelect
          v-model="query.status"
          placeholder="全部状态"
          clearable
          class="!w-140px mr-10px"
          @change="((query.page = 1), fetchList())"
        >
          <ElOption label="活动" value="active" />
          <ElOption label="已确认" value="acknowledged" />
          <ElOption label="已清除" value="cleared" />
        </ElSelect>
        <ElButton type="primary" @click="((query.page = 1), fetchList())">刷新</ElButton>
      </div>
    </template>

    <ElTable v-loading="loading" :data="list" border stripe>
      <template #empty>
        <div class="py-20px text-center text-gray-400">暂无报警记录</div>
      </template>
      <ElTableColumn prop="id" label="ID" width="70" />
      <ElTableColumn prop="device_name" label="设备" min-width="140" show-overflow-tooltip />
      <ElTableColumn prop="tag_name" label="点位" min-width="120" show-overflow-tooltip />
      <ElTableColumn label="级别" width="90">
        <template #default="{ row }"
          ><ElTag :type="levelType(row.alarm_level)">{{ levelLabel(row.alarm_level) }}</ElTag></template
        >
      </ElTableColumn>
      <ElTableColumn prop="alarm_message" label="报警内容" min-width="200" show-overflow-tooltip />
      <ElTableColumn label="状态" width="100">
        <template #default="{ row }"
          ><ElTag :type="statusType(row.status)">{{ statusText(row.status) }}</ElTag></template
        >
      </ElTableColumn>
      <ElTableColumn label="触发时间" width="170">
        <template #default="{ row }">{{ formatTime(row.triggered_at) }}</template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <ElButton
            v-if="row.status === 'active'"
            v-hasPermi="['alarm.ack']"
            link
            type="warning"
            @click="doAck(row)"
            >确认</ElButton
          >
          <ElButton
            v-if="row.status !== 'cleared'"
            v-hasPermi="['alarm.clear']"
            link
            type="success"
            @click="doClear(row)"
            >清除</ElButton
          >
        </template>
      </ElTableColumn>
    </ElTable>

    <div class="flex justify-end mt-16px">
      <ElPagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList"
        @size-change="((query.page = 1), fetchList())"
      />
    </div>
  </ContentWrap>
</template>
