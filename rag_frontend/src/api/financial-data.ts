/**
 * 财务数据管理 API 客户端
 */

import axios from 'axios'
import { ElMessage } from 'element-plus'
import { API_BASE } from '@/config/api'

const API_BASE_URL = '/api/v1'

const financialDataApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
})

financialDataApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('rag_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

financialDataApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const errorMessage = error.response?.data?.detail || error.response?.data?.message

    if (status === 401 || status === 403) {
      localStorage.removeItem('rag_token')
      localStorage.removeItem('user')
      
      const message = status === 401 
        ? '登录已过期，请重新登录' 
        : '登录已过期，请重新登录'
      
      ElMessage.error({
        message,
        duration: 3000,
        onClose: () => {
          window.location.href = '/login'
        }
      })
    } else if (status === 500) {
      ElMessage.error({
        message: '服务器错误，请稍后重试',
        duration: 3000
      })
    }
    
    return Promise.reject(error)
  }
)

export type DataSourceEnum = 'manual' | 'upload' | 'auto'

export interface FinancialDataCreate {
  fiscal_year: number
  period_type: string
  period_start: string
  period_end: string
  total_revenue: number
  taxable_sales: number
  tax_free_sales: number
  total_expenses: number
  deductible_expenses: number
  non_deductible_expenses?: number
  input_tax: number
  output_tax: number
  vat_rate: number
  taxable_income: number
  corporate_tax_rate: number
  total_payroll: number
  special_deductions: number
  is_small_enterprise: boolean
  notes?: string
  cost_breakdown?: Record<string, number>
  total_invoices?: number
  input_invoice_count?: number
  output_invoice_count?: number
  data_source?: DataSourceEnum
}

export interface FinancialDataUpdate {
  total_revenue?: number
  taxable_sales?: number
  tax_free_sales?: number
  total_expenses?: number
  deductible_expenses?: number
  non_deductible_expenses?: number
  input_tax?: number
  output_tax?: number
  vat_rate?: number
  taxable_income?: number
  corporate_tax_rate?: number
  total_payroll?: number
  special_deductions?: number
  is_small_enterprise?: boolean
  data_status?: string
  notes?: string
  cost_breakdown?: Record<string, number>
  total_invoices?: number
  input_invoice_count?: number
  output_invoice_count?: number
}

export interface FinancialDataResponse {
  id: string
  user_id: string
  tenant_id: string
  fiscal_year: number
  period_type: string
  period_start: string
  period_end: string
  total_revenue: number
  taxable_sales: number
  tax_free_sales: number
  total_expenses: number
  deductible_expenses: number
  non_deductible_expenses: number
  input_tax: number
  output_tax: number
  vat_rate: number
  taxable_income: number
  corporate_tax_rate: number
  total_payroll: number
  special_deductions: number
  is_small_enterprise: boolean
  data_status: string
  data_source: string
  notes: string
  total_invoices: number
  input_invoice_count: number
  output_invoice_count: number
  created_at: string
  updated_at: string
  calculated_vat: number
  calculated_corporate_tax: number
  tax_burden_rate: number
}

export interface TaxQueryRequest {
  fiscal_year?: number
  include_vat?: boolean
  include_corporate_tax?: boolean
  include_personal_tax?: boolean
}

export interface TaxCalculationResult {
  tax_type: string
  amount: number
  rate: number
  details: Record<string, any>
}

export interface TaxQueryResponse {
  fiscal_year: number
  tax_results: TaxCalculationResult[]
  total_tax_amount: number
  tax_burden_analysis: Record<string, any>
  risk_alerts: string[]
  recommendations: string[]
  financial_summary: Record<string, any>
}

