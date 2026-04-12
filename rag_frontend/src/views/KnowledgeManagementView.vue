<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useAuthStore } from '@/stores/auth'
import { knowledgeApi } from '@/api/knowledge'
import { useWordDocument } from '@/composables/useWordDocument'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Database,
  Plus,
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  Trash2,
  RefreshCw,
  AlertCircle,
  FolderOpen,
  Cloud,
  X,
  Eye,
  Info,
  Download,
  Lock,
  Globe,
  Building2,
  Users
} from 'lucide-vue-next'
import type { Document } from '@/types'

const { convertToHtmlWithStyles, isConverting, conversionError } = useWordDocument()

const router = useRouter()
const knowledgeStore = useKnowledgeStore()
const authStore = useAuthStore()

if (!authStore.isLoggedIn) {
  router.push('/login')
}

const showCreateKBDialog = ref(false)
const newKBName = ref('')
const newKBDescription = ref('')
const newKBVisibility = ref<'private' | 'enterprise'>('private')
const isCreatingKB = ref(false)

const selectedDocVisibility = ref<'private' | 'public'>('public')
const showUploadVisibilityModal = ref(false)
const pendingUploadFiles = ref<File[]>([])

const showPreviewModal = ref(false)
const previewContent = ref<string | null>(null)
const previewPdfUrl = ref<string | null>(null)
const previewHtmlUrl = ref<string | null>(null)
const docxHtmlUrl = ref<string | null>(null)
const isLoadingPreview = ref(false)
const previewError = ref<string | null>(null)

const uploadFileRef = ref<HTMLInputElement | null>(null)
const isDragging = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)

const pollingInterval = ref<number | null>(null)
const isPolling = ref(false)

const showDocDetailModal = ref(false)
const selectedDoc = ref<any>(null)

const selectedKB = computed(() => knowledgeStore.selectedKnowledgeBase)
const isEnterpriseKB = computed(() => selectedKB.value?.visibility === 'enterprise')
const showUploadVisibilityOption = computed(() => isEnterpriseKB.value)
const documents = computed(() => {
  if (!selectedKB.value) return []
  return knowledgeStore.documents[selectedKB.value.id] || []
})

const hasProcessingDocs = computed(() => {
  return documents.value.some(doc => 
    doc.status === 'pending' || doc.status === 'processing'
  )
})

const completedDocs = computed(() => {
  return documents.value.filter(doc => doc.status === 'completed').length
})

const failedDocs = computed(() => {
  return documents.value.filter(doc => doc.status === 'failed').length
})

const processingDocs = computed(() => {
  return documents.value.filter(doc => doc.status === 'processing' || doc.status === 'pending').length
})

onMounted(async () => {
  await knowledgeStore.fetchKnowledgeBases()
  if (selectedKB.value) {
    await knowledgeStore.fetchDocuments(selectedKB.value.id)
    startPollingIfNeeded()
  }
})

watch(() => selectedKB.value?.id, async (newId) => {
  if (newId) {
    await knowledgeStore.fetchDocuments(newId)
    startPollingIfNeeded()
  } else {
    stopPolling()
  }
})

