<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Bot, CheckCircle2, FlaskConical, Play, RefreshCw, Wand2 } from 'lucide-vue-next'
import { agentDiscoveryApi, type AgentSummary } from '@/api/agent-discovery'
import { customToolsApi, type CustomTool, type CustomToolKind, type CustomToolSpec } from '@/api/custom-tools'

const isLoading = ref(false)
const isGenerating = ref(false)
const isGeneratingCode = ref(false)
const isSaving = ref(false)
const tools = ref<CustomTool[]>([])
const agents = ref<AgentSummary[]>([])
const selectedToolId = ref('')
const testArgumentsText = ref('{\n  "query": "test"\n}')
const testResult = ref('')

const generatorForm = ref({
  natural_language: '',
  purpose: '',
  inputs: '',
  outputs: '',
  preferred_kind: 'echo' as CustomToolKind,
  agent_id: '',
})

const draftSpec = ref<CustomToolSpec | null>(null)
const draftJson = computed({
  get: () => JSON.stringify(draftSpec.value, null, 2),
  set: (value: string) => {
    try {
      draftSpec.value = JSON.parse(value)
    } catch {
      // Keep user text editable; validation happens when saving.
    }
  },
})

const selectedTool = computed(() => tools.value.find(tool => tool.id === selectedToolId.value))
const publishedTools = computed(() => tools.value.filter(tool => tool.enabled && tool.status === 'published' && tool.kind !== 'python_code'))
const selectedToolInputSchema = computed(() => selectedTool.value?.input_schema || {})
const selectedToolOutputSchema = computed(() => selectedTool.value?.output_schema || {})
const isSelectedToolExecutable = computed(() => Boolean(
  selectedTool.value &&
  selectedTool.value.enabled &&
  selectedTool.value.status === 'published' &&
  selectedTool.value.kind !== 'python_code'
))
const testRequestPreview = computed(() => {
  let args: Record<string, any> = {}
  try {
    args = JSON.parse(testArgumentsText.value || '{}')
  } catch {
    args = {}
  }
  return JSON.stringify({ arguments: args }, null, 2)
})
const outputSchemaPreview = computed(() => JSON.stringify(selectedToolOutputSchema.value, null, 2))

function getSampleValue(field: any, name: string): any {
  if (field?.default !== undefined && field.default !== null) return field.default
  const type = String(field?.type || 'string').toLowerCase()
  const normalizedName = name.toLowerCase()
  if (type === 'integer' || type === 'int') return 1
  if (type === 'number' || type === 'float') return 1.23
  if (type === 'boolean' || type === 'bool') return true
  if (type === 'array' || type === 'list') return []
  if (type === 'object' || type === 'dict') return {}
  if (normalizedName.includes('phone')) return '13800000000'
  if (normalizedName.includes('email')) return 'demo@example.com'
  if (normalizedName.includes('url')) return 'https://example.com'
  if (normalizedName.includes('amount') || normalizedName.includes('price')) return 100
  if (normalizedName.includes('query') || normalizedName.includes('question')) return '测试查询'
  return `测试${name}`
}

function buildSampleArguments(tool?: CustomTool | CustomToolSpec | null): string {
  const schema = tool?.input_schema || {}
  const sample = Object.fromEntries(
    Object.entries(schema).map(([name, field]) => [name, getSampleValue(field, name)])
  )
  return JSON.stringify(Object.keys(sample).length ? sample : { query: '测试查询' }, null, 2)
}

function getFieldMetaText(field: any): string {
  const parts = [field?.type || 'string']
  parts.push(field?.required === false ? '可选' : '必填')
  if (field?.description) parts.push(field.description)
  return parts.join(' · ')
}

function truncateText(text: string, maxLength = 72): string {
  if (!text) return ''
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text
}

function parseTestArguments(): Record<string, any> | null {
  try {
    const parsed = JSON.parse(testArgumentsText.value || '{}')
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      ElMessage.warning('测试入参必须是 JSON 对象')
      return null
    }
    return parsed
  } catch {
    ElMessage.warning('测试 JSON 格式不正确')
    return null
  }
}

function fillTestArguments() {
  if (!selectedTool.value) {
    ElMessage.warning('请先选择一个工具')
    return
  }
  testArgumentsText.value = buildSampleArguments(selectedTool.value)
  testResult.value = ''
  ElMessage.success('已按入参 Schema 填充测试 JSON')
}

function formatTestResult(result: any, args: Record<string, any>): string {
  return JSON.stringify({
    tool: result?.tool || selectedTool.value?.name,
    status: result?.status,
    input: result?.arguments || args,
    output_schema: result?.output_schema || selectedToolOutputSchema.value,
    output: result?.output ?? result?.data ?? null,
    raw_response: result,
  }, null, 2)
}

