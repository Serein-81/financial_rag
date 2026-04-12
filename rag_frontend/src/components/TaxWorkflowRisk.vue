<template>
  <div class="tax-workflow-risk">
    <el-row :gutter="20" class="summary-row">
      <el-col :span="6">
        <el-card class="summary-card" shadow="hover">
          <div class="summary-content">
            <div class="summary-value danger">{{ assessment.overallScore }}</div>
            <div class="summary-label">风险评分</div>
            <el-rate v-model="assessment.overallScore" disabled size="small" />
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="summary-card critical" shadow="hover">
          <div class="summary-content">
            <div class="summary-value">
              {{ countBySeverity('critical') }}
            </div>
            <div class="summary-label">严重风险</div>
            <el-icon class="critical-icon"><AlertTriangleFilled /></el-icon>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="summary-card high" shadow="hover">
          <div class="summary-content">
            <div class="summary-value">
              {{ countBySeverity('high') }}
            </div>
            <div class="summary-label">高风险</div>
            <el-icon class="high-icon"><AlertTriangle /></el-icon>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card class="summary-card medium" shadow="hover">
          <div class="summary-content">
            <div class="summary-value">
              {{ countBySeverity('medium') + countBySeverity('low') }}
            </div>
            <div class="summary-label">中低风险</div>
            <el-icon class="medium-icon"><InfoFilled /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="risk-items-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>
            <el-icon><AlertTriangleFilled /></el-icon>
            风险项详情
          </span>
        </div>
      </template>

      <el-collapse v-model="activeRiskItems" class="risk-collapse">
        <el-collapse-item
          v-for="(item, index) in assessment.riskItems"
          :key="index"
          :name="index"
          :class="'risk-item-' + item.severity"
        >
          <template #title>
            <div class="risk-item-header">
              <el-tag
                :type="getSeverityType(item.severity)"
                size="small"
                effect="dark"
              >
                {{ getSeverityText(item.severity) }}
              </el-tag>
              <span class="risk-title">{{ item.riskType }}</span>
            </div>
          </template>

          <div class="risk-detail">
            <el-alert
              :title="item.description"
              :type="getSeverityType(item.severity)"
              :closable="false"
              show-icon
            >
              <template #default>
                <div class="risk-info">
                  <div class="info-item">
                    <strong>潜在处罚:</strong>
                    {{ item.potentialPenalty }}
                  </div>
                </div>
              </template>
            </el-alert>

            <el-divider content-position="left">
              <el-icon><Document /></el-icon>
              法律依据
            </el-divider>

            <div class="legal-basis">
              <el-tag
                v-for="(law, i) in item.legalBasis"
                :key="i"
                size="small"
                effect="plain"
                class="law-tag"
              >
                {{ law }}
              </el-tag>
            </div>

            <el-divider content-position="left">
              <el-icon><Memo /></el-icon>
              整改建议
            </el-divider>

            <el-ul class="suggestions">
              <li
                v-for="(suggestion, i) in item.remediationSuggestions"
                :key="i"
                class="suggestion-item"
              >
                {{ suggestion }}
              </li>
            </el-ul>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import {
  WarningFilled,
  AlertTriangle,
  InfoFilled,
  Document,
  Memo
} from '@element-plus/icons-vue'
import type { RiskAssessmentResult } from '@/types/tax-workflow'

interface Props {
  assessment: RiskAssessmentResult
}

const props = defineProps<Props>()

const activeRiskItems = ref<number[]>([])

const countBySeverity = (severity: string): number => {
  return props.assessment.riskItems.filter(item => item.severity === severity).length
}

const getSeverityType = (severity: string): '' | 'success' | 'warning' | 'danger' | 'info' => {
  switch (severity) {
    case 'critical':
      return 'error'
    case 'high':
      return 'warning'
    case 'medium':
      return 'info'
    case 'low':
      return 'success'
    default:
      return 'info'
  }
}

const getSeverityText = (severity: string): string => {
  switch (severity) {
    case 'critical':
      return '严重'
    case 'high':
      return '高危'
    case 'medium':
      return '中等'
    case 'low':
      return '低危'
    default:
      return '未知'
  }
}
</script>

<style scoped>
.summary-row {
  margin-bottom: 20px;
}

.summary-card {
  text-align: center;
}

.summary-card.critical {
  border-left: 4px solid #f56c6c;
}

.summary-card.high {
  border-left: 4px solid #e6a23c;
}

.summary-card.medium {
  border-left: 4px solid #909399;
}

.summary-content {
  padding: 16px;
}

.summary-value {
  font-size: 32px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 8px;
}

.summary-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.critical-icon {
  color: #f56c6c;
  font-size: 20px;
}

.high-icon {
  color: #e6a23c;
  font-size: 20px;
}

.medium-icon {
  color: #909399;
  font-size: 20px;
}

.risk-items-card {
  margin-top: 16px;
}

.card-header {
  font-weight: 600;
}

.risk-item-header {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.risk-title {
  flex: 1;
  font-weight: 600;
}

.risk-detail {
  padding: 16px;
}

.risk-info {
  margin-top: 12px;
}

.info-item {
  line-height: 1.8;
}

.law-tag {
  margin-right: 8px;
  margin-bottom: 8px;
}

.suggestions {
  padding-left: 20px;
}

.suggestion-item {
  line-height: 2;
  color: #606266;
  margin-bottom: 8px;
}

.suggestion-item:last-child {
  margin-bottom: 0;
}

:deep(.el-collapse-item__header) {
  font-weight: 600;
}

.risk-item-critical :deep(.el-collapse-item__header) {
  background-color: #fef0f0;
}

.risk-item-high :deep(.el-collapse-item__header) {
  background-color: #fdf6ec;
}
</style>
