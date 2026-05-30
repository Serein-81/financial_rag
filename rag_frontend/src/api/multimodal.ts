// 多模态配置 API
// 对应后端 rag_backend/app/api/v1/endpoints/multimodal_config.py
import { request, get, post, del } from '@/utils/request'

// ==================== Types ====================

export type ParseMode = 'basic' | 'rule_based' | 'ai_enhanced'

export interface MultimodalConfigCreate {
  enabled: boolean
  table_mode: ParseMode
  chart_mode: ParseMode
  image_mode: ParseMode
  vision_model?: string
  llm_model?: string
  use_own_api_key: boolean
  /** 主 API Key（向后兼容，取 provider_api_keys 中必填 provider 的值） */
  user_api_key?: string
  /** 各 provider 独立 API Key，存入 custom_config.provider_api_keys */
  provider_api_keys?: Record<string, string>
  daily_ai_limit: number
  enable_cache?: boolean
  ai_timeout?: number
  max_concurrent?: number
}

export interface MultimodalConfigUpdate {
  enabled?: boolean
  table_mode?: ParseMode
  chart_mode?: ParseMode
  image_mode?: ParseMode
  vision_model?: string
  llm_model?: string
  use_own_api_key?: boolean
  user_api_key?: string
  provider_api_keys?: Record<string, string>
  daily_ai_limit?: number
  enable_cache?: boolean
  ai_timeout?: number
  max_concurrent?: number
}

export interface MultimodalConfig {
  tenant_id?: string
  enabled: boolean
  modes: {
    table: ParseMode
    chart: ParseMode
    image: ParseMode
  }
  models: {
    vision: string
    llm: string
  }
  use_own_api_key: boolean
  cost_control: {
    daily_limit: number
    daily_used: number
    total_calls: number
  }
  performance: {
    enable_cache: boolean
    ai_timeout: number
    max_concurrent: number
  }
  /** 自定义配置，包含 provider_api_keys 等扩展字段 */
  custom_config?: {
    provider_api_keys?: Record<string, boolean>  // 仅返回是否已配置，不返回明文
    [key: string]: unknown
  }
  is_default?: boolean
}

export interface CostEstimate {
  modes: {
    table: ParseMode
    chart: ParseMode
    image: ParseMode
  }
  cost_per_1k_objects: {
    table: string
    chart: string
    image: string
  }
  total_cost_per_1k_docs: string
  note?: string
}

export interface UsageStats {
  daily_limit: number
  daily_used: number
  daily_remaining: number
  total_calls: number
  cost_estimate: CostEstimate | { total_cost_per_1k_docs: string }
}

export interface UsageLog {
  id: string
  tenant_id: string
  content_type: string
  parse_mode: ParseMode
  model_used?: string | null
  total_tokens?: number | null
  response_time_ms?: number | null
  success: boolean
  error_message?: string | null
  created_at: string
}

export interface UsageSummary {
  period: string
  total_calls: number
  success_rate: string
  by_content_type: Array<{
    content_type: string
    count: number
    total_tokens: number
    avg_response_time_ms: number
  }>
  by_mode: Array<{
    mode: ParseMode
    count: number
  }>
}

export interface AvailableModel {
  id: string
  name: string
  provider: string
  cost: string
  speed: string
  quality: string
  recommended: boolean
}

export interface AvailableModels {
  vision_models: AvailableModel[]
  llm_models: AvailableModel[]
}

// ==================== API ====================

export const multimodalApi = {
  // Config
  async getConfig(): Promise<MultimodalConfig> {
    return get('/multimodal/config')
  },

  async upsertConfig(payload: MultimodalConfigCreate): Promise<{ message: string; config: MultimodalConfig }> {
    return post('/multimodal/config', payload)
  },

  async patchConfig(payload: MultimodalConfigUpdate): Promise<{ message: string; config: MultimodalConfig }> {
    return request('/multimodal/config', { method: 'PATCH', data: payload })
  },

  async deleteConfig(): Promise<{ message: string }> {
    return del('/multimodal/config')
  },

  // Cost & usage
  async getCostEstimate(): Promise<CostEstimate> {
    return get('/multimodal/config/cost-estimate')
  },

  async getUsageStats(): Promise<UsageStats> {
    return get('/multimodal/usage/stats')
  },

  async getUsageLogs(params: { limit?: number; offset?: number; content_type?: string } = {}): Promise<{
    total: number
    limit: number
    offset: number
    logs: UsageLog[]
  }> {
    return get('/multimodal/usage/logs', { params })
  },

  async getUsageSummary(days = 7): Promise<UsageSummary> {
    return get('/multimodal/usage/summary', { params: { days } })
  },

  // Models
  async getAvailableModels(): Promise<AvailableModels> {
    return get('/multimodal/models/available')
  },
}
