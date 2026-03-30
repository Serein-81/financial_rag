<script setup lang="ts">
import { ref, computed } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useAuthStore } from '@/stores/auth'
import {
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  Database,
  X,
  Sparkles,
  Plus,
  Building2,
  User,
  Globe,
  Lock
} from 'lucide-vue-next'
import type { VisibilityType } from '@/types'

const knowledgeStore = useKnowledgeStore()
const authStore = useAuthStore()

const selectedFile = ref<File | null>(null)
const isUploading = ref(false)
const uploadResult = ref<any>(null)
const isDragging = ref(false)

const showCreateKBDialog = ref(false)
const newKBName = ref('')
const newKBDescription = ref('')
const newKBVisibility = ref<VisibilityType>('private')
const isCreatingKB = ref(false)

const selectedKB = computed(() => knowledgeStore.selectedKnowledgeBase)

const isEnterpriseKB = computed(() => selectedKB.value?.visibility === 'enterprise')

const showUploadVisibilityOption = computed(() => isEnterpriseKB.value)

const selectedDocVisibility = ref<'public' | 'private'>('public')

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    selectedFile.value = file
  }
}

function handleDragOver(event: DragEvent) {
  event.preventDefault()
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  isDragging.value = false
  const file = event.dataTransfer?.files[0]
  if (file) {
    selectedFile.value = file
  }
}

