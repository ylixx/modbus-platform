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
let lastMeCheck = 0
const ME_CHECK_INTERVAL = 60_000 // 60s 内不重复调 getMeApi

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

    // 节流：60s 内只调一次 getMeApi
    const now = Date.now()
    if (now - lastMeCheck > ME_CHECK_INTERVAL) {
      lastMeCheck = now
      try {
        const res = await getMeApi()
        if (res?.data) {
          const newPerms = res.data.permissions || []
          const oldPerms = userStore.getPermissions || []
          // 权限变更时重置路由缓存，强制重新生成
          const permsChanged =
            newPerms.length !== oldPerms.length ||
            newPerms.some((p: string, i: number) => p !== oldPerms[i])
          if (permsChanged && permissionStore.getIsAddRouters) {
            permissionStore.setIsAddRouters(false)
          }
          userStore.setUserInfo(res.data)
          userStore.setPermissions(newPerms)
        }
      } catch (e: any) {
        // 401 / 403 → token 失效，跳登录
        const status = e?.response?.status
        if (status === 401 || status === 403) {
          userStore.reset()
          next(`/login?redirect=${to.path}`)
          return
        }
        // 其他错误（网络波动等）静默继续，不影响导航
      }
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
