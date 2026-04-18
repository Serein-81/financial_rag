/**
 * 工作流监控 API 客户端
 * 具有鲁棒的错误处理机制，支持租户上下文错误处理
 */

import axios, { type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import { API_BASE } from '@/config/api'

const API_BASE_URL = `${API_BASE}/api/v1`

/**
 * 防止重复登录提示的状态管理
 */
let isShowingReloginMessage = false
let lastReloginTimestamp = 0
const RELOGIN_COOLDOWN_MS = 5000 // 5秒内不重复提示

const workflowApi = axios.create<any>({
  baseURL: API_BASE_URL,
  timeout: 30000,
})

workflowApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('rag_token')
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/**
 * 认证错误类型枚举（与后端保持一致）
 */
enum AuthErrorType {
  NO_TOKEN = 'no_token',
  TOKEN_EXPIRED = 'token_expired',
  TOKEN_INVALID = 'token_invalid',
  TENANT_MISSING = 'tenant_missing',
  TENANT_INACTIVE = 'tenant_inactive',
  USER_NOT_FOUND = 'user_not_found',
  PERMISSION_DENIED = 'permission_denied',
  UNKNOWN_ERROR = 'unknown_error'
}

/**
 * 认证错误消息映射
 */
const AuthErrorMessages: Record<AuthErrorType, string> = {
  [AuthErrorType.NO_TOKEN]: '请先登录',
  [AuthErrorType.TOKEN_EXPIRED]: '登录已过期，请重新登录',
  [AuthErrorType.TOKEN_INVALID]: '登录会话无效，请重新登录',
  [AuthErrorType.TENANT_MISSING]: '会话已失效，请重新登录',
  [AuthErrorType.TENANT_INACTIVE]: '租户账户已被禁用',
  [AuthErrorType.USER_NOT_FOUND]: '用户不存在',
  [AuthErrorType.PERMISSION_DENIED]: '权限不足，无法访问该资源',
  [AuthErrorType.UNKNOWN_ERROR]: '认证失败，请稍后重试'
}

/**
 * 从错误响应中提取错误类型
 */
function extractErrorType(error: any): AuthErrorType | null {
  // 优先从 error_type 字段获取（后端新版响应）
  if (error.response?.data?.error_type) {
    const errorType = error.response.data.error_type as string
    if (Object.values(AuthErrorType).includes(errorType as AuthErrorType)) {
      return errorType as AuthErrorType
    }
  }
  
  // 从错误消息推断（兼容旧版响应）
  const errorMessage = error.response?.data?.detail || 
                       error.response?.data?.message ||
                       error.message
  
  if (!errorMessage) return null
  
  const lowerMessage = errorMessage.toLowerCase()
  
  if (lowerMessage.includes('tenant') || 
      lowerMessage.includes('租户') ||
      lowerMessage.includes('missing tenant')) {
    return AuthErrorType.TENANT_MISSING
  }
  
  if (lowerMessage.includes('expired') || 
      lowerMessage.includes('过期')) {
    return AuthErrorType.TOKEN_EXPIRED
  }
  
  if (lowerMessage.includes('invalid') || 
      lowerMessage.includes('无效')) {
    return AuthErrorType.TOKEN_INVALID
  }
  
  if (lowerMessage.includes('no token') || 
      lowerMessage.includes('authentication required')) {
    return AuthErrorType.NO_TOKEN
  }
  
  return null
}

/**
 * 安全地处理认证错误，显示登录提示
 */
function handleAuthError(error?: any): void {
  // 防止重复提示
  const now = Date.now()
  if (isShowingReloginMessage || (now - lastReloginTimestamp < RELOGIN_COOLDOWN_MS)) {
    return
  }
  
  // 检查是否已经在登录页
  if (window.location.pathname === '/login') {
    return
  }
  
  isShowingReloginMessage = true
  lastReloginTimestamp = now
  
  // 清除本地认证信息
  localStorage.removeItem('rag_token')
  localStorage.removeItem('user')
  
  // 根据错误类型获取精确的消息
  let message = '登录已过期，请重新登录'
  
  if (error) {
    const errorType = extractErrorType(error)
    if (errorType && AuthErrorMessages[errorType]) {
      message = AuthErrorMessages[errorType]
    }
  }
  
  ElMessage.error({
    message,
    duration: 3000,
    onClose: () => {
      isShowingReloginMessage = false
      window.location.href = '/login'
    }
  })
}

workflowApi.interceptors.response.use(
  (response) => response,
  (error) => {
    // 安全获取错误信息
    const status = error.response?.status
    const errorMessage = error.response?.data?.detail || 
                         error.response?.data?.message || 
                         error.message

    // 处理 401 未授权错误
    if (status === 401) {
      handleAuthError(error)
      return Promise.reject(error)
    }
    
    // 处理 403 禁止访问错误
    if (status === 403) {
      // 区分 tenant context 错误和普通权限错误
      const errorType = extractErrorType(error)
      if (errorType === AuthErrorType.TENANT_MISSING || 
          errorType === AuthErrorType.TENANT_INACTIVE ||
          errorType === AuthErrorType.TOKEN_INVALID) {
        // Tenant context 缺失或租户无效，视为未登录处理
        handleAuthError(error)
      } else {
        // 其他 403 错误（如权限不足）
        ElMessage.error({
          message: errorMessage || '权限不足，无法访问该资源',
          duration: 3000
        })
      }
      return Promise.reject(error)
    }
    
    // 处理 500 服务器错误
    if (status === 500) {
      ElMessage.error({
        message: '服务器错误，请稍后重试',
        duration: 3000
      })
      return Promise.reject(error)
    }
    
    // 处理其他错误（如网络错误、超时等）
    if (!error.response) {
      console.error('[Workflow API] Network error:', error.message)
      ElMessage.error({
        message: '网络连接失败，请检查网络',
        duration: 3000
      })
    }
    
    return Promise.reject(error)
  }
)

/**
 * 工作流追踪记录
 */
export interface WorkflowTrace {
  id: string
  workflow_type: string
  workflow_version?: string
  session_id?: string
  tenant_id?: string
  user_id?: string
  status: 'running' | 'completed' | 'failed'
  total_nodes: number
  completed_nodes: number
  current_node?: string
  metadata?: Record<string, any>
  started_at: string
  completed_at?: string
  duration?: number
  error_message?: string
}

/**
 * 工作流节点执行记录
 */
export interface WorkflowNodeExecution {
  id: string
  workflow_trace_id: string
  node_name: string
  node_type: string
  execution_order: number
  status: 'running' | 'completed' | 'failed'
  input_data?: Record<string, any>
  output_data?: Record<string, any>
  error_message?: string
  started_at: string
  completed_at?: string
  duration?: number
}

/**
 * 人工审核追踪记录
 */
export interface HumanReviewTracking {
  id: string
  task_id?: string
  tenant_id?: string
  user_id?: string
  title?: string
  description?: string
  review_type: string
  priority: 'low' | 'normal' | 'high' | 'urgent'
  status: 'pending' | 'in_progress' | 'completed' | 'rejected' | 'cancelled'
  trigger_reason?: string
  content?: Record<string, any>
  document_ids?: string[]
  assigned_to?: string
  assigned_at?: string
  review_result?: Record<string, any>
  review_comments?: string
  reviewed_at?: string
  sla_deadline?: string
  created_at: string
  updated_at?: string
  is_overdue: boolean
  age_hours: number
}

/**
 * 人工审核动作记录
 */
export interface ReviewActionRecord {
  id: string
  tracking_id: string
  action: string
  actor_id?: string
  actor_name?: string
  comment?: string
  created_at: string
}

/**
 * 工作流统计数据
 */
export interface WorkflowStatistics {
  total_workflows: number
  running_workflows: number
  completed_workflows: number
  failed_workflows: number
  average_duration: number
  success_rate: number
  workflows_by_type: Record<string, number>
  recent_traces: WorkflowTrace[]
}

/**
 * 工作流执行摘要
 */
export interface WorkflowExecutionSummary {
  workflow_trace_id: string
  workflow_type: string
  status: string
  started_at: string
  completed_at?: string
  duration?: number
  total_nodes: number
  completed_nodes: number
  current_node?: string
  node_executions: WorkflowNodeExecution[]
  error_count: number
  human_review_count: number
}

/**
 * 工作流列表响应
 */
export interface WorkflowListResponse {
  items: WorkflowTrace[]
  total: number
  page: number
  page_size: number
}

/**
 * 节点类型统计
 */
export interface NodeTypeStats {
  node_type: string
  count: number
  average_duration: number
  success_rate: number
}

/**
 * 工作流监控 API 客户端
 */
export const workflowMonitorApi = {
  /**
   * 获取工作流追踪列表
   */
  async getTraces(params: {
    page?: number
    page_size?: number
    workflow_type?: string
    status?: string
    tenant_id?: string
    start_date?: string
    end_date?: string
  } = {}): Promise<WorkflowListResponse> {
    const response = await workflowApi.get('/workflow/traces', { params })
    return response.data
  },

  /**
   * 获取单个工作流追踪详情
   */
  async getTrace(traceId: string): Promise<WorkflowExecutionSummary> {
    const response = await workflowApi.get(`/workflow/traces/${traceId}`)
    return response.data
  },

  /**
   * 获取工作流统计数据
   */
  async getStatistics(params: {
    workflow_type?: string
    start_date?: string
    end_date?: string
  } = {}): Promise<WorkflowStatistics> {
    const response = await workflowApi.get('/workflow/statistics', { params })
    return response.data
  },

  /**
   * 获取节点执行历史
   */
  async getNodeExecutions(traceId: string): Promise<WorkflowNodeExecution[]> {
    const response = await workflowApi.get(`/workflow/traces/${traceId}/nodes`)
    return response.data
  },

  /**
   * 获取人工审核追踪列表
   */
  async getHumanReviewTrackings(params: {
    page?: number
    page_size?: number
    status?: string
    priority?: string
  } = {}): Promise<{ items: HumanReviewTracking[]; total: number }> {
    const response = await workflowApi.get<{ items: HumanReviewTracking[]; total: number }>('/human-review/reviews', { params })
    return {
      items: response.data.items || [],
      total: response.data.total || 0
    }
  },

  /**
   * 获取人工审核动作历史
   */
  async getReviewActions(trackingId: string): Promise<ReviewActionRecord[]> {
    const response = await workflowApi.get<ReviewActionRecord[]>(`/human-review/reviews/${trackingId}/comments`)
    return response.data || []
  },

  /**
   * 创建人工审核追踪
   */
  async createHumanReview(data: {
    workflow_trace_id: string
    node_execution_id?: string
    review_type: string
    priority?: string
    reason?: string
    assigned_to?: string
  }): Promise<HumanReviewTracking> {
    const response = await workflowApi.post('/human-review/reviews', data)
    return response.data
  },

  /**
   * 记录审核动作
   */
  async recordReviewAction(trackingId: string, data: {
    action: string
    comment?: string
  }): Promise<ReviewActionRecord> {
    const response = await workflowApi.post(`/human-review/reviews/${trackingId}/comments`, data)
    return response.data
  },

  /**
   * 获取节点类型统计
   */
  async getNodeTypeStats(params: {
    workflow_type?: string
    start_date?: string
    end_date?: string
  } = {}): Promise<NodeTypeStats[]> {
    const response = await workflowApi.get('/workflow/node-stats', { params })
    return response.data
  },

  /**
   * 获取正在运行的工作流
   */
  async getRunningWorkflows(): Promise<WorkflowTrace[]> {
    const response = await workflowApi.get('/workflow/running')
    return response.data
  },

  /**
   * 取消工作流
   */
  async cancelWorkflow(traceId: string): Promise<void> {
    await workflowApi.post(`/workflow/traces/${traceId}/cancel`)
  },

  /**
   * 重试失败的工作流
   */
  async retryWorkflow(traceId: string): Promise<WorkflowTrace> {
    const response = await workflowApi.post(`/workflow/traces/${traceId}/retry`)
    return response.data
  },
}

/**
 * 税务工作流监控 API 客户端
 */
export const taxWorkflowMonitorApi = {
  /**
   * 获取税务工作流列表
   */
  async getTaxWorkflows(params: {
    page?: number
    page_size?: number
    tax_type?: string
    status?: string
  } = {}): Promise<WorkflowListResponse> {
    const response = await workflowApi.get('/workflow/tax', { params })
    return response.data
  },

  /**
   * 获取税务工作流详情
   */
  async getTaxWorkflow(traceId: string): Promise<WorkflowExecutionSummary> {
    const response = await workflowApi.get(`/workflow/tax/${traceId}`)
    return response.data
  },

  /**
   * 获取税务工作流统计数据
   */
  async getTaxStatistics(params: {
    start_date?: string
    end_date?: string
  } = {}): Promise<WorkflowStatistics> {
    const response = await workflowApi.get('/workflow/tax/statistics', { params })
    return response.data
  },

  /**
   * 创建税务工作流监控会话
   */
  async createMonitoringSession(data: {
    workflow_trace_id: string
    tax_type: string
    tax_period: string
  }): Promise<{ session_id: string }> {
    const response = await workflowApi.post('/workflow/tax/monitor', data)
    return response.data
  },
}

/**
 * 政策推送工作流监控 API 客户端
 */
export const policyWorkflowMonitorApi = {
  /**
   * 获取政策推送工作流列表
   */
  async getPolicyWorkflows(params: {
    page?: number
    page_size?: number
    status?: string
    policy_id?: string
  } = {}): Promise<WorkflowListResponse> {
    const response = await workflowApi.get('/workflow/policy', { params })
    return response.data
  },

  /**
   * 获取政策推送工作流详情
   */
  async getPolicyWorkflow(traceId: string): Promise<WorkflowExecutionSummary> {
    const response = await workflowApi.get(`/workflow/policy/${traceId}`)
    return response.data
  },

  /**
   * 获取政策推送工作流统计数据
   */
  async getPolicyStatistics(params: {
    start_date?: string
    end_date?: string
  } = {}): Promise<WorkflowStatistics> {
    const response = await workflowApi.get('/workflow/policy/statistics', { params })
    return response.data
  },

  /**
   * 获取政策匹配结果
   */
  async getPolicyMatches(traceId: string): Promise<any[]> {
    const response = await workflowApi.get(`/workflow/policy/${traceId}/matches`)
    return response.data
  },

  /**
   * 获取通知发送记录
   */
  async getNotificationRecords(traceId: string): Promise<any[]> {
    const response = await workflowApi.get(`/workflow/policy/${traceId}/notifications`)
    return response.data
  },
}
