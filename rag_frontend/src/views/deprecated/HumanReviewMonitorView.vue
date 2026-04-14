<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElCard, ElSkeleton, ElEmpty, ElButton, ElTag, ElProgress, ElTable, ElTableColumn, ElSelect, ElOption, ElDatePicker, ElPagination, ElDialog, ElForm, ElFormItem, ElInput, ElMessage, ElAvatar, ElBadge } from 'element-plus'
import { 
  Users, 
  CheckCircle, 
  XCircle, 
  Clock, 
  RefreshCw,
  ArrowLeft,
  AlertCircle,
  Plus,
  MessageSquare,
  Eye,
  ThumbsUp,
  ThumbsDown,
  AlertTriangle,
  Send,
  User
} from 'lucide-vue-next'
import { workflowMonitorApi, type HumanReviewTracking, type ReviewActionRecord } from '@/api/workflow-monitor'
import { useEnterpriseTheme } from '@/composables/useEnterpriseTheme'

const router = useRouter()
const { enterpriseTheme } = useEnterpriseTheme()

const primaryColor = computed(() => enterpriseTheme.value.primary_color)

const loading = ref(true)
const reviewList = ref<HumanReviewTracking[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

const selectedStatus = ref('')
const selectedPriority = ref('')

const detailDialogVisible = ref(false)
const currentReview = ref<HumanReviewTracking | null>(null)
const reviewActions = ref<ReviewActionRecord[]>([])
const actionsLoading = ref(false)

const newActionDialogVisible = ref(false)
const actionForm = ref({
  action: 'comment',
  comment: ''
})

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待审核' },
  { value: 'in_review', label: '审核中' },
  { value: 'approved', label: '已批准' },
  { value: 'rejected', label: '已拒绝' },
  { value: 'changes_requested', label: '需要修改' },
  { value: 'escalated', label: '已上报' },
]

const priorityOptions = [
  { value: '', label: '全部优先级' },
  { value: 'low', label: '低' },
  { value: 'normal', label: '普通' },
  { value: 'high', label: '高' },
  { value: 'urgent', label: '紧急' },
]

const actionOptions = [
  { value: 'start_review', label: '开始审核' },
  { value: 'approve', label: '批准' },
  { value: 'reject', label: '拒绝' },
  { value: 'request_changes', label: '要求修改' },
  { value: 'escalate', label: '上报' },
  { value: 'comment', label: '评论' },
  { value: 'complete', label: '完成' },
]

const statistics = computed(() => {
  const pending = reviewList.value.filter(r => r.status === 'pending').length
  const inReview = reviewList.value.filter(r => r.status === 'in_review').length
  const approved = reviewList.value.filter(r => r.status === 'approved').length
  const rejected = reviewList.value.filter(r => r.status === 'rejected').length
  
  return { pending, inReview, approved, rejected, total: total.value }
})

const getStatusType = (status: string): 'info' | 'warning' | 'success' | 'danger' | '' => {
  switch (status) {
    case 'pending': return 'info'
    case 'in_review': return 'warning'
    case 'approved': return 'success'
    case 'rejected': return 'danger'
    case 'changes_requested': return 'warning'
    case 'escalated': return 'danger'
    default: return ''
  }
}

const getStatusText = (status: string): string => {
  const map: Record<string, string> = {
    pending: '待审核',
    in_review: '审核中',
    approved: '已批准',
    rejected: '已拒绝',
    changes_requested: '需修改',
    escalated: '已上报'
  }
  return map[status] || status
}

const getPriorityType = (priority: string): 'info' | 'warning' | 'danger' => {
  switch (priority) {
    case 'low': return 'info'
    case 'normal': return 'info'
    case 'high': return 'warning'
    case 'urgent': return 'danger'
    default: return 'info'
  }
}

const getPriorityText = (priority: string): string => {
  const map: Record<string, string> = {
    low: '低',
    normal: '普通',
    high: '高',
    urgent: '紧急'
  }
  return map[priority] || priority
}

