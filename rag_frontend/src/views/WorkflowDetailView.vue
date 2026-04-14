<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElCard, ElSkeleton, ElEmpty, ElButton, ElTag, ElTimeline, ElTimelineItem, ElCollapse, ElCollapseItem, ElTable, ElTableColumn, ElBadge, ElAlert } from 'element-plus'
import { 
  ArrowLeft,
  CheckCircle, 
  XCircle, 
  Clock, 
  Play,
  AlertCircle,
  GitBranch,
  FileText,
  Database,
  Calculator,
  Shield,
  UserCheck,
  Save,
  Target,
  Bell,
  BellRing,
  TrendingUp,
  Users,
  RefreshCw,
  Eye,
  Code
} from 'lucide-vue-next'
import { workflowMonitorApi, type WorkflowExecutionSummary, type WorkflowNodeExecution } from '@/api/workflow-monitor'
import { useEnterpriseTheme } from '@/composables/useEnterpriseTheme'

const route = useRoute()
const router = useRouter()
const { enterpriseTheme } = useEnterpriseTheme()

const primaryColor = computed(() => enterpriseTheme.value.primary_color)

const loading = ref(true)
const workflowDetail = ref<WorkflowExecutionSummary | null>(null)
const error = ref<string | null>(null)

const traceId = computed(() => route.params.id as string)

const nodeIcons: Record<string, any> = {
  data_validation: FileText,
  financial_data: Database,
  tax_calculation: Calculator,
  risk_assessment: Shield,
  human_review: UserCheck,
  save_result: Save,
  policy_collection: FileText,
  policy_parsing: FileText,
  enterprise_matching: Target,
  match_scoring: TrendingUp,
  notification_preparation: Bell,
  notification_sending: BellRing,
  subscription_management: Users,
  policy_update_detection: RefreshCw,
}

const getNodeIcon = (nodeName: string) => {
  const key = nodeName.toLowerCase().replace(/\s+/g, '_')
  return nodeIcons[key] || GitBranch
}

const getStatusType = (status: string): 'success' | 'warning' | 'danger' | 'info' => {
  switch (status) {
    case 'completed': return 'success'
    case 'running': return 'warning'
    case 'failed': return 'danger'
    default: return 'info'
  }
}

const getStatusText = (status: string): string => {
  switch (status) {
    case 'completed': return '已完成'
    case 'running': return '运行中'
    case 'failed': return '失败'
    default: return status
  }
}

const getNodeTypeText = (nodeType: string): string => {
  const map: Record<string, string> = {
    agent: '智能体节点',
    normal: '普通节点',
    human_review: '人工审核节点',
  }
  return map[nodeType] || nodeType
}

