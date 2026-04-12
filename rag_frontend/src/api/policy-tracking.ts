import { request } from '@/utils/request'

export interface PolicySubscriptionRequest {
  enterprise_id?: string
  industry?: string
  region?: string
  company_size?: string
  business_scope?: string[]
  funding_stage?: string
  notification_methods?: string[]
  severity_threshold?: number
  categories?: string[]
}

export interface PolicySubscription {
  id: string
  enterprise_id: string
  industry: string
  region: string
  company_size: string
  business_scope: string[]
  funding_stage: string
  notification_methods: string[]
  severity_threshold: number
  categories: string[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PolicyUpdate {
  id: string
  policy_id: string
  title: string
  summary: string
  source: string
  published_date: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  categories: string[]
  relevance_score: number
  matched_reasons: string[]
  url?: string
}

export interface PolicyQueryRequest {
  query?: string
  industries?: string[]
  regions?: string[]
  categories?: string[]
  date_range?: {
    start: string
    end: string
  }
  page?: number
  page_size?: number
}

export interface PolicyQueryResponse {
  policies: Array<{
    id: string
    title: string
    summary: string
    source: string
    published_date: string
    effective_date?: string
    categories: string[]
    industries: string[]
    regions: string[]
    relevance_score: number
  }>
  total: number
  page: number
  page_size: number
}

export interface CategoryInfo {
  id: string
  name: string
  icon: string
  policy_count: number
}

export interface TrendData {
  month: string
  new_policies: number
  matched_count: number
}

export interface CalendarEvent {
  date: string
  events: Array<{
    id: string
    title: string
    type: 'deadline' | 'effective' | 'published'
    policy_id?: string
  }>
}

export const policyTrackingApi = {
  subscribe: async (params: PolicySubscriptionRequest): Promise<PolicySubscription> => {
    return request('/policy-tracking/subscribe', {
      method: 'POST',
      data: params
    })
  },

  getSubscriptions: async (): Promise<{
    subscriptions: PolicySubscription[]
    total: number
  }> => {
    return request('/policy-tracking/subscriptions', {
      method: 'GET'
    })
  },

  deleteSubscription: async (subscriptionId: string): Promise<void> => {
    return request(`/policy-tracking/subscribe/${subscriptionId}`, {
      method: 'DELETE'
    })
  },

  getUpdates: async (params: {
    page?: number
    page_size?: number
    category?: string
    severity?: string
  } = {}): Promise<{
    updates: PolicyUpdate[]
    total: number
    page: number
    page_size: number
  }> => {
    return request('/policy-tracking/updates', {
      method: 'GET',
      params
    })
  },

  queryPolicies: async (params: PolicyQueryRequest): Promise<PolicyQueryResponse> => {
    return request('/policy-tracking/query', {
      method: 'GET',
      params
    })
  },

  getTrends: async (): Promise<{
    trends: TrendData[]
    summary: {
      total_policies: number
      matched_policies: number
      growth_rate: number
    }
  }> => {
    return request('/policy-tracking/trends', {
      method: 'GET'
    })
  },

  getCalendar: async (params: {
    year: number
    month: number
  }): Promise<{
    events: CalendarEvent[]
  }> => {
    return request('/policy-tracking/calendar', {
      method: 'GET',
      params
    })
  },

  sendNotification: async (subscriptionId: string): Promise<void> => {
    return request(`/policy-tracking/notify/${subscriptionId}`, {
      method: 'POST'
    })
  },

  getCategories: async (): Promise<{
    categories: CategoryInfo[]
  }> => {
    return request('/policy-tracking/categories', {
      method: 'GET'
    })
  },

  getHealth: async (): Promise<{
    status: string
    timestamp: string
  }> => {
    return request('/policy-tracking/health', {
      method: 'GET'
    })
  }
}
