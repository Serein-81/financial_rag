<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElCard, ElSkeleton, ElEmpty, ElButton, ElTag, ElProgress, ElTable, ElTableColumn } from 'element-plus'
import { 
  Activity, 
  CheckCircle, 
  XCircle, 
  Clock, 
  TrendingUp,
  GitBranch,
  Users,
  FileBarChart,
  Sparkles,
  ArrowRight,
  RefreshCw,
  AlertCircle,
  Play,
  Pause
} from 'lucide-vue-next'
import { workflowMonitorApi, type WorkflowTrace, type WorkflowStatistics } from '@/api/workflow-monitor'
import { useEnterpriseTheme } from '@/composables/useEnterpriseTheme'

const router = useRouter()
const { enterpriseTheme } = useEnterpriseTheme()

const primaryColor = computed(() => enterpriseTheme.value.primary_color)
const secondaryColor = computed(() => enterpriseTheme.value.secondary_color)

const loading = ref(true)
const statistics = ref<WorkflowStatistics | null>(null)
const recentTraces = ref<WorkflowTrace[]>([])
const runningWorkflows = ref<WorkflowTrace[]>([])
const autoRefresh = ref(true)
let refreshInterval: number | null = null

const statCards = computed(() => {
  if (!statistics.value) return []
  
  return [
    {
      title: '总工作流数',
      value: statistics.value.total_workflows,
      icon: GitBranch,
      color: primaryColor.value,
      change: null,
      changeType: null
    },
    {
      title: '正在运行',
      value: statistics.value.running_workflows,
      icon: Play,
      color: '#409eff',
      change: null,
      changeType: 'running'
    },
    {
      title: '已完成',
      value: statistics.value.completed_workflows,
      icon: CheckCircle,
      color: '#67c23a',
      change: null,
      changeType: 'completed'
    },
    {
      title: '失败',
      value: statistics.value.failed_workflows,
      icon: XCircle,
      color: '#f56c6c',
      change: null,
      changeType: 'failed'
    }
  ]
})

const successRate = computed(() => {
  if (!statistics.value || statistics.value.total_workflows === 0) return 0
  return Math.round((statistics.value.completed_workflows / statistics.value.total_workflows) * 100)
})

const averageDurationFormatted = computed(() => {
  if (!statistics.value) return '0s'
  const seconds = statistics.value.average_duration
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
})

const workflowTypeOptions = [
  { type: 'tax_notification', label: '税务工作流', icon: FileBarChart, color: '#667eea', path: '/workflow/tax' },
  { type: 'policy_notification', label: '政策推送', icon: Sparkles, color: '#f093fb', path: '/workflow/policy' },
  { type: 'human_review', label: '人工审核', icon: Users, color: '#4facfe', path: '/workflow/reviews' },
]

const workflowsByType = computed(() => {
  if (!statistics.value) return []
  
  return workflowTypeOptions.map(opt => ({
    ...opt,
    count: statistics.value?.workflows_by_type?.[opt.type] || 0
  }))
})

const formatDuration = (seconds: number | undefined): string => {
  if (!seconds) return '-'
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
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

const getWorkflowTypeText = (type: string): string => {
  const typeMap: Record<string, string> = {
    'tax_notification': '税务工作流',
    'policy_notification': '政策推送',
    'human_review': '人工审核'
  }
  return typeMap[type] || type
}

const loadData = async () => {
  loading.value = true
  try {
    const [statsData, tracesData, runningData] = await Promise.all([
      workflowMonitorApi.getStatistics(),
      workflowMonitorApi.getTraces({ page: 1, page_size: 10 }),
      workflowMonitorApi.getRunningWorkflows()
    ])
    
    statistics.value = statsData
    recentTraces.value = tracesData.items
    runningWorkflows.value = runningData
  } catch (error) {
    console.error('加载工作流数据失败:', error)
  } finally {
    loading.value = false
  }
}

const refresh = async () => {
  await loadData()
}

const goToWorkflow = (trace: WorkflowTrace) => {
  router.push(`/workflow/detail/${trace.id}`)
}

const goToWorkflowType = (path: string) => {
  router.push(path)
}

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}

const startAutoRefresh = () => {
  if (refreshInterval) return
  refreshInterval = window.setInterval(() => {
    if (autoRefresh.value) {
      loadData()
    }
  }, 30000)
}

const stopAutoRefresh = () => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
    refreshInterval = null
  }
}

