import { request } from '@/utils/request'

export interface TenantInfo {
  tenant_id: string
  company_name: string
  is_primary: boolean
}

export interface ChatLogMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  sources?: any[]
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  model_name?: string
  agent_name?: string
  turn?: number
  created_at: string
}

export interface ChatLogSession {
  id: string
  user_id: string
  user_name: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  last_message_preview?: string
  total_prompt_tokens?: number
  total_completion_tokens?: number
  total_tokens?: number
}

export interface ChatLogSessionStatistics {
  session_id: string
  title: string
  user_name: string
  user_id: string
  created_at: string
  message_count: number
  total_turns: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  model_name?: string
}

export interface ChatLogUserStatistics {
  user_id: string
  user_name: string
  chat_statistics: {
    total_sessions: number
    total_messages: number
    total_turns: number
    total_prompt_tokens: number
    total_completion_tokens: number
    total_tokens: number
  }
  action_statistics: {
    total_actions: number
    level_stats: {
      INFO: number
      ERROR: number
      WARNING: number
      DEBUG: number
    }
    success_count: number
    failure_count: number
    success_rate: number
    action_type_stats?: Record<string, number>
    top_actions?: Array<Record<string, number>>
  }
}

export interface ChatLogTenantStatistics {
  total_users: number
  active_users: number
  total_sessions: number
  total_messages: number
  total_turns: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  tenant_id?: string
  tenant_ids?: string[]
}

export interface ChatLogSessionListResponse {
  sessions: ChatLogSession[]
  total: number
  page: number
  page_size: number
}

export interface ChatLogMessagesResponse {
  messages: ChatLogMessage[]
  total: number
}

export interface ChatLogQueryParams {
  page?: number
  page_size?: number
  user_id?: string
  start_date?: string
  end_date?: string
  keyword?: string
  format?: 'xlsx' | 'csv'
}

