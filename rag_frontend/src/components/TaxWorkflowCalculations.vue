<template>
  <div class="tax-workflow-calculations">
    <el-card
      v-for="calc in calculations"
      :key="calc.taxType"
      class="calculation-card"
      shadow="hover"
    >
      <template #header>
        <div class="card-header">
          <span class="tax-type">{{ calc.taxType }}</span>
          <el-tag type="success" size="small">
            税率: {{ (calc.taxRate * 100).toFixed(2) }}%
          </el-tag>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="8">
          <div class="stat-item">
            <div class="stat-label">计税金额</div>
            <div class="stat-value primary">
              ¥{{ formatNumber(calc.taxableAmount) }}
            </div>
          </div>
        </el-col>

        <el-col :span="8">
          <div class="stat-item">
            <div class="stat-label">适用税率</div>
            <div class="stat-value">
              {{ (calc.taxRate * 100).toFixed(2) }}%
            </div>
          </div>
        </el-col>

        <el-col :span="8">
          <div class="stat-item">
            <div class="stat-label">应纳税额</div>
            <div class="stat-value warning">
              ¥{{ formatNumber(calc.calculatedTax) }}
            </div>
          </div>
        </el-col>
      </el-row>

      <el-divider />

      <el-row :gutter="20">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">进项税额</div>
            <div class="stat-value info">
              ¥{{ formatNumber(calc.inputTax) }}
            </div>
          </div>
        </el-col>

        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">销项税额</div>
            <div class="stat-value info">
              ¥{{ formatNumber(calc.outputTax) }}
            </div>
          </div>
        </el-col>

        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">实际税率</div>
            <div class="stat-value">
              {{ (calc.effectiveRate * 100).toFixed(2) }}%
            </div>
          </div>
        </el-col>

        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">净应纳税额</div>
            <div class="stat-value danger">
              ¥{{ formatNumber(calc.netTaxPayable) }}
            </div>
          </div>
        </el-col>
      </el-row>

      <div class="effective-rate-chart">
        <div class="rate-bar">
          <div
            class="rate-fill"
            :style="{ width: Math.min(calc.effectiveRate * 100, 100) + '%' }"
          ></div>
        </div>
        <div class="rate-label">
          实际税负率: {{ (calc.effectiveRate * 100).toFixed(2) }}%
        </div>
      </div>
    </el-card>

    <el-empty v-if="calculations.length === 0" description="暂无计算结果" />
  </div>
</template>

<script setup lang="ts">
import type { TaxCalculationResult } from '@/types/tax-workflow'

interface Props {
  calculations: TaxCalculationResult[]
}

defineProps<Props>()

const formatNumber = (value: number): string => {
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}
</script>

<style scoped>
.calculation-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tax-type {
  font-weight: 600;
  font-size: 16px;
}

.stat-item {
  text-align: center;
  padding: 12px 8px;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.stat-value.primary {
  color: #409eff;
}

.stat-value.warning {
  color: #e6a23c;
}

.stat-value.danger {
  color: #f56c6c;
}

.stat-value.info {
  color: #909399;
}

.effective-rate-chart {
  margin-top: 16px;
}

.rate-bar {
  height: 8px;
  background: #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.rate-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #67c23a);
  transition: width 0.3s ease;
}

.rate-label {
  text-align: center;
  margin-top: 8px;
  font-size: 12px;
  color: #606266;
}
</style>
