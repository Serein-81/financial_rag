<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useKnowledgeStore } from '@/stores/knowledge'
import { 
  ArrowLeft, Database, FileText, CheckCircle, Clock, XCircle, Loader2,
  Upload, X
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const knowledgeStore = useKnowledgeStore()

const kbId = route.params.id as string
const showUploadModal = ref(false)
const selectedFile = ref<File | null>(null)
const isUploading = ref(false)
const uploadResult = ref<any>(null)
const showDocDetailModal = ref(false)
const selectedDoc = ref<any>(null)

const knowledgeBase = computed(() => {
  return knowledgeStore.knowledgeBases.find(kb => kb.id === kbId)
})

const documents = computed(() => {
  return knowledgeStore.documents[kbId] || []
})

onMounted(async () => {
  await knowledgeStore.fetchKnowledgeBases()
  if (kbId) {
    await knowledgeStore.fetchDocuments(kbId)
  }
})

function goBack() {
  router.push('/')
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    selectedFile.value = file
  }
}

async function handleUpload() {
  if (!selectedFile.value || !kbId || isUploading.value) return

  isUploading.value = true
  uploadResult.value = null

  try {
    const result = await knowledgeStore.uploadFile(kbId, selectedFile.value)
    uploadResult.value = {
      success: true,
      ...result
    }
    await knowledgeStore.fetchDocuments(kbId)
  } catch (error: any) {
    uploadResult.value = {
      success: false,
      error: error.message || '上传失败'
    }
  } finally {
    isUploading.value = false
  }
}

function clearFile() {
  selectedFile.value = null
  uploadResult.value = null
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed': return 'text-green-600'
    case 'failed': return 'text-red-600'
    case 'processing': return 'text-emerald-600'
    case 'pending': return 'text-yellow-600'
    default: return 'text-gray-500'
  }
}

function getStatusBgColor(status: string): string {
  switch (status) {
    case 'completed': return 'bg-green-50 border-green-200'
    case 'failed': return 'bg-red-50 border-red-200'
    case 'processing': return 'bg-emerald-50 border-emerald-200'
    case 'pending': return 'bg-yellow-50 border-yellow-200'
    default: return 'bg-gray-50 border-gray-200'
  }
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'completed': return CheckCircle
    case 'failed': return XCircle
    case 'processing': return Loader2
    default: return Clock
  }
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    completed: '已完成',
    failed: '失败',
    ready: '已完成',
    processing: '处理中',
    pending: '等待中'
  }
  return labels[status] || status
}

function getStatusDescription(status: string): string {
  const desc: Record<string, string> = {
    ready: '文档已处理完成，向量已入库，可到对话页检索',
    completed: '文档已处理完成，向量已入库，可到对话页检索',
    failed: '文档处理出错，请检查文件格式后重新上传',
    processing: '文档正在后台解析和向量化，请稍候',
    pending: '文档已上传，等待后台处理'
  }
  return desc[status] || status
}

function getDomainLabel(meta_info: any): string {
  if (!meta_info || !meta_info.domain) return ''
  const labels: Record<string, string> = {
    finance: '财务类 FinancialChunker',
    tax: '税务类 TaxChunker',
    legal: '法务类 LegalChunker',
    general: '通用类 GeneralChunker'
  }
  return labels[meta_info.domain] || meta_info.domain
}

function getDomainColor(meta_info: any): string {
  if (!meta_info || !meta_info.domain) return ''
  const colors: Record<string, string> = {
    finance: 'bg-amber-50 border-amber-200 text-amber-700',
    tax: 'bg-blue-50 border-blue-200 text-blue-700',
    legal: 'bg-purple-50 border-purple-200 text-purple-700',
    general: 'bg-gray-50 border-gray-200 text-gray-600'
  }
  return colors[meta_info.domain] || 'bg-gray-50 border-gray-200 text-gray-600'
}

