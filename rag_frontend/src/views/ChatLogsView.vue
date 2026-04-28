<script setup lang="ts">


import { ref, computed, onMounted } from 'vue'


import { chatLogsApi, type ChatLogSession, type ChatLogMessage, type ChatLogSessionStatistics, type ChatLogUserStatistics, type ChatLogTenantStatistics, type UserActionLog, type EnterpriseLogEntry, type TenantInfo } from '@/api/chat-logs'


import { useAuthStore } from '@/stores/auth'


import { formatChatTime } from '@/utils/time'


import {


  MessageSquare,


  RefreshCw,


  Loader2,


  ArrowLeft,


  Clock,


  User,


  Bot,


  Hash,


  FileText,


  BarChart3,


  ChevronRight,


  AlertCircle,


  TrendingUp,


  Users,


  MessageCircle,


  Download,


  CheckCircle,


  XCircle,


  AlertTriangle,


  Info,


  List,


  Building2,


} from 'lucide-vue-next'





const authStore = useAuthStore()


const isAdmin = computed(() => authStore.isAdmin)





type TabType = 'actions' | 'sessions' | 'statistics' | 'enterprise'


const activeTab = ref<TabType>('actions')


const isLoading = ref(false)


const error = ref('')





const sessions = ref<ChatLogSession[]>([])


const total = ref(0)


const page = ref(1)


const pageSize = ref(20)





const userStats = ref<ChatLogUserStatistics | null>(null)


const tenantStats = ref<ChatLogTenantStatistics | null>(null)





const actionLogs = ref<UserActionLog[]>([])


const actionLogsTotal = ref(0)


const actionLogsPage = ref(1)


const actionLogsPageSize = ref(20)


const isLoadingActionLogs = ref(false)





const filters = ref({


  keyword: '',


  start_date: '',


  end_date: '',


  user_id: ''


})





const actionLogsFilters = ref({


  level: '',


  start_date: '',


  end_date: ''


})





const enterpriseLogs = ref<any[]>([])


const enterpriseLogsTotal = ref(0)


const enterpriseLogsPage = ref(1)


const enterpriseLogsPageSize = ref(50)


const isLoadingEnterpriseLogs = ref(false)


const enterpriseLogsFilters = ref({


  level: '',


  action: '',


  start_time: '',


  end_time: ''


})





const managedTenants = ref<TenantInfo[]>([])


const selectedTenantId = ref<string>('')


const expandedTenantIds = ref<string[]>([])


const expandedLogIds = ref<string[]>([])





function toggleTenantInfo(logId: string) {


  const index = expandedTenantIds.value.indexOf(logId)


  if (index > -1) {


    expandedTenantIds.value.splice(index, 1)


  } else {


    expandedTenantIds.value.push(logId)


  }


}





function toggleLogDetail(logId: string) {


  const index = expandedLogIds.value.indexOf(logId)


  if (index > -1) {


    expandedLogIds.value.splice(index, 1)


  } else {


    expandedLogIds.value.push(logId)


  }


}





async function loadManagedTenants() {


  try {


    const response = await chatLogsApi.getManagedTenants()


    const tenants = response.data || response.tenants || []


    managedTenants.value = tenants


    if (tenants.length > 0) {


      const primaryTenant = tenants.find((t: TenantInfo) => t.is_primary)


      selectedTenantId.value = primaryTenant?.tenant_id || tenants[0].tenant_id


    }


  } catch (err: any) {


    console.error('加载企业列表失败:', err)


  }


}





const logLevels = [


  { value: '', label: '全部' },


  { value: 'INFO', label: 'INFO' },


  { value: 'WARNING', label: 'WARNING' },


  { value: 'ERROR', label: 'ERROR' },


  { value: 'DEBUG', label: 'DEBUG' }


]





onMounted(async () => {


  if (isAdmin.value) {


    await loadManagedTenants()


  }


  await loadActionLogs()


})





async function loadSessions() {


  try {


    isLoading.value = true


    error.value = ''





    const response = await chatLogsApi.getSessions({


      page: page.value,


      page_size: pageSize.value,


      keyword: filters.value.keyword || undefined,


      start_date: filters.value.start_date || undefined,


      end_date: filters.value.end_date || undefined,


      user_id: filters.value.user_id || undefined


    })





    sessions.value = response.sessions


    total.value = response.total


  } catch (err: any) {


    error.value = err.message || '加载会话列表失败'


  } finally {


    isLoading.value = false


  }


}





async function viewSessionDetail(session: ChatLogSession) {


  activeTab.value = 'statistics'


  await loadStatistics()


}





async function loadStatistics() {


  try {


    isLoading.value = true


    error.value = ''





    if (isAdmin.value) {


      tenantStats.value = await chatLogsApi.getTenantStatistics(selectedTenantId.value || undefined)


    } else {


      let userId = ''


      if (authStore.userProfile?.id) {


        userId = authStore.userProfile.id


      } else {


        await authStore.fetchUserProfile()


        userId = authStore.userProfile?.id || ''


      }





      if (!userId) {


        error.value = '暂无统计数据，请先发起一些对话'


        return


      }


      


      const [userStatsResponse, tenantStatsResponse] = await Promise.all([


        chatLogsApi.getUserStatistics(userId),


        chatLogsApi.getTenantStatistics(selectedTenantId.value || undefined).catch(() => null)


      ])


      


      userStats.value = userStatsResponse


      tenantStats.value = tenantStatsResponse


    }





    activeTab.value = 'statistics'


    await loadActionLogs()


  } catch (err: any) {


    console.error('加载统计失败:', err)


    if (err.message && err.message.includes('404')) {


      error.value = '暂无统计数据，请先发起一些对话'
    } else {


      error.value = err.message || '加载统计信息失败'


    }


  } finally {


    isLoading.value = false


  }


}





async function loadActionLogs() {


  try {


    isLoadingActionLogs.value = true





    const response = await chatLogsApi.getUserActionLogs({


      page: actionLogsPage.value,


      page_size: actionLogsPageSize.value,


      level: actionLogsFilters.value.level || undefined,


      start_date: actionLogsFilters.value.start_date || undefined,


      end_date: actionLogsFilters.value.end_date || undefined,


    })





    actionLogs.value = response.logs


    actionLogsTotal.value = response.total


  } catch (err: any) {


    console.error('加载操作日志失败:', err)


  } finally {


    isLoadingActionLogs.value = false


  }


}





