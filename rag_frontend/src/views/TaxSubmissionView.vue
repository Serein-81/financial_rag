<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { 
  Upload, 
  Document, 
  CheckCircle, 
  Clock, 
  AlertTriangle, 
  FileText,
  TrendCharts,
  Money,
  CircleCheck,
  Warning,
  Refresh,
  Download,
  Delete,
  View
} from '@element-plus/icons-vue'
import { taxReportApiClient } from '@/api/tax-report'
import type { TaxReport, TaxReportStatusResponse, TaxTypeEnum } from '@/types/tax'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()

const activeTab = ref('upload')
const uploadLoading = ref(false)
const uploadProgress = ref(0)
const selectedFile = ref<File | null>(null)
const listLoading = ref(false)

const detailDialogVisible = ref(false)
const currentReport = ref<TaxReport | null>(null)
const detailLoading = ref(false)

const taxTypeOptions = [
  { value: 'vat', label: '增值税 (VAT)', color: '#409eff' },
  { value: 'income', label: '企业所得税', color: '#67c23a' },
  { value: 'personal', label: '个人所得税', color: '#e6a23c' },
  { value: 'consumption', label: '消费税', color: '#f56c6c' },
  { value: 'behavior', label: '行为税', color: '#909399' },
  { value: 'comprehensive', label: '综合税务', color: '#667eea' }
]

const uploadForm = ref({
  tax_type: '' as TaxTypeEnum,
  tax_period_year: new Date().getFullYear(),
  tax_period_month: new Date().getMonth() + 1,
  description: ''
})

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

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const handleFileChange = (file: any) => {
  selectedFile.value = file.raw
  return false
}

const handleRemoveFile = () => {
  selectedFile.value = null
  uploadProgress.value = 0
}

const handleUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择要上传的文件')
    return
  }

  if (!uploadForm.value.tax_type) {
    ElMessage.warning('请选择税务类型')
    return
  }

  try {
    uploadLoading.value = true
    uploadProgress.value = 0

    const result = await taxReportApiClient.upload(selectedFile.value, {
      tax_type: uploadForm.value.tax_type,
      tax_period_year: uploadForm.value.tax_period_year,
      tax_period_month: uploadForm.value.tax_period_month,
      description: uploadForm.value.description,
      onProgress: (progress) => {
        uploadProgress.value = progress
      }
    })

    ElMessage.success('文件上传成功，正在后台处理...')
    
    selectedFile.value = null
    uploadProgress.value = 0
    uploadForm.value.description = ''
    
    await loadReportList()
    activeTab.value = 'list'
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '上传失败，请重试')
  } finally {
    uploadLoading.value = false
  }
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
    const stats = await taxReportApiClient.list({
      page_size: 1
    })

    statistics.value.total = stats.total
    
    const allReports = await taxReportApiClient.list({
      page_size: 1000
    })

    statistics.value.pending = allReports.items.filter(r => r.status === 'pending').length
    statistics.value.processing = allReports.items.filter(r => r.status === 'processing').length
    statistics.value.completed = allReports.items.filter(r => r.status === 'completed').length
    statistics.value.needs_review = allReports.items.filter(r => r.needs_human_review).length
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

