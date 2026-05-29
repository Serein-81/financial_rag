<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ListChecks,
  RefreshCw,
  ThumbsUp,
  ThumbsDown,
  Star,
  TrendingUp,
  Trash2,
  Eye,
  AlertCircle,
} from 'lucide-vue-next'
import { feedbackApi } from '@/api/feedback'
import type { UserFeedback, FeedbackType, FeedbackSummary } from '@/api/feedback'

const feedbacks = ref<UserFeedback[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// 过滤
const filterType = ref<FeedbackType | ''>('')
const filterRatingMin = ref<number>(0)
const filterSessionId = ref<string>('')

// 统计
const summary = ref<FeedbackSummary | null>(null)
const summaryLoading = ref(false)

// 详情抽屉
const drawerVisible = ref(false)
const selectedFeedback = ref<UserFeedback | null>(null)

onMounted(async () => {
  await Promise.all([loadList(), loadSummary()])
})

async function loadList() {
  loading.value = true
  try {
    const res = await feedbackApi.listFeedbacks({
      feedback_type: filterType.value || undefined,
      rating_min: filterRatingMin.value || undefined,
      session_id: filterSessionId.value || undefined,
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    })
    feedbacks.value = res.feedbacks
    total.value = res.total
  } catch (e: any) {
    ElMessage.error('加载反馈列表失败：' + (e?.message || ''))
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  summaryLoading.value = true
  try {
    summary.value = await feedbackApi.getFeedbackSummary()
  } catch (e: any) {
    console.warn('loadSummary failed:', e)
  } finally {
    summaryLoading.value = false
  }
}

function onFilterChange() {
  page.value = 1
  loadList()
}

function onPageChange(p: number) {
  page.value = p
  loadList()
}

function openDetail(row: UserFeedback) {
  selectedFeedback.value = row
  drawerVisible.value = true
}

async function deleteFeedback(row: UserFeedback) {
  try {
    await ElMessageBox.confirm(`确定要删除该反馈吗？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await feedbackApi.deleteFeedback(row.id)
    ElMessage.success('已删除')
    await Promise.all([loadList(), loadSummary()])
  } catch (e: any) {
    if (e === 'cancel' || e?.message === 'cancel') return
    ElMessage.error('删除失败：' + (e?.message || ''))
  }
}

async function refreshAll() {
  await Promise.all([loadList(), loadSummary()])
  ElMessage.success('已刷新')
}

function typeColor(t?: FeedbackType): 'success' | 'danger' | 'info' {
  if (t === 'positive') return 'success'
  if (t === 'negative') return 'danger'
  return 'info'
}

function typeLabel(t?: FeedbackType): string {
  if (t === 'positive') return '正面'
  if (t === 'negative') return '负面'
  return '中性'
}

function truncate(s?: string | null, n = 60): string {
  if (!s) return '—'
  if (s.length <= n) return s
  return s.slice(0, n) + '…'
}

function formatTime(s?: string | null): string {
  if (!s) return '—'
  try {
    const d = new Date(s)
    return d.toLocaleString('zh-CN', { hour12: false })
  } catch {
    return s
  }
}

function formatDuration(ms?: number | null): string {
  if (ms === undefined || ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

const positivePercent = computed(() => {
  if (!summary.value || summary.value.total_feedbacks === 0) return 0
  return Math.round((summary.value.positive_count / summary.value.total_feedbacks) * 100)
})

const negativePercent = computed(() => {
  if (!summary.value || summary.value.total_feedbacks === 0) return 0
  return Math.round((summary.value.negative_count / summary.value.total_feedbacks) * 100)
})

async function createFailureCaseFromFeedback() {
  if (!selectedFeedback.value) return
  try {
    await feedbackApi.createFailureCase({
      feedback_id: selectedFeedback.value.id,
      // 默认设为 "other"，由后端 FailureAnalyzer 自动重分类
      failure_type: 'other',
    })
    ElMessage.success('已创建失败案例，可在「失败分析」页查看')
  } catch (e: any) {
    ElMessage.error('创建失败案例失败：' + (e?.message || ''))
  }
}
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <ListChecks :size="24" class="text-emerald-600" />
          反馈管理
        </h1>
        <p class="text-sm text-gray-500 mt-1">查看用户对 AI 回答的反馈，转化为失败案例进行根因分析</p>
      </div>
      <el-button :icon="RefreshCw" @click="refreshAll" :loading="loading">刷新</el-button>
    </div>

    <!-- Stats Cards -->
    <div v-loading="summaryLoading" class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <el-card shadow="never" class="!border-gray-200">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center">
            <ListChecks :size="20" class="text-gray-600" />
          </div>
          <div>
            <div class="text-xs text-gray-500">总反馈数</div>
            <div class="text-2xl font-bold text-gray-900">{{ summary?.total_feedbacks ?? 0 }}</div>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="!border-emerald-200 bg-emerald-50/30">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <ThumbsUp :size="20" class="text-emerald-600" />
          </div>
          <div>
            <div class="text-xs text-gray-500">正面 / 占比</div>
            <div class="text-2xl font-bold text-gray-900">
              {{ summary?.positive_count ?? 0 }}
              <span class="text-sm font-normal text-emerald-600 ml-1">{{ positivePercent }}%</span>
            </div>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="!border-red-200 bg-red-50/30">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
            <ThumbsDown :size="20" class="text-red-600" />
          </div>
          <div>
            <div class="text-xs text-gray-500">负面 / 占比</div>
            <div class="text-2xl font-bold text-gray-900">
              {{ summary?.negative_count ?? 0 }}
              <span class="text-sm font-normal text-red-600 ml-1">{{ negativePercent }}%</span>
            </div>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="!border-amber-200 bg-amber-50/30">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
            <Star :size="20" class="text-amber-600" />
          </div>
          <div>
            <div class="text-xs text-gray-500">平均评分</div>
            <div class="text-2xl font-bold text-gray-900">
              {{ summary?.avg_rating?.toFixed(1) ?? '—' }}
              <span class="text-sm font-normal text-gray-400">/ 5</span>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 二级统计：失败/修复 -->
    <div v-if="summary && (summary.total_failures > 0 || summary.fixed_count > 0)"
         class="mb-6 p-4 bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-200 rounded-xl flex items-center justify-between">
      <div class="flex items-center gap-6">
        <div>
          <div class="text-xs text-gray-500">已识别失败案例</div>
          <div class="text-xl font-bold text-gray-900">{{ summary.total_failures }}</div>
        </div>
        <div>
          <div class="text-xs text-gray-500">已修复</div>
          <div class="text-xl font-bold text-gray-900">{{ summary.fixed_count }}</div>
        </div>
        <div>
          <div class="text-xs text-gray-500">修复率</div>
          <div class="text-xl font-bold text-purple-700">{{ summary.fix_rate?.toFixed(1) ?? 0 }}%</div>
        </div>
      </div>
      <router-link to="/failure-analysis" class="text-sm text-purple-600 hover:text-purple-800">
        前往失败分析 →
      </router-link>
    </div>

    <!-- Filter Bar -->
    <el-card shadow="never" class="mb-4">
      <div class="flex items-center gap-3 flex-wrap">
        <el-select
          v-model="filterType"
          placeholder="反馈类型"
          clearable
          size="default"
          style="width: 160px"
          @change="onFilterChange"
        >
          <el-option value="" label="全部" />
          <el-option value="positive" label="正面" />
          <el-option value="negative" label="负面" />
          <el-option value="neutral" label="中性" />
        </el-select>

        <el-select
          v-model="filterRatingMin"
          placeholder="最低评分"
          clearable
          size="default"
          style="width: 140px"
          @change="onFilterChange"
        >
          <el-option :value="0" label="不限" />
          <el-option v-for="n in 5" :key="n" :value="n" :label="`≥ ${n} 星`" />
        </el-select>

        <el-input
          v-model="filterSessionId"
          placeholder="会话 ID 精确搜索"
          clearable
          size="default"
          style="width: 280px"
          @change="onFilterChange"
        />
      </div>
    </el-card>

    <!-- Table -->
    <el-card shadow="never">
      <el-table
        :data="feedbacks"
        v-loading="loading"
        stripe
        empty-text="暂无反馈数据"
      >
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="typeColor(row.feedback_type)">
              {{ typeLabel(row.feedback_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="评分" width="100">
          <template #default="{ row }">
            <div v-if="row.rating" class="flex items-center gap-0.5">
              <Star v-for="n in 5" :key="n" :size="12"
                    :fill="n <= row.rating ? '#f59e0b' : 'none'"
                    :class="n <= row.rating ? 'text-amber-500' : 'text-gray-300'" />
            </div>
            <span v-else class="text-gray-400 text-xs">—</span>
          </template>
        </el-table-column>
        <el-table-column label="查询" min-width="200">
          <template #default="{ row }">
            <div class="text-sm text-gray-700">{{ truncate(row.query, 50) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="回答" min-width="200">
          <template #default="{ row }">
            <div class="text-sm text-gray-600">{{ truncate(row.response, 50) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="评论" min-width="140">
          <template #default="{ row }">
            <span class="text-xs text-gray-500">{{ truncate(row.comment, 30) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="检索" width="100">
          <template #default="{ row }">
            <span class="text-xs text-gray-500">{{ row.retrieval_method || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <div class="flex items-center gap-1">
              <button class="action-btn" title="详情" @click="openDetail(row)">
                <Eye :size="14" />
              </button>
              <button class="action-btn action-btn-danger" title="删除" @click="deleteFeedback(row)">
                <Trash2 :size="14" />
              </button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="mt-4 flex justify-end">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next, total"
          background
          @current-change="onPageChange"
        />
      </div>
    </el-card>

    <!-- Detail Drawer -->
    <el-drawer
      v-model="drawerVisible"
      title="反馈详情"
      direction="rtl"
      size="600px"
    >
      <div v-if="selectedFeedback" class="space-y-4">
        <!-- 基本信息 -->
        <el-card shadow="never">
          <template #header>
            <div class="text-sm font-medium">基本信息</div>
          </template>
          <div class="space-y-2 text-sm">
            <div class="flex items-center gap-2">
              <el-tag size="small" :type="typeColor(selectedFeedback.feedback_type)">
                {{ typeLabel(selectedFeedback.feedback_type) }}
              </el-tag>
              <div v-if="selectedFeedback.rating" class="flex items-center gap-0.5">
                <Star v-for="n in 5" :key="n" :size="14"
                      :fill="n <= selectedFeedback.rating ? '#f59e0b' : 'none'"
                      :class="n <= selectedFeedback.rating ? 'text-amber-500' : 'text-gray-300'" />
              </div>
              <span class="text-xs text-gray-400 ml-auto">{{ formatTime(selectedFeedback.created_at) }}</span>
            </div>
            <div class="text-xs text-gray-500">
              <div><span class="text-gray-400">会话 ID:</span> {{ selectedFeedback.session_id }}</div>
              <div v-if="selectedFeedback.message_id"><span class="text-gray-400">消息 ID:</span> {{ selectedFeedback.message_id }}</div>
              <div v-if="selectedFeedback.kb_id"><span class="text-gray-400">知识库:</span> {{ selectedFeedback.kb_id }}</div>
            </div>
          </div>
        </el-card>

        <!-- 查询 & 回答 -->
        <el-card shadow="never">
          <template #header>
            <div class="text-sm font-medium">查询 & 回答</div>
          </template>
          <div class="space-y-3 text-sm">
            <div>
              <div class="text-xs text-gray-400 mb-1">用户查询</div>
              <div class="bg-gray-50 rounded-lg p-3 text-gray-800 whitespace-pre-wrap">{{ selectedFeedback.query }}</div>
            </div>
            <div>
              <div class="text-xs text-gray-400 mb-1">系统响应</div>
              <div class="bg-emerald-50/40 rounded-lg p-3 text-gray-800 whitespace-pre-wrap">{{ selectedFeedback.response }}</div>
            </div>
            <div v-if="selectedFeedback.comment">
              <div class="text-xs text-gray-400 mb-1">用户评论</div>
              <div class="bg-amber-50 rounded-lg p-3 text-amber-900 whitespace-pre-wrap">{{ selectedFeedback.comment }}</div>
            </div>
          </div>
        </el-card>

        <!-- 性能 -->
        <el-card shadow="never">
          <template #header>
            <div class="text-sm font-medium">性能指标</div>
          </template>
          <div class="grid grid-cols-2 gap-3 text-xs">
            <div class="bg-gray-50 rounded p-2">
              <div class="text-gray-400">检索方法</div>
              <div class="text-gray-800 font-medium mt-0.5">{{ selectedFeedback.retrieval_method || '—' }}</div>
            </div>
            <div class="bg-gray-50 rounded p-2">
              <div class="text-gray-400">Token 消耗</div>
              <div class="text-gray-800 font-medium mt-0.5">{{ selectedFeedback.token_count ?? '—' }}</div>
            </div>
            <div class="bg-gray-50 rounded p-2">
              <div class="text-gray-400">检索时间</div>
              <div class="text-gray-800 font-medium mt-0.5">{{ formatDuration(selectedFeedback.retrieval_time) }}</div>
            </div>
            <div class="bg-gray-50 rounded p-2">
              <div class="text-gray-400">生成时间</div>
              <div class="text-gray-800 font-medium mt-0.5">{{ formatDuration(selectedFeedback.generation_time) }}</div>
            </div>
            <div class="bg-gray-50 rounded p-2 col-span-2">
              <div class="text-gray-400">总耗时</div>
              <div class="text-gray-800 font-medium mt-0.5">{{ formatDuration(selectedFeedback.total_time) }}</div>
            </div>
          </div>
        </el-card>

        <!-- chunks_used -->
        <el-card v-if="selectedFeedback.chunks_used && (Array.isArray(selectedFeedback.chunks_used) ? selectedFeedback.chunks_used.length : true)" shadow="never">
          <template #header>
            <div class="text-sm font-medium">使用的文档块</div>
          </template>
          <pre class="text-xs text-gray-700 bg-gray-50 rounded p-3 overflow-x-auto max-h-72">{{ JSON.stringify(selectedFeedback.chunks_used, null, 2) }}</pre>
        </el-card>

        <!-- 操作 -->
        <div v-if="selectedFeedback.feedback_type === 'negative'" class="bg-red-50 border border-red-200 rounded-xl p-3">
          <div class="flex items-start gap-2">
            <AlertCircle :size="16" class="text-red-600 mt-0.5 flex-shrink-0" />
            <div class="flex-1">
              <div class="text-sm font-medium text-red-900">这是一条负面反馈</div>
              <div class="text-xs text-red-700 mt-1">可以创建为失败案例，由系统自动分析根因并生成改进建议。</div>
              <el-button size="small" type="danger" class="mt-2" @click="createFailureCaseFromFeedback">
                创建失败案例
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: #6b7280;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
}
.action-btn:hover {
  background: #f3f4f6;
  color: #111827;
}
.action-btn-danger:hover {
  background: #fef2f2;
  color: #dc2626;
}
</style>
