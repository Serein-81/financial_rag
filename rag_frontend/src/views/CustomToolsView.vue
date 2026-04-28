<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Bot, CheckCircle2, FlaskConical, Play, RefreshCw, Wand2 } from 'lucide-vue-next'
import { agentDiscoveryApi, type AgentSummary } from '@/api/agent-discovery'
import { customToolsApi, type CustomTool, type CustomToolKind, type CustomToolSpec } from '@/api/custom-tools'

const isLoading = ref(false)
const isGenerating = ref(false)
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

async function loadPage() {
  isLoading.value = true
  try {
    const [toolResponse, agentResponse] = await Promise.all([
      customToolsApi.list(),
      agentDiscoveryApi.getAgents(undefined, true),
    ])
    tools.value = toolResponse.tools
    agents.value = agentResponse
    if (!selectedToolId.value && tools.value.length) selectedToolId.value = tools.value[0].id
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
    ElMessage.success('工具规格已生成')
  } finally {
    isGenerating.value = false
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
  try {
    const args = JSON.parse(testArgumentsText.value || '{}')
    const result = await customToolsApi.execute(selectedTool.value.id, args)
    testResult.value = JSON.stringify(result, null, 2)
  } catch (error: any) {
    testResult.value = error?.response?.data?.detail || error.message || String(error)
  }
}

onMounted(loadPage)
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

      <section class="grid gap-4 lg:grid-cols-[1fr_420px]">
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
                <p class="mt-1 truncate text-xs text-slate-500">{{ tool.name }} · {{ tool.description }}</p>
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
          <textarea v-model="testArgumentsText" class="h-32 w-full rounded-md border border-slate-300 p-3 font-mono text-xs" spellcheck="false"></textarea>
          <button class="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white" :disabled="!selectedTool" @click="runTest">
            <Play class="h-4 w-4" />
            执行测试
          </button>
          <pre class="mt-3 max-h-64 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">{{ testResult }}</pre>
        </div>
      </section>
    </div>
  </div>
</template>
