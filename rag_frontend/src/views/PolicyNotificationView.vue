<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { policyApi, type PolicyNotification, type SSEPolicyNotification } from '@/api/policy'
import { policyTrackingApi } from '@/api/policy-tracking'
import { tenantSettingsApi, type TenantSettings } from '@/api/tenant-settings'
import { getEnterpriseId, getTenantIdFromToken, isAuthenticated } from '@/utils/request'
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
  Mail,
  Wifi,
  WifiOff,
  Activity,
  Zap,
  Brain,
  Cpu,
  MessageSquare
} from 'lucide-vue-next'

const router = useRouter()

const isLoading = ref(false)
const notifications = ref<PolicyNotification[]>([])
const filterStatus = ref<string>('all')
const selectedNotifications = ref<Set<string>>(new Set())
const showEnterpriseProfile = ref(false)
const showSubscriptionManagement = ref(false)
const showPushConfig = ref(false)

// PolicyNotificationAgent 状态
const agentStatus = ref<any>(null)
const isCheckingAgent = ref(false)
const llmGeneratedContent = ref<Map<string, any>>(new Map())
const isGeneratingContent = ref(false)
const tenantSettings = ref<TenantSettings | null>(null)

// SSE Real-time Push State
const sseConnected = ref(false)
const sseConnecting = ref(false)
const eventSource = ref<EventSource | null>(null)
const realTimeNotification = ref<SSEPolicyNotification | null>(null)
const showRealTimeAlert = ref(false)
const sseLastHeartbeat = ref<string>('')

// SSE Connection Management
function getAuthToken(): string {
  return localStorage.getItem('rag_token') || ''
}

function connectSSE() {
  const token = getAuthToken()
  if (!token) {
    console.warn('⚠️ 未登录或认证已过期，无法建立实时推送连接')
    ElMessage.warning('请先登录以启用实时推送功能')
    return
  }

  const tenantId = getTenantIdFromToken()
  if (!tenantId) {
    console.warn('⚠️ 无法获取租户ID，无法建立实时推送连接')
    ElMessage.warning('租户信息缺失，请重新登录')
    return
  }

  if (eventSource.value) {
    console.log('SSE connection already exists')
    return
  }

  sseConnecting.value = true
  console.log('🔌 正在建立SSE连接...')

  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const url = `${baseUrl}/api/v1/policy-notifications/stream?token=${encodeURIComponent(token)}&tenant_id=${encodeURIComponent(tenantId)}`

  try {
    eventSource.value = new EventSource(url)

    eventSource.value.onopen = () => {
      console.log('✅ SSE连接已建立')
      sseConnected.value = true
      sseConnecting.value = false
      ElMessage.success('实时推送已连接')
    }

    eventSource.value.addEventListener('heartbeat', (event) => {
      try {
        const data = JSON.parse(event.data)
        sseLastHeartbeat.value = new Date(data.timestamp).toLocaleTimeString('zh-CN')
        console.log('💓 心跳:', sseLastHeartbeat.value)
      } catch (error) {
        console.error('解析心跳数据失败:', error)
      }
    })

    eventSource.value.addEventListener('policy_matched', (event) => {
      try {
        const data: SSEPolicyNotification = JSON.parse(event.data)
        console.log('📨 收到实时政策推送:', data)

        realTimeNotification.value = data
        showRealTimeAlert.value = true

        if (Notification.permission === 'granted') {
          new Notification('🔔 新政策通知', {
            body: `${data.policy_title}\n匹配度: ${(data.match_score * 100).toFixed(0)}%`,
            icon: '🔔',
            tag: data.policy_id
          })
        }

        ElMessage.success(`收到新政策推送: ${data.policy_title}`)

        setTimeout(() => {
          showRealTimeAlert.value = false
        }, 10000)
      } catch (error) {
        console.error('解析政策推送数据失败:', error)
      }
    })

    eventSource.value.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log('📨 收到消息:', data)
      } catch (error) {
        console.error('解析消息失败:', error)
      }
    })

    eventSource.value.onerror = (error) => {
      console.error('❌ SSE连接错误:', error)
      sseConnected.value = false
      sseConnecting.value = false
      ElMessage.error('实时推送连接失败，正在尝试重新连接...')

      disconnectSSE()

      setTimeout(() => {
        connectSSE()
      }, 5000)
    }
  } catch (error) {
    console.error('创建SSE连接失败:', error)
    sseConnecting.value = false
    ElMessage.error('建立实时推送失败')
  }
}

function disconnectSSE() {
  if (eventSource.value) {
    eventSource.value.close()
    eventSource.value = null
    sseConnected.value = false
    sseConnecting.value = false
    console.log('❌ SSE连接已断开')
  }
}

function dismissRealTimeNotification() {
  showRealTimeAlert.value = false
  realTimeNotification.value = null
}

async function viewRealTimePolicyDetail() {
  if (realTimeNotification.value) {
    dismissRealTimeNotification()
    router.push(`/policy/${realTimeNotification.value.policy_id}`)
  }
}

