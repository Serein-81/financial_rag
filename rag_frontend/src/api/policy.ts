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

export interface SSEPolicyNotification {
  event_type: string
  enterprise_id: string
  policy_id: string
  policy_title: string
  match_score: number
  impact_level: string
  timestamp: string
  match_details?: {
    policy_id: string
    title: string
    industries: string[]
    regions: string[]
    tax_types: string[]
    priority: string
    source: string
  }
}

export interface NotificationStatus {
  enterprise_id: string
  active_subscribers: number
  total_notifications: number
  stream_endpoint: string
}

// PolicyNotificationAgent 相关类型
export interface PolicyAgentMatchRequest {
  policy: {
    policy_id: string
    title: string
    content: string
    source?: string
    publish_date?: string
    priority?: string
  }
  enterprise: EnterpriseProfileInput
  use_llm?: boolean
}

export interface EnterpriseProfileInput {
  enterprise_id: string
  enterprise_name: string
  industry: string
  region: string
  scale: string
  tax_types: string[]
  qualifications?: string[]
}

export interface PolicyAgentMatchResponse {
  match_score: number
  semantic_score: number
  industry_score: number
  region_score: number
  scale_score: number
  tax_type_score: number
  urgency_score: number
  reasons: string[]
  policy_id: string
  enterprise_id: string
  use_llm: boolean
}

export interface PolicyAgentNotificationRequest {
  policy: Record<string, any>
  enterprise_profile: EnterpriseProfileInput
  match_result: Record<string, any>
}

export interface PolicyAgentNotificationResponse {
  title: string
  content: string
  urgency_level: string
  key_points: string[]
  action_steps: string[]
  deadline?: string
  use_llm: boolean
}

export interface PolicyAgentPriorityRequest {
  policies: Record<string, any>[]
  enterprise_profile: EnterpriseProfileInput
}

export interface PolicyAgentStatus {
  status: string
  use_llm: boolean
  llm_provider?: string
  agent_capabilities: {
    policy_understanding: boolean
    semantic_matching: boolean
    personalized_generation: boolean
    fallback_mode: boolean
  }
  match_weights?: {
    industry: number
    region: number
    scale: number
    tax_type: number
    semantic: number
    urgency: number
  }
}

export interface PolicyAgentTestRequest {
  policies: {
    policy_id: string
    title: string
    content: string
    source?: string
    publish_date?: string
    priority?: string
  }[]
  enterprise: EnterpriseProfileInput
  use_llm?: boolean
}

export interface PolicyAgentTestResponse {
  enterprise_id: string
  policies_processed: number
  matches: PolicyAgentMatchResponse[]
  notifications: PolicyAgentNotificationResponse[]
  prioritized_policies: Record<string, any>[]
  use_llm: boolean
  llm_provider: string
  processing_time: number
}

export const policyApi = {
  createEventSource(token: string): EventSource {
    const url = `${import.meta.env.VITE_API_BASE_URL}/api/v1/policy-notifications/stream`
    return new EventSource(url, {
      withCredentials: false
    } as EventSourceInit & { headers?: Record<string, string> })
  },

  async getNotificationStatus(token: string): Promise<NotificationStatus> {
    return request('/policy-notifications/status', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
  },

  async getRecentNotifications(token: string, limit: number = 50): Promise<{
    enterprise_id: string
    count: number
    notifications: SSEPolicyNotification[]
  }> {
    return request('/policy-notifications/recent', {
      method: 'GET',
      params: { limit },
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
  },

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
  },

  // PolicyNotificationAgent API
  async getPolicyAgentStatus(): Promise<PolicyAgentStatus> {
    return request('/policy-agent/status', {
      method: 'GET'
    })
  },

  async matchPolicyWithEnterprise(matchRequest: PolicyAgentMatchRequest): Promise<PolicyAgentMatchResponse> {
    return request('/policy-agent/match', {
      method: 'POST',
      data: matchRequest
    })
  },

  async generatePolicyNotification(notifyRequest: PolicyAgentNotificationRequest): Promise<PolicyAgentNotificationResponse> {
    return request('/policy-agent/notify', {
      method: 'POST',
      data: notifyRequest
    })
  },

  async prioritizePolicies(priorityRequest: PolicyAgentPriorityRequest): Promise<Record<string, any>[]> {
    return request('/policy-agent/prioritize', {
      method: 'POST',
      data: priorityRequest
    })
  },

  async testPolicyAgent(testRequest: PolicyAgentTestRequest): Promise<PolicyAgentTestResponse> {
    return request('/policy-agent/test', {
      method: 'POST',
      data: testRequest
    })
  }
}
