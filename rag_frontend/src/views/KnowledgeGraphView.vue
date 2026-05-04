<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { knowledgeGraphApi } from '@/api/knowledge-graph'
import type { KnowledgeGraphEntity, KnowledgeGraphRelation } from '@/api/knowledge-graph'
import {
  Network,
  Search,
  Plus,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Move,
  Trash2,
  Loader2,
  AlertCircle,
  CheckCircle,
  Globe
} from 'lucide-vue-next'
import * as d3 from 'd3'

const SESSION_KEY = 'knowledge_graph_state'

function saveSessionState() {
  const state = {
    activeTab: activeTab.value,
    inputText: inputText.value,
    searchQuery: searchQuery.value,
    entityName: entityName.value,
    buildResult: buildResult.value,
    error: error.value,
    success: success.value
  }
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(state))
}

function loadSessionState() {
  const saved = sessionStorage.getItem(SESSION_KEY)
  if (saved) {
    try {
      const state = JSON.parse(saved)
      activeTab.value = state.activeTab || 'build'
      inputText.value = state.inputText || ''
      searchQuery.value = state.searchQuery || ''
      entityName.value = state.entityName || ''
      buildResult.value = state.buildResult || null
      error.value = state.error || ''
      success.value = state.success || ''
    } catch (e) {
      console.error('Failed to load session state:', e)
    }
  }
}

function clearSessionState() {
  sessionStorage.removeItem(SESSION_KEY)
  activeTab.value = 'build'
  inputText.value = ''
  searchQuery.value = ''
  entityName.value = ''
  buildResult.value = null
  searchResults.value = []
  queryResult.value = null
  error.value = ''
  success.value = ''
}

const knowledgeStore = useKnowledgeStore()

const activeTab = ref<'build' | 'query' | 'visualize' | 'overview'>('build')
const isLoading = ref(false)
const error = ref('')
const success = ref('')

const inputText = ref('')
const searchQuery = ref('')
const entityName = ref('')

const buildResult = ref<{
  entities: KnowledgeGraphEntity[]
  relations: KnowledgeGraphRelation[]
} | null>(null)

const searchResults = ref<any[]>([])
const queryResult = ref<any | null>(null)

const wholeGraphData = ref<{
  nodes: any[]
  edges: any[]
} | null>(null)
const wholeGraphLimit = ref(50)
const graphContainer = ref<HTMLElement | null>(null)
const graphStats = ref<{ nodes: number; edges: number }>({ nodes: 0, edges: 0 })

const selectedKB = computed(() => knowledgeStore.selectedKnowledgeBase)

onMounted(async () => {
  await knowledgeStore.fetchKnowledgeBases()
  loadSessionState()
})

watch([activeTab, inputText, searchQuery, entityName, buildResult, error, success], () => {
  saveSessionState()
}, { deep: true })

async function handleBuildGraph() {
  if (!inputText.value.trim()) {
    error.value = '请输入文本内容'
    return
  }

  try {
    isLoading.value = true
    error.value = ''
    const result = await knowledgeGraphApi.build({
      text: inputText.value,
      extract_entities: true,
      extract_relations: true
    })

    const entities = result.entities || []
    const relations = result.relations || []
    buildResult.value = {
      entities: entities,
      relations: relations
    }
    if (!result.success) {
      error.value = result.message || '构建知识图谱失败'
    } else if (entities.length === 0) {
      success.value = '文本分析完成，但未提取到实体（请查看服务端日志）'
    } else {
      success.value = `成功提取 ${entities.length} 个实体和 ${relations.length} 个关系`
    }
  } catch (err: any) {
    error.value = err.message || '构建知识图谱失败'
  } finally {
    isLoading.value = false
  }
}

async function handleSearch() {
  if (!searchQuery.value.trim()) {
    error.value = '请输入搜索内容'
    return
  }

  try {
    isLoading.value = true
    error.value = ''
    const result = await knowledgeGraphApi.search({
      query: searchQuery.value,
      top_k: 10,
      vector_weight: 0.7,
      graph_weight: 0.3,
      use_graph: true
    })

    searchResults.value = result.results
    success.value = `找到 ${result.total_count} 个结果（向量检索: ${result.vector_results_count}，图检索: ${result.graph_results_count}）`
  } catch (err: any) {
    error.value = err.message || '搜索失败'
  } finally {
    isLoading.value = false
  }
}

