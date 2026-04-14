<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { policyApi, type PolicyMatchResult } from '@/api/policy'
import { getEnterpriseId } from '@/utils/request'
import { ElMessage } from 'element-plus'
import {
  Building2,
  Loader2,
  Target,
  TrendingUp,
  CheckCircle,
  AlertCircle,
  Eye,
  ArrowRight,
  RefreshCw,
  Settings,
  Calendar,
  Bell,
  BarChart3,
  Sparkles,
  Brain,
  Zap,
  Cpu
} from 'lucide-vue-next'

const router = useRouter()

const isLoading = ref(false)
const isRefreshing = ref(false)
const matches = ref<PolicyMatchResult[]>([])
const selectedMatch = ref<PolicyMatchResult | null>(null)

// PolicyNotificationAgent 状态
const useLLM = ref(true)
const agentStatus = ref<any>(null)
const isCheckingAgent = ref(false)
const detailedMatches = ref<any[]>([])
const isLoadingDetails = ref(false)

// 获取企业画像（示例数据）
const enterpriseProfile = ref({
  enterprise_id: 'ENT-001',
  enterprise_name: '示例科技有限公司',
  industry: '科技',
  region: '北京',
  scale: '中型企业',
  tax_types: ['增值税', '企业所得税'],
  qualifications: ['高新技术企业', '软件企业']
})

const statistics = computed(() => ({
  total: matches.value.length,
  highMatch: matches.value.filter(m => m.match_score >= 0.8).length,
  mediumMatch: matches.value.filter(m => m.match_score >= 0.6 && m.match_score < 0.8).length,
  lowMatch: matches.value.filter(m => m.match_score < 0.6).length
}))

onMounted(async () => {
  await loadMatches()
  await checkAgentStatus()
})

async function checkAgentStatus() {
  isCheckingAgent.value = true
  try {
    agentStatus.value = await policyApi.getPolicyAgentStatus()
    useLLM.value = agentStatus.value.use_llm
  } catch (error: any) {
    console.error('Failed to check agent status:', error)
    agentStatus.value = null
  } finally {
    isCheckingAgent.value = false
  }
}

async function loadMatches() {
  const enterpriseId = getEnterpriseId()

  isLoading.value = true
  try {
    matches.value = await policyApi.getEnterpriseMatches(enterpriseId)
  } catch (error: any) {
    ElMessage.error('加载匹配结果失败')
    console.error('Failed to load matches:', error)
  } finally {
    isLoading.value = false
  }
}

async function refreshMatches() {
  isRefreshing.value = true
  try {
    await policyApi.matchEnterprisePolicies(getEnterpriseId())
    await loadMatches()
    ElMessage.success('匹配结果已更新')
  } catch (error: any) {
    ElMessage.error('刷新匹配结果失败')
    console.error('Failed to refresh matches:', error)
  } finally {
    isRefreshing.value = false
  }
}

async function loadDetailedMatches() {
  if (matches.value.length === 0) {
    ElMessage.warning('请先加载匹配结果')
    return
  }

  isLoadingDetails.value = true
  detailedMatches.value = []

  try {
    for (const match of matches.value.slice(0, 5)) {
      const policy = match.policy

      const matchRequest = {
        policy: {
          policy_id: policy.id || policy.policy_id,
          title: policy.title,
          content: policy.content || '',
          source: 'policy_center',
          priority: policy.priority || 'medium'
        },
        enterprise: enterpriseProfile.value,
        use_llm: useLLM.value
      }

      const result = await policyApi.matchPolicyWithEnterprise(matchRequest)
      detailedMatches.value.push({
        policy_id: policy.id || policy.policy_id,
        title: policy.title,
        ...result
      })
    }

    ElMessage.success('详细匹配分析完成')
  } catch (error: any) {
    ElMessage.error('加载详细匹配失败')
    console.error('Failed to load detailed matches:', error)
  } finally {
    isLoadingDetails.value = false
  }
}

