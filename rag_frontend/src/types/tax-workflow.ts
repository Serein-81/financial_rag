/**
 * 税务提交流工作流类型定义
 */

export enum WorkflowEventType {
  STARTED = 'workflow_started',
  STEP_STARTED = 'step_started',
  STEP_COMPLETED = 'step_completed',
  STEP_FAILED = 'step_failed',
  STEP_WARNING = 'step_warning',
  STATUS_CHANGED = 'status_changed',
  DATA_UPDATED = 'data_updated',
  HUMAN_REVIEW_REQUIRED = 'human_review_required',
  HUMAN_REVIEW_COMPLETED = 'human_review_completed',
  COMPLETED = 'workflow_completed',
  FAILED = 'workflow_failed',
  HEARTBEAT = 'heartbeat'
}

export enum WorkflowStepStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  WARNING = 'warning',
  WAITING_REVIEW = 'waiting_review'
}

export interface WorkflowEvent {
  event_id: string
  event_type: WorkflowEventType
  workflow_id: string
  session_id: string
  timestamp: string
  step_name?: string
  step_number?: number
  data: Record<string, any>
  error?: string
  error_details?: {
    message?: string
    stack?: string
    context?: Record<string, any>
  }
}

export interface WorkflowStep {
  name: string
  number: number
  status: WorkflowStepStatus
  startTime?: string
  endTime?: string
  duration?: number
  data?: Record<string, any>
  error?: string
  errorDetails?: Record<string, any>
  warnings?: string[]
}

export interface TaxWorkflowState {
  workflowId: string
  sessionId: string
  status: 'idle' | 'running' | 'completed' | 'failed'
  currentStep: number
  totalSteps: number
  steps: WorkflowStep[]
  validationResult?: ValidationResultData
  financialData?: FinancialDataResult
  taxCalculations?: TaxCalculationResult[]
  riskAssessment?: RiskAssessmentResult
  humanReviewRequest?: HumanReviewRequestData
  error?: string
  startTime?: string
  endTime?: string
  duration?: number
}

export interface ValidationResultData {
  isValid: boolean
  errors: string[]
  warnings: string[]
  validatedFields: string[]
}

export interface FinancialDataResult {
  totalRevenue: number
  taxableSales: number
  totalExpenses: number
  inputTax: number
  outputTax: number
  taxableIncome: number
  dataStatus: string
}

export interface TaxCalculationResult {
  taxType: string
  taxableAmount: number
  taxRate: number
  calculatedTax: number
  effectiveRate: number
  inputTax: number
  outputTax: number
  netTaxPayable: number
}

export interface RiskAssessmentResult {
  overallScore: number
  riskItems: RiskItem[]
  highRiskCount: number
  mediumRiskCount: number
  lowRiskCount: number
}

export interface RiskItem {
  riskId: string
  riskType: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  description: string
  legalBasis: string[]
  potentialPenalty: string
  remediationSuggestions: string[]
}

export interface HumanReviewRequestData {
  reviewId: string
  reason: string
  requestedAt: string
  requestedBy: string
  status: 'pending' | 'approved' | 'rejected'
  riskItems: RiskItem[]
  reviewData?: Record<string, any>
}

export interface WorkflowHistoryItem {
  event: WorkflowEvent
  stepName?: string
  stepNumber?: number
  message: string
  severity: 'info' | 'warning' | 'error' | 'success'
}

export const WORKFLOW_STEPS = [
  { name: 'validate_submission', label: '数据验证', description: '验证提交数据的完整性和合法性' },
  { name: 'fetch_financial_data', label: '获取财务数据', description: '从数据库获取财务数据' },
  { name: 'calculate_taxes', label: '税务计算', description: '执行税务计算' },
  { name: 'assess_risk', label: '风险评估', description: '评估税务风险' },
  { name: 'human_review', label: '人工审核', description: '高风险项需人工审核' },
  { name: 'save_submission', label: '保存结果', description: '保存税务分析结果' }
]

export const STEP_ICONS: Record<string, string> = {
  validate_submission: 'DocumentCheck',
  fetch_financial_data: 'DataLine',
  calculate_taxes: 'Money',
  assess_risk: 'Warning',
  human_review: 'UserFilled',
  save_submission: 'Check'
}

export const STEP_COLORS: Record<WorkflowStepStatus, string> = {
  [WorkflowStepStatus.PENDING]: '#909399',
  [WorkflowStepStatus.RUNNING]: '#409EFF',
  [WorkflowStepStatus.COMPLETED]: '#67C23A',
  [WorkflowStepStatus.FAILED]: '#F56C6C',
  [WorkflowStepStatus.WARNING]: '#E6A23C',
  [WorkflowStepStatus.WAITING_REVIEW]: '#9B59B6'
}
