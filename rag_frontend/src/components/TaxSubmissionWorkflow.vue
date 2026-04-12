<template>
  <div class="tax-submission-workflow">
    <el-row :gutter="20">
      <el-col :span="workflowState?.humanReviewRequest ? 16 : 24">
        <tax-workflow-viewer
          :workflow-state="workflowState"
          :history="history"
          :steps="steps"
          :is-running="isRunning"
          :is-completed="isCompleted"
          :is-failed="isFailed"
          :error="error"
          @cancel="handleCancel"
          @retry="handleRetry"
          @view-details="handleViewDetails"
        />
      </el-col>

      <el-col :span="8" v-if="workflowState?.humanReviewRequest">
        <el-card class="review-notification-card" shadow="hover">
          <template #header>
            <div class="notification-header">
              <span>
                <el-icon><Bell /></el-icon>
                人工审核通知
              </span>
              <el-badge is-dot />
            </div>
          </template>

          <el-alert
            title="需要人工审核"
            type="warning"
            :closable="false"
            show-icon
          >
            <template #default>
              <p class="alert-text">
                检测到 <strong>{{ workflowState.humanReviewRequest.riskItems.length }}</strong> 个风险项需要人工审核。
              </p>
            </template>
          </el-alert>

          <div class="notification-actions">
            <el-button
              type="primary"
              size="large"
              @click="openReviewDialog"
              class="review-button"
            >
              <el-icon><EditPen /></el-icon>
              前往审核
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" v-if="showDetails">
      <el-col :span="24">
        <el-card class="details-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>
                <el-icon><DataAnalysis /></el-icon>
                工作流详情
              </span>
              <el-button size="small" @click="showDetails = false">
                收起
                <el-icon><ArrowUp /></el-icon>
              </el-button>
            </div>
          </template>

          <el-tabs v-model="activeDetailTab">
            <el-tab-pane label="步骤数据" name="step-data">
              <tax-workflow-step-data :steps="steps" />
            </el-tab-pane>

            <el-tab-pane label="税务计算结果" name="tax-calculations">
              <tax-workflow-calculations
                v-if="workflowState?.taxCalculations"
                :calculations="workflowState.taxCalculations"
              />
              <el-empty v-else description="暂无计算结果" />
            </el-tab-pane>

            <el-tab-pane label="风险评估" name="risk-assessment">
              <tax-workflow-risk
                v-if="workflowState?.riskAssessment"
                :assessment="workflowState.riskAssessment"
              />
              <el-empty v-else description="暂无风险评估" />
            </el-tab-pane>

            <el-tab-pane label="原始数据" name="raw-data">
              <el-input
                v-model="rawData"
                type="textarea"
                :rows="10"
                readonly
                class="raw-data-input"
              />
              <el-button
                size="small"
                @click="copyRawData"
                class="copy-button"
              >
                <el-icon><DocumentCopy /></el-icon>
                复制数据
              </el-button>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>

    <human-review-dialog
      v-model:visible="reviewDialogVisible"
      :review-data="workflowState?.humanReviewRequest || null"
      @approve="handleApprove"
      @reject="handleReject"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Bell,
  EditPen,
  DataAnalysis,
  ArrowUp,
  DocumentCopy
} from '@element-plus/icons-vue'
import TaxWorkflowViewer from './TaxWorkflowViewer.vue'
import HumanReviewDialog from './HumanReviewDialog.vue'
import { useTaxWorkflow } from '@/hooks/useTaxWorkflow'

interface Props {
  workflowId?: string
  sessionId?: string
}

interface Emits {
  (e: 'start', data: { workflowId: string; sessionId: string }): void
  (e: 'cancel'): void
  (e: 'complete', data: any): void
  (e: 'error', error: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const {
  workflowState,
  history,
  steps,
  isRunning,
  isCompleted,
  isFailed,
  error,
  isConnected,
  humanReviewRequest,
  hasHumanReviewRequest,
  initWorkflow,
  connect,
  disconnect,
  submitHumanReview
} = useTaxWorkflow()

const showDetails = ref(false)
const activeDetailTab = ref('step-data')
const reviewDialogVisible = ref(false)

const rawData = computed(() => {
  return JSON.stringify(workflowState.value, null, 2)
})

watch(hasHumanReviewRequest, (hasReview) => {
  if (hasReview) {
    ElMessage.warning({
      message: '检测到需要人工审核的风险项，请及时处理',
      duration: 0
    })
  }
})

const startWorkflow = (workflowId: string, sessionId: string) => {
  initWorkflow(workflowId, sessionId)
  connect(workflowId)
  emit('start', { workflowId, sessionId })
}

const handleCancel = () => {
  ElMessageBox.confirm('确定要取消当前工作流吗？', '确认取消', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    disconnect()
    emit('cancel')
  }).catch(() => {})
}

const handleRetry = () => {
  if (props.workflowId && props.sessionId) {
    disconnect()
    initWorkflow(props.workflowId, props.sessionId)
    connect(props.workflowId)
  }
}

const handleViewDetails = () => {
  showDetails.value = !showDetails.value
}

const openReviewDialog = () => {
  reviewDialogVisible.value = true
}

const handleApprove = async (data: { comment: string; note?: string }) => {
  if (!props.workflowId || !props.sessionId) {
    ElMessage.error('工作流信息不完整')
    return
  }

  try {
    await submitHumanReview({
      decision: 'approved',
      comment: data.comment,
      note: data.note
    })
    ElMessage.success('审核已批准，工作流将继续执行')
  } catch (err) {
    ElMessage.error('提交审核失败')
    emit('error', '提交审核失败')
  }
}

const handleReject = async (data: { comment: string; note?: string }) => {
  if (!props.workflowId || !props.sessionId) {
    ElMessage.error('工作流信息不完整')
    return
  }

  try {
    await submitHumanReview({
      decision: 'rejected',
      comment: data.comment,
      note: data.note
    })
    ElMessage.warning('审核已拒绝，工作流将终止')
  } catch (err) {
    ElMessage.error('提交审核失败')
    emit('error', '提交审核失败')
  }
}

const copyRawData = async () => {
  try {
    await navigator.clipboard.writeText(rawData.value)
    ElMessage.success('数据已复制到剪贴板')
  } catch (err) {
    ElMessage.error('复制失败')
  }
}

onUnmounted(() => {
  disconnect()
})

defineExpose({
  startWorkflow,
  disconnect,
  workflowState,
  isRunning,
  isCompleted,
  isFailed,
  error,
  isConnected
})
</script>

<style scoped>
.tax-submission-workflow {
  padding: 16px;
}

.review-notification-card {
  position: sticky;
  top: 16px;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.alert-text {
  margin: 8px 0 0;
  line-height: 1.6;
}

.notification-actions {
  margin-top: 16px;
}

.review-button {
  width: 100%;
  height: 48px;
  font-size: 16px;
}

.details-card {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.raw-data-input {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.copy-button {
  margin-top: 12px;
}

:deep(.el-tab-pane) {
  padding: 16px;
}
</style>
