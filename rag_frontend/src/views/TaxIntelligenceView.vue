<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { taxIntelligenceApi, type TaxAnalysisResult, type TaxReport } from '@/api/tax-intelligence'
import { financialDataApiClient, type FinancialDataResponse } from '@/api/financial-data'
import {
  FileBarChart,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  Clock,
  Download,
  RefreshCw,
  Search,
  ChevronRight,
  Loader2,
  BarChart3,
  PieChart,
  DollarSign,
  Shield,
  Info,
  X,
  Users,
  MessageSquare,
  Sparkles,
  TrendingUp as TrendingUpIcon,
  Building2,
  Calendar,
  FileText
} from 'lucide-vue-next'

const router = useRouter()

const isLoading = ref(false)
const isExporting = ref(false)
const isExplaining = ref(false)
const isQueryingPolicies = ref(false)

const activeTab = ref<'dashboard' | 'history' | 'detail'>('dashboard')

const selectedAnalysis = ref<TaxAnalysisResult | null>(null)
const analysisHistory = ref<TaxReport[]>([])
const historyTotal = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

const statistics = ref({
  total_analyses: 0,
  current_quarter_analyses: 0,
  high_risk_count: 0,
  compliance_rate: 0.985
})

const financialDataList = ref<FinancialDataResponse[]>([])
const selectedFinancialData = ref<FinancialDataResponse | null>(null)
const showFinancialDataDrawer = ref(false)

const showAnalysisModal = ref(false)
const analysisRequest = ref({
  fiscal_year: new Date().getFullYear(),
  fiscal_period: 'Q4',
  tax_type: '',
  company_name: '',
  financial_data: {} as Record<string, any>
})

const showExplanationPanel = ref(false)
const explanationInput = ref('')
const explanationResult = ref<string>('')
const explanationLoading = ref(false)

const showPolicyDialog = ref(false)
const policyQueryInput = ref('')
const matchedPolicies = ref<Array<{
  policy_name: string
  policy_content: string
  match_level: string
  applicable_conditions: string[]
  potential_savings: number
}>>([])

const riskLevelColors = {
  low: 'text-emerald-500 bg-emerald-50',
  medium: 'text-amber-500 bg-amber-50',
  high: 'text-orange-500 bg-orange-50',
  critical: 'text-red-500 bg-red-50'
}

const riskLevelBgColors = {
  low: 'bg-emerald-500',
  medium: 'bg-amber-500',
  high: 'bg-orange-500',
  critical: 'bg-red-500'
}

const severityIcons = {

  low: CheckCircle,

  medium: Info,

  high: AlertTriangle,

  critical: AlertTriangle

}



async function loadHistory() {

  isLoading.value = true

  try {

    const result = await taxIntelligenceApi.getAnalysisHistory({

      page: currentPage.value,

      page_size: pageSize.value

    })

    analysisHistory.value = result.analyses

    historyTotal.value = result.total

  } catch (e: any) {

    console.error('Failed to load history:', e)

  } finally {

    isLoading.value = false

  }

}



async function viewDetail(analysisId: string) {

  isLoading.value = true

  try {

    selectedAnalysis.value = await taxIntelligenceApi.getAnalysisDetail(analysisId)

    activeTab.value = 'detail'

  } catch (e: any) {

    console.error('Failed to load analysis detail:', e)

  } finally {

    isLoading.value = false

  }

}



async function startAnalysis() {

  if (!analysisRequest.value.tax_type) {

    alert('请选择税种类型')

    return

  }

  

  isLoading.value = true

  try {

    const result = await taxIntelligenceApi.analyzeTax(analysisRequest.value)

    selectedAnalysis.value = result

    activeTab.value = 'detail'

    showAnalysisModal.value = false

    await loadHistory()

  } catch (e: any) {

    console.error('Failed to start analysis:', e)

    alert('分析失败: ' + (e.message || '未知错误'))

  } finally {

    isLoading.value = false

  }

}



async function exportPdf(analysisId: string) {

  isExporting.value = true

  try {

    const blob = await taxIntelligenceApi.exportReportPdf(analysisId)

    const url = window.URL.createObjectURL(blob)

    const a = document.createElement('a')

    a.href = url

    a.download = `税务分析报告_${analysisId}_${new Date().toISOString().split('T')[0]}.pdf`

    document.body.appendChild(a)

    a.click()

    window.URL.revokeObjectURL(url)

    document.body.removeChild(a)

  } catch (e: any) {

    console.error('Failed to export PDF:', e)

    alert('导出失败')

  } finally {

    isExporting.value = false

  }

}



function formatCurrency(value: any): string {
  const num = Number(value)
  if (isNaN(num)) return '¥0.00'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(num)
}



function formatPercent(value: any): string {
  const num = Number(value)
  if (isNaN(num)) return '0.00%'
  return (num * 100).toFixed(2) + '%'
}



function formatRiskScorePercent(value: any): string {
  const num = Number(value)
  if (isNaN(num)) return '0.0%'
  return (num * 100).toFixed(1) + '%'
}



