import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/dashboard/Index.vue'),
        meta: { title: '仪表盘', icon: 'Odometer' },
      },
      {
        path: 'devices',
        name: 'Devices',
        component: () => import('../views/devices/Index.vue'),
        meta: { title: '设备管理', icon: 'Cpu' },
      },
      {
        path: 'devices/:id',
        name: 'DeviceDetail',
        component: () => import('../views/devices/Detail.vue'),
        meta: { title: '设备详情', hidden: true },
      },
      {
        path: 'tags',
        name: 'Tags',
        component: () => import('../views/tags/Index.vue'),
        meta: { title: '采集点位', icon: 'Connection' },
      },
      {
        path: 'groups',
        name: 'Groups',
        component: () => import('../views/groups/Index.vue'),
        meta: { title: '设备分组', icon: 'Files' },
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('../views/history/Index.vue'),
        meta: { title: '历史数据', icon: 'DataLine' },
      },
      {
        path: 'alarms',
        name: 'Alarms',
        component: () => import('../views/alarms/Index.vue'),
        meta: { title: '报警管理', icon: 'Bell' },
      },
      {
        path: 'alarms/rules',
        name: 'AlarmRules',
        component: () => import('../views/alarms/Rules.vue'),
        meta: { title: '报警规则', hidden: true },
      },
      {
        path: 'control',
        name: 'Control',
        component: () => import('../views/control/Index.vue'),
        meta: { title: '远程控制', icon: 'Switch' },
      },
      {
        path: 'sms',
        name: 'Sms',
        component: () => import('../views/sms/Index.vue'),
        meta: { title: '短信管理', icon: 'Message' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  if (to.path !== '/login' && !userStore.token) {
    next('/login')
  } else {
    next()
  }
})

export default router
