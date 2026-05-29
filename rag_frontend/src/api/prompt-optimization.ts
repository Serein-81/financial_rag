// Prompt 自我优化 API
// 对应后端 rag_backend/app/api/v1/endpoints/prompt_optimization.py
import { request, get, post } from '@/utils/request'

// 后端 main.py 注册 prefix 为 /api/v1/prompt（与已有 prompt.ts 同前缀）
const PREFIX = '/prompt'

// ==================== Types ====================

export interface TemplateCreate {
  name: string
  version: string
  template_text: string
  agent_type: string
  use_case?: string
  variables?: Record<string, any>
  description?: string
  is_baseline?: boolean
}

export interface TemplateResponse {
  id: string
  name: string
  version: string
  agent_type: string
  use_case: string
  is_active: boolean
  is_baseline: boolean
  description?: string | null
  created_at: string
}

export interface TemplateDetail extends TemplateResponse {
  template_text: string
  variables?: Record<string, any> | null
}

export interface ExecutionRecord {
  template_id: string
  user_query: string
  trace_id?: string
  final_answer?: string
  execution_time?: number
  iterations_count?: number
  tool_calls_count?: number
  success?: boolean
  user_feedback?: number
  auto_score?: number
  error_type?: string
  error_message?: string
}

export interface Execution {
  id: string
  user_query: string
  success: boolean
  execution_time?: number | null
  iterations_count?: number | null
  auto_score?: number | null
  created_at: string
}

export interface PerformanceMetrics {
  template_id: string
  total_executions: number
  success_rate: number
  avg_execution_time?: number
  avg_iterations?: number
  avg_user_feedback?: number
  avg_auto_score?: number
  days: number
  [key: string]: any
}

export interface TemplateComparison {
  template_a: PerformanceMetrics
  template_b: PerformanceMetrics
  winner?: 'template_a' | 'template_b' | 'tie' | null
  significance?: number
}

export interface OptimizationSuggestion {
  category: string
  priority: 'high' | 'medium' | 'low' | string
  description: string
  expected_improvement?: string
}

export interface ABTestCreate {
  test_name: string
  template_a_id: string
  template_b_id: string
  traffic_split?: number
  description?: string
}

export interface ABTestResponse {
  id: string
  test_name: string
  status: string
  template_a_id: string
  template_b_id: string
  traffic_split: number
  total_executions: number
  winner_template_id?: string | null
}

export interface ABTestResults {
  test_id: string
  template_a_metrics?: PerformanceMetrics
  template_b_metrics?: PerformanceMetrics
  winner?: 'template_a' | 'template_b' | 'tie' | null
  confidence?: number
  recommendation?: string
  [key: string]: any
}

// ==================== API ====================

export const promptOptimizationApi = {
  // Templates
  async createTemplate(payload: TemplateCreate): Promise<TemplateResponse> {
    return post(`${PREFIX}/templates`, payload)
  },

  async listTemplates(params: {
    agent_type?: string
    use_case?: string
    is_active?: boolean
  } = {}): Promise<TemplateResponse[]> {
    return get(`${PREFIX}/templates`, { params })
  },

  async getTemplate(id: string): Promise<TemplateDetail> {
    return get(`${PREFIX}/templates/${id}`)
  },

  async updateTemplateStatus(id: string, is_active: boolean): Promise<{ message: string; is_active: boolean }> {
    return request(`${PREFIX}/templates/${id}/status`, {
      method: 'PATCH',
      params: { is_active },
    })
  },

  // Executions
  async recordExecution(payload: ExecutionRecord): Promise<{ message: string; execution_id: string }> {
    return post(`${PREFIX}/executions`, payload)
  },

  async getTemplateExecutions(id: string, limit = 100): Promise<{
    template_id: string
    total: number
    executions: Execution[]
  }> {
    return get(`${PREFIX}/templates/${id}/executions`, { params: { limit } })
  },

  // Performance analysis
  async analyzeTemplatePerformance(id: string, days = 7): Promise<PerformanceMetrics> {
    return get(`${PREFIX}/templates/${id}/performance`, { params: { days } })
  },

  async compareTemplates(template_a_id: string, template_b_id: string, days = 7): Promise<TemplateComparison> {
    return get(`${PREFIX}/templates/compare`, {
      params: { template_a_id, template_b_id, days },
    })
  },

  async getOptimizationSuggestions(id: string, days = 7): Promise<{
    template_id: string
    suggestions: OptimizationSuggestion[]
  }> {
    return get(`${PREFIX}/templates/${id}/suggestions`, { params: { days } })
  },

  // A/B tests
  async createABTest(payload: ABTestCreate): Promise<ABTestResponse> {
    return post(`${PREFIX}/ab-tests`, payload)
  },

  async listABTests(status?: string): Promise<ABTestResponse[]> {
    return get(`${PREFIX}/ab-tests`, { params: status ? { status } : {} })
  },

  async getABTestResults(test_id: string): Promise<ABTestResults> {
    return get(`${PREFIX}/ab-tests/${test_id}/results`)
  },

  async completeABTest(test_id: string, winner: 'template_a' | 'template_b'): Promise<{ message: string; winner: string }> {
    return post(`${PREFIX}/ab-tests/${test_id}/complete`, undefined, {
      params: { winner },
    })
  },

  async selectTemplateForTest(test_name: string): Promise<{ template_id: string }> {
    return get(`${PREFIX}/ab-tests/${test_name}/select-template`)
  },
}