onMounted(() => {
  loadData()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<template>
  <div class="workflow-dashboard min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
    <!-- Header -->
    <div class="mb-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-3xl font-bold text-slate-900 mb-2">工作流监控中心</h1>
          <p class="text-slate-600">实时监控所有工作流执行状态和性能指标</p>
        </div>
        <div class="flex items-center gap-3">
          <el-button 
            :type="autoRefresh ? 'primary' : 'default'"
            @click="toggleAutoRefresh"
            circle
          >
            <RefreshCw :size="16" :class="{ 'animate-spin': autoRefresh }" />
          </el-button>
          <el-button type="primary" @click="refresh" :loading="loading">
            刷新数据
          </el-button>
        </div>
      </div>
    </div>

    <!-- Statistics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <el-card 
        v-for="(stat, index) in statCards" 
        :key="index"
        class="stat-card hover:shadow-lg transition-all duration-300"
        :body-style="{ padding: '20px' }"
      >
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500 mb-1">{{ stat.title }}</p>
            <p class="text-3xl font-bold" :style="{ color: stat.color }">
              <el-skeleton v-if="loading" animated :rows="0" />
              <span v-else>{{ stat.value }}</span>
            </p>
          </div>
          <div 
            class="w-12 h-12 rounded-xl flex items-center justify-center"
            :style="{ backgroundColor: `${stat.color}15` }"
          >
            <component :is="stat.icon" :size="24" :style="{ color: stat.color }" />
          </div>
        </div>
      </el-card>
    </div>

    <!-- Main Content Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
      <!-- Success Rate Card -->
      <el-card class="success-rate-card" :body-style="{ padding: '24px' }">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-slate-800">成功率</h3>
          <TrendingUp :size="20" class="text-slate-400" />
        </div>
        <div class="flex items-center justify-center">
          <el-progress
            type="circle"
            :percentage="successRate"
            :width="160"
            :stroke-width="12"
            :color="[
              { color: '#f56c6c', percentage: 25 },
              { color: '#e6a23c', percentage: 50 },
              { color: '#67c23a', percentage: 75 },
              { color: '#409eff', percentage: 100 }
            ]"
          >
            <template #default>
              <div class="text-center">
                <p class="text-4xl font-bold text-slate-800">{{ successRate }}%</p>
                <p class="text-sm text-slate-500 mt-1">总体成功率</p>
              </div>
            </template>
          </el-progress>
        </div>
        <div class="mt-4 flex justify-center gap-8 text-sm">
          <div class="text-center">
            <p class="text-slate-600">平均耗时</p>
            <p class="font-semibold text-slate-800">{{ averageDurationFormatted }}</p>
          </div>
        </div>
      </el-card>

      <!-- Workflow Types Distribution -->
      <el-card class="workflow-types-card" :body-style="{ padding: '24px' }">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">工作流类型分布</h3>
        <div class="space-y-4">
          <div 
            v-for="wf in workflowsByType" 
            :key="wf.type"
            class="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
            @click="goToWorkflowType(wf.path)"
          >
            <div class="flex items-center gap-3">
              <div 
                class="w-10 h-10 rounded-lg flex items-center justify-center"
                :style="{ backgroundColor: `${wf.color}15` }"
              >
                <component :is="wf.icon" :size="20" :style="{ color: wf.color }" />
              </div>
              <div>
                <p class="font-medium text-slate-800">{{ wf.label }}</p>
                <p class="text-sm text-slate-500">{{ wf.count }} 个工作流</p>
              </div>
            </div>
            <ArrowRight :size="16" class="text-slate-400" />
          </div>
        </div>
      </el-card>

      <!-- Running Workflows -->
      <el-card class="running-workflows-card" :body-style="{ padding: '24px' }">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-slate-800">正在运行</h3>
          <el-tag type="warning" size="small">{{ runningWorkflows.length }}</el-tag>
        </div>
        <div class="space-y-3 max-h-64 overflow-y-auto">
          <div 
            v-for="wf in runningWorkflows.slice(0, 5)" 
            :key="wf.id"
            class="p-3 rounded-lg bg-blue-50 border border-blue-100 hover:border-blue-200 transition-colors cursor-pointer"
            @click="goToWorkflow(wf)"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="font-medium text-slate-800 text-sm">{{ getWorkflowTypeText(wf.workflow_type) }}</span>
              <el-tag type="warning" size="small" effect="dark">
                <Play :size="10" class="mr-1" />
                运行中
              </el-tag>
            </div>
            <p class="text-xs text-slate-500">
              节点: {{ wf.completed_nodes }}/{{ wf.total_nodes }} | {{ wf.current_node }}
            </p>
          </div>
          <el-empty 
            v-if="runningWorkflows.length === 0" 
            description="暂无运行中的工作流"
            :image-size="60"
          />
        </div>
      </el-card>
    </div>

    <!-- Recent Workflows Table -->
    <el-card class="recent-workflows-card" :body-style="{ padding: '0' }">
      <div class="p-4 border-b border-slate-100 flex items-center justify-between">
        <h3 class="text-lg font-semibold text-slate-800">最近工作流追踪</h3>
        <el-button type="primary" text @click="router.push('/workflow/traces')">
          查看全部
          <ArrowRight :size="14" class="ml-1" />
        </el-button>
      </div>
      <el-table 
        :data="recentTraces" 
        style="width: 100%"
        :header-cell-style="{ backgroundColor: '#f8fafc', color: '#475569' }"
        @row-click="goToWorkflow"
        class="workflow-table"
      >
        <el-table-column prop="workflow_type" label="工作流类型" min-width="140">
          <template #default="{ row }">
            <div class="flex items-center gap-2">
              <FileBarChart v-if="row.workflow_type === 'tax_notification'" :size="16" class="text-indigo-500" />
              <Sparkles v-else-if="row.workflow_type === 'policy_notification'" :size="16" class="text-pink-500" />
              <Users v-else :size="16" class="text-blue-500" />
              <span>{{ getWorkflowTypeText(row.workflow_type) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small" effect="dark">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="completed_nodes" label="进度" width="180">
          <template #default="{ row }">
            <div class="flex items-center gap-2">
              <el-progress 
                :percentage="Math.round((row.completed_nodes / row.total_nodes) * 100)" 
                :stroke-width="8"
                style="width: 100px"
              />
              <span class="text-xs text-slate-500">
                {{ row.completed_nodes }}/{{ row.total_nodes }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="current_node" label="当前节点" min-width="120">
          <template #default="{ row }">
            <span class="text-slate-600">{{ row.current_node || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="耗时" width="100">
          <template #default="{ row }">
            <span class="text-slate-600">{{ formatDuration(row.duration) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" width="160">
          <template #default="{ row }">
            <span class="text-slate-600">{{ formatTime(row.started_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" text size="small" @click.stop="goToWorkflow(row)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Quick Actions -->
    <div class="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
      <el-card 
        class="quick-action-card cursor-pointer" 
        :body-style="{ padding: '20px' }"
        @click="router.push('/workflow/tax')"
      >
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center">
            <FileBarChart :size="24" class="text-indigo-600" />
          </div>
          <div>
            <h4 class="font-semibold text-slate-800">税务工作流监控</h4>
            <p class="text-sm text-slate-500">监控税务提交流程</p>
          </div>
        </div>
      </el-card>
      
      <el-card 
        class="quick-action-card cursor-pointer" 
        :body-style="{ padding: '20px' }"
        @click="router.push('/workflow/policy')"
      >
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-xl bg-pink-100 flex items-center justify-center">
            <Sparkles :size="24" class="text-pink-600" />
          </div>
          <div>
            <h4 class="font-semibold text-slate-800">政策推送监控</h4>
            <p class="text-sm text-slate-500">监控政策匹配和推送</p>
          </div>
        </div>
      </el-card>
      
      <el-card 
        class="quick-action-card cursor-pointer" 
        :body-style="{ padding: '20px' }"
        @click="router.push('/workflow/reviews')"
      >
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
            <Users :size="24" class="text-blue-600" />
          </div>
          <div>
            <h4 class="font-semibold text-slate-800">人工审核管理</h4>
            <p class="text-sm text-slate-500">管理人工审核流程</p>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.workflow-dashboard {
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

.success-rate-card,
.workflow-types-card,
.running-workflows-card {
  border-radius: 12px;
  border: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.recent-workflows-card {
  border-radius: 12px;
  border: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.quick-action-card {
  border-radius: 12px;
  border: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.quick-action-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.workflow-table {
  cursor: pointer;
}

:deep(.el-table__row) {
  transition: background-color 0.2s ease;
}

:deep(.el-table__row:hover) {
  background-color: #f8fafc;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
