<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { 
  Upload, 
  FileText, 
  CheckCircle, 
  XCircle, 
  Clock,
  ClipboardList,
  DollarSign,
  Scale,
  ScaleIcon,
  Sparkles,
  ArrowRight,
  FileBarChart
} from 'lucide-vue-next'
import { auditApi } from '@/api/audit'
import type { AuditType, AuditDocument } from '@/types'

const router = useRouter()

const selectedFiles = ref<File[]>([])
const selectedAuditType = ref<AuditType>('comprehensive')
const isUploading = ref(false)
const uploadResult = ref<{ success: boolean; taskId?: string; error?: string } | null>(null)
const isDragging = ref(false)

const auditTypes = [
  { 
    value: 'financial', 
    label: '财务审查',
    icon: DollarSign,
    description: '资产负债表、利润表、现金流量表',
    color: 'from-green-500 to-emerald-600'
  },
  { 
    value: 'tax', 
    label: '税务审查', 
    icon: ClipboardList,
    description: '税务合规性、税收风险',
    color: 'from-blue-500 to-cyan-600'
  },
  { 
    value: 'legal', 
    label: '法务审查', 
    icon: Scale,
    description: '合同风险、法律合规',
    color: 'from-purple-500 to-pink-600'
  },
  { 
    value: 'compliance', 
    label: '合规审查', 
    icon: Sparkles,
    description: '全面合规性检查',
    color: 'from-orange-500 to-red-600'
  },
]

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const files = Array.from(target.files || [])
  addFiles(files)
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
  const files = Array.from(event.dataTransfer?.files || [])
  addFiles(files)
}

function addFiles(files: File[]) {
  const allowedTypes = ['.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx', '.csv']
  const validFiles = files.filter(file => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    return allowedTypes.includes(ext)
  })
  selectedFiles.value = [...selectedFiles.value, ...validFiles]
}

function removeFile(index: number) {
  selectedFiles.value.splice(index, 1)
}

function clearFiles() {
  selectedFiles.value = []
  uploadResult.value = null
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

async function handleStartAudit() {
  if (selectedFiles.value.length === 0 || isUploading.value) {
    return
  }

  isUploading.value = true
  uploadResult.value = null

  try {
    const documents: AuditDocument[] = await Promise.all(
      selectedFiles.value.map(async (file) => {
        const content = await readFileContent(file)
        return {
          name: file.name,
          content: content,
          type: getFileType(file.name)
        }
      })
    )

    const task = await auditApi.createTask({
      audit_type: selectedAuditType.value,
      documents: documents
    })

    uploadResult.value = {
      success: true,
      taskId: task.id
    }

    setTimeout(() => {
      router.push(`/audit/result/${task.id}`)
    }, 1500)

  } catch (error: any) {
    uploadResult.value = {
      success: false,
      error: error.message || '启动审查失败'
    }
  } finally {
    isUploading.value = false
  }
}

async function readFileContent(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      if (file.name.endsWith('.txt') || file.name.endsWith('.csv')) {
        resolve(result)
      } else {
        resolve(`[${file.name}] 文件内容已提取`)
      }
    }
    reader.onerror = () => reject(new Error('读取文件失败'))
    reader.readAsText(file)
  })
}

function getFileType(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || 'txt'
  return ext
}

const selectedAuditTypeInfo = computed(() => {
  return auditTypes.find(t => t.value === selectedAuditType.value)
})
</script>

