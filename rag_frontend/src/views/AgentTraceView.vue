<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { agentTraceApi, type AgentTrace, type ToolTrace } from '@/api/agent-trace'
import {
  Network,
  Clock,
  Search,
  RefreshCw,
  ChevronRight,
  Brain,
  Cpu,
  Eye,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  Play,
  Pause,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Download,
  Copy,
  ArrowLeft,
  ExternalLink
} from 'lucide-vue-next'
import * as d3 from 'd3'

const router = useRouter()

const isLoading = ref(false)
const error = ref('')
const activeTab = ref<'traces' | 'visualization'>('traces')

const sessionId = ref('')
const selectedTrace = ref<AgentTrace | null>(null)
const traces = ref<AgentTrace[]>([])
const toolTraces = ref<ToolTrace[]>([])
const visualizationData = ref<{
  nodes: any[]
  edges: any[]
  summary: any
} | null>(null)

const flowChartContainer = ref<HTMLElement | null>(null)
const simulation = ref<any>(null)

const langSmithUrl = computed(() => {
  const project = import.meta.env.VITE_LANGSMITH_PROJECT || 'financial_rag'
  return `https://smith.langchain.com/projects/${project}?public=true`
})

const filteredTraces = computed(() => {
  if (!sessionId.value.trim()) return traces.value
  return traces.value.filter(t => t.session_id.includes(sessionId.value))
})

const stepTypeIcons = {
  start: Play,
  thinking: Brain,
  tool_call: Cpu,
  tool_result: Eye,
  response: CheckCircle,
  end: CheckCircle
}

const stepTypeColors = {
  start: 'bg-emerald-100 text-emerald-700 border-emerald-300',
  thinking: 'bg-blue-100 text-blue-700 border-blue-300',
  tool_call: 'bg-purple-100 text-purple-700 border-purple-300',
  tool_result: 'bg-orange-100 text-orange-700 border-orange-300',
  response: 'bg-green-100 text-green-700 border-green-300',
  end: 'bg-gray-100 text-gray-700 border-gray-300'
}

function formatTime(timestamp: string | number): string {
  if (!timestamp) return '-'
  if (typeof timestamp === 'number') {
    const millis = timestamp < 1000000000000 ? timestamp * 1000 : timestamp
    return new Date(millis).toLocaleString('zh-CN')
  }
  return new Date(timestamp).toLocaleString('zh-CN')
}

