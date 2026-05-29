<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { ThumbsUp, ThumbsDown, Star, MessageSquareText } from 'lucide-vue-next'
import { useFeedbackStore } from '@/stores/feedback'
import type { FeedbackCreate, FeedbackType } from '@/api/feedback'

/**
 * 聊天消息底部反馈按钮组
 * 提供 👍 / 👎 / ⭐评分 / 💬评论 4 种交互，全部对接后端 /feedbacks
 *
 * 已提交过的反馈会回显当前状态，再次操作自动转为更新
 */

interface MessageMeta {
  message_id?: string
  retrieval_method?: string
  kb_id?: string
  chunks_used?: any[]
  // 后端 SSE done 事件中字段名带 _ms 后缀
  retrieval_time_ms?: number
  generation_time_ms?: number
  total_time_ms?: number
  token_count?: number
  // 后端可能透传的检索参数（与请求 echo）
  top_k?: number | null
  enable_rerank?: boolean | null
  enable_graph_expansion?: boolean | null
  max_iterations?: number | null
  retrieval_history?: any[]
  evaluation?: any
}

interface ChatMessage {
  id?: string
  content: string
  sources?: any[]
  meta?: MessageMeta
}

const props = defineProps<{
  message: ChatMessage
  previousUserQuery: string
  sessionId: string | null
}>()

const feedbackStore = useFeedbackStore()

const showCommentPopover = ref(false)
const showRatingPopover = ref(false)
const commentDraft = ref('')
const ratingDraft = ref(0)

const messageId = computed(() => props.message.meta?.message_id || props.message.id || '')

const submitted = computed(() => feedbackStore.getMessageFeedback(messageId.value))

const currentType = computed<FeedbackType | null>(() => submitted.value?.feedback_type ?? null)
const currentRating = computed<number>(() => submitted.value?.rating ?? 0)
const currentComment = computed<string>(() => submitted.value?.comment ?? '')

function buildBasePayload(feedbackType: FeedbackType): FeedbackCreate {
  const meta = props.message.meta || {}
  const chunks = (props.message.sources || []).map((s: any) => ({
    id: s.id,
    filename: s.filename,
    score: s.score,
  }))
  return {
    session_id: props.sessionId || '',
    message_id: messageId.value || null,
    query: props.previousUserQuery,
    response: props.message.content,
    feedback_type: feedbackType,
    rating: null,
    comment: null,
    retrieval_method: meta.retrieval_method ?? null,
    chunks_used: meta.chunks_used ?? (chunks.length > 0 ? chunks : null),
    kb_id: meta.kb_id ?? null,
    // feedback API 字段名无 _ms 后缀，从 SSE meta 的 *_ms 字段映射
    retrieval_time: meta.retrieval_time_ms ?? null,
    generation_time: meta.generation_time_ms ?? null,
    total_time: meta.total_time_ms ?? null,
    token_count: meta.token_count ?? null,
  }
}

async function handleLike() {
  if (!props.sessionId) {
    ElMessage.warning('当前没有会话上下文，无法提交反馈')
    return
  }
  try {
    // 如果当前已是 positive 则取消（设为 neutral），否则切换为 positive
    const nextType: FeedbackType = currentType.value === 'positive' ? 'neutral' : 'positive'
    const payload = buildBasePayload(nextType)
    payload.rating = currentRating.value || null
    payload.comment = currentComment.value || null
    await feedbackStore.submitFeedback(messageId.value, payload)
    if (nextType === 'positive') ElMessage.success('已点赞，感谢反馈')
  } catch (e: any) {
    ElMessage.error('提交反馈失败：' + (e?.message || '未知错误'))
  }
}

async function handleDislike() {
  if (!props.sessionId) {
    ElMessage.warning('当前没有会话上下文，无法提交反馈')
    return
  }
  // 点踩时默认展开评论框邀请填写原因
  showCommentPopover.value = true
  commentDraft.value = currentComment.value
  try {
    const payload = buildBasePayload('negative')
    payload.rating = currentRating.value || null
    payload.comment = currentComment.value || null
    await feedbackStore.submitFeedback(messageId.value, payload)
  } catch (e: any) {
    ElMessage.error('提交反馈失败：' + (e?.message || '未知错误'))
  }
}

async function submitRating(rating: number) {
  ratingDraft.value = rating
  try {
    const baseType: FeedbackType = currentType.value
      ?? (rating >= 4 ? 'positive' : rating <= 2 ? 'negative' : 'neutral')
    const payload = buildBasePayload(baseType)
    payload.rating = rating
    payload.comment = currentComment.value || null
    await feedbackStore.submitFeedback(messageId.value, payload)
    ElMessage.success(`已评分 ${rating} 星`)
    showRatingPopover.value = false
  } catch (e: any) {
    ElMessage.error('提交评分失败：' + (e?.message || '未知错误'))
  }
}

