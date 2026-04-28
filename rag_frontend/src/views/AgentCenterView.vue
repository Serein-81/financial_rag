<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { agentDiscoveryApi, type AgentSummary, type AgentDetail, type ToolInfo, type RegistrySummary, type AgentTrace, type AgentTraceEvent, type AgentTraceStep, ToolLocation } from '@/api/agent-discovery'
import { multiAgentApi, type SystemHealth, type TaskPipeline, type AgentMetric, SessionState } from '@/api/multi-agent'
import { langSmithApi, type LangSmithStatus, type LangSmithStats, type LangSmithDashboard, type LangSmithProjectInfo, type LangSmithTrace } from '@/api/langsmith'
import {
  Compass,
  Monitor,
  Activity,
  History,
  Bot,
  Wrench,
  Server,
  Cloud,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Clock,
  CheckCircle2,
  XCircle,
  Warning,
  Loader2,
  Search,
  Network,
  Users,
  Zap,
  Shield,
  Brain,
  Cpu,
  Eye,
  Play,
  Pause,
  ZoomIn,
  ZoomOut,
  Maximize2,
  ArrowLeft,
  Layers,
  Link2,
  Settings,
  ExternalLink,
  ActivitySquare,
  BarChart3,
} from 'lucide-vue-next'
import * as d3 from 'd3'
import ObservabilityPanel from '@/components/ObservabilityPanel.vue'

const activeTab = ref<'discovery' | 'monitor' | 'trace' | 'history' | 'langsmith' | 'observability'>('discovery')
const isLoading = ref(false)
const error = ref('')
const lastRefresh = ref(new Date())

const summary = ref<RegistrySummary | null>(null)
const agents = ref<AgentSummary[]>([])
const agentDetails = ref<Map<string, AgentDetail>>(new Map())
const tools = ref<ToolInfo[]>([])
const expandedAgent = ref<string | null>(null)
const toolViewMode = ref<'location' | 'category' | 'agent'>('location')

const systemHealth = ref<SystemHealth | null>(null)
const activePipelines = ref<TaskPipeline[]>([])
const agentMetrics = ref<AgentMetric[]>([])
const showHistory = ref(false)
const pipelineHistory = ref<TaskPipeline[]>([])
const selectedPipeline = ref<TaskPipeline | null>(null)

const sessionId = ref('')
const traces = ref<AgentTrace[]>([])
const selectedTrace = ref<AgentTrace | null>(null)
const visualizationData = ref<{
  nodes: any[]
  edges: any[]
  summary: any
} | null>(null)
const flowChartContainer = ref<HTMLElement | null>(null)

// LangSmith 监控状态
const langSmithStatus = ref<LangSmithStatus | null>(null)
const langSmithStats = ref<LangSmithStats | null>(null)
const langSmithDashboard = ref<LangSmithDashboard | null>(null)
const langSmithProjectInfo = ref<LangSmithProjectInfo | null>(null)
const recentTraces = ref<LangSmithTrace[]>([])
const langSmithLoading = ref(false)
const langSmithError = ref('')
const showLangSmithConfig = ref(false)
const langSmithConfigForm = ref({
  api_key: '',
  project: '',
  tracing: true
})

const statusColors = {
  healthy: 'text-green-600 bg-green-50',
  degraded: 'text-yellow-600 bg-yellow-50',
  down: 'text-red-600 bg-red-50',
}

const stateLabels = {
  [SessionState.IDLE]: { text: '空闲', color: 'gray' },
  [SessionState.PROCESSING]: { text: '处理中', color: 'blue' },
  [SessionState.WAITING_FOR_USER_REPLY]: { text: '等待回复', color: 'yellow' },
  [SessionState.COMPLETED]: { text: '已完成', color: 'green' },
}

const taskStatusColors = {
  pending: 'bg-gray-400',
  running: 'bg-emerald-500 animate-pulse',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  streaming: 'bg-emerald-500 animate-pulse',
}

const stepTypeIcons = {
  start: Play,
  thinking: Brain,
  tool_call: Cpu,
  tool_result: Eye,
  response: CheckCircle2,
  end: CheckCircle2
}

const stepTypeColors = {
  start: 'bg-emerald-100 text-emerald-700 border-emerald-300',
  thinking: 'bg-blue-100 text-blue-700 border-blue-300',
  tool_call: 'bg-purple-100 text-purple-700 border-purple-300',
  tool_result: 'bg-orange-100 text-orange-700 border-orange-300',
  response: 'bg-green-100 text-green-700 border-green-300',
  end: 'bg-gray-100 text-gray-700 border-gray-300'
}

const toolLocationMeta = {
  local: {
    label: '本地工具',
    detail: '进程内 / 本地资源',
    emptyLabel: '本地',
    icon: Server,
    cardClass: 'bg-emerald-50',
    iconClass: 'text-emerald-600',
    textClass: 'text-emerald-700',
    badgeClass: 'bg-emerald-100 text-emerald-700',
  },
  mcp: {
    label: 'MCP 工具',
    detail: 'MCP 协议/进程内适配',
    emptyLabel: 'MCP',
    icon: Network,
    cardClass: 'bg-blue-50',
    iconClass: 'text-blue-600',
    textClass: 'text-blue-700',
    badgeClass: 'bg-blue-100 text-blue-700',
  },
  cloud: {
    label: '云端工具',
    detail: '已连接远端服务',
    emptyLabel: '云端',
    icon: Cloud,
    cardClass: 'bg-orange-50',
    iconClass: 'text-orange-600',
    textClass: 'text-orange-700',
    badgeClass: 'bg-orange-100 text-orange-700',
  },
} as const

const toolLocations = ['local', 'mcp', 'cloud'] as const

function getToolLocationMeta(location: string) {
  return toolLocationMeta[location as keyof typeof toolLocationMeta] || toolLocationMeta.mcp
}

function mapTraceStepToEvent(step: AgentTraceStep): AgentTraceEvent {
  const eventTypeMap: Record<string, AgentTraceEvent['event_type']> = {
    thought: 'thinking',
    action: 'tool_call',
    observation: 'tool_result',
    final_answer: 'response',
  }

  const timestamp = typeof step.timestamp === 'number'
    ? new Date(step.timestamp * 1000).toISOString()
    : new Date().toISOString()

  return {
    timestamp,
    event_type: eventTypeMap[step.step_type] || 'thinking',
    content: step.content,
    metadata: {
      step_number: step.step_number,
      step_type: step.step_type,
      tool_name: step.tool_name,
      tool_input: step.tool_input,
      tool_output: step.tool_output,
      tool_duration: step.tool_duration,
      confidence: step.confidence,
    },
  }
}