function formatDuration(ms: number): string {
  if (!ms) return '0ms'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}min`
}

async function loadTraces() {
  if (!sessionId.value.trim()) {
    error.value = '请输入会话ID'
    return
  }

  try {
    isLoading.value = true
    error.value = ''
    const [traceData, toolData] = await Promise.all([
      agentTraceApi.getSessionTraces(sessionId.value),
      agentTraceApi.getToolTraces(sessionId.value)
    ])
    traces.value = traceData
    toolTraces.value = toolData.traces
  } catch (err: any) {
    error.value = err.message || '加载追踪记录失败'
  } finally {
    isLoading.value = false
  }
}

async function selectTrace(trace: AgentTrace) {
  try {
    isLoading.value = true
    selectedTrace.value = await agentTraceApi.getTrace(trace.trace_id)
    activeTab.value = 'visualization'
    await loadVisualization(trace.trace_id)
  } catch (err: any) {
    selectedTrace.value = trace
    error.value = err.message || '加载追踪详情失败'
  } finally {
    isLoading.value = false
  }
}

async function loadVisualization(traceId: string) {
  try {
    isLoading.value = true
    visualizationData.value = await agentTraceApi.getVisualization(traceId)
    await nextTick()
    drawFlowChart()
  } catch (err: any) {
    error.value = err.message || '加载可视化数据失败'
  } finally {
    isLoading.value = false
  }
}

function drawFlowChart() {
  if (!flowChartContainer.value || !visualizationData.value) return

  const container = flowChartContainer.value
  container.innerHTML = ''

  const width = container.clientWidth || 800
  const height = 500

  const svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('class', 'flow-chart-svg')

  const g = svg.append('g')

  const zoom = d3.zoom()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
    })

  svg.call(zoom as any)

  const nodes = visualizationData.value.nodes.map((n: any) => ({
    ...n,
    x: width / 2,
    y: height / 2
  }))

  const edges = visualizationData.value.edges.map((e: any) => ({
    ...e,
    source: nodes.find((n: any) => n.id === e.from),
    target: nodes.find((n: any) => n.id === e.to)
  }))

  nodes.forEach((node: any, index: number) => {
    node.y = 60 + index * 80
  })

  const link = g.selectAll('.link')
    .data(edges)
    .enter()
    .append('g')
    .attr('class', 'link')

  link.append('path')
    .attr('d', (d: any) => {
      const sourceY = d.source.y
      const targetY = d.target.y
      const midY = (sourceY + targetY) / 2
      return `M${d.source.x + 60},${sourceY + 20} 
              C${d.source.x + 100},${sourceY + 20} 
               ${d.target.x + 100},${targetY + 20} 
               ${d.target.x + 60},${targetY + 20}`
    })
    .attr('fill', 'none')
    .attr('stroke', '#94a3b8')
    .attr('stroke-width', 2)
    .attr('marker-end', 'url(#arrowhead)')

  svg.append('defs').append('marker')
    .attr('id', 'arrowhead')
    .attr('viewBox', '-0 -5 10 10')
    .attr('refX', 8)
    .attr('refY', 0)
    .attr('orient', 'auto')
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .append('path')
    .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
    .attr('fill', '#94a3b8')

  link.append('text')
    .attr('x', width / 2)
    .attr('y', (d: any) => (d.source.y + d.target.y) / 2)
    .attr('text-anchor', 'middle')
    .attr('fill', '#64748b')
    .attr('font-size', '11px')
    .text((d: any) => d.label || '')

  const nodeGroups = g.selectAll('.node')
    .data(nodes)
    .enter()
    .append('g')
    .attr('class', 'node')
    .attr('transform', (d: any) => `translate(${d.x}, ${d.y})`)
    .style('cursor', 'pointer')

  nodeGroups.append('rect')
    .attr('width', 120)
    .attr('height', 40)
    .attr('x', -60)
    .attr('y', -20)
    .attr('rx', 8)
    .attr('ry', 8)
    .attr('fill', '#ffffff')
    .attr('stroke', (d: any) => {
      const colors: Record<string, string> = {
        'thought': '#3b82f6',
        'action': '#8b5cf6',
        'observation': '#f97316',
        'final_answer': '#22c55e'
      }
      return colors[d.type] || '#94a3b8'
    })
    .attr('stroke-width', 2)
    .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))')

  nodeGroups.append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .attr('fill', '#1e293b')
    .attr('font-size', '12px')
    .attr('font-weight', '500')
    .text((d: any) => d.label || d.type)
}

function zoomIn() {
  if (!flowChartContainer.value) return
  const svg = d3.select(flowChartContainer.value).select('svg')
  svg.transition().call(
    d3.zoom().scaleBy as any,
    1.3
  )
}

function zoomOut() {
  if (!flowChartContainer.value) return
  const svg = d3.select(flowChartContainer.value).select('svg')
  svg.transition().call(
    d3.zoom().scaleBy as any,
    0.7
  )
}

function resetZoom() {
  if (!flowChartContainer.value) return
  const svg = d3.select(flowChartContainer.value).select('svg')
  svg.transition().call(
    d3.zoom().transform as any,
    d3.zoomIdentity
  )
}

function copyTraceId(id: string) {
  navigator.clipboard.writeText(id)
}

function exportVisualization() {
  if (!visualizationData.value || !flowChartContainer.value) return

  const dataStr = JSON.stringify(visualizationData.value, null, 2)
  const dataBlob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(dataBlob)
  const link = document.createElement('a')
  link.href = url
  link.download = `trace-${selectedTrace.value?.trace_id || 'export'}.json`
  link.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  const routeTraceId = router.currentRoute.value.query.trace_id
  if (routeTraceId && typeof routeTraceId === 'string') {
    sessionId.value = routeTraceId
    await loadTraces()
  }
})
</script>

<template>
  <div class="h-full flex flex-col bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-6 py-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Network :size="28" class="text-purple-600" />
            智能体追踪可视化
          </h1>
          <p class="text-sm text-gray-500 mt-1">查看 Agent 执行流程和工具调用详情</p>
        </div>
        <div class="flex items-center gap-3">
          <a
            :href="langSmithUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 flex items-center gap-2 transition-all"
          >
            <ExternalLink :size="18" />
            LangSmith
          </a>
          <button
            @click="exportVisualization"
            :disabled="!visualizationData"
            class="px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 flex items-center gap-2"
          >
            <Download :size="18" />
            导出数据
          </button>
        </div>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Left Sidebar: Trace List -->
      <div class="w-80 bg-white border-r border-gray-200 flex flex-col">
        <div class="p-4 border-b border-gray-200">
          <label class="block text-sm font-medium text-gray-700 mb-2">会话ID</label>
          <div class="flex gap-2">
            <input
              v-model="sessionId"
              type="text"
              placeholder="输入会话ID..."
              class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
              @keyup.enter="loadTraces"
            />
            <button
              @click="loadTraces"
              :disabled="isLoading"
              class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
            >
              <Loader2 v-if="isLoading" :size="18" class="animate-spin" />
              <Search v-else :size="18" />
            </button>
          </div>
        </div>

        <!-- Error Message -->
        <div v-if="error" class="mx-4 mt-4 bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
          <AlertCircle :size="18" class="text-red-500" />
          <p class="text-sm text-red-700">{{ error }}</p>
        </div>

        <!-- Trace List -->
        <div class="flex-1 overflow-y-auto p-4">
          <div v-if="filteredTraces.length === 0" class="text-center py-8">
            <Network :size="48" class="mx-auto text-gray-300 mb-3" />
            <p class="text-gray-500">暂无追踪记录</p>
            <p class="text-xs text-gray-400 mt-1">输入会话ID并点击搜索</p>
          </div>

          <div v-else class="space-y-3">
            <div
              v-for="trace in filteredTraces"
              :key="trace.trace_id"
              @click="selectTrace(trace)"
              :class="[
                'p-4 rounded-lg border cursor-pointer transition-all',
                selectedTrace?.trace_id === trace.trace_id
                  ? 'bg-purple-50 border-purple-300 ring-2 ring-purple-200'
                  : 'bg-white border-gray-200 hover:border-purple-300 hover:shadow-sm'
              ]"
            >
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-mono text-gray-500">{{ trace.trace_id.slice(0, 12) }}...</span>
                <div class="flex items-center gap-1 text-xs text-gray-400">
                  <Clock :size="12" />
                  {{ formatDuration(trace.total_time) }}
                </div>
              </div>
              <p class="text-sm text-gray-700 line-clamp-2">{{ trace.query }}</p>
              <div class="flex items-center gap-2 mt-2">
                <span
                  v-for="(event, idx) in trace.events.slice(0, 3)"
                  :key="idx"
                  :class="['text-xs px-2 py-0.5 rounded-full border', stepTypeColors[event.event_type]]"
                >
                  {{ event.event_type }}
                </span>
                <span v-if="trace.events.length > 3" class="text-xs text-gray-400">
                  +{{ trace.events.length - 3 }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Main Content Area -->
      <div class="flex-1 flex flex-col overflow-hidden">
        <!-- Tabs -->
        <div class="bg-white border-b border-gray-200 px-6 py-3">
          <div class="flex gap-4">
            <button
              @click="activeTab = 'traces'"
              :class="[
                'px-4 py-2 font-medium rounded-lg transition-colors flex items-center gap-2',
                activeTab === 'traces'
                  ? 'bg-purple-100 text-purple-700'
                  : 'text-gray-600 hover:bg-gray-100'
              ]"
            >
              <Cpu :size="18" />
              追踪详情
            </button>
            <button
              @click="activeTab = 'visualization'"
              :disabled="!selectedTrace"
              :class="[
                'px-4 py-2 font-medium rounded-lg transition-colors flex items-center gap-2',
                activeTab === 'visualization'
                  ? 'bg-purple-100 text-purple-700'
                  : 'text-gray-600 hover:bg-gray-100',
                !selectedTrace && 'opacity-50 cursor-not-allowed'
              ]"
            >
              <Network :size="18" />
              流程可视化
            </button>
          </div>
        </div>

        <!-- Tab Content -->
        <div class="flex-1 overflow-y-auto p-6">
          <!-- Traces Tab -->
          <div v-if="activeTab === 'traces'" class="space-y-6">
            <div v-if="!selectedTrace" class="text-center py-12">
              <ArrowLeft :size="48" class="mx-auto text-gray-300 mb-3" />
              <p class="text-gray-500">请从左侧选择一个追踪记录</p>
            </div>

            <div v-else>
              <!-- Trace Summary -->
              <div class="bg-white rounded-xl border border-gray-200 p-6 mb-6">
                <div class="flex items-center justify-between mb-4">
                  <h3 class="text-lg font-semibold text-gray-900">追踪概览</h3>
                  <div class="flex items-center gap-2">
                    <button
                      @click="copyTraceId(selectedTrace.trace_id)"
                      class="p-2 hover:bg-gray-100 rounded-lg"
                      title="复制追踪ID"
                    >
                      <Copy :size="16" class="text-gray-500" />
                    </button>
                  </div>
                </div>

                <div class="grid grid-cols-4 gap-4 mb-4">
                  <div class="bg-gray-50 rounded-lg p-4">
                    <div class="text-2xl font-bold text-purple-600">{{ selectedTrace.events.length }}</div>
                    <div class="text-sm text-gray-500">事件总数</div>
                  </div>
                  <div class="bg-gray-50 rounded-lg p-4">
                    <div class="text-2xl font-bold text-blue-600">
                      {{ selectedTrace.events.filter(e => e.event_type === 'tool_call').length }}
                    </div>
                    <div class="text-sm text-gray-500">工具调用</div>
                  </div>
                  <div class="bg-gray-50 rounded-lg p-4">
                    <div class="text-2xl font-bold text-orange-600">
                      {{ selectedTrace.events.filter(e => e.event_type === 'tool_result').length }}
                    </div>
                    <div class="text-sm text-gray-500">工具结果</div>
                  </div>
                  <div class="bg-gray-50 rounded-lg p-4">
                    <div class="text-2xl font-bold text-gray-600">{{ formatDuration(selectedTrace.total_time) }}</div>
                    <div class="text-sm text-gray-500">总耗时</div>
                  </div>
                </div>

                <div class="flex items-center gap-2 text-sm text-gray-500">
                  <Clock :size="14" />
                  {{ formatTime(selectedTrace.created_at) }}
                </div>
              </div>

              <!-- Event Timeline -->
              <div class="bg-white rounded-xl border border-gray-200 p-6">
                <h3 class="text-lg font-semibold text-gray-900 mb-4">执行时间线</h3>
                <div class="relative">
                  <div class="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200"></div>
                  <div class="space-y-4">
                    <div
                      v-for="(event, index) in selectedTrace.events"
                      :key="index"
                      class="relative pl-10"
                    >
                      <div
                        :class="[
                          'absolute left-2 w-5 h-5 rounded-full border-2 flex items-center justify-center',
                          stepTypeColors[event.event_type].split(' ')[0],
                          stepTypeColors[event.event_type].split(' ')[1]
                        ]"
                      >
                        <component
                          :is="stepTypeIcons[event.event_type]"
                          :size="12"
                          class="text-white"
                        />
                      </div>

                      <div class="bg-gray-50 rounded-lg p-4">
                        <div class="flex items-center justify-between mb-2">
                          <span
                            :class="[
                              'text-xs px-2 py-1 rounded-full border',
                              stepTypeColors[event.event_type]
                            ]"
                          >
                            {{ event.event_type }}
                          </span>
                          <span class="text-xs text-gray-400">
                            {{ formatTime(event.timestamp) }}
                          </span>
                        </div>
                        <p class="text-sm text-gray-700 whitespace-pre-wrap">{{ event.content }}</p>
                        <div v-if="event.metadata" class="mt-2 text-xs text-gray-500">
                          <pre class="bg-white p-2 rounded border">{{ JSON.stringify(event.metadata, null, 2) }}</pre>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Visualization Tab -->
          <div v-if="activeTab === 'visualization'" class="h-full flex flex-col">
            <div v-if="!visualizationData" class="flex-1 flex items-center justify-center">
              <div class="text-center">
                <Loader2 :size="48" class="mx-auto text-purple-300 animate-spin mb-3" />
                <p class="text-gray-500">加载可视化数据...</p>
              </div>
            </div>

            <template v-else>
              <!-- Summary Cards -->
              <div class="grid grid-cols-4 gap-4 mb-6">
                <div class="bg-white rounded-lg border border-gray-200 p-4">
                  <div class="text-sm text-gray-500">总步骤数</div>
                  <div class="text-2xl font-bold text-purple-600">{{ visualizationData.summary?.total_steps || 0 }}</div>
                </div>
                <div class="bg-white rounded-lg border border-gray-200 p-4">
                  <div class="text-sm text-gray-500">总耗时</div>
                  <div class="text-2xl font-bold text-blue-600">{{ formatDuration(visualizationData.summary?.total_time || 0) }}</div>
                </div>
                <div class="bg-white rounded-lg border border-gray-200 p-4">
                  <div class="text-sm text-gray-500">工具调用数</div>
                  <div class="text-2xl font-bold text-orange-600">{{ visualizationData.summary?.tool_calls || 0 }}</div>
                </div>
                <div class="bg-white rounded-lg border border-gray-200 p-4">
                  <div class="text-sm text-gray-500">状态</div>
                  <div :class="[
                    'text-lg font-semibold',
                    visualizationData.summary?.status === 'completed' ? 'text-green-600' : 'text-yellow-600'
                  ]">
                    {{ visualizationData.summary?.status || 'unknown' }}
                  </div>
                </div>
              </div>

              <!-- Flow Chart Controls -->
              <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-2">
                  <button
                    @click="zoomIn"
                    class="p-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                    title="放大"
                  >
                    <ZoomIn :size="18" />
                  </button>
                  <button
                    @click="zoomOut"
                    class="p-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                    title="缩小"
                  >
                    <ZoomOut :size="18" />
                  </button>
                  <button
                    @click="resetZoom"
                    class="p-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                    title="重置"
                  >
                    <Maximize2 :size="18" />
                  </button>
                </div>
                <div class="flex items-center gap-4 text-sm">
                  <div class="flex items-center gap-2">
                    <div class="w-3 h-3 rounded-full bg-blue-500"></div>
                    <span>思考</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <div class="w-3 h-3 rounded-full bg-purple-500"></div>
                    <span>行动</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <div class="w-3 h-3 rounded-full bg-orange-500"></div>
                    <span>观察</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <div class="w-3 h-3 rounded-full bg-green-500"></div>
                    <span>答案</span>
                  </div>
                </div>
              </div>

              <!-- Flow Chart -->
              <div
                ref="flowChartContainer"
                class="flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden"
                style="min-height: 400px"
              ></div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.flow-chart-svg {
  background: linear-gradient(45deg, #f8fafc 25%, transparent 25%),
              linear-gradient(-45deg, #f8fafc 25%, transparent 25%),
              linear-gradient(45deg, transparent 75%, #f8fafc 75%),
              linear-gradient(-45deg, transparent 75%, #f8fafc 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
}
</style>
