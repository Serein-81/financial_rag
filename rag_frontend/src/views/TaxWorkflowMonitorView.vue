<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElCard, ElSkeleton, ElEmpty, ElButton, ElTag, ElProgress, ElTable, ElTableColumn, ElSelect, ElOption, ElDatePicker, ElPagination } from 'element-plus'
import { 
  FileBarChart, 
  CheckCircle, 
  XCircle, 
  Clock, 
  RefreshCw,
  ArrowLeft,
  ArrowRight,
  AlertCircle,
  Play,
  Pause,
  FileText,
  Calculator,
  Shield,
  UserCheck,
  Database,
  TrendingUp,
  BarChart3
} from 'lucide-vue-next'
import { taxWorkflowMonitorApi, type WorkflowTrace, type WorkflowStatistics } from '@/api/workflow-monitor'
import { useEnterpriseTheme } from '@/composables/useEnterpriseTheme'

const router = useRouter()
const { enterpriseTheme } = useEnterpriseTheme()

const primaryColor = computed(() => enterpriseTheme.value.primary_color)
const secondaryColor = computed(() => enterpriseTheme.value.secondary_color)

const loading = ref(true)
const statistics = ref<WorkflowStatistics | null>(null)
const workflowList = ref<WorkflowTrace[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

const selectedStatus = ref('')
const selectedTaxType = ref('')
const dateRange = ref<[Date, Date] | null>(null)

const taxTypeOptions = [
  { value: 'vat', label: '增值税 (VAT)' },
  { value: 'income', label: '企业所得税' },
  { value: 'personal', label: '个人所得税' },
  { value: 'consumption', label: '消费税' },
  { value: 'behavior', label: '行为税' },
]

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
]

const workflowSteps = [
  { name: '数据验证', icon: FileText, key: 'data_validation' },
  { name: '获取财务数据', icon: Database, key: 'financial_data' },
  { name: '税务计算', icon: Calculator, key: 'tax_calculation' },
  { name: '风险评估', icon: Shield, key: 'risk_assessment' },
  { name: '人工审核', icon: UserCheck, key: 'human_review' },
  { name: '保存结果', icon: CheckCircle, key: 'save_result' },
]

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

const getStepStatus = (workflow: WorkflowTrace, stepKey: string): 'pending' | 'running' | 'completed' | 'failed' => {
  const completedNodes = workflow.completed_nodes || 0
  const currentNode = workflow.current_node || ''
  
  const stepIndex = workflowSteps.findIndex(s => s.key === stepKey)
  
  if (workflow.status === 'completed') return 'completed'
  if (workflow.status === 'failed') return 'failed'
  
  if (currentNode.includes(stepKey) || stepIndex < completedNodes) return 'running'
  if (stepIndex <= completedNodes) return 'completed'
  
  return 'pending'
}

