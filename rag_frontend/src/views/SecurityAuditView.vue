<script setup lang="ts">

import { ref, computed, onMounted } from 'vue'

import { multiAgentApi, type SecurityEvent } from '@/api/multi-agent'

import {

  Shield,

  AlertTriangle,

  ShieldCheck,

  ShieldAlert,

  ShieldX,

  Clock,

  RefreshCw,

  ChevronDown,

  ChevronRight,

  Filter,

  Activity,

  Settings,

  BarChart3,

} from 'lucide-vue-next'

import SecurityMonitorPanel from '@/components/SecurityMonitorPanel.vue'

const activeTab = ref<'audit' | 'monitor'>('audit')

const isLoading = ref(true)

const isRefreshing = ref(false)



const securityEvents = ref<SecurityEvent[]>([])

const securityStats = ref<{

  total_events: number

  by_severity: Record<string, number>

  by_type: Record<string, number>

  recent_trends: Array<{ date: string; count: number }>

} | null>(null)



const selectedSeverity = ref<string>('all')

const showFilters = ref(false)



const severityColors = {

  low: { bg: 'bg-gray-100', text: 'text-gray-700', icon: ShieldCheck },

  medium: { bg: 'bg-yellow-100', text: 'text-yellow-700', icon: AlertTriangle },

  high: { bg: 'bg-orange-100', text: 'text-orange-700', icon: ShieldAlert },

  critical: { bg: 'bg-red-100', text: 'text-red-700', icon: ShieldX },

}



const eventTypeLabels: Record<string, string> = {

  permission_denied: '权限拒绝',

  approval_request: '审批请求',

  approval_completed: '审批完成',

  prompt_injection: '提示词注入',

  role_change: '角色变更',

}



const severityLabels: Record<string, string> = {

  low: '低危',

  medium: '中危',

  high: '高危',

  critical: '严重',

}



const filteredEvents = computed(() => {

  if (selectedSeverity.value === 'all') return securityEvents.value

  return securityEvents.value.filter(e => e.severity === selectedSeverity.value)

})



async function fetchData() {

  try {

    const [events, stats] = await Promise.all([

      multiAgentApi.getSecurityEvents({ limit: 100 }),

      multiAgentApi.getSecurityStats(),

    ])

    securityEvents.value = events

    securityStats.value = stats

  } catch (error) {

    console.error('获取安全事件失败:', error)

  } finally {

    isLoading.value = false

    isRefreshing.value = false

  }

}



async function refresh() {

  isRefreshing.value = true

  await fetchData()

}



function formatDate(dateStr: string): string {

  return new Date(dateStr).toLocaleString('zh-CN')

}



function getEventTypeIcon(eventType: string) {

  switch (eventType) {

    case 'permission_denied': return ShieldX

    case 'approval_request': return ShieldAlert

    case 'approval_completed': return ShieldCheck

    case 'prompt_injection': return AlertTriangle

    case 'role_change': return Shield

    default: return Shield

  }

}

</script>



