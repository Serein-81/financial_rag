/**
 * 财务数据管理 API 客户端
 * 具有鲁棒的错误处理机制，支持租户上下文错误处理
 */

import axios, { AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

/**
 * 防止重复登录提示的状态管理
 */
let isShowingReloginMessage = false
let lastReloginTimestamp = 0
const RELOGIN_COOLDOWN_MS = 5000 // 5秒内不重复提示

const financialDataApi = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

financialDataApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('rag_token')
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/**
 * 认证错误类型枚举（与后端保持一致）
 */
enum AuthErrorType {
  NO_TOKEN = 'no_token',
  TOKEN_EXPIRED = 'token_expired',
  TOKEN_INVALID = 'token_invalid',
  TENANT_MISSING = 'tenant_missing',
  TENANT_INACTIVE = 'tenant_inactive',
  USER_NOT_FOUND = 'user_not_found',
  PERMISSION_DENIED = 'permission_denied',
  UNKNOWN_ERROR = 'unknown_error'
}

/**
 * 认证错误消息映射
 */
const AuthErrorMessages: Record<AuthErrorType, string> = {
  [AuthErrorType.NO_TOKEN]: '请先登录',
  [AuthErrorType.TOKEN_EXPIRED]: '登录已过期，请重新登录',
  [AuthErrorType.TOKEN_INVALID]: '登录会话无效，请重新登录',
  [AuthErrorType.TENANT_MISSING]: '会话已失效，请重新登录',
  [AuthErrorType.TENANT_INACTIVE]: '租户账户已被禁用',
  [AuthErrorType.USER_NOT_FOUND]: '用户不存在',
  [AuthErrorType.PERMISSION_DENIED]: '权限不足，无法访问该资源',
  [AuthErrorType.UNKNOWN_ERROR]: '认证失败，请稍后重试'
}

/**
 * 从错误响应中提取错误类型
 */
function extractErrorType(error: any): AuthErrorType | null {
  // 优先从 error_type 字段获取（后端新版响应）
  if (error.response?.data?.error_type) {
    const errorType = error.response.data.error_type as string
    if (Object.values(AuthErrorType).includes(errorType as AuthErrorType)) {
      return errorType as AuthErrorType
    }
  }
  
  // 从错误消息推断（兼容旧版响应）
  const errorMessage = error.response?.data?.detail || 
                       error.response?.data?.message ||
                       error.message
  
  if (!errorMessage) return null
  
  const lowerMessage = errorMessage.toLowerCase()
  
  if (lowerMessage.includes('tenant') || 
      lowerMessage.includes('租户') ||
      lowerMessage.includes('missing tenant')) {
    return AuthErrorType.TENANT_MISSING
  }
  
  if (lowerMessage.includes('expired') || 
      lowerMessage.includes('过期')) {
    return AuthErrorType.TOKEN_EXPIRED
  }
  
  if (lowerMessage.includes('invalid') || 
      lowerMessage.includes('无效')) {
    return AuthErrorType.TOKEN_INVALID
  }
  
  if (lowerMessage.includes('no token') || 
      lowerMessage.includes('authentication required')) {
    return AuthErrorType.NO_TOKEN
  }
  
  return null
}

/**
 * 安全地处理认证错误，显示登录提示
 */
function handleAuthError(error?: any): void {
  // 防止重复提示
  const now = Date.now()
  if (isShowingReloginMessage || (now - lastReloginTimestamp < RELOGIN_COOLDOWN_MS)) {
    return
  }
  
  // 检查是否已经在登录页
  if (window.location.pathname === '/login') {
    return
  }
  
  isShowingReloginMessage = true
  lastReloginTimestamp = now
  
  // 清除本地认证信息
  localStorage.removeItem('rag_token')
  localStorage.removeItem('user')
  
  // 根据错误类型获取精确的消息
  let message = '登录已过期，请重新登录'
  
  if (error) {
    const errorType = extractErrorType(error)
    if (errorType && AuthErrorMessages[errorType]) {
      message = AuthErrorMessages[errorType]
    }
  }
  
  ElMessage.error({
    message,
    duration: 3000,
    onClose: () => {
      isShowingReloginMessage = false
      window.location.href = '/login'
    }
  })
}

financialDataApi.interceptors.response.use(
  (response) => response,
  (error) => {
    // 安全获取错误信息
    const status = error.response?.status
    const errorMessage = error.response?.data?.detail || 
                         error.response?.data?.message || 
                         error.message

    // 处理 401 未授权错误
    if (status === 401) {
      handleAuthError(error)
      return Promise.reject(error)
    }
    
    // 处理 403 禁止访问错误
    if (status === 403) {
      // 区分 tenant context 错误和普通权限错误
      const errorType = extractErrorType(error)
      if (errorType === AuthErrorType.TENANT_MISSING || 
          errorType === AuthErrorType.TENANT_INACTIVE ||
          errorType === AuthErrorType.TOKEN_INVALID) {
        // Tenant context 缺失或租户无效，视为未登录处理
        handleAuthError(error)
      } else {
        // 其他 403 错误（如权限不足）
        ElMessage.error({
          message: errorMessage || '权限不足，无法访问该资源',
          duration: 3000
        })
      }
      return Promise.reject(error)
    }
    
    // 处理 500 服务器错误
    if (status === 500) {
      ElMessage.error({
        message: '服务器错误，请稍后重试',
        duration: 3000
      })
      return Promise.reject(error)
    }
    
    // 处理其他错误（如网络错误、超时等）
    if (!error.response) {
      console.error('[Financial Data API] Network error:', error.message)
      ElMessage.error({
        message: '网络连接失败，请检查网络',
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
    const response = await financialDataApi.post<FinancialDataResponse>('/financial-data', data)
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
    const response = await financialDataApi.get<PaginatedResponse<FinancialDataResponse>>('/financial-data', { params })
    return response.data
  },

  /**
   * 获取财务数据详情
   */
  async get(recordId: string): Promise<FinancialDataResponse> {
    const response = await financialDataApi.get<FinancialDataResponse>(`/financial-data/${recordId}`)
    return response.data
  },

  /**
   * 根据年度和周期类型获取财务数据
   */
  async getByYear(fiscalYear: number, periodType: string = 'yearly'): Promise<FinancialDataResponse | null> {
    const response = await financialDataApi.get<FinancialDataResponse | null>('/financial-data/by-year', {
      params: { fiscal_year: fiscalYear, period_type: periodType }
    })
    return response.data
  },

  /**
   * 更新财务数据
   */
  async update(recordId: string, data: FinancialDataUpdate): Promise<FinancialDataResponse> {
    const response = await financialDataApi.put<FinancialDataResponse>(`/financial-data/${recordId}`, data)
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
    const response = await financialDataApi.post<TaxQueryResponse>('/financial-data/query-tax', params)
    return response.data
  },

  /**
   * 获取财务数据统计
   */
  async getStatistics(fiscalYear?: number): Promise<FinancialStatistics> {
    const params = fiscalYear ? { fiscal_year: fiscalYear } : {}
    const response = await financialDataApi.get<FinancialStatistics>('/financial-data/statistics', { params })
    return response.data
  },

  /**
   * 获取财务数据修改历史
   */
  async getHistory(recordId: string): Promise<any[]> {
    const response = await financialDataApi.get<any[]>(`/financial-data/history/${recordId}`)
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
    
    const response = await financialDataApi.post<{
      success: boolean
      message: string
      records_created: number
      records_updated: number
      records_skipped: number
      errors: Array<{ row: number; field: string; message: string }>
    }>('/financial-data/upload-excel', formData, {
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
      const response = await financialDataApi.post<{
        success: boolean
        message: string
        detected_columns: Record<string, string | null>
        records_created: number
        records_updated: number
        records_skipped: number
        validation_errors: Array<{ row: number; field: string; message: string }>
      }>('/financial-data/upload-excel-intelligent', formData, {
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
   * 获取财务数据模板说明
   */
  async getTemplateDescription(): Promise<any> {
    try {
      const response = await financialDataApi.get<any>('/financial-data/template-description')
      return response.data
    } catch (error: any) {
      console.error('获取模板说明失败:', error)
      throw error
    }
  },

  /**
   * 下载财务数据Excel模板
   */
  async downloadTemplate(): Promise<void> {
    try {
      const response = await financialDataApi.get<Blob>('/financial-data/download-template', {
        responseType: 'blob',
      })

      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
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
      const response = await financialDataApi.get<Blob>('/financial-data/download-test-templates', {
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

      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
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