async function loadPage() {
  isLoading.value = true
  try {
    const [toolResponse, agentResponse] = await Promise.all([
      customToolsApi.list(),
      agentDiscoveryApi.getAgents(undefined, true),
    ])
    tools.value = toolResponse.tools
    agents.value = agentResponse
    if (!selectedToolId.value && tools.value.length) {
      selectedToolId.value = publishedTools.value[0]?.id || tools.value[0].id
    }
    if (selectedTool.value) testArgumentsText.value = buildSampleArguments(selectedTool.value)
  } finally {
    isLoading.value = false
  }
}

async function generateSpec() {
  if (!generatorForm.value.natural_language.trim()) {
    ElMessage.warning('请输入工具需求')
    return
  }
  isGenerating.value = true
  try {
    draftSpec.value = await customToolsApi.generate(generatorForm.value)
    testArgumentsText.value = buildSampleArguments(draftSpec.value)
    ElMessage.success('工具规格已生成')
  } finally {
    isGenerating.value = false
  }
}

async function generateCodeDraft() {
  if (!draftSpec.value) return
  isGeneratingCode.value = true
  try {
    draftSpec.value = await customToolsApi.generateCode(
      draftSpec.value,
      generatorForm.value.natural_language
    )
    ElMessage.success('代码草稿已生成，仅保存待审核，不会执行')
  } finally {
    isGeneratingCode.value = false
  }
}

async function saveDraft() {
  if (!draftSpec.value) return
  isSaving.value = true
  try {
    await customToolsApi.create(draftSpec.value)
    ElMessage.success('工具已创建，等待发布')
    await loadPage()
  } finally {
    isSaving.value = false
  }
}

async function publishTool(tool: CustomTool) {
  await customToolsApi.publish(tool.id, tool.agent_id || generatorForm.value.agent_id || undefined)
  ElMessage.success('工具已发布并注册到当前进程')
  await loadPage()
}

async function runTest() {
  if (!selectedTool.value) return
  if (!isSelectedToolExecutable.value) {
    testResult.value = JSON.stringify({
      status: 'error',
      tool: selectedTool.value.name,
      input: parseTestArguments() || {},
      output_schema: selectedToolOutputSchema.value,
      error: '当前工具尚未发布或不可执行，请先发布后再测试。',
    }, null, 2)
    return
  }
  const args = parseTestArguments()
  if (!args) return
  try {
    const result = await customToolsApi.execute(selectedTool.value.id, args)
    testResult.value = formatTestResult(result, args)
  } catch (error: any) {
    testResult.value = JSON.stringify({
      status: 'error',
      tool: selectedTool.value.name,
      input: args,
      output_schema: selectedToolOutputSchema.value,
      error: error?.response?.data?.detail || error.message || String(error),
    }, null, 2)
  }
}

onMounted(loadPage)

