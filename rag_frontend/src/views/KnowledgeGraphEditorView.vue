<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { knowledgeGraphApi } from '@/api/knowledge-graph'
import {
  Network,
  Plus,
  Search,
  RefreshCw,
  Trash2,
  Edit3,
  Save,
  X,
  Download,
  Upload,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Move,
  GitBranch,
  GitMerge,
  ChevronRight,
  AlertCircle,
  CheckCircle,
  Loader2,
  Eye,
  EyeOff,
  MoreVertical,
  Copy,
  Link,
  ArrowLeft,
  HelpCircle,
  BookOpen,
  MousePointer,
  ZoomIn as ZoomInIcon,
  Layers,
  Sparkles
} from 'lucide-vue-next'
import * as d3 from 'd3'

interface GraphNode {
  id: string
  name: string
  type: string
  properties?: Record<string, any>
  x?: number
  y?: number
  fx?: number | null
  fy?: number | null
}

interface GraphEdge {
  id: string
  source: string | GraphNode
  target: string | GraphNode
  type: string
  properties?: Record<string, any>
}

const isLoading = ref(false)
const isSaving = ref(false)
const error = ref('')
const success = ref('')
const activeTab = ref<'build' | 'edit' | 'visualize'>('edit')

const graphData = ref<{
  nodes: GraphNode[]
  edges: GraphEdge[]
}>({ nodes: [], edges: [] })

const selectedNode = ref<GraphNode | null>(null)
const selectedEdge = ref<GraphEdge | null>(null)

const searchQuery = ref('')
const centerEntity = ref('')
const maxDepth = ref(2)
const nodeLimit = ref(50)

const showLabels = ref(true)
const showProperties = ref(true)
const highlightedNodes = ref<Set<string>>(new Set())

const graphContainer = ref<HTMLElement | null>(null)
const simulation = ref<any>(null)
const graphSvg = ref<any>(null)
const graphZoom = ref<any>(null)
const simulationNodes = ref<GraphNode[]>([])

const editMode = ref(false)
const showHelp = ref(false)
const hasUnsavedChanges = ref(false)
const deletedNodeIds = ref<string[]>([])
const deletedEdgeIds = ref<string[]>([])
const importFileInput = ref<HTMLInputElement | null>(null)
const newNodeName = ref('')
const newNodeType = ref('COMPANY')
const newEdgeSource = ref('')
const newEdgeTarget = ref('')
const newEdgeType = ref('RELATED_TO')

const nodeTypes = [
  { value: 'COMPANY', label: '公司', color: '#3b82f6' },
  { value: 'PERSON', label: '人物', color: '#10b981' },
  { value: 'DEPARTMENT', label: '部门', color: '#06b6d4' },
  { value: 'FINANCIAL_METRIC', label: '财务指标', color: '#f59e0b' },
  { value: 'FINANCIAL_REPORT', label: '财务报表', color: '#f59e0b' },
  { value: 'ACCOUNT', label: '账户', color: '#f59e0b' },
  { value: 'BUDGET', label: '预算', color: '#f59e0b' },
  { value: 'TAX_TYPE', label: '税种', color: '#8b5cf6' },
  { value: 'TAX_POLICY', label: '税收政策', color: '#8b5cf6' },
  { value: 'TAX_RATE', label: '税率', color: '#8b5cf6' },
  { value: 'TAX_EXEMPTION', label: '税收优惠', color: '#8b5cf6' },
  { value: 'CONTRACT', label: '合同', color: '#e11d48' },
  { value: 'LEGAL_CASE', label: '案件', color: '#e11d48' },
  { value: 'REGULATION', label: '法规', color: '#e11d48' },
  { value: 'CLAUSE', label: '条款', color: '#e11d48' },
  { value: 'PRODUCT', label: '产品', color: '#14b8a6' },
  { value: 'SERVICE', label: '服务', color: '#14b8a6' },
  { value: 'LOCATION', label: '地点', color: '#22c55e' },
  { value: 'DATE_PERIOD', label: '日期/期间', color: '#f97316' },
  { value: 'EVENT', label: '事件', color: '#ef4444' },
  { value: 'TECHNOLOGY', label: '技术/专利', color: '#6366f1' },
]

const edgeTypes = [
  { value: 'WORKS_AT', label: '工作于（人→公司）' },
  { value: 'MANAGED_BY', label: '由...管理' },
  { value: 'BELONGS_TO', label: '属于' },
  { value: 'PARTNER_WITH', label: '合作' },
  { value: 'COMPETES_WITH', label: '竞争' },
  { value: 'SUBSIDIARY_OF', label: '子公司' },
  { value: 'SUPPLIER_OF', label: '供应商' },
  { value: 'CUSTOMER_OF', label: '客户' },
  { value: 'INVESTED_IN', label: '投资' },
  { value: 'OWNS', label: '持有' },
  { value: 'HAS_METRIC', label: '有财务指标' },
  { value: 'REPORTED_IN', label: '体现在报表' },
  { value: 'AUDITED_BY', label: '由...审计' },
  { value: 'SUBJECT_TO', label: '适用税种' },
  { value: 'HAS_RATE', label: '税率为' },
  { value: 'ELIGIBLE_FOR', label: '符合优惠' },
  { value: 'CLAIMED', label: '已申报' },
  { value: 'SIGNED', label: '签署合同' },
  { value: 'GOVERNS', label: '管辖/适用' },
  { value: 'VIOLATES', label: '违反' },
  { value: 'CONTAINS_CLAUSE', label: '包含条款' },
  { value: 'EFFECTIVE_PERIOD', label: '有效期' },
  { value: 'LOCATED_AT', label: '位于' },
  { value: 'PRODUCES', label: '生产/提供' },
  { value: 'USES', label: '使用技术' },
  { value: 'RELATED_TO', label: '相关（通用）' },
]

