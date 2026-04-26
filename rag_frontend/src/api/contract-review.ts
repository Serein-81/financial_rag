import { request } from '@/utils/request'

export interface ContractAnalysisRequest {
  contract_text: string
  contract_type?: 'purchase' | 'sales' | 'service' | 'lease' | 'employment' | 'partnership' | 'loan' | 'other'
  counterparty?: string
  contract_value?: number
}

export interface ContractClause {
  type: string
  title: string
  text: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  risk_score: number
  analysis: string
  suggestions: string[]
  position: number
}

export interface ContractAnalysisResult {
  analysis_id: string
  contract_type: string
  counterparty: string
  contract_value: number
  currency: string
  overall_risk_score: number
  overall_risk_level: 'low' | 'medium' | 'high' | 'critical'
  basic_analysis: {
    parties: Array<{ name: string; role: string }>
    effective_date: string
    expiration_date: string
    duration_days: number
  }
  clauses: ContractClause[]
  risk_summary: {
    high_risk_count: number
    medium_risk_count: number
    low_risk_count: number
    key_risks: string[]
  }
  compliance_checks: Array<{
    check_type: string
    passed: boolean
    details: string
  }>
  suggestions: Array<{
    priority: 'high' | 'medium' | 'low'
    category: string
    title: string
    description: string
    clause_position?: number
  }>
  unfavorable_clauses: Array<{
    clause: string
    risk_description: string
    suggested_revision: string
  }>
  ai_summary: string
  created_at: string
}

export interface DeepClauseAnalysisResult {
  clause_type: string
  original_text: string
  analysis: {
    legal_interpretation: string
    business_impact: string
    potential_risks: string[]
    negotiation_points: string[]
  }
  suggestions: Array<{
    type: 'revision' | 'addition' | 'deletion'
    suggested_text: string
    rationale: string
  }>
  comparison: {
    is_standard: boolean
    market_average: string
    risk_level: string
  }
}

export interface ContractComparisonResult {
  contract1_id: string
  contract2_id: string
  similarity_score: number
  differences: Array<{
    category: string
    contract1_value: string
    contract2_value: string
    impact: string
  }>
  comparison_summary: string
}

export interface ContractReport {
  id: string
  analysis_id: string
  contract_name: string
  contract_type: string
  counterparty: string
  overall_risk_score: number
  overall_risk_level: string
  review_status: string
  created_at: string
}

export const contractReviewApi = {
  analyzeContract: async (params: ContractAnalysisRequest): Promise<ContractAnalysisResult> => {
    return request('/contract-review/analyze', {
      method: 'POST',
      data: params
    })
  },

  uploadAndAnalyzeContract: async (formData: FormData): Promise<{
    success: boolean
    message: string
    analysis_id: string
    file_metadata: {
      file_id: string
      file_name: string
      minio_path: string
      content_type: string
      size: number
      uploaded_by: string
      uploaded_at: string
      analysis_id: string
    }
    result: ContractAnalysisResult
  }> => {
    return request('/contract-review/upload', {
      method: 'POST',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  analyzeDeepClause: async (params: {
    contract_id: string
    clause_type: string
    clause_text: string
  }): Promise<DeepClauseAnalysisResult> => {
    return request('/contract-review/deep-clause', {
      method: 'POST',
      data: params
    })
  },

  compareContracts: async (params: {
    contract1_id: string
    contract2_id: string
  }): Promise<ContractComparisonResult> => {
    return request('/contract-review/compare', {
      method: 'POST',
      data: params
    })
  },

  getAnalysisHistory: async (params: {
    page?: number
    page_size?: number
    contract_type?: string
    risk_level?: string
  } = {}): Promise<{
    analyses: ContractReport[]
    total: number
    page: number
    page_size: number
  }> => {
    return request('/contract-review/history', {
      method: 'GET',
      params
    })
  },

  getAnalysisDetail: async (analysisId: string): Promise<ContractAnalysisResult> => {
    return request(`/contract-review/analysis/${analysisId}`, {
      method: 'GET'
    })
  },

  exportReportPdf: async (analysisId: string): Promise<Blob> => {
    const response = await request('/contract-review/report/export', {
      method: 'GET',
      params: { analysis_id: analysisId },
      responseType: 'blob'
    })
    return response
  },

  deleteAnalysis: async (analysisId: string): Promise<void> => {
    return request(`/contract-review/analysis/${analysisId}`, {
      method: 'DELETE'
    })
  },

  getClauseTypes: async (): Promise<Array<{ value: string; label: string }>> => {
    return request('/contract-review/clause-types', {
      method: 'GET'
    })
  },

  getTemplates: async (params: {
    contract_type?: string
  } = {}): Promise<Array<{
    id: string
    name: string
    description: string
    contract_type: string
    usage_count: number
  }>> => {
    const response = await request<{ templates: Array<{
      id: string
      name: string
      description: string
      contract_type: string
      usage_count: number
    }>, total: number }>('/contract-review/templates', {
      method: 'GET',
      params
    })
    return response.templates
  }
}