watch(hasProcessingDocs, (hasProcessing) => {
  if (hasProcessing) {
    startPollingIfNeeded()
  } else {
    stopPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})

async function handleCreateKB() {
  if (!newKBName.value.trim()) {
    ElMessage.warning('请输入知识库名称')
    return
  }

  try {
    isCreatingKB.value = true
    const newKB = await knowledgeStore.createKnowledgeBase(
      newKBName.value.trim(),
      newKBDescription.value.trim() || undefined,
      newKBVisibility.value
    )
    
    ElMessage.success('知识库创建成功')
    showCreateKBDialog.value = false
    newKBName.value = ''
    newKBDescription.value = ''
    newKBVisibility.value = 'private'
    
    knowledgeStore.selectKnowledgeBase(newKB.id)
  } catch (error: any) {
    ElMessage.error(error.message || '创建知识库失败')
  } finally {
    isCreatingKB.value = false
  }
}

async function handleDeleteKB(kb_id: string, kb_name: string) {
  try {
    await ElMessageBox.confirm(
      `确定要删除知识库"${kb_name}"吗？此操作将删除该知识库下的所有文档。`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    await knowledgeStore.deleteKnowledgeBase(kb_id)
    ElMessage.success('知识库已删除')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除知识库失败')
    }
  }
}

async function handleDeleteDoc(doc_id: string, doc_name: string) {
  console.log('handleDeleteDoc called:', { doc_id, doc_name })
  try {
    await ElMessageBox.confirm(
      `确定要删除文档"${doc_name}"吗？`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    if (!doc_id) {
      ElMessage.error('文档ID无效')
      return
    }
    await knowledgeStore.deleteDocument(selectedKB.value?.id || '', doc_id)
    ElMessage.success('文档已删除')
    if (selectedKB.value) {
      await knowledgeStore.fetchDocuments(selectedKB.value.id)
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除文档失败')
    }
  }
}

function triggerFileUpload() {
  uploadFileRef.value?.click()
}

async function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (files && files.length > 0) {
    await uploadFiles(Array.from(files))
  }
  target.value = ''
}

function handleDragOver(event: DragEvent) {
  event.preventDefault()
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

async function handleDrop(event: DragEvent) {
  event.preventDefault()
  isDragging.value = false

  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    await uploadFiles(Array.from(files))
  }
}

async function uploadFiles(files: File[]) {
  if (!selectedKB.value) {
    ElMessage.warning('请先选择知识库')
    return
  }

  if (showUploadVisibilityOption.value) {
    pendingUploadFiles.value = files
    showUploadVisibilityModal.value = true
    return
  }

  await doUploadFiles(files)
}

async function doUploadFiles(files: File[]) {
  isUploading.value = true
  uploadProgress.value = 0

  try {
    const docVisibility = showUploadVisibilityOption.value ? selectedDocVisibility.value : undefined
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      await knowledgeStore.uploadFile(selectedKB.value!.id, file, docVisibility)
      uploadProgress.value = Math.round(((i + 1) / files.length) * 100)
    }

    ElMessage.success(`成功上传 ${files.length} 个文件`)
    
    await knowledgeStore.fetchDocuments(selectedKB.value!.id)
    startPollingIfNeeded()
  } catch (error: any) {
    // 错误已在全局拦截器中显示，不需要重复显示
    // 只记录日志用于调试
    console.error('Upload error:', error)
  } finally {
    isUploading.value = false
    uploadProgress.value = 0
    showUploadVisibilityModal.value = false
    pendingUploadFiles.value = []
  }
}

function startPollingIfNeeded() {
  if (isPolling.value || !hasProcessingDocs.value || !selectedKB.value) {
    return
  }

  isPolling.value = true
  pollingInterval.value = window.setInterval(async () => {
    if (selectedKB.value) {
      await knowledgeStore.fetchDocuments(selectedKB.value.id)
    }
  }, 3000)
}

function stopPolling() {
  if (pollingInterval.value !== null) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
  isPolling.value = false
}

async function refreshDocuments() {
  if (!selectedKB.value) return
  await knowledgeStore.fetchDocuments(selectedKB.value.id)
  ElMessage.success('刷新成功')
}

function viewDocumentDetail(doc: any) {
  selectedDoc.value = doc
  showDocDetailModal.value = true
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'text-emerald-600'
    case 'failed':
      return 'text-red-600'
    case 'processing':
      return 'text-emerald-600'
    case 'pending':
      return 'text-amber-600'
    default:
      return 'text-gray-500'
  }
}

function getStatusBgColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'bg-emerald-50 border-emerald-200 text-emerald-700'
    case 'failed':
      return 'bg-red-50 border-red-200 text-red-700'
    case 'processing':
      return 'bg-emerald-50 border-emerald-200 text-emerald-700'
    case 'pending':
      return 'bg-amber-50 border-amber-200 text-amber-700'
    default:
      return 'bg-gray-50 border-gray-200 text-gray-700'
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

function closePreviewModal() {
  if (previewPdfUrl.value) {
    window.URL.revokeObjectURL(previewPdfUrl.value)
    previewPdfUrl.value = null
  }
  if (previewHtmlUrl.value) {
    window.URL.revokeObjectURL(previewHtmlUrl.value)
    previewHtmlUrl.value = null
  }
  if (docxHtmlUrl.value) {
    window.URL.revokeObjectURL(docxHtmlUrl.value)
    docxHtmlUrl.value = null
  }
  previewContent.value = null
  showPreviewModal.value = false
}

