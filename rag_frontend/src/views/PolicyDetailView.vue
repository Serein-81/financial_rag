<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { policyApi, type Policy } from '@/api/policy'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  Building2,
  MapPin,
  Scale,
  DollarSign,
  Calendar,
  Clock,
  Eye,
  ExternalLink,
  Copy,
  CheckCircle,
  Archive,
  AlertCircle,
  FileWarning,
  TrendingUp,
  Loader2,
  Tag,
  Share2,
  Bookmark,
  FileText
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const policy = ref<Policy | null>(null)
const isLoading = ref(true)
const copied = ref(false)

const filterOptions = {
  status: [
    { value: 'active', label: '有效', icon: CheckCircle, color: 'bg-emerald-500' },
    { value: 'archived', label: '已归档', icon: Archive, color: 'bg-gray-400' },
    { value: 'draft', label: '草稿', icon: FileWarning, color: 'bg-amber-500' },
    { value: 'expired', label: '已过期', icon: AlertCircle, color: 'bg-red-500' }
  ],
  priority: [
    { value: 'critical', label: '紧急重要', color: 'bg-red-500 text-white' },
    { value: 'high', label: '高优先级', color: 'bg-orange-500 text-white' },
    { value: 'medium', label: '中优先级', color: 'bg-blue-500 text-white' },
    { value: 'low', label: '低优先级', color: 'bg-gray-400 text-white' }
  ]
}

onMounted(async () => {
  await fetchPolicyDetail()
})

async function fetchPolicyDetail() {
  const policyId = route.params.id as string

  if (!policyId) {
    ElMessage.error('政策ID不能为空')
    router.push('/policy')
    return
  }

  isLoading.value = true
  try {
    policy.value = await policyApi.getPolicy(policyId)
  } catch (error: any) {
    ElMessage.error('获取政策详情失败')
    console.error('Failed to fetch policy detail:', error)
    router.push('/policy')
  } finally {
    isLoading.value = false
  }
}

