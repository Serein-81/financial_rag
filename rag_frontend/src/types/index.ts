export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  timestamp: number
}

export interface Source {
  filename: string
  score: number
  content: string
}

export interface StreamEvent {
  type: 'sources' | 'content' | 'session'
  data?: Source[]
  delta?: string
  id?: string // session id for new sessions
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: number
  updatedAt: number
}

export interface SystemStatus {
  database: 'connected' | 'disconnected'
  model: string
  latency: number
}

// API 2.0 Types

export interface AuthResponse {
  access_token: string
  token_type: string
  user_name: string
  avatar_url?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
}

export type VisibilityType = 'private' | 'enterprise'

export type DocumentVisibilityType = 'private' | 'public'

export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  visibility: VisibilityType
  user_id: string
  created_at: string
}

export interface CreateKnowledgeBaseRequest {
  name: string
  description?: string
  visibility?: VisibilityType
}

export interface Document {
  id: string
  kb_id: string
  user_id: string
  visibility: DocumentVisibilityType
  filename: string
  file_type: string | null
  file_size: number | null
  status: string
  meta_info: Record<string, unknown>
  created_at: string
  error_msg: string | null
}

export interface UploadResponse {
  msg: string
  doc_id: string
  status: string
}

export interface Session {
  id: string
  title: string
  created_at?: string | null
  updated_at?: string | null
}

export interface SessionMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
}

export interface ChatRequestV2 {
  query: string
  kb_id?: string | null
  top_k?: number
  session_id?: string | null
}

export interface SearchResultRequest {
  query: string
  kb_id?: string | null
  top_k: number
  score_threshold: number
}

// Audit Types
export type AuditType = 'financial' | 'legal' | 'tax' | 'compliance'
export type AuditSeverity = 'low' | 'medium' | 'high' | 'critical'

export interface AuditDocument {
  name: string
  content: string
  type: string
}

export interface Finding {
  id?: string
  category: string
  description: string
  severity: AuditSeverity
  confidence: number
  evidence?: string
  agent_name?: string
  risk_score?: number
  legal_basis?: string[]
  recommendations?: string[]
}

export interface Conflict {
  id?: string
  type: string
  description: string
  severity: string
  finding_ids: string[]
  resolution_suggestion?: string
}

export interface AuditStatistics {
  total_findings: number
  total_conflicts: number
  average_confidence: number
  risk_level_distribution?: Record<string, number>
  agent_contribution?: Record<string, number>
  category_distribution?: Record<string, number>
  average_risk_score?: number
}

export interface AuditTask {
  id: string
  tenant_id: string
  user_id: string
  audit_type: AuditType
  status: 'pending' | 'processing' | 'completed' | 'failed'
  documents: AuditDocument[]
  created_at: string
  completed_at?: string
  error_message?: string
}

export interface AuditResult {
  task_id: string
  tenant_id: string
  audit_type: AuditType
  findings: Finding[]
  conflicts: Conflict[]
  overall_risk_score: number
  summary: string
  recommendations: string[]
  statistics: AuditStatistics
  created_at: string
}

// Enterprise Types
export interface EnterpriseUser {
  id: string
  email: string
  full_name: string | null
  nickname?: string | null
  phone?: string | null
  company_position?: string | null
  avatar_url?: string | null
  is_active: boolean
  is_admin: boolean
  created_at: string
}

export interface InviteCode {
  code: string
  created_by: string
  created_at: string
  expires_at: string
  max_uses: number
  used_count: number
  is_active: boolean
}

export interface CreateInviteCodeRequest {
  max_uses?: number
  expires_in_days?: number
}

export interface EnterpriseResponse {
  id: string
  name: string
  tenant_id: string
  created_at: string
  member_count: number
}

// Memory Types
export interface MemorySearchRequest {
  keywords: string[]
  session_id: string
  role?: 'user' | 'assistant' | 'system'
  importance_min?: number
  top_k?: number
}

export interface MemoryResult {
  id: string
  content: string
  role: 'user' | 'assistant' | 'system'
  timestamp: string
  importance: number
  access_count: number
  decay_factor: number
  metadata: {
    topic?: string
    confidence?: number
  }
}

export interface MemoryStatistics {
  total_memories: number
  user_memories: number
  assistant_memories: number
  average_importance: number
  most_accessed_topic: string
  memory_distribution: {
    high_importance: number
    medium_importance: number
    low_importance: number
  }
}

export interface SessionSummary {
  session_id: string
  total_messages: number
  key_topics: string[]
  important_insights: string[]
  conversation_flow: string
  generated_at: string
}

// Knowledge Graph Types
export interface KnowledgeGraphEntity {
  name: string
  type: string
  properties: Record<string, any>
}

export interface KnowledgeGraphRelation {
  source: string
  target: string
  type: string
  properties: Record<string, any>
}

export interface BuildKnowledgeGraphRequest {
  text: string
  user_id?: string
  session_id?: string
  extract_entities?: boolean
  extract_relations?: boolean
}

export interface KnowledgeGraphSearchRequest {
  query: string
  user_id?: string
  session_id?: string
  top_k?: number
  vector_weight?: number
  graph_weight?: number
  use_graph?: boolean
}

// Agent Trace Types
export interface AgentTraceEvent {
  timestamp: string
  event_type: 'start' | 'thinking' | 'tool_call' | 'tool_result' | 'response' | 'end'
  content: string
  metadata?: Record<string, any>
}

export interface AgentTrace {
  trace_id: string
  session_id: string
  query: string
  events: AgentTraceEvent[]
  total_time: number
  created_at: string
}

export interface ToolTrace {
  tool_id: string
  tool_name: string
  input: Record<string, any>
  output?: Record<string, any>
  error?: string
  start_time: string
  end_time?: string
  duration?: number
}

// Prompt Types
export interface PromptTemplate {
  id: string
  name: string
  description: string
  system_prompt: string
  user_prompt_template: string
  variables: string[]
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface CreatePromptRequest {
  name: string
  description: string
  system_prompt: string
  user_prompt_template: string
  is_default?: boolean
}

// Log Types
export interface LogEntry {
  timestamp: string
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
  module: string
  message: string
  details?: Record<string, any>
}

export interface LogsResponse {
  logs: LogEntry[]
  total: number
  page: number
  page_size: number
}

export interface LogsQueryParams {
  page?: number
  page_size?: number
  level?: string
  module?: string
  keyword?: string
  start_date?: string
  end_date?: string
}

// User Profile Types
export interface UserProfile {
  id: string
  email: string
  full_name: string | null
  nickname: string | null
  phone: string | null
  avatar_url: string | null
  tenant_id: string | null
  is_admin: boolean
  is_active: boolean
  company_name: string | null
  created_at: string
}

export interface UpdateProfileRequest {
  full_name?: string
  nickname?: string
  bio?: string
}
