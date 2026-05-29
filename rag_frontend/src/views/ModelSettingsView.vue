<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Cpu, Cloud, Server, RefreshCw, Save, RotateCcw,
  Eye, EyeOff, Info, Zap, Download, CheckCircle2, XCircle, BarChart3,
} from 'lucide-vue-next'
import {
  modelConfigApi,
  type ProviderInfo,
  type ChatRole,
  type TestConnectionResult,
  type UsageOverview,
  type EmbeddingTestResult,
  type RerankTestResult,
} from '@/api/model-config'

const activeTab = ref<'chat' | 'usage' | 'embedding' | 'rerank'>('chat')
const showHelp = ref(false)

// ===== 使用概览（管理员视角）=====
const overview = ref<UsageOverview | null>(null)
const overviewLoading = ref(false)

async function loadOverview() {
  overviewLoading.value = true
  try {
    overview.value = await modelConfigApi.getUsageOverview()
  } catch (e: any) {
    ElMessage.error('加载使用概览失败：' + (e?.response?.data?.detail || e?.message || e))
  } finally {
    overviewLoading.value = false
  }
}

function fmtTime(t?: string | null): string {
  if (!t) return '无'
  const d = new Date(t)
  return isNaN(d.getTime()) ? '无' : d.toLocaleString()
}

watch(activeTab, (tab) => {
  if (tab === 'usage' && !overview.value) loadOverview()
  if (tab === 'embedding' && !embProviders.value.length) loadEmbedding()
  if (tab === 'rerank' && !rrkProviders.value.length) loadRerank()
})

function findProvider(list: ProviderInfo[], id: string): ProviderInfo | undefined {
  return list.find(p => p.id === id)
}

// ===== 向量模型（Embedding）=====
const embProviders = ref<ProviderInfo[]>([])
const embRequiredDim = ref(1024)
const embOllamaModels = ref<string[]>([])
const embTest = ref<EmbeddingTestResult | null>(null)
const embBusy = reactive({ loading: false, testing: false, saving: false, detecting: false })
const embForm = reactive({ provider: '', model: '', base_url: '', api_key: '', showKey: false })

const embCloud = computed(() => embProviders.value.filter(p => p.group === 'cloud'))
const embLocal = computed(() => embProviders.value.filter(p => p.group === 'local'))
const embProviderInfo = computed(() => findProvider(embProviders.value, embForm.provider))

function embModelOptions(): string[] {
  if (embProviderInfo.value?.group === 'local' && embOllamaModels.value.length) return embOllamaModels.value
  return embProviderInfo.value?.models || []
}

async function loadEmbedding() {
  embBusy.loading = true
  try {
    const [cat, cfg] = await Promise.all([
      modelConfigApi.getEmbeddingCatalog(),
      modelConfigApi.getEmbeddingConfig(),
    ])
    embProviders.value = cat.providers
    embRequiredDim.value = cat.required_dim
    embForm.provider = cfg.provider
    embForm.model = cfg.model || ''
    embForm.base_url = cfg.base_url || ''
    embForm.api_key = cfg.api_key || ''
  } catch (e: any) {
    ElMessage.error('加载向量模型配置失败：' + (e?.response?.data?.detail || e?.message || e))
  } finally {
    embBusy.loading = false
  }
}

function onEmbProviderChange() {
  embForm.model = ''
  embForm.base_url = ''
  embTest.value = null
  embOllamaModels.value = []
}

async function detectEmbOllama() {
  embBusy.detecting = true
  try {
    const res = await modelConfigApi.listOllamaModels(embForm.base_url || undefined)
    embOllamaModels.value = res.models.map(m => m.name).filter(Boolean) as string[]
    if (!embOllamaModels.value.length) ElMessage.warning('未检测到本地模型，请先 `ollama pull bge-m3`')
    else { if (!embForm.model) embForm.model = embOllamaModels.value[0]; ElMessage.success(`检测到 ${embOllamaModels.value.length} 个本地模型`) }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '检测失败，请确认 Ollama 已启动')
  } finally {
    embBusy.detecting = false
  }
}

async function testEmbedding() {
  embBusy.testing = true
  embTest.value = null
  try {
    embTest.value = await modelConfigApi.testEmbedding({
      provider: embForm.provider, model: embForm.model || undefined,
      api_key: embForm.api_key || undefined, base_url: embForm.base_url || undefined,
    })
  } catch (e: any) {
    embTest.value = { ok: false, error: e?.response?.data?.detail || e?.message || '测试失败' }
  } finally {
    embBusy.testing = false
  }
}

