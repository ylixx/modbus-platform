import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import type { App } from 'vue'
import { Layout } from '@/utils/routerHelper'
import { useI18n } from '@/hooks/web/useI18n'
import { NO_RESET_WHITE_LIST } from '@/constants'

const { t } = useI18n()

export const constantRouterMap: AppRouteRecordRaw[] = [
  {
    path: '/',
    component: Layout,
    redirect: '/monitor/dashboard',
    name: 'Root',
    meta: {
      hidden: true
    }
  },
  {
    path: '/redirect',
    component: Layout,
    name: 'RedirectWrap',
    children: [
      {
        path: '/redirect/:path(.*)',
        name: 'Redirect',
        component: () => import('@/views/Redirect/Redirect.vue'),
        meta: {}
      }
    ],
    meta: {
      hidden: true,
      noTagsView: true
    }
  },
  {
    path: '/login',
    component: () => import('@/views/Login/Login.vue'),
    name: 'Login',
    meta: {
      hidden: true,
      title: t('router.login'),
      noTagsView: true
    }
  },
  {
    path: '/personal',
    component: Layout,
    redirect: '/personal/personal-center',
    name: 'Personal',
    meta: {
      title: t('router.personal'),
      hidden: true,
      canTo: true
    },
    children: [
      {
        path: 'personal-center',
        component: () => import('@/views/Personal/PersonalCenter/PersonalCenter.vue'),
        name: 'PersonalCenter',
        meta: {
          title: t('router.personalCenter'),
          hidden: true,
          canTo: true
        }
      }
    ]
  },
  {
    path: '/404',
    component: () => import('@/views/Error/404.vue'),
    name: 'NoFind',
    meta: {
      hidden: true,
      title: '404',
      noTagsView: true
    }
  }
]

