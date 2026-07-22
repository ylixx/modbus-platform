/**
 * usePermission composable — button-level permission control.
 *
 * Usage:
 *   const { hasPermission, hasAnyPermission } = usePermission()
 *
 *   <el-button v-if="hasPermission('device.control')">写入</el-button>
 *   <el-button v-if="hasAnyPermission(['alarm.ack', 'alarm.clear'])">处理</el-button>
 */
import { computed } from 'vue'
import { usePermissionStore } from '../stores/permission'

export function usePermission() {
  const permissionStore = usePermissionStore()

  function hasPermission(code) {
    return permissionStore.hasPermission(code)
  }

  function hasAnyPermission(codes) {
    return permissionStore.hasAnyPermission(codes)
  }

  function hasAllPermissions(codes) {
    return codes.every(c => permissionStore.hasPermission(c))
  }

  return { hasPermission, hasAnyPermission, hasAllPermissions }
}