const loadData = async () => {
  loading.value = true
  try {
    const [statsData, listData] = await Promise.all([
      taxWorkflowMonitorApi.getTaxStatistics(),
      taxWorkflowMonitorApi.getTaxWorkflows({
        page: currentPage.value,
        page_size: pageSize.value,
        status: selectedStatus.value || undefined,
        tax_type: selectedTaxType.value || undefined,
      })
    ])
    
    statistics.value = statsData
    workflowList.value = listData.items
    total.value = listData.total
  } catch (error) {
    console.error('加载税务工作流数据失败:', error)
  } finally {
    loading.value = false
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

const goToWorkflowDetail = (trace: WorkflowTrace) => {
  router.push(`/workflow/detail/${trace.id}`)
}

const goBack = () => {
  router.push('/workflow')
}

onMounted(() => {
  loadData()
})

watch([selectedStatus, selectedTaxType], () => {
  handleSearch()
})
</script>

<template>
  <div class="tax-workflow-monitor min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
    <!-- Header -->
    <div class="mb-6">
      <div class="flex items-center gap-4 mb-4">
        <el-button circle @click="goBack">
          <ArrowLeft :size="16" />
        </el-button>
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center">
            <FileBarChart :size="24" class="text-indigo-600" />
          </div>
          <div>
            <h1 class="text-3xl font-bold text-slate-900">税务工作流监控</h1>
            <p class="text-slate-600">监控税务提交流程的执行状态和结果</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Statistics Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <el-card class="stat-card" :body-style="{ padding: '20px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500 mb-1">总工作流数</p>
            <p class="text-3xl font-bold text-indigo-600">
              <el-skeleton v-if="loading" animated :rows="0" />
              <span v-else>{{ statistics?.total_workflows || 0 }}</span>
            </p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center">
            <FileBarChart :size="24" class="text-indigo-600" />
          </div>
        </div>
      </el-card>

      <el-card class="stat-card" :body-style="{ padding: '20px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500 mb-1">成功率</p>
            <p class="text-3xl font-bold text-emerald-600">{{ successRate }}%</p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center">
            <TrendingUp :size="24" class="text-emerald-600" />
          </div>
        </div>
      </el-card>

      <el-card class="stat-card" :body-style="{ padding: '20px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500 mb-1">平均耗时</p>
            <p class="text-3xl font-bold text-slate-700">{{ averageDurationFormatted }}</p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center">
            <Clock :size="24" class="text-slate-600" />
          </div>
        </div>
      </el-card>

      <el-card class="stat-card" :body-style="{ padding: '20px' }">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-slate-500 mb-1">失败数</p>
            <p class="text-3xl font-bold text-red-600">
              <el-skeleton v-if="loading" animated :rows="0" />
              <span v-else>{{ statistics?.failed_workflows || 0 }}</span>
            </p>
          </div>
          <div class="w-12 h-12 rounded-xl bg-red-100 flex items-center justify-center">
            <XCircle :size="24" class="text-red-600" />
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
          v-model="selectedTaxType" 
          placeholder="选择税种"
          clearable
          style="width: 160px"
        >
          <el-option
            v-for="item in taxTypeOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 260px"
        />
        
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

    <!-- Workflow List -->
    <el-card :body-style="{ padding: '0' }">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="text-lg font-semibold text-slate-800">工作流列表</span>
          <span class="text-sm text-slate-500">共 {{ total }} 条记录</span>
        </div>
      </template>
      
      <el-table 
        :data="workflowList" 
        style="width: 100%"
        :header-cell-style="{ backgroundColor: '#f8fafc', color: '#475569' }"
        @row-click="goToWorkflowDetail"
        v-loading="loading"
        class="workflow-table"
      >
        <el-table-column prop="id" label="工作流ID" width="280">
          <template #default="{ row }">
            <span class="text-xs text-slate-500 font-mono">{{ row.id }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small" effect="dark">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="workflow" label="工作流步骤" min-width="400">
          <template #default="{ row }">
            <div class="flex items-center gap-1">
              <div 
                v-for="(step, index) in workflowSteps" 
                :key="step.key"
                class="flex items-center"
              >
                <div 
                  :class="[
                    'w-8 h-8 rounded-lg flex items-center justify-center transition-all',
                    getStepStatus(row, step.key) === 'completed' ? 'bg-emerald-500 text-white' :
                    getStepStatus(row, step.key) === 'running' ? 'bg-amber-500 text-white animate-pulse' :
                    getStepStatus(row, step.key) === 'failed' ? 'bg-red-500 text-white' :
                    'bg-slate-200 text-slate-500'
                  ]"
                  :title="step.name"
                >
                  <component :is="step.icon" :size="14" />
                </div>
                <ArrowRight 
                  v-if="index < workflowSteps.length - 1" 
                  :size="12" 
                  class="text-slate-300 mx-0.5" 
                />
              </div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="current_node" label="当前节点" width="120">
          <template #default="{ row }">
            <span class="text-slate-600">{{ row.current_node || '-' }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="duration" label="耗时" width="100">
          <template #default="{ row }">
            <span class="text-slate-600">{{ formatDuration(row.duration) }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="started_at" label="开始时间" width="140">
          <template #default="{ row }">
            <span class="text-slate-600">{{ formatTime(row.started_at) }}</span>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" text size="small" @click.stop="goToWorkflowDetail(row)">
              查看详情
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

    <!-- Legend -->
    <el-card class="mt-6" :body-style="{ padding: '16px' }">
      <div class="flex items-center gap-6">
        <span class="text-sm text-slate-600 font-medium">图例:</span>
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 rounded bg-emerald-500 flex items-center justify-center">
            <CheckCircle :size="12" class="text-white" />
          </div>
          <span class="text-sm text-slate-600">已完成</span>
        </div>
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 rounded bg-amber-500 flex items-center justify-center animate-pulse">
            <Play :size="12" class="text-white" />
          </div>
          <span class="text-sm text-slate-600">运行中</span>
        </div>
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 rounded bg-red-500 flex items-center justify-center">
            <XCircle :size="12" class="text-white" />
          </div>
          <span class="text-sm text-slate-600">失败</span>
        </div>
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 rounded bg-slate-200 flex items-center justify-center">
            <Clock :size="12" class="text-slate-500" />
          </div>
          <span class="text-sm text-slate-600">等待中</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.tax-workflow-monitor {
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

.workflow-table {
  cursor: pointer;
}

:deep(.el-table__row) {
  transition: background-color 0.2s ease;
}

:deep(.el-table__row:hover) {
  background-color: #f8fafc;
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}
</style>
