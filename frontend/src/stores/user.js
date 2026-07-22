import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/request'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => userInfo.value?.role === 'admin')

  async function login(username, password) {
    const res = await api.post('/auth/login', { username, password })
    token.value = res.data.access_token
    userInfo.value = res.data.user
    localStorage.setItem('token', token.value)
    localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
    return res.data
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
  }

  return { token, userInfo, isLoggedIn, isAdmin, login, logout }
})
