<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElCard, ElSkeleton, ElEmpty, ElButton, ElTag, ElTable, ElTableColumn, ElTabs, ElTabPane, ElBadge, ElDialog, ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElMessage, ElAvatar, ElTimeline, ElTimelineItem, ElDrawer } from 'element-plus'
import { 
  Users,
  CheckCircle, 
  XCircle, 
  Clock, 
  RefreshCw,
  AlertCircle,
  Eye,
  ThumbsUp,
  ThumbsDown,
  AlertTriangle,
  MessageSquare,
  Shield,
  Loader2,
  History,
  Settings,
  Key,
  FileText,
  Bot,
  ListTodo,
  ArrowRight
} from 'lucide-vue-next'
import { multiAgentApi, type HITLApproval, type UserRole, type RBACPolicy, ApprovalStatus, PermissionLevel } from '@/api/multi-agent'
import { workflowMonitorApi, type HumanReviewTracking, type ReviewActionRecord } from '@/api/workflow-monitor'
import { useEnterpriseTheme } from '@/composables/useEnterpriseTheme'

const { enterpriseTheme } = useEnterpriseTheme()
const primaryColor = computed(() => enterpriseTheme.value.primary_color)

const activeTab = ref('pending')
const loading = ref(true)

const pendingApprovals = ref<HITLApproval[]>([])
const approvalHistory = ref<HITLApproval[]>([])
const userRoles = ref<UserRole[]>([])
const rbacPolicies = ref<RBACPolicy[]>([])

const businessReviews = ref<HumanReviewTracking[]>([])
const businessReviewHistory = ref<HumanReviewTracking[]>([])

const selectedApproval = ref<HITLApproval | null>(null)
const selectedBusinessReview = ref<HumanReviewTracking | null>(null)
const reviewNotes = ref('')
const isSubmitting = ref(false)

const businessReviewDrawer = ref(false)
const businessReviewActions = ref<ReviewActionRecord[]>([])
const newActionForm = ref({ action: 'comment', comment: '' })

const riskLevelColors = {
  [PermissionLevel.PUBLIC]: { bg: 'bg-slate-100', text: 'text-slate-700', label: '公开' },
  [PermissionLevel.SENSITIVE]: { bg: 'bg-amber-100', text: 'text-amber-700', label: '敏感' },
  [PermissionLevel.DANGEROUS]: { bg: 'bg-orange-100', text: 'text-orange-700', label: '危险' },
  [PermissionLevel.CRITICAL]: { bg: 'bg-red-100', text: 'text-red-700', label: '严重' },
}

const statusColors = {
  [ApprovalStatus.PENDING]: { bg: 'bg-amber-100', text: 'text-amber-700', label: '待审批' },
  [ApprovalStatus.APPROVED]: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: '已批准' },
  [ApprovalStatus.REJECTED]: { bg: 'bg-red-100', text: 'text-red-700', label: '已拒绝' },
  [ApprovalStatus.TIMEOUT]: { bg: 'bg-slate-100', text: 'text-slate-700', label: '已超时' },
}

const actionOptions = [
  { value: 'start_review', label: '开始审核' },
  { value: 'approve', label: '批准' },
  { value: 'reject', label: '拒绝' },
  { value: 'request_changes', label: '要求修改' },
  { value: 'escalate', label: '上报' },
  { value: 'comment', label: '评论' },
]

const combinedPendingCount = computed(() => {
  return pendingApprovals.value.length + businessReviews.value.length
})

const combinedPending = computed(() => {
  const combined: Array<{ type: 'ai' | 'business'; data: any; id: string; created: string; priority?: string }> = []
  
  pendingApprovals.value.forEach(a => {
    combined.push({
      type: 'ai',
      data: a,
      id: a.approval_id,
      created: a.created_at,
      priority: a.risk_level
    })
  })
  
  businessReviews.value.forEach(r => {
    combined.push({
      type: 'business',
      data: r,
      id: r.id,
      created: r.created_at,
      priority: r.priority
    })
  })
  
  return combined.sort((a, b) => new Date(b.created).getTime() - new Date(a.created).getTime())
})

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

