<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import {
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  Trash2,
  RefreshCw,
  Database,
  Loader2,
  AlertCircle,
  X,
  Eye
} from 'lucide-vue-next'

const knowledgeStore = useKnowledgeStore()

const isRefreshing = ref(false)
const showDocDetailModal = ref(false)
const selectedDoc = ref<any>(null)

const selectedKB = computed(() => knowledgeStore.selectedKnowledgeBase)
const documents = computed(() => {
  if (!selectedKB.value) return []
  return knowledgeStore.documents[selectedKB.value.id] || []
})

onMounted(async () => {
  await knowledgeStore.fetchKnowledgeBases()
  if (selectedKB.value) {
    await knowledgeStore.fetchDocuments(selectedKB.value.id)
  }
})

watch(() => selectedKB.value?.id, async (newId) => {
  if (newId) {
    await knowledgeStore.fetchDocuments(newId)
  }
})

async function refreshDocuments() {
  if (!selectedKB.value) return
  isRefreshing.value = true
  await knowledgeStore.fetchDocuments(selectedKB.value.id)
  isRefreshing.value = false
}

function viewDocumentDetail(doc: any) {
  selectedDoc.value = doc
  showDocDetailModal.value = true
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'text-green-600'
    case 'failed':
      return 'text-red-600'
    case 'processing':
      return 'text-emerald-600'
    case 'pending':
      return 'text-yellow-600'
    default:
      return 'text-gray-500'
  }
}

function getStatusBgColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'bg-green-50 border-green-200'
    case 'failed':
      return 'bg-red-50 border-red-200'
    case 'processing':
      return 'bg-emerald-50 border-emerald-200'
    case 'pending':
      return 'bg-yellow-50 border-yellow-200'
    default:
      return 'bg-gray-50 border-gray-200'
  }
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'completed':
      return CheckCircle
    case 'failed':
      return XCircle
    case 'processing':
      return Loader2
    default:
      return Clock
  }
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    completed: '已完成',
    failed: '失败',
    processing: '处理中',
    pending: '等待中'
  }
  return labels[status] || status
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-slate-100 via-emerald-50/30 to-teal-50/30 h-full">
    <!-- Top Bar -->
    <div class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center">
          <FileText :size="20" class="text-white" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-gray-900">文档管理</h2>
          <p class="text-xs text-gray-500">查看和管理知识库文档</p>
        </div>
      </div>
      
      <div class="flex items-center gap-3">
        <!-- KB Selector -->
        <div class="flex items-center gap-2 px-4 py-2 bg-gray-50 rounded-xl border border-gray-200">
          <Database :size="16" class="text-gray-500" />
          <select
            v-model="knowledgeStore.selectedKnowledgeBaseId"
            class="bg-transparent text-sm text-gray-700 outline-none cursor-pointer"
          >
            <option :value="null">选择知识库</option>
            <option v-for="kb in knowledgeStore.knowledgeBases" :key="kb.id" :value="kb.id">
              {{ kb.name }}
            </option>
          </select>
        </div>
        
        <button
          @click="refreshDocuments"
          :disabled="isRefreshing || !selectedKB"
          class="px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-xl hover:bg-gray-50 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <RefreshCw :size="16" :class="{ 'animate-spin': isRefreshing }" />
          <span class="text-sm font-medium">刷新</span>
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 overflow-y-auto p-8">
      <!-- No KB Selected -->
      <div v-if="!selectedKB" class="h-full flex items-center justify-center">
        <div class="text-center space-y-4 max-w-md">
          <div class="w-20 h-20 bg-gradient-to-br from-gray-200 to-gray-300 rounded-3xl flex items-center justify-center mx-auto">
            <Database :size="40" class="text-gray-500" />
          </div>
          <h3 class="text-xl font-bold text-gray-900">请选择知识库</h3>
          <p class="text-gray-600">在右上角选择一个知识库以查看文档</p>
        </div>
      </div>

      <!-- Loading -->
      <div v-else-if="knowledgeStore.isLoading" class="h-full flex items-center justify-center">
        <div class="text-center space-y-4">
          <Loader2 :size="48" class="mx-auto text-emerald-500 animate-spin" />
          <p class="text-gray-600">加载中...</p>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else-if="documents.length === 0" class="h-full flex items-center justify-center">
        <div class="text-center space-y-4 max-w-md">
          <div class="w-20 h-20 bg-gradient-to-br from-gray-200 to-gray-300 rounded-3xl flex items-center justify-center mx-auto">
            <FileText :size="40" class="text-gray-500" />
          </div>
          <h3 class="text-xl font-bold text-gray-900">暂无文档</h3>
          <p class="text-gray-600">这个知识库还没有上传任何文档</p>
          <router-link
            to="/upload"
            class="inline-block px-6 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all shadow-lg font-medium"
          >
            立即上传
          </router-link>
        </div>
      </div>

      <!-- Documents Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-7xl mx-auto">
        <div
          v-for="doc in documents"
          :key="doc.id"
          class="bg-white rounded-2xl shadow-md hover:shadow-xl transition-all duration-300 overflow-hidden border border-gray-200"
        >
          <!-- Header -->
          <div class="p-6 border-b border-gray-100">
            <div class="flex items-start gap-3">
              <div class="w-12 h-12 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md">
                <FileText :size="24" class="text-white" />
              </div>
              <div class="flex-1 min-w-0">
                <h3 class="font-semibold text-gray-900 truncate mb-1" :title="doc.filename">
                  {{ doc.filename }}
                </h3>
                <div
                  class="inline-flex items-center gap-2 px-3 py-1 rounded-lg text-xs font-medium border"
                  :class="getStatusBgColor(doc.status)"
                >
                  <component
                    :is="getStatusIcon(doc.status)"
                    :size="14"
                    :class="[getStatusColor(doc.status), doc.status === 'processing' ? 'animate-spin' : '']"
                  />
                  <span :class="getStatusColor(doc.status)">
                    {{ getStatusLabel(doc.status) }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Body -->
          <div class="p-6 space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <p class="text-xs text-gray-500 mb-1">文件大小</p>
                <p class="text-sm font-medium text-gray-900">{{ formatFileSize(doc.file_size) }}</p>
              </div>
              <div>
                <p class="text-xs text-gray-500 mb-1">文件类型</p>
                <p class="text-sm font-medium text-gray-900 truncate" :title="doc.file_type || '-'">
                  {{ doc.file_type || '-' }}
                </p>
              </div>
            </div>

            <div>
              <p class="text-xs text-gray-500 mb-1">上传时间</p>
              <p class="text-sm text-gray-700">{{ formatDate(doc.created_at) }}</p>
            </div>

            <!-- Error Message -->
            <div v-if="doc.error_msg" class="bg-red-50 border border-red-200 rounded-xl p-3">
              <div class="flex items-start gap-2">
                <AlertCircle :size="16" class="text-red-500 flex-shrink-0 mt-0.5" />
                <p class="text-xs text-red-700">{{ doc.error_msg }}</p>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="px-6 py-4 bg-gray-50 border-t border-gray-100 flex gap-2">
            <button
              @click="viewDocumentDetail(doc)"
              class="flex-1 py-2.5 px-4 bg-white border border-gray-200 text-gray-700 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-600 rounded-xl transition-all flex items-center justify-center gap-2 text-sm font-medium"
            >
              <Eye :size="16" />
              查看详情
            </button>
            <button
              class="flex-1 py-2.5 px-4 bg-white border border-gray-200 text-gray-700 hover:border-red-300 hover:bg-red-50 hover:text-red-600 rounded-xl transition-all flex items-center justify-center gap-2 text-sm font-medium"
            >
              <Trash2 :size="16" />
              删除文档
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Document Detail Modal -->
    <div
      v-if="showDocDetailModal && selectedDoc"
      class="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50 overflow-y-auto"
      @click.self="showDocDetailModal = false"
    >
      <div class="bg-white rounded-2xl p-8 max-w-3xl w-full shadow-2xl my-8">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-2xl font-bold text-gray-900">文档详情</h3>
          <button @click="showDocDetailModal = false" class="p-2 hover:bg-gray-100 rounded-lg">
            <X :size="20" class="text-gray-500" />
          </button>
        </div>
        
        <div class="space-y-6">
          <!-- 基本信息 -->
          <div class="bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl p-6">
            <div class="flex items-start gap-4">
              <div class="w-16 h-16 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg">
                <FileText :size="32" class="text-white" />
              </div>
              <div class="flex-1">
                <h4 class="text-lg font-bold text-gray-900 mb-2">{{ selectedDoc.filename }}</h4>
                <div class="flex items-center gap-3 flex-wrap">
                  <div
                    class="inline-flex items-center gap-2 px-3 py-1 rounded-lg text-sm font-medium border"
                    :class="getStatusBgColor(selectedDoc.status)"
                  >
                    <component
                      :is="getStatusIcon(selectedDoc.status)"
                      :size="16"
                      :class="[getStatusColor(selectedDoc.status), selectedDoc.status === 'processing' ? 'animate-spin' : '']"
                    />
                    <span :class="getStatusColor(selectedDoc.status)">
                      {{ getStatusLabel(selectedDoc.status) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 详细信息 -->
          <div class="grid grid-cols-2 gap-4">
            <div class="bg-gray-50 rounded-xl p-4">
              <p class="text-xs text-gray-500 mb-1">文档 ID</p>
              <p class="text-sm font-mono text-gray-900 break-all">{{ selectedDoc.id }}</p>
            </div>
            
            <div class="bg-gray-50 rounded-xl p-4">
              <p class="text-xs text-gray-500 mb-1">知识库 ID</p>
              <p class="text-sm font-mono text-gray-900 break-all">{{ selectedDoc.kb_id }}</p>
            </div>
            
            <div class="bg-gray-50 rounded-xl p-4">
              <p class="text-xs text-gray-500 mb-1">文件大小</p>
              <p class="text-sm font-medium text-gray-900">{{ formatFileSize(selectedDoc.file_size) }}</p>
            </div>
            
            <div class="bg-gray-50 rounded-xl p-4">
              <p class="text-xs text-gray-500 mb-1">文件类型</p>
              <p class="text-sm font-medium text-gray-900">{{ selectedDoc.file_type || '-' }}</p>
            </div>
            
            <div class="bg-gray-50 rounded-xl p-4">
              <p class="text-xs text-gray-500 mb-1">上传时间</p>
              <p class="text-sm font-medium text-gray-900">{{ formatDate(selectedDoc.created_at) }}</p>
            </div>
            
            <div class="bg-emerald-50 rounded-xl p-4 border border-emerald-200">
              <p class="text-xs text-emerald-600 mb-1">切块数量</p>
              <p class="text-lg font-bold text-emerald-700">{{ selectedDoc.chunk_count || 0 }}</p>
            </div>
            
            <div class="bg-gray-50 rounded-xl p-4">
              <p class="text-xs text-gray-500 mb-1">文件路径</p>
              <p class="text-sm font-mono text-gray-900 truncate" :title="selectedDoc.file_path">
                {{ selectedDoc.file_path }}
              </p>
            </div>
          </div>

          <!-- 元信息 -->
          <div v-if="selectedDoc.meta_info && Object.keys(selectedDoc.meta_info).length > 0" class="bg-gray-50 rounded-xl p-4">
            <p class="text-sm font-medium text-gray-900 mb-3">元信息</p>
            <pre class="text-xs text-gray-700 bg-white p-3 rounded-lg overflow-x-auto">{{ JSON.stringify(selectedDoc.meta_info, null, 2) }}</pre>
          </div>

          <!-- 错误信息 -->
          <div v-if="selectedDoc.error_msg" class="bg-red-50 border border-red-200 rounded-xl p-4">
            <div class="flex items-start gap-3">
              <XCircle :size="20" class="text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p class="text-sm font-medium text-red-900 mb-1">错误信息</p>
                <p class="text-sm text-red-700">{{ selectedDoc.error_msg }}</p>
              </div>
            </div>
          </div>

          <!-- 处理提示 -->
          <div v-if="selectedDoc.status === 'completed'" class="bg-green-50 border border-green-200 rounded-xl p-4">
            <div class="flex items-start gap-3">
              <CheckCircle :size="20" class="text-green-500 flex-shrink-0 mt-0.5" />
              <div>
                <p class="text-sm font-medium text-green-900 mb-1">处理完成</p>
                <p class="text-sm text-green-700">文档已成功向量化，可以在对话中使用</p>
              </div>
            </div>
          </div>

          <div v-else-if="selectedDoc.status === 'processing'" class="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
            <div class="flex items-start gap-3">
              <Loader2 :size="20" class="text-emerald-500 flex-shrink-0 mt-0.5 animate-spin" />
              <div>
                <p class="text-sm font-medium text-emerald-900 mb-1">正在处理</p>
                <p class="text-sm text-emerald-700">系统正在进行文本提取、切分和向量化，请稍候...</p>
              </div>
            </div>
          </div>

          <div v-else-if="selectedDoc.status === 'pending'" class="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
            <div class="flex items-start gap-3">
              <Clock :size="20" class="text-yellow-500 flex-shrink-0 mt-0.5" />
              <div>
                <p class="text-sm font-medium text-yellow-900 mb-1">等待处理</p>
                <p class="text-sm text-yellow-700">文档已上传，等待系统处理</p>
              </div>
            </div>
          </div>
        </div>
        
        <div class="flex gap-3 mt-6">
          <button
            @click="showDocDetailModal = false"
            class="flex-1 py-3 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-all font-medium"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
