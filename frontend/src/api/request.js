import axios from 'axios'
import { ElMessage } from 'element-plus'

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

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const msg = error.response?.data?.detail || error.response?.data?.message || error.message || '请求失败'
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default api