function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 历史记录中 tax_type 以英文代码存库（如 VAT/income/consumption），显示层统一映射为中文；
// 中文/未知值原样返回，兼容"新建分析"弹窗传中文的链路
const taxTypeLabels: Record<string, string> = {
  // schemas/tax_report.py TaxTypeEnum
  vat: '增值税',
  income: '企业所得税',
  personal: '个人所得税',
  consumption: '消费税',
  behavior: '行为税',
  comprehensive: '全税种综合',
  // multi_agent_system tax_specialist.TaxType 变体
  income_tax: '企业所得税',
  corporate_income: '企业所得税',
  personal_income: '个人所得税',
  personal_income_tax: '个人所得税',
  consumption_tax: '消费税',
  business_tax: '营业税',
  property_tax: '房产税',
  land_use_tax: '城镇土地使用税',
  stamp: '印花税',
  stamp_tax: '印花税',
  environment_tax: '环境保护税',
}

function formatTaxType(t: any): string {
  if (!t) return '综合分析'
  const key = String(t).toLowerCase().trim()
  return taxTypeLabels[key] || String(t)
}



function getRiskScoreColor(score: any): string {
  const num = Number(score)
  if (isNaN(num)) return 'text-slate-500'
  if (num < 0.3) return 'text-emerald-500'
  if (num < 0.6) return 'text-amber-500'
  if (num < 0.8) return 'text-orange-500'
  return 'text-red-500'
}



function getRiskScoreBg(score: any): string {
  const num = Number(score)
  if (isNaN(num)) return 'bg-slate-500'
  if (num < 0.3) return 'bg-emerald-500'
  if (num < 0.6) return 'bg-amber-500'
  if (num < 0.8) return 'bg-orange-500'
  return 'bg-red-500'
}



interface TaxPolicy {

  name: string

  description: string

  condition: string

  savings: number

}



interface FilingRecommendation {

  title: string

  description: string

  priority?: 'high' | 'medium' | 'low'

}



function calculateTotalSavings(): number {
  const policies = matchedPolicies.value.length > 0 ? matchedPolicies.value : getApplicablePolicies()
  return policies.reduce((sum, policy) => sum + (policy.potential_savings || policy.savings || 0), 0)
}



function getApplicablePolicies(): TaxPolicy[] {

  if (!selectedAnalysis.value) return []

  

  const policies: TaxPolicy[] = []

  const financialSummary = selectedAnalysis.value.financial_summary || {}

  

  if (financialSummary.revenue > 0) {

    if (selectedAnalysis.value.analysis_type?.includes('研发') || selectedAnalysis.value.analysis_type?.includes('高新技术企业')) {

      policies.push({

        name: '研发费用加计扣除',

        description: '企业研发费用可按75%-100%加计扣除，科技型中小企业可填100%加计扣除',

        condition: '企业具有研发活动且研发费用单独核算',

        savings: financialSummary.expenses * 0.15 * 0.25

      })

    }

    

    if (financialSummary.profit > 0) {

      policies.push({

        name: '小型微利企业优惠',

        description: '小型微利企业年应纳税所得额不超过300万元部分，减按2.5%计入应纳税所得额',

        condition: '年应纳税所得额300万元，从业人数≤300人，资产总额≤5000万元',

        savings: Math.min(financialSummary.profit, 3000000) * 0.075 * 0.25

      })

    }

    

    if (selectedAnalysis.value.analysis_type?.includes('增值税') || String(selectedAnalysis.value.analysis_type || '').toLowerCase().includes('vat')) {

      policies.push({

        name: '小规模纳税人免税',

        description: '月销售额未超过15万元（季度未超过45万元）的增值税小规模纳税人，免征增值税',

        condition: '小规模纳税人，月销售额15万元或季度销售额45万元',

        savings: Math.min(financialSummary.revenue * 0.03, 150000)

      })

    }

  }

  

  return policies.sort((a, b) => b.savings - a.savings)

}



function getFilingRecommendations(): FilingRecommendation[] {

  if (!selectedAnalysis.value) return []

  

  const recommendations: FilingRecommendation[] = []

  

  const riskAssessment = selectedAnalysis.value.risk_assessment || []

  if (riskAssessment.length > 0) {

    const highSeverityIssues = riskAssessment.filter(

      (issue: any) => issue.severity === 'high' || issue.severity === 'critical'

    )

    

    if (highSeverityIssues.length > 0) {

      recommendations.push({

        title: '优先处理高风险合规问题',

        description: `发现 ${highSeverityIssues.length} 项高风险合规问题，建议在申报前完成整改，避免产生滞纳金和罚款`,

        priority: 'high'

      })

    }

    

    const mediumSeverityIssues = riskAssessment.filter(

      (issue: any) => issue.severity === 'medium'

    )

    

    if (mediumSeverityIssues.length > 0) {

      recommendations.push({

        title: '关注中等风险事项',

        description: `存在 ${mediumSeverityIssues.length} 项中等风险事项，建议在季度内完成规范`,

        priority: 'medium'

      })

    }

  }

  

  const financialSummary = selectedAnalysis.value.financial_summary || {}

  if (financialSummary.effective_tax_rate > 0.25) {

    recommendations.push({

      title: '优化税负结构',

      description: '当前有效税率偏高，建议咨询专业税务顾问，合理利用税收优惠政策降低税负',

      priority: 'medium'

    })

  }

  

  if (calculateTotalSavings() > 0) {

    recommendations.push({

      title: '及时申报可享受的优惠政策',

      description: `系统检测到 ${getApplicablePolicies().length} 项适用的税收优惠政策，预计可节省${formatCurrency(calculateTotalSavings())}，请在申报时一并填报`,

      priority: 'high'

    })

  }

  

  recommendations.push({

    title: '准备完整凭证资料',

    description: '建议提前准备好发票、合同、银行回单等凭证，确保申报数据准确无误',

    priority: 'low'

  })

  

  recommendations.push({

    title: '关注申报截止日期',

    description: '企业所得税年度汇算清缴截止日期为每年5月31日，增值税申报截止日期为每月15日',

    priority: 'low'

  })

  

  return recommendations
}

