// 用户反馈系统 API
// 对应后端 rag_backend/app/api/v1/endpoints/feedback.py
import { request, get, post, del } from '@/utils/request'

// ==================== Types ====================

export type FeedbackType = 'positive' | 'negative' | 'neutral'

export type FailureType =
  | 'retrieval'
  | 'generation'
  | 'hallucination'
  | 'incomplete'
  | 'irrelevant'
  | 'other'

export type FailureStatus = 'pending' | 'analyzing' | 'fixed' | 'ignored'

export type ImprovementType = 'prompt' | 'retrieval' | 'chunking' | 'parameter' | 'other'

export interface ChunkUsed {
  id?: string
  filename?: string
  score?: number
  content?: string
}

export interface FeedbackCreate {
  session_id: string
  message_id?: string | null
  query: string
  response: string
  feedback_type: FeedbackType
  rating?: number | null
  comment?: string | null
  retrieval_method?: string | null
  chunks_used?: ChunkUsed[] | Record<string, unknown> | null
  kb_id?: string | null
  retrieval_time?: number | null
  generation_time?: number | null
  total_time?: number | null
  token_count?: number | null
}

export interface FeedbackUpdate {
  feedback_type?: FeedbackType
  rating?: number
  comment?: string
}

export interface UserFeedback {
  id: string
  session_id: string
  message_id?: string | null
  user_id?: string | null
  query: string
  response: string
  feedback_type: FeedbackType
  rating?: number | null
  comment?: string | null
  retrieval_method?: string | null
  chunks_used?: any
  kb_id?: string | null
  retrieval_time?: number | null
  generation_time?: number | null
  total_time?: number | null
  token_count?: number | null
  created_at: string
}

export interface FeedbackListParams {
  session_id?: string
  feedback_type?: FeedbackType
  rating_min?: number
  skip?: number
  limit?: number
}

export interface FailureCase {
  id: string
  feedback_id: string
  failure_type: FailureType
  analysis?: Record<string, any> | null
  fix_suggestions?: any[] | null
  status: FailureStatus
  confidence_score?: number | null
  created_at: string
  updated_at?: string | null
}

export interface FailureCaseCreate {
  feedback_id: string
  failure_type: FailureType
  analysis?: Record<string, any> | null
  fix_suggestions?: any[] | null
}

export interface FailureCaseUpdate {
  failure_type?: FailureType
  analysis?: Record<string, any>
  fix_suggestions?: any[]
  status?: FailureStatus
}

export interface ImprovementRecord {
  id: string
  failure_case_id: string
  improvement_type: ImprovementType
  before_config?: Record<string, any> | null
  after_config?: Record<string, any> | null
  description?: string | null
  ab_test_result?: Record<string, any> | null
  deployed: boolean
  success_rate_before?: number | null
  success_rate_after?: number | null
  created_at: string
}

export interface ImprovementRecordCreate {
  failure_case_id: string
  improvement_type: ImprovementType
  before_config?: Record<string, any>
  after_config?: Record<string, any>
  description?: string
}

export interface FeedbackSummary {
  total_feedbacks: number
  positive_count: number
  negative_count: number
  neutral_count: number
  avg_rating: number
  total_failures: number
  fixed_count: number
  fix_rate: number
}

export interface FailureTypeStat {
  type: FailureType | string
  count: number
}

// ==================== Feedback CRUD ====================

export const feedbackApi = {
  async createFeedback(payload: FeedbackCreate): Promise<{ success: boolean; feedback: UserFeedback; message?: string }> {
    return post('/feedbacks', payload)
  },

  async getFeedback(id: string): Promise<{ success: boolean; feedback: UserFeedback }> {
    return get(`/feedbacks/${id}`)
  },

  async listFeedbacks(params: FeedbackListParams = {}): Promise<{
    success: boolean
    feedbacks: UserFeedback[]
    total: number
    skip: number
    limit: number
  }> {
    return get('/feedbacks', { params })
  },

  async updateFeedback(id: string, payload: FeedbackUpdate): Promise<{ success: boolean; feedback: UserFeedback }> {
    return request(`/feedbacks/${id}`, { method: 'PATCH', data: payload })
  },

  async deleteFeedback(id: string): Promise<{ success: boolean }> {
    return del(`/feedbacks/${id}`)
  },

  // ==================== Failure Cases ====================

  async createFailureCase(payload: FailureCaseCreate): Promise<{ success: boolean; failure_case: FailureCase }> {
    return post('/failure-cases', payload)
  },

  async listFailureCases(params: {
    status?: FailureStatus
    failure_type?: FailureType
    skip?: number
    limit?: number
  } = {}): Promise<{
    success: boolean
    failure_cases: FailureCase[]
    total: number
    skip?: number
    limit?: number
  }> {
    return get('/failure-cases', { params })
  },

  async getFailureCase(id: string): Promise<{ success: boolean; failure_case: FailureCase }> {
    return get(`/failure-cases/${id}`)
  },

  async updateFailureCase(id: string, payload: FailureCaseUpdate): Promise<{ success: boolean; failure_case: FailureCase }> {
    return request(`/failure-cases/${id}`, { method: 'PATCH', data: payload })
  },

  // ==================== Improvement Records ====================

  async createImprovementRecord(payload: ImprovementRecordCreate): Promise<{ success: boolean; record: ImprovementRecord }> {
    return post('/improvement-records', payload)
  },

  async listImprovementRecords(params: {
    failure_case_id?: string
    deployed?: boolean
    skip?: number
    limit?: number
  } = {}): Promise<{
    success: boolean
    records: ImprovementRecord[]
    total: number
  }> {
    return get('/improvement-records', { params })
  },

  // ==================== Statistics ====================

  async getFeedbackSummary(): Promise<FeedbackSummary> {
    return get('/statistics/feedback-summary')
  },

  async getFailureTypesStats(): Promise<{ success: boolean; distribution: Record<string, number> }> {
    return get('/statistics/failure-types')
  },
}