function viewPolicyDetail(policyId: string) {
  router.push(`/policy/${policyId}`)
}

function getMatchScoreColor(score: number) {
  if (score >= 0.8) return 'bg-emerald-500'
  if (score >= 0.6) return 'bg-blue-500'
  if (score >= 0.4) return 'bg-amber-500'
  return 'bg-gray-400'
}

function getMatchScoreBgColor(score: number) {
  if (score >= 0.8) return 'bg-emerald-50 border-emerald-200'
  if (score >= 0.6) return 'bg-blue-50 border-blue-200'
  if (score >= 0.4) return 'bg-amber-50 border-amber-200'
  return 'bg-gray-50 border-gray-200'
}

function getMatchStatusLabel(score: number) {
  if (score >= 0.8) return '高度匹配'
  if (score >= 0.6) return '良好匹配'
  if (score >= 0.4) return '一般匹配'
  return '低匹配'
}

function toggleLLMMode() {
  useLLM.value = !useLLM.value
  ElMessage.success(useLLM.value ? '已启用 LLM 智能匹配模式' : '已切换到规则匹配模式')
}

function getDetailedMatch(policyId: string) {
  return detailedMatches.value.find(m => m.policy_id === policyId)
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-slate-100 via-blue-50/30 to-indigo-50/30 h-full">
    <!-- Top Bar -->
    <div class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-gradient-to-br from-teal-600 to-emerald-600 rounded-xl flex items-center justify-center">
          <Target :size="20" class="text-white" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-gray-900">企业政策匹配</h2>
          <p class="text-xs text-gray-500">管理与查看企业政策匹配结果</p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <!-- Agent Status -->
        <div v-if="agentStatus" class="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border border-purple-200">
          <Brain :size="16" class="text-purple-600" />
          <span class="text-xs font-medium text-purple-700">
            {{ agentStatus.use_llm ? 'LLM智能模式' : '规则匹配模式' }}
          </span>
          <span v-if="agentStatus.llm_provider" class="text-xs text-purple-500">
            ({{ agentStatus.llm_provider }})
          </span>
        </div>

        <!-- LLM Mode Toggle -->
        <button
          v-if="agentStatus"
          @click="toggleLLMMode"
          :disabled="isCheckingAgent"
          :class="[
            'px-4 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-2',
            useLLM
              ? 'bg-purple-600 text-white hover:bg-purple-700'
              : 'border border-gray-200 text-gray-700 hover:bg-gray-50'
          ]"
        >
          <Cpu :size="16" />
          {{ useLLM ? '已启用LLM' : '启用LLM' }}
        </button>

        <!-- LLM智能分析按钮 -->
        <button
          @click="loadDetailedMatches"
          :disabled="isLoadingDetails || matches.length === 0"
          class="px-4 py-2 rounded-xl bg-gradient-to-r from-teal-600 to-emerald-600 text-white text-sm font-medium hover:from-teal-700 hover:to-emerald-700 transition-all disabled:opacity-50 flex items-center gap-2"
        >
          <Sparkles :size="16" :class="{ 'animate-pulse': isLoadingDetails }" />
          {{ isLoadingDetails ? '分析中...' : 'LLM智能分析' }}
        </button>

        <button
          @click="refreshMatches"
          :disabled="isRefreshing"
          class="px-4 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-all flex items-center gap-2"
        >
          <RefreshCw :size="16" :class="{ 'animate-spin': isRefreshing }" />
          重新匹配
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 overflow-y-auto p-6">
      <div class="max-w-6xl mx-auto space-y-6">
        <!-- Statistics Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                <Target :size="24" class="text-blue-600" />
              </div>
              <span class="px-2 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium">
                总计
              </span>
            </div>
            <h3 class="text-2xl font-bold text-gray-900 mb-1">{{ statistics.total }}</h3>
            <p class="text-xs text-gray-500">匹配政策数量</p>
          </div>

          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center">
                <CheckCircle :size="24" class="text-emerald-600" />
              </div>
              <span class="px-2 py-1 bg-emerald-50 text-emerald-700 rounded-lg text-xs font-medium">
                高度匹配
              </span>
            </div>
            <h3 class="text-2xl font-bold text-emerald-600 mb-1">{{ statistics.highMatch }}</h3>
            <p class="text-xs text-gray-500">匹配度 ≥ 80%</p>
          </div>

          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                <TrendingUp :size="24" class="text-blue-600" />
              </div>
              <span class="px-2 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium">
                良好匹配
              </span>
            </div>
            <h3 class="text-2xl font-bold text-blue-600 mb-1">{{ statistics.mediumMatch }}</h3>
            <p class="text-xs text-gray-500">匹配度 60% - 80%</p>
          </div>

          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center">
                <AlertCircle :size="24" class="text-amber-600" />
              </div>
              <span class="px-2 py-1 bg-amber-50 text-amber-700 rounded-lg text-xs font-medium">
                一般匹配
              </span>
            </div>
            <h3 class="text-2xl font-bold text-amber-600 mb-1">{{ statistics.lowMatch }}</h3>
            <p class="text-xs text-gray-500">匹配度 &lt; 60%</p>
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="isLoading" class="flex items-center justify-center py-20">
          <div class="text-center">
            <Loader2 :size="40" class="animate-spin text-teal-600 mx-auto mb-3" />
            <p class="text-sm text-gray-500">正在加载匹配结果...</p>
          </div>
        </div>

        <!-- Match List -->
        <div v-else-if="matches.length > 0">
          <div class="flex items-center gap-2 mb-4">
            <h3 class="text-lg font-semibold text-gray-900">匹配结果列表</h3>
            <span class="px-2 py-0.5 bg-teal-100 text-teal-700 rounded text-xs">
              {{ matches.length }} 条
            </span>
          </div>

          <div class="space-y-4">
            <div
              v-for="match in matches"
              :key="match.policy_id"
              @click="viewPolicyDetail(match.policy_id)"
              :class="[
                'bg-white rounded-2xl p-6 shadow-sm border-2 transition-all cursor-pointer group hover:shadow-lg',
                getMatchScoreBgColor(match.match_score)
              ]"
            >
              <div class="flex items-start gap-6">
                <!-- Match Score -->
                <div class="flex-shrink-0">
                  <div class="relative w-20 h-20">
                    <svg class="w-20 h-20 transform -rotate-90">
                      <circle
                        cx="40"
                        cy="40"
                        r="36"
                        stroke="currentColor"
                        stroke-width="6"
                        fill="none"
                        :class="match.match_score >= 0.8 ? 'text-emerald-200' : match.match_score >= 0.6 ? 'text-blue-200' : match.match_score >= 0.4 ? 'text-amber-200' : 'text-gray-200'"
                      />
                      <circle
                        cx="40"
                        cy="40"
                        r="36"
                        stroke="currentColor"
                        stroke-width="6"
                        fill="none"
                        stroke-linecap="round"
                        :stroke-dasharray="`${match.match_score * 226} 226`"
                        :class="getMatchScoreColor(match.match_score)"
                      />
                    </svg>
                    <div class="absolute inset-0 flex items-center justify-center">
                      <span class="text-lg font-bold text-gray-900">
                        {{ (match.match_score * 100).toFixed(0) }}%
                      </span>
                    </div>
                  </div>
                </div>

                <!-- Content -->
                <div class="flex-1 min-w-0">
                  <div class="flex items-start justify-between gap-4 mb-3">
                    <div>
                      <h3 class="text-lg font-semibold text-gray-900 group-hover:text-teal-600 transition-colors mb-1">
                        {{ match.policy_title }}
                      </h3>
                      <span
                        :class="[
                          'px-2 py-1 rounded text-xs font-medium text-white',
                          getMatchScoreColor(match.match_score)
                        ]"
                      >
                        {{ getMatchScoreLabel(match.match_score) }}
                      </span>
                    </div>

                    <ArrowRight
                      :size="20"
                      class="text-gray-300 group-hover:text-teal-600 transition-colors flex-shrink-0"
                    />
                  </div>

                  <!-- Match Reasons -->
                  <div v-if="match.match_reasons && match.match_reasons.length > 0" class="mb-3">
                    <div class="flex flex-wrap gap-2">
                      <span
                        v-for="reason in match.match_reasons.slice(0, 4)"
                        :key="reason"
                        class="px-2 py-1 bg-white rounded-lg text-xs text-gray-600 border border-gray-200"
                      >
                        {{ reason }}
                      </span>
                    </div>
                  </div>

                  <!-- Quick Info -->
                  <div class="flex items-center gap-4 text-xs text-gray-500">
                    <span class="flex items-center gap-1">
                      <Eye :size="12" />
                      查看详情
                    </span>
                  </div>

                  <!-- LLM详细分析结果 -->
                  <div v-if="getDetailedMatch(match.policy_id)" class="mt-4 p-4 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-xl border border-purple-200">
                    <div class="flex items-center gap-2 mb-3">
                      <Brain :size="16" class="text-purple-600" />
                      <span class="text-sm font-semibold text-purple-900">LLM智能分析</span>
                    </div>

                    <!-- 详细分数展示 -->
                    <div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
                      <div class="bg-white rounded-lg p-2 border border-purple-100">
                        <div class="text-xs text-gray-500 mb-1">语义匹配</div>
                        <div class="flex items-center gap-2">
                          <div class="flex-1 bg-gray-200 rounded-full h-2 overflow-hidden">
                            <div
                              class="bg-purple-600 h-full rounded-full transition-all"
                              :style="{ width: `${(getDetailedMatch(match.policy_id)?.semantic_score || 0) * 100}%` }"
                            ></div>
                          </div>
                          <span class="text-xs font-semibold text-purple-700">
                            {{ ((getDetailedMatch(match.policy_id)?.semantic_score || 0) * 100).toFixed(0) }}%
                          </span>
                        </div>
                      </div>

                      <div class="bg-white rounded-lg p-2 border border-purple-100">
                        <div class="text-xs text-gray-500 mb-1">行业匹配</div>
                        <div class="flex items-center gap-2">
                          <div class="flex-1 bg-gray-200 rounded-full h-2 overflow-hidden">
                            <div
                              class="bg-blue-600 h-full rounded-full transition-all"
                              :style="{ width: `${(getDetailedMatch(match.policy_id)?.industry_score || 0) * 100}%` }"
                            ></div>
                          </div>
                          <span class="text-xs font-semibold text-blue-700">
                            {{ ((getDetailedMatch(match.policy_id)?.industry_score || 0) * 100).toFixed(0) }}%
                          </span>
                        </div>
                      </div>

                      <div class="bg-white rounded-lg p-2 border border-purple-100">
                        <div class="text-xs text-gray-500 mb-1">地区匹配</div>
                        <div class="flex items-center gap-2">
                          <div class="flex-1 bg-gray-200 rounded-full h-2 overflow-hidden">
                            <div
                              class="bg-emerald-600 h-full rounded-full transition-all"
                              :style="{ width: `${(getDetailedMatch(match.policy_id)?.region_score || 0) * 100}%` }"
                            ></div>
                          </div>
                          <span class="text-xs font-semibold text-emerald-700">
                            {{ ((getDetailedMatch(match.policy_id)?.region_score || 0) * 100).toFixed(0) }}%
                          </span>
                        </div>
                      </div>

                      <div class="bg-white rounded-lg p-2 border border-purple-100">
                        <div class="text-xs text-gray-500 mb-1">规模匹配</div>
                        <div class="flex items-center gap-2">
                          <div class="flex-1 bg-gray-200 rounded-full h-2 overflow-hidden">
                            <div
                              class="bg-amber-600 h-full rounded-full transition-all"
                              :style="{ width: `${(getDetailedMatch(match.policy_id)?.scale_score || 0) * 100}%` }"
                            ></div>
                          </div>
                          <span class="text-xs font-semibold text-amber-700">
                            {{ ((getDetailedMatch(match.policy_id)?.scale_score || 0) * 100).toFixed(0) }}%
                          </span>
                        </div>
                      </div>

                      <div class="bg-white rounded-lg p-2 border border-purple-100">
                        <div class="text-xs text-gray-500 mb-1">税种匹配</div>
                        <div class="flex items-center gap-2">
                          <div class="flex-1 bg-gray-200 rounded-full h-2 overflow-hidden">
                            <div
                              class="bg-teal-600 h-full rounded-full transition-all"
                              :style="{ width: `${(getDetailedMatch(match.policy_id)?.tax_type_score || 0) * 100}%` }"
                            ></div>
                          </div>
                          <span class="text-xs font-semibold text-teal-700">
                            {{ ((getDetailedMatch(match.policy_id)?.tax_type_score || 0) * 100).toFixed(0) }}%
                          </span>
                        </div>
                      </div>

                      <div class="bg-white rounded-lg p-2 border border-purple-100">
                        <div class="text-xs text-gray-500 mb-1">紧急程度</div>
                        <div class="flex items-center gap-2">
                          <div class="flex-1 bg-gray-200 rounded-full h-2 overflow-hidden">
                            <div
                              class="bg-red-600 h-full rounded-full transition-all"
                              :style="{ width: `${(getDetailedMatch(match.policy_id)?.urgency_score || 0) * 100}%` }"
                            ></div>
                          </div>
                          <span class="text-xs font-semibold text-red-700">
                            {{ ((getDetailedMatch(match.policy_id)?.urgency_score || 0) * 100).toFixed(0) }}%
                          </span>
                        </div>
                      </div>
                    </div>

                    <!-- LLM匹配原因 -->
                    <div v-if="getDetailedMatch(match.policy_id)?.reasons?.length > 0">
                      <div class="text-xs font-medium text-purple-900 mb-2">智能分析理由：</div>
                      <div class="space-y-1">
                        <div
                          v-for="(reason, idx) in getDetailedMatch(match.policy_id)?.reasons"
                          :key="idx"
                          class="flex items-start gap-2 text-xs text-purple-800"
                        >
                          <Zap :size="12" class="text-purple-600 mt-0.5 flex-shrink-0" />
                          <span>{{ reason }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else class="bg-white rounded-2xl p-12 shadow-sm border border-gray-100 text-center">
          <div class="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Target :size="40" class="text-gray-400" />
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">暂无匹配结果</h3>
          <p class="text-sm text-gray-500 mb-6">
            系统正在分析您的企业画像并匹配相关政策，请稍后再试
          </p>
          <button
            @click="refreshMatches"
            :disabled="isRefreshing"
            class="px-6 py-3 bg-teal-600 text-white rounded-xl hover:bg-teal-700 transition-all disabled:opacity-50 inline-flex items-center gap-2"
          >
            <RefreshCw :size="16" :class="{ 'animate-spin': isRefreshing }" />
            立即匹配
          </button>
        </div>

        <!-- Tips -->
        <div class="bg-gradient-to-r from-teal-50 to-emerald-50 rounded-2xl p-6 border border-teal-100">
          <div class="flex items-start gap-3">
            <div class="w-10 h-10 bg-teal-100 rounded-xl flex items-center justify-center">
              <Sparkles :size="20" class="text-teal-600" />
            </div>
            <div>
              <h4 class="text-sm font-semibold text-teal-900 mb-1">匹配说明</h4>
              <p class="text-xs text-teal-700 leading-relaxed">
                系统会根据企业的行业、地区、税种、企业规模等特征，自动匹配合适的政策。
                匹配度越高，表示政策与企业越相关。您可以点击查看政策详情，了解政策的完整内容和适用条件。
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
