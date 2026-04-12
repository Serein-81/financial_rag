<template>

  <div class="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-8">

    <div class="max-w-5xl mx-auto">

      <!-- 页面标题 -->

      <div class="text-center mb-12">

        <h1 class="text-4xl font-bold text-gray-900 mb-4">

          📊 企业财政数据测试指南

        </h1>

        <p class="text-lg text-gray-600">

          了解如何使用智能识别功能测试您的财务数据导入系统

        </p>

      </div>



      <!-- 功能介绍 -->

      <div class="bg-white rounded-2xl shadow-lg p-8 mb-8">

        <div class="flex items-start gap-4 mb-6">

          <div class="bg-blue-100 p-3 rounded-lg">

            <Sparkles class="text-blue-600" :size="32" />

          </div>

          <div>

            <h2 class="text-2xl font-bold text-gray-900 mb-2">智能识别系统</h2>

            <p class="text-gray-600">

              系统支持自动识别各种格式的Excel文件，无需严格按模板格式准备数据              无论您的Excel使用中文列名还是英文列名，系统都能智能匹配并提取财务数据            </p>

          </div>

        </div>



        <div class="grid md:grid-cols-3 gap-6">

          <div class="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-6">

            <div class="flex items-center gap-2 mb-3">

              <FileSpreadsheet class="text-blue-600" :size="24" />

              <h3 class="font-bold text-gray-900">中文格式</h3>

            </div>

            <p class="text-sm text-gray-600 mb-3">

              支持各种中文列名格式

            </p>

            <div class="bg-white rounded-lg p-3 space-y-1">

              <div class="text-xs text-gray-500">示例列名</div>

              <div class="text-xs font-mono bg-gray-100 p-2 rounded">

                总收入、应税销售额<br/>

                进项税额、销项税额              </div>

            </div>

          </div>



          <div class="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-6">

            <div class="flex items-center gap-2 mb-3">

              <FileSpreadsheet class="text-green-600" :size="24" />

              <h3 class="font-bold text-gray-900">英文格式</h3>

            </div>

            <p class="text-sm text-gray-600 mb-3">

              支持各种英文列名格式

            </p>

            <div class="bg-white rounded-lg p-3 space-y-1">

              <div class="text-xs text-gray-500">示例列名</div>

              <div class="text-xs font-mono bg-gray-100 p-2 rounded">

                Revenue, Sales, Tax,<br/>

                VAT In, VAT Out

              </div>

            </div>

          </div>



          <div class="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-6">

            <div class="flex items-center gap-2 mb-3">

              <FileSpreadsheet class="text-purple-600" :size="24" />

              <h3 class="font-bold text-gray-900">混合格式</h3>

            </div>

            <p class="text-sm text-gray-600 mb-3">

              支持中英文混合列名            </p>

            <div class="bg-white rounded-lg p-3 space-y-1">

              <div class="text-xs text-gray-500">示例列名</div>

              <div class="text-xs font-mono bg-gray-100 p-2 rounded">

                收入 Revenue, 销售额<br/>

                Sales Amount

              </div>

            </div>

          </div>

        </div>

      </div>



      <!-- 测试数据下载 -->

      <div class="bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl shadow-lg p-8 text-white mb-8">

        <div class="flex items-start justify-between gap-6">

          <div class="flex-1">

            <div class="flex items-center gap-3 mb-4">

              <Download class="text-white" :size="32" />

              <h2 class="text-2xl font-bold">下载测试数据</h2>

            </div>

            <p class="text-lg mb-6 text-green-100">

              包含3家企业的2022-2024年度财务数据，共9条记录br/>

              涵盖收入、支出、税费、工资等完整财务指标

            </p>

            <div class="grid md:grid-cols-3 gap-4">

              <div class="bg-white/20 backdrop-blur rounded-lg p-4">

                <div class="font-bold mb-2">A公司</div>

                <div class="text-sm text-green-100">

                  大型企业<br/>

                  年收入约500万br/>

                  2022-2024数据

                </div>

              </div>

              <div class="bg-white/20 backdrop-blur rounded-lg p-4">

                <div class="font-bold mb-2">B公司</div>

                <div class="text-sm text-green-100">

                  小微企业<br/>

                  年收入约80万br/>

                  2022-2024数据

                </div>

              </div>

              <div class="bg-white/20 backdrop-blur rounded-lg p-4">

                <div class="font-bold mb-2">C公司</div>

                <div class="text-sm text-green-100">

                  中型企业<br/>

                  年收入约280万br/>

                  2022-2024数据

                </div>

              </div>

            </div>

          </div>

          <div class="flex-shrink-0">

            <button

              @click="downloadTestData"

              :disabled="isDownloading"

              class="bg-white text-green-600 px-8 py-4 rounded-xl font-bold text-lg

                     hover:bg-green-50 transition-all duration-200 shadow-lg

                     disabled:opacity-50 disabled:cursor-not-allowed

                     flex items-center gap-3"

            >

              <Download v-if="!isDownloading" :size="24" />

              <Loader v-else class="animate-spin" :size="24" />

              {{ isDownloading ? '下载中...' : '下载测试数据' }}

            </button>

          </div>

        </div>

      </div>



      <!-- 数据结构说明 -->

      <div class="bg-white rounded-2xl shadow-lg p-8 mb-8">

        <div class="flex items-center gap-3 mb-6">

          <Database class="text-indigo-600" :size="28" />

          <h2 class="text-2xl font-bold text-gray-900">数据结构说明</h2>

        </div>



        <div class="grid md:grid-cols-2 gap-6">

          <!-- 必需字段 -->

          <div class="bg-blue-50 rounded-xl p-6">

            <div class="flex items-center gap-2 mb-4">

              <div class="bg-blue-600 text-white text-xs px-2 py-1 rounded-full font-bold">

                必需

              </div>

              <h3 class="font-bold text-gray-900">必需字段</h3>

            </div>

            <div class="space-y-2 text-sm">

              <div class="flex items-start gap-2">

                <CheckCircle class="text-blue-600 flex-shrink-0 mt-0.5" :size="16" />

                <div>

                  <span class="font-medium">财务年度</span>

                  <span class="text-gray-500 ml-2">（如2024）</span>

                </div>

              </div>

              <div class="flex items-start gap-2">

                <CheckCircle class="text-blue-600 flex-shrink-0 mt-0.5" :size="16" />

                <div>

                  <span class="font-medium">总收入</span>

                  <span class="text-gray-500 ml-2">（单位：元）</span>

                </div>

              </div>

              <div class="flex items-start gap-2">

                <CheckCircle class="text-blue-600 flex-shrink-0 mt-0.5" :size="16" />

                <div>

                  <span class="font-medium">应税销售额</span>

                  <span class="text-gray-500 ml-2">（含税销售额）</span>

                </div>

              </div>

            </div>

          </div>



          <!-- 可选字段-->

          <div class="bg-gray-50 rounded-xl p-6">

            <div class="flex items-center gap-2 mb-4">

              <div class="bg-gray-600 text-white text-xs px-2 py-1 rounded-full font-bold">

                可填              </div>

              <h3 class="font-bold text-gray-900">可选字段</h3>

            </div>

            <div class="space-y-2 text-sm text-gray-600">

              <div>• 免税销售额</div>

              <div>• 总支出、可抵扣/不可抵扣支出</div>
              <div>• 进项税额、销项税额</div>
              <div>• 增值税率、企业所得税率</div>
              <div>• 工资薪金、专项附加扣除</div>

              <div>• 发票数量统计</div>

            </div>

          </div>

        </div>



        <!-- 字段映射说明-->

        <div class="mt-6">

          <h4 class="font-bold text-gray-900 mb-4">智能识别支持（部分示例）</h4>

          <div class="overflow-x-auto">

            <table class="w-full text-sm">

              <thead>

                <tr class="bg-gray-100">

                  <th class="px-4 py-2 text-left font-bold text-gray-700">系统字段</th>

                  <th class="px-4 py-2 text-left font-bold text-gray-700">支持的中文列名</th>
                  <th class="px-4 py-2 text-left font-bold text-gray-700">支持的英文列名</th>

                </tr>

              </thead>

              <tbody class="divide-y divide-gray-200">

                <tr v-for="field in fieldMappings" :key="field.name">

                  <td class="px-4 py-2 font-medium text-gray-900">{{ field.name }}</td>

                  <td class="px-4 py-2 text-gray-600">{{ field.chinese }}</td>

                  <td class="px-4 py-2 text-gray-600">{{ field.english }}</td>

                </tr>

              </tbody>

            </table>

          </div>

        </div>

      </div>



      <!-- 使用流程 -->

      <div class="bg-white rounded-2xl shadow-lg p-8 mb-8">

        <div class="flex items-center gap-3 mb-6">

          <Route class="text-orange-600" :size="28" />

          <h2 class="text-2xl font-bold text-gray-900">测试流程</h2>

        </div>



        <div class="relative">

          <div class="absolute left-8 top-0 bottom-0 w-0.5 bg-blue-200"></div>

          <div class="space-y-8">

            <div v-for="(step, index) in testSteps" :key="index" class="relative flex items-start gap-6">

              <div class="flex-shrink-0 w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center

                          text-white font-bold text-xl z-10 shadow-lg">

                {{ index + 1 }}

              </div>

              <div class="flex-1 bg-gray-50 rounded-xl p-6">

                <h3 class="font-bold text-gray-900 mb-2">{{ step.title }}</h3>

                <p class="text-gray-600 mb-3">{{ step.description }}</p>

                <div v-if="step.action" class="bg-white rounded-lg p-3 border border-gray-200">

                  <code class="text-sm text-blue-600">{{ step.action }}</code>

                </div>

              </div>

            </div>

          </div>

        </div>

      </div>



      <!-- 注意事项 -->

      <div class="bg-yellow-50 border border-yellow-200 rounded-2xl p-8">

        <div class="flex items-start gap-3">

          <AlertTriangle class="text-yellow-600 flex-shrink-0 mt-0.5" :size="24" />

          <div>

            <h3 class="font-bold text-gray-900 mb-4">重要注意事项</h3>

            <ul class="space-y-3 text-sm text-gray-700">

              <li class="flex items-start gap-2">

