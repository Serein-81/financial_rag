<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { policyApi, type PolicyNotification } from '@/api/policy'
import { policyTrackingApi } from '@/api/policy-tracking'
import { getEnterpriseId, isAuthenticated } from '@/utils/request'
import { ElMessage } from 'element-plus'
import {
  Bell,
  Loader2,
  CheckCircle,
  AlertCircle,
  Eye,
  Trash2,
  Sparkles,
  Target,
  Calendar,
  ArrowRight,
  Filter,
  Settings,
  X,
  Building2,
  Tag,
  Mail
} from 'lucide-vue-next'

const router = useRouter()

const isLoading = ref(false)
const notifications = ref<PolicyNotification[]>([])
const filterStatus = ref<string>('all')
const selectedNotifications = ref<Set<string>>(new Set())
const showEnterpriseProfile = ref(false)
const showSubscriptionManagement = ref(false)
const showPushConfig = ref(false)

const enterpriseProfile = ref({
  industry: '',
  region: '',
  company_size: '',
  business_scope: [] as string[],
  funding_stage: ''
})

const subscriptionCategories = ref([
  { id: 'tax', name: '税收优惠', checked: true, icon: '💰' },
  { id: 'subsidy', name: '政府补贴', checked: true, icon: '🏛️' },
  { id: 'finance', name: '金融支持', checked: true, icon: '🏦' },
  { id: 'talent', name: '人才政策', checked: false, icon: '👥' },
  { id: 'technology', name: '科技创新', checked: true, icon: '🔬' },
  { id: 'environmental', name: '环保政策', checked: false, icon: '🌿' }
])

const pushConfig = ref({
  email: true,
  sms: false,
  in_app: true,
  frequency: 'realtime',
  severity_threshold: 0.6
})

const statistics = computed(() => ({
  total: notifications.value.length,
  pending: notifications.value.filter(n => n.status === 'pending').length,
  acknowledged: notifications.value.filter(n => n.status === 'acknowledged').length,
  dismissed: notifications.value.filter(n => n.status === 'dismissed').length
}))

const filteredNotifications = computed(() => {
  if (filterStatus.value === 'all') {
    return notifications.value
  }
  return notifications.value.filter(n => n.status === filterStatus.value)
})

onMounted(async () => {
  if (isAuthenticated()) {
    await Promise.all([
      loadNotifications(),
      loadSubscriptions()
    ])
  }
})

async function loadSubscriptions() {
  try {
    const response = await policyTrackingApi.getSubscriptions()
    if (response.subscriptions && response.subscriptions.length > 0) {
      const sub = response.subscriptions[0]
      enterpriseProfile.value = {
        industry: sub.industry,
        region: sub.region,
        company_size: sub.company_size,
        business_scope: sub.business_scope || [],
        funding_stage: sub.funding_stage
      }
      sub.categories?.forEach(cat => {
        const category = subscriptionCategories.value.find(c => c.id === cat)
        if (category) category.checked = true
      })
      if (sub.notification_methods) {
        pushConfig.value.email = sub.notification_methods.includes('email')
        pushConfig.value.sms = sub.notification_methods.includes('sms')
        pushConfig.value.in_app = sub.notification_methods.includes('in_app')
      }
      if (sub.severity_threshold) {
        pushConfig.value.severity_threshold = sub.severity_threshold
      }
    }
  } catch (error) {
    console.error('加载订阅配置失败:', error)
  }
}

async function loadNotifications() {
  let enterpriseId = getEnterpriseId()
  if (!enterpriseId || enterpriseId === 'undefined' || enterpriseId === 'default') {
    console.warn('EnterpriseId not available, using tenant fallback')
    enterpriseId = 'default'
  }

  isLoading.value = true
  try {
    const response = await policyApi.getNotifications(enterpriseId, undefined, 50)
    notifications.value = response?.notifications || []
  } catch (error: any) {
    console.warn('Failed to load notifications (may need subscription):', error)
    notifications.value = []
  } finally {
    isLoading.value = false
  }
}

async function acknowledgeNotification(notificationId: string) {
  try {
    await policyApi.acknowledgeNotification(notificationId)
    await loadNotifications()
    ElMessage.success('已确认通知')
  } catch (error: any) {
    ElMessage.error('确认失败')
    console.error('Failed to acknowledge:', error)
  }
}

