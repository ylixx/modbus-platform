<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTabs,
  ElTabPane,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElCheckboxGroup,
  ElCheckbox,
  ElMessage,
  ElMessageBox
} from 'element-plus'
import {
  getRoles,
  createRole,
  updateRole,
  deleteRole,
  getPermissions,
  getUsers,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'Rbac' })

const activeTab = ref('roles')
const roles = ref<any[]>([])
const permissions = ref<any[]>([])
const users = ref<any[]>([])
const loading = ref(false)

const fetchRoles = async () => {
  loading.value = true
  try {
    roles.value = unwrapList(await getRoles()).list
  } finally {
    loading.value = false
  }
}
const fetchPermissions = async () => {
  permissions.value = unwrapList(await getPermissions()).list
}
const fetchUsers = async () => {
  users.value = unwrapList(await getUsers({ page: 1, page_size: 100 })).list
}

const permCode = (p: any) => (typeof p === 'string' ? p : p.code || p.name)

const dialogVisible = ref(false)
const dialogTitle = ref('新增角色')
const formRef = ref()
const form = reactive<any>({ id: null, name: '', description: '', permissionCodes: [] as string[] })
const rules = { name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }] }

const openCreate = () => {
  dialogTitle.value = '新增角色'
  Object.assign(form, { id: null, name: '', description: '', permissionCodes: [] })
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑角色'
  Object.assign(form, {
    id: row.id,
    name: row.name,
    description: row.description || '',
    permissionCodes: (row.permissions || []).map((p: any) => permCode(p))
  })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  const payload = {
    name: form.name,
    description: form.description,
    permissions: form.permissionCodes
  }
  if (form.id) {
    await updateRole(form.id, payload)
    ElMessage.success('更新成功')
  } else {
    await createRole(payload)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchRoles()
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除角色「${row.name}」？`, '提示', { type: 'warning' })
  await deleteRole(row.id)
  ElMessage.success('删除成功')
  fetchRoles()
}

onMounted(() => {
  fetchRoles()
  fetchPermissions()
  fetchUsers()
})
</script>

<template>
  <ContentWrap title="权限管理">
    <ElTabs v-model="activeTab">
      <ElTabPane label="角色管理" name="roles">
        <div class="flex justify-end mb-12px">
          <ElButton v-hasPermi="['rbac.write']" type="success" @click="openCreate"
            >新增角色</ElButton
          >
        </div>
        <ElTable v-loading="loading" :data="roles" border stripe>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn prop="name" label="角色名称" width="150" />
          <ElTableColumn prop="description" label="描述" min-width="160" show-overflow-tooltip />
          <ElTableColumn label="权限数" width="100">
            <template #default="{ row }">{{ (row.permissions || []).length }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <ElButton v-hasPermi="['rbac.write']" link type="primary" @click="openEdit(row)"
                >编辑</ElButton
              >
              <ElButton v-hasPermi="['rbac.write']" link type="danger" @click="remove(row)"
                >删除</ElButton
              >
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>

      <ElTabPane label="用户管理" name="users">
        <ElTable :data="users" border stripe>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn prop="username" label="用户名" width="140" />
          <ElTableColumn prop="display_name" label="显示名" min-width="140" />
          <ElTableColumn label="角色" width="130">
            <template #default="{ row }"
              ><ElTag>{{ row.role || '—' }}</ElTag></template
            >
          </ElTableColumn>
          <ElTableColumn prop="phone" label="手机号" width="140" />
          <ElTableColumn label="状态" width="90">
            <template #default="{ row }">
              <ElTag :type="row.is_active !== false ? 'success' : 'info'">{{
                row.is_active !== false ? '启用' : '停用'
              }}</ElTag>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>

      <ElTabPane label="权限清单" name="perms">
        <div class="flex flex-wrap gap-8px py-8px">
          <ElTag v-for="p in permissions" :key="permCode(p)" class="mb-6px">{{
            permCode(p)
          }}</ElTag>
        </div>
      </ElTabPane>
    </ElTabs>

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="640px">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="80px">
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="form.description" type="textarea" :rows="2" />
        </ElFormItem>
        <ElFormItem label="权限">
          <ElCheckboxGroup v-model="form.permissionCodes">
            <ElCheckbox
              v-for="p in permissions"
              :key="permCode(p)"
              :value="permCode(p)"
              :label="permCode(p)"
            />
          </ElCheckboxGroup>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