function viewDocumentDetail(doc: any) {
  selectedDoc.value = doc
  showDocDetailModal.value = true
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
  <div class="min-h-screen bg-gradient-to-br from-slate-100 via-emerald-50/30 to-teal-50/30">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 shadow-sm">
      <div class="max-w-7xl mx-auto px-6 py-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <button
              @click="goBack"
              class="p-2 hover:bg-gray-100 rounded-xl transition-all"
            >
              <ArrowLeft :size="20" class="text-gray-600" />
            </button>
            <div class="flex items-center gap-3">
              <div class="w-12 h-12 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center shadow-lg">
                <Database :size="24" class="text-white" />
              </div>
              <div>
                <h1 class="text-2xl font-bold text-gray-900">{{ knowledgeBase?.name || '知识库详情' }}</h1>
                <p class="text-sm text-gray-500">{{ knowledgeBase?.description || '暂无描述' }}</p>
              </div>
            </div>
          </div>
          
          <button
            @click="showUploadModal = true"
            class="px-6 py-3 bg-gradient-to-r from-orange-500 to-red-600 text-white rounded-xl hover:from-orange-600 hover:to-red-700 transition-all flex items-center gap-2 shadow-lg"
          >
            <Upload :size="20" />
            <span class="font-medium">上传文档</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Content -->
    <div class="max-w-7xl mx-auto px-6 py-8">
      <!-- Stats -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div class="bg-white rounded-2xl p-6 shadow-md border border-gray-100">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-500 mb-1">总文档数</p>
              <p class="text-3xl font-bold text-gray-900">{{ documents.length }}</p>
            </div>
            <div class="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center">
              <FileText :size="24" class="text-emerald-600" />
            </div>
          </div>
        </div>
        
        <div class="bg-white rounded-2xl p-6 shadow-md border border-gray-100">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-500 mb-1">已完成</p>
              <p class="text-3xl font-bold text-green-600">
                {{ documents.filter(d => d.status === 'completed').length }}
              </p>
            </div>
            <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
              <CheckCircle :size="24" class="text-green-600" />
            </div>
          </div>
        </div>
        
        <div class="bg-white rounded-2xl p-6 shadow-md border border-gray-100">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-500 mb-1">处理中</p>
              <p class="text-3xl font-bold text-emerald-600">
                {{ documents.filter(d => d.status === 'processing').length }}
              </p>
            </div>
            <div class="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center">
              <Loader2 :size="24" class="text-emerald-600 animate-spin" />
            </div>
          </div>
        </div>
        
        <div class="bg-white rounded-2xl p-6 shadow-md border border-gray-100">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-500 mb-1">失败</p>
              <p class="text-3xl font-bold text-red-600">
                {{ documents.filter(d => d.status === 'failed').length }}
              </p>
            </div>
            <div class="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center">
              <XCircle :size="24" class="text-red-600" />
            </div>
          </div>
        </div>
      </div>

      <!-- Documents List -->
      <div class="bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden">
        <div class="p-6 border-b border-gray-200">
          <h2 class="text-xl font-bold text-gray-900 flex items-center gap-2">
            <FileText :size="24" />
            文档列表
          </h2>
        </div>
        
        <div v-if="documents.length === 0" class="p-12 text-center">
          <FileText :size="64" class="mx-auto text-gray-300 mb-4" />
          <p class="text-gray-500 text-lg">暂无文档</p>
          <p class="text-gray-400 text-sm mt-2">点击右上角"上传文档"按钮添加文档</p>
        </div>
        
        <div v-else class="divide-y divide-gray-100">
          <div
            v-for="doc in documents"
            :key="doc.id"
            class="p-6 hover:bg-gray-50 transition-all group"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="flex items-start gap-4 flex-1 min-w-0">
                <div class="w-12 h-12 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md">
                  <FileText :size="24" class="text-white" />
                </div>
                
                <div class="flex-1 min-w-0">
                  <h3 class="text-lg font-semibold text-gray-900 mb-2 truncate">{{ doc.filename }}</h3>
                  
                  <div class="flex items-center gap-4 flex-wrap mb-3">
                    <div
                      class="inline-flex items-center gap-2 px-3 py-1 rounded-lg text-sm font-medium border"
                      :class="getStatusBgColor(doc.status)"
                    >
                      <component
                        :is="getStatusIcon(doc.status)"
                        :size="16"
                        :class="[getStatusColor(doc.status), doc.status === 'processing' ? 'animate-spin' : '']"
                      />
                      <span
                        :class="getStatusColor(doc.status)"
                        :title="getStatusDescription(doc.status)"
                      >
                        {{ getStatusLabel(doc.status) }}
                      </span>
                    </div>

                    <span
                      v-if="doc.meta_info?.domain"
                      class="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-medium border"
                      :class="getDomainColor(doc.meta_info)"
                      :title="'采用策略: ' + getDomainLabel(doc.meta_info)"
                    >
                      {{ getDomainLabel(doc.meta_info) }}
                    </span>

                    <span class="text-sm text-gray-500">{{ formatFileSize(doc.file_size) }}</span>
                    <span class="text-sm text-gray-500">{{ formatDate(doc.created_at) }}</span>
                  </div>
                  
                  <p v-if="doc.error_msg" class="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
                    {{ doc.error_msg }}
                  </p>
                </div>
              </div>
              
              <div class="flex items-center gap-2 flex-shrink-0">
                <button
                  @click="viewDocumentDetail(doc)"
                  class="px-4 py-2 bg-emerald-100 text-emerald-600 rounded-xl hover:bg-emerald-200 transition-all font-medium"
                >
                  查看详情
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Upload Modal -->
    <div
      v-if="showUploadModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
      @click.self="showUploadModal = false"
    >
      <div class="bg-white rounded-2xl p-8 max-w-2xl w-full shadow-2xl">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-2xl font-bold text-gray-900">上传文档</h3>
          <button @click="showUploadModal = false" class="p-2 hover:bg-gray-100 rounded-lg">
            <X :size="20" class="text-gray-500" />
          </button>
        </div>
        
        <!-- File Upload Area -->
        <div
          class="border-2 border-dashed rounded-2xl p-8 text-center transition-all duration-300 cursor-pointer mb-6"
          :class="[
            selectedFile 
              ? 'border-green-400 bg-green-50/50' 
              : 'border-gray-300 bg-white hover:border-gray-400'
          ]"
          @click="$refs.fileInput?.click()"
        >
          <input
            ref="fileInput"
            type="file"
            class="hidden"
            accept=".pdf,.doc,.docx,.txt,.md,.csv,.png,.jpg,.jpeg,.bmp,.tiff"
            @change="handleFileSelect"
          />

          <div v-if="!selectedFile" class="space-y-3">
            <Upload :size="48" class="mx-auto text-gray-400" />
            <div>
              <p class="text-lg font-medium text-gray-900">选择文件上传</p>
              <div class="mt-2 inline-block px-3 py-1.5 bg-orange-50 border border-orange-200 rounded-lg">
                <p class="text-xs text-orange-700 font-medium">支持文件类型：</p>
                <p class="text-xs text-orange-600 mt-0.5">
                  PDF · DOC · DOCX · XLS · XLSX · TXT · MD · CSV · PNG · JPG · JPEG · BMP · TIFF
                </p>
              </div>
              <div class="mt-2 inline-block px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg">
                <p class="text-xs text-blue-700">
                  <span class="font-medium">提示：</span>文件名含「财务」「税务」「合同」等关键词，系统自动采用对应的优化切块策略，提升检索精度。
                </p>
                <p class="text-xs text-blue-500 mt-1">状态流转：等待中 → 处理中 → 已完成 → 可检索</p>
              </div>
            </div>
          </div>

          <div v-else class="space-y-3">
            <FileText :size="48" class="mx-auto text-emerald-500" />
            <div>
              <p class="text-lg font-medium text-gray-900 truncate">{{ selectedFile.name }}</p>
              <p class="text-sm text-gray-600">{{ formatFileSize(selectedFile.size) }}</p>
            </div>
            <button
              @click.stop="clearFile"
              class="mt-3 px-4 py-2 bg-gray-100 hover:bg-red-50 text-gray-700 hover:text-red-600 rounded-lg transition-all inline-flex items-center gap-2"
            >
              <X :size="16" />
              清除
            </button>
          </div>
        </div>

        <!-- Upload Button -->
        <button
          v-if="selectedFile"
          @click="handleUpload"
          :disabled="isUploading"
          class="w-full py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl hover:from-green-600 hover:to-emerald-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg flex items-center justify-center gap-2 font-medium mb-6"
        >
          <Upload :size="20" v-if="!isUploading" />
          <Loader2 :size="20" class="animate-spin" v-else />
          <span>{{ isUploading ? '上传中...' : '开始上传' }}</span>
        </button>

        <!-- Upload Result -->
        <div v-if="uploadResult" class="bg-gray-50 rounded-xl p-4">
          <div class="flex items-start gap-3">
            <div
              class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
              :class="uploadResult.success ? 'bg-green-100' : 'bg-red-100'"
            >
              <CheckCircle v-if="uploadResult.success" :size="20" class="text-green-600" />
              <XCircle v-else :size="20" class="text-red-600" />
            </div>
            
            <div class="flex-1">
              <h4 class="font-semibold text-gray-900 mb-1">
                {{ uploadResult.success ? '上传成功！' : '上传失败' }}
              </h4>
              <p class="text-sm text-gray-600">
                {{ uploadResult.success ? uploadResult.msg : uploadResult.error }}
              </p>
            </div>
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
                    <span
                      :class="getStatusColor(selectedDoc.status)"
                      :title="getStatusDescription(selectedDoc.status)"
                    >
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

          <!-- 分类策略 -->
          <div v-if="selectedDoc.meta_info?.domain" class="bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl p-4 border border-emerald-200">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-sm font-medium text-gray-900">分类策略</span>
            </div>
            <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium border"
              :class="getDomainColor(selectedDoc.meta_info)">
              {{ getDomainLabel(selectedDoc.meta_info) }}
            </div>
            <p class="text-xs text-gray-500 mt-2">
              文件名含「财务」「税务」「合同」等关键词自动触发对应策略。未匹配时由 LLM 自动分类。
            </p>
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

<style scoped>
.scrollbar-custom::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.scrollbar-custom::-webkit-scrollbar-track {
  background: transparent;
}

.scrollbar-custom::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.scrollbar-custom::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