const filteredNodes = computed(() => {
  if (!searchQuery.value.trim()) return graphData.value.nodes
  const query = searchQuery.value.toLowerCase()
  return graphData.value.nodes.filter(
    n => n.name.toLowerCase().includes(query) ||
         n.type.toLowerCase().includes(query)
  )
})

function getNodeColor(type: string): string {
  // 直接匹配（新格式：COMPANY, TAX_TYPE 等）
  const nodeType = nodeTypes.find(t => t.value === type)
  if (nodeType) return nodeType.color
  // 兼容旧格式（Person, Organization 等）- 转大写后重试
  const upperType = type.toUpperCase().replace(/\s+/g, '_')
  const fallback = nodeTypes.find(t => t.value === upperType)
  return fallback?.color || '#64748b'
}

function getEdgeEndpointId(endpoint: string | GraphNode): string {
  return typeof endpoint === 'object' ? endpoint.id : endpoint
}

function markDirty() {
  hasUnsavedChanges.value = true
}

async function loadGraph() {
  if (!centerEntity.value.trim()) {
    error.value = '请输入中心实体名称'
    return
  }

  try {
    isLoading.value = true
    error.value = ''
    const result = await knowledgeGraphApi.visualize({
      entity_name: centerEntity.value,
      max_depth: maxDepth.value,
      limit: nodeLimit.value
    })

    graphData.value = {
      nodes: result.nodes.map((n: any) => ({
        id: n.id,
        name: n.label,
        type: n.type,
        properties: n.properties
      })),
      edges: result.edges.map((e: any) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type,
        properties: e.properties
      }))
    }

    success.value = `成功加载图谱：${graphData.value.nodes.length} 个节点，${graphData.value.edges.length} 条边`
    deletedNodeIds.value = []
    deletedEdgeIds.value = []
    hasUnsavedChanges.value = false
    await nextTick()
    drawGraph()
  } catch (err: any) {
    error.value = err.message || '加载图谱失败'
  } finally {
    isLoading.value = false
  }
}

function drawGraph() {
  if (!graphContainer.value || graphData.value.nodes.length === 0) return

  if (simulation.value) {
    simulation.value.stop()
  }

  const container = graphContainer.value
  container.innerHTML = ''

  const width = container.clientWidth || 800
  const height = container.clientHeight || 600

  const svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('class', 'knowledge-graph-svg')

  const g = svg.append('g')
  graphSvg.value = svg

  const zoom = d3.zoom()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
    })

  svg.call(zoom as any)
  svg.on('dblclick.zoom', null)
  graphZoom.value = zoom

  const nodes = graphData.value.nodes
  simulationNodes.value = nodes
  const edges = graphData.value.edges.map(e => ({
    ...e,
    source: nodes.find(n => n.id === getEdgeEndpointId(e.source) || n.name === getEdgeEndpointId(e.source)),
    target: nodes.find(n => n.id === getEdgeEndpointId(e.target) || n.name === getEdgeEndpointId(e.target))
  })).filter(e => e.source && e.target)

  simulation.value = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id((d: any) => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(40))

  const link = g.selectAll('.link')
    .data(edges)
    .enter()
    .append('g')
    .attr('class', 'link')
    .attr('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      selectEdge(d)
    })

  const linkLine = link.append('line')
    .attr('class', 'edge-line')
    .attr('stroke', '#94a3b8')
    .attr('stroke-width', 2)
    .attr('stroke-opacity', 0.6)

  const linkText = link.append('text')
    .attr('class', 'edge-label')
    .attr('fill', '#64748b')
    .attr('font-size', '10px')
    .attr('text-anchor', 'middle')
    .attr('dy', -5)
    .text((d: any) => showLabels.value ? d.type : '')

  const nodeGroup = g.selectAll('.node')
    .data(nodes)
    .enter()
    .append('g')
    .attr('class', 'node')
    .attr('cursor', 'pointer')
    .call(d3.drag<any, any>()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended)
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      selectNode(d)
    })

  nodeGroup.append('circle')
    .attr('r', 20)
    .attr('fill', (d: any) => getNodeColor(d.type))
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)
    .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))')

  nodeGroup.append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', 4)
    .attr('fill', '#fff')
    .attr('font-size', '10px')
    .attr('font-weight', '600')
    .text((d: any) => d.name.slice(0, 2))

  const nodeLabel = nodeGroup.append('text')
    .attr('class', 'node-label')
    .attr('text-anchor', 'middle')
    .attr('dy', 38)
    .attr('fill', '#374151')
    .attr('font-size', '12px')
    .text((d: any) => showLabels.value ? d.name : '')

  simulation.value.on('tick', () => {
    linkLine
      .attr('x1', (d: any) => d.source.x)
      .attr('y1', (d: any) => d.source.y)
      .attr('x2', (d: any) => d.target.x)
      .attr('y2', (d: any) => d.target.y)

    linkText
      .attr('x', (d: any) => (d.source.x + d.target.x) / 2)
      .attr('y', (d: any) => (d.source.y + d.target.y) / 2)

    nodeGroup.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
  })

  function dragstarted(event: any, d: any) {
    if (!event.active) simulation.value.alphaTarget(0.3).restart()
    d.fx = d.x
    d.fy = d.y
  }

  function dragged(event: any, d: any) {
    d.fx = event.x
    d.fy = event.y
  }

  function dragended(event: any, d: any) {
    if (!event.active) simulation.value.alphaTarget(0)
    d.fx = null
    d.fy = null
  }
}