const getActionIcon = (action: string) => {
  switch (action) {
    case 'approve': return ThumbsUp
    case 'reject': return ThumbsDown
    case 'request_changes': return AlertTriangle
    case 'escalate': return AlertCircle
    case 'comment': return MessageSquare
    case 'start_review': return Eye
    default: return MessageSquare
  }
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

const getActionColor = (action: string): string => {
  switch (action) {
    case 'approve': return '#67c23a'
    case 'reject': return '#f56c6c'
    case 'request_changes': return '#e6a23c'
    case 'escalate': return '#f56c6c'
    case 'comment': return '#409eff'
    case 'start_review': return '#409eff'
    default: return '#909399'
  }
}

const formatTime = (time: string | undefined): string => {
  if (!time) return '-'
  const date = new Date(time)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const loadData = async () => {
  loading.value = true
  try {
    const data = await workflowMonitorApi.getHumanReviewTrackings({
      page: currentPage.value,
      page_size: pageSize.value,
      status: selectedStatus.value || undefined,
      priority: selectedPriority.value || undefined,
    })
    
    reviewList.value = data.items
    total.value = data.total
  } catch (error) {
    console.error('加载人工审核数据失败:', error)
  } finally {
    loading.value = false
  }
}

const loadReviewActions = async (trackingId: string) => {
  actionsLoading.value = true
  try {
    reviewActions.value = await workflowMonitorApi.getReviewActions(trackingId)
  } catch (error) {
    console.error('加载审核动作失败:', error)
    reviewActions.value = []
  } finally {
    actionsLoading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  loadData()
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  loadData()
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  loadData()
}

const openDetailDialog = async (review: HumanReviewTracking) => {
  currentReview.value = review
  detailDialogVisible.value = true
  await loadReviewActions(review.id)
}

const closeDetailDialog = () => {
  detailDialogVisible.value = false
  currentReview.value = null
  reviewActions.value = []
}

const submitAction = async () => {
  if (!currentReview.value || !actionForm.value.action) return
  
  try {
    await workflowMonitorApi.recordReviewAction(currentReview.value.id, {
      action: actionForm.value.action,
      comment: actionForm.value.comment || undefined
    })
    
    ElMessage.success('操作成功')
    newActionDialogVisible.value = false
    actionForm.value = { action: 'comment', comment: '' }
    await loadReviewActions(currentReview.value.id)
    await loadData()
  } catch (error) {
    console.error('提交操作失败:', error)
    ElMessage.error('操作失败，请重试')
  }
}

const goBack = () => {
  router.push('/workflow')
}

onMounted(() => {
  loadData()
})

watch([selectedStatus, selectedPriority], () => {
  handleSearch()
})
</script>

<template>
  <div class="human-review-monitor min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
    <!-- Header -->
    <div class="mb-6">
      <div class="flex items-center gap-4 mb-4">
        <el-button circle @click="goBack">
          <ArrowLeft :size="16" />
        </el-button>
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
            <Users :size="24" class="text-blue-600" />
          </div>
          <div>
            <h1 class="text-3xl font-bold text-slate-900">人工审核管理</h1>
            <p class="text-slate-600">管理人工审核流程和处理审核任务</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Statistics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
      <el-card class="stat-card" :body-style="{ padding: '20px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500 mb-1">总审核数</p>
            <p class="text-3xl font-bold text-slate-700">{{ statistics.total }}</p>
          </div>
          <div class="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center">
            <Users :size="20" class="text-slate-600" />
          </div>
        </div>
      </el-card>

      <el-card class="stat-card" :body-style="{ padding: '20px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500 mb-1">待审核</p>
            <p class="text-3xl font-bold text-blue-600">{{ statistics.pending }}</p>
          </div>
          <el-badge :value="statistics.pending" :hidden="statistics.pending === 0" type="primary">
            <div class="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
              <Clock :size="20" class="text-blue-600" />
            </div>
          </el-badge>
        </div>
      </el-card>

      <el-card class="stat-card" :body-style="{ padding: '20px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500 mb-1">审核中</p>
            <p class="text-3xl font-bold text-amber-600">{{ statistics.inReview }}</p>
          </div>
          <div class="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
            <Eye :size="20" class="text-amber-600" />
          </div>
        </div>
      </el-card>

      <el-card class="stat-card" :body-style="{ padding: '20px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500 mb-1">已批准</p>
            <p class="text-3xl font-bold text-emerald-600">{{ statistics.approved }}</p>
          </div>
          <div class="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <ThumbsUp :size="20" class="text-emerald-600" />
          </div>
        </div>
      </el-card>

      <el-card class="stat-card" :body-style="{ padding: '20px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500 mb-1">已拒绝</p>
            <p class="text-3xl font-bold text-red-600">{{ statistics.rejected }}</p>
          </div>
          <div class="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
            <ThumbsDown :size="20" class="text-red-600" />
          </div>
        </div>
      </el-card>
    </div>

    <!-- Filters -->
    <el-card class="mb-6" :body-style="{ padding: '16px' }">
      <div class="flex flex-wrap items-center gap-4">
        <el-select 
          v-model="selectedStatus" 
          placeholder="选择状态"
          clearable
          style="width: 140px"
        >
          <el-option
            v-for="item in statusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        
        <el-select 
          v-model="selectedPriority" 
          placeholder="选择优先级"
          clearable
          style="width: 140px"
        >
          <el-option
            v-for="item in priorityOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        
        <el-button type="primary" @click="handleSearch">
          <RefreshCw :size="14" class="mr-1" />
          搜索
        </el-button>
        
        <el-button @click="loadData">
          <RefreshCw :size="14" class="mr-1" />
          刷新
        </el-button>
      </div>
    </el-card>

    <!-- Review List -->
    <el-card :body-style="{ padding: '0' }">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="text-lg font-semibold text-slate-800">审核任务列表</span>
          <span class="text-sm text-slate-500">共 {{ total }} 条记录</span>
        </div>
      </template>
      
      <el-table 
        :data="reviewList" 
        style="width: 100%"
        :header-cell-style="{ backgroundColor: '#f8fafc', color: '#475569' }"
        v-loading="loading"
        class="review-table"
      >
        <el-table-column prop="id" label="审核ID" width="280">
          <template #default="{ row }">
            <span class="text-xs text-slate-500 font-mono">{{ row.id }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="review_type" label="审核类型" width="140">
          <template #default="{ row }">
            <el-tag size="small">{{ row.review_type }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" size="small" effect="dark">
              {{ getPriorityText(row.priority) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small" effect="dark">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="assigned_to" label="审核人" width="140">
          <template #default="{ row }">
            <div v-if="row.assigned_to" class="flex items-center gap-2">
              <el-avatar :size="24" src="https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png" />
              <span class="text-slate-600">{{ row.assigned_to }}</span>
            </div>
            <span v-else class="text-slate-400">未分配</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="reason" label="审核原因" min-width="200">
          <template #default="{ row }">
            <span class="text-slate-600 text-sm">{{ row.reason || '-' }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="创建时间" width="140">
          <template #default="{ row }">
            <span class="text-slate-600">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" text size="small" @click="openDetailDialog(row)">
              查看详情
            </el-button>
            <el-button 
              v-if="row.status === 'pending'" 
              type="success" 
              text 
              size="small"
              @click="openDetailDialog(row)"
            >
              处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="p-4 border-t border-slate-100 flex justify-end">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <!-- Detail Dialog -->
    <el-dialog
      v-model="detailDialogVisible"
      title="审核详情"
      width="700px"
      :close-on-click-modal="false"
    >
      <div v-if="currentReview" class="space-y-4">
        <!-- Review Info -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <p class="text-sm text-slate-500 mb-1">审核ID</p>
            <p class="text-slate-800 font-mono text-sm">{{ currentReview.id }}</p>
          </div>
          <div>
            <p class="text-sm text-slate-500 mb-1">审核类型</p>
            <el-tag>{{ currentReview.review_type }}</el-tag>
          </div>
          <div>
            <p class="text-sm text-slate-500 mb-1">优先级</p>
            <el-tag :type="getPriorityType(currentReview.priority)" effect="dark">
              {{ getPriorityText(currentReview.priority) }}
            </el-tag>
          </div>
          <div>
            <p class="text-sm text-slate-500 mb-1">状态</p>
            <el-tag :type="getStatusType(currentReview.status)" effect="dark">
              {{ getStatusText(currentReview.status) }}
            </el-tag>
          </div>
          <div>
            <p class="text-sm text-slate-500 mb-1">审核人</p>
            <p class="text-slate-800">{{ currentReview.assigned_to || '未分配' }}</p>
          </div>
          <div>
            <p class="text-sm text-slate-500 mb-1">创建时间</p>
            <p class="text-slate-800">{{ formatTime(currentReview.created_at) }}</p>
          </div>
        </div>
        
        <div>
          <p class="text-sm text-slate-500 mb-1">审核原因</p>
          <p class="text-slate-800 bg-slate-50 p-3 rounded-lg">{{ currentReview.reason || '无' }}</p>
        </div>

        <!-- Action Timeline -->
        <div>
          <div class="flex items-center justify-between mb-3">
            <p class="text-sm font-medium text-slate-700">审核历史</p>
            <el-button type="primary" size="small" @click="newActionDialogVisible = true">
              <Plus :size="14" class="mr-1" />
              添加操作
            </el-button>
          </div>
          
          <div class="space-y-3 max-h-60 overflow-y-auto">
            <div 
              v-for="action in reviewActions" 
              :key="action.id"
              class="flex items-start gap-3 p-3 bg-slate-50 rounded-lg"
            >
              <div 
                class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                :style="{ backgroundColor: `${getActionColor(action.action)}20` }"
              >
                <component 
                  :is="getActionIcon(action.action)" 
                  :size="14" 
                  :style="{ color: getActionColor(action.action) }"
                />
              </div>
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-slate-800">{{ getActionText(action.action) }}</span>
                  <span v-if="action.actor_name" class="text-sm text-slate-500">
                    by {{ action.actor_name }}
                  </span>
                </div>
                <p v-if="action.comment" class="text-sm text-slate-600 mt-1">{{ action.comment }}</p>
                <p class="text-xs text-slate-400 mt-1">{{ formatTime(action.created_at) }}</p>
              </div>
            </div>
            
            <el-empty 
              v-if="reviewActions.length === 0 && !actionsLoading" 
              description="暂无审核历史"
              :image-size="60"
            />
          </div>
        </div>
      </div>
      
      <template #footer>
        <el-button @click="closeDetailDialog">关闭</el-button>
        <el-button type="primary" @click="newActionDialogVisible = true">
          <Plus :size="14" class="mr-1" />
          添加操作
        </el-button>
      </template>
    </el-dialog>

    <!-- New Action Dialog -->
    <el-dialog
      v-model="newActionDialogVisible"
      title="添加审核操作"
      width="500px"
    >
      <el-form :model="actionForm" label-width="80px">
        <el-form-item label="操作类型">
          <el-select v-model="actionForm.action" style="width: 100%">
            <el-option
              v-for="item in actionOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="actionForm.comment"
            type="textarea"
            :rows="3"
            placeholder="请输入备注信息（可选）"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="newActionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAction">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.human-review-monitor {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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

.review-table {
  cursor: pointer;
}

:deep(.el-table__row) {
  transition: background-color 0.2s ease;
}

:deep(.el-table__row:hover) {
  background-color: #f8fafc;
}

.custom-scrollbar {
  scrollbar-width: thin;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #cbd5e1;
  border-radius: 3px;
}
</style>
