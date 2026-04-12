<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { 
  Document, 
  CheckCircle, 
  Clock, 
  CircleCheck,
  Refresh,
  Delete,
  View,
  Upload,
  Edit
} from '@element-plus/icons-vue'
import { AlertTriangle, FileText as FileTextIcon, Edit as EditIcon } from 'lucide-vue-next'
import { taxReportApiClient } from '@/api/tax-report'
import type { TaxReport, DuplicateFileResponse } from '@/types/tax'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePullRefresh } from '@/composables/usePullRefresh'
import ManualTaxReportDialog from '@/components/ManualTaxReportDialog.vue'

const router = useRouter()

const { pullDistance, isRefreshing, isPulling } = usePullRefresh({
  onRefresh: async () => {
    await loadReportList()
    await loadStatistics()
    ElMessage.success('刷新成功')
  }
})

const activeTab = ref('upload')
const listLoading = ref(false)
const uploadLoading = ref(false)

const detailDialogVisible = ref(false)
const currentReport = ref<TaxReport | null>(null)
const detailLoading = ref(false)

const selectedFiles = ref<File[]>([])
const isDragging = ref(false)
const selectedTaxType = ref('vat')
const selectedYear = ref(new Date().getFullYear())
const selectedMonth = ref(new Date().getMonth() + 1)
const uploadProgress = ref(0)
const uploadResult = ref<{ success: boolean; message: string } | null>(null)

const showManualDialog = ref(false)

const showWorkflowProgress = ref(false)
const currentWorkflowId = ref('')
const workflowStatus = ref<'idle' | 'running' | 'completed' | 'failed'>('idle')
const currentStepIndex = ref(-1)
const workflowSteps = ref([
  { name: '数据验证', status: 'pending' as 'pending' | 'running' | 'completed' | 'failed' | 'warning' },
  { name: '获取财务数据', status: 'pending' as 'pending' | 'running' | 'completed' | 'failed' | 'warning' },
  { name: '税务计算', status: 'pending' as 'pending' | 'running' | 'completed' | 'failed' | 'warning' },
  { name: '风险评估', status: 'pending' as 'pending' | 'running' | 'completed' | 'failed' | 'warning' },
  { name: '人工审核', status: 'pending' as 'pending' | 'running' | 'completed' | 'failed' | 'warning' },
  { name: '保存结果', status: 'pending' as 'pending' | 'running' | 'completed' | 'failed' | 'warning' }
])
const workflowStartTime = ref<Date | null>(null)
const workflowMessages = ref<Array<{ time: string; message: string; type: string }>>([])

const taxTypeOptions = [
  { value: 'vat', label: '增值税 (VAT)', color: '#409eff' },
  { value: 'income', label: '企业所得税', color: '#67c23a' },
  { value: 'personal', label: '个人所得税', color: '#e6a23c' },
  { value: 'consumption', label: '消费税', color: '#f56c6c' },
  { value: 'behavior', label: '行为税', color: '#909399' },
  { value: 'comprehensive', label: '综合税务', color: '#667eea' }
]

const taxTypeInfo = computed(() => {
  return taxTypeOptions.find(o => o.value === selectedTaxType.value)
})

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  const files = Array.from(target.files || [])
  addFiles(files)
}

const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = true
}

const handleDragLeave = () => {
  isDragging.value = false
}

const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = false
  const files = Array.from(event.dataTransfer?.files || [])
  addFiles(files)
}

const addFiles = (files: File[]) => {
  const allowedTypes = ['.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx', '.csv']
  const validFiles = files.filter(file => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    return allowedTypes.includes(ext)
  })
  selectedFiles.value = [...selectedFiles.value, ...validFiles]
}

const removeFile = (index: number) => {
  selectedFiles.value.splice(index, 1)
}

const clearFiles = () => {
  selectedFiles.value = []
  uploadResult.value = null
}

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

const getFileExtension = (filename: string): string => {
  const ext = filename.split('.').pop()?.toUpperCase() || 'FILE'
  return ext
}

const getFileTypeTag = (filename: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  const typeMap: Record<string, string> = {
    'pdf': 'danger',
    'doc': 'primary',
    'docx': 'primary',
    'xls': 'success',
    'xlsx': 'success',
    'csv': 'warning',
    'txt': 'info'
  }
  return typeMap[ext] || 'info'
}

