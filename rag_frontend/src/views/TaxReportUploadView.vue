<template>
  <div class="tax-report-upload">
    <div class="page-header">
      <div class="header-content">
        <div class="header-text">
          <h1>税务报告上传</h1>
          <p class="subtitle">上传税务报告文件，系统将自动进行AI分析和验证</p>
        </div>
        <div class="header-stats">
          <div class="stat-badge">
            <el-icon><Upload /></el-icon>
            <span>{{ todayStats.total }}</span>
          </div>
          <div class="stat-badge success">
            <el-icon><Check /></el-icon>
            <span>{{ todayStats.completed }}</span>
          </div>
          <div class="stat-badge warning">
            <el-icon><Clock /></el-icon>
            <span>{{ todayStats.pending }}</span>
          </div>
          <el-button type="primary" @click="showManualDialog = true">
            <el-icon><Edit /></el-icon>
            手动录入
          </el-button>
        </div>
      </div>
    </div>

    <div class="animated-gradient"></div>

    <div class="main-content">
      <!-- 左侧上传区域 -->
      <div class="left-panel">
        <el-card class="upload-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <div class="header-title">
                <el-icon><Upload /></el-icon>
                <span>上传文件</span>
              </div>
              <el-button link @click="showBatchUpload = !showBatchUpload">
                {{ showBatchUpload ? '单文件上传' : '批量上传' }}
              </el-button>
            </div>
          </template>

          <el-form :model="form" label-width="100px" v-if="!showBatchUpload">
            <el-form-item label="选择文件">
              <el-upload
                ref="uploadRef"
                class="upload-demo"
                drag
                :auto-upload="false"
                :limit="1"
                :on-change="handleFileChange"
                :on-remove="handleFileRemove"
                :file-list="fileList"
                accept=".pdf,.xlsx,.xls,.jpg,.jpeg,.png"
              >
                <div class="upload-content">
                  <el-icon class="upload-icon"><UploadFilled /></el-icon>
                  <div class="upload-text">
                    拖拽文件到此处或 <em>点击上传</em>
                  </div>
                  <div class="upload-tip">
                    支持 PDF、Excel、图片格式，单个文件不超过 50MB
                  </div>
                </div>
              </el-upload>
            </el-form-item>

            <el-form-item label="税务类型">
              <el-select v-model="form.tax_type" placeholder="请选择税务类型" clearable>
                <el-option label="增值税" value="vat" />
                <el-option label="企业所得税" value="income" />
                <el-option label="个人所得税" value="personal" />
                <el-option label="消费税" value="consumption" />
                <el-option label="行为税" value="behavior" />
              </el-select>
            </el-form-item>

            <el-form-item label="所属期">
              <el-date-picker
                v-model="taxPeriod"
                type="month"
                placeholder="选择税务所属期"
                format="YYYY-MM"
                value-format="YYYY-MM"
              />
            </el-form-item>

            <el-form-item label="备注">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="2"
                placeholder="可选：添加备注信息"
              />
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                @click="handleUpload"
                :loading="uploading"
                :disabled="!selectedFile"
                size="large"
                class="upload-btn"
              >
                {{ uploading ? '上传中...' : '开始上传' }}
              </el-button>
              <el-button @click="resetForm" size="large">重置</el-button>
            </el-form-item>
          </el-form>

          <!-- 批量上传模式 -->
          <div v-else class="batch-upload">
            <el-upload
              ref="batchUploadRef"
              class="upload-demo"
              drag
              :auto-upload="false"
              :multiple="true"
              :on-change="handleBatchFileChange"
              :on-remove="handleBatchFileRemove"
              :file-list="batchFileList"
              accept=".pdf,.xlsx,.xls,.jpg,.jpeg,.png"
            >
              <div class="upload-content">
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <div class="upload-text">
                  拖拽文件到此处或 <em>点击上传</em>
                </div>
                <div class="upload-tip">
                  支持批量上传多个文件，单个文件不超过 50MB
                </div>
              </div>
            </el-upload>

            <el-form :model="batchForm" label-width="100px" class="batch-form">
              <el-form-item label="统一税务类型">
                <el-select v-model="batchForm.tax_type" placeholder="可选：统一设置" clearable>
                  <el-option label="增值税" value="vat" />
                  <el-option label="企业所得税" value="income" />
                  <el-option label="个人所得税" value="personal" />
                  <el-option label="消费税" value="consumption" />
                  <el-option label="行为税" value="behavior" />
                </el-select>
              </el-form-item>

              <el-form-item label="统一所属期">
                <el-date-picker
                  v-model="batchTaxPeriod"
                  type="month"
                  placeholder="可选：统一设置"
                  format="YYYY-MM"
                  value-format="YYYY-MM"
                />
              </el-form-item>

              <el-form-item>
                <el-button
                  type="primary"
                  @click="handleBatchUpload"
                  :loading="uploading"
                  :disabled="batchFileList.length === 0"
                  size="large"
                >
                  {{ uploading ? '上传中...' : `开始上传 (${batchFileList.length})` }}
                </el-button>
                <el-button @click="resetBatchForm" size="large">重置</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-card>

        <!-- 实时处理状态 -->
        <el-card v-if="processingSteps.length > 0" class="processing-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <div class="header-title">
                <el-icon class="is-loading processing-icon"><Loading /></el-icon>
                <span>实时处理状态</span>
              </div>
              <el-tag v-if="currentStatus" :type="getStatusTagType(currentStatus)" effect="dark" size="small">
                {{ getStatusText(currentStatus) }}
              </el-tag>
            </div>
          </template>

          <div class="processing-steps">
            <div
              v-for="(step, index) in processingSteps"
              :key="index"
              :class="['step-item', { 'step-active': step.status === 'active', 'step-completed': step.status === 'completed', 'step-error': step.status === 'error' }]"
            >
              <div class="step-indicator">
                <div class="step-dot" :class="step.status">
                  <el-icon v-if="step.status === 'completed'"><Check /></el-icon>
                  <el-icon v-else-if="step.status === 'error'"><Close /></el-icon>
                  <el-icon v-else class="is-loading"><Loading /></el-icon>
                </div>
                <div v-if="index < processingSteps.length - 1" class="step-line" :class="step.status" />
              </div>
              <div class="step-content">
                <div class="step-title">{{ step.title }}</div>
                <div class="step-description">{{ step.description }}</div>
                <div v-if="step.progress !== undefined" class="step-progress">
                  <el-progress :percentage="step.progress" :show-text="false" :stroke-width="6" :color="getStepColor(step.status)" />
                </div>
              </div>
            </div>
          </div>

          <div v-if="processingDetails" class="processing-details">
            <div class="details-header">
              <el-icon><Document /></el-icon>
              <span>详细信息</span>
            </div>
            <pre class="details-content">{{ processingDetails }}</pre>
          </div>
        </el-card>
      </div>

      <!-- 右侧统计区域 -->
      <div class="right-panel">
        <el-card class="stats-card" shadow="hover">
          <template #header>
            <div class="header-title">
              <el-icon><DataLine /></el-icon>
              <span>今日统计</span>
            </div>
          </template>
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-value text-primary">{{ todayStats.total }}</div>
              <div class="stat-label">上传总数</div>
            </div>
            <div class="stat-item">
              <div class="stat-value text-success">{{ todayStats.completed }}</div>
              <div class="stat-label">已完成</div>
            </div>
            <div class="stat-item">
              <div class="stat-value text-warning">{{ todayStats.pending }}</div>
              <div class="stat-label">处理中</div>
            </div>
            <div class="stat-item">
              <div class="stat-value text-danger">{{ todayStats.needsReview }}</div>
              <div class="stat-label">待审核</div>
            </div>
          </div>
        </el-card>

        <el-card class="tips-card" shadow="hover">
          <template #header>
            <div class="header-title">
              <el-icon><InfoFilled /></el-icon>
              <span>使用提示</span>
            </div>
          </template>
          <ul class="tips-list">
            <li>支持 PDF、Excel、图片等格式文件上传</li>
            <li>系统会自动识别税务类型和关键信息</li>
            <li>检测到异常时会自动创建人工审核任务</li>
            <li>高风险报告建议人工复核确认</li>
          </ul>
        </el-card>
      </div>
    </div>

    <!-- 历史记录 -->
    <el-card class="history-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <el-icon><Clock /></el-icon>
            <span>历史记录</span>
          </div>
          <el-button link @click="loadReports">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>

      <div class="filter-bar">
        <el-form inline :model="filterForm">
          <el-form-item label="状态">
            <el-select v-model="filterForm.status" placeholder="全部" clearable size="default">
              <el-option label="待处理" value="pending" />
              <el-option label="处理中" value="processing" />
              <el-option label="已完成" value="completed" />
              <el-option label="失败" value="failed" />
              <el-option label="待审核" value="pending_review" />
            </el-select>
          </el-form-item>
          <el-form-item label="风险等级">
            <el-select v-model="filterForm.risk_level" placeholder="全部" clearable size="default">
              <el-option label="低" value="low" />
              <el-option label="中" value="medium" />
              <el-option label="高" value="high" />
              <el-option label="严重" value="critical" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadReports">查询</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="reportList" v-loading="loading" stripe>
        <el-table-column prop="original_filename" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column prop="file_type" label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.file_type?.toUpperCase() || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="tax_type" label="税务类型" width="100">
          <template #default="{ row }">
            <span class="tax-type">{{ getTaxTypeName(row.tax_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="risk_level" label="风险" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.risk_level" :type="getRiskType(row.risk_level)" size="small">
              {{ getRiskLabel(row.risk_level) }}
            </el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="confidence_score" label="置信度" width="100" align="center">
          <template #default="{ row }">
            <div v-if="row.confidence_score" class="confidence-bar">
              <el-progress
                :percentage="Math.round(row.confidence_score * 100)"
                :color="getConfidenceColor(row.confidence_score)"
                :show-text="false"
                :stroke-width="6"
              />
              <span class="confidence-text">{{ Math.round(row.confidence_score * 100) }}%</span>
            </div>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="160">
          <template #default="{ row }">
            <span class="time-text">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewDetails(row)">
              详情
            </el-button>
            <el-button
              link
              type="danger"
              @click="handleDelete(row)"
              v-if="row.status !== 'processing'"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadReports"
          @current-change="loadReports"
        />
      </div>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="currentReport?.original_filename || '报告详情'"
      width="1000px"
      :close-on-click-modal="false"
      class="detail-dialog"
    >
      <div v-if="currentReport" class="report-details">
        <el-descriptions :column="2" border class="basic-info">
          <el-descriptions-item label="文件名">
            {{ currentReport.original_filename }}
          </el-descriptions-item>
          <el-descriptions-item label="文件类型">
            <el-tag size="small">{{ currentReport.file_type?.toUpperCase() }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="税务类型">
            {{ getTaxTypeName(currentReport.tax_type) }}
          </el-descriptions-item>
          <el-descriptions-item label="所属期">
            {{ currentReport.tax_period_year }}-{{ String(currentReport.tax_period_month).padStart(2, '0') }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTagType(currentReport.status)">
              {{ getStatusText(currentReport.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag v-if="currentReport.risk_level" :type="getRiskType(currentReport.risk_level)">
              {{ getRiskLabel(currentReport.risk_level) }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="置信度">
            <span v-if="currentReport.confidence_score" class="confidence-badge" :style="{ backgroundColor: getConfidenceColor(currentReport.confidence_score) }">
              {{ (currentReport.confidence_score * 100).toFixed(1) }}%
            </span>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="需要人工审核">
            <el-tag :type="currentReport.needs_human_review ? 'warning' : 'success'">
              {{ currentReport.needs_human_review ? '是' : '否' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="currentReport.processing_result" class="result-section">
          <div class="section-header">
            <el-icon><DataAnalysis /></el-icon>
            <h4>AI分析结果</h4>
          </div>

          <el-row :gutter="20" class="summary-cards">
            <el-col :span="6">
              <div class="summary-card">
                <div class="summary-value">{{ currentReport.processing_result.summary?.total_issues || 0 }}</div>
                <div class="summary-label">总问题数</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-card danger">
                <div class="summary-value">{{ currentReport.processing_result.summary?.high_severity_issues || 0 }}</div>
                <div class="summary-label">高严重问题</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-card warning">
                <div class="summary-value">¥{{ formatNumber(currentReport.processing_result.summary?.tax_amount_at_risk || 0) }}</div>
                <div class="summary-label">风险金额</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-card" :class="currentReport.risk_level">
                <div class="summary-value">{{ currentReport.overall_risk_score?.toFixed(1) || '-' }}</div>
                <div class="summary-label">风险评分</div>
              </div>
            </el-col>
          </el-row>

          <el-tabs v-if="hasIssueTabs" class="issue-tabs">
            <el-tab-pane label="税务问题" v-if="currentReport.processing_result.tax_findings?.length">
              <IssueList :issues="currentReport.processing_result.tax_findings" type="tax" />
            </el-tab-pane>
            <el-tab-pane label="财务问题" v-if="currentReport.processing_result.finance_findings?.length">
              <IssueList :issues="currentReport.processing_result.finance_findings" type="finance" />
            </el-tab-pane>
            <el-tab-pane label="法务问题" v-if="currentReport.processing_result.legal_findings?.length">
              <IssueList :issues="currentReport.processing_result.legal_findings" type="legal" />
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button v-if="currentReport?.needs_human_review" type="warning" @click="goToReview">
          前往审核
        </el-button>
      </template>
    </el-dialog>

    <ManualTaxReportDialog
      v-model:visible="showManualDialog"
      @success="handleManualSuccess"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload,
  UploadFilled,
  Refresh,
  Loading,
  Check,
  Close,
  Document,
  DataLine,
  InfoFilled,
  Clock,
  DataAnalysis,
  TrendCharts,
  MagicStick,
  Edit
} from '@element-plus/icons-vue'
import { taxReportApiClient } from '@/api/tax-report'
import ManualTaxReportDialog from '@/components/ManualTaxReportDialog.vue'
import type {
  TaxReport,
  TaxReportUploadResponse,
  TaxReportFilter,
  TaxReportStatusResponse,
  TaxTypeEnum,
  TaxIssue
} from '@/types/tax'

const showBatchUpload = ref(false)
const showManualDialog = ref(false)
const uploading = ref(false)
const loading = ref(false)
const fileList = ref<any[]>([])
const batchFileList = ref<any[]>([])
const selectedFile = ref<File | null>(null)
const uploadRef = ref()
const batchUploadRef = ref()

const form = reactive({
  tax_type: '',
  description: ''
})

const batchForm = reactive({
  tax_type: ''
})

const taxPeriod = ref('')
const batchTaxPeriod = ref('')
const uploadProgress = ref<TaxReportUploadResponse | null>(null)
const processingStatus = ref('')
const currentStatus = ref('')

interface ProcessingStep {
  title: string
  description: string
  status: 'pending' | 'active' | 'completed' | 'error'
  progress?: number
}

const processingSteps = ref<ProcessingStep[]>([])
const processingDetails = ref('')

const filterForm = reactive({
  status: '',
  risk_level: ''
})

const reportList = ref<TaxReport[]>([])
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const detailDialogVisible = ref(false)
const currentReport = ref<TaxReport | null>(null)

const todayStats = reactive({
  total: 0,
  completed: 0,
  pending: 0,
  needsReview: 0
})

let pollingInterval: number | null = null
let eventSource: EventSource | null = null

const hasIssueTabs = computed(() => {
  if (!currentReport.value?.processing_result) return false
  const result = currentReport.value.processing_result
  return (result.tax_findings?.length || 0) + (result.finance_findings?.length || 0) + (result.legal_findings?.length || 0) > 0
})

const handleFileChange = (file: any) => {
  selectedFile.value = file.raw
  fileList.value = [file]
}

const handleFileRemove = () => {
  selectedFile.value = null
  fileList.value = []
}

const handleBatchFileChange = (file: any) => {
  batchFileList.value.push(file)
}

const handleBatchFileRemove = (file: any) => {
  const index = batchFileList.value.indexOf(file)
  if (index > -1) {
    batchFileList.value.splice(index, 1)
  }
}

const initProcessingSteps = () => {
  processingSteps.value = [
    { title: '文件上传', description: '正在上传文件到服务器', status: 'pending', progress: 0 },
    { title: '文件解析', description: '提取文本内容和结构', status: 'pending', progress: 0 },
    { title: '税务识别', description: '识别税务类型和关键指标', status: 'pending', progress: 0 },
    { title: 'AI分析', description: '进行税务逻辑验证和异常检测', status: 'pending', progress: 0 },
    { title: '风险评估', description: '评估风险等级和置信度', status: 'pending', progress: 0 }
  ]
}

const updateStepStatus = (stepIndex: number, status: ProcessingStep['status'], description?: string, progress?: number) => {
  if (stepIndex < processingSteps.value.length) {
    const step = processingSteps.value[stepIndex]
    step.status = status
    if (description) step.description = description
    if (progress !== undefined) step.progress = progress
  }
}

const handleUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }

  console.log('🔍 [TaxUpload] 开始上传流程')
  console.log('🔍 [TaxUpload] 文件:', selectedFile.value.name, selectedFile.value.size)
  console.log('🔍 [TaxUpload] tax_type:', form.tax_type)
  console.log('🔍 [TaxUpload] API_BASE:', import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000')

  if (!form.tax_type) {
    ElMessage.warning('请选择税务类型')
    return
  }

  try {
    uploading.value = true
    initProcessingSteps()
    updateStepStatus(0, 'active', '正在上传文件...', 0)
    processingDetails.value = ''

    const [year, month] = (taxPeriod.value || '').split('-')

    console.log('🔍 [TaxUpload] 调用 API，参数:', {
      tax_type: form.tax_type,
      tax_period_year: year ? parseInt(year) : undefined,
      tax_period_month: month ? parseInt(month) : undefined,
    })

    const result = await taxReportApiClient.upload(selectedFile.value, {
      tax_type: form.tax_type as TaxTypeEnum,
      tax_period_year: year ? parseInt(year) : undefined,
      tax_period_month: month ? parseInt(month) : undefined,
      description: form.description,
      onProgress: (progress) => {
        updateStepStatus(0, 'active', `上传进度: ${progress}%`, progress)
      }
    })

    console.log('🔍 [TaxUpload] 上传成功，结果:', result)

    updateStepStatus(0, 'completed', '文件上传完成', 100)
    uploadProgress.value = result
    ElMessage.success('文件上传成功，正在处理中...')

    updateStepStatus(1, 'active', '开始解析文件...')
    startProcessing(result.id)

  } catch (error: any) {
    console.error('🔍 [TaxUpload] 上传失败，错误:', error)
    updateStepStatus(0, 'error', error.response?.data?.detail || error.message || '上传失败')
    ElMessage.error(error.response?.data?.detail || error.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

const startProcessing = (reportId: string) => {
  pollingInterval = window.setInterval(async () => {
    try {
      const status = await taxReportApiClient.getStatus(reportId)
      currentStatus.value = status.status
      processingDetails.value = status.processing_message || ''

      updateStepStatus(1, status.progress_percent && status.progress_percent > 20 ? 'completed' : 'active',
        '文件解析中...', Math.min(status.progress_percent * 2, 40))
      updateStepStatus(2, status.progress_percent && status.progress_percent > 40 ? 'completed' : 'active',
        '税务识别中...', Math.min((status.progress_percent - 20) * 2, 30))
      updateStepStatus(3, status.progress_percent && status.progress_percent > 70 ? 'completed' : 'active',
        'AI分析中...', Math.min((status.progress_percent - 40) * 2, 20))
      updateStepStatus(4, status.progress_percent === 100 ? 'completed' : 'active',
        '风险评估中...', Math.min((status.progress_percent - 70) * 2, 10))

      if (status.status === 'completed') {
        ElMessage.success('处理完成!')
        completeAllSteps()
        stopPolling()
        loadReports()
        loadTodayStats()
      } else if (status.status === 'failed') {
        ElMessage.error('处理失败')
        updateStepStatus(3, 'error', '处理失败')
        stopPolling()
      } else if (status.status === 'pending_review') {
        ElMessage.warning('需要人工审核')
        completeAllSteps()
        stopPolling()
        loadReports()
      }
    } catch (error) {
      console.error('轮询状态失败:', error)
    }
  }, 1500)
}

const completeAllSteps = () => {
  processingSteps.value.forEach(step => {
    if (step.status !== 'completed') {
      step.status = 'completed'
      step.progress = 100
    }
  })
}

const stopPolling = () => {
  if (pollingInterval) {
    clearInterval(pollingInterval)
    pollingInterval = null
  }
  processingStatus.value = ''
}

const handleBatchUpload = async () => {
  if (batchFileList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }

  try {
    uploading.value = true
    const files = batchFileList.value.map((f: any) => f.raw)
    const [year, month] = (batchTaxPeriod.value || '').split('-')

    let completed = 0
    const result = await taxReportApiClient.batchUpload(files, {
      tax_type: batchForm.tax_type as TaxTypeEnum,
      tax_period_year: year ? parseInt(year) : undefined,
      tax_period_month: month ? parseInt(month) : undefined,
      onProgress: (c, t) => {
        completed = c
        processingStatus.value = `上传中: ${c}/${t}`
      }
    })

    ElMessage.success(`上传完成: ${result.successful} 成功, ${result.failed} 失败`)

    if (result.errors.length > 0) {
      console.error('上传失败的文件:', result.errors)
    }

    resetBatchForm()
    loadReports()
    loadTodayStats()

  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '批量上传失败')
  } finally {
    uploading.value = false
    processingStatus.value = ''
  }
}

const loadReports = async () => {
  try {
    loading.value = true
    const filter: TaxReportFilter = {
      status: filterForm.status as any,
      risk_level: filterForm.risk_level as any,
      page: pagination.page,
      page_size: pagination.pageSize
    }

    const result = await taxReportApiClient.list(filter)
    reportList.value = result.items
    pagination.total = result.total
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

const loadTodayStats = async () => {
  try {
    const result = await taxReportApiClient.list({ page_size: 100 })
    const today = new Date().toDateString()
    const todayReports = result.items.filter(r => new Date(r.created_at).toDateString() === today)

    todayStats.total = todayReports.length
    todayStats.completed = todayReports.filter(r => r.status === 'completed').length
    todayStats.pending = todayReports.filter(r => r.status === 'processing' || r.status === 'pending').length
    todayStats.needsReview = todayReports.filter(r => r.needs_human_review).length
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const viewDetails = async (report: TaxReport) => {
  try {
    const details = await taxReportApiClient.get(report.id)
    currentReport.value = details
    detailDialogVisible.value = true
  } catch (error: any) {
    ElMessage.error('加载详情失败')
  }
}

const handleDelete = async (report: TaxReport) => {
  try {
    await ElMessageBox.confirm('确定要删除这个报告吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await taxReportApiClient.delete(report.id)
    ElMessage.success('删除成功')
    loadReports()
    loadTodayStats()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

const handleManualSuccess = (data: any) => {
  ElMessage.success({
    message: '税务报告录入成功',
    duration: 2000,
  })
  if (data.run_analysis) {
    ElMessage.info({
      message: 'AI分析任务已启动，请稍后在列表中查看结果',
      duration: 3000,
    })
  }
  loadReports()
}

const goToReview = () => {
  detailDialogVisible.value = false
  window.location.href = '/review'
}

const resetForm = () => {
  form.tax_type = ''
  form.description = ''
  taxPeriod.value = ''
  selectedFile.value = null
  fileList.value = []
  uploadProgress.value = null
  processingStatus.value = ''
  processingSteps.value = []
  processingDetails.value = ''
  currentStatus.value = ''
  stopPolling()
}

const resetBatchForm = () => {
  batchForm.tax_type = ''
  batchTaxPeriod.value = ''
  batchFileList.value = []
  processingStatus.value = ''
}

const getStatusTagType = (status: string) => {
  const typeMap: Record<string, string> = {
    pending: 'info',
    processing: 'warning',
    completed: 'success',
    failed: 'danger',
    pending_review: 'warning'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待处理',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
    pending_review: '待审核'
  }
  return textMap[status] || status
}

const getRiskType = (level: string) => {
  const typeMap: Record<string, string> = {
    low: 'success',
    medium: 'warning',
    high: 'danger',
    critical: 'danger'
  }
  return typeMap[level] || 'info'
}

const getRiskLabel = (level: string) => {
  const labelMap: Record<string, string> = {
    low: '低',
    medium: '中',
    high: '高',
    critical: '严重'
  }
  return labelMap[level] || level
}

const getTaxTypeName = (type?: string) => {
  if (!type) return '-'
  const nameMap: Record<string, string> = {
    vat: '增值税',
    income: '企业所得税',
    personal: '个人所得税',
    consumption: '消费税',
    behavior: '行为税'
  }
  return nameMap[type] || type
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatNumber = (num: number) => {
  return num.toLocaleString('zh-CN')
}

const getConfidenceColor = (score: number) => {
  if (score >= 0.9) return '#67c23a'
  if (score >= 0.7) return '#409eff'
  if (score >= 0.5) return '#e6a23c'
  return '#f56c6c'
}

const getStepColor = (status: string) => {
  const colorMap: Record<string, string> = {
    pending: '#909399',
    active: '#409eff',
    completed: '#67c23a',
    error: '#f56c6c'
  }
  return colorMap[status] || '#409eff'
}

onMounted(() => {
  loadReports()
  loadTodayStats()
})

onUnmounted(() => {
  stopPolling()
  if (eventSource) {
    eventSource.close()
  }
})
</script>

<script lang="ts">
import { defineComponent, h } from 'vue'
import { ElTag, ElAlert } from 'element-plus'

const IssueList = defineComponent({
  name: 'IssueList',
  props: {
    issues: { type: Array as () => TaxIssue[], required: true },
    type: { type: String, required: true }
  },
  setup(props) {
    const getSeverityType = (severity: string) => {
      const map: Record<string, string> = {
        low: 'info',
        medium: 'warning',
        high: 'danger',
        critical: 'danger'
      }
      return map[severity] || 'info'
    }

    const getSeverityLabel = (severity: string) => {
      const map: Record<string, string> = {
        low: '低',
        medium: '中',
        high: '高',
        critical: '严重'
      }
      return map[severity] || severity
    }

    return () => h('div', { class: 'issue-list' },
      props.issues.map((issue, index) =>
        h(ElAlert, {
          key: index,
          type: getSeverityType(issue.severity),
          showIcon: true,
          closable: false,
          class: 'issue-item'
        }, {
          title: () => [
            h('span', { class: 'issue-type' }, issue.issue_type),
            h(ElTag, { size: 'small', type: getSeverityType(issue.severity) }, { default: () => getSeverityLabel(issue.severity) })
          ],
          default: () => [
            h('div', { class: 'issue-content' }, [
              h('p', { class: 'issue-description' }, issue.description),
              h('div', { class: 'issue-meta' }, [
                issue.location && h('span', { class: 'meta-item' }, `位置: ${issue.location}`),
                issue.amount && h('span', { class: 'meta-item' }, `金额: ¥${issue.amount.toLocaleString()}`),
                issue.suggestion && h('span', { class: 'meta-item suggestion' }, issue.suggestion)
              ].filter(Boolean))
            ])
          ]
        })
      )
    )
  }
})
</script>

<style scoped>
.tax-report-upload {
  padding: 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%);
  min-height: calc(100vh - 60px);
  position: relative;
  overflow: hidden;
}

.animated-gradient {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 300px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  opacity: 0.05;
  pointer-events: none;
}

.page-header {
  margin-bottom: 24px;
  position: relative;
  z-index: 1;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  padding: 24px 32px;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.header-text h1 {
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 700;
  color: #1a1a2e;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  color: #64748b;
  margin: 0;
  font-size: 14px;
}

.header-stats {
  display: flex;
  gap: 12px;
}

.stat-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  border-radius: 12px;
  font-weight: 600;
  color: #475569;
  transition: all 0.3s ease;
}

.stat-badge:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-badge.success {
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
  color: #065f46;
}

.stat-badge.warning {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #92400e;
}

.main-content {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 20px;
  margin-bottom: 20px;
  position: relative;
  z-index: 1;
}

.left-panel,
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #1e293b;
}

.upload-card :deep(.el-card__header) {
  padding: 20px 24px;
  border-bottom: 1px solid #f1f5f9;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 16px 16px 0 0;
}

.upload-card :deep(.el-card__body) {
  padding: 24px;
}

.upload-card :deep(.el-card) {
  border-radius: 16px;
  border: none;
  transition: all 0.3s ease;
}

.upload-card :deep(.el-card):hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.1);
}

.upload-content {
  padding: 40px 20px;
  text-align: center;
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  border-radius: 12px;
  border: 2px dashed #cbd5e1;
  transition: all 0.3s ease;
}

.upload-content:hover {
  border-color: #667eea;
  background: linear-gradient(135deg, #edeff5 0%, #e2e8f0 100%);
}

.upload-icon {
  font-size: 56px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 16px;
  transition: all 0.3s ease;
}

.upload-content:hover .upload-icon {
  transform: scale(1.1);
}

.upload-text {
  font-size: 16px;
  color: #475569;
  margin-bottom: 8px;
}

.upload-text em {
  color: #667eea;
  font-style: normal;
  font-weight: 600;
}

.upload-tip {
  font-size: 12px;
  color: #94a3b8;
}

.upload-btn {
  min-width: 140px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  transition: all 0.3s ease;
}

.upload-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
}

.batch-upload {
  padding: 20px 0;
}

.batch-form {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e2e8f0;
}

.processing-card {
  background: white;
  border-radius: 16px;
  border: none;
  overflow: hidden;
}

.processing-card :deep(.el-card__header) {
  padding: 20px 24px;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border-bottom: none;
}

.processing-icon {
  color: #92400e;
}

.processing-steps {
  display: flex;
  flex-direction: column;
  padding: 20px 24px;
}

.step-item {
  display: flex;
  gap: 20px;
  position: relative;
  transition: all 0.3s ease;
}

.step-item:hover {
  transform: translateX(4px);
}

.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 32px;
}

.step-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  z-index: 1;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.step-dot.pending {
  background: #cbd5e1;
}

.step-dot.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  animation: pulse 2s infinite;
}

.step-dot.completed {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.step-dot.error {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(102, 126, 234, 0.4);
  }
  50% {
    box-shadow: 0 0 0 12px rgba(102, 126, 234, 0);
  }
}

.step-line {
  width: 3px;
  flex: 1;
  min-height: 40px;
  background: #e2e8f0;
  margin: 4px 0;
  transition: all 0.3s ease;
}

.step-line.completed {
  background: linear-gradient(to bottom, #10b981 0%, #e2e8f0 100%);
}

.step-line.active {
  background: linear-gradient(to bottom, #667eea 0%, #e2e8f0 100%);
}

.step-content {
  flex: 1;
  padding-bottom: 24px;
}

.step-title {
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 6px;
  font-size: 15px;
}

.step-description {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 10px;
}

.step-progress {
  max-width: 320px;
}

.processing-details {
  margin: 0 24px 24px;
  padding: 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 12px;
  border-left: 4px solid #667eea;
}

.details-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #475569;
}

.details-content {
  font-size: 12px;
  color: #64748b;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  max-height: 200px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', monospace;
}

.stats-card {
  background: white;
  border-radius: 16px;
  border: none;
}

.stats-card :deep(.el-card__header) {
  padding: 20px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-bottom: none;
}

.stats-card :deep(.el-card__header .header-title) {
  color: white;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 20px 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.stat-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 4px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.stat-label {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}

.text-primary { color: #667eea; }
.text-success { color: #10b981; }
.text-warning { color: #f59e0b; }
.text-danger { color: #ef4444; }

.tips-card {
  background: white;
  border-radius: 16px;
  border: none;
}

.tips-card :deep(.el-card__header) {
  padding: 20px 24px;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  border-bottom: none;
}

.tips-card :deep(.el-card__header .header-title) {
  color: white;
}

.tips-list {
  margin: 0;
  padding-left: 20px;
  color: #475569;
  font-size: 14px;
  line-height: 1.8;
}

.tips-list li {
  margin-bottom: 8px;
  transition: all 0.3s ease;
}

.tips-list li:hover {
  color: #667eea;
  transform: translateX(4px);
}

.tips-list li:last-child {
  margin-bottom: 0;
}

.history-card {
  background: white;
  border-radius: 16px;
  border: none;
  position: relative;
  z-index: 1;
}

.history-card :deep(.el-card__header) {
  padding: 20px 24px;
  border-bottom: 1px solid #f1f5f9;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 16px 16px 0 0;
}

.history-card :deep(.el-card__body) {
  padding: 24px;
}

.filter-bar {
  margin-bottom: 20px;
  padding: 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 12px;
}

.pagination-wrapper {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-table) {
  border-radius: 12px;
  overflow: hidden;
}

:deep(.el-table th) {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  color: #475569;
  font-weight: 600;
}

:deep(.el-table tr:hover > td) {
  background: #f8fafc;
}

:deep(.el-progress__text) {
  color: #64748b;
}

.confidence-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tax-type {
  font-weight: 500;
}

.confidence-bar :deep(.el-progress) {
  flex: 1;
}

.confidence-text {
  font-size: 12px;
  color: #475569;
  min-width: 36px;
}

.text-muted {
  color: #c0c4cc;
}

.time-text {
  font-size: 13px;
  color: #475569;
}

.detail-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.basic-info {
  margin-bottom: 24px;
}

.result-section {
  margin-top: 24px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.section-header h4 {
  margin: 0;
  font-size: 16px;
  color: #1e293b;
}

.summary-cards {
  margin-bottom: 24px;
}

.summary-card {
  padding: 20px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 12px;
  text-align: center;
  border-left: 4px solid #667eea;
  transition: all 0.3s ease;
}

.summary-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
}

.summary-card.danger {
  border-left-color: #ef4444;
}

.summary-card.warning {
  border-left-color: #f59e0b;
}

.summary-card.low {
  border-left-color: #10b981;
}

.summary-card.medium {
  border-left-color: #f59e0b;
}

.summary-card.high,
.summary-card.critical {
  border-left-color: #ef4444;
}

.summary-value {
  font-size: 24px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 4px;
}

.summary-label {
  font-size: 12px;
  color: #64748b;
}

.issue-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.issue-item :deep(.el-alert__title) {
  display: flex;
  align-items: center;
  gap: 8px;
}

.issue-type {
  font-weight: 600;
}

.issue-content {
  margin-top: 8px;
}

.issue-description {
  margin: 0 0 12px 0;
  color: #475569;
  line-height: 1.6;
}

.issue-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: #64748b;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.meta-item.suggestion {
  color: #667eea;
}

.confidence-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  color: #fff;
  font-weight: 600;
  font-size: 13px;
}

@media (max-width: 1200px) {
  .main-content {
    grid-template-columns: 1fr;
  }

  .right-panel {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }
}

@media (max-width: 768px) {
  .right-panel {
    grid-template-columns: 1fr;
  }

  .stats-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
</style>
