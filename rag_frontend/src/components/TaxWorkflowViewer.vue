<template>
  <div class="tax-workflow-viewer">
    <el-card class="workflow-card" shadow="hover">
      <template #header>
        <div class="workflow-header">
          <div class="header-title">
            <el-icon class="header-icon"><TrendCharts /></el-icon>
            <span>税务提交流工作流</span>
          </div>
          <div class="header-actions">
            <el-tag :type="statusType" size="large" effect="dark">
              {{ statusText }}
            </el-tag>
            <el-button
              v-if="workflowState?.status === 'running'"
              type="danger"
              size="small"
              @click="handleCancel"
            >
              取消
            </el-button>
          </div>
        </div>
      </template>

      <!-- 进度条 -->
      <div class="progress-section">
        <div class="progress-info">
          <span class="progress-text">
            当前步骤: {{ currentStepInfo?.label || '准备中' }}
          </span>
          <span class="progress-time" v-if="workflowState?.startTime">
            已用时: {{ elapsedTime }}
          </span>
        </div>
        
        <div class="progress-bar-container">
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: progressPercentage + '%' }"
              :class="progressClass"
            ></div>
          </div>
          <div class="progress-percentage">{{ progressPercentage }}%</div>
        </div>
      </div>

      <!-- 步骤条 -->
      <div class="steps-container">
        <div
          v-for="(step, index) in steps"
          :key="step.name"
          class="step-item"
          :class="getStepClass(step)"
        >
          <div class="step-connector" v-if="index > 0">
            <div
              class="connector-line"
              :class="{
                'completed': isStepCompleted(steps[index - 1]),
                'failed': steps[index - 1]?.status === 'failed'
              }"
            ></div>
          </div>
          
          <div class="step-node">
            <div class="step-icon-wrapper">
              <el-icon class="step-icon" v-if="step.status === 'completed'">
                <Check />
              </el-icon>
              <el-icon class="step-icon" v-else-if="step.status === 'failed'">
                <CloseBold />
              </el-icon>
              <el-icon class="step-icon" v-else-if="step.status === 'running'">
                <Loading />
              </el-icon>
              <el-icon class="step-icon" v-else-if="step.status === 'waiting_review'">
                <UserFilled />
              </el-icon>
              <span class="step-number" v-else>{{ index + 1 }}</span>
            </div>
            
            <div class="step-content">
              <div class="step-label">{{ step.label }}</div>
              <div class="step-description">{{ step.description }}</div>
              
              <div class="step-meta" v-if="step.startTime">
                <span class="meta-item">
                  <el-icon><Clock /></el-icon>
                  {{ formatDuration(step.duration) }}
                </span>
              </div>
              
              <div class="step-error" v-if="step.error">
                <AlertTriangle class="step-error-icon" />
                {{ step.error }}
              </div>
              
              <div class="step-warnings" v-if="step.warnings?.length">
                <el-tag
                  v-for="(warning, i) in step.warnings"
                  :key="i"
                  type="warning"
                  size="small"
                  effect="plain"
                >
                  {{ warning }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 错误详情 -->
      <el-alert
        v-if="error"
        :title="error"
        type="error"
        :closable="false"
        show-icon
        class="error-alert"
      >
        <template #default>
          <div class="error-actions">
            <el-button size="small" @click="handleRetry">
              <el-icon><RefreshRight /></el-icon>
              重试
            </el-button>
            <el-button size="small" @click="handleViewDetails">
              <el-icon><View /></el-icon>
              查看详情
            </el-button>
          </div>
        </template>
      </el-alert>
    </el-card>

    <!-- 历史记录 -->
    <el-card class="history-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <el-icon><Timer /></el-icon>
            <span>执行历史</span>
          </div>
          <el-badge :value="history.length" :hidden="history.length === 0" />
        </div>
      </template>
      
      <el-scrollbar height="300px">
        <div class="history-list">
          <div
            v-for="(item, index) in history"
            :key="index"
            class="history-item"
            :class="item.severity"
          >
            <div class="history-icon">
              <el-icon v-if="item.severity === 'success'"><CircleCheck /></el-icon>
              <el-icon v-else-if="item.severity === 'error'"><CircleClose /></el-icon>
              <el-icon v-else-if="item.severity === 'warning'"><AlertTriangleFilled /></el-icon>
              <el-icon v-else><InfoFilled /></el-icon>
            </div>
            <div class="history-content">
              <div class="history-message">{{ item.message }}</div>
              <div class="history-time">
                {{ formatTime(item.event.timestamp) }}
              </div>
            </div>
          </div>
          
          <el-empty
            v-if="history.length === 0"
            description="暂无执行历史"
            :image-size="60"
          />
        </div>
      </el-scrollbar>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  TrendCharts,
  Check,
  CloseBold,
  Loading,
  UserFilled,
  Clock,
  RefreshRight,
  View,
  Timer,
  CircleCheck,
  CircleClose,
  WarningFilled,
  InfoFilled
} from '@element-plus/icons-vue'
import { AlertTriangle } from 'lucide-vue-next'
import type { WorkflowStep, WorkflowHistoryItem, TaxWorkflowState } from '@/types/tax-workflow'
import { WorkflowStepStatus } from '@/types/tax-workflow'

