<template>
  <div class="review-dashboard">
    <div class="page-header">
      <div class="header-content">
        <h1>审核工作台</h1>
        <p class="subtitle">处理需要人工审核的税务报告</p>
      </div>
      <div class="header-actions">
        <el-badge :value="newReviewsCount" :hidden="newReviewsCount === 0" :max="99">
          <el-button @click="handleNewReviews" :disabled="newReviewsCount === 0">
            <el-icon><Bell /></el-icon>
            新任务 {{ newReviewsCount > 0 ? `(${newReviewsCount})` : '' }}
          </el-button>
        </el-badge>
        <el-button @click="refreshData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-tag :type="isConnected ? 'success' : 'info'" size="small">
          <el-icon><Connection /></el-icon>
          {{ isConnected ? '实时连接' : '轮询模式' }}
        </el-tag>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="statistics-row">
      <el-card class="stat-card pending" shadow="hover" @click="filterByStatus('pending')">
        <div class="stat-content">
          <div class="stat-icon">
            <el-icon :size="32"><Clock /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.pending_count }}</div>
            <div class="stat-label">待处理</div>
          </div>
          <div class="stat-trend up" v-if="statistics.pending_count > 0">
            <el-icon><Top /></el-icon>
          </div>
        </div>
      </el-card>

      <el-card class="stat-card in-progress" shadow="hover">
        <div class="stat-content">
          <div class="stat-icon">
            <el-icon :size="32"><Loading /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.in_progress_count }}</div>
            <div class="stat-label">处理中</div>
          </div>
        </div>
      </el-card>

      <el-card class="stat-card completed" shadow="hover">
        <div class="stat-content">
          <div class="stat-icon">
            <el-icon :size="32"><Check /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.completed_today }}</div>
            <div class="stat-label">今日完成</div>
          </div>
        </div>
      </el-card>

      <el-card class="stat-card overdue" shadow="hover" @click="filterByStatus('pending', true)">
        <div class="stat-content">
          <div class="stat-icon warning">
            <el-icon :size="32"><AlertTriangle /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.overdue_count }}</div>
            <div class="stat-label">已逾期</div>
          </div>
          <div class="stat-alert" v-if="statistics.overdue_count > 0">
            <el-icon><Bell /></el-icon>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 优先级分布和时间线 -->
    <div class="middle-section">
      <el-card class="priority-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <div class="header-title">
              <el-icon><DataLine /></el-icon>
              <span>待处理优先级分布</span>
            </div>
          </div>
        </template>
        <div class="priority-bars">
          <div class="priority-item">
            <div class="priority-label">
              <el-tag type="danger" size="small">紧急</el-tag>
              <span class="count">{{ statistics.priority_breakdown?.urgent || 0 }}</span>
            </div>
            <el-progress
              :percentage="getPercentage(statistics.priority_breakdown?.urgent || 0)"
              :stroke-width="10"
              :show-text="false"
              color="#f56c6c"
            />
          </div>
          <div class="priority-item">
            <div class="priority-label">
              <el-tag type="warning" size="small">高</el-tag>
              <span class="count">{{ statistics.priority_breakdown?.high || 0 }}</span>
            </div>
            <el-progress
              :percentage="getPercentage(statistics.priority_breakdown?.high || 0)"
              :stroke-width="10"
              :show-text="false"
              color="#e6a23c"
            />
          </div>
          <div class="priority-item">
            <div class="priority-label">
              <el-tag type="primary" size="small">普通</el-tag>
              <span class="count">{{ statistics.priority_breakdown?.normal || 0 }}</span>
            </div>
            <el-progress
              :percentage="getPercentage(statistics.priority_breakdown?.normal || 0)"
              :stroke-width="10"
              :show-text="false"
              color="#409eff"
            />
          </div>
          <div class="priority-item">
            <div class="priority-label">
              <el-tag type="info" size="small">低</el-tag>
              <span class="count">{{ statistics.priority_breakdown?.low || 0 }}</span>
            </div>
            <el-progress
              :percentage="getPercentage(statistics.priority_breakdown?.low || 0)"
              :stroke-width="10"
              :show-text="false"
              color="#909399"
            />
          </div>
        </div>
        <div class="avg-time">
          <el-icon><Timer /></el-icon>
          平均处理时间: <strong>{{ statistics.avg_processing_hours || 0 }}小时</strong>
        </div>
      </el-card>

      <el-card class="activity-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <div class="header-title">
              <el-icon><Timer /></el-icon>
              <span>最近活动</span>
            </div>
          </div>
        </template>
        <div class="activity-timeline">
          <div v-for="(activity, index) in recentActivities" :key="index" class="activity-item">
            <div class="activity-dot" :class="activity.type" />
            <div class="activity-content">
              <div class="activity-text">{{ activity.text }}</div>
              <div class="activity-time">{{ activity.time }}</div>
            </div>
          </div>
          <el-empty v-if="recentActivities.length === 0" description="暂无活动记录" :image-size="60" />
        </div>
      </el-card>
    </div>

    <!-- 筛选和列表 -->
    <el-card class="list-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <el-icon><List /></el-icon>
            <span>审核任务列表</span>
            <el-tag size="small" type="info">{{ pagination.total }} 条记录</el-tag>
          </div>
          <div class="filter-tabs">
            <el-radio-group v-model="filterStatus" size="small" @change="handleStatusChange">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button label="pending">
                待处理
                <el-badge :value="statistics.pending_count" :hidden="statistics.pending_count === 0" class="status-badge" />
              </el-radio-button>
              <el-radio-button label="in_progress">处理中</el-radio-button>
              <el-radio-button label="completed">已完成</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>

      <div class="filter-row">
        <el-form inline :model="filterForm" size="default">
          <el-form-item label="优先级">
            <el-select v-model="filterForm.priority" placeholder="全部" clearable>
              <el-option label="紧急" value="urgent" />
              <el-option label="高" value="high" />
              <el-option label="普通" value="normal" />
              <el-option label="低" value="low" />
            </el-select>
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="filterForm.review_type" placeholder="全部" clearable>
              <el-option label="税务" value="tax" />
              <el-option label="财务" value="finance" />
              <el-option label="法务" value="legal" />
              <el-option label="合规" value="compliance" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="filterForm.overdue_only" label="仅显示逾期" />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="filterForm.assigned_to_me" label="仅看我负责的" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadReviews">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="reviewList" v-loading="loading" stripe @row-click="handleRowClick" highlight-current-row>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-content">
              <el-alert
                v-if="row.description"
                :title="row.description"
                type="info"
                :closable="false"
                show-icon
              />
              <el-alert
                v-if="row.trigger_reason"
                :title="`触发原因: ${row.trigger_reason}`"
                type="warning"
                :closable="false"
                show-icon
                style="margin-top: 8px"
              />
              <div v-if="row.content" class="content-preview">
                <div class="preview-header">
                  <el-icon><DataAnalysis /></el-icon>
                  <strong>AI分析结果摘要</strong>
                </div>
                <div class="preview-box">
                  <el-row :gutter="16">
                    <el-col :span="8">
                      <div class="preview-stat">
                        <span class="label">总问题数</span>
                        <span class="value">{{ row.content.total_issues || 0 }}</span>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="preview-stat danger">
                        <span class="label">高严重问题</span>
                        <span class="value">{{ row.content.high_severity_issues || 0 }}</span>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="preview-stat">
                        <span class="label">风险评分</span>
                        <span class="value">{{ (row.content.overall_risk_score || 0).toFixed(1) }}</span>
                      </div>
                    </el-col>
                  </el-row>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="优先级" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" size="small" effect="dark">
              {{ getPriorityText(row.priority) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="title" label="标题" min-width="200">
          <template #default="{ row }">
            <div class="title-cell">
              <span class="title-text">{{ row.title || row.trigger_reason }}</span>
              <el-icon v-if="row.is_overdue" class="overdue-icon" color="#f56c6c"><AlertTriangleFilled /></el-icon>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="review_type" label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ getTypeName(row.review_type) }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="SLA" width="120" align="center">
          <template #default="{ row }">
            <div v-if="row.sla_deadline" :class="{ 'overdue-text': row.is_overdue }">
              <el-icon><Timer /></el-icon>
              {{ formatSLA(row.sla_deadline) }}
            </div>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="age_hours" label="等待时间" width="100" align="center">
          <template #default="{ row }">
            <span :class="{ 'wait-time-long': row.age_hours > 24 }">
              {{ formatAge(row.age_hours) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button
                v-if="row.status === 'pending'"
                type="primary"
                size="small"
                @click.stop="handleClaim(row)"
                :loading="claimingId === row.id"
              >
                <el-icon><Edit /></el-icon>
                领取
              </el-button>
              <el-button
                v-if="row.status === 'in_progress'"
                type="success"
                size="small"
                @click.stop="handleRowClick(row)"
              >
                <el-icon><Edit /></el-icon>
                审核
              </el-button>
              <el-button
                v-if="row.status === 'completed'"
                type="info"
                size="small"
                @click.stop="handleRowClick(row)"
              >
                <el-icon><View /></el-icon>
                查看
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadReviews"
          @current-change="loadReviews"
        />
      </div>
    </el-card>

    <!-- 审核详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="currentReview?.title || '审核详情'"
      width="1000px"
      :close-on-click-modal="false"
      class="review-dialog"
    >
      <div v-if="currentReview" class="review-detail">
        <el-alert
          v-if="currentReview.is_overdue"
          title="此任务已逾期，请尽快处理"
          type="error"
          show-icon
          :closable="false"
          class="overdue-alert"
        />

        <el-descriptions :column="2" border class="basic-info">
          <el-descriptions-item label="优先级">
            <el-tag :type="getPriorityType(currentReview.priority)" effect="dark">
              {{ getPriorityText(currentReview.priority) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentReview.status)">
              {{ getStatusText(currentReview.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="类型">
            <el-tag effect="plain">{{ getTypeName(currentReview.review_type) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="触发原因">
            {{ currentReview.trigger_reason || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="SLA截止">
            <span :class="{ 'overdue-text': currentReview.is_overdue }">
              {{ currentReview.sla_deadline ? new Date(currentReview.sla_deadline).toLocaleString() : '-' }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="等待时间">
            {{ formatAge(currentReview.age_hours) }}
          </el-descriptions-item>
        </el-descriptions>

        <el-tabs class="detail-tabs">
          <el-tab-pane label="基本信息">
            <div class="detail-section">
              <h4>描述</h4>
              <p class="description-text">{{ currentReview.description || '无' }}</p>
            </div>

            <div class="detail-section" v-if="currentReview.content">
              <h4>AI分析结果</h4>
              <el-row :gutter="16" class="content-stats">
                <el-col :span="6">
                  <el-statistic title="总问题数" :value="currentReview.content.total_issues || 0" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="高严重问题" :value="currentReview.content.high_severity_issues || 0" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="风险评分" :value="currentReview.content.overall_risk_score || 0" suffix="/ 10" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="置信度" :value="((currentReview.content.confidence_score || 0) * 100).toFixed(0)" suffix="%" />
                </el-col>
              </el-row>
            </div>
          </el-tab-pane>

          <el-tab-pane label="原始内容">
            <div class="detail-section">
              <h4>内容详情</h4>
              <div class="content-display">
                <pre>{{ JSON.stringify(currentReview.content, null, 2) }}</pre>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="历史记录">
            <div class="history-section">
              <el-timeline>
                <el-timeline-item
                  v-for="(item, index) in reviewHistory"
                  :key="index"
                  :timestamp="item.timestamp"
                  :type="item.type"
                  :icon="item.icon"
                  placement="top"
                >
                  <el-card shadow="hover" class="history-card">
                    <div class="history-title">{{ item.title }}</div>
                    <div class="history-content">{{ item.content }}</div>
                  </el-card>
                </el-timeline-item>
              </el-timeline>
              <el-empty v-if="reviewHistory.length === 0" description="暂无历史记录" :image-size="60" />
            </div>
          </el-tab-pane>
        </el-tabs>

        <div v-if="currentReview.status === 'in_progress'" class="review-form">
          <el-divider content-position="left">审核操作</el-divider>

          <el-form :model="reviewForm" label-width="100px">
            <el-form-item label="审核结论">
              <el-radio-group v-model="reviewForm.decision">
                <el-radio label="approved">通过</el-radio>
                <el-radio label="rejected">驳回</el-radio>
                <el-radio label="needs_modification">需要修改</el-radio>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="处理结果">
              <el-input
                v-model="reviewForm.result"
                type="textarea"
                :rows="3"
                placeholder="请输入处理结果..."
              />
            </el-form-item>

            <el-form-item label="审核意见">
              <el-input
                v-model="reviewForm.comments"
                type="textarea"
                :rows="2"
                placeholder="请输入审核意见..."
              />
            </el-form-item>

            <el-form-item>
              <el-button type="success" @click="handleComplete" :loading="submitting">
                <el-icon><Check /></el-icon>
                完成审核
              </el-button>
              <el-button type="danger" @click="handleReject" :loading="submitting">
                <el-icon><Close /></el-icon>
                驳回
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button
          v-if="currentReview?.status === 'pending'"
          type="primary"
          @click="handleClaimFromDialog"
          :loading="claimingId === currentReview?.id"
        >
          领取任务
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  Clock,
  Loading,
  Check,
  AlertTriangle,
  Timer,
  Bell,
  Connection,
  Top,
  DataLine,
  List,
  Edit,
  View,
  WarningFilled,
  DataAnalysis
} from '@element-plus/icons-vue'
import { reviewApiClient } from '@/api/review'
import type { ReviewRequest, ReviewStatistics } from '@/types/review'

const loading = ref(false)
const detailDialogVisible = ref(false)
const currentReview = ref<ReviewRequest | null>(null)
const submitting = ref(false)
const claimingId = ref<string | null>(null)

const isConnected = ref(false)
const newReviewsCount = ref(0)

const reviewForm = reactive({
  decision: 'approved',
  result: '',
  comments: ''
})

const filterStatus = ref('')
const filterForm = reactive({
  priority: '',
  review_type: '',
  overdue_only: false,
  assigned_to_me: false
})

const reviewList = ref<ReviewRequest[]>([])
const statistics = ref<ReviewStatistics>({
  pending_count: 0,
  in_progress_count: 0,
  completed_today: 0,
  overdue_count: 0,
  priority_breakdown: {},
  avg_processing_hours: 0
})

const recentActivities = ref<Array<{ type: string; text: string; time: string }>>([])

const reviewHistory = ref<Array<{ timestamp: string; type: string; icon: string; title: string; content: string }>>([])

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

let ws: WebSocket | null = null
let pollingInterval: number | null = null

const loadStatistics = async () => {
  try {
    const stats = await reviewApiClient.getStatistics()
    const oldPending = statistics.value.pending_count
    statistics.value = stats

    if (stats.pending_count > oldPending && oldPending > 0) {
      newReviewsCount.value += stats.pending_count - oldPending
    }
  } catch (error: any) {
    console.error('加载统计失败:', error)
  }
}

const loadReviews = async () => {
  try {
    loading.value = true
    const result = await reviewApiClient.list({
      status: filterStatus.value as any,
      priority: filterForm.priority as any,
      review_type: filterForm.review_type as any,
      overdue_only: filterForm.overdue_only,
      assigned_to_me: filterForm.assigned_to_me,
      page: pagination.page,
      page_size: pagination.pageSize
    })

    reviewList.value = result.items
    pagination.total = result.total
  } catch (error: any) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const refreshData = () => {
  loadStatistics()
  loadReviews()
  addActivity('refresh', '刷新了数据')
}

const handleNewReviews = () => {
  filterStatus.value = 'pending'
  pagination.page = 1
  loadReviews()
  newReviewsCount.value = 0
}

const handleStatusChange = () => {
  pagination.page = 1
  loadReviews()
}

const filterByStatus = (status: string, overdueOnly: boolean = false) => {
  filterStatus.value = status
  filterForm.overdue_only = overdueOnly
  pagination.page = 1
  loadReviews()
}

const resetFilters = () => {
  filterStatus.value = ''
  filterForm.priority = ''
  filterForm.review_type = ''
  filterForm.overdue_only = false
  filterForm.assigned_to_me = false
  pagination.page = 1
  loadReviews()
}

const handleRowClick = (row: ReviewRequest) => {
  currentReview.value = row
  reviewForm.decision = 'approved'
  reviewForm.result = ''
  reviewForm.comments = ''
  detailDialogVisible.value = true
  loadReviewHistory(row.id)
}

const handleClaim = async (row: ReviewRequest) => {
  try {
    claimingId.value = row.id
    await reviewApiClient.claim(row.id)
    ElMessage.success('任务已领取')
    addActivity('claim', `领取了任务: ${row.title || row.trigger_reason}`)
    loadStatistics()
    loadReviews()
  } catch (error: any) {
    ElMessage.error('领取失败')
  } finally {
    claimingId.value = null
  }
}

const handleClaimFromDialog = async () => {
  if (!currentReview.value) return
  await handleClaim(currentReview.value)
  detailDialogVisible.value = false
}

const handleComplete = async () => {
  if (!currentReview.value) return

  try {
    submitting.value = true
    await reviewApiClient.update(currentReview.value.id, {
      status: 'completed',
      review_result: { decision: reviewForm.decision, details: reviewForm.result },
      review_comments: reviewForm.comments
    })

    ElMessage.success('审核已完成')
    addActivity('complete', `完成了审核: ${currentReview.value.title || currentReview.value.trigger_reason}`)
    detailDialogVisible.value = false
    loadStatistics()
    loadReviews()
  } catch (error: any) {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

const handleReject = async () => {
  if (!currentReview.value) return

  try {
    await ElMessageBox.confirm('确定要驳回此审核吗？', '确认', { type: 'warning' })

    submitting.value = true
    await reviewApiClient.update(currentReview.value.id, {
      status: 'rejected',
      review_result: { decision: 'rejected', details: reviewForm.result },
      review_comments: reviewForm.comments
    })

    ElMessage.warning('审核已驳回')
    addActivity('reject', `驳回了审核: ${currentReview.value.title || currentReview.value.trigger_reason}`)
    detailDialogVisible.value = false
    loadStatistics()
    loadReviews()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  } finally {
    submitting.value = false
  }
}

const loadReviewHistory = async (id: string) => {
  try {
    const review = await reviewApiClient.get(id)
    const actions = await reviewApiClient.getActions(id)
    
    const historyFromReview = [
      {
        timestamp: review.created_at,
        type: 'primary',
        icon: 'Plus',
        title: '任务创建',
        content: '审核任务已创建'
      },
      ...(review.assigned_at ? [{
        timestamp: review.assigned_at,
        type: 'warning',
        icon: 'User',
        title: '任务分配',
        content: `分配给 ${review.assigned_to_name || '未分配'}`
      }] : []),
      ...(review.completed_at ? [{
        timestamp: review.completed_at,
        type: 'success',
        icon: 'Check',
        title: '任务完成',
        content: `审核结论: ${review.review_result?.decision || '-'}`
      }] : [])
    ]
    
    const historyFromActions = actions.map(action => {
      const actionTypeMap: Record<string, { icon: string; type: string }> = {
        'create': { icon: 'Plus', type: 'primary' },
        'start': { icon: 'VideoPlay', type: 'primary' },
        'assign': { icon: 'User', type: 'warning' },
        'complete': { icon: 'Check', type: 'success' },
        'reject': { icon: 'Close', type: 'danger' },
        'cancel': { icon: 'CloseBold', type: 'info' }
      }
      
      const { icon, type } = actionTypeMap[action.action] || { icon: 'Info', type: 'info' }
      
      let content = ''
      if (action.action_details) {
        if (action.action_details.description) {
          content = action.action_details.description
        }
        if (action.action_details.comment) {
          content += content ? `\n意见: ${action.action_details.comment}` : `意见: ${action.action_details.comment}`
        }
      }
      if (!content) {
        content = `执行了 ${action.action} 操作`
      }
      
      return {
        timestamp: action.created_at,
        type,
        icon,
        title: getActionTitle(action.action),
        content
      }
    })
    
    reviewHistory.value = [...historyFromReview, ...historyFromActions]
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  } catch (error) {
    console.error('加载历史记录失败:', error)
  }
}

const getActionTitle = (action: string): string => {
  const titleMap: Record<string, string> = {
    'create': '任务创建',
    'start': '开始处理',
    'assign': '任务分配',
    'complete': '审核通过',
    'reject': '审核驳回',
    'cancel': '任务取消'
  }
  return titleMap[action] || `操作: ${action}`
}

const addActivity = (type: string, text: string) => {
  const time = new Date().toLocaleTimeString()
  recentActivities.value.unshift({ type, text, time })
  if (recentActivities.value.length > 10) {
    recentActivities.value.pop()
  }
}

const getPercentage = (value: number): number => {
  const total = Object.values(statistics.value.priority_breakdown || {}).reduce((a: number, b: number) => a + b, 0)
  return total > 0 ? Math.round((value / total) * 100) : 0
}

const getPriorityType = (priority: string) => {
  const typeMap: Record<string, string> = {
    urgent: 'danger',
    high: 'warning',
    normal: 'primary',
    low: 'info'
  }
  return typeMap[priority] || 'info'
}

const getPriorityText = (priority: string) => {
  const textMap: Record<string, string> = {
    urgent: '紧急',
    high: '高',
    normal: '普通',
    low: '低'
  }
  return textMap[priority] || priority
}

const getStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    rejected: 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待处理',
    in_progress: '处理中',
    completed: '已完成',
    rejected: '已驳回'
  }
  return textMap[status] || status
}

const getTypeName = (type: string) => {
  const nameMap: Record<string, string> = {
    tax: '税务',
    finance: '财务',
    legal: '法务',
    compliance: '合规'
  }
  return nameMap[type] || type
}

const formatSLA = (deadline: string) => {
  const deadlineDate = new Date(deadline)
  const now = new Date()
  const diff = deadlineDate.getTime() - now.getTime()

  if (diff < 0) {
    const hours = Math.abs(Math.floor(diff / (1000 * 60 * 60)))
    return `已逾期${hours}h`
  }

  const hours = Math.floor(diff / (1000 * 60 * 60))
  if (hours < 24) {
    return `${hours}h`
  }
  const days = Math.floor(hours / 24)
  return `${days}天`
}

const formatAge = (hours: number) => {
  if (hours < 1) {
    return `${Math.round(hours * 60)}m`
  }
  if (hours < 24) {
    return `${Math.round(hours)}h`
  }
  const days = Math.floor(hours / 24)
  return `${days}天${Math.round(hours % 24)}h`
}

const subscribeToUpdates = () => {
  try {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/v1/reviews/stream`

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      isConnected.value = true
      console.log('WebSocket连接成功')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.event_type === 'created') {
          newReviewsCount.value++
          addActivity('new', `收到新任务: ${data.title || '新审核'}`)
        }
        if (data.event_type === 'updated') {
          refreshData()
        }
      } catch (e) {
        console.error('解析WebSocket消息失败:', e)
      }
    }

    ws.onerror = () => {
      console.error('WebSocket连接失败，切换到轮询')
      isConnected.value = false
      startPolling()
    }

    ws.onclose = () => {
      isConnected.value = false
      startPolling()
    }
  } catch {
    startPolling()
  }
}

const startPolling = () => {
  if (pollingInterval) return
  pollingInterval = window.setInterval(() => {
    loadStatistics()
  }, 30000)
}

onMounted(() => {
  loadStatistics()
  loadReviews()
  subscribeToUpdates()
})

onUnmounted(() => {
  if (ws) {
    ws.close()
  }
  if (pollingInterval) {
    clearInterval(pollingInterval)
  }
})
</script>

<style scoped>
.review-dashboard {
  padding: 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%);
  min-height: calc(100vh - 60px);
  position: relative;
  overflow: hidden;
}

.review-dashboard::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 400px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  opacity: 0.03;
  pointer-events: none;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  background: white;
  padding: 24px 32px;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
  position: relative;
  z-index: 1;
}

.header-content h1 {
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  color: #64748b;
  margin: 0;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.header-actions :deep(.el-button) {
  transition: all 0.3s ease;
}

.header-actions :deep(.el-button):hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.statistics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 20px;
  position: relative;
  z-index: 1;
}

.stat-card {
  cursor: pointer;
  transition: all 0.3s ease;
  border-radius: 16px;
  border: none;
  overflow: hidden;
  background: white;
}

.stat-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12);
}

.stat-card.pending {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  border-left: none;
}

.stat-card.in-progress {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border-left: none;
}

.stat-card.completed {
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
  border-left: none;
}

.stat-card.overdue {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  border-left: none;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px;
}

.stat-icon {
  background: white;
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.stat-card:hover .stat-icon {
  transform: scale(1.1);
}

.stat-icon.warning {
  color: #ef4444;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #1e293b;
}

.stat-label {
  font-size: 13px;
  color: #64748b;
  margin-top: 4px;
  font-weight: 500;
}

.stat-trend {
  margin-left: auto;
  color: #10b981;
}

.stat-alert {
  margin-left: auto;
  color: #ef4444;
  animation: pulse-alert 2s infinite;
}

@keyframes pulse-alert {
  0%, 100% { 
    opacity: 1;
    transform: scale(1);
  }
  50% { 
    opacity: 0.6;
    transform: scale(1.1);
  }
}

.middle-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
  position: relative;
  z-index: 1;
}

.priority-card,
.activity-card {
  background: white;
  border-radius: 16px;
  border: none;
  transition: all 0.3s ease;
}

.priority-card:hover,
.activity-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.1);
}

.priority-card :deep(.el-card__header),
.activity-card :deep(.el-card__header) {
  padding: 20px 24px;
  border-bottom: 1px solid #f1f5f9;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 16px 16px 0 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #1e293b;
}

.priority-bars {
  margin-bottom: 20px;
}

.priority-item {
  margin-bottom: 20px;
  transition: all 0.3s ease;
}

.priority-item:hover {
  transform: translateX(4px);
}

.priority-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.priority-label .count {
  font-weight: 700;
  color: #1e293b;
  font-size: 16px;
}

.avg-time {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 14px;
  padding: 12px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 10px;
}

.activity-timeline {
  max-height: 300px;
  overflow-y: auto;
  padding: 4px;
}

.activity-item {
  display: flex;
  gap: 16px;
  padding: 16px 12px;
  border-radius: 12px;
  transition: all 0.3s ease;
  background: #f8fafc;
  margin-bottom: 8px;
}

.activity-item:hover {
  background: #f1f5f9;
  transform: translateX(4px);
}

.activity-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #667eea;
  margin-top: 6px;
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(102, 126, 234, 0.4);
}

.activity-dot.refresh { 
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.activity-dot.claim { 
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}
.activity-dot.complete { 
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}
.activity-dot.reject { 
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}
.activity-dot.new { 
  background: linear-gradient(135deg, #64748b 0%, #475569 100%);
}

.activity-content {
  flex: 1;
}

.activity-text {
  color: #475569;
  font-size: 14px;
  line-height: 1.5;
}

.activity-time {
  color: #94a3b8;
  font-size: 12px;
  margin-top: 6px;
  font-weight: 500;
}

.list-card {
  background: white;
  border-radius: 16px;
  border: none;
  position: relative;
  z-index: 1;
}

.list-card :deep(.el-card__header) {
  padding: 20px 24px;
  border-bottom: 1px solid #f1f5f9;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 16px 16px 0 0;
}

.list-card :deep(.el-card__body) {
  padding: 24px;
}

.filter-tabs {
  display: flex;
  gap: 8px;
}

.filter-tabs :deep(.el-radio-button__inner) {
  border-radius: 8px;
  transition: all 0.3s ease;
}

.status-badge {
  margin-left: 4px;
}

.title-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-text {
  font-weight: 500;
  color: #1e293b;
}

.overdue-icon {
  flex-shrink: 0;
  animation: shake 1s ease-in-out infinite;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-2px); }
  75% { transform: translateX(2px); }
}

.wait-time-long {
  color: #ef4444;
  font-weight: 700;
}

.text-muted {
  color: #c0c4cc;
}

.expand-content {
  padding: 20px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 12px;
  margin: 0;
}

.content-preview {
  margin-top: 20px;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 600;
  color: #1e293b;
}

.preview-box {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.preview-stat {
  text-align: center;
  padding: 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 10px;
  transition: all 0.3s ease;
}

.preview-stat:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.preview-stat .label {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
  font-weight: 500;
}

.preview-stat .value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.preview-stat.danger .value {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  -webkit-background-clip: text;
  background-clip: text;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.action-buttons :deep(.el-button) {
  transition: all 0.3s ease;
}

.action-buttons :deep(.el-button):hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.pagination-wrapper {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
}

.review-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.overdue-alert {
  margin-bottom: 20px;
  border-radius: 12px;
}

.basic-info {
  margin-bottom: 24px;
}

.detail-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}

.detail-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 2px;
  background: #e2e8f0;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section h4 {
  margin: 0 0 12px 0;
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.description-text {
  color: #475569;
  line-height: 1.7;
  margin: 0;
  padding: 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 10px;
}

.content-stats {
  margin-top: 16px;
}

.content-display {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  padding: 20px;
  border-radius: 12px;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', monospace;
}

.content-display pre {
  margin: 0;
  font-size: 12px;
  color: #475569;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}

.history-section {
  max-height: 400px;
  overflow-y: auto;
  padding: 8px;
}

.review-form {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #e2e8f0;
}

.review-form :deep(.el-radio-group) {
  display: flex;
  gap: 12px;
}

.review-form :deep(.el-radio) {
  margin: 0;
  padding: 12px 20px;
  border-radius: 10px;
  border: 2px solid #e2e8f0;
  transition: all 0.3s ease;
}

.review-form :deep(.el-radio):hover {
  border-color: #667eea;
  background: #f8fafc;
}

.review-form :deep(.el-radio.is-checked) {
  border-color: #667eea;
  background: linear-gradient(135deg, #edeff5 0%, #e2e8f0 100%);
}

.history-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  transition: all 0.3s ease;
}

.history-card:hover {
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.history-title {
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 8px;
  font-size: 15px;
}

.history-content {
  color: #64748b;
  line-height: 1.6;
  font-size: 14px;
}

.detail-tabs :deep(.el-timeline-item__node) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 2px 6px rgba(102, 126, 234, 0.4);
}

.detail-tabs :deep(.el-timeline-item__wrapper) {
  top: -4px;
}

.overdue-text {
  color: #ef4444;
  font-weight: 600;
}

.detail-tabs :deep(.el-descriptions__label) {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  font-weight: 600;
  color: #1e293b;
}

.detail-tabs :deep(.el-descriptions__cell) {
  padding: 12px 16px;
}

.detail-tabs :deep(.el-tab-pane) {
  padding: 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 12px;
}

.detail-tabs :deep(.el-tabs__item) {
  font-weight: 600;
  color: #64748b;
  transition: all 0.3s ease;
}

.detail-tabs :deep(.el-tabs__item:hover) {
  color: #667eea;
}

.detail-tabs :deep(.el-tabs__item.is-active) {
  color: #667eea;
  font-weight: 700;
}

.review-form :deep(.el-divider--horizontal) {
  border-top: 2px solid #e2e8f0;
}

.review-form :deep(.el-divider__text) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 8px 16px;
  border-radius: 8px;
  font-weight: 600;
}

.review-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: #1e293b;
}

.review-form :deep(.el-input__wrapper) {
  border-radius: 10px;
  transition: all 0.3s ease;
}

.review-form :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
}

.review-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.4);
}

@media (max-width: 1200px) {
  .statistics-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .middle-section {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .statistics-row {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }
}
</style>