function selectNode(node: GraphNode) {
  selectedNode.value = node
  selectedEdge.value = null
  highlightedNodes.value = new Set([node.id])
  highlightConnectedNodes(node.id)
}

function selectEdge(edge: GraphEdge) {
  selectedEdge.value = edge
  selectedNode.value = null
  highlightedNodes.value = new Set([
    getEdgeEndpointId(edge.source),
    getEdgeEndpointId(edge.target)
  ])
}

function highlightConnectedNodes(nodeId: string) {
  graphData.value.edges.forEach(edge => {
    const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source
    const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target
    if (sourceId === nodeId) {
      highlightedNodes.value.add(targetId)
    } else if (targetId === nodeId) {
      highlightedNodes.value.add(sourceId)
    }
  })
}

function clearSelection() {
  selectedNode.value = null
  selectedEdge.value = null
  highlightedNodes.value.clear()
}

function zoomIn() {
  if (!graphSvg.value || !graphZoom.value) return
  graphSvg.value.transition().call(graphZoom.value.scaleBy as any, 1.3)
}

function zoomOut() {
  if (!graphSvg.value || !graphZoom.value) return
  graphSvg.value.transition().call(graphZoom.value.scaleBy as any, 0.7)
}

function resetZoom() {
  if (!graphSvg.value || !graphZoom.value) return
  graphSvg.value.transition().call(graphZoom.value.transform as any, d3.zoomIdentity)
}

function fitToScreen() {
  if (!graphContainer.value || !graphSvg.value || !graphZoom.value || simulationNodes.value.length === 0) return
  const width = graphContainer.value.clientWidth || 800
  const height = graphContainer.value.clientHeight || 600
  const positionedNodes = simulationNodes.value.filter(n => Number.isFinite(n.x) && Number.isFinite(n.y))
  if (positionedNodes.length === 0) return
  const bounds = {
    minX: Math.min(...positionedNodes.map(n => n.x || 0)) - 50,
    maxX: Math.max(...positionedNodes.map(n => n.x || 0)) + 50,
    minY: Math.min(...positionedNodes.map(n => n.y || 0)) - 50,
    maxY: Math.max(...positionedNodes.map(n => n.y || 0)) + 50
  }
  const fullWidth = bounds.maxX - bounds.minX
  const fullHeight = bounds.maxY - bounds.minY
  const scale = Math.min(1.5, Math.max(0.1, Math.min(width / fullWidth, height / fullHeight) * 0.9))
  const translate = [
    width / 2 - scale * (bounds.minX + fullWidth / 2),
    height / 2 - scale * (bounds.minY + fullHeight / 2)
  ]
  graphSvg.value.transition().call(
    graphZoom.value.transform as any,
    d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale)
  )
}

function exportGraph() {
  const data = {
    nodes: graphData.value.nodes,
    edges: graphData.value.edges.map(e => ({
      id: e.id,
      source: getEdgeEndpointId(e.source),
      target: getEdgeEndpointId(e.target),
      type: e.type,
      properties: e.properties || {}
    }))
  }
  const dataStr = JSON.stringify(data, null, 2)
  const dataBlob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(dataBlob)
  const link = document.createElement('a')
  link.href = url
  link.download = `knowledge-graph-${Date.now()}.json`
  link.click()
  URL.revokeObjectURL(url)
}

async function saveGraph() {
  if (graphData.value.nodes.length === 0) {
    error.value = '当前没有可保存的图谱数据'
    return
  }

  try {
    isSaving.value = true
    error.value = ''
    const result = await knowledgeGraphApi.importGraph({
      nodes: graphData.value.nodes.map(node => ({
        id: node.id,
        label: node.name,
        type: node.type,
        properties: node.properties || {}
      })),
      edges: graphData.value.edges.map(edge => ({
        id: edge.id,
        source: getEdgeEndpointId(edge.source),
        target: getEdgeEndpointId(edge.target),
        type: edge.type,
        properties: edge.properties || {},
        description: (edge as any).description || undefined
      })),
      deleted_node_ids: deletedNodeIds.value,
      deleted_edge_ids: deletedEdgeIds.value
    })

    if (!result.success && result.errors.length > 0) {
      error.value = result.errors.slice(0, 3).join('；')
      return
    }

    deletedNodeIds.value = []
    deletedEdgeIds.value = []
    hasUnsavedChanges.value = false
    success.value = `已保存 ${result.nodes_saved} 个节点、${result.edges_saved} 条关系`
  } catch (err: any) {
    error.value = err.message || '保存图谱失败'
  } finally {
    isSaving.value = false
  }
}

function triggerImport() {
  importFileInput.value?.click()
}

function importGraphFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = () => {
    try {
      const parsed = JSON.parse(String(reader.result || '{}'))
      const nodes = Array.isArray(parsed.nodes) ? parsed.nodes : []
      const edges = Array.isArray(parsed.edges) ? parsed.edges : []
      graphData.value = {
        nodes: nodes.map((node: any, index: number) => ({
          id: String(node.id || `import_node_${Date.now()}_${index}`),
          name: String(node.name || node.label || '').trim(),
          type: String(node.type || 'Entity'),
          properties: node.properties || {}
        })).filter((node: GraphNode) => node.name),
        edges: edges.map((edge: any, index: number) => ({
          id: String(edge.id || `import_edge_${Date.now()}_${index}`),
          source: String(edge.source || ''),
          target: String(edge.target || ''),
          type: String(edge.type || 'related_to'),
          properties: edge.properties || {}
        })).filter((edge: GraphEdge) => edge.source && edge.target)
      }
      deletedNodeIds.value = []
      deletedEdgeIds.value = []
      clearSelection()
      markDirty()
      drawGraph()
      success.value = 'JSON 图谱已导入到编辑器'
    } catch (err: any) {
      error.value = err.message || '导入 JSON 失败'
    } finally {
      input.value = ''
    }
  }
  reader.readAsText(file)
}