export interface FinancialStatistics {
  fiscal_year: number
  total_revenue: number
  total_expenses: number
  calculated_vat: number
  calculated_corporate_tax: number
  total_tax: number
  tax_burden_rate: number
  record_count: number
  data_completeness: number
  year_over_year_comparison: {
    revenue_change: number
    revenue_change_rate: number
    expense_change: number
    expense_change_rate: number
    tax_change: number
    tax_change_rate: number
  }
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export const financialDataApiClient = {
  /**
   * 创建财务数据记录
   */
  async create(data: FinancialDataCreate): Promise<FinancialDataResponse> {
    const response = await financialDataApi.post('/financial-data', data)
    ElMessage.success('财务数据创建成功')
    return response.data
  },

  /**
   * 获取财务数据列表
   */
  async list(params: {
    page?: number
    page_size?: number
    fiscal_year?: number
  } = {}): Promise<PaginatedResponse<FinancialDataResponse>> {
    const response = await financialDataApi.get('/financial-data', { params })
    return response.data
  },

  /**
   * 获取财务数据详情
   */
  async get(recordId: string): Promise<FinancialDataResponse> {
    const response = await financialDataApi.get(`/financial-data/${recordId}`)
    return response.data
  },

  /**
   * 根据年度和周期类型获取财务数据
   */
  async getByYear(fiscalYear: number, periodType: string = 'yearly'): Promise<FinancialDataResponse | null> {
    const response = await financialDataApi.get('/financial-data/by-year', {
      params: { fiscal_year: fiscalYear, period_type: periodType }
    })
    return response.data
  },

  /**
   * 更新财务数据
   */
  async update(recordId: string, data: FinancialDataUpdate): Promise<FinancialDataResponse> {
    const response = await financialDataApi.put(`/financial-data/${recordId}`, data)
    ElMessage.success('财务数据更新成功')
    return response.data
  },

  /**
   * 删除财务数据
   */
  async delete(recordId: string): Promise<void> {
    await financialDataApi.delete(`/financial-data/${recordId}`)
    ElMessage.success('财务数据删除成功')
  },

  /**
   * 查询税务信息
   */
  async queryTax(params: TaxQueryRequest = {}): Promise<TaxQueryResponse> {
    const response = await financialDataApi.post('/financial-data/query-tax', params)
    return response.data
  },

  /**
   * 获取财务数据统计
   */
  async getStatistics(fiscalYear?: number): Promise<FinancialStatistics> {
    const params = fiscalYear ? { fiscal_year: fiscalYear } : {}
    const response = await financialDataApi.get('/financial-data/statistics', { params })
    return response.data
  },

  /**
   * 获取财务数据修改历史
   */
  async getHistory(recordId: string): Promise<any[]> {
    const response = await financialDataApi.get(`/financial-data/history/${recordId}`)
    return response.data
  },

  /**
   * 上传Excel文件导入财务数据
   */
  async uploadExcel(file: File, overwriteExisting: boolean = false): Promise<{
    success: boolean
    message: string
    records_created: number
    records_updated: number
    records_skipped: number
    errors: Array<{ row: number; field: string; message: string }>
  }> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('overwrite_existing', String(overwriteExisting))
    
    const response = await financialDataApi.post('/financial-data/upload-excel', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    
    if (response.data.success) {
      ElMessage.success({
        message: `成功导入 ${response.data.records_created} 条记录，更新 ${response.data.records_updated} 条记录`,
        duration: 3000
      })
    }
    
    return response.data
  },

  /**
   * 智能上传Excel文件（自动识别列名）
   * 支持各种格式的Excel文件，自动识别财务数据列
   */
  async uploadExcelIntelligent(file: File, options: {
    fiscalYear?: number
    periodType?: string
    overwriteExisting?: boolean
  } = {}): Promise<{
    success: boolean
    message: string
    detected_columns: Record<string, string | null>
    records_created: number
    records_updated: number
    records_skipped: number
    validation_errors: Array<{ row: number; field: string; message: string }>
  }> {
    const formData = new FormData()
    formData.append('file', file)
    
    if (options.fiscalYear) {
      formData.append('fiscal_year', String(options.fiscalYear))
    }
    if (options.periodType) {
      formData.append('period_type', options.periodType)
    }
    formData.append('overwrite_existing', String(options.overwriteExisting || false))
    
    try {
      const response = await financialDataApi.post('/financial-data/upload-excel-intelligent', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      
      const data = response.data
      
      if (data.success) {
        const detectedCount = Object.values(data.detected_columns).filter(v => v !== null).length
        ElMessage.success({
          message: `${data.message}，系统自动识别了 ${detectedCount} 个财务字段`,
          duration: 4000
        })
      }
      
      return data
    } catch (error: any) {
      if (error.response?.status === 400) {
        const detail = error.response.data?.detail
        
        if (typeof detail === 'object' && detail?.missing_columns) {
          const missingMsg = `无法识别以下必需列：${detail.missing_columns.join('、')}`
          ElMessage.error({
            message: missingMsg,
            duration: 5000
          })
          
          return {
            success: false,
            message: detail.message || '列名识别失败',
            detected_columns: detail.detected_columns || {},
            records_created: 0,
            records_updated: 0,
            records_skipped: 0,
            validation_errors: []
          }
        } else {
          ElMessage.error({
            message: detail || '上传失败',
            duration: 3000
          })
        }
      }
      throw error
    }
  },

  /**
   * 下载财务数据Excel模板
   */
  async downloadTemplate(): Promise<void> {
    try {
      const response = await financialDataApi.get('/financial-data/download-template', {
        responseType: 'blob',
      })

      const blob = new Blob([response.data])
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', '财务数据导入模板.xlsx')
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)

      ElMessage.success({
        message: '模板下载成功',
        duration: 2000
      })
    } catch (error: any) {
      console.error('下载模板失败:', error)
      console.error('Error details:', {
        name: error?.name,
        message: error?.message,
        status: error?.response?.status,
      })
      ElMessage.error({
        message: '模板下载失败，请稍后重试',
        duration: 2000
      })
      throw error
    }
  },

  /**
   * 下载智能识别测试模板
   * @param type 模板类型: all, standard, english, simplified, mixed, custom
   */
  async downloadTestTemplate(type: string = 'all'): Promise<void> {
    try {
      const response = await financialDataApi.get('/financial-data/download-test-templates', {
        params: { template_type: type },
        responseType: 'blob',
      })

      const contentDisposition = response.headers['content-disposition']
      let filename = '测试模板.xlsx'

      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?([^";\n]+)"?/i)
        if (match) {
          filename = match[1]
        }
      }

      const blob = new Blob([response.data])
      const blobUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = blobUrl
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(blobUrl)

      ElMessage.success({
        message: `测试模板下载成功: ${filename}`,
        duration: 3000
      })
    } catch (error: any) {
      console.error('下载测试模板失败:', error)
      console.error('Error details:', {
        name: error?.name,
        message: error?.message,
        status: error?.response?.status,
      })
      ElMessage.error({
        message: '下载测试模板失败，请稍后重试',
        duration: 3000
      })
      throw error
    }
  }
}

export default financialDataApiClient