async function handleQueryEntity() {
  if (!entityName.value.trim()) {
    error.value = '请输入实体名称'
    return
  }

  try {
    isLoading.value = true
    error.value = ''
    const result = await knowledgeGraphApi.queryEntity({
      entity_name: entityName.value,
      max_depth: 2,
      limit: 20
    })

    queryResult.value = result
    success.value = `找到实体 "${result.entity.name}" 及其相关关系`
  } catch (err: any) {
    error.value = err.message || '查询实体失败'
    queryResult.value = null
  } finally {
    isLoading.value = false
  }
}

function getEntityTypeColor(type: string): string {
  const colors: Record<string, string> = {
    'Company': 'bg-blue-100 text-blue-700 border-blue-300',
    'Person': 'bg-emerald-100 text-emerald-700 border-emerald-300',
    'Department': 'bg-cyan-100 text-cyan-700 border-cyan-300',
    'FinancialMetric': 'bg-amber-100 text-amber-700 border-amber-300',
    'FinancialReport': 'bg-amber-100 text-amber-700 border-amber-300',
    'Account': 'bg-amber-100 text-amber-700 border-amber-300',
    'Budget': 'bg-amber-100 text-amber-700 border-amber-300',
    'TaxType': 'bg-purple-100 text-purple-700 border-purple-300',
    'TaxPolicy': 'bg-purple-100 text-purple-700 border-purple-300',
    'TaxRate': 'bg-purple-100 text-purple-700 border-purple-300',
    'TaxExemption': 'bg-purple-100 text-purple-700 border-purple-300',
    'Contract': 'bg-rose-100 text-rose-700 border-rose-300',
    'LegalCase': 'bg-rose-100 text-rose-700 border-rose-300',
    'Regulation': 'bg-rose-100 text-rose-700 border-rose-300',
    'Clause': 'bg-rose-100 text-rose-700 border-rose-300',
    'Product': 'bg-teal-100 text-teal-700 border-teal-300',
    'Service': 'bg-teal-100 text-teal-700 border-teal-300',
    'Location': 'bg-green-100 text-green-700 border-green-300',
    'DatePeriod': 'bg-orange-100 text-orange-700 border-orange-300',
    'Event': 'bg-orange-100 text-orange-700 border-orange-300',
    'Technology': 'bg-indigo-100 text-indigo-700 border-indigo-300',
    'Entity': 'bg-gray-100 text-gray-700 border-gray-300',
    'default': 'bg-gray-100 text-gray-700 border-gray-300'
  }
  return colors[type] || colors.default
}

async function loadWholeGraph() {
  try {
    isLoading.value = true
    error.value = ''
    const result = await knowledgeGraphApi.visualize({
      max_depth: 1,
      limit: wholeGraphLimit.value
    })

    wholeGraphData.value = {
      nodes: result.nodes,
      edges: result.edges
    }
    graphStats.value = {
      nodes: result.nodes.length,
      edges: result.edges.length
    }
    success.value = `已加载图谱概览：${result.nodes.length} 个节点，${result.edges.length} 条边`

    nextTick(() => {
      renderGraph()
    })
  } catch (err: any) {
    error.value = err.message || '加载图谱概览失败'
    wholeGraphData.value = null
  } finally {
    isLoading.value = false
  }
}

let currentSvg: any = null
let currentSimulation: any = null
let currentZoom: any = null
let currentG: any = null
let currentNodes: any[] = []
let currentLinks: any[] = []
let currentLinkSel: any = null
let currentNodeSel: any = null

