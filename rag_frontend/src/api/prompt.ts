import { request } from '@/utils/request'

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

export interface OptimizePromptRequest {
  original_prompt: string
  objective: string
  examples?: string[]
}

export interface OptimizePromptResponse {
  optimized_prompt: string
  improvements: string[]
  estimated_improvement: string
}

export const promptApi = {
  async getTemplates(): Promise<PromptTemplate[]> {
    return request<PromptTemplate[]>('/prompt/templates')
  },

  async getTemplate(id: string): Promise<PromptTemplate> {
    return request<PromptTemplate>(`/prompt/templates/${id}`)
  },

  async createTemplate(data: CreatePromptRequest): Promise<PromptTemplate> {
    return request<PromptTemplate>('/prompt/templates', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateTemplate(id: string, data: Partial<CreatePromptRequest>): Promise<PromptTemplate> {
    return request<PromptTemplate>(`/prompt/templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteTemplate(id: string): Promise<void> {
    return request<void>(`/prompt/templates/${id}`, {
      method: 'DELETE',
    })
  },

  async optimizePrompt(data: OptimizePromptRequest): Promise<OptimizePromptResponse> {
    return request<OptimizePromptResponse>('/prompt/optimize', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
}
