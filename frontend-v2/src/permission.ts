import router from './router'
import type { RouteRecordRaw } from 'vue-router'
import { useTitle } from '@/hooks/web/useTitle'
import { useNProgress } from '@/hooks/web/useNProgress'
import { usePermissionStoreWithOut } from '@/store/modules/permission'
import { usePageLoading } from '@/hooks/web/usePageLoading'
import { NO_REDIRECT_WHITE_LIST } from '@/constants'
import { useUserStoreWithOut } from '@/store/modules/user'
import { useWsStoreWithOut } from '@/store/modules/websocket'

const { start, done } = useNProgress()

const { loadStart, loadDone } = usePageLoading()

let wsInitialized = false

router.beforeEach(async (to, from, next) => {
  start()
  loadStart()
  const permissionStore = usePermissionStoreWithOut()
  const userStore = useUserStoreWithOut()
  if (userStore.getUserInfo) {
    // 已登录：确保 WebSocket 已连接
    if (!wsInitialized) {
      const wsStore = useWsStoreWithOut()
      wsStore.init()
      wsInitialized = true
    }

    if (to.path === '/login') {
      next({ path: '/' })
    } else {
      if (permissionStore.getIsAddRouters) {
        next()
        return
      }

      // 前端静态路由 + 后端权限码过滤
      const permissions = userStore.getPermissions || []
      await permissionStore.generateRoutes('permission', permissions)

      permissionStore.getAddRouters.forEach((route) => {
        router.addRoute(route as unknown as RouteRecordRaw) // 动态添加可访问路由表
      })
      const redirectPath = from.query.redirect || to.path
      const redirect = decodeURIComponent(redirectPath as string)
      const nextData = to.path === redirect ? { ...to, replace: true } : { path: redirect }
      permissionStore.setIsAddRouters(true)
      next(nextData)
    }
  } else {
    // 未登录：断开 WebSocket
    if (wsInitialized) {
      const wsStore = useWsStoreWithOut()
      wsStore.destroy()
      wsInitialized = false
    }

    if (NO_REDIRECT_WHITE_LIST.indexOf(to.path) !== -1) {
      next()
    } else {
      next(`/login?redirect=${to.path}`) // 否则全部重定向到登录页
    }
  }
})

router.afterEach((to) => {
  useTitle(to?.meta?.title as string)
  done() // 结束Progress
  loadDone()
})
