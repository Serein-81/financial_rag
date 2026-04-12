import { request } from '@/utils/request'

export interface FinancialHealthRequest {
  tenant_id?: string
  user_id?: string
  period_start?: string
  period_end?: string
  include_anomaly_detection?: boolean
  include_trend_analysis?: boolean
  financial_data?: Record<string, any>
}

export interface FinancialHealthReport {
  report_id: string
  tenant_id: string
  period_start: string
  period_end: string
  overall_health_score: number
  health_status: 'healthy' | 'warning' | 'critical' | 'unknown'
  data_available?: boolean
  data_unavailable_message?: string | null
  revenue_summary: {
    total: number
    trend: 'up' | 'down' | 'stable'
    growth_rate: number
  }
  expense_summary: {
    total: number
    breakdown: Record<string, number>
  }
  profit_summary: {
    gross_profit: number
    net_profit: number
    profit_margin: number
  }
  cash_flow_summary: {
    inflow: number
    outflow: number
    net_flow: number
  }
  financial_metrics: {
    current_ratio: number
    quick_ratio: number
    debt_ratio: number
    roa: number
    roe: number
  }
  anomalies_detected: Array<{
    type: string
    severity: 'low' | 'medium' | 'high' | 'critical'
    description: string
    detected_value: number
    expected_value: number
    deviation: number
  }>
  trend_indicators: Array<{
    metric: string
    direction: 'up' | 'down' | 'stable'
    change_percentage: number
  }>
  recommendations: Array<{
    priority: 'high' | 'medium' | 'low'
    category: string
    title: string
    description: string
    action_items: string[]
  }>
  generated_at: string
}

export interface AnomalyRecord {
  id: string
  anomaly_type: string
  severity: string
  title: string
  description: string
  detected_value: number
  expected_value: number
  deviation: number
  status: 'detected' | 'acknowledged' | 'resolved'
  created_at: string
}

export const financialHealthApi = {
  monitorHealth: async (params: FinancialHealthRequest): Promise<FinancialHealthReport> => {
    return request('/financial-health/monitor', {
      method: 'POST',
      data: params
    })
  },

  getReportHistory: async (params: {
    page?: number
    page_size?: number
    start_date?: string
    end_date?: string
    health_status?: string
  } = {}): Promise<{
    reports: FinancialHealthReport[]
    total: number
    page: number
    page_size: number
  }> => {
    return request('/financial-health/history', {
      method: 'GET',
      params
    })
  },

  getReportById: async (reportId: string): Promise<FinancialHealthReport> => {
    return request(`/financial-health/report/${reportId}`, {
      method: 'GET'
    })
  },

  exportReportPdf: async (params: { period_days?: number } = {}): Promise<Blob> => {
    const response = await request('/financial-health/report/export', {
      method: 'GET',
      params,
      responseType: 'blob'
    })
    return response
  },

  getAnomalies: async (params: {
    page?: number
    page_size?: number
    severity?: string
    status?: string
    start_date?: string
    end_date?: string
  } = {}): Promise<{
    anomalies: AnomalyRecord[]
    total: number
    page: number
    page_size: number
  }> => {
    return request('/financial-health/anomalies', {
      method: 'GET',
      params
    })
  },

  acknowledgeAnomaly: async (anomalyId: string): Promise<void> => {
    return request(`/financial-health/anomalies/${anomalyId}/acknowledge`, {
      method: 'POST'
    })
  },

  resolveAnomaly: async (anomalyId: string, resolution: string): Promise<void> => {
    return request(`/financial-health/anomalies/${anomalyId}/resolve`, {
      method: 'POST',
      data: { resolution }
    })
  },

  getMetrics: async (params: {
    metric_name?: string
    start_date?: string
    end_date?: string
    period_type?: 'daily' | 'weekly' | 'monthly'
  } = {}): Promise<Array<{
    metric_name: string
    metric_value: number
    record_date: string
  }>> => {
    return request('/financial-health/metrics', {
      method: 'GET',
      params
    })
  },

  getThresholds: async (): Promise<Array<{
    metric_name: string
    warning_threshold: number
    critical_threshold: number
    enabled: boolean
  }>> => {
    return request('/financial-health/thresholds', {
      method: 'GET'
    })
  },

  updateThreshold: async (metricName: string, config: {
    warning_threshold?: number
    critical_threshold?: number
    enabled?: boolean
  }): Promise<void> => {
    return request(`/financial-health/thresholds/${metricName}`, {
      method: 'PUT',
      data: config
    })
  }
}
