<template>
  <div>
    <div class="page-header">
      <h2>操作审计</h2>
      <p>系统操作日志记录与查询</p>
    </div>

    <el-card style="margin-bottom:16px">
      <el-row :gutter="16" align="middle">
        <el-col :span="4"><el-input v-model="searchParams.username" placeholder="操作人" clearable @keyup.enter="handleSearch" /></el-col>
        <el-col :span="4">
          <el-select v-model="searchParams.resource_type" placeholder="资源类型" clearable @change="handleSearch">
            <el-option label="设备" value="device" /><el-option label="点位" value="tag" /><el-option label="报警" value="alarm" /><el-option label="短信" value="sms" /><el-option label="用户" value="user" />
          </el-select>
        </el-col>
        <el-col :span="8">
          <el-date-picker v-model="timeRange" type="datetimerange" range-separator="至" start-placeholder="开始" end-placeholder="结束"
            format="YYYY-MM-DD HH:mm:ss" value-format="YYYY-MM-DD HH:mm:ss" @change="onTimeChange" />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="handleSearch"><el-icon><Search /></el-icon> 查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="操作人" width="100" />
        <el-table-column prop="action" label="操作" width="180">
          <template #default="{ row }"><el-tag :type="actionType(row.action)" size="small">{{ row.action }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="resource_type" label="资源类型" width="80" />
        <el-table-column prop="resource_name" label="资源名称" width="160" show-overflow-tooltip />
        <el-table-column prop="detail" label="详情" show-overflow-tooltip />
        <el-table-column prop="ip_address" label="IP" width="130" />
        <el-table-column prop="created_at" label="时间" width="170"><template #default="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" :total="total" layout="total, prev, pager, next"
        style="margin-top:16px;justify-content:flex-end" @current-change="handlePageChange" />
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../../api/request'
import { useTable } from '../../composables/useTable'
import { formatTime } from '../../utils'

const timeRange = ref([])

const { tableData, loading, total, page, searchParams, handleSearch, handleReset, handlePageChange } = useTable({
  listApi: (params) => api.get('/audit/logs', { params }),
  defaultParams: { username: '', resource_type: '', start_time: '', end_time: '' },
})

function onTimeChange(val) {
  searchParams.start_time = val?.[0] || ''
  searchParams.end_time = val?.[1] || ''
  handleSearch()
}

const actionType = (a) => {
  if (a?.includes('create')) return 'success'
  if (a?.includes('delete')) return 'danger'
  if (a?.includes('update') || a?.includes('edit')) return 'warning'
  return 'info'
}
</script>