async function handleDownload(doc: any) {
  if (!doc || !doc.id) {
    ElMessage.error('文档信息不完整')
    return
  }
  
  try {
    ElMessage.info('正在准备下载...')
    console.log('Downloading document:', doc.id)
    const blob = await knowledgeApi.downloadDocument(doc.id)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = doc.filename || 'document'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch (error: any) {
    console.error('Download error:', error)
    ElMessage.error(error.message || '下载失败')
  }
}

async function handlePreview(doc: any) {
  if (!doc || !doc.id) {
    ElMessage.error('文档信息不完整')
    return
  }
  
  previewContent.value = null
  previewPdfUrl.value = null
  previewHtmlUrl.value = null
  docxHtmlUrl.value = null
  previewError.value = null
  isLoadingPreview.value = true
  showPreviewModal.value = true
  
  try {
    console.log('Previewing document:', doc.id, doc.filename, doc.file_type)
    const blob = await knowledgeApi.downloadDocument(doc.id)
    const fileType = (doc.file_type || '').toLowerCase()
    const filename = doc.filename || ''
    
    console.log('🔍 File type:', fileType, '| Filename:', filename)
    console.log('🔍 Checking isPdfFile:', fileType.includes('pdf') || filename.endsWith('.pdf'))
    console.log('🔍 Checking isHtmlFile:', filename.endsWith('.html') || filename.endsWith('.htm') || fileType.includes('html'))
    console.log('🔍 Checking isWordFile:', fileType.includes('word') || filename.endsWith('.docx') || filename.endsWith('.doc'))
    
    const isPdfFile = fileType.includes('pdf') || filename.endsWith('.pdf')
    const isHtmlFile = filename.endsWith('.html') || filename.endsWith('.htm') || fileType.includes('html')
    const isWordFile = fileType.includes('word') || 
                       fileType.includes('msword') || 
                       fileType.includes('openxmlformats') ||
                       filename.endsWith('.docx') || 
                       filename.endsWith('.doc')
    
    if (isPdfFile) {
      const url = window.URL.createObjectURL(blob)
      previewPdfUrl.value = url
      console.log('PDF preview URL created')
    } else if (isWordFile) {
      console.log('Converting Word document to HTML...')
      const htmlContent = await convertToHtmlWithStyles(blob)
      const blob2 = new Blob([htmlContent], { type: 'text/html' })
      const url = window.URL.createObjectURL(blob2)
      docxHtmlUrl.value = url
      console.log('Word document converted and preview URL created')
    } else if (isHtmlFile) {
      const url = window.URL.createObjectURL(blob)
      previewHtmlUrl.value = url
      console.log('HTML preview URL created')
    } else {
      const text = await blob.text()
      previewContent.value = text
      console.log('Text preview content loaded, length:', text.length)
    }
  } catch (error: any) {
    console.error('Preview error:', error)
    previewError.value = error.message || '预览加载失败'
  } finally {
    isLoadingPreview.value = false
  }
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
  <div class="flex h-screen bg-slate-50">
    <!-- 左侧：知识库列表 -->
    <div class="w-96 bg-white border-r border-slate-200 flex flex-col shadow-xl">
      <!-- 左侧头部 -->
      <div class="p-6 border-b border-slate-200 bg-gradient-to-br from-emerald-50 to-teal-50">
        <div class="flex items-center gap-3 mb-5">
          <div class="w-11 h-11 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/30">
            <Database :size="22" class="text-white" />
          </div>
          <div>
            <h2 class="text-lg font-bold text-slate-900">知识库管理</h2>
            <p class="text-xs text-slate-600">Knowledge Bases</p>
          </div>
        </div>
        
        <button
          @click="showCreateKBDialog = true"
          class="w-full py-3 px-4 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2 font-medium"
        >
          <Plus :size="18" />
          <span>新建知识库</span>
        </button>
      </div>

      <!-- 知识库列表 -->
      <div class="flex-1 overflow-y-auto p-4 space-y-2">
        <div v-if="knowledgeStore.isLoading && knowledgeStore.knowledgeBases.length === 0" class="flex items-center justify-center py-12">
          <Loader2 :size="32" class="text-emerald-500 animate-spin" />
        </div>

        <div v-else-if="knowledgeStore.knowledgeBases.length === 0" class="text-center py-12 px-4">
          <FolderOpen :size="48" class="mx-auto text-slate-300 mb-3" />
          <p class="text-sm text-slate-500">暂无知识库</p>
          <p class="text-xs text-slate-400 mt-1">点击上方按钮创建</p>
        </div>

        <div
          v-for="kb in knowledgeStore.knowledgeBases"
          :key="kb.id"
          @click="knowledgeStore.selectKnowledgeBase(kb.id)"
          class="p-4 rounded-xl border-2 transition-all duration-200 cursor-pointer group hover:shadow-md"
          :class="selectedKB?.id === kb.id 
            ? 'bg-gradient-to-r from-emerald-50 to-teal-50 border-emerald-400 shadow-md shadow-emerald-500/10' 
            : 'bg-white border-slate-200 hover:border-emerald-300'"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="flex-1 min-w-0">
              <h3 class="font-semibold text-slate-900 truncate mb-1" :title="kb.name">
                {{ kb.name }}
              </h3>
              <p class="text-xs text-slate-500 line-clamp-2" :title="kb.description || ''">
                {{ kb.description || '暂无描述' }}
              </p>
              <p class="text-xs text-slate-400 mt-2">
                {{ formatDate(kb.created_at) }}
              </p>
            </div>
            
            <button
              @click.stop="handleDeleteKB(kb.id, kb.name)"
              class="opacity-0 group-hover:opacity-100 p-2 hover:bg-red-50 rounded-lg transition-all"
              title="删除知识库"
            >
              <Trash2 :size="16" class="text-red-500" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧：文档管理 -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- 右侧头部 -->
      <div v-if="selectedKB" class="bg-white border-b border-slate-200 px-8 py-5 shadow-sm">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <FileText :size="24" class="text-white" />
            </div>
            <div>
              <h2 class="text-xl font-bold text-slate-900">{{ selectedKB.name }}</h2>
              <p class="text-sm text-slate-600">{{ selectedKB.description || '暂无描述' }}</p>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <div v-if="isPolling" class="flex items-center gap-2 px-4 py-2 bg-emerald-50 rounded-xl border border-emerald-200">
              <Loader2 :size="14" class="text-emerald-600 animate-spin" />
              <span class="text-xs text-emerald-700 font-medium">自动刷新中...</span>
            </div>

            <button
              @click="refreshDocuments"
              :disabled="!selectedKB || knowledgeStore.isLoading"
              class="px-4 py-2.5 bg-white border border-slate-300 text-slate-700 rounded-xl hover:bg-slate-50 hover:border-slate-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-sm"
            >
              <RefreshCw :size="16" :class="{ 'animate-spin': knowledgeStore.isLoading }" />
              <span class="text-sm font-medium">刷新</span>
            </button>

            <button
              @click="triggerFileUpload"
              :disabled="!selectedKB || isUploading"
              class="px-6 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 font-medium"
            >
              <Upload :size="18" />
              <span>上传文档</span>
            </button>
            <input
              ref="uploadFileRef"
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.txt,.md"
              class="hidden"
              @change="handleFileSelect"
            />
          </div>
        </div>

        <!-- 统计信息 -->
        <div class="mt-5 flex items-center gap-4">
          <div class="px-4 py-2 bg-slate-50 rounded-lg border border-slate-200">
            <span class="text-xs text-slate-600">文档总数</span>
            <p class="text-lg font-bold text-slate-900">{{ documents.length }}</p>
          </div>
          <div class="px-4 py-2 bg-emerald-50 rounded-lg border border-emerald-200">
            <span class="text-xs text-emerald-700">已完成</span>
            <p class="text-lg font-bold text-emerald-700">{{ completedDocs }}</p>
          </div>
          <div v-if="processingDocs > 0" class="px-4 py-2 bg-emerald-50 rounded-lg border border-emerald-200">
            <span class="text-xs text-emerald-700">处理中</span>
            <p class="text-lg font-bold text-emerald-700">{{ processingDocs }}</p>
          </div>
          <div v-if="failedDocs > 0" class="px-4 py-2 bg-red-50 rounded-lg border border-red-200">
            <span class="text-xs text-red-700">失败</span>
            <p class="text-lg font-bold text-red-700">{{ failedDocs }}</p>
          </div>
        </div>
      </div>

      <!-- 主内容区 -->
      <div class="flex-1 overflow-y-auto p-8">
        <!-- 未选择知识库 -->
        <div v-if="!selectedKB" class="h-full flex items-center justify-center">
          <div class="text-center space-y-4 max-w-md">
            <div class="w-24 h-24 bg-gradient-to-br from-slate-200 to-slate-300 rounded-3xl flex items-center justify-center mx-auto shadow-lg">
              <Database :size="48" class="text-slate-500" />
            </div>
            <h3 class="text-2xl font-bold text-slate-900">请选择知识库</h3>
            <p class="text-slate-600">在左侧选择一个知识库以查看和管理文档</p>
          </div>
        </div>

        <!-- 拖拽上传区域 -->
        <div
          v-else-if="documents.length === 0"
          @dragover="handleDragOver"
          @dragleave="handleDragLeave"
          @drop="handleDrop"
          class="h-full flex items-center justify-center"
        >
          <div
            class="text-center space-y-6 max-w-lg p-12 rounded-3xl border-2 border-dashed transition-all"
            :class="isDragging 
              ? 'border-emerald-500 bg-emerald-50' 
              : 'border-slate-300 bg-white shadow-lg'"
          >
            <div class="w-24 h-24 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-3xl flex items-center justify-center mx-auto shadow-xl">
              <Cloud :size="48" class="text-white" />
            </div>
            <div>
              <h3 class="text-2xl font-bold text-slate-900 mb-2">上传文档</h3>
              <p class="text-slate-600 mb-4">拖拽文件到此处，或点击下方按钮选择文件</p>
              <p class="text-sm text-slate-500">支持 PDF、Word、TXT、Markdown 等格式</p>
            </div>
            <button
              @click="triggerFileUpload"
              class="px-8 py-4 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all shadow-lg hover:shadow-xl font-medium text-lg"
            >
              选择文件
            </button>
          </div>
        </div>

        <!-- 文档列表 -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          <div
            v-for="doc in documents"
            :key="doc.id"
            class="bg-white rounded-2xl shadow-md hover:shadow-xl transition-all duration-300 overflow-hidden border border-slate-200 hover:border-emerald-300"
          >
            <!-- 卡片头部 -->
            <div class="p-6 bg-gradient-to-r from-emerald-50 to-teal-50 border-b border-slate-100">
              <div class="flex items-start gap-3">
                <div class="w-12 h-12 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md">
                  <FileText :size="24" class="text-white" />
                </div>
                <div class="flex-1 min-w-0">
                  <h3 class="font-semibold text-slate-900 truncate mb-2" :title="doc.filename">
                    {{ doc.filename }}
                  </h3>
                  <div
                    class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold border"
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

            <!-- 卡片内容 -->
            <div class="p-6 space-y-4">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <p class="text-xs text-slate-500 mb-1">文件大小</p>
                  <p class="text-sm font-semibold text-slate-900">{{ formatFileSize(doc.file_size) }}</p>
                </div>
                <div>
                  <p class="text-xs text-slate-500 mb-1">文件类型</p>
                  <p class="text-sm font-semibold text-slate-900 truncate" :title="doc.file_type || '-'">
                    {{ doc.file_type || '-' }}
                  </p>
                </div>
              </div>

              <div>
                <p class="text-xs text-slate-500 mb-1">上传时间</p>
                <p class="text-sm text-slate-700">{{ formatDate(doc.created_at) }}</p>
              </div>

              <div>
                <p class="text-xs text-slate-500 mb-1">切块数量</p>
                <p class="text-sm font-semibold text-emerald-600">{{ doc.chunk_count || 0 }}</p>
              </div>

              <!-- 错误信息 -->
              <div v-if="doc.error_msg" class="bg-red-50 border border-red-200 rounded-xl p-3">
                <div class="flex items-start gap-2">
                  <AlertCircle :size="14" class="text-red-500 flex-shrink-0 mt-0.5" />
                  <p class="text-xs text-red-700 line-clamp-2">{{ doc.error_msg }}</p>
                </div>
              </div>
            </div>

            <!-- 卡片操作 -->
            <div class="px-6 py-4 bg-slate-50 border-t border-slate-100 flex gap-2">
              <button
                @click="viewDocumentDetail(doc)"
                class="flex-1 py-2.5 px-3 bg-white border border-slate-300 text-slate-700 hover:border-emerald-400 hover:bg-emerald-50 hover:text-emerald-600 rounded-xl transition-all flex items-center justify-center gap-2 text-sm font-medium shadow-sm"
              >
                <Eye :size="16" />
                查看详情
              </button>
              <button
                @click="handleDeleteDoc(doc.id, doc.filename)"
                class="flex-1 py-2.5 px-3 bg-white border border-slate-300 text-slate-700 hover:border-red-400 hover:bg-red-50 hover:text-red-600 rounded-xl transition-all flex items-center justify-center gap-2 text-sm font-medium shadow-sm"
              >
                <Trash2 :size="16" />
                删除
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建知识库对话框 -->
    <div
      v-if="showCreateKBDialog"
      class="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
      @click.self="showCreateKBDialog = false"
    >
      <div class="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl">
        <h3 class="text-2xl font-bold text-slate-900 mb-6">新建知识库</h3>
        
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">
              知识库名称 <span class="text-red-500">*</span>
            </label>
            <input
              v-model="newKBName"
              type="text"
              placeholder="请输入知识库名称"
              class="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none transition-all"
              @keyup.enter="handleCreateKB"
            />
          </div>

          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">
              描述（可选）
            </label>
            <textarea
              v-model="newKBDescription"
              rows="3"
              placeholder="请输入知识库描述"
              class="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent outline-none transition-all resize-none"
            ></textarea>
          </div>

          <!-- 可见性选择 -->
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">
              可见性
            </label>
            
            <!-- 管理员可见选项 -->
            <div v-if="authStore.isAdmin" class="grid grid-cols-2 gap-3">
              <button
                @click="newKBVisibility = 'private'"
                class="p-4 rounded-xl border-2 transition-all flex flex-col items-center gap-2"
                :class="newKBVisibility === 'private' 
                  ? 'border-emerald-500 bg-emerald-50 text-emerald-700' 
                  : 'border-slate-200 bg-white text-slate-600 hover:border-emerald-300'"
              >
                <Lock :size="20" />
                <span class="font-medium">私人知识库</span>
                <span class="text-xs">仅自己可见</span>
              </button>
              <button
                @click="newKBVisibility = 'enterprise'"
                class="p-4 rounded-xl border-2 transition-all flex flex-col items-center gap-2"
                :class="newKBVisibility === 'enterprise' 
                  ? 'border-emerald-500 bg-emerald-50 text-emerald-700' 
                  : 'border-slate-200 bg-white text-slate-600 hover:border-emerald-300'"
              >
                <Building2 :size="20" />
                <span class="font-medium">企业知识库</span>
                <span class="text-xs">企业内可见</span>
              </button>
            </div>

            <!-- 普通用户提示 -->
            <div v-else class="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
              <div class="flex items-center gap-2 text-emerald-800">
                <Lock :size="16" />
                <span class="text-sm font-medium">私人知识库</span>
              </div>
              <p class="text-xs text-emerald-600 mt-1">普通用户只能创建私人知识库</p>
            </div>
          </div>
        </div>

        <div class="flex gap-3 mt-6">
          <button
            @click="showCreateKBDialog = false"
            :disabled="isCreatingKB"
            class="flex-1 py-3 bg-slate-100 text-slate-700 rounded-xl hover:bg-slate-200 transition-all font-medium disabled:opacity-50"
          >
            取消
          </button>
          <button
            @click="handleCreateKB"
            :disabled="isCreatingKB || !newKBName.trim()"
            class="flex-1 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all shadow-md font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <Loader2 v-if="isCreatingKB" :size="18" class="animate-spin" />
            <span>{{ isCreatingKB ? '创建中...' : '创建' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 上传文档可见性选择模态框 -->
    <div
      v-if="showUploadVisibilityModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
      @click.self="showUploadVisibilityModal = false"
    >
      <div class="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl">
        <div class="flex items-center justify-between mb-6">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center">
              <Building2 :size="24" class="text-white" />
            </div>
            <div>
              <h3 class="text-xl font-bold text-slate-900">上传到企业知识库</h3>
              <p class="text-sm text-slate-500">{{ selectedKB?.name }}</p>
            </div>
          </div>
          <button @click="showUploadVisibilityModal = false" class="p-2 hover:bg-slate-100 rounded-xl transition-all">
            <X :size="20" class="text-slate-500" />
          </button>
        </div>

        <p class="text-sm text-slate-600 mb-4">
          请选择文档的可见性（共 {{ pendingUploadFiles.length }} 个文件）
        </p>

        <div class="grid grid-cols-2 gap-4 mb-6">
          <button
            @click="selectedDocVisibility = 'public'"
            class="p-5 rounded-xl border-2 transition-all flex flex-col items-center gap-3"
            :class="selectedDocVisibility === 'public' 
              ? 'border-emerald-500 bg-emerald-50' 
              : 'border-slate-200 bg-white hover:border-emerald-300'"
          >
            <Globe :size="28" :class="selectedDocVisibility === 'public' ? 'text-emerald-600' : 'text-slate-400'" />
            <div class="text-center">
              <span class="font-semibold" :class="selectedDocVisibility === 'public' ? 'text-emerald-700' : 'text-slate-600'">公开上传</span>
              <p class="text-xs mt-1" :class="selectedDocVisibility === 'public' ? 'text-emerald-600' : 'text-slate-400'">全公司可见</p>
            </div>
          </button>
          <button
            @click="selectedDocVisibility = 'private'"
            class="p-5 rounded-xl border-2 transition-all flex flex-col items-center gap-3"
            :class="selectedDocVisibility === 'private' 
              ? 'border-emerald-500 bg-emerald-50' 
              : 'border-slate-200 bg-white hover:border-emerald-300'"
          >
            <Lock :size="28" :class="selectedDocVisibility === 'private' ? 'text-emerald-600' : 'text-slate-400'" />
            <div class="text-center">
              <span class="font-semibold" :class="selectedDocVisibility === 'private' ? 'text-emerald-700' : 'text-slate-600'">私人上传</span>
              <p class="text-xs mt-1" :class="selectedDocVisibility === 'private' ? 'text-emerald-600' : 'text-slate-400'">仅自己可见</p>
            </div>
          </button>
        </div>

        <div class="flex gap-3">
          <button
            @click="showUploadVisibilityModal = false"
            class="flex-1 py-3 bg-slate-100 text-slate-700 rounded-xl hover:bg-slate-200 transition-all font-medium"
          >
            取消
          </button>
          <button
            @click="doUploadFiles(pendingUploadFiles)"
            :disabled="isUploading"
            class="flex-1 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all shadow-md font-medium disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <Loader2 v-if="isUploading" :size="18" class="animate-spin" />
            <span>{{ isUploading ? '上传中...' : '确认上传' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 文档预览模态框 -->
    <div
      v-if="showPreviewModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center p-6 z-[60]"
      @click.self="closePreviewModal"
    >
      <div class="bg-white rounded-2xl w-full h-full max-w-[95vw] max-h-[95vh] shadow-2xl flex flex-col">
        <div class="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center">
              <Eye :size="20" class="text-white" />
            </div>
            <div>
              <h3 class="text-lg font-bold text-slate-900">文档预览</h3>
              <p class="text-sm text-slate-500">{{ selectedDoc?.filename }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              v-if="previewContent && previewContent !== 'PREVIEW_UNAVAILABLE'"
              @click="handleDownload(selectedDoc)"
              class="px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-all flex items-center gap-2 text-sm font-medium"
            >
              <Download :size="16" />
              下载
            </button>
            <button @click="closePreviewModal" class="p-2 hover:bg-slate-100 rounded-xl transition-all">
              <X :size="20" class="text-slate-500" />
            </button>
          </div>
        </div>

        <div class="flex-1 overflow-hidden">
          <div v-if="isLoadingPreview" class="h-full flex items-center justify-center">
            <div class="text-center">
              <Loader2 :size="48" class="text-emerald-500 animate-spin mx-auto mb-4" />
              <p v-if="isConverting" class="text-slate-600">正在转换 Word 文档...</p>
              <p v-else class="text-slate-600">正在加载预览...</p>
            </div>
          </div>

          <div v-else-if="previewError" class="h-full flex items-center justify-center">
            <div class="text-center text-red-500">
              <XCircle :size="48" class="mx-auto mb-4" />
              <p>{{ previewError }}</p>
            </div>
          </div>

          <div v-else-if="previewContent === 'PREVIEW_UNAVAILABLE'" class="h-full flex items-center justify-center">
            <div class="text-center">
              <FileText :size="64" class="text-slate-300 mx-auto mb-4" />
              <p class="text-slate-600 mb-2">该文件类型不支持在线预览</p>
              <p class="text-sm text-slate-400">请下载后查看</p>
              <button
                @click="handleDownload(selectedDoc)"
                class="mt-4 px-6 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all font-medium flex items-center gap-2 mx-auto"
              >
                <Download :size="18" />
                下载文件
              </button>
            </div>
          </div>

          <iframe
            v-else-if="previewPdfUrl"
            :src="previewPdfUrl"
            class="w-full h-full border-0"
            title="PDF Preview"
            scrolling="yes"
            sandbox="allow-same-origin allow-scripts"
          />

          <iframe
            v-else-if="docxHtmlUrl"
            :src="docxHtmlUrl"
            class="w-full h-full border-0"
            title="Word Preview"
            scrolling="yes"
            sandbox="allow-same-origin allow-scripts"
          />

          <iframe
            v-else-if="previewHtmlUrl"
            :src="previewHtmlUrl"
            class="w-full h-full border-0"
            title="HTML Preview"
            scrolling="yes"
            sandbox="allow-same-origin allow-scripts"
          />

          <pre
            v-else-if="previewContent"
            class="h-full bg-slate-50 p-4 overflow-auto font-mono text-sm text-slate-700 whitespace-pre-wrap break-all"
          >{{ previewContent }}</pre>
        </div>
      </div>
    </div>

    <!-- 文档详情模态框 -->
    <div
      v-if="showDocDetailModal && selectedDoc"
      class="fixed inset-0 bg-black/50 flex items-center justify-center p-6 z-50 overflow-y-auto"
      @click.self="showDocDetailModal = false"
    >
      <div class="bg-white rounded-2xl p-8 max-w-3xl w-full shadow-2xl my-8">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-2xl font-bold text-slate-900">文档详情</h3>
          <button @click="showDocDetailModal = false" class="p-2 hover:bg-slate-100 rounded-xl transition-all">
            <X :size="20" class="text-slate-500" />
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
                <h4 class="text-lg font-bold text-slate-900 mb-2">{{ selectedDoc.filename }}</h4>
                <div class="flex items-center gap-3 flex-wrap">
                  <div
                    class="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold border"
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
            <div class="bg-slate-50 rounded-xl p-4">
              <p class="text-xs text-slate-500 mb-1">文档 ID</p>
              <p class="text-sm font-mono text-slate-900 break-all">{{ selectedDoc.id }}</p>
            </div>
            
            <div class="bg-slate-50 rounded-xl p-4">
              <p class="text-xs text-slate-500 mb-1">知识库 ID</p>
              <p class="text-sm font-mono text-slate-900 break-all">{{ selectedDoc.kb_id }}</p>
            </div>
            
            <div class="bg-slate-50 rounded-xl p-4">
              <p class="text-xs text-slate-500 mb-1">文件大小</p>
              <p class="text-sm font-semibold text-slate-900">{{ formatFileSize(selectedDoc.file_size) }}</p>
            </div>
            
            <div class="bg-slate-50 rounded-xl p-4">
              <p class="text-xs text-slate-500 mb-1">文件类型</p>
              <p class="text-sm font-semibold text-slate-900">{{ selectedDoc.file_type || '-' }}</p>
            </div>
            
            <div class="bg-slate-50 rounded-xl p-4">
              <p class="text-xs text-slate-500 mb-1">上传时间</p>
              <p class="text-sm font-semibold text-slate-900">{{ formatDate(selectedDoc.created_at) }}</p>
            </div>
            
            <div class="bg-emerald-50 rounded-xl p-4 border border-emerald-200">
              <p class="text-xs text-emerald-600 mb-1">切块数量</p>
              <p class="text-lg font-bold text-emerald-700">{{ selectedDoc.chunk_count || 0 }}</p>
            </div>
            
            <div class="bg-slate-50 rounded-xl p-4">
              <p class="text-xs text-slate-500 mb-1">文件路径</p>
              <p class="text-sm font-mono text-slate-900 truncate" :title="selectedDoc.file_path">
                {{ selectedDoc.file_path }}
              </p>
            </div>
          </div>

          <!-- 元信息 -->
          <div v-if="selectedDoc.meta_info && Object.keys(selectedDoc.meta_info).length > 0" class="bg-slate-50 rounded-xl p-4">
            <p class="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
              <Info :size="16" class="text-emerald-500" />
              元信息
            </p>
            <pre class="text-xs text-slate-700 bg-white p-3 rounded-lg overflow-x-auto">{{ JSON.stringify(selectedDoc.meta_info, null, 2) }}</pre>
          </div>

          <!-- 错误信息 -->
          <div v-if="selectedDoc.error_msg" class="bg-red-50 border border-red-200 rounded-xl p-4">
            <div class="flex items-start gap-3">
              <XCircle :size="20" class="text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p class="text-sm font-semibold text-red-900 mb-1">错误信息</p>
                <p class="text-sm text-red-700">{{ selectedDoc.error_msg }}</p>
              </div>
            </div>
          </div>

          <!-- 处理提示 -->
          <div v-if="selectedDoc.status === 'completed'" class="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
            <div class="flex items-start gap-3">
              <CheckCircle :size="20" class="text-emerald-500 flex-shrink-0 mt-0.5" />
              <div>
                <p class="text-sm font-semibold text-emerald-900 mb-1">处理完成</p>
                <p class="text-sm text-emerald-700">文档已成功向量化，可以在对话中使用</p>
              </div>
            </div>
          </div>

          <div v-else-if="selectedDoc.status === 'processing'" class="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
              <div class="flex items-start gap-3">
                <Loader2 :size="20" class="text-emerald-500 flex-shrink-0 mt-0.5 animate-spin" />
                <div>
                  <p class="text-sm font-semibold text-emerald-900 mb-1">正在处理</p>
                  <p class="text-sm text-emerald-700">系统正在进行文本提取、切分和向量化，请稍候...</p>
              </div>
            </div>
          </div>

          <div v-else-if="selectedDoc.status === 'pending'" class="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <div class="flex items-start gap-3">
              <Clock :size="20" class="text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <p class="text-sm font-semibold text-amber-900 mb-1">等待处理</p>
                <p class="text-sm text-amber-700">文档已上传，等待系统处理</p>
              </div>
            </div>
          </div>

          <!-- 源文档操作 -->
          <div class="flex gap-3 pt-4 border-t border-slate-200 mt-4">
            <button
              @click="handlePreview(selectedDoc)"
              class="flex-1 py-3 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all shadow-md hover:shadow-lg font-medium flex items-center justify-center gap-2"
            >
              <Eye :size="18" />
              <span>预览</span>
            </button>
            <button
              @click="handleDownload(selectedDoc)"
              class="flex-1 py-3 bg-white border-2 border-slate-300 text-slate-700 rounded-xl hover:bg-slate-50 hover:border-slate-400 transition-all font-medium flex items-center justify-center gap-2"
            >
              <Download :size="18" />
              <span>下载</span>
            </button>
          </div>
        </div>

        <div class="flex gap-3 mt-6">
          <button
            @click="showDocDetailModal = false"
            class="flex-1 py-3 bg-slate-100 text-slate-700 rounded-xl hover:bg-slate-200 transition-all font-medium"
          >
            关闭
          </button>
          <button
            @click="handleDeleteDoc(selectedDoc.id, selectedDoc.filename); showDocDetailModal = false"
            class="flex-1 py-3 bg-red-500 text-white rounded-xl hover:bg-red-600 transition-all font-medium flex items-center justify-center gap-2"
          >
            <Trash2 :size="18" />
            删除文档
          </button>
        </div>
      </div>
    </div>

    <!-- 上传进度提示 -->
    <div
      v-if="isUploading"
      class="fixed bottom-8 right-8 bg-white rounded-2xl shadow-2xl border border-slate-200 p-6 w-80 z-50"
    >
      <div class="flex items-center gap-3 mb-3">
        <Loader2 :size="20" class="text-emerald-600 animate-spin" />
        <span class="font-semibold text-slate-900">上传中...</span>
      </div>
      <div class="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
        <div
          class="bg-gradient-to-r from-emerald-600 to-teal-600 h-full transition-all duration-300"
          :style="{ width: `${uploadProgress}%` }"
        ></div>
      </div>
      <p class="text-xs text-slate-500 mt-2">{{ uploadProgress }}%</p>
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
