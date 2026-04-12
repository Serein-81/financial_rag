<script setup lang="ts">

import { ref, computed, onMounted } from 'vue'

import { taskManagerApi, type ScheduledTask, type TaskExecutionLog, type TaskStatistics } from '@/api/task-manager'

import {

  Calendar,

  Clock,

  Play,

  Pause,

  RefreshCw,

  Plus,

  Loader2,

  X,

  CheckCircle,

  AlertTriangle,

  Trash2,

  PlayCircle,

  Timer,

  Settings,

  BarChart3,

  FileText,

  User,

  Zap,

  ChevronRight,

  Copy,

  Check

} from 'lucide-vue-next'



const isLoading = ref(false)

const activeTab = ref<'tasks' | 'logs' | 'settings'>('tasks')

const tasks = ref<ScheduledTask[]>([])

const executionLogs = ref<TaskExecutionLog[]>([])

const statistics = ref<TaskStatistics | null>(null)

const totalTasks = ref(0)

const totalLogs = ref(0)

const currentPage = ref(1)

const pageSize = ref(10)



const showCreateModal = ref(false)

const showQuickSetupModal = ref(false)

const selectedLogDetail = ref<TaskExecutionLog | null>(null)

const showLogDetailModal = ref(false)

const isLoadingLogDetail = ref(false)

const newTask = ref({

  name: '',

  description: '',

  task_type: 'custom' as ScheduledTask['task_type'],

  frequency: 'daily' as ScheduledTask['frequency'],

  next_run_time: ''

})



const quickSetup = ref({

  type: 'tax_reminder' as string,

  tax_type: '',

  due_date: '',

  report_type: 'financial',

  frequency: 'monthly' as string,

  policy_id: '',

  anomaly_frequency: 'daily' as string

})



const taskTypeOptions = [

  { value: 'tax_reminder', label: '税务提醒' },

  { value: 'financial_report', label: '财务报告' },

  { value: 'policy_update', label: '政策更新' },

  { value: 'anomaly_check', label: '异常检测' },

  { value: 'custom', label: '自定义任务' }

]



const frequencyOptions = [

  { value: 'once', label: '仅执行一次' },

  { value: 'daily', label: '每天' },

  { value: 'weekly', label: '每周' },

  { value: 'monthly', label: '每月' },

  { value: 'quarterly', label: '每季度' }

]



const statusColors = {

  pending: 'text-blue-500 bg-blue-50',

  running: 'text-amber-500 bg-amber-50',

  completed: 'text-emerald-500 bg-emerald-50',

  failed: 'text-red-500 bg-red-50',

  paused: 'text-slate-500 bg-slate-50'

}



const taskTypeIcons: Record<string, any> = {

  tax_reminder: Calendar,

  financial_report: BarChart3,

  policy_update: Clock,

  anomaly_check: AlertTriangle,

  custom: Settings

}



async function loadTasks() {

  isLoading.value = true

  try {

    const result = await taskManagerApi.listTasks({

      page: currentPage.value,

      page_size: pageSize.value

    })

    tasks.value = result.tasks

    totalTasks.value = result.total

  } catch (e: any) {

    console.error('Failed to load tasks:', e)

  } finally {

    isLoading.value = false

  }

}



async function loadLogs() {

  isLoading.value = true

  try {

    const result = await taskManagerApi.getExecutionLogs({

      page: currentPage.value,

      page_size: pageSize.value

    })

    executionLogs.value = result.logs

    totalLogs.value = result.total

  } catch (e: any) {

    console.error('Failed to load logs:', e)

  } finally {

    isLoading.value = false

  }

}



async function loadStatistics() {

  try {

    statistics.value = await taskManagerApi.getStatistics()

  } catch (e: any) {

    console.error('Failed to load statistics:', e)

  }

}



async function viewLogDetail(logId: string) {

  isLoadingLogDetail.value = true

  showLogDetailModal.value = true

  try {

    selectedLogDetail.value = await taskManagerApi.getLogDetail(logId)

  } catch (e: any) {

    console.error('Failed to load log detail:', e)

    selectedLogDetail.value = null

  } finally {

    isLoadingLogDetail.value = false

  }

}



function copyToClipboard(text: string) {

  navigator.clipboard.writeText(text)

}