async function loadStatistics() {
  try {
    const stats = await taxIntelligenceApi.getStatistics()
    statistics.value = stats
  } catch (e: any) {
    console.error('Failed to load statistics:', e)
    statistics.value.high_risk_count = analysisHistory.value.filter(a => a.risk_score > 0.7).length
  }
}

async function loadFinancialData() {
  try {
    const result = await financialDataApiClient.list({ page_size: 100 })
    financialDataList.value = result.items
  } catch (e: any) {
    console.error('Failed to load financial data:', e)
  }
}

function openFinancialDataDrawer() {
  showFinancialDataDrawer.value = true
  loadFinancialData()
}

function selectFinancialData(data: FinancialDataResponse) {
  selectedFinancialData.value = data
  analysisRequest.value.financial_data = {
    total_revenue: data.total_revenue,
    total_expenses: data.total_expenses,
    taxable_sales: data.taxable_sales,
    input_tax: data.input_tax,
    output_tax: data.output_tax,
    taxable_income: data.taxable_income,
    is_small_enterprise: data.is_small_enterprise
  }
  analysisRequest.value.fiscal_year = data.fiscal_year
  showFinancialDataDrawer.value = false
  showAnalysisModal.value = true
}

async function queryPoliciesFromBackend() {
  if (!policyQueryInput.value.trim()) return
  
  isQueryingPolicies.value = true
  try {
    const result = await taxIntelligenceApi.queryPolicies({
      query: policyQueryInput.value,
      top_k: 5
    })
    matchedPolicies.value = result.policies
    showPolicyDialog.value = true
  } catch (e: any) {
    console.error('Failed to query policies:', e)
  } finally {
    isQueryingPolicies.value = false
  }
}

async function explainReport() {
  if (!selectedAnalysis.value || !explanationInput.value.trim()) return
  
  explanationLoading.value = true
  try {
    const result = await taxIntelligenceApi.explainReport(
      selectedAnalysis.value.analysis_id,
      { question: explanationInput.value }
    )
    explanationResult.value = result.explanation
  } catch (e: any) {
    console.error('Failed to explain report:', e)
    explanationResult.value = '解释生成失败，请稍后重试'
  } finally {
    explanationLoading.value = false
  }
}

async function generateGeneralExplanation() {
  if (!selectedAnalysis.value) return
  
  explanationLoading.value = true
  try {
    const result = await taxIntelligenceApi.explainReport(
      selectedAnalysis.value.analysis_id,
      {}
    )
    explanationResult.value = result.explanation
    showExplanationPanel.value = true
  } catch (e: any) {
    console.error('Failed to generate explanation:', e)
  } finally {
    explanationLoading.value = false
  }
}

onMounted(() => {
  loadHistory()
  loadStatistics()
})

</script>



