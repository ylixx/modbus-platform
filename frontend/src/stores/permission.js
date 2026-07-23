/**
 * Permission store — dynamic route generation from backend permissions.
 *
 * On login:
 *   1. Fetch user permissions from /rbac/me/permissions
 *   2. Filter menu items based on permissions
 *   3. Generate accessible routes
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/request'

// Menu categories — render order + group title/icon for the sidebar.
export const MENU_CATEGORIES = [
  { key: 'monitor', title: '总览监控', icon: 'DataBoard' },
  { key: 'device', title: '设备中心', icon: 'Cpu' },
  { key: 'alarm', title: '报警与通知', icon: 'Bell' },
  { key: 'data', title: '数据运维', icon: 'Folder' },
  { key: 'system', title: '系统管理', icon: 'Setting' },
]

// All available menu items with required permissions
const ALL_MENUS = [
  { path: '/dashboard', title: '仪表盘', icon: 'Odometer', permission: null, category: 'monitor' },
  { path: '/realtime', title: '实时数据', icon: 'DataBoard', permission: 'device.read', category: 'monitor' },
  { path: '/screen', title: '数据大屏', icon: 'Monitor', permission: null, category: 'monitor' },
  { path: '/history', title: '历史数据', icon: 'DataLine', permission: 'history.read', category: 'monitor' },
  { path: '/devices', title: '设备管理', icon: 'Cpu', permission: 'device.read', category: 'device' },
  { path: '/topology', title: '设备拓扑', icon: 'Share', permission: 'device.read', category: 'device' },
  { path: '/groups', title: '设备分组', icon: 'Files', permission: 'group.read', category: 'device' },
  { path: '/tags', title: '采集点位', icon: 'Connection', permission: 'tag.read', category: 'device' },
  { path: '/scada', title: 'SCADA 画面', icon: 'Picture', permission: 'device.read', category: 'device' },
  { path: '/control', title: '远程控制', icon: 'Switch', permission: 'device.control', category: 'device' },
  { path: '/alarms', title: '报警管理', icon: 'Bell', permission: 'alarm.read', category: 'alarm' },
  { path: '/sms', title: '短信管理', icon: 'Message', permission: 'sms.read', category: 'alarm' },
  { path: '/exports', title: '数据导出', icon: 'Download', permission: 'export.download', category: 'data' },
  { path: '/scripts', title: '脚本算法', icon: 'Document', permission: 'device.write', category: 'data' },
  { path: '/imports', title: '批量导入', icon: 'Upload', permission: 'device.write', category: 'data' },
  { path: '/templates', title: '设备模板', icon: 'Files', permission: 'device.write', category: 'data' },
  { path: '/archive', title: '数据归档', icon: 'FolderDelete', permission: 'system.admin', category: 'data' },
  { path: '/audit', title: '操作审计', icon: 'List', permission: 'audit.read', category: 'system' },
  { path: '/rbac', title: '权限管理', icon: 'Lock', permission: 'rbac.read', category: 'system' },
]

export const usePermissionStore = defineStore('permission', () => {
  const menus = ref([])
  const permissions = ref(new Set())
  const dataScope = ref({ scope: 'all', values: [] })
  const roles = ref([])

  /**
   * Fetch permissions from backend and generate menu
   */
  async function fetchPermissions() {
    try {
      const res = await api.get('/rbac/me/permissions')
      permissions.value = new Set(res.data.permissions || [])
      dataScope.value = res.data.data_scope || { scope: 'all', values: [] }
      roles.value = res.data.roles || []
      generateMenus()
    } catch {
      // If RBAC endpoint fails, show all menus (fallback)
      menus.value = ALL_MENUS
    }
  }

  /**
   * Generate menus based on permissions
   */
  function generateMenus() {
    if (permissions.value.has('*')) {
      // Admin sees everything
      menus.value = ALL_MENUS
      return
    }
    menus.value = ALL_MENUS.filter(item => {
      if (!item.permission) return true  // No permission required
      return permissions.value.has(item.permission)
    })
  }

  /**
   * Check if user has a specific permission
   */
  function hasPermission(code) {
    if (permissions.value.has('*')) return true
    return permissions.value.has(code)
  }

  /**
   * Check if user has any of the given permissions
   */
  function hasAnyPermission(codes) {
    if (permissions.value.has('*')) return true
    return codes.some(c => permissions.value.has(c))
  }

  /**
   * Clear on logout
   */
  function $reset() {
    menus.value = []
    permissions.value = new Set()
    dataScope.value = { scope: 'all', values: [] }
    roles.value = []
  }

  return { menus, permissions, dataScope, roles, fetchPermissions, generateMenus, hasPermission, hasAnyPermission, $reset }
})
