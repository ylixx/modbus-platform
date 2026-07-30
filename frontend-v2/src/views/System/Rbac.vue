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
  ElSwitch,
  ElSelect,
  ElOption,
  ElMessage,
  ElMessageBox,
  ElPagination,
  ElEmpty
} from 'element-plus'
import {
  getRoles,
  createRole,
  updateRole,
  deleteRole,
  getPermissions,
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  resetUserPassword,
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

// ── 用户分页 ──
const userPage = ref(1)
const userPageSize = ref(20)
const userTotal = ref(0)
const userSearch = ref('')

const permCode = (p: any) => (typeof p === 'string' ? p : p.code || p.name)
// ── 权限按 module 分组 ──
const permissionsByModule = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const p of permissions.value) {
    const code = permCode(p)
    // 解析 module: 取第一个点号前的部分，如 alarm.read → alarm
    const module = code.includes('.') ? code.split('.')[0] : 'other'
    if (!groups[module]) groups[module] = []
    groups[module].push(p)
  }
  return groups
})

const permMap = computed<Record<string, number>>(() => {
  const m: Record<string, number> = {}
  for (const p of permissions.value) m[permCode(p)] = p.id
  return m
})

// ── 角色管理 ──
const fetchRoles = async () => {
  loading.value = true
  try {
    roles.value = unwrapList(await getRoles()).list
  } finally {
    loading.value = false
  }
}
const fetchPermissions = async () => {
  try {
    permissions.value = unwrapList(await getPermissions()).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取权限列表失败')
  }
}
const fetchUsers = async () => {
  try {
    const params: any = { page: userPage.value, page_size: userPageSize.value }
    if (userSearch.value) params.keyword = userSearch.value
    const res = unwrapList(await getUsers(params))
    users.value = res.list
    userTotal.value = res.total
  } catch (e: any) {
    ElMessage.error(e?.message || '获取用户列表失败')
  }
}
const onUserPageChange = (p: number) => {
  userPage.value = p
  fetchUsers()
}
const onUserSizeChange = (s: number) => {
  userPageSize.value = s
  userPage.value = 1
  fetchUsers()
}
const onUserSearch = () => {
  userPage.value = 1
  fetchUsers()
}
const fetchOrgTree = async () => {
  try {
    const res = await getOrgTree()
    orgTree.value = res?.data || []
  } catch (e: any) {
    ElMessage.error(e?.message || '获取组织架构失败')
  }
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
  data_scope: 'all',
  org_node_ids: [] as number[]
})
const isAdminRole = computed(() => form.code === 'admin')
const roleRules = {
  code: [{ required: true, message: '请输入角色代码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
}

const openCreate = () => {
  dialogTitle.value = '新增角色'
  Object.assign(form, {
    id: null, code: '', name: '', description: '',
    permissionCodes: [], data_scope: 'all', org_node_ids: []
  })
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑角色'
  Object.assign(form, {
    id: row.id, code: row.code, name: row.name,
    description: row.description || '',
    permissionCodes: (row.permissions || []).map((p: any) => permCode(p)),
    data_scope: row.data_scope || 'all',
    org_node_ids: (row.org_node_ids || []).slice()
  })
  dialogVisible.value = true
}
const submitRole = async () => {
  try {
    await formRef.value?.validate()
    const permission_ids = form.permissionCodes.map((c: string) => permMap.value[c]).filter(Boolean)
    const payload: any = {
      name: form.name, description: form.description,
      permission_ids, data_scope: form.data_scope,
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
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}
const removeRole = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除角色「${row.name}」？`, '提示', { type: 'warning' })
    await deleteRole(row.id)
    ElMessage.success('删除成功')
    fetchRoles()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}

// ── 用户管理 ──
const userDialogVisible = ref(false)
const userDialogTitle = ref('新增用户')
const userFormRef = ref()
const userForm = reactive<any>({
  id: null,
  username: '',
  password: '',
  display_name: '',
  phone: '',
  email: '',
  role: 'operator',
  is_active: true
})
const userRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码长度不能少于8位', trigger: 'blur' },
    { pattern: /^(?=.*[a-zA-Z])(?=.*\d)/, message: '密码需包含字母和数字', trigger: 'blur' }
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }],
  email: [{ type: 'email' as const, message: '请输入正确的邮箱地址', trigger: 'blur' }]
}
const userEditRules = {
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }],
  email: [{ type: 'email' as const, message: '请输入正确的邮箱地址', trigger: 'blur' }]
}

const roleOptions = computed(() => roles.value.map((r) => ({ label: r.name, value: r.code || r.name })))

const openUserCreate = () => {
  userDialogTitle.value = '新增用户'
  Object.assign(userForm, {
    id: null, username: '', password: '', display_name: '',
    phone: '', email: '', role: 'operator', is_active: true
  })
  userDialogVisible.value = true
}
const openUserEdit = (row: any) => {
  userDialogTitle.value = '编辑用户'
  Object.assign(userForm, {
    id: row.id, username: row.username, password: '',
    display_name: row.display_name || '', phone: row.phone || '',
    email: row.email || '', role: row.role || 'operator',
    is_active: row.is_active !== false
  })
  userDialogVisible.value = true
}
const submitUser = async () => {
  try {
    const rules = userForm.id ? userEditRules : userRules
    await userFormRef.value?.validate(rules)
    if (userForm.id) {
      const payload: any = {
        display_name: userForm.display_name,
        phone: userForm.phone,
        email: userForm.email,
        role: userForm.role,
        is_active: userForm.is_active
      }
      await updateUser(userForm.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createUser({
        username: userForm.username,
        password: userForm.password,
        display_name: userForm.display_name,
        phone: userForm.phone,
        email: userForm.email,
        role: userForm.role
      })
      ElMessage.success('创建成功')
    }
    userDialogVisible.value = false
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}
const removeUser = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除用户「${row.username}」？`, '提示', { type: 'warning' })
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    fetchUsers()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}
const resetPassword = async (row: any) => {
  const { value } = await ElMessageBox.prompt('请输入新密码', `重置密码 - ${row.username}`, {
    inputType: 'password',
    inputPlaceholder: '请输入新密码',
    inputValidator: (v) => {
      if (!v?.trim()) return '密码不能为空'
      if (v.length < 8) return '密码长度不能少于8位'
      if (!/^(?=.*[a-zA-Z])(?=.*\d)/.test(v)) return '密码需包含字母和数字'
      return true
    },
    confirmButtonText: '确认重置',
    cancelButtonText: '取消'
  })
  try {
    await resetUserPassword(row.id, { new_password: value })
    ElMessage.success('密码已重置')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '重置失败')
  }
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
      <!-- 角色管理 -->
      <ElTabPane label="角色管理" name="roles">
        <div class="flex justify-end mb-12px">
          <ElButton v-hasPermi="['rbac.write']" type="success" @click="openCreate">新增角色</ElButton>
        </div>
        <ElTable v-loading="loading" :data="roles" border stripe>
          <template #empty><ElEmpty description="暂无数据" :image-size="80" /></template>
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
              <ElButton v-hasPermi="['rbac.write']" link type="primary" @click="openEdit(row)">编辑</ElButton>
              <ElButton v-hasPermi="['rbac.write']" link type="danger" @click="removeRole(row)">删除</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>

      <!-- 用户管理 -->
      <ElTabPane label="用户管理" name="users">
        <div class="flex justify-between items-center mb-12px">
          <ElInput
            v-model="userSearch"
            placeholder="搜索用户名/显示名"
            clearable
            style="width: 240px"
            @keyup.enter="onUserSearch"
            @clear="onUserSearch"
          />
          <ElButton v-hasPermi="['rbac.write']" type="success" @click="openUserCreate">新增用户</ElButton>
        </div>
        <ElTable v-loading="loading" :data="users" border stripe>
          <template #empty><ElEmpty description="暂无数据" :image-size="80" /></template>
          <ElTableColumn prop="id" label="ID" width="60" />
          <ElTableColumn prop="username" label="用户名" width="120" />
          <ElTableColumn prop="display_name" label="显示名" width="120" />
          <ElTableColumn label="角色" width="110">
            <template #default="{ row }">
              <ElTag>{{ row.role || '—' }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="phone" label="手机号" width="130" />
          <ElTableColumn prop="email" label="邮箱" min-width="160" show-overflow-tooltip />
          <ElTableColumn label="状态" width="80">
            <template #default="{ row }">
              <ElTag :type="row.is_active !== false ? 'success' : 'info'">
                {{ row.is_active !== false ? '启用' : '停用' }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <ElButton v-hasPermi="['rbac.write']" link type="primary" @click="openUserEdit(row)">编辑</ElButton>
              <ElButton v-hasPermi="['rbac.write']" link type="warning" @click="resetPassword(row)">重置密码</ElButton>
              <ElButton v-hasPermi="['rbac.write']" link type="danger" @click="removeUser(row)">删除</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
        <div class="flex justify-end mt-12px">
          <ElPagination
            v-model:current-page="userPage"
            v-model:page-size="userPageSize"
            :total="userTotal"
            layout="total, sizes, prev, pager, next, jumper"
            :page-sizes="[10, 20, 50]"
            @current-change="onUserPageChange"
            @size-change="onUserSizeChange"
          />
        </div>
      </ElTabPane>

      <!-- 权限清单 -->
      <ElTabPane label="权限清单" name="perms">
        <div v-for="(perms, module) in permissionsByModule" :key="module" class="mb-16px">
          <div class="text-14px font-600 mb-8px text-gray-500">{{ module }}</div>
          <div class="flex flex-wrap gap-8px">
            <ElTag v-for="p in perms" :key="permCode(p)" class="mb-6px">{{ permCode(p) }}</ElTag>
          </div>
        </div>
        <div v-if="!Object.keys(permissionsByModule).length" class="text-13px text-gray-400">暂无权限数据</div>
      </ElTabPane>
    </ElTabs>

    <!-- 角色编辑对话框 -->
    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="660px" @close="formRef?.resetFields()">
      <ElForm ref="formRef" :model="form" :rules="roleRules" label-width="90px">
        <ElFormItem label="角色代码" prop="code">
          <ElInput v-model="form.code" :disabled="!!form.id" placeholder="如：workshop_admin" />
        </ElFormItem>
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="form.name" placeholder="请输入角色名称" />
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
            multiple check-strictly clearable
            placeholder="勾选可访问的组织节点"
            class="w-full"
          />
        </ElFormItem>
        <ElFormItem label="权限">
          <ElCheckboxGroup v-model="form.permissionCodes">
            <ElCheckbox v-for="p in permissions" :key="permCode(p)" :value="permCode(p)" :label="permCode(p)" />
          </ElCheckboxGroup>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitRole">确定</ElButton>
      </template>
    </ElDialog>

    <!-- 用户编辑对话框 -->
    <ElDialog v-model="userDialogVisible" :title="userDialogTitle" width="500px" @close="userFormRef?.resetFields()">
      <ElForm ref="userFormRef" :model="userForm" :rules="userForm.id ? userEditRules : userRules" label-width="80px">
        <ElFormItem label="用户名" prop="username">
          <ElInput v-model="userForm.username" :disabled="!!userForm.id" placeholder="登录用户名" />
        </ElFormItem>
        <ElFormItem v-if="!userForm.id" label="密码" prop="password">
          <ElInput v-model="userForm.password" type="password" placeholder="登录密码" show-password />
        </ElFormItem>
        <ElFormItem label="显示名">
          <ElInput v-model="userForm.display_name" placeholder="真实姓名" />
        </ElFormItem>
        <ElFormItem label="手机号" prop="phone">
          <ElInput v-model="userForm.phone" placeholder="可选" />
        </ElFormItem>
        <ElFormItem label="邮箱" prop="email">
          <ElInput v-model="userForm.email" placeholder="可选" />
        </ElFormItem>
        <ElFormItem label="角色" prop="role">
          <ElSelect v-model="userForm.role" class="w-full">
            <ElOption v-for="r in roleOptions" :key="r.value" :label="r.label" :value="r.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem v-if="userForm.id" label="状态">
          <ElSwitch v-model="userForm.is_active" />
          <span class="text-12px text-gray-400 ml-8px">{{ userForm.is_active ? '启用' : '停用' }}</span>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="userDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitUser">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
