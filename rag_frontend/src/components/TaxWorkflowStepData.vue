<template>
  <div class="tax-workflow-step-data">
    <el-collapse v-model="activeSteps" class="step-collapse">
      <el-collapse-item
        v-for="step in steps"
        :key="step.name"
        :name="step.name"
        :disabled="!step.data"
      >
        <template #title>
          <div class="step-header">
            <el-tag :type="getStatusType(step.status)" size="small">
              {{ getStatusText(step.status) }}
            </el-tag>
            <span class="step-name">{{ step.label }}</span>
            <span class="step-duration" v-if="step.duration">
              {{ formatDuration(step.duration) }}
            </span>
          </div>
        </template>

        <div class="step-data-content" v-if="step.data">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item
              v-for="(value, key) in formatStepData(step.data)"
              :key="key"
              :label="formatLabel(key as string)"
            >
              <span v-if="isSimpleValue(value)">{{ value }}</span>
              <el-tag v-else-if="Array.isArray(value)" size="small">
                {{ value.length }} 项
              </el-tag>
              <span v-else-if="typeof value === 'object'">
                <pre class="json-content">{{ JSON.stringify(value, null, 2) }}</pre>
              </span>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <el-empty v-else description="暂无数据" :image-size="60" />
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { WorkflowStep } from '@/types/tax-workflow'
import { WorkflowStepStatus } from '@/types/tax-workflow'

interface Props {
  steps: WorkflowStep[]
}

const props = defineProps<Props>()

const activeSteps = ref<string[]>([])

const getStatusType = (status: WorkflowStepStatus): '' | 'success' | 'warning' | 'danger' | 'info' => {
  switch (status) {
    case WorkflowStepStatus.COMPLETED:
      return 'success'
    case WorkflowStepStatus.RUNNING:
      return 'primary'
    case WorkflowStepStatus.FAILED:
      return 'danger'
    case WorkflowStepStatus.WARNING:
      return 'warning'
    case WorkflowStepStatus.WAITING_REVIEW:
      return 'warning'
    default:
      return 'info'
  }
}

const getStatusText = (status: WorkflowStepStatus): string => {
  switch (status) {
    case WorkflowStepStatus.PENDING:
      return '待处理'
    case WorkflowStepStatus.RUNNING:
      return '运行中'
    case WorkflowStepStatus.COMPLETED:
      return '已完成'
    case WorkflowStepStatus.FAILED:
      return '失败'
    case WorkflowStepStatus.WARNING:
      return '警告'
    case WorkflowStepStatus.WAITING_REVIEW:
      return '待审核'
    default:
      return '未知'
  }
}

const formatDuration = (ms: number): string => {
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}秒`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}分${remainingSeconds}秒`
}

const formatLabel = (key: string): string => {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .trim()
    .replace(/^./, (str) => str.toUpperCase())
}

const formatStepData = (data: Record<string, any>): Record<string, any> => {
  const formatted: Record<string, any> = {}
  for (const [key, value] of Object.entries(data)) {
    if (value === null || value === undefined) {
      continue
    }
    if (typeof value === 'object' && !Array.isArray(value)) {
      formatted[key] = JSON.stringify(value)
    } else {
      formatted[key] = value
    }
  }
  return formatted
}

const isSimpleValue = (value: any): boolean => {
  return (
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  )
}
</script>

<style scoped>
.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.step-name {
  flex: 1;
  font-weight: 600;
}

.step-duration {
  color: #909399;
  font-size: 12px;
}

.step-data-content {
  padding: 12px;
}

.json-content {
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
  max-height: 200px;
}
</style>
