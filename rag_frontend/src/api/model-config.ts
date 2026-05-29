// 模型配置 API
// 对应后端 rag_backend/app/api/v1/endpoints/agent_llm_config.py (prefix: /api/v1/agents)
import { get, post, put, del } from '@/utils/request'

// ==================== Types ====================

export type ProviderGroup = 'cloud' | 'local'

// 对话模型可配置的角色（与后端 AgentType 对应）
export type ChatRole = 'chat' | 'finance' | 'tax' | 'legal'

export interface ProviderInfo {
  id: string
  name: string
  group: ProviderGroup
  requires_api_key: boolean
  default_base_url?: string | null
  supports_detect?: boolean
  note?: string
  models: string[]
  /** .env 中当前实际配置的模型（已置顶到 models） */
  configured_model?: string | null
}

export interface AgentLLMConfig {
  agent_type: string
  provider: string
  model?: string | null
  api_key?: string | null
  base_url?: string | null
  temperature?: number
  max_tokens?: number | null
  enabled?: boolean
}

export interface TenantLLMConfig {
  default_provider: string
  default_model?: string | null
  agent_overrides: Record<string, AgentLLMConfig>
}

export interface UpsertAgentConfigPayload {
  agent_type: ChatRole | string
  provider: string
  model?: string
  api_key?: string
  base_url?: string
  temperature?: number
  max_tokens?: number
  enabled?: boolean
}

export interface TestConnectionPayload {
  provider: string
  model?: string
  api_key?: string
  base_url?: string
}

export interface TestConnectionResult {
  ok: boolean
  error?: string
  latency_ms?: number
  model?: string
  sample?: string
}

export interface OllamaModel {
  name: string
  size?: number
  modified_at?: string
}

export interface RoleModelRow {
  role: string
  label: string
  provider: string
  model?: string | null
  source: 'custom' | 'default'
}

export interface ModelCount {
  model: string
  count: number
}

export interface TenantUsage {
  total_conversations: number
  total_tool_calls: number
  last_conversation_at?: string | null
  /** 最近一次对话实际使用的模型 */
  last_model?: string | null
  /** 各模型调用次数 */
  model_counts?: ModelCount[]
}

export interface TenantOverview {
  tenant_id: string
  company_name: string
  roles: RoleModelRow[]
  usage: TenantUsage
}

export interface UsageOverview {
  generated_at: string
  env_default: { provider: string; model?: string | null }
  note: string
  tenants: TenantOverview[]
}

// ===== 向量模型（Embedding）· 部署级 =====
export interface EmbeddingConfig {
  provider: string
  model?: string | null
  api_key?: string | null
  base_url?: string | null
  is_custom?: boolean
  required_dim?: number
}

export interface EmbeddingTestResult {
  ok: boolean
  error?: string
  dim?: number
  required_dim?: number
  compatible?: boolean
}

// ===== 重排模型（Rerank）· 部署级 =====
export interface RerankConfig {
  provider: string
  model?: string | null
  api_key?: string | null
  base_url?: string | null
  enabled: boolean
  top_k?: number
  is_custom?: boolean
}

export interface RerankTestResult {
  ok: boolean
  error?: string
  latency_ms?: number
  results_count?: number
}

// ==================== API ====================

export const modelConfigApi = {
  /** 获取支持的对话模型提供商目录（含分组与表单元数据） */
  getSupportedProviders: () =>
    get<{ providers: ProviderInfo[] }>('/agents/supported-providers'),

  /** 获取当前租户的对话模型配置 */
  getConfig: () => get<TenantLLMConfig>('/agents/llm-config'),

  /** 创建或更新某个角色的对话模型配置 */
  upsertAgentConfig: (payload: UpsertAgentConfigPayload) =>
    post<{ message: string }>('/agents/llm-config/agent', payload),

  /** 删除某个角色的配置（回退到全局默认） */
  deleteAgentConfig: (agentType: string) =>
    del<{ message: string }>(`/agents/llm-config/agent/${agentType}`),

  /** 测试一组模型配置是否可用 */
  testConnection: (payload: TestConnectionPayload) =>
    post<TestConnectionResult>('/agents/llm-config/test-connection', payload),

  /** 检测本地 Ollama 已安装的模型 */
  listOllamaModels: (baseUrl?: string) =>
    get<{ base_url: string; models: OllamaModel[] }>(
      '/agents/llm-config/ollama/models',
      baseUrl ? { params: { base_url: baseUrl } } : {}
    ),

  /** 管理员视角：各企业/各角色当前生效模型 + 调用统计 */
  getUsageOverview: () => get<UsageOverview>('/agents/llm-config/usage-overview'),

  // ===== 向量模型（Embedding）=====
  getEmbeddingConfig: () => get<EmbeddingConfig>('/agents/llm-config/embedding'),
  getEmbeddingCatalog: () =>
    get<{ providers: ProviderInfo[]; required_dim: number }>('/agents/llm-config/embedding/catalog'),
  testEmbedding: (p: Partial<EmbeddingConfig>) =>
    post<EmbeddingTestResult>('/agents/llm-config/embedding/test', p),
  updateEmbeddingConfig: (p: Partial<EmbeddingConfig>) =>
    put<{ message: string; dim: number }>('/agents/llm-config/embedding', p),

  // ===== 重排模型（Rerank）=====
  getRerankConfig: () => get<RerankConfig>('/agents/llm-config/rerank'),
  getRerankCatalog: () =>
    get<{ providers: ProviderInfo[] }>('/agents/llm-config/rerank/catalog'),
  testRerank: (p: Partial<RerankConfig>) =>
    post<RerankTestResult>('/agents/llm-config/rerank/test', p),
  updateRerankConfig: (p: Partial<RerankConfig>) =>
    put<{ message: string }>('/agents/llm-config/rerank', p),
}

export default modelConfigApi