<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-purple-50 via-pink-50 to-indigo-50 h-full">
    <!-- Top Bar -->
    <div class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center">
          <FileBarChart :size="20" class="text-white" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-gray-900">智能审查</h2>
          <p class="text-xs text-gray-500">上传报表，启动 AI 审查</p>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 overflow-y-auto p-8">
      <div class="max-w-5xl mx-auto space-y-8">
        
        <!-- Audit Type Selection -->
        <div class="bg-white rounded-2xl p-6 shadow-lg border border-gray-200">
          <h3 class="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Sparkles :size="20" class="text-purple-500" />
            选择审查类型
          </h3>
          <div class="grid grid-cols-2 gap-4">
            <button
              v-for="type in auditTypes"
              :key="type.value"
              @click="selectedAuditType = type.value as AuditType"
              class="p-4 rounded-xl border-2 transition-all text-left"
              :class="[
                selectedAuditType === type.value
                  ? 'border-purple-500 bg-purple-50 shadow-md'
                  : 'border-gray-200 bg-white hover:border-purple-300'
              ]"
            >
              <div class="flex items-center gap-3 mb-2">
                <div 
                  class="w-10 h-10 rounded-xl flex items-center justify-center"
                  :class="`bg-gradient-to-br ${type.color}`"
                >
                  <component :is="type.icon" :size="20" class="text-white" />
                </div>
                <span class="font-semibold text-gray-900">{{ type.label }}</span>
              </div>
              <p class="text-sm text-gray-600">{{ type.description }}</p>
            </button>
          </div>
        </div>

        <!-- Upload Area -->
        <div
          class="border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300 cursor-pointer"
          :class="[
            isDragging 
              ? 'border-purple-500 bg-purple-50' 
              : selectedFiles.length > 0 
                ? 'border-purple-400 bg-purple-50/50' 
                : 'border-gray-300 bg-white hover:border-gray-400'
          ]"
          @dragover="handleDragOver"
          @dragleave="handleDragLeave"
          @drop="handleDrop"
          @click="($refs.fileInput as HTMLInputElement)?.click()"
        >
          <input
            ref="fileInput"
            type="file"
            class="hidden"
            multiple
            accept=".pdf,.doc,.docx,.txt,.xls,.xlsx,.csv"
            @change="handleFileSelect"
          />

          <div v-if="selectedFiles.length === 0" class="space-y-4">
            <div class="w-20 h-20 bg-gradient-to-br from-purple-400 to-pink-500 rounded-3xl flex items-center justify-center mx-auto shadow-xl">
              <Upload :size="40" class="text-white" />
            </div>
            <div class="space-y-2">
              <h3 class="text-xl font-bold text-gray-900">拖拽报表文件到这里</h3>
              <p class="text-gray-600">或点击选择文件</p>
              <p class="text-sm text-gray-500">支持 PDF, DOC, DOCX, XLS, XLSX, CSV, TXT</p>
            </div>
          </div>

          <div v-else class="space-y-4">
            <div class="flex items-center justify-center gap-4 flex-wrap">
              <div
                v-for="(file, index) in selectedFiles"
                :key="index"
                class="relative bg-white rounded-xl p-4 shadow-md border border-gray-200 hover:shadow-lg transition-all"
                style="min-width: 200px"
              >
                <button
                  @click.stop="removeFile(index)"
                  class="absolute -top-2 -right-2 w-6 h-6 bg-red-500 hover:bg-red-600 text-white rounded-full flex items-center justify-center shadow-lg"
                >
                  <span class="text-xs font-bold">×</span>
                </button>
                <div class="flex items-center gap-2 mb-2">
                  <FileText :size="20" class="text-purple-600" />
                  <span class="font-medium text-gray-900 text-sm truncate max-w-[150px]">
                    {{ file.name }}
                  </span>
                </div>
                <p class="text-xs text-gray-500">{{ formatFileSize(file.size) }}</p>
              </div>
            </div>
            
            <button
              @click.stop="clearFiles"
              class="mt-4 px-6 py-2.5 bg-gray-100 hover:bg-red-50 text-gray-700 hover:text-red-600 rounded-xl transition-all inline-flex items-center gap-2 font-medium"
            >
              清空文件
            </button>
          </div>
        </div>

        <!-- Start Audit Button -->
        <button
          v-if="selectedFiles.length > 0"
          @click="handleStartAudit"
          :disabled="isUploading"
          class="w-full py-4 bg-gradient-to-r from-purple-500 to-pink-600 text-white rounded-2xl hover:from-purple-600 hover:to-pink-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl flex items-center justify-center gap-3 font-medium text-lg"
        >
          <Sparkles :size="24" v-if="!isUploading" />
          <FileBarChart :size="24" class="animate-spin" v-else />
          <span>{{ isUploading ? '正在启动审查...' : `开始${selectedAuditTypeInfo?.label}` }}</span>
          <ArrowRight :size="20" v-if="!isUploading" />
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
                {{ uploadResult.success ? '审查任务已创建！' : '创建失败' }}
              </h3>
              
              <div v-if="uploadResult.success" class="space-y-2 text-sm text-gray-600">
                <p>任务 ID: {{ uploadResult.taskId }}</p>
                <div class="flex items-center gap-2 text-xs bg-blue-50 px-3 py-2 rounded-lg">
                  <Clock :size="14" class="text-blue-600" />
                  <span class="text-blue-700">正在跳转到结果页面...</span>
                </div>
              </div>
              
              <p v-else class="text-sm text-red-600">
                {{ uploadResult.error }}
              </p>
            </div>
          </div>
        </div>

        <!-- Process Info Card -->
        <div class="bg-white rounded-2xl p-6 shadow-md border border-gray-200">
          <h3 class="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Sparkles :size="20" class="text-purple-500" />
            审查流程
          </h3>
          <div class="space-y-3">
            <div class="flex items-start gap-3">
              <div class="w-6 h-6 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <span class="text-xs font-bold text-blue-600">1</span>
              </div>
              <div>
                <p class="font-medium text-gray-900 text-sm">文档解析</p>
                <p class="text-xs text-gray-600 mt-1">提取文本内容和关键数据</p>
              </div>
            </div>
            
            <div class="flex items-start gap-3">
              <div class="w-6 h-6 bg-purple-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <span class="text-xs font-bold text-purple-600">2</span>
              </div>
              <div>
                <p class="font-medium text-gray-900 text-sm">并行专业审查</p>
                <p class="text-xs text-gray-600 mt-1">财务、税务、法务 Agent 同时审查</p>
              </div>
            </div>
            
            <div class="flex items-start gap-3">
              <div class="w-6 h-6 bg-pink-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <span class="text-xs font-bold text-pink-600">3</span>
              </div>
              <div>
                <p class="font-medium text-gray-900 text-sm">冲突检测</p>
                <p class="text-xs text-gray-600 mt-1">反思专家检查跨领域一致性</p>
              </div>
            </div>

            <div class="flex items-start gap-3">
              <div class="w-6 h-6 bg-green-100 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <span class="text-xs font-bold text-green-600">4</span>
              </div>
              <div>
                <p class="font-medium text-gray-900 text-sm">生成报告</p>
                <p class="text-xs text-gray-600 mt-1">输出风险评估和改进建议</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
