/**
 * Axios 请求工具 - 全局拦截器 + 统一请求函数 + 认证函数
 */

import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

function normalizeApiBase(base?: string): string {
  if (!base) return '/api/v1'
  const trimmed = base.replace(/\/+$/, '')
  return trimmed.endsWith('/api/v1') ? trimmed : `${trimmed}/api/v1`
}

const API_BASE_URL = normalizeApiBase(
  import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE
)

// 获取 token
export function getToken(): string | null {
  return localStorage.getItem('rag_token')
}

// 检查是否已认证
export function isAuthenticated(): boolean {
  return !!getToken()
}

// 从 JWT token 中解码获取用户 ID
export function getUserIdFromToken(): string | null {
  const token = getToken()
  if (!token) return null

  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    const payload = JSON.parse(jsonPayload)
    return payload.sub || null
  } catch (error) {
    console.error('Failed to decode token:', error)
    return null
  }
}

// 从 JWT token 中解码获取租户 ID
export function getTenantIdFromToken(): string | null {
  const token = getToken()
  if (!token) return null

  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    const payload = JSON.parse(jsonPayload)
    return payload.tenant_id || null
  } catch (error) {
    console.error('Failed to decode tenant_id from token:', error)
    return null
  }
}

// 获取企业 ID（优先从 token 获取 tenant_id）
export function getEnterpriseId(): string {
  const fromToken = getTenantIdFromToken()
  if (fromToken && fromToken !== 'undefined') {
    return fromToken
  }
  const fromStorage = localStorage.getItem('enterprise_id')
  if (fromStorage && fromStorage !== 'undefined') {
    return fromStorage
  }
  return 'default'
}

// 创建全局 axios 实例
const instance = axios.create({
  baseURL: API_BASE_URL,
})

// 全局请求拦截器
instance.interceptors.request.use(
  (config: any) => {
    const token = getToken()
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
      console.log(`[REQUEST] URL: ${config.url}, Token set, length: ${token.length}`)
      console.log(`[REQUEST] Authorization header: Bearer ${token.substring(0, 30)}...`)
    } else {
      console.log(`[REQUEST] URL: ${config.url}, No token found!`)
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 全局响应拦截器
instance.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const errorMessage = error.response?.data?.detail ||
                         error.response?.data?.message ||
                         error.message

    if (status === 401) {
      localStorage.removeItem('rag_token')
      localStorage.removeItem('user')

      ElMessage.error({
        message: '登录已过期，请重新登录',
        duration: 3000,
        onClose: () => {
          router.push('/login')
        }
      })
    } else if (status === 403) {
      if (errorMessage?.includes('tenant')) {
        localStorage.removeItem('rag_token')
        localStorage.removeItem('user')
        ElMessage.error({
          message: '会话无效，请重新登录',
          duration: 3000,
          onClose: () => {
            router.push('/login')
          }
        })
      } else {
        console.warn(`[REQUEST] 权限错误 (403): ${errorMessage}`)
      }
    }
    else if (status === 500) {
      ElMessage.error({
        message: '服务器错误，请稍后重试',
        duration: 3000
      })
    }
    else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      ElMessage.error({
        message: '请求超时，请检查网络连接',
        duration: 3000
      })
    }
    else if (status) {
      let friendlyMessage = errorMessage || '请求失败'

      if (friendlyMessage.includes('文件为空')) {
        friendlyMessage = `⚠️ 上传失败：${friendlyMessage}`
      }

      ElMessage.error({
        message: friendlyMessage,
        duration: 5000
      })
    }

    return Promise.reject(error)
  }
)

export async function request<T = any>(
  url: string,
  config: any = {}
): Promise<T> {
  const response = await instance.request<T>({
    url,
    baseURL: API_BASE_URL,
    timeout: 120000,
    headers: {
      'Content-Type': 'application/json',
      ...(config.headers || {}),
    },
    ...config,
  })
  return response.data
}

export async function requestForm<T = any>(
  url: string,
  formData: FormData,
  config: any = {}
): Promise<T> {
  const response = await instance.request<T>({
    url,
    baseURL: API_BASE_URL,
    method: 'POST',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data',
      ...(config.headers || {}),
    },
    ...config,
  })
  return response.data
}

export function get<T = any>(url: string, config: any = {}): Promise<T> {
  return request<T>(url, { ...config, method: 'GET' })
}

export function post<T = any>(url: string, data?: any, config: any = {}): Promise<T> {
  return request<T>(url, { ...config, method: 'POST', data })
}

export function put<T = any>(url: string, data?: any, config: any = {}): Promise<T> {
  return request<T>(url, { ...config, method: 'PUT', data })
}

export function del<T = any>(url: string, config: any = {}): Promise<T> {
  return request<T>(url, { ...config, method: 'DELETE' })
}

export async function login(identifier: string, password: string): Promise<{
  access_token: string
  token_type: string
  user_name: string
  avatar_url?: string
}> {
  const isEmail = identifier.includes('@')
  const loginData = isEmail 
    ? { email: identifier, password: password }
    : { username: identifier, password: password }
  
  const data = await request<{
    access_token: string
    token_type: string
    user_name: string
    avatar_url?: string
  }>('/auth/login', {
    method: 'POST',
    data: loginData
  })

  localStorage.setItem('rag_token', data.access_token)
  localStorage.setItem('rag_user_name', data.user_name)
  if (data.avatar_url) {
    localStorage.setItem('rag_avatar_url', data.avatar_url)
  }

  return data
}

export async function register(
  email: string,
  password: string,
  full_name: string,
  invite_code?: string,
  phone?: string
): Promise<{
  access_token: string
  token_type: string
  user_name: string
  avatar_url?: string
}> {
  const response = await instance.post<{
    access_token: string
    token_type: string
    user_name: string
    avatar_url?: string
  }>('/auth/register', {
    email,
    password,
    full_name,
    invite_code,
    phone
  })

  const data = response.data
  localStorage.setItem('rag_token', data.access_token)
  localStorage.setItem('rag_user_name', data.user_name)
  if (data.avatar_url) {
    localStorage.setItem('rag_avatar_url', data.avatar_url)
  }

  return data
}

export async function registerAdmin(
  email: string,
  password: string,
  full_name: string,
  company_name: string,
  phone?: string
): Promise<{
  access_token: string
  token_type: string
  user_name: string
  avatar_url?: string
}> {
  const response = await instance.post<{
    access_token: string
    token_type: string
    user_name: string
    avatar_url?: string
  }>('/auth/register/admin', {
    email,
    password,
    full_name,
    company_name,
    phone
  })

  const data = response.data
  localStorage.setItem('rag_token', data.access_token)
  localStorage.setItem('rag_user_name', data.user_name)
  if (data.avatar_url) {
    localStorage.setItem('rag_avatar_url', data.avatar_url)
  }

  return data
}

export function logout(): void {
  localStorage.removeItem('rag_token')
  localStorage.removeItem('rag_user_name')
  localStorage.removeItem('rag_user_email')
  localStorage.removeItem('rag_avatar_url')
  localStorage.removeItem('rag_user_role')
  router.push('/login')
}

export default instance
