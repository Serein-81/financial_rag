<script setup lang="ts">

import { ref, reactive, computed, onMounted, watch } from 'vue'

import { financialDataApiClient, type FinancialDataCreate, type FinancialDataResponse } from '@/api/financial-data'

import {

  Save,

  Calculator,

  TrendingUp,

  TrendingDown,

  DollarSign,

  AlertCircle,

  CheckCircle,

  Loader2,

  Trash2,

  Edit,

  RefreshCw,

  FileText,

  PiggyBank,

  Upload,

  Download,

  X,

  FileSpreadsheet,

  AlertTriangle,

  CheckCircle2

} from 'lucide-vue-next'

import { ElMessage } from 'element-plus'

import { ElDialog } from 'element-plus'



const isLoading = ref(false)

const isSaving = ref(false)

const isEditing = ref(false)

const isDownloadingTest = ref(false)

const savedData = ref<FinancialDataResponse | null>(null)

const fiscalYears = ref<number[]>([])



const currentYear = new Date().getFullYear()

for (let y = currentYear; y >= currentYear - 5; y--) {

  fiscalYears.value.push(y)

}



const periodTypes = [

  { label: '年度', value: 'yearly' },

  { label: '季度', value: 'quarterly' },

  { label: '月度', value: 'monthly' }

]



const quarters = [

  { label: 'Q1 (1-3月)', value: 1 },
  { label: 'Q2 (4-6月)', value: 2 },
  { label: 'Q3 (7-9月)', value: 3 },
  { label: 'Q4 (10-12月)', value: 4 }

]



const months = Array.from({ length: 12 }, (_, i) => ({

  label: `${i + 1}月`,

  value: i + 1

}))



const selectedQuarter = ref(1)

const selectedMonth = ref(1)



function calculatePeriodDates() {

  const year = formData.fiscal_year!

  if (formData.period_type === 'yearly') {

    formData.period_start = `${year}-01-01`

    formData.period_end = `${year}-12-31`

  } else if (formData.period_type === 'quarterly') {

    const startMonth = (selectedQuarter.value - 1) * 3 + 1

    const endMonth = selectedQuarter.value * 3

    const lastDay = new Date(year, endMonth, 0).getDate()

    formData.period_start = `${year}-${String(startMonth).padStart(2, '0')}-01`

    formData.period_end = `${year}-${String(endMonth).padStart(2, '0')}-${lastDay}`

  } else if (formData.period_type === 'monthly') {

    const lastDay = new Date(year, selectedMonth.value, 0).getDate()

    formData.period_start = `${year}-${String(selectedMonth.value).padStart(2, '0')}-01`

    formData.period_end = `${year}-${String(selectedMonth.value).padStart(2, '0')}-${lastDay}`

  }

}



const formData = reactive<FinancialDataCreate>({

  fiscal_year: currentYear,

  period_type: 'yearly',

  period_start: `${currentYear}-01-01`,

  period_end: `${currentYear}-12-31`,

  total_revenue: 0,

  taxable_sales: 0,

  tax_free_sales: 0,

  total_expenses: 0,

  deductible_expenses: 0,

  input_tax: 0,

  output_tax: 0,

  vat_rate: 0.13,

  taxable_income: 0,

  corporate_tax_rate: 0.25,

  total_payroll: 0,

  special_deductions: 0,

  is_small_enterprise: false,

  notes: '',

  data_source: 'manual'

})



const calculatedVAT = computed(() => {

  return Math.max(0, formData.output_tax - formData.input_tax)

})



const calculatedCorporateTax = computed(() => {

  return Math.max(0, formData.taxable_income * formData.corporate_tax_rate)

})



const taxBurdenRate = computed(() => {

  if (formData.total_revenue <= 0) return 0

  return ((calculatedVAT.value + calculatedCorporateTax.value) / formData.total_revenue * 100).toFixed(2)

})



const isSmallEnterpriseEligible = computed(() => {

  return formData.total_revenue <= 5000000 && formData.taxable_income <= 3000000

})