watch(selectedTool, (tool) => {
  if (tool) {
    testArgumentsText.value = buildSampleArguments(tool)
    testResult.value = ''
  }
})
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <div class="mx-auto flex max-w-7xl flex-col gap-5 px-6 py-6">
      <header class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-semibold text-slate-900">智能体工具构建器</h1>
          <p class="mt-1 text-sm text-slate-500">通过自然语言生成受控工具规格，审核后注册到 Agent。</p>
        </div>
        <button class="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700" @click="loadPage">
          <RefreshCw class="h-4 w-4" />
          刷新
        </button>
      </header>

      <section class="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
        <div class="font-medium">使用说明</div>
        <div class="mt-1 leading-6">
          先描述工具用途、入参和出参，再生成规格并检查 JSON；创建草稿后点击发布，工具会注册为当前进程内的本地 Agent 工具。HTTP 工具默认禁止访问内网地址；python_code 只保存为待审核代码，不会直接执行。
        </div>
      </section>

      <section class="grid gap-4 lg:grid-cols-[420px_1fr]">
        <div class="rounded-lg border border-slate-200 bg-white p-4">
          <div class="mb-4 flex items-center gap-2 text-sm font-medium text-slate-800">
            <Wand2 class="h-4 w-4 text-blue-600" />
            生成工具
          </div>
          <div class="space-y-3">
            <textarea v-model="generatorForm.natural_language" class="h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="例如：创建一个工具，根据发票号调用外部接口查询发票状态"></textarea>
            <input v-model="generatorForm.purpose" class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="用途" />
            <input v-model="generatorForm.inputs" class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="入参说明" />
            <input v-model="generatorForm.outputs" class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="出参说明" />
            <select v-model="generatorForm.preferred_kind" class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
              <option value="echo">echo</option>
              <option value="http">http</option>
              <option value="rag_query">rag_query</option>
              <option value="python_code">python_code</option>
            </select>
            <select v-model="generatorForm.agent_id" class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
              <option value="">暂不绑定 Agent</option>
              <option v-for="agent in agents" :key="agent.agent_id" :value="agent.agent_id">{{ agent.agent_name }}</option>
            </select>
            <button class="inline-flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-60" :disabled="isGenerating" @click="generateSpec">
              <Wand2 class="h-4 w-4" />
              生成规格
            </button>
            <button class="inline-flex w-full items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 disabled:opacity-60" :disabled="!draftSpec || isGeneratingCode" @click="generateCodeDraft">
              <Wand2 class="h-4 w-4" />
              生成代码草稿
            </button>
          </div>
        </div>

        <div class="rounded-lg border border-slate-200 bg-white p-4">
          <div class="mb-4 flex items-center justify-between">
            <div class="flex items-center gap-2 text-sm font-medium text-slate-800">
              <FlaskConical class="h-4 w-4 text-emerald-600" />
              工具规格预览
            </div>
            <button class="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-60" :disabled="!draftSpec || isSaving" @click="saveDraft">
              <CheckCircle2 class="h-4 w-4" />
              创建草稿
            </button>
          </div>
          <textarea v-model="draftJson" class="h-[360px] w-full rounded-md border border-slate-300 bg-slate-950 p-3 font-mono text-xs text-slate-100" spellcheck="false"></textarea>
        </div>
      </section>

      <section class="grid gap-4 lg:grid-cols-[minmax(0,0.75fr)_minmax(460px,0.95fr)]">
        <div class="rounded-lg border border-slate-200 bg-white">
          <div class="border-b border-slate-200 px-4 py-3 text-sm font-medium text-slate-800">工具列表</div>
          <div class="divide-y divide-slate-100">
            <div v-for="tool in tools" :key="tool.id" class="flex items-center justify-between gap-4 px-4 py-3">
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <Bot class="h-4 w-4 text-slate-500" />
                  <button class="truncate text-left text-sm font-medium text-slate-900" @click="selectedToolId = tool.id">{{ tool.display_name }}</button>
                  <span class="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{{ tool.kind }}</span>
                  <span class="rounded px-2 py-0.5 text-xs" :class="tool.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'">{{ tool.status }}</span>
                </div>
                <p class="mt-1 truncate text-xs text-slate-500" :title="tool.description">{{ tool.name }} · {{ truncateText(tool.description) }}</p>
              </div>
              <button class="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 disabled:opacity-50" :disabled="tool.enabled || tool.kind === 'python_code'" @click="publishTool(tool)">
                <Play class="h-4 w-4" />
                发布
              </button>
            </div>
            <div v-if="!tools.length && !isLoading" class="px-4 py-8 text-center text-sm text-slate-500">暂无自定义工具</div>
          </div>
        </div>

        <div class="rounded-lg border border-slate-200 bg-white p-4">
          <div class="mb-3 text-sm font-medium text-slate-800">测试已发布工具</div>
          <select v-model="selectedToolId" class="mb-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
            <option v-for="tool in tools" :key="tool.id" :value="tool.id">{{ tool.display_name }}</option>
          </select>
          <div v-if="selectedTool && !isSelectedToolExecutable" class="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            当前工具未发布或不可执行，发布后才能得到真实出参。
          </div>
          <div v-if="selectedTool" class="mb-3 rounded-md border border-slate-200 bg-slate-50 p-3">
            <div class="mb-2 text-xs font-medium text-slate-700">入参说明</div>
            <div v-if="Object.keys(selectedToolInputSchema).length" class="space-y-1">
              <div v-for="(field, name) in selectedToolInputSchema" :key="name" class="text-xs text-slate-600">
                <span class="font-mono font-medium text-slate-800">{{ name }}</span>
                <span class="ml-1">{{ getFieldMetaText(field) }}</span>
              </div>
            </div>
            <div v-else class="text-xs text-slate-500">未声明入参，默认使用 query 测试。</div>
          </div>
          <div class="mb-2 flex items-center justify-between">
            <span class="text-xs font-medium text-slate-700">入参测试 JSON</span>
            <button class="rounded px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 disabled:text-slate-400" type="button" :disabled="!selectedTool" @click="fillTestArguments">
              自动填充
            </button>
          </div>
          <textarea v-model="testArgumentsText" class="h-32 w-full rounded-md border border-slate-300 p-3 font-mono text-xs" spellcheck="false"></textarea>
          <div class="mt-3 text-xs font-medium text-slate-700">实际请求体</div>
          <pre class="mt-2 max-h-28 overflow-auto rounded-md bg-slate-100 p-3 text-xs text-slate-700">{{ testRequestPreview }}</pre>
          <div class="mt-3 text-xs font-medium text-slate-700">预期出参 Schema</div>
          <pre class="mt-2 max-h-28 overflow-auto rounded-md bg-slate-100 p-3 text-xs text-slate-700">{{ outputSchemaPreview }}</pre>
          <button class="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50" :disabled="!selectedTool" @click="runTest">
            <Play class="h-4 w-4" />
            执行测试
          </button>
          <div class="mt-3 text-xs font-medium text-slate-700">出参结果</div>
          <pre class="mt-2 max-h-64 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">{{ testResult || '执行后将在这里显示 input / output_schema / output。' }}</pre>
        </div>
      </section>
    </div>
  </div>
</template>