function goBack() {


  activeTab.value = 'sessions'


}





function formatDate(dateStr: string | number | null | undefined): string {


  return formatChatTime(dateStr)


}





function formatTokens(tokens: number | undefined): string {


  if (!tokens) return '0'


  return tokens.toLocaleString()


}





function getTotalPages(): number {


  return Math.ceil(total.value / pageSize.value)


}





async function clearFilters() {


  filters.value = {


    keyword: '',


    start_date: '',


    end_date: '',


    user_id: ''


  }


  page.value = 1


  await loadSessions()


}





async function clearActionLogsFilters() {


  actionLogsFilters.value = {


    level: '',


    start_date: '',


    end_date: ''


  }


  actionLogsPage.value = 1


  await loadActionLogs()


}





function getRoleIcon(role: string) {


  return role === 'user' ? User : Bot


}





function getRoleName(role: string): string {


  const names: Record<string, string> = {


    'user': '用户',


    'assistant': '助手',


    'system': '系统'


  }


  return names[role] || role


}





function getLevelIcon(level: string | undefined) {


  const icons: Record<string, any> = {


    'INFO': CheckCircle,


    'WARNING': AlertTriangle,


    'ERROR': XCircle,


    'DEBUG': Info


  }


  return icons[level || 'INFO'] || Info


}

function getLevelIconClass(level: string | undefined): string {
  return level === 'DEBUG' ? 'text-gray-500' : 'text-gray-600'
}

function getLevelIconBgClass(level: string | undefined): string {
  return level === 'DEBUG' ? 'bg-gray-100' : 'bg-gray-200'
}

function getLevelBadgeClass(level: string | undefined): string {
  return level === 'DEBUG' ? 'bg-gray-100 text-gray-700' : 'bg-gray-200 text-gray-700'
}

function getRiskBadgeClass(riskLevel: string | undefined): string {
  const classes: Record<string, string> = {
    medium: 'bg-yellow-100 text-yellow-700',
    high: 'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700'
  }
  return classes[riskLevel || ''] || 'bg-gray-100 text-gray-600'
}

function getRiskLabel(riskLevel: string | undefined): string {
  const labels: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
    critical: '严重风险'
  }
  return labels[riskLevel || ''] || riskLevel || '低风险'
}





async function loadMoreActionLogs() {


  actionLogsPage.value += 1


  try {


    isLoadingActionLogs.value = true





    const response = await chatLogsApi.getUserActionLogs({


      page: actionLogsPage.value,


      page_size: actionLogsPageSize.value,


      level: actionLogsFilters.value.level || undefined,


      start_date: actionLogsFilters.value.start_date || undefined,


      end_date: actionLogsFilters.value.end_date || undefined,


    })





    actionLogs.value = [...actionLogs.value, ...response.logs]


    actionLogsTotal.value = response.total


  } catch (err: any) {


    console.error('加载更多操作日志失败:', err)


  } finally {


    isLoadingActionLogs.value = false


  }


}





const isExporting = ref(false)


const exportFormat = ref('xlsx')





async function exportSessions() {


  try {


    isExporting.value = true


    await chatLogsApi.exportSessions({


      page: 1,


      page_size: 1000,


      keyword: filters.value.keyword || undefined,


      start_date: filters.value.start_date || undefined,


      end_date: filters.value.end_date || undefined,


      user_id: filters.value.user_id || undefined,


      format: exportFormat.value


    })


  } catch (err: any) {


    error.value = err.message || '导出失败'


  } finally {


    isExporting.value = false


  }


}





async function exportActionLogs() {


  try {


    isExporting.value = true


    await chatLogsApi.exportActionLogs({


      page: 1,


      page_size: 1000,


      level: actionLogsFilters.value.level || undefined,


      start_date: actionLogsFilters.value.start_date || undefined,


      end_date: actionLogsFilters.value.end_date || undefined,


      format: exportFormat.value


    })


  } catch (err: any) {


    error.value = err.message || '导出操作日志失败'


  } finally {


    isExporting.value = false


  }


}





async function loadEnterpriseLogs() {


  try {


    isLoadingEnterpriseLogs.value = true


    error.value = ''





    const response = await chatLogsApi.getEnterpriseLogs({


      level: enterpriseLogsFilters.value.level || undefined,


      action: enterpriseLogsFilters.value.action || undefined,


      start_time: enterpriseLogsFilters.value.start_time || undefined,


      end_time: enterpriseLogsFilters.value.end_time || undefined,


      limit: enterpriseLogsPageSize.value,


      offset: (enterpriseLogsPage.value - 1) * enterpriseLogsPageSize.value,


      tenant_id: selectedTenantId.value || undefined


    })





    if (response.success && response.data) {


      enterpriseLogs.value = response.data.logs || []


      enterpriseLogsTotal.value = response.data.total || 0


    }


  } catch (err: any) {


    console.error('加载企业日志失败:', err)


    error.value = err.message || '加载企业日志失败'


  } finally {


    isLoadingEnterpriseLogs.value = false


  }


}





async function loadMoreEnterpriseLogs() {


  enterpriseLogsPage.value += 1


  try {


    isLoadingEnterpriseLogs.value = true





    const response = await chatLogsApi.getEnterpriseLogs({


      level: enterpriseLogsFilters.value.level || undefined,


      action: enterpriseLogsFilters.value.action || undefined,


      start_time: enterpriseLogsFilters.value.start_time || undefined,


      end_time: enterpriseLogsFilters.value.end_time || undefined,


      limit: enterpriseLogsPageSize.value,


      offset: (enterpriseLogsPage.value - 1) * enterpriseLogsPageSize.value


    })





    if (response.success && response.data) {


      enterpriseLogs.value = [...enterpriseLogs.value, ...(response.data.logs || [])]


      enterpriseLogsTotal.value = response.data.total || 0


    }


  } catch (err: any) {


    console.error('加载更多企业日志失败:', err)


  } finally {


    isLoadingEnterpriseLogs.value = false


  }


}





async function clearEnterpriseLogsFilters() {


  enterpriseLogsFilters.value = {


    level: '',


    action: '',


    start_time: '',


    end_time: ''


  }


  enterpriseLogsPage.value = 1


  await loadEnterpriseLogs()


}





