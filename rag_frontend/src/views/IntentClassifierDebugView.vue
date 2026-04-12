<script setup lang="ts">

import { ref, computed } from 'vue'

import { multiAgentApi, type IntentClassificationResult, IntentClassificationStage } from '@/api/multi-agent'

import {

  Brain,

  Search,

  Zap,

  CheckCircle2,

  XCircle,

  Loader2,

  Plus,

  Trash2,

  Play,

  ChevronDown,

  ChevronRight,

  AlertTriangle,

  Sparkles,

  FileJson,

  RotateCcw,

  Copy,

  Check,

} from 'lucide-vue-next'



const isLoading = ref(false)

const testMessages = ref<string[]>([''])

const results = ref<IntentClassificationResult[]>([])

const selectedResult = ref<IntentClassificationResult | null>(null)

const copiedIndex = ref<number | null>(null)



const stageColors = {

  [IntentClassificationStage.KEYWORD]: { bg: 'bg-gray-100', text: 'text-gray-700', icon: Search, label: '关键词' },

  [IntentClassificationStage.EMBEDDING]: { bg: 'bg-emerald-100', text: 'text-emerald-700', icon: Zap, label: 'Embedding' },

  [IntentClassificationStage.SLM]: { bg: 'bg-purple-100', text: 'text-purple-700', icon: Brain, label: 'SLM' },

}



const sampleMessages = [

  { text: '报销机票1000元', category: '财务', icon: '💰' },

  { text: '查一下深圳明天天气', category: '查询', icon: '🌤' },

  { text: '张三说李四要报销', category: '财务', icon: '💰' },

  { text: '帮我查一下上个月的报销记录', category: '财务', icon: '📊' },

  { text: '导出财务报表', category: '高风险', icon: '⚠️' },

  { text: '今天吃什么', category: '闲聊', icon: '💬' },

]



const stats = computed(() => {

  if (results.value.length === 0) return null

  

  const total = results.value.length

  const expenseRelated = results.value.filter(r => r.is_expense_related).length

  const shouldProcess = results.value.filter(r => r.should_process).length

  const avgConfidence = results.value.reduce((sum, r) => sum + r.confidence, 0) / total

  const highRisk = results.value.filter(r => r.reasoning?.includes('高风险')).length

  

  return { total, expenseRelated, shouldProcess, avgConfidence, highRisk }

})



function addMessage() {

  testMessages.value.push('')

}



function removeMessage(index: number) {

  if (testMessages.value.length > 1) {

    testMessages.value.splice(index, 1)

  }

}



function useSample(index: number) {

  testMessages.value.push(sampleMessages[index].text)

}



function resetMessages() {

  testMessages.value = ['']

  results.value = []

  selectedResult.value = null

}



async function runTest() {

  const messages = testMessages.value.filter(m => m.trim())

  if (messages.length === 0) return



  isLoading.value = true

  results.value = []

  selectedResult.value = null



  try {

    results.value = await multiAgentApi.testIntentClassification(messages)

    if (results.value.length > 0) {

      selectedResult.value = results.value[0]

    }

  } catch (error) {

    console.error('意图分类测试失败:', error)

  } finally {

    isLoading.value = false

  }

}



async function classifySingle() {

  const message = testMessages.value[0].trim()

  if (!message) return



  isLoading.value = true

  try {

    const result = await multiAgentApi.classifyIntent(message)

    results.value = [result]

    selectedResult.value = result

  } catch (error) {

    console.error('单条意图分类失败:', error)

  } finally {

    isLoading.value = false

  }

}



function toggleResult(result: IntentClassificationResult) {

  selectedResult.value = selectedResult.value === result ? null : result

}



function getConfidenceColor(confidence: number): string {

  if (confidence >= 0.8) return 'text-green-600'

  if (confidence >= 0.6) return 'text-yellow-600'

  return 'text-red-600'

}



function getConfidenceBg(confidence: number): string {

  if (confidence >= 0.8) return 'bg-green-100'

  if (confidence >= 0.6) return 'bg-yellow-100'

  return 'bg-red-100'

}