async function saveEmbedding() {
  try {
    await ElMessageBox.confirm(
      `更换向量模型有风险：新模型维度必须等于 ${embRequiredDim.value}，否则会与已建索引不兼容（系统会校验并拒绝）。确认保存？`,
      '确认保存向量模型', { type: 'warning' }
    )
  } catch { return }
  embBusy.saving = true
  try {
    const res = await modelConfigApi.updateEmbeddingConfig({
      provider: embForm.provider, model: embForm.model || undefined,
      api_key: embForm.api_key || undefined, base_url: embForm.base_url || undefined,
    })
    ElMessage.success(`已保存并生效（维度 ${res.dim}）`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '保存失败')
  } finally {
    embBusy.saving = false
  }
}

// ===== 重排模型（Rerank）=====
const rrkProviders = ref<ProviderInfo[]>([])
const rrkTest = ref<RerankTestResult | null>(null)
const rrkBusy = reactive({ loading: false, testing: false, saving: false })
const rrkForm = reactive({ provider: '', model: '', base_url: '', api_key: '', showKey: false, enabled: true, top_k: 10 })
const rrkProviderInfo = computed(() => findProvider(rrkProviders.value, rrkForm.provider))

async function loadRerank() {
  rrkBusy.loading = true
  try {
    const [cat, cfg] = await Promise.all([
      modelConfigApi.getRerankCatalog(),
      modelConfigApi.getRerankConfig(),
    ])
    rrkProviders.value = cat.providers
    rrkForm.provider = cfg.provider
    rrkForm.model = cfg.model || ''
    rrkForm.base_url = cfg.base_url || ''
    rrkForm.api_key = cfg.api_key || ''
    rrkForm.enabled = cfg.enabled
    rrkForm.top_k = cfg.top_k || 10
  } catch (e: any) {
    ElMessage.error('加载重排模型配置失败：' + (e?.response?.data?.detail || e?.message || e))
  } finally {
    rrkBusy.loading = false
  }
}

async function testRerank() {
  rrkBusy.testing = true
  rrkTest.value = null
  try {
    rrkTest.value = await modelConfigApi.testRerank({
      provider: rrkForm.provider, model: rrkForm.model || undefined,
      api_key: rrkForm.api_key || undefined, base_url: rrkForm.base_url || undefined,
    })
  } catch (e: any) {
    rrkTest.value = { ok: false, error: e?.response?.data?.detail || e?.message || '测试失败' }
  } finally {
    rrkBusy.testing = false
  }
}

async function saveRerank() {
  rrkBusy.saving = true
  try {
    await modelConfigApi.updateRerankConfig({
      provider: rrkForm.provider, model: rrkForm.model || undefined,
      api_key: rrkForm.api_key || undefined, base_url: rrkForm.base_url || undefined,
      enabled: rrkForm.enabled, top_k: rrkForm.top_k,
    })
    ElMessage.success('重排配置已保存并生效')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '保存失败')
  } finally {
    rrkBusy.saving = false
  }
}

const providers = ref<ProviderInfo[]>([])
const cloudProviders = computed(() => providers.value.filter(p => p.group === 'cloud'))
const localProviders = computed(() => providers.value.filter(p => p.group === 'local'))

const roles: { key: ChatRole; label: string; desc: string; primary?: boolean }[] = [
  { key: 'chat', label: '默认对话模型', desc: '通用问答与检索增强对话的主模型（保存后立即生效）', primary: true },
  { key: 'finance', label: '金融专家模型', desc: '财务分析类智能体' },
  { key: 'tax', label: '税务专家模型', desc: '税务问答与计算类智能体' },
  { key: 'legal', label: '法律专家模型', desc: '合同 / 法规类智能体' },
]

interface RoleForm {
  enabled: boolean
  provider: string
  model: string
  base_url: string
  api_key: string
  showKey: boolean
  testing: boolean
  saving: boolean
  detecting: boolean
  testResult: TestConnectionResult | null
  ollamaModels: string[]
}

const forms = reactive<Record<string, RoleForm>>({})
const loading = ref(false)

function blankForm(provider = 'zhipu'): RoleForm {
  return {
    enabled: false,
    provider,
    model: '',
    base_url: '',
    api_key: '',
    showKey: false,
    testing: false,
    saving: false,
    detecting: false,
    testResult: null,
    ollamaModels: [],
  }
}