function renderGraph() {
  if (!graphContainer.value || !wholeGraphData.value) {
    return
  }

  if (currentSvg) {
    currentSvg.remove()
    currentSvg = null
  }
  if (currentSimulation) {
    currentSimulation.stop()
    currentSimulation = null
  }

  const container = graphContainer.value
  container.innerHTML = ''

  const width = container.clientWidth || 800
  const height = 500

  const svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .style('border', '1px solid #e5e7eb')
    .style('border-radius', '8px')
    .style('background', '#f9fafb')

  currentSvg = svg

  const g = svg.append('g')
  currentG = g

  const zoom = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
    })

  svg.call(zoom)
  currentZoom = zoom

  const nodes = wholeGraphData.value.nodes.map(n => ({ ...n }))
  const nodeIds = new Set(nodes.map(n => n.id))
  const edges = wholeGraphData.value.edges
    .filter((e: any) => e.source && e.target && nodeIds.has(String(e.source)) && nodeIds.has(String(e.target)))
    .map(e => ({ ...e }))

  const nodeMap = new Map(nodes.map(n => [n.id, n]))

  currentNodes = nodes
  currentLinks = edges

  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id((d: any) => d.id).distance(120))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(40))

  currentSimulation = simulation

  const linkSel = g.append('g')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('stroke', '#9ca3af')
    .attr('stroke-width', 1.5)
    .attr('marker-end', 'url(#arrowhead)')

  currentLinkSel = linkSel

  const nodeColors: Record<string, string> = {
    'Company': '#3b82f6',
    'Person': '#10b981',
    'Department': '#06b6d4',
    'FinancialMetric': '#f59e0b',
    'FinancialReport': '#f59e0b',
    'Account': '#f59e0b',
    'Budget': '#f59e0b',
    'TaxType': '#8b5cf6',
    'TaxPolicy': '#8b5cf6',
    'TaxRate': '#8b5cf6',
    'TaxExemption': '#8b5cf6',
    'Contract': '#e11d48',
    'LegalCase': '#e11d48',
    'Regulation': '#e11d48',
    'Clause': '#e11d48',
    'Product': '#14b8a6',
    'Service': '#14b8a6',
    'Location': '#22c55e',
    'DatePeriod': '#f97316',
    'Event': '#ef4444',
    'Technology': '#6366f1',
    'Entity': '#64748b',
    'default': '#64748b'
  }

  function getNodeColor(type: string): string {
    if (!type) return nodeColors.default
    // 兼容新旧类型名：COMPANY -> Company, TAX_TYPE -> TaxType, FINANCIAL_METRIC -> FinancialMetric
    const normalized = type
      .split('_')
      .map(s => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase())
      .join('')
    return nodeColors[normalized] || nodeColors.default
  }

  const nodeSel = g.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .call(d3.drag<SVGGElement, any>()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended) as any)

  currentNodeSel = nodeSel

  nodeSel.append('circle')
    .attr('r', 20)
    .attr('fill', d => getNodeColor(d.type))
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)

  nodeSel.append('text')
    .text(d => d.label.substring(0, 6))
    .attr('text-anchor', 'middle')
    .attr('dy', 35)
    .attr('font-size', '11px')
    .attr('fill', '#374151')

  nodeSel.append('title')
    .text(d => `${d.label}\n类型: ${d.type}`)

  svg.append('defs').append('marker')
    .attr('id', 'arrowhead')
    .attr('viewBox', '-0 -5 10 10')
    .attr('refX', 25)
    .attr('refY', 0)
    .attr('orient', 'auto')
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .append('path')
    .attr('d', 'M 0,-5 L 10,0 L 0,5')
    .attr('fill', '#9ca3af')

  simulation.on('tick', () => {
    linkSel
      .attr('x1', (d: any) => d.source.x)
      .attr('y1', (d: any) => d.source.y)
      .attr('x2', (d: any) => d.target.x)
      .attr('y2', (d: any) => d.target.y)

    nodeSel.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
  })

  function dragstarted(event: any) {
    if (!event.active) simulation.alphaTarget(0.3).restart()
    event.subject.fx = event.subject.x
    event.subject.fy = event.subject.y
  }

  function dragged(event: any) {
    event.subject.fx = event.x
    event.subject.fy = event.y
  }

  function dragended(event: any) {
    if (!event.active) simulation.alphaTarget(0)
    event.subject.fx = null
    event.subject.fy = null
  }
}

