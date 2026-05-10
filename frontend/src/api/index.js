import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    if (err.response?.status === 401) {
      // 如果当前不在登录页，清除凭据并跳转
      if (!window.location.pathname.startsWith('/login')) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        window.location.href = '/login'
      }
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(err)
  }
)

export default api
