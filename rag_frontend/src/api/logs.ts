import { request } from '@/utils/request'

export interface LogEntry {
  timestamp: string
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
  module: string
  message: string
  details?: Record<string, any>
}

export interface LogsResponse {
  logs: LogEntry[]
  total: number
  page: number
  page_size: number
}

export interface LogsQueryParams {
  page?: number
  page_size?: number
  level?: string
  module?: string
  keyword?: string
  start_date?: string
  end_date?: string
}

export const logsApi = {
  async getLogs(params: LogsQueryParams = {}): Promise<LogsResponse> {
    const searchParams = new URLSearchParams()

    if (params.page) searchParams.append('page', String(params.page))
    if (params.page_size) searchParams.append('page_size', String(params.page_size))
    if (params.level) searchParams.append('level', params.level)
    if (params.module) searchParams.append('module', params.module)
    if (params.keyword) searchParams.append('keyword', params.keyword)
    if (params.start_date) searchParams.append('start_date', params.start_date)
    if (params.end_date) searchParams.append('end_date', params.end_date)

    return request<LogsResponse>(`/logs?${searchParams.toString()}`)
  },

  async clearLogs(): Promise<void> {
    return request<void>('/logs/clear', {
      method: 'POST',
    })
  },

  async exportLogs(params: LogsQueryParams = {}): Promise<Blob> {
    const searchParams = new URLSearchParams()

    if (params.level) searchParams.append('level', params.level)
    if (params.module) searchParams.append('module', params.module)
    if (params.keyword) searchParams.append('keyword', params.keyword)
    if (params.start_date) searchParams.append('start_date', params.start_date)
    if (params.end_date) searchParams.append('end_date', params.end_date)

    const token = localStorage.getItem('rag_token')
    const response = await fetch(`/logs/export?${searchParams.toString()}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    return response.blob()
  },
}