<span class="text-yellow-600">⚠</span>
                <span><strong>年份格式</strong>：请填写4位数字年份（如2024），不支持2024年、FY2024等格式</span>

              </li>

              <li class="flex items-start gap-2">

                <span class="text-yellow-600">⚠</span>
                <span><strong>金额格式</strong>：建议填写纯数字，可使用千分位格式（如1,000,000），会自动处理</span>

              </li>

              <li class="flex items-start gap-2">

                <span class="text-yellow-600">⚠</span>
                <span><strong>税率格式</strong>：建议填写小数形式（如0.13表示13%），部分情况也支持百分比形式</span>

              </li>

              <li class="flex items-start gap-2">

                <span class="text-yellow-600">⚠</span>
                <span><strong>文件大小</strong>：建议单个文件不超过5MB，超过可能需要分批处理</span>

              </li>

              <li class="flex items-start gap-2">

                <span class="text-yellow-600">⚠</span>
                <span><strong>数据验证</strong>：上传后会进行数据验证，错误数据会高亮显示并提示修正</span>

              </li>

              <li class="flex items-start gap-2">

                <span class="text-yellow-600">⚠</span>
                <span><strong>重复数据</strong>：相同年份和周期的数据会被标记为重复，可选择覆盖或跳过</span>

              </li>

            </ul>

          </div>

        </div>

      </div>



      <!-- 快速跳转-->

      <div class="mt-8 text-center">

        <button

          @click="goToFinancialDataEntry"

          class="bg-indigo-600 text-white px-8 py-4 rounded-xl font-bold text-lg

                 hover:bg-indigo-700 transition-all duration-200 shadow-lg

                 inline-flex items-center gap-3"

        >

          <FileSpreadsheet :size="24" />

          前往财务数据录入

        </button>

      </div>

    </div>

  </div>