function resetView() {
  renderGraph()
}
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-6 py-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Network :size="28" class="text-emerald-600" />
            知识图谱
          </h1>
          <p class="text-sm text-gray-500 mt-1">构建、可视化和查询知识图谱</p>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex items-center justify-between mt-4">
        <div class="flex gap-4">
          <button
          @click="activeTab = 'build'"
          :class="[
            'px-4 py-2 font-medium rounded-lg transition-colors',
            activeTab === 'build'
              ? 'bg-emerald-100 text-emerald-600'
              : 'text-gray-600 hover:bg-gray-100'
          ]"
        >
          构建图谱
        </button>
        <button
          @click="activeTab = 'query'"
          :class="[
            'px-4 py-2 font-medium rounded-lg transition-colors',
            activeTab === 'query'
              ? 'bg-emerald-100 text-emerald-600'
              : 'text-gray-600 hover:bg-gray-100'
          ]"
        >
          查询实体
        </button>
        <button
          @click="activeTab = 'visualize'"
          :class="[
            'px-4 py-2 font-medium rounded-lg transition-colors',
            activeTab === 'visualize'
              ? 'bg-emerald-100 text-emerald-600'
              : 'text-gray-600 hover:bg-gray-100'
          ]"
        >
          混合检索
        </button>
        <button
          @click="activeTab = 'overview'"
          :class="[
            'px-4 py-2 font-medium rounded-lg transition-colors',
            activeTab === 'overview'
              ? 'bg-emerald-100 text-emerald-600'
              : 'text-gray-600 hover:bg-gray-100'
          ]"
        >
          图谱概览
        </button>
        </div>
        <button
          @click="clearSessionState"
          class="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
        >
          清除数据
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6">
      <!-- Error/Success Messages -->
      <div v-if="error" class="mb-4 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
        <AlertCircle :size="20" class="text-red-500" />
        <p class="text-sm text-red-700">{{ error }}</p>
      </div>

      <div v-if="success" class="mb-4 bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
        <CheckCircle :size="20" class="text-green-500" />
        <p class="text-sm text-green-700">{{ success }}</p>
      </div>

      <!-- Build Graph Tab -->
      <div v-if="activeTab === 'build'" class="space-y-6">
        <div class="bg-white rounded-xl border border-gray-200 p-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">从文本构建知识图谱</h2>
          <textarea
            v-model="inputText"
            rows="8"
            placeholder="请输入需要分析的文本内容，系统将自动提取实体和关系..."
            class="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none resize-none"
          />
          <div class="flex items-center justify-between mt-4">
            <p class="text-sm text-gray-500">支持从文档或对话中提取结构化知识</p>
            <button
              @click="handleBuildGraph"
              :disabled="isLoading"
              class="px-6 py-2.5 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Loader2 v-if="isLoading" :size="18" class="animate-spin" />
              <Plus v-else :size="18" />
              {{ isLoading ? '构建中...' : '构建图谱' }}
            </button>
          </div>
        </div>

        <!-- Build Results -->
        <div v-if="buildResult" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Entities -->
          <div class="bg-white rounded-xl border border-gray-200 p-6">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">提取的实体 ({{ buildResult.entities.length }})</h3>
            <div class="space-y-3 max-h-96 overflow-y-auto">
              <div
                v-for="entity in buildResult.entities"
                :key="entity.name"
                class="p-4 border border-gray-200 rounded-lg"
              >
                <div class="flex items-center gap-3 mb-2">
                  <span class="font-semibold text-gray-900">{{ entity.name }}</span>
                  <span :class="['px-2 py-0.5 text-xs font-medium rounded-full border', getEntityTypeColor(entity.type)]">
                    {{ entity.type }}
                  </span>
                </div>
                <div v-if="entity.properties && Object.keys(entity.properties).length > 0" class="text-sm text-gray-600">
                  <span v-for="(value, key) in entity.properties" :key="key" class="inline-block mr-3">
                    <span class="text-gray-500">{{ key }}:</span> {{ value }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Relations -->
          <div class="bg-white rounded-xl border border-gray-200 p-6">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">提取的关系 ({{ buildResult.relations.length }})</h3>
            <div class="space-y-3 max-h-96 overflow-y-auto">
              <div
                v-for="(relation, index) in buildResult.relations"
                :key="index"
                class="p-4 border border-gray-200 rounded-lg flex items-center gap-3"
              >
                <span class="font-medium text-emerald-600">{{ relation.source }}</span>
                <span class="text-gray-400">→</span>
                <span class="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs font-medium rounded">
                  {{ relation.type }}
                </span>
                <span class="text-gray-400">→</span>
                <span class="font-medium text-teal-600">{{ relation.target }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Query Entity Tab -->
      <div v-if="activeTab === 'query'" class="space-y-6">
        <div class="bg-white rounded-xl border border-gray-200 p-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">查询实体及关系</h2>
          <div class="flex gap-4">
            <input
              v-model="entityName"
              type="text"
              placeholder="输入实体名称，如：苹果公司"
              class="flex-1 px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
              @keydown.enter="handleQueryEntity"
            />
            <button
              @click="handleQueryEntity"
              :disabled="isLoading"
              class="px-6 py-3 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Loader2 v-if="isLoading" :size="18" class="animate-spin" />
              <Search v-else :size="18" />
              {{ isLoading ? '查询中...' : '查询' }}
            </button>
          </div>
        </div>

        <!-- Query Result -->
        <div v-if="queryResult" class="bg-white rounded-xl border border-gray-200 p-6">
          <h3 class="text-lg font-semibold text-gray-900 mb-4">
            实体详情：{{ queryResult.entity.name }}
          </h3>
          <div class="space-y-6">
            <!-- Entity Info -->
            <div class="p-4 bg-gray-50 rounded-lg">
              <span :class="['px-3 py-1 text-sm font-medium rounded-full border', getEntityTypeColor(queryResult.entity.type)]">
                {{ queryResult.entity.type }}
              </span>
              <div v-if="queryResult.entity.properties && Object.keys(queryResult.entity.properties).length > 0" class="mt-3 grid grid-cols-2 gap-4">
                <div v-for="(value, key) in queryResult.entity.properties" :key="key" class="text-sm">
                  <span class="text-gray-500">{{ key }}:</span>
                  <span class="ml-2 text-gray-900">{{ value }}</span>
                </div>
              </div>
            </div>

            <!-- Relations -->
            <div>
              <h4 class="text-md font-medium text-gray-900 mb-3">相关关系</h4>
              <div class="space-y-3">
                <div
                  v-for="(rel, index) in queryResult.relations"
                  :key="index"
                  class="p-4 border border-gray-200 rounded-lg"
                >
                  <div class="flex items-center gap-3 mb-2">
                    <span class="font-semibold text-gray-900">{{ queryResult.entity.name }}</span>
                    <span class="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-medium rounded">
                      {{ rel.relation }}
                    </span>
                    <span class="font-semibold text-gray-900">{{ rel.target.name }}</span>
                  </div>
                  <div class="text-sm text-gray-600">
                    <span :class="['px-2 py-0.5 text-xs font-medium rounded-full border', getEntityTypeColor(rel.target.type)]">
                      {{ rel.target.type }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Hybrid Search Tab -->
      <div v-if="activeTab === 'visualize'" class="space-y-6">
        <div class="bg-white rounded-xl border border-gray-200 p-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">混合检索（向量 + 图谱）</h2>
          <div class="flex gap-4">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="输入查询内容..."
              class="flex-1 px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
              @keydown.enter="handleSearch"
            />
            <button
              @click="handleSearch"
              :disabled="isLoading"
              class="px-6 py-3 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Loader2 v-if="isLoading" :size="18" class="animate-spin" />
              <Search v-else :size="18" />
              {{ isLoading ? '搜索中...' : '搜索' }}
            </button>
          </div>
        </div>

        <!-- Search Results -->
        <div v-if="searchResults.length > 0" class="space-y-4">
          <div
            v-for="(result, index) in searchResults"
            :key="index"
            class="bg-white rounded-xl border border-gray-200 p-6"
          >
            <div class="flex items-start justify-between mb-3">
              <div class="flex items-center gap-2">
                <span
                  :class="[
                    'px-2 py-1 text-xs font-medium rounded',
                    result.source === 'vector'
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-teal-100 text-teal-700'
                  ]"
                >
                  {{ result.source === 'vector' ? '向量检索' : '图谱检索' }}
                </span>
                <span class="text-sm text-gray-500">相似度: {{ (result.score * 100).toFixed(1) }}%</span>
              </div>
            </div>
            <p class="text-gray-900 mb-3">{{ result.content }}</p>
            <div v-if="result.metadata" class="text-sm text-gray-500">
              <span v-if="result.metadata.document" class="mr-4">
                文档: {{ result.metadata.document }}
              </span>
              <span v-if="result.metadata.entity">
                实体: {{ result.metadata.entity }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Graph Overview Tab -->
      <div v-if="activeTab === 'overview'" class="space-y-6">
        <div class="bg-white rounded-xl border border-gray-200 p-6">
          <h2 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Globe :size="20" class="text-emerald-600" />
            图谱概览
          </h2>
          <div class="flex gap-4 items-center">
            <div class="flex items-center gap-2">
              <label class="text-sm text-gray-600">节点数量：</label>
              <select
                v-model="wholeGraphLimit"
                class="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
              >
                <option :value="20">20</option>
                <option :value="50">50</option>
                <option :value="100">100</option>
                <option :value="200">200</option>
              </select>
            </div>
            <button
              @click="loadWholeGraph"
              :disabled="isLoading"
              class="px-6 py-2.5 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Loader2 v-if="isLoading" :size="18" class="animate-spin" />
              <Globe v-else :size="18" />
              {{ isLoading ? '加载中...' : '查看全图' }}
            </button>
          </div>
          <p class="text-sm text-gray-500 mt-3">查看 Neo4j 图数据库中的实体和关系分布（采样显示）</p>
        </div>

        <!-- Graph Stats -->
        <div v-if="graphStats.nodes > 0" class="grid grid-cols-2 gap-4">
          <div class="bg-white rounded-xl border border-gray-200 p-6 text-center">
            <div class="text-3xl font-bold text-emerald-600">{{ graphStats.nodes }}</div>
            <div class="text-sm text-gray-500 mt-1">节点数</div>
          </div>
          <div class="bg-white rounded-xl border border-gray-200 p-6 text-center">
            <div class="text-3xl font-bold text-teal-600">{{ graphStats.edges }}</div>
            <div class="text-sm text-gray-500 mt-1">边数</div>
          </div>
        </div>

        <!-- Graph Visualization -->
        <div v-if="wholeGraphData" class="bg-white rounded-xl border border-gray-200 p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-gray-900">图可视化</h3>
            <button
              @click="resetView"
              class="px-4 py-2 text-sm bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200 flex items-center gap-2"
            >
              <Move :size="16" />
              聚拢重置
            </button>
          </div>
          <div class="flex flex-wrap gap-3 mb-4 text-sm text-gray-500">
            <span>🔵 Company</span>
            <span>🟢 Person</span>
            <span>🟣 TaxType/Policy</span>
            <span>🔴 Contract</span>
            <span>🟠 FinancialMetric</span>
            <span>🟡 Location</span>
            <span>⚫ 其他</span>
          </div>
          <div ref="graphContainer" class="w-full h-[500px]"></div>
          <p class="text-xs text-gray-400 mt-2">拖拽节点可移动，滚轮可缩放</p>
        </div>

        <!-- Node List -->
        <div v-if="wholeGraphData && wholeGraphData.nodes.length > 0" class="bg-white rounded-xl border border-gray-200 p-6">
          <h3 class="text-lg font-semibold text-gray-900 mb-4">节点列表</h3>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-96 overflow-y-auto">
            <div
              v-for="node in wholeGraphData.nodes"
              :key="node.id"
              class="p-3 border border-gray-200 rounded-lg hover:bg-gray-50"
            >
              <div class="flex items-center gap-2">
                <span class="font-medium text-gray-900">{{ node.label }}</span>
              </div>
              <span :class="['px-2 py-0.5 text-xs font-medium rounded-full border mt-1 inline-block', getEntityTypeColor(node.type)]">
                {{ node.type }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
