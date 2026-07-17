<template>
  <div class="layout-container">
    <header class="layout-header">
      <div class="logo">
        <el-icon><Cpu /></el-icon>
        Modbus 数据采集平台
      </div>
      <div class="header-right">
        <el-badge :value="activeAlarmCount" :hidden="activeAlarmCount === 0" class="alarm-badge">
          <el-button text style="color: #fff" @click="$router.push('/alarms')">
            <el-icon size="20"><Bell /></el-icon>
          </el-button>
        </el-badge>
        <el-dropdown @command="handleCommand">
          <span style="color: #fff; cursor: pointer">
            <el-icon><User /></el-icon>
            {{ userStore.userInfo?.display_name || userStore.userInfo?.username }}
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="layout-body">
      <aside class="layout-sidebar">
        <el-menu
          :default-active="$route.path"
          router
        >
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
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import api from '../api/request'

const router = useRouter()
const userStore = useUserStore()
const activeAlarmCount = ref(0)

const menuItems = [
  { path: '/dashboard', title: '仪表盘', icon: 'Odometer' },
  { path: '/devices', title: '设备管理', icon: 'Cpu' },
  { path: '/groups', title: '设备分组', icon: 'Files' },
  { path: '/tags', title: '采集点位', icon: 'Connection' },
  { path: '/history', title: '历史数据', icon: 'DataLine' },
  { path: '/alarms', title: '报警管理', icon: 'Bell' },
  { path: '/control', title: '远程控制', icon: 'Switch' },
  { path: '/sms', title: '短信管理', icon: 'Message' },
]

let timer = null

async function fetchAlarmCount() {
  try {
    const res = await api.get('/alarms/stats')
    activeAlarmCount.value = res.data.total_active || 0
  } catch (e) {
    // ignore
  }
}

function handleCommand(cmd) {
  if (cmd === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}

onMounted(() => {
  fetchAlarmCount()
  timer = setInterval(fetchAlarmCount, 15000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
