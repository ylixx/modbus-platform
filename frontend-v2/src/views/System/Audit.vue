<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import { ElTable, ElTableColumn, ElPagination, ElInput, ElButton, ElTag, ElMessage, ElEmpty } from 'element-plus'
import { getAuditLogs, unwrapList } from '@/api/modbus'
import { formatTime } from '@/utils/modbus'

defineOptions({ name: 'Audit' })

const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 15, keyword: '' })

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getAuditLogs({
      page: query.page,
      page_size: query.page_size,
      keyword: query.keyword || undefined
    })
    const { list: l, total: t } = unwrapList(res)
    list.value = l
    total.value = t
  } catch (e: any) {
    ElMessage.error(e?.message || '获取审计日志失败')
  } finally {
    loading.value = false
  }
}
onMounted(fetchList)
</script>

<template>
  <ContentWrap title="操作审计">
    <template #header>
      <div class="flex-grow flex justify-end">
        <ElInput
          v-model="query.keyword"
          placeholder="搜索用户/操作"
          clearable
          class="!w-220px mr-10px"
          @keyup.enter="((query.page = 1), fetchList())"
        />
        <ElButton type="primary" @click="((query.page = 1), fetchList())">查询</ElButton>
      </div>
    </template>
    <ElTable v-loading="loading" :data="list" border stripe>
      <template #empty><ElEmpty description="暂无数据" :image-size="80" /></template>
      <ElTableColumn sortable prop="id" label="ID" width="70" />
      <ElTableColumn sortable prop="username" label="操作用户" width="130" />
      <ElTableColumn label="操作" width="130">
        <template #default="{ row }"
          ><ElTag>{{ row.action || row.operation || '—' }}</ElTag></template
        >
      </ElTableColumn>
      <ElTableColumn sortable prop="resource" label="对象" min-width="140" show-overflow-tooltip />
      <ElTableColumn sortable prop="detail" label="详情" min-width="240" show-overflow-tooltip />
      <ElTableColumn sortable prop="ip" label="IP" width="140" />
      <ElTableColumn label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </ElTableColumn>
    </ElTable>
    <div class="flex justify-end mt-16px">
      <ElPagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[15, 30, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList"
        @size-change="((query.page = 1), fetchList())"
      />
    </div>
  </ContentWrap>
</template>
