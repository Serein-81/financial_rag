<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { policyApi, type Policy, type PolicySearchParams } from '@/api/policy'
import { ElMessage } from 'element-plus'
import {
  FileText,
  Search,
  Filter,
  X,
  ChevronLeft,
  ChevronRight,
  Calendar,
  Building2,
  MapPin,
  Scale,
  DollarSign,
  Clock,
  Eye,
  Loader2,
  Tag,
  RefreshCw,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Archive,
  FileWarning,
  Sparkles,
  ExternalLink,
  Hash,
  FileBadge,
  Zap,
  Shield,
  FileDown,
  ChevronDown,
  File,
  FileSpreadsheet,
  Brain,
  FileText as FileTextIcon,
  Cpu,
  Wand2
} from 'lucide-vue-next'
import ExportProgressModal from '@/components/ExportProgressModal.vue'
import { useExport, type ExportFormat } from '@/composables/useExport'
import { useWordGenerator } from '@/composables/useWordGenerator'

const router = useRouter()

const policies = ref<Policy[]>([])
const totalPolicies = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const isLoading = ref(false)

// PolicyNotificationAgent 状态
const agentStatus = ref<any>(null)
const isCheckingAgent = ref(false)

// LLM 摘要状态
const llmSummaries = ref<Map<string, any>>(new Map())
const isGeneratingSummary = ref(false)
const batchGeneratingPolicies = ref<Set<string>>(new Set())

const searchQuery = ref('')
const showFilters = ref(false)

const {
  exportProgress,
  isExporting,
  estimatedTimeRemaining,
  exportWithProgress
} = useExport()

const {
  generatePolicyReport
} = useWordGenerator()

const showExportModal = ref(false)
const showExportMenu = ref(false)
const selectedExportFormat = ref<ExportFormat>('pdf')

const filters = ref<PolicySearchParams>({
  industries: [],
  regions: [],
  tax_types: [],
  scales: [],
  status: '',
  priority: '',
  start_date: '',
  end_date: ''
})

const filterOptions = {
  industries: ['制造业', '科技', '金融', '房地产', '零售', '医疗', '教育', '能源'],
  regions: ['全国', '北京', '上海', '广州', '深圳', '浙江', '江苏', '广东', '四川', '湖北'],
  tax_types: ['增值税', '企业所得税', '个人所得税', '消费税', '关税', '印花税', '土地增值税'],
  scales: ['大型企业', '中型企业', '小型企业', '微型企业', '所有规模'],
  status: [
    { value: 'active', label: '有效', icon: CheckCircle, color: 'text-emerald-500' },
    { value: 'archived', label: '已归档', icon: Archive, color: 'text-gray-400' },
    { value: 'draft', label: '草稿', icon: FileWarning, color: 'text-amber-500' },
    { value: 'expired', label: '已过期', icon: AlertCircle, color: 'text-red-500' }
  ],
  priority: [
    { value: 'critical', label: '紧急重要', color: 'bg-red-500 text-white' },
    { value: 'high', label: '高优先级', color: 'bg-orange-500 text-white' },
    { value: 'medium', label: '中优先级', color: 'bg-blue-500 text-white' },
    { value: 'low', label: '低优先级', color: 'bg-gray-400 text-white' }
  ]
}

const totalPages = computed(() => Math.ceil(totalPolicies.value / pageSize.value))

const activeFilterCount = computed(() => {
  let count = 0
  if (filters.value.industries && filters.value.industries.length > 0) count++
  if (filters.value.regions && filters.value.regions.length > 0) count++
  if (filters.value.tax_types && filters.value.tax_types.length > 0) count++
  if (filters.value.scales && filters.value.scales.length > 0) count++
  if (filters.value.status) count++
  if (filters.value.priority) count++
  return count
})

onMounted(async () => {
  await Promise.all([
    fetchPolicies(),
    checkAgentStatus()
  ])
})

async function fetchPolicies() {
  isLoading.value = true
  try {
    const params: PolicySearchParams = {
      query: searchQuery.value || undefined,
      page: currentPage.value,
      page_size: pageSize.value,
      ...filters.value
    }

    const response = await policyApi.listPolicies(params)
    policies.value = response.policies
    totalPolicies.value = response.total
  } catch (error: any) {
    ElMessage.error('获取政策列表失败')
    console.error('Failed to fetch policies:', error)
  } finally {
    isLoading.value = false
  }
}

