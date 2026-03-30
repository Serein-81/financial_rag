import { request } from '@/utils/request'

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

export interface ToolTracesResponse {
  traces: ToolTrace[]
  total: number
}

export const agentTraceApi = {
  async getSessionTraces(session_id: string): Promise<AgentTrace[]> {
    return request<AgentTrace[]>(`/api/v1/agent-trace/session/${session_id}`)
  },

  async getTrace(trace_id: string): Promise<AgentTrace> {
    return request<AgentTrace>(`/api/v1/agent-trace/${trace_id}`)
  },

  async getToolTraces(session_id: string): Promise<ToolTracesResponse> {
    return request<ToolTracesResponse>(`/api/v1/tool-trace/session/${session_id}`)
  },
}