async function submitComment() {
  if (!commentDraft.value.trim() && !currentComment.value) {
    showCommentPopover.value = false
    return
  }
  try {
    const baseType: FeedbackType = currentType.value ?? 'neutral'
    const payload = buildBasePayload(baseType)
    payload.rating = currentRating.value || null
    payload.comment = commentDraft.value.trim()
    await feedbackStore.submitFeedback(messageId.value, payload)
    ElMessage.success('已保存评论')
    showCommentPopover.value = false
  } catch (e: any) {
    ElMessage.error('提交评论失败：' + (e?.message || '未知错误'))
  }
}

function openComment() {
  commentDraft.value = currentComment.value
  showCommentPopover.value = true
}

function openRating() {
  ratingDraft.value = currentRating.value
  showRatingPopover.value = true
}
</script>

<template>
  <div class="message-feedback flex items-center gap-1">
    <!-- 点赞 -->
    <button
      class="fb-btn"
      :class="{ 'fb-active fb-positive': currentType === 'positive' }"
      :title="currentType === 'positive' ? '已点赞 (再次点击取消)' : '点赞'"
      :disabled="feedbackStore.loading"
      @click="handleLike"
    >
      <ThumbsUp :size="14" />
    </button>

    <!-- 点踩 -->
    <button
      class="fb-btn"
      :class="{ 'fb-active fb-negative': currentType === 'negative' }"
      :title="currentType === 'negative' ? '已点踩' : '点踩并反馈原因'"
      :disabled="feedbackStore.loading"
      @click="handleDislike"
    >
      <ThumbsDown :size="14" />
    </button>

    <!-- 评分 (popover) -->
    <el-popover
      v-model:visible="showRatingPopover"
      placement="top"
      :width="220"
      trigger="click"
    >
      <template #reference>
        <button
          class="fb-btn"
          :class="{ 'fb-active fb-rating': currentRating > 0 }"
          :title="currentRating > 0 ? `当前评分: ${currentRating} 星` : '评分'"
          @click="openRating"
        >
          <Star :size="14" />
          <span v-if="currentRating > 0" class="ml-0.5 text-xs">{{ currentRating }}</span>
        </button>
      </template>
      <div class="p-1">
        <div class="text-xs text-gray-500 mb-2">为本次回答打分</div>
        <div class="flex items-center gap-1">
          <button
            v-for="s in 5"
            :key="s"
            class="rating-star"
            :class="{ active: s <= ratingDraft }"
            @click="submitRating(s)"
          >
            <Star :size="20" :fill="s <= ratingDraft ? 'currentColor' : 'none'" />
          </button>
        </div>
      </div>
    </el-popover>

    <!-- 评论 (popover) -->
    <el-popover
      v-model:visible="showCommentPopover"
      placement="top"
      :width="320"
      trigger="click"
    >
      <template #reference>
        <button
          class="fb-btn"
          :class="{ 'fb-active fb-comment': !!currentComment }"
          :title="currentComment ? `已评论: ${currentComment}` : '添加评论'"
          @click="openComment"
        >
          <MessageSquareText :size="14" />
        </button>
      </template>
      <div class="p-1">
        <div class="text-xs text-gray-500 mb-2">补充评论 (可选)</div>
        <el-input
          v-model="commentDraft"
          type="textarea"
          :rows="3"
          placeholder="例如：答案不完整、缺少具体税率…"
          maxlength="500"
          show-word-limit
        />
        <div class="flex justify-end gap-2 mt-2">
          <el-button size="small" @click="showCommentPopover = false">取消</el-button>
          <el-button size="small" type="primary" @click="submitComment" :loading="feedbackStore.loading">提交</el-button>
        </div>
      </div>
    </el-popover>
  </div>
</template>

<style scoped>
.fb-btn {
  display: inline-flex;
  align-items: center;
  padding: 6px;
  border-radius: 8px;
  color: #9ca3af;
  transition: all 0.15s ease;
  background: transparent;
  border: none;
  cursor: pointer;
}
.fb-btn:hover {
  background: #f3f4f6;
  color: #374151;
}
.fb-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.fb-active.fb-positive {
  background: #fef2f2;
  color: #ef4444;
}
.fb-active.fb-negative {
  background: #eff6ff;
  color: #3b82f6;
}
.fb-active.fb-rating {
  background: #fffbeb;
  color: #f59e0b;
}
.fb-active.fb-comment {
  background: #ecfdf5;
  color: #10b981;
}
.rating-star {
  background: transparent;
  border: none;
  cursor: pointer;
  color: #d1d5db;
  padding: 2px;
}
.rating-star.active {
  color: #f59e0b;
}
.rating-star:hover {
  color: #fbbf24;
}
</style>