async function loadCurrentYearData() {

  isLoading.value = true

  try {

    const result = await financialDataApiClient.getByYear(formData.fiscal_year!, formData.period_type)

    if (result) {

      savedData.value = result

      Object.assign(formData, {

        fiscal_year: result.fiscal_year,

        period_type: result.period_type,

        period_start: result.period_start,

        period_end: result.period_end,

        total_revenue: result.total_revenue,

        taxable_sales: result.taxable_sales,

        tax_free_sales: result.tax_free_sales,

        total_expenses: result.total_expenses,

        deductible_expenses: result.deductible_expenses,

        input_tax: result.input_tax,

        output_tax: result.output_tax,

        vat_rate: result.vat_rate,

        taxable_income: result.taxable_income,

        corporate_tax_rate: result.corporate_tax_rate,

        total_payroll: result.total_payroll,

        special_deductions: result.special_deductions,

        is_small_enterprise: result.is_small_enterprise

      })

      

      if (result.period_type === 'quarterly') {

        const startDate = new Date(result.period_start)

        const month = startDate.getMonth() + 1

        selectedQuarter.value = Math.ceil(month / 3)

      } else if (result.period_type === 'monthly') {

        const startDate = new Date(result.period_start)

        selectedMonth.value = startDate.getMonth() + 1

      }

      

      ElMessage.success('已加载财务数据')
    }
  } catch (e: any) {
    if (e.response?.status === 404) {
      savedData.value = null
      calculatePeriodDates()
      ElMessage.info('该周期暂无财务数据，请填写')

    } else {

      console.error('Failed to load data:', e)

      ElMessage.error('加载数据失败')

    }

  } finally {

    isLoading.value = false

  }

}



async function saveFinancialData() {

  isSaving.value = true

  try {

    if (savedData.value) {

      await financialDataApiClient.update(savedData.value.id, formData)

      ElMessage.success('财务数据更新成功')

    } else {

      await financialDataApiClient.create(formData)

      ElMessage.success('财务数据保存成功')

    }

    isEditing.value = false

    await loadCurrentYearData()

  } catch (e: any) {

    console.error('Failed to save data:', e)

    const msg = e.response?.data?.detail || '保存失败'

    ElMessage.error(msg)

  } finally {

    isSaving.value = false

  }

}



function autoCalculate() {

  if (formData.taxable_sales && formData.vat_rate) {

    formData.output_tax = formData.taxable_sales * formData.vat_rate

  }

  if (formData.taxable_income <= 0 && formData.total_revenue > 0) {

    formData.taxable_income = Math.max(0, formData.total_revenue - formData.total_expenses)

  }

}



function toggleEdit() {

  isEditing.value = !isEditing.value

  if (!isEditing.value) {

    loadCurrentYearData()

  }

}



watch(() => formData.period_type, () => {

  calculatePeriodDates()

  loadCurrentYearData()

})



const showUploadDialog = ref(false)

const uploadFile = ref<File | null>(null)

const uploadProgress = ref(0)

const isUploading = ref(false)

const uploadErrors = ref<Array<{ row: number; field: string; message: string }>>([])

const overwriteExisting = ref(false)



