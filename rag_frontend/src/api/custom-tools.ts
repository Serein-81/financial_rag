import { request } from '@/utils/request'

export type CustomToolKind = 'echo' | 'http' | 'rag_query' | 'python_code'

export interface ToolFieldSpec {
  type: string
  description?: string
  required?: boolean
  default?: any
}

export interface CustomToolSpec {
  name: string
  display_name: string
  description: string
  purpose?: string
  kind: CustomToolKind
  version: string
  input_schema: Record<string, ToolFieldSpec>
  output_schema: Record<string, ToolFieldSpec>
  runtime_config: Record<string, any>
  safety_policy: Record<string, any>
  generated_code?: string | null
  agent_id?: string | null
}

export interface CustomTool extends CustomToolSpec {
  id: string
  status: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface GenerateToolRequest {
  natural_language: string
  purpose?: string
  inputs?: string
  outputs?: string
  preferred_kind?: CustomToolKind
  agent_id?: string
}

export const customToolsApi = {
  generate(payload: GenerateToolRequest) {
    return request<CustomToolSpec>('/custom-tools/generate', {
      method: 'POST',
      data: payload,
    })
  },

  generateCode(spec: CustomToolSpec, instruction?: string) {
    return request<CustomToolSpec>('/custom-tools/generate-code', {
      method: 'POST',
      data: { spec, instruction },
    })
  },

  create(payload: CustomToolSpec) {
    return request<CustomTool>('/custom-tools', {
      method: 'POST',
      data: payload,
    })
  },

  list() {
    return request<{ total: number; tools: CustomTool[] }>('/custom-tools')
  },

  publish(toolId: string, agentId?: string) {
    return request<CustomTool>(`/custom-tools/${toolId}/publish`, {
      method: 'POST',
      data: { agent_id: agentId || null },
    })
  },

  execute(toolId: string, argumentsPayload: Record<string, any>) {
    return request<any>(`/custom-tools/${toolId}/execute`, {
      method: 'POST',
      data: { arguments: argumentsPayload },
    })
  },
}
