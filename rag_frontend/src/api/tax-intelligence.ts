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
