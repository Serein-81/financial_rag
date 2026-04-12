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
  Sparkles
} from 'lucide-vue-next'

const router = useRouter()

const isLoading = ref(false)
const isRefreshing = ref(false)
const matches = ref<PolicyMatchResult[]>([])
const selectedMatch = ref<PolicyMatchResult | null>(null)

const statistics = computed(() => ({
  total: matches.value.length,
  highMatch: matches.value.filter(m => m.match_score >= 0.8).length,
  mediumMatch: matches.value.filter(m => m.match_score >= 0.6 && m.match_score < 0.8).length,
  lowMatch: matches.value.filter(m => m.match_score < 0.6).length
}))

onMounted(async () => {
  await loadMatches()
})

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