const handleStartUpload = async () => {
  if (selectedFiles.value.length === 0 || uploadLoading.value) {
    return
  }

  uploadLoading.value = true
  uploadResult.value = null
  uploadProgress.value = 0

  try {
    for (let i = 0; i < selectedFiles.value.length; i++) {
      const file = selectedFiles.value[i]
      try {
        await taxReportApiClient.upload(file, {
          tax_type: selectedTaxType.value as any,
          tax_period_year: selectedYear.value,
          tax_period_month: selectedMonth.value,
          onProgress: (progress) => {
            uploadProgress.value = progress
          }
        })
      } catch (uploadError: any) {
        const errorData = uploadError.response?.data as DuplicateFileResponse | undefined
        
        if (errorData?.error_type === 'DUPLICATE_FILE') {
          await ElMessageBox.confirm(
            `<div style="text-align: left; line-height: 1.8;">
              <p style="color: #e6a23c; font-size: 16px; font-weight: bold; margin-bottom: 12px;">
                ⚠️ 发现重复文件
              </p>
              <p><strong>文件名：</strong>${errorData.details.original_filename}</p>
              <p><strong>上传时间：</strong>${errorData.details.created_at ? new Date(errorData.details.created_at).toLocaleString('zh-CN') : '未知'}</p>
              <p><strong>当前状态：</strong><span style="color: ${
                errorData.details.existing_status === 'completed' ? '#67c23a' : 
                errorData.details.existing_status === 'processing' ? '#409eff' : '#909399'
              }">${
                errorData.details.existing_status === 'completed' ? '✅ 已完成' :
                errorData.details.existing_status === 'processing' ? '🔄 处理中' :
                errorData.details.existing_status === 'pending_review' ? '⚠️ 待审核' :
                '⏳ 待处理'
              }</span></p>
              ${
                errorData.details.existing_confidence_score !== null 
                  ? `<p><strong>置信度：</strong>${(errorData.details.existing_confidence_score * 100).toFixed(0)}%</p>` 
                  : ''
              }
              ${
                errorData.details.existing_risk_level 
                  ? `<p><strong>风险等级：</strong><span style="color: ${
                    errorData.details.existing_risk_level === 'high' || errorData.details.existing_risk_level === 'critical' ? '#f56c6c' :
                    errorData.details.existing_risk_level === 'medium' ? '#e6a23c' : '#67c23a'
                  }">${errorData.details.existing_risk_level.toUpperCase()}</span></p>` 
                  : ''
              }
              <p style="color: #606266; margin-top: 16px; font-size: 13px;">
                💡 ${errorData.details.suggestion}
              </p>
            </div>`,
            '文件已存在',
            {
              confirmButtonText: '查看已有报告',
              cancelButtonText: '关闭',
              type: 'warning',
              dangerouslyUseHTMLString: true,
              distinguishCancelAndClose: true
            }
          ).then(() => {
            activeTab.value = 'list'
            loadReportList()
          }).catch(() => {
            // 用户取消
          })
          
          selectedFiles.value.splice(selectedFiles.value.indexOf(file), 1)
          uploadResult.value = {
            success: false,
            message: `文件「${file.name}」已存在，跳过上传`
          }
          uploadLoading.value = false
          return
        }
        throw uploadError
      }
      uploadProgress.value = ((i + 1) / selectedFiles.value.length) * 100
    }

    uploadResult.value = {
      success: true,
      message: `成功上传 ${selectedFiles.value.length} 个文件，正在启动分析流程...`
    }
    selectedFiles.value = []

    startWorkflowSimulation()

  } catch (error: any) {
    if (error.response?.data?.error_type !== 'DUPLICATE_FILE') {
      uploadResult.value = {
        success: false,
        message: error.response?.data?.message || error.message || '上传失败'
      }
    }
  } finally {
    uploadLoading.value = false
  }
}

const handleManualSuccess = (data: any) => {
  ElMessage.success({ message: '税务报告录入成功' })
  showManualDialog.value = false
  activeTab.value = 'list'
  loadReportList()
  loadStatistics()
}

const startWorkflowSimulation = () => {
  showWorkflowProgress.value = true
  workflowStatus.value = 'running'
  workflowStartTime.value = new Date()
  currentWorkflowId.value = `workflow-${Date.now()}`
  workflowMessages.value = []
  
  resetWorkflowSteps()
  updateWorkflowMessage('success', '税务报告上传成功，开始分析流程...')
  
  const stepDurations = [2000, 3000, 2500, 2000, 0, 1500]
  let totalDelay = 0
  
  workflowSteps.value.forEach((step, index) => {
    totalDelay += stepDurations[index]
    
    setTimeout(() => {
      updateWorkflowStep(index, 'running')
      updateWorkflowMessage('info', `开始执行：${step.name}`)
      
      setTimeout(() => {
        const isLastStep = index === workflowSteps.value.length - 1
        const needsReview = index === 3 && Math.random() > 0.7
        
        if (needsReview && index === 3) {
          updateWorkflowStep(index, 'warning')
          updateWorkflowMessage('warning', `${step.name}发现风险项，需要人工审核`)
          
          setTimeout(() => {
            updateWorkflowStep(4, 'running')
            updateWorkflowMessage('info', '人工审核中...')
            
            setTimeout(() => {
              updateWorkflowStep(4, 'completed')
              updateWorkflowMessage('success', '人工审核通过')
              
              setTimeout(() => {
                updateWorkflowStep(5, 'running')
                updateWorkflowMessage('info', '正在保存结果...')
                
                setTimeout(() => {
                  updateWorkflowStep(5, 'completed')
                  workflowStatus.value = 'completed'
                  updateWorkflowMessage('success', '税务分析完成！')
                  
                  setTimeout(() => {
                    activeTab.value = 'list'
                    loadReportList()
                    loadStatistics()
                  }, 2000)
                }, stepDurations[5])
              }, 3000)
            }, 2000)
          }, 500)
        } else {
          updateWorkflowStep(index, 'completed')
          updateWorkflowMessage('success', `${step.name}完成`)
          
          if (isLastStep) {
            workflowStatus.value = 'completed'
            updateWorkflowMessage('success', '税务分析完成！所有检查通过！')
            
            setTimeout(() => {
              activeTab.value = 'list'
              loadReportList()
              loadStatistics()
            }, 2000)
          }
        }
      }, stepDurations[index] - 500)
    }, totalDelay - stepDurations[index])
  })
}

const resetWorkflowSteps = () => {
  workflowSteps.value.forEach(step => {
    step.status = 'pending'
  })
  currentStepIndex.value = -1
}

const updateWorkflowStep = (index: number, status: 'pending' | 'running' | 'completed' | 'failed' | 'warning') => {
  if (index >= 0 && index < workflowSteps.value.length) {
    workflowSteps.value[index].status = status
    if (status === 'running') {
      currentStepIndex.value = index
    }
  }
}

const updateWorkflowMessage = (type: string, message: string) => {
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  workflowMessages.value.push({ time, message, type })
}

const getStepIcon = (status: string) => {
  const iconMap: Record<string, string> = {
    pending: 'Clock',
    running: 'Refresh',
    completed: 'CircleCheck',
    failed: 'Close',
    warning: 'WarningFilled'
  }
  return iconMap[status] || 'Clock'
}

const getStepClass = (status: string) => {
  return `step-item ${status}`
}

const reportList = ref<TaxReport[]>([])
const pagination = ref({
  page: 1,
  page_size: 10,
  total: 0
})

const statusFilter = ref('')
const taxTypeFilter = ref('')

const statistics = ref({
  total: 0,
  pending: 0,
  processing: 0,
  completed: 0,
  needs_review: 0
})

const getTaxTypeLabel = (type: string) => {
  const option = taxTypeOptions.find(o => o.value === type)
  return option?.label || type
}

const getTaxTypeColor = (type: string) => {
  const option = taxTypeOptions.find(o => o.value === type)
  return option?.color || '#909399'
}

const getStatusType = (status: string) => {
  const statusMap: Record<string, string> = {
    'pending': 'info',
    'processing': 'warning',
    'completed': 'success',
    'failed': 'danger',
    'pending_review': 'warning'
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    'pending': '待处理',
    'processing': '处理中',
    'completed': '已完成',
    'failed': '失败',
    'pending_review': '待审核'
  }
  return statusMap[status] || status
}

const getRiskLevelType = (level: string) => {
  const levelMap: Record<string, string> = {
    'low': 'success',
    'medium': 'warning',
    'high': 'danger',
    'critical': 'danger'
  }
  return levelMap[level] || 'info'
}

const loadReportList = async () => {
  try {
    listLoading.value = true
    const result = await taxReportApiClient.list({
      page: pagination.value.page,
      page_size: pagination.value.page_size,
      status: statusFilter.value || undefined,
      tax_type: taxTypeFilter.value || undefined
    })

    reportList.value = result.items
    pagination.value.total = result.total
  } catch (error) {
    ElMessage.error('加载报告列表失败')
  } finally {
    listLoading.value = false
  }
}

const loadStatistics = async () => {
  try {
    const stats = await taxReportApiClient.statistics()
    
    statistics.value.total = stats.total
    statistics.value.pending = stats.by_status.pending || 0
    statistics.value.processing = stats.by_status.processing || 0
    statistics.value.completed = stats.by_status.completed || 0
    statistics.value.needs_review = stats.needs_review || 0
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

const handleViewDetail = async (report: TaxReport) => {
  try {
    detailLoading.value = true
    const details = await taxReportApiClient.get(report.id)
    currentReport.value = details
    detailDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载报告详情失败')
  } finally {
    detailLoading.value = false
  }
}

const handleDelete = async (report: TaxReport) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除税务报告 "${report.filename}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await taxReportApiClient.delete(report.id)
    ElMessage.success('删除成功')
    await loadReportList()
    await loadStatistics()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handlePageChange = (page: number) => {
  pagination.value.page = page
  loadReportList()
}

const handleFilterChange = () => {
  pagination.value.page = 1
  loadReportList()
}

const formatDate = (date: string | Date) => {
  return new Date(date).toLocaleString('zh-CN')
}

onMounted(() => {
  loadReportList()
  loadStatistics()
})
</script>

<template>
  <div class="tax-submission-view">
    <div 
      v-if="isPulling || isRefreshing" 
      class="pull-indicator"
      :style="{ transform: `translateY(${pullDistance}px)` }"
    >
      <div v-if="isRefreshing" class="flex items-center gap-2">
        <el-icon class="animate-spin"><Refresh /></el-icon>
        <span class="text-sm">刷新中...</span>
      </div>
      <div v-else class="flex items-center gap-2">
        <svg 
          class="w-5 h-5 transition-transform" 
          :class="{ 'rotate-180': pullDistance >= 80 }"
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
        <span class="text-sm">下拉刷新</span>
      </div>
    </div>

    <div class="page-header">
      <div class="header-content">
        <div class="header-text">
          <h1>税务报告管理</h1>
          <p class="subtitle">AI智能分析税务报告，实时追踪处理进度</p>
        </div>
        <div v-if="statistics.total > 0" class="header-stats">
          <div class="stat-badge total smart-badge">
            <el-icon><Document /></el-icon>
            <span class="stat-label">总计</span>
            <span class="stat-value">{{ statistics.total }}</span>
          </div>
          <div class="stat-badge pending">
            <el-icon><Clock /></el-icon>
            <span class="stat-label">待处理</span>
            <span class="stat-value">{{ statistics.pending }}</span>
          </div>
          <div v-if="statistics.processing > 0" class="stat-badge processing intelligent-processing">
            <el-icon><Refresh /></el-icon>
            <span class="stat-label">处理中</span>
            <span class="stat-value">{{ statistics.processing }}</span>
          </div>
          <div class="stat-badge completed smart-badge">
            <el-icon><CircleCheck /></el-icon>
            <span class="stat-label">已完成</span>
            <span class="stat-value">{{ statistics.completed }}</span>
          </div>
          <div v-if="statistics.needs_review > 0" class="stat-badge review">
            <AlertTriangle class="text-orange-500" />
            <span class="stat-label">待审核</span>
            <span class="stat-value">{{ statistics.needs_review }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="main-content">
      <el-tabs v-model="activeTab" class="main-tabs">
        <el-tab-pane label="提交报告" name="upload">
          <div class="upload-section">
            <el-card shadow="hover" class="upload-card intelligent-card">
              <template #header>
                <div class="card-header">
                  <el-icon><Upload /></el-icon>
                  <span>上传税务报告</span>
                  <el-button 
                    type="primary" 
                    size="small" 
                    class="ml-auto"
                    @click="showManualDialog = true"
                  >
                    <el-icon><Edit /></el-icon>
                    手动录入
                  </el-button>
                </div>
              </template>
              
              <el-form label-position="top">
                <el-form-item label="税务类型">
                  <el-select v-model="selectedTaxType" class="w-full">
                    <el-option
                      v-for="option in taxTypeOptions"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>

                <el-form-item label="税务期间">
                  <div class="flex gap-2">
                    <el-select v-model="selectedYear" class="flex-1">
                      <el-option
                        v-for="year in [2020, 2021, 2022, 2023, 2024, 2025]"
                        :key="year"
                        :label="`${year}年`"
                        :value="year"
                      />
                    </el-select>
                    <el-select v-model="selectedMonth" class="flex-1">
                      <el-option
                        v-for="month in 12"
                        :key="month"
                        :label="`${month}月`"
                        :value="month"
                      />
                    </el-select>
                  </div>
                </el-form-item>
              </el-form>

              <div
                class="upload-area shimmer-effect"
                :class="{ 'is-dragging': isDragging, 'has-files': selectedFiles.length > 0 }"
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

                <div v-if="selectedFiles.length === 0" class="upload-placeholder">
                  <el-icon class="upload-icon"><Upload /></el-icon>
                  <h3 class="upload-title">拖拽报表文件到这里</h3>
                  <p class="upload-subtitle">或点击选择文件</p>
                  <div class="upload-formats">
                    <el-tag size="small" effect="plain">PDF</el-tag>
                    <el-tag size="small" effect="plain">Word</el-tag>
                    <el-tag size="small" effect="plain">Excel</el-tag>
                    <el-tag size="small" effect="plain">CSV</el-tag>
                    <el-tag size="small" effect="plain">TXT</el-tag>
                  </div>
                  <p class="upload-hint">支持多文件上传</p>
                </div>

                <div v-else class="file-list">
                  <div class="file-list-header">
                    <span class="file-count">已选择 {{ selectedFiles.length }} 个文件</span>
                    <el-button
                      @click="clearFiles"
                      type="danger"
                      size="small"
                      text
                    >
                      清空全部
                    </el-button>
                  </div>
                  <div
                    v-for="(file, index) in selectedFiles"
                    :key="index"
                    class="file-item"
                  >
                    <el-icon class="file-icon"><Document /></el-icon>
                    <div class="file-info">
                      <div class="file-name">{{ file.name }}</div>
                      <div class="file-meta">
                        <el-tag size="small" type="info">{{ formatFileSize(file.size) }}</el-tag>
                        <el-tag size="small" :type="getFileTypeTag(file.name)">
                          {{ getFileExtension(file.name) }}
                        </el-tag>
                      </div>
                    </div>
                    <el-button
                      type="danger"
                      size="small"
                      circle
                      @click.stop="removeFile(index)"
                    >
                      <el-icon><Close /></el-icon>
                    </el-button>
                  </div>
                </div>
              </div>

              <el-button
                v-if="selectedFiles.length > 0"
                type="primary"
                size="large"
                class="w-full mt-4"
                :loading="uploadLoading"
                @click="handleStartUpload"
              >
                <el-icon v-if="!uploadLoading"><Upload /></el-icon>
                {{ uploadLoading ? '上传中...' : `开始上传 (${selectedFiles.length} 个文件)` }}
              </el-button>

              <el-progress
                v-if="uploadLoading"
                :percentage="Math.round(uploadProgress)"
                class="mt-4 upload-progress intelligent-processing"
                :stroke-width="12"
                :percentage-text="`${Math.round(uploadProgress)}%`"
              >
                <template #default>
                  <span class="progress-text">
                    正在上传 {{ selectedFiles.length }} 个文件...
                  </span>
                </template>
              </el-progress>

              <el-alert
                v-if="uploadResult"
                :title="uploadResult.message"
                :type="uploadResult.success ? 'success' : 'error'"
                :closable="false"
                class="mt-4"
              />

              <div v-if="showWorkflowProgress" class="workflow-progress mt-4">
                <el-card shadow="hover" class="workflow-card intelligent-card scan-effect">
                  <template #header>
                    <div class="workflow-header">
                      <div class="workflow-title">
                        <el-icon><Refresh /></el-icon>
                        <span>AI 税务分析进度</span>
                      </div>
                      <el-tag
                        :type="workflowStatus === 'running' ? 'primary' : workflowStatus === 'completed' ? 'success' : 'danger'"
                        size="small"
                      >
                        {{ workflowStatus === 'running' ? '处理中' : workflowStatus === 'completed' ? '已完成' : '失败' }}
                      </el-tag>
                    </div>
                  </template>

                  <div class="workflow-steps">
                    <div
                      v-for="(step, index) in workflowSteps"
                      :key="index"
                      :class="getStepClass(step.status)"
                      class="workflow-step"
                    >
                      <div class="step-indicator">
                        <div class="step-number">{{ index + 1 }}</div>
                        <div v-if="index < workflowSteps.length - 1" class="step-line" />
                      </div>
                      <div class="step-content">
                        <div class="step-name">{{ step.name }}</div>
                        <div class="step-status">
                          <el-icon v-if="step.status === 'pending'" class="text-gray-400"><Clock /></el-icon>
                          <el-icon v-else-if="step.status === 'running'" class="text-blue-500 animate-spin"><Refresh /></el-icon>
                          <el-icon v-else-if="step.status === 'completed'" class="text-green-500"><CircleCheck /></el-icon>
                          <el-icon v-else-if="step.status === 'warning'" class="text-orange-500"><WarningFilled /></el-icon>
                          <el-icon v-else class="text-red-500"><Close /></el-icon>
                          <span class="ml-2">
                            {{ step.status === 'pending' ? '等待中' : step.status === 'running' ? '执行中' : step.status === 'completed' ? '已完成' : step.status === 'warning' ? '需审核' : '失败' }}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div v-if="workflowMessages.length > 0" class="workflow-messages mt-4">
                    <el-divider>处理日志</el-divider>
                    <div class="messages-list" style="max-height: 200px; overflow-y: auto;">
                      <div
                        v-for="(msg, index) in workflowMessages.slice(-10)"
                        :key="index"
                        :class="`message-${msg.type}`"
                        class="message-item"
                      >
                        <span class="message-time">{{ msg.time }}</span>
                        <span class="message-text">{{ msg.message }}</span>
                      </div>
                    </div>
                  </div>
                </el-card>
              </div>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane name="list">
          <template #label>
            <span>报告列表</span>
            <el-badge :value="statistics.total" class="tab-badge" />
          </template>

          <div class="list-section">
            <el-card class="filter-card" shadow="hover">
              <div class="filter-bar">
                <el-select 
                  v-model="statusFilter" 
                  placeholder="筛选状态"
                  clearable
                  @change="handleFilterChange"
                  class="filter-select"
                >
                  <el-option label="全部" value="" />
                  <el-option label="待处理" value="pending" />
                  <el-option label="处理中" value="processing" />
                  <el-option label="已完成" value="completed" />
                  <el-option label="失败" value="failed" />
                  <el-option label="待审核" value="pending_review" />
                </el-select>

                <el-select 
                  v-model="taxTypeFilter" 
                  placeholder="筛选税种"
                  clearable
                  @change="handleFilterChange"
                  class="filter-select"
                >
                  <el-option label="全部" value="" />
                  <el-option 
                    v-for="option in taxTypeOptions" 
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>

                <el-button @click="loadReportList">
                  <el-icon><Refresh /></el-icon>
                  刷新
                </el-button>
              </div>
            </el-card>

            <el-card class="table-card" shadow="hover">
              <el-table 
                :data="reportList" 
                v-loading="listLoading"
                stripe
                class="report-table"
              >
                <el-table-column label="文件名" min-width="200">
                  <template #default="{ row }">
                    <div class="file-cell">
                      <el-icon class="file-icon"><Document /></el-icon>
                      <div class="file-info">
                        <span class="file-name">{{ row.filename }}</span>
                        <span class="file-meta">
                          {{ formatFileSize(row.file_size) }} · {{ formatDate(row.created_at) }}
                        </span>
                      </div>
                    </div>
                  </template>
                </el-table-column>

                <el-table-column label="税务类型" width="140">
                  <template #default="{ row }">
                    <el-tag 
                      :color="getTaxTypeColor(row.tax_type)" 
                      effect="dark"
                      size="small"
                    >
                      {{ getTaxTypeLabel(row.tax_type) }}
                    </el-tag>
                  </template>
                </el-table-column>

                <el-table-column label="税务期间" width="120">
                  <template #default="{ row }">
                    {{ row.tax_period_year }}年{{ row.tax_period_month }}月
                  </template>
                </el-table-column>

                <el-table-column label="状态" width="120">
                  <template #default="{ row }">
                    <el-tag :type="getStatusType(row.status)" size="small">
                      {{ getStatusText(row.status) }}
                    </el-tag>
                  </template>
                </el-table-column>

                <el-table-column label="风险等级" width="100">
                  <template #default="{ row }">
                    <el-tag 
                      v-if="row.risk_level" 
                      :type="getRiskLevelType(row.risk_level)"
                      size="small"
                    >
                      {{ row.risk_level.toUpperCase() }}
                    </el-tag>
                    <span v-else class="text-muted">-</span>
                  </template>
                </el-table-column>

                <el-table-column label="置信度" width="100">
                  <template #default="{ row }">
                    <span v-if="row.confidence_score">
                      {{ (row.confidence_score * 100).toFixed(0) }}%
                    </span>
                    <span v-else class="text-muted">-</span>
                  </template>
                </el-table-column>

                <el-table-column label="操作" width="200" fixed="right">
                  <template #default="{ row }">
                    <div class="action-buttons">
                      <el-button 
                        type="primary" 
                        size="small"
                        @click="handleViewDetail(row)"
                        :disabled="row.status !== 'completed'"
                      >
                        <el-icon><View /></el-icon>
                        查看
                      </el-button>
                      <el-button 
                        type="danger" 
                        size="small"
                        @click="handleDelete(row)"
                      >
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </div>
                  </template>
                </el-table-column>

                <template #empty>
                  <el-empty description="暂无税务报告" :image-size="120">
                    <el-button type="primary" @click="activeTab = 'upload'">
                      上传报告
                    </el-button>
                  </el-empty>
                </template>
              </el-table>

              <el-pagination
                v-if="pagination.total > 0"
                class="pagination"
                :current-page="pagination.page"
                :page-size="pagination.page_size"
                :total="pagination.total"
                layout="total, prev, pager, next"
                @current-change="handlePageChange"
              />
            </el-card>
          </div>
        </el-tab-pane>
      </el-tabs>

      <el-dialog
        v-model="detailDialogVisible"
        title="报告详情"
        width="900px"
        :close-on-click-modal="false"
        class="detail-dialog"
      >
        <div v-loading="detailLoading" class="detail-content">
          <template v-if="currentReport">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="文件名" :span="2">
                {{ currentReport.original_filename || currentReport.filename }}
              </el-descriptions-item>
              <el-descriptions-item label="税务类型">
                <el-tag :color="getTaxTypeColor(currentReport.tax_type)" effect="dark" size="small">
                  {{ getTaxTypeLabel(currentReport.tax_type) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="税务期间">
                {{ currentReport.tax_period_year || '-' }}年{{ currentReport.tax_period_month || '-' }}月
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="getStatusType(currentReport.status)" size="small">
                  {{ getStatusText(currentReport.status) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="风险等级">
                <el-tag v-if="currentReport.risk_level" :type="getRiskLevelType(currentReport.risk_level)" size="small">
                  {{ currentReport.risk_level.toUpperCase() }}
                </el-tag>
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item label="文件大小">
                {{ formatFileSize(currentReport.file_size) }}
              </el-descriptions-item>
              <el-descriptions-item label="置信度">
                <span v-if="currentReport.confidence_score">
                  {{ (currentReport.confidence_score * 100).toFixed(1) }}%
                </span>
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item label="需要人工审核" :span="2">
                <el-tag :type="currentReport.needs_human_review ? 'warning' : 'success'" size="small">
                  {{ currentReport.needs_human_review ? '是' : '否' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="上传时间">
                {{ formatDate(currentReport.created_at) }}
              </el-descriptions-item>
              <el-descriptions-item label="更新时间">
                {{ formatDate(currentReport.updated_at) }}
              </el-descriptions-item>
            </el-descriptions>

            <div v-if="currentReport.needs_human_review" class="review-notice" style="margin-top: 20px;">
              <el-alert
                title="此报告需要人工审核"
                type="warning"
                :description="currentReport.processing_message || '系统检测到此报告可能存在风险，建议人工复核'"
                :closable="false"
                show-icon
              />
            </div>

            <div v-if="currentReport.issues?.length || currentReport.confidence_score" class="result-section" style="margin-top: 20px;">
              <el-card shadow="hover">
                <template #header>
                  <div class="card-header">
                    <FileTextIcon class="text-blue-500" />
                    <span>AI分析结果</span>
                  </div>
                </template>
                
                <div v-if="currentReport.issues?.length" class="summary-cards">
                  <el-row :gutter="12">
                    <el-col :span="8">
                      <div class="summary-card">
                        <div class="summary-value">{{ currentReport.issues?.length || 0 }}</div>
                        <div class="summary-label">总问题数</div>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="summary-card" :class="currentReport.risk_level">
                        <div class="summary-value">{{ currentReport.risk_score || 0 }}</div>
                        <div class="summary-label">风险评分</div>
                      </div>
                    </el-col>
                    <el-col :span="8">
                      <div class="summary-card" :style="{ background: currentReport.confidence_score ? `linear-gradient(135deg, #10b981 0%, #059669 100%)` : '#6b7280' }">
                        <div class="summary-value">{{ ((currentReport.confidence_score || 0) * 100).toFixed(0) }}%</div>
                        <div class="summary-label">置信度</div>
                      </div>
                    </el-col>
                  </el-row>
                </div>

                <div v-if="currentReport.issues?.length" style="margin-top: 20px;">
                  <h4 style="margin-bottom: 12px; color: #409eff;">
                    <AlertTriangle class="text-orange-500" />
                    发现的问题 ({{ currentReport.issues.length }})
                  </h4>
                  <el-alert
                    v-for="(issue, index) in currentReport.issues.slice(0, 5)"
                    :key="index"
                    :title="`[${issue.category}] ${issue.description}`"
                    :type="(issue.severity === 'high' || issue.severity === 'critical') ? 'error' : issue.severity === 'medium' ? 'warning' : 'info'"
                    :closable="false"
                    show-icon
                    style="margin-bottom: 8px;"
                  >
                    <template #default>
                      <div style="margin-top: 4px;">
                        <span v-if="issue.severity" style="font-size: 12px; color: #6b7280;">
                          风险等级: {{ issue.severity }} | 置信度: {{ ((issue.confidence || 0) * 100).toFixed(0) }}%
                        </span>
                        <div v-if="issue.recommendation" style="margin-top: 4px; font-size: 12px;">
                          <strong>建议:</strong> {{ issue.recommendation }}
                        </div>
                      </div>
                    </template>
                  </el-alert>
                  <el-link v-if="currentReport.issues.length > 5" type="primary" style="margin-top: 8px;">
                    还有 {{ currentReport.issues.length - 5 }} 个问题...
                  </el-link>
                </div>

                <div v-if="currentReport.rag_references?.length" style="margin-top: 20px;">
                  <h4 style="margin-bottom: 12px; color: #8b5cf6;">
                    <BookOpen class="text-purple-500" />
                    RAG 参考资料 ({{ currentReport.rag_references.length }})
                  </h4>
                  <el-tag
                    v-for="(ref, index) in currentReport.rag_references.slice(0, 3)"
                    :key="index"
                    type="info"
                    style="margin-right: 8px; margin-bottom: 8px;"
                  >
                    {{ ref.source || '文档' }} ({{ ((ref.relevance || ref.relevance_score || 0) * 100).toFixed(0) }}%)
                  </el-tag>
                </div>
              </el-card>
            </div>
          </template>
        </div>

        <template #footer>
          <el-button @click="detailDialogVisible = false">关闭</el-button>
        </template>
      </el-dialog>

      <ManualTaxReportDialog
        v-model:visible="showManualDialog"
        @success="handleManualSuccess"
      />
    </div>
  </div>
</template>

<style scoped>
.pull-indicator {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  background: #ffffff;
  color: #111827;
  transition: transform 0.2s ease-out;
  border-bottom: 1px solid #e5e7eb;
}

.dark .pull-indicator {
  background: #1f2937;
  color: #f9fafb;
  border-bottom: 1px solid #374151;
}

.tax-submission-view {
  min-height: 100vh;
  background: #f3f4f6;
}

.dark .tax-submission-view {
  background: #111827;
}

.page-header {
  background: white;
  padding: 24px 32px;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 10;
}

.dark .page-header {
  background: #1f2937;
  border-bottom: 1px solid #374151;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1400px;
  margin: 0 auto;
}

.header-text h1 {
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 600;
  color: #111827;
}

.dark .header-text h1 {
  color: #f9fafb;
}

.subtitle {
  margin: 0;
  font-size: 14px;
  color: #6b7280;
}

.dark .subtitle {
  color: #9ca3af;
}

.header-stats {
  display: flex;
  gap: 16px;
}

.stat-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  transition: all 0.2s;
  min-width: 80px;
  border: 1px solid #e5e7eb;
}

.dark .stat-badge {
  background: #374151;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  border: 1px solid #4b5563;
}

.stat-badge:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.dark .stat-badge:hover {
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}

.stat-badge .el-icon {
  font-size: 20px;
  margin-bottom: 4px;
}

.stat-badge.total .el-icon { color: #3b82f6; }
.stat-badge.pending .el-icon { color: #6b7280; }
.stat-badge.processing .el-icon { color: #f59e0b; }
.stat-badge.completed .el-icon { color: #10b981; }
.stat-badge.review .el-icon { color: #ef4444; }

.dark .stat-badge.total .el-icon { color: #60a5fa; }
.dark .stat-badge.pending .el-icon { color: #9ca3af; }
.dark .stat-badge.processing .el-icon { color: #fbbf24; }
.dark .stat-badge.completed .el-icon { color: #34d399; }
.dark .stat-badge.review .el-icon { color: #f87171; }

.stat-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 2px;
}

.dark .stat-label {
  color: #9ca3af;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #111827;
}

.dark .stat-value {
  color: #f9fafb;
}

.main-content {
  padding: 24px 32px;
  max-width: 1400px;
  margin: 0 auto;
  min-height: calc(100vh - 200px);
}

.main-tabs {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
}

.dark .main-tabs {
  background: #1f2937;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  border: 1px solid #374151;
}

.tab-badge {
  margin-left: 8px;
}

.list-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card {
  border-radius: 8px;
}

.dark .filter-card {
  background: #374151;
}

.dark .filter-card :deep(.el-card__body) {
  background: #374151;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.dark .filter-bar {
  color: #f9fafb;
}

.filter-select {
  width: 180px;
}

.dark .filter-select {
  background: #4b5563;
  color: #f9fafb;
}

.dark .filter-select :deep(.el-input__wrapper) {
  background: #4b5563;
  color: #f9fafb;
}

.table-card {
  border-radius: 8px;
}

.dark .table-card {
  background: #374151;
}

.dark .table-card :deep(.el-card__body) {
  background: #374151;
}

.report-table {
  border-radius: 8px;
}

.dark .report-table :deep(.el-table) {
  background: #374151;
  color: #f9fafb;
}

.dark .report-table :deep(.el-table tr) {
  background-color: #374151;
}

.dark .report-table :deep(.el-table th.el-table__cell) {
  background-color: #4b5563;
  color: #f9fafb;
}

.dark .report-table :deep(.el-table td.el-table__cell) {
  border-bottom: 1px solid #4b5563;
}

.dark .report-table :deep(.el-table__body tr:hover > td.el-table__cell) {
  background-color: #4b5563;
}

.file-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-cell .file-icon {
  font-size: 24px;
  color: #3b82f6;
}

.dark .file-cell .file-icon {
  color: #60a5fa;
}

.file-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-name {
  font-weight: 500;
  color: #111827;
}

.dark .file-name {
  color: #f9fafb;
}

.file-meta {
  font-size: 12px;
  color: #6b7280;
}

.dark .file-meta {
  color: #9ca3af;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.dark .pagination {
  color: #f9fafb;
}

.detail-content {
  min-height: 200px;
}

.dark .detail-content {
  color: #f9fafb;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #111827;
}

.dark .card-header {
  color: #f9fafb;
}

.summary-cards {
  margin-top: 16px;
}

.summary-card {
  padding: 16px;
  background: #3b82f6;
  border-radius: 8px;
  color: white;
  text-align: center;
}

.summary-card.danger {
  background: #ef4444;
}

.summary-card.warning {
  background: #f59e0b;
}

.summary-card.success {
  background: #10b981;
}

.dark .summary-card {
  background: #3b82f6;
}

.dark .summary-card.danger {
  background: #ef4444;
}

.dark .summary-card.warning {
  background: #f59e0b;
}

.dark .summary-card.success {
  background: #10b981;
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 4px;
}

.summary-label {
  font-size: 12px;
  opacity: 0.9;
}

.text-muted {
  color: #9ca3af;
  font-size: 12px;
}

.dark .text-muted {
  color: #6b7280;
}

.upload-section {
  max-width: 800px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.upload-card {
  border-radius: 12px;
}

.dark .upload-card {
  background: #374151;
}

.dark .upload-card :deep(.el-card__header) {
  background: #4b5563;
  color: #f9fafb;
}

.upload-area {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 48px 24px;
  text-align: center;
  transition: all 0.3s;
  cursor: pointer;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-area:hover {
  border-color: #3b82f6;
  background: #f9fafb;
}

.upload-area.is-dragging {
  border-color: #3b82f6;
  background: #eff6ff;
}

.upload-area.has-files {
  border-color: #10b981;
  background: #f0fdf4;
}

.dark .upload-area {
  border-color: #4b5563;
}

.dark .upload-area:hover {
  border-color: #60a5fa;
  background: #1e3a5f;
}

.dark .upload-area.is-dragging {
  border-color: #60a5fa;
  background: #1e3a5f;
}

.dark .upload-area.has-files {
  border-color: #34d399;
  background: #064e3b;
}

.upload-placeholder {
  color: #6b7280;
}

.dark .upload-placeholder {
  color: #9ca3af;
}

.upload-icon {
  font-size: 64px;
  color: #d1d5db;
  margin-bottom: 16px;
}

.dark .upload-icon {
  color: #6b7280;
}

.upload-title {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: #111827;
}

.dark .upload-title {
  color: #f9fafb;
}

.upload-subtitle {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #6b7280;
}

.dark .upload-subtitle {
  color: #9ca3af;
}

.upload-hint {
  margin: 0;
  font-size: 12px;
  color: #9ca3af;
}

.file-list {
  width: 100%;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 8px;
  transition: all 0.2s;
}

.file-item:hover {
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.dark .file-item {
  background: #4b5563;
  border-color: #6b7280;
}

.dark .file-item:hover {
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.file-item .file-icon {
  font-size: 32px;
  color: #3b82f6;
}

.dark .file-item .file-icon {
  color: #60a5fa;
}

.file-item .file-info {
  flex: 1;
  text-align: left;
}

.file-item .file-name {
  font-weight: 500;
  color: #111827;
  margin-bottom: 4px;
}

.dark .file-item .file-name {
  color: #f9fafb;
}

.file-item .file-size {
  font-size: 12px;
  color: #6b7280;
}

.dark .file-item .file-size {
  color: #9ca3af;
}

.process-steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
  border-left: 4px solid #3b82f6;
}

.dark .step {
  background: #374151;
}

.dark .step .step-number {
  background: #3b82f6;
  color: white;
}

.dark .step h4 {
  color: #f9fafb;
}

.dark .step p {
  color: #9ca3af;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #3b82f6;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}

.step-content h4 {
  margin: 0 0 4px 0;
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.step-content p {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
}

.dark .step-content p {
  color: #9ca3af;
}

.workflow-progress {
  margin-top: 20px;
}

.workflow-card {
  border-radius: 12px;
}

.dark .workflow-card {
  background: #374151;
}

.dark .workflow-card :deep(.el-card__header) {
  background: #4b5563;
  color: #f9fafb;
  border-bottom: 1px solid #6b7280;
}

.dark .workflow-card :deep(.el-card__body) {
  background: #374151;
}

.workflow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.workflow-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #111827;
}

.dark .workflow-title {
  color: #f9fafb;
}

.workflow-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 20px 0;
}

.workflow-step {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  position: relative;
}

.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 32px;
  flex-shrink: 0;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #e5e7eb;
  color: #6b7280;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  transition: all 0.3s;
  z-index: 1;
}

.dark .step-number {
  background: #4b5563;
  color: #9ca3af;
}

.workflow-step.running .step-number {
  background: #3b82f6;
  color: white;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2);
  animation: pulse-ring 1.5s ease-in-out infinite;
}

.dark .workflow-step.running .step-number {
  background: #60a5fa;
  box-shadow: 0 0 0 4px rgba(96, 165, 250, 0.2);
  animation: pulse-ring-dark 1.5s ease-in-out infinite;
}

@keyframes pulse-ring {
  0%, 100% {
    box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(59, 130, 246, 0.1);
  }
}

@keyframes pulse-ring-dark {
  0%, 100% {
    box-shadow: 0 0 0 4px rgba(96, 165, 250, 0.2);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(96, 165, 250, 0.1);
  }
}

.workflow-step.completed .step-number {
  background: #10b981;
  color: white;
}

.dark .workflow-step.completed .step-number {
  background: #34d399;
}

.workflow-step.warning .step-number {
  background: #f59e0b;
  color: white;
}

.dark .workflow-step.warning .step-number {
  background: #fbbf24;
}

.workflow-step.failed .step-number {
  background: #ef4444;
  color: white;
}

.dark .workflow-step.failed .step-number {
  background: #f87171;
}

.step-line {
  width: 2px;
  height: 40px;
  background: #e5e7eb;
  margin-top: 4px;
}

.dark .step-line {
  background: #4b5563;
}

.workflow-step.completed .step-line {
  background: #10b981;
}

.dark .workflow-step.completed .step-line {
  background: #34d399;
}

.workflow-step.running .step-line {
  background: linear-gradient(to bottom, #3b82f6, #e5e7eb);
  animation: line-flow 2s ease-in-out infinite;
}

.dark .workflow-step.running .step-line {
  background: linear-gradient(to bottom, #60a5fa, #4b5563);
  animation: line-flow-dark 2s ease-in-out infinite;
}

@keyframes line-flow {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

@keyframes line-flow-dark {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.step-content {
  flex: 1;
  padding-bottom: 16px;
}

.workflow-step:last-child .step-content {
  padding-bottom: 0;
}

.step-name {
  font-weight: 500;
  color: #111827;
  margin-bottom: 4px;
}

.dark .step-name {
  color: #f9fafb;
}

.workflow-step.pending .step-name {
  color: #9ca3af;
}

.dark .workflow-step.pending .step-name {
  color: #6b7280;
}

.step-status {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: #6b7280;
}

.dark .step-status {
  color: #9ca3af;
}

.workflow-messages {
  border-top: 1px solid #e5e7eb;
  padding-top: 16px;
  max-height: 200px;
  overflow-y: auto;
}

.dark .workflow-messages {
  border-top-color: #4b5563;
}

.messages-title {
  font-weight: 600;
  font-size: 14px;
  color: #111827;
  margin-bottom: 12px;
}

.dark .messages-title {
  color: #f9fafb;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-item {
  display: flex;
  gap: 12px;
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 6px;
  font-size: 13px;
  border-left: 3px solid #d1d5db;
}

.dark .message-item {
  background: #4b5563;
}

.message-time {
  color: #6b7280;
  font-family: monospace;
  flex-shrink: 0;
}

.dark .message-time {
  color: #9ca3af;
}

.message-text {
  color: #374151;
}

.dark .message-text {
  color: #e5e7eb;
}

.message-success {
  border-left-color: #10b981;
  background: #f0fdf4;
}

.dark .message-success {
  background: #064e3b;
}

.message-success .message-text {
  color: #065f46;
}

.dark .message-success .message-text {
  color: #a7f3d0;
}

.message-warning {
  border-left-color: #f59e0b;
  background: #fffbeb;
}

.dark .message-warning {
  background: #451a03;
}

.message-warning .message-text {
  color: #92400e;
}

.dark .message-warning .message-text {
  color: #fde68a;
}

.message-error {
  border-left-color: #ef4444;
  background: #fef2f2;
}

.dark .message-error {
  background: #450a0a;
}

.message-error .message-text {
  color: #991b1b;
}

.dark .message-error .message-text {
  color: #fecaca;
}

.message-info {
  border-left-color: #3b82f6;
}

.dark .message-info {
  border-left-color: #60a5fa;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.upload-progress {
  border-radius: 8px;
  overflow: hidden;
}

.upload-progress :deep(.el-progress-bar__outer) {
  background: #e5e7eb;
  border-radius: 8px;
}

.dark .upload-progress :deep(.el-progress-bar__outer) {
  background: #4b5563;
}

.upload-progress :deep(.el-progress-bar__inner) {
  background: linear-gradient(90deg, #3b82f6 0%, #10b981 100%);
  border-radius: 8px;
  transition: width 0.3s ease;
}

.dark .upload-progress :deep(.el-progress-bar__inner) {
  background: linear-gradient(90deg, #60a5fa 0%, #34d399 100%);
}

.progress-text {
  color: #374151;
  font-size: 14px;
  font-weight: 500;
}

.dark .progress-text {
  color: #f9fafb;
}

@media (max-width: 768px) {
  .header-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .header-stats {
    flex-wrap: wrap;
    margin-top: 16px;
    width: 100%;
    gap: 8px;
  }

  .stat-badge {
    flex: 1;
    min-width: 100px;
    padding: 8px 12px;
    font-size: 12px;
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .filter-select {
    width: 100%;
  }

  .main-content {
    padding: 16px;
  }

  .page-header {
    padding: 16px;
  }

  .upload-area {
    padding: 24px 16px;
    min-height: 180px;
  }

  .upload-icon {
    font-size: 48px;
  }

  .upload-title {
    font-size: 16px;
  }

  .file-item {
    padding: 8px;
  }

  .file-icon {
    font-size: 24px;
  }

  .workflow-steps {
    padding: 12px 0;
  }

  .step-indicator {
    width: 24px;
  }

  .step-number {
    width: 28px;
    height: 28px;
    font-size: 12px;
  }

  .workflow-messages {
    max-height: 150px;
  }
}

/* 智能AI动画效果 */
@keyframes intelligent-pulse {
  0%, 100% {
    opacity: 0.8;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.02);
  }
}

@keyframes data-flow {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

@keyframes glow-pulse {
  0%, 100% {
    box-shadow: 0 0 5px rgba(59, 130, 246, 0.5),
                0 0 10px rgba(59, 130, 246, 0.3),
                0 0 15px rgba(59, 130, 246, 0.1);
  }
  50% {
    box-shadow: 0 0 10px rgba(59, 130, 246, 0.8),
                0 0 20px rgba(59, 130, 246, 0.5),
                0 0 30px rgba(59, 130, 246, 0.3);
  }
}

@keyframes breathing-glow {
  0%, 100% {
    box-shadow: 0 0 2px rgba(16, 185, 129, 0.4),
                0 0 4px rgba(16, 185, 129, 0.2);
  }
  50% {
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.6),
                0 0 16px rgba(16, 185, 129, 0.4),
                0 0 24px rgba(16, 185, 129, 0.2);
  }
}

@keyframes scan-line {
  0% {
    transform: translateY(-100%);
    opacity: 0;
  }
  10% {
    opacity: 0.5;
  }
  90% {
    opacity: 0.5;
  }
  100% {
    transform: translateY(100%);
    opacity: 0;
  }
}

@keyframes particle-float {
  0%, 100% {
    transform: translateY(0) translateX(0);
    opacity: 0;
  }
  10% {
    opacity: 1;
  }
  90% {
    opacity: 1;
  }
  100% {
    transform: translateY(-20px) translateX(10px);
    opacity: 0;
  }
}

@keyframes shimmer {
  0% {
    background-position: -200% 0;
  }
  100% {
    background-position: 200% 0;
  }
}

@keyframes ripple {
  0% {
    transform: scale(0.8);
    opacity: 1;
  }
  100% {
    transform: scale(2);
    opacity: 0;
  }
}

.intelligent-card {
  animation: intelligent-pulse 3s ease-in-out infinite;
  position: relative;
  overflow: hidden;
}

.intelligent-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, #3b82f6, #10b981, transparent);
  background-size: 200% 100%;
  animation: data-flow 3s ease-in-out infinite;
}

.intelligent-processing {
  animation: glow-pulse 2s ease-in-out infinite;
}

.smart-badge {
  animation: breathing-glow 2s ease-in-out infinite;
}

.scan-effect {
  position: relative;
}

.scan-effect::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, transparent, #3b82f6, transparent);
  animation: scan-line 2s ease-in-out infinite;
  pointer-events: none;
}

.shimmer-effect {
  background: linear-gradient(
    90deg,
    rgba(59, 130, 246, 0.1) 0%,
    rgba(59, 130, 246, 0.3) 50%,
    rgba(59, 130, 246, 0.1) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 2s ease-in-out infinite;
}

.processing-indicator {
  position: relative;
}

.processing-indicator::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 20px;
  height: 20px;
  border: 2px solid rgba(59, 130, 246, 0.3);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  animation: ripple 1.5s ease-out infinite;
}

.dark .intelligent-card::before {
  background: linear-gradient(90deg, transparent, #60a5fa, #34d399, transparent);
}

.dark .intelligent-processing {
  animation: glow-pulse 2s ease-in-out infinite;
}

.dark .smart-badge {
  animation: breathing-glow 2s ease-in-out infinite;
}

.dark .scan-effect::after {
  background: linear-gradient(90deg, transparent, #60a5fa, transparent);
}

.dark .shimmer-effect {
  background: linear-gradient(
    90deg,
    rgba(96, 165, 250, 0.1) 0%,
    rgba(96, 165, 250, 0.3) 50%,
    rgba(96, 165, 250, 0.1) 100%
  );
}
</style>