const handleRetry = async (report: TaxReport) => {
  try {
    await ElMessageBox.confirm(
      '确定要重新处理此报告吗？',
      '确认重试',
      {
        confirmButtonText: '重试',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    ElMessage.info('重试任务已提交')
    await loadReportList()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('重试失败')
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
    <div class="page-header">
      <div class="header-content">
        <div class="header-text">
          <h1>税务报告管理</h1>
          <p class="subtitle">上传和管理您的税务报告，AI将自动分析并验证</p>
        </div>
        <div class="header-stats">
          <div class="stat-badge total">
            <el-icon><Document /></el-icon>
            <span class="stat-label">总计</span>
            <span class="stat-value">{{ statistics.total }}</span>
          </div>
          <div class="stat-badge pending">
            <el-icon><Clock /></el-icon>
            <span class="stat-label">待处理</span>
            <span class="stat-value">{{ statistics.pending }}</span>
          </div>
          <div class="stat-badge processing">
            <el-icon><Refresh /></el-icon>
            <span class="stat-label">处理中</span>
            <span class="stat-value">{{ statistics.processing }}</span>
          </div>
          <div class="stat-badge completed">
            <el-icon><CircleCheck /></el-icon>
            <span class="stat-label">已完成</span>
            <span class="stat-value">{{ statistics.completed }}</span>
          </div>
          <div class="stat-badge review">
            <el-icon><Warning /></el-icon>
            <span class="stat-label">待审核</span>
            <span class="stat-value">{{ statistics.needs_review }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="animated-gradient"></div>

    <div class="main-content">
      <el-tabs v-model="activeTab" class="main-tabs">
        <el-tab-pane label="上传报告" name="upload">
          <div class="upload-section">
            <el-card class="upload-card" shadow="hover">
              <template #header>
                <div class="card-header">
                  <div class="header-title">
                    <el-icon><Upload /></el-icon>
                    <span>上传税务报告</span>
                  </div>
                </div>
              </template>

              <el-form :model="uploadForm" label-width="120px" class="upload-form">
                <el-form-item label="税务类型" required>
                  <el-select 
                    v-model="uploadForm.tax_type" 
                    placeholder="请选择税务类型"
                    class="full-width"
                  >
                    <el-option
                      v-for="option in taxTypeOptions"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    >
                      <span :style="{ color: option.color }">{{ option.label }}</span>
                    </el-option>
                  </el-select>
                </el-form-item>

                <el-form-item label="税务期间">
                  <el-row :gutter="12">
                    <el-col :span="12">
                      <el-select v-model="uploadForm.tax_period_year" class="full-width">
                        <el-option
                          v-for="year in [2023, 2024, 2025]"
                          :key="year"
                          :label="`${year}年`"
                          :value="year"
                        />
                      </el-select>
                    </el-col>
                    <el-col :span="12">
                      <el-select v-model="uploadForm.tax_period_month" class="full-width">
                        <el-option
                          v-for="month in 12"
                          :key="month"
                          :label="`${month}月`"
                          :value="month"
                        />
                      </el-select>
                    </el-col>
                  </el-row>
                </el-form-item>

                <el-form-item label="报告描述">
                  <el-input
                    v-model="uploadForm.description"
                    type="textarea"
                    :rows="3"
                    placeholder="请输入报告描述（可选）"
                  />
                </el-form-item>

                <el-form-item label="选择文件" required>
                  <div class="upload-area">
                    <el-upload
                      class="upload-dragger"
                      drag
                      :auto-upload="false"
                      :show-file-list="false"
                      :on-change="handleFileChange"
                      accept=".pdf,.xlsx,.xls,.csv"
                    >
                      <div v-if="!selectedFile" class="upload-placeholder">
                        <el-icon class="upload-icon"><Upload /></el-icon>
                        <div class="upload-text">
                          <span class="main-text">将文件拖到此处，或<em>点击上传</em></span>
                          <span class="sub-text">支持 PDF、Excel、CSV 格式，最大 50MB</span>
                        </div>
                      </div>
                      <div v-else class="selected-file">
                        <el-icon class="file-icon"><Document /></el-icon>
                        <div class="file-info">
                          <span class="file-name">{{ selectedFile.name }}</span>
                          <span class="file-size">{{ formatFileSize(selectedFile.size) }}</span>
                        </div>
                        <el-button 
                          type="danger" 
                          circle 
                          size="small"
                          @click.stop="handleRemoveFile"
                        >
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                    </el-upload>

                    <el-progress 
                      v-if="uploadProgress > 0 && uploadProgress < 100" 
                      :percentage="uploadProgress"
                      :stroke-width="8"
                      class="upload-progress"
                    />
                  </div>
                </el-form-item>

                <el-form-item>
                  <el-button 
                    type="primary" 
                    size="large"
                    :loading="uploadLoading"
                    @click="handleUpload"
                    :disabled="!selectedFile || !uploadForm.tax_type"
                    class="upload-button"
                  >
                    <el-icon v-if="!uploadLoading"><Upload /></el-icon>
                    提交报告
                  </el-button>
                </el-form-item>
              </el-form>
            </el-card>

            <el-card class="info-card" shadow="hover">
              <template #header>
                <div class="card-header">
                  <div class="header-title">
                    <el-icon><TrendCharts /></el-icon>
                    <span>处理流程</span>
                  </div>
                </div>
              </template>

              <div class="process-steps">
                <div class="step">
                  <div class="step-icon">
                    <el-icon><Upload /></el-icon>
                  </div>
                  <div class="step-content">
                    <div class="step-title">文件上传</div>
                    <div class="step-desc">支持PDF、Excel、CSV格式</div>
                  </div>
                </div>
                <div class="step-arrow">
                  <el-icon><TrendCharts /></el-icon>
                </div>
                <div class="step">
                  <div class="step-icon warning">
                    <el-icon><Document /></el-icon>
                  </div>
                  <div class="step-content">
                    <div class="step-title">AI解析</div>
                    <div class="step-desc">自动提取税务数据</div>
                  </div>
                </div>
                <div class="step-arrow">
                  <el-icon><TrendCharts /></el-icon>
                </div>
                <div class="step">
                  <div class="step-icon success">
                    <el-icon><TrendCharts /></el-icon>
                  </div>
                  <div class="step-content">
                    <div class="step-title">智能分析</div>
                    <div class="step-desc">验证税务逻辑和合规性</div>
                  </div>
                </div>
                <div class="step-arrow">
                  <el-icon><TrendCharts /></el-icon>
                </div>
                <div class="step">
                  <div class="step-icon primary">
                    <el-icon><CircleCheck /></el-icon>
                  </div>
                  <div class="step-content">
                    <div class="step-title">生成报告</div>
                    <div class="step-desc">输出分析结果和建议</div>
                  </div>
                </div>
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
                        v-if="row.status === 'failed'"
                        type="warning" 
                        size="small"
                        @click="handleRetry(row)"
                      >
                        <el-icon><Refresh /></el-icon>
                        重试
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
        width="800px"
        :close-on-click-modal="false"
        class="detail-dialog"
      >
        <div v-loading="detailLoading" class="detail-content">
          <template v-if="currentReport">
            <el-descriptions :column="2" border>
              <el-descriptions-item label="文件名">
                {{ currentReport.original_filename || currentReport.filename }}
              </el-descriptions-item>
              <el-descriptions-item label="文件类型">
                {{ currentReport.file_type?.toUpperCase() || '-' }}
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
              <el-descriptions-item label="处理信息" :span="2">
                <div class="processing-message">
                  <span v-if="currentReport.processing_message">{{ currentReport.processing_message }}</span>
                  <span v-else class="text-muted">暂无处理信息</span>
                </div>
              </el-descriptions-item>
              <el-descriptions-item label="上传时间">
                {{ formatDate(currentReport.created_at) }}
              </el-descriptions-item>
              <el-descriptions-item label="更新时间">
                {{ formatDate(currentReport.updated_at) }}
              </el-descriptions-item>
            </el-descriptions>

            <div v-if="currentReport.needs_human_review" class="review-notice">
              <el-alert
                title="此报告需要人工审核"
                type="warning"
                :description="currentReport.processing_message || '系统检测到此报告可能存在风险，建议人工复核'"
                :closable="false"
                show-icon
              />
            </div>
          </template>

          <el-empty v-else description="暂无报告详情" />
        </div>

        <template #footer>
          <el-button @click="detailDialogVisible = false">关闭</el-button>
          <el-button 
            v-if="currentReport?.status === 'failed'" 
            type="warning" 
            @click="handleRetry(currentReport); detailDialogVisible = false"
          >
            重试处理
          </el-button>
          <el-button 
            v-if="currentReport?.needs_human_review" 
            type="danger" 
            @click="router.push('/audit/upload'); detailDialogVisible = false"
          >
            前往审核
          </el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<style scoped>
.tax-submission-view {
  padding: 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%);
  min-height: calc(100vh - 60px);
  position: relative;
  overflow-y: auto;
  overflow-x: hidden;
}

.tax-submission-view::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 400px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  opacity: 0.03;
  pointer-events: none;
}

.page-header {
  margin-bottom: 24px;
  position: relative;
  z-index: 1;
  flex-shrink: 0;
}

.header-content {
  background: white;
  padding: 24px 32px;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.header-text h1 {
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 700;
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
  gap: 16px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.stat-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 12px;
  transition: all 0.3s ease;
  cursor: pointer;
}

.stat-badge:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-badge.total {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
}

.stat-badge.total .el-icon {
  color: #3b82f6;
}

.stat-badge.pending {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
}

.stat-badge.pending .el-icon {
  color: #f59e0b;
}

.stat-badge.processing {
  background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
}

.stat-badge.processing .el-icon {
  color: #6366f1;
}

.stat-badge.completed {
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
}

.stat-badge.completed .el-icon {
  color: #10b981;
}

.stat-badge.review {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
}

.stat-badge.review .el-icon {
  color: #ef4444;
}

.stat-label {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #1e293b;
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

.main-content {
  position: relative;
  z-index: 1;
}

.main-tabs {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.main-tabs :deep(.el-tabs__header) {
  margin-bottom: 24px;
}

.main-tabs :deep(.el-tabs__item) {
  font-size: 16px;
  font-weight: 600;
  color: #64748b;
  transition: all 0.3s ease;
}

.main-tabs :deep(.el-tabs__item:hover) {
  color: #667eea;
}

.main-tabs :deep(.el-tabs__item.is-active) {
  color: #667eea;
  font-weight: 700;
}

.main-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 2px;
  background: #e2e8f0;
}

.main-tabs :deep(.el-tabs__content) {
  padding: 0;
}

.upload-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

@media (max-width: 1200px) {
  .upload-section {
    grid-template-columns: 1fr;
  }
}

.upload-card,
.info-card {
  border: none;
  border-radius: 16px;
  transition: all 0.3s ease;
}

.upload-card:hover,
.info-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.1);
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
  font-size: 16px;
  color: #1e293b;
}

.upload-form {
  padding: 20px 0;
}

.full-width {
  width: 100%;
}

.upload-area {
  width: 100%;
}

.upload-dragger {
  width: 100%;
}

.upload-dragger :deep(.el-upload-dragger) {
  border: 2px dashed #e2e8f0;
  border-radius: 12px;
  padding: 32px;
  transition: all 0.3s ease;
}

.upload-dragger :deep(.el-upload-dragger:hover) {
  border-color: #667eea;
  background: #f8fafc;
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.upload-icon {
  font-size: 48px;
  color: #667eea;
}

.upload-text {
  text-align: center;
}

.main-text {
  display: block;
  font-size: 16px;
  color: #1e293b;
  margin-bottom: 8px;
}

.main-text em {
  color: #667eea;
  font-style: normal;
}

.sub-text {
  display: block;
  font-size: 14px;
  color: #64748b;
}

.selected-file {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 8px;
}

.file-icon {
  font-size: 32px;
  color: #667eea;
}

.file-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-name {
  font-weight: 600;
  color: #1e293b;
  word-break: break-all;
}

.file-meta {
  font-size: 13px;
  color: #64748b;
}

.upload-progress {
  margin-top: 16px;
}

.upload-button {
  width: 100%;
  height: 48px;
  font-size: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  transition: all 0.3s ease;
}

.upload-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(102, 126, 234, 0.4);
}

.upload-button:disabled {
  background: #cbd5e1;
  transform: none;
  box-shadow: none;
}

.process-steps {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.step-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  color: #3b82f6;
  font-size: 24px;
  flex-shrink: 0;
}

.step-icon.warning {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #f59e0b;
}

.step-icon.success {
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
  color: #10b981;
}

.step-icon.primary {
  background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
  color: #6366f1;
}

.step-content {
  flex: 1;
  padding-top: 8px;
}

.step-title {
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 4px;
}

.step-desc {
  font-size: 14px;
  color: #64748b;
}

.step-arrow {
  display: flex;
  justify-content: center;
  padding: 8px 0;
  color: #cbd5e1;
}

.list-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.filter-card {
  border: none;
  border-radius: 16px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-select {
  width: 160px;
}

.table-card {
  border: none;
  border-radius: 16px;
}

.report-table :deep(.el-table__header) {
  font-weight: 600;
}

.report-table :deep(.el-table__row) {
  transition: all 0.2s ease;
}

.report-table :deep(.el-table__row:hover) {
  background: #f8fafc;
}

.file-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.file-cell .file-icon {
  font-size: 28px;
  color: #667eea;
}

.file-cell .file-info {
  gap: 4px;
}

.file-cell .file-name {
  font-weight: 500;
  color: #1e293b;
}

.text-muted {
  color: #c0c4cc;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.tab-badge {
  margin-left: 8px;
}

.tab-badge :deep(.el-badge__content) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

@media (max-width: 768px) {
  .header-stats {
    flex-direction: column;
  }

  .stat-badge {
    width: 100%;
  }

  .upload-section {
    grid-template-columns: 1fr;
  }

  .filter-bar {
    flex-direction: column;
  }

  .filter-select {
    width: 100%;
  }
}

.detail-content {
  min-height: 200px;
}

.processing-message {
  max-width: 500px;
  word-break: break-all;
}

.review-notice {
  margin-top: 20px;
}

.detail-dialog :deep(.el-dialog__body) {
  padding: 24px;
}
</style>
