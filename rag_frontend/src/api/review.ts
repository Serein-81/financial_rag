/**
 * 人工审核 API 客户端
 */

import axios from 'axios'
import { ElMessage } from 'element-plus'
import type {
  ReviewRequest,
  ReviewRequestCreate,
  ReviewRequestUpdate,
  ReviewRequestFilter,
  ReviewRequestListResponse,
  ReviewStatistics,
  ReviewComment,
  ReviewCommentCreate,
  ReviewAction,
  ReviewActionCreate,
  ReviewStatusEnum,
  ReviewPriorityEnum,
  ReviewTypeEnum
} from '@/types/review'
import { API_BASE } from '@/config/api'

const API_BASE_URL = `${API_BASE}/api/v1`

const reviewApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

reviewApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('rag_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

reviewApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const errorMessage = error.response?.data?.detail || error.response?.data?.message

    if (status === 401 || status === 403) {
      localStorage.removeItem('rag_token')
      localStorage.removeItem('user')
      
      const message = status === 401 
        ? '登录已过期，请重新登录' 
        : (errorMessage?.includes('tenant') ? '会话无效，请重新登录' : '登录已过期，请重新登录')
      
      ElMessage.error({
        message,
        duration: 3000,
        onClose: () => {
          window.location.href = '/login'
        }
      })
    } else if (status === 500) {
      ElMessage.error({
        message: '服务器错误，请稍后重试',
        duration: 3000
      })
    }
    
    return Promise.reject(error)
  }
)

export const reviewApiClient = {
  /**
   * 创建审核请求
   */
  async create(data: ReviewRequestCreate): Promise<ReviewRequest> {
    const response = await reviewApi.post<ReviewRequest>('/human-review/reviews', data)
    return response.data
  },

  /**
   * 获取审核请求列表
   */
  async list(filter: ReviewRequestFilter = {}): Promise<ReviewRequestListResponse> {
    const params = new URLSearchParams()

    if (filter.status) params.append('status', filter.status)
    if (filter.priority) params.append('priority', filter.priority)
    if (filter.review_type) params.append('review_type', filter.review_type)
    if (filter.assigned_to_me) params.append('assigned_to_me', 'true')
    if (filter.overdue_only) params.append('overdue_only', 'true')
    if (filter.page) params.append('page', String(filter.page))
    if (filter.page_size) params.append('page_size', String(filter.page_size))

    const response = await reviewApi.get<ReviewRequestListResponse>(
      `/human-review/reviews?${params.toString()}`
    )
    return response.data
  },

  /**
   * 获取审核请求详情
   */
  async get(id: string): Promise<ReviewRequest> {
    const response = await reviewApi.get<ReviewRequest>(`/human-review/reviews/${id}`)
    return response.data
  },

  /**
   * 更新审核请求
   */
  async update(id: string, data: Partial<ReviewRequestUpdate>): Promise<ReviewRequest> {
    const response = await reviewApi.patch<ReviewRequest>(`/human-review/reviews/${id}`, data)
    return response.data
  },

  /**
   * 删除审核请求
   */
  async delete(id: string): Promise<void> {
    await reviewApi.delete(`/human-review/reviews/${id}`)
  },

  /**
   * 获取审核统计信息
   */
  async getStatistics(): Promise<ReviewStatistics> {
    const response = await reviewApi.get<ReviewStatistics>('/human-review/reviews/statistics')
    return response.data
  },

  /**
   * 获取待审核数量（徽章显示用）
   */
  async getPendingCount(): Promise<number> {
    const response = await reviewApi.get<{ count: number }>('/human-review/reviews/pending-count')
    return response.data.count
  },

  /**
   * 认领审核请求
   */
  async claim(id: string): Promise<ReviewRequest> {
    const response = await reviewApi.post<ReviewRequest>(`/human-review/reviews/${id}/claim`)
    return response.data
  },

  /**
   * 转交审核请求
   */
  async transfer(id: string, targetUserId: string): Promise<ReviewRequest> {
    const response = await reviewApi.post<ReviewRequest>(`/human-review/reviews/${id}/transfer`, {
      target_user_id: targetUserId
    })
    return response.data
  },

  /**
   * 添加审核评论
   */
  async addComment(id: string, data: ReviewCommentCreate): Promise<ReviewComment> {
    const response = await reviewApi.post<ReviewComment>(
      `/human-review/reviews/${id}/comments`,
      data
    )
    return response.data
  },

  /**
   * 获取审核评论列表
   */
  async getComments(id: string): Promise<ReviewComment[]> {
    const response = await reviewApi.get<ReviewComment[]>(`/human-review/reviews/${id}/comments`)
    return response.data
  },

  /**
   * 记录审核操作
   */
  async recordAction(id: string, data: ReviewActionCreate): Promise<ReviewAction> {
    const response = await reviewApi.post<ReviewAction>(
      `/human-review/reviews/${id}/actions`,
      data
    )
    return response.data
  },

  /**
   * 获取审核操作历史
   */
  async getActions(id: string): Promise<ReviewAction[]> {
    const response = await reviewApi.get<ReviewAction[]>(`/human-review/reviews/${id}/actions`)
    return response.data
  },

  /**
   * 批量更新状态
   */
  async batchUpdateStatus(ids: string[], status: ReviewStatusEnum): Promise<void> {
    await reviewApi.post('/human-review/reviews/batch-update-status', {
      ids,
      status
    })
  },

  /**
   * 导出审核记录
   */
  async export(
    format: 'csv' | 'excel' = 'csv',
    filter?: ReviewRequestFilter
  ): Promise<Blob> {
    const params = new URLSearchParams()
    params.append('format', format)

    if (filter?.status) params.append('status', filter.status)
    if (filter?.priority) params.append('priority', filter.priority)
    if (filter?.review_type) params.append('review_type', filter.review_type)
    if (filter?.overdue_only) params.append('overdue_only', 'true')

    const response = await reviewApi.get(`/human-review/reviews/export?${params.toString()}`, {
      responseType: 'blob'
    })
    return response.data
  }
}

export default reviewApiClient