function getEnterpriseLogLevelIcon(level: string) {


  const icons: Record<string, any> = {


    'INFO': CheckCircle,


    'WARNING': AlertTriangle,


    'ERROR': XCircle,


    'DEBUG': Info


  }


  return icons[level] || Info


}


</script>





<template>


  <div class="h-full flex flex-col bg-gray-50">


    <div class="bg-white border-b border-gray-200 px-6 py-4">


      <div class="flex items-center justify-between">


        <div>


          <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">


            <FileText :size="28" class="text-gray-600" />


            日志详情


          </h1>


          <p class="text-sm text-gray-500 mt-1">{{ activeTab === 'actions' ? actionLogsTotal : activeTab === 'enterprise' ? enterpriseLogsTotal : total }} 条记录</p>


        </div>





        <div class="flex items-center bg-gray-100 rounded-lg p-1">


          <button


            @click="activeTab = 'actions'; actionLogsPage = 1; loadActionLogs()"


            :class="[


              'px-4 py-2 rounded-md font-medium transition-all',


              activeTab === 'actions'


                ? 'bg-white text-gray-600 shadow-sm'


                : 'text-gray-600 hover:text-gray-900'


            ]"


          >


            操作日志


          </button>


          <button


            @click="activeTab = 'sessions'; page = 1; loadSessions()"


            :class="[


              'px-4 py-2 rounded-md font-medium transition-all',


              activeTab === 'sessions'


                ? 'bg-white text-gray-600 shadow-sm'


                : 'text-gray-600 hover:text-gray-900'


            ]"


          >


            对话日志


          </button>


          <button


            v-if="isAdmin"


            @click="activeTab = 'enterprise'; enterpriseLogsPage = 1; loadEnterpriseLogs()"


            :class="[


              'px-4 py-2 rounded-md font-medium transition-all',


              activeTab === 'enterprise'


                ? 'bg-white text-gray-600 shadow-sm'


                : 'text-gray-600 hover:text-gray-900'


            ]"


          >


            企业日志


          </button>


        </div>


        <div class="flex items-center gap-2">


          <button


            @click="activeTab === 'statistics' ? loadStatistics() : (activeTab === 'actions' ? loadActionLogs() : activeTab === 'enterprise' ? loadEnterpriseLogs() : loadSessions())"


            :disabled="isLoading || isLoadingActionLogs || isLoadingEnterpriseLogs"


            class="px-4 py-2 bg-gray-700 text-white font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 flex items-center gap-2"


          >


            <Loader2 v-if="isLoading || isLoadingActionLogs || isLoadingEnterpriseLogs" :size="18" class="animate-spin" />


            <RefreshCw v-else :size="18" />


            刷新


          </button>


          <button


            v-if="isAdmin"


            @click="loadStatistics"


            :disabled="isLoading"


            class="px-4 py-2 bg-gray-700 text-white font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 flex items-center gap-2"


          >


            <BarChart3 :size="18" />


            企业统计


          </button>


          <button


            v-if="!isAdmin"


            @click="activeTab = 'statistics'; loadStatistics()"


            :disabled="isLoading"


            class="px-4 py-2 bg-gray-700 text-white font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 flex items-center gap-2"


          >


            <BarChart3 :size="18" />


            我的统计


          </button>


        </div>


      </div>





      <div v-if="activeTab === 'sessions'" class="flex gap-4 mt-4">


        <input


          v-model="filters.keyword"


          type="text"


          placeholder="搜索会话内容..."


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none flex-1"


        />


        <input


          v-model="filters.start_date"


          type="date"


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"


        />


        <input


          v-model="filters.end_date"


          type="date"


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"


        />


        <button


          @click="loadSessions"


          class="px-4 py-2 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200 flex items-center gap-2"


        >


          <TrendingUp :size="18" />


          搜索


        </button>


        <button


          @click="clearFilters"


          class="px-4 py-2 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200"


        >


          重置


        </button>


        <select


          v-model="exportFormat"


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none text-sm"


        >


          <option value="xlsx">Excel (.xlsx)</option>


          <option value="csv">CSV (.csv)</option>


        </select>


        <button


          @click="exportSessions"


          :disabled="isLoading || isExporting"


          class="px-4 py-2 bg-gray-700 text-white font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 flex items-center gap-2"


        >


          <Loader2 v-if="isExporting" :size="18" class="animate-spin" />


          <Download v-else :size="18" />


          导出对话日志


        </button>


      </div>





      <div v-if="activeTab === 'actions'" class="flex gap-4 mt-4 flex-wrap">


        <select


          v-model="actionLogsFilters.level"


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none bg-white"


        >


          <option v-for="level in logLevels" :key="level.value" :value="level.value">


            {{ level.label }}


          </option>


        </select>


        <input


          v-model="actionLogsFilters.start_date"


          type="date"


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"


        />


        <input


          v-model="actionLogsFilters.end_date"


          type="date"


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"


        />


        <button


          @click="loadActionLogs"


          class="px-4 py-2 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200 flex items-center gap-2"


        >


          <TrendingUp :size="18" />


          搜索


        </button>


        <button


          @click="clearActionLogsFilters"


          class="px-4 py-2 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200"


        >


          重置


        </button>


        <select


          v-model="exportFormat"


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none text-sm"


        >


          <option value="xlsx">Excel (.xlsx)</option>


          <option value="csv">CSV (.csv)</option>


        </select>


        <button


          @click="exportActionLogs"


          :disabled="isLoadingActionLogs || isExporting"


          class="px-4 py-2 bg-gray-700 text-white font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 flex items-center gap-2"


        >


          <Loader2 v-if="isExporting" :size="18" class="animate-spin" />


          <Download v-else :size="18" />


          导出操作日志


        </button>


      </div>





      <div v-if="activeTab === 'enterprise'" class="flex gap-4 mt-4 flex-wrap items-center">


        <div v-if="managedTenants.length > 1" class="flex gap-2 flex-wrap items-center">


          <span class="text-sm font-medium text-gray-700">选择企业</span>


          <div class="flex gap-2 bg-gray-100 p-1 rounded-lg">


            <button


              v-for="tenant in managedTenants"


              :key="tenant.tenant_id"


              @click="selectedTenantId = tenant.tenant_id; loadEnterpriseLogs(); enterpriseLogsPage = 1"


              :class="[


                'px-4 py-2 rounded-md font-medium transition-all text-sm',


                selectedTenantId === tenant.tenant_id


                  ? 'bg-white text-gray-600 shadow-sm'


                  : 'text-gray-600 hover:text-gray-900'


              ]"


            >


              <div class="flex items-center gap-2">


                <Building2 :size="16" />


                {{ tenant.company_name }}


                <span v-if="tenant.is_primary" class="px-1.5 py-0.5 text-xs bg-gray-200 text-gray-700 rounded">✓</span>


              </div>


            </button>


          </div>


        </div>


        <div v-else-if="managedTenants.length === 1" class="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg border border-gray-300">


          <Building2 :size="18" class="text-gray-600" />


          <span class="text-sm font-medium text-gray-800">{{ managedTenants[0].company_name }}</span>


          <span v-if="managedTenants[0].is_primary" class="px-1.5 py-0.5 text-xs bg-gray-300 text-gray-900 rounded">✓</span>


        </div>


        <select


          v-model="enterpriseLogsFilters.level"


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none bg-white"


        >


          <option v-for="level in logLevels" :key="level.value" :value="level.value">


            {{ level.label }}


          </option>


        </select>


        <input


          v-model="enterpriseLogsFilters.action"


          type="text"


          placeholder="搜索操作..."


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"


        />


        <input


          v-model="enterpriseLogsFilters.start_time"


          type="date"


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"


        />


        <input


          v-model="enterpriseLogsFilters.end_time"


          type="date"


          class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"


        />


        <button


          @click="loadEnterpriseLogs"


          class="px-4 py-2 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200 flex items-center gap-2"


        >


          <TrendingUp :size="18" />


          搜索


        </button>


        <button


          @click="clearEnterpriseLogsFilters"


          class="px-4 py-2 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200"


        >


          重置


        </button>


      </div>


    </div>





    <div v-if="error" class="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">


      <AlertCircle :size="18" />


      {{ error }}


    </div>





    <div v-if="isLoadingActionLogs && !actionLogs.length" class="flex-1 flex items-center justify-center">


      <Loader2 :size="48" class="animate-spin text-gray-600" />


    </div>





    <div v-else-if="activeTab === 'actions'" class="flex-1 overflow-auto p-4">


      <div class="space-y-2">


        <div


          v-for="log in actionLogs"


          :key="log.id"


          class="bg-white rounded-lg shadow-sm border border-gray-200 p-3 hover:shadow-md transition-shadow"


        >


          <div class="flex items-start gap-3">


            <div class="flex-shrink-0 mt-0.5">


              <div


                class="w-8 h-8 rounded-full flex items-center justify-center"
                :class="getLevelIconBgClass(log.level)"
              >
                <component
                  :is="getLevelIcon(log.level)"
                  :size="16"
                  :class="getLevelIconClass(log.level)"


                />


              </div>


            </div>





            <div class="flex-1 min-w-0">


              <div class="flex items-center gap-2 mb-1 flex-wrap">


                <span class="font-semibold text-sm text-gray-900">{{ log.action_name }}</span>


                <span


                  class="px-2 py-0.5 text-xs rounded-full font-medium"
                  :class="getLevelBadgeClass(log.level)"
                >
                  {{ log.level || 'INFO' }}
                </span>


                <span


                  v-if="log.success"


                  class="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700 font-medium"


                >


                  成功


                </span>


                <span


                  v-else


                  class="px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-700 font-medium"


                >


                  失败


                </span>


              </div>





              <span
                v-if="log.risk_level && log.risk_level !== 'low'"
                class="inline-flex mb-2 px-2 py-0.5 text-xs rounded-full font-medium"
                :class="getRiskBadgeClass(log.risk_level)"
              >
                {{ getRiskLabel(log.risk_level) }}
              </span>

              <div class="text-gray-500 text-xs mb-2">


                {{ log.description || log.action_type }}


              </div>





              <div class="flex items-center gap-4 text-xs text-gray-400 flex-wrap">


                <div class="flex items-center gap-1">


                  <Clock :size="12" />


                  <span>{{ formatDate(log.created_at) }}</span>


                </div>


                <div v-if="log.ip_address" class="flex items-center gap-1">


                  <User :size="12" />


                  <span>IP: {{ log.ip_address }}</span>


                </div>

                <div v-if="log.tenant_id" class="flex items-center gap-1">
                  <span>企业: {{ log.tenant_id }}</span>
                </div>


              </div>





              <div v-if="log.result_message" class="mt-1 p-1.5 bg-red-50 border border-red-100 rounded text-red-600 text-xs">


                {{ log.result_message }}


              </div>


            </div>


          </div>


        </div>





        <div v-if="actionLogs.length === 0 && !isLoadingActionLogs" class="text-center py-12">


          <FileText :size="48" class="mx-auto text-gray-300 mb-4" />


          <div class="text-gray-500 mb-2">暂无操作日志记录</div>


          <div class="text-sm text-gray-400">登录、上传文档等操作将会显示在这里</div>


        </div>





        <div v-if="actionLogsTotal > actionLogsPage * actionLogsPageSize" class="flex justify-center">


          <button


            @click="loadMoreActionLogs"


            class="px-6 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-2"


          >


            <Loader2 v-if="isLoadingActionLogs" :size="18" class="animate-spin" />


            加载更多


          </button>


        </div>


      </div>


    </div>





    <div v-else-if="activeTab === 'enterprise'" class="flex-1 overflow-auto p-4">


      <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">


        <table class="w-full">


          <thead class="bg-gray-50 border-b border-gray-200">


            <tr>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">时间</th>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">员工</th>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">等级</th>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">分类</th>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">操作</th>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">消息</th>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">IP</th>


            </tr>


          </thead>


          <tbody class="divide-y divide-gray-100">


            <tr


              v-for="log in enterpriseLogs"


              :key="log.id"


              class="hover:bg-gray-50 transition-colors"


            >


              <td class="px-3 py-2">


                <div class="flex items-center gap-1 text-xs text-gray-500">


                  <Clock :size="12" />


                  {{ formatDate(log.created_at) }}


                </div>


              </td>


              <td class="px-3 py-2">


                <div class="flex items-center gap-2">


                  <div class="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center">


                    <User :size="12" class="text-gray-600" />


                  </div>


                  <div>


                    <div class="text-xs font-medium text-gray-900">{{ log.user_name || log.user_email || '系统' }}</div>


                    <div v-if="log.user_email && log.user_name" class="text-xs text-gray-400">{{ log.user_email }}</div>


                    <div v-if="log.tenant_name" class="mt-0.5">


                      <button


                        @click.stop="toggleTenantInfo(log.id)"


                        class="text-xs text-gray-600 hover:text-gray-800 flex items-center gap-1"


                      >


                        <Building2 :size="10" />


                        {{ log.tenant_name }}


                        <ChevronRight :size="10" :class="{ 'rotate-90': expandedTenantIds.includes(log.id) }" class="transition-transform" />


                      </button>


                      <div v-if="expandedTenantIds.includes(log.id)" class="mt-1 p-1.5 bg-gray-50 rounded text-xs text-gray-600 space-y-0.5">


                        <div><span class="font-medium">企业名称：</span>{{ log.tenant_name }}</div>


                        <div><span class="font-medium">企业ID：</span>{{ log.tenant_id }}</div>


                        <div><span class="font-medium">邀请码：</span>{{ log.tenant_invite_code || '无' }}</div>


                      </div>


                    </div>


                  </div>


                </div>


              </td>


              <td class="px-3 py-2">
                <span
                  class="px-2 py-0.5 text-xs rounded-full font-medium"
                  :class="getLevelBadgeClass(log.level)"
                >
                  {{ log.level || 'INFO' }}
                </span>
              </td>


              <td class="px-3 py-2">


                <span class="text-xs text-gray-700">{{ log.category || '-' }}</span>


              </td>


              <td class="px-3 py-2">


                <span class="text-xs text-gray-900">{{ log.action || '-' }}</span>


              </td>


              <td class="px-3 py-2">


                <div v-if="expandedLogIds.includes(log.id)" class="text-xs text-gray-600 max-w-md p-2 bg-gray-50 rounded border border-gray-200 max-h-40 overflow-y-auto">


                  {{ log.message }}


                </div>


                <div v-else class="text-xs text-gray-600 max-w-xs truncate" :title="log.message">


                  {{ log.message }}


                </div>


                <button


                  v-if="log.message && log.message.length > 50"


                  @click.stop="toggleLogDetail(log.id)"


                  class="text-xs text-gray-600 hover:text-gray-800 mt-1 flex items-center gap-1"


                >


                  <component :is="expandedLogIds.includes(log.id) ? ChevronRight : ChevronRight" :size="12" :class="{ 'rotate-90': expandedLogIds.includes(log.id) }" class="transition-transform" />


                  {{ expandedLogIds.includes(log.id) ? '收起' : '查看详情' }}


                </button>


              </td>


              <td class="px-3 py-2">


                <span class="text-xs text-gray-500">{{ log.ip_address || '-' }}</span>


              </td>


            </tr>


          </tbody>


        </table>





        <div v-if="!enterpriseLogs.length && !isLoadingEnterpriseLogs" class="p-8 text-center text-gray-500">


          <Building2 :size="48" class="mx-auto text-gray-300 mb-4" />


          <div class="mb-2">暂无企业日志记录</div>


          <div class="text-sm text-gray-400">所有员工的系统操作将会显示在这里</div>


        </div>





        <div v-if="isLoadingEnterpriseLogs && !enterpriseLogs.length" class="p-8 text-center">


          <Loader2 :size="32" class="animate-spin text-gray-600 mx-auto" />


        </div>





        <div v-if="enterpriseLogsTotal > enterpriseLogsPage * enterpriseLogsPageSize" class="px-4 py-3 border-t border-gray-200 flex items-center justify-center">


          <button


            @click="loadMoreEnterpriseLogs"


            :disabled="isLoadingEnterpriseLogs"


            class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"


          >


            <Loader2 v-if="isLoadingEnterpriseLogs" :size="16" class="animate-spin" />


            加载更多


          </button>


        </div>


      </div>


    </div>





    <div v-else-if="activeTab === 'sessions'" class="flex-1 overflow-auto p-4">


      <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">


        <table class="w-full">


          <thead class="bg-gray-50 border-b border-gray-200">


            <tr>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">用户</th>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">会话标题</th>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">消息数</th>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">Token 使用</th>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">创建时间</th>


              <th class="px-3 py-2 text-left text-xs font-medium text-gray-600">操作</th>


            </tr>


          </thead>


          <tbody class="divide-y divide-gray-100">


            <tr


              v-for="session in sessions"


              :key="session.id"


              class="hover:bg-gray-50 cursor-pointer transition-colors"


              @click="viewSessionDetail(session)"


            >


              <td class="px-3 py-2">


                <div class="flex items-center gap-1">


                  <User :size="12" class="text-gray-400" />


                  <span class="text-xs text-gray-900">{{ session.user_name }}</span>


                </div>


              </td>


              <td class="px-3 py-2">


                <div class="text-xs text-gray-900 font-medium truncate max-w-xs">{{ session.title || '无标题' }}</div>


                <div v-if="session.last_message_preview" class="text-xs text-gray-500 truncate max-w-xs">


                  {{ session.last_message_preview }}


                </div>


              </td>


              <td class="px-3 py-2">


                <div class="flex items-center gap-1 text-xs text-gray-600">


                  <MessageCircle :size="12" />


                  {{ session.message_count }}


                </div>


              </td>


              <td class="px-3 py-2">


                <div class="text-xs text-gray-600">


                  <span class="text-gray-600">{{ formatTokens(session.total_prompt_tokens) }}</span>


                  <span class="text-gray-400 mx-0.5">/</span>


                  <span class="text-gray-600">{{ formatTokens(session.total_completion_tokens) }}</span>


                  <span class="text-gray-400 mx-0.5">=</span>


                  <span class="text-gray-900 font-medium">{{ formatTokens(session.total_tokens) }}</span>


                </div>


              </td>


              <td class="px-3 py-2">


                <div class="flex items-center gap-1 text-xs text-gray-500">


                  <Clock :size="12" />


                  {{ formatDate(session.created_at) }}


                </div>


              </td>


              <td class="px-3 py-2">


                <button


                  class="px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-100 rounded flex items-center gap-0.5"


                  @click.stop="viewSessionDetail(session)"


                >


                  查看 <ChevronRight :size="12" />


                </button>


              </td>


            </tr>


          </tbody>


        </table>





        <div v-if="!sessions.length && !isLoading" class="p-6 text-center text-gray-500">


          暂无会话记录


        </div>





        <div v-if="getTotalPages() > 1" class="px-3 py-2 border-t border-gray-200 flex items-center justify-between">


          <div class="text-xs text-gray-500">


            第 {{ page }} 页，共 {{ getTotalPages() }} ?

          </div>


          <div class="flex gap-1">


            <button


              @click="page = Math.max(1, page - 1); loadSessions()"


              :disabled="page <= 1"


              class="px-2 py-0.5 text-xs bg-white border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-50"


            >


              上一页

            </button>


            <button


              @click="page = Math.min(getTotalPages(), page + 1); loadSessions()"


              :disabled="page >= getTotalPages()"


              class="px-2 py-0.5 text-xs bg-white border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-50"


            >


              下一页

            </button>


          </div>


        </div>


      </div>


    </div>





    <div v-else-if="activeTab === 'statistics'" class="flex-1 overflow-auto p-6">


      <div class="bg-white rounded-lg shadow-sm border border-gray-200 mb-6">


        <div class="px-6 py-4 flex items-center gap-4">


          <button


            @click="goBack"


            class="p-2 hover:bg-gray-100 rounded-lg transition-colors"


          >


            <ArrowLeft :size="20" />


          </button>


          <div class="flex-1">


            <div class="flex items-center gap-4 flex-wrap">


              <h2 class="text-lg font-semibold text-gray-900">


                {{ isAdmin ? '企业统计' : '我的统计' }}


              </h2>


              <div v-if="isAdmin && managedTenants.length > 1" class="flex gap-2 items-center">


                <span class="text-sm font-medium text-gray-600">选择企业</span>


                <div class="flex gap-1 bg-gray-100 p-1 rounded-lg">


                  <button


                    v-for="tenant in managedTenants"


                    :key="tenant.tenant_id"


                    @click="selectedTenantId = tenant.tenant_id; loadStatistics()"


                    :class="[


                      'px-3 py-1.5 rounded-md font-medium transition-all text-sm',


                      selectedTenantId === tenant.tenant_id


                        ? 'bg-white text-gray-600 shadow-sm'


                        : 'text-gray-600 hover:text-gray-900'


                    ]"


                  >


                    <div class="flex items-center gap-1.5">


                      <Building2 :size="14" />


                      {{ tenant.company_name }}


                      <span v-if="tenant.is_primary" class="px-1 py-0.5 text-xs bg-gray-200 text-gray-700 rounded">✓</span>


                    </div>


                  </button>


                </div>


              </div>


              <div v-else-if="isAdmin && managedTenants.length === 1" class="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg border border-gray-300">


                <Building2 :size="16" class="text-gray-600" />


                <span class="text-sm font-medium text-gray-800">{{ managedTenants[0].company_name }}</span>


                <span v-if="managedTenants[0].is_primary" class="px-1 py-0.5 text-xs bg-gray-300 text-gray-900 rounded">✓</span>


              </div>


            </div>


            <p class="text-sm text-gray-500 mt-2">


              {{ isAdmin ? '查看企业所有用户的对话统计' : '查看个人对话统计' }}


            </p>


          </div>


        </div>


      </div>





      <!-- 普通用户统计-->


      <template v-if="!isAdmin && userStats">


        <!-- AI对话统计 -->


        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">


          <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">


            <Bot :size="20" class="text-gray-600" />


            AI 对话统计


          </h3>


          <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">


            <div class="p-4 bg-gray-100 rounded-lg">


              <div class="text-sm text-gray-600 font-medium">会话总数</div>


              <div class="text-2xl font-bold text-gray-700 mt-1">{{ userStats.chat_statistics?.total_sessions || 0 }}</div>


            </div>


            <div class="p-4 bg-gray-100 rounded-lg">
              <div class="text-sm text-gray-600 font-medium">消息总数</div>
              <div class="text-2xl font-bold text-gray-700 mt-1">{{ userStats.chat_statistics?.total_messages || 0 }}</div>
            </div>


            <div class="p-4 bg-teal-50 rounded-lg">


              <div class="text-sm text-teal-600 font-medium">对话轮数</div>


              <div class="text-2xl font-bold text-teal-700 mt-1">{{ userStats.chat_statistics?.total_turns || 0 }}</div>


            </div>


            <div class="p-4 bg-orange-50 rounded-lg">


              <div class="text-sm text-orange-600 font-medium">Token 消费</div>


              <div class="text-2xl font-bold text-orange-700 mt-1">{{ formatTokens(userStats.chat_statistics?.total_tokens || 0) }}</div>


            </div>


          </div>


          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">


            <div class="p-4 bg-gray-100 rounded-lg">
              <div class="text-sm text-gray-700 font-medium">Prompt Tokens</div>
              <div class="text-xl font-bold text-gray-800 mt-1">{{ formatTokens(userStats.chat_statistics?.total_prompt_tokens || 0) }}</div>
            </div>


            <div class="p-4 bg-gray-200 rounded-lg">


              <div class="text-sm text-gray-700 font-medium">Completion Tokens</div>


              <div class="text-xl font-bold text-gray-800 mt-1">{{ formatTokens(userStats.chat_statistics?.total_completion_tokens || 0) }}</div>


            </div>


            <div class="p-4 bg-gray-100 rounded-lg">


              <div class="text-sm text-gray-700 font-medium">?Token</div>


              <div class="text-xl font-bold text-gray-800 mt-1">{{ formatTokens(userStats.chat_statistics?.total_tokens || 0) }}</div>


            </div>


          </div>


        </div>





        <!-- 用户操作日志统计 -->


        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">


          <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">


            <FileText :size="20" class="text-gray-600" />


            用户操作日志统计


          </h3>


          <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">


            <div class="p-4 bg-gray-100 rounded-lg">


              <div class="text-sm text-gray-600 font-medium">总操作数</div>


              <div class="text-2xl font-bold text-gray-700 mt-1">{{ userStats.action_statistics?.total_actions || 0 }}</div>


            </div>


            <div class="p-4 bg-green-50 rounded-lg">


              <div class="text-sm text-green-600 font-medium">成功操作 (INFO)</div>


              <div class="text-2xl font-bold text-green-700 mt-1">{{ userStats.action_statistics?.level_stats?.INFO || 0 }}</div>


            </div>


            <div class="p-4 bg-red-50 rounded-lg">


              <div class="text-sm text-red-600 font-medium">失败操作 (ERROR)</div>


              <div class="text-2xl font-bold text-red-700 mt-1">{{ userStats.action_statistics?.level_stats?.ERROR || 0 }}</div>


            </div>


            <div class="p-4 bg-teal-50 rounded-lg">


              <div class="text-sm text-teal-600 font-medium">成功率</div>


              <div class="text-2xl font-bold text-teal-700 mt-1">{{ userStats.action_statistics?.success_rate || 0 }}%</div>


            </div>


          </div>


          


          <!-- 日志级别分布 -->


          <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">


            <div class="p-3 bg-green-100 rounded-lg">


              <div class="flex items-center gap-2">


                <div class="w-3 h-3 rounded-full bg-green-500"></div>


                <span class="text-sm text-green-700">INFO</span>


              </div>


              <div class="text-lg font-bold text-green-800 mt-1">{{ userStats.action_statistics?.level_stats?.INFO || 0 }}</div>


            </div>


            <div class="p-3 bg-yellow-100 rounded-lg">


              <div class="flex items-center gap-2">


                <div class="w-3 h-3 rounded-full bg-yellow-500"></div>


                <span class="text-sm text-yellow-700">WARNING</span>


              </div>


              <div class="text-lg font-bold text-yellow-800 mt-1">{{ userStats.action_statistics?.level_stats?.WARNING || 0 }}</div>


            </div>


            <div class="p-3 bg-red-100 rounded-lg">


              <div class="flex items-center gap-2">


                <div class="w-3 h-3 rounded-full bg-red-500"></div>


                <span class="text-sm text-red-700">ERROR</span>


              </div>


              <div class="text-lg font-bold text-red-800 mt-1">{{ userStats.action_statistics?.level_stats?.ERROR || 0 }}</div>


            </div>


            <div class="p-3 bg-gray-100 rounded-lg">


              <div class="flex items-center gap-2">


                <div class="w-3 h-3 rounded-full bg-gray-500"></div>


                <span class="text-sm text-gray-700">DEBUG</span>


              </div>


              <div class="text-lg font-bold text-gray-800 mt-1">{{ userStats.action_statistics?.level_stats?.DEBUG || 0 }}</div>


            </div>


          </div>





          <!-- 操作类型统计 -->


          <div v-if="userStats.action_statistics?.action_type_stats && Object.keys(userStats.action_statistics.action_type_stats).length > 0">


            <h4 class="text-md font-semibold text-gray-800 mb-3">操作类型分布</h4>


            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">


              <div 


                v-for="(count, type) in userStats.action_statistics.action_type_stats" 


                :key="type"


                class="p-3 bg-gray-50 rounded-lg flex items-center justify-between"


              >


                <span class="text-sm font-medium text-gray-700">{{ type }}</span>


                <span class="text-lg font-bold text-gray-600">{{ count }}</span>


              </div>


            </div>


          </div>


          <div v-else class="text-center py-8 text-gray-500">


            暂无操作日志记录


          </div>


        </div>





        <!-- 企业统计（普通用户可见） -->


        <div v-if="tenantStats" class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">


          <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">


            <Building2 :size="20" class="text-gray-600" />


            企业统计概览


          </h3>


          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">


            <div class="p-4 bg-teal-50 rounded-lg">


              <div class="flex items-center gap-2 mb-2">


                <Users :size="16" class="text-teal-600" />


                <span class="text-sm text-teal-600 font-medium">企业用户数</span>


              </div>


              <div class="text-2xl font-bold text-teal-700">{{ tenantStats.total_users }}</div>


            </div>


            <div class="p-4 bg-gray-100 rounded-lg">
              <div class="flex items-center gap-2 mb-2">
                <MessageCircle :size="16" class="text-gray-600" />
                <span class="text-sm text-gray-600 font-medium">活跃用户数</span>
              </div>
              <div class="text-2xl font-bold text-gray-700">{{ tenantStats.active_users }}</div>
            </div>


            <div class="p-4 bg-gray-100 rounded-lg">


              <div class="flex items-center gap-2 mb-2">


                <Hash :size="16" class="text-gray-600" />


                <span class="text-sm text-gray-600 font-medium">总会话数</span>


              </div>


              <div class="text-2xl font-bold text-gray-700">{{ tenantStats.total_sessions }}</div>


            </div>


            <div class="p-4 bg-orange-50 rounded-lg">


              <div class="flex items-center gap-2 mb-2">


                <BarChart3 :size="16" class="text-orange-600" />


                <span class="text-sm text-orange-600 font-medium">总Token消费</span>


              </div>


              <div class="text-2xl font-bold text-orange-700">{{ formatTokens(tenantStats.total_tokens) }}</div>


            </div>


          </div>


          


          <div class="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">


            <div class="p-3 bg-gray-100 rounded-lg">
              <div class="text-sm text-gray-700 font-medium">企业Prompt Tokens</div>
              <div class="text-lg font-bold text-gray-800 mt-1">{{ formatTokens(tenantStats.total_prompt_tokens) }}</div>
            </div>


            <div class="p-3 bg-gray-200 rounded-lg">


              <div class="text-sm text-gray-700 font-medium">企业Completion Tokens</div>


              <div class="text-lg font-bold text-gray-800 mt-1">{{ formatTokens(tenantStats.total_completion_tokens) }}</div>


            </div>


            <div class="p-3 bg-gray-100 rounded-lg">


              <div class="text-sm text-gray-700 font-medium">企业总消息数</div>


              <div class="text-lg font-bold text-gray-800 mt-1">{{ tenantStats.total_messages?.toLocaleString() }}</div>


            </div>


          </div>


        </div>





        <!-- 用户操作日志详细列表 -->


        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">


          <div class="flex items-center justify-between mb-4">


            <h3 class="text-lg font-semibold text-gray-900 flex items-center gap-2">


              <List :size="20" class="text-gray-600" />


              操作日志详情


            </h3>


            <div class="text-sm text-gray-500">


              {{ actionLogsTotal }} 条记录

            </div>


          </div>





          <div v-if="isLoadingActionLogs" class="flex items-center justify-center py-12">


            <Loader2 :size="32" class="animate-spin text-gray-600" />


            <span class="ml-2 text-gray-600">加载中...</span>


          </div>





          <div v-else-if="actionLogs.length === 0" class="text-center py-12">


            <div class="text-gray-400 mb-2">暂无操作日志记录</div>


            <div class="text-sm text-gray-400">登录、登出等操作将会显示在这里</div>


          </div>





          <div v-else class="space-y-3">


            <div


              v-for="log in actionLogs"


              :key="log.id"


              class="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"


            >


              <div class="flex items-start gap-4">


                <div class="flex-shrink-0 mt-1">


                  <div


                    class="w-10 h-10 rounded-full flex items-center justify-center"


                    :class="getLevelIconBgClass(log.level)"
                  >
                    <component
                      :is="getLevelIcon(log.level)"
                      :size="20"
                      :class="getLevelIconClass(log.level)"
                    />


                  </div>


                </div>





                <div class="flex-1 min-w-0">


                  <div class="flex items-center gap-2 mb-1">


                    <span class="font-semibold text-gray-900">{{ log.action_name }}</span>


                    <span


                      class="px-2 py-0.5 text-xs rounded-full"
                      :class="getLevelBadgeClass(log.level)"
                    >
                      {{ log.level || 'INFO' }}
                    </span>


                    <span


                      v-if="log.success"


                      class="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700"


                    >


                      成功


                    </span>


                    <span


                      v-else


                      class="px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-700"


                    >


                      失败


                    </span>


                  </div>





                  <span
                    v-if="log.risk_level && log.risk_level !== 'low'"
                    class="inline-flex mb-2 px-2 py-0.5 text-xs rounded-full font-medium"
                    :class="getRiskBadgeClass(log.risk_level)"
                  >
                    {{ getRiskLabel(log.risk_level) }}
                  </span>

                  <div class="text-sm text-gray-600 mb-1">


                    {{ log.description || log.action_type }}


                  </div>





                  <div class="flex items-center gap-4 text-xs text-gray-400 flex-wrap">


                    <span>{{ formatDate(log.created_at) }}</span>


                    <span v-if="log.ip_address">IP: {{ log.ip_address }}</span>
                    <span v-if="log.tenant_id">企业: {{ log.tenant_id }}</span>


                    <span v-if="log.result_message" class="text-red-500">{{ log.result_message }}</span>


                  </div>

                  <div
                    v-if="log.extra_info && Object.keys(log.extra_info).length"
                    class="mt-3 rounded-md bg-gray-50 p-3 text-xs text-gray-600"
                  >
                    <div class="mb-1 font-medium text-gray-700">详情</div>
                    <pre class="whitespace-pre-wrap break-words">{{ JSON.stringify(log.extra_info, null, 2) }}</pre>
                  </div>


                </div>


              </div>


            </div>





            <div v-if="actionLogsTotal > actionLogsPageSize" class="flex justify-center mt-4">


              <button


                @click="loadMoreActionLogs"


                class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"


              >


                加载更多


              </button>


            </div>


          </div>


        </div>


      </template>





      <!-- 管理员统计-->


      <template v-else-if="isAdmin && tenantStats">


        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">


          <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">


            <div class="flex items-center justify-between">


              <div>


                <div class="text-sm text-gray-500">企业用户数</div>


                <div class="text-3xl font-bold text-gray-900 mt-1">


                  {{ tenantStats.total_users }}


                </div>


              </div>


              <div class="p-3 bg-gray-200 rounded-full">


                <Users :size="24" class="text-gray-600" />


              </div>


            </div>


          </div>





          <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">


            <div class="flex items-center justify-between">


              <div>


                <div class="text-sm text-gray-500">活跃用户数</div>


                <div class="text-3xl font-bold text-gray-900 mt-1">


                  {{ tenantStats.active_users }}


                </div>


              </div>


              <div class="p-3 bg-gray-200 rounded-full">
                <MessageCircle :size="24" class="text-gray-600" />
              </div>


            </div>


          </div>





          <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">


            <div class="flex items-center justify-between">


              <div>


                <div class="text-sm text-gray-500">总会话数</div>


                <div class="text-3xl font-bold text-gray-900 mt-1">


                  {{ tenantStats.total_sessions }}


                </div>


              </div>


              <div class="p-3 bg-teal-100 rounded-full">


                <Hash :size="24" class="text-teal-600" />


              </div>


            </div>


          </div>





          <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">


            <div class="flex items-center justify-between">


              <div>


                <div class="text-sm text-gray-500">?Token 消费</div>


                <div class="text-3xl font-bold text-gray-900 mt-1">


                  {{ formatTokens(tenantStats.total_tokens) }}


                </div>


              </div>


              <div class="p-3 bg-orange-100 rounded-full">


                <BarChart3 :size="24" class="text-orange-600" />


              </div>


            </div>


          </div>


        </div>





        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">


          <h3 class="text-lg font-semibold text-gray-900 mb-4">企业 Token 使用详情</h3>


          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">


            <div class="p-4 bg-gray-100 rounded-lg">
              <div class="text-sm text-gray-600 font-medium">Prompt Tokens</div>
              <div class="text-2xl font-bold text-gray-700 mt-1">{{ formatTokens(tenantStats.total_prompt_tokens) }}</div>
            </div>


            <div class="p-4 bg-gray-100 rounded-lg">


              <div class="text-sm text-gray-600 font-medium">Completion Tokens</div>


              <div class="text-2xl font-bold text-gray-700 mt-1">{{ formatTokens(tenantStats.total_completion_tokens) }}</div>


            </div>


            <div class="p-4 bg-gray-100 rounded-lg">


              <div class="text-sm text-gray-600 font-medium">总消息数</div>


              <div class="text-2xl font-bold text-gray-700 mt-1">{{ tenantStats.total_messages?.toLocaleString() }}</div>


            </div>


          </div>


        </div>


      </template>


    </div>


  </div>


</template>