onMounted(async () => {
  if (isAuthenticated()) {
    await Promise.all([
      loadNotifications(),
      loadSubscriptions(),
      loadTenantSettings(),
      connectSSE(),
      checkAgentStatus()
    ])

    if (Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }
})

async function loadTenantSettings() {
  try {
    tenantSettings.value = await tenantSettingsApi.getMySettings()
    enterpriseProfile.value = {
      ...enterpriseProfile.value,
      industry: tenantSettings.value.industry || enterpriseProfile.value.industry,
      region: tenantSettings.value.region || enterpriseProfile.value.region,
      company_size: tenantSettings.value.scale || enterpriseProfile.value.company_size
    }
  } catch (error) {
    console.warn('Failed to load tenant settings:', error)
  }
}

function getEnterpriseName() {
  return tenantSettings.value?.company_name || '企业'
}

onUnmounted(() => {
  disconnectSSE()
})

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

async function generateLLMNotificationContent(policyId: string, policy: any) {
  if (!agentStatus.value?.use_llm) {
    ElMessage.warning('请先启用LLM模式以生成个性化通知')
    return
  }

  if (llmGeneratedContent.value.has(policyId)) {
    ElMessage.info('该通知已生成LLM分析内容')
    return
  }

  isGeneratingContent.value = true
  try {
    const enterpriseId = getEnterpriseId() || 'default'

    const request = {
      policy: {
        policy_id: policyId,
        title: policy.title || '政策通知',
        content: policy.content || policy.summary || '',
        source: 'policy_notifications'
      },
      enterprise_profile: {
        enterprise_id: enterpriseId,
        enterprise_name: getEnterpriseName(),
        industry: enterpriseProfile.value.industry || '通用',
        region: enterpriseProfile.value.region || '全国',
        scale: enterpriseProfile.value.scale || '中型企业',
        tax_types: enterpriseProfile.value.tax_types || [],
        qualifications: enterpriseProfile.value.qualifications || []
      },
      match_result: {
        match_score: policy.match_score || 0.5,
        industry_match: true,
        region_match: true,
        scale_match: true,
        reasons: []
      }
    }

    const result = await policyApi.generatePolicyNotification(request)

    llmGeneratedContent.value.set(policyId, result)
    ElMessage.success('已生成个性化通知内容')
  } catch (error: any) {
    ElMessage.error('生成失败')
    console.error('Failed to generate LLM content:', error)
  } finally {
    isGeneratingContent.value = false
  }
}

async function batchGenerateLLMContent() {
  if (notifications.value.length === 0) {
    ElMessage.warning('暂无通知可生成')
    return
  }

  const pendingNotifications = notifications.value.slice(0, 5)
  isGeneratingContent.value = true

  try {
    for (const notification of pendingNotifications) {
      if (!llmGeneratedContent.value.has(notification.policy_id)) {
        await generateLLMNotificationContent(notification.policy_id, {
          title: notification.policy_title,
          match_score: notification.match_score
        })
      }
    }

    ElMessage.success('批量生成完成')
  } catch (error: any) {
    ElMessage.error('批量生成失败')
    console.error('Failed to batch generate:', error)
  } finally {
    isGeneratingContent.value = false
  }
}

function getLLMContent(policyId: string) {
  return llmGeneratedContent.value.get(policyId)
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
      <div class="flex items-center gap-4">
        <!-- SSE Status Indicator -->
        <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50">
          <template v-if="sseConnecting">
            <Loader2 :size="14" class="text-amber-600 animate-spin" />
            <span class="text-xs text-amber-600">连接中...</span>
          </template>
          <template v-else-if="sseConnected">
            <Activity :size="14" class="text-emerald-600" />
            <span class="text-xs text-emerald-600">实时推送已连接</span>
            <span v-if="sseLastHeartbeat" class="text-xs text-gray-400">{{ sseLastHeartbeat }}</span>
          </template>
          <template v-else>
            <WifiOff :size="14" class="text-gray-400" />
            <span class="text-xs text-gray-400">实时推送已断开</span>
            <button
              @click="connectSSE"
              class="text-xs text-blue-600 hover:text-blue-700"
            >
              重新连接
            </button>
          </template>
        </div>

        <!-- Agent Status -->
        <div v-if="agentStatus" class="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border border-purple-200">
          <Brain :size="16" class="text-purple-600" />
          <span class="text-xs font-medium text-purple-700">
            {{ agentStatus.use_llm ? 'LLM智能通知' : '规则通知' }}
          </span>
          <span v-if="agentStatus.llm_provider" class="text-xs text-purple-500">
            ({{ agentStatus.llm_provider }})
          </span>
        </div>

        <!-- LLM批量生成按钮 -->
        <button
          v-if="agentStatus?.use_llm"
          @click="batchGenerateLLMContent"
          :disabled="isGeneratingContent || notifications.length === 0"
          class="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-sm font-medium hover:from-purple-700 hover:to-indigo-700 transition-all disabled:opacity-50 flex items-center gap-2"
        >
          <Sparkles :size="16" :class="{ 'animate-pulse': isGeneratingContent }" />
          {{ isGeneratingContent ? '生成中...' : '批量生成LLM通知' }}
        </button>

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

    <!-- Real-time Notification Alert -->
    <Transition
      enter-active-class="transition ease-out duration-300"
      enter-from-class="transform -translate-y-full opacity-0"
      enter-to-class="transform translate-y-0 opacity-100"
      leave-active-class="transition ease-in duration-200"
      leave-from-class="transform translate-y-0 opacity-100"
      leave-to-class="transform -translate-y-full opacity-0"
    >
      <div
        v-if="showRealTimeAlert && realTimeNotification"
        class="bg-gradient-to-r from-emerald-500 to-teal-500 text-white px-6 py-4 shadow-lg z-50"
      >
        <div class="max-w-5xl mx-auto flex items-center justify-between gap-4">
          <div class="flex items-center gap-3 flex-1">
            <div class="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
              <Zap :size="20" class="text-white" />
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-1">
                <span class="px-2 py-0.5 bg-white/20 rounded text-xs font-medium">
                  实时推送
                </span>
                <span class="text-xs text-white/80">
                  {{ new Date(realTimeNotification.timestamp).toLocaleTimeString('zh-CN') }}
                </span>
              </div>
              <h4 class="text-sm font-semibold mb-1">{{ realTimeNotification.policy_title }}</h4>
              <div class="flex items-center gap-3 text-xs text-white/80">
                <span>匹配度: {{ (realTimeNotification.match_score * 100).toFixed(0) }}%</span>
                <span>影响级别: {{ realTimeNotification.impact_level }}</span>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="viewRealTimePolicyDetail"
              class="px-4 py-2 bg-white text-emerald-600 rounded-lg text-sm font-medium hover:bg-emerald-50 transition-colors flex items-center gap-1"
            >
              <Eye :size="14" />
              查看详情
            </button>
            <button
              @click="dismissRealTimeNotification"
              class="p-2 hover:bg-white/20 rounded-lg transition-colors"
            >
              <X :size="20" />
            </button>
          </div>
        </div>
      </div>
    </Transition>

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
                    <!-- LLM生成按钮 -->
                    <button
                      v-if="agentStatus?.use_llm"
                      @click.stop="generateLLMNotificationContent(notification.policy_id, { title: notification.policy_title, match_score: notification.match_score })"
                      :disabled="isGeneratingContent || llmGeneratedContent.has(notification.policy_id)"
                      class="px-3 py-1.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg text-xs font-medium hover:from-purple-700 hover:to-indigo-700 transition-all disabled:opacity-50 flex items-center gap-1"
                    >
                      <Brain :size="12" :class="{ 'animate-pulse': isGeneratingContent }" />
                      {{ llmGeneratedContent.has(notification.policy_id) ? '已生成' : 'LLM分析' }}
                    </button>

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

                <!-- LLM生成内容展示 -->
                <div
                  v-if="getLLMContent(notification.policy_id)"
                  class="mt-4 p-4 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-xl border border-purple-200"
                >
                  <div class="flex items-center gap-2 mb-3">
                    <Brain :size="16" class="text-purple-600" />
                    <span class="text-sm font-semibold text-purple-900">LLM个性化分析</span>
                  </div>

                  <div class="space-y-3">
                    <div v-if="getLLMContent(notification.policy_id)?.title">
                      <div class="text-xs text-gray-500 mb-1">个性化标题：</div>
                      <div class="text-sm font-medium text-purple-900">
                        {{ getLLMContent(notification.policy_id)?.title }}
                      </div>
                    </div>

                    <div v-if="getLLMContent(notification.policy_id)?.summary">
                      <div class="text-xs text-gray-500 mb-1">政策摘要：</div>
                      <div class="text-sm text-gray-700">
                        {{ getLLMContent(notification.policy_id)?.summary }}
                      </div>
                    </div>

                    <div v-if="getLLMContent(notification.policy_id)?.personalized_message">
                      <div class="text-xs text-gray-500 mb-1">个性化说明：</div>
                      <div class="text-sm text-gray-700">
                        {{ getLLMContent(notification.policy_id)?.personalized_message }}
                      </div>
                    </div>

                    <div v-if="getLLMContent(notification.policy_id)?.key_benefits?.length > 0">
                      <div class="text-xs text-gray-500 mb-2">关键利好：</div>
                      <div class="space-y-1">
                        <div
                          v-for="(benefit, idx) in getLLMContent(notification.policy_id)?.key_benefits"
                          :key="idx"
                          class="flex items-start gap-2 text-xs text-gray-700"
                        >
                          <MessageSquare :size="12" class="text-purple-600 mt-0.5 flex-shrink-0" />
                          <span>{{ benefit }}</span>
                        </div>
                      </div>
                    </div>

                    <div v-if="getLLMContent(notification.policy_id)?.action_items?.length > 0">
                      <div class="text-xs text-gray-500 mb-2">建议行动：</div>
                      <div class="space-y-1">
                        <div
                          v-for="(action, idx) in getLLMContent(notification.policy_id)?.action_items"
                          :key="idx"
                          class="flex items-start gap-2 text-xs text-gray-700"
                        >
                          <Zap :size="12" class="text-emerald-600 mt-0.5 flex-shrink-0" />
                          <span>{{ action }}</span>
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