export const asyncRouterMap: AppRouteRecordRaw[] = [
  {
    path: '/monitor',
    component: Layout,
    redirect: '/monitor/dashboard',
    name: 'Monitor',
    meta: {
      title: t('router.monitor'),
      icon: 'vi-ant-design:dashboard-filled',
      alwaysShow: true
    },
    children: [
      {
        path: 'dashboard',
        component: () => import('@/views/Monitor/Dashboard.vue'),
        name: 'Dashboard',
        meta: {
          title: t('router.dashboard'),
          icon: 'vi-ant-design:dashboard-outlined',
          permission: 'dashboard.read'
        }
      },
      {
        path: 'realtime',
        component: () => import('@/views/Monitor/Realtime.vue'),
        name: 'Realtime',
        meta: {
          title: t('router.realtime'),
          icon: 'vi-ant-design:fund-outlined',
          permission: 'dashboard.read'
        }
      },
      {
        path: 'live-dashboard',
        component: () => import('@/views/Monitor/LiveDashboard.vue'),
        name: 'LiveDashboard',
        meta: {
          title: '监控看板',
          icon: 'vi-ant-design:appstore-outlined',
          permission: 'dashboard.read'
        }
      },
      {
        path: 'screen',
        component: () => import('@/views/Monitor/Screen.vue'),
        name: 'Screen',
        meta: {
          title: t('router.screen'),
          icon: 'vi-ant-design:desktop-outlined',
          permission: 'dashboard.read'
        }
      }
    ]
  },
  {
    path: '/device',
    component: Layout,
    redirect: '/device/list',
    name: 'Device',
    meta: {
      title: t('router.device'),
      icon: 'vi-ant-design:hdd-outlined',
      alwaysShow: true
    },
    children: [
      {
        path: 'list',
        component: () => import('@/views/Device/Devices.vue'),
        name: 'Devices',
        meta: {
          title: t('router.deviceList'),
          icon: 'vi-ant-design:cluster-outlined',
          permission: 'device.read'
        }
      },
      {
        path: 'detail/:id',
        component: () => import('@/views/Device/DeviceDetail.vue'),
        name: 'DeviceDetail',
        meta: {
          title: t('router.deviceDetail'),
          hidden: true,
          canTo: true,
          noTagsView: false,
          activeMenu: '/device/list',
          permission: 'device.read'
        }
      },
      {
        path: 'detail/:id/tag/:tagId/chart',
        component: () => import('@/views/Device/TagChart.vue'),
        name: 'TagChart',
        meta: {
          title: '点位曲线',
          hidden: true,
          canTo: true,
          noTagsView: false,
          activeMenu: '/device/list',
          permission: 'device.read'
        }
      },
      {
        path: 'topology',
        component: () => import('@/views/Device/Topology.vue'),
        name: 'Topology',
        meta: {
          title: t('router.topology'),
          icon: 'vi-ant-design:share-alt-outlined',
          permission: 'device.read'
        }
      },
      {
        path: 'tags',
        component: () => import('@/views/Device/Tags.vue'),
        name: 'Tags',
        meta: {
          title: t('router.tags'),
          icon: 'vi-ant-design:api-outlined',
          permission: 'tag.read'
        }
      },
      {
        path: 'org',
        component: () => import('@/views/Device/Organization.vue'),
        name: 'Organization',
        meta: {
          title: t('router.org'),
          icon: 'vi-ant-design:apartment-outlined',
          permission: 'org.read'
        }
      },
      {
        path: 'templates',
        component: () => import('@/views/Device/Templates.vue'),
        name: 'Templates',
        meta: {
          title: t('router.templates'),
          icon: 'vi-ant-design:copy-outlined',
          permission: 'template.read'
        }
      },
      {
        path: 'batch-control',
        component: () => import('@/views/Alarm/BatchControl.vue'),
        name: 'BatchControl',
        meta: {
          title: '批量控制',
          icon: 'vi-ant-design:thunderbolt-outlined',
          permission: 'device.control'
        }
      }
    ]
  },
  {
    path: '/data',
    component: Layout,
    redirect: '/data/history',
    name: 'Data',
    meta: {
      title: t('router.data'),
      icon: 'vi-ant-design:line-chart-outlined',
      alwaysShow: true
    },
    children: [
      {
        path: 'history',
        component: () => import('@/views/Data/History.vue'),
        name: 'History',
        meta: {
          title: t('router.history'),
          icon: 'vi-ant-design:area-chart-outlined',
          permission: 'history.read'
        }
      },
      {
        path: 'exports',
        component: () => import('@/views/Data/Exports.vue'),
        name: 'Exports',
        meta: {
          title: t('router.exports'),
          icon: 'vi-ant-design:download-outlined',
          permission: 'export.download'
        }
      },
      {
        path: 'imports',
        component: () => import('@/views/Data/Imports.vue'),
        name: 'Imports',
        meta: {
          title: t('router.imports'),
          icon: 'vi-ant-design:upload-outlined',
          permission: 'import.read'
        }
      },
      {
        path: 'archive',
        component: () => import('@/views/Data/Archive.vue'),
        name: 'Archive',
        meta: {
          title: t('router.archive'),
          icon: 'vi-ant-design:database-outlined',
          permission: 'config.read'
        }
      },
      {
        path: 'forward',
        component: () => import('@/views/Data/DataForward.vue'),
        name: 'DataForward',
        meta: {
          title: '数据转发',
          icon: 'vi-ant-design:cloud-outlined',
          permission: 'device.read'
        }
      },
      {
        path: 'mqtt-status',
        component: () => import('@/views/Data/MqttStatus.vue'),
        name: 'MqttStatus',
        meta: {
          title: 'MQTT状态',
          icon: 'vi-ant-design:wifi-outlined',
          permission: 'device.read'
        }
      },
      {
        path: 'lab',
        component: () => import('@/views/Data/LabCompare.vue'),
        name: 'LabCompare',
        meta: {
          title: '化验对比',
          icon: 'vi-ant-design:experiment-outlined',
          permission: 'history.read'
        }
      }
    ]
  },
  {
    path: '/alarm',
    component: Layout,
    redirect: '/alarm/records',
    name: 'Alarm',
    meta: {
      title: t('router.alarm'),
      icon: 'vi-ant-design:alert-outlined',
      alwaysShow: true
    },
    children: [
      {
        path: 'records',
        component: () => import('@/views/Alarm/Alarms.vue'),
        name: 'Alarms',
        meta: {
          title: t('router.alarms'),
          icon: 'vi-ant-design:bell-outlined',
          permission: 'alarm.read'
        }
      },
      {
        path: 'rules',
        component: () => import('@/views/Alarm/AlarmRules.vue'),
        name: 'AlarmRules',
        meta: {
          title: t('router.alarmRules'),
          icon: 'vi-ant-design:profile-outlined',
          permission: 'alarm.read'
        }
      },
      {
        path: 'control',
        component: () => import('@/views/Alarm/Control.vue'),
        name: 'Control',
        meta: {
          title: t('router.control'),
          icon: 'vi-ant-design:control-outlined',
          permission: 'device.control'
        }
      },
      {
        path: 'sms',
        component: () => import('@/views/Alarm/Sms.vue'),
        name: 'Sms',
        meta: {
          title: t('router.sms'),
          icon: 'vi-ant-design:message-outlined',
          permission: 'sms.read'
        }
      },
      {
        path: 'mqtt',
        component: () => import('@/views/Alarm/AlarmMqtt.vue'),
        name: 'AlarmMqtt',
        meta: {
          title: 'MQTT推送',
          icon: 'vi-ant-design:send-outlined',
          permission: 'alarm.read'
        }
      }
    ]
  },
  {
    path: '/scada',
    component: Layout,
    redirect: '/scada/pages',
    name: 'Scada',
    meta: {
      title: t('router.scadaGroup'),
      icon: 'vi-ant-design:picture-outlined',
      alwaysShow: true
    },
    children: [
      {
        path: 'pages',
        component: () => import('@/views/Scada/Scada.vue'),
        name: 'ScadaPages',
        meta: {
          title: t('router.scada'),
          icon: 'vi-ant-design:fund-projection-screen-outlined',
          permission: 'scada.read'
        }
      },
      {
        path: 'editor/:id',
        component: () => import('@/views/Scada/ScadaEditor.vue'),
        name: 'ScadaEditor',
        meta: {
          title: t('router.scadaEditor'),
          hidden: true,
          canTo: true,
          activeMenu: '/scada/pages',
          permission: 'scada.write'
        }
      },
      {
        path: 'view/:id',
        component: () => import('@/views/Scada/ScadaViewer.vue'),
        name: 'ScadaViewer',
        meta: {
          title: t('router.scadaViewer'),
          hidden: true,
          canTo: true,
          activeMenu: '/scada/pages',
          permission: 'scada.read'
        }
      },
      {
        path: 'widgets',
        component: () => import('@/views/Scada/ScadaWidgets.vue'),
        name: 'ScadaWidgets',
        meta: {
          title: t('router.scadaWidgets'),
          icon: 'vi-ant-design:build-outlined',
          permission: 'scada.write'
        }
      }
    ]
  },
  {
    path: '/system',
    component: Layout,
    redirect: '/system/rbac',
    name: 'System',
    meta: {
      title: t('router.system'),
      icon: 'vi-ant-design:setting-outlined',
      alwaysShow: true
    },
    children: [
      {
        path: 'scripts',
        component: () => import('@/views/System/Scripts.vue'),
        name: 'Scripts',
        meta: {
          title: t('router.scripts'),
          icon: 'vi-ant-design:code-outlined',
          permission: 'script.read'
        }
      },
      {
        path: 'audit',
        component: () => import('@/views/System/Audit.vue'),
        name: 'Audit',
        meta: {
          title: t('router.audit'),
          icon: 'vi-ant-design:file-search-outlined',
          permission: 'audit.read'
        }
      },
      {
        path: 'rbac',
        component: () => import('@/views/System/Rbac.vue'),
        name: 'Rbac',
        meta: {
          title: t('router.rbac'),
          icon: 'vi-ant-design:lock-outlined',
          permission: 'rbac.read'
        }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  strict: true,
  routes: constantRouterMap as RouteRecordRaw[],
  scrollBehavior: () => ({ left: 0, top: 0 })
})

export const resetRouter = (): void => {
  router.getRoutes().forEach((route) => {
    const { name } = route
    if (name && !NO_RESET_WHITE_LIST.includes(name as string)) {
      router.hasRoute(name) && router.removeRoute(name)
    }
  })
}

export const setupRouter = (app: App<Element>) => {
  app.use(router)
}

export default router
