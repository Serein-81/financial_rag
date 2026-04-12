<script setup lang="ts">

import { ref, computed, onMounted } from 'vue'

import { contractReviewApi, type ContractAnalysisResult, type ContractReport } from '@/api/contract-review'

import {

  FileText,

  AlertTriangle,

  CheckCircle,

  Download,

  RefreshCw,

  Search,

  ChevronRight,

  Loader2,

  Scale,

  FileAlertTriangle,

  FileWarning,

  X,

  Eye,

  Trash2,

  GitCompare,

  LayoutTemplate

} from 'lucide-vue-next'



const isLoading = ref(false)

const isExporting = ref(false)

const activeTab = ref<'dashboard' | 'history' | 'detail' | 'compare'>('dashboard')

const selectedAnalysis = ref<ContractAnalysisResult | null>(null)

const analysisHistory = ref<ContractReport[]>([])

const totalHistory = ref(0)

const currentPage = ref(1)

const pageSize = ref(10)



const showAnalysisModal = ref(false)

const showCompareModal = ref(false)

const comparisonResult = ref<any>(null)

const templates = ref<any[]>([])

const compareContracts = ref({

  contract1: '',

  contract2: '',

  template: ''

})



const analysisRequest = ref({

  contract_text: '',

  contract_type: 'other' as const,

  counterparty: '',

  contract_value: 0

})



const contractTypes = [

  { value: 'purchase', label: '采购合同' },

  { value: 'sales', label: '销售合同' },

  { value: 'service', label: '服务合同' },

  { value: 'lease', label: '租赁合同' },

  { value: 'employment', label: '劳动合同' },

  { value: 'partnership', label: '合作协议' },

  { value: 'loan', label: '借款合同' },

  { value: 'other', label: '其他合同' }

]



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



async function loadHistory() {

  isLoading.value = true

  try {

    const result = await contractReviewApi.getAnalysisHistory({

      page: currentPage.value,

      page_size: pageSize.value

    })

    analysisHistory.value = result.analyses

    totalHistory.value = result.total

  } catch (e: any) {

    console.error('Failed to load history:', e)

  } finally {

    isLoading.value = false

  }

}



async function viewDetail(analysisId: string) {

  isLoading.value = true

  try {

    selectedAnalysis.value = await contractReviewApi.getAnalysisDetail(analysisId)

    activeTab.value = 'detail'

  } catch (e: any) {

    console.error('Failed to load analysis detail:', e)

  } finally {

    isLoading.value = false

  }

}



async function startAnalysis() {

  if (!analysisRequest.value.contract_text) {

    alert('请输入合同文本')

    return

  }

  

  isLoading.value = true

  try {

    const result = await contractReviewApi.analyzeContract(analysisRequest.value)

    selectedAnalysis.value = result

    activeTab.value = 'detail'

    showAnalysisModal.value = false

    await loadHistory()

  } catch (e: any) {

    console.error('Failed to analyze contract:', e)

    alert('分析失败: ' + (e.message || '未知错误'))

  } finally {

    isLoading.value = false

  }

}