function normalizeTrace(trace: AgentTrace): AgentTrace {
  if (trace.events?.length) return trace
  return {
    ...trace,
    events: (trace.steps || []).map(mapTraceStepToEvent),
  }
}

function getUniqueCategories(): string[] {
  const categories = new Set<string>()
  tools.value.forEach(tool => {
    if (tool.category && tool.category !== 'general') {
      categories.add(tool.category)
    }
  })
  return Array.from(categories).sort()
}

function getUniqueAgents(): string[] {
  const agents = new Set<string>()
  tools.value.forEach(tool => {
    if (tool.agent_name) {
      agents.add(tool.agent_name)
    }
  })
  return Array.from(agents).sort()
}

function getCategoryColor(category: string): string {
  const colorMap: Record<string, string> = {
    '金额信息': 'bg-amber-100 text-amber-700',
    '百分比异常': 'bg-orange-100 text-orange-700',
    '财务合规': 'bg-emerald-100 text-emerald-700',
    '发票管理': 'bg-blue-100 text-blue-700',
    '税率合规': 'bg-cyan-100 text-cyan-700',
    '税务合规': 'bg-purple-100 text-purple-700',
    '合同管理': 'bg-indigo-100 text-indigo-700',
    '日期审查': 'bg-pink-100 text-pink-700',
    '法律合规': 'bg-rose-100 text-rose-700',
    '门卫审核': 'bg-gray-100 text-gray-700',
    '安全拦截': 'bg-red-100 text-red-700',
    '执行错误': 'bg-red-100 text-red-700',
    'research': 'bg-teal-100 text-teal-700',
    '优惠政策': 'bg-green-100 text-green-700',
    '进项管理': 'bg-blue-100 text-blue-700',
  }
  return colorMap[category] || 'bg-slate-100 text-slate-700'
}

async function loadDiscoveryData() {
  try {
    isLoading.value = true
    error.value = ''
    const [summaryData, toolsData] = await Promise.all([
      agentDiscoveryApi.getSummary(),
      agentDiscoveryApi.getTools()
    ])
    summary.value = summaryData
    agents.value = summaryData.agents
    tools.value = toolsData
    lastRefresh.value = new Date()
  } catch (err: any) {
    error.value = err.message || '加载发现数据失败'
  } finally {
    isLoading.value = false
  }
}

async function loadAgentDetail(agentId: string) {
  try {
    if (!agentDetails.value.has(agentId)) {
      const detail = await agentDiscoveryApi.getAgent(agentId)
      agentDetails.value.set(agentId, detail)
    }
  } catch (err: any) {
    console.error('加载智能体详情失败', err)
    error.value = err.message || '加载智能体详情失败，请稍后重试'
    agentDetails.value.set(agentId, {
      agent_id: agentId,
      agent_name: '',
      agent_type: '',
      description: '加载失败',
      tool_count: 0,
      tool_breakdown: {},
      enabled: false,
      capabilities: [],
      tools: [],
      tool_summary: {},
      created_at: '',
      last_updated: '',
    })
  }
}

async function loadMonitorData() {
  try {
    const results = await Promise.allSettled([
      multiAgentApi.getSystemHealth(),
      multiAgentApi.getActivePipelines(),
      multiAgentApi.getAgentMetrics(),
    ])

    const [healthResult, pipelinesResult, metricsResult] = results

    if (healthResult.status === 'fulfilled') {
      systemHealth.value = healthResult.value
    }
    if (pipelinesResult.status === 'fulfilled') {
      activePipelines.value = pipelinesResult.value
    }
    if (metricsResult.status === 'fulfilled') {
      agentMetrics.value = metricsResult.value
    }
  } catch (err: any) {
    error.value = err.message || '加载监控数据失败'
  }
}

async function loadHistoryData() {
  try {
    isLoading.value = true
    pipelineHistory.value = await multiAgentApi.getPipelineHistory({ limit: 50 })
  } catch (err: any) {
    console.error('加载历史数据失败', err)
    pipelineHistory.value = []
  } finally {
    isLoading.value = false
  }
}

async function loadTraceData() {
  try {
    isLoading.value = true
    error.value = ''
    const result = await agentDiscoveryApi.getTraces(50)
    traces.value = result.traces.map(normalizeTrace)
    lastRefresh.value = new Date()
  } catch (err: any) {
    error.value = err.message || '加载追踪数据失败'
  } finally {
    isLoading.value = false
  }
}

async function selectTrace(trace: AgentTrace) {
  try {
    isLoading.value = true
    error.value = ''
    const detail = await agentDiscoveryApi.getTrace(trace.trace_id)
    selectedTrace.value = normalizeTrace({ ...trace, ...detail })
  } catch (err: any) {
    selectedTrace.value = normalizeTrace(trace)
    error.value = err.message || '加载追踪详情失败'
  } finally {
    isLoading.value = false
  }

  await loadVisualization(trace.trace_id)
}

async function loadVisualization(traceId: string) {
  try {
    isLoading.value = true
    visualizationData.value = await agentDiscoveryApi.getTraceVisualization(traceId)
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

  const zoom = d3.zoom<any, any>()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
    })

  svg.call(zoom)

  const nodes = visualizationData.value.nodes
  const edges = visualizationData.value.edges

  const simulation = d3.forceSimulation(nodes as any)
    .force('link', d3.forceLink(edges).id((d: any) => d.id).distance(150))
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(50))

  const link = g.append('g')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('stroke', '#94a3b8')
    .attr('stroke-width', 2)
    .attr('stroke-opacity', 0.6)

  const dragBehavior = d3.drag<any, any>()
    .on('start', (event: any, d: any) => {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      d.fx = d.x
      d.fy = d.y
    })
    .on('drag', (event: any, d: any) => {
      d.fx = event.x
      d.fy = event.y
    })
    .on('end', (event: any, d: any) => {
      if (!event.active) simulation.alphaTarget(0)
      d.fx = null
      d.fy = null
    })

  const node = g.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .call(dragBehavior)

  node.append('circle')
    .attr('r', 30)
    .attr('fill', (d: any) => {
      const colors: Record<string, string> = {
        start: '#10b981',
        end: '#6366f1',
        tool_call: '#8b5cf6',
        thinking: '#3b82f6',
        tool_result: '#f59e0b',
        response: '#22c55e'
      }
      return colors[d.type] || '#64748b'
    })
    .attr('stroke', '#fff')
    .attr('stroke-width', 3)

  node.append('text')
    .text((d: any) => d.label?.substring(0, 10) || d.id.substring(0, 10))
    .attr('text-anchor', 'middle')
    .attr('dy', 45)
    .attr('font-size', 12)
    .attr('fill', '#475569')

  simulation.on('tick', () => {
    link
      .attr('x1', (d: any) => d.source.x)
      .attr('y1', (d: any) => d.source.y)
      .attr('x2', (d: any) => d.target.x)
      .attr('y2', (d: any) => d.target.y)

    node.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
  })
}

