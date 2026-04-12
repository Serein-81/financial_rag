<script setup lang="ts">

import { ref, computed, onMounted, onUnmounted } from 'vue'

import { useAuthStore } from '@/stores/auth'

import { multiAgentApi, type SystemHealth, type TaskPipeline, type AgentMetric, SessionState } from '@/api/multi-agent'

import {

  Activity,

  CheckCircle2,

  XCircle,

  Warning,

  Clock,

  Zap,

  Users,

  Database,

  Shield,

  RefreshCw,

  ArrowRight,

  Loader2,

  ChevronDown,

  ChevronUp,

} from 'lucide-vue-next'



const authStore = useAuthStore()



const isAdmin = computed(() => authStore.isAdmin || localStorage.getItem('rag_user_role') === 'admin')

const activeTab = ref<'overview' | 'pipelines' | 'agents'>('overview')

const isLoading = ref(true)

const isRefreshing = ref(false)

const serviceUnavailable = ref(false)

const errorMessage = ref('')



const systemHealth = ref<SystemHealth | null>(null)

const activePipelines = ref<TaskPipeline[]>([])

const pipelineHistory = ref<TaskPipeline[]>([])

const agentMetrics = ref<AgentMetric[]>([])



const showHistory = ref(false)

const selectedPipeline = ref<TaskPipeline | null>(null)



let refreshInterval: number | null = null



const statusColors = {

  healthy: 'text-green-600 bg-green-50',

  degraded: 'text-yellow-600 bg-yellow-50',

  down: 'text-red-600 bg-red-50',

}



