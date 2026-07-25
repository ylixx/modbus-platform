import type { App, Directive, DirectiveBinding } from 'vue'
import { useUserStoreWithOut } from '@/store/modules/user'

// 按钮级权限指令：v-hasPermi="['device.write']" 或 v-hasPermi="'device.write'"
// 依据当前登录用户拥有的权限码（userStore.permissions）判定，缺失则移除该元素。
const hasPermission = (value: string | string[]): boolean => {
  const userStore = useUserStoreWithOut()
  const permissions = (userStore.getPermissions || []) as string[]
  if (!value) return true
  const required = Array.isArray(value) ? value : [value]
  if (required.length === 0) return true
  // 拥有其中任意一个权限码即可展示
  return required.some((p) => permissions.includes(p))
}

function hasPermi(el: Element, binding: DirectiveBinding) {
  const value = binding.value
  const flag = hasPermission(value)
  if (!flag) {
    el.parentNode?.removeChild(el)
  }
}

const mounted = (el: Element, binding: DirectiveBinding<any>) => {
  hasPermi(el, binding)
}

const permiDirective: Directive = {
  mounted
}

export const setupPermissionDirective = (app: App<Element>) => {
  app.directive('hasPermi', permiDirective)
}

export default permiDirective
