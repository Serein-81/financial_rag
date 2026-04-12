<template>
  <el-dialog
    v-model="dialogVisible"
    title="手动录入税务报告"
    width="900px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-width="120px"
      class="manual-entry-form"
    >
      <el-divider content-position="left">
        <el-icon><FileText /></el-icon>
        基本信息
      </el-divider>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="税务类型" prop="tax_type">
            <el-select v-model="formData.tax_type" placeholder="请选择税务类型" style="width: 100%">
              <el-option label="增值税" value="vat" />
              <el-option label="企业所得税" value="income" />
              <el-option label="个人所得税" value="personal" />
              <el-option label="消费税" value="consumption" />
              <el-option label="行为税" value="behavior" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="财务年度" prop="fiscal_year">
            <el-input-number
              v-model="formData.fiscal_year"
              :min="2000"
              :max="2100"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="财务期间" prop="fiscal_period">
            <el-date-picker
              v-model="fiscalPeriod"
              type="month"
              placeholder="选择财务期间"
              format="YYYY-MM"
              value-format="YYYY-MM"
              style="width: 100%"
              :disabled-date="disabledDate"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="关联财务数据">
            <el-select
              v-model="formData.financial_data_id"
              placeholder="可选：关联已有财务数据"
              clearable
              filterable
              style="width: 100%"
              @focus="loadFinancialData"
            >
              <el-option
                v-for="item in financialDataList"
                :key="item.id"
                :label="`${item.fiscal_year}年 ${item.period_type}`"
                :value="item.id"
              >
                <span>{{ item.fiscal_year }}年 {{ item.period_type }}</span>
                <span style="float: right; color: #8492a6; font-size: 13px">
                  营收: {{ formatCurrency(item.total_revenue) }}
                </span>
              </el-option>
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-divider content-position="left">
        <el-icon><BarChart /></el-icon>
        营收信息
      </el-divider>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="营业收入" prop="revenue">
            <el-input-number
              v-model="formData.revenue"
              :min="0"
              :precision="2"
              :controls="false"
              placeholder="请输入营业收入"
              style="width: 100%"
            >
              <template #suffix>元</template>
            </el-input-number>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="应税销售额" prop="taxable_sales">
            <el-input-number
              v-model="formData.taxable_sales"
              :min="0"
              :precision="2"
              :controls="false"
              placeholder="请输入应税销售额"
              style="width: 100%"
            >
              <template #suffix>元</template>
            </el-input-number>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="免税销售额" prop="tax_free_sales">
            <el-input-number
              v-model="formData.tax_free_sales"
              :min="0"
              :precision="2"
              :controls="false"
              placeholder="请输入免税销售额"
              style="width: 100%"
            >
              <template #suffix>元</template>
            </el-input-number>
          </el-form-item>
        </el-col>
      </el-row>

      <el-divider content-position="left">
        <el-icon><DollarSign /></el-icon>
        税务信息
      </el-divider>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="进项税额" prop="input_tax">
            <el-input-number
              v-model="formData.input_tax"
              :min="0"
              :precision="2"
              :controls="false"
              placeholder="请输入进项税额"
              style="width: 100%"
            >
              <template #suffix>元</template>
            </el-input-number>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="销项税额" prop="output_tax">
            <el-input-number
              v-model="formData.output_tax"
              :min="0"
              :precision="2"
              :controls="false"
              placeholder="请输入销项税额"
              style="width: 100%"
            >
              <template #suffix>元</template>
            </el-input-number>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="增值税率" prop="vat_rate">
            <el-input-number
              v-model="formData.vat_rate"
              :min="0"
              :max="1"
              :precision="4"
              :controls="false"
              placeholder="请输入增值税率"
              style="width: 100%"
            >
              <template #suffix>%</template>
            </el-input-number>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="企业所得税率" prop="corporate_tax_rate">
            <el-input-number
              v-model="formData.corporate_tax_rate"
              :min="0"
              :max="1"
              :precision="4"
              :controls="false"
              placeholder="请输入企业所得税率"
              style="width: 100%"
            >
              <template #suffix>%</template>
            </el-input-number>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="应纳税所得额" prop="taxable_income">
            <el-input-number
              v-model="formData.taxable_income"
              :min="0"
              :precision="2"
              :controls="false"
              placeholder="请输入应纳税所得额"
              style="width: 100%"
            >
              <template #suffix>元</template>
            </el-input-number>
          </el-form-item>
        </el-col>
      </el-row>

      <el-divider content-position="left">
        <el-icon><Calculator /></el-icon>
        支出与成本
      </el-divider>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="总支出" prop="total_expenses">
            <el-input-number
              v-model="formData.total_expenses"
              :min="0"
              :precision="2"
              :controls="false"
              placeholder="请输入总支出"
              style="width: 100%"
            >
              <template #suffix>元</template>
            </el-input-number>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="可抵扣支出" prop="deductible_expenses">
            <el-input-number
              v-model="formData.deductible_expenses"
              :min="0"
              :precision="2"
              :controls="false"
              placeholder="请输入可抵扣支出"
              style="width: 100%"
            >
              <template #suffix>元</template>
            </el-input-number>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="工资薪金总额" prop="total_payroll">
            <el-input-number
              v-model="formData.total_payroll"
              :min="0"
              :precision="2"
              :controls="false"
              placeholder="请输入工资薪金总额"
              style="width: 100%"
            >
              <template #suffix>元</template>
            </el-input-number>
          </el-form-item>
        </el-col>
      </el-row>

      <el-divider content-position="left">
        <el-icon><Receipt /></el-icon>
        发票统计
      </el-divider>

      <el-row :gutter="20">
        <el-col :span="8">
          <el-form-item label="发票总数" prop="total_invoices">
            <el-input-number
              v-model="formData.total_invoices"
              :min="0"
              :precision="0"
              :controls="false"
              placeholder="请输入发票总数"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="进项发票数" prop="input_invoice_count">
            <el-input-number
              v-model="formData.input_invoice_count"
              :min="0"
              :precision="0"
              :controls="false"
              placeholder="请输入进项发票数"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="销项发票数" prop="output_invoice_count">
            <el-input-number
              v-model="formData.output_invoice_count"
              :min="0"
              :precision="0"
              :controls="false"
              placeholder="请输入销项发票数"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-divider content-position="left">
        <el-icon><Settings /></el-icon>
        其他设置
      </el-divider>

      <el-form-item label="备注">
        <el-input
          v-model="formData.notes"
          type="textarea"
          :rows="2"
          placeholder="可选：添加备注信息"
        />
      </el-form-item>

      <el-form-item label="AI分析">
        <el-switch
          v-model="formData.run_analysis"
          active-text="提交后立即运行AI分析"
          inactive-text="仅保存数据，稍后分析"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          确认录入
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { FileText, BarChart, DollarSign, Receipt, Settings, Calculator } from 'lucide-vue-next'
import { taxReportApiClient } from '@/api/tax-report'
import type { TaxTypeEnum } from '@/types/tax'

