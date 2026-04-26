/**
 * 税务报告 API 客户端
 */

import axios, { AxiosProgressEvent } from 'axios'
import { ElMessage } from 'element-plus'
import type {
  TaxReport,
  TaxReportUploadResponse,
  TaxReportListResponse,
  TaxReportStatusResponse,
  TaxReportFilter,
  TaxReportWithDetails,
  UploadProgress,
  BatchUploadResponse,
  TaxTypeEnum
} from '@/types/tax'
import { API_BASE } from '@/config/api'

const API_BASE_URL = `${API_BASE}/api/v1`

const taxReportApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
})

taxReportApi.interceptors.request.use((config) => {
  console.log('📤 [TaxAPI] 请求拦截:', config.method, config.url)
  console.log('📤 [TaxAPI] Headers:', JSON.stringify(config.headers))
  console.log('📤 [TaxAPI] Data type:', typeof config.data)
  if (config.data instanceof FormData) {
    console.log('📤 [TaxAPI] FormData entries:')
    for (const [key, value] of config.data.entries()) {
      console.log(`  ${key}:`, value instanceof File ? `File(${value.name}, ${value.size})` : value)
    }
    delete config.headers['Content-Type']
  }
  const token = localStorage.getItem('rag_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  console.log('📤 [TaxAPI] 最终 Headers:', JSON.stringify(config.headers))
  return config
})

taxReportApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const errorMessage = error.response?.data?.detail || error.response?.data?.message

    if (status === 401 || status === 403) {
      localStorage.removeItem('rag_token')
      localStorage.removeItem('user')
      
      const message = status === 401 
        ? '登录已过期，请重新登录' 
        : (errorMessage?.includes('tenant') ? '会话无效，请重新登录' : '登录已过期，请重新登录')
      
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

export const taxReportApiClient = {
  /**
   * 上传税务报告
   */
  async upload(
    file: File,
    options: {
      tax_type?: TaxTypeEnum
      tax_period_year?: number
      tax_period_month?: number
      description?: string
      onProgress?: (progress: number) => void
    } = {}
  ): Promise<TaxReportUploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    
    // tax_type 是必需的查询参数
    const params = new URLSearchParams()
    if (options.tax_type) {
      params.append('tax_type', options.tax_type)
    }

    const url = `${API_BASE || ''}/api/v1/tax-reports/upload?${params.toString()}`
    const token = localStorage.getItem('rag_token')

    console.log('📤 [TaxUpload] 准备上传文件:', file.name, file.size, file.type)
    console.log('📤 [TaxUpload] 请求URL:', url)

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      
      xhr.timeout = 120000
      
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && options.onProgress) {
          const progress = Math.round((event.loaded * 100) / event.total)
          options.onProgress(progress)
          console.log(`📤 [TaxUpload] 上传进度: ${progress}%`)
        }
      }

      xhr.onloadstart = () => {
        console.log('📤 [TaxUpload] 请求开始发送')
      }

      xhr.onload = () => {
        console.log('📤 [TaxUpload] 请求完成:', xhr.status, xhr.statusText)
        if (xhr.status >= 200 && xhr.status < 300) {
          console.log('📤 [TaxUpload] 上传成功:', xhr.responseText)
          resolve(JSON.parse(xhr.responseText))
        } else {
          console.error('📤 [TaxUpload] 上传失败:', xhr.status, xhr.responseText)
          try {
            const errorData = JSON.parse(xhr.responseText)
            const error = new Error(errorData.message || errorData.detail || '上传失败') as any
            error.response = { data: errorData }
            error.status = xhr.status
            reject(error)
          } catch {
            reject(new Error(`上传失败: ${xhr.status}`))
          }
        }
      }

      xhr.ontimeout = () => {
        console.error('📤 [TaxUpload] 上传超时 - 120秒内未收到响应')
        console.error('📤 [TaxUpload] 可能原因: 后端未启动、路由错误、网络问题')
        reject(new Error('上传超时，请重试或检查文件大小'))
      }

      xhr.onerror = () => {
        console.error('📤 [TaxUpload] 网络错误')
        console.error('📤 [TaxUpload] readyState:', xhr.readyState)
        console.error('📤 [TaxUpload] status:', xhr.status)
        reject(new Error('网络错误，请检查网络连接'))
      }

      xhr.onabort = () => {
        console.error('📤 [TaxUpload] 请求被取消')
        reject(new Error('请求被取消'))
      }

      console.log('📤 [TaxUpload] 准备发送请求...')
      xhr.open('POST', url)
      console.log('📤 [TaxUpload] 设置 Authorization header')
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      console.log('📤 [TaxUpload] 发送表单数据')
      xhr.send(formData)
      console.log('📤 [TaxUpload] send() 已调用，等待响应...')
    })
  },

  /**
   * 批量上传税务报告
   */
  async batchUpload(
    files: File[],
    options: {
      tax_type?: TaxTypeEnum
      tax_period_year?: number
      tax_period_month?: number
      onProgress?: (completed: number, total: number) => void
    } = {}
  ): Promise<BatchUploadResponse> {
    const results: TaxReportUploadResponse[] = []
    const errors: Array<{ filename: string; error: string }> = []
    let completed = 0

    for (const file of files) {
      try {
        const result = await this.upload(file, {
          tax_type: options.tax_type,
          tax_period_year: options.tax_period_year,
          tax_period_month: options.tax_period_month
        })
        results.push(result)
      } catch (error: any) {
        errors.push({
          filename: file.name,
          error: error.response?.data?.detail || '上传失败'
        })
      }
      
      completed++
      if (options.onProgress) {
        options.onProgress(completed, files.length)
      }
    }

    return {
      total: files.length,
      successful: results.length,
      failed: errors.length,
      reports: results,
      errors
    }
  },

  /**
   * 获取税务报告列表
   */
  async list(filter: TaxReportFilter = {}): Promise<TaxReportListResponse> {
    const params = new URLSearchParams()
    
    if (filter.status) params.append('status', filter.status)
    if (filter.tax_type) params.append('tax_type', filter.tax_type)
    if (filter.risk_level) params.append('risk_level', filter.risk_level)
    if (filter.needs_review !== undefined) params.append('needs_review', String(filter.needs_review))
    if (filter.start_date) params.append('start_date', filter.start_date)
    if (filter.end_date) params.append('end_date', filter.end_date)
    if (filter.keyword) params.append('keyword', filter.keyword)
    
    // 后端使用 skip/limit，前端使用 page/page_size，需要转换
    if (filter.page !== undefined) {
      const skip = (filter.page - 1) * (filter.page_size || 20)
      params.append('skip', String(skip))
    }
    if (filter.page_size) params.append('limit', String(filter.page_size))

    const response = await taxReportApi.get<TaxReportListResponse>(
      `/tax-reports?${params.toString()}`
    )
    return response.data
  },

  /**
   * 获取税务报告详情
   */
  async get(reportId: string): Promise<TaxReport> {
    const response = await taxReportApi.get<TaxReport>(
      `/tax-reports/${reportId}`
    )
    return response.data
  },

  /**
   * 获取待审核的税务报告列表
   */
  async getPendingReviews(
    page: number = 1,
    pageSize: number = 20
  ): Promise<TaxReportListResponse> {
    const params = new URLSearchParams()
    params.append('skip', String((page - 1) * pageSize))
    params.append('limit', String(pageSize))
    
    const response = await taxReportApi.get<TaxReportListResponse>(
      `/tax-reports/reviews/pending`,
      { params }
    )
    return response.data
  },

  /**
   * 获取税务报告详情（包含处理结果）
   */
  async getWithDetails(reportId: string): Promise<TaxReportWithDetails> {
    const response = await taxReportApi.get<TaxReportWithDetails>(
      `/tax-reports/${reportId}`
    )
    return response.data
  },

  /**
   * 获取报告处理状态
   */
  async getStatus(reportId: string): Promise<TaxReportStatusResponse> {
    const response = await taxReportApi.get<TaxReportStatusResponse>(
      `/tax-reports/${reportId}/status`
    )
    return response.data
  },

  /**
   * 删除税务报告
   */
  async delete(reportId: string): Promise<void> {
    await taxReportApi.delete(`/tax-reports/${reportId}`)
  },

  /**
   * 取消处理
   */
  async cancel(reportId: string): Promise<void> {
    await taxReportApi.post(`/tax-reports/${reportId}/cancel`)
  },

  /**
   * WebSocket 实时状态订阅
   */
  subscribeToStatus(
    reportId: string,
    onUpdate: (status: TaxReportStatusResponse) => void,
    onError?: (error: Event) => void
  ): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}${API_BASE_URL}/tax-reports/${reportId}/stream`
    
    const ws = new WebSocket(wsUrl)
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.error) {
        console.error('WebSocket error:', data.error)
        onError?.(new Event(data.error))
      } else {
        onUpdate(data as TaxReportStatusResponse)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket connection error:', error)
      onError?.(error)
    }

    return ws
  },

  /**
   * 轮询状态更新
   */
  async pollStatus(
    reportId: string,
    interval: number = 2000,
    maxAttempts: number = 60
  ): Promise<TaxReportStatusResponse> {
    return new Promise((resolve, reject) => {
      let attempts = 0

      const poll = async () => {
        try {
          const status = await this.getStatus(reportId)
          
          if (status.status === 'completed' || status.status === 'failed' || status.status === 'pending_review') {
            resolve(status)
            return
          }

          attempts++
          if (attempts >= maxAttempts) {
            reject(new Error('状态轮询超时'))
            return
          }

          setTimeout(poll, interval)
        } catch (error) {
          reject(error)
        }
      }

      poll()
    })
  },

  /**
   * 手动录入税务报告
   */
  async createManualTaxReport(inputData: {
    tax_type: TaxTypeEnum
    fiscal_year: number
    fiscal_period?: string
    company_name?: string
    tax_id?: string
    revenue: number
    taxable_sales: number
    tax_free_sales: number
    input_tax: number
    output_tax: number
    vat_rate: number
    total_expenses: number
    deductible_expenses: number
    taxable_income: number
    corporate_tax_rate: number
    total_payroll: number
    total_invoices: number
    input_invoice_count: number
    output_invoice_count: number
    financial_data_id?: string
    notes?: string
    run_analysis: boolean
  }): Promise<{
    success: boolean
    message: string
    data: {
      id: string
      tenant_id: string
      user_id: string
      filename: string
      original_filename: string
      tax_type: string
      status: string
      created_at: string
      key_metrics: Record<string, any>
      needs_analysis: boolean
      analysis_triggered?: boolean
      analysis_error?: string
    }
  }> {
    const response = await taxReportApi.post('/tax-reports/manual', {
      input_data: inputData
    })
    return response.data
  },

  /**
   * 获取财务数据列表（用于关联）
   */
  async getFinancialDataList(params: {
    skip?: number
    limit?: number
    fiscal_year?: number
  } = {}): Promise<{
    items: Array<{
      id: string
      fiscal_year: number
      period_type: string
      period_start: string
      period_end: string
      total_revenue: number
      taxable_sales: number
      input_tax: number
      output_tax: number
    }>
    total: number
  }> {
    const queryParams = new URLSearchParams()
    if (params.skip) queryParams.append('skip', String(params.skip))
    if (params.limit) queryParams.append('limit', String(params.limit))
    if (params.fiscal_year) queryParams.append('fiscal_year', String(params.fiscal_year))
    
    const response = await taxReportApi.get(`/financial-data?${queryParams.toString()}`)
    return response.data
  },

  /**
   * 获取税务报告统计信息
   */
  async statistics(): Promise<{
    total_reports: number
    total?: number  // 兼容旧字段名
    by_status: {
      pending?: number
      processing?: number
      completed?: number
      failed?: number
      pending_review?: number
      [key: string]: number | undefined
    }
    by_tax_type: Record<string, number>
    by_risk_level?: Record<string, number>
    needs_review_count: number
    needs_review?: number  // 兼容旧字段名
    recent_activity?: {
      last_7_days: number
      last_30_days: number
      today: number
    }
  }> {
    const response = await taxReportApi.get('/tax-reports/statistics')
    return response.data
  },

  /**
   * 获取税务报告的AI智能解释
   */
  async explainReport(
    analysisId: string,
    question?: string
  ): Promise<{
    report_id: string
    question?: string
    explanation: string
    report_summary?: {
      tax_type?: string
      total_tax_burden?: number
      risk_score?: number
      confidence_score?: number
    }
    generated_at: string
    success?: boolean
  }> {
    const response = await taxReportApi.post(
      `/tax-intelligence/report/${analysisId}/explain`,
      question ? { question } : null  // 修复：发送 null 而不是空对象
    )
    return response.data
  }
}

export default taxReportApiClient
