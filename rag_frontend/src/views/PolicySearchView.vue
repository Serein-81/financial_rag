<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { policyApi, type Policy, type PolicyMatchResult } from '@/api/policy'
import { tenantSettingsApi, type TenantSettings } from '@/api/tenant-settings'
import { getEnterpriseId } from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import {
  Search,
  Sparkles,
  FileText,
  Loader2,
  Building2,
  MapPin,
  Scale,
  DollarSign,
  TrendingUp,
  CheckCircle,
  ArrowRight,
  Target,
  Brain,
  Bell,
  Star,
  Filter,
  X,
  Cpu,
  Lightbulb,
  Wand2
} from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

const searchQuery = ref('')
const isSearching = ref(false)
const searchResults = ref<PolicyMatchResult[]>([])
const recommendations = ref<PolicyMatchResult[]>([])
const isLoadingRecommendations = ref(false)
const tenantSettings = ref<TenantSettings | null>(null)

// PolicyNotificationAgent 状态
const agentStatus = ref<any>(null)
const isCheckingAgent = ref(false)
const searchSuggestions = ref<string[]>([])
const isGeneratingSuggestions = ref(false)

// 语义相似度详情
const semanticDetails = ref<Map<string, any>>(new Map())
const isLoadingDetails = ref(false)

const showFilters = ref(false)
const filters = ref({
  industries: [] as string[],
  regions: [] as string[],
  tax_types: [] as string[],
  scales: [] as string[]
})

const filterOptions = {
  industries: ['制造业', '科技', '金融', '房地产', '零售', '医疗', '教育', '能源'],
  regions: ['全国', '北京', '上海', '广州', '深圳', '浙江', '江苏', '广东', '四川', '湖北'],
  tax_types: ['增值税', '企业所得税', '个人所得税', '消费税', '关税', '印花税', '土地增值税'],
  scales: ['大型企业', '中型企业', '小型企业', '微型企业']
}

onMounted(async () => {
  await loadTenantSettings()
  await Promise.all([
    loadRecommendations(),
    checkAgentStatus()
  ])
})

async function loadTenantSettings() {
  try {
    tenantSettings.value = await tenantSettingsApi.getMySettings()
  } catch (error) {
    console.warn('Failed to load tenant settings:', error)
  }
}

function getEnterpriseProfile(enterpriseId: string) {
  return {
    enterprise_id: enterpriseId,
    enterprise_name: tenantSettings.value?.company_name || '企业',
    industry: tenantSettings.value?.industry || '通用',
    region: tenantSettings.value?.region || '全国',
    scale: tenantSettings.value?.scale || '中型企业',
    tax_types: tenantSettings.value?.tax_types || [],
    qualifications: []
  }
}

async function checkAgentStatus() {
  isCheckingAgent.value = true
  try {
    agentStatus.value = await policyApi.getPolicyAgentStatus()
    if (agentStatus.value?.use_llm) {
      await generateSearchSuggestions()
    }
  } catch (error: any) {
    console.error('Failed to check agent status:', error)
    agentStatus.value = null
  } finally {
    isCheckingAgent.value = false
  }
}

async function generateSearchSuggestions() {
  if (!agentStatus.value?.use_llm) {
    return
  }

  isGeneratingSuggestions.value = true
  try {
    const enterpriseId = getEnterpriseId() || 'default'

    const policies = recommendations.value.slice(0, 3).map(r => ({
      policy_id: r.policy_id,
      title: r.policy_title,
      content: r.policy?.content || ''
    }))

    if (policies.length > 0) {
      const request = {
        policies: policies,
        enterprise_profile: getEnterpriseProfile(enterpriseId)
      }

      const result = await policyApi.prioritizePolicies(request)
      if (result && result.length > 0) {
        searchSuggestions.value = result.slice(0, 5).map((r: any) =>
          `推荐：${r.policy_title} - 优先级提升原因：${r.reason || '高度匹配您的企业画像'}`
        )
      }
    }
  } catch (error: any) {
    console.error('Failed to generate search suggestions:', error)
    searchSuggestions.value = []
  } finally {
    isGeneratingSuggestions.value = false
  }
}