function addNode() {
  if (!newNodeName.value.trim()) {
    error.value = '请输入节点名称'
    return
  }
  const newNode: GraphNode = {
    id: `node_${Date.now()}`,
    name: newNodeName.value.trim(),
    type: newNodeType.value,
    properties: {}
  }
  graphData.value.nodes.push(newNode)
  newNodeName.value = ''
  editMode.value = false
  markDirty()
  drawGraph()
}

function deleteNode(nodeId: string) {
  if (/^\d+$/.test(nodeId) && !deletedNodeIds.value.includes(nodeId)) {
    deletedNodeIds.value.push(nodeId)
  }
  graphData.value.edges.forEach(edge => {
    const edgeId = edge.id
    if (
      /^\d+$/.test(edgeId) &&
      (getEdgeEndpointId(edge.source) === nodeId || getEdgeEndpointId(edge.target) === nodeId) &&
      !deletedEdgeIds.value.includes(edgeId)
    ) {
      deletedEdgeIds.value.push(edgeId)
    }
  })
  graphData.value.nodes = graphData.value.nodes.filter(n => n.id !== nodeId)
  graphData.value.edges = graphData.value.edges.filter(
    e => getEdgeEndpointId(e.source) !== nodeId &&
         getEdgeEndpointId(e.target) !== nodeId
  )
  if (selectedNode.value?.id === nodeId) {
    clearSelection()
  }
  markDirty()
  drawGraph()
}

function addEdge() {
  if (!newEdgeSource.value.trim() || !newEdgeTarget.value.trim()) {
    error.value = '请输入源节点和目标节点'
    return
  }

  let sourceNode = graphData.value.nodes.find(n =>
    n.name === newEdgeSource.value || n.id === newEdgeSource.value
  )
  let targetNode = graphData.value.nodes.find(n =>
    n.name === newEdgeTarget.value || n.id === newEdgeTarget.value
  )

  if (!sourceNode) {
    sourceNode = {
      id: `node_${Date.now()}_source`,
      name: newEdgeSource.value,
      type: 'Entity'
    }
    graphData.value.nodes.push(sourceNode)
  }

  if (!targetNode) {
    targetNode = {
      id: `node_${Date.now()}_target`,
      name: newEdgeTarget.value,
      type: 'Entity'
    }
    graphData.value.nodes.push(targetNode)
  }

  const newEdge: GraphEdge = {
    id: `${sourceNode.id}-${targetNode.id}-${newEdgeType.value}`,
    source: sourceNode.id,
    target: targetNode.id,
    type: newEdgeType.value
  }

  const exists = graphData.value.edges.some(e =>
    (typeof e.source === 'object' ? e.source.id : e.source) === sourceNode.id &&
    (typeof e.target === 'object' ? e.target.id : e.target) === targetNode.id
  )

  if (!exists) {
    graphData.value.edges.push(newEdge)
    markDirty()
  }

  newEdgeSource.value = ''
  newEdgeTarget.value = ''
  editMode.value = false
  drawGraph()
}

function deleteEdge(edgeId: string) {
  if (/^\d+$/.test(edgeId) && !deletedEdgeIds.value.includes(edgeId)) {
    deletedEdgeIds.value.push(edgeId)
  }
  graphData.value.edges = graphData.value.edges.filter(e => e.id !== edgeId)
  if (selectedEdge.value?.id === edgeId) {
    clearSelection()
  }
  markDirty()
  drawGraph()
}

function copyNodeId(id: string) {
  navigator.clipboard.writeText(id)
}

function updateGraphLabelVisibility() {
  if (!graphContainer.value) return
  d3.select(graphContainer.value)
    .selectAll('.node-label')
    .text((d: any) => showLabels.value ? d.name : '')
  d3.select(graphContainer.value)
    .selectAll('.edge-label')
    .text((d: any) => showLabels.value ? d.type : '')
}

watch(showLabels, updateGraphLabelVisibility)

