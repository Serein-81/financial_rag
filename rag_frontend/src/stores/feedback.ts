// 用户反馈 Pinia Store
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { feedbackApi } from '@/api/feedback'
import type { FeedbackCreate, FeedbackUpdate, UserFeedback } from '@/api/feedback'

export const useFeedbackStore = defineStore('feedback', () => {
  // messageId -> 已提交的反馈记录
  const messageFeedbacks = ref<Map<string, UserFeedback>>(new Map())
  const loading = ref(false)
  const error = ref<string | null>(null)

  /**
   * 提交新反馈或更新已有反馈
   * 同一个 message_id 二次操作会自动改为 update
   */
  async function submitFeedback(messageId: string, payload: FeedbackCreate): Promise<UserFeedback> {
    loading.value = true
    error.value = null
    try {
      const existing = messageFeedbacks.value.get(messageId)
      if (existing) {
        // 已存在 → update
        const updatePayload: FeedbackUpdate = {
          feedback_type: payload.feedback_type,
          rating: payload.rating ?? undefined,
          comment: payload.comment ?? undefined,
        }
        const res = await feedbackApi.updateFeedback(existing.id, updatePayload)
        const feedback = res.feedback
        messageFeedbacks.value.set(messageId, feedback)
        return feedback
      } else {
        // 新建
        const res = await feedbackApi.createFeedback(payload)
        const feedback = res.feedback
        if (messageId) {
          messageFeedbacks.value.set(messageId, feedback)
        }
        return feedback
      }
    } catch (e: any) {
      error.value = e?.message || '提交反馈失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * 显式更新已有反馈
   */
  async function updateFeedback(feedbackId: string, payload: FeedbackUpdate): Promise<UserFeedback> {
    loading.value = true
    error.value = null
    try {
      const res = await feedbackApi.updateFeedback(feedbackId, payload)
      const feedback = res.feedback
      // 同步本地 map
      for (const [mid, fb] of messageFeedbacks.value.entries()) {
        if (fb.id === feedbackId) {
          messageFeedbacks.value.set(mid, feedback)
          break
        }
      }
      return feedback
    } catch (e: any) {
      error.value = e?.message || '更新反馈失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载某个 session 已有的反馈，回填 UI
   */
  async function loadSessionFeedbacks(sessionId: string) {
    loading.value = true
    error.value = null
    try {
      const res = await feedbackApi.listFeedbacks({ session_id: sessionId, limit: 100 })
      messageFeedbacks.value.clear()
      for (const fb of res.feedbacks) {
        if (fb.message_id) {
          messageFeedbacks.value.set(fb.message_id, fb)
        }
      }
    } catch (e: any) {
      error.value = e?.message || '加载反馈失败'
    } finally {
      loading.value = false
    }
  }

  function getMessageFeedback(messageId: string): UserFeedback | undefined {
    return messageFeedbacks.value.get(messageId)
  }

  function hasSubmitted(messageId: string): boolean {
    return messageFeedbacks.value.has(messageId)
  }

  function clear() {
    messageFeedbacks.value.clear()
  }

  return {
    messageFeedbacks,
    loading,
    error,
    submitFeedback,
    updateFeedback,
    loadSessionFeedbacks,
    getMessageFeedback,
    hasSubmitted,
    clear,
  }
})