async function toggleAgent(agentId: string) {
  if (expandedAgent.value === agentId) {
    expandedAgent.value = null
  } else {
    expandedAgent.value = agentId
    await loadAgentDetail(agentId)
  }
}

function formatTime(timestamp: string): string {
  if (!timestamp) return '-'
  const d = new Date(timestamp)
  if (isNaN(d.getTime())) return '-'
  return d.toLocaleString('zh-CN')
}

function truncateText(text: string | null | undefined, maxLen: number): string {
  if (!text) return '无查询'
  return text.length > maxLen ? text.substring(0, maxLen) + '...' : text
}

function formatDuration(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '-'
  if (seconds < 60) return `${seconds.toFixed(0)}秒`
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}分钟`
  return `${(seconds / 3600).toFixed(1)}小时`
}

function getTaskProgress(tasks: any[]): number {
  if (tasks.length === 0) return 0
  const completed = tasks.filter(t => t.status === 'completed' || t.status === 'failed').length
  return Math.round((completed / tasks.length) * 100)
}

function selectPipeline(pipeline: TaskPipeline) {
  selectedPipeline.value = selectedPipeline.value?.pipeline_id === pipeline.pipeline_id ? null : pipeline
}

async function refresh() {
  if (activeTab.value === 'discovery') {
    await loadDiscoveryData()
  } else if (activeTab.value === 'monitor') {
    await loadMonitorData()
  } else if (activeTab.value === 'history') {
    await loadHistoryData()
  } else if (activeTab.value === 'trace') {
    await loadTraceData()
  } else if (activeTab.value === 'langsmith') {
    await loadLangSmithData()
  }
}

async function loadLangSmithData() {
  try {
    langSmithLoading.value = true
    langSmithError.value = ''
    const [status, stats, dashboard, projectInfo, traces] = await Promise.allSettled([
      langSmithApi.getStatus(),
      langSmithApi.getStats(),
      langSmithApi.getDashboard(),
      langSmithApi.getProjectInfo(),
      langSmithApi.getRecentTraces(10)
    ])

    if (status.status === 'fulfilled') {
      langSmithStatus.value = status.value
    }
    if (stats.status === 'fulfilled') {
      langSmithStats.value = stats.value
    }
    if (dashboard.status === 'fulfilled') {
      langSmithDashboard.value = dashboard.value
    }
    if (projectInfo.status === 'fulfilled') {
      langSmithProjectInfo.value = projectInfo.value
    }
    if (traces.status === 'fulfilled') {
      recentTraces.value = traces.value.traces || []
    }
  } catch (err: any) {
    langSmithError.value = err.message || '加载 LangSmith 数据失败'
  } finally {
    langSmithLoading.value = false
  }
}

async function testLangSmithConnection() {
  try {
    langSmithError.value = ''
    const result = await langSmithApi.testConnection()
    if (!result.success) {
      langSmithError.value = result.message
    } else {
      alert('LangSmith 连接测试成功！')
    }
  } catch (err: any) {
    langSmithError.value = err.message || '测试连接失败'
  }
}

async function updateLangSmithConfig() {
  try {
    const result = await langSmithApi.updateConfig(langSmithConfigForm.value)
    if (result.current_config) {
      langSmithStatus.value = result.current_config
    }
    showLangSmithConfig.value = false
    alert('LangSmith 配置已更新！')
  } catch (err: any) {
    langSmithError.value = err.message || '更新配置失败'
  }
}

function openLangSmithDashboard() {
  if (langSmithDashboard.value?.dashboard_url) {
    window.open(langSmithDashboard.value.dashboard_url, '_blank')
  }
}

onMounted(() => {
  loadDiscoveryData()
})
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
    <div class="max-w-[1800px] mx-auto p-6">
      <div class="mb-6">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
              <Bot :size="24" class="text-white" />
            </div>
            <div>
              <h1 class="text-3xl font-bold text-slate-900">智能体中心</h1>
              <p class="text-slate-600 text-sm mt-1">统一管理、监控和追踪您的智能体系统</p>
            </div>
          </div>
          <button
            @click="refresh"
            :disabled="isLoading"
            class="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50 shadow-sm"
          >
            <RefreshCw :size="16" :class="{ 'animate-spin': isLoading }" />
            <span class="text-sm font-medium">刷新</span>
          </button>
        </div>

        <div class="flex gap-2 bg-white p-1.5 rounded-xl shadow-sm border border-slate-200 w-fit">
          <button
            v-for="tab in [
              { id: 'discovery', label: '发现', icon: Compass },
              { id: 'monitor', label: '监控', icon: Monitor },
              { id: 'trace', label: '追踪', icon: Activity },
              { id: 'history', label: '历史', icon: History },
              { id: 'langsmith', label: 'LangSmith', icon: ActivitySquare },
              { id: 'observability', label: '可观测性', icon: BarChart3 }
            ]"
            :key="tab.id"
            @click="activeTab = tab.id as any; refresh()"
            :class="[
              'flex items-center gap-2 px-5 py-2.5 rounded-lg font-medium transition-all',
              activeTab === tab.id
                ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-md'
                : 'text-slate-600 hover:bg-slate-100'
            ]"
          >
            <component :is="tab.icon" :size="18" />
            <span>{{ tab.label }}</span>
          </button>
        </div>
      </div>

      <div v-if="error" class="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
        {{ error }}
      </div>

      <div v-if="isLoading && !summary" class="flex items-center justify-center h-64">
        <Loader2 :size="32" class="animate-spin text-indigo-500" />
      </div>

      <div v-else>
        <div v-if="activeTab === 'discovery'" class="space-y-6">
          <div v-if="summary" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 hover:shadow-md transition-shadow">
              <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Bot :size="20" class="text-blue-600" />
                </div>
                <span class="text-sm font-medium text-slate-600">智能体总数</span>
              </div>
              <p class="text-3xl font-bold text-slate-900">{{ summary.total_agents }}</p>
            </div>
            <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 hover:shadow-md transition-shadow">
              <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                  <Wrench :size="20" class="text-purple-600" />
                </div>
                <span class="text-sm font-medium text-slate-600">工具总数</span>
              </div>
              <p class="text-3xl font-bold text-slate-900">{{ summary.total_tools }}</p>
            </div>
            <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 hover:shadow-md transition-shadow">
              <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
                  <Server :size="20" class="text-emerald-600" />
                </div>
                <span class="text-sm font-medium text-slate-600">本地工具</span>
              </div>
              <p class="text-3xl font-bold text-slate-900">{{ summary.tool_breakdown?.local || 0 }}</p>
            </div>
            <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 hover:shadow-md transition-shadow">
              <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Network :size="20" class="text-blue-600" />
                </div>
                <span class="text-sm font-medium text-slate-600">MCP 工具</span>
              </div>
              <p class="text-3xl font-bold text-slate-900">{{ summary.tool_breakdown?.mcp || 0 }}</p>
            </div>
            <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 hover:shadow-md transition-shadow">
              <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
                  <Cloud :size="20" class="text-orange-600" />
                </div>
                <span class="text-sm font-medium text-slate-600">云端工具</span>
              </div>
              <p class="text-3xl font-bold text-slate-900">{{ summary.tool_breakdown?.cloud || 0 }}</p>
            </div>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div class="px-5 py-4 border-b border-slate-200 bg-slate-50">
                <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                  <Bot :size="20" class="text-indigo-600" />
                  已注册智能体
                </h2>
              </div>
              <div class="divide-y divide-slate-100 max-h-[500px] overflow-y-auto">
                <div
                  v-for="agent in agents"
                  :key="agent.agent_id"
                  class="p-4 hover:bg-slate-50 transition-colors"
                >
                  <div
                    @click="toggleAgent(agent.agent_id)"
                    class="flex items-center justify-between cursor-pointer"
                  >
                    <div class="flex items-center gap-3">
                      <div :class="[
                        'w-10 h-10 rounded-lg flex items-center justify-center',
                        agent.enabled ? 'bg-emerald-100' : 'bg-slate-100'
                      ]">
                        <Bot :size="20" :class="agent.enabled ? 'text-emerald-600' : 'text-slate-400'" />
                      </div>
                      <div>
                        <h3 class="font-medium text-slate-900">{{ agent.agent_name }}</h3>
                        <p class="text-sm text-slate-500">{{ agent.specialty || agent.capabilities.slice(0, 2).join(', ') }}</p>
                      </div>
                    </div>
                    <div class="flex items-center gap-3">
                      <span :class="[
                        'px-2.5 py-1 rounded-full text-xs font-medium',
                        agent.agent_type === 'specialist' ? 'bg-blue-100 text-blue-700' :
                        agent.agent_type === 'router' ? 'bg-purple-100 text-purple-700' :
                        'bg-slate-100 text-slate-700'
                      ]">
                        {{ agent.agent_type }}
                      </span>
                      <span class="text-xs text-slate-400">{{ agent.tool_count }} 工具</span>
                      <component :is="expandedAgent === agent.agent_id ? ChevronDown : ChevronRight" :size="16" class="text-slate-400" />
                    </div>
                  </div>
                  <div v-if="expandedAgent === agent.agent_id" class="mt-4 pl-4 border-l-2 border-indigo-200">
                    <p class="text-sm text-slate-600 mb-3">{{ agent.description }}</p>
                    <div class="grid grid-cols-2 gap-2">
                      <div
                        v-for="tool in agentDetails.get(agent.agent_id)?.tools || []"
                        :key="tool.name"
                        class="flex items-center gap-2 p-2 bg-slate-50 rounded-lg"
                      >
                        <Wrench :size="14" class="text-slate-400" />
                        <span class="text-sm text-slate-700">{{ tool.name }}</span>
                        <span :class="[
                          'px-1.5 py-0.5 rounded text-xs',
                          getToolLocationMeta(tool.location).badgeClass
                        ]">
                          {{ getToolLocationMeta(tool.location).label }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-if="agents.length === 0" class="p-8 text-center text-slate-500">
                  暂无注册的智能体
                </div>
              </div>
            </div>

            <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div class="px-5 py-4 border-b border-slate-200 bg-slate-50">
                <div class="flex items-center justify-between">
                  <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                    <Wrench :size="20" class="text-indigo-600" />
                    工具分类
                  </h2>
                  <div class="flex gap-2">
                    <button
                      @click="toolViewMode = 'location'"
                      :class="[
                        'px-3 py-1 text-xs rounded-full transition-colors',
                        toolViewMode === 'location' 
                          ? 'bg-indigo-100 text-indigo-700 font-medium' 
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      ]"
                    >
                      按位置
                    </button>
                    <button
                      @click="toolViewMode = 'category'"
                      :class="[
                        'px-3 py-1 text-xs rounded-full transition-colors',
                        toolViewMode === 'category' 
                          ? 'bg-indigo-100 text-indigo-700 font-medium' 
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      ]"
                    >
                      按功能                    </button>
                    <button
                      @click="toolViewMode = 'agent'"
                      :class="[
                        'px-3 py-1 text-xs rounded-full transition-colors',
                        toolViewMode === 'agent' 
                          ? 'bg-indigo-100 text-indigo-700 font-medium' 
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      ]"
                    >
                      按Agent
                    </button>
                  </div>
                </div>
              </div>
              <div class="p-5 space-y-4 max-h-[500px] overflow-y-auto">
                <!-- 按位置分类视图-->
                <template v-if="toolViewMode === 'location'">
                  <div v-for="location in toolLocations" :key="location" class="border border-slate-200 rounded-lg overflow-hidden">
                    <div :class="[
                      'px-4 py-3 flex items-center justify-between',
                      getToolLocationMeta(location).cardClass
                    ]">
                      <div class="flex items-center gap-2">
                        <component
                          :is="getToolLocationMeta(location).icon"
                          :size="18"
                          :class="getToolLocationMeta(location).iconClass"
                        />
                        <span :class="[
                          'font-medium',
                          getToolLocationMeta(location).textClass
                        ]">
                          {{ getToolLocationMeta(location).label }}
                          <span class="ml-1 text-xs font-normal text-slate-500">{{ getToolLocationMeta(location).detail }}</span>
                        </span>
                      </div>
                      <span class="text-sm text-slate-600">
                        {{ tools.filter(t => t.location === location).length }} 个
                      </span>
                    </div>
                    <div class="p-3 space-y-2">
                      <div
                        v-for="tool in tools.filter(t => t.location === location)"
                        :key="tool.name"
                        class="flex items-start gap-2 p-2 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                      >
                        <Wrench :size="14" class="text-slate-400 mt-0.5" />
                        <div class="flex-1 min-w-0">
                          <div class="flex items-center gap-2 flex-wrap">
                            <p class="text-sm font-medium text-slate-700">{{ tool.name }}</p>
                            <span v-if="tool.category && tool.category !== 'general'" :class="[
                              'px-1.5 py-0.5 rounded text-xs',
                              getCategoryColor(tool.category)
                            ]">
                              {{ tool.category }}
                            </span>
                          </div>
                          <p class="text-xs text-slate-500 mt-0.5">{{ tool.description }}</p>
                          <p class="text-xs text-slate-400 mt-1">归属: {{ tool.agent_name || '未知' }}</p>
                        </div>
                      </div>
                      <div v-if="tools.filter(t => t.location === location).length === 0" class="text-sm text-slate-400 text-center py-2">
                        暂无{{ getToolLocationMeta(location).emptyLabel }}工具
                      </div>
                    </div>
                  </div>
                </template>

                <!-- 按功能分类视图-->
                <template v-else-if="toolViewMode === 'category'">
                  <div v-for="category in getUniqueCategories()" :key="category" class="border border-slate-200 rounded-lg overflow-hidden">
                    <div class="px-4 py-3 flex items-center justify-between bg-purple-50">
                      <div class="flex items-center gap-2">
                        <Layers :size="18" class="text-purple-600" />
                        <span class="font-medium text-purple-700">{{ category }}</span>
                      </div>
                      <span class="text-sm text-slate-600">
                        {{ tools.filter(t => t.category === category).length }} 个
                      </span>
                    </div>
                    <div class="p-3 space-y-2">
                      <div
                        v-for="tool in tools.filter(t => t.category === category)"
                        :key="tool.name"
                        class="flex items-start gap-2 p-2 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                      >
                        <Wrench :size="14" class="text-slate-400 mt-0.5" />
                        <div class="flex-1 min-w-0">
                          <div class="flex items-center gap-2 flex-wrap">
                            <p class="text-sm font-medium text-slate-700">{{ tool.name }}</p>
                            <span :class="[
                              'px-1.5 py-0.5 rounded text-xs',
                              getToolLocationMeta(tool.location).badgeClass
                            ]">
                              {{ getToolLocationMeta(tool.location).label }}
                            </span>
                          </div>
                          <p class="text-xs text-slate-500 mt-0.5">{{ tool.description }}</p>
                          <p class="text-xs text-slate-400 mt-1">归属: {{ tool.agent_name || '未知' }}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                  <!-- 未分类工具-->
                  <div v-if="tools.filter(t => !t.category || t.category === 'general').length > 0" class="border border-slate-200 rounded-lg overflow-hidden">
                    <div class="px-4 py-3 flex items-center justify-between bg-slate-50">
                      <div class="flex items-center gap-2">
                        <Layers :size="18" class="text-slate-600" />
                        <span class="font-medium text-slate-700">未分类</span>
                      </div>
                      <span class="text-sm text-slate-600">
                        {{ tools.filter(t => !t.category || t.category === 'general').length }} 个
                      </span>
                    </div>
                    <div class="p-3 space-y-2">
                      <div
                        v-for="tool in tools.filter(t => !t.category || t.category === 'general')"
                        :key="tool.name"
                        class="flex items-start gap-2 p-2 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                      >
                        <Wrench :size="14" class="text-slate-400 mt-0.5" />
                        <div class="flex-1 min-w-0">
                          <div class="flex items-center gap-2 flex-wrap">
                            <p class="text-sm font-medium text-slate-700">{{ tool.name }}</p>
                            <span :class="[
                              'px-1.5 py-0.5 rounded text-xs',
                              getToolLocationMeta(tool.location).badgeClass
                            ]">
                              {{ getToolLocationMeta(tool.location).label }}
                            </span>
                          </div>
                          <p class="text-xs text-slate-500 mt-0.5">{{ tool.description }}</p>
                          <p class="text-xs text-slate-400 mt-1">归属: {{ tool.agent_name || '未知' }}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>

                <!-- 按Agent分类视图 -->
                <template v-else-if="toolViewMode === 'agent'">
                  <div v-for="agentName in getUniqueAgents()" :key="agentName" class="border border-slate-200 rounded-lg overflow-hidden">
                    <div class="px-4 py-3 flex items-center justify-between bg-indigo-50">
                      <div class="flex items-center gap-2">
                        <Bot :size="18" class="text-indigo-600" />
                        <span class="font-medium text-indigo-700">{{ agentName }}</span>
                      </div>
                      <span class="text-sm text-slate-600">
                        {{ tools.filter(t => t.agent_name === agentName).length }} 个
                      </span>
                    </div>
                    <div class="p-3 space-y-2">
                      <div
                        v-for="tool in tools.filter(t => t.agent_name === agentName)"
                        :key="tool.name"
                        class="flex items-start gap-2 p-2 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                      >
                        <Wrench :size="14" class="text-slate-400 mt-0.5" />
                        <div class="flex-1 min-w-0">
                          <div class="flex items-center gap-2 flex-wrap">
                            <p class="text-sm font-medium text-slate-700">{{ tool.name }}</p>
                            <span v-if="tool.category && tool.category !== 'general'" :class="[
                              'px-1.5 py-0.5 rounded text-xs',
                              getCategoryColor(tool.category)
                            ]">
                              {{ tool.category }}
                            </span>
                          </div>
                          <p class="text-xs text-slate-500 mt-0.5">{{ tool.description }}</p>
                          <span :class="[
                            'inline-block mt-1 px-1.5 py-0.5 rounded text-xs',
                            getToolLocationMeta(tool.location).badgeClass
                          ]">
                            {{ getToolLocationMeta(tool.location).label }}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'monitor'" class="space-y-6">
          <div v-if="systemHealth" class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
              <div class="flex items-center justify-between mb-3">
                <span class="text-sm font-medium text-slate-600">系统状态</span>
                <div :class="[
                  'px-2.5 py-1 rounded-full text-xs font-medium',
                  statusColors[systemHealth.status as keyof typeof statusColors] || 'bg-slate-100 text-slate-600'
                ]">
                  {{ systemHealth.status === 'healthy' ? '健康' : systemHealth.status === 'degraded' ? '降级' : '故障' }}
                </div>
              </div>
              <div class="flex items-center gap-2">
                <Activity :size="20" class="text-indigo-600" />
                <span class="text-2xl font-bold text-slate-900">{{ systemHealth.active_agents || 0 }}</span>
                <span class="text-sm text-slate-500">活跃智能体</span>
              </div>
            </div>
            <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
              <div class="flex items-center justify-between mb-3">
                <span class="text-sm font-medium text-slate-600">会话状态</span>
              </div>
              <div class="flex items-center gap-2">
                <Users :size="20" class="text-indigo-600" />
                <span class="text-2xl font-bold text-slate-900">{{ systemHealth.active_sessions || 0 }}</span>
                <span class="text-sm text-slate-500">活跃会话</span>
              </div>
            </div>
            <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
              <div class="flex items-center justify-between mb-3">
                <span class="text-sm font-medium text-slate-600">任务队列</span>
              </div>
              <div class="flex items-center gap-2">
                <Zap :size="20" class="text-indigo-600" />
                <span class="text-2xl font-bold text-slate-900">{{ systemHealth.tasks_in_queue || 0 }}</span>
                <span class="text-sm text-slate-500">待处理任务</span>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div class="px-5 py-4 border-b border-slate-200 bg-slate-50">
                <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                  <Zap :size="20" class="text-indigo-600" />
                  活跃管道
                </h2>
              </div>
              <div class="divide-y divide-slate-100 max-h-[400px] overflow-y-auto">
                <div
                  v-for="pipeline in activePipelines"
                  :key="pipeline.pipeline_id"
                  class="p-4 hover:bg-slate-50 transition-colors"
                >
                  <div
                    @click="selectPipeline(pipeline)"
                    class="cursor-pointer"
                  >
                    <div class="flex items-center justify-between mb-2">
                      <div class="flex items-center gap-2">
                        <span class="font-medium text-slate-900 text-sm">{{ truncateText(pipeline.query, 30) }}</span>
                        <span :class="[
                          'px-2 py-0.5 rounded-full text-xs font-medium',
                          `bg-${stateLabels[pipeline.state]?.color}-100 text-${stateLabels[pipeline.state]?.color}-700`
                        ]">
                          {{ stateLabels[pipeline.state]?.text || pipeline.state }}
                        </span>
                      </div>
                      <span class="text-xs text-slate-400">{{ formatDuration((new Date(pipeline.updated_at).getTime() - new Date(pipeline.created_at).getTime()) / 1000) }}</span>
                    </div>
                    <div class="flex items-center gap-2">
                      <div class="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          class="h-full bg-gradient-to-r from-indigo-500 to-purple-600 transition-all"
                          :style="{ width: `${getTaskProgress(pipeline.tasks)}%` }"
                        />
                      </div>
                      <span class="text-xs text-slate-500">{{ getTaskProgress(pipeline.tasks) }}%</span>
                    </div>
                  </div>
                  <div v-if="selectedPipeline?.pipeline_id === pipeline.pipeline_id" class="mt-3 pl-3 border-l-2 border-indigo-200 space-y-2">
                    <div v-for="task in pipeline.tasks" :key="task.task_id" class="flex items-center gap-2 text-sm">
                      <span :class="['w-2 h-2 rounded-full', taskStatusColors[task.status]]" />
                      <span class="text-slate-600">{{ task.agent_name }}</span>
                      <span class="text-slate-400">{{ task.status }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="activePipelines.length === 0" class="p-8 text-center text-slate-500">
                  暂无活跃管道
                </div>
              </div>
            </div>

            <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div class="px-5 py-4 border-b border-slate-200 bg-slate-50">
                <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                  <Bot :size="20" class="text-indigo-600" />
                  智能体指标</h2>
              </div>
              <div class="p-5 max-h-[400px] overflow-y-auto">
                <div v-for="metric in agentMetrics" :key="metric.agent_id" class="mb-4 last:mb-0">
                  <div class="flex items-center justify-between mb-2">
                    <span class="font-medium text-slate-900">{{ metric.agent_name }}</span>
                    <span class="text-sm text-slate-500">{{ metric.tasks_completed }} 任务</span>
                  </div>
                  <div class="grid grid-cols-3 gap-2 text-sm">
                    <div class="bg-slate-50 rounded-lg p-2 text-center">
                      <p class="text-slate-500">成功率</p>
                      <p class="font-semibold text-slate-900">{{ (metric.success_rate * 100).toFixed(1) }}%</p>
                    </div>
                    <div class="bg-slate-50 rounded-lg p-2 text-center">
                      <p class="text-slate-500">平均耗时</p>
                      <p class="font-semibold text-slate-900">{{ metric.avg_duration?.toFixed(1) || 0 }}s</p>
                    </div>
                    <div class="bg-slate-50 rounded-lg p-2 text-center">
                      <p class="text-slate-500">活跃状态</p>
                      <p class="font-semibold" :class="metric.is_active ? 'text-emerald-600' : 'text-slate-400'">
                        {{ metric.is_active ? '在线' : '离线' }}
                      </p>
                    </div>
                  </div>
                </div>
                <div v-if="agentMetrics.length === 0" class="text-center text-slate-500 py-8">
                  暂无智能体指标                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'trace'" class="space-y-6">
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-1 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div class="px-5 py-4 border-b border-slate-200 bg-slate-50">
                <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                  <Activity :size="20" class="text-indigo-600" />
                  追踪记录
                </h2>
              </div>
              <div class="divide-y divide-slate-100 max-h-[600px] overflow-y-auto">
                <div
                  v-for="trace in traces"
                  :key="trace.trace_id"
                  @click="selectTrace(trace)"
                  :class="[
                    'p-4 cursor-pointer hover:bg-slate-50 transition-colors',
                    selectedTrace?.trace_id === trace.trace_id ? 'bg-indigo-50' : ''
                  ]"
                >
                  <div class="flex items-center justify-between mb-2">
                    <span :class="[
                      'px-2 py-0.5 rounded-full text-xs font-medium',
                      trace.status === 'completed' ? 'bg-emerald-100 text-emerald-700' :
                      trace.status === 'failed' ? 'bg-red-100 text-red-700' :
                      'bg-blue-100 text-blue-700'
                    ]">
                      {{ trace.status === 'completed' ? '成功' : trace.status === 'failed' ? '失败' : '运行中' }}
                    </span>
                    <span class="text-xs text-slate-400">{{ formatTime(trace.created_at) }}</span>
                  </div>
                  <p class="text-sm text-slate-700 mb-1 truncate">{{ trace.user_query }}</p>
                  <p class="text-xs text-slate-500">{{ trace.agent_type }} · {{ (trace.total_time || 0).toFixed(1) }}s</p>
                </div>
                <div v-if="traces.length === 0" class="p-8 text-center text-slate-500">
                  暂无追踪记录
                </div>
              </div>
            </div>

            <div class="lg:col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div class="px-5 py-4 border-b border-slate-200 bg-slate-50">
                <div class="flex items-center justify-between">
                  <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                    <Network :size="20" class="text-indigo-600" />
                    执行流程
                  </h2>
                  <div v-if="selectedTrace" class="flex items-center gap-2">
                    <span class="text-sm text-slate-500">{{ selectedTrace.events?.length || 0 }} 步骤</span>
                  </div>
                </div>
              </div>
              <div class="p-5">
                <div v-if="selectedTrace && selectedTrace.events?.length" class="space-y-3">
                  <div
                    v-for="(event, index) in selectedTrace.events"
                    :key="index"
                    :class="[
                      'flex items-start gap-3 p-3 rounded-lg border',
                      stepTypeColors[event.event_type as keyof typeof stepTypeColors]
                    ]"
                  >
                    <component
                      :is="stepTypeIcons[event.event_type as keyof typeof stepTypeIcons]"
                      :size="16"
                      class="mt-0.5 flex-shrink-0"
                    />
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 mb-1">
                        <span class="font-medium text-sm">{{ event.event_type }}</span>
                        <span class="text-xs text-slate-500">{{ formatTime(event.timestamp) }}</span>
                      </div>
                      <p class="text-sm text-slate-700 line-clamp-2">{{ event.content }}</p>
                    </div>
                  </div>
                </div>
                <div v-else-if="selectedTrace" class="flex items-center justify-center h-96 text-slate-400">
                  <div class="text-center">
                    <Activity :size="48" class="mx-auto mb-3 opacity-50" />
                    <p>这条追踪暂无步骤详情</p>
                  </div>
                </div>
                <div v-else class="flex items-center justify-center h-96 text-slate-400">
                  <div class="text-center">
                    <Activity :size="48" class="mx-auto mb-3 opacity-50" />
                    <p>选择一个追踪记录查看详情</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="visualizationData" class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-200 bg-slate-50">
              <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                <Network :size="20" class="text-indigo-600" />
                可视化流程图
              </h2>
            </div>
            <div ref="flowChartContainer" class="h-[500px] bg-slate-50" />
          </div>
        </div>

        <div v-if="activeTab === 'history'" class="space-y-6">
          <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="px-5 py-4 border-b border-slate-200 bg-slate-50">
              <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                <History :size="20" class="text-indigo-600" />
                历史任务管道
              </h2>
            </div>
            <div class="overflow-x-auto">
              <table class="w-full">
                <thead class="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th class="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">会话ID</th>
                    <th class="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">查询</th>
                    <th class="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">状态</th>
                    <th class="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">任务</th>
                    <th class="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">创建时间</th>
                    <th class="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">耗时</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr
                    v-for="pipeline in pipelineHistory"
                    :key="pipeline.pipeline_id"
                    class="hover:bg-slate-50 transition-colors"
                  >
                    <td class="px-5 py-4 whitespace-nowrap text-sm text-slate-600 font-mono">{{ pipeline.session_id?.substring(0, 8) }}</td>
                    <td class="px-5 py-4 text-sm text-slate-700 max-w-xs truncate">{{ pipeline.query }}</td>
                    <td class="px-5 py-4 whitespace-nowrap">
                      <span :class="[
                        'px-2.5 py-1 rounded-full text-xs font-medium',
                        `bg-${stateLabels[pipeline.state]?.color}-100 text-${stateLabels[pipeline.state]?.color}-700`
                      ]">
                        {{ stateLabels[pipeline.state]?.text || pipeline.state }}
                      </span>
                    </td>
                    <td class="px-5 py-4 whitespace-nowrap text-sm text-slate-600">{{ pipeline.tasks?.length || 0 }}</td>
                    <td class="px-5 py-4 whitespace-nowrap text-sm text-slate-600">{{ formatTime(pipeline.created_at) }}</td>
                    <td class="px-5 py-4 whitespace-nowrap text-sm text-slate-600">
                      {{ formatDuration((new Date(pipeline.updated_at).getTime() - new Date(pipeline.created_at).getTime()) / 1000) }}
                    </td>
                  </tr>
                  <tr v-if="pipelineHistory.length === 0">
                    <td colspan="6" class="px-5 py-12 text-center text-slate-500">
                      暂无历史记录
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'langsmith'" class="space-y-6">
          <div v-if="langSmithLoading" class="flex items-center justify-center h-64">
            <Loader2 :size="32" class="animate-spin text-indigo-500" />
          </div>

          <div v-else-if="langSmithError" class="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {{ langSmithError }}
          </div>

          <div v-else>
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-3">
                <div :class="[
                  'w-3 h-3 rounded-full',
                  langSmithStatus?.enabled ? 'bg-emerald-500 animate-pulse' : 'bg-gray-400'
                ]" />
                <span class="text-lg font-semibold text-slate-900">
                  {{ langSmithStatus?.enabled ? 'LangSmith 已启用' : 'LangSmith 未启用' }}
                </span>
              </div>
              <div class="flex items-center gap-2">
                <button
                  @click="openLangSmithDashboard"
                  :disabled="!langSmithDashboard?.dashboard_url"
                  class="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ExternalLink :size="16" />
                  <span>打开 LangSmith Dashboard</span>
                </button>
                <button
                  @click="showLangSmithConfig = true"
                  class="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                >
                  <Settings :size="16" />
                  <span>配置</span>
                </button>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
                <div class="flex items-center gap-3 mb-3">
                  <div class="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                    <Activity :size="20" class="text-indigo-600" />
                  </div>
                  <span class="text-sm font-medium text-slate-600">追踪总数</span>
                </div>
                <p class="text-3xl font-bold text-slate-900">{{ langSmithStats?.total_traces || 0 }}</p>
              </div>
              <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
                <div class="flex items-center gap-3 mb-3">
                  <div class="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
                    <Brain :size="20" class="text-emerald-600" />
                  </div>
                  <span class="text-sm font-medium text-slate-600">LLM 调用</span>
                </div>
                <p class="text-3xl font-bold text-slate-900">{{ langSmithStats?.total_llm_calls || 0 }}</p>
              </div>
              <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
                <div class="flex items-center gap-3 mb-3">
                  <div class="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                    <Cpu :size="20" class="text-purple-600" />
                  </div>
                  <span class="text-sm font-medium text-slate-600">工具调用</span>
                </div>
                <p class="text-3xl font-bold text-slate-900">{{ langSmithStats?.total_tool_calls || 0 }}</p>
              </div>
              <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
                <div class="flex items-center gap-3 mb-3">
                  <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
                    <Zap :size="20" class="text-amber-600" />
                  </div>
                  <span class="text-sm font-medium text-slate-600">活跃运行</span>
                </div>
                <p class="text-3xl font-bold text-slate-900">{{ langSmithStats?.active_runs || 0 }}</p>
              </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
              <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div class="px-5 py-4 border-b border-slate-200 bg-slate-50">
                  <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                    <Link2 :size="20" class="text-indigo-600" />
                    LangSmith 项目信息
                  </h2>
                </div>
                <div class="p-5 space-y-4">
                  <div class="flex items-center justify-between py-2 border-b border-slate-100">
                    <span class="text-sm text-slate-600">项目名称</span>
                    <span class="text-sm font-medium text-slate-900">{{ langSmithStatus?.project || '未配置' }}</span>
                  </div>
                  <div class="flex items-center justify-between py-2 border-b border-slate-100">
                    <span class="text-sm text-slate-600">API Key 配置</span>
                    <span :class="langSmithStatus?.api_key_configured ? 'text-emerald-600' : 'text-red-600'">
                      {{ langSmithStatus?.api_key_configured ? '已配置' : '未配置' }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between py-2 border-b border-slate-100">
                    <span class="text-sm text-slate-600">追踪状态</span>
                    <span :class="langSmithStatus?.tracing_enabled ? 'text-emerald-600' : 'text-red-600'">
                      {{ langSmithStatus?.tracing_enabled ? '已启用' : '已禁用' }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between py-2 border-b border-slate-100">
                    <span class="text-sm text-slate-600">客户端状态</span>
                    <span :class="langSmithStatus?.client_initialized ? 'text-emerald-600' : 'text-red-600'">
                      {{ langSmithStatus?.client_initialized ? '已初始化' : '未初始化' }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between py-2">
                    <span class="text-sm text-slate-600">最后检查</span>
                    <span class="text-sm text-slate-500">{{ langSmithStatus?.last_check ? formatTime(langSmithStatus.last_check) : '-' }}</span>
                  </div>
                </div>
              </div>

              <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div class="px-5 py-4 border-b border-slate-200 bg-slate-50">
                  <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                    <ExternalLink :size="20" class="text-indigo-600" />
                    快速链接
                  </h2>
                </div>
                <div class="p-5 space-y-3">
                  <a
                    v-if="langSmithDashboard?.dashboard_url"
                    :href="langSmithDashboard.dashboard_url"
                    target="_blank"
                    class="flex items-center justify-between p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                  >
                    <div class="flex items-center gap-3">
                      <ActivitySquare :size="18" class="text-indigo-600" />
                      <span class="text-sm font-medium text-slate-900">Dashboard</span>
                    </div>
                    <ExternalLink :size="14" class="text-slate-400" />
                  </a>
                  <a
                    v-if="langSmithDashboard?.project_url"
                    :href="langSmithDashboard.project_url"
                    target="_blank"
                    class="flex items-center justify-between p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                  >
                    <div class="flex items-center gap-3">
                      <Layers :size="18" class="text-purple-600" />
                      <span class="text-sm font-medium text-slate-900">项目页面</span>
                    </div>
                    <ExternalLink :size="14" class="text-slate-400" />
                  </a>
                  <a
                    v-if="langSmithDashboard?.traces_url"
                    :href="langSmithDashboard.traces_url"
                    target="_blank"
                    class="flex items-center justify-between p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                  >
                    <div class="flex items-center gap-3">
                      <Activity :size="18" class="text-emerald-600" />
                      <span class="text-sm font-medium text-slate-900">追踪记录</span>
                    </div>
                    <ExternalLink :size="14" class="text-slate-400" />
                  </a>
                  <a
                    v-if="langSmithDashboard?.datasets_url"
                    :href="langSmithDashboard.datasets_url"
                    target="_blank"
                    class="flex items-center justify-between p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                  >
                    <div class="flex items-center gap-3">
                      <Shield :size="18" class="text-amber-600" />
                      <span class="text-sm font-medium text-slate-900">数据集</span>
                    </div>
                    <ExternalLink :size="14" class="text-slate-400" />
                  </a>
                  <div v-if="!langSmithDashboard?.dashboard_url" class="text-center text-slate-500 py-4">
                    暂无链接可用
                  </div>
                </div>
              </div>
            </div>

            <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden mt-6">
              <div class="px-5 py-4 border-b border-slate-200 bg-slate-50">
                <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                  <Activity :size="20" class="text-indigo-600" />
                  最近追踪记录
                </h2>
              </div>
              <div class="divide-y divide-slate-100 max-h-[400px] overflow-y-auto">
                <div
                  v-for="trace in recentTraces"
                  :key="trace.run_id"
                  class="p-4 hover:bg-slate-50 transition-colors"
                >
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                      <span :class="[
                        'px-2.5 py-1 rounded-full text-xs font-medium',
                        trace.error ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'
                      ]">
                        {{ trace.run_type }}
                      </span>
                      <span class="font-medium text-slate-900">{{ trace.name }}</span>
                    </div>
                    <span class="text-xs text-slate-400">{{ formatTime(trace.created_at) }}</span>
                  </div>
                  <p v-if="trace.error" class="mt-2 text-sm text-red-600">{{ trace.error }}</p>
                  <div v-if="trace.tags?.length" class="mt-2 flex gap-2">
                    <span
                      v-for="tag in trace.tags"
                      :key="tag"
                      class="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs"
                    >
                      {{ tag }}
                    </span>
                  </div>
                </div>
                <div v-if="recentTraces.length === 0" class="p-8 text-center text-slate-500">
                  暂无追踪记录
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="activeTab === 'observability'" class="space-y-6">
          <ObservabilityPanel />
        </div>

        <div v-if="showLangSmithConfig" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
            <div class="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
                <Settings :size="20" class="text-indigo-600" />
                LangSmith 配置
              </h3>
              <button
                @click="showLangSmithConfig = false"
                class="text-slate-400 hover:text-slate-600 transition-colors"
              >
                <XCircle :size="20" />
              </button>
            </div>
            <div class="p-6 space-y-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-2">API Key</label>
                <input
                  v-model="langSmithConfigForm.api_key"
                  type="password"
                  placeholder="输入 LangSmith API Key"
                  class="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-2">项目名称</label>
                <input
                  v-model="langSmithConfigForm.project"
                  type="text"
                  placeholder="默认项目名称"
                  class="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                />
              </div>
              <div class="flex items-center gap-2">
                <input
                  v-model="langSmithConfigForm.tracing"
                  type="checkbox"
                  id="tracing-enabled"
                  class="w-4 h-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500"
                />
                <label for="tracing-enabled" class="text-sm font-medium text-slate-700">
                  启用追踪
                </label>
              </div>
            </div>
            <div class="px-6 py-4 border-t border-slate-200 flex items-center justify-end gap-3">
              <button
                @click="testLangSmithConnection"
                class="px-4 py-2 text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
              >
                测试连接
              </button>
              <button
                @click="showLangSmithConfig = false"
                class="px-4 py-2 text-slate-600 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
              >
                取消
              </button>
              <button
                @click="updateLangSmithConfig"
                class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              >
                保存配置
              </button>
            </div>
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
</style>
