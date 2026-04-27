import { request } from '@/utils/request'

export interface LangSmithStatus {
  enabled: boolean
  api_key_configured: boolean
  project: string
  endpoint: string
  tracing_enabled: boolean
  client_initialized: boolean
  last_check: string
}

export interface LangSmithStats {
  total_traces: number
  total_llm_calls: number
  total_tool_calls: number
  active_runs: number
  error_count: number
  last_trace_time: string | null
  uptime_seconds: number
}

export interface LangSmithDashboard {
  dashboard_url: string
  project_url: string
  traces_url: string
  datasets_url: string
  evaluations_url: string
}

export interface LangSmithProjectInfo {
  project_name: string
  run_count: number
  last_run_time: string | null
  trace_count: number
  warning?: string
  error?: string
}

export interface LangSmithConfigUpdate {
  api_key?: string
  project?: string
  endpoint?: string
  tracing?: boolean
}

export interface LangSmithTrace {
  run_id: string
  name: string
  run_type: string
  created_at: string
  inputs: Record<string, any>
  outputs: Record<string, any>
  error: string | null
  tags: string[]
}

export interface RecentTracesResponse {
  total: number
  traces: LangSmithTrace[]
  error?: string
}

export interface ConfigUpdateResponse {
  message: string
  updates: Record<string, string>
  current_config: LangSmithStatus
}

export interface TestConnectionResponse {
  success: boolean
  message: string
  details: Record<string, any>
}

export const langSmithApi = {
  async getStatus(): Promise<LangSmithStatus> {
    return request<LangSmithStatus>('/langsmith/status')
  },

  async getStats(): Promise<LangSmithStats> {
    return request<LangSmithStats>('/langsmith/stats')
  },

  async getDashboard(): Promise<LangSmithDashboard> {
    return request<LangSmithDashboard>('/langsmith/dashboard')
  },

  async getProjectInfo(): Promise<LangSmithProjectInfo> {
    return request<LangSmithProjectInfo>('/langsmith/project')
  },

  async updateConfig(config: LangSmithConfigUpdate): Promise<ConfigUpdateResponse> {
    return request<ConfigUpdateResponse>('/langsmith/config', {
      method: 'POST',
      data: config
    })
  },

  async testConnection(): Promise<TestConnectionResponse> {
    return request<TestConnectionResponse>('/langsmith/test', {
      method: 'POST'
    })
  },

  async getRecentTraces(limit: number = 10): Promise<RecentTracesResponse> {
    return request<RecentTracesResponse>(`/langsmith/recent-traces?limit=${limit}`)
  }
}