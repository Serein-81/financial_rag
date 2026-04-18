<template>
  <div class="tax-review-queue">
    <div class="page-header">
      <div class="header-content">
        <div class="header-text">
          <h1>税务风险审核队列</h1>
          <p class="subtitle">待处理的税务风险和异常报告</p>
        </div>
        <div class="header-stats">
          <div class="stat-badge total">
            <el-icon><Warning /></el-icon>
            <span>{{ statistics.total }}</span>
          </div>
          <el-button type="primary" @click="loadPendingReviews">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>
    </div>

    <el-card class="stats-card" shadow="hover">
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value text-warning">{{ statistics.pending }}</div>
            <div class="stat-label">待处理</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value text-danger">{{ statistics.high_risk }}</div>
            <div class="stat-label">高风险</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value text-info">{{ statistics.medium_risk }}</div>
            <div class="stat-label">中风险</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-value text-success">{{ statistics.resolved }}</div>
            <div class="stat-label">已处理</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="review-list-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>待审核报告</span>
          <span class="text-muted">共 {{ pagination.total }} 条记录</span>
        </div>
      </template>

      <el-table :data="reviewList" v-loading="loading" stripe>
        <el-table-column prop="filename" label="文件名" min-width="200">
          <template #default="{ row }">
            <div class="file-info">
              <el-icon><Document /></el-icon>
              <span>{{ row.original_filename || row.filename }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="tax_type" label="税务类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ getTaxTypeName(row.tax_type) }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="risk_level" label="风险等级" width="100" align="center">
          <template #default="{ row }">
            <el-tag 
              :type="getRiskType(row.risk_level)" 
              size="small"
              effect="dark"
            >
              {{ getRiskLabel(row.risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="confidence_score" label="置信度" width="120" align="center">
          <template #default="{ row }">
            <div v-if="row.confidence_score" class="confidence-bar">
              <el-progress
                :percentage="Math.round(row.confidence_score * 100)"
                :color="getConfidenceColor(row.confidence_score)"
                :show-text="false"
                :stroke-width="8"
              />
              <span class="confidence-text">{{ Math.round(row.confidence_score * 100) }}%</span>
            </div>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="processing_result" label="风险问题" width="200">
          <template #default="{ row }">
            <div v-if="row.processing_result" class="issues-summary">
              <el-tag 
                v-if="getIssueCount(row.processing_result, 'high') > 0" 
                type="danger" 
                size="small"
                effect="plain"
              >
                高风险 {{ getIssueCount(row.processing_result, 'high') }} 个
              </el-tag>
              <el-tag 
                v-if="getIssueCount(row.processing_result, 'medium') > 0" 
                type="warning" 
                size="small"
                effect="plain"
              >
                中风险 {{ getIssueCount(row.processing_result, 'medium') }} 个
              </el-tag>
              <el-tag 
                v-if="getIssueCount(row.processing_result, 'low') > 0" 
                type="info" 
                size="small"
                effect="plain"
              >
                低风险 {{ getIssueCount(row.processing_result, 'low') }} 个
              </el-tag>
            </div>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            <span class="time-text">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewDetails(row)">
              查看详情
            </el-button>
            <el-button link type="success" @click="handleReview(row)">
              开始审核
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
          @size-change="loadPendingReviews"
          @current-change="loadPendingReviews"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="detailDialogVisible"
      title="审核详情"
      width="900px"
      :close-on-click-modal="false"
    >
      <div v-if="currentReport" class="detail-content">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="文件名">
            {{ currentReport.original_filename || currentReport.filename }}
          </el-descriptions-item>
          <el-descriptions-item label="税务类型">
            {{ getTaxTypeName(currentReport.tax_type) }}
          </el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag :type="getRiskType(currentReport.risk_level)">
              {{ getRiskLabel(currentReport.risk_level) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="置信度">
            {{ currentReport.confidence_score ? (currentReport.confidence_score * 100).toFixed(1) + '%' : '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="currentReport.processing_result" class="issues-section">
          <h4>发现的问题</h4>
          
          <el-tabs>
            <el-tab-pane label="税务问题" v-if="hasIssues(currentReport.processing_result, 'tax')">
              <div 
                v-for="(issue, index) in getIssues(currentReport.processing_result, 'tax')" 
                :key="index"
                class="issue-item"
              >
                <el-alert
                  :title="issue.description || issue.title"
                  :type="getIssueType(issue.severity)"
                  :closable="false"
                  show-icon
                >
                  <template #default>
                    <div class="issue-content">
                      <div class="issue-meta">
                        <el-tag :type="getIssueType(issue.severity)" size="small">
                          {{ issue.severity }}
                        </el-tag>
                        <span v-if="issue.category" class="category">{{ issue.category }}</span>
                      </div>
                      <div v-if="issue.evidence && issue.evidence.length" class="issue-evidence">
                        <strong>证据:</strong>
                        <ul>
                          <li v-for="(ev, i) in issue.evidence" :key="i">{{ ev }}</li>
                        </ul>
                      </div>
                      <div v-if="issue.recommendation" class="issue-recommendation">
                        <strong>建议:</strong> {{ issue.recommendation }}
                      </div>
                    </div>
                  </template>
                </el-alert>
              </div>
            </el-tab-pane>
            
            <el-tab-pane label="财务问题" v-if="hasIssues(currentReport.processing_result, 'finance')">
              <div 
                v-for="(issue, index) in getIssues(currentReport.processing_result, 'finance')" 
                :key="index"
                class="issue-item"
              >
                <el-alert
                  :title="issue.description || issue.title"
                  :type="getIssueType(issue.severity)"
                  :closable="false"
                  show-icon
                >
                  <template #default>
                    <div class="issue-content">
                      <div class="issue-meta">
                        <el-tag :type="getIssueType(issue.severity)" size="small">
                          {{ issue.severity }}
                        </el-tag>
                        <span v-if="issue.category" class="category">{{ issue.category }}</span>
                      </div>
                      <div v-if="issue.evidence && issue.evidence.length" class="issue-evidence">
                        <strong>证据:</strong>
                        <ul>
                          <li v-for="(ev, i) in issue.evidence" :key="i">{{ ev }}</li>
                        </ul>
                      </div>
                      <div v-if="issue.recommendation" class="issue-recommendation">
                        <strong>建议:</strong> {{ issue.recommendation }}
                      </div>
                    </div>
                  </template>
                </el-alert>
              </div>
            </el-tab-pane>
            
            <el-tab-pane label="法务问题" v-if="hasIssues(currentReport.processing_result, 'legal')">
              <div 
                v-for="(issue, index) in getIssues(currentReport.processing_result, 'legal')" 
                :key="index"
                class="issue-item"
              >
                <el-alert
                  :title="issue.description || issue.title"
                  :type="getIssueType(issue.severity)"
                  :closable="false"
                  show-icon
                >
                  <template #default>
                    <div class="issue-content">
                      <div class="issue-meta">
                        <el-tag :type="getIssueType(issue.severity)" size="small">
                          {{ issue.severity }}
                        </el-tag>
                        <span v-if="issue.category" class="category">{{ issue.category }}</span>
                      </div>
                      <div v-if="issue.evidence && issue.evidence.length" class="issue-evidence">
                        <strong>证据:</strong>
                        <ul>
                          <li v-for="(ev, i) in issue.evidence" :key="i">{{ ev }}</li>
                        </ul>
                      </div>
                      <div v-if="issue.recommendation" class="issue-recommendation">
                        <strong>建议:</strong> {{ issue.recommendation }}
                      </div>
                    </div>
                  </template>
                </el-alert>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleReview(currentReport)">
          开始审核
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Warning, Document, Refresh } from '@element-plus/icons-vue'
import { taxReportApiClient } from '@/api/tax-report'
import type { TaxReport } from '@/types/tax'

const loading = ref(false)
const reviewList = ref<TaxReport[]>([])
const detailDialogVisible = ref(false)
const currentReport = ref<TaxReport | null>(null)

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const statistics = reactive({
  total: 0,
  pending: 0,
  high_risk: 0,
  medium_risk: 0,
  resolved: 0
})

const getTaxTypeName = (type: string) => {
  const typeMap: Record<string, string> = {
    'vat': '增值税',
    'income': '企业所得税',
    'personal': '个人所得税',
    'consumption': '消费税',
    'behavior': '行为税'
  }
  return typeMap[type] || type
}

const getRiskType = (level: string) => {
  const typeMap: Record<string, string> = {
    'low': 'success',
    'medium': 'warning',
    'high': 'danger',
    'critical': 'danger'
  }
  return typeMap[level] || 'info'
}

const getRiskLabel = (level: string) => {
  const labelMap: Record<string, string> = {
    'low': '低',
    'medium': '中',
    'high': '高',
    'critical': '严重'
  }
  return labelMap[level] || level
}

const getConfidenceColor = (score: number) => {
  if (score >= 0.8) return '#67c23a'
  if (score >= 0.5) return '#e6a23c'
  return '#f56c6c'
}

const getIssueCount = (processingResult: any, severity: string) => {
  if (!processingResult) return 0
  
  const findings = [
    ...(processingResult.tax_findings || []),
    ...(processingResult.finance_findings || []),
    ...(processingResult.legal_findings || [])
  ]
  
  return findings.filter(f => 
    (f.severity === severity || f.risk_level === severity)
  ).length
}

const getIssues = (processingResult: any, category: string) => {
  if (!processingResult) return []
  
  const categoryMap: Record<string, string[]> = {
    'tax': ['tax_findings'],
    'finance': ['finance_findings'],
    'legal': ['legal_findings']
  }
  
  const keys = categoryMap[category] || []
  let issues: any[] = []
  
  keys.forEach(key => {
    issues = issues.concat(processingResult[key] || [])
  })
  
  return issues
}

const hasIssues = (processingResult: any, category: string) => {
  return getIssues(processingResult, category).length > 0
}

const getIssueType = (severity: string) => {
  const typeMap: Record<string, string> = {
    'low': 'info',
    'medium': 'warning',
    'high': 'error',
    'critical': 'error'
  }
  return typeMap[severity] || 'info'
}

const formatDate = (date: string | Date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

const loadPendingReviews = async () => {
  try {
    loading.value = true
    
    const response = await taxReportApiClient.getPendingReviews(
      pagination.page,
      pagination.pageSize
    )
    
    reviewList.value = response.items
    pagination.total = response.total
    
    // 更新统计
    statistics.total = response.total
    statistics.pending = response.items.filter(r => r.status === 'pending_review').length
    statistics.high_risk = response.items.filter(r => 
      r.risk_level === 'high' || r.risk_level === 'critical'
    ).length
    statistics.medium_risk = response.items.filter(r => 
      r.risk_level === 'medium'
    ).length
    statistics.resolved = response.items.filter(r => 
      r.status === 'completed'
    ).length
    
  } catch (error) {
    ElMessage.error('加载待审核列表失败')
  } finally {
    loading.value = false
  }
}

const viewDetails = async (report: TaxReport) => {
  try {
    const details = await taxReportApiClient.get(report.id)
    currentReport.value = details
    detailDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载详情失败')
  }
}

const handleReview = (report: TaxReport) => {
  ElMessage.info('审核功能开发中...')
  detailDialogVisible.value = false
}

onMounted(() => {
  loadPendingReviews()
})
</script>

<style scoped>
.tax-review-queue {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-text h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
}

.subtitle {
  margin: 0;
  color: #909399;
}

.header-stats {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  font-weight: 600;
}

.stat-badge.total {
  background: #fef0f0;
  color: #f56c6c;
}

.stats-card {
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 8px;
}

.stat-label {
  color: #909399;
  font-size: 14px;
}

.text-warning {
  color: #e6a23c;
}

.text-danger {
  color: #f56c6c;
}

.text-info {
  color: #409eff;
}

.text-success {
  color: #67c23a;
}

.review-list-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.text-muted {
  color: #909399;
  font-size: 14px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.confidence-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.confidence-text {
  font-size: 12px;
  min-width: 40px;
}

.issues-summary {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.time-text {
  color: #909399;
  font-size: 13px;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.detail-content {
  padding: 20px;
}

.issues-section {
  margin-top: 20px;
}

.issues-section h4 {
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
}

.issue-item {
  margin-bottom: 16px;
}

.issue-content {
  padding: 8px 0;
}

.issue-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.category {
  color: #909399;
  font-size: 13px;
}

.issue-evidence,
.issue-recommendation {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.6;
}

.issue-evidence ul {
  margin: 4px 0;
  padding-left: 20px;
}
</style>
