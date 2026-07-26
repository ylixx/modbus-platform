import type { App, Directive, DirectiveBinding } from 'vue'
import { useUserStoreWithOut } from '@/store/modules/user'

const hasPermission = (value: string | string[]): boolean => {
  const userStore = useUserStoreWithOut()
  const permissions = (userStore.getPermissions || []) as string[]
  if (!value) return true
  const required = Array.isArray(value) ? value : [value]
  if (required.length === 0) return true
  return required.some((p) => permissions.includes(p))
}

function applyPermission(el: HTMLElement, binding: DirectiveBinding) {
  const value = binding.value
  const flag = hasPermission(value)
  if (!flag) {
    el.style.display = 'none'
    el.setAttribute('data-has-permi', 'false')
  } else {
    if (el.getAttribute('data-has-permi') === 'false') {
      el.style.display = ''
      el.removeAttribute('data-has-permi')
    }
  }
}

const mounted = (el: HTMLElement, binding: DirectiveBinding) => {
  applyPermission(el, binding)
}

const updated = (el: HTMLElement, binding: DirectiveBinding) => {
  applyPermission(el, binding)
}

const permiDirective: Directive = {
  mounted,
  updated
}

export const setupPermissionDirective = (app: App<Element>) => {
  app.directive('hasPermi', permiDirective)
}

export default permiDirective
