import { request } from '@/utils/request'

export enum ToolLocation {
  LOCAL = 'local',
  CLOUD = 'cloud',
  MCP = 'mcp',
}

export enum AgentType {
  SPECIALIST = 'specialist',
  GENERAL = 'general',
  ROUTER = 'router',
  UTILITY = 'utility',
}

export interface ToolInfo {
  name: string
  description: string
  location: ToolLocation
  category?: string
  tags: string[]
  agent_id?: string
  agent_name?: string
  parameters?: Record<string, any>
  is_async?: boolean
  enabled?: boolean
}

export interface AgentSummary {
  agent_id: string
  agent_name: string
  agent_type: string
  specialty?: string
  description: string
  tool_count: number
  tool_breakdown: {
    local?: number
    cloud?: number
    mcp?: number
  }
  enabled: boolean
  capabilities: string[]
}

export interface AgentDetail extends AgentSummary {
  tools: ToolInfo[]
  tool_summary: {
    local?: number
    cloud?: number
    mcp?: number
  }
  created_at: string
  last_updated: string
}

export interface RegistrySummary {
  total_agents: number
  enabled_agents: number
  total_tools: number
  tool_breakdown: {
    local?: number
    cloud?: number
    mcp?: number
  }
  agents: AgentSummary[]
}

export interface AgentTraceEvent {
  timestamp: string
  event_type: 'start' | 'thinking' | 'tool_call' | 'tool_result' | 'response' | 'end'
  content: string
  metadata?: Record<string, any>
}

export interface AgentTraceStep {
  step_number: number
  step_type: 'thought' | 'action' | 'observation' | 'final_answer' | string
  content: string
  tool_name?: string
  tool_input?: Record<string, any>
  tool_output?: string
  tool_duration?: number
  confidence?: number
  timestamp: number
}

export interface AgentTrace {
  trace_id: string
  agent_type: string
  user_query: string
  status: 'running' | 'completed' | 'failed'
  total_iterations?: number
  total_time?: number
  tool_calls_count?: number
  created_at: string
  final_answer?: string
  events?: AgentTraceEvent[]
  steps?: AgentTraceStep[]
  session_id?: string
  query?: string
}

export const agentDiscoveryApi = {
  async getSummary(): Promise<RegistrySummary> {
    return request<RegistrySummary>('/agent-discovery/summary')
  },

  async getAgents(agent_type?: string, enabled_only: boolean = true): Promise<AgentSummary[]> {
    const params = new URLSearchParams()
    if (agent_type) params.append('agent_type', agent_type)
    params.append('enabled_only', String(enabled_only))
    return request<AgentSummary[]>(`/agent-discovery/agents?${params.toString()}`)
  },

  async getAgent(agent_id: string): Promise<AgentDetail> {
    return request<AgentDetail>(`/agent-discovery/agents/${agent_id}`)
  },

  async getTools(location?: ToolLocation, agent_id?: string, enabled_only: boolean = true): Promise<ToolInfo[]> {
    const params = new URLSearchParams()
    if (location) params.append('location', location)
    if (agent_id) params.append('agent_id', agent_id)
    params.append('enabled_only', String(enabled_only))
    return request<ToolInfo[]>(`/agent-discovery/tools?${params.toString()}`)
  },

  async getTraces(limit: number = 50): Promise<{total: number; traces: AgentTrace[]}> {
    return request<{total: number; traces: AgentTrace[]}>(`/agent-discovery/traces?limit=${limit}`)
  },

  async getTrace(trace_id: string): Promise<AgentTrace> {
    return request<AgentTrace>(`/agent-discovery/traces/${trace_id}/steps`)
  },

  async getTraceVisualization(trace_id: string): Promise<{
    nodes: any[]
    edges: any[]
    summary: any
  }> {
    return request<{
      nodes: any[]
      edges: any[]
      summary: any
    }>(`/agent-discovery/traces/${trace_id}/visualization`)
  },
}
