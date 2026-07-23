<template>
  <div>
    <div class="page-header">
      <h2>设备分组</h2>
      <p>管理设备分组，便于分类组织</p>
    </div>
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>分组列表</span>
          <el-button type="primary" size="small" @click="openDialog()"><el-icon><Plus /></el-icon> 新增分组</el-button>
        </div>
      </template>
      <el-table :data="pagedRows" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="分组名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        style="margin-top:12px; display:flex; justify-content:flex-end"
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        :page-size="pageSize"
        :current-page="currentPage"
        :page-sizes="[10, 20, 30, 50, 100]"
        @size-change="onSizeChange"
        @current-change="onPageChange"
      />
    </el-card>

    <!-- Dialog using useForm -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑分组' : '新增分组'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称" required><el-input v-model="form.name" placeholder="请输入分组名称" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" placeholder="选填" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="form.sort_order" :min="0" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import api from '../../api/request'
import { useTable } from '../../composables/useTable'
import { useForm } from '../../composables/useForm'
import { useClientPagination } from '../../composables/useClientPagination'

// Table: list + delete
const { tableData, loading, fetchList, handleDelete } = useTable({
  listApi: (params) => api.get('/devices/groups', { params }),
  deleteApi: (id) => api.delete(`/devices/groups/${id}`),
  immediate: true,
  onDeleteSuccess: () => resetPage(),
})
const {
  pageSize, currentPage, total, pagedRows,
  onSizeChange, onPageChange, resetPage,
} = useClientPagination(tableData)

// Form: create + update
const { form, dialogVisible, isEdit, submitLoading, openDialog, closeDialog, handleSubmit } = useForm({
  defaultForm: { name: '', description: '', sort_order: 0 },
  createApi: (data) => api.post('/devices/groups', data),
  updateApi: (id, data) => api.put(`/devices/groups/${id}`, data),
  validate: (form) => {
    if (!form.name) return '请输入分组名称'
  },
  onSuccess: () => fetchList(),
})
</script>
