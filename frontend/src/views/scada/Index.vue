<template>
  <div>
    <div class="page-header">
      <h2>SCADA 画面</h2>
      <p>组态画面编辑与运行</p>
    </div>

    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>画面列表</span>
          <div>
            <el-button @click="$router.push('/scada/widgets')"><el-icon><Picture /></el-icon> 自定义图元</el-button>
            <el-button type="primary" @click="createPage"><el-icon><Plus /></el-icon> 新建画面</el-button>
          </div>
        </div>
      </template>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="画面名称" width="200" />
        <el-table-column prop="description" label="描述" />
        <el-table-column label="尺寸" width="120"><template #default="{ row }">{{ row.width }} × {{ row.height }}</template></el-table-column>
        <el-table-column prop="updated_at" label="最后修改" width="170"><template #default="{ row }">{{ formatTime(row.updated_at) }}</template></el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="$router.push(`/scada/editor/${row.id}`)">编辑</el-button>
            <el-button size="small" type="success" @click="$router.push(`/scada/view/${row.id}`)">运行</el-button>
            <el-button size="small" @click="duplicatePage(row)">复制</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row, 'name')">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/request'
import { useTable } from '../../composables/useTable'
import { formatTime } from '../../utils'

const router = useRouter()

const { tableData, loading, fetchList, handleDelete } = useTable({
  listApi: () => api.get('/scada/pages'),
  deleteApi: (id) => api.delete(`/scada/pages/${id}`),
  immediate: true,
})

async function createPage() {
  const res = await api.post('/scada/pages', { name: '新画面' })
  router.push(`/scada/editor/${res.data.id}`)
}

async function duplicatePage(page) {
  await api.post(`/scada/pages/${page.id}/duplicate`)
  ElMessage.success('已复制')
  fetchList()
}
</script>
