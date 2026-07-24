<template>
  <div class="layout-container">
    <header class="layout-header">
      <div class="logo">
        <el-icon><Cpu /></el-icon>
        工业设备数据采集平台
      </div>
      <div class="header-right">
        <el-badge :value="activeAlarmCount" :hidden="activeAlarmCount === 0" class="alarm-badge">
          <el-button text style="color: #fff" @click="$router.push('/alarms')">
            <el-icon size="20"><Bell /></el-icon>
          </el-button>
        </el-badge>
        <el-tag v-if="wsConnected" type="success" size="small" effect="dark">实时连接</el-tag>
        <el-tag v-else type="info" size="small">离线</el-tag>
        <el-dropdown @command="handleCommand">
          <span style="color: #fff; cursor: pointer">
            <el-icon><User /></el-icon>
            {{ userStore.userInfo?.display_name || userStore.userInfo?.username }}
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="screen">数据大屏</el-dropdown-item>
              <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="layout-body">
      <aside class="layout-sidebar" :class="{ 'is-collapse': isCollapse }">
        <div class="sidebar-toggle" @click="isCollapse = !isCollapse" :title="isCollapse ? '展开菜单' : '收起菜单'">
          <el-icon size="18"><component :is="isCollapse ? 'Expand' : 'Fold'" /></el-icon>
        </div>
        <el-menu
          :default-active="$route.path"
          router
          :collapse="isCollapse"
          :collapse-transition="false"
          class="sidebar-menu"
        >
          <template v-for="group in groupedMenus" :key="group.key">
            <el-sub-menu :index="group.key">
              <template #title>
                <el-icon><component :is="group.icon" /></el-icon>
                <span>{{ group.title }}</span>
              </template>
              <el-menu-item
                v-for="item in group.children"
                :key="item.path"
                :index="item.path"
              >
                <el-icon><component :is="item.icon" /></el-icon>
                <span>{{ item.title }}</span>
              </el-menu-item>
            </el-sub-menu>
          </template>
        </el-menu>
      </aside>

      <main class="layout-content">
        <router-view v-slot="{ Component, route }">
          <transition name="fade">
            <keep-alive :include="cachedViews" :max="15">
              <component :is="Component" :key="route.name" />
            </keep-alive>
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { usePermissionStore, MENU_CATEGORIES } from '../stores/permission'
import api from '../api/request'

const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const activeAlarmCount = ref(0)
const wsConnected = ref(false)

// Sidebar collapse state (icon rail vs. full)
const isCollapse = ref(false)

// Dynamic menu from permission store, grouped by category
const menuItems = computed(() => permissionStore.menus)
const groupedMenus = computed(() =>
  MENU_CATEGORIES.map(cat => ({
    ...cat,
    children: menuItems.value.filter(m => m.category === cat.key),
  })).filter(g => g.children.length > 0)
)

// 仅缓存展示型页面（仪表盘/实时/大屏/拓扑/SCADA），列表页不缓存（避免切回显示旧数据）。
// keep-alive 必须「始终包裹」，不能用 v-if 在 keep-alive 与裸 component 之间切换——
// 否则跨缓存边界切页时 transition 的子节点类型突变，进入阶段收不到而整屏卡白。
// :include 匹配各缓存视图的组件 name（见各视图 defineOptions），与路由 name 一一对应。
const cachedViews = computed(() =>
  router.getRoutes()
    .filter(r => r.meta && r.meta.keepAlive)
    .map(r => r.name)
    .filter(Boolean)
)

let timer = null, ws = null

async function fetchAlarmCount() {
  try {
    const res = await api.get('/alarms/stats')
    activeAlarmCount.value = res.data.total_active || 0
  } catch {}
}

function connectWs() {
  const token = userStore.token
  if (!token) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${token}`)
  ws.onopen = () => { wsConnected.value = true }
  ws.onclose = () => {
    wsConnected.value = false
    setTimeout(connectWs, 5000)
  }
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'alarm_triggered') {
        activeAlarmCount.value = (activeAlarmCount.value || 0) + 1
      } else if (msg.type === 'alarm_cleared' || msg.type === 'alarm_acknowledged') {
        fetchAlarmCount()
      }
    } catch {}
  }
}

function handleCommand(cmd) {
  if (cmd === 'logout') {
    userStore.logout()
    permissionStore.$reset()
    router.push('/login')
  } else if (cmd === 'screen') {
    router.push('/screen')
  }
}

onMounted(async () => {
  await permissionStore.fetchPermissions()
  fetchAlarmCount()
  connectWs()
  timer = setInterval(fetchAlarmCount, 15000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
  ws?.close()
})
</script>

<style scoped>
.layout-sidebar {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
  border-right: 1px solid #ebeef5;
  transition: width 0.28s ease;
}
.layout-sidebar.is-collapse {
  width: 64px;
}
.sidebar-toggle {
  height: 42px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #606266;
  border-bottom: 1px solid #f0f0f0;
}
.sidebar-toggle:hover {
  background: #f5f7fa;
  color: #409eff;
}
.sidebar-menu {
  flex: 1;
  border-right: none !important;
  overflow-y: auto;
}
</style>

<style>
/* 路由切换淡入淡出：消除切页时内容区"白一下"的整屏刷新感 */
/* 去掉 mode="out-in"：默认模式下新页面立即挂载，避免与条件 keep-alive
   叠加时进入阶段永不触发而整屏卡白（跨缓存边界切页尤其明显）。 */
.layout-content {
  position: relative;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
/* 默认模式新旧组件会短暂共存；让离场元素脱离文档流，
   避免把新页面挤下去造成跳动（对齐 .layout-content 的 20px 内边距）。 */
.fade-leave-active {
  position: absolute;
  top: 20px;
  left: 20px;
  right: 20px;
}
</style>