async function checkAgentStatus() {
  isCheckingAgent.value = true
  try {
    agentStatus.value = await policyApi.getPolicyAgentStatus()
  } catch (error: any) {
    console.error('Failed to check agent status:', error)
    agentStatus.value = null
  } finally {
    isCheckingAgent.value = false
  }
}

async function generateLLMSummary(policyId: string, policy: Policy) {
  if (!agentStatus.value?.use_llm) {
    ElMessage.warning('请先启用LLM模式以生成摘要')
    return
  }

  if (llmSummaries.value.has(policyId)) {
    ElMessage.info('该政策已生成LLM摘要')
    return
  }

  isGeneratingSummary.value = true
  batchGeneratingPolicies.value.add(policyId)

  try {
    const request = {
      policy: {
        policy_id: policyId,
        title: policy.title,
        content: policy.content || policy.summary || '',
        source: policy.source_name || 'policy_center'
      },
      enterprise_profile: {
        enterprise_id: 'default',
        enterprise_name: '企业',
        industry: '通用',
        region: '全国',
        scale: '中型企业',
        tax_types: policy.tax_types || [],
        qualifications: []
      },
      match_result: {
        match_score: 0.5,
        industry_match: true,
        region_match: true,
        scale_match: true,
        reasons: []
      }
    }

    const result = await policyApi.generatePolicyNotification(request)

    llmSummaries.value.set(policyId, {
      summary: result.content || policy.summary,
      key_points: result.key_points || [],
      recommendations: result.action_steps || []
    })

    ElMessage.success('已生成政策摘要')
  } catch (error: any) {
    ElMessage.error('生成摘要失败')
    console.error('Failed to generate LLM summary:', error)
  } finally {
    isGeneratingSummary.value = false
    batchGeneratingPolicies.value.delete(policyId)
  }
}

async function batchGenerateSummaries() {
  if (policies.value.length === 0) {
    ElMessage.warning('暂无政策可生成摘要')
    return
  }

  isGeneratingSummary.value = true

  try {
    const policiesToProcess = policies.value.slice(0, 10)

    for (const policy of policiesToProcess) {
      if (!llmSummaries.value.has(policy.id)) {
        await generateLLMSummary(policy.id, policy)
        await new Promise(resolve => setTimeout(resolve, 500))
      }
    }

    ElMessage.success('批量生成摘要完成')
  } catch (error: any) {
    ElMessage.error('批量生成失败')
    console.error('Failed to batch generate summaries:', error)
  } finally {
    isGeneratingSummary.value = false
  }
}

function getLLMSummary(policyId: string) {
  return llmSummaries.value.get(policyId)
}

function handleSearch() {
  currentPage.value = 1
  fetchPolicies()
}

function clearFilters() {
  filters.value = {
    industries: [],
    regions: [],
    tax_types: [],
    scales: [],
    status: '',
    priority: '',
    start_date: '',
    end_date: ''
  }
  currentPage.value = 1
  fetchPolicies()
}

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
  fetchPolicies()
}

function viewPolicyDetail(policy: Policy) {
  router.push(`/policy/${policy.id}`)
}

function getStatusConfig(status: string) {
  return filterOptions.status.find(s => s.value === status) || filterOptions.status[0]
}

