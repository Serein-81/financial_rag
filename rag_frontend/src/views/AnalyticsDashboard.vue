<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useGroupChatStore } from '@/stores/group-chat'
import { analyticsApi, type TenantStatistics, type UserStatistics } from '@/api/analytics'
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Users,
  MessageSquare,
  Clock,
  Activity,
  Shield,
  Eye,
  FileText,
  Calendar,
  RefreshCw,
  ChevronRight,
  Crown,
  UserCheck,
  Zap,
  AlertCircle,
  CheckCircle,
  XCircle,
  Loader2
} from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import SkeletonCard from '@/components/SkeletonCard.vue'

const authStore = useAuthStore()
const groupChatStore = useGroupChatStore()

const isAdmin = computed(() => authStore.isAdmin || localStorage.getItem('rag_user_role') === 'admin')
const currentUserId = computed(() => authStore.userEmail || '')

const isLoading = ref(false)
const error = ref<string | null>(null)
const lastUpdated = ref(new Date())
const animatedValues = ref<Record<string, number>>({})

const timeRange = ref<'today' | 'week' | 'month' | 'all'>('week')

const adminStats = ref<TenantStatistics | null>(null)
const userStats = ref<UserStatistics | null>(null)
const groupStats = ref<any[]>([])

function getDateRangeParams() {
  const now = new Date()
  let startDate: Date | undefined
  
  switch (timeRange.value) {
    case 'today':
      startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate())
      break
    case 'week':
      startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
      break
    case 'month':
      startDate = new Date(now.getFullYear(), now.getMonth(), 1)
      break
    case 'all':
      startDate = undefined
      break
  }
  
  return {
    start_date: startDate?.toISOString(),
    end_date: now.toISOString()
  }
}

async function loadStats() {
  isLoading.value = true
  error.value = null
  
  try {
    const dateParams = getDateRangeParams()
    
    if (isAdmin.value) {
      try {
        adminStats.value = await analyticsApi.getTenantStatistics(dateParams)
      } catch (e: any) {
        console.error('Failed to load admin stats:', e)
        adminStats.value = createMockAdminStats()
      }
    }
    
    try {
      userStats.value = await analyticsApi.getUserStatistics(
        currentUserId.value,
        dateParams
      )
    } catch (e: any) {
      console.error('Failed to load user stats:', e)
      userStats.value = createMockUserStats()
    }
    
    try {
      groupStats.value = groupChatStore.groups.map(g => ({
        group_id: g.id,
        group_name: g.name,
        member_count: g.member_count || 0,
        message_count: g.last_message ? 1 : 0
      }))
    } catch (e: any) {
      console.error('Failed to load group stats:', e)
    }
    
    lastUpdated.value = new Date()
    
    // 触发数字动画
    animateAllNumbers()
  } catch (e: any) {
    error.value = e.message || '加载数据失败'
    console.error('Failed to load stats:', e)
  } finally {
    isLoading.value = false
  }
}

const animateAllNumbers = () => {
  if (adminStats.value) {
    animateNumber('totalUsers', adminStats.value.total_users)
    animateNumber('activeUsers', adminStats.value.active_users)
    animateNumber('totalSessions', adminStats.value.total_sessions)
    animateNumber('activeSessions', adminStats.value.active_sessions)
    animateNumber('totalMessages', adminStats.value.total_messages)
    animateNumber('avgSessionLength', adminStats.value.avg_session_length)
  }
  if (userStats.value) {
    animateNumber('userMessages', userStats.value.total_messages)
    animateNumber('userSessions', userStats.value.total_sessions)
  }
}

const animateNumber = (key: string, target: number) => {
  const start = animatedValues.value[key] || 0
  const duration = 1500
  const startTime = performance.now()
  
  const animate = (currentTime: number) => {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    const easeOut = 1 - Math.pow(1 - progress, 3)
    
    animatedValues.value = {
      ...animatedValues.value,
      [key]: Math.round(start + (target - start) * easeOut)
    }
    
    if (progress < 1) {
      requestAnimationFrame(animate)
    }
  }
  
  requestAnimationFrame(animate)
}

function createMockAdminStats(): TenantStatistics {
  return {
    total_users: 0,
    active_users: 0,
    total_sessions: 0,
    active_sessions: 0,
    total_messages: 0,
    total_tokens: 0,
    avg_session_length: 0,
    period_start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    period_end: new Date().toISOString(),
    daily_stats: [],
    hourly_stats: [],
    top_users: [],
    top_sessions: []
  }
}

function createMockUserStats(): UserStatistics {
  return {
    user_id: currentUserId.value,
    user_name: authStore.userName || '未知用户',
    total_sessions: 0,
    active_sessions: 0,
    total_messages: 0,
    total_tokens: 0,
    avg_session_length: 0,
    period_start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    period_end: new Date().toISOString(),
    daily_stats: [],
    top_sessions: []
  }
}

