<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox
} from 'element-plus'
import { getGroups, createGroup, updateGroup, deleteGroup, unwrapList } from '@/api/modbus'

defineOptions({ name: 'Groups' })

const loading = ref(false)
const list = ref<any[]>([])
const fetchList = async () => {
  loading.value = true
  try {
    list.value = unwrapList(await getGroups()).list
  } finally {
    loading.value = false
  }
}

const dialogVisible = ref(false)
const dialogTitle = ref('新增分组')
const formRef = ref()
const form = reactive<any>({ id: null, name: '', description: '' })
const rules = { name: [{ required: true, message: '请输入分组名称', trigger: 'blur' }] }

const openCreate = () => {
  dialogTitle.value = '新增分组'
  Object.assign(form, { id: null, name: '', description: '' })
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑分组'
  Object.assign(form, { id: row.id, name: row.name, description: row.description || '' })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  const payload = { name: form.name, description: form.description }
  if (form.id) {
    await updateGroup(form.id, payload)
    ElMessage.success('更新成功')
  } else {
    await createGroup(payload)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchList()
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除分组「${row.name}」？`, '提示', { type: 'warning' })
  await deleteGroup(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

onMounted(fetchList)
</script>

<template>
  <ContentWrap title="设备分组">
    <template #header>
      <div class="flex-grow flex justify-end">
        <ElButton v-hasPermi="['group.write']" type="success" @click="openCreate"
          >新增分组</ElButton
        >
      </div>
    </template>
    <ElTable v-loading="loading" :data="list" border stripe>
      <ElTableColumn prop="id" label="ID" width="80" />
      <ElTableColumn prop="name" label="分组名称" min-width="160" />
      <ElTableColumn prop="device_count" label="设备数" width="100" />
      <ElTableColumn prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <ElTableColumn label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <ElButton v-hasPermi="['group.write']" link type="primary" @click="openEdit(row)"
            >编辑</ElButton
          >
          <ElButton v-hasPermi="['group.write']" link type="danger" @click="remove(row)"
            >删除</ElButton
          >
        </template>
      </ElTableColumn>
    </ElTable>

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="460px">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="80px">
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="form.description" type="textarea" :rows="2" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
