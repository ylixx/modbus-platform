<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElMessage,
  ElMessageBox,
  ElCheckbox,
  ElCheckboxGroup,
  ElEmpty
} from 'element-plus'
import { getRoles, createRole, updateRole, deleteRole, getPermissions } from '@/api/modbus'

defineOptions({ name: 'RoleManagement' })

const loading = ref(false)
const list = ref<any[]>([])
const permissions = ref<any[]>([])

// Dialog state
const dialogVisible = ref(false)
const dialogTitle = ref('新增角色')
const formRef = ref()
const form = ref<any>({
  id: null,
  code: '',
  name: '',
  description: '',
  permission_ids: [] as number[],
  data_scope: 'all'
})
const formRules = {
  code: [{ required: true, message: '请输入角色代码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
}

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getRoles()
    list.value = res?.data || res || []
  } finally {
    loading.value = false
  }
}

const fetchPermissions = async () => {
  try {
    const res = await getPermissions()
    permissions.value = res?.data || res || []
  } catch {
    permissions.value = []
  }
}

// Group permissions by module for display
const permissionsByModule = ref<Record<string, any[]>>({})
const groupPermissions = () => {
  const grouped: Record<string, any[]> = {}
  for (const p of permissions.value) {
    const mod = p.module || '其他'
    if (!grouped[mod]) grouped[mod] = []
    grouped[mod].push(p)
  }
  permissionsByModule.value = grouped
}

const openCreate = () => {
  dialogTitle.value = '新增角色'
  form.value = {
    id: null,
    code: '',
    name: '',
    description: '',
    permission_ids: [],
    data_scope: 'all'
  }
  dialogVisible.value = true
}

const openEdit = (row: any) => {
  dialogTitle.value = '编辑角色'
  form.value = {
    id: row.id,
    code: row.code,
    name: row.name,
    description: row.description,
    permission_ids: (row.permissions || []).map((p: any) => p.id),
    data_scope: row.data_scope || 'all'
  }
  dialogVisible.value = true
}

const submit = async () => {
  await formRef.value?.validate()
  const payload = {
    code: form.value.code,
    name: form.value.name,
    description: form.value.description,
    permission_ids: form.value.permission_ids,
    data_scope: form.value.data_scope
  }
  if (form.value.id) {
    await updateRole(form.value.id, payload)
    ElMessage.success('更新成功')
  } else {
    await createRole(payload)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchList()
}

const remove = async (row: any) => {
  if (row.is_system) {
    ElMessage.warning('系统角色不可删除')
    return
  }
  await ElMessageBox.confirm(`确认删除角色「${row.name}」？`, '提示', { type: 'warning' })
  await deleteRole(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

onMounted(() => {
  fetchList()
  fetchPermissions().then(groupPermissions)
})
</script>

<template>
  <ContentWrap title="角色管理">
    <div class="mb-12px">
      <ElButton v-hasPermi="['rbac.write']" type="primary" @click="openCreate">新增角色</ElButton>
    </div>

    <ElTable v-loading="loading" :data="list" border stripe>
      <template #empty><ElEmpty description="暂无数据" :image-size="80" /></template>
      <ElTableColumn sortable prop="id" label="ID" width="70" />
      <ElTableColumn sortable prop="code" label="角色代码" width="140" />
      <ElTableColumn sortable prop="name" label="角色名称" min-width="140" />
      <ElTableColumn sortable prop="description" label="描述" min-width="160" show-overflow-tooltip />
      <ElTableColumn label="数据范围" width="100">
        <template #default="{ row }">
          <ElTag :type="row.data_scope === 'all' ? 'success' : 'warning'">
            {{ row.data_scope === 'all' ? '全部' : '组织' }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="系统角色" width="90">
        <template #default="{ row }">
          <ElTag v-if="row.is_system" type="info" size="small">是</ElTag>
          <span v-else>-</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="权限数" width="80">
        <template #default="{ row }">
          {{ row.permissions?.length || 0 }}
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <ElButton v-hasPermi="['rbac.write']" link type="primary" @click="openEdit(row)">编辑</ElButton>
          <ElButton v-if="!row.is_system" v-hasPermi="['rbac.write']" link type="danger" @click="remove(row)">删除</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>

    <!-- 新增/编辑对话框 -->
    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="640px" top="5vh" @close="formRef?.resetFields()">
      <ElForm ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <ElFormItem label="角色代码" prop="code">
          <ElInput v-model="form.code" placeholder="如 admin, operator" :disabled="!!form.id" />
        </ElFormItem>
        <ElFormItem label="角色名称" prop="name">
          <ElInput v-model="form.name" placeholder="请输入角色名称" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="form.description" type="textarea" :rows="2" placeholder="可选" />
        </ElFormItem>
        <ElFormItem label="数据范围">
          <ElSelect v-model="form.data_scope" class="w-full">
            <ElOption label="全部数据" value="all" />
            <ElOption label="组织范围" value="org" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="权限">
          <div class="w-full max-h-300px overflow-auto">
            <div v-for="(perms, mod) in permissionsByModule" :key="mod" class="mb-8px">
              <div class="font-bold text-13px mb-4px">{{ mod }}</div>
              <ElCheckboxGroup v-model="form.permission_ids">
                <ElCheckbox
                  v-for="p in perms"
                  :key="p.id"
                  :value="p.id"
                  :label="p.name"
                  class="!mr-16px !mb-4px"
                />
              </ElCheckboxGroup>
            </div>
          </div>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