async function dismissNotification(notificationId: string) {
  try {
    await policyApi.dismissNotification(notificationId, '用户手动忽略')
    await loadNotifications()
    ElMessage.success('已忽略通知')
  } catch (error: any) {
    ElMessage.error('忽略失败')
    console.error('Failed to dismiss:', error)
  }
}

function viewPolicyDetail(policyId: string) {
  router.push(`/policy/${policyId}`)
}

function getStatusConfig(status: string) {
  switch (status) {
    case 'pending':
      return { label: '待处理', color: 'bg-amber-500', textColor: 'text-amber-600', bgColor: 'bg-amber-50' }
    case 'sent':
      return { label: '已发送', color: 'bg-blue-500', textColor: 'text-blue-600', bgColor: 'bg-blue-50' }
    case 'acknowledged':
      return { label: '已确认', color: 'bg-emerald-500', textColor: 'text-emerald-600', bgColor: 'bg-emerald-50' }
    case 'dismissed':
      return { label: '已忽略', color: 'bg-gray-400', textColor: 'text-gray-500', bgColor: 'bg-gray-50' }
    case 'failed':
      return { label: '失败', color: 'bg-red-500', textColor: 'text-red-600', bgColor: 'bg-red-50' }
    default:
      return { label: '未知', color: 'bg-gray-400', textColor: 'text-gray-600', bgColor: 'bg-gray-50' }
  }
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

function getMatchScoreColor(score: number) {
  if (score >= 0.8) return 'text-emerald-600 bg-emerald-50'
  if (score >= 0.6) return 'text-blue-600 bg-blue-50'
  if (score >= 0.4) return 'text-amber-600 bg-amber-50'
  return 'text-gray-600 bg-gray-50'
}

async function saveEnterpriseProfile() {
  try {
    await policyTrackingApi.subscribe({
      ...enterpriseProfile.value,
      business_scope: subscriptionCategories.value.filter(c => c.checked).map(c => c.id),
      notification_methods: Object.entries({
        email: pushConfig.value.email,
        sms: pushConfig.value.sms,
        in_app: pushConfig.value.in_app
      }).filter(([, enabled]) => enabled).map(([method]) => method),
      severity_threshold: pushConfig.value.severity_threshold
    })
    ElMessage.success('企业画像已保存')
    showEnterpriseProfile.value = false
  } catch (error) {
    ElMessage.error('保存失败')
    console.error('保存企业画像失败:', error)
  }
}

async function saveSubscription() {
  try {
    const selectedCategories = subscriptionCategories.value.filter(c => c.checked).map(c => c.id)
    await policyTrackingApi.subscribe({
      categories: selectedCategories,
      notification_methods: Object.entries({
        email: pushConfig.value.email,
        sms: pushConfig.value.sms,
        in_app: pushConfig.value.in_app
      }).filter(([, enabled]) => enabled).map(([method]) => method),
      severity_threshold: pushConfig.value.severity_threshold
    })
    ElMessage.success('订阅配置已保存')
    showSubscriptionManagement.value = false
  } catch (error) {
    ElMessage.error('保存失败')
    console.error('保存订阅配置失败:', error)
  }
}

async function savePushConfiguration() {
  try {
    await policyTrackingApi.subscribe({
      notification_methods: Object.entries({
        email: pushConfig.value.email,
        sms: pushConfig.value.sms,
        in_app: pushConfig.value.in_app
      }).filter(([, enabled]) => enabled).map(([method]) => method),
      severity_threshold: pushConfig.value.severity_threshold
    })
    ElMessage.success('推送配置已保存')
    showPushConfig.value = false
  } catch (error) {
    ElMessage.error('保存失败')
    console.error('保存推送配置失败:', error)
  }
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-slate-100 via-blue-50/30 to-indigo-50/30 h-full">
    <!-- Top Bar -->
    <div class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-gradient-to-br from-amber-500 to-orange-500 rounded-xl flex items-center justify-center">
          <Bell :size="20" class="text-white" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-gray-900">政策通知</h2>
          <p class="text-xs text-gray-500">查看和管理政策匹配通知</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="showEnterpriseProfile = true"
          class="px-3 py-1.5 text-sm bg-white border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-1.5 transition-colors"
        >
          <Building2 :size="14" />
          企业画像
        </button>
        <button
          @click="showSubscriptionManagement = true"
          class="px-3 py-1.5 text-sm bg-white border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-1.5 transition-colors"
        >
          <Tag :size="14" />
          订阅管理
        </button>
        <button
          @click="showPushConfig = true"
          class="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-1.5 transition-colors"
        >
          <Settings :size="14" />
          推送设置
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 overflow-y-auto p-6">
      <div class="max-w-5xl mx-auto space-y-6">
        <!-- Statistics Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                <Bell :size="24" class="text-blue-600" />
              </div>
              <span class="px-2 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium">
                总计
              </span>
            </div>
            <h3 class="text-2xl font-bold text-gray-900 mb-1">{{ statistics.total }}</h3>
            <p class="text-xs text-gray-500">通知数量</p>
          </div>

          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center">
                <AlertCircle :size="24" class="text-amber-600" />
              </div>
              <span class="px-2 py-1 bg-amber-50 text-amber-700 rounded-lg text-xs font-medium">
                待处理
              </span>
            </div>
            <h3 class="text-2xl font-bold text-amber-600 mb-1">{{ statistics.pending }}</h3>
            <p class="text-xs text-gray-500">需要处理</p>
          </div>

          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center">
                <CheckCircle :size="24" class="text-emerald-600" />
              </div>
              <span class="px-2 py-1 bg-emerald-50 text-emerald-700 rounded-lg text-xs font-medium">
                已确认
              </span>
            </div>
            <h3 class="text-2xl font-bold text-emerald-600 mb-1">{{ statistics.acknowledged }}</h3>
            <p class="text-xs text-gray-500">已处理</p>
          </div>

          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center">
                <Trash2 :size="24" class="text-gray-500" />
              </div>
              <span class="px-2 py-1 bg-gray-50 text-gray-600 rounded-lg text-xs font-medium">
                已忽略
              </span>
            </div>
            <h3 class="text-2xl font-bold text-gray-500 mb-1">{{ statistics.dismissed }}</h3>
            <p class="text-xs text-gray-500">已忽略</p>
          </div>
        </div>

        <!-- Filter Tabs -->
        <div class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
          <div class="flex items-center gap-2">
            <button
              v-for="status in ['all', 'pending', 'acknowledged', 'dismissed']"
              :key="status"
              @click="filterStatus = status"
              :class="[
                'px-4 py-2 rounded-xl text-sm font-medium transition-all',
                filterStatus === status
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              ]"
            >
              {{ status === 'all' ? '全部' : status === 'pending' ? '待处理' : status === 'acknowledged' ? '已确认' : '已忽略' }}
            </button>
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="isLoading" class="flex items-center justify-center py-20">
          <div class="text-center">
            <Loader2 :size="40" class="animate-spin text-amber-600 mx-auto mb-3" />
            <p class="text-sm text-gray-500">正在加载通知...</p>
          </div>
        </div>

        <!-- Notification List -->
        <div v-else-if="filteredNotifications.length > 0" class="space-y-4">
          <div
            v-for="notification in filteredNotifications"
            :key="notification.id"
            :class="[
              'bg-white rounded-2xl p-6 shadow-sm border-2 transition-all',
              getStatusConfig(notification.status).bgColor + ' ' + 'border-gray-200'
            ]"
          >
            <div class="flex items-start gap-4">
              <!-- Icon -->
              <div class="flex-shrink-0">
                <div class="w-12 h-12 bg-gradient-to-br from-amber-400 to-orange-500 rounded-xl flex items-center justify-center">
                  <Sparkles :size="24" class="text-white" />
                </div>
              </div>

              <!-- Content -->
              <div class="flex-1 min-w-0">
                <div class="flex items-start justify-between gap-4 mb-2">
                  <div>
                    <h3 class="text-base font-semibold text-gray-900 mb-1">
                      {{ notification.policy_title }}
                    </h3>
                    <span
                      :class="[
                        'px-2 py-0.5 rounded text-xs font-medium',
                        getStatusConfig(notification.status).color + ' text-white'
                      ]"
                    >
                      {{ getStatusConfig(notification.status).label }}
                    </span>
                  </div>

                  <div class="flex items-center gap-2">
                    <span
                      :class="[
                        'px-2 py-1 rounded text-xs font-medium',
                        getMatchScoreColor(notification.match_score)
                      ]"
                    >
                      {{ (notification.match_score * 100).toFixed(0) }}% 匹配
                    </span>
                  </div>
                </div>

                <!-- Summary -->
                <p v-if="notification.policy_summary" class="text-sm text-gray-600 mb-3 line-clamp-2">
                  {{ notification.policy_summary }}
                </p>

                <!-- Match Reasons -->
                <div v-if="notification.match_reasons && notification.match_reasons.length > 0" class="mb-3">
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="reason in notification.match_reasons.slice(0, 3)"
                      :key="reason"
                      class="px-2 py-0.5 bg-white rounded text-xs text-gray-600 border border-gray-200"
                    >
                      {{ reason }}
                    </span>
                  </div>
                </div>

                <!-- Meta Info -->
                <div class="flex items-center justify-between gap-4">
                  <div class="flex items-center gap-4 text-xs text-gray-500">
                    <span class="flex items-center gap-1">
                      <Calendar :size="12" />
                      {{ formatDate(notification.created_at) }}
                    </span>
                  </div>

                  <!-- Actions -->
                  <div class="flex items-center gap-2">
                    <button
                      v-if="notification.status === 'pending' || notification.status === 'sent'"
                      @click="acknowledgeNotification(notification.id)"
                      class="px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-medium hover:bg-emerald-700 transition-all flex items-center gap-1"
                    >
                      <CheckCircle :size="12" />
                      确认
                    </button>

                    <button
                      v-if="notification.status === 'pending' || notification.status === 'sent'"
                      @click="dismissNotification(notification.id)"
                      class="px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg text-xs font-medium hover:bg-gray-300 transition-all flex items-center gap-1"
                    >
                      <Trash2 :size="12" />
                      忽略
                    </button>

                    <button
                      @click="viewPolicyDetail(notification.policy_id)"
                      class="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 transition-all flex items-center gap-1"
                    >
                      <Eye :size="12" />
                      查看详情
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else class="bg-white rounded-2xl p-12 shadow-sm border border-gray-100 text-center">
          <div class="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Bell :size="40" class="text-gray-400" />
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">暂无通知</h3>
          <p class="text-sm text-gray-500">
            当有新政策匹配时，您将在这里收到通知
          </p>
        </div>

        <!-- Tips -->
        <div class="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl p-6 border border-amber-100">
          <div class="flex items-start gap-3">
            <div class="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center">
              <Sparkles :size="20" class="text-amber-600" />
            </div>
            <div>
              <h4 class="text-sm font-semibold text-amber-900 mb-1">通知说明</h4>
              <p class="text-xs text-amber-700 leading-relaxed">
                系统会根据您的企业画像自动匹配相关政策，并通过此页面通知您。
                您可以确认感兴趣的政策、忽略不相关的政策，或者查看政策详情了解更多内容。
              </p>
            </div>
          </div>
        </div>

        <!-- Enterprise Profile Modal -->
        <div
          v-if="showEnterpriseProfile"
          class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          @click.self="showEnterpriseProfile = false"
        >
          <div class="bg-white rounded-xl w-full max-w-lg mx-4">
            <div class="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 class="font-semibold text-gray-900 flex items-center gap-2">
                <Building2 :size="18" />
                企业画像设置
              </h3>
              <button @click="showEnterpriseProfile = false" class="p-1 hover:bg-gray-100 rounded">
                <X :size="20" class="text-gray-500" />
              </button>
            </div>
            <div class="p-5 space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">所属行业</label>
                <select
                  v-model="enterpriseProfile.industry"
                  class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">请选择行业</option>
                  <option value="technology">科技/互联网</option>
                  <option value="manufacturing">制造业</option>
                  <option value="service">服务业</option>
                  <option value="finance">金融</option>
                  <option value="education">教育</option>
                  <option value="healthcare">医疗健康</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">所在地区</label>
                <input
                  v-model="enterpriseProfile.region"
                  type="text"
                  placeholder="如：北京市海淀区"
                  class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">企业规模</label>
                <select
                  v-model="enterpriseProfile.company_size"
                  class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">请选择规模</option>
                  <option value="micro">微型企业（1-9人）</option>
                  <option value="small">小型企业（10-99人）</option>
                  <option value="medium">中型企业（100-499人）</option>
                  <option value="large">大型企业（500人以上）</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">融资阶段</label>
                <select
                  v-model="enterpriseProfile.funding_stage"
                  class="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">请选择融资阶段</option>
                  <option value="seed">种子轮</option>
                  <option value="series_a">A轮</option>
                  <option value="series_b">B轮</option>
                  <option value="series_c">C轮及以上</option>
                  <option value="profit">已盈利</option>
                </select>
              </div>
            </div>
            <div class="px-5 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button
                @click="showEnterpriseProfile = false"
                class="px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                @click="saveEnterpriseProfile"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                保存配置
              </button>
            </div>
          </div>
        </div>

        <!-- Subscription Management Modal -->
        <div
          v-if="showSubscriptionManagement"
          class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          @click.self="showSubscriptionManagement = false"
        >
          <div class="bg-white rounded-xl w-full max-w-lg mx-4">
            <div class="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 class="font-semibold text-gray-900 flex items-center gap-2">
                <Tag :size="18" />
                订阅管理
              </h3>
              <button @click="showSubscriptionManagement = false" class="p-1 hover:bg-gray-100 rounded">
                <X :size="20" class="text-gray-500" />
              </button>
            </div>
            <div class="p-5 space-y-3">
              <p class="text-sm text-gray-600 mb-4">选择您感兴趣的政策类别，系统将优先推送相关政策</p>
              <div
                v-for="category in subscriptionCategories"
                :key="category.id"
                class="p-4 border border-gray-200 rounded-lg hover:border-blue-300 transition-colors"
              >
                <label class="flex items-center justify-between cursor-pointer">
                  <div class="flex items-center gap-3">
                    <span class="text-xl">{{ category.icon }}</span>
                    <span class="font-medium text-gray-900">{{ category.name }}</span>
                  </div>
                  <input
                    v-model="category.checked"
                    type="checkbox"
                    class="w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                </label>
              </div>
            </div>
            <div class="px-5 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button
                @click="showSubscriptionManagement = false"
                class="px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                @click="saveSubscription"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                保存订阅
              </button>
            </div>
          </div>
        </div>

        <!-- Push Configuration Modal -->
        <div
          v-if="showPushConfig"
          class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          @click.self="showPushConfig = false"
        >
          <div class="bg-white rounded-xl w-full max-w-lg mx-4">
            <div class="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 class="font-semibold text-gray-900 flex items-center gap-2">
                <Settings :size="18" />
                智能推送配置
              </h3>
              <button @click="showPushConfig = false" class="p-1 hover:bg-gray-100 rounded">
                <X :size="20" class="text-gray-500" />
              </button>
            </div>
            <div class="p-5 space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">推送方式</label>
                <div class="space-y-2">
                  <label class="flex items-center gap-2">
                    <input v-model="pushConfig.email" type="checkbox" class="w-4 h-4 text-blue-600 rounded" />
                    <span class="text-sm text-gray-700 flex items-center gap-1">
                      <Mail :size="14" />
                      邮件通知
                    </span>
                  </label>
                  <label class="flex items-center gap-2">
                    <input v-model="pushConfig.sms" type="checkbox" class="w-4 h-4 text-blue-600 rounded" />
                    <span class="text-sm text-gray-700">短信通知</span>
                  </label>
                  <label class="flex items-center gap-2">
                    <input v-model="pushConfig.in_app" type="checkbox" class="w-4 h-4 text-blue-600 rounded" />
                    <span class="text-sm text-gray-700">应用内通知</span>
                  </label>
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">推送频率</label>
                <div class="flex gap-2">
                  <button
                    v-for="freq in [{ value: 'realtime', label: '实时' }, { value: 'daily', label: '每日' }, { value: 'weekly', label: '每周' }]"
                    :key="freq.value"
                    @click="pushConfig.frequency = freq.value"
                    :class="[
                      'px-4 py-2 text-sm rounded-lg border transition-colors',
                      pushConfig.frequency === freq.value ? 'bg-blue-50 border-blue-300 text-blue-700' : 'bg-gray-50 border-gray-200 text-gray-600'
                    ]"
                  >
                    {{ freq.label }}
                  </button>
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  匹配度阈值：{{ (pushConfig.severity_threshold * 100).toFixed(0) }}%
                </label>
                <input
                  v-model.number="pushConfig.severity_threshold"
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                />
                <div class="flex justify-between text-xs text-gray-500 mt-1">
                  <span>全部通知</span>
                  <span>高匹配度</span>
                </div>
              </div>
            </div>
            <div class="px-5 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button
                @click="showPushConfig = false"
                class="px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                @click="savePushConfiguration"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                保存配置
              </button>
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
