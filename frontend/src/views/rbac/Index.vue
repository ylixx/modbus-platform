<template>
  <div>
    <div class="page-header">
      <h2>权限管理</h2>
      <p>角色定义、权限分配、用户角色绑定（含数据范围）</p>
    </div>

    <el-tabs v-model="activeTab">
      <!-- Roles -->
      <el-tab-pane label="角色管理" name="roles">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>角色列表</span>
              <el-button type="primary" size="small" @click="showRoleDialog()"><el-icon><Plus /></el-icon> 新建角色</el-button>
            </div>
          </template>
          <el-table :data="rolePag.pagedRows" v-loading="loading" stripe>
            <el-table-column prop="code" label="代码" width="120" />
            <el-table-column prop="name" label="名称" width="140" />
            <el-table-column prop="description" label="描述" />
            <el-table-column label="权限" min-width="300">
              <template #default="{ row }">
                <el-tag v-for="p in row.permissions" :key="p.id" size="small" style="margin:2px">{{ p.name }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_system" label="系统角色" width="90">
              <template #default="{ row }"><el-tag v-if="row.is_system" type="warning" size="small">系统</el-tag></template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" @click="showRoleDialog(row)">编辑</el-button>
                <el-button size="small" type="danger" :disabled="row.is_system" @click="deleteRole(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            style="margin-top:12px; display:flex; justify-content:flex-end"
            layout="total, sizes, prev, pager, next, jumper"
            :total="rolePag.total"
            :page-size="rolePag.pageSize"
            :current-page="rolePag.currentPage"
            :page-sizes="[10, 20, 30, 50, 100]"
            @size-change="rolePag.onSizeChange"
            @current-change="rolePag.onPageChange"
          />
        </el-card>
      </el-tab-pane>

      <!-- User-Role Assignment -->
      <el-tab-pane label="用户角色分配" name="user-roles">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>用户角色分配</span>
              <el-button type="primary" size="small" @click="showAssignDialog()"><el-icon><Plus /></el-icon> 分配角色</el-button>
            </div>
          </template>
          <el-table :data="userPag.pagedRows" v-loading="loading" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="username" label="用户名" width="120" />
            <el-table-column prop="display_name" label="显示名" width="120" />
            <el-table-column label="已分配角色" min-width="300">
              <template #default="{ row }">
                <div v-for="ur in getUserRoles(row.id)" :key="ur.id" style="display:inline-block;margin:2px">
                  <el-tag closable @close="removeUserRole(ur.id)" size="small">
                    {{ ur.role_name }}
                    <span v-if="ur.data_scope !== 'all'"> ({{ scopeLabel(ur.data_scope) }}: {{ ur.scope_values.join(', ') || '-' }})</span>
                  </el-tag>
                </div>
                <span v-if="!getUserRoles(row.id).length" style="color:#999">未分配</span>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            style="margin-top:12px; display:flex; justify-content:flex-end"
            layout="total, sizes, prev, pager, next, jumper"
            :total="userPag.total"
            :page-size="userPag.pageSize"
            :current-page="userPag.currentPage"
            :page-sizes="[10, 20, 30, 50, 100]"
            @size-change="userPag.onSizeChange"
            @current-change="userPag.onPageChange"
          />
        </el-card>
      </el-tab-pane>

      <!-- Permissions List -->
      <el-tab-pane label="权限点" name="permissions">
        <el-card>
          <el-table :data="permPag.pagedRows" stripe>
            <el-table-column prop="code" label="权限代码" width="200"><template #default="{ row }"><code>{{ row.code }}</code></template></el-table-column>
            <el-table-column prop="name" label="名称" width="160" />
            <el-table-column prop="module" label="模块" width="100"><template #default="{ row }"><el-tag size="small">{{ row.module }}</el-tag></template></el-table-column>
            <el-table-column prop="description" label="描述" />
          </el-table>
          <el-pagination
            style="margin-top:12px; display:flex; justify-content:flex-end"
            layout="total, sizes, prev, pager, next, jumper"
            :total="permPag.total"
            :page-size="permPag.pageSize"
            :current-page="permPag.currentPage"
            :page-sizes="[10, 20, 30, 50, 100]"
            @size-change="permPag.onSizeChange"
            @current-change="permPag.onPageChange"
          />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Role Dialog -->
    <el-dialog v-model="roleDialogVisible" :title="editingRoleId ? '编辑角色' : '新建角色'" width="600px">
      <el-scrollbar max-height="60vh">
        <el-form :model="roleForm" label-width="80px" style="padding-right:20px">
          <el-form-item label="代码" required><el-input v-model="roleForm.code" :disabled="!!editingRoleId" /></el-form-item>
          <el-form-item label="名称" required><el-input v-model="roleForm.name" /></el-form-item>
          <el-form-item label="描述"><el-input v-model="roleForm.description" type="textarea" /></el-form-item>
          <el-form-item label="权限">
            <el-checkbox-group v-model="roleForm.permission_ids">
              <div v-for="(perms, module) in groupedPermissions" :key="module" style="margin-bottom:8px">
                <el-divider content-position="left">{{ module }}</el-divider>
                <el-checkbox v-for="p in perms" :key="p.id" :value="p.id">{{ p.name }}</el-checkbox>
              </div>
            </el-checkbox-group>
          </el-form-item>
        </el-form>
      </el-scrollbar>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>

    <!-- Assign Role Dialog -->
    <el-dialog v-model="assignDialogVisible" title="分配角色" width="500px">
      <el-form :model="assignForm" label-width="80px">
        <el-form-item label="用户" required>
          <el-select v-model="assignForm.user_id" placeholder="选择用户" style="width:100%">
            <el-option v-for="u in allUsers" :key="u.id" :label="`${u.username} (${u.display_name})`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="assignForm.role_id" placeholder="选择角色" style="width:100%">
            <el-option v-for="r in roles" :key="r.id" :label="`${r.name} (${r.code})`" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据范围">
          <el-select v-model="assignForm.data_scope" style="width:100%">
            <el-option label="全部数据" value="all" />
            <el-option label="指定厂级" value="factory" />
            <el-option label="指定区级" value="workshop" />
            <el-option label="仅自己" value="self" />
          </el-select>
        </el-form-item>
        <el-form-item label="范围值" v-if="['factory','workshop'].includes(assignForm.data_scope)">
          <el-select v-model="assignForm.scope_values" multiple filterable allow-create placeholder="输入或选择" style="width:100%">
            <el-option v-for="v in scopeOptions" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="assignRole">分配</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/request'
import { useClientPagination } from '../../composables/useClientPagination'

const activeTab = ref('roles')
const loading = ref(false)
const roles = ref([])
const permissions = ref([])
const allUsers = ref([])
const userRolesMap = ref({})
const scopeOptions = ref([])

const rolePag = reactive(useClientPagination(roles))
const userPag = reactive(useClientPagination(allUsers))
const permPag = reactive(useClientPagination(permissions))

const roleDialogVisible = ref(false)
const editingRoleId = ref(null)
const roleForm = reactive({ code: '', name: '', description: '', permission_ids: [] })

const assignDialogVisible = ref(false)
const assignForm = reactive({ user_id: null, role_id: null, data_scope: 'all', scope_values: [] })

const scopeLabel = (s) => ({ all: '全部', factory: '厂级', workshop: '区级', self: '仅自己' }[s] || s)
const groupedPermissions = computed(() => { const g = {}; for (const p of permissions.value) { (g[p.module] ??= []).push(p) } return g })
const getUserRoles = (uid) => userRolesMap.value[uid] || []

async function fetchAll() {
  loading.value = true
  const [r, p, u] = await Promise.all([api.get('/rbac/roles'), api.get('/rbac/permissions'), api.get('/users', { params: { page: 1, page_size: 100 } })])
  roles.value = r.data; permissions.value = p.data; allUsers.value = u.data.data || []
  for (const user of allUsers.value) { try { userRolesMap.value[user.id] = (await api.get(`/rbac/users/${user.id}/roles`)).data } catch { userRolesMap.value[user.id] = [] } }
  try { const loc = await api.get('/devices/locations'); scopeOptions.value = [...(loc.data.factories || []), ...(loc.data.workshops || [])] } catch {}
  loading.value = false
}

function showRoleDialog(role) {
  if (role) { editingRoleId.value = role.id; Object.assign(roleForm, { code: role.code, name: role.name, description: role.description, permission_ids: role.permissions.map(p => p.id) }) }
  else { editingRoleId.value = null; Object.assign(roleForm, { code: '', name: '', description: '', permission_ids: [] }) }
  roleDialogVisible.value = true
}

async function saveRole() {
  if (!roleForm.code || !roleForm.name) { ElMessage.warning('请填写必填字段'); return }
  if (editingRoleId.value) { await api.put(`/rbac/roles/${editingRoleId.value}`, roleForm) } else { await api.post('/rbac/roles', roleForm) }
  ElMessage.success('保存成功'); roleDialogVisible.value = false; fetchAll()
}

async function deleteRole(role) { await ElMessageBox.confirm(`确定删除角色 "${role.name}"？`); await api.delete(`/rbac/roles/${role.id}`); ElMessage.success('已删除'); fetchAll() }

function showAssignDialog() { Object.assign(assignForm, { user_id: null, role_id: null, data_scope: 'all', scope_values: [] }); assignDialogVisible.value = true }

async function assignRole() {
  if (!assignForm.user_id || !assignForm.role_id) { ElMessage.warning('请选择用户和角色'); return }
  await api.post(`/rbac/users/${assignForm.user_id}/roles`, assignForm); ElMessage.success('分配成功'); assignDialogVisible.value = false; fetchAll()
}

async function removeUserRole(urId) { await ElMessageBox.confirm('确定移除该角色？'); await api.delete(`/rbac/user-roles/${urId}`); ElMessage.success('已移除'); fetchAll() }

onMounted(fetchAll)
</script>
