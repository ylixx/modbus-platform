<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
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
  ElMessage
} from 'element-plus'
import { getAllDevices, getDeviceTags, getHistory, unwrap, unwrapList } from '@/api/modbus'

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
  page_size: 20
})

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
  loading.value = true
  try {
    const params: any = {
      device_id: query.device_id,
      tag_id: query.tag_id || undefined,
      page: query.page,
      page_size: query.page_size
    }
    if (query.range && query.range.length === 2) {
      params.start = query.range[0]
      params.end = query.range[1]
    }
    const res = await getHistory(params)
    const { list: l, total: t } = unwrapList(res)
    list.value = l
    total.value = t
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

    <ElTable v-loading="loading" :data="list" border stripe>
      <ElTableColumn prop="id" label="ID" width="80" />
      <ElTableColumn prop="tag_name" label="点位" min-width="140" show-overflow-tooltip />
      <ElTableColumn prop="value" label="数值" min-width="120" />
      <ElTableColumn prop="unit" label="单位" width="90" />
      <ElTableColumn prop="timestamp" label="采集时间" width="190">
        <template #default="{ row }">{{ row.timestamp || row.created_at || row.time }}</template>
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
  </ContentWrap>
</template>
