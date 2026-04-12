/**
 * 税务报告相关类型定义
 */

export enum TaxTypeEnum {
  VAT = 'vat',
  INCOME = 'income',
  PERSONAL = 'personal',
  CONSUMPTION = 'consumption',
  BEHAVIOR = 'behavior'
}

export enum TaxReportStatusEnum {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  PENDING_REVIEW = 'pending_review'
}

export enum RiskLevelEnum {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export interface TaxReportUploadRequest {
  file: File
  tax_type?: TaxTypeEnum
  tax_period_year?: number
  tax_period_month?: number
  description?: string
}

export interface DuplicateFileResponse {
  success: false
  error_type: 'DUPLICATE_FILE'
  message: string
  details: {
    original_filename: string
    existing_report_id: string
    existing_status: TaxReportStatusEnum
    existing_confidence_score: number | null
    existing_risk_level: RiskLevelEnum | null
    created_at: string
    suggestion: string
  }
}

export interface TaxIssue {
  id: string
  severity: RiskLevelEnum
  category: string
  description: string
  evidence: string[]
  legal_basis?: string[]
  recommendation?: string
  confidence: number
}

export interface RAGReference {
  content: string
  source: string
  relevance: number
}

export interface TaxReport {
  id: string
  tenant_id: string
  user_id: string
  filename: string
  original_filename: string
  file_type: string
  file_size: number
  file_size_mb: number
  tax_type?: TaxTypeEnum
  tax_period_year?: number
  tax_period_month?: number
  status: TaxReportStatusEnum
  processing_message?: string
  confidence_score?: number
  risk_score?: number
  risk_level?: RiskLevelEnum
  needs_human_review: boolean
  review_request_id?: string
  issues: TaxIssue[]
  rag_references: RAGReference[]
  tax_validation_result?: TaxValidationResult
  created_at: string
  updated_at: string
  completed_at?: string
}

export interface TaxReportUploadResponse {
  id: string
  filename: string
  file_size: number
  file_size_mb: number
  file_type: string
  status: TaxReportStatusEnum
  created_at: string
  message: string
}

export interface TaxReportListResponse {
  items: TaxReport[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface TaxReportStatusResponse {
  id: string
  status: TaxReportStatusEnum
  processing_message?: string
  progress_percent: number
  needs_human_review: boolean
}

export interface TaxReportFilter {
  status?: TaxReportStatusEnum
  tax_type?: TaxTypeEnum
  risk_level?: RiskLevelEnum
  needs_review?: boolean
  start_date?: string
  end_date?: string
  keyword?: string
  page?: number
  page_size?: number
}

export interface KeyMetrics {
  input_tax: number
  output_tax: number
  tax_difference: number
  tax_difference_rate: number
  tax_adjustments: {
    type: string
    amount: number
    description: string
  }[]
  invoice_count: {
    input: number
    output: number
  }
  reconciliation_status: 'normal' | 'warning' | 'error'
  reconciliation_details?: string
}

export interface TaxIssue {
  id?: string
  issue_type?: string
  category?: string
  severity?: 'low' | 'medium' | 'high' | 'critical' | 'info'
  risk_level?: 'low' | 'medium' | 'high' | 'critical' | 'info'
  description: string
  location?: string
  amount?: number
  tax_type?: string
  reference?: string
  suggestion?: string
  recommendations?: string[]
  evidence?: string[]
  confidence?: number
  source?: 'tax' | 'finance' | 'legal'
}

export interface TaxValidationResult {
  is_valid?: boolean
  errors: TaxIssue[]
  warnings: TaxIssue[]
  validation_rules?: {
    rule_name: string
    status: 'passed' | 'failed' | 'warning'
    details?: string
  }[]
}

export interface RAGReference {
  content?: string
  content_snippet?: string
  source?: string
  document_id?: string
  document_name?: string
  relevance_score?: number
  relevance?: number
}

export interface TaxIndicator {
  name: string
  value: number
  unit: string
  trend?: 'up' | 'down' | 'stable'
  threshold_warning?: boolean
  description?: string
}

export interface TaxReportProcessingResult {
  status: string
  report_id: string
  key_metrics?: KeyMetrics
  tax_findings?: TaxIssue[]
  finance_findings?: TaxIssue[]
  legal_findings?: TaxIssue[]
  tax_validation?: TaxValidationResult
  confidence_scores?: Record<string, number>
  conflicts?: Array<{
    item_a: string
    item_b: string
    conflict_type: string
    description: string
  }>
  evidence_gaps?: Array<{
    item: string
    required_evidence: string
    severity: 'low' | 'medium' | 'high'
  }>
  rag_contexts?: RAGReference[]
  needs_human_review: boolean
  review_trigger_reason?: string
  overall_risk_score: number
  risk_level: RiskLevelEnum
  summary?: {
    total_issues: number
    high_severity_issues: number
    tax_amount_at_risk: number
    recommendations: string[]
  }
}

export interface TaxReportWithDetails extends TaxReport {
  result?: TaxReportProcessingResult
  tax_validation?: TaxValidationResult
}

export interface UploadProgress {
  report_id: string
  filename: string
  progress: number
  status: TaxReportStatusEnum
  message?: string
}

export interface BatchUploadRequest {
  files: File[]
  tax_type?: TaxTypeEnum
  tax_period_year?: number
  tax_period_month?: number
}

export interface BatchUploadResponse {
  total: number
  successful: number
  failed: number
  reports: TaxReportUploadResponse[]
  errors: Array<{
    filename: string
    error: string
  }>
}
