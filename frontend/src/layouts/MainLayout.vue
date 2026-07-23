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
        <router-view />
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
