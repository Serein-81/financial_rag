import { request } from '@/utils/request'

export interface TaxAnalysisRequest {
  financial_data?: Record<string, any>
  tax_type?: string
  fiscal_year?: number
  fiscal_period?: string
  company_name?: string
  industry?: string
}

export interface TaxAnalysisResult {
  analysis_id: string
  analysis_type: string
  fiscal_year: number
  fiscal_period: string
  status: string
  financial_summary: {
    revenue: number
    expenses: number
    profit: number
    tax_amount: number
    effective_tax_rate: number
  }
  tax_calculations: Array<{
    tax_type: string
    taxable_amount: number
    tax_rate: number
    tax_payable: number
    deductions: number
  }>
  compliance_issues: Array<{
    severity: 'low' | 'medium' | 'high' | 'critical'
    category: string
    description: string
    recommendation: string
  }>
  risk_score: number
  confidence: number
  created_at: string
}

export interface TaxReport {
  id: string
  analysis_id: string
  analysis_type: string
  fiscal_year: number
  fiscal_period: string
  status: string
  risk_score: number
  confidence_score: string
  created_at: string
  updated_at: string
}

export interface TaxIntelligenceStatistics {
  total_analyses: number
  current_quarter_analyses: number
  high_risk_count: number
  compliance_rate: number
}

export interface PolicyQueryParams {
  query: string
  tax_types?: string[]
  industries?: string[]
  regions?: string[]
  top_k?: number
}

export interface PolicyMatchItem {
  policy_id: string
  policy_name: string
  policy_content: string
  match_level: string
  applicable_conditions: string[]
  potential_savings: number
  source_url?: string
  source_name?: string
  industries?: string[]
  regions?: string[]
  tax_types?: string[]
  effective_date?: string
  expiry_date?: string
}

export interface PolicyQueryResponse {
  policies: PolicyMatchItem[]
  total_count: number
  query: string
}

export interface ExplainRequest {
  question?: string
}

export interface ExplainResponse {
  explanation: string
  confidence: number
  related_policies?: string[]
  follow_up_suggestions?: string[]
}

export const taxIntelligenceApi = {
  analyzeTax: async (params: TaxAnalysisRequest): Promise<TaxAnalysisResult> => {
    return request('/tax-intelligence/analyze', {
      method: 'POST',
      data: params
    })
  },

  getAnalysisHistory: async (params: {
    page?: number
    page_size?: number
    tax_type?: string
    start_date?: string
    end_date?: string
  } = {}): Promise<{
    analyses: TaxReport[]
    total: number
    page: number
    page_size: number
  }> => {
    return request('/tax-intelligence/history', {
      method: 'GET',
      params
    })
  },

  getAnalysisDetail: async (analysisId: string): Promise<TaxAnalysisResult> => {
    return request(`/tax-intelligence/report/${analysisId}`, {
      method: 'GET'
    })
  },

  getReportById: async (analysisId: string): Promise<TaxAnalysisResult> => {
    return request(`/tax-intelligence/report/${analysisId}`, {
      method: 'GET'
    })
  },

  exportReportPdf: async (analysisId: string): Promise<Blob> => {
    const response = await request(`/tax-intelligence/report/${analysisId}/export`, {
      method: 'GET',
      responseType: 'blob'
    })
    return response
  },

  deleteAnalysis: async (analysisId: string): Promise<void> => {
    return request(`/tax-intelligence/report/${analysisId}`, {
      method: 'DELETE'
    })
  },

  getStatistics: async (): Promise<TaxIntelligenceStatistics> => {
    return request('/tax-intelligence/statistics', {
      method: 'GET'
    })
  },

  explainReport: async (analysisId: string, params: ExplainRequest = {}): Promise<ExplainResponse> => {
    return request(`/tax-intelligence/report/${analysisId}/explain`, {
      method: 'POST',
      data: params
    })
  },

  queryPolicies: async (params: PolicyQueryParams): Promise<PolicyQueryResponse> => {
    const queryParams = new URLSearchParams()
    queryParams.append('query', params.query)
    if (params.tax_types) queryParams.append('tax_types', params.tax_types.join(','))
    if (params.industries) queryParams.append('industries', params.industries.join(','))
    if (params.regions) queryParams.append('regions', params.regions.join(','))
    if (params.top_k) queryParams.append('top_k', String(params.top_k))
    
    return request(`/tax-intelligence/policies?${queryParams.toString()}`, {
      method: 'GET'
    })
  },

  getRiskLevel: async (_analysisId: string) => {
    return Promise.resolve({
      level: 'low' as const,
      score: 0,
      reasons: []
    })
  },

  getComplianceStatus: async (_analysisId: string) => {
    return Promise.resolve({
      status: 'compliant' as const,
      issues: []
    })
  }
}
