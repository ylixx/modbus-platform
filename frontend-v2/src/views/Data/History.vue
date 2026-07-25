<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElForm,
  ElFormItem,
  ElSelect,
  ElOption,
  ElDatePicker,
  ElTable,
  ElTableColumn,
  ElPagination,
  ElMessage,
  ElEmpty,
  ElRadioGroup,
  ElRadioButton
} from 'element-plus'
import { getAllDevices, getDeviceTags, getHistory, getAggregate, unwrap, unwrapList } from '@/api/modbus'

defineOptions({ name: 'History' })

const devices = ref<any[]>([])
const tags = ref<any[]>([])
const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)

const query = reactive<any>({
  device_id: null,
  tag_id: null,
  range: [],
  page: 1,
  page_size: 20,
  interval: 'raw'
})

const intervalOptions = [
  { label: '原始数据', value: 'raw' },
  { label: '1分钟均值', value: '60' },
  { label: '5分钟均值', value: '300' },
  { label: '15分钟均值', value: '900' },
  { label: '1小时均值', value: '3600' },
  { label: '1天均值', value: '86400' }
]

const isAggregated = computed(() => query.interval !== 'raw')

const fetchDevices = async () => {
  devices.value = unwrapList(await getAllDevices()).list
}
const onDeviceChange = async () => {
  query.tag_id = null
  tags.value = []
  if (query.device_id == null) return
  const res = await getDeviceTags(query.device_id)
  const body = unwrap(res)
  tags.value = Array.isArray(body) ? body : unwrapList(res).list
}
const fetchList = async () => {
  if (query.device_id == null) {
    ElMessage.warning('请先选择设备')
    return
  }
  if (!query.tag_id) {
    ElMessage.warning('请选择点位')
    return
  }
  loading.value = true
  try {
    const params: any = {
      device_id: query.device_id,
      tag_id: query.tag_id,
      page: query.page,
      page_size: query.page_size
    }
    if (query.range && query.range.length === 2) {
      params.start_time = query.range[0]
      params.end_time = query.range[1]
    }

    if (isAggregated.value) {
      // 聚合查询
      params.granularity = Number(query.interval)
      const res = await getAggregate(params)
      const body = (res as any)?.data || res
      list.value = body?.data || []
      total.value = list.value.length
    } else {
      // 原始查询
      params.interval = 'raw'
      const res = await getHistory(params)
      const { list: l, total: t } = unwrapList(res)
      list.value = l
      total.value = t
    }
  } finally {
    loading.value = false
  }
}

onMounted(fetchDevices)
</script>

<template>
  <ContentWrap title="历史数据">
    <ElForm :inline="true" :model="query" class="mb-8px">
      <ElFormItem label="设备">
        <ElSelect
          v-model="query.device_id"
          class="!w-180px"
          placeholder="选择设备"
          @change="onDeviceChange"
        >
          <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="点位">
        <ElSelect
          v-model="query.tag_id"
          class="!w-160px"
          clearable
          placeholder="全部点位"
          :disabled="query.device_id == null"
        >
          <ElOption v-for="t in tags" :key="t.id" :label="t.name" :value="t.id" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="时间">
        <ElDatePicker
          v-model="query.range"
          type="datetimerange"
          value-format="YYYY-MM-DD HH:mm:ss"
          start-placeholder="开始"
          end-placeholder="结束"
        />
      </ElFormItem>
      <ElFormItem>
        <ElButton type="primary" @click="((query.page = 1), fetchList())">查询</ElButton>
      </ElFormItem>
    </ElForm>

    <!-- 粒度切换 -->
    <div class="mb-12px">
      <ElRadioGroup v-model="query.interval" @change="((query.page = 1), fetchList())">
        <ElRadioButton
          v-for="opt in intervalOptions"
          :key="opt.value"
          :value="opt.value"
          :label="opt.label"
        />
      </ElRadioGroup>
    </div>

    <ElEmpty v-if="!loading && !list.length" description="暂无数据，请选择设备和点位后查询" />

    <!-- 原始数据表格 -->
    <template v-if="!isAggregated">
      <ElTable v-loading="loading" :data="list" border stripe>
        <ElTableColumn prop="id" label="ID" width="80" />
        <ElTableColumn prop="tag_name" label="点位" min-width="140" show-overflow-tooltip />
        <ElTableColumn prop="value" label="数值" min-width="120" />
        <ElTableColumn prop="raw_value" label="原始值" min-width="100" />
        <ElTableColumn prop="quality" label="质量" width="80">
          <template #default="{ row }">
            <ElTag :type="row.quality === 'good' ? 'success' : 'danger'" size="small">
              {{ row.quality || '—' }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="采集时间" width="190">
          <template #default="{ row }">{{ row.time || row.created_at || row.recorded_at }}</template>
        </ElTableColumn>
      </ElTable>
      <div class="flex justify-end mt-16px">
        <ElPagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="fetchList"
          @size-change="((query.page = 1), fetchList())"
        />
      </div>
    </template>

    <!-- 聚合数据表格 -->
    <template v-else>
      <ElTable v-loading="loading" :data="list" border stripe>
        <ElTableColumn label="时间" width="190">
          <template #default="{ row }">{{ row.time?.replace('T', ' ').slice(0, 19) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="avg" label="均值" min-width="100">
          <template #default="{ row }">
            <span class="font-700 text-blue-500">{{ row.avg }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="min" label="最小值" min-width="100" />
        <ElTableColumn prop="max" label="最大值" min-width="100" />
        <ElTableColumn prop="first" label="首值" min-width="100" />
        <ElTableColumn prop="last" label="末值" min-width="100" />
        <ElTableColumn prop="count" label="采样数" width="80" />
      </ElTable>
    </template>
  </ContentWrap>
</template>