function getPriorityConfig(priority: string) {
  return filterOptions.priority.find(p => p.value === priority) || filterOptions.priority[2]
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '未知'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

function highlightText(text: string, query: string) {
  if (!query) return text
  const regex = new RegExp(`(${query})`, 'gi')
  return text.replace(regex, '<mark class="bg-yellow-200 px-0.5 rounded">$1</mark>')
}

async function handleExport() {
  showExportMenu.value = false

  if (totalPolicies.value === 0) {
    ElMessage.warning('没有可导出的政策')
    return
  }

  showExportModal.value = true

  try {
    if (selectedExportFormat.value === 'pdf') {
      await exportWithProgress(
        async () => {
          return await policyApi.exportPolicyReport({
            query: searchQuery.value || undefined,
            topK: 20
          })
        },
        '政策报告',
        'pdf',
        (progress, message) => {
          exportProgress.value.progress = progress
          exportProgress.value.message = message
        }
      )
    } else if (selectedExportFormat.value === 'word') {
      await exportWithProgress(
        async () => {
          const response = await policyApi.exportPolicyReport({
            query: searchQuery.value || undefined,
            topK: 20
          })

          const text = await response.text()
          let policiesData = []

          try {
            const jsonStart = text.indexOf('{')
            const jsonEnd = text.lastIndexOf('}') + 1
            if (jsonStart !== -1 && jsonEnd !== -1) {
              const jsonStr = text.substring(jsonStart, jsonEnd)
              const data = JSON.parse(jsonStr)
              policiesData = data.policies || []
            }
          } catch (parseError) {
            console.warn('Failed to parse policies from API response, using mock data')
            policiesData = policies.value.slice(0, 20).map(p => ({
              policy_title: p.title,
              summary: p.summary,
              policy_source: p.source_name,
              department: '',
              publish_date: p.published_date,
              tags: p.tags,
              match_score: 0.8
            }))
          }

          return await generatePolicyReport({
            policies: policiesData,
            exportTime: new Date().toISOString(),
            totalCount: policiesData.length,
            query: searchQuery.value || '所有政策'
          })
        },
        '政策报告',
        'word',
        (progress, message) => {
          exportProgress.value.progress = progress
          exportProgress.value.message = message
        }
      )
    } else if (selectedExportFormat.value === 'excel') {
      ElMessage.info('Excel导出功能开发中，敬请期待')
      showExportModal.value = false
    }
  } catch (error) {
    console.error('Export failed:', error)
  }
}

function selectExportFormat(format: ExportFormat) {
  selectedExportFormat.value = format
  handleExport()
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-slate-100 via-blue-50/30 to-indigo-50/30 h-full">
    <!-- Top Bar -->
    <div class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center">
          <FileText :size="20" class="text-white" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-gray-900">政策中心</h2>
          <p class="text-xs text-gray-500">浏览最新税务政策</p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <!-- Agent Status -->
        <div v-if="agentStatus" class="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border border-purple-200">
          <Brain :size="16" class="text-purple-600" />
          <span class="text-xs font-medium text-purple-700">
            {{ agentStatus.use_llm ? 'LLM智能摘要' : '基础摘要' }}
          </span>
          <span v-if="agentStatus.llm_provider" class="text-xs text-purple-500">
            ({{ agentStatus.llm_provider }})
          </span>
        </div>

        <!-- LLM Batch Generate Button -->
        <button
          v-if="agentStatus?.use_llm"
          @click="batchGenerateSummaries"
          :disabled="isGeneratingSummary || policies.length === 0"
          class="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 text-white hover:from-purple-700 hover:to-indigo-700 transition-all flex items-center gap-2 text-sm font-medium shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Sparkles :size="16" :class="{ 'animate-pulse': isGeneratingSummary }" />
          {{ isGeneratingSummary ? '生成中...' : '批量生成摘要' }}
        </button>

        <div class="relative">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索政策标题或内容..."
            class="w-80 pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 placeholder-gray-400 focus:bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none"
            @keydown.enter="handleSearch"
          />
          <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        </div>

        <button
          @click="showFilters = !showFilters"
          :class="[
            'px-4 py-2 rounded-xl border transition-all flex items-center gap-2 text-sm font-medium',
            showFilters ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-200 hover:border-blue-300'
          ]"
        >
          <Filter :size="16" />
          筛选
          <span
            v-if="activeFilterCount > 0"
            class="w-5 h-5 bg-red-500 text-white rounded-full text-xs flex items-center justify-center"
          >
            {{ activeFilterCount }}
          </span>
        </button>

        <button
          @click="fetchPolicies"
          class="p-2 rounded-xl border border-gray-200 hover:bg-gray-50 transition-all"
          title="刷新"
        >
          <RefreshCw :size="18" :class="{ 'animate-spin': isLoading }" class="text-gray-600" />
        </button>

        <div class="relative">
          <button
            @click="showExportMenu = !showExportMenu"
            :disabled="isLoading || totalPolicies === 0 || isExporting"
            class="px-4 py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-xl hover:from-green-700 hover:to-emerald-700 transition-all flex items-center gap-2 text-sm font-medium shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <FileDown :size="16" />
            {{ isExporting ? '导出中...' : '导出' }}
            <ChevronDown :size="14" :class="{ 'rotate-180': showExportMenu }" class="transition-transform" />
          </button>

          <Transition
            enter-active-class="transition duration-200 ease-out"
            enter-from-class="opacity-0 scale-95 -translate-y-2"
            enter-to-class="opacity-100 scale-100 translate-y-0"
            leave-active-class="transition duration-150 ease-in"
            leave-from-class="opacity-100 scale-100 translate-y-0"
            leave-to-class="opacity-0 scale-95 -translate-y-2"
          >
            <div
              v-if="showExportMenu"
              class="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lg border border-gray-200 py-2 z-50"
            >
              <button
                @click="selectExportFormat('pdf')"
                class="w-full px-4 py-3 flex items-center gap-3 hover:bg-emerald-50 transition-colors text-left"
              >
                <div class="w-8 h-8 bg-red-100 rounded-lg flex items-center justify-center">
                  <FileText :size="16" class="text-red-600" />
                </div>
                <div class="flex-1">
                  <div class="text-sm font-medium text-gray-900">PDF 格式</div>
                  <div class="text-xs text-gray-500">便携式文档格式</div>
                </div>
              </button>

              <button
                @click="selectExportFormat('word')"
                class="w-full px-4 py-3 flex items-center gap-3 hover:bg-blue-50 transition-colors text-left"
              >
                <div class="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                  <File :size="16" class="text-blue-600" />
                </div>
                <div class="flex-1">
                  <div class="text-sm font-medium text-gray-900">Word 格式</div>
                  <div class="text-xs text-gray-500">可编辑文档格式</div>
                </div>
              </button>

              <button
                @click="selectExportFormat('excel')"
                class="w-full px-4 py-3 flex items-center gap-3 hover:bg-green-50 transition-colors text-left"
              >
                <div class="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
                  <FileSpreadsheet :size="16" class="text-green-600" />
                </div>
                <div class="flex-1">
                  <div class="text-sm font-medium text-gray-900">Excel 格式</div>
                  <div class="text-xs text-gray-500">表格数据格式</div>
                </div>
                <span class="text-xs text-gray-400 mr-2">即将推出</span>
              </button>
            </div>
          </Transition>
        </div>
      </div>
    </div>

    <!-- Filters Panel -->
    <Transition
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="opacity-0 -translate-y-4"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-4"
    >
      <div v-if="showFilters" class="bg-white border-b border-gray-200 p-6 shadow-sm">
        <div class="max-w-7xl mx-auto space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-semibold text-gray-700">筛选条件</h3>
            <button
              v-if="activeFilterCount > 0"
              @click="clearFilters"
              class="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
            >
              <X :size="14" />
              清除所有筛选
            </button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <!-- 行业 -->
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-2 flex items-center gap-1">
                <Building2 :size="12" />
                行业
              </label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="industry in filterOptions.industries"
                  :key="industry"
                  @click="
                    filters.industries = filters.industries?.includes(industry)
                      ? filters.industries.filter(i => i !== industry)
                      : [...(filters.industries || []), industry]
                  "
                  :class="[
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                    filters.industries?.includes(industry)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  ]"
                >
                  {{ industry }}
                </button>
              </div>
            </div>

            <!-- 地区 -->
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-2 flex items-center gap-1">
                <MapPin :size="12" />
                地区
              </label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="region in filterOptions.regions"
                  :key="region"
                  @click="
                    filters.regions = filters.regions?.includes(region)
                      ? filters.regions.filter(r => r !== region)
                      : [...(filters.regions || []), region]
                  "
                  :class="[
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                    filters.regions?.includes(region)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  ]"
                >
                  {{ region }}
                </button>
              </div>
            </div>

            <!-- 税种 -->
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-2 flex items-center gap-1">
                <DollarSign :size="12" />
                税种
              </label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="taxType in filterOptions.tax_types"
                  :key="taxType"
                  @click="
                    filters.tax_types = filters.tax_types?.includes(taxType)
                      ? filters.tax_types.filter(t => t !== taxType)
                      : [...(filters.tax_types || []), taxType]
                  "
                  :class="[
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                    filters.tax_types?.includes(taxType)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  ]"
                >
                  {{ taxType }}
                </button>
              </div>
            </div>

            <!-- 企业规模 -->
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-2 flex items-center gap-1">
                <Scale :size="12" />
                企业规模
              </label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="scale in filterOptions.scales"
                  :key="scale"
                  @click="
                    filters.scales = filters.scales?.includes(scale)
                      ? filters.scales.filter(s => s !== scale)
                      : [...(filters.scales || []), scale]
                  "
                  :class="[
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                    filters.scales?.includes(scale)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  ]"
                >
                  {{ scale }}
                </button>
              </div>
            </div>

            <!-- 状态 -->
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-2 flex items-center gap-1">
                <CheckCircle :size="12" />
                状态
              </label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="status in filterOptions.status"
                  :key="status.value"
                  @click="filters.status = filters.status === status.value ? '' : status.value"
                  :class="[
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1',
                    filters.status === status.value
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  ]"
                >
                  <component :is="status.icon" :size="12" :class="filters.status === status.value ? 'text-white' : status.color" />
                  {{ status.label }}
                </button>
              </div>
            </div>

            <!-- 优先级 -->
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-2 flex items-center gap-1">
                <TrendingUp :size="12" />
                优先级
              </label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="priority in filterOptions.priority"
                  :key="priority.value"
                  @click="filters.priority = filters.priority === priority.value ? '' : priority.value"
                  :class="[
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                    filters.priority === priority.value ? priority.color : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  ]"
                >
                  {{ priority.label }}
                </button>
              </div>
            </div>
          </div>

          <div class="flex justify-end pt-2">
            <button
              @click="handleSearch"
              class="px-6 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-xl hover:from-blue-700 hover:to-indigo-700 transition-all text-sm font-medium shadow-lg hover:shadow-xl"
            >
              应用筛选
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Main Content -->
    <div class="flex-1 overflow-y-auto p-6">
      <div class="max-w-7xl mx-auto">
        <!-- Stats -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-xs text-gray-500 mb-1">政策总数</p>
                <p class="text-2xl font-bold text-gray-900">{{ totalPolicies }}</p>
              </div>
              <div class="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
                <FileText :size="20" class="text-blue-600" />
              </div>
            </div>
          </div>

          <div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-xs text-gray-500 mb-1">有效政策</p>
                <p class="text-2xl font-bold text-emerald-600">{{ policies.filter(p => p.status === 'active').length }}</p>
              </div>
              <div class="w-10 h-10 bg-emerald-100 rounded-xl flex items-center justify-center">
                <CheckCircle :size="20" class="text-emerald-600" />
              </div>
            </div>
          </div>

          <div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-xs text-gray-500 mb-1">高优先级</p>
                <p class="text-2xl font-bold text-orange-600">{{ policies.filter(p => p.priority === 'high' || p.priority === 'critical').length }}</p>
              </div>
              <div class="w-10 h-10 bg-orange-100 rounded-xl flex items-center justify-center">
                <TrendingUp :size="20" class="text-orange-600" />
              </div>
            </div>
          </div>

          <div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-xs text-gray-500 mb-1">本周更新</p>
                <p class="text-2xl font-bold text-indigo-600">{{ policies.filter(p => {
                  const updated = new Date(p.updated_at)
                  const weekAgo = new Date()
                  weekAgo.setDate(weekAgo.getDate() - 7)
                  return updated >= weekAgo
                }).length }}</p>
              </div>
              <div class="w-10 h-10 bg-indigo-100 rounded-xl flex items-center justify-center">
                <Clock :size="20" class="text-indigo-600" />
              </div>
            </div>
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="isLoading" class="flex items-center justify-center py-20">
          <div class="text-center">
            <Loader2 :size="40" class="animate-spin text-blue-600 mx-auto mb-3" />
            <p class="text-sm text-gray-500">加载中...</p>
          </div>
        </div>

        <!-- Policy List -->
        <div v-else-if="policies.length > 0" class="space-y-4">
          <div v-for="(policy, index) in policies" :key="policy.id" @click="viewPolicyDetail(policy)" class="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 hover:shadow-lg hover:border-emerald-300 transition-all cursor-pointer group animate-policy-card" :style="{ animationDelay: index * 0.05 + 's' }">
            <div class="flex items-start justify-between gap-4">
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-2 flex-wrap">
                  <span
                    :class="[
                      'px-2 py-0.5 rounded text-xs font-medium',
                      getPriorityConfig(policy.priority).color
                    ]"
                  >
                    {{ getPriorityConfig(policy.priority).label }}
                  </span>
                  <span class="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600 flex items-center gap-1">
                    <component :is="getStatusConfig(policy.status).icon" :size="12" :class="getStatusConfig(policy.status).color" />
                    {{ getStatusConfig(policy.status).label }}
                  </span>
                  <span v-if="policy.policy_id" class="px-2 py-0.5 rounded text-xs font-medium bg-indigo-50 text-indigo-600 flex items-center gap-1">
                    <FileBadge :size="12" />
                    {{ policy.policy_id }}
                  </span>
                </div>

                <h3
                  class="text-lg font-semibold text-gray-900 group-hover:text-blue-600 transition-colors mb-2 line-clamp-2"
                  v-html="highlightText(policy.title, searchQuery)"
                ></h3>

                <p class="text-sm text-gray-600 line-clamp-2 mb-3">
                  {{ policy.summary || policy.content.substring(0, 200) + '...' }}
                </p>

                <div class="bg-gray-50 rounded-lg p-3 mb-3">
                  <div class="flex items-center gap-4 text-xs text-gray-600">
                    <span class="flex items-center gap-1 font-medium text-blue-600">
                      <Shield :size="12" />
                      {{ policy.source_name }}
                    </span>
                    <span v-if="policy.published_date" class="flex items-center gap-1">
                      <Calendar :size="12" />
                      发布: {{ formatDate(policy.published_date) }}
                    </span>
                    <span v-if="policy.effective_date" class="flex items-center gap-1">
                      <Zap :size="12" class="text-green-500" />
                      生效: {{ formatDate(policy.effective_date) }}
                    </span>
                    <span v-if="policy.expiry_date" class="flex items-center gap-1 text-orange-500">
                      <AlertCircle :size="12" />
                      失效: {{ formatDate(policy.expiry_date) }}
                    </span>
                  </div>
                  <a 
                    v-if="policy.source_url"
                    :href="policy.source_url"
                    target="_blank"
                    @click.stop
                    class="text-xs text-blue-500 hover:text-blue-600 flex items-center gap-1 mt-2"
                  >
                    <ExternalLink :size="12" />
                    查看原文
                  </a>
                </div>

                <div class="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                  <span class="flex items-center gap-1">
                    <Building2 :size="12" />
                    {{ policy.industries.slice(0, 2).join(', ') || '通用' }}
                  </span>
                  <span class="flex items-center gap-1">
                    <MapPin :size="12" />
                    {{ policy.regions.slice(0, 2).join(', ') || '全国' }}
                  </span>
                  <span class="flex items-center gap-1">
                    <DollarSign :size="12" />
                    {{ policy.tax_types.slice(0, 2).join(', ') || '其他' }}
                  </span>
                  <span class="flex items-center gap-1">
                    <Scale :size="12" />
                    {{ policy.scales.slice(0, 2).join(', ') || '所有规模' }}
                  </span>
                </div>

                <div v-if="policy.tags && policy.tags.length > 0" class="flex flex-wrap items-center gap-2 mt-3">
                  <Tag :size="12" class="text-gray-400" />
                  <span
                    v-for="tag in policy.tags.slice(0, 5)"
                    :key="tag"
                    class="px-2 py-0.5 bg-gray-50 text-gray-600 rounded text-xs"
                  >
                    {{ tag }}
                  </span>
                </div>

                <!-- LLM Summary Section -->
                <div v-if="agentStatus?.use_llm" class="mt-4 pt-4 border-t border-gray-100">
                  <button
                    @click.stop="generateLLMSummary(policy.id, policy)"
                    :disabled="isGeneratingSummary && batchGeneratingPolicies.has(policy.id)"
                    class="text-xs text-purple-600 hover:text-purple-700 flex items-center gap-1"
                  >
                    <Brain :size="12" />
                    {{ getLLMSummary(policy.id) ? '查看智能摘要' : '生成智能摘要' }}
                    <Loader2 v-if="batchGeneratingPolicies.has(policy.id)" :size="12" class="animate-spin" />
                  </button>

                  <div v-if="getLLMSummary(policy.id)" class="mt-3 p-4 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-xl border border-purple-200">
                    <div class="flex items-center gap-2 mb-3">
                      <Cpu :size="14" class="text-purple-600" />
                      <span class="text-sm font-semibold text-purple-900">智能摘要</span>
                    </div>

                    <div class="space-y-3">
                      <div v-if="getLLMSummary(policy.id).summary" class="mb-3">
                        <div class="text-xs text-purple-700 font-medium mb-1">摘要：</div>
                        <p class="text-xs text-gray-700 leading-relaxed">{{ getLLMSummary(policy.id).summary }}</p>
                      </div>

                      <div v-if="getLLMSummary(policy.id).key_points?.length > 0" class="mb-3">
                        <div class="text-xs text-purple-700 font-medium mb-2">关键要点：</div>
                        <div class="space-y-1">
                          <div v-for="(point, idx) in getLLMSummary(policy.id).key_points.slice(0, 4)" :key="idx" class="flex items-start gap-2 text-xs text-gray-700 mb-1">
                            <Wand2 :size="10" class="text-purple-600 mt-0.5 flex-shrink-0" />
                            <span>{{ point }}</span>
                          </div>
                        </div>
                      </div>

                      <div v-if="getLLMSummary(policy.id).recommendations?.length > 0" class="mb-3">
                        <div class="text-xs text-purple-700 font-medium mb-2">建议行动：</div>
                        <div class="space-y-1">
                          <div v-for="(rec, idx) in getLLMSummary(policy.id).recommendations.slice(0, 3)" :key="idx" class="flex items-start gap-2 text-xs text-gray-700 mb-1">
                            <Sparkles :size="10" class="text-blue-600 mt-0.5 flex-shrink-0" />
                            <span>{{ rec }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="flex flex-col items-end gap-2 text-xs text-gray-400">
                <div class="flex items-center gap-1">
                  <Eye :size="12" />
                  {{ policy.view_count }}
                </div>
                <span class="text-xs">{{ formatDate(policy.updated_at) }}</span>
              </div>
            </div>
          </div>
        </div>
              <!-- Empty State -->
      <div v-else class="text-center py-20">
        <div class="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <FileText :size="40" class="text-gray-400" />
        </div>
        <h3 class="text-lg font-semibold text-gray-900 mb-2">暂无政策</h3>
        <p class="text-sm text-gray-500">请尝试调整筛选条件或搜索关键词</p>
      </div>
      </div>



      <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-8">
          <button
            @click="goToPage(currentPage - 1)"
            :disabled="currentPage === 1"
            class="px-4 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-1"
          >
            <ChevronLeft :size="16" />
            上一页
          </button>

          <div class="flex items-center gap-1">
            <button
              v-for="page in Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const start = Math.max(1, currentPage - 2)
                return start + i
              })"
              :key="page"
              @click="goToPage(page)"
              :class="[
                'w-10 h-10 rounded-xl text-sm font-medium transition-all',
                page === currentPage
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'bg-white border border-gray-200 text-gray-700 hover:bg-gray-50'
              ]"
            >
              {{ page }}
            </button>
          </div>

          <button
            @click="goToPage(currentPage + 1)"
            :disabled="currentPage === totalPages"
            class="px-4 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-1"
          >
            下一页
            <ChevronRight :size="16" />
          </button>
        </div>
      </div>
    </div>


  <ExportProgressModal
    :visible="showExportModal"
    :progress="exportProgress.progress"
    :status="exportProgress.status"
    :message="exportProgress.message"
    :estimated-time="estimatedTimeRemaining"
    @close="showExportModal = false"
  />
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 政策列表动画 */
.policy-list-enter-active {
  animation: policySlideIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.policy-list-leave-active {
  animation: policyFadeOut 0.2s ease-out;
}

.policy-list-move {
  transition: transform 0.3s ease;
}

@keyframes policySlideIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes policyFadeOut {
  from {
    opacity: 1;
    transform: scale(1);
  }
  to {
    opacity: 0;
    transform: scale(0.95);
  }
}

/* 单个政策卡片动画 */
.animate-policy-card {
  animation: cardSlideIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) backwards;
}

@keyframes cardSlideIn {
  from {
    opacity: 0;
    transform: translateY(15px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