</template>



<script setup lang="ts">

import { ref } from 'vue'

import { useRouter } from 'vue-router'

import { ElMessage } from 'element-plus'

import {

  Sparkles,

  FileSpreadsheet,

  Download,

  Database,

  CheckCircle,

  Route,

  AlertTriangle,

  Loader

} from 'lucide-vue-next'

import { financialDataApiClient } from '@/api/financial-data'



const router = useRouter()

const isDownloading = ref(false)



const fieldMappings = [

  {

    name: '总收入',
    chinese: '总收入、营业收入、营业额、销售收入',
    english: 'Revenue, Total Revenue, Sales'

  },

  {

    name: '应税销售额',

    chinese: '应税销售额、含税销售额、Sales',

    english: 'Taxable Sales, Taxable Revenue'

  },

  {

    name: '进项税额',

    chinese: '进项税额、收票税额、增值税进项',

    english: 'Input Tax, VAT In, Purchase Tax'

  },

  {

    name: '销项税额',
    chinese: '销项税额、开票税额、增值税销项',
    english: 'Output Tax, VAT Out, Sales Tax'

  },

  {

    name: '可抵扣支出',
    chinese: '可抵扣支出 deductible Expenses',

    english: 'Deductible Expenses, Deductible Cost'

  }

]



const testSteps = [

  {

    title: '下载测试数据',

    description: '点击上方"下载测试数据"按钮，获取包含企业财政模拟数据的Excel模板',

    action: '点击 "下载测试数据" 按钮'

  },

  {

    title: '打开Excel文件',

    description: '使用Excel或其他表格软件打开下载的文件，查看示例数据格式',

    action: '打开 "企业财政模拟数据.xlsx"'

  },

  {

    title: '修改或直接使用',
    description: '可以修改示例数据为您自己的财务数据，也可以直接上传测试识别功能',
    action: '修改数据或保持原样'
  },

  {

    title: '上传文件',

    description: '在财务数据录入页面，点击"导入Excel"按钮，上传测试文件',
    action: '前往 "财务数据录入" 页面'

  },

  {

    title: '查看识别结果',

    description: '系统会自动识别列名并显示识别结果，查看是否所有字段都正确识别',

    action: '查看 "识别结果" 区域'

  },

  {

    title: '确认导入',

    description: '确认数据无误后，点击"确认导入"按钮，将数据批量导入系统',

    action: '点击 "确认导入"'

  }

]



async function downloadTestData() {

  if (isDownloading.value) return



  isDownloading.value = true

  try {

    await financialDataApiClient.downloadTestTemplate('all')

  } catch (error) {

    console.error('下载失败:', error)

    ElMessage.error('下载失败，请稍后重试')

  } finally {

    isDownloading.value = false

  }

}



function goToFinancialDataEntry() {

  router.push('/financial-data-entry')

}

</script>



<style scoped>

.animate-spin {

  animation: spin 1s linear infinite;

}



@keyframes spin {

  from {

    transform: rotate(0deg);

  }

  to {

    transform: rotate(360deg);

  }

}

</style>

