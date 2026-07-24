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
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/dashboard/Index.vue'), meta: { title: '仪表盘', icon: 'Odometer', keepAlive: true } },
      { path: 'realtime', name: 'Realtime', component: () => import('../views/dashboard/Realtime.vue'), meta: { title: '实时数据', icon: 'DataBoard', keepAlive: true } },
      { path: 'screen', name: 'Screen', component: () => import('../views/dashboard/Screen.vue'), meta: { title: '数据大屏', icon: 'Monitor', keepAlive: true } },
      { path: 'devices', name: 'Devices', component: () => import('../views/devices/Index.vue'), meta: { title: '设备管理', icon: 'Cpu' } },
      { path: 'devices/:id', name: 'DeviceDetail', component: () => import('../views/devices/Detail.vue'), meta: { title: '设备详情', hidden: true } },
      { path: 'topology', name: 'Topology', component: () => import('../views/devices/Topology.vue'), meta: { title: '设备拓扑', icon: 'Share', keepAlive: true } },
      { path: 'tags', name: 'Tags', component: () => import('../views/tags/Index.vue'), meta: { title: '采集点位', icon: 'Connection' } },
      { path: 'groups', name: 'Groups', component: () => import('../views/groups/Index.vue'), meta: { title: '设备分组', icon: 'Files' } },
      { path: 'history', name: 'History', component: () => import('../views/history/Index.vue'), meta: { title: '历史数据', icon: 'DataLine' } },
      { path: 'alarms', name: 'Alarms', component: () => import('../views/alarms/Index.vue'), meta: { title: '报警管理', icon: 'Bell' } },
      { path: 'alarms/rules', name: 'AlarmRules', component: () => import('../views/alarms/Rules.vue'), meta: { title: '报警规则', hidden: true } },
      { path: 'control', name: 'Control', component: () => import('../views/control/Index.vue'), meta: { title: '远程控制', icon: 'Switch' } },
      { path: 'sms', name: 'Sms', component: () => import('../views/sms/Index.vue'), meta: { title: '短信管理', icon: 'Message' } },
      { path: 'audit', name: 'Audit', component: () => import('../views/audit/Index.vue'), meta: { title: '操作审计', icon: 'List' } },
      { path: 'exports', name: 'Exports', component: () => import('../views/exports/Index.vue'), meta: { title: '数据导出', icon: 'Download' } },
      { path: 'scada', name: 'Scada', component: () => import('../views/scada/Index.vue'), meta: { title: 'SCADA 画面', icon: 'Picture', keepAlive: true } },
      { path: 'scada/editor/:id', name: 'ScadaEditor', component: () => import('../views/scada/Editor.vue'), meta: { title: 'SCADA 编辑器', hidden: true } },
      { path: 'scada/view/:id', name: 'ScadaViewer', component: () => import('../views/scada/Viewer.vue'), meta: { title: 'SCADA 运行', hidden: true } },
      { path: 'scada/widgets', name: 'ScadaWidgets', component: () => import('../views/scada/Widgets.vue'), meta: { title: '自定义图元', hidden: true } },
      { path: 'scripts', name: 'Scripts', component: () => import('../views/scripts/Index.vue'), meta: { title: '脚本算法', icon: 'Document' } },
      { path: 'imports', name: 'Imports', component: () => import('../views/imports/Index.vue'), meta: { title: '批量导入', icon: 'Upload' } },
      { path: 'templates', name: 'Templates', component: () => import('../views/templates/Index.vue'), meta: { title: '设备模板', icon: 'Files' } },
      { path: 'archive', name: 'Archive', component: () => import('../views/settings/Archive.vue'), meta: { title: '数据归档', icon: 'FolderDelete' } },
      { path: 'rbac', name: 'RBAC', component: () => import('../views/rbac/Index.vue'), meta: { title: '权限管理', icon: 'Lock' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  // 切页时滚动复位到顶部，避免滚动位置残留造成的“跳动”观感
  scrollBehavior() {
    return { top: 0 }
  },
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