function providerInfo(id: string): ProviderInfo | undefined {
  return providers.value.find(p => p.id === id)
}

onMounted(load)

async function load() {
  loading.value = true
  try {
    const [cat, cfg] = await Promise.all([
      modelConfigApi.getSupportedProviders(),
      modelConfigApi.getConfig(),
    ])
    providers.value = cat.providers
    const defaultProvider = cfg.default_provider || 'zhipu'
    for (const r of roles) {
      const override = cfg.agent_overrides?.[r.key]
      if (override) {
        forms[r.key] = {
          ...blankForm(override.provider || defaultProvider),
          enabled: override.enabled !== false,
          provider: override.provider || defaultProvider,
          model: override.model || '',
          base_url: override.base_url || '',
          api_key: override.api_key || '',
        }
      } else {
        // 无租户覆盖：用 .env 当前默认 provider/model 预填，反映「当前在用」
        const f = blankForm(defaultProvider)
        f.model = cfg.default_model || providerInfo(defaultProvider)?.configured_model || ''
        forms[r.key] = f
      }
    }
  } catch (e: any) {
    ElMessage.error('加载模型配置失败：' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

function onProviderChange(role: string) {
  const f = forms[role]
  // 切换 provider 时预填该 provider 在 .env 中配置的模型
  f.model = providerInfo(f.provider)?.configured_model || ''
  f.base_url = ''
  f.testResult = null
  f.ollamaModels = []
}

function modelOptions(role: string): string[] {
  const f = forms[role]
  const info = providerInfo(f.provider)
  if (info?.group === 'local' && f.ollamaModels.length) return f.ollamaModels
  return info?.models || []
}

async function detectOllama(role: string) {
  const f = forms[role]
  f.detecting = true
  try {
    const res = await modelConfigApi.listOllamaModels(f.base_url || undefined)
    f.ollamaModels = res.models.map(m => m.name).filter(Boolean) as string[]
    if (!f.ollamaModels.length) {
      ElMessage.warning('未检测到本地模型，请先执行 `ollama pull <模型名>`')
    } else {
      if (!f.model) f.model = f.ollamaModels[0]
      ElMessage.success(`检测到 ${f.ollamaModels.length} 个本地模型`)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '检测失败，请确认 Ollama 已启动')
  } finally {
    f.detecting = false
  }
}

function normalizeBaseUrl(raw: string): { ok: boolean; value?: string } {
  const v = (raw || '').trim()
  if (!v) return { ok: true, value: undefined }
  if (!/^https?:\/\//i.test(v)) return { ok: false }
  return { ok: true, value: v }
}

async function testConnection(role: string) {
  const f = forms[role]
  const bu = normalizeBaseUrl(f.base_url)
  if (!bu.ok) {
    ElMessage.warning('Base URL 需以 http:// 或 https:// 开头，或留空以使用提供商默认地址')
    return
  }
  f.testing = true
  f.testResult = null
  try {
    f.testResult = await modelConfigApi.testConnection({
      provider: f.provider,
      model: f.model || undefined,
      api_key: f.api_key || undefined,
      base_url: bu.value,
    })
  } catch (e: any) {
    f.testResult = { ok: false, error: e?.response?.data?.detail || e?.message || '测试失败' }
  } finally {
    f.testing = false
  }
}

async function save(role: string) {
  const f = forms[role]
  if (!f.provider) {
    ElMessage.warning('请选择提供商')
    return
  }
  const bu = normalizeBaseUrl(f.base_url)
  if (!bu.ok) {
    ElMessage.warning('Base URL 需以 http:// 或 https:// 开头，或留空以使用提供商默认地址')
    return
  }
  const info = providerInfo(f.provider)
  if (info?.requires_api_key && !f.api_key) {
    // 允许留空 -> 回退到 .env 全局配置；仅提示
    ElMessage.info('未填写 API Key，将回退使用服务端 .env 中的全局密钥')
  }
  f.saving = true
  try {
    await modelConfigApi.upsertAgentConfig({
      agent_type: role,
      provider: f.provider,
      model: f.model || undefined,
      api_key: f.api_key || undefined,
      base_url: bu.value,
      enabled: true,
    })
    f.enabled = true
    ElMessage.success('已保存并生效')
  } catch (e: any) {
    ElMessage.error('保存失败：' + (e?.response?.data?.detail || e?.message || e))
  } finally {
    f.saving = false
  }
}

async function reset(role: string) {
  const r = roles.find(x => x.key === role)
  try {
    await ElMessageBox.confirm(
      `确定删除「${r?.label}」的自定义配置吗？删除后该角色将回退到服务端 .env 的全局默认模型。`,
      '确认重置', { type: 'warning' }
    )
  } catch { return }
  try {
    if (forms[role].enabled) {
      await modelConfigApi.deleteAgentConfig(role)
    }
    const defaultProvider = providers.value[0]?.id || 'zhipu'
    forms[role] = blankForm(defaultProvider)
    ElMessage.success('已重置为全局默认')
  } catch (e: any) {
    ElMessage.error('重置失败：' + (e?.response?.data?.detail || e?.message || e))
  }
}
</script>

<template>
  <div class="model-settings" v-loading="loading">
    <header class="page-head">
      <div class="title">
        <Cpu :size="22" />
        <h2>模型配置中心</h2>
      </div>
      <p class="subtitle">
        按用途分类配置大模型，支持云端 API 与本地 Ollama。配置存储于当前企业，
        <strong>未配置项自动回退到服务端 .env 的全局默认</strong>，不会修改你的配置文件。
      </p>
    </header>

    <el-tabs v-model="activeTab" class="tabs">
      <!-- ============ 对话模型 ============ -->
      <el-tab-pane name="chat">
        <template #label><span class="tab-label"><Cloud :size="15" /> 对话模型</span></template>

        <div class="help-bar">
          <el-button type="primary" plain size="small" @click="showHelp = true">
            <Info :size="14" /> 说明详情
          </el-button>
        </div>

        <el-card v-for="r in roles" :key="r.key" class="role-card" shadow="never">
          <template #header>
            <div class="role-head">
              <div>
                <span class="role-name">{{ r.label }}</span>
                <el-tag v-if="r.primary" size="small" type="success" effect="plain" class="ml8">主模型</el-tag>
                <el-tag v-if="forms[r.key]?.enabled" size="small" type="primary" effect="plain" class="ml8">已自定义</el-tag>
                <el-tag v-else size="small" type="info" effect="plain" class="ml8">使用全局默认</el-tag>
                <div class="role-desc">{{ r.desc }}</div>
              </div>
            </div>
          </template>

          <template v-if="forms[r.key]">
            <el-form label-width="92px" label-position="left" class="role-form">
              <el-form-item label="提供商">
                <el-select
                  v-model="forms[r.key].provider" filterable
                  placeholder="选择提供商" style="width: 320px"
                  @change="onProviderChange(r.key)"
                >
                  <el-option-group label="☁ 云端 API">
                    <el-option v-for="p in cloudProviders" :key="p.id" :label="p.name" :value="p.id" />
                  </el-option-group>
                  <el-option-group label="🖥 本地部署">
                    <el-option v-for="p in localProviders" :key="p.id" :label="p.name" :value="p.id" />
                  </el-option-group>
                </el-select>
                <el-tag
                  v-if="providerInfo(forms[r.key].provider)?.group === 'local'"
                  size="small" type="warning" effect="light" class="ml8"
                >
                  <Server :size="12" style="vertical-align:-1px" /> 本地
                </el-tag>
              </el-form-item>

              <el-form-item label="模型">
                <el-select
                  v-model="forms[r.key].model" filterable allow-create default-first-option
                  placeholder="选择或输入模型名" style="width: 320px"
                >
                  <el-option v-for="m in modelOptions(r.key)" :key="m" :label="m" :value="m" />
                </el-select>
                <el-button
                  v-if="providerInfo(forms[r.key].provider)?.supports_detect"
                  class="ml8" :loading="forms[r.key].detecting" @click="detectOllama(r.key)"
                >
                  <Download :size="14" /> 检测本地模型
                </el-button>
              </el-form-item>

              <el-form-item label="Base URL">
                <el-input
                  v-model="forms[r.key].base_url"
                  :placeholder="providerInfo(forms[r.key].provider)?.default_base_url || '默认（留空使用提供商默认地址）'"
                  style="width: 420px"
                  autocomplete="off" name="model-cfg-base-url"
                />
              </el-form-item>

              <el-form-item
                v-if="providerInfo(forms[r.key].provider)?.requires_api_key"
                label="API Key"
              >
                <el-input
                  v-model="forms[r.key].api_key"
                  :type="forms[r.key].showKey ? 'text' : 'password'"
                  placeholder="留空则回退使用服务端 .env 全局密钥" style="width: 420px"
                  autocomplete="new-password" name="model-cfg-api-key"
                >
                  <template #suffix>
                    <component
                      :is="forms[r.key].showKey ? EyeOff : Eye" :size="15"
                      style="cursor:pointer" @click="forms[r.key].showKey = !forms[r.key].showKey"
                    />
                  </template>
                </el-input>
              </el-form-item>

              <el-form-item v-if="providerInfo(forms[r.key].provider)?.note">
                <el-text type="warning" size="small">
                  <Info :size="13" style="vertical-align:-2px" /> {{ providerInfo(forms[r.key].provider)?.note }}
                </el-text>
              </el-form-item>

              <!-- 测试结果 -->
              <el-form-item v-if="forms[r.key].testResult">
                <el-text v-if="forms[r.key].testResult!.ok" type="success" size="small">
                  <CheckCircle2 :size="14" style="vertical-align:-2px" />
                  连接正常（{{ forms[r.key].testResult!.latency_ms }}ms）
                  <span v-if="forms[r.key].testResult!.sample"> · 返回：{{ forms[r.key].testResult!.sample }}</span>
                </el-text>
                <el-text v-else type="danger" size="small">
                  <XCircle :size="14" style="vertical-align:-2px" />
                  {{ forms[r.key].testResult!.error }}
                </el-text>
              </el-form-item>

              <el-form-item>
                <el-button :loading="forms[r.key].testing" @click="testConnection(r.key)">
                  <Zap :size="14" /> 测试连接
                </el-button>
                <el-button type="primary" :loading="forms[r.key].saving" @click="save(r.key)">
                  <Save :size="14" /> 保存
                </el-button>
                <el-button text @click="reset(r.key)">
                  <RotateCcw :size="14" /> 重置为默认
                </el-button>
              </el-form-item>
            </el-form>
          </template>
        </el-card>
      </el-tab-pane>

      <!-- ============ 使用概览（管理员视角） ============ -->
      <el-tab-pane name="usage">
        <template #label><span class="tab-label"><BarChart3 :size="15" /> 使用概览</span></template>

        <div v-loading="overviewLoading">
          <div class="ov-head">
            <el-text size="small" type="info">
              全局默认：<b>{{ overview?.env_default.provider }}</b> / {{ overview?.env_default.model || '—' }}
            </el-text>
            <el-button text size="small" @click="loadOverview">
              <RefreshCw :size="13" /> 刷新
            </el-button>
          </div>

          <el-alert v-if="overview?.note" type="info" :closable="false" show-icon class="ov-note" :title="overview.note" />

          <el-empty v-if="overview && !overview.tenants.length" description="暂无企业数据" />

          <el-card
            v-for="t in overview?.tenants || []" :key="t.tenant_id"
            class="ov-card" shadow="never"
          >
            <template #header>
              <div class="ov-card-head">
                <div>
                  <span class="ov-company">{{ t.company_name }}</span>
                  <span class="ov-tenant">租户 {{ t.tenant_id }}</span>
                </div>
                <div class="ov-usage">
                  <el-tag size="small" type="primary" effect="plain">对话 {{ t.usage.total_conversations }} 次</el-tag>
                  <el-tag size="small" type="warning" effect="plain">工具调用 {{ t.usage.total_tool_calls }} 次</el-tag>
                  <el-tag size="small" type="success" effect="plain">最近模型：{{ t.usage.last_model || '未记录' }}</el-tag>
                  <el-tag size="small" type="info" effect="plain">最近对话：{{ fmtTime(t.usage.last_conversation_at) }}</el-tag>
                </div>
              </div>
            </template>

            <el-table :data="t.roles" size="small">
              <el-table-column prop="label" label="角色" width="120" />
              <el-table-column prop="provider" label="提供商" width="140" />
              <el-table-column prop="model" label="当前生效模型">
                <template #default="{ row }">{{ row.model || '—' }}</template>
              </el-table-column>
              <el-table-column label="来源" width="120">
                <template #default="{ row }">
                  <el-tag v-if="row.source === 'custom'" size="small" type="primary" effect="plain">自定义</el-tag>
                  <el-tag v-else size="small" type="info" effect="plain">全局默认</el-tag>
                </template>
              </el-table-column>
            </el-table>

            <div v-if="t.usage.model_counts && t.usage.model_counts.length" class="ov-models">
              <span class="ov-models-label">各模型调用次数：</span>
              <el-tag
                v-for="mc in t.usage.model_counts" :key="mc.model"
                size="small" effect="plain" class="ov-model-tag"
              >
                {{ mc.model }} · {{ mc.count }}
              </el-tag>
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ============ 向量模型 Embedding（部署级） ============ -->
      <el-tab-pane name="embedding">
        <template #label><span class="tab-label"><RefreshCw :size="15" /> 向量模型</span></template>

        <el-alert
          type="warning" :closable="false" show-icon class="hint"
          title="部署级配置 · 维度必须匹配"
          :description="`向量模型为整个部署共用（非按租户）。新模型输出维度必须等于 ${embRequiredDim}，否则与已建索引不兼容，保存时会被拒绝。更换不同维度模型需先重建知识库索引。`"
        />

        <el-card class="role-card" shadow="never" v-loading="embBusy.loading">
          <el-form label-width="92px" label-position="left" class="role-form">
            <el-form-item label="提供商">
              <el-select v-model="embForm.provider" filterable style="width: 320px" @change="onEmbProviderChange">
                <el-option-group label="☁ 云端 API">
                  <el-option v-for="p in embCloud" :key="p.id" :label="p.name" :value="p.id" />
                </el-option-group>
                <el-option-group label="🖥 本地部署">
                  <el-option v-for="p in embLocal" :key="p.id" :label="p.name" :value="p.id" />
                </el-option-group>
              </el-select>
              <el-tag size="small" type="info" effect="plain" class="ml8">要求 {{ embRequiredDim }} 维</el-tag>
            </el-form-item>

            <el-form-item label="模型">
              <el-select v-model="embForm.model" filterable allow-create default-first-option placeholder="选择或输入模型名" style="width: 320px">
                <el-option v-for="m in embModelOptions()" :key="m" :label="m" :value="m" />
              </el-select>
              <el-button v-if="embProviderInfo?.supports_detect" class="ml8" :loading="embBusy.detecting" @click="detectEmbOllama">
                <Download :size="14" /> 检测本地模型
              </el-button>
            </el-form-item>

            <el-form-item label="Base URL">
              <el-input v-model="embForm.base_url" :placeholder="embProviderInfo?.default_base_url || '默认（留空使用提供商默认地址）'" style="width: 420px" autocomplete="off" name="emb-base-url" />
            </el-form-item>

            <el-form-item v-if="embProviderInfo?.requires_api_key" label="API Key">
              <el-input v-model="embForm.api_key" :type="embForm.showKey ? 'text' : 'password'" placeholder="留空则回退使用服务端 .env 全局密钥" style="width: 420px" autocomplete="new-password" name="emb-api-key">
                <template #suffix>
                  <component :is="embForm.showKey ? EyeOff : Eye" :size="15" style="cursor:pointer" @click="embForm.showKey = !embForm.showKey" />
                </template>
              </el-input>
            </el-form-item>

            <el-form-item v-if="embProviderInfo?.note">
              <el-text type="warning" size="small"><Info :size="13" style="vertical-align:-2px" /> {{ embProviderInfo?.note }}</el-text>
            </el-form-item>

            <el-form-item v-if="embTest">
              <el-text v-if="embTest.ok && embTest.compatible" type="success" size="small">
                <CheckCircle2 :size="14" style="vertical-align:-2px" /> 可用，输出 {{ embTest.dim }} 维（与索引兼容）
              </el-text>
              <el-text v-else-if="embTest.ok" type="danger" size="small">
                <XCircle :size="14" style="vertical-align:-2px" /> 输出 {{ embTest.dim }} 维，与要求 {{ embTest.required_dim }} 维不兼容，保存会被拒绝
              </el-text>
              <el-text v-else type="danger" size="small"><XCircle :size="14" style="vertical-align:-2px" /> {{ embTest.error }}</el-text>
            </el-form-item>

            <el-form-item>
              <el-button :loading="embBusy.testing" @click="testEmbedding"><Zap :size="14" /> 测试 / 检测维度</el-button>
              <el-button type="primary" :loading="embBusy.saving" @click="saveEmbedding"><Save :size="14" /> 保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- ============ 重排模型 Rerank（部署级） ============ -->
      <el-tab-pane name="rerank">
        <template #label><span class="tab-label"><RefreshCw :size="15" /> 重排模型</span></template>

        <el-alert
          type="info" :closable="false" show-icon class="hint"
          title="部署级配置"
          description="重排（Rerank）模型为整个部署共用。本地 Ollama 无原生 Rerank；本地优先场景可关闭重排或继续使用云端重排服务。"
        />

        <el-card class="role-card" shadow="never" v-loading="rrkBusy.loading">
          <el-form label-width="92px" label-position="left" class="role-form">
            <el-form-item label="启用重排">
              <el-switch v-model="rrkForm.enabled" />
              <el-text size="small" type="info" class="ml8">关闭后检索将跳过重排，直接用融合排序结果</el-text>
            </el-form-item>

            <template v-if="rrkForm.enabled">
              <el-form-item label="提供商">
                <el-select v-model="rrkForm.provider" filterable style="width: 320px">
                  <el-option v-for="p in rrkProviders" :key="p.id" :label="p.name" :value="p.id" />
                </el-select>
              </el-form-item>

              <el-form-item label="模型">
                <el-select v-model="rrkForm.model" filterable allow-create default-first-option placeholder="选择或输入模型名" style="width: 320px">
                  <el-option v-for="m in (rrkProviderInfo?.models || [])" :key="m" :label="m" :value="m" />
                </el-select>
              </el-form-item>

              <el-form-item label="Base URL">
                <el-input v-model="rrkForm.base_url" :placeholder="rrkProviderInfo?.default_base_url || '重排服务地址'" style="width: 420px" autocomplete="off" name="rrk-base-url" />
              </el-form-item>

              <el-form-item v-if="rrkProviderInfo?.requires_api_key" label="API Key">
                <el-input v-model="rrkForm.api_key" :type="rrkForm.showKey ? 'text' : 'password'" placeholder="留空则回退使用服务端 .env 全局密钥" style="width: 420px" autocomplete="new-password" name="rrk-api-key">
                  <template #suffix>
                    <component :is="rrkForm.showKey ? EyeOff : Eye" :size="15" style="cursor:pointer" @click="rrkForm.showKey = !rrkForm.showKey" />
                  </template>
                </el-input>
              </el-form-item>

              <el-form-item label="Top K">
                <el-input-number v-model="rrkForm.top_k" :min="1" :max="50" />
              </el-form-item>

              <el-form-item v-if="rrkTest">
                <el-text v-if="rrkTest.ok" type="success" size="small">
                  <CheckCircle2 :size="14" style="vertical-align:-2px" /> 可用（{{ rrkTest.latency_ms }}ms，返回 {{ rrkTest.results_count }} 条）
                </el-text>
                <el-text v-else type="danger" size="small"><XCircle :size="14" style="vertical-align:-2px" /> {{ rrkTest.error }}</el-text>
              </el-form-item>
            </template>

            <el-form-item>
              <el-button v-if="rrkForm.enabled" :loading="rrkBusy.testing" @click="testRerank"><Zap :size="14" /> 测试连接</el-button>
              <el-button type="primary" :loading="rrkBusy.saving" @click="saveRerank"><Save :size="14" /> 保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 说明详情抽屉 -->
    <el-drawer v-model="showHelp" title="模型配置 · 使用说明" size="46%" :append-to-body="true">
      <div class="help-doc">
        <section>
          <h4>这是什么</h4>
          <p>
            按 <b>企业（租户）</b> 配置各类大模型。配置保存在数据库，<b>未配置的项会自动回退到服务端
            <code>.env</code> 的全局默认</b>，本页面 <b>不会修改你的 <code>.env</code> 文件</b>。
          </p>
        </section>

        <section>
          <h4>三类模型</h4>
          <ul>
            <li><b>对话模型</b>（已开放）：问答 / 检索增强对话的主模型，以及各领域专家智能体。</li>
            <li><b>向量模型</b>（第 2 步开放）：文档向量化，切换会改变向量维度、需重建索引。</li>
            <li><b>重排模型</b>（第 3 步开放）：检索结果重排序。</li>
          </ul>
        </section>

        <section>
          <h4>对话模型的角色</h4>
          <ul>
            <li><b>默认对话模型（主模型）</b>：检索增强问答的主力模型，保存后对当前企业 <b>立即生效</b>。</li>
            <li><b>金融 / 税务 / 法律 专家模型</b>：对应领域智能体专用，可与主模型用不同的模型/供应商。</li>
          </ul>
        </section>

        <section>
          <h4>每个字段怎么填</h4>
          <ul>
            <li>
              <b>提供商</b>：分两组——<el-tag size="small" effect="plain">☁ 云端 API</el-tag>
              （OpenRouter / 智谱 / OpenAI / Claude / MiniMax 等）与
              <el-tag size="small" type="warning" effect="plain">🖥 本地部署</el-tag>（Ollama）。
            </li>
            <li><b>模型</b>：下拉已自动带出 <code>.env</code> 当前在用的模型并置顶；也可直接输入任意模型名。</li>
            <li>
              <b>Base URL</b>：<b>留空 = 使用该提供商默认地址</b>（占位文字即默认值）；
              如需自定义，必须以 <code>http://</code> 或 <code>https://</code> 开头。
            </li>
            <li>
              <b>API Key</b>：<b>留空 = 回退使用服务端 <code>.env</code> 的全局密钥</b>；
              填写则为该企业单独使用此密钥。
            </li>
          </ul>
        </section>

        <section>
          <h4>使用本地 Ollama</h4>
          <ol>
            <li>宿主机先启动：<code>ollama serve</code>，并拉取模型：<code>ollama pull qwen2.5</code>。</li>
            <li>提供商选 <b>Ollama（本地部署）</b>，点 <b>「检测本地模型」</b> 自动拉取已安装模型列表。</li>
            <li>必须选 <b>支持 Function Calling 的模型</b>（如 qwen2.5、llama3.1），否则工具调用不可用。</li>
          </ol>
          <el-alert
            type="warning" :closable="false" show-icon class="doc-alert"
            title="后端运行在 Docker 时注意"
            description="容器内的 localhost 指向容器自身，连不到宿主机的 Ollama。请把 Base URL 填为 http://host.docker.internal:11434/v1（Windows Docker Desktop 支持）。"
          />
        </section>

        <section>
          <h4>三个操作按钮</h4>
          <ul>
            <li><b>测试连接</b>：用当前填写的配置发一次最小请求，验证地址/密钥是否可用，并显示延迟与返回样例。</li>
            <li><b>保存</b>：写入当前企业配置并立即生效。</li>
            <li><b>重置为默认</b>：删除该角色的自定义配置，回退到服务端 <code>.env</code> 的全局默认模型。</li>
          </ul>
        </section>

        <section>
          <h4>生效范围</h4>
          <p>
            「默认对话模型」在 <b>检索增强（agentic）对话主链路</b> 必定生效；金融/税务/法律专家配置在走
            <b>专家路由</b> 的环节生效。配置变更对当前企业的新对话立即起作用，无需重启。
          </p>
        </section>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.model-settings { padding: 20px; max-width: 920px; margin: 0 auto; }
.page-head { margin-bottom: 16px; }
.title { display: flex; align-items: center; gap: 8px; }
.title h2 { margin: 0; font-size: 20px; }
.subtitle { color: var(--el-text-color-secondary); font-size: 13px; margin: 6px 0 0; line-height: 1.6; }
.tabs { margin-top: 8px; }
.tab-label { display: inline-flex; align-items: center; gap: 6px; }
.help-bar { display: flex; justify-content: flex-end; margin-bottom: 12px; }
.help-doc { font-size: 13px; line-height: 1.75; color: var(--el-text-color-primary); }
.help-doc section { margin-bottom: 18px; }
.help-doc h4 { margin: 0 0 6px; font-size: 14px; color: var(--el-color-primary); }
.help-doc ul, .help-doc ol { margin: 4px 0; padding-left: 20px; }
.help-doc li { margin: 4px 0; }
.help-doc p { margin: 4px 0; color: var(--el-text-color-regular); }
.help-doc code {
  background: var(--el-fill-color-light); padding: 1px 5px; border-radius: 4px;
  font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px;
}
.doc-alert { margin-top: 8px; }
.ov-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.ov-note { margin-bottom: 14px; }
.ov-card { margin-bottom: 14px; }
.ov-card-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.ov-company { font-weight: 600; font-size: 15px; }
.ov-tenant { color: var(--el-text-color-secondary); font-size: 12px; margin-left: 10px; }
.ov-usage { display: flex; gap: 8px; flex-wrap: wrap; }
.ov-models { margin-top: 10px; display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.ov-models-label { font-size: 12px; color: var(--el-text-color-secondary); }
.ov-model-tag { font-family: ui-monospace, Menlo, Consolas, monospace; }
.role-card { margin-bottom: 14px; }
.role-head { display: flex; justify-content: space-between; align-items: flex-start; }
.role-name { font-weight: 600; font-size: 15px; }
.role-desc { color: var(--el-text-color-secondary); font-size: 12px; margin-top: 4px; }
.role-form { margin-top: 4px; }
.ml8 { margin-left: 8px; }
:deep(.el-form-item) { margin-bottom: 14px; }
</style>
