<template>
  <div class="issue-list">
    <div v-for="(issue, index) in issues" :key="index" class="issue-item" :class="issue.severity">
      <div class="issue-header">
        <el-icon class="issue-icon">
          <AlertTriangle v-if="issue.severity === 'high'" />
          <AlertTriangle v-else-if="issue.severity === 'medium'" />
          <InfoFilled v-else />
        </el-icon>
        <span class="issue-title">{{ issue.title || issue.description }}</span>
        <el-tag :type="getSeverityType(issue.severity)" size="small">
          {{ getSeverityText(issue.severity) }}
        </el-tag>
      </div>
      <div v-if="issue.description" class="issue-description">
        {{ issue.description }}
      </div>
      <div v-if="issue.amount" class="issue-amount">
        <el-icon><Money /></el-icon>
        <span>涉及金额: ¥{{ formatNumber(issue.amount) }}</span>
      </div>
      <div v-if="issue.suggestion" class="issue-suggestion">
        <strong>建议:</strong> {{ issue.suggestion }}
      </div>
      <div v-if="issue.evidence" class="issue-evidence">
        <strong>证据:</strong> {{ issue.evidence }}
      </div>
    </div>
    <el-empty v-if="!issues || issues.length === 0" description="暂无问题" :image-size="80" />
  </div>
</template>

<script setup lang="ts">
import { AlertTriangle, InfoFilled, Money } from '@element-plus/icons-vue'

interface Issue {
  title?: string
  description: string
  severity?: 'high' | 'medium' | 'low'
  amount?: number
  suggestion?: string
  evidence?: string
}

defineProps<{
  issues: Issue[]
  type?: 'tax' | 'finance' | 'legal'
}>()

const formatNumber = (value: number): string => {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value)
}

const getSeverityType = (severity?: string) => {
  switch (severity) {
    case 'high':
      return 'danger'
    case 'medium':
      return 'warning'
    default:
      return 'info'
  }
}

const getSeverityText = (severity?: string) => {
  switch (severity) {
    case 'high':
      return '高'
    case 'medium':
      return '中'
    case 'low':
      return '低'
    default:
      return '信息'
  }
}
</script>

<style scoped>
.issue-list {
  max-height: 400px;
  overflow-y: auto;
}

.issue-item {
  padding: 16px;
  margin-bottom: 12px;
  border-radius: 8px;
  background: #f5f7fa;
  border-left: 4px solid #909399;
}

.issue-item.high {
  background: #fef0f0;
  border-left-color: #f56c6c;
}

.issue-item.medium {
  background: #fdf6ec;
  border-left-color: #e6a23c;
}

.issue-item.low {
  background: #f0f9eb;
  border-left-color: #67c23a;
}

.issue-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.issue-icon {
  font-size: 18px;
}

.issue-item.high .issue-icon {
  color: #f56c6c;
}

.issue-item.medium .issue-icon {
  color: #e6a23c;
}

.issue-item.low .issue-icon {
  color: #67c23a;
}

.issue-title {
  flex: 1;
  font-weight: 600;
  font-size: 14px;
}

.issue-description {
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 8px;
}

.issue-amount {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #f56c6c;
  font-size: 13px;
  margin-bottom: 8px;
}

.issue-suggestion,
.issue-evidence {
  color: #606266;
  font-size: 12px;
  line-height: 1.5;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #dcdfe6;
}

.issue-suggestion strong,
.issue-evidence strong {
  color: #303133;
}
</style>