interface Props {
  workflowState: TaxWorkflowState | null
  history: WorkflowHistoryItem[]
  steps: WorkflowStep[]
  isRunning: boolean
  isCompleted: boolean
  isFailed: boolean
  error?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'retry'): void
  (e: 'viewDetails'): void
}>()

const currentStepInfo = computed(() => {
  if (!props.workflowState) return null
  return props.steps.find(s => s.number === props.workflowState?.currentStep)
})

const progressPercentage = computed(() => {
  if (!props.workflowState) return 0
  
  const completedSteps = props.steps.filter(s =>
    s.status === WorkflowStepStatus.COMPLETED ||
    s.status === WorkflowStepStatus.FAILED
  ).length
  
  if (props.workflowState.status === 'completed') return 100
  if (props.workflowState.status === 'failed') {
    const failedIndex = props.steps.findIndex(s => s.status === WorkflowStepStatus.FAILED)
    return Math.round((failedIndex / props.steps.length) * 100)
  }
  
  return Math.round((completedSteps / props.steps.length) * 100)
})

const progressClass = computed(() => {
  if (props.isFailed) return 'failed'
  if (props.isCompleted) return 'completed'
  return 'running'
})

const statusText = computed(() => {
  if (props.workflowState?.status === 'running') return '处理中'
  if (props.workflowState?.status === 'completed') return '已完成'
  if (props.workflowState?.status === 'failed') return '失败'
  return '等待开始'
})

const statusType = computed(() => {
  if (props.workflowState?.status === 'running') return 'primary'
  if (props.workflowState?.status === 'completed') return 'success'
  if (props.workflowState?.status === 'failed') return 'danger'
  return 'info'
})

const elapsedTime = computed(() => {
  if (!props.workflowState?.startTime) return '0秒'
  
  const start = new Date(props.workflowState.startTime)
  const end = props.workflowState.endTime
    ? new Date(props.workflowState.endTime)
    : new Date()
  
  const duration = Math.floor((end.getTime() - start.getTime()) / 1000)
  
  if (duration < 60) return `${duration}秒`
  if (duration < 3600) return `${Math.floor(duration / 60)}分${duration % 60}秒`
  return `${Math.floor(duration / 3600)}时${Math.floor((duration % 3600) / 60)}分`
})

const getStepClass = (step: WorkflowStep) => {
  return {
    pending: step.status === WorkflowStepStatus.PENDING,
    running: step.status === WorkflowStepStatus.RUNNING,
    completed: step.status === WorkflowStepStatus.COMPLETED,
    failed: step.status === WorkflowStepStatus.FAILED,
    warning: step.status === WorkflowStepStatus.WARNING,
    waiting_review: step.status === WorkflowStepStatus.WAITING_REVIEW
  }
}

const isStepCompleted = (step: WorkflowStep | undefined) => {
  if (!step) return false
  return step.status === WorkflowStepStatus.COMPLETED ||
    step.status === WorkflowStepStatus.FAILED
}

const formatDuration = (duration?: number): string => {
  if (!duration) return '-'
  const seconds = Math.floor(duration / 1000)
  if (seconds < 60) return `${seconds}秒`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (minutes < 60) return `${minutes}分${remainingSeconds}秒`
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return `${hours}时${remainingMinutes}分`
}

const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const handleCancel = () => {
  ElMessageBox.confirm('确定要取消当前工作流吗？', '确认取消', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    emit('cancel')
  }).catch(() => {})
}

const handleRetry = () => {
  emit('retry')
}

const handleViewDetails = () => {
  emit('viewDetails')
}
</script>