function handleFileSelect(event: Event) {

  const target = event.target as HTMLInputElement

  const file = target.files?.[0]

  if (file) {

    const validTypes = ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel']

    if (!validTypes.includes(file.type) && !file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {

      ElMessage.error('请选择 Excel 文件(.xlsx 或 .xls)')

      return

    }

    uploadFile.value = file

    uploadErrors.value = []

  }

}



function removeSelectedFile() {

  uploadFile.value = null

  uploadErrors.value = []

}



async function handleUploadExcel() {

  if (!uploadFile.value) {

    ElMessage.warning('请选择要上传的 Excel 文件')

    return

  }



  isUploading.value = true

  uploadProgress.value = 0

  uploadErrors.value = []



  try {

    uploadProgress.value = 30

    

    const result = await financialDataApiClient.uploadExcelIntelligent(uploadFile.value, {

      overwriteExisting: overwriteExisting.value

    })

    

    uploadProgress.value = 100

    

    if (result.validation_errors && result.validation_errors.length > 0) {

      uploadErrors.value = result.validation_errors

      ElMessage.warning({

        message: `导入完成，但有${result.validation_errors.length} 条验证警告`,

        duration: 5000

      })

      

      if (result.records_created > 0 || result.records_updated > 0) {

        ElMessage.success({

          message: `成功导入 ${result.records_created} 条记录，更新 ${result.records_updated} 条记录`,

          duration: 3000

        })

        showUploadDialog.value = false

        uploadFile.value = null

        overwriteExisting.value = false

        await loadCurrentYearData()

      }

    } else if (result.success) {

      const detectedCount = Object.values(result.detected_columns || {}).filter(v => v !== null).length

      

      ElMessage.success({

        message: `成功导入 ${result.records_created} 条记录，更新 ${result.records_updated} 条记录，系统自动识别了${detectedCount}个财务字段`,

        duration: 4000

      })

      showUploadDialog.value = false

      uploadFile.value = null

      overwriteExisting.value = false

      await loadCurrentYearData()

    }

  } catch (error: any) {

    uploadProgress.value = 0

    const errorMessage = error.response?.data?.detail || error.response?.data?.message || '上传失败'

    

    if (typeof error.response?.data?.detail === 'object' && error.response?.data?.detail?.missing_columns) {

      uploadErrors.value = error.response?.data?.detail?.missing_columns?.map((col: string, idx: number) => ({

        row: 0,

        field: 'column',

        message: col

      })) || []

      

      ElMessage.error({

        message: '无法识别Excel中的必需列，请检查文件格式',

        duration: 5000

      })

    } else {

      uploadErrors.value = error.response?.data?.errors || []

      

      if (uploadErrors.value.length > 0) {

        ElMessage.warning({

          message: `上传完成，但有${uploadErrors.value.length} 条验证错误`,

          duration: 5000

        })

      } else {

        ElMessage.error(errorMessage)

      }

    }

  } finally {

    isUploading.value = false

  }

}



async function handleDownloadTemplate() {

  try {

    await financialDataApiClient.downloadTemplate()

  } catch (error: any) {

    console.error('Failed to download template:', error)

    ElMessage.error('模板下载失败')

  }

}



function openUploadDialog() {

  uploadFile.value = null

  uploadErrors.value = []

  overwriteExisting.value = false

  uploadProgress.value = 0

  showUploadDialog.value = true

}



onMounted(() => {

  calculatePeriodDates()

  loadCurrentYearData()

})



async function downloadTestData() {

  if (isDownloadingTest.value) return



  isDownloadingTest.value = true

  try {

    await financialDataApiClient.downloadTestTemplate('all')

    ElMessage.success({

      message: '测试数据下载成功，请解压缩后使用',

      duration: 3000

    })

  } catch (error: any) {

    console.error('下载测试数据失败:', error)

    ElMessage.error({

      message: '下载测试数据失败，请稍后重试',

      duration: 3000

    })

  } finally {

    isDownloadingTest.value = false

  }

}

</script>



<template>

  <div class="h-screen flex flex-col bg-gray-50 overflow-hidden">

    <div class="flex items-center justify-between mb-6 px-6 pt-6 pb-4 flex-shrink-0">

      <div class="flex items-center gap-3">

        <div class="p-2 bg-blue-100 rounded-lg">

          <PiggyBank class="text-blue-600" :size="24" />

        </div>

        <div>

          <h1 class="text-2xl font-bold text-gray-900">财务数据录入</h1>

          <p class="text-sm text-gray-500">录入企业财务信息，支持税务智能分析</p>

        </div>

      </div>

      <div class="flex gap-2">

        <button

          @click="$router.push('/financial-data-list')"

          class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 flex items-center gap-2"

        >

          <FileText :size="16" />

          查看数据列表

        </button>

        <button

          v-if="!savedData && !isEditing"

          @click="toggleEdit"

          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"

        >

          <Edit :size="16" />

          录入数据

        </button>

        <button

          v-else-if="savedData"

          @click="toggleEdit"

          class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 flex items-center gap-2"

        >

          <Edit :size="16" />

          {{ isEditing ? '取消编辑' : '编辑数据' }}

        </button>

        <button

          v-if="savedData"

          @click="loadCurrentYearData"

          class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 flex items-center gap-2"

        >

          <RefreshCw :size="16" />

          刷新

        </button>

        <button

          @click="handleDownloadTemplate"

          class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"

        >

          <Download :size="16" />

          下载模板

        </button>

        <button

          @click="openUploadDialog"

          class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center gap-2"

        >

          <Upload :size="16" />

          Excel导入

        </button>

      </div>

    </div>



    <div class="flex-1 min-h-0 overflow-y-auto px-6 pb-6">

      <div class="max-w-6xl mx-auto">

        <!-- 测试数据下载区域 -->

        <div class="mb-6 bg-gradient-to-r from-green-500 to-emerald-600 rounded-xl shadow-lg p-6 text-white">

          <div class="flex items-center justify-between gap-6">

            <div class="flex-1">

              <div class="flex items-center gap-3 mb-3">

                <div class="bg-white/20 backdrop-blur rounded-lg p-2">

                  <FileSpreadsheet :size="24" />

                </div>

                <div>

                  <h3 class="text-xl font-bold">下载测试数据</h3>

                  <p class="text-green-100 text-sm">包含1200条模拟财务数据，适用于智能上传接口</p>

                </div>

              </div>

              <div class="flex flex-wrap gap-3 mt-4">

                <div class="bg-white/10 backdrop-blur rounded-lg px-4 py-2 text-sm">

                  <div class="font-bold">A公司</div>

                  <div class="text-green-100">大型企业</div>

                </div>

                <div class="bg-white/10 backdrop-blur rounded-lg px-4 py-2 text-sm">

                  <div class="font-bold">B公司</div>

                  <div class="text-green-100">小微企业</div>

                </div>

                <div class="bg-white/10 backdrop-blur rounded-lg px-4 py-2 text-sm">

                  <div class="font-bold">C公司</div>

                  <div class="text-green-100">中型企业</div>

                </div>

              </div>

            </div>

            <div class="flex-shrink-0">

              <button

                @click="downloadTestData"

                :disabled="isDownloadingTest"

                class="bg-white text-green-600 px-6 py-3 rounded-xl font-bold text-lg

                       hover:bg-green-50 transition-all duration-200 shadow-lg

                       disabled:opacity-50 disabled:cursor-not-allowed

                       flex items-center gap-3 whitespace-nowrap"

              >

                <Download v-if="!isDownloadingTest" :size="20" />

                <Loader2 v-else class="animate-spin" :size="20" />

                {{ isDownloadingTest ? '下载中...' : '下载测试数据' }}

              </button>

            </div>

          </div>

        </div>



        <!-- Small Enterprise Alert -->

        <div v-if="isSmallEnterpriseEligible && !formData.is_small_enterprise" class="mb-4 bg-amber-50 border border-amber-200 rounded-lg p-4">

        <div class="flex items-start gap-3">

          <AlertCircle class="text-amber-500 flex-shrink-0 mt-0.5" :size="20" />

          <div>

            <h3 class="font-medium text-amber-800">小微企业优惠提醒</h3>

            <p class="text-sm text-amber-700 mt-1">

              您的企业符合小微企业条件（年销售额<100万，应纳税所得额<100万），可享受企业所得税优惠政策）            </p>

          </div>

        </div>

      </div>



      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

        <!-- Main Form -->

        <div class="lg:col-span-2 space-y-6">

          <!-- Basic Info Card -->

          <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">

            <h2 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">

              <FileText :size="20" class="text-blue-500" />

              基本信息

            </h2>

            <div class="grid grid-cols-2 gap-4">

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">财务年度</label>

                <select

                  v-model="formData.fiscal_year"

                  :disabled="!isEditing"

                  @change="calculatePeriodDates"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                >

                  <option v-for="year in fiscalYears" :key="year" :value="year">{{ year }}</option>

                </select>

              </div>

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">周期类型</label>

                <select

                  v-model="formData.period_type"

                  :disabled="!isEditing"

                  @change="calculatePeriodDates"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                >

                  <option v-for="pt in periodTypes" :key="pt.value" :value="pt.value">{{ pt.label }}</option>

                </select>

              </div>

              <div v-if="formData.period_type === 'quarterly'">

                <label class="block text-sm font-medium text-gray-700 mb-1">选择季度</label>

                <select

                  v-model="selectedQuarter"

                  :disabled="!isEditing"

                  @change="calculatePeriodDates"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                >

                  <option v-for="q in quarters" :key="q.value" :value="q.value">{{ q.label }}</option>

                </select>

              </div>

              <div v-if="formData.period_type === 'monthly'">

                <label class="block text-sm font-medium text-gray-700 mb-1">选择月份</label>

                <select

                  v-model="selectedMonth"

                  :disabled="!isEditing"

                  @change="calculatePeriodDates"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                >

                  <option v-for="m in months" :key="m.value" :value="m.value">{{ m.label }}</option>

                </select>

              </div>

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">周期开始日期</label>

                <input

                  v-model="formData.period_start"

                  :disabled="!isEditing"

                  type="date"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                />

              </div>

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">周期结束日期</label>

                <input

                  v-model="formData.period_end"

                  :disabled="!isEditing"

                  type="date"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                />

              </div>

              <div class="col-span-2">

                <label class="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1">

                  <input

                    v-model="formData.is_small_enterprise"

                    :disabled="!isEditing"

                    type="checkbox"

                    class="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"

                  />

                  小微企业

                </label>

                <p class="text-xs text-gray-500">（年销售额<100万，应纳税所得额<100万）</p>

              </div>

            </div>

          </div>



          <!-- Revenue Card -->

          <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">

            <h2 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">

              <TrendingUp :size="20" class="text-green-500" />

              收入数据

            </h2>

            <div class="grid grid-cols-2 gap-4">

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">总收入（元）</label>

                <input

                  v-model.number="formData.total_revenue"

                  :disabled="!isEditing"

                  type="number"

                  step="0.01"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                  placeholder="0.00"

                />

              </div>

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">应税销售额（元）</label>

                <input

                  v-model.number="formData.taxable_sales"

                  :disabled="!isEditing"

                  type="number"

                  step="0.01"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                  placeholder="0.00"

                />

              </div>

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">免税销售额（元）</label>

                <input

                  v-model.number="formData.tax_free_sales"

                  :disabled="!isEditing"

                  type="number"

                  step="0.01"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                  placeholder="0.00"

                />

              </div>

            </div>

          </div>



          <!-- Expenses Card -->

          <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">

            <h2 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">

              <TrendingDown :size="20" class="text-red-500" />

              支出数据

            </h2>

            <div class="grid grid-cols-2 gap-4">

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">总支出（元）</label>

                <input

                  v-model.number="formData.total_expenses"

                  :disabled="!isEditing"

                  type="number"

                  step="0.01"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                  placeholder="0.00"

                />

              </div>

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">可抵扣支出（元）</label>

                <input

                  v-model.number="formData.deductible_expenses"

                  :disabled="!isEditing"

                  type="number"

                  step="0.01"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                  placeholder="0.00"

                />

              </div>

            </div>

          </div>



          <!-- Tax Card -->

          <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">

            <h2 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">

              <Calculator :size="20" class="text-purple-500" />

              税务数据

            </h2>

            <div class="grid grid-cols-2 gap-4">

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">进项税额（元）</label>

                <input

                  v-model.number="formData.input_tax"

                  :disabled="!isEditing"

                  type="number"

                  step="0.01"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                  placeholder="0.00"

                />

              </div>

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">销项税额（元）</label>

                <input

                  v-model.number="formData.output_tax"

                  :disabled="!isEditing"

                  type="number"

                  step="0.01"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                  placeholder="0.00"

                />

              </div>

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">增值税</label>

                <select

                  v-model.number="formData.vat_rate"

                  :disabled="!isEditing"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                >

                  <option :value="0.13">13%</option>

                  <option :value="0.09">9%</option>

                  <option :value="0.06">6%</option>

                  <option :value="0.03">3%</option>

                </select>

              </div>

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">应纳税所得额（元）</label>

                <input

                  v-model.number="formData.taxable_income"

                  :disabled="!isEditing"

                  type="number"

                  step="0.01"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                  placeholder="0.00"

                />

              </div>

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">企业所得税</label>

                <select

                  v-model.number="formData.corporate_tax_rate"

                  :disabled="!isEditing"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                >

                  <option :value="0.25">25% (标准税率)</option>

                  <option v-if="formData.is_small_enterprise" :value="0.05">5% (小微企业优惠)</option>

                  <option v-if="formData.is_small_enterprise" :value="0.10">10% (小微企业优惠)</option>

                </select>

              </div>

              <div>

                <label class="block text-sm font-medium text-gray-700 mb-1">工资薪金总额（元）</label>

                <input

                  v-model.number="formData.total_payroll"

                  :disabled="!isEditing"

                  type="number"

                  step="0.01"

                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

                  placeholder="0.00"

                />

              </div>

            </div>

          </div>



          <!-- Notes -->

          <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">

            <h2 class="text-lg font-semibold text-gray-900 mb-4">备注信息</h2>

            <textarea

              v-model="formData.notes"

              :disabled="!isEditing"

              rows="3"

              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"

              placeholder="添加备注信息..."

            ></textarea>

          </div>



          <!-- Actions -->

          <div v-if="isEditing || !savedData" class="flex gap-3">

            <button

              @click="autoCalculate"

              class="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 flex items-center justify-center gap-2"

            >

              <Calculator :size="18" />

              自动计算

            </button>

            <button

              @click="saveFinancialData"

              :disabled="isSaving"

              class="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"

            >

              <Loader2 v-if="isSaving" class="animate-spin" :size="18" />

              <Save v-else :size="18" />

              {{ isSaving ? '保存中...' : (savedData ? '更新数据' : '录入数据') }}

            </button>

          </div>

        </div>



        <!-- Tax Summary Sidebar -->

        <div class="lg:col-span-1">

          <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 sticky top-6">

            <h2 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">

              <DollarSign :size="20" class="text-green-500" />

              税务预估

            </h2>



            <div class="space-y-4">

              <div class="p-4 bg-green-50 rounded-lg">

                <p class="text-sm text-green-600 mb-1">应缴增值税</p>

                <p class="text-2xl font-bold text-green-700">¥{{ calculatedVAT.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}</p>

                <p class="text-xs text-green-600 mt-1">

                  销项{{formData.output_tax?.toLocaleString() || 0 }} - 进项 {{ formData.input_tax?.toLocaleString() || 0 }}

                </p>

              </div>



              <div class="p-4 bg-blue-50 rounded-lg">

                <p class="text-sm text-blue-600 mb-1">应缴企业所得税</p>

                <p class="text-2xl font-bold text-blue-700">¥{{ calculatedCorporateTax.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}</p>

                <p class="text-xs text-blue-600 mt-1">

                  应税所得额 × {{ (formData.corporate_tax_rate * 100).toFixed(0) }}%

                </p>

              </div>



              <div class="p-4 bg-purple-50 rounded-lg">

                <p class="text-sm text-purple-600 mb-1">总税负率</p>

                <p class="text-2xl font-bold text-purple-700">{{ taxBurdenRate }}%</p>

                <p class="text-xs text-purple-600 mt-1">

                  税负占收入比

                </p>

              </div>

            </div>



            <div v-if="savedData" class="mt-6 pt-4 border-t border-gray-200">

              <div class="flex items-center gap-2 text-sm text-gray-500">

                <CheckCircle :size="16" class="text-green-500" />

                <span>数据已保存于 {{ new Date(savedData.created_at).toLocaleDateString() }}</span>

              </div>

            </div>

            </div>

          </div>

        </div>

      </div>

    </div>



    <el-dialog

      v-model="showUploadDialog"

      title="Excel导入财务数据"

      width="600px"

      :close-on-click-modal="false"

    >

      <div class="space-y-6">

        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">

          <div class="flex items-start gap-3">

            <FileSpreadsheet class="text-blue-500 flex-shrink-0 mt-0.5" :size="20" />

            <div>

              <h3 class="font-medium text-blue-800">智能导入说明</h3>

              <ul class="text-sm text-blue-700 mt-2 space-y-1">

                <li>• <strong>智能识别</strong>：系统自动识别Excel列名，无需严格按模板格式</li>

                <li>✓ 支持中文列名（如：总收入、应税销售额、税额等）</li>

                <li>✓ 支持英文列名（如：Revenue, Sales, Tax 等）</li>

                <li>✓ 支持各种变体和缩写（如：营业额、销售收入、Taxable Sales 等）</li>

                <li>✓ 支持 .xlsx 和 .xls 格式的Excel 文件</li>

                <li>✓ 文件大小建议不超过5MB</li>

                <li>✓ 每行数据将作为一条财务记录导入</li>

              </ul>

            </div>

          </div>

        </div>



        <div>

          <label class="block text-sm font-medium text-gray-700 mb-2">选择Excel文件</label>

          <div

            v-if="!uploadFile"

            class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-indigo-400 transition-colors cursor-pointer"

            @click="($refs.fileInput as HTMLInputElement)?.click()"

          >

            <input

              ref="fileInput"

              type="file"

              accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"

              class="hidden"

              @change="handleFileSelect"

            />

            <Upload class="mx-auto text-gray-400 mb-3" :size="48" />

            <p class="text-gray-600">点击选择文件或将文件拖拽到此区域</p>

            <p class="text-sm text-gray-400 mt-2">支持 .xlsx, .xls 格式</p>

          </div>



          <div

            v-else

            class="border border-gray-200 rounded-lg p-4 bg-gray-50"

          >

            <div class="flex items-center justify-between">

              <div class="flex items-center gap-3">

                <FileSpreadsheet class="text-green-500" :size="32" />

                <div>

                  <p class="font-medium text-gray-900">{{ uploadFile.name }}</p>

                  <p class="text-sm text-gray-500">{{ (uploadFile.size / 1024).toFixed(2) }} KB</p>

                </div>

              </div>

              <button

                @click="removeSelectedFile"

                class="p-2 text-gray-400 hover:text-red-500 transition-colors"

              >

                <X :size="20" />

              </button>

            </div>

          </div>

        </div>



        <div v-if="uploadErrors.length > 0" class="bg-red-50 border border-red-200 rounded-lg p-4">

          <div class="flex items-start gap-3">

            <AlertTriangle class="text-red-500 flex-shrink-0 mt-0.5" :size="20" />

            <div class="flex-1">

              <h3 class="font-medium text-red-800">导入错误（{{ uploadErrors.length }}条）</h3>

              <div class="mt-2 max-h-40 overflow-y-auto space-y-2">

                <div

                  v-for="(error, index) in uploadErrors.slice(0, 10)"

                  :key="index"

                  class="text-sm text-red-700"

                >

                  <span class="font-medium">第{{ error.row }}行，{{ error.field }}列：</span> {{ error.message }}

                </div>

                <p v-if="uploadErrors.length > 10" class="text-sm text-red-600">

                  还有 {{ uploadErrors.length - 10 }} 条错误未显示...

                </p>

              </div>

            </div>

          </div>

        </div>



        <div class="border border-gray-200 rounded-lg p-4">

          <label class="flex items-center gap-3 cursor-pointer">

            <input

              v-model="overwriteExisting"

              type="checkbox"

              class="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"

            />

            <div>

              <span class="text-sm font-medium text-gray-700">覆盖已存在的记录</span>

              <p class="text-xs text-gray-500">勾选后，将覆盖相同年度和周期的财务数据</p>

            </div>

          </label>

        </div>



        <div v-if="isUploading" class="space-y-2">

          <div class="flex items-center justify-between text-sm">

            <span class="text-gray-600">上传进度</span>

            <span class="text-indigo-600 font-medium">{{ uploadProgress }}%</span>

          </div>

          <div class="w-full bg-gray-200 rounded-full h-2">

            <div

              class="bg-indigo-600 h-2 rounded-full transition-all duration-300"

              :style="{ width: uploadProgress + '%' }"

            ></div>

          </div>

        </div>

      </div>



      <template #footer>

        <div class="flex gap-3 justify-end">

          <button

            @click="showUploadDialog = false"

            :disabled="isUploading"

            class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"

          >

            取消

          </button>

          <button

            @click="handleUploadExcel"

            :disabled="!uploadFile || isUploading"

            class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"

          >

            <Loader2 v-if="isUploading" class="animate-spin" :size="16" />

            <Upload v-else :size="16" />

            {{ isUploading ? '导入中...' : '开始导入' }}

          </button>

        </div>

      </template>

    </el-dialog>

  </div>

</template>