async function handleUpload() {
  if (!selectedFile.value || !selectedKB.value || isUploading.value) {
    if (!selectedKB.value) {
      alert('请先选择一个知识库')
    }
    return
  }

  isUploading.value = true
  uploadResult.value = null

  try {
    const docVisibility = showUploadVisibilityOption.value
      ? selectedDocVisibility.value
      : undefined
    const result = await knowledgeStore.uploadFile(
      selectedKB.value.id,
      selectedFile.value,
      docVisibility
    )
    uploadResult.value = {
      success: true,
      ...result
    }
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

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

async function createNewKB() {
  if (!newKBName.value.trim()) {
    alert('请输入知识库名称')
    return
  }

  isCreatingKB.value = true
  try {
    const newKB = await knowledgeStore.createKnowledgeBase(
      newKBName.value.trim(),
      newKBDescription.value.trim() || undefined,
      newKBVisibility.value
    )
    knowledgeStore.selectKnowledgeBase(newKB.id)
    showCreateKBDialog.value = false
    newKBName.value = ''
    newKBDescription.value = ''
    newKBVisibility.value = 'private'
  } catch (error) {
    console.error('Failed to create knowledge base:', error)
    alert('创建知识库失败')
  } finally {
    isCreatingKB.value = false
  }
}

function getVisibilityLabel(visibility: VisibilityType): string {
  return visibility === 'enterprise' ? '企业' : '私人'
}

function getVisibilityColor(visibility: VisibilityType): string {
  return visibility === 'enterprise'
    ? 'bg-purple-100 text-purple-700'
    : 'bg-blue-100 text-blue-700'
}

</script>

<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-green-50 via-emerald-50 to-teal-50 h-full">
    <!-- Top Bar -->
    <div class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl flex items-center justify-center">
          <Upload :size="20" class="text-white" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-gray-900">文档上传</h2>
          <p class="text-xs text-gray-500">上传文档到知识库</p>
        </div>
      </div>
      
      <!-- KB Selector -->
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2 px-4 py-2 bg-gray-50 rounded-xl border border-gray-200">
          <Database :size="16" class="text-gray-500" />
          <select
            v-model="knowledgeStore.selectedKnowledgeBaseId"
            class="bg-transparent text-sm text-gray-700 outline-none cursor-pointer min-w-48"
          >
            <option :value="null">选择知识库</option>
            <option v-for="kb in knowledgeStore.knowledgeBases" :key="kb.id" :value="kb.id">
              {{ kb.name }} ({{ kb.visibility === 'enterprise' ? '企业' : '私人' }})
            </option>
          </select>
        </div>

        <!-- Create New KB Button -->
        <button
          @click="showCreateKBDialog = true"
          class="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl hover:from-green-600 hover:to-emerald-700 transition-all shadow-md hover:shadow-lg"
        >
          <Plus :size="16" />
          <span class="text-sm font-medium">新建知识库</span>
        </button>
      </div>
    </div>

    <!-- Create KB Dialog -->
    <Teleport to="body">
      <div v-if="showCreateKBDialog" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
          <div class="bg-gradient-to-r from-green-500 to-emerald-600 px-6 py-4">
            <h3 class="text-lg font-semibold text-white">创建新知识库</h3>
            <p class="text-green-100 text-sm">设置知识库名称和可见性</p>
          </div>

          <div class="p-6 space-y-5">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">知识库名称</label>
              <input
                v-model="newKBName"
                type="text"
                placeholder="例如：产品文档、公司规范"
                class="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-green-500 focus:ring-2 focus:ring-green-200 outline-none transition-all"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">描述（可选）</label>
              <textarea
                v-model="newKBDescription"
                rows="2"
                placeholder="描述知识库的用途..."
                class="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-green-500 focus:ring-2 focus:ring-green-200 outline-none transition-all resize-none"
              />
            </div>

            <!-- 🔐 仅管理员可选择可见性，普通用户默认私人 -->
            <div v-if="authStore.isAdmin">
              <label class="block text-sm font-medium text-gray-700 mb-2">可见性</label>
              <div class="grid grid-cols-2 gap-3">
                <button
                  @click="newKBVisibility = 'private'"
                  class="p-4 rounded-xl border-2 transition-all text-left"
                  :class="[
                    newKBVisibility === 'private'
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 bg-gray-50 hover:border-gray-300'
                  ]"
                >
                  <div class="flex items-center gap-2 mb-1">
                    <User :size="18" :class="newKBVisibility === 'private' ? 'text-blue-600' : 'text-gray-500'" />
                    <span class="font-medium text-sm" :class="newKBVisibility === 'private' ? 'text-blue-700' : 'text-gray-700'">私人</span>
                  </div>
                  <p class="text-xs" :class="newKBVisibility === 'private' ? 'text-blue-600' : 'text-gray-500'">仅自己可见</p>
                </button>

                <button
                  @click="newKBVisibility = 'enterprise'"
                  class="p-4 rounded-xl border-2 transition-all text-left"
                  :class="[
                    newKBVisibility === 'enterprise'
                      ? 'border-purple-500 bg-purple-50'
                      : 'border-gray-200 bg-gray-50 hover:border-gray-300'
                  ]"
                >
                  <div class="flex items-center gap-2 mb-1">
                    <Building2 :size="18" :class="newKBVisibility === 'enterprise' ? 'text-purple-600' : 'text-gray-500'" />
                    <span class="font-medium text-sm" :class="newKBVisibility === 'enterprise' ? 'text-purple-700' : 'text-gray-700'">企业</span>
                  </div>
                  <p class="text-xs" :class="newKBVisibility === 'enterprise' ? 'text-purple-600' : 'text-gray-500'">全公司可见</p>
                </button>
              </div>
            </div>
            <div v-else>
              <div class="p-3 bg-blue-50 rounded-xl border border-blue-200">
                <div class="flex items-center gap-2 text-blue-700">
                  <Lock :size="16" />
                  <span class="text-sm font-medium">私人知识库</span>
                </div>
                <p class="text-xs text-blue-600 mt-1">普通用户只能创建私人知识库</p>
              </div>
            </div>
          </div>

          <div class="px-6 py-4 bg-gray-50 flex justify-end gap-3">
            <button
              @click="showCreateKBDialog = false"
              class="px-5 py-2.5 text-gray-700 bg-white border border-gray-300 rounded-xl hover:bg-gray-50 transition-all font-medium"
            >
              取消
            </button>
            <button
              @click="createNewKB"
              :disabled="isCreatingKB"
              class="px-5 py-2.5 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl hover:from-green-600 hover:to-emerald-700 transition-all font-medium disabled:opacity-50 flex items-center gap-2"
            >
              <Sparkles :size="16" class="animate-spin" v-if="isCreatingKB" />
              {{ isCreatingKB ? '创建中...' : '创建' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Main Content -->
    <div class="flex-1 overflow-y-auto p-8">
      <div class="max-w-3xl mx-auto space-y-6">
        <!-- Warning if no KB selected -->
        <div v-if="!selectedKB" class="bg-yellow-50 border border-yellow-200 rounded-2xl p-6 flex items-start gap-4">
          <div class="w-10 h-10 bg-yellow-100 rounded-xl flex items-center justify-center flex-shrink-0">
            <Database :size="20" class="text-yellow-600" />
          </div>
          <div>
            <h3 class="font-semibold text-yellow-900 mb-1">请先选择知识库</h3>
            <p class="text-sm text-yellow-700">在右上角选择一个知识库后才能上传文档</p>
          </div>
        </div>

        <!-- Upload Area -->
        <div
          class="border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300 cursor-pointer"
          :class="[
            isDragging 
              ? 'border-green-500 bg-green-50' 
              : selectedFile 
                ? 'border-green-400 bg-green-50/50' 
                : 'border-gray-300 bg-white hover:border-gray-400'
          ]"
          @dragover="handleDragOver"
          @dragleave="handleDragLeave"
          @drop="handleDrop"
          @click="$refs.fileInput?.click()"
        >
          <input
            ref="fileInput"
            type="file"
            class="hidden"
            accept=".pdf,.doc,.docx,.txt,.png"
            @change="handleFileSelect"
          />

          <div v-if="!selectedFile" class="space-y-4">
            <div class="w-20 h-20 bg-gradient-to-br from-green-400 to-emerald-500 rounded-3xl flex items-center justify-center mx-auto shadow-xl">
              <Upload :size="40" class="text-white" />
            </div>
            <div class="space-y-2">
              <h3 class="text-xl font-bold text-gray-900">拖拽文件到这里</h3>
              <p class="text-gray-600">或点击选择文件</p>
              <p class="text-sm text-gray-500">支持 PDF, DOC, DOCX, TXT, PNG</p>
            </div>
          </div>

          <div v-else class="space-y-4">
            <div class="w-20 h-20 bg-gradient-to-br from-blue-400 to-blue-500 rounded-3xl flex items-center justify-center mx-auto shadow-xl">
              <FileText :size="40" class="text-white" />
            </div>
            <div class="space-y-2">
              <h3 class="text-xl font-bold text-gray-900 truncate max-w-md mx-auto">
                {{ selectedFile.name }}
              </h3>
              <p class="text-gray-600">{{ formatFileSize(selectedFile.size) }}</p>
            </div>
            <button
              @click.stop="clearFile"
              class="mt-4 px-6 py-2.5 bg-gray-100 hover:bg-red-50 text-gray-700 hover:text-red-600 rounded-xl transition-all inline-flex items-center gap-2 font-medium"
            >
              <X :size="16" />
              清除文件
            </button>
</div>
          </div>
        </div>

        <!-- 🔐 Document Visibility Selection for Enterprise KB -->
        <div v-if="selectedFile && selectedKB && showUploadVisibilityOption" class="bg-purple-50 border border-purple-200 rounded-2xl p-4">
          <div class="flex items-center gap-2 mb-3">
            <Building2 :size="18" class="text-purple-600" />
            <span class="text-sm font-medium text-purple-900">上传到企业知识库</span>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <button
              @click="selectedDocVisibility = 'public'"
              class="p-3 rounded-xl border-2 transition-all text-left"
              :class="[
                selectedDocVisibility === 'public'
                  ? 'border-green-500 bg-green-50'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              ]"
            >
              <div class="flex items-center gap-2">
                <Globe :size="16" :class="selectedDocVisibility === 'public' ? 'text-green-600' : 'text-gray-500'" />
                <span class="text-sm font-medium" :class="selectedDocVisibility === 'public' ? 'text-green-700' : 'text-gray-700'">公开上传</span>
              </div>
              <p class="text-xs mt-1" :class="selectedDocVisibility === 'public' ? 'text-green-600' : 'text-gray-500'">全公司可见</p>
            </button>

            <button
              @click="selectedDocVisibility = 'private'"
              class="p-3 rounded-xl border-2 transition-all text-left"
              :class="[
                selectedDocVisibility === 'private'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              ]"
            >
              <div class="flex items-center gap-2">
                <Lock :size="16" :class="selectedDocVisibility === 'private' ? 'text-blue-600' : 'text-gray-500'" />
                <span class="text-sm font-medium" :class="selectedDocVisibility === 'private' ? 'text-blue-700' : 'text-gray-700'">私人上传</span>
              </div>
              <p class="text-xs mt-1" :class="selectedDocVisibility === 'private' ? 'text-blue-600' : 'text-gray-500'">仅自己可见</p>
            </button>
          </div>
        </div>

        <!-- Upload Button -->
        <button
          v-if="selectedFile && selectedKB"
          @click="handleUpload"
          :disabled="isUploading"
          class="w-full py-4 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-2xl hover:from-green-600 hover:to-emerald-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl flex items-center justify-center gap-3 font-medium text-lg"
        >
          <Upload :size="24" v-if="!isUploading" />
          <Sparkles :size="24" class="animate-spin" v-else />
          <span>{{ isUploading ? '上传中...' : '开始上传' }}</span>
        </button>

        <!-- Upload Result -->
        <div v-if="uploadResult" class="bg-white rounded-2xl p-6 shadow-lg border border-gray-200">
          <div class="flex items-start gap-4">
            <div
              class="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
              :class="[
                uploadResult.success 
                  ? 'bg-green-100' 
                  : 'bg-red-100'
              ]"
            >
              <CheckCircle v-if="uploadResult.success" :size="24" class="text-green-600" />
              <XCircle v-else :size="24" class="text-red-600" />
            </div>
            
            <div class="flex-1">
              <h3 class="font-semibold text-gray-900 mb-2">
                {{ uploadResult.success ? '上传成功！' : '上传失败' }}
              </h3>
              
              <div v-if="uploadResult.success" class="space-y-2 text-sm text-gray-600">
                <p>{{ uploadResult.msg }}</p>
                <div class="flex items-center gap-2 text-xs bg-blue-50 px-3 py-2 rounded-lg">
                  <Clock :size="14" class="text-blue-600" />
                  <span class="text-blue-700">系统正在后台进行 AI 向量化处理，请稍后在文档列表查看</span>
                </div>
              </div>
              
              <p v-else class="text-sm text-red-600">
                {{ uploadResult.error }}
              </p>
            </div>
          </div>
        </div>

        <!-- Info Card -->
        <div class="bg-white rounded-2xl p-6 shadow-md border border-gray-200">
          <h3 class="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Sparkles :size="20" class="text-purple-500" />
            处理流程
          </h3>
          <div class="space-y-3">
            <div class="flex items-start gap-3">
              <div class="w-6 h-6 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <span class="text-xs font-bold text-blue-600">1</span>
              </div>
              <div>
                <p class="font-medium text-gray-900 text-sm">文本提取</p>
                <p class="text-xs text-gray-600 mt-1">从文档中提取纯文本内容</p>
              </div>
            </div>
            
            <div class="flex items-start gap-3">
              <div class="w-6 h-6 bg-purple-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <span class="text-xs font-bold text-purple-600">2</span>
              </div>
              <div>
                <p class="font-medium text-gray-900 text-sm">智能切分</p>
                <p class="text-xs text-gray-600 mt-1">将长文本切分为语义完整的片段</p>
              </div>
            </div>
            
            <div class="flex items-start gap-3">
              <div class="w-6 h-6 bg-green-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <span class="text-xs font-bold text-green-600">3</span>
              </div>
              <div>
                <p class="font-medium text-gray-900 text-sm">向量化存储</p>
                <p class="text-xs text-gray-600 mt-1">使用 AI 模型生成向量并存入数据库</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