<style scoped>
.tax-workflow-viewer {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.workflow-card,
.history-card {
  border-radius: 12px;
  border: none;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
}

.workflow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.header-icon {
  font-size: 24px;
  color: #409EFF;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 进度条 */
.progress-section {
  margin-bottom: 30px;
  padding: 20px;
  background: #ffffff;
  border-radius: 12px;
  color: #111827;
  border: 1px solid #e5e7eb;
}

.dark .progress-section {
  background: #1f2937;
  color: #f9fafb;
  border-color: #374151;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.progress-text {
  font-size: 16px;
  font-weight: 500;
}

.dark .progress-text {
  color: #f9fafb;
}

.progress-time {
  font-size: 14px;
  color: #6b7280;
}

.dark .progress-time {
  color: #9ca3af;
}

.progress-bar-container {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
}

.dark .progress-bar {
  background: #374151;
}

.progress-fill {
  height: 100%;
  background: #3b82f6;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-fill.running {
  animation: progressPulse 2s ease-in-out infinite;
}

.progress-fill.failed {
  background: #f56c6c;
}

.progress-fill.completed {
  background: #67c23a;
}

@keyframes progressPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.progress-percentage {
  font-size: 14px;
  font-weight: 600;
  min-width: 45px;
  text-align: right;
}

/* 步骤条 */
.steps-container {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 20px 0;
}

.step-item {
  display: flex;
  align-items: flex-start;
  position: relative;
}

.step-connector {
  position: absolute;
  left: 23px;
  top: 48px;
  height: calc(100% - 28px);
  width: 2px;
}

.connector-line {
  width: 100%;
  height: 100%;
  background: #e0e0e0;
  transition: background 0.3s ease;
}

.connector-line.completed {
  background: linear-gradient(180deg, #67c23a 0%, #85ce61 100%);
}

.connector-line.failed {
  background: linear-gradient(180deg, #f56c6c 0%, #f78989 100%);
}

.step-node {
  display: flex;
  gap: 16px;
  padding: 12px 16px;
  border-radius: 12px;
  transition: all 0.3s ease;
  flex: 1;
}

.step-node:hover {
  background: rgba(64, 158, 255, 0.05);
}

.step-icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 16px;
  transition: all 0.3s ease;
  position: relative;
  z-index: 1;
  flex-shrink: 0;
}

.step-item.pending .step-icon-wrapper {
  background: linear-gradient(135deg, #909399 0%, #a6a9ad 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(144, 147, 153, 0.3);
}

.step-item.running .step-icon-wrapper {
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
  animation: stepPulse 1.5s ease-in-out infinite;
}

.step-item.completed .step-icon-wrapper {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.3);
}

.step-item.failed .step-icon-wrapper {
  background: linear-gradient(135deg, #f56c6c 0%, #f78989 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(245, 108, 108, 0.3);
}

.step-item.warning .step-icon-wrapper {
  background: linear-gradient(135deg, #e6a23c 0%, #ebb563 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(230, 162, 60, 0.3);
}

.step-item.waiting_review .step-icon-wrapper {
  background: linear-gradient(135deg, #9b59b6 0%, #bb79d1 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(155, 89, 182, 0.3);
  animation: reviewPulse 2s ease-in-out infinite;
}

@keyframes stepPulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

@keyframes reviewPulse {
  0%, 100% { box-shadow: 0 4px 12px rgba(155, 89, 182, 0.3); }
  50% { box-shadow: 0 4px 20px rgba(155, 89, 182, 0.5); }
}

.step-icon {
  font-size: 24px;
}

.step-number {
  font-size: 16px;
}

.step-content {
  flex: 1;
  padding-top: 4px;
}

.step-label {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.step-description {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.step-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #c0c4cc;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.step-error {
  margin-top: 8px;
  padding: 8px 12px;
  background: rgba(245, 108, 108, 0.1);
  border-left: 3px solid #f56c6c;
  border-radius: 4px;
  font-size: 13px;
  color: #f56c6c;
  display: flex;
  align-items: center;
  gap: 6px;
}

.step-warnings {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* 历史记录 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.history-item:hover {
  background: rgba(64, 158, 255, 0.05);
}

.history-item.success {
  background: rgba(103, 194, 58, 0.05);
  border-left: 3px solid #67c23a;
}

.history-item.error {
  background: rgba(245, 108, 108, 0.05);
  border-left: 3px solid #f56c6c;
}

.history-item.warning {
  background: rgba(230, 162, 60, 0.05);
  border-left: 3px solid #e6a23c;
}

.history-item.info {
  background: rgba(64, 158, 255, 0.05);
  border-left: 3px solid #409eff;
}

.history-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.history-item.success .history-icon {
  color: #67c23a;
}

.history-item.error .history-icon {
  color: #f56c6c;
}

.history-item.warning .history-icon {
  color: #e6a23c;
}

.history-item.info .history-icon {
  color: #409eff;
}

.history-content {
  flex: 1;
}

.history-message {
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
}

.history-time {
  font-size: 12px;
  color: #909399;
}

.error-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}
</style>
