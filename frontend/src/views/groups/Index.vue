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
          <el-button type="primary" size="small" @click="showDialog()">新增分组</el-button>
        </div>
      </template>
      <el-table :data="groups" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="分组名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="showDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑分组' : '新增分组'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="form.sort_order" :min="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/request'

const groups = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const form = reactive({ name: '', description: '', sort_order: 0 })

async function fetchGroups() {
  const res = await api.get('/devices/groups')
  groups.value = res.data
}

function showDialog(g) {
  if (g) {
    editingId.value = g.id
    Object.assign(form, { name: g.name, description: g.description, sort_order: g.sort_order })
  } else {
    editingId.value = null
    Object.assign(form, { name: '', description: '', sort_order: 0 })
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.name) { ElMessage.warning('请输入名称'); return }
  if (editingId.value) {
    await api.put(`/devices/groups/${editingId.value}`, form)
  } else {
    await api.post('/devices/groups', form)
  }
  ElMessage.success('保存成功')
  dialogVisible.value = false
  fetchGroups()
}

async function handleDelete(g) {
  await ElMessageBox.confirm(`确定删除分组 "${g.name}"？`)
  await api.delete(`/devices/groups/${g.id}`)
  ElMessage.success('删除成功')
  fetchGroups()
}

onMounted(fetchGroups)
</script>