async function loadSemanticDetails(policyId: string, policy: any) {
  if (!agentStatus.value?.use_llm || semanticDetails.value.has(policyId)) {
    return
  }

  const enterpriseId = getEnterpriseId() || 'default'

  try {
    const matchRequest = {
      policy: {
        policy_id: policyId,
        title: policy.title,
        content: policy.content || '',
        source: 'policy_center'
      },
      enterprise: getEnterpriseProfile(enterpriseId),
      use_llm: true
    }

    const result = await policyApi.matchPolicyWithEnterprise(matchRequest)
    semanticDetails.value.set(policyId, result)
  } catch (error: any) {
    console.error('Failed to load semantic details:', error)
  }
}

function getSemanticDetails(policyId: string) {
  return semanticDetails.value.get(policyId)
}

async function loadRecommendations() {
  const enterpriseId = getEnterpriseId()

  isLoadingRecommendations.value = true
  try {
    recommendations.value = await policyApi.getPolicyRecommendations(enterpriseId, 10)
  } catch (error: any) {
    console.error('Failed to load recommendations:', error)
    recommendations.value = []
  } finally {
    isLoadingRecommendations.value = false
  }
}

async function handleSearch() {
  if (!searchQuery.value.trim()) return

  isSearching.value = true
  searchResults.value = []

  try {
    const params = {
      query: searchQuery.value,
      industries: filters.value.industries.length > 0 ? filters.value.industries : undefined,
      regions: filters.value.regions.length > 0 ? filters.value.regions : undefined,
      tax_types: filters.value.tax_types.length > 0 ? filters.value.tax_types : undefined,
      scales: filters.value.scales.length > 0 ? filters.value.scales : undefined
    }

    const results = await policyApi.searchPolicies(params)
    searchResults.value = results.map(r => ({
      policy_id: r.policy.id,
      policy_title: r.policy.title,
      match_score: r.score,
      match_reasons: [],
      policy: r.policy
    }))
  } catch (error: any) {
    ElMessage.error('搜索失败，请重试')
    console.error('Search failed:', error)
  } finally {
    isSearching.value = false
  }
}

function viewPolicyDetail(policyId: string) {
  router.push(`/policy/${policyId}`)
}

function getMatchScoreColor(score: number) {
  if (score >= 0.8) return 'text-emerald-600 bg-emerald-50'
  if (score >= 0.6) return 'text-blue-600 bg-blue-50'
  if (score >= 0.4) return 'text-amber-600 bg-amber-50'
  return 'text-gray-600 bg-gray-50'
}

function getMatchScoreLabel(score: number) {
  if (score >= 0.8) return '高度匹配'
  if (score >= 0.6) return '良好匹配'
  if (score >= 0.4) return '一般匹配'
  return '低匹配'
}

