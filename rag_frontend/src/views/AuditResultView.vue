<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { 
  FileBarChart,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  AlertCircle,
  DollarSign,
  Scale,
  ClipboardList,
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Sparkles,
  TrendingUp,
  Shield,
  Lightbulb
} from 'lucide-vue-next'
import { auditApi } from '@/api/audit'
import type { AuditTask, AuditResult, Finding, Conflict, AuditSeverity } from '@/types'

const route = useRoute()
const router = useRouter()

const task = ref<AuditTask | null>(null)
const result = ref<AuditResult | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)
const pollingInterval = ref<number | null>(null)
const expandedFindings = ref<Set<string>>(new Set())
const expandedConflicts = ref<Set<string>>(new Set())

const taskId = computed(() => route.params.id as string)

const riskLevelConfig = {
  critical: { color: 'bg-red-500', text: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200' },
  high: { color: 'bg-orange-500', text: 'text-orange-600', bg: 'bg-orange-50', border: 'border-orange-200' },
  medium: { color: 'bg-yellow-500', text: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-200' },
  low: { color: 'bg-green-500', text: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200' }
}

const agentIcons = {
  finance_agent: DollarSign,
  tax_agent: ClipboardList,
  legal_agent: Scale,
  reflection_agent: Sparkles
}

const sortedFindings = computed(() => {
  if (!result.value?.findings) return []
  return [...result.value.findings].sort((a, b) => {
    const order: Record<AuditSeverity, number> = { critical: 0, high: 1, medium: 2, low: 3 }
    return order[a.severity] - order[b.severity]
  })
})

const findingsByRisk = computed(() => {
  if (!result.value?.findings) return { critical: [], high: [], medium: [], low: [] }
  return {
    critical: sortedFindings.value.filter(f => f.severity === 'critical'),
    high: sortedFindings.value.filter(f => f.severity === 'high'),
    medium: sortedFindings.value.filter(f => f.severity === 'medium'),
    low: sortedFindings.value.filter(f => f.severity === 'low')
  }
})

const overallRiskLevel = computed(() => {
  if (!result.value) return 'low'
  const score = result.value.overall_risk_score
  if (score >= 80) return 'critical'
  if (score >= 60) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
})

async function fetchTask() {
  try {
    task.value = await auditApi.getTask(taskId.value)
    
    if (task.value.status === 'completed') {
      await fetchResults()
      stopPolling()
    } else if (task.value.status === 'failed') {
      error.value = task.value.error_message || '任务执行失败'
      stopPolling()
    } else {
      startPolling()
    }
  } catch (err: any) {
    error.value = err.message || '获取任务状态失败'
  } finally {
    isLoading.value = false
  }
}

async function fetchResults() {
  try {
    result.value = await auditApi.getTaskResults(taskId.value)
  } catch (err: any) {
    error.value = err.message || '获取审查结果失败'
  }
}

function startPolling() {
  pollingInterval.value = window.setInterval(fetchTask, 3000)
}

function stopPolling() {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
}

function toggleFinding(findingId: string | undefined) {
  if (!findingId) return
  if (expandedFindings.value.has(findingId)) {
    expandedFindings.value.delete(findingId)
  } else {
    expandedFindings.value.add(findingId)
  }
  expandedFindings.value = new Set(expandedFindings.value)
}

function toggleConflict(conflictId: string | undefined) {
  if (!conflictId) return
  if (expandedConflicts.value.has(conflictId)) {
    expandedConflicts.value.delete(conflictId)
  } else {
    expandedConflicts.value.add(conflictId)
  }
  expandedConflicts.value = new Set(expandedConflicts.value)
}

function goBack() {
  router.push('/audit/upload')
}

function retry() {
  error.value = null
  isLoading.value = true
  fetchTask()
}

onMounted(() => {
  fetchTask()
})
</script>

<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-slate-50 via-purple-50 to-indigo-50 h-full">
    <!-- Top Bar -->
    <div class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
      <div class="flex items-center gap-3">
        <button 
          @click="goBack"
          class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft :size="20" class="text-gray-600" />
        </button>
        <div class="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center">
          <FileBarChart :size="20" class="text-white" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-gray-900">审查结果</h2>
          <p class="text-xs text-gray-500">任务 ID: {{ taskId.slice(0, 8) }}...</p>
        </div>
      </div>
      
      <button
        v-if="error && task?.status !== 'failed'"
        @click="retry"
        class="px-4 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg transition-colors flex items-center gap-2"
      >
        <RefreshCw :size="16" />
        重试
      </button>
    </div>

    <!-- Main Content -->
    <div class="flex-1 overflow-y-auto p-8">
      
      <!-- Loading State -->
      <div v-if="isLoading" class="max-w-5xl mx-auto">
        <div class="bg-white rounded-2xl p-12 shadow-lg border border-gray-200 text-center">
          <div class="w-16 h-16 bg-gradient-to-br from-purple-400 to-pink-500 rounded-3xl flex items-center justify-center mx-auto mb-6 animate-pulse">
            <Clock :size="32" class="text-white" />
          </div>
          <h3 class="text-xl font-bold text-gray-900 mb-2">审查进行中...</h3>
          <p class="text-gray-600 mb-6">AI 智能体正在分析您的文档，请稍候</p>
          
          <!-- Progress Steps -->
          <div class="max-w-md mx-auto space-y-3">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center">
                <CheckCircle :size="16" class="text-purple-600" />
              </div>
              <span class="text-sm text-gray-700">文档解析</span>
            </div>
            <div class="ml-4 border-l-2 border-purple-200 h-6"></div>
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center animate-bounce">
                <RefreshCw :size="16" class="text-purple-600" />
              </div>
              <span class="text-sm text-gray-700">智能体审查中</span>
            </div>
            <div class="ml-4 border-l-2 border-gray-200 h-6"></div>
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
                <Clock :size="16" class="text-gray-400" />
              </div>
              <span class="text-sm text-gray-400">生成报告</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="max-w-5xl mx-auto">
        <div class="bg-red-50 rounded-2xl p-8 border border-red-200">
          <div class="flex items-start gap-4">
            <div class="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center flex-shrink-0">
              <XCircle :size="24" class="text-red-600" />
            </div>
            <div class="flex-1">
              <h3 class="font-bold text-red-900 mb-2">出错了</h3>
              <p class="text-red-700">{{ error }}</p>
              <button
                @click="retry"
                class="mt-4 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors"
              >
                重试
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Results -->
      <div v-else-if="result" class="max-w-5xl mx-auto space-y-6">
        
        <!-- Summary Card -->
        <div class="bg-white rounded-2xl p-6 shadow-lg border border-gray-200">
          <div class="flex items-start justify-between mb-6">
            <div>
              <h3 class="font-bold text-gray-900 text-lg mb-1">审查摘要</h3>
              <p class="text-sm text-gray-600">{{ result.audit_type }} · {{ new Date(result.created_at).toLocaleString() }}</p>
            </div>
            <div 
              class="px-4 py-2 rounded-xl border-2"
              :class="`${riskLevelConfig[overallRiskLevel].bg} ${riskLevelConfig[overallRiskLevel].border}`"
            >
              <div class="flex items-center gap-2">
                <AlertTriangle :size="20" :class="riskLevelConfig[overallRiskLevel].text" />
                <span class="font-bold" :class="riskLevelConfig[overallRiskLevel].text">
                  {{ overallRiskLevel.toUpperCase() }} 风险
                </span>
              </div>
            </div>
          </div>
          
          <p class="text-gray-700 mb-6">{{ result.summary }}</p>
          
          <!-- Statistics Grid -->
          <div class="grid grid-cols-4 gap-4 mb-6">
            <div class="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl p-4">
              <div class="text-2xl font-bold text-purple-700">{{ result.statistics.total_findings }}</div>
              <div class="text-sm text-purple-600">发现问题</div>
            </div>
            <div class="bg-gradient-to-br from-orange-50 to-red-50 rounded-xl p-4">
              <div class="text-2xl font-bold text-orange-700">{{ result.statistics.total_conflicts }}</div>
              <div class="text-sm text-orange-600">检测冲突</div>
            </div>
            <div class="bg-gradient-to-br from-blue-50 to-cyan-50 rounded-xl p-4">
              <div class="text-2xl font-bold text-blue-700">{{ (result.statistics.average_confidence * 100).toFixed(0) }}%</div>
              <div class="text-sm text-blue-600">平均置信度</div>
            </div>
            <div class="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl p-4">
              <div class="text-2xl font-bold text-green-700">{{ result.overall_risk_score.toFixed(0) }}</div>
              <div class="text-sm text-green-600">综合风险分</div>
            </div>
          </div>
          
          <!-- Risk Level Distribution -->
          <div class="mb-6">
            <h4 class="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Shield :size="18" class="text-purple-500" />
              风险分布
            </h4>
            <div class="flex gap-2">
              <div 
                v-for="(level, key) in findingsByRisk" 
                :key="key"
                class="flex-1 h-8 rounded-lg flex items-center justify-center text-sm font-medium text-white"
                :class="riskLevelConfig[key as RiskLevel].color"
                :style="{ opacity: level.length > 0 ? 1 : 0.3 }"
              >
                {{ level.length }}
              </div>
            </div>
            <div class="flex gap-2 mt-2 text-xs text-gray-600">
              <span class="flex-1 text-center">严重 {{ findingsByRisk.critical.length }}</span>
              <span class="flex-1 text-center">高危 {{ findingsByRisk.high.length }}</span>
              <span class="flex-1 text-center">中危 {{ findingsByRisk.medium.length }}</span>
              <span class="flex-1 text-center">低危 {{ findingsByRisk.low.length }}</span>
            </div>
          </div>
          
          <!-- Agent Contribution -->
          <div>
            <h4 class="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Sparkles :size="18" class="text-purple-500" />
              Agent 贡献分布
            </h4>
            <div class="flex flex-wrap gap-2">
              <div
                v-for="(count, agent) in result.statistics.agent_contribution"
                :key="agent"
                class="flex items-center gap-2 bg-gray-100 rounded-lg px-3 py-2"
              >
                <component 
                  :is="agentIcons[agent as keyof typeof agentIcons] || Sparkles" 
                  :size="16" 
                  class="text-purple-600" 
                />
                <span class="text-sm font-medium text-gray-700">{{ agent.replace('_agent', '') }}</span>
                <span class="text-sm text-purple-600 font-bold">{{ count }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Recommendations -->
        <div v-if="result.recommendations.length > 0" class="bg-gradient-to-br from-blue-50 to-purple-50 rounded-2xl p-6 shadow-lg border border-blue-200">
          <h3 class="font-bold text-gray-900 text-lg mb-4 flex items-center gap-2">
            <Lightbulb :size="20" class="text-blue-600" />
            改进建议
          </h3>
          <div class="space-y-3">
            <div
              v-for="(rec, index) in result.recommendations"
              :key="index"
              class="flex items-start gap-3 bg-white rounded-xl p-4 shadow-sm"
            >
              <div class="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0">
                <span class="text-xs font-bold text-white">{{ index + 1 }}</span>
              </div>
              <p class="text-gray-700">{{ rec }}</p>
            </div>
          </div>
        </div>

        <!-- Findings -->
        <div v-if="sortedFindings.length > 0" class="bg-white rounded-2xl p-6 shadow-lg border border-gray-200">
          <h3 class="font-bold text-gray-900 text-lg mb-4 flex items-center gap-2">
            <AlertTriangle :size="20" class="text-orange-600" />
            审查发现 ({{ sortedFindings.length }})
          </h3>
          
          <div class="space-y-3">
            <div
              v-for="finding in sortedFindings"
              :key="finding.id || finding.category"
              class="border rounded-xl overflow-hidden"
              :class="riskLevelConfig[finding.severity].border"
            >
              <div
                @click="toggleFinding(finding.id || finding.category)"
                class="p-4 cursor-pointer hover:bg-gray-50 transition-colors flex items-start gap-3"
              >
                <component 
                  :is="expandedFindings.has(finding.id || finding.category) ? ChevronDown : ChevronRight"
                  :size="20"
                  class="text-gray-400 flex-shrink-0 mt-1"
                />
                <div class="flex-1">
                  <div class="flex items-start justify-between gap-3 mb-2">
                    <div>
                      <span class="font-semibold text-gray-900">{{ finding.category }}</span>
                      <span v-if="finding.agent_name" class="ml-2 text-sm text-gray-500">{{ finding.agent_name.replace('_agent', '') }}</span>
                    </div>
                    <div 
                      class="px-2 py-1 rounded-lg text-xs font-medium"
                      :class="`${riskLevelConfig[finding.severity].bg} ${riskLevelConfig[finding.severity].text}`"
                    >
                      {{ finding.severity.toUpperCase() }}
                    </div>
                  </div>
                  <p class="text-gray-700 text-sm">{{ finding.description }}</p>
                  <div class="flex items-center gap-4 mt-2 text-xs text-gray-500">
                    <span v-if="finding.risk_score">风险分: {{ (finding.risk_score * 100).toFixed(0) }}</span>
                    <span>置信度: {{ (finding.confidence * 100).toFixed(0) }}%</span>
                  </div>
                </div>
              </div>
              
              <div v-if="expandedFindings.has(finding.id || finding.category)" class="border-t p-4 bg-gray-50 space-y-4">
                <div v-if="finding.evidence">
                  <h5 class="font-semibold text-gray-900 text-sm mb-2">证据</h5>
                  <p class="text-sm text-gray-700 whitespace-pre-wrap">{{ finding.evidence }}</p>
                </div>
                
                <div v-if="finding.legal_basis && finding.legal_basis.length > 0">
                  <h5 class="font-semibold text-gray-900 text-sm mb-2">法律依据</h5>
                  <ul class="space-y-1">
                    <li v-for="(law, i) in finding.legal_basis" :key="i" class="text-sm text-gray-700 flex items-start gap-2">
                      <span class="text-blue-500">•</span>
                      {{ law }}
                    </li>
                  </ul>
                </div>
                
                <div v-if="finding.recommendations && finding.recommendations.length > 0">
                  <h5 class="font-semibold text-gray-900 text-sm mb-2">建议</h5>
                  <ul class="space-y-1">
                    <li v-for="(rec, i) in finding.recommendations" :key="i" class="text-sm text-gray-700 flex items-start gap-2">
                      <span class="text-green-500">•</span>
                      {{ rec }}
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Conflicts -->
        <div v-if="result.conflicts && result.conflicts.length > 0" class="bg-orange-50 rounded-2xl p-6 shadow-lg border border-orange-200">
          <h3 class="font-bold text-orange-900 text-lg mb-4 flex items-center gap-2">
            <AlertCircle :size="20" class="text-orange-600" />
            冲突检测 ({{ result.conflicts.length }})
          </h3>
          
          <div class="space-y-3">
            <div
              v-for="conflict in result.conflicts"
              :key="conflict.id || conflict.type"
              class="bg-white rounded-xl p-4 shadow-sm border border-orange-200"
            >
              <div
                @click="toggleConflict(conflict.id || conflict.type)"
                class="cursor-pointer flex items-start gap-3"
              >
                <component 
                  :is="expandedConflicts.has(conflict.id || conflict.type) ? ChevronDown : ChevronRight"
                  :size="20"
                  class="text-orange-400 flex-shrink-0 mt-1"
                />
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-1">
                    <span class="font-semibold text-gray-900">{{ conflict.type }}</span>
                    <span class="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs">
                      {{ conflict.severity }}
                    </span>
                  </div>
                  <p class="text-gray-700 text-sm">{{ conflict.description }}</p>
                </div>
              </div>
              
              <div v-if="expandedConflicts.has(conflict.id || conflict.type)" class="mt-4 pl-8">
                <h5 class="font-semibold text-gray-900 text-sm mb-2">涉及发现</h5>
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="fid in conflict.finding_ids"
                    :key="fid"
                    class="px-2 py-1 bg-gray-100 rounded text-xs font-mono text-gray-600"
                  >
                    {{ fid.slice(0, 8) }}...
                  </span>
                </div>
                <div v-if="conflict.resolution_suggestion" class="mt-3">
                  <h5 class="font-semibold text-gray-900 text-sm mb-1">解决建议</h5>
                  <p class="text-sm text-gray-700">{{ conflict.resolution_suggestion }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bg-gradient-to-br {
  transition: all 0.3s ease;
}

.bg-gradient-to-br:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12);
}

.bg-white {
  transition: all 0.3s ease;
}

.bg-white:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.08);
}

button {
  transition: all 0.2s ease;
}

button:hover {
  transform: translateY(-2px);
}

button:active {
  transform: translateY(0);
}

.border {
  transition: all 0.2s ease;
}

.animate-pulse {
  animation: custom-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes custom-pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.8;
    transform: scale(1.05);
  }
}