<template>

  <div class="min-h-screen bg-gray-50 p-6">

    <div class="max-w-7xl mx-auto">

      <div class="flex items-center justify-between mb-6">

        <div>

          <h1 class="text-2xl font-bold text-gray-900">安全管理中心</h1>

          <p class="text-sm text-gray-500 mt-1">统一管理安全监控与审计</p>

        </div>

        <button

          @click="refresh"

          :disabled="isRefreshing"

          class="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"

        >

          <RefreshCw :size="18" :class="{ 'animate-spin': isRefreshing }" />

          刷新

        </button>

      </div>

      <div class="flex gap-2 bg-white p-1.5 rounded-xl shadow-sm border border-gray-200 w-fit mb-6">

        <button

          @click="activeTab = 'audit'"

          :class="[

            'flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium transition-all',

            activeTab === 'audit'

              ? 'bg-emerald-600 text-white shadow-md'

              : 'text-gray-600 hover:bg-gray-100'

          ]"

        >

          <Shield :size="18" />

          <span>安全审计</span>

        </button>

        <button

          @click="activeTab = 'monitor'"

          :class="[

            'flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium transition-all',

            activeTab === 'monitor'

              ? 'bg-emerald-600 text-white shadow-md'

              : 'text-gray-600 hover:bg-gray-100'

          ]"

        >

          <Settings :size="18" />

          <span>安全配置</span>

        </button>

      </div>



      <div v-if="activeTab === 'monitor'" class="space-y-6">

        <SecurityMonitorPanel />

      </div>

      <template v-else>

        <div v-if="isLoading" class="flex items-center justify-center h-64">

          <Activity :size="32" class="animate-spin text-emerald-600" />

        </div>

        <template v-else>

          <div class="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-6">

          <div class="bg-white rounded-xl p-5 border border-gray-200">

            <div class="flex items-center gap-3">

              <div class="p-2 bg-gray-100 rounded-lg">

                <Shield :size="20" class="text-gray-600" />

              </div>

              <div>

                <p class="text-sm text-gray-500">总事件数</p>

                <p class="text-2xl font-bold text-gray-900">{{ securityStats?.total_events || 0 }}</p>

              </div>

            </div>

          </div>



          <div

            v-for="(count, severity) in securityStats?.by_severity"

            :key="severity"

            class="bg-white rounded-xl p-5 border border-gray-200"

          >

            <div class="flex items-center gap-3">

              <div :class="['p-2 rounded-lg', severityColors[severity as keyof typeof severityColors]?.bg]">

                <component

                  :is="severityColors[severity as keyof typeof severityColors]?.icon"

                  :size="20"

                  :class="severityColors[severity as keyof typeof severityColors]?.text"

                />

              </div>

              <div>

                <p class="text-sm text-gray-500">{{ severityLabels[severity] || severity }}</p>

                <p class="text-2xl font-bold" :class="severityColors[severity as keyof typeof severityColors]?.text">

                  {{ count }}

                </p>

              </div>

            </div>

          </div>

        </div>



        <div class="bg-white rounded-xl p-4 border border-gray-200 mb-6">

          <div class="flex items-center justify-between">

            <div class="flex items-center gap-2">

              <button

                v-for="sev in ['all', 'critical', 'high', 'medium', 'low']"

                :key="sev"

                @click="selectedSeverity = sev"

                :class="[

                  'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',

                  selectedSeverity === sev

                    ? 'bg-emerald-600 text-white'

                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'

                ]"

              >

                {{ sev === 'all' ? '全部' : severityLabels[sev] }}

                <span

                  v-if="sev !== 'all' && securityStats?.by_severity[sev]"

                  :class="[

                    'ml-1 px-1.5 py-0.5 rounded text-xs',

                    selectedSeverity === sev ? 'bg-emerald-400' : 'bg-gray-200'

                  ]"

                >

                  {{ securityStats?.by_severity[sev] }}

                </span>

              </button>

            </div>

          </div>

        </div>



        <div class="space-y-4">

          <div

            v-for="event in filteredEvents"

            :key="event.event_id"

            class="bg-white rounded-xl border border-gray-200 overflow-hidden"

          >

            <div class="p-4">

              <div class="flex items-start justify-between">

                <div class="flex items-start gap-3">

                  <div :class="['p-2 rounded-lg', severityColors[event.severity as keyof typeof severityColors]?.bg]">

                    <component

                      :is="getEventTypeIcon(event.event_type)"

                      :size="20"

                      :class="severityColors[event.severity as keyof typeof severityColors]?.text"

                    />

                  </div>

                  <div>

                    <div class="flex items-center gap-2 mb-1">

                      <span :class="['px-2 py-0.5 rounded text-xs font-medium', severityColors[event.severity as keyof typeof severityColors]?.bg, severityColors[event.severity as keyof typeof severityColors]?.text]">

                        {{ severityLabels[event.severity] }}

                      </span>

                      <span class="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded text-xs font-medium">

                        {{ eventTypeLabels[event.event_type] || event.event_type }}

                      </span>

                    </div>

                    <p class="font-medium text-gray-900 mb-1">

                      {{ event.details?.message || event.event_type }}

                    </p>

                    <div class="text-sm text-gray-500 space-y-1">

                      <p v-if="event.target_resource">

                        目标资源: {{ event.target_resource }}

                      </p>

                      <p>用户: {{ event.user_id.slice(0, 12) }}...</p>

                      <p v-if="event.ip_address">IP地址: {{ event.ip_address }}</p>

                    </div>

                  </div>

                </div>

                <div class="text-right">

                  <p class="text-sm text-gray-500">

                    <Clock :size="14" class="inline mr-1" />

                    {{ formatDate(event.created_at) }}

                  </p>

                </div>

              </div>



              <div v-if="event.details && Object.keys(event.details).length > 0" class="mt-4 pt-4 border-t border-gray-100">

                <p class="text-xs font-medium text-gray-500 mb-2">详细信息</p>

                <pre class="text-xs text-gray-600 bg-gray-50 p-3 rounded overflow-x-auto">{{ JSON.stringify(event.details, null, 2) }}</pre>

              </div>

            </div>

          </div>



          <div v-if="filteredEvents.length === 0" class="bg-white rounded-xl p-12 border border-gray-200 text-center">

            <ShieldCheck :size="48" class="mx-auto text-green-500 mb-4" />

            <h3 class="text-lg font-medium text-gray-900">暂无安全事件</h3>

            <p class="text-gray-500 mt-1">当前没有检测到安全威胁</p>

          </div>

        </div>



        <div v-if="securityStats?.recent_trends?.length" class="mt-8 bg-white rounded-xl p-6 border border-gray-200">

          <h3 class="text-lg font-semibold mb-4">最近7天事件趋势</h3>

          <div class="flex items-end gap-2 h-40">

            <div

              v-for="day in securityStats.recent_trends"

              :key="day.date"

              class="flex-1 flex flex-col items-center"

            >

              <div

                class="w-full bg-emerald-600 rounded-t transition-all hover:bg-emerald-700"

                :style="{ height: `${Math.max((day.count / Math.max(...securityStats.recent_trends.map(d => d.count))) * 100, 5)}%` }"

              />

              <span class="text-xs text-gray-500 mt-2">{{ day.date.slice(5) }}</span>

              <span class="text-xs font-medium text-gray-700">{{ day.count }}</span>

            </div>

          </div>

        </div>

        </template>

      </template>

    </div>

  </div>

</template>