export const chatLogsApi = {
  async getSessions(params: ChatLogQueryParams = {}): Promise<ChatLogSessionListResponse> {
    const searchParams = new URLSearchParams()

    if (params.page) searchParams.append('page', String(params.page))
    if (params.page_size) searchParams.append('page_size', String(params.page_size))
    if (params.user_id) searchParams.append('user_id', params.user_id)
    if (params.start_date) searchParams.append('start_date', params.start_date)
    if (params.end_date) searchParams.append('end_date', params.end_date)
    if (params.keyword) searchParams.append('keyword', params.keyword)

    return request<ChatLogSessionListResponse>(`/chat-logs/sessions?${searchParams.toString()}`)
  },

  async getSessionMessages(sessionId: string): Promise<ChatLogMessagesResponse> {
    return request<ChatLogMessagesResponse>(`/chat-logs/sessions/${sessionId}/messages`)
  },

  async getSessionStatistics(sessionId: string): Promise<ChatLogSessionStatistics> {
    return request<ChatLogSessionStatistics>(`/chat-logs/sessions/${sessionId}/statistics`)
  },

  async getUserStatistics(userId: string): Promise<ChatLogUserStatistics> {
    return request<ChatLogUserStatistics>(`/chat-logs/statistics/user/${userId}`)
  },

  async getTenantStatistics(tenantId?: string): Promise<ChatLogTenantStatistics> {
    const searchParams = new URLSearchParams()
    if (tenantId) searchParams.append('tenant_id', tenantId)
    return request<ChatLogTenantStatistics>(`/chat-logs/statistics/tenant?${searchParams.toString()}`)
  },

  async getManagedTenants(): Promise<{ tenants: TenantInfo[]; count: number }> {
    return request<{ tenants: TenantInfo[]; count: number }>('/chat-logs/tenants')
  },

  async exportSessions(params: ChatLogQueryParams = {}): Promise<void> {
    const searchParams = new URLSearchParams()
    const token = localStorage.getItem('rag_token')
    const format = params.format || 'xlsx'

    if (params.page) searchParams.append('page', String(params.page))
    if (params.page_size) searchParams.append('page_size', String(params.page_size))
    if (params.user_id) searchParams.append('user_id', params.user_id)
    if (params.start_date) searchParams.append('start_date', params.start_date)
    if (params.end_date) searchParams.append('end_date', params.end_date)
    if (params.keyword) searchParams.append('keyword', params.keyword)
    searchParams.append('format', format)

    const headers: Record<string, string> = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`/chat-logs/export/sessions?${searchParams.toString()}`, {
      method: 'GET',
      headers,
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('导出失败')
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = `chat_logs_${new Date().toISOString().slice(0, 10)}.${format}`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
      if (match) {
        filename = decodeURIComponent(match[1])
      }
    }
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  },

  async exportActionLogs(params: {
    page?: number
    page_size?: number
    level?: string
    action_type?: string
    start_date?: string
    end_date?: string
    format?: 'xlsx' | 'csv'
  } = {}): Promise<void> {
    const searchParams = new URLSearchParams()
    const token = localStorage.getItem('rag_token')
    const format = params.format || 'xlsx'

    if (params.page) searchParams.append('page', String(params.page))
    if (params.page_size) searchParams.append('page_size', String(params.page_size))
    if (params.level) searchParams.append('level', params.level)
    if (params.action_type) searchParams.append('action_type', params.action_type)
    if (params.start_date) searchParams.append('start_date', params.start_date)
    if (params.end_date) searchParams.append('end_date', params.end_date)
    searchParams.append('format', format)

    const headers: Record<string, string> = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`/chat-logs/export/actions?${searchParams.toString()}`, {
      method: 'GET',
      headers,
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('导出失败')
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = `action_logs_${new Date().toISOString().slice(0, 10)}.${format}`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
      if (match) {
        filename = decodeURIComponent(match[1])
      }
    }
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  },

  async getUserActionLogs(params: {
    page?: number
    page_size?: number
    level?: string
    action_type?: string
    start_date?: string
    end_date?: string
  } = {}): Promise<{
    logs: UserActionLog[]
    total: number
    page: number
    page_size: number
  }> {
    const searchParams = new URLSearchParams()

    if (params.page) searchParams.append('page', String(params.page))
    if (params.page_size) searchParams.append('page_size', String(params.page_size))
    if (params.level) searchParams.append('level', params.level)
    if (params.action_type) searchParams.append('action_type', params.action_type)
    if (params.start_date) searchParams.append('start_date', params.start_date)
    if (params.end_date) searchParams.append('end_date', params.end_date)

    return request<{
      logs: UserActionLog[]
      total: number
      page: number
      page_size: number
    }>(`/chat-logs/actions?${searchParams.toString()}`)
  },

  async getEnterpriseLogs(params: {
    level?: string
    action?: string
    start_time?: string
    end_time?: string
    limit?: number
    offset?: number
    tenant_id?: string
  } = {}): Promise<{
    success: boolean
    data: EnterpriseLogsResponse
  }> {
    const searchParams = new URLSearchParams()

    if (params.level) searchParams.append('level', params.level)
    if (params.action) searchParams.append('action', params.action)
    if (params.start_time) searchParams.append('start_time', params.start_time)
    if (params.end_time) searchParams.append('end_time', params.end_time)
    if (params.limit) searchParams.append('limit', String(params.limit))
    if (params.offset) searchParams.append('offset', String(params.offset))
    if (params.tenant_id) searchParams.append('tenant_id', params.tenant_id)

    return request<{
      success: boolean
      data: EnterpriseLogsResponse
    }>(`/logs/system?${searchParams.toString()}`)
  },
}

export interface UserActionLog {
  id: string
  user_id: string
  user_email?: string
  tenant_id?: string
  action_type: string
  action_name: string
  description?: string
  resource_type?: string
  resource_id?: string
  resource_name?: string
  success: boolean
  result_message?: string
  ip_address?: string
  user_agent?: string
  created_at: string
  level?: string
  risk_level?: string
  extra_info?: Record<string, any>
}

export interface EnterpriseLogEntry {
  id: string
  created_at: string
  level: string
  category: string
  action: string
  message: string
  user_id: string | null
  user_email: string | null
  user_name?: string
  ip_address: string | null
  endpoint?: string
  method?: string
  status_code?: number
  execution_time?: number
  tenant_id?: string
  tenant_name?: string
  tenant_invite_code?: string
}

export interface EnterpriseLogsResponse {
  logs: EnterpriseLogEntry[]
  total: number
  limit: number
  offset: number
}
