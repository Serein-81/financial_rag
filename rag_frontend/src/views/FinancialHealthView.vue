<script setup lang="ts">

import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

import { financialHealthApi, type FinancialHealthReport, type AnomalyRecord } from '@/api/financial-health'

import {

  Activity,

  TrendingUp,

  TrendingDown,

  AlertTriangle,

  CheckCircle,

  DollarSign,

  Download,

  RefreshCw,

  Search,

  ChevronRight,

  Loader2,

  BarChart3,

  PieChart,

  Wallet,

  Clock,

  X,

  Filter,

  Bell,

  Minus

} from 'lucide-vue-next'



const isLoading = ref(false)

const isExporting = ref(false)

const activeTab = ref<'dashboard' | 'anomalies' | 'report'>('dashboard')

const currentReport = ref<FinancialHealthReport | null>(null)

const financialMetricsMap = computed(() => {
  if (!currentReport.value?.financial_metrics) return {}
  const map: Record<string, any> = {}
  for (const m of currentReport.value.financial_metrics) {
    map[m.name] = m
  }
  return map
})

const anomalies = ref<AnomalyRecord[]>([])

const reportHistory = ref<FinancialHealthReport[]>([])

const totalReports = ref(0)

const totalAnomalies = ref(0)

const currentPage = ref(1)

const pageSize = ref(10)

const dataUnavailableMessage = ref<string | null>(null)



const showMonitorModal = ref(false)

const showAlertSubscription = ref(false)

const selectedPeriod = ref('2024-01')

const alertSubscription = ref({

  email: true,

  sms: false,

  webhook: false,

  webhookUrl: '',

  severity_levels: ['medium', 'high', 'critical']

})



const getDefaultDateRange = () => {

  const end = new Date()

  const start = new Date()

  start.setMonth(start.getMonth() - 3)

  const formatDate = (d: Date | string | undefined) => d ? new Date(d).toISOString().split('T')[0] : '--'

  return {

    period_start: formatDate(start),

    period_end: formatDate(end)

  }

}



const monitorRequest = ref({

  ...getDefaultDateRange(),

  include_anomaly_detection: true,

  include_trend_analysis: true

})



const healthStatusColors = {

  healthy: 'text-emerald-500 bg-emerald-50',

  warning: 'text-amber-500 bg-amber-50',

  critical: 'text-red-500 bg-red-50',

  unknown: 'text-slate-500 bg-slate-50'

}



const severityColors = {

  low: 'text-blue-500 bg-blue-50',

  medium: 'text-amber-500 bg-amber-50',

  high: 'text-orange-500 bg-orange-50',

  critical: 'text-red-500 bg-red-50'

}



const severityBgColors = {

  low: 'bg-blue-500',

  medium: 'bg-amber-500',

  high: 'bg-orange-500',

  critical: 'bg-red-500'

}



async function loadDashboard(skipCurrentReport = false) {
  isLoading.value = true
  try {
    const [reportRes, anomalyRes] = await Promise.all([
      financialHealthApi.getReportHistory({ page: 1, page_size: 5 }),
      financialHealthApi.getAnomalies({ page: 1, page_size: 5 })
    ])

    reportHistory.value = reportRes?.reports ?? []
    totalReports.value = reportRes?.total ?? 0
    anomalies.value = anomalyRes?.anomalies ?? []
    totalAnomalies.value = anomalyRes?.total ?? 0

    if (reportHistory.value.length > 0 && !skipCurrentReport) {
      currentReport.value = reportHistory.value[0]
    }

  } catch (e: any) {
    console.error('Failed to load dashboard:', e)
  } finally {
    isLoading.value = false
  }
}



async function loadAnomalies() {

  isLoading.value = true

  try {

    const result = await financialHealthApi.getAnomalies({

      page: currentPage.value,

      page_size: pageSize.value

    })

    anomalies.value = result.anomalies

    totalAnomalies.value = result.total

  } catch (e: any) {

    console.error('Failed to load anomalies:', e)

  } finally {

    isLoading.value = false

  }

}