onMounted(() => {
  if (centerEntity.value) {
    loadGraph()
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
            <Network :size="28" class="text-emerald-600" />
            知识图谱编辑器
          </h1>
          <p class="text-sm text-gray-500 mt-1">构建、可视化和编辑知识图谱</p>
        </div>
        <div class="flex items-center gap-3">
          <button
            @click="showHelp = true"
            class="px-4 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 flex items-center gap-2"
          >
            <HelpCircle :size="18" />
            使用说明
          </button>
          <input
            ref="importFileInput"
            type="file"
            accept="application/json,.json"
            class="hidden"
            @change="importGraphFile"
          />
          <button
            @click="triggerImport"
            class="px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2"
          >
            <Upload :size="18" />
            导入
          </button>
          <button
            @click="saveGraph"
            :disabled="isSaving || graphData.nodes.length === 0"
            class="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Loader2 v-if="isSaving" :size="18" class="animate-spin" />
            <Save v-else :size="18" />
            {{ hasUnsavedChanges ? '保存*' : '保存' }}
          </button>
          <button
            @click="exportGraph"
            :disabled="graphData.nodes.length === 0"
            class="px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 flex items-center gap-2"
          >
            <Download :size="18" />
            导出
          </button>
          <button
            @click="editMode = !editMode"
            :class="[
              'px-4 py-2 rounded-lg flex items-center gap-2',
              editMode ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'bg-white border border-gray-300 hover:bg-gray-50'
            ]"
          >
            <Edit3 :size="18" />
            {{ editMode ? '完成编辑' : '编辑模式' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Left Sidebar: Search and Node List -->
      <div class="w-72 bg-white border-r border-gray-200 flex flex-col">
        <!-- Search -->
        <div class="p-4 border-b border-gray-200">
          <label class="block text-sm font-medium text-gray-700 mb-2">中心实体</label>
          <div class="flex gap-2 mb-3">
            <input
              v-model="centerEntity"
              type="text"
              placeholder="输入实体名称..."
              class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              @keyup.enter="loadGraph"
            />
          </div>
          <div class="flex gap-2 mb-3">
            <input
              v-model.number="maxDepth"
              type="number"
              min="1"
              max="3"
              class="w-20 px-3 py-2 border border-gray-300 rounded-lg"
              title="最大深度"
            />
            <input
              v-model.number="nodeLimit"
              type="number"
              min="10"
              max="200"
              class="w-20 px-3 py-2 border border-gray-300 rounded-lg"
              title="节点限制"
            />
            <button
              @click="loadGraph"
              :disabled="isLoading"
              class="flex-1 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <Loader2 v-if="isLoading" :size="18" class="animate-spin" />
              <Search v-else :size="18" />
              加载
            </button>
          </div>
        </div>

        <!-- Node Search -->
        <div class="p-4 border-b border-gray-200">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索节点..."
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
          />
        </div>

        <!-- Node List -->
        <div class="flex-1 overflow-y-auto p-4">
          <div v-if="filteredNodes.length === 0" class="text-center py-8">
            <Network :size="48" class="mx-auto text-gray-300 mb-3" />
            <p class="text-gray-500">暂无节点</p>
            <p class="text-xs text-gray-400 mt-1">加载图谱或添加节点</p>
          </div>

          <div v-else class="space-y-2">
            <div
              v-for="node in filteredNodes"
              :key="node.id"
              @click="selectNode(node)"
              :class="[
                'p-3 rounded-lg border cursor-pointer transition-all group',
                selectedNode?.id === node.id
                  ? 'bg-emerald-50 border-emerald-300 ring-2 ring-emerald-200'
                  : 'bg-white border-gray-200 hover:border-emerald-300',
                highlightedNodes.has(node.id) && selectedNode ? 'ring-2 ring-yellow-200' : ''
              ]"
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <div
                    class="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold"
                    :style="{ backgroundColor: getNodeColor(node.type) }"
                  >
                    {{ node.name.slice(0, 2) }}
                  </div>
                  <div>
                    <div class="font-medium text-gray-900">{{ node.name }}</div>
                    <div class="text-xs text-gray-500">{{ node.type }}</div>
                  </div>
                </div>
                <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    v-if="editMode"
                    @click.stop="deleteNode(node.id)"
                    class="p-1 hover:bg-red-100 rounded"
                    title="删除节点"
                  >
                    <Trash2 :size="14" class="text-red-500" />
                  </button>
                  <button
                    @click.stop="copyNodeId(node.id)"
                    class="p-1 hover:bg-gray-100 rounded"
                    title="复制ID"
                  >
                    <Copy :size="14" class="text-gray-500" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Edit Panel -->
        <div v-if="editMode" class="border-t border-gray-200 p-4 space-y-3">
          <h4 class="font-medium text-gray-900 flex items-center gap-2">
            <Plus :size="16" />
            添加节点
          </h4>
          <input
            v-model="newNodeName"
            type="text"
            placeholder="节点名称"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg"
          />
          <select
            v-model="newNodeType"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg"
          >
            <option v-for="t in nodeTypes" :key="t.value" :value="t.value">
              {{ t.label }}
            </option>
          </select>
          <button
            @click="addNode"
            class="w-full px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 flex items-center justify-center gap-2"
          >
            <Plus :size="16" />
            添加节点
          </button>

          <div class="border-t border-gray-200 pt-3">
            <h4 class="font-medium text-gray-900 flex items-center gap-2 mb-2">
              <Link :size="16" />
              添加关系
            </h4>
            <div class="flex gap-2 mb-2">
              <input
                v-model="newEdgeSource"
                type="text"
                placeholder="源节点"
                class="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
              />
              <input
                v-model="newEdgeTarget"
                type="text"
                placeholder="目标节点"
                class="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
              />
            </div>
            <select
              v-model="newEdgeType"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg mb-2"
            >
              <option v-for="t in edgeTypes" :key="t.value" :value="t.value">
                {{ t.label }}
              </option>
            </select>
            <button
              @click="addEdge"
              class="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center justify-center gap-2"
            >
              <Plus :size="16" />
              添加关系
            </button>
          </div>
        </div>
      </div>

      <!-- Main Content Area -->
      <div class="flex-1 flex flex-col overflow-hidden">
        <!-- Toolbar -->
        <div class="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
          <div class="flex items-center gap-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="showLabels" class="rounded" />
              <span class="text-sm text-gray-600">显示标签</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="showProperties" class="rounded" />
              <span class="text-sm text-gray-600">显示属性</span>
            </label>
          </div>

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
              @click="fitToScreen"
              class="p-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              title="适应屏幕"
            >
              <Maximize2 :size="18" />
            </button>
          </div>
        </div>

        <!-- Graph Container -->
        <div class="flex-1 relative">
          <div
            ref="graphContainer"
            class="w-full h-full"
            @click="clearSelection"
          ></div>

          <!-- Selected Node Panel -->
          <div
            v-if="selectedNode"
            class="absolute right-4 top-4 w-80 bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden"
          >
            <div class="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center justify-between">
              <h3 class="font-semibold text-gray-900">节点详情</h3>
              <button @click="clearSelection" class="p-1 hover:bg-gray-200 rounded">
                <X :size="16" />
              </button>
            </div>
            <div class="p-4">
              <div class="flex items-center gap-3 mb-4">
                <div
                  class="w-12 h-12 rounded-full flex items-center justify-center text-white text-lg font-bold"
                  :style="{ backgroundColor: getNodeColor(selectedNode.type) }"
                >
                  {{ selectedNode.name.slice(0, 2) }}
                </div>
                <div>
                  <div class="font-medium text-gray-900">{{ selectedNode.name }}</div>
                  <div class="text-sm text-gray-500">{{ selectedNode.type }}</div>
                </div>
              </div>

              <div class="mb-4">
                <div class="text-xs text-gray-500 mb-1">ID</div>
                <div class="text-sm font-mono bg-gray-50 px-2 py-1 rounded">{{ selectedNode.id }}</div>
              </div>

              <div v-if="showProperties && selectedNode.properties" class="mb-4">
                <div class="text-xs text-gray-500 mb-2">属性</div>
                <div class="space-y-1">
                  <div
                    v-for="(value, key) in selectedNode.properties"
                    :key="key"
                    class="flex items-start gap-2 text-sm"
                  >
                    <span class="text-gray-500">{{ key }}:</span>
                    <span class="text-gray-900">{{ value }}</span>
                  </div>
                </div>
              </div>

              <div class="text-xs text-gray-500 mb-2">关联边</div>
              <div class="space-y-1 max-h-32 overflow-y-auto">
                <div
                  v-for="edge in graphData.edges.filter(e =>
                    (typeof e.source === 'object' ? e.source.id : e.source) === selectedNode.id ||
                    (typeof e.target === 'object' ? e.target.id : e.target) === selectedNode.id
                  )"
                  :key="edge.id"
                  class="text-sm px-2 py-1 bg-gray-50 rounded flex items-center gap-2"
                >
                  <Link :size="12" class="text-gray-400" />
                  <span class="text-gray-600">{{ edge.type }}</span>
                </div>
              </div>

              <div v-if="editMode" class="mt-4 pt-4 border-t border-gray-200">
                <button
                  @click="deleteNode(selectedNode.id)"
                  class="w-full px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 flex items-center justify-center gap-2"
                >
                  <Trash2 :size="16" />
                  删除节点
                </button>
              </div>
            </div>
          </div>

          <!-- Selected Edge Panel -->
          <div
            v-if="selectedEdge"
            class="absolute right-4 top-4 w-80 bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden"
          >
            <div class="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center justify-between">
              <h3 class="font-semibold text-gray-900">关系详情</h3>
              <button @click="clearSelection" class="p-1 hover:bg-gray-200 rounded">
                <X :size="16" />
              </button>
            </div>
            <div class="p-4 space-y-3">
              <div>
                <div class="text-xs text-gray-500 mb-1">类型</div>
                <div class="text-sm font-medium text-gray-900">{{ selectedEdge.type }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500 mb-1">源节点</div>
                <div class="text-sm font-mono bg-gray-50 px-2 py-1 rounded">{{ getEdgeEndpointId(selectedEdge.source) }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500 mb-1">目标节点</div>
                <div class="text-sm font-mono bg-gray-50 px-2 py-1 rounded">{{ getEdgeEndpointId(selectedEdge.target) }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500 mb-1">语义描述</div>
                <input
                  v-model="selectedEdge.description"
                  type="text"
                  placeholder="描述这个关系的含义..."
                  class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                  @input="markDirty"
                />
              </div>
              <div v-if="showProperties && selectedEdge.properties">
                <div class="text-xs text-gray-500 mb-2">属性</div>
                <div class="space-y-1 max-h-24 overflow-y-auto">
                  <div
                    v-for="(value, key) in selectedEdge.properties"
                    :key="key"
                    class="flex items-start gap-2 text-sm"
                  >
                    <span class="text-gray-500">{{ key }}:</span>
                    <span class="text-gray-900">{{ String(value) }}</span>
                  </div>
                </div>
              </div>
              <div v-if="editMode" class="pt-3 border-t border-gray-200 space-y-2">
                <button
                  @click="deleteEdge(selectedEdge.id)"
                  class="w-full px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 flex items-center justify-center gap-2"
                >
                  <Trash2 :size="16" />
                  删除关系
                </button>
              </div>
            </div>
          </div>

          <!-- Loading Overlay -->
          <div v-if="isLoading" class="absolute inset-0 bg-white bg-opacity-80 flex items-center justify-center">
            <div class="text-center">
              <Loader2 :size="48" class="mx-auto text-emerald-300 animate-spin mb-3" />
              <p class="text-gray-500">加载图谱数据...</p>
            </div>
          </div>

          <!-- Empty State -->
          <div v-if="!isLoading && graphData.nodes.length === 0" class="absolute inset-0 flex items-center justify-center">
            <div class="text-center">
              <Network :size="64" class="mx-auto text-gray-300 mb-4" />
              <p class="text-gray-500 mb-2">暂无图谱数据</p>
              <p class="text-sm text-gray-400">输入中心实体并点击"加载"开始构建图谱</p>
            </div>
          </div>
        </div>

        <!-- Legend -->
        <div class="bg-white border-t border-gray-200 px-6 py-3">
          <div class="flex items-center gap-6">
            <span class="text-sm text-gray-500">节点类型:</span>
            <div class="flex items-center gap-4">
              <div v-for="t in nodeTypes" :key="t.value" class="flex items-center gap-1">
                <div class="w-3 h-3 rounded-full" :style="{ backgroundColor: t.color }"></div>
                <span class="text-xs text-gray-600">{{ t.label }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Help Modal -->
    <div
      v-if="showHelp"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showHelp = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
        <div class="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-4 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <BookOpen :size="24" class="text-white" />
            <h2 class="text-xl font-bold text-white">知识图谱编辑器使用指南</h2>
          </div>
          <button @click="showHelp = false" class="p-2 hover:bg-white hover:bg-opacity-20 rounded-lg transition-colors">
            <X :size="20" class="text-white" />
          </button>
        </div>

        <div class="p-6 overflow-y-auto max-h-[calc(90vh-80px)] space-y-6">
          <!-- Section 1: Overview -->
          <div class="bg-blue-50 rounded-xl p-5">
            <div class="flex items-start gap-3">
              <div class="p-2 bg-blue-100 rounded-lg">
                <Layers :size="20" class="text-blue-600" />
              </div>
              <div>
                <h3 class="font-semibold text-blue-900 mb-2">功能概述</h3>
                <p class="text-sm text-blue-700 leading-relaxed">
                  知识图谱编辑器是一个强大的可视化工具，帮助您构建、编辑和探索实体之间的关系网络。通过直观的拖拽操作和丰富的交互功能，您可以轻松管理和分析复杂的知识结构。
                </p>
              </div>
            </div>
          </div>

          <!-- Section 2: Load Graph -->
          <div class="border border-gray-200 rounded-xl overflow-hidden">
            <div class="bg-gray-50 px-5 py-3 border-b border-gray-200">
              <div class="flex items-center gap-2">
                <Download :size="18" class="text-emerald-600" />
                <h3 class="font-semibold text-gray-900">第一步：加载知识图谱</h3>
              </div>
            </div>
            <div class="p-5 space-y-3">
              <div class="flex items-start gap-3">
                <div class="w-6 h-6 bg-emerald-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span class="text-xs font-bold text-emerald-600">1</span>
                </div>
                <p class="text-gray-700 text-sm">在左侧面板的「中心实体」输入框中输入您想查询的实体名称</p>
              </div>
              <div class="flex items-start gap-3">
                <div class="w-6 h-6 bg-emerald-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span class="text-xs font-bold text-emerald-600">2</span>
                </div>
                <p class="text-gray-700 text-sm">设置搜索参数：最大深度（1-3层关系）和节点限制（10-200个节点）</p>
              </div>
              <div class="flex items-start gap-3">
                <div class="w-6 h-6 bg-emerald-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span class="text-xs font-bold text-emerald-600">3</span>
                </div>
                <p class="text-gray-700 text-sm">点击「加载」按钮，系统将从后端知识图谱数据库中获取相关数据</p>
              </div>
              <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 mt-3">
                <p class="text-xs text-amber-800 flex items-start gap-2">
                  <AlertCircle :size="14" class="flex-shrink-0 mt-0.5" />
                  <span>提示：深度越深、节点限制越大，加载时间越长。建议从较小范围开始探索。</span>
                </p>
              </div>
            </div>
          </div>

          <!-- Section 3: Graph Interaction -->
          <div class="border border-gray-200 rounded-xl overflow-hidden">
            <div class="bg-gray-50 px-5 py-3 border-b border-gray-200">
              <div class="flex items-center gap-2">
                <MousePointer :size="18" class="text-emerald-600" />
                <h3 class="font-semibold text-gray-900">第二步：图谱交互操作</h3>
              </div>
            </div>
            <div class="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                <div class="p-2 bg-white rounded-lg shadow-sm">
                  <MousePointer :size="16" class="text-gray-600" />
                </div>
                <div>
                  <h4 class="font-medium text-gray-900 text-sm">选择节点</h4>
                  <p class="text-xs text-gray-500 mt-1">点击任意节点查看详情，关联的节点会高亮显示</p>
                </div>
              </div>
              <div class="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                <div class="p-2 bg-white rounded-lg shadow-sm">
                  <Move :size="16" class="text-gray-600" />
                </div>
                <div>
                  <h4 class="font-medium text-gray-900 text-sm">拖拽移动</h4>
                  <p class="text-xs text-gray-500 mt-1">按住并拖动节点可调整其在图谱中的位置</p>
                </div>
              </div>
              <div class="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                <div class="p-2 bg-white rounded-lg shadow-sm">
                  <ZoomInIcon :size="16" class="text-gray-600" />
                </div>
                <div>
                  <h4 class="font-medium text-gray-900 text-sm">缩放视图</h4>
                  <p class="text-xs text-gray-500 mt-1">使用顶部工具栏的放大、缩小、适应屏幕按钮调整视图</p>
                </div>
              </div>
              <div class="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                <div class="p-2 bg-white rounded-lg shadow-sm">
                  <Eye :size="16" class="text-gray-600" />
                </div>
                <div>
                  <h4 class="font-medium text-gray-900 text-sm">显示/隐藏</h4>
                  <p class="text-xs text-gray-500 mt-1">可切换标签显示和属性显示，优化视图清晰度</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Section 4: Edit Mode -->
          <div class="border border-gray-200 rounded-xl overflow-hidden">
            <div class="bg-gray-50 px-5 py-3 border-b border-gray-200">
              <div class="flex items-center gap-2">
                <Edit3 :size="18" class="text-emerald-600" />
                <h3 class="font-semibold text-gray-900">第三步：编辑模式</h3>
              </div>
            </div>
            <div class="p-5 space-y-4">
              <div>
                <h4 class="font-medium text-gray-900 mb-2 flex items-center gap-2">
                  <Plus :size="14" class="text-emerald-600" />
                  添加节点
                </h4>
                <ol class="text-sm text-gray-600 space-y-1 ml-6 list-decimal">
                  <li>点击右上角「编辑模式」按钮进入编辑状态</li>
                  <li>在左侧面板输入节点名称和选择节点类型</li>
                  <li>点击「添加节点」按钮完成添加</li>
                </ol>
              </div>
              <div>
                <h4 class="font-medium text-gray-900 mb-2 flex items-center gap-2">
                  <Link :size="14" class="text-blue-600" />
                  添加关系
                </h4>
                <ol class="text-sm text-gray-600 space-y-1 ml-6 list-decimal">
                  <li>在编辑模式下，输入源节点和目标节点名称</li>
                  <li>选择关系类型（相关、属于、位于、任职、创建）</li>
                  <li>点击「添加关系」建立连接</li>
                </ol>
              </div>
              <div>
                <h4 class="font-medium text-gray-900 mb-2 flex items-center gap-2">
                  <Trash2 :size="14" class="text-red-600" />
                  删除操作
                </h4>
                <ol class="text-sm text-gray-600 space-y-1 ml-6 list-decimal">
                  <li>在节点列表中悬停并点击删除图标</li>
                  <li>或在节点详情面板中点击「删除节点」</li>
                </ol>
              </div>
              <div class="bg-red-50 border border-red-200 rounded-lg p-3">
                <p class="text-xs text-red-800 flex items-start gap-2">
                  <AlertCircle :size="14" class="flex-shrink-0 mt-0.5" />
                  <span>注意：编辑操作仅影响本地数据，不会自动同步到后端数据库。如需持久化，请使用专门的导入/导出功能。</span>
                </p>
              </div>
            </div>
          </div>

          <!-- Section 5: Export -->
          <div class="border border-gray-200 rounded-xl overflow-hidden">
            <div class="bg-gray-50 px-5 py-3 border-b border-gray-200">
              <div class="flex items-center gap-2">
                <Download :size="18" class="text-emerald-600" />
                <h3 class="font-semibold text-gray-900">第四步：导出数据</h3>
              </div>
            </div>
            <div class="p-5">
              <p class="text-sm text-gray-600 mb-3">点击右上角「导出」按钮，可以将当前图谱导出为 JSON 格式文件，方便后续分析和分享。</p>
              <div class="bg-gray-100 rounded-lg p-3 font-mono text-xs text-gray-700">
                export &#123;<br/>
                &nbsp;&nbsp;nodes: [&#123; id, name, type &#125;, ...],<br/>
                &nbsp;&nbsp;edges: [&#123; source, target, type &#125;, ...]<br/>
                &#125;
              </div>
            </div>
          </div>

          <!-- Section 6: Node Types -->
          <div class="border border-gray-200 rounded-xl overflow-hidden">
            <div class="bg-gray-50 px-5 py-3 border-b border-gray-200">
              <div class="flex items-center gap-2">
                <Network :size="18" class="text-emerald-600" />
                <h3 class="font-semibold text-gray-900">节点类型说明</h3>
              </div>
            </div>
            <div class="p-5 grid grid-cols-2 md:grid-cols-3 gap-3">
              <div v-for="t in nodeTypes" :key="t.value" class="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-50">
                <div class="w-4 h-4 rounded-full flex-shrink-0" :style="{ backgroundColor: t.color }"></div>
                <span class="text-sm text-gray-700">{{ t.label }}</span>
              </div>
            </div>
          </div>

          <!-- Section 7: Tips -->
          <div class="bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl p-5">
            <div class="flex items-start gap-3">
              <div class="p-2 bg-purple-100 rounded-lg">
                <Sparkles :size="20" class="text-purple-600" />
              </div>
              <div>
                <h3 class="font-semibold text-purple-900 mb-3">使用技巧</h3>
                <ul class="space-y-2 text-sm text-purple-700">
                  <li class="flex items-start gap-2">
                    <CheckCircle :size="14" class="flex-shrink-0 mt-1" />
                    <span>双击空白区域可快速清除当前选择</span>
                  </li>
                  <li class="flex items-start gap-2">
                    <CheckCircle :size="14" class="flex-shrink-0 mt-1" />
                    <span>使用搜索功能快速定位特定节点</span>
                  </li>
                  <li class="flex items-start gap-2">
                    <CheckCircle :size="14" class="flex-shrink-0 mt-1" />
                    <span>拖拽节点时按住可以临时固定位置</span>
                  </li>
                  <li class="flex items-start gap-2">
                    <CheckCircle :size="14" class="flex-shrink-0 mt-1" />
                    <span>复制节点 ID 方便在代码中引用</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error/Success Messages -->
    <div v-if="error" class="fixed bottom-4 right-4 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3 shadow-lg">
      <AlertCircle :size="20" class="text-red-500" />
      <p class="text-sm text-red-700">{{ error }}</p>
      <button @click="error = ''" class="p-1 hover:bg-red-100 rounded">
        <X :size="16" class="text-red-500" />
      </button>
    </div>

    <div v-if="success" class="fixed bottom-4 right-4 bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3 shadow-lg">
      <CheckCircle :size="20" class="text-green-500" />
      <p class="text-sm text-green-700">{{ success }}</p>
      <button @click="success = ''" class="p-1 hover:bg-green-100 rounded">
        <X :size="16" class="text-green-500" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.knowledge-graph-svg {
  background: linear-gradient(45deg, #f8fafc 25%, transparent 25%),
              linear-gradient(-45deg, #f8fafc 25%, transparent 25%),
              linear-gradient(45deg, transparent 75%, #f8fafc 75%),
              linear-gradient(-45deg, transparent 75%, #f8fafc 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
}
</style>
