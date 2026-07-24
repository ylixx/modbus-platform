import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 防止并发 401 时重复跳转登录页（之前用 window.location.href 会导致整页刷新）
let redirecting = false

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const msg = error.response?.data?.detail || error.response?.data?.message || error.message || '请求失败'
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      const onLogin = router.currentRoute.value.path.includes('/login')
      if (!redirecting && !onLogin) {
        redirecting = true
        ElMessage.warning('登录状态已失效，请重新登录')
        router.push('/login').finally(() => { redirecting = false })
      }
      return Promise.reject(error)
    }
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default api
