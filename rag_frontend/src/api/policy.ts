import { request } from '@/utils/request'

export interface Policy {
  id: string
  policy_id: string
  title: string
  content: string
  summary?: string
  source_url?: string
  source_name: string
  published_date?: string
  effective_date?: string
  expiry_date?: string
  industries: string[]
  regions: string[]
  scales: string[]
  tax_types: string[]
  tags: string[]
  status: 'active' | 'archived' | 'draft' | 'expired'
  priority: 'critical' | 'high' | 'medium' | 'low'
  version: string
  view_count: number
  meta_info?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface PolicySearchParams {
  query?: string
  industries?: string[]
  regions?: string[]
  tax_types?: string[]
  scales?: string[]
  status?: string
  priority?: string
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}

export interface PolicyListResponse {
  policies: Policy[]
  total: number
  page: number
  page_size: number
}

export interface PolicyRetrievalResult {
  policy: Policy
  score: number
  highlight?: string
}

export interface PolicyMatchResult {
  policy_id: string
  policy_title: string
  match_score: number
  match_reasons: string[]
  policy: Policy
}

export interface EnterpriseProfile {
  enterprise_id: string
  enterprise_name: string
  industry: string
  region: string
  tax_types: string[]
  scale: string
}

export interface MatchRecord {
  id: string
  enterprise_id: string
  policy_id: string
  match_score: number
  match_reasons: string[]
  notification_status: 'pending' | 'sent' | 'acknowledged' | 'dismissed' | 'failed'
  match_status: 'active' | 'inactive' | 'expired'
  created_at: string
  notified_at?: string
  acknowledged_at?: string
}

export interface PolicyNotification {
  id: string
  enterprise_id: string
  policy_id: string
  policy_title: string
  policy_summary?: string
  match_score: number
  match_reasons: string[]
  status: 'pending' | 'sent' | 'acknowledged' | 'dismissed' | 'failed'
  created_at: string
  notified_at?: string
  acknowledged_at?: string
}

export interface NotificationListResponse {
  enterprise_id: string
  notifications: PolicyNotification[]
  total: number
}

export const policyApi = {
  listPolicies: async (params: PolicySearchParams = {}): Promise<PolicyListResponse> => {
    return request('/policy/list', {
      method: 'POST',
      data: params
    })
  },

  getPolicy: async (id: string): Promise<Policy> => {
    return request(`/policy/detail/${id}`, {
      method: 'GET'
    })
  },

  searchPolicies: async (params: PolicySearchParams): Promise<PolicyRetrievalResult[]> => {
    return request('/policy/search', {
      method: 'POST',
      data: params
    })
  },

  getPolicyRecommendations: async (enterpriseId: string, limit?: number): Promise<PolicyMatchResult[]> => {
    return request('/policy/recent', {
      method: 'GET',
      params: { limit: limit || 10 }
    })
  },

  matchEnterprisePolicies: async (enterpriseId: string, topK?: number): Promise<PolicyMatchResult[]> => {
    return request('/policy/match', {
      method: 'POST',
      data: JSON.stringify({ enterprise_id: enterpriseId, top_k: topK || 10 })
    })
  },

  getEnterpriseMatches: async (enterpriseId: string): Promise<MatchRecord[]> => {
    const res = await request(`/policy/notifications/${enterpriseId}`, {
      method: 'GET'
    })
    return res?.notifications || []
  },

  updateMatchStatus: async (matchId: string, status: string): Promise<void> => {
    return request(`/policy/notifications/${matchId}`, {
      method: 'PATCH',
      data: JSON.stringify({ status })
    })
  },

  acknowledgeMatch: async (matchId: string): Promise<void> => {
    return request(`/policy/notifications/${matchId}/acknowledge`, {
      method: 'POST'
    })
  },

  dismissMatch: async (matchId: string, reason?: string): Promise<void> => {
    return request(`/policy/notifications/${matchId}/dismiss`, {
      method: 'POST',
      data: JSON.stringify({ reason })
    })
  },

  getPolicyStatistics: async (): Promise<{
    total: number
    active: number
    by_industry: Record<string, number>
    by_tax_type: Record<string, number>
    recent_updates: number
  }> => {
    return request('/policy/sources', {
      method: 'GET'
    })
  },

  getPolicySources: async (): Promise<{ name: string; count: number }[]> => {
    return request('/policy/sources', {
      method: 'GET'
    })
  },

  getNotifications: async (
    enterpriseId: string,
    status?: string,
    limit?: number
  ): Promise<NotificationListResponse> => {
    return request(`/policy/notifications/${enterpriseId}`, {
      method: 'GET',
      params: {
        status: status,
        limit: limit || 20
      }
    })
  },

  acknowledgeNotification: async (
    notificationId: string,
    feedback?: Record<string, any>
  ): Promise<void> => {
    return request(`/policy/notifications/${notificationId}/acknowledge`, {
      method: 'POST',
      data: JSON.stringify({ feedback })
    })
  },

  dismissNotification: async (
    notificationId: string,
    reason?: string
  ): Promise<void> => {
    return request(`/policy/notifications/${notificationId}/dismiss`, {
      method: 'POST',
      data: JSON.stringify({ reason })
    })
  },

  exportPolicyReport: async (params: {
    policyIds?: string[]
    query?: string
    topK?: number
  }): Promise<Blob> => {
    const response = await request('/policy/report/export', {
      method: 'GET',
      params: {
        policy_ids: params.policyIds?.join(','),
        query: params.query,
        top_k: params.topK || 20
      },
      responseType: 'blob'
    })
    return response as Blob
  }
}