interface Props {
  visible: boolean
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'success', data: any): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const fiscalPeriod = ref('')
const financialDataList = ref<any[]>([])

const formData = reactive({
  tax_type: '' as TaxTypeEnum | '',
  fiscal_year: new Date().getFullYear(),
  fiscal_period: '',
  company_name: '',
  tax_id: '',
  revenue: 0,
  taxable_sales: 0,
  tax_free_sales: 0,
  input_tax: 0,
  output_tax: 0,
  vat_rate: 0.13,
  total_expenses: 0,
  deductible_expenses: 0,
  taxable_income: 0,
  corporate_tax_rate: 0.25,
  total_payroll: 0,
  total_invoices: 0,
  input_invoice_count: 0,
  output_invoice_count: 0,
  financial_data_id: '',
  notes: '',
  run_analysis: true,
})

const formRules: FormRules = {
  tax_type: [
    { required: true, message: '请选择税务类型', trigger: 'change' },
  ],
  fiscal_year: [
    { required: true, message: '请输入财务年度', trigger: 'blur' },
  ],
  revenue: [
    { required: true, message: '请输入营业收入', trigger: 'blur' },
  ],
}

watch(() => props.visible, (val) => {
  dialogVisible.value = val
  if (val) {
    resetForm()
  }
})

watch(dialogVisible, (val) => {
  emit('update:visible', val)
})

watch(fiscalPeriod, (val) => {
  formData.fiscal_period = val
})

const disabledDate = (date: Date) => {
  return date.getFullYear() < 2000 || date.getFullYear() > 2100
}

const formatCurrency = (value: number) => {
  if (!value && value !== 0) return '¥0'
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

const loadFinancialData = async () => {
  if (financialDataList.value.length > 0) return
  
  try {
    const result = await taxReportApiClient.getFinancialDataList({
      fiscal_year: formData.fiscal_year,
      limit: 50,
    })
    financialDataList.value = result.items || []
  } catch (error) {
    console.error('加载财务数据失败:', error)
  }
}

const resetForm = () => {
  formData.tax_type = ''
  formData.fiscal_year = new Date().getFullYear()
  fiscalPeriod.value = ''
  formData.company_name = ''
  formData.tax_id = ''
  formData.revenue = 0
  formData.taxable_sales = 0
  formData.tax_free_sales = 0
  formData.input_tax = 0
  formData.output_tax = 0
  formData.vat_rate = 0.13
  formData.total_expenses = 0
  formData.deductible_expenses = 0
  formData.taxable_income = 0
  formData.corporate_tax_rate = 0.25
  formData.total_payroll = 0
  formData.total_invoices = 0
  formData.input_invoice_count = 0
  formData.output_invoice_count = 0
  formData.financial_data_id = ''
  formData.notes = ''
  formData.run_analysis = true
  formRef.value?.clearValidate()
}

const handleClose = () => {
  dialogVisible.value = false
  resetForm()
}

const handleSubmit = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
  } catch {
    ElMessage.warning('请完善表单信息')
    return
  }
  
  submitting.value = true
  
  try {
    const submitData = {
      ...formData,
      tax_type: formData.tax_type as TaxTypeEnum,
    }
    
    const result = await taxReportApiClient.createManualTaxReport(submitData)
    
    if (result.success) {
      ElMessage.success({
        message: formData.run_analysis 
          ? '税务报告录入成功，AI分析已启动' 
          : '税务报告录入成功',
        duration: 3000,
      })
      emit('success', result.data)
      handleClose()
    } else {
      ElMessage.error(result.message || '录入失败')
    }
  } catch (error: any) {
    console.error('提交失败:', error)
    ElMessage.error(error.response?.data?.detail || error.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

defineExpose({
  open: () => {
    dialogVisible.value = true
  },
})
</script>

<style scoped lang="css">
.manual-entry-form {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 10px;
  
  &::-webkit-scrollbar {
    width: 6px;
  }
  
  &::-webkit-scrollbar-thumb {
    background: #dcdfe6;
    border-radius: 3px;
  }
  
  &::-webkit-scrollbar-track {
    background: #f5f7fa;
    border-radius: 3px;
  }
}

:deep(.el-divider__text) {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #409eff;
  font-weight: 500;
}

:deep(.el-input-number) {
  .el-input__wrapper {
    text-align: left;
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
