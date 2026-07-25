<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
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
  ElRadioGroup,
  ElRadio,
  ElCheckboxGroup,
  ElCheckbox,
  ElTreeSelect,
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
  getOrgTree,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'Rbac' })

const activeTab = ref('roles')
const roles = ref<any[]>([])
const permissions = ref<any[]>([])
const users = ref<any[]>([])
const orgTree = ref<any[]>([])
const loading = ref(false)

const permCode = (p: any) => (typeof p === 'string' ? p : p.code || p.name)
// 权限 code -> id 映射，用于提交 permission_ids
const permMap = computed<Record<string, number>>(() => {
  const m: Record<string, number> = {}
  for (const p of permissions.value) m[permCode(p)] = p.id
  return m
})

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
const fetchOrgTree = async () => {
  const res = await getOrgTree()
  orgTree.value = res?.data || []
}

const dialogVisible = ref(false)
const dialogTitle = ref('新增角色')
const formRef = ref()
const form = reactive<any>({
  id: null,
  code: '',
  name: '',
  description: '',
  permissionCodes: [] as string[],
  data_scope: 'all', // all | org
  org_node_ids: [] as number[]
})
const isAdminRole = computed(() => form.code === 'admin')
const rules = {
  code: [{ required: true, message: '请输入角色代码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
}

const openCreate = () => {
  dialogTitle.value = '新增角色'
  Object.assign(form, {
    id: null,
    code: '',
    name: '',
    description: '',
    permissionCodes: [],
    data_scope: 'all',
    org_node_ids: []
  })
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑角色'
  Object.assign(form, {
    id: row.id,
    code: row.code,
    name: row.name,
    description: row.description || '',
    permissionCodes: (row.permissions || []).map((p: any) => permCode(p)),
    data_scope: row.data_scope || 'all',
    org_node_ids: (row.org_node_ids || []).slice()
  })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  const permission_ids = form.permissionCodes.map((c: string) => permMap.value[c]).filter(Boolean)
  const payload: any = {
    name: form.name,
    description: form.description,
    permission_ids,
    data_scope: form.data_scope,
    org_node_ids: form.data_scope === 'org' ? form.org_node_ids : []
  }
  if (!form.id) payload.code = form.code
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
  fetchOrgTree()
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
          <ElTableColumn prop="code" label="角色代码" width="140" />
          <ElTableColumn prop="description" label="描述" min-width="160" show-overflow-tooltip />
          <ElTableColumn label="数据范围" width="130">
            <template #default="{ row }">
              <ElTag :type="(row.data_scope || 'all') === 'all' ? 'success' : 'warning'">
                {{ (row.data_scope || 'all') === 'all' ? '全部数据' : '按组织范围' }}
              </ElTag>
            </template>
          </ElTableColumn>
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

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="660px">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="90px">
        <ElFormItem label="角色代码" prop="code">
          <ElInput v-model="form.code" :disabled="!!form.id" placeholder="如：workshop_admin" />
        </ElFormItem>
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="form.description" type="textarea" :rows="2" />
        </ElFormItem>
        <ElFormItem label="数据范围">
          <ElRadioGroup v-model="form.data_scope" :disabled="isAdminRole">
            <ElRadio value="all">全部数据</ElRadio>
            <ElRadio value="org">按组织范围</ElRadio>
          </ElRadioGroup>
        </ElFormItem>
        <ElFormItem v-if="form.data_scope === 'org'" label="组织范围">
          <ElTreeSelect
            v-model="form.org_node_ids"
            :data="orgTree"
            node-key="id"
            :props="{ label: 'name', children: 'children' }"
            multiple
            check-strictly
            clearable
            placeholder="勾选可访问的组织节点（含其下级）"
            class="w-full"
          />
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
