import { request } from '@/utils/request'

export enum PermissionLevel {
  PUBLIC = 'public',
  SENSITIVE = 'sensitive',
  DANGEROUS = 'dangerous',
  CRITICAL = 'critical',
}

export enum SessionState {
  IDLE = 'idle',
  PROCESSING = 'processing',
  WAITING_FOR_USER_REPLY = 'waiting',
  COMPLETED = 'completed',
}

export enum ApprovalStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  TIMEOUT = 'timeout',
}

export enum IntentClassificationStage {
  KEYWORD = 'keyword',
  EMBEDDING = 'embedding',
  SLM = 'slm',
}

export interface UserRole {
  role_id: string
  role_name: string
  permissions: PermissionLevel[]
}

export interface RBACPolicy {
  policy_id: string
  role: string
  allowed_operations: string[]
  denied_operations: string[]
  created_at: string
}

export interface HITLApproval {
  approval_id: string
  task_id: string
  user_id: string
  user_name?: string
  applicant_user_id?: string
  applicant_name?: string
  operator_user_id?: string
  operator_name?: string
  operation: string
  details: Record<string, any>
  risk_level: PermissionLevel
  status: ApprovalStatus
  created_at: string
  expires_at: string
  reviewed_at?: string
  reviewer_notes?: string
}

export interface StreamingTask {
  task_id: string
  agent_id: string
  agent_name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'streaming'
  progress: number
  started_at?: string
  completed_at?: string
  result?: any
  error?: string
  estimated_time?: number
}

export interface TaskPipeline {
  pipeline_id: string
  session_id: string
  user_id: string
  query: string
  tasks: StreamingTask[]
  state: SessionState
  intent_classification?: IntentClassificationResult
  created_at: string
  updated_at: string
}

export interface IntentClassificationResult {
  stage: IntentClassificationStage
  intent: string
  confidence: number
  is_expense_related: boolean
  should_process: boolean
  matched_keywords?: string[]
  embedding_score?: number
  reasoning?: string
}

export interface SecurityEvent {
  event_id: string
  event_type: 'permission_denied' | 'approval_request' | 'approval_completed' | 'prompt_injection' | 'role_change'
  user_id: string
  target_resource?: string
  details: Record<string, any>
  severity: 'low' | 'medium' | 'high' | 'critical'
  ip_address?: string
  user_agent?: string
  created_at: string
}

export interface SessionContext {
  session_id: string
  user_id: string
  state: SessionState
  pending_questions: PendingQuestion[]
  historical_results: Record<string, any>
  current_task_id?: string
  created_at: string
  updated_at: string
}

export interface PendingQuestion {
  question_id: string
  source_agent: string
  question_content: string
  expected_params: string[]
}

export interface AgentMetric {
  agent_id: string
  agent_name: string
  total_requests: number
  success_rate: number
  avg_latency: number
  last_execution?: string
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'down'
  components: {
    rbac_service: boolean
    task_scheduler: boolean
    session_blackboard: boolean
    hitl_manager: boolean
    intent_classifier: boolean
  }
  uptime: number
  active_sessions: number
  pending_approvals: number
}

export const multiAgentApi = {
  async getSystemHealth(): Promise<SystemHealth> {
    return request<SystemHealth>('/multi-agent/monitor/health')
  },

  async getAgentMetrics(): Promise<AgentMetric[]> {
    return request<AgentMetric[]>('/multi-agent/metrics')
  },

  async getUserRoles(): Promise<UserRole[]> {
    return request<UserRole[]>('/multi-agent/rbac/roles')
  },

  async getRBACPolicies(): Promise<RBACPolicy[]> {
    return request<RBACPolicy[]>('/multi-agent/rbac/policies')
  },

  async getPendingApprovals(): Promise<HITLApproval[]> {
    return request<HITLApproval[]>('/multi-agent/hitl/pending')
  },

  async getApprovalHistory(params?: { status?: ApprovalStatus; limit?: number }): Promise<HITLApproval[]> {
    return request<HITLApproval[]>('/multi-agent/hitl/history', { params })
  },

  async createApproval(taskId: string, operation: string, details: Record<string, any>): Promise<HITLApproval> {
    return request<HITLApproval>('/multi-agent/hitl/approve', {
      method: 'POST',
      data: { task_id: taskId, operation, details },
    })
  },

  async reviewApproval(approvalId: string, action: 'approve' | 'reject', notes?: string): Promise<HITLApproval> {
    return request<HITLApproval>(`/multi-agent/hitl/${approvalId}/review`, {
      method: 'POST',
      data: { action, notes },
    })
  },

  async getActivePipelines(): Promise<TaskPipeline[]> {
    return request<TaskPipeline[]>('/multi-agent/pipelines/active')
  },

  async getPipelineHistory(params?: { limit?: number; session_id?: string }): Promise<TaskPipeline[]> {
    return request<TaskPipeline[]>('/multi-agent/pipelines/history', { params })
  },

  async getSessionContext(sessionId: string): Promise<SessionContext> {
    return request<SessionContext>(`/multi-agent/session/${sessionId}`)
  },

  async classifyIntent(message: string, useAdvanced?: boolean): Promise<IntentClassificationResult> {
    return request<IntentClassificationResult>('/multi-agent/intent/classify', {
      method: 'POST',
      data: { message, use_advanced: useAdvanced ?? true },
    })
  },

  async testIntentClassification(messages: string[]): Promise<IntentClassificationResult[]> {
    return request<IntentClassificationResult[]>('/multi-agent/intent/test', {
      method: 'POST',
      data: { messages },
    })
  },

  async getSecurityEvents(params?: { severity?: string; limit?: number }): Promise<SecurityEvent[]> {
    return request<SecurityEvent[]>('/multi-agent/security/events', { params })
  },

  async getSecurityStats(): Promise<{
    total_events: number
    by_severity: Record<string, number>
    by_type: Record<string, number>
    recent_trends: Array<{ date: string; count: number }>
  }> {
    return request('/multi-agent/security/stats')
  },

  async streamTaskResults(sessionId: string): Promise<ReadableStream> {
    const response = await fetch(`/multi-agent/stream/${sessionId}`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem('rag_token')}`,
      },
    })
    return response.body as ReadableStream
  },
}
