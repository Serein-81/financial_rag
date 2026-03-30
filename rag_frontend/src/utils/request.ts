/**
 * Axios 请求工具 - 全局拦截器 + 统一请求函数 + 认证函数
 */

import axios, { AxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

// 获取 token
export function getToken(): string | null {
  return localStorage.getItem('rag_token')
}

// 检查是否已认证
export function isAuthenticated(): boolean {
  return !!getToken()
}

// 创建全局 axios 实例
const instance = axios.create()

// 全局请求拦截器
instance.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
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

    // 认证错误
    if (status === 401 || status === 403) {
      localStorage.removeItem('rag_token')
      localStorage.removeItem('user')
      
      const message = status === 401 
        ? '登录已过期，请重新登录' 
        : (errorMessage?.includes('tenant') ? '会话无效，请重新登录' : '登录已过期，请重新登录')
      
      ElMessage.error({
        message,
        duration: 3000,
        onClose: () => {
          router.push('/login')
        }
      })
    } 
    // 服务器错误
    else if (status === 500) {
      ElMessage.error({
        message: '服务器错误，请稍后重试',
        duration: 3000
      })
    }
    // 网络错误
    else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      ElMessage.error({
        message: '请求超时，请检查网络连接',
        duration: 3000
      })
    }
    // 其他错误
    else if (status) {
      ElMessage.error({
        message: errorMessage || '请求失败',
        duration: 3000
      })
    }
    
    return Promise.reject(error)
  }
)

// 通用的 request 函数
export function request<T = any>(
  url: string,
  config: AxiosRequestConfig = {}
): Promise<T> {
  return instance.request<T>({
    url,
    baseURL: '/api/v1',
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
      ...config.headers,
    },
    ...config,
  }).then((response: AxiosResponse<T>) => response.data)
}

// 表单请求函数
export function requestForm<T = any>(
  url: string,
  formData: FormData,
  config: AxiosRequestConfig = {}
): Promise<T> {
  return instance.request<T>({
    url,
    baseURL: '/api/v1',
    method: 'POST',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data',
      ...config.headers,
    },
    ...config,
  }).then((response: AxiosResponse<T>) => response.data)
}

// 登录函数
export async function login(email: string, password: string): Promise<{
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
  }>('/auth/login', {
    email: email,
    password: password
  })
  
  const data = response.data
  localStorage.setItem('rag_token', data.access_token)
  localStorage.setItem('rag_user_name', data.user_name)
  if (data.avatar_url) {
    localStorage.setItem('rag_avatar_url', data.avatar_url)
  }
  
  return data
}

// 注册函数
export async function register(
  email: string, 
  password: string, 
  full_name: string, 
  invite_code?: string
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
  }>('/api/v1/auth/register', {
    email,
    password,
    full_name,
    invite_code
  })
  
  const data = response.data
  localStorage.setItem('rag_token', data.access_token)
  localStorage.setItem('rag_user_name', data.user_name)
  if (data.avatar_url) {
    localStorage.setItem('rag_avatar_url', data.avatar_url)
  }
  
  return data
}

// 企业管理员注册
export async function registerAdmin(
  email: string, 
  password: string, 
  full_name: string, 
  company_name: string
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
  }>('/api/v1/auth/register/admin', {
    email,
    password,
    full_name,
    company_name
  })
  
  const data = response.data
  localStorage.setItem('rag_token', data.access_token)
  localStorage.setItem('rag_user_name', data.user_name)
  if (data.avatar_url) {
    localStorage.setItem('rag_avatar_url', data.avatar_url)
  }
  
  return data
}

// 登出函数
export function logout(): void {
  localStorage.removeItem('rag_token')
  localStorage.removeItem('rag_user_name')
  localStorage.removeItem('rag_user_email')
  localStorage.removeItem('rag_avatar_url')
  localStorage.removeItem('rag_user_role')
  router.push('/login')
}

export default instance