async function createTask() {

  if (!newTask.value.name || !newTask.value.next_run_time) {

    alert('请填写任务名称和执行时间')

    return

  }

  isLoading.value = true

  try {

    await taskManagerApi.createTask(newTask.value)

    showCreateModal.value = false

    await loadTasks()

    await loadStatistics()

  } catch (e: any) {

    console.error('Failed to create task:', e)

    alert('创建任务失败')

  } finally {

    isLoading.value = false

  }

}



async function quickSetupTask() {

  isLoading.value = true

  try {

    switch (quickSetup.value.type) {

      case 'tax_reminder':

        await taskManagerApi.setupTaxReminder({

          tax_type: quickSetup.value.tax_type,

          due_date: quickSetup.value.due_date

        })

        break

      case 'financial_report':

        await taskManagerApi.setupPeriodicReport({

          report_type: quickSetup.value.report_type,

          frequency: quickSetup.value.frequency as any

        })

        break

      case 'policy_update':

        await taskManagerApi.setupPolicyUpdate({

          policy_id: quickSetup.value.policy_id,

          frequency: quickSetup.value.frequency as any

        })

        break

      case 'anomaly_check':

        await taskManagerApi.setupAnomalyCheck({

          frequency: quickSetup.value.anomaly_frequency as any

        })

        break

    }

    showQuickSetupModal.value = false

    await loadTasks()

    await loadStatistics()

  } catch (e: any) {

    console.error('Failed to setup task:', e)

    alert('创建任务失败')

  } finally {

    isLoading.value = false

  }

}



async function toggleTask(task: ScheduledTask) {

  try {

    await taskManagerApi.toggleTask(task.id, !task.enabled)

    await loadTasks()

  } catch (e: any) {

    console.error('Failed to toggle task:', e)

  }

}



async function deleteTask(taskId: string) {

  if (!confirm('确定要删除这个任务吗')) return

  try {

    await taskManagerApi.deleteTask(taskId)

    await loadTasks()

    await loadStatistics()

  } catch (e: any) {

    console.error('Failed to delete task:', e)

  }

}



async function runTaskNow(taskId: string) {

  try {

    await taskManagerApi.runTaskNow(taskId)

    alert('任务已启用')

    await loadLogs()

  } catch (e: any) {

    console.error('Failed to run task:', e)

    alert('启动任务失败')

  }

}



function formatDateTime(dateStr: string): string {

  if (!dateStr) return '-'

  const date = new Date(dateStr)

  if (isNaN(date.getTime())) return '-'

  return date.toLocaleString('zh-CN', {

    year: 'numeric',

    month: '2-digit',

    day: '2-digit',

    hour: '2-digit',

    minute: '2-digit',

    second: '2-digit',

    hour12: false

  })

}



