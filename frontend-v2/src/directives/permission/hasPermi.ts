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

// 存储被移除元素的占位注释节点，用于权限恢复时重新插入
const placeholderMap = new WeakMap<
  HTMLElement,
  { parent: Node; comment: Comment; nextSibling: Node | null }
>()

function applyPermission(el: HTMLElement, binding: DirectiveBinding) {
  const value = binding.value
  const flag = hasPermission(value)
  if (!flag) {
    // 权限不足：从 DOM 移除元素，防止 DevTools 绕过
    if (el.parentNode && !placeholderMap.has(el)) {
      const comment = document.createComment('v-hasPermi: removed')
      const parent = el.parentNode
      const nextSibling = el.nextSibling
      placeholderMap.set(el, { parent, comment, nextSibling })
      parent.replaceChild(comment, el)
    }
  } else {
    // 权限恢复：重新插入元素
    const info = placeholderMap.get(el)
    if (info) {
      info.parent.insertBefore(el, info.comment)
      info.parent.removeChild(info.comment)
      placeholderMap.delete(el)
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