const formatTime = (time: string | undefined): string => {
  if (!time) return '-'
  const date = new Date(time)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const formatDuration = (seconds: number | undefined): string => {
  if (!seconds && seconds !== 0) return '-'
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`
  return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`
}

const getProgress = computed(() => {
  if (!workflowDetail.value) return 0
  const { total_nodes, completed_nodes } = workflowDetail.value
  if (total_nodes === 0) return 0
  return Math.round((completed_nodes / total_nodes) * 100)
})

const getWorkflowTypeText = (type: string): string => {
  const map: Record<string, string> = {
    tax_notification: '税务工作流',
    policy_notification: '政策推送',
    human_review: '人工审核',
  }
  return map[type] || type
}

const loadData = async () => {
  loading.value = true
  error.value = null
  
  try {
    workflowDetail.value = await workflowMonitorApi.getTrace(traceId.value)
  } catch (err: any) {
    console.error('加载工作流详情失败:', err)
    error.value = err.response?.data?.detail || err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.back()
}

const formatJson = (data: any): string => {
  if (!data) return '{}'
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="workflow-detail min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
    <!-- Header -->
    <div class="mb-6">
      <div class="flex items-center gap-4 mb-4">
        <el-button circle @click="goBack">
          <ArrowLeft :size="16" />
        </el-button>
        <div class="flex-1">
          <h1 class="text-2xl font-bold text-slate-900">工作流执行详情</h1>
          <p class="text-slate-600 text-sm mt-1">
            <span class="font-mono">{{ traceId }}</span>
          </p>
        </div>
        <el-button @click="loadData" :loading="loading">
          <RefreshCw :size="14" class="mr-1" />
          刷新
        </el-button>
      </div>
    </div>

    <!-- Error Alert -->
    <el-alert
      v-if="error"
      type="error"
      :title="error"
      :closable="false"
      class="mb-6"
    />

    <!-- Loading State -->
    <div v-if="loading" class="space-y-4">
      <el-card :body-style="{ padding: '24px' }">
        <el-skeleton animated :rows="6" />
      </el-card>
    </div>

    <!-- Content -->
    <div v-else-if="workflowDetail" class="space-y-6">
      <!-- Overview Card -->
      <el-card :body-style="{ padding: '24px' }">
        <div class="flex items-start justify-between mb-6">
          <div class="flex items-center gap-4">
            <div 
              class="w-14 h-14 rounded-xl flex items-center justify-center"
              :class="{
                'bg-emerald-100': workflowDetail.status === 'completed',
                'bg-amber-100': workflowDetail.status === 'running',
                'bg-red-100': workflowDetail.status === 'failed',
              }"
            >
              <CheckCircle 
                v-if="workflowDetail.status === 'completed'" 
                :size="28" 
                class="text-emerald-600" 
              />
              <Play 
                v-else-if="workflowDetail.status === 'running'" 
                :size="28" 
                class="text-amber-600" 
              />
              <XCircle 
                v-else 
                :size="28" 
                class="text-red-600" 
              />
            </div>
            <div>
              <h2 class="text-xl font-bold text-slate-800">
                {{ getWorkflowTypeText(workflowDetail.workflow_type) }}
              </h2>
              <div class="flex items-center gap-3 mt-2">
                <el-tag :type="getStatusType(workflowDetail.status)" effect="dark">
                  {{ getStatusText(workflowDetail.status) }}
                </el-tag>
                <span class="text-sm text-slate-500">
                  开始于 {{ formatTime(workflowDetail.started_at) }}
                </span>
              </div>
            </div>
          </div>
          
          <!-- Progress -->
          <div class="text-right">
            <p class="text-sm text-slate-500 mb-1">执行进度</p>
            <p class="text-2xl font-bold text-slate-800">{{ getProgress }}%</p>
            <p class="text-sm text-slate-500">
              {{ workflowDetail.completed_nodes }} / {{ workflowDetail.total_nodes }} 节点
            </p>
          </div>
        </div>

        <!-- Progress Bar -->
        <el-progress 
          :percentage="getProgress" 
          :stroke-width="10"
          :color="workflowDetail.status === 'failed' ? '#f56c6c' : undefined"
        />

        <!-- Info Grid -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-100">
          <div>
            <p class="text-sm text-slate-500 mb-1">当前节点</p>
            <p class="font-medium text-slate-800">
              {{ workflowDetail.current_node || '-' }}
            </p>
          </div>
          <div>
            <p class="text-sm text-slate-500 mb-1">运行时长</p>
            <p class="font-medium text-slate-800">
              {{ formatDuration(workflowDetail.duration) }}
            </p>
          </div>
          <div>
            <p class="text-sm text-slate-500 mb-1">错误数量</p>
            <p class="font-medium" :class="workflowDetail.error_count > 0 ? 'text-red-600' : 'text-slate-800'">
              {{ workflowDetail.error_count }}
            </p>
          </div>
          <div>
            <p class="text-sm text-slate-500 mb-1">人工审核</p>
            <p class="font-medium text-slate-800">
              {{ workflowDetail.human_review_count }}
            </p>
          </div>
        </div>
      </el-card>

      <!-- Node Executions Timeline -->
      <el-card :body-style="{ padding: '24px' }">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="text-lg font-semibold text-slate-800">节点执行历史</span>
            <el-tag type="info">{{ workflowDetail.node_executions.length }} 个节点</el-tag>
          </div>
        </template>

        <el-timeline v-if="workflowDetail.node_executions.length > 0">
          <el-timeline-item
            v-for="node in workflowDetail.node_executions"
            :key="node.id"
            :type="getStatusType(node.status)"
            :hollow="node.status === 'pending'"
          >
            <el-card class="node-card" shadow="hover">
              <div class="flex items-start justify-between">
                <div class="flex items-start gap-3">
                  <div 
                    class="w-10 h-10 rounded-lg flex items-center justify-center"
                    :class="{
                      'bg-emerald-100': node.status === 'completed',
                      'bg-amber-100': node.status === 'running',
                      'bg-red-100': node.status === 'failed',
                      'bg-slate-100': node.status === 'pending',
                    }"
                  >
                    <component 
                      :is="getNodeIcon(node.node_name)" 
                      :size="20"
                      :class="{
                        'text-emerald-600': node.status === 'completed',
                        'text-amber-600': node.status === 'running',
                        'text-red-600': node.status === 'failed',
                        'text-slate-500': node.status === 'pending',
                      }"
                    />
                  </div>
                  <div>
                    <h4 class="font-semibold text-slate-800">{{ node.node_name }}</h4>
                    <div class="flex items-center gap-2 mt-1">
                      <el-tag size="small" type="info">
                        {{ getNodeTypeText(node.node_type) }}
                      </el-tag>
                      <el-tag 
                        size="small" 
                        :type="getStatusType(node.status)"
                        effect="dark"
                      >
                        {{ getStatusText(node.status) }}
                      </el-tag>
                    </div>
                    <p class="text-xs text-slate-500 mt-2">
                      执行顺序: {{ node.execution_order }}
                    </p>
                    <p class="text-xs text-slate-500">
                      耗时: {{ formatDuration(node.duration) }}
                    </p>
                  </div>
                </div>
                
                <div class="text-right text-xs text-slate-500">
                  <p>开始: {{ formatTime(node.started_at) }}</p>
                  <p v-if="node.completed_at">完成: {{ formatTime(node.completed_at) }}</p>
                </div>
              </div>

              <!-- Error Message -->
              <el-alert
                v-if="node.error_message"
                type="error"
                :title="node.error_message"
                :closable="false"
                class="mt-3"
                show-icon
              />

              <!-- Input/Output Data -->
              <el-collapse class="mt-3">
                <el-collapse-item title="输入数据" name="input">
                  <div class="bg-slate-50 p-3 rounded-lg">
                    <pre class="text-xs text-slate-600 overflow-x-auto">{{ formatJson(node.input_data) }}</pre>
                  </div>
                </el-collapse-item>
                <el-collapse-item title="输出数据" name="output">
                  <div class="bg-slate-50 p-3 rounded-lg">
                    <pre class="text-xs text-slate-600 overflow-x-auto">{{ formatJson(node.output_data) }}</pre>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </el-card>
          </el-timeline-item>
        </el-timeline>

        <el-empty v-else description="暂无节点执行记录" />
      </el-card>

      <!-- Metadata -->
      <el-card v-if="workflowDetail.node_executions.length > 0" :body-style="{ padding: '24px' }">
        <template #header>
          <span class="text-lg font-semibold text-slate-800">原始数据</span>
        </template>
        
        <el-table :data="[]" style="width: 100%">
          <el-table-column prop="key" label="属性" width="200" />
          <el-table-column prop="value" label="值">
            <template #default>
              <pre class="text-xs text-slate-600">{{ JSON.stringify(workflowDetail, null, 2) }}</pre>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- Empty State -->
    <el-empty 
      v-else-if="!loading && !error"
      description="工作流不存在或已被删除"
    >
      <el-button type="primary" @click="goBack">返回列表</el-button>
    </el-empty>
  </div>
</template>

<style scoped>
.workflow-detail {
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

.node-card {
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.node-card:hover {
  border-color: #cbd5e1;
}

:deep(.el-timeline-item__content) {
  padding-bottom: 0;
}

:deep(.el-timeline-item__node) {
  background-color: transparent;
}

pre {
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