function formatDuration(ms: number): string {

  if (ms < 1000) return `${ms}ms`

  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`

  return `${(ms / 60000).toFixed(1)}min`

}



function getTaskTypeLabel(type: string): string {

  return taskTypeOptions.find(t => t.value === type)?.label || type

}



function getFrequencyLabel(freq: string): string {

  return frequencyOptions.find(f => f.value === freq)?.label || freq

}



onMounted(() => {

  loadTasks()

  loadStatistics()

})

</script>



<template>

  <div class="h-full flex flex-col bg-slate-50">

    <div class="bg-white border-b border-slate-200 px-6 py-4">

      <div class="flex items-center justify-between">

        <div class="flex items-center gap-3">

          <div class="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center">

            <Timer :size="20" class="text-amber-600" />

          </div>

          <div>

            <h1 class="text-xl font-bold text-slate-900">定时任务管理</h1>

            <p class="text-sm text-slate-500">自动化任务调度与执行监控</p>

          </div>

        </div>

        <div class="flex gap-2">

          <button

            @click="showQuickSetupModal = true"

            class="px-4 py-2 border border-amber-200 text-amber-600 rounded-lg hover:bg-amber-50 transition-colors"

          >

            快速创建          </button>

          <button

            @click="showCreateModal = true"

            class="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 flex items-center gap-2 transition-colors"

          >

            <Plus :size="16" />

            新建任务

          </button>

        </div>

      </div>



      <div class="flex gap-4 mt-4 border-b border-slate-200">

        <button

          @click="activeTab = 'tasks'; loadTasks()"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'tasks' ? 'text-amber-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          任务列表

          <div v-if="activeTab === 'tasks'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-amber-600" />

        </button>

        <button

          @click="activeTab = 'logs'; loadLogs()"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'logs' ? 'text-amber-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          执行日志

          <div v-if="activeTab === 'logs'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-amber-600" />

        </button>

        <button

          @click="activeTab = 'settings'; loadStatistics()"

          :class="[

            'pb-3 px-1 text-sm font-medium transition-colors relative',

            activeTab === 'settings' ? 'text-amber-600' : 'text-slate-500 hover:text-slate-700'

          ]"

        >

          统计概览

          <div v-if="activeTab === 'settings'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-amber-600" />

        </button>

      </div>

    </div>



    <div class="flex-1 overflow-auto p-6">

      <div v-if="isLoading" class="flex items-center justify-center h-64">

        <Loader2 :size="32" class="animate-spin text-amber-600" />

      </div>



      <template v-else>

        <div v-if="activeTab === 'tasks'" class="space-y-4">

          <div v-if="tasks.length === 0" class="bg-white rounded-xl border border-slate-200 p-8 text-center">

            <Calendar :size="48" class="mx-auto text-slate-300 mb-4" />

            <p class="text-slate-500">暂无任务</p>

            <button

              @click="showCreateModal = true"

              class="mt-4 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors"

            >

              创建第一个任务            </button>

          </div>



          <div v-else class="space-y-3">

            <div

              v-for="task in tasks"

              :key="task.id"

              class="bg-white rounded-xl border border-slate-200 p-5"

            >

              <div class="flex items-center justify-between">

                <div class="flex items-center gap-4">

                  <div class="w-12 h-12 rounded-lg flex items-center justify-center" :class="task.enabled ? 'bg-amber-100' : 'bg-slate-100'">

                    <component :is="taskTypeIcons[task.task_type] || Settings" :size="24" :class="task.enabled ? 'text-amber-600' : 'text-slate-400'" />

                  </div>

                  <div>

                    <div class="flex items-center gap-2">

                      <h3 class="font-semibold text-slate-900">{{ task.name }}</h3>

                      <span v-if="!task.enabled" class="px-2 py-0.5 text-xs rounded bg-slate-100 text-slate-500">已暂停</span>

                    </div>

                    <p class="text-sm text-slate-500 mt-1">{{ task.description || '无描述' }}</p>

                    <div class="flex items-center gap-4 mt-2 text-xs text-slate-500">

                      <span>类型: {{ getTaskTypeLabel(task.task_type) }}</span>

                      <span>频率: {{ getFrequencyLabel(task.frequency) }}</span>

                      <span>下次执行: {{ formatDateTime(task.next_run_time) }}</span>

                    </div>

                  </div>

                </div>

                <div class="flex items-center gap-2">

                  <button

                    @click="toggleTask(task)"

                    :class="[

                      'p-2 rounded-lg transition-colors',

                      task.enabled ? 'hover:bg-amber-50 text-amber-600' : 'hover:bg-emerald-50 text-emerald-600'

                    ]"

                    :title="task.enabled ? '暂停任务' : '启用任务'"

                  >

                    <Pause v-if="task.enabled" :size="18" />

                    <Play v-else :size="18" />

                  </button>

                  <button

                    @click="runTaskNow(task.id)"

                    class="p-2 hover:bg-blue-50 text-blue-600 rounded-lg transition-colors"

                    title="立即执行"

                  >

                    <PlayCircle :size="18" />

                  </button>

                  <button

                    @click="deleteTask(task.id)"

                    class="p-2 hover:bg-red-50 text-red-500 rounded-lg transition-colors"

                    title="删除任务"

                  >

                    <Trash2 :size="18" />

                  </button>

                </div>

              </div>

              <div v-if="task.last_run_time" class="mt-4 pt-4 border-t border-slate-100">

                <div class="flex items-center gap-4 text-sm">

                  <span class="text-slate-500">上次执行: {{ formatDateTime(task.last_run_time) }}</span>

                  <span v-if="task.result" :class="task.result.status === 'success' ? 'text-emerald-600' : 'text-red-600'">

                    结果: {{ task.result.status === 'success' ? '成功' : '失败' }}

                  </span>

                </div>

              </div>

            </div>

          </div>

        </div>



        <div v-else-if="activeTab === 'logs'" class="space-y-4">

          <div v-if="executionLogs.length === 0" class="bg-white rounded-xl border border-slate-200 p-8 text-center">

            <Clock :size="48" class="mx-auto text-slate-300 mb-4" />

            <p class="text-slate-500">暂无执行日志</p>

          </div>



          <div v-else class="bg-white rounded-xl border border-slate-200 overflow-hidden">

            <table class="w-full">

              <thead class="bg-slate-50">

                <tr class="text-left text-sm text-slate-500">

                  <th class="px-5 py-3">任务名称</th>

                  <th class="px-5 py-3">状态</th>

                  <th class="px-5 py-3">开始时间</th>

                  <th class="px-5 py-3">执行时长</th>

                  <th class="px-5 py-3">结果</th>

                </tr>

              </thead>

              <tbody class="divide-y divide-slate-100">

                <tr 

                  v-for="log in executionLogs" 

                  :key="log.id" 

                  class="hover:bg-slate-50 cursor-pointer transition-colors"

                  @click="viewLogDetail(log.id)"

                >

                  <td class="px-5 py-4">

                    <p class="font-medium text-slate-900">{{ log.task_name }}</p>

                    <p class="text-xs text-slate-500 mt-1">{{ log.id }}</p>

                  </td>

                  <td class="px-5 py-4">

                    <span :class="['px-2 py-1 rounded text-xs font-medium', statusColors[log.status as keyof typeof statusColors] || statusColors.pending]">

                      {{ log.status === 'completed' ? '已完成' : log.status === 'failed' ? '失败' : log.status === 'started' ? '运行中' : '已取消' }}

                    </span>

                  </td>

                  <td class="px-5 py-4 text-sm text-slate-600">

                    {{ formatDateTime(log.start_time) }}

                  </td>

                  <td class="px-5 py-4 text-sm text-slate-600">

                    {{ log.duration ? formatDuration(log.duration) : '-' }}

                  </td>

                  <td class="px-5 py-4">

                    <span v-if="log.result?.success" class="text-emerald-600 text-sm">成功</span>

                    <span v-else-if="log.error" class="text-red-600 text-sm">{{ log.error }}</span>

                    <span v-else class="text-slate-500 text-sm">-</span>

                  </td>

                </tr>

              </tbody>

            </table>

          </div>

        </div>



        <div v-else-if="activeTab === 'settings'" class="space-y-6">

          <div v-if="statistics" class="grid grid-cols-1 md:grid-cols-4 gap-4">

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">任务总数</p>

                  <p class="text-2xl font-bold text-slate-900 mt-1">{{ statistics.total_tasks }}</p>

                </div>

                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">

                  <Calendar :size="20" class="text-blue-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">活跃任务</p>

                  <p class="text-2xl font-bold text-emerald-600 mt-1">{{ statistics.active_tasks }}</p>

                </div>

                <div class="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">

                  <Play :size="20" class="text-emerald-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">今日完成</p>

                  <p class="text-2xl font-bold text-slate-900 mt-1">{{ statistics.completed_today }}</p>

                </div>

                <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">

                  <CheckCircle :size="20" class="text-amber-600" />

                </div>

              </div>

            </div>

            <div class="bg-white rounded-xl p-5 border border-slate-200">

              <div class="flex items-center justify-between">

                <div>

                  <p class="text-sm text-slate-500">今日失败</p>

                  <p class="text-2xl font-bold text-red-500 mt-1">{{ statistics.failed_today }}</p>

                </div>

                <div class="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">

                  <AlertTriangle :size="20" class="text-red-600" />

                </div>

              </div>

            </div>

          </div>



          <div v-if="statistics?.upcoming_tasks.length" class="bg-white rounded-xl border border-slate-200">

            <div class="px-5 py-4 border-b border-slate-200">

              <h3 class="font-semibold text-slate-900">即将执行的任务</h3>

            </div>

            <div class="p-5 space-y-3">

              <div

                v-for="task in statistics.upcoming_tasks"

                :key="task.id"

                class="flex items-center justify-between p-3 bg-slate-50 rounded-lg"

              >

                <div class="flex items-center gap-3">

                  <component :is="taskTypeIcons[task.task_type] || Settings" :size="18" class="text-amber-600" />

                  <span class="font-medium text-slate-900">{{ task.name }}</span>

                </div>

                <span class="text-sm text-slate-500">{{ formatDateTime(task.next_run_time) }}</span>

              </div>

            </div>

          </div>

        </div>

      </template>

    </div>



    <div

      v-if="showCreateModal"

      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"

      @click.self="showCreateModal = false"

    >

      <div class="bg-white rounded-xl w-full max-w-lg mx-4">

        <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

          <h3 class="font-semibold text-slate-900">新建任务</h3>

          <button @click="showCreateModal = false" class="p-1 hover:bg-slate-100 rounded">

            <X :size="20" class="text-slate-500" />

          </button>

        </div>

        <div class="p-5 space-y-4">

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">任务名称</label>

            <input

              v-model="newTask.name"

              type="text"

              placeholder="请输入任务名称"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"

            />

          </div>

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">任务描述</label>

            <textarea

              v-model="newTask.description"

              rows="2"

              placeholder="请输入任务描述（可选）"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"

            />

          </div>

          <div class="grid grid-cols-2 gap-4">

            <div>

              <label class="block text-sm font-medium text-slate-700 mb-1">任务类型</label>

              <select

                v-model="newTask.task_type"

                class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"

              >

                <option v-for="type in taskTypeOptions" :key="type.value" :value="type.value">

                  {{ type.label }}

                </option>

              </select>

            </div>

            <div>

              <label class="block text-sm font-medium text-slate-700 mb-1">执行频率</label>

              <select

                v-model="newTask.frequency"

                class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"

              >

                <option v-for="freq in frequencyOptions" :key="freq.value" :value="freq.value">

                  {{ freq.label }}

                </option>

              </select>

            </div>

          </div>

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">下次执行时间</label>

            <input

              v-model="newTask.next_run_time"

              type="datetime-local"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"

            />

          </div>

        </div>

        <div class="px-5 py-4 border-t border-slate-200 flex justify-end gap-3">

          <button

            @click="showCreateModal = false"

            class="px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"

          >

            取消

          </button>

          <button

            @click="createTask"

            :disabled="isLoading"

            class="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors disabled:opacity-50 flex items-center gap-2"

          >

            <Loader2 v-if="isLoading" :size="16" class="animate-spin" />

            创建任务

          </button>

        </div>

      </div>

    </div>



    <div

      v-if="showQuickSetupModal"

      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"

      @click.self="showQuickSetupModal = false"

    >

      <div class="bg-white rounded-xl w-full max-w-lg mx-4">

        <div class="px-5 py-4 border-b border-slate-200 flex items-center justify-between">

          <h3 class="font-semibold text-slate-900">快速创建任务</h3>

          <button @click="showQuickSetupModal = false" class="p-1 hover:bg-slate-100 rounded">

            <X :size="20" class="text-slate-500" />

          </button>

        </div>

        <div class="p-5 space-y-4">

          <div>

            <label class="block text-sm font-medium text-slate-700 mb-1">任务类型</label>

            <select

              v-model="quickSetup.type"

              class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"

            >

              <option value="tax_reminder">税务提醒</option>

              <option value="financial_report">定期财务报告</option>

              <option value="policy_update">政策更新订阅</option>

              <option value="anomaly_check">异常检测</option>

            </select>

          </div>



          <template v-if="quickSetup.type === 'tax_reminder'">

            <div>

              <label class="block text-sm font-medium text-slate-700 mb-1">税种</label>

              <select

                v-model="quickSetup.tax_type"

                class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"

              >

                <option value="">请选择税种</option>

                <option value="企业所得税">企业所得税</option>

                <option value="增值税">增值税</option>

                <option value="个人所得税">个人所得税</option>

              </select>

            </div>

            <div>

              <label class="block text-sm font-medium text-slate-700 mb-1">截止日期</label>

              <input

                v-model="quickSetup.due_date"

                type="date"

                class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"

              />

            </div>

          </template>



          <template v-else-if="quickSetup.type === 'financial_report'">

            <div>

              <label class="block text-sm font-medium text-slate-700 mb-1">报告类型</label>

              <select

                v-model="quickSetup.report_type"

                class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"

              >

                <option value="financial">财务健康报告</option>

                <option value="tax">税务分析报告</option>

              </select>

            </div>

            <div>

              <label class="block text-sm font-medium text-slate-700 mb-1">执行频率</label>

              <select

                v-model="quickSetup.frequency"

                class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"

              >

                <option value="daily">每天</option>

                <option value="weekly">每周</option>

                <option value="monthly">每月</option>

                <option value="quarterly">每季度</option>

              </select>

            </div>

          </template>



          <template v-else-if="quickSetup.type === 'anomaly_check'">

            <div>

              <label class="block text-sm font-medium text-slate-700 mb-1">检查频率</label>

              <select

                v-model="quickSetup.anomaly_frequency"

                class="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"

              >

                <option value="hourly">每小时</option>

                <option value="daily">每天</option>

                <option value="weekly">每周</option>

              </select>

            </div>

          </template>

        </div>

        <div class="px-5 py-4 border-t border-slate-200 flex justify-end gap-3">

          <button

            @click="showQuickSetupModal = false"

            class="px-4 py-2 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"

          >

            取消

          </button>

          <button

            @click="quickSetupTask"

            :disabled="isLoading"

            class="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors disabled:opacity-50 flex items-center gap-2"

          >

            <Loader2 v-if="isLoading" :size="16" class="animate-spin" />

            创建

          </button>

        </div>

      </div>

    </div>



    <div

      v-if="showLogDetailModal"

      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"

      @click.self="showLogDetailModal = false"

    >

      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden">

        <div class="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-gradient-to-r from-slate-50 to-white">

          <div class="flex items-center gap-3">

            <div class="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center">

              <FileText :size="20" class="text-amber-600" />

            </div>

            <div>

              <h2 class="text-lg font-semibold text-slate-900">执行日志详情</h2>

              <p class="text-sm text-slate-500">查看任务执行的完整信息</p>

            </div>

          </div>

          <button @click="showLogDetailModal = false" class="p-2 hover:bg-slate-100 rounded-lg transition-colors">

            <X :size="20" class="text-slate-500" />

          </button>

        </div>



        <div v-if="isLoadingLogDetail" class="flex items-center justify-center h-64">

          <Loader2 :size="32" class="animate-spin text-amber-600" />

        </div>



        <div v-else-if="selectedLogDetail" class="p-6 overflow-y-auto max-h-[calc(90vh-140px)] space-y-6">

          <div class="flex items-center justify-between">

            <div class="flex items-center gap-3">

              <span :class="[

                'px-3 py-1.5 rounded-lg text-sm font-medium',

                selectedLogDetail.status === 'completed' ? 'bg-emerald-100 text-emerald-700' :

                selectedLogDetail.status === 'failed' ? 'bg-red-100 text-red-700' :

                selectedLogDetail.status === 'running' ? 'bg-amber-100 text-amber-700' :

                'bg-slate-100 text-slate-700'

              ]">

                {{ selectedLogDetail.status === 'completed' ? '已完成' : 
                   selectedLogDetail.status === 'failed' ? '失败' : 
                   selectedLogDetail.status === 'running' ? '运行中' : '已取消' }}

              </span>

            </div>

            <div class="text-sm text-slate-500">

              日志 ID: {{ selectedLogDetail.id.slice(0, 8) }}...

            </div>

          </div>



          <div class="grid grid-cols-2 gap-4">

            <div class="bg-slate-50 rounded-xl p-4">

              <div class="flex items-center gap-2 text-slate-500 text-sm mb-2">

                <Clock :size="16" />

                <span>开始时间</span>

              </div>

              <p class="font-medium text-slate-900">{{ formatDateTime(selectedLogDetail.start_time) }}</p>

            </div>

            <div class="bg-slate-50 rounded-xl p-4">

              <div class="flex items-center gap-2 text-slate-500 text-sm mb-2">

                <Timer :size="16" />

                <span>执行时长</span>

              </div>

              <p class="font-medium text-slate-900">{{ selectedLogDetail.duration ? formatDuration(selectedLogDetail.duration) : '-' }}</p>

            </div>

            <div class="bg-slate-50 rounded-xl p-4">

              <div class="flex items-center gap-2 text-slate-500 text-sm mb-2">

                <Calendar :size="16" />

                <span>任务 ID</span>

              </div>

              <div class="flex items-center gap-2">

                <p class="font-medium text-slate-900 font-mono text-sm">{{ selectedLogDetail.task_id }}</p>

                <button @click="copyToClipboard(selectedLogDetail.task_id)" class="p-1 hover:bg-slate-200 rounded transition-colors">

                  <Copy :size="14" class="text-slate-400" />

                </button>

              </div>

            </div>

            <div class="bg-slate-50 rounded-xl p-4">

              <div class="flex items-center gap-2 text-slate-500 text-sm mb-2">

                <Zap :size="16" />

                <span>执行类型</span>

              </div>

              <p class="font-medium text-slate-900">{{ selectedLogDetail.execution_type === 'scheduled' ? '定时执行' : '手动执行' }}</p>

            </div>

          </div>



          <div v-if="selectedLogDetail.result" class="bg-gradient-to-br from-slate-50 to-white rounded-xl border border-slate-200">

            <div class="px-4 py-3 border-b border-slate-200 flex items-center gap-2">

              <CheckCircle :size="16" class="text-emerald-600" />

              <span class="font-medium text-slate-900">执行结果</span>

            </div>

            <div class="p-4">

              <div class="grid grid-cols-3 gap-4 mb-4">

                <div>

                  <p class="text-sm text-slate-500">状态</p>

                  <p :class="selectedLogDetail.result.success ? 'text-emerald-600 font-medium' : 'text-red-600 font-medium'">

                    {{ selectedLogDetail.result.success ? '成功' : '失败' }}

                  </p>

                </div>

                <div v-if="selectedLogDetail.result.message">

                  <p class="text-sm text-slate-500">消息</p>

                  <p class="text-slate-900">{{ selectedLogDetail.result.message }}</p>

                </div>

              </div>

              <div v-if="selectedLogDetail.result.data" class="mt-4">

                <p class="text-sm text-slate-500 mb-2">返回数据</p>

                <pre class="bg-slate-900 text-slate-100 p-4 rounded-lg text-xs overflow-x-auto">{{ JSON.stringify(selectedLogDetail.result.data, null, 2) }}</pre>

              </div>

            </div>

          </div>



          <div v-if="selectedLogDetail.error" class="bg-red-50 rounded-xl border border-red-200">

            <div class="px-4 py-3 border-b border-red-200 flex items-center gap-2">

              <AlertTriangle :size="16" class="text-red-600" />

              <span class="font-medium text-red-900">错误信息</span>

            </div>

            <div class="p-4">

              <p class="text-red-800 whitespace-pre-wrap">{{ selectedLogDetail.error }}</p>

            </div>

          </div>



          <div v-if="selectedLogDetail.error_traceback" class="bg-slate-900 rounded-xl overflow-hidden">

            <div class="px-4 py-3 border-b border-slate-700 flex items-center justify-between">

              <div class="flex items-center gap-2">

                <FileText :size="16" class="text-slate-400" />

                <span class="font-medium text-slate-300">完整堆栈跟踪</span>

              </div>

              <button @click="copyToClipboard(selectedLogDetail.error_traceback)" class="flex items-center gap-1 px-2 py-1 bg-slate-800 text-slate-400 rounded hover:bg-slate-700 transition-colors text-xs">

                <Copy :size="12" />

                复制

              </button>

            </div>

            <pre class="p-4 text-xs text-red-400 overflow-x-auto font-mono leading-relaxed">{{ selectedLogDetail.error_traceback }}</pre>

          </div>



          <div class="bg-gradient-to-br from-amber-50 to-white rounded-xl border border-amber-200">

            <div class="px-4 py-3 border-b border-amber-200 flex items-center gap-2">

              <Clock :size="16" class="text-amber-600" />

              <span class="font-medium text-amber-900">创建时间</span>

            </div>

            <div class="p-4">

              <p class="text-amber-800">{{ formatDateTime(selectedLogDetail.created_at) }}</p>

            </div>

          </div>

        </div>

      </div>

    </div>

  </div>

</template>