<template>

  <div class="h-full flex flex-col bg-slate-50">

    <div class="bg-white border-b border-slate-200 px-6 py-4">

      <div class="flex items-center justify-between">

        <div class="flex items-center gap-3">

          <div class="w-10 h-10 bg-emerald-100 rounded-xl flex items-center justify-center">

            <FileBarChart :size="20" class="text-emerald-600" />

          </div>

          <div>

            <h1 class="text-xl font-bold text-slate-900">税务智能分析</h1>

            <p class="text-sm text-slate-500">AI驱动的税务合规性分析与风险评估</p>

          </div>

        </div>

        <button

          @click="showAnalysisModal = true"

          class="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 flex items-center gap-2 transition-colors"

        >

          <Search :size="16" />

          新建分析

        </button>

      </div>



      <div class="flex gap-4 mt-4 border-b border-slate-200">

        <button

          @click="activeTab = 'dashboard'"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'dashboard' ? 'text-emerald-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          分析概览

          <div

            v-if="activeTab === 'dashboard'"

            class="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-600"

          />

        </button>

        <button

          @click="activeTab = 'history'"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'history' ? 'text-emerald-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          历史记录

          <div

            v-if="activeTab === 'history'"

            class="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-600"

          />

        </button>

        <button

          v-if="selectedAnalysis"

          @click="activeTab = 'detail'"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'detail' ? 'text-emerald-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          详细报告

          <div

            v-if="activeTab === 'detail'"

            class="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-600"

          />

        </button>

      </div>

    </div>



    <div class="flex-1 overflow-auto p-6">

      <div v-if="isLoading" class="flex items-center justify-center h-64">

        <Loader2 :size="32" class="animate-spin text-emerald-600" />

      </div>



      <template v-else>

        <div v-if="activeTab === 'dashboard'" class="space-y-6">

          <div class="grid grid-cols-1 md:grid-cols-4 gap-4">

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">分析记录</p>

                  <p class="text-2xl font-bold text-slate-900 mt-1">{{ statistics.total_analyses }}</p>

                </div>

                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">

                  <BarChart3 :size="20" class="text-blue-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">本季度分析</p>

                  <p class="text-2xl font-bold text-slate-900 mt-1">{{ statistics.current_quarter_analyses }}</p>

                </div>

                <div class="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">

                  <TrendingUp :size="20" class="text-emerald-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">高风险项</p>

                  <p class="text-2xl font-bold text-slate-900 mt-1">{{ statistics.high_risk_count }}</p>

                </div>

                <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">

                  <AlertTriangle :size="20" class="text-amber-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">合规</p>

                  <p class="text-2xl font-bold text-emerald-600 mt-1">{{ (statistics.compliance_rate * 100).toFixed(1) }}%</p>

                </div>

                <div class="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">

                  <Shield :size="20" class="text-emerald-600" />

                </div>

              </div>

            </div>

          </div>



          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

            <div class="bg-white rounded-xl border border-slate-200">

              <div class="px-5 py-4 border-b border-slate-200">

                <h3 class="font-semibold text-slate-900">最近分析</h3>

              </div>

              <div class="p-5">

                <div v-if="analysisHistory.length === 0" class="text-center py-8 text-slate-500">

                  暂无分析记录

                </div>

                <div v-else class="space-y-3">

                  <div

                    v-for="item in analysisHistory.slice(0, 5)"

                    :key="item.id"

                    @click="viewDetail(item.analysis_id)"

                    class="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors"

                  >

                    <div class="flex items-center gap-3">

                      <div :class="['w-2 h-2 rounded-full', getRiskScoreBg(item.risk_score)]" />

                      <div>

                        <p class="font-medium text-slate-900">{{ formatTaxType(item.analysis_type) }}</p>

                        <p class="text-sm text-slate-500">{{ formatDate(item.created_at) }}</p>

                      </div>

                    </div>

                    <ChevronRight :size="16" class="text-slate-400" />

                  </div>

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl border border-slate-200">

              <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

                <h3 class="font-semibold text-slate-900">快捷操作</h3>

              </div>

              <div class="p-5 space-y-3">

                <button

                  @click="openFinancialDataDrawer"

                  class="w-full p-4 border border-emerald-200 rounded-lg hover:border-emerald-500 hover:bg-emerald-50 transition-colors text-left flex items-center gap-3"

                >

                  <div class="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">

                    <TrendingUpIcon :size="20" class="text-emerald-600" />

                  </div>

                  <div class="flex-1">

                    <p class="font-medium text-slate-900">从财务数据发起分析</p>

                    <p class="text-xs text-slate-500 mt-1">选择已录入的财务数据，一键开始智能分析</p>

                  </div>

                  <ChevronRight :size="16" class="text-slate-400" />

                </button>

                <button

                  @click="policyQueryInput = '研发费用加计扣除'; queryPoliciesFromBackend()"

                  class="w-full p-4 border border-blue-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-colors text-left flex items-center gap-3"

                >

                  <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">

                    <Sparkles :size="20" class="text-blue-600" />

                  </div>

                  <div class="flex-1">

                    <p class="font-medium text-slate-900">查询研发优惠政策</p>

                    <p class="text-xs text-slate-500 mt-1">智能匹配企业适用的研发税收优惠</p>

                  </div>

                  <ChevronRight :size="16" class="text-slate-400" />

                </button>

                <button

                  @click="policyQueryInput = '小微企业优惠'; queryPoliciesFromBackend()"

                  class="w-full p-4 border border-purple-200 rounded-lg hover:border-purple-500 hover:bg-purple-50 transition-colors text-left flex items-center gap-3"

                >

                  <div class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">

                    <Shield :size="20" class="text-purple-600" />

                  </div>

                  <div class="flex-1">

                    <p class="font-medium text-slate-900">查询小微企业优惠</p>

                    <p class="text-xs text-slate-500 mt-1">查询小规模纳税人适用的税收优惠政策</p>

                  </div>

                  <ChevronRight :size="16" class="text-slate-400" />

                </button>

              </div>

            </div>

          </div>

        </div>



        <div v-else-if="activeTab === 'history'" class="space-y-4">

          <div class="bg-white rounded-xl border border-slate-200">

            <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

              <h3 class="font-semibold text-slate-900">分析历史</h3>

              <button

                @click="loadHistory"

                class="p-2 hover:bg-slate-100 rounded-lg transition-colors"

              >

                <RefreshCw :size="16" class="text-slate-500" />

              </button>

            </div>

            <div class="p-5">

              <div v-if="analysisHistory.length === 0" class="text-center py-8 text-slate-500">

                暂无分析记录

              </div>

              <div v-else class="space-y-3">

                <div

                  v-for="item in analysisHistory"

                  :key="item.id"

                  @click="viewDetail(item.analysis_id)"

                  class="flex items-center justify-between p-4 border border-slate-200 rounded-lg hover:border-emerald-500 cursor-pointer transition-colors"

                >

                  <div class="flex items-center gap-4">

                      <div :class="['w-3 h-3 rounded-full', getRiskScoreBg(item.risk_score)]" />

                      <div>

                        <p class="font-medium text-slate-900">{{ formatTaxType(item.analysis_type) }} - {{ item.fiscal_year }}年{{ item.fiscal_period }}</p>

                        <p class="text-sm text-slate-500 mt-1">风险评分: {{ formatRiskScorePercent(item.risk_score) }}</p>

                      </div>

                    </div>

                  <div class="flex items-center gap-4">

                    <span class="text-sm text-slate-500">{{ formatDate(item.created_at) }}</span>

                    <ChevronRight :size="16" class="text-slate-400" />

                  </div>

                </div>

              </div>

            </div>

          </div>

        </div>



        <div v-else-if="activeTab === 'detail' && selectedAnalysis" class="space-y-6">

          <div class="flex items-center justify-between">

            <div>

              <h2 class="text-lg font-semibold text-slate-900">分析报告详情</h2>

              <p class="text-sm text-slate-500 mt-1">报告ID: {{ selectedAnalysis.analysis_id }}</p>

            </div>

            <div class="flex gap-2">

              <button

                @click="showExplanationPanel = true; generateGeneralExplanation()"

                :disabled="explanationLoading"

                class="px-4 py-2 border border-blue-200 rounded-lg hover:bg-blue-50 flex items-center gap-2 transition-colors disabled:opacity-50"

              >

                <Sparkles :size="16" class="text-blue-600" />

                AI智能解读

              </button>

              <button

                @click="exportPdf(selectedAnalysis.analysis_id)"

                :disabled="isExporting"

                class="px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 flex items-center gap-2 transition-colors disabled:opacity-50"

              >

                <Download v-if="!isExporting" :size="16" />

                <Loader2 v-else :size="16" class="animate-spin" />

                导出PDF

              </button>

              <button

                @click="activeTab = 'history'"

                class="px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"

              >

                返回列表

              </button>

            </div>

          </div>



          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

            <div class="lg:col-span-2 space-y-6">

              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">财务摘要</h3>

                </div>

                <div class="p-5 grid grid-cols-2 md:grid-cols-4 gap-4">

                  <div>

                    <p class="text-sm text-slate-500">营业收入</p>

                    <p class="text-lg font-semibold text-slate-900">{{ formatCurrency(selectedAnalysis.financial_summary?.revenue || 0) }}</p>

                  </div>

                  <div>

                    <p class="text-sm text-slate-500">营业成本</p>

                    <p class="text-lg font-semibold text-slate-900">{{ formatCurrency(selectedAnalysis.financial_summary?.expenses || 0) }}</p>

                  </div>

                  <div>

                    <p class="text-sm text-slate-500">净利润</p>

                    <p class="text-lg font-semibold text-slate-900">{{ formatCurrency(selectedAnalysis.financial_summary?.profit || 0) }}</p>

                  </div>

                  <div>

                    <p class="text-sm text-slate-500">有效税率</p>

                    <p class="text-lg font-semibold text-slate-900">{{ formatPercent(selectedAnalysis.financial_summary?.effective_tax_rate || 0) }}</p>

                  </div>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">税种计算明细</h3>

                </div>

                <div class="p-5">

                  <table class="w-full">

                    <thead>

                      <tr class="text-left text-sm text-slate-500 border-b border-slate-200">

                        <th class="pb-3">税种</th>

                        <th class="pb-3 text-right">计税金额</th>

                        <th class="pb-3 text-right">税率</th>

                        <th class="pb-3 text-right">应纳税额</th>

                        <th class="pb-3 text-right">可抵扣项</th>

                      </tr>

                    </thead>

                    <tbody>

                      <tr

                        v-for="calc in selectedAnalysis.tax_calculations"

                        :key="calc.tax_type"

                        class="border-b border-slate-100 last:border-0"

                      >

                        <td class="py-3 font-medium text-slate-900">{{ formatTaxType(calc.tax_type) }}</td>

                        <td class="py-3 text-right text-slate-600">{{ formatCurrency(calc.taxable_amount) }}</td>

                        <td class="py-3 text-right text-slate-600">{{ formatPercent(calc.tax_rate) }}</td>

                        <td class="py-3 text-right font-medium text-slate-900">{{ formatCurrency(calc.tax_payable) }}</td>

                        <td class="py-3 text-right text-emerald-600">{{ formatCurrency(calc.deductions || 0) }}</td>

                      </tr>

                    </tbody>

                  </table>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

                  <h3 class="font-semibold text-slate-900">可享受的税收优惠政策</h3>

                  <span class="px-2 py-1 bg-emerald-50 text-emerald-700 text-xs font-medium rounded">

                    节省{{ formatCurrency(calculateTotalSavings()) }}

                  </span>

                </div>

                <div class="p-5 space-y-3">

                  <div
                    v-for="(policy, index) in matchedPolicies.length > 0 ? matchedPolicies : getApplicablePolicies()"
                    :key="index"
                    class="p-4 bg-gradient-to-r from-emerald-50 to-teal-50 rounded-lg border border-emerald-100"
                  >
                    <div class="flex items-start justify-between">
                      <div class="flex-1">
                        <div class="flex items-center gap-2 mb-2">
                          <CheckCircle :size="16" class="text-emerald-600" />
                          <h4 class="font-medium text-slate-900">{{ policy.policy_name || policy.name }}</h4>
                        </div>
                        <p class="text-sm text-slate-600 mb-2">{{ policy.policy_content || policy.description }}</p>
                        <div class="flex items-center gap-4 text-xs">
                          <span v-if="policy.applicable_conditions?.length || policy.condition" class="text-slate-500">
                            适用条件：{{ (policy.applicable_conditions || [policy.condition]).join(', ') }}
                          </span>
                        </div>
                      </div>
                      <div class="text-right ml-4">
                        <p class="text-lg font-bold text-emerald-600">{{ formatCurrency(policy.potential_savings || policy.savings) }}</p>
                        <p class="text-xs text-slate-500">节省金额</p>
                      </div>
                    </div>
                  </div>

                  <div v-if="matchedPolicies.length === 0 && getApplicablePolicies().length === 0" class="text-center py-6 text-slate-500">
                    <AlertTriangle :size="24" class="mx-auto mb-2 text-amber-500" />
                    <p>暂未匹配到适用的税收优惠政策</p>
                    <p class="text-xs mt-1">建议关注最新政策动态或调整企业经营范围</p>
                  </div>
                </div>
              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">申报建议</h3>

                </div>

                <div class="p-5 space-y-3">

                  <div

                    v-for="(recommendation, index) in getFilingRecommendations()"

                    :key="index"

                    class="p-4 bg-slate-50 rounded-lg border border-slate-200"

                  >

                    <div class="flex items-start gap-3">

                      <div class="w-6 h-6 bg-emerald-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">

                        <span class="text-xs font-bold text-emerald-600">{{ index + 1 }}</span>

                      </div>

                      <div class="flex-1">

                        <p class="font-medium text-slate-900 mb-1">{{ recommendation.title }}</p>

                        <p class="text-sm text-slate-600">{{ recommendation.description }}</p>

                        <div v-if="recommendation.priority" class="mt-2">

                          <span

                            :class="[

                              'px-2 py-1 text-xs font-medium rounded',

                              recommendation.priority === 'high' ? 'bg-red-100 text-red-700' :

                              recommendation.priority === 'medium' ? 'bg-amber-100 text-amber-700' :

                              'bg-blue-100 text-blue-700'

                            ]"

                          >

                            {{ recommendation.priority === 'high' ? '高优先级' : recommendation.priority === 'medium' ? '中优先级' : '建议关注' }}

                          </span>

                        </div>

                      </div>

                    </div>

                  </div>

                  <div v-if="getFilingRecommendations().length === 0" class="text-center py-6 text-slate-500">

                    <CheckCircle :size="24" class="mx-auto mb-2 text-emerald-500" />

                    <p>当前申报状态良好</p>

                    <p class="text-xs mt-1">请按常规流程完成申报即可</p>

                  </div>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">合规问题</h3>

                </div>

                <div class="p-5 space-y-3">

                  <div

                    v-for="(issue, index) in selectedAnalysis.risk_assessment || []"

                    :key="index"

                    :class="['p-4 rounded-lg border', riskLevelColors[issue.severity as keyof typeof riskLevelColors] || riskLevelColors.medium]"

                  >

                    <div class="flex items-start gap-3">

                      <component :is="severityIcons[issue.severity as keyof typeof severityIcons] || Info" :size="18" />

                      <div>

                        <p class="font-medium">{{ issue.risk_type }}</p>

                        <p class="text-sm mt-1 opacity-80">{{ issue.description }}</p>

                        <p class="text-sm mt-2 font-medium" v-if="issue.remediation_suggestions && issue.remediation_suggestions.length">
                          建议: {{ issue.remediation_suggestions[0] }}
                        </p>

                      </div>

                    </div>

                  </div>

                  <div v-if="!selectedAnalysis.risk_assessment || selectedAnalysis.risk_assessment.length === 0" class="text-center py-4 text-slate-500">

                    未发现合规问题                  </div>

                </div>

              </div>

            </div>



            <div class="space-y-6">

              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">风险评分</h3>

                </div>

                <div class="p-5 text-center">

                  <div class="relative w-32 h-32 mx-auto">

                    <svg class="w-full h-full transform -rotate-90">

                      <circle cx="64" cy="64" r="56" stroke="#e2e8f0" stroke-width="12" fill="none" />

                      <circle

                        cx="64"

                        cy="64"

                        r="56"

                        :stroke="selectedAnalysis.risk_score < 0.3 ? '#10b981' : selectedAnalysis.risk_score < 0.6 ? '#f59e0b' : selectedAnalysis.risk_score < 0.8 ? '#f97316' : '#ef4444'"

                        stroke-width="12"

                        fill="none"

                        :stroke-dasharray="`${selectedAnalysis.risk_score * 352} 352`"

                        stroke-linecap="round"

                      />

                    </svg>

                    <div class="absolute inset-0 flex items-center justify-center flex-col">

                      <span :class="['text-3xl font-bold', getRiskScoreColor(selectedAnalysis.risk_score)]">

                        {{ (selectedAnalysis.risk_score * 100).toFixed(0) }}

                      </span>

                      <span class="text-sm text-slate-500">/ 100</span>

                    </div>

                  </div>

                  <p class="mt-4 text-sm text-slate-600">

                    {{ selectedAnalysis.risk_score < 0.3 ? '低风险' : selectedAnalysis.risk_score < 0.6 ? '中等风险' : selectedAnalysis.risk_score < 0.8 ? '较高风险' : '高风险' }}

                  </p>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">置信度</h3>

                </div>

                <div class="p-5 text-center">

                  <p class="text-3xl font-bold text-emerald-600">{{ formatPercent(selectedAnalysis.confidence) }}</p>

                  <p class="text-sm text-slate-500 mt-1">分析置信度</p>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">报告信息</h3>

                </div>

                <div class="p-5 text-sm space-y-2">

                  <div class="flex justify-between">

                    <span class="text-slate-500">分析类型</span>

                    <span class="text-slate-900">{{ formatTaxType(selectedAnalysis.analysis_type) }}</span>

                  </div>

                  <div class="flex justify-between">

                    <span class="text-slate-500">会计年度</span>

                    <span class="text-slate-900">{{ selectedAnalysis.fiscal_year }}</span>

                  </div>

                  <div class="flex justify-between">

                    <span class="text-slate-500">会计期间</span>

                    <span class="text-slate-900">{{ selectedAnalysis.fiscal_period }}</span>

                  </div>

                  <div class="flex justify-between">

                    <span class="text-slate-500">生成时间</span>

                    <span class="text-slate-900">{{ formatDate(selectedAnalysis.created_at) }}</span>

                  </div>

                </div>

              </div>

            </div>

          </div>

        </div>

      </template>

    </div>



    <div

      v-if="showAnalysisModal"

      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"

      @click.self="showAnalysisModal = false"

    >

      <div class="bg-white rounded-xl w-full max-w-lg mx-4">

        <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

          <h3 class="font-semibold text-slate-900">新建税务分析</h3>

          <button @click="showAnalysisModal = false" class="p-1 hover:bg-slate-100 rounded">

            <X :size="20" class="text-slate-500" />

          </button>

        </div>

        <div class="p-5 space-y-4">

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">税种类型</label>

            <select

              v-model="analysisRequest.tax_type"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"

            >

              <option value="">请选择税种</option>

              <option value="企业所得税">企业所得税</option>

              <option value="增值税">增值税</option>

              <option value="个人所得税">个人所得税</option>

              <option value="消费税">消费税</option>

              <option value="全税种">全税种</option>

            </select>

          </div>

          <div class="grid grid-cols-2 gap-4">

            <div>

              <label class="block text-sm font-medium text-slate-700 mb-1">会计年度</label>

              <input

                v-model.number="analysisRequest.fiscal_year"

                type="number"

                class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"

              />

            </div>

            <div>

              <label class="block text-sm font-medium text-slate-700 mb-1">会计期间</label>

              <select

                v-model="analysisRequest.fiscal_period"

                class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"

              >

                <option value="Q1">第一季度</option>

                <option value="Q2">第二季度</option>

                <option value="Q3">第三季度</option>

                <option value="Q4">第四季度</option>

                <option value="全年">全年</option>

              </select>

            </div>

          </div>

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">企业名称</label>

            <input

              v-model="analysisRequest.company_name"

              type="text"

              placeholder="请输入企业名称"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"

            />

          </div>

        </div>

        <div class="px-5 py-4 border-t border-slate-200 flex justify-end gap-3">

          <button

            @click="showAnalysisModal = false"

            class="px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"

          >

            取消

          </button>

          <button

            @click="startAnalysis"

            :disabled="isLoading"

            class="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50 flex items-center gap-2"

          >

            <Loader2 v-if="isLoading" :size="16" class="animate-spin" />

            开始分析          </button>

        </div>

      </div>

    </div>

    <el-drawer
      v-model="showFinancialDataDrawer"
      title="选择财务数据"
      size="500px"
      direction="rtl"
    >
      <div class="p-4">
        <div v-if="financialDataList.length === 0" class="text-center py-8 text-slate-500">
          暂无财务数据记录
        </div>
        <div v-else class="space-y-3">
          <div
            v-for="item in financialDataList"
            :key="item.id"
            @click="selectFinancialData(item)"
            class="p-4 border border-slate-200 rounded-lg hover:border-emerald-500 hover:bg-emerald-50 cursor-pointer transition-colors"
          >
            <div class="flex justify-between items-center">
              <div>
                <p class="font-medium text-slate-900">{{ item.fiscal_year }}年 {{ item.period_type }}</p>
                <p class="text-sm text-slate-500 mt-1">收入: {{ formatCurrency(item.total_revenue) }}</p>
              </div>
              <div class="text-right">
                <p class="text-sm text-slate-500">利润</p>
                <p class="font-medium" :class="item.taxable_income > 0 ? 'text-emerald-600' : 'text-red-600'">
                  {{ formatCurrency(item.taxable_income) }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>

    <el-dialog
      v-model="showExplanationPanel"
      title="AI智能解读"
      width="600px"
      :close-on-click-modal="false"
    >
      <div class="space-y-4">
        <div class="flex gap-2">
          <input
            v-model="explanationInput"
            type="text"
            placeholder="输入您的问题，如：为什么我的企业所得税偏高？"
            class="flex-1 px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            @keyup.enter="explainReport"
          />
          <button
            @click="explainReport"
            :disabled="explanationLoading || !explanationInput.trim()"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Loader2 v-if="explanationLoading" :size="16" class="animate-spin" />
            提问
          </button>
        </div>
        <div v-if="explanationResult" class="p-4 bg-blue-50 rounded-lg border border-blue-100">
          <div class="flex items-start gap-2">
            <MessageSquare :size="20" class="text-blue-600 mt-1 flex-shrink-0" />
            <div class="text-sm text-slate-700 whitespace-pre-wrap">{{ explanationResult }}</div>
          </div>
        </div>
        <div v-else-if="explanationLoading" class="text-center py-8">
          <Loader2 :size="32" class="animate-spin text-blue-600 mx-auto" />
          <p class="text-sm text-slate-500 mt-2">正在生成解读...</p>
        </div>
      </div>
    </el-dialog>

    <el-dialog
      v-model="showPolicyDialog"
      title="匹配的税收优惠政策"
      width="800px"
    >
      <div class="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
        <div
          v-for="(policy, index) in matchedPolicies"
          :key="index"
          class="bg-white rounded-xl p-4 border border-gray-200 hover:shadow-md hover:border-emerald-300 transition-all"
        >
          <div class="flex items-start justify-between mb-3">
            <div class="flex-1">
              <h4 class="font-semibold text-gray-900 text-lg mb-1">{{ policy.policy_name }}</h4>
              <div class="flex items-center gap-3 text-xs text-gray-500">
                <span v-if="policy.source_name" class="flex items-center gap-1 text-blue-600">
                  <Shield :size="12" />
                  {{ policy.source_name }}
                </span>
                <span v-if="policy.effective_date" class="flex items-center gap-1">
                  <Calendar :size="12" />
                  生效: {{ formatDate(policy.effective_date) }}
                </span>
              </div>
            </div>
            <span :class="[
              'px-3 py-1 text-xs rounded-lg font-medium',
              policy.match_level === 'high' ? 'bg-emerald-100 text-emerald-700' :
              policy.match_level === 'medium' ? 'bg-blue-100 text-blue-700' :
              'bg-gray-100 text-gray-600'
            ]">
              {{ policy.match_level === 'high' ? '高匹配' : policy.match_level === 'medium' ? '中匹配' : '低匹配' }}
            </span>
          </div>
          <p class="text-sm text-gray-600 mb-3 line-clamp-3">{{ policy.policy_content }}</p>
          <div class="flex flex-wrap gap-2 mb-3">
            <span
              v-for="(condition, ci) in policy.applicable_conditions"
              :key="ci"
              class="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded border border-gray-200"
            >
              {{ condition }}
            </span>
          </div>
          <div class="flex items-center justify-between pt-3 border-t border-gray-100">
            <div class="flex items-center gap-4 text-xs text-gray-500">
              <span v-if="policy.tax_types?.length" class="flex items-center gap-1">
                <DollarSign :size="12" />
                {{ policy.tax_types.slice(0, 2).join(', ') }}
              </span>
              <span v-if="policy.industries?.length" class="flex items-center gap-1">
                <Building2 :size="12" />
                {{ policy.industries.slice(0, 2).join(', ') }}
              </span>
            </div>
            <div v-if="policy.potential_savings > 0" class="text-right">
              <span class="text-xl font-bold text-emerald-600">{{ formatCurrency(policy.potential_savings) }}</span>
              <span class="text-xs text-gray-500 ml-1">预计节省</span>
            </div>
          </div>
        </div>
        <div v-if="matchedPolicies.length === 0 && !isQueryingPolicies" class="text-center py-12">
          <FileText :size="40" class="mx-auto mb-3 text-gray-300" />
          <p class="text-gray-500">未找到匹配的优惠政策</p>
        </div>
      </div>
    </el-dialog>

  </div>

</template>