function getConfidenceBarColor(confidence: number): string {

  if (confidence >= 0.8) return 'bg-green-500'

  if (confidence >= 0.6) return 'bg-yellow-500'

  return 'bg-red-500'

}



async function copyJson(index: number) {

  const result = results.value[index]

  if (result) {

    await navigator.clipboard.writeText(JSON.stringify(result, null, 2))

    copiedIndex.value = index

    setTimeout(() => {

      copiedIndex.value = null

    }, 2000)

  }

}

</script>



<template>

  <div class="h-screen overflow-auto bg-gradient-to-br from-gray-50 to-gray-100 p-6">

    <div class="max-w-6xl mx-auto space-y-6 pb-6">

      <div class="flex items-center justify-between">

        <div>

          <h1 class="text-2xl font-bold text-gray-900">意图分类器调试</h1>

          <p class="text-sm text-gray-500 mt-1">测试混合意图分类器的两阶段分类效果</p>

        </div>

        <button

          @click="resetMessages"

          class="flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-white hover:shadow-md rounded-lg transition-all"

        >

          <RotateCcw :size="18" />

          重置

        </button>

      </div>



      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">

        <div class="flex items-center justify-between mb-4">

          <h3 class="text-lg font-semibold flex items-center gap-2">

            <Sparkles class="text-emerald-500" :size="20" />

            测试输入

          </h3>

          <span class="text-sm text-gray-500">{{ testMessages.filter(m => m.trim()).length }} 条有效消息</span>

        </div>



        <div class="max-h-48 overflow-y-auto border border-gray-200 rounded-lg p-3 space-y-2 mb-4">

          <div

            v-for="(message, index) in testMessages"

            :key="index"

            class="flex items-center gap-3"

          >

            <span class="text-sm text-gray-400 w-6 text-right flex-shrink-0">{{ index + 1 }}.</span>

            <input

              v-model="testMessages[index]"

              type="text"

              class="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"

              placeholder="输入测试消息..."

              @keyup.enter="runTest"

            />

            <button

              v-if="testMessages.length > 1"

              @click="removeMessage(index)"

              class="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"

            >

              <Trash2 :size="16" />

            </button>

          </div>

        </div>



        <div class="flex items-center justify-between flex-wrap gap-3">

          <div class="flex items-center gap-2 flex-wrap">

            <button

              @click="addMessage"

              class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"

            >

              <Plus :size="16" />

              添加消息

            </button>

            <div class="relative group">

              <button class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors">

                <Sparkles :size="16" />

                示例

                <ChevronDown :size="14" />

              </button>

              <div class="absolute left-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg py-2 w-72 z-20 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all">

                <div class="px-3 py-1.5 text-xs text-gray-500 border-b border-gray-100">点击添加示例消息</div>

                <button

                  v-for="(sample, index) in sampleMessages"

                  :key="index"

                  @click="useSample(index)"

                  class="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex items-center gap-2"

                >

                  <span>{{ sample.icon }}</span>

                  <span class="flex-1 truncate">{{ sample.text }}</span>

                  <span class="text-xs text-gray-400">{{ sample.category }}</span>

                </button>

              </div>

            </div>

          </div>



          <div class="flex items-center gap-2">

            <button

              @click="classifySingle"

              :disabled="isLoading || !testMessages[0].trim()"

              class="flex items-center gap-2 px-4 py-2 text-sm text-emerald-600 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors disabled:opacity-50"

            >

              <Brain :size="16" />

              单条分类

            </button>

            <button

              @click="runTest"

              :disabled="isLoading || testMessages.every(m => !m.trim())"

              class="flex items-center gap-2 px-5 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50 shadow-sm"

            >

              <Loader2 v-if="isLoading" :size="18" class="animate-spin" />

              <Play v-else :size="18" />

              批量测试

            </button>

          </div>

        </div>

      </div>



      <div v-if="stats" class="grid grid-cols-5 gap-4">

        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4">

          <div class="text-2xl font-bold text-gray-900">{{ stats.total }}</div>

          <div class="text-sm text-gray-500">测试总数</div>

        </div>

        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4">

          <div class="text-2xl font-bold text-emerald-600">{{ (stats.avgConfidence * 100).toFixed(0) }}%</div>

          <div class="text-sm text-gray-500">平均置信度</div>

        </div>

        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4">

          <div class="text-2xl font-bold text-orange-600">{{ stats.expenseRelated }}</div>

          <div class="text-sm text-gray-500">费用相关</div>

        </div>

        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4">

          <div class="text-2xl font-bold text-blue-600">{{ stats.shouldProcess }}</div>

          <div class="text-sm text-gray-500">应处理</div>

        </div>

        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4">

          <div class="text-2xl font-bold text-red-600">{{ stats.highRisk }}</div>

          <div class="text-sm text-gray-500">高风险</div>

        </div>

      </div>



      <div v-if="results.length > 0" class="grid grid-cols-12 gap-6">

        <div class="col-span-12 lg:col-span-5 space-y-3">

          <div class="flex items-center justify-between">

            <h3 class="text-lg font-semibold">分类结果</h3>

            <span class="text-sm text-gray-500">{{ results.length }} 条</span>

          </div>

          

          <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden max-h-[600px] overflow-y-auto">

            <div

              v-for="(result, index) in results"

              :key="index"

              class="border-b border-gray-100 last:border-b-0"

            >

              <div

                @click="toggleResult(result)"

                class="p-4 cursor-pointer hover:bg-gray-50 transition-colors"

              >

                <div class="flex items-start justify-between">

                  <div class="flex-1 min-w-0">

                    <div class="text-sm font-medium text-gray-900 truncate mb-1.5">

                      {{ testMessages[index] || `消息 ${index + 1}` }}

                    </div>

                    <div class="flex flex-wrap items-center gap-1.5">

                      <span :class="['px-2 py-0.5 rounded text-xs font-medium flex items-center gap-1', stageColors[result.stage]?.bg, stageColors[result.stage]?.text]">

                        <component :is="stageColors[result.stage]?.icon" :size="12" />

                        {{ stageColors[result.stage]?.label }}

                      </span>

                      <span class="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">

                        {{ result.intent || 'general' }}

                      </span>

                      <span

                        v-if="result.is_expense_related"

                        class="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs font-medium flex items-center gap-0.5"

                      >

                        💰 费用相关

                      </span>

                    </div>

                  </div>

                  <div class="flex items-center gap-2 ml-2">

                    <div class="text-right">

                      <div :class="['text-sm font-bold', getConfidenceColor(result.confidence)]">

                        {{ (result.confidence * 100).toFixed(0) }}%

                      </div>

                      <div class="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">

                        <div

                          :class="['h-full rounded-full transition-all', getConfidenceBarColor(result.confidence)]"

                          :style="{ width: `${result.confidence * 100}%` }"

                        />

                      </div>

                    </div>

                    <component

                      :is="selectedResult === result ? ChevronDown : ChevronRight"

                      :size="18"

                      class="text-gray-400"

                    />

                  </div>

                </div>

              </div>

            </div>

          </div>

        </div>



        <div class="col-span-12 lg:col-span-7">

          <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">

            <div class="p-4 border-b border-gray-200 flex items-center justify-between">

              <h3 class="text-lg font-semibold">详细信息</h3>

              <button

                v-if="selectedResult"

                @click="copyJson(results.indexOf(selectedResult))"

                class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"

              >

                <Check v-if="copiedIndex !== null" :size="16" class="text-green-500" />

                <Copy v-else :size="16" />

                {{ copiedIndex !== null ? '已复制' : '复制JSON' }}

              </button>

            </div>



            <div v-if="selectedResult" class="max-h-[600px] overflow-y-auto">

              <div class="p-6 space-y-6">

                <div class="grid grid-cols-2 gap-4">

                  <div class="bg-gray-50 rounded-lg p-4">

                    <div class="text-sm text-gray-500 mb-1">分类阶段</div>

                    <div class="flex items-center gap-2">

                      <component :is="stageColors[selectedResult.stage]?.icon" :size="18" :class="stageColors[selectedResult.stage]?.text" />

                      <span class="font-semibold">{{ stageColors[selectedResult.stage]?.label }}</span>

                    </div>

                  </div>

                  <div class="bg-gray-50 rounded-lg p-4">

                    <div class="text-sm text-gray-500 mb-1">置信度</div>

                    <div class="flex items-center gap-2">

                      <span :class="['text-2xl font-bold', getConfidenceColor(selectedResult.confidence)]">

                        {{ (selectedResult.confidence * 100).toFixed(1) }}%

                      </span>

                    </div>

                    <div class="w-full h-2 bg-gray-200 rounded-full mt-2 overflow-hidden">

                      <div

                        :class="['h-full rounded-full', getConfidenceBarColor(selectedResult.confidence)]"

                        :style="{ width: `${selectedResult.confidence * 100}%` }"

                      />

                    </div>

                  </div>

                </div>



                <div class="grid grid-cols-2 gap-4">

                  <div class="bg-gray-50 rounded-lg p-4">

                    <div class="text-sm text-gray-500 mb-1">识别的意图</div>

                    <div class="font-semibold text-gray-900">{{ selectedResult.intent || 'general' }}</div>

                  </div>

                  <div class="bg-gray-50 rounded-lg p-4">

                    <div class="text-sm text-gray-500 mb-1">处理状态</div>

                    <div class="flex items-center gap-2">

                      <CheckCircle2 v-if="selectedResult.should_process" :size="18" class="text-green-500" />

                      <XCircle v-else :size="18" class="text-gray-400" />

                      <span :class="selectedResult.should_process ? 'text-green-600' : 'text-gray-500'">

                        {{ selectedResult.should_process ? '应处理' : '静默' }}

                      </span>

                    </div>

                  </div>

                </div>



                <div v-if="selectedResult.matched_keywords?.length" class="bg-gray-50 rounded-lg p-4">

                  <div class="text-sm text-gray-500 mb-2">匹配的关键词</div>

                  <div class="flex flex-wrap gap-2">

                    <span

                      v-for="keyword in selectedResult.matched_keywords"

                      :key="keyword"

                      class="px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-sm font-medium"

                    >

                      {{ keyword }}

                    </span>

                  </div>

                </div>



                <div v-if="selectedResult.embedding_score !== undefined && selectedResult.embedding_score !== null" class="bg-gray-50 rounded-lg p-4">

                  <div class="text-sm text-gray-500 mb-1">Embedding 相似度</div>

                  <div class="flex items-center gap-3">

                    <span :class="['text-xl font-bold', getConfidenceColor(selectedResult.embedding_score)]">

                      {{ (selectedResult.embedding_score * 100).toFixed(1) }}%

                    </span>

                    <div class="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">

                      <div

                        :class="['h-full rounded-full', getConfidenceBarColor(selectedResult.embedding_score)]"

                        :style="{ width: `${selectedResult.embedding_score * 100}%` }"

                      />

                    </div>

                  </div>

                </div>



                <div v-if="selectedResult.reasoning" class="bg-emerald-50 rounded-lg p-4 border border-emerald-100">

                  <div class="text-sm text-emerald-600 mb-1">推理过程</div>

                  <div class="text-gray-700">{{ selectedResult.reasoning }}</div>

                </div>



                <div v-if="selectedResult.is_expense_related" class="flex items-start gap-2 p-4 bg-orange-50 rounded-lg border border-orange-100">

                  <AlertTriangle class="text-orange-500 flex-shrink-0 mt-0.5" :size="18" />

                  <div>

                    <div class="font-medium text-orange-700">费用相关检查</div>

                    <div class="text-sm text-orange-600 mt-0.5">此消息被识别为与费用/报销相关，可能需要特殊处理流程</div>

                  </div>

                </div>



                <div class="bg-gray-900 rounded-lg p-4">

                  <div class="flex items-center justify-between mb-3">

                    <div class="flex items-center gap-2 text-gray-400">

                      <FileJson :size="16" />

                      <span class="text-sm font-medium">完整JSON</span>

                    </div>

                  </div>

                  <pre class="text-xs text-green-400 overflow-x-auto max-h-64 overflow-y-auto">{{ JSON.stringify(selectedResult, null, 2) }}</pre>

                </div>

              </div>

            </div>



            <div v-else class="p-12 text-center text-gray-400">

              <Brain :size="48" class="mx-auto mb-3 opacity-50" />

              <p>选择左侧结果查看详情</p>

            </div>

          </div>

        </div>

      </div>



      <div v-else class="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">

        <Brain :size="48" class="mx-auto text-gray-300 mb-4" />

        <h3 class="text-lg font-medium text-gray-900">暂无测试结果</h3>

        <p class="text-gray-500 mt-1">输入测试消息并点击批量测试"按钮</p>

      </div>



      <div class="bg-gradient-to-r from-emerald-500 to-teal-500 rounded-xl p-6 text-white shadow-lg">

        <h3 class="text-lg font-semibold mb-4 flex items-center gap-2">

          <Brain :size="20" />

          两阶段意图分类说明        </h3>

        <div class="grid md:grid-cols-2 gap-6">

          <div class="bg-white/10 rounded-lg p-4 backdrop-blur-sm">

            <div class="flex items-center gap-2 mb-2">

              <div class="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-sm font-bold">1</div>

              <span class="font-semibold">阶段一：关键词快速过滤</span>

            </div>

            <ul class="text-sm text-white/90 space-y-1 ml-10">

              <li>• 使用预定义关键词匹配</li>

              <li>• 支持税务、法律、财务、审计、费用等类别</li>

              <li>• 延迟低，适用于快速筛选</li>

              <li>• 置信度= 匹配度× 0.3 + 0.4</li>

            </ul>

          </div>

          <div class="bg-white/10 rounded-lg p-4 backdrop-blur-sm">

            <div class="flex items-center gap-2 mb-2">

              <div class="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-sm font-bold">2</div>

              <span class="font-semibold">阶段二：精确分类</span>

            </div>

            <ul class="text-sm text-white/90 space-y-1 ml-10">

              <li>• 当关键词无法确定时触发</li>

              <li>• 使用向量相似度或小型语言模型</li>

              <li>• 准确率高，延迟较高</li>

              <li>• 返回详细的推理过程</li>

            </ul>

          </div>

        </div>

        <div class="mt-4 p-3 bg-white/10 rounded-lg backdrop-blur-sm">

          <div class="text-sm font-medium mb-2">意图关键词库</div>

          <div class="flex flex-wrap gap-2">

            <span class="px-2 py-0.5 bg-white/20 rounded text-xs">税务: 税务/税收/纳税/报税</span>

            <span class="px-2 py-0.5 bg-white/20 rounded text-xs">法律: 法律/合同/法规/条款</span>

            <span class="px-2 py-0.5 bg-white/20 rounded text-xs">财务: 财务/会计/报表/资产</span>

            <span class="px-2 py-0.5 bg-white/20 rounded text-xs">审计: 审计/检查/核查/盘点</span>

            <span class="px-2 py-0.5 bg-white/20 rounded text-xs">费用: 报销/费用/支出/差旅</span>

          </div>

        </div>

        <div class="mt-3 p-3 bg-orange-500/30 rounded-lg border border-orange-400/30">

          <div class="flex items-center gap-2 text-orange-100 mb-2">

            <AlertTriangle :size="16" />

            <span class="text-sm font-medium">高风险关键词（需审批）</span>

          </div>

          <div class="flex flex-wrap gap-2">

            <span class="px-2 py-0.5 bg-orange-500/50 rounded text-xs">删除</span>

            <span class="px-2 py-0.5 bg-orange-500/50 rounded text-xs">批量</span>

            <span class="px-2 py-0.5 bg-orange-500/50 rounded text-xs">导出</span>

            <span class="px-2 py-0.5 bg-orange-500/50 rounded text-xs">全部</span>

            <span class="px-2 py-0.5 bg-orange-500/50 rounded text-xs">税务申报</span>

            <span class="px-2 py-0.5 bg-orange-500/50 rounded text-xs">合同生成</span>

            <span class="px-2 py-0.5 bg-orange-500/50 rounded text-xs">审计请求</span>

            <span class="px-2 py-0.5 bg-orange-500/50 rounded text-xs">外部共享</span>

          </div>

        </div>

      </div>

    </div>

  </div>

</template>

