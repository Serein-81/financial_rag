import { request, get } from '@/utils/request'

export interface TenantStatistics {
  total_users: number
  active_users: number
  total_sessions: number
  active_sessions: number
  total_messages: number
  total_tokens: number
  avg_session_length: number
  period_start: string
  period_end: string
  daily_stats: DailyStat[]
  hourly_stats: HourlyStat[]
  top_users: UserActivity[]
  top_sessions: SessionActivity[]
}

export interface DailyStat {
  date: string
  sessions: number
  messages: number
  users: number
  tokens: number
}

export interface HourlyStat {
  hour: number
  sessions: number
  messages: number
}

export interface UserActivity {
  user_id: string
  user_name: string
  session_count: number
  message_count: number
  token_usage: number
}

export interface SessionActivity {
  session_id: string
  title: string
  message_count: number
  token_usage: number
  created_at: string
}

export interface UserStatistics {
  user_id: string
  user_name: string
  total_sessions: number
  active_sessions: number
  total_messages: number
  total_tokens: number
  avg_session_length: number
  period_start: string
  period_end: string
  daily_stats: DailyStat[]
  top_sessions: SessionActivity[]
}

export interface GroupStatistics {
  group_id: string
  group_name: string
  member_count: number
  message_count: number
  active_members: number
  created_at: string
}

export const analyticsApi = {
  async getTenantStatistics(params?: {
    start_date?: string
    end_date?: string
    tenant_id?: string
  }): Promise<TenantStatistics> {
    return get('/chat-logs/statistics/tenant', { params })
  },

  async getUserStatistics(
    userId: string,
    params?: {
      start_date?: string
      end_date?: string
    }
  ): Promise<UserStatistics> {
    return get(`/chat-logs/statistics/user/${userId}`, { params })
  },

  async getGroupStatistics(): Promise<GroupStatistics[]> {
    return get('/groups/statistics')
  },

  async getActiveUsers(): Promise<{ user_id: string; user_name: string; is_online: boolean }[]> {
    return get('/users/active')
  }
}

export interface ChatLogTenantStatistics {
  total_users: number
  active_users: number
  total_sessions: number
  active_sessions: number
  total_messages: number
  total_tokens: number
  avg_session_length: number
  period_start?: string
  period_end?: string
}

export interface ChatLogUserStatistics {
  user_id: string
  user_name: string
  total_sessions: number
  active_sessions: number
  total_messages: number
  total_tokens: number
  avg_session_length: number
}

export interface ChatLogSessionStatistics {
  session_id: string
  title: string
  message_count: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  created_at: string
  updated_at: string
}

export interface ChatLogSessionListResponse {
  total: number
  page: number
  page_size: number
  sessions: ChatLogSessionItem[]
}

export interface ChatLogSessionItem {
  id: string
  user_id: string
  user_name: string
  title: string
  message_count: number
  created_at: string
  updated_at: string
  last_message: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}
