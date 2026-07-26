import router from './router'
import type { RouteRecordRaw } from 'vue-router'
import { useTitle } from '@/hooks/web/useTitle'
import { useNProgress } from '@/hooks/web/useNProgress'
import { usePermissionStoreWithOut } from '@/store/modules/permission'
import { usePageLoading } from '@/hooks/web/usePageLoading'
import { NO_REDIRECT_WHITE_LIST } from '@/constants'
import { useUserStoreWithOut } from '@/store/modules/user'
import { useWsStoreWithOut } from '@/store/modules/websocket'
import { getMeApi } from '@/api/login'

const { start, done } = useNProgress()

const { loadStart, loadDone } = usePageLoading()

let wsInitialized = false

router.beforeEach(async (to, from, next) => {
  start()
  loadStart()
  const permissionStore = usePermissionStoreWithOut()
  const userStore = useUserStoreWithOut()

  if (userStore.getUserInfo) {
    if (!wsInitialized) {
      const wsStore = useWsStoreWithOut()
      wsStore.init()
      wsInitialized = true
    }

    if (to.path === '/login') {
      next({ path: '/' })
      return
    }

    try {
      const res = await getMeApi()
      if (res?.data) {
        userStore.setUserInfo(res.data)
        userStore.setPermissions(res.data.permissions || [])
      }
    } catch (_) {
      // token might be expired, let the interceptor handle it
    }

    if (permissionStore.getIsAddRouters) {
      next()
      return
    }

    const permissions = userStore.getPermissions || []
    await permissionStore.generateRoutes('permission', permissions)

    const addRouters = permissionStore.getAddRouters
    addRouters.forEach((route) => {
      router.addRoute(route as unknown as RouteRecordRaw)
    })

    if (router.hasRoute('TempCatchAll')) {
      router.removeRoute('TempCatchAll')
    }

    const redirectPath = (from.query.redirect || to.path) as string
    const redirect = decodeURIComponent(redirectPath)
    const nextData = to.path === redirect ? { ...to, replace: true } : { path: redirect }
    permissionStore.setIsAddRouters(true)
    next(nextData)
  } else {
    if (wsInitialized) {
      const wsStore = useWsStoreWithOut()
      wsStore.destroy()
      wsInitialized = false
    }

    if (NO_REDIRECT_WHITE_LIST.indexOf(to.path) !== -1) {
      next()
    } else {
      next(`/login?redirect=${to.path}`)
    }
  }
})

router.afterEach((to) => {
  useTitle(to?.meta?.title as string)
  done()
  loadDone()
})
