<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { logsApi } from '@/api/logs'
import type { LogEntry, LogsResponse } from '@/api/logs'
import {
  ScrollText,
  Search,
  RefreshCw,
  Download,
  Trash2,
  Loader2,
  AlertCircle,
  Filter,
  MessageSquare
} from 'lucide-vue-next'

const isLoading = ref(false)
const error = ref('')

const logs = ref<LogEntry[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)

const filters = ref({
  level: '',
  module: '',
  keyword: ''
})

const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
const modules = ['auth', 'chat', 'knowledge', 'search', 'agent', 'system']

onMounted(async () => {
  await loadLogs()
})

async function loadLogs() {
  try {
    isLoading.value = true
    error.value = ''

    const response = await logsApi.getLogs({
      page: page.value,
      page_size: pageSize.value,
      level: filters.value.level || undefined,
      module: filters.value.module || undefined,
      keyword: filters.value.keyword || undefined
    })

    logs.value = response.logs
    total.value = response.total
  } catch (err: any) {
    error.value = err.message || '加载日志失败'
  } finally {
    isLoading.value = false
  }
}

async function clearFilters() {
  filters.value = {
    level: '',
    module: '',
    keyword: ''
  }
  page.value = 1
  await loadLogs()
}

async function exportLogs() {
  try {
    const blob = await logsApi.exportLogs({
      level: filters.value.level || undefined,
      module: filters.value.module || undefined,
      keyword: filters.value.keyword || undefined
    })

    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  } catch (err: any) {
    error.value = err.message || '导出日志失败'
  }
}

function getLevelColor(level: string): string {
  const colors: Record<string, string> = {
    'DEBUG': 'bg-gray-100 text-gray-700',
    'INFO': 'bg-blue-100 text-blue-700',
    'WARNING': 'bg-yellow-100 text-yellow-700',
    'ERROR': 'bg-red-100 text-red-700'
  }
  return colors[level] || colors['INFO']
}

function formatTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleString('zh-CN')
}

function getTotalPages(): number {
  return Math.ceil(total.value / pageSize.value)
}
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-6 py-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <ScrollText :size="28" class="text-blue-600" />
            日志查看
          </h1>
          <p class="text-sm text-gray-500 mt-1">共 {{ total }} 条日志</p>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="loadLogs"
            :disabled="isLoading"
            class="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Loader2 v-if="isLoading" :size="18" class="animate-spin" />
            <RefreshCw v-else :size="18" />
            刷新
          </button>
          <button
            @click="exportLogs"
            :disabled="isLoading || logs.length === 0"
            class="px-4 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Download :size="18" />
            导出
          </button>
        </div>
      </div>

      <!-- Filters -->
      <div class="flex gap-4 mt-4">
        <div class="flex items-center gap-2">
          <Filter :size="18" class="text-gray-500" />
          <select
            v-model="filters.level"
            class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-500 outline-none"
          >
            <option value="">所有级别</option>
            <option v-for="level in levels" :key="level" :value="level">{{ level }}</option>
          </select>
        </div>

        <div class="flex items-center gap-2">
          <select
            v-model="filters.module"
            class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-500 outline-none"
          >
            <option value="">所有模块</option>
            <option v-for="module in modules" :key="module" :value="module">{{ module }}</option>
          </select>
        </div>

        <div class="flex-1 flex items-center gap-2">
          <div class="relative flex-1 max-w-md">
            <Search :size="18" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              v-model="filters.keyword"
              type="text"
              placeholder="搜索关键词..."
              class="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-500 outline-none"
              @keydown.enter="loadLogs"
            />
          </div>
        </div>

        <button
          @click="loadLogs"
          class="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700"
        >
          搜索
        </button>

        <button
          @click="clearFilters"
          class="px-4 py-2 text-gray-700 font-medium rounded-lg hover:bg-gray-100"
        >
          重置
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6">
      <!-- Error Message -->
      <div v-if="error" class="mb-4 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
        <AlertCircle :size="20" class="text-red-500" />
        <p class="text-sm text-red-700">{{ error }}</p>
      </div>

      <!-- Loading -->
      <div v-if="isLoading && logs.length === 0" class="flex items-center justify-center h-64">
        <Loader2 :size="32" class="animate-spin text-blue-600" />
      </div>

      <!-- Empty State -->
      <div v-else-if="logs.length === 0" class="flex flex-col items-center justify-center h-64">
        <div class="bg-blue-50 rounded-full p-6 mb-4">
          <ScrollText :size="48" class="text-blue-400" />
        </div>
        <h3 class="text-lg font-medium text-gray-700 mb-2">暂无日志记录</h3>
        <p class="text-sm text-gray-500 text-center max-w-md">
          {{ error ? '' : '您还没有任何系统日志。这可能是因为：' }}
        </p>
        <ul v-if="!error" class="mt-2 text-sm text-gray-500 space-y-1 text-center">
          <li>• 刚刚完成注册，尚未进行任何操作</li>
          <li>• 您的操作尚未产生系统日志</li>
          <li>• 尝试与智能助手对话，系统会记录您的操作</li>
        </ul>
        <button
          @click="$router.push('/')"
          class="mt-4 px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 flex items-center gap-2"
        >
          <MessageSquare :size="18" />
          去发起对话
        </button>
      </div>

      <!-- Logs List -->
      <div v-else class="space-y-3">
        <div
          v-for="(log, index) in logs"
          :key="index"
          class="bg-white rounded-lg border border-gray-200 p-4"
        >
          <div class="flex items-start justify-between mb-2">
            <div class="flex items-center gap-3">
              <span :class="['px-2 py-1 text-xs font-medium rounded', getLevelColor(log.level)]">
                {{ log.level }}
              </span>
              <span class="text-sm text-gray-500">{{ log.module }}</span>
            </div>
            <span class="text-xs text-gray-400">{{ formatTimestamp(log.timestamp) }}</span>
          </div>
          <p class="text-gray-900 font-mono text-sm">{{ log.message }}</p>
          <div v-if="log.details" class="mt-2 text-xs text-gray-500 bg-gray-50 p-2 rounded">
            <pre class="whitespace-pre-wrap">{{ JSON.stringify(log.details, null, 2) }}</pre>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="getTotalPages() > 1" class="mt-6 flex items-center justify-center gap-2">
        <button
          @click="page = Math.max(1, page - 1); loadLogs()"
          :disabled="page === 1"
          class="px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          上一页
        </button>

        <span class="px-4 py-2 text-gray-600">
          第 {{ page }} / {{ getTotalPages() }} 页
        </span>

        <button
          @click="page = Math.min(getTotalPages(), page + 1); loadLogs()"
          :disabled="page === getTotalPages()"
          class="px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>