async function exportPdf(analysisId: string) {

  isExporting.value = true

  try {

    const blob = await contractReviewApi.exportReportPdf(analysisId)

    const url = window.URL.createObjectURL(blob)

    const a = document.createElement('a')

    a.href = url

    a.download = `合同审核报告_${analysisId}_${new Date().toISOString().split('T')[0]}.pdf`

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



async function deleteAnalysis(analysisId: string) {

  if (!confirm('确定要删除这条分析记录吗？')) return

  try {

    await contractReviewApi.deleteAnalysis(analysisId)

    await loadHistory()

  } catch (e: any) {

    console.error('Failed to delete analysis:', e)

  }

}



function getContractTypeLabel(type: string): string {

  return contractTypes.find(t => t.value === type)?.label || type

}



function formatCurrency(value: number): string {

  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(value)

}



function formatDate(dateStr: string): string {

  return new Date(dateStr).toLocaleString('zh-CN')

}



function getRiskScoreColor(score: number): string {

  if (score < 0.3) return 'text-emerald-500'

  if (score < 0.6) return 'text-amber-500'

  if (score < 0.8) return 'text-orange-500'

  return 'text-red-500'

}



async function loadTemplates() {

  try {

    templates.value = await contractReviewApi.getTemplates({})

  } catch (e) {

    console.error('Failed to load templates:', e)

  }

}



async function openCompareModal() {

  showCompareModal.value = true

  await loadTemplates()

}



async function performComparison() {

  if (!compareContracts.value.contract1 || !compareContracts.value.contract2) {

    alert('请选择要对比的合同')

    return

  }

  isLoading.value = true

  try {

    comparisonResult.value = await contractReviewApi.compareContracts({

      contract1_id: compareContracts.value.contract1,

      contract2_id: compareContracts.value.contract2

    })

    activeTab.value = 'compare'

    showCompareModal.value = false

  } catch (e) {

    console.error('Failed to compare contracts:', e)

  } finally {

    isLoading.value = false

  }

}



onMounted(() => {

  loadHistory()

})

</script>



<template>

  <div class="h-full flex flex-col bg-slate-50">

    <div class="bg-white border-b border-slate-200 px-6 py-4">

      <div class="flex items-center justify-between">

        <div class="flex items-center gap-3">

          <div class="w-10 h-10 bg-purple-100 rounded-xl flex items-center justify-center">

            <Scale :size="20" class="text-purple-600" />

          </div>

          <div>

            <h1 class="text-xl font-bold text-slate-900">合同智能审核</h1>

            <p class="text-sm text-slate-500">AI驱动的合同风险识别与条款分析</p>

          </div>

        </div>

        <div class="flex items-center gap-2">

          <button

            @click="openCompareModal"

            class="px-4 py-2 bg-white border border-purple-300 text-purple-600 rounded-lg hover:bg-purple-50 flex items-center gap-2 transition-colors"

          >

            <GitCompare :size="16" />

            模板对比

          </button>

          <button

            @click="showAnalysisModal = true"

            class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center gap-2 transition-colors"

          >

            <Search :size="16" />

            新建审核

          </button>

        </div>

      </div>



      <div class="flex gap-4 mt-4 border-b border-slate-200">

        <button

          @click="activeTab = 'dashboard'"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'dashboard' ? 'text-purple-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          审核概览

          <div v-if="activeTab === 'dashboard'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-purple-600" />

        </button>

        <button

          @click="activeTab = 'history'"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'history' ? 'text-purple-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          审核记录

          <div v-if="activeTab === 'history'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-purple-600" />

        </button>

        <button

          v-if="selectedAnalysis"

          @click="activeTab = 'detail'"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'detail' ? 'text-purple-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          审核详情

          <div v-if="activeTab === 'detail'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-purple-600" />

        </button>

        <button

          v-if="comparisonResult"

          @click="activeTab = 'compare'"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'compare' ? 'text-purple-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          对比结果

          <div v-if="activeTab === 'compare'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-purple-600" />

        </button>

      </div>

    </div>



    <div class="flex-1 overflow-auto p-6">

      <div v-if="isLoading" class="flex items-center justify-center h-64">

        <Loader2 :size="32" class="animate-spin text-purple-600" />

      </div>



      <template v-else>

        <div v-if="activeTab === 'dashboard'" class="space-y-6">

          <div class="grid grid-cols-1 md:grid-cols-4 gap-4">

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">审核总数</p>

                  <p class="text-2xl font-bold text-slate-900 mt-1">{{ totalHistory }}</p>

                </div>

                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">

                  <FileText :size="20" class="text-blue-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">高风险合同</p>

                  <p class="text-2xl font-bold text-red-500 mt-1">{{ analysisHistory.filter(a => a.overall_risk_level === 'high' || a.overall_risk_level === 'critical').length }}</p>

                </div>

                <div class="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">

                  <AlertTriangle :size="20" class="text-red-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">低风险合同</p>

                  <p class="text-2xl font-bold text-emerald-500 mt-1">{{ analysisHistory.filter(a => a.overall_risk_level === 'low').length }}</p>

                </div>

                <div class="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">

                  <CheckCircle :size="20" class="text-emerald-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">本月审核</p>

                  <p class="text-2xl font-bold text-slate-900 mt-1">{{ analysisHistory.length }}</p>

                </div>

                <div class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">

                  <Scale :size="20" class="text-purple-600" />

                </div>

              </div>

            </div>

          </div>



          <div class="bg-white rounded-xl border border-slate-200">

            <div class="px-5 py-4 border-b border-slate-200">

              <h3 class="font-semibold text-slate-900">最近审核</h3>

            </div>

            <div class="p-5">

              <div v-if="analysisHistory.length === 0" class="text-center py-8 text-slate-500">

                暂无审核记录

              </div>

              <div v-else class="space-y-3">

                <div

                  v-for="item in analysisHistory.slice(0, 5)"

                  :key="item.id"

                  @click="viewDetail(item.analysis_id)"

                  class="flex items-center justify-between p-4 border border-slate-200 rounded-lg hover:border-purple-500 cursor-pointer transition-colors"

                >

                  <div class="flex items-center gap-4">

                    <div :class="['w-3 h-3 rounded-full', riskLevelBgColors[item.overall_risk_level as keyof typeof riskLevelBgColors]]" />

                    <div>

                      <p class="font-medium text-slate-900">{{ item.contract_name || item.contract_type }}</p>

                      <p class="text-sm text-slate-500 mt-1">

                        {{ getContractTypeLabel(item.contract_type) }} - {{ item.counterparty }}

                      </p>

                    </div>

                  </div>

                  <div class="flex items-center gap-4">

                    <span :class="['px-2 py-1 rounded text-xs font-medium', riskLevelColors[item.overall_risk_level as keyof typeof riskLevelColors]]">

                      {{ item.overall_risk_level }}

                    </span>

                    <span class="text-sm text-slate-500">{{ formatDate(item.created_at) }}</span>

                    <ChevronRight :size="16" class="text-slate-400" />

                  </div>

                </div>

              </div>

            </div>

          </div>

        </div>



        <div v-else-if="activeTab === 'history'" class="space-y-4">

          <div class="bg-white rounded-xl border border-slate-200">

            <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

              <h3 class="font-semibold text-slate-900">审核记录</h3>

              <button

                @click="loadHistory"

                class="p-2 hover:bg-slate-100 rounded-lg transition-colors"

              >

                <RefreshCw :size="16" class="text-slate-500" />

              </button>

            </div>

            <div class="p-5">

              <div v-if="analysisHistory.length === 0" class="text-center py-8 text-slate-500">

                暂无审核记录

              </div>

              <div v-else class="space-y-3">

                <div

                  v-for="item in analysisHistory"

                  :key="item.id"

                  class="flex items-center justify-between p-4 border border-slate-200 rounded-lg hover:border-purple-500 transition-colors"

                >

                  <div class="flex items-center gap-4">

                    <div :class="['w-3 h-3 rounded-full', riskLevelBgColors[item.overall_risk_level as keyof typeof riskLevelBgColors]]" />

                    <div>

                      <p class="font-medium text-slate-900">{{ item.contract_name || getContractTypeLabel(item.contract_type) }}</p>

                      <p class="text-sm text-slate-500 mt-1">{{ item.counterparty }} | {{ formatDate(item.created_at) }}</p>

                    </div>

                  </div>

                  <div class="flex items-center gap-2">

                    <span :class="['px-2 py-1 rounded text-xs font-medium', riskLevelColors[item.overall_risk_level as keyof typeof riskLevelColors]]">

                      {{ item.overall_risk_level }}

                    </span>

                    <button

                      @click="viewDetail(item.analysis_id)"

                      class="p-2 hover:bg-slate-100 rounded-lg"

                    >

                      <Eye :size="16" class="text-slate-500" />

                    </button>

                    <button

                      @click="deleteAnalysis(item.analysis_id)"

                      class="p-2 hover:bg-red-50 rounded-lg"

                    >

                      <Trash2 :size="16" class="text-red-500" />

                    </button>

                  </div>

                </div>

              </div>

            </div>

          </div>

        </div>



        <div v-else-if="activeTab === 'detail' && selectedAnalysis" class="space-y-6">

          <div class="flex items-center justify-between">

            <div>

              <h2 class="text-lg font-semibold text-slate-900">合同审核报告</h2>

              <p class="text-sm text-slate-500 mt-1">审核ID: {{ selectedAnalysis.analysis_id }}</p>

            </div>

            <div class="flex gap-2">

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

                  <h3 class="font-semibold text-slate-900">基本信息</h3>

                </div>

                <div class="p-5">

                  <div class="grid grid-cols-2 gap-4">

                    <div>

                      <p class="text-sm text-slate-500">合同类型</p>

                      <p class="font-medium text-slate-900">{{ getContractTypeLabel(selectedAnalysis.contract_type) }}</p>

                    </div>

                    <div>

                      <p class="text-sm text-slate-500">合同金额</p>

                      <p class="font-medium text-slate-900">{{ formatCurrency(selectedAnalysis.contract_value) }}</p>

                    </div>

                    <div>

                      <p class="text-sm text-slate-500">相对风险</p>

                      <p class="font-medium text-slate-900">{{ selectedAnalysis.counterparty }}</p>

                    </div>

                    <div>

                      <p class="text-sm text-slate-500">有效期</p>

                      <p class="font-medium text-slate-900">

                        {{ new Date(selectedAnalysis.basic_analysis.effective_date).toLocaleDateString() }} 

                        ?

                        {{ new Date(selectedAnalysis.basic_analysis.expiration_date).toLocaleDateString() }}

                      </p>

                    </div>

                  </div>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">风险条款分析</h3>

                </div>

                <div class="p-5 space-y-4">

                  <div

                    v-for="(clause, index) in selectedAnalysis.clauses"

                    :key="index"

                    :class="['p-4 rounded-lg border', riskLevelColors[clause.risk_level as keyof typeof riskLevelColors]]"

                  >

                    <div class="flex items-start gap-3">

                      <FileWarning :size="18" />

                      <div class="flex-1">

                        <div class="flex items-center justify-between">

                          <p class="font-medium">{{ clause.title }}</p>

                          <span :class="['px-2 py-1 rounded text-xs font-medium', riskLevelColors[clause.risk_level as keyof typeof riskLevelColors]]">

                            {{ clause.risk_level }}

                          </span>

                        </div>

                        <p class="text-sm opacity-80 mt-2">{{ clause.text }}</p>

                        <div class="mt-3">

                          <p class="text-sm font-medium">分析:</p>

                          <p class="text-sm opacity-80">{{ clause.analysis }}</p>

                        </div>

                        <div v-if="clause.suggestions.length > 0" class="mt-3">

                          <p class="text-sm font-medium">建议:</p>

                          <ul class="text-sm opacity-80 list-disc list-inside">

                            <li v-for="(sug, idx) in clause.suggestions" :key="idx">{{ sug }}</li>

                          </ul>

                        </div>

                      </div>

                    </div>

                  </div>

                  <div v-if="selectedAnalysis.clauses.length === 0" class="text-center py-4 text-slate-500">

                    未检测到风险条款

                  </div>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">不利条款</h3>

                </div>

                <div class="p-5 space-y-4">

                  <div

                    v-for="(clause, index) in selectedAnalysis.unfavorable_clauses"

                    :key="index"

                    class="p-4 border border-red-200 rounded-lg bg-red-50"

                  >

                    <p class="font-medium text-red-700">{{ clause.clause }}</p>

                    <p class="text-sm text-red-600 mt-2">{{ clause.risk_description }}</p>

                    <div class="mt-3 p-3 bg-white rounded">

                      <p class="text-sm font-medium text-slate-700">建议修改:</p>

                      <p class="text-sm text-slate-600">{{ clause.suggested_revision }}</p>

                    </div>

                  </div>

                  <div v-if="selectedAnalysis.unfavorable_clauses.length === 0" class="text-center py-4 text-slate-500">

                    未发现不利条款                  </div>

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

                        cx="64" cy="64" r="56"

                        :stroke="selectedAnalysis.overall_risk_score < 0.3 ? '#10b981' : selectedAnalysis.overall_risk_score < 0.6 ? '#f59e0b' : selectedAnalysis.overall_risk_score < 0.8 ? '#f97316' : '#ef4444'"

                        stroke-width="12" fill="none"

                        :stroke-dasharray="`${selectedAnalysis.overall_risk_score * 352} 352`"

                        stroke-linecap="round"

                      />

                    </svg>

                    <div class="absolute inset-0 flex items-center justify-center flex-col">

                      <span :class="['text-3xl font-bold', getRiskScoreColor(selectedAnalysis.overall_risk_score)]">

                        {{ (selectedAnalysis.overall_risk_score * 100).toFixed(0) }}

                      </span>

                      <span class="text-sm text-slate-500">/ 100</span>

                    </div>

                  </div>

                  <p class="mt-4 text-sm text-slate-600">

                    {{ selectedAnalysis.overall_risk_level === 'low' ? '低风险' : selectedAnalysis.overall_risk_level === 'medium' ? '中等风险' : selectedAnalysis.overall_risk_level === 'high' ? '较高风险' : '高风险' }}

                  </p>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">风险统计</h3>

                </div>

                <div class="p-5">

                  <div class="space-y-3">

                    <div class="flex items-center justify-between">

                      <div class="flex items-center gap-2">

                        <div class="w-3 h-3 rounded-full bg-red-500" />

                        <span class="text-sm text-slate-600">高风险</span>

                      </div>

                      <span class="font-medium text-slate-900">{{ selectedAnalysis.risk_summary.high_risk_count }}</span>

                    </div>

                    <div class="flex items-center justify-between">

                      <div class="flex items-center gap-2">

                        <div class="w-3 h-3 rounded-full bg-amber-500" />

                        <span class="text-sm text-slate-600">中等风险</span>

                      </div>

                      <span class="font-medium text-slate-900">{{ selectedAnalysis.risk_summary.medium_risk_count }}</span>

                    </div>

                    <div class="flex items-center justify-between">

                      <div class="flex items-center gap-2">

                        <div class="w-3 h-3 rounded-full bg-emerald-500" />

                        <span class="text-sm text-slate-600">低风险</span>

                      </div>

                      <span class="font-medium text-slate-900">{{ selectedAnalysis.risk_summary.low_risk_count }}</span>

                    </div>

                  </div>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">AI摘要</h3>

                </div>

                <div class="p-5">

                  <p class="text-sm text-slate-600">{{ selectedAnalysis.ai_summary }}</p>

                </div>

              </div>

            </div>

          </div>

        </div>



        <div v-else-if="activeTab === 'compare' && comparisonResult" class="space-y-6">

          <div class="flex items-center justify-between">

            <div>

              <h2 class="text-lg font-semibold text-slate-900">合同对比结果</h2>

              <p class="text-sm text-slate-500 mt-1">相似度 {{ (comparisonResult.similarity_score * 100).toFixed(1) }}%</p>

            </div>

            <div class="flex gap-2">

              <button

                @click="comparisonResult = null; activeTab = 'dashboard'"

                class="px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"

              >

                返回概览

              </button>

            </div>

          </div>



          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

            <div class="bg-white rounded-xl border border-slate-200">

              <div class="px-5 py-4 border-b border-slate-200">

                <h3 class="font-semibold text-slate-900">差异对比</h3>

              </div>

              <div class="p-5 space-y-4">

                <div

                  v-for="(diff, index) in comparisonResult.differences"

                  :key="index"

                  class="p-4 bg-slate-50 rounded-lg"

                >

                  <div class="flex items-center justify-between mb-2">

                    <span class="font-medium text-slate-900">{{ diff.category }}</span>

                  </div>

                  <div class="grid grid-cols-2 gap-2 text-sm">

                    <div class="p-2 bg-blue-50 rounded">

                      <p class="text-xs text-slate-500 mb-1">合同1</p>

                      <p class="text-slate-700">{{ diff.contract1_value }}</p>

                    </div>

                    <div class="p-2 bg-purple-50 rounded">

                      <p class="text-xs text-slate-500 mb-1">合同2</p>

                      <p class="text-slate-700">{{ diff.contract2_value }}</p>

                    </div>

                  </div>

                  <p class="text-sm text-amber-600 mt-2">影响: {{ diff.impact }}</p>

                </div>

                <div v-if="comparisonResult.differences.length === 0" class="text-center py-8 text-slate-500">

                  未发现显著差异                </div>

              </div>

            </div>



            <div class="bg-white rounded-xl border border-slate-200">

              <div class="px-5 py-4 border-b border-slate-200">

                <h3 class="font-semibold text-slate-900">对比摘要</h3>

              </div>

              <div class="p-5">

                <p class="text-sm text-slate-600">{{ comparisonResult.comparison_summary }}</p>

              </div>

            </div>

          </div>



          <div v-if="templates.length > 0" class="bg-white rounded-xl border border-slate-200">

            <div class="px-5 py-4 border-b border-slate-200">

              <h3 class="font-semibold text-slate-900 flex items-center gap-2">

                <LayoutTemplate :size="18" />

                标准模板参考              </h3>

            </div>

            <div class="p-5 grid grid-cols-1 md:grid-cols-3 gap-4">

              <div

                v-for="template in templates.slice(0, 3)"

                :key="template.id"

                class="p-4 border border-slate-200 rounded-lg hover:border-purple-300 transition-colors"

              >

                <div class="flex items-start justify-between mb-2">

                  <h4 class="font-medium text-slate-900">{{ template.name }}</h4>

                  <span class="text-xs text-slate-500">{{ template.usage_count }}次使用</span>

                </div>

                <p class="text-sm text-slate-500">{{ template.description }}</p>

              </div>

            </div>

          </div>

        </div>

      </template>

    </div>



    <div

      v-if="showCompareModal"

      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"

      @click.self="showCompareModal = false"

    >

      <div class="bg-white rounded-xl w-full max-w-lg mx-4">

        <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

          <h3 class="font-semibold text-slate-900 flex items-center gap-2">

            <GitCompare :size="18" />

            合同模板对比

          </h3>

          <button @click="showCompareModal = false" class="p-1 hover:bg-slate-100 rounded">

            <X :size="20" class="text-slate-500" />

          </button>

        </div>

        <div class="p-5 space-y-4">

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">选择合同1</label>

            <select

              v-model="compareContracts.contract1"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"

            >

              <option value="">请选择合同</option>

              <option v-for="item in analysisHistory" :key="item.id" :value="item.id">

                {{ item.contract_name || item.contract_type }} - {{ item.counterparty }}

              </option>

            </select>

          </div>

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">选择合同2</label>

            <select

              v-model="compareContracts.contract2"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"

            >

              <option value="">请选择合同</option>

              <option v-for="item in analysisHistory" :key="item.id" :value="item.id">

                {{ item.contract_name || item.contract_type }} - {{ item.counterparty }}

              </option>

            </select>

          </div>

        </div>

        <div class="px-5 py-4 border-t border-slate-200 flex justify-end gap-3">

          <button

            @click="showCompareModal = false"

            class="px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"

          >

            取消

          </button>

          <button

            @click="performComparison"

            :disabled="isLoading"

            class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 flex items-center gap-2"

          >

            <Loader2 v-if="isLoading" :size="16" class="animate-spin" />

            开始对话          </button>

        </div>

      </div>

    </div>



    <div

      v-if="showAnalysisModal"

      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"

      @click.self="showAnalysisModal = false"

    >

      <div class="bg-white rounded-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-auto">

        <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between sticky top-0 bg-white">

          <h3 class="font-semibold text-slate-900">新建合同审核</h3>

          <button @click="showAnalysisModal = false" class="p-1 hover:bg-slate-100 rounded">

            <X :size="20" class="text-slate-500" />

          </button>

        </div>

        <div class="p-5 space-y-4">

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">合同类型</label>

            <select

              v-model="analysisRequest.contract_type"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"

            >

              <option v-for="type in contractTypes" :key="type.value" :value="type.value">

                {{ type.label }}

              </option>

            </select>

          </div>

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">相对风险</label>

            <input

              v-model="analysisRequest.counterparty"

              type="text"

              placeholder="请输入合同相对方名称"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"

            />

          </div>

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">合同金额</label>

            <input

              v-model.number="analysisRequest.contract_value"

              type="number"

              placeholder="请输入合同金额"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"

            />

          </div>

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">合同文本</label>

            <textarea

              v-model="analysisRequest.contract_text"

              rows="10"

              placeholder="请粘贴合同文本内容"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"

            />

          </div>

        </div>

        <div class="px-5 py-4 border-t border-slate-200 flex justify-end gap-3 sticky bottom-0 bg-white">

          <button

            @click="showAnalysisModal = false"

            class="px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"

          >

            取消

          </button>

          <button

            @click="startAnalysis"

            :disabled="isLoading"

            class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 flex items-center gap-2"

          >

            <Loader2 v-if="isLoading" :size="16" class="animate-spin" />

            开始审核          </button>

        </div>

      </div>

    </div>

  </div>

</template>