function formatMatchReasons(reasons: string[]) {
  return reasons.length > 0 ? reasons : ['基于语义相似度匹配']
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-slate-100 via-blue-50/30 to-indigo-50/30 h-full">
    <!-- Top Bar -->
    <div class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-gradient-to-br from-purple-600 to-pink-600 rounded-xl flex items-center justify-center">
          <Brain :size="20" class="text-white" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-gray-900">智能政策匹配</h2>
          <p class="text-xs text-gray-500">AI驱动的政策搜索与推荐</p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <!-- Agent Status -->
        <div v-if="agentStatus" class="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border border-purple-200">
          <Brain :size="16" class="text-purple-600" />
          <span class="text-xs font-medium text-purple-700">
            {{ agentStatus.use_llm ? 'LLM智能搜索' : '规则搜索' }}
          </span>
          <span v-if="agentStatus.llm_provider" class="text-xs text-purple-500">
            ({{ agentStatus.llm_provider }})
          </span>
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
        </button>
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
        <div class="max-w-6xl mx-auto">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-gray-700">搜索筛选条件</h3>
            <button
              v-if="filters.industries.length || filters.regions.length || filters.tax_types.length || filters.scales.length"
              @click="filters = { industries: [], regions: [], tax_types: [], scales: [] }"
              class="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
            >
              <X :size="14" />
              清除筛选
            </button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
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
                    filters.industries = filters.industries.includes(industry)
                      ? filters.industries.filter(i => i !== industry)
                      : [...filters.industries, industry]
                  "
                  :class="[
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                    filters.industries.includes(industry)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  ]"
                >
                  {{ industry }}
                </button>
              </div>
            </div>

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
                    filters.regions = filters.regions.includes(region)
                      ? filters.regions.filter(r => r !== region)
                      : [...filters.regions, region]
                  "
                  :class="[
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                    filters.regions.includes(region)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  ]"
                >
                  {{ region }}
                </button>
              </div>
            </div>

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
                    filters.tax_types = filters.tax_types.includes(taxType)
                      ? filters.tax_types.filter(t => t !== taxType)
                      : [...filters.tax_types, taxType]
                  "
                  :class="[
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                    filters.tax_types.includes(taxType)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  ]"
                >
                  {{ taxType }}
                </button>
              </div>
            </div>

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
                    filters.scales = filters.scales.includes(scale)
                      ? filters.scales.filter(s => s !== scale)
                      : [...filters.scales, scale]
                  "
                  :class="[
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                    filters.scales.includes(scale)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  ]"
                >
                  {{ scale }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Main Content -->
    <div class="flex-1 overflow-y-auto p-6">
      <div class="max-w-6xl mx-auto space-y-8">
        <!-- Search Box -->
        <div class="bg-white rounded-2xl shadow-xl p-8">
          <div class="flex gap-3 mb-4">
            <div class="flex-1 relative">
              <input
                v-model="searchQuery"
                type="text"
                placeholder="输入您想了解的政策内容..."
                class="w-full pl-12 pr-4 py-4 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:bg-white focus:border-purple-500 focus:ring-2 focus:ring-purple-200 transition-all outline-none text-lg"
                @keydown.enter="handleSearch"
              />
              <Brain :size="20" class="absolute left-4 top-1/2 -translate-y-1/2 text-purple-400" />
            </div>
            <button
              @click="handleSearch"
              :disabled="isSearching || !searchQuery.trim()"
              class="px-8 py-4 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-xl hover:from-purple-700 hover:to-pink-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl flex items-center gap-3 font-medium"
            >
              <Search :size="20" v-if="!isSearching" />
              <Loader2 :size="20" class="animate-spin" v-else />
              智能搜索
            </button>
          </div>

          <div class="flex items-center gap-2 text-xs text-gray-500 mb-4">
            <Sparkles :size="14" class="text-purple-500" />
            <span>基于语义理解和向量检索的智能搜索</span>
          </div>

          <!-- LLM Search Suggestions -->
          <div v-if="searchSuggestions.length > 0" class="mt-4 p-4 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-xl border border-purple-200">
            <div class="flex items-center gap-2 mb-3">
              <Lightbulb :size="16" class="text-purple-600" />
              <span class="text-sm font-semibold text-purple-900">智能搜索建议</span>
              <span v-if="isGeneratingSuggestions" class="text-xs text-purple-600 flex items-center gap-1">
                <Loader2 :size="12" class="animate-spin" />
                生成中...
              </span>
            </div>
            <div class="space-y-2">
              <div
                v-for="(suggestion, idx) in searchSuggestions.slice(0, 3)"
                :key="idx"
                @click="searchQuery = suggestion.split(' - ')[0].replace('推荐：', ''); handleSearch()"
                class="p-3 bg-white rounded-lg border border-purple-100 hover:border-purple-300 cursor-pointer transition-all group"
              >
                <div class="flex items-start gap-2">
                  <Wand2 :size="14" class="text-purple-600 mt-0.5 flex-shrink-0" />
                  <span class="text-xs text-gray-700 group-hover:text-purple-700">{{ suggestion }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Search Results -->
        <div v-if="searchResults.length > 0">
          <div class="flex items-center gap-2 mb-4">
            <h3 class="text-lg font-semibold text-gray-900">搜索结果</h3>
            <span class="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">
              {{ searchResults.length }} 条
            </span>
          </div>

          <div class="space-y-4">
            <div
              v-for="result in searchResults"
              :key="result.policy_id"
              @click="viewPolicyDetail(result.policy_id)"
              class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-lg hover:border-purple-200 transition-all cursor-pointer group"
            >
              <div class="flex items-start justify-between gap-4">
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-2">
                    <span
                      :class="[
                        'px-3 py-1 rounded-lg text-xs font-medium',
                        getMatchScoreColor(result.match_score)
                      ]"
                    >
                      {{ (result.match_score * 100).toFixed(0) }}% {{ getMatchScoreLabel(result.match_score) }}
                    </span>
                  </div>

                  <h3 class="text-lg font-semibold text-gray-900 group-hover:text-purple-600 transition-colors mb-2">
                    {{ result.policy_title }}
                  </h3>

                  <p class="text-sm text-gray-600 line-clamp-2 mb-3">
                    {{ result.policy.summary || result.policy.content.substring(0, 150) + '...' }}
                  </p>

                  <div class="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                    <span class="flex items-center gap-1">
                      <Building2 :size="12" />
                      {{ result.policy.industries.slice(0, 2).join(', ') || '通用' }}
                    </span>
                    <span class="flex items-center gap-1">
                      <DollarSign :size="12" />
                      {{ result.policy.tax_types.slice(0, 2).join(', ') }}
                    </span>
                  </div>

                  <!-- LLM Semantic Details -->
                  <div v-if="agentStatus?.use_llm" class="mt-3">
                    <button
                      @click.stop="loadSemanticDetails(result.policy_id, result.policy)"
                      class="text-xs text-purple-600 hover:text-purple-700 flex items-center gap-1"
                    >
                      <Brain :size="12" />
                      {{ getSemanticDetails(result.policy_id) ? '查看语义分析' : '加载语义分析' }}
                    </button>

                    <div v-if="getSemanticDetails(result.policy_id)" class="mt-3 p-3 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border border-purple-200">
                      <div class="grid grid-cols-2 gap-2 mb-3">
                        <div class="bg-white rounded p-2 border border-purple-100">
                          <div class="text-xs text-gray-500 mb-1">语义匹配</div>
                          <div class="text-xs font-semibold text-purple-700">
                            {{ ((getSemanticDetails(result.policy_id)?.semantic_score || 0) * 100).toFixed(0) }}%
                          </div>
                        </div>
                        <div class="bg-white rounded p-2 border border-purple-100">
                          <div class="text-xs text-gray-500 mb-1">综合匹配</div>
                          <div class="text-xs font-semibold text-blue-700">
                            {{ ((getSemanticDetails(result.policy_id)?.match_score || 0) * 100).toFixed(0) }}%
                          </div>
                        </div>
                      </div>

                      <div v-if="getSemanticDetails(result.policy_id)?.reasons?.length > 0">
                        <div class="text-xs font-medium text-purple-900 mb-2">智能分析理由：</div>
                        <div class="space-y-1">
                          <div
                            v-for="(reason, idx) in getSemanticDetails(result.policy_id)?.reasons.slice(0, 3)"
                            :key="idx"
                            class="flex items-start gap-2 text-xs text-gray-700"
                          >
                            <Sparkles :size="10" class="text-purple-600 mt-0.5 flex-shrink-0" />
                            <span>{{ reason }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="flex flex-col items-end gap-2">
                  <ArrowRight :size="20" class="text-gray-300 group-hover:text-purple-600 transition-colors" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Recommended Policies -->
        <div v-if="searchResults.length === 0 && !isSearching">
          <div class="flex items-center gap-2 mb-4">
            <Star :size="20" class="text-amber-500" />
            <h3 class="text-lg font-semibold text-gray-900">为您推荐的政策</h3>
            <span class="px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs">
              个性化
            </span>
          </div>

          <!-- Loading State -->
          <div v-if="isLoadingRecommendations" class="flex items-center justify-center py-12">
            <div class="text-center">
              <Loader2 :size="40" class="animate-spin text-purple-600 mx-auto mb-3" />
              <p class="text-sm text-gray-500">正在分析您的企业画像...</p>
            </div>
          </div>

          <!-- Recommendations -->
          <div v-else-if="recommendations.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div
              v-for="(result, index) in recommendations"
              :key="result.policy_id"
              @click="viewPolicyDetail(result.policy_id)"
              class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-lg hover:border-amber-200 transition-all cursor-pointer group"
            >
              <div class="flex items-start gap-4">
                <div class="w-12 h-12 bg-gradient-to-br from-amber-400 to-orange-500 rounded-xl flex items-center justify-center text-white font-bold text-lg">
                  {{ index + 1 }}
                </div>

                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-2">
                    <span
                      :class="[
                        'px-2 py-0.5 rounded text-xs font-medium',
                        getMatchScoreColor(result.match_score)
                      ]"
                    >
                      {{ (result.match_score * 100).toFixed(0) }}% 匹配
                    </span>
                  </div>

                  <h3 class="text-base font-semibold text-gray-900 group-hover:text-amber-600 transition-colors mb-2 line-clamp-2">
                    {{ result.policy_title }}
                  </h3>

                  <div class="flex flex-wrap gap-2 text-xs text-gray-500 mb-2">
                    <span class="flex items-center gap-1">
                      <Building2 :size="10" />
                      {{ result.policy.industries[0] || '通用' }}
                    </span>
                    <span class="flex items-center gap-1">
                      <MapPin :size="10" />
                      {{ result.policy.regions[0] || '全国' }}
                    </span>
                  </div>

                  <div v-if="result.match_reasons && result.match_reasons.length > 0" class="flex flex-wrap gap-1">
                    <span
                      v-for="reason in result.match_reasons.slice(0, 3)"
                      :key="reason"
                      class="px-2 py-0.5 bg-amber-50 text-amber-700 rounded text-xs"
                    >
                      {{ reason }}
                    </span>
                  </div>

                  <!-- LLM Semantic Details for Recommendations -->
                  <div v-if="agentStatus?.use_llm" class="mt-3">
                    <button
                      @click.stop="loadSemanticDetails(result.policy_id, result.policy)"
                      class="text-xs text-amber-600 hover:text-amber-700 flex items-center gap-1"
                    >
                      <Brain :size="12" />
                      {{ getSemanticDetails(result.policy_id) ? '查看智能分析' : '加载智能分析' }}
                    </button>

                    <div v-if="getSemanticDetails(result.policy_id)" class="mt-3 p-3 bg-gradient-to-r from-amber-50 to-orange-50 rounded-lg border border-amber-200">
                      <div class="text-xs font-medium text-amber-900 mb-2">智能分析理由：</div>
                      <div class="space-y-1">
                        <div
                          v-for="(reason, idx) in getSemanticDetails(result.policy_id)?.reasons.slice(0, 3)"
                          :key="idx"
                          class="flex items-start gap-2 text-xs text-gray-700"
                        >
                          <Sparkles :size="10" class="text-amber-600 mt-0.5 flex-shrink-0" />
                          <span>{{ reason }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Empty State -->
          <div v-else class="text-center py-12">
            <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Target :size="32" class="text-gray-400" />
            </div>
            <h3 class="text-base font-semibold text-gray-900 mb-2">暂无推荐</h3>
            <p class="text-sm text-gray-500">系统正在学习您的偏好，请先进行搜索</p>
          </div>
        </div>

        <!-- Tips -->
        <div class="bg-gradient-to-r from-purple-50 to-pink-50 rounded-2xl p-6 border border-purple-100">
          <div class="flex items-start gap-3">
            <div class="w-10 h-10 bg-purple-100 rounded-xl flex items-center justify-center">
              <Sparkles :size="20" class="text-purple-600" />
            </div>
            <div>
              <h4 class="text-sm font-semibold text-purple-900 mb-1">智能匹配说明</h4>
              <p class="text-xs text-purple-700 leading-relaxed">
                我们的AI系统会根据您的企业画像（行业、地区、税种、企业规模等）自动匹配合适的政策。
                您也可以通过语义搜索查找感兴趣的政策内容，系统会基于政策内容的相关性进行排序。
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
