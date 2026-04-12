<template>
  <el-dialog
    v-model="dialogVisible"
    title="人工审核"
    width="900px"
    :close-on-click-modal="false"
    class="human-review-dialog"
  >
    <div class="review-content">
      <el-alert
        :title="reviewTitle"
        type="warning"
        :closable="false"
        show-icon
        class="review-alert"
      >
        <template #default>
          <div class="alert-description">
            检测到 <strong>{{ riskItemCount }}</strong> 个需要人工审核的风险项，请仔细评估后做出决定。
          </div>
        </template>
      </el-alert>

      <el-card class="risk-items-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="header-title">
              <el-icon><AlertTriangleFilled /></el-icon>
              风险项详情
            </span>
            <el-tag type="danger" size="large">
              {{ riskItemCount }} 项待审核
            </el-tag>
          </div>
        </template>

        <el-scrollbar height="400px">
          <div class="risk-items-list">
            <el-collapse v-model="activeNames" class="risk-collapse">
              <el-collapse-item
                v-for="(item, index) in riskItems"
                :key="index"
                :name="index"
                class="risk-item"
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
                    <el-tag
                      :type="getSeverityType(item.severity)"
                      size="small"
                      plain
                    >
                      {{ item.severity }}
                    </el-tag>
                  </div>
                </template>

                <div class="risk-detail">
                  <el-descriptions :column="2" border size="small">
                    <el-descriptions-item label="风险描述">
                      <span class="description-text">{{ item.description }}</span>
                    </el-descriptions-item>
                    <el-descriptions-item label="潜在处罚">
                      <el-tag type="danger" size="small">
                        {{ item.potentialPenalty }}
                      </el-tag>
                    </el-descriptions-item>
                  </el-descriptions>

                  <div class="legal-basis">
                    <div class="section-title">
                      <el-icon><Document /></el-icon>
                      法律依据
                    </div>
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

                  <div class="suggestions">
                    <div class="section-title">
                      <el-icon><Memo /></el-icon>
                      整改建议
                    </div>
                    <el-ul>
                      <li
                        v-for="(suggestion, i) in item.remediationSuggestions"
                        :key="i"
                        class="suggestion-item"
                      >
                        {{ suggestion }}
                      </li>
                    </el-ul>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-scrollbar>
      </el-card>

      <el-card class="review-form-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="header-title">
              <el-icon><EditPen /></el-icon>
              审核意见
            </span>
          </div>
        </template>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
        >
          <el-form-item label="审核决定" prop="decision">
            <el-radio-group v-model="form.decision" size="large">
              <el-radio-button value="approved">
                <el-icon><Check /></el-icon>
                批准通过
              </el-radio-button>
              <el-radio-button value="rejected">
                <el-icon><CloseBold /></el-icon>
                拒绝驳回
              </el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="审核意见" prop="comment">
            <el-input
              v-model="form.comment"
              type="textarea"
              :rows="4"
              :placeholder="getCommentPlaceholder()"
              maxlength="500"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="备注">
            <el-input
              v-model="form.note"
              type="textarea"
              :rows="2"
              placeholder="补充说明（可选）"
              maxlength="200"
            />
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel">取消</el-button>
        <el-button
          type="danger"
          @click="handleReject"
          :loading="loading"
          :disabled="form.decision !== 'rejected'"
        >
          <el-icon><CloseBold /></el-icon>
          拒绝
        </el-button>
        <el-button
          type="success"
          @click="handleApprove"
          :loading="loading"
          :disabled="form.decision !== 'approved'"
        >
          <el-icon><Check /></el-icon>
          批准
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  WarningFilled,
  Document,
  Memo,
  EditPen,
  Check,
  CloseBold
} from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { RiskItem, HumanReviewRequestData } from '@/types/tax-workflow'

interface Props {
  visible: boolean
  reviewData: HumanReviewRequestData | null
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'approve', data: { comment: string; note?: string }): void
  (e: 'reject', data: { comment: string; note?: string }): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const dialogVisible = ref(false)
const activeNames = ref<number[]>([0])
const loading = ref(false)
const formRef = ref<FormInstance>()

const form = ref({
  decision: 'approved' as 'approved' | 'rejected',
  comment: '',
  note: ''
})

const rules: FormRules = {
  decision: [
    { required: true, message: '请选择审核决定', trigger: 'change' }
  ],
  comment: [
    { required: true, message: '请输入审核意见', trigger: 'blur' },
    { min: 10, message: '审核意见至少需要10个字符', trigger: 'blur' }
  ]
}

const riskItems = computed(() => {
  return props.reviewData?.riskItems || []
})

const riskItemCount = computed(() => {
  return riskItems.value.length
})

const reviewTitle = computed(() => {
  if (riskItemCount.value === 0) {
    return '系统提示'
  }
  const highRiskCount = riskItems.value.filter(
    item => item.severity === 'high' || item.severity === 'critical'
  ).length
  return highRiskCount > 0
    ? `高风险预警：检测到 ${highRiskCount} 个高风险项`
    : '风险提示'
})

watch(() => props.visible, (val) => {
  dialogVisible.value = val
  if (val) {
    resetForm()
  }
})

watch(dialogVisible, (val) => {
  emit('update:visible', val)
})

const getSeverityType = (severity: string): '' | 'success' | 'warning' | 'danger' | 'info' => {
  switch (severity) {
    case 'critical':
      return 'danger'
    case 'high':
      return 'danger'
    case 'medium':
      return 'warning'
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

const getCommentPlaceholder = (): string => {
  if (form.value.decision === 'approved') {
    return '请输入批准原因，如：已核实相关资料，风险可控，同意提交。'
  } else if (form.value.decision === 'rejected') {
    return '请输入拒绝原因，如：存在重大税务风险，建议整改后重新提交。'
  }
  return '请先选择审核决定，然后输入审核意见。'
}

const resetForm = () => {
  form.value = {
    decision: 'approved',
    comment: '',
    note: ''
  }
  activeNames.value = [0]
  formRef.value?.clearValidate()
}

const handleApprove = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        emit('approve', {
          comment: form.value.comment,
          note: form.value.note || undefined
        })
        ElMessage.success('审核已批准')
        dialogVisible.value = false
      } catch (error) {
        ElMessage.error('操作失败，请重试')
      } finally {
        loading.value = false
      }
    }
  })
}

const handleReject = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        emit('reject', {
          comment: form.value.comment,
          note: form.value.note || undefined
        })
        ElMessage.warning('审核已拒绝')
        dialogVisible.value = false
      } catch (error) {
        ElMessage.error('操作失败，请重试')
      } finally {
        loading.value = false
      }
    }
  })
}

const handleCancel = () => {
  dialogVisible.value = false
  resetForm()
}
</script>

<style scoped>
.review-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.review-alert {
  border-radius: 8px;
}

.alert-description {
  margin-top: 8px;
  line-height: 1.6;
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
}

.risk-items-list {
  padding: 8px;
}

.risk-item {
  margin-bottom: 12px;
  border-radius: 8px;
  overflow: hidden;
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
  background: #f5f7fa;
  border-radius: 8px;
  margin-top: 12px;
}

.description-text {
  line-height: 1.6;
  color: #606266;
}

.legal-basis,
.suggestions {
  margin-top: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #409eff;
}

.law-tag {
  margin-right: 8px;
  margin-bottom: 8px;
}

.suggestion-item {
  line-height: 1.8;
  color: #606266;
  margin-bottom: 8px;
}

.suggestion-item:last-child {
  margin-bottom: 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

:deep(.el-radio-button__inner) {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