function goBack() {
  router.push('/policy')
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
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

function copyContent() {
  if (!policy.value) return

  navigator.clipboard.writeText(policy.value.content).then(() => {
    copied.value = true
    ElMessage.success('内容已复制到剪贴板')
    setTimeout(() => {
      copied.value = false
    }, 2000)
  })
}

function openSourceUrl() {
  if (!policy.value?.source_url) return
  window.open(policy.value.source_url, '_blank')
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-slate-100 via-blue-50/30 to-indigo-50/30 h-full">
    <!-- Top Bar -->
    <div class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
      <div class="flex items-center gap-3">
        <button
          @click="goBack"
          class="p-2 rounded-xl hover:bg-gray-100 transition-all"
        >
          <ArrowLeft :size="20" class="text-gray-600" />
        </button>
        <div class="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center">
          <FileText :size="20" class="text-white" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-gray-900">政策详情</h2>
          <p class="text-xs text-gray-500">查看政策详细信息</p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button
          @click="copyContent"
          class="px-4 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-all flex items-center gap-2"
        >
          <CheckCircle v-if="copied" :size="16" class="text-emerald-500" />
          <Copy v-else :size="16" />
          {{ copied ? '已复制' : '复制内容' }}
        </button>

        <button
          v-if="policy?.source_url"
          @click="openSourceUrl"
          class="px-4 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-all flex items-center gap-2"
        >
          <ExternalLink :size="16" />
          查看原文
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 overflow-y-auto p-6">
      <!-- Loading State -->
      <div v-if="isLoading" class="flex items-center justify-center py-20">
        <div class="text-center">
          <Loader2 :size="40" class="animate-spin text-blue-600 mx-auto mb-3" />
          <p class="text-sm text-gray-500">加载中...</p>
        </div>
      </div>

      <!-- Policy Detail -->
      <div v-else-if="policy" class="max-w-5xl mx-auto">
        <!-- Header -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 mb-6">
          <div class="flex items-start justify-between gap-4 mb-6">
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-3">
                <span
                  :class="[
                    'px-3 py-1 rounded-lg text-sm font-medium',
                    getPriorityConfig(policy.priority).color
                  ]"
                >
                  {{ getPriorityConfig(policy.priority).label }}
                </span>
                <span
                  class="px-3 py-1 rounded-lg text-sm font-medium text-white flex items-center gap-1"
                  :class="getStatusConfig(policy.status).color"
                >
                  <component :is="getStatusConfig(policy.status).icon" :size="14" />
                  {{ getStatusConfig(policy.status).label }}
                </span>
              </div>

              <h1 class="text-2xl font-bold text-gray-900 mb-4">
                {{ policy.title }}
              </h1>

              <div class="flex items-center gap-6 text-sm text-gray-500">
                <span class="flex items-center gap-1">
                  <Building2 :size="14" />
                  {{ policy.source_name }}
                </span>
                <span class="flex items-center gap-1">
                  <Calendar :size="14" />
                  {{ formatDate(policy.published_date) }}
                </span>
                <span class="flex items-center gap-1">
                  <Eye :size="14" />
                  {{ policy.view_count }} 次浏览
                </span>
              </div>
            </div>
          </div>

          <!-- Metadata Grid -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 p-6 bg-gray-50 rounded-xl">
            <div>
              <h3 class="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1">
                <Building2 :size="12" />
                适用行业
              </h3>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="industry in policy.industries"
                  :key="industry"
                  class="px-3 py-1 bg-white rounded-lg text-sm text-gray-700 border border-gray-200"
                >
                  {{ industry }}
                </span>
                <span v-if="policy.industries.length === 0" class="text-sm text-gray-400">通用</span>
              </div>
            </div>

            <div>
              <h3 class="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1">
                <MapPin :size="12" />
                适用地区
              </h3>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="region in policy.regions"
                  :key="region"
                  class="px-3 py-1 bg-white rounded-lg text-sm text-gray-700 border border-gray-200"
                >
                  {{ region }}
                </span>
                <span v-if="policy.regions.length === 0" class="text-sm text-gray-400">全国</span>
              </div>
            </div>

            <div>
              <h3 class="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1">
                <DollarSign :size="12" />
                涉及税种
              </h3>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="taxType in policy.tax_types"
                  :key="taxType"
                  class="px-3 py-1 bg-white rounded-lg text-sm text-gray-700 border border-gray-200"
                >
                  {{ taxType }}
                </span>
                <span v-if="policy.tax_types.length === 0" class="text-sm text-gray-400">未分类</span>
              </div>
            </div>

            <div>
              <h3 class="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1">
                <Scale :size="12" />
                企业规模
              </h3>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="scale in policy.scales"
                  :key="scale"
                  class="px-3 py-1 bg-white rounded-lg text-sm text-gray-700 border border-gray-200"
                >
                  {{ scale }}
                </span>
                <span v-if="policy.scales.length === 0" class="text-sm text-gray-400">所有规模</span>
              </div>
            </div>
          </div>

          <!-- Tags -->
          <div v-if="policy.tags && policy.tags.length > 0" class="mt-6">
            <h3 class="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1">
              <Tag :size="12" />
              标签
            </h3>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="tag in policy.tags"
                :key="tag"
                class="px-3 py-1 bg-blue-50 text-blue-700 rounded-lg text-sm"
              >
                {{ tag }}
              </span>
            </div>
          </div>
        </div>

        <!-- Summary -->
        <div v-if="policy.summary" class="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 mb-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">政策摘要</h2>
          <div class="p-4 bg-blue-50 rounded-xl border border-blue-100">
            <p class="text-gray-700 leading-relaxed">{{ policy.summary }}</p>
          </div>
        </div>

        <!-- Dates -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 mb-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">重要日期</h2>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="p-4 bg-gray-50 rounded-xl">
              <p class="text-xs text-gray-500 mb-1">发布日期</p>
              <p class="text-sm font-medium text-gray-900">{{ formatDate(policy.published_date) }}</p>
            </div>
            <div class="p-4 bg-gray-50 rounded-xl">
              <p class="text-xs text-gray-500 mb-1">生效日期</p>
              <p class="text-sm font-medium text-gray-900">{{ formatDate(policy.effective_date) }}</p>
            </div>
            <div class="p-4 bg-gray-50 rounded-xl">
              <p class="text-xs text-gray-500 mb-1">失效日期</p>
              <p class="text-sm font-medium text-gray-900">{{ formatDate(policy.expiry_date) }}</p>
            </div>
          </div>
        </div>

        <!-- Content -->
        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">政策正文</h2>
          <div class="prose prose-blue max-w-none">
            <div class="p-6 bg-gray-50 rounded-xl whitespace-pre-wrap text-gray-700 leading-relaxed">
              {{ policy.content }}
            </div>
          </div>
        </div>

        <!-- Footer Info -->
        <div class="mt-6 text-center text-xs text-gray-400">
          <p>政策编号: {{ policy.policy_id }} | 版本: {{ policy.version }}</p>
          <p class="mt-1">最后更新: {{ formatDate(policy.updated_at) }}</p>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-20">
        <div class="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <FileText :size="40" class="text-gray-400" />
        </div>
        <h3 class="text-lg font-semibold text-gray-900 mb-2">政策不存在</h3>
        <p class="text-sm text-gray-500">该政策可能已被删除或转移</p>
        <button
          @click="goBack"
          class="mt-4 px-6 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all"
        >
          返回政策列表
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.prose {
  max-width: 100%;
}
</style>