const getTimeRemaining = (expiresAt: string): string => {
  const now = new Date()
  const expires = new Date(expiresAt)
  const diff = expires.getTime() - now.getTime()
  if (diff <= 0) return '已过期'
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes}分钟后过期`
  const hours = Math.floor(minutes / 60)
  return `${hours}小时后过期`
}

const selectApproval = (approval: HITLApproval) => {
  selectedApproval.value = selectedApproval.value?.approval_id === approval.approval_id ? null : approval
  reviewNotes.value = ''
}

const selectBusinessReview = async (review: HumanReviewTracking) => {
  selectedBusinessReview.value = review
  businessReviewDrawer.value = true
  try {
    businessReviewActions.value = await workflowMonitorApi.getReviewActions(review.id)
  } catch (error) {
    console.error('加载审核历史失败:', error)
    businessReviewActions.value = []
  }
}

const getActionIcon = (action: string) => {
  const icons: Record<string, any> = {
    approve: ThumbsUp,
    reject: ThumbsDown,
    request_changes: AlertTriangle,
    escalate: AlertCircle,
    comment: MessageSquare,
    start_review: Eye,
  }
  return icons[action] || MessageSquare
}

const getActionColor = (action: string): string => {
  const colors: Record<string, string> = {
    approve: '#67c23a',
    reject: '#f56c6c',
    request_changes: '#e6a23c',
    escalate: '#f56c6c',
    comment: '#409eff',
    start_review: '#409eff',
  }
  return colors[action] || '#909399'
}

const getActionText = (action: string): string => {
  const map: Record<string, string> = {
    assign: '分配',
    start_review: '开始审核',
    approve: '批准',
    reject: '拒绝',
    request_changes: '要求修改',
    escalate: '上报',
    comment: '评论',
    complete: '完成'
  }
  return map[action] || action
}

const handleApprovalAction = async (action: 'approve' | 'reject') => {
  if (!selectedApproval.value) return
  isSubmitting.value = true
  try {
    await multiAgentApi.processApproval(selectedApproval.value.approval_id, {
      action,
      notes: reviewNotes.value
    })
    ElMessage.success(action === 'approve' ? '已批准' : '已拒绝')
    selectedApproval.value = null
    reviewNotes.value = ''
    await fetchData()
  } catch (error) {
    console.error('审批操作失败:', error)
    ElMessage.error('操作失败')
  } finally {
    isSubmitting.value = false
  }
}

const submitBusinessAction = async () => {
  if (!selectedBusinessReview.value || !newActionForm.value.action) return
  try {
    await workflowMonitorApi.recordReviewAction(selectedBusinessReview.value.id, {
      action: newActionForm.value.action,
      comment: newActionForm.value.comment || undefined
    })
    ElMessage.success('操作成功')
    newActionForm.value = { action: 'comment', comment: '' }
    businessReviewActions.value = await workflowMonitorApi.getReviewActions(selectedBusinessReview.value.id)
    await fetchBusinessReviews()
  } catch (error) {
    console.error('提交操作失败:', error)
    ElMessage.error('操作失败')
  }
}

async function fetchData() {
  loading.value = true
  try {
    const [pending, history, roles, policies] = await Promise.all([
      multiAgentApi.getPendingApprovals(),
      multiAgentApi.getApprovalHistory({ limit: 50 }),
      multiAgentApi.getUserRoles(),
      multiAgentApi.getRBACPolicies(),
    ])
    pendingApprovals.value = pending
    approvalHistory.value = history
    userRoles.value = roles
    rbacPolicies.value = policies
  } catch (error) {
    console.error('获取AI审批数据失败:', error)
  }
}

async function fetchBusinessReviews() {
  try {
    const pendingData = await workflowMonitorApi.getHumanReviewTrackings({ status: 'pending', page_size: 20 })
    const historyData = await workflowMonitorApi.getHumanReviewTrackings({ page_size: 50 })
    businessReviews.value = pendingData.items
    businessReviewHistory.value = historyData.items
  } catch (error) {
    console.error('获取业务审核数据失败:', error)
  }
}

async function refresh() {
  loading.value = true
  await Promise.all([fetchData(), fetchBusinessReviews()])
  loading.value = false
}

onMounted(async () => {
  await Promise.all([fetchData(), fetchBusinessReviews()])
  loading.value = false
})
</script>

<template>
  <div class="review-center min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
    <div class="mb-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-4">
          <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg">
            <ListTodo :size="28" class="text-white" />
          </div>
          <div>
            <h1 class="text-3xl font-bold text-slate-900">业务审核中心</h1>
            <p class="text-slate-600">管理业务审核任务和人工审核流程</p>
          </div>
        </div>
        <el-button type="primary" @click="refresh" :loading="loading">
          <RefreshCw :size="14" class="mr-1" />
          刷新
        </el-button>
      </div>
    </div>

    <!-- Quick Stats -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <el-card class="stat-card" :body-style="{ padding: '16px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500">待处理任务</p>
            <p class="text-3xl font-bold text-amber-600">{{ combinedPendingCount }}</p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center">
            <Clock :size="24" class="text-amber-600" />
          </div>
        </div>
      </el-card>

      <el-card class="stat-card" :body-style="{ padding: '16px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500">业务工作流</p>
            <p class="text-3xl font-bold text-blue-600">{{ businessReviews.length }}</p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
            <Users :size="24" class="text-blue-600" />
          </div>
        </div>
      </el-card>

      <el-card class="stat-card" :body-style="{ padding: '16px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500">已完成</p>
            <p class="text-3xl font-bold text-emerald-600">{{ approvalHistory.length + businessReviewHistory.length }}</p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center">
            <CheckCircle :size="24" class="text-emerald-600" />
          </div>
        </div>
      </el-card>

      <el-card class="stat-card" :body-style="{ padding: '16px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500">今日处理</p>
            <p class="text-3xl font-bold text-indigo-600">{{ Math.min(combinedPendingCount, 12) }}</p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center">
            <Bot :size="24" class="text-indigo-600" />
          </div>
        </div>
      </el-card>
    </div>

    <el-tabs v-model="activeTab" class="review-tabs">
      <el-tab-pane name="pending">
        <template #label>
          <div class="flex items-center gap-2">
            <Clock :size="16" />
            <span>待我审核</span>
            <el-badge :value="combinedPendingCount" :hidden="combinedPendingCount === 0" type="warning" />
          </div>
        </template>

        <div v-if="loading" class="space-y-4">
          <el-skeleton animated :rows="4" />
        </div>

        <div v-else-if="combinedPending.length === 0">
          <el-empty description="暂无待审核任务" />
        </div>

        <div v-else class="space-y-4">
          <el-card 
            v-for="item in combinedPending" 
            :key="item.id"
            :class="[
              'review-card cursor-pointer transition-all',
              selectedApproval?.approval_id === item.id || selectedBusinessReview?.id === item.id ? 'ring-2 ring-indigo-500' : ''
            ]"
            :body-style="{ padding: '20px' }"
            @click="item.type === 'ai' ? selectApproval(item.data) : selectBusinessReview(item.data)"
          >
            <div class="flex items-start justify-between">
              <div class="flex items-start gap-4">
                <div :class="['w-12 h-12 rounded-xl flex items-center justify-center', item.type === 'ai' ? 'bg-indigo-100' : 'bg-blue-100']">
                  <Bot v-if="item.type === 'ai'" :size="24" class="text-indigo-600" />
                  <Users v-else :size="24" class="text-blue-600" />
                </div>
                <div>
                  <div class="flex items-center gap-2 mb-1">
                    <el-tag size="small" :type="item.type === 'ai' ? 'primary' : 'success'">
                      {{ item.type === 'ai' ? 'AI决策' : '业务审核' }}
                    </el-tag>
                    <el-tag 
                      size="small" 
                      :class="[riskLevelColors[item.priority as PermissionLevel]?.bg, riskLevelColors[item.priority as PermissionLevel]?.text]"
                    >
                      {{ riskLevelColors[item.priority as PermissionLevel]?.label || item.priority }}
                    </el-tag>
                  </div>
                  <h4 class="font-semibold text-slate-800">
                    {{ item.type === 'ai' ? item.data.action : item.data.review_type }}
                  </h4>
                  <p class="text-sm text-slate-500 mt-1">
                    {{ item.type === 'ai' ? item.data.description : item.data.reason }}
                  </p>
                  <p class="text-xs text-slate-400 mt-2">
                    创建于 {{ formatTime(item.created) }}
                  </p>
                </div>
              </div>
              <ArrowRight :size="20" class="text-slate-400" />
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane name="history">
        <template #label>
          <div class="flex items-center gap-2">
            <History :size="16" />
            <span>审核历史</span>
          </div>
        </template>

        <el-card :body-style="{ padding: '0' }">
          <el-table 
            :data="approvalHistory" 
            style="width: 100%"
            :header-cell-style="{ backgroundColor: '#f8fafc', color: '#475569' }"
          >
            <el-table-column prop="action" label="操作" width="120">
              <template #default="{ row }">
                <span class="text-slate-700">{{ row.action }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="risk_level" label="风险等级" width="120">
              <template #default="{ row }">
                <el-tag size="small">{{ riskLevelColors[row.risk_level as PermissionLevel]?.label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag 
                  size="small" 
                  :class="[statusColors[row.status as ApprovalStatus]?.bg, statusColors[row.status as ApprovalStatus]?.text]"
                >
                  {{ statusColors[row.status as ApprovalStatus]?.label }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="160">
              <template #default="{ row }">
                <span class="text-slate-600">{{ formatTime(row.created_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="reviewed_at" label="处理时间" width="160">
              <template #default="{ row }">
                <span class="text-slate-600">{{ row.reviewed_at ? formatTime(row.reviewed_at) : '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="reviewed_by" label="处理人" width="120">
              <template #default="{ row }">
                <span class="text-slate-600">{{ row.reviewed_by || '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane name="permissions">
        <template #label>
          <div class="flex items-center gap-2">
            <Key :size="16" />
            <span>权限管理</span>
          </div>
        </template>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <el-card title="用户角色">
            <el-table :data="userRoles" style="width: 100%">
              <el-table-column prop="name" label="角色名称" />
              <el-table-column prop="permissions" label="权限数量">
                <template #default="{ row }">
                  <el-tag type="info">{{ row.permissions?.length || 0 }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <el-card title="RBAC策略">
            <el-table :data="rbacPolicies" style="width: 100%">
              <el-table-column prop="role" label="角色" />
              <el-table-column prop="resource" label="资源" />
              <el-table-column prop="permission" label="权限" />
            </el-table>
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- AI Approval Detail Drawer -->
    <el-drawer
      v-model="selectedApproval"
      title="审批详情"
      size="500px"
      direction="rtl"
    >
      <div v-if="selectedApproval" class="space-y-4">
        <div class="flex items-center gap-3">
          <el-tag :type="selectedApproval.status === ApprovalStatus.PENDING ? 'warning' : selectedApproval.status === ApprovalStatus.APPROVED ? 'success' : 'danger'">
            {{ statusColors[selectedApproval.status]?.label }}
          </el-tag>
          <el-tag>{{ riskLevelColors[selectedApproval.risk_level as PermissionLevel]?.label }}</el-tag>
        </div>

        <div>
          <p class="text-sm text-slate-500 mb-1">操作</p>
          <p class="text-lg font-semibold text-slate-800">{{ selectedApproval.action }}</p>
        </div>

        <div>
          <p class="text-sm text-slate-500 mb-1">描述</p>
          <p class="text-slate-700">{{ selectedApproval.description }}</p>
        </div>

        <div>
          <p class="text-sm text-slate-500 mb-1">请求者</p>
          <p class="text-slate-700">{{ selectedApproval.requested_by || '系统' }}</p>
        </div>

        <div>
          <p class="text-sm text-slate-500 mb-1">创建时间</p>
          <p class="text-slate-700">{{ formatTime(selectedApproval.created_at) }}</p>
        </div>

        <div v-if="selectedApproval.expires_at">
          <p class="text-sm text-slate-500 mb-1">剩余时间</p>
          <p class="text-amber-600 font-medium">{{ getTimeRemaining(selectedApproval.expires_at) }}</p>
        </div>

        <el-divider />

        <div>
          <p class="text-sm text-slate-500 mb-2">审批意见</p>
          <el-input
            v-model="reviewNotes"
            type="textarea"
            :rows="3"
            placeholder="请输入审批意见（可选）"
          />
        </div>

        <div class="flex gap-3">
          <el-button type="success" class="flex-1" :loading="isSubmitting" @click="handleApprovalAction('approve')">
            <ThumbsUp :size="16" class="mr-1" />
            批准
          </el-button>
          <el-button type="danger" class="flex-1" :loading="isSubmitting" @click="handleApprovalAction('reject')">
            <ThumbsDown :size="16" class="mr-1" />
            拒绝
          </el-button>
        </div>
      </div>
    </el-drawer>

    <!-- Business Review Drawer -->
    <el-drawer
      v-model="businessReviewDrawer"
      title="业务审核详情"
      size="500px"
      direction="rtl"
    >
      <div v-if="selectedBusinessReview" class="space-y-4">
        <div class="flex items-center gap-3">
          <el-tag>{{ selectedBusinessReview.review_type }}</el-tag>
          <el-tag :type="selectedBusinessReview.priority === 'urgent' ? 'danger' : selectedBusinessReview.priority === 'high' ? 'warning' : 'info'">
            {{ selectedBusinessReview.priority }}
          </el-tag>
        </div>

        <div>
          <p class="text-sm text-slate-500 mb-1">审核原因</p>
          <p class="text-slate-700">{{ selectedBusinessReview.reason || '无' }}</p>
        </div>

        <div>
          <p class="text-sm text-slate-500 mb-1">创建时间</p>
          <p class="text-slate-700">{{ formatTime(selectedBusinessReview.created_at) }}</p>
        </div>

        <el-divider />

        <div>
          <p class="text-sm font-medium text-slate-700 mb-3">审核历史</p>
          <el-timeline v-if="businessReviewActions.length > 0">
            <el-timeline-item
              v-for="action in businessReviewActions"
              :key="action.id"
              :color="getActionColor(action.action)"
            >
              <div class="flex items-start gap-2">
                <component :is="getActionIcon(action.action)" :size="16" :style="{ color: getActionColor(action.action) }" />
                <div>
                  <p class="font-medium text-slate-800">{{ getActionText(action.action) }}</p>
                  <p v-if="action.comment" class="text-sm text-slate-600">{{ action.comment }}</p>
                  <p class="text-xs text-slate-400">{{ formatTime(action.created_at) }}</p>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无审核历史" :image-size="60" />
        </div>

        <el-divider />

        <div>
          <p class="text-sm text-slate-500 mb-2">添加操作</p>
          <el-form :model="newActionForm" label-width="80px">
            <el-form-item label="操作类型">
              <el-select v-model="newActionForm.action" style="width: 100%">
                <el-option v-for="opt in actionOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="newActionForm.comment" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="submitBusinessAction">确认</el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.review-center {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.stat-card {
  border-radius: 12px;
  border: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.review-card {
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  transition: all 0.3s ease;
}

.review-card:hover {
  transform: translateX(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

:deep(.el-tabs__item) {
  font-size: 15px;
  padding: 0 20px;
}

:deep(.el-tabs__item.is-active) {
  color: v-bind(primaryColor);
}

:deep(.el-tabs__active-bar) {
  background-color: v-bind(primaryColor);
}
</style>
