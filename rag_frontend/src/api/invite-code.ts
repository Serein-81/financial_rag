import { request } from '@/utils/request'

export interface InviteCode {
  id: string
  code: string
  tenant_id: string
  created_by: string
  max_uses: number
  used_count: number
  expires_at: string
  description?: string
  role: string
  is_active: boolean
  is_expired: boolean
  is_exhausted: boolean
  is_valid: boolean
  remaining_uses: number
  created_at: string
  updated_at?: string
}

export interface InviteCodeStats {
  total_codes: number
  active_codes: number
  expired_codes: number
  exhausted_codes: number
  total_uses: number
  total_invited_users: number
}

export interface InviteCodeValidationResult {
  valid: boolean
  message: string
  tenant_id?: string
  company_name?: string
  creator_name?: string
  description?: string
  expires_at?: string
  remaining_uses?: number
}

export interface CreateInviteCodeRequest {
  max_uses: number
  expires_hours: number
  description?: string
  role?: string
}

export interface BatchCreateInviteCodeRequest {
  count: number
  max_uses: number
  expires_hours: number
  description_template?: string
  role?: string
}

export interface UpdateInviteCodeRequest {
  is_active?: boolean
  description?: string
}

export const inviteCodeApi = {
  async getCodes(params: {
    skip?: number
    limit?: number
    include_inactive?: boolean
  } = {}): Promise<InviteCode[]> {
    const { skip = 0, limit = 20, include_inactive = false } = params
    return request<InviteCode[]>(
      `/api/v1/invite-code?skip=${skip}&limit=${limit}&include_inactive=${include_inactive}`
    )
  },

  async getCode(codeId: string): Promise<InviteCode> {
    return request<InviteCode>(`/api/v1/invite-code/${codeId}`)
  },

  async createCode(data: CreateInviteCodeRequest): Promise<InviteCode> {
    return request<InviteCode>('/api/v1/invite-code', {
      method: 'POST',
      body: data,
    })
  },

  async batchCreateCodes(
    data: BatchCreateInviteCodeRequest
  ): Promise<InviteCode[]> {
    return request<InviteCode[]>('/api/v1/invite-code/batch', {
      method: 'POST',
      body: data,
    })
  },

  async updateCode(
    codeId: string,
    data: UpdateInviteCodeRequest
  ): Promise<InviteCode> {
    return request<InviteCode>(`/api/v1/invite-code/${codeId}`, {
      method: 'PUT',
      body: data,
    })
  },

  async deleteCode(code: string): Promise<void> {
    return request(`/api/v1/invite-code/${code}`, {
      method: 'DELETE',
    })
  },

  async getStats(): Promise<InviteCodeStats> {
    return request<InviteCodeStats>('/api/v1/invite-code/stats')
  },

  async validateCode(code: string): Promise<InviteCodeValidationResult> {
    return request<InviteCodeValidationResult>(
      `/api/v1/invite-code/validate/${code}`
    )
  },
}
