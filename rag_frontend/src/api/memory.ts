import { request } from '@/utils/request'

export interface MemorySearchRequest {
  keywords: string[]
  session_id: string
  role?: 'user' | 'assistant' | 'system'
  importance_min?: number
  top_k?: number
}

export interface MemoryResult {
  id: string
  content: string
  role: 'user' | 'assistant' | 'system'
  timestamp: string
  importance: number
  access_count: number
  decay_factor: number
  metadata: {
    topic?: string
    confidence?: number
  }
}

export interface MemorySearchResponse {
  success: boolean
  results: MemoryResult[]
  total: number
  keywords: string[]
  session_id: string
}

export interface MemoryStatistics {
  total_memories: number
  user_memories: number
  assistant_memories: number
  average_importance: number
  most_accessed_topic: string
  memory_distribution: {
    high_importance: number
    medium_importance: number
    low_importance: number
  }
}

export interface MemoryStatisticsResponse {
  success: boolean
  statistics: MemoryStatistics
}

export interface SessionSummary {
  session_id: string
  total_messages: number
  key_topics: string[]
  important_insights: string[]
  conversation_flow: string
  generated_at: string
}

export interface SessionSummaryResponse {
  success: boolean
  summary: SessionSummary
}

export const memoryApi = {
  // 搜索记忆
  async searchMemories(data: MemorySearchRequest): Promise<MemorySearchResponse> {
    return request<MemorySearchResponse>('/memory/search', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  // 获取记忆统计
  async getStatistics(session_id: string): Promise<MemoryStatisticsResponse> {
    return request<MemoryStatisticsResponse>(`/memory/statistics/${session_id}`)
  },

  // 导出会话摘要
  async getSessionSummary(session_id: string): Promise<SessionSummaryResponse> {
    return request<SessionSummaryResponse>(`/memory/summary/${session_id}`)
  },
}