async function startMonitoring() {

  isLoading.value = true

  dataUnavailableMessage.value = null

  try {

    const result = await financialHealthApi.monitorHealth(monitorRequest.value)

    currentReport.value = result

    console.log('📊 [Monitor] API Response:', {
      data_available: result.data_available,
      data_unavailable_message: result.data_unavailable_message,
      revenue_summary: result.revenue_summary,
      total_revenue: result.revenue_summary?.total_revenue
    })


    if (result.data_available === false || result.data_unavailable_message) {

      dataUnavailableMessage.value = result.data_unavailable_message || '财务数据功能暂时不可用，请先录入财务数据'

    }



    activeTab.value = 'report'

    showMonitorModal.value = false

    await loadDashboard(true)

  } catch (e: any) {

    console.error('Failed to start monitoring:', e)

    ElMessage.error('监控启动失败')

  } finally {

    isLoading.value = false

  }

}



async function exportPdf() {

  isExporting.value = true

  try {

    const blob = await financialHealthApi.exportReportPdf({ period_days: 90 })

    const url = window.URL.createObjectURL(blob)

    const a = document.createElement('a')

    a.href = url

    a.download = `财务健康报告_${new Date().toISOString().split('T')[0]}.pdf`

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



async function acknowledgeAnomaly(anomalyId: string) {

  try {

    await financialHealthApi.acknowledgeAnomaly(anomalyId)

    await loadAnomalies()

  } catch (e: any) {

    console.error('Failed to acknowledge anomaly:', e)

  }

}



async function saveAlertSubscription() {

  try {

    console.log('保存预警订阅配置:', alertSubscription.value)

    alertSubscription.value = {

      email: true,

      sms: false,

      webhook: false,

      webhookUrl: '',

      severity_levels: ['medium', 'high', 'critical']

    }

    showAlertSubscription.value = false

  } catch (e: any) {

    console.error('保存预警订阅失败:', e)

  }

}



function formatCurrency(value: number): string {

  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(value)

}



function formatPercent(value: number): string {

  return (value * 100).toFixed(2) + '%'

}



function formatDate(dateStr: string): string {

  return new Date(dateStr).toLocaleString('zh-CN')

}



function getHealthScoreColor(score: number): string {

  if (score >= 80) return 'text-emerald-500'

  if (score >= 60) return 'text-amber-500'

  if (score >= 40) return 'text-orange-500'

  return 'text-red-500'

}



function getHealthScoreBg(score: number): string {

  if (score >= 80) return 'bg-emerald-500'

  if (score >= 60) return 'bg-amber-500'

  if (score >= 40) return 'bg-orange-500'

  return 'bg-red-500'

}



function getHealthStatusLabel(status: string): string {

  const labels: Record<string, string> = {

    healthy: '健康',

    warning: '预警',

    critical: '危险',

    unknown: '未知'

  }

  return labels[status] || status

}



onMounted(() => {

  loadDashboard()

})

</script>



<template>

  <div class="h-screen flex flex-col bg-slate-50 overflow-hidden">

    <div class="bg-white border-b border-slate-200 px-6 py-4 flex-shrink-0">

      <div class="flex items-center justify-between">

        <div class="flex items-center gap-3">

          <div class="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">

            <Activity :size="20" class="text-blue-600" />

          </div>

          <div>

            <h1 class="text-xl font-bold text-slate-900">财务健康监控</h1>

            <p class="text-sm text-slate-500">实时监控企业财务状况与异常预警</p>

          </div>

        </div>

        <button

          @click="showMonitorModal = true"

          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 transition-colors"

        >

          <Search :size="16" />

          启动监控

        </button>

      </div>



      <div class="flex gap-4 mt-4 border-b border-slate-200">

        <button

          @click="activeTab = 'dashboard'"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'dashboard' ? 'text-blue-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          监控面板

          <div v-if="activeTab === 'dashboard'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />

        </button>

        <button

          @click="activeTab = 'anomalies'; loadAnomalies()"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'anomalies' ? 'text-blue-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          异常记录

          <div v-if="activeTab === 'anomalies'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />

        </button>

        <button

          v-if="currentReport"

          @click="activeTab = 'report'"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'report' ? 'text-blue-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          详细报告

          <div v-if="activeTab === 'report'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />

        </button>

      </div>

    </div>



    <div class="flex-1 overflow-y-auto p-6 min-h-0">

      <div v-if="isLoading" class="flex items-center justify-center h-64">

        <Loader2 :size="32" class="animate-spin text-blue-600" />

      </div>



      <template v-else>

        <div v-if="activeTab === 'dashboard'" class="space-y-6">

          <div class="grid grid-cols-1 md:grid-cols-4 gap-4">

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">健康评分</p>

                  <p class="text-2xl font-bold text-slate-900 mt-1">

                    {{ currentReport?.overall_health_score || '--' }}

                  </p>

                </div>

                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">

                  <BarChart3 :size="20" class="text-blue-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">健康状态</p>

                  <p class="text-2xl font-bold mt-1" :class="currentReport ? healthStatusColors[currentReport.health_status as keyof typeof healthStatusColors] : 'text-slate-500'">

                    {{ currentReport ? getHealthStatusLabel(currentReport.health_status) : '--' }}

                  </p>

                </div>

                <div class="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">

                  <CheckCircle :size="20" class="text-emerald-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">检测到异常</p>

                  <p class="text-2xl font-bold text-slate-900 mt-1">{{ totalAnomalies }}</p>

                </div>

                <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">

                  <AlertTriangle :size="20" class="text-amber-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">报告总数</p>

                  <p class="text-2xl font-bold text-slate-900 mt-1">{{ totalReports }}</p>

                </div>

                <div class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">

                  <Wallet :size="20" class="text-purple-600" />

                </div>

              </div>

            </div>

          </div>



          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

            <div class="bg-white rounded-xl border border-slate-200">

              <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

                <h3 class="font-semibold text-slate-900">财务指标</h3>

                <button @click="exportPdf" :disabled="isExporting" class="p-2 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50">

                  <Download v-if="!isExporting" :size="16" class="text-slate-500" />

                  <Loader2 v-else :size="16" class="text-slate-500 animate-spin" />

                </button>

              </div>

              <div class="p-5 space-y-4">

                <div v-if="currentReport">

                  <div class="grid grid-cols-2 gap-4">

                    <div class="p-3 bg-slate-50 rounded-lg">

                      <p class="text-sm text-slate-500">营收总额</p>

                      <p class="text-lg font-semibold text-slate-900">{{ formatCurrency(currentReport.revenue_summary?.total_revenue || 0) }}</p>

                      <div class="flex items-center gap-1 mt-1">

                        <TrendingUp v-if="currentReport.revenue_summary?.revenue_growth >= 0" :size="14" class="text-emerald-500" />

                        <TrendingDown v-else :size="14" class="text-red-500" />

                        <span :class="currentReport.revenue_summary?.revenue_growth >= 0 ? 'text-emerald-500' : 'text-red-500'" class="text-sm">

                          {{ (currentReport.revenue_summary?.revenue_growth || 0) > 0 ? '+' : '' }}{{ formatPercent(currentReport.revenue_summary?.revenue_growth || 0) }}

                        </span>

                      </div>

                    </div>

                    <div class="p-3 bg-slate-50 rounded-lg">

                      <p class="text-sm text-slate-500">净利润</p>

                      <p class="text-lg font-semibold text-slate-900">{{ formatCurrency(currentReport.profit_summary?.net_profit || 0) }}</p>

                      <p class="text-sm text-slate-500 mt-1">利润率 {{ formatPercent(currentReport.profit_summary?.profit_margin || 0) }}</p>

                    </div>

                    <div class="p-3 bg-slate-50 rounded-lg">

                      <p class="text-sm text-slate-500">现金流入</p>

                      <p class="text-lg font-semibold text-slate-900">{{ formatCurrency(currentReport.cash_flow_summary?.inflow || 0) }}</p>

                    </div>

                    <div class="p-3 bg-slate-50 rounded-lg">

                      <p class="text-sm text-slate-500">净现金流</p>

                      <p class="text-lg font-semibold" :class="(currentReport.cash_flow_summary?.net_flow || 0) >= 0 ? 'text-emerald-600' : 'text-red-600'">

                        {{ formatCurrency(currentReport.cash_flow_summary?.net_flow || 0) }}

                      </p>

                    </div>

                  </div>

                </div>

                <div v-else class="text-center py-8 text-slate-500">

                  暂无数据，请启动监控

                </div>

              </div>

            </div>



            <div class="bg-white rounded-xl border border-slate-200">

              <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

                <h3 class="font-semibold text-slate-900">最近异常</h3>

                <button

                  v-if="anomalies.length > 0"

                  @click="showAlertSubscription = true"

                  class="px-3 py-1 text-xs bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 flex items-center gap-1"

                >

                  <Bell :size="12" />

                  预警订阅

                </button>

              </div>

              <div class="p-5">

                <div v-if="anomalies.length === 0" class="text-center py-8 text-slate-500">

                  <CheckCircle :size="32" class="mx-auto mb-2 text-emerald-500" />

                  <p>暂无异常记录</p>

                  <p class="text-xs mt-1">财务状况健康</p>

                </div>

                <div v-else class="space-y-3">

                  <div

                    v-for="anomaly in anomalies.slice(0, 5)"

                    :key="anomaly.id"

                    :class="['p-3 rounded-lg border', severityColors[anomaly.severity as keyof typeof severityColors]]"

                  >

                    <div class="flex items-start justify-between">

                      <div class="flex-1">

                        <p class="font-medium">{{ anomaly.title }}</p>

                        <p class="text-sm opacity-80 mt-1">{{ anomaly.description }}</p>

                        <div class="flex items-center gap-3 mt-2 text-xs opacity-70">

                          <span>检测值 {{ anomaly.detected_value }}</span>

                          <span>偏差: {{ anomaly.deviation }}%</span>

                        </div>

                      </div>

                      <button

                        v-if="anomaly.status === 'detected'"

                        @click="acknowledgeAnomaly(anomaly.id)"

                        class="text-xs px-2 py-1 rounded hover:opacity-80 bg-white/50"

                      >

                        确认

                      </button>

                    </div>

                  </div>

                </div>

              </div>

            </div>

          </div>



          <div v-if="currentReport && currentReport.trend_indicators?.length > 0" class="bg-white rounded-xl border border-slate-200">

            <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

              <h3 class="font-semibold text-slate-900">趋势分析</h3>

              <div class="flex gap-2">

                <button

                  v-for="period in ['日', '周', '月']"

                  :key="period"

                  @click="selectedPeriod = period"

                  :class="[

                    'px-3 py-1 text-xs rounded-lg transition-colors',

                    selectedPeriod === period ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'

                  ]"

                >

                  {{ period }}

                </button>

              </div>

            </div>

            <div class="p-5">

              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">

                <div

                  v-for="trend in (currentReport.trend_indicators || [])"

                  :key="trend.metric"

                  class="p-4 bg-slate-50 rounded-lg"

                >

                  <div class="flex items-center justify-between mb-2">

                    <p class="text-sm text-slate-600">{{ trend.metric }}</p>

                    <TrendingUp v-if="trend.direction === 'up'" :size="16" class="text-emerald-500" />

                    <TrendingDown v-else-if="trend.direction === 'down'" :size="16" class="text-red-500" />

                    <Minus v-else :size="16" class="text-slate-400" />

                  </div>

                  <p class="text-xl font-bold" :class="trend.direction === 'up' ? 'text-emerald-600' : trend.direction === 'down' ? 'text-red-600' : 'text-slate-600'">

                    {{ trend.change_percentage > 0 ? '+' : '' }}{{ formatPercent(trend.change_percentage) }}

                  </p>

                  <div class="w-full h-2 bg-slate-200 rounded-full mt-2 overflow-hidden">

                    <div

                      :class="[

                        'h-full rounded-full transition-all',

                        trend.direction === 'up' ? 'bg-emerald-500' : trend.direction === 'down' ? 'bg-red-500' : 'bg-slate-400'

                      ]"

                      :style="{ width: `${Math.min(Math.abs(trend.change_percentage), 100)}%` }"

                    />

                  </div>

                </div>

              </div>

            </div>

          </div>



          <div class="bg-white rounded-xl border border-slate-200">

            <div class="px-5 py-4 border-b border-slate-200">

              <h3 class="font-semibold text-slate-900">关键财务指标</h3>

            </div>

            <div class="p-5">

              <div v-if="currentReport" class="grid grid-cols-2 md:grid-cols-5 gap-4">

                <div class="text-center">

                  <p class="text-sm text-slate-500">流动比率</p>

                  <p class="text-xl font-bold text-slate-900">{{ financialMetricsMap['流动比率']?.value?.toFixed(2) || '--' }}</p>

                </div>

                <div class="text-center">

                  <p class="text-sm text-slate-500">速动比率</p>

                  <p class="text-xl font-bold text-slate-900">{{ financialMetricsMap['速动比率']?.value?.toFixed(2) || '--' }}</p>

                </div>

                <div class="text-center">

                  <p class="text-sm text-slate-500">资产负债率</p>

                  <p class="text-xl font-bold text-slate-900">{{ formatPercent(financialMetricsMap['资产负债率']?.value || 0) }}</p>

                </div>

                <div class="text-center">

                  <p class="text-sm text-slate-500">资产回报率</p>

                  <p class="text-xl font-bold text-slate-900">{{ formatPercent(financialMetricsMap['资产回报率']?.value || 0) }}</p>

                </div>

                <div class="text-center">

                  <p class="text-sm text-slate-500">净资产回报率</p>

                  <p class="text-xl font-bold text-slate-900">{{ formatPercent(financialMetricsMap['净资产回报率']?.value || 0) }}</p>

                </div>

              </div>

              <div v-else class="text-center py-8 text-slate-500">

                暂无数据

              </div>

            </div>

          </div>

        </div>



        <div v-else-if="activeTab === 'anomalies'" class="space-y-4">

          <div class="bg-white rounded-xl border border-slate-200">

            <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

              <h3 class="font-semibold text-slate-900">异常记录</h3>

              <button

                @click="loadAnomalies"

                class="p-2 hover:bg-slate-100 rounded-lg transition-colors"

              >

                <RefreshCw :size="16" class="text-slate-500" />

              </button>

            </div>

            <div class="p-5">

              <div v-if="anomalies.length === 0" class="text-center py-8 text-slate-500">

                暂无异常记录

              </div>

              <div v-else class="space-y-3">

                <div

                  v-for="anomaly in anomalies"

                  :key="anomaly.id"

                  :class="['p-4 rounded-lg border', severityColors[anomaly.severity as keyof typeof severityColors]]"

                >

                  <div class="flex items-start justify-between">

                    <div class="flex items-start gap-3">

                      <AlertTriangle :size="18" />

                      <div>

                        <p class="font-medium">{{ anomaly.title }}</p>

                        <p class="text-sm opacity-80 mt-1">{{ anomaly.description }}</p>

                        <div class="flex items-center gap-4 mt-2 text-xs opacity-70">

                          <span>检测值 {{ anomaly.detected_value }}</span>

                          <span>期望值 {{ anomaly.expected_value }}</span>

                          <span>偏差: {{ anomaly.deviation }}%</span>

                        </div>

                      </div>

                    </div>

                    <div class="flex items-center gap-2">

                      <span :class="['px-2 py-1 rounded text-xs font-medium', severityColors[anomaly.severity as keyof typeof severityColors]]">

                        {{ anomaly.severity }}

                      </span>

                      <button

                        v-if="anomaly.status === 'detected'"

                        @click="acknowledgeAnomaly(anomaly.id)"

                        class="px-3 py-1 bg-white/50 rounded text-xs hover:bg-white/80 transition-colors"

                      >

                        确认

                      </button>

                    </div>

                  </div>

                </div>

              </div>

            </div>

          </div>

        </div>



        <div v-else-if="activeTab === 'report' && currentReport" class="space-y-6">

          <div v-if="dataUnavailableMessage" class="bg-amber-50 border border-amber-200 rounded-lg p-4">

            <div class="flex items-start gap-3">

              <AlertTriangle class="text-amber-500 flex-shrink-0 mt-0.5" :size="20" />

              <div class="flex-1">

                <h3 class="font-medium text-amber-800">数据不可填</h3>

                <p class="text-sm text-amber-700 mt-1">{{ dataUnavailableMessage }}</p>

                <button

                  @click="$router.push('/financial-data-entry')"

                  class="mt-3 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 text-sm flex items-center gap-2"

                >

                  <span>立即录入财务数据</span>

                  <ChevronRight :size="16" />

                </button>

              </div>

            </div>

          </div>



          <div class="flex items-center justify-between">

            <div>

              <h2 class="text-lg font-semibold text-slate-900">财务健康报告</h2>

              <p class="text-sm text-slate-500 mt-1">报告ID: {{ currentReport.id }}</p>

            </div>

            <div class="flex gap-2">

              <button

                @click="exportPdf"

                :disabled="isExporting"

                class="px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 flex items-center gap-2 transition-colors disabled:opacity-50"

              >

                <Download v-if="!isExporting" :size="16" />

                <Loader2 v-else :size="16" class="animate-spin" />

                导出PDF

              </button>

            </div>

          </div>



          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

            <div class="lg:col-span-2 space-y-6">

              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">财务摘要</h3>

                </div>

                <div class="p-5">

                  <div class="grid grid-cols-3 gap-4">

                    <div class="text-center p-4 bg-slate-50 rounded-lg">

                      <p class="text-sm text-slate-500">营收</p>

                      <p class="text-xl font-bold text-slate-900">{{ formatCurrency(currentReport.revenue_summary?.total_revenue || 0) }}</p>

                    </div>

                    <div class="text-center p-4 bg-slate-50 rounded-lg">

                      <p class="text-sm text-slate-500">成本</p>

                      <p class="text-xl font-bold text-slate-900">{{ formatCurrency(currentReport.expense_summary?.total_expenses || 0) }}</p>

                    </div>

                    <div class="text-center p-4 bg-slate-50 rounded-lg">

                      <p class="text-sm text-slate-500">净利润</p>

                      <p class="text-xl font-bold text-emerald-600">{{ formatCurrency(currentReport.profit_summary?.net_profit || 0) }}</p>

                    </div>

                  </div>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">异常检测</h3>

                </div>

                <div class="p-5 space-y-3">

                  <div

                    v-for="anomaly in (currentReport.anomaly_detections || [])"

                    :key="anomaly.anomaly_type"

                    :class="['p-4 rounded-lg border', severityColors[anomaly.severity as keyof typeof severityColors]]"

                  >

                    <div class="flex items-start gap-3">

                      <AlertTriangle :size="18" />

                      <div>

                        <p class="font-medium">{{ anomaly.anomaly_type }}</p>

                        <p class="text-sm opacity-80 mt-1">{{ anomaly.description }}</p>

                      </div>

                    </div>

                  </div>

                  <div v-if="currentReport?.anomalies_detected?.length === 0" class="text-center py-4 text-slate-500">

                    未检测到异常

                  </div>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">建议措施</h3>

                </div>

                <div class="p-5 space-y-3">

                  <div

                    v-for="(rec, index) in (currentReport.recommendations || [])"

                    :key="index"

                    class="p-4 border border-slate-200 rounded-lg"

                  >

                    <div class="flex items-start gap-3">

                      <span :class="['px-2 py-1 rounded text-xs font-medium', rec.priority === 'high' ? 'bg-red-100 text-red-600' : rec.priority === 'medium' ? 'bg-amber-100 text-amber-600' : 'bg-blue-100 text-blue-600']">

                        {{ rec.priority }}

                      </span>

                      <div>

                        <p class="font-medium">{{ rec.title }}</p>

                        <p class="text-sm text-slate-600 mt-1">{{ rec.description }}</p>

                        <ul class="mt-2 text-sm text-slate-500 list-disc list-inside">

                          <li v-for="(action, idx) in rec.action_items" :key="idx">{{ action }}</li>

                        </ul>

                      </div>

                    </div>

                  </div>

                </div>

              </div>

            </div>



            <div class="space-y-6">

              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">健康评分</h3>

                </div>

                <div class="p-5 text-center">

                  <div class="relative w-32 h-32 mx-auto">

                    <svg class="w-full h-full transform -rotate-90">

                      <circle cx="64" cy="64" r="56" stroke="#e2e8f0" stroke-width="12" fill="none" />

                      <circle

                        cx="64" cy="64" r="56"

                        :stroke="currentReport.overall_health_score >= 80 ? '#10b981' : currentReport.overall_health_score >= 60 ? '#f59e0b' : currentReport.overall_health_score >= 40 ? '#f97316' : '#ef4444'"

                        stroke-width="12" fill="none"

                        :stroke-dasharray="`${currentReport.overall_health_score * 3.52} 352`"

                        stroke-linecap="round"

                      />

                    </svg>

                    <div class="absolute inset-0 flex items-center justify-center flex-col">

                      <span :class="['text-3xl font-bold', getHealthScoreColor(currentReport.overall_health_score)]">

                        {{ currentReport.overall_health_score }}

                      </span>

                      <span class="text-sm text-slate-500">/ 100</span>

                    </div>

                  </div>

                  <p class="mt-4 text-sm text-slate-600">

                    {{ getHealthStatusLabel(currentReport.health_status) }}

                  </p>

                </div>

              </div>



              <div class="bg-white rounded-xl border border-slate-200">

                <div class="px-5 py-4 border-b border-slate-200">

                  <h3 class="font-semibold text-slate-900">报告信息</h3>

                </div>

                <div class="p-5 text-sm space-y-2">

                  <div class="flex justify-between">

                    <span class="text-slate-500">监控期间</span>

                    <span class="text-slate-900">{{ new Date(currentReport.period_start).toLocaleDateString() }} - {{ new Date(currentReport.period_end).toLocaleDateString() }}</span>

                  </div>

                  <div class="flex justify-between">

                    <span class="text-slate-500">生成时间</span>

                    <span class="text-slate-900">{{ formatDate(currentReport.created_at) }}</span>

                  </div>

                </div>

              </div>

            </div>

          </div>

        </div>

      </template>

    </div>



    <div

      v-if="showMonitorModal"

      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"

      @click.self="showMonitorModal = false"

    >

      <div class="bg-white rounded-xl w-full max-w-lg mx-4">

        <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

          <h3 class="font-semibold text-slate-900">启动财务监控</h3>

          <button @click="showMonitorModal = false" class="p-1 hover:bg-slate-100 rounded">

            <X :size="20" class="text-slate-500" />

          </button>

        </div>

        <div class="p-5 space-y-4">

          <div class="grid grid-cols-2 gap-4">

            <div>

              <label class="block text-sm font-medium text-slate-700 mb-1">开始日期</label>

              <input

                v-model="monitorRequest.period_start"

                type="date"

                class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"

              />

            </div>

            <div>

              <label class="block text-sm font-medium text-slate-700 mb-1">结束日期</label>

              <input

                v-model="monitorRequest.period_end"

                type="date"

                class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"

              />

            </div>

          </div>

          <div class="space-y-2">

            <label class="flex items-center gap-2">

              <input

                v-model="monitorRequest.include_anomaly_detection"

                type="checkbox"

                class="w-4 h-4 text-blue-600 border-slate-300 rounded focus:ring-blue-500"

              />

              <span class="text-sm text-slate-700">包含异常检测</span>

            </label>

            <label class="flex items-center gap-2">

              <input

                v-model="monitorRequest.include_trend_analysis"

                type="checkbox"

                class="w-4 h-4 text-blue-600 border-slate-300 rounded focus:ring-blue-500"

              />

              <span class="text-sm text-slate-700">包含趋势分析</span>

            </label>

          </div>

        </div>

        <div class="px-5 py-4 border-t border-slate-200 flex justify-end gap-3">

          <button

            @click="showMonitorModal = false"

            class="px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"

          >

            取消

          </button>

          <button

            @click="startMonitoring"

            :disabled="isLoading"

            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center gap-2"

          >

            <Loader2 v-if="isLoading" :size="16" class="animate-spin" />

            启动监控

          </button>

        </div>

      </div>

    </div>



    <div

      v-if="showAlertSubscription"

      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"

      @click.self="showAlertSubscription = false"

    >

      <div class="bg-white rounded-xl w-full max-w-lg mx-4">

        <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

          <h3 class="font-semibold text-slate-900 flex items-center gap-2">

            <Bell :size="18" />

            预警订阅设置

          </h3>

          <button @click="showAlertSubscription = false" class="p-1 hover:bg-slate-100 rounded">

            <X :size="20" class="text-slate-500" />

          </button>

        </div>

        <div class="p-5 space-y-4">

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-2">通知方式</label>

            <div class="space-y-2">

              <label class="flex items-center gap-2">

                <input

                  v-model="alertSubscription.email"

                  type="checkbox"

                  class="w-4 h-4 text-blue-600 border-slate-300 rounded focus:ring-blue-500"

                />

                <span class="text-sm text-slate-700">邮件通知</span>

              </label>

              <label class="flex items-center gap-2">

                <input

                  v-model="alertSubscription.sms"

                  type="checkbox"

                  class="w-4 h-4 text-blue-600 border-slate-300 rounded focus:ring-blue-500"

                />

                <span class="text-sm text-slate-700">短信通知</span>

              </label>

              <label class="flex items-center gap-2">

                <input

                  v-model="alertSubscription.webhook"

                  type="checkbox"

                  class="w-4 h-4 text-blue-600 border-slate-300 rounded focus:ring-blue-500"

                />

                <span class="text-sm text-slate-700">Webhook回调</span>

              </label>

            </div>

          </div>

          <div v-if="alertSubscription.webhook">

            <label class="block text-sm font-medium text-slate-700 mb-1">Webhook地址</label>

            <input

              v-model="alertSubscription.webhookUrl"

              type="url"

              placeholder="https://your-api.com/webhook"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"

            />

          </div>

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-2">预警级别</label>

            <div class="flex gap-2">

              <button

                @click="alertSubscription.severity_levels.includes('low') ? alertSubscription.severity_levels = alertSubscription.severity_levels.filter(s => s !== 'low') : alertSubscription.severity_levels.push('low')"

                :class="[

                  'px-3 py-1 text-sm rounded-lg border transition-colors',

                  alertSubscription.severity_levels.includes('low') ? 'bg-blue-50 border-blue-300 text-blue-700' : 'bg-slate-50 border-slate-200 text-slate-600'

                ]"

              >

                ?              </button>

              <button

                @click="alertSubscription.severity_levels.includes('medium') ? alertSubscription.severity_levels = alertSubscription.severity_levels.filter(s => s !== 'medium') : alertSubscription.severity_levels.push('medium')"

                :class="[

                  'px-3 py-1 text-sm rounded-lg border transition-colors',

                  alertSubscription.severity_levels.includes('medium') ? 'bg-amber-50 border-amber-300 text-amber-700' : 'bg-slate-50 border-slate-200 text-slate-600'

                ]"

              >

                ?              </button>

              <button

                @click="alertSubscription.severity_levels.includes('high') ? alertSubscription.severity_levels = alertSubscription.severity_levels.filter(s => s !== 'high') : alertSubscription.severity_levels.push('high')"

                :class="[

                  'px-3 py-1 text-sm rounded-lg border transition-colors',

                  alertSubscription.severity_levels.includes('high') ? 'bg-orange-50 border-orange-300 text-orange-700' : 'bg-slate-50 border-slate-200 text-slate-600'

                ]"

              >

                ?              </button>

              <button

                @click="alertSubscription.severity_levels.includes('critical') ? alertSubscription.severity_levels = alertSubscription.severity_levels.filter(s => s !== 'critical') : alertSubscription.severity_levels.push('critical')"

                :class="[

                  'px-3 py-1 text-sm rounded-lg border transition-colors',

                  alertSubscription.severity_levels.includes('critical') ? 'bg-red-50 border-red-300 text-red-700' : 'bg-slate-50 border-slate-200 text-slate-600'

                ]"

              >

                严重

              </button>

            </div>

          </div>

        </div>

        <div class="px-5 py-4 border-t border-slate-200 flex justify-end gap-3">

          <button

            @click="showAlertSubscription = false"

            class="px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"

          >

            取消

          </button>

          <button

            @click="saveAlertSubscription"

            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"

          >

            保存设置

          </button>

        </div>

      </div>

    </div>

  </div>

</template>