const selectedTimeRange = (range: 'today' | 'week' | 'month' | 'all') => {
  timeRange.value = range
  loadStats()
}

onMounted(async () => {
  await loadStats()
})

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num?.toString() || '0'
}

function formatTokens(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(2) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num?.toString() || '0'
}

function getTimeAgo(dateStr: string): string {
  if (!dateStr) return '暂无数据'
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  return `${days} 天前`
}

function getInitials(name: string): string {
  return name?.charAt(0)?.toUpperCase() || '?'
}

function getAvatarColor(name: string): string {
  const colors = [
    'from-emerald-500 to-teal-600',
    'from-emerald-500 to-teal-600',
    'from-green-500 to-emerald-600',
    'from-orange-500 to-red-600'
  ]
  const index = (name?.charCodeAt(0) || 0) % colors.length
  return colors[index]
}
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-gradient-to-br from-slate-100 via-emerald-50/30 to-teal-50/30 overflow-y-auto">
    <!-- Loading State -->
    <div v-if="isLoading" class="p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <SkeletonCard v-for="i in 4" :key="i" :lines="2" :hasHeader="true" />
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl">
      <div class="flex items-start gap-3">
        <AlertCircle :size="20" class="text-red-600 flex-shrink-0 mt-0.5" />
        <div>
          <p class="font-medium text-red-900">{{ error }}</p>
          <button @click="loadStats" class="text-sm text-red-600 hover:text-red-700 mt-1">
            点击重试
          </button>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <template v-else>
      <PageHeader
        :icon="BarChart3"
        title="运营分析"
        :subtitle="isAdmin ? '企业整体运营数据概览' : '个人使用统计'"
      >
        <div class="flex items-center gap-3">
          <div
            :class="[
              'px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-2',
              isAdmin ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
            ]"
          >
            <component :is="isAdmin ? Crown : UserCheck" :size="16" />
            <span>{{ isAdmin ? '管理员' : '个人' }}</span>
          </div>
          <button
            @click="loadStats"
            :disabled="isLoading"
            class="p-2 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw :size="18" :class="{ 'animate-spin': isLoading }" class="text-slate-500" />
          </button>
        </div>
      </PageHeader>

      <div class="px-6 pb-4">
        <div class="flex items-center gap-2">
          <button
            v-for="range in ['today', 'week', 'month', 'all'] as const"
            :key="range"
            @click="selectedTimeRange(range)"
            :class="[
              'px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200',
              timeRange === range
                ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-md'
                : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'
            ]"
          >
            {{
              range === 'today' ? '今日' :
              range === 'week' ? '本周' :
              range === 'month' ? '本月' : '全部'
            }}
          </button>
          <span class="ml-auto text-xs text-slate-400">
            最后更新: {{ lastUpdated.toLocaleTimeString() }}
          </span>
        </div>
      </div>

      <div class="px-6 pb-6">
        <template v-if="isAdmin && adminStats">
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard
              :icon="Users"
              label="总用户数"
              :value="formatNumber(animatedValues.totalUsers || 0)"
              icon-gradient="from-emerald-500 to-teal-600"
            />
            <StatCard
              :icon="MessageSquare"
              label="总消息数"
              :value="formatNumber(animatedValues.totalMessages || 0)"
              icon-gradient="from-green-500 to-emerald-600"
            />
            <StatCard
              :icon="Activity"
              label="总会话数"
              :value="formatNumber(animatedValues.totalSessions || 0)"
              icon-gradient="from-teal-500 to-cyan-600"
            />
            <StatCard
              :icon="Zap"
              label="平均会话长度"
              :value="formatNumber(animatedValues.avgSessionLength || 0)"
              icon-gradient="from-amber-500 to-orange-600"
            />
          </div>

        <!-- 详细数据区域 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <!-- 活跃用户排名 -->
          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-emerald-100 rounded-xl flex items-center justify-center">
                  <Users :size="20" class="text-emerald-600" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">活跃用户排名</h3>
                  <p class="text-xs text-gray-500">{{ timeRange === 'today' ? '今日' : timeRange === 'week' ? '本周' : timeRange === 'month' ? '本月' : '全部' }}消息量排行</p>
                </div>
              </div>
            </div>
            
            <div v-if="adminStats.top_users && adminStats.top_users.length > 0" class="space-y-3">
              <div
                v-for="(user, index) in adminStats.top_users.slice(0, 5)"
                :key="user.user_id"
                class="flex items-center gap-4 p-3 rounded-xl hover:bg-gray-50 transition-colors"
              >
                <div
                  :class="[
                    'w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold',
                    index === 0 ? 'bg-amber-100 text-amber-700' :
                    index === 1 ? 'bg-gray-200 text-gray-600' :
                    index === 2 ? 'bg-orange-100 text-orange-700' :
                    'bg-gray-100 text-gray-500'
                  ]"
                >
                  {{ index + 1 }}
                </div>
                <div :class="['w-10 h-10 bg-gradient-to-br rounded-xl flex items-center justify-center text-white font-bold', getAvatarColor(user.user_name)]">
                  {{ getInitials(user.user_name) }}
                </div>
                <div class="flex-1 min-w-0">
                  <p class="font-medium text-gray-900">{{ user.user_name }}</p>
                  <p class="text-xs text-gray-500">{{ formatNumber(user.message_count) }} 条消息</p>
                </div>
                <div class="text-right">
                  <p class="font-bold text-gray-900">{{ formatTokens(user.token_usage) }}</p>
                  <p class="text-xs text-gray-500">Tokens</p>
                </div>
              </div>
            </div>
            <div v-else class="py-8 text-center text-gray-500">
              暂无用户数据
            </div>
          </div>

          <!-- 群组活跃度 -->
          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-green-100 rounded-xl flex items-center justify-center">
                  <MessageSquare :size="20" class="text-green-600" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">群组活跃度</h3>
                  <p class="text-xs text-gray-500">群组消息统计</p>
                </div>
              </div>
            </div>
            
            <div v-if="groupStats && groupStats.length > 0" class="space-y-4">
              <div
                v-for="group in groupStats"
                :key="group.group_id"
                class="space-y-2"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <div :class="['w-8 h-8 bg-gradient-to-br rounded-lg flex items-center justify-center text-white font-bold text-xs', getAvatarColor(group.group_name)]">
                      {{ getInitials(group.group_name) }}
                    </div>
                    <span class="font-medium text-gray-900">{{ group.group_name }}</span>
                  </div>
                  <span class="text-sm font-bold text-gray-700">{{ group.message_count }}</span>
                </div>
                <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    class="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all duration-500"
                    :style="{ width: `${Math.min((group.message_count / Math.max(...groupStats.map(g => g.message_count || 1))) * 100, 100)}%` }"
                  ></div>
                </div>
              </div>
            </div>
            <div v-else class="py-8 text-center text-gray-500">
              暂无群组数据
            </div>
          </div>

          <!-- 峰值时段 -->
          <div v-if="adminStats.hourly_stats && adminStats.hourly_stats.length > 0" class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center">
                  <Clock :size="20" class="text-amber-600" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">活跃时段分布</h3>
                  <p class="text-xs text-gray-500">消息发送高峰时段</p>
                </div>
              </div>
            </div>
            
            <div class="space-y-3">
              <div
                v-for="hour in adminStats.hourly_stats.slice(0, 6)"
                :key="hour.hour"
                class="flex items-center gap-3"
              >
                <span class="w-12 text-sm font-medium text-gray-600">{{ hour.hour }}:00</span>
                <div class="flex-1 h-8 bg-gray-100 rounded-lg overflow-hidden">
                  <div
                    class="h-full bg-gradient-to-r from-amber-400 to-orange-500 rounded-lg flex items-center justify-end px-2 transition-all duration-500"
                    :style="{ width: `${Math.min((hour.messages / Math.max(...adminStats.hourly_stats.map(h => h.messages))) * 100, 100)}%` }"
                  >
                    <span class="text-xs font-medium text-white">{{ hour.messages }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 每日趋势 -->
          <div v-if="adminStats.daily_stats && adminStats.daily_stats.length > 0" class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-emerald-100 rounded-xl flex items-center justify-center">
                  <TrendingUp :size="20" class="text-emerald-600" />
                </div>
                <div>
                  <h3 class="font-bold text-gray-900">每日趋势</h3>
                  <p class="text-xs text-gray-500">会话/消息数量趋势</p>
                </div>
              </div>
            </div>
            
            <div class="space-y-4">
              <div
                v-for="day in adminStats.daily_stats.slice(-7)"
                :key="day.date"
                class="flex items-center gap-4"
              >
                <span class="w-16 text-xs text-gray-500">{{ day.date }}</span>
                <div class="flex-1 flex items-center gap-2">
                  <div class="flex-1 h-6 bg-emerald-50 rounded overflow-hidden">
                    <div
                      class="h-full bg-emerald-500 rounded transition-all duration-300"
                      :style="{ width: `${Math.min((day.sessions / Math.max(...adminStats.daily_stats.map(d => d.sessions))) * 100, 100)}%` }"
                    ></div>
                  </div>
                  <span class="w-8 text-xs text-gray-600">{{ day.sessions }}</span>
                </div>
                <div class="flex-1 flex items-center gap-2">
                  <div class="flex-1 h-6 bg-green-50 rounded overflow-hidden">
                    <div
                      class="h-full bg-green-500 rounded transition-all duration-300"
                      :style="{ width: `${Math.min((day.messages / Math.max(...adminStats.daily_stats.map(d => d.messages))) * 100, 100)}%` }"
                    ></div>
                  </div>
                  <span class="w-8 text-xs text-gray-600">{{ day.messages }}</span>
                </div>
              </div>
              <div class="flex items-center gap-4 pt-2 border-t border-gray-100">
                <span class="w-16"></span>
                <div class="flex-1 flex items-center gap-2">
                  <div class="w-3 h-3 bg-emerald-500 rounded"></div>
                  <span class="text-xs text-gray-500">会话数</span>
                </div>
                <div class="flex-1 flex items-center gap-2">
                  <div class="w-3 h-3 bg-green-500 rounded"></div>
                  <span class="text-xs text-gray-500">消息数</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- 普通用户视图 -->
      <template v-else-if="userStats">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center gap-4 mb-4">
              <div class="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center">
                <MessageSquare :size="24" class="text-emerald-600" />
              </div>
              <div>
                <p class="text-sm text-gray-500">我的会话</p>
                <p class="text-2xl font-bold text-gray-900">{{ formatNumber(userStats.total_sessions) }}</p>
              </div>
            </div>
            <div class="pt-4 border-t border-gray-100">
              <p class="text-xs text-gray-500">
                活跃会话 <span class="font-bold text-emerald-600">{{ formatNumber(userStats.active_sessions) }}</span>
              </p>
            </div>
          </div>

          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center gap-4 mb-4">
              <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
                <FileText :size="24" class="text-green-600" />
              </div>
              <div>
                <p class="text-sm text-gray-500">我的消息</p>
                <p class="text-2xl font-bold text-gray-900">{{ formatNumber(userStats.total_messages) }}</p>
              </div>
            </div>
            <div class="pt-4 border-t border-gray-100">
              <p class="text-xs text-gray-500">
                Token 使用 <span class="font-bold text-green-600">{{ formatTokens(userStats.total_tokens) }}</span>
              </p>
            </div>
          </div>

          <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div class="flex items-center gap-4 mb-4">
              <div class="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center">
                <Clock :size="24" class="text-amber-600" />
              </div>
              <div>
                <p class="text-sm text-gray-500">平均会话长度</p>
                <p class="text-2xl font-bold text-gray-900">{{ formatNumber(userStats.avg_session_length) }}</p>
              </div>
            </div>
            <div class="pt-4 border-t border-gray-100">
              <p class="text-xs text-gray-500">消息数/会话</p>
            </div>
          </div>
        </div>

        <!-- 最近会话 -->
        <div v-if="userStats.top_sessions && userStats.top_sessions.length > 0" class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-teal-100 rounded-xl flex items-center justify-center">
                <Activity :size="20" class="text-teal-600" />
              </div>
              <div>
                <h3 class="font-bold text-gray-900">最近会话</h3>
                <p class="text-xs text-gray-500">我的活跃会话记录</p>
              </div>
            </div>
          </div>

          <div class="space-y-3">
            <div
              v-for="session in userStats.top_sessions.slice(0, 5)"
              :key="session.session_id"
              class="flex items-center gap-4 p-4 rounded-xl hover:bg-gray-50 transition-colors cursor-pointer"
            >
              <div class="w-12 h-12 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center text-white font-bold text-lg">
                {{ getInitials(session.title) }}
              </div>
              <div class="flex-1 min-w-0">
                <p class="font-bold text-gray-900 truncate">{{ session.title || '无标题会话' }}</p>
                <p class="text-sm text-gray-500">创建于: {{ session.created_at }}</p>
              </div>
              <div class="text-right">
                <p class="text-lg font-bold text-gray-900">{{ session.message_count }}</p>
                <p class="text-xs text-gray-500">条消息</p>
              </div>
              <ChevronRight :size="20" class="text-gray-400" />
            </div>
          </div>
        </div>
        <div v-else class="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 text-center text-gray-500 py-8">
          暂无会话数据
        </div>
      </template>

      <!-- 提示信息 -->
      <div class="mt-6 p-4 bg-emerald-50 border border-emerald-200 rounded-xl">
        <div class="flex items-start gap-3">
          <AlertCircle :size="20" class="text-emerald-600 flex-shrink-0 mt-0.5" />
          <div>
            <p class="font-medium text-emerald-900">
              {{ isAdmin ? '管理员提示' : '个人用户提示' }}
            </p>
            <p class="text-sm text-emerald-700 mt-1">
              {{
                isAdmin
                  ? '此页面显示企业整体的运营数据，包括用户活跃度、消息统计等。数据来源于对话日志服务。'
                  : '此页面显示您的个人使用统计，包括会话数量、消息数量等。群组相关功能可在侧边栏"群组聊天"中访问。'
              }}
            </p>
          </div>
        </div>
      </div>
      </div>
    </template>
  </div>
</template>