.animate-bounce {
  animation: custom-bounce 1s ease-in-out infinite;
}

@keyframes custom-bounce {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}

.bg-red-50, .bg-orange-50, .bg-blue-50, .bg-green-50, .bg-purple-50, .bg-yellow-50 {
  transition: all 0.3s ease;
}

.bg-red-50:hover, .bg-orange-50:hover, .bg-blue-50:hover, .bg-green-50:hover, .bg-purple-50:hover, .bg-yellow-50:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.08);
}

.text-2xl {
  font-weight: 700;
}

.rounded-2xl {
  overflow: hidden;
}

@media print {
  .shadow-lg {
    box-shadow: none !important;
  }
  
  .bg-gradient-to-br {
    background: white !important;
  }
  
  .bg-white {
    page-break-inside: avoid;
  }
}

@media (max-width: 768px) {
  .grid-cols-4 {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .max-w-5xl {
    max-width: 100%;
  }
  
  .p-8 {
    padding: 16px;
  }
  
  .flex.items-start {
    flex-direction: column;
  }
  
  .space-y-3 > :not([hidden]) ~ :not([hidden]) {
    margin-top: 12px;
  }
  
  .flex.gap-2 {
    flex-wrap: wrap;
  }
  
  .bg-white.rounded-2xl.p-6 {
    padding: 16px;
  }
  
  .text-lg {
    font-size: 16px;
  }
  
  .text-xl {
    font-size: 18px;
  }
  
  .text-2xl {
    font-size: 20px;
  }
}

@media (max-width: 480px) {
  .grid-cols-4 {
    grid-template-columns: 1fr;
  }
  
  .flex.items-center.justify-between {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
}
</style>
