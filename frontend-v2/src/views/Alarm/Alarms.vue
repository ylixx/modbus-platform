<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElSelect,
  ElOption,
  ElPagination,
  ElMessage
} from 'element-plus'
import { getAlarmRecords, ackAlarm, clearAlarm, unwrapList } from '@/api/modbus'

defineOptions({ name: 'Alarms' })

const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, status: '' })

const levelType = (l?: string) => {
  if (l === 'critical' || l === 'high') return 'danger'
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
  } finally {
    loading.value = false
  }
}
const doAck = async (row: any) => {
  await ackAlarm(row.id)
  ElMessage.success('已确认')
  fetchList()
}
const doClear = async (row: any) => {
  await clearAlarm(row.id)
  ElMessage.success('已清除')
  fetchList()
}

onMounted(fetchList)
</script>

<template>
  <ContentWrap title="报警管理">
    <template #header>
      <div class="flex-grow flex justify-end items-center">
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
      <ElTableColumn prop="id" label="ID" width="70" />
      <ElTableColumn prop="device_name" label="设备" min-width="140" show-overflow-tooltip />
      <ElTableColumn prop="tag_name" label="点位" min-width="120" show-overflow-tooltip />
      <ElTableColumn label="级别" width="90">
        <template #default="{ row }"
          ><ElTag :type="levelType(row.level)">{{ row.level || '—' }}</ElTag></template
        >
      </ElTableColumn>
      <ElTableColumn prop="message" label="报警内容" min-width="200" show-overflow-tooltip />
      <ElTableColumn label="状态" width="100">
        <template #default="{ row }"
          ><ElTag :type="statusType(row.status)">{{ statusText(row.status) }}</ElTag></template
        >
      </ElTableColumn>
      <ElTableColumn prop="triggered_at" label="触发时间" width="170" />
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
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList"
        @size-change="((query.page = 1), fetchList())"
      />
    </div>
  </ContentWrap>
</template>
