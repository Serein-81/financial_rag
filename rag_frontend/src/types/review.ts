/**
 * 人工审核相关类型定义
 */

export enum ReviewStatusEnum {
  PENDING = 'pending',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  REJECTED = 'rejected',
  CANCELLED = 'cancelled'
}

export enum ReviewPriorityEnum {
  LOW = 'low',
  NORMAL = 'normal',
  HIGH = 'high',
  URGENT = 'urgent'
}

export enum ReviewTypeEnum {
  TAX = 'tax',
  FINANCE = 'finance',
  LEGAL = 'legal',
  COMPLIANCE = 'compliance'
}

export interface ReviewRequest {
  id: string
  tenant_id: string
  task_id?: string
  user_id: string
  title?: string
  description?: string
  review_type: ReviewTypeEnum
  priority: ReviewPriorityEnum
  status: ReviewStatusEnum
  trigger_reason?: string
  trigger_details?: Record<string, any>
  content?: Record<string, any>
  document_ids?: string[]
  assigned_to?: string
  created_at: string
  updated_at?: string
  completed_at?: string
  sla_deadline?: string
  is_overdue: boolean
  age_hours: number
  review_result?: ReviewResult
  review_comments?: string
}

export interface ReviewResult {
  decision: 'approved' | 'rejected' | 'needs_modification'
  details?: string
  confidence_score?: number
}

export interface ReviewRequestCreate {
  task_id?: string
  title?: string
  description?: string
  review_type: ReviewTypeEnum
  priority: ReviewPriorityEnum
  trigger_reason?: string
  trigger_details?: Record<string, any>
  content?: Record<string, any>
  document_ids?: string[]
}

export interface ReviewRequestUpdate {
  title?: string
  description?: string
  priority?: ReviewPriorityEnum
  assigned_to?: string
  status?: ReviewStatusEnum
  review_result?: ReviewResult
  review_comments?: string
}

export interface ReviewRequestFilter {
  status?: ReviewStatusEnum
  priority?: ReviewPriorityEnum
  review_type?: ReviewTypeEnum
  assigned_to_me?: boolean
  overdue_only?: boolean
  page?: number
  page_size?: number
}

export interface ReviewRequestListResponse {
  items: ReviewRequest[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ReviewStatistics {
  pending_count: number
  in_progress_count: number
  completed_today: number
  completed_this_week: number
  overdue_count: number
  avg_processing_hours: number
  priority_breakdown: {
    urgent?: number
    high?: number
    normal?: number
    low?: number
  }
}

export interface ReviewComment {
  id: string
  review_request_id: string
  user_id: string
  user_name?: string
  content: string
  created_at: string
}

export interface ReviewCommentCreate {
  content: string
}

export interface ReviewAction {
  id: string
  review_request_id: string
  user_id: string
  user_name?: string
  action: string
  details?: Record<string, any>
  created_at: string
}

export interface ReviewActionCreate {
  action: string
  details?: Record<string, any>
}
