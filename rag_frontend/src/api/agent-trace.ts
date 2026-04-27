import { request } from '@/utils/request'

export interface AgentTraceEvent {
  timestamp: string | number
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
  status?: string
  agent_type?: string
  user_query?: string
  final_answer?: string
  steps?: any[]
  total_iterations?: number
  tool_calls_count?: number
}

export interface ToolTrace {
  tool_id: string
  trace_id?: string
  tool_name: string
  input: Record<string, any>
  output?: any
  error?: string
  start_time: string | number
  end_time?: string
  duration?: number
  status?: string
  tool_type?: string
}

export interface ToolTracesResponse {
  traces: ToolTrace[]
  total: number
}

export interface TraceVisualization {
  trace_id: string
  nodes: any[]
  edges: any[]
  summary: any
}

function stepToEvent(step: any): AgentTraceEvent {
  const eventTypeMap: Record<string, AgentTraceEvent['event_type']> = {
    thought: 'thinking',
    action: 'tool_call',
    observation: 'tool_result',
    final_answer: 'response',
  }

  return {
    timestamp: step.timestamp || step.created_at || '',
    event_type: eventTypeMap[step.step_type] || 'response',
    content: step.content || '',
    metadata: {
      step_number: step.step_number,
      step_type: step.step_type,
      tool_name: step.tool_name,
      tool_input: step.tool_input,
      tool_output: step.tool_output,
      tool_duration: step.tool_duration,
      confidence: step.confidence,
    },
  }
}

function normalizeTrace(trace: any): AgentTrace {
  const steps = trace.steps || []
  return {
    ...trace,
    trace_id: trace.trace_id,
    session_id: trace.session_id || '',
    query: trace.query || trace.user_query || '',
    events: trace.events || steps.map(stepToEvent),
    total_time: trace.total_time || 0,
    created_at: trace.created_at || '',
    steps,
  }
}

export const agentTraceApi = {
  async getSessionTraces(session_id: string): Promise<AgentTrace[]> {
    const response = await request<{ traces?: any[] } | any[]>(`/agent_trace/traces/${session_id}`)
    const traces = Array.isArray(response) ? response : response.traces || []
    return traces.map(normalizeTrace)
  },

  async getTrace(trace_id: string): Promise<AgentTrace> {
    const response = await request<any>(`/agent_trace/traces/${trace_id}/steps`)
    return normalizeTrace(response)
  },

  async getVisualization(trace_id: string): Promise<TraceVisualization> {
    return request<TraceVisualization>(`/agent_trace/traces/${trace_id}/visualization`)
  },

  async getToolTraces(session_id: string): Promise<ToolTracesResponse> {
    return request<ToolTracesResponse>(`/tool_trace/session/${session_id}`)
  },
}
