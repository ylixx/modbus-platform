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
      <aside class="layout-sidebar">
        <el-menu :default-active="$route.path" router>
          <template v-for="item in menuItems" :key="item.path">
            <el-menu-item :index="item.path">
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </el-menu-item>
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
import { usePermissionStore } from '../stores/permission'
import api from '../api/request'

const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const activeAlarmCount = ref(0)
const wsConnected = ref(false)

// Dynamic menu from permission store
const menuItems = computed(() => permissionStore.menus)

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
