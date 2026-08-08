<script setup lang="ts">
import { ref } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import { ElTable, ElTableColumn, ElPagination, ElInput, ElButton, ElTag, ElMessage, ElEmpty } from 'element-plus'
import { getAuditLogs } from '@/api/modbus'
import { formatTime } from '@/utils/modbus'
import { usePagination } from '@/hooks/web/usePagination'

defineOptions({ name: 'Audit' })

const keyword = ref('')

const { list, total, loading, page, page_size, onPageChange, onSizeChange, resetPage } = usePagination(
  async (q) => {
    try {
      return await getAuditLogs({ page: q.page, page_size: q.page_size, keyword: keyword.value || undefined })
    } catch (e: any) {
      ElMessage.error(e?.message || '获取审计日志失败')
      throw e
    }
  },
  { pageSize: 15 }
)
</script>

<template>
  <ContentWrap title="操作审计">
    <template #header>
      <div class="flex-grow flex justify-end">
        <ElInput
          v-model="keyword"
          placeholder="搜索用户/操作"
          clearable
          class="!w-220px mr-10px"
          @keyup.enter="resetPage"
        />
        <ElButton type="primary" @click="resetPage">查询</ElButton>
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
        v-model:current-page="page"
        v-model:page-size="page_size"
        :total="total"
        :page-sizes="[15, 30, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>
  </ContentWrap>
</template>
