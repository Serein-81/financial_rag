<script setup lang="ts">
import { ref, computed } from 'vue'
import { ChevronDown, ChevronUp, Activity, Search, Brain, CheckCircle2 } from 'lucide-vue-next'

/**
 * Agentic RAG 多轮检索步骤可视化
 * 后端 chat 接口在 message meta 中携带 retrieval_history 数组时展示
 * 数据结构对应 backend/agentic_rag_state.py 的 RetrievalStep
 */

export interface RetrievalStep {
  step_number: number
  action: string  // vector_search | hybrid_search | multi_step_search | plan | evaluate | aggregate
  query?: string
  parameters?: Record<string, any>
  results?: any[]
  result_count?: number
  timestamp?: string
  duration_ms?: number
  // plan / evaluate 节点的扩展字段（如果后端透传）
  reasoning?: string
  decision?: string
}

export interface Evaluation {
  is_sufficient?: boolean
  coverage_score?: number
  relevance_score?: number
  completeness_score?: number
  overall_score?: number
  missing_aspects?: string[]
  reasoning?: string
}

const props = defineProps<{
  history: RetrievalStep[]
  evaluation?: Evaluation
  retrievalMethod?: string
}>()

const expanded = ref(false)

const totalSteps = computed(() => props.history?.length || 0)
const totalResults = computed(() => {
  let sum = 0
  for (const s of props.history || []) {
    sum += s.result_count || 0
  }
  return sum
})
const iterations = computed(() => {
  if (!props.history) return 0
  const steps = props.history.map(s => s.step_number || 0)
  return Math.max(0, ...steps)
})

function actionLabel(action: string): string {
  const map: Record<string, string> = {
    plan: '规划',
    vector_search: '向量检索',
    hybrid_search: '混合检索',
    multi_step_search: '多步检索',
    graph_traverse: '图谱遍历',
    execute: '执行',
    evaluate: '评估',
    aggregate: '聚合',
  }
  return map[action] || action
}

function actionColor(action: string): string {
  if (action.includes('plan')) return 'bg-blue-100 text-blue-700'
  if (action.includes('search') || action.includes('traverse')) return 'bg-emerald-100 text-emerald-700'
  if (action.includes('evaluate')) return 'bg-amber-100 text-amber-700'
  if (action.includes('aggregate')) return 'bg-purple-100 text-purple-700'
  return 'bg-gray-100 text-gray-700'
}

function actionIcon(action: string) {
  if (action.includes('plan')) return Brain
  if (action.includes('search') || action.includes('traverse')) return Search
  if (action.includes('evaluate')) return CheckCircle2
  return Activity
}
</script>

<template>
  <div class="agentic-trace border border-emerald-200 rounded-xl bg-gradient-to-br from-emerald-50/40 to-teal-50/40 overflow-hidden">
    <!-- Header -->
    <button
      class="w-full px-3 py-2 flex items-center justify-between hover:bg-emerald-50/60 transition-colors"
      @click="expanded = !expanded"
    >
      <div class="flex items-center gap-2">
        <Activity :size="14" class="text-emerald-600" />
        <span class="text-xs font-medium text-gray-700">
          Agentic RAG 检索过程
        </span>
        <span class="px-1.5 py-0.5 rounded text-[10px] bg-emerald-100 text-emerald-700">
          {{ iterations }} 轮 / {{ totalSteps }} 步 / {{ totalResults }} 条
        </span>
        <span v-if="retrievalMethod" class="text-[10px] text-gray-400">
          · {{ retrievalMethod }}
        </span>
      </div>
      <ChevronDown v-if="!expanded" :size="14" class="text-gray-400" />
      <ChevronUp v-else :size="14" class="text-gray-400" />
    </button>

    <!-- Steps -->
    <div v-if="expanded" class="px-3 py-2 space-y-2 border-t border-emerald-100">
      <div
        v-for="(step, idx) in history"
        :key="idx"
        class="flex gap-2 text-xs"
      >
        <!-- Round number -->
        <div class="flex-shrink-0 w-8 text-center">
          <div class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-white border border-emerald-300 text-emerald-700 font-medium text-[10px]">
            {{ step.step_number }}
          </div>
        </div>

        <!-- Step content -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-1.5 mb-1 flex-wrap">
            <component :is="actionIcon(step.action)" :size="12" class="text-gray-500" />
            <span :class="['px-1.5 py-0.5 rounded text-[10px] font-medium', actionColor(step.action)]">
              {{ actionLabel(step.action) }}
            </span>
            <span v-if="step.duration_ms" class="text-[10px] text-gray-400">
              {{ step.duration_ms }}ms
            </span>
            <span v-if="step.result_count !== undefined" class="text-[10px] text-gray-500">
              · {{ step.result_count }} 条结果
            </span>
          </div>

          <div v-if="step.query" class="text-gray-700 mb-0.5 break-words">
            <span class="text-gray-400">查询:</span> {{ step.query }}
          </div>

          <div v-if="step.reasoning" class="text-gray-600 break-words">
            <span class="text-gray-400">理由:</span> {{ step.reasoning }}
          </div>

          <div v-if="step.decision" class="text-gray-600 break-words">
            <span class="text-gray-400">决策:</span> {{ step.decision }}
          </div>
        </div>
      </div>

      <!-- Final evaluation -->
      <div v-if="evaluation" class="mt-3 p-2 rounded-lg bg-white/80 border border-emerald-200">
        <div class="flex items-center gap-2 mb-1.5">
          <CheckCircle2 :size="12" class="text-emerald-600" />
          <span class="text-xs font-medium text-gray-700">最终评估</span>
          <span v-if="evaluation.overall_score !== undefined"
                class="ml-auto text-[10px] font-medium text-emerald-700">
            综合 {{ (evaluation.overall_score * 100).toFixed(0) }}%
          </span>
        </div>
        <div class="grid grid-cols-3 gap-2 text-[10px] text-gray-600 mb-1">
          <div v-if="evaluation.coverage_score !== undefined">
            覆盖: <span class="font-medium">{{ (evaluation.coverage_score * 100).toFixed(0) }}%</span>
          </div>
          <div v-if="evaluation.relevance_score !== undefined">
            相关: <span class="font-medium">{{ (evaluation.relevance_score * 100).toFixed(0) }}%</span>
          </div>
          <div v-if="evaluation.completeness_score !== undefined">
            完整: <span class="font-medium">{{ (evaluation.completeness_score * 100).toFixed(0) }}%</span>
          </div>
        </div>
        <div v-if="evaluation.missing_aspects?.length" class="text-[10px] text-amber-700">
          缺失方面: {{ evaluation.missing_aspects.join(', ') }}
        </div>
        <div v-if="evaluation.reasoning" class="text-[10px] text-gray-500 mt-1">
          {{ evaluation.reasoning }}
        </div>
      </div>
    </div>
  </div>
</template>