const stateLabels = {

  [SessionState.IDLE]: { text: '空闲', color: 'gray' },

  [SessionState.PROCESSING]: { text: '处理中， color: 'blue' },

  [SessionState.WAITING_FOR_USER_REPLY]: { text: '等待回复', color: 'yellow' },

  [SessionState.COMPLETED]: { text: '已完成， color: 'green' },

}



const taskStatusColors = {

  pending: 'bg-gray-400',

  running: 'bg-emerald-500 animate-pulse',

  completed: 'bg-green-500',

  failed: 'bg-red-500',

  streaming: 'bg-emerald-500 animate-pulse',

}



async function fetchData() {

  try {

    const results = await Promise.allSettled([

      multiAgentApi.getSystemHealth(),

      multiAgentApi.getActivePipelines(),

      multiAgentApi.getAgentMetrics(),

    ])



    const [healthResult, pipelinesResult, metricsResult] = results

    

    if (healthResult.status === 'fulfilled') {

      systemHealth.value = healthResult.value

    }

    if (pipelinesResult.status === 'fulfilled') {

      activePipelines.value = pipelinesResult.value

    }

    if (metricsResult.status === 'fulfilled') {

      agentMetrics.value = metricsResult.value

    }



    const hasAnyData = systemHealth.value || activePipelines.value.length > 0 || agentMetrics.value.length > 0

    

    if (!hasAnyData) {

      serviceUnavailable.value = true

      errorMessage.value = '多智能体服务未启用或暂无可用数据'

    } else {

      serviceUnavailable.value = false

      errorMessage.value = ''

    }



    if (showHistory.value && pipelineHistory.value.length === 0) {

      try {

        pipelineHistory.value = await multiAgentApi.getPipelineHistory({ limit: 20 })

      } catch {

        pipelineHistory.value = []

      }

    }

  } catch (error: any) {

    serviceUnavailable.value = true

    errorMessage.value = '多智能体服务未启用或暂无可用数据'

  } finally {

    isLoading.value = false

    isRefreshing.value = false

  }

}



async function refresh() {

  isRefreshing.value = true

  await fetchData()

}



function formatDuration(seconds: number): string {

  if (seconds < 60) return `${seconds.toFixed(0)}秒`

  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}分钟`

  return `${(seconds / 3600).toFixed(1)}小时`

}



function formatDate(dateStr: string): string {

  return new Date(dateStr).toLocaleString('zh-CN')

}



function getTaskProgress(tasks: any[]): number {

  if (tasks.length === 0) return 0

  const completed = tasks.filter(t => t.status === 'completed' || t.status === 'failed').length

  return Math.round((completed / tasks.length) * 100)

}



function toggleHistory() {

  showHistory.value = !showHistory.value

  if (showHistory.value && pipelineHistory.value.length === 0) {

    multiAgentApi.getPipelineHistory({ limit: 20 })

      .then(data => {

        pipelineHistory.value = data

      })

      .catch(() => {

        pipelineHistory.value = []

      })

  }

}



function selectPipeline(pipeline: TaskPipeline) {

  selectedPipeline.value = selectedPipeline.value?.pipeline_id === pipeline.pipeline_id ? null : pipeline

}



onMounted(() => {

  fetchData()

  refreshInterval = window.setInterval(() => {

    if (!document.hidden) {

      refresh()

    }

  }, 30000)

})



onUnmounted(() => {

  if (refreshInterval) {

    clearInterval(refreshInterval)

  }

})

</script>



<template>

  <div class="min-h-screen bg-gray-50 p-6">

    <div class="max-w-7xl mx-auto">

      <div class="flex items-center justify-between mb-6">

        <div>

          <h1 class="text-2xl font-bold text-gray-900">多智能体系统监控</h1>

          <p class="text-sm text-gray-500 mt-1">实时监控任务流水线、Agent状态和系统健康度</p>

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



      <div class="flex gap-2 mb-6">

        <button

          v-for="tab in [

            { key: 'overview', label: '系统概览' },

            { key: 'pipelines', label: '任务流水线 },

            { key: 'agents', label: 'Agent性能' },

          ]"

          :key="tab.key"

          @click="activeTab = tab.key as any"

          :class="[

            'px-4 py-2 rounded-lg font-medium transition-colors',

            activeTab === tab.key

              ? 'bg-emerald-600 text-white'

              : 'bg-white text-gray-600 hover:bg-gray-100'

          ]"

        >

          {{ tab.label }}

        </button>

      </div>



      <div v-if="isLoading" class="flex items-center justify-center h-64">

        <Loader2 :size="32" class="animate-spin text-emerald-600" />

      </div>



      <div v-else-if="serviceUnavailable" class="bg-white rounded-xl border border-gray-200 p-8">

        <div class="text-center">

          <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-50 mb-4">

            <Activity :size="32" class="text-emerald-400" />

          </div>

          <h3 class="text-lg font-semibold text-gray-900 mb-2">多智能体服务监控</h3>

          <p class="text-gray-500 mb-2">{{ errorMessage || '当前没有正在运行的智能体任务' }}</p>

          <p class="text-sm text-gray-400 mb-6">

            当您运行智能体对话时，这里将显示实时的任务流水线、Agent状态和系统健康度         </p>

          

          <div class="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto text-left">

            <div class="p-4 bg-gray-50 rounded-lg">

              <h4 class="font-medium text-gray-900 mb-2 flex items-center gap-2">

                <Zap :size="16" class="text-emerald-600" />

                任务流水线             </h4>

              <p class="text-sm text-gray-500">实时显示多Agent协作的任务执行流程和进度</p>

            </div>

            

            <div class="p-4 bg-gray-50 rounded-lg">

              <h4 class="font-medium text-gray-900 mb-2 flex items-center gap-2">

                <Users :size="16" class="text-green-600" />

                Agent性能

              </h4>

              <p class="text-sm text-gray-500">监控各Agent的请求量、响应时间和成功率</p>

            </div>

            

            <div class="p-4 bg-gray-50 rounded-lg">

              <h4 class="font-medium text-gray-900 mb-2 flex items-center gap-2">

                <Shield :size="16" class="text-orange-600" />

                系统健康度             </h4>

              <p class="text-sm text-gray-500">展示RBAC、调度器、存储等核心组件状态</p>

            </div>

          </div>

          

          <button

            @click="refresh"

            :disabled="isRefreshing"

            class="mt-6 inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"

          >

            <RefreshCw :size="16" :class="{ 'animate-spin': isRefreshing }" />

            重新检测         </button>

        </div>

      </div>



      <template v-else>

        <template v-if="activeTab === 'overview'">

          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">

            <div class="bg-white rounded-xl p-6 border border-gray-200">

              <div class="flex items-center gap-3 mb-4">

                <div :class="['p-2 rounded-lg', statusColors[systemHealth?.status || 'healthy']]">

                  <Activity :size="24" />

                </div>

                <div>

                  <p class="text-sm text-gray-500">系统状态</p>

                  <p class="text-lg font-semibold">

                    {{ systemHealth?.status === 'healthy' ? '健康' : systemHealth?.status === 'degraded' ? '降级' : '异常' }}

                  </p>

                </div>

              </div>

            </div>



            <div class="bg-white rounded-xl p-6 border border-gray-200">

              <div class="flex items-center gap-3 mb-4">

                <div class="p-2 rounded-lg bg-emerald-50 text-emerald-600">

                  <Zap :size="24" />

                </div>

                <div>

                  <p class="text-sm text-gray-500">活跃会话</p>

                  <p class="text-lg font-semibold">{{ systemHealth?.active_sessions || 0 }}</p>

                </div>

              </div>

            </div>



            <div class="bg-white rounded-xl p-6 border border-gray-200">

              <div class="flex items-center gap-3 mb-4">

                <div class="p-2 rounded-lg bg-orange-50 text-orange-600">

                  <Shield :size="24" />

                </div>

                <div>

                  <p class="text-sm text-gray-500">待审核</p>

                  <p class="text-lg font-semibold">{{ systemHealth?.pending_approvals || 0 }}</p>

                </div>

              </div>

            </div>

          </div>



          <div class="bg-white rounded-xl p-6 border border-gray-200 mb-6">

            <h3 class="text-lg font-semibold mb-4">组件状态/h3>

            <div class="grid grid-cols-2 md:grid-cols-5 gap-4">

              <div

                v-for="(status, component) in systemHealth?.components"

                :key="component"

                class="flex flex-col items-center p-4 rounded-lg border"

                :class="status ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'"

              >

                <CheckCircle2 v-if="status" :size="24" class="text-green-600 mb-2" />

                <XCircle v-else :size="24" class="text-red-600 mb-2" />

                <span class="text-sm font-medium text-center">

                  {{ component === 'rbac_service' ? 'RBAC服务' :

                     component === 'task_scheduler' ? '任务调度' :

                     component === 'session_blackboard' ? '会话存储' :

                     component === 'hitl_manager' ? 'HITL审批' :

                     '意图分类' }}

                </span>

              </div>

            </div>

          </div>



          <div class="bg-white rounded-xl p-6 border border-gray-200">

            <h3 class="text-lg font-semibold mb-4">运行时间</h3>

            <p class="text-3xl font-bold text-emerald-600">{{ formatDuration(systemHealth?.uptime || 0) }}</p>

          </div>

        </template>



        <template v-if="activeTab === 'pipelines'">

          <div class="space-y-4">

            <div

              v-for="pipeline in activePipelines"

              :key="pipeline.pipeline_id"

              class="bg-white rounded-xl border border-gray-200 overflow-hidden"

            >

              <div

                @click="selectPipeline(pipeline)"

                class="p-4 cursor-pointer hover:bg-gray-50 transition-colors"

              >

                <div class="flex items-center justify-between">

                  <div class="flex items-center gap-4">

                    <div>

                      <p class="font-medium text-gray-900">{{ pipeline.query }}</p>

                      <p class="text-sm text-gray-500">

                        会话: {{ pipeline.session_id.slice(0, 8) }}...

                        <span

                          :class="[

                            'ml-2 px-2 py-0.5 rounded text-xs',

                            stateLabels[pipeline.state as SessionState]?.color === 'green' ? 'bg-green-100 text-green-700' :

                            stateLabels[pipeline.state as SessionState]?.color === 'blue' ? 'bg-emerald-100 text-emerald-700' :

                            stateLabels[pipeline.state as SessionState]?.color === 'yellow' ? 'bg-yellow-100 text-yellow-700' :

                            'bg-gray-100 text-gray-700'

                          ]"

                        >

                          {{ stateLabels[pipeline.state as SessionState]?.text }}

                        </span>

                      </p>

                    </div>

                  </div>

                  <div class="flex items-center gap-4">

                    <div class="w-32">

                      <div class="flex justify-between text-xs text-gray-500 mb-1">

                        <span>进度</span>

                        <span>{{ getTaskProgress(pipeline.tasks) }}%</span>

                      </div>

                      <div class="h-2 bg-gray-200 rounded-full overflow-hidden">

                        <div

                          class="h-full bg-emerald-600 transition-all duration-300"

                          :style="{ width: `${getTaskProgress(pipeline.tasks)}%` }"

                        />

                      </div>

                    </div>

                    <component :is="selectedPipeline?.pipeline_id === pipeline.pipeline_id ? ChevronUp : ChevronDown" :size="20" class="text-gray-400" />

                  </div>

                </div>

              </div>



              <div v-if="selectedPipeline?.pipeline_id === pipeline.pipeline_id" class="border-t border-gray-200 p-4 bg-gray-50">

                <div class="space-y-3">

                  <div

                    v-for="(task, index) in pipeline.tasks"

                    :key="task.task_id"

                    class="flex items-center gap-4 p-3 bg-white rounded-lg border border-gray-200"

                  >

                    <div :class="['w-3 h-3 rounded-full', taskStatusColors[task.status as keyof typeof taskStatusColors]]" />

                    <div class="flex-1">

                      <p class="font-medium text-gray-900">{{ task.agent_name }}</p>

                      <p class="text-sm text-gray-500">

                        {{ task.status === 'running' ? '运行中 :

                           task.status === 'completed' ? '已完成 :

                           task.status === 'failed' ? '失败' :

                           task.status === 'pending' ? '等待中 : '流式输出中 }}

                      </p>

                    </div>

                    <div v-if="task.progress" class="text-sm text-gray-500">

                      {{ task.progress }}%

                    </div>

                    <ArrowRight v-if="index < pipeline.tasks.length - 1" :size="16" class="text-gray-300" />

                  </div>

                </div>

              </div>

            </div>



            <button

              @click="toggleHistory"

              class="w-full py-3 bg-white border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"

            >

              <Clock :size="18" />

              {{ showHistory ? '收起历史记录' : '查看历史记录' }}

            </button>



            <div v-if="showHistory" class="space-y-4">

              <div

                v-for="pipeline in pipelineHistory"

                :key="pipeline.pipeline_id"

                class="bg-white rounded-xl border border-gray-200 p-4"

              >

                <div class="flex items-center justify-between">

                  <div>

                    <p class="font-medium text-gray-900">{{ pipeline.query }}</p>

                    <p class="text-sm text-gray-500">

                      {{ formatDate(pipeline.created_at) }}

                    </p>

                  </div>

                  <div class="flex items-center gap-2">

                    <span

                      :class="[

                        'px-2 py-1 rounded text-xs',

                        stateLabels[pipeline.state as SessionState]?.color === 'green' ? 'bg-green-100 text-green-700' :

                        'bg-gray-100 text-gray-700'

                      ]"

                    >

                      {{ stateLabels[pipeline.state as SessionState]?.text }}

                    </span>

                    <span class="text-sm text-gray-500">{{ pipeline.tasks.length }}个任务</span>

                  </div>

                </div>

              </div>

            </div>

          </div>

        </template>



        <template v-if="activeTab === 'agents'">

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

            <div

              v-for="metric in agentMetrics"

              :key="metric.agent_id"

              class="bg-white rounded-xl p-6 border border-gray-200"

            >

              <div class="flex items-center justify-between mb-4">

                <h4 class="font-semibold text-gray-900">{{ metric.agent_name }}</h4>

                <Users :size="20" class="text-gray-400" />

              </div>

              <div class="space-y-3">

                <div class="flex justify-between">

                  <span class="text-sm text-gray-500">总请求数</span>

                  <span class="font-medium">{{ metric.total_requests }}</span>

                </div>

                <div class="flex justify-between">

                  <span class="text-sm text-gray-500">成功率</span>

                  <span :class="metric.success_rate >= 90 ? 'text-green-600' : metric.success_rate >= 70 ? 'text-yellow-600' : 'text-red-600'">

                    {{ metric.success_rate.toFixed(1) }}%

                  </span>

                </div>

                <div class="flex justify-between">

                  <span class="text-sm text-gray-500">平均延迟</span>

                  <span class="font-medium">{{ metric.avg_latency.toFixed(0) }}ms</span>

                </div>

              </div>

              <div v-if="metric.last_execution" class="mt-4 pt-4 border-t border-gray-100">

                <p class="text-xs text-gray-400">

                  最后执行时间 {{ formatDate(metric.last_execution) }}

                </p>

              </div>

            </div>

          </div>

        </template>

      </template>

    </div>

  </div>

</template>




