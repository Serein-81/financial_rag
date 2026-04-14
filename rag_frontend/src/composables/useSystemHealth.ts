/**
 * 系统健康状态 Hook
 */

import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

interface ComponentHealth {
  name: string
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  latency_ms?: number
  message?: string
  details?: Record<string, any>
  last_check?: string
}

interface HealthReport {
  status: 'healthy' | 'degraded' | 'unhealthy'
  timestamp: string
  uptime_seconds: number
  components: ComponentHealth[]
  summary: {
    healthy: number
    degraded: number
    unhealthy: number
    total: number
  }
}

const healthApi = axios.create({
  baseURL: '/',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

healthApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('rag_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

healthApi.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('Health API Error:', error)
    return Promise.reject(error)
  }
)

export const useSystemHealth = () => {
  const healthReport = ref<HealthReport | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const fetchHealth = async () => {
    loading.value = true
    error.value = null

    try {
      const response = await healthApi.get<HealthReport>('health')
      healthReport.value = response.data
    } catch (err) {
      error.value = err instanceof Error ? err.message : '获取健康状态失败'
      ElMessage.error('获取系统健康状态失败')
      console.error('Failed to fetch system health:', err)
    } finally {
      loading.value = false
    }
  }

  const getComponentByName = (name: string) => {
    return healthReport.value?.components.find(c => c.name === name)
  }

  const getOverallStatus = () => {
    return healthReport.value?.status || 'unknown'
  }

  const getUptime = () => {
    if (!healthReport.value?.uptime_seconds) return '0小时 0分钟'
    const seconds = healthReport.value.uptime_seconds
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)
    
    if (hours > 24) {
      const days = Math.floor(hours / 24)
      return `${days}天 ${hours % 24}小时`
    }
    return `${hours}小时 ${minutes}分钟`
  }

  onMounted(() => {
    fetchHealth()
  })

  return {
    healthReport,
    loading,
    error,
    fetchHealth,
    getComponentByName,
    getOverallStatus,
    getUptime
  }
}
