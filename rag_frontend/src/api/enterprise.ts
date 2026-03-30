import { request } from '@/utils/request'

export interface EnterpriseUser {
  id: string
  email: string
  full_name: string
  nickname?: string
  phone?: string
  company_position?: string
  avatar_url?: string
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

export const enterpriseApi = {
  // 获取企业信息
  async getEnterprise(): Promise<EnterpriseResponse> {
    return request<EnterpriseResponse>('/enterprise/info')
  },

  // 获取企业用户列表
  async getUsers(): Promise<EnterpriseUser[]> {
    return request<EnterpriseUser[]>('/enterprise/users')
  },

  // 更新用户状态
  async updateUserStatus(userId: string, is_active: boolean): Promise<void> {
    return request<void>(`/enterprise/users/${userId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ is_active }),
    })
  },

  // 删除用户
  async deleteUser(userId: string): Promise<void> {
    return request<void>(`/enterprise/users/${userId}`, {
      method: 'DELETE',
    })
  },

  // 生成邀请码
  async createInviteCode(data?: CreateInviteCodeRequest): Promise<InviteCode> {
    return request<InviteCode>('/invite-codes', {
      method: 'POST',
      body: JSON.stringify(data || {}),
    })
  },

  // 获取邀请码列表
  async getInviteCodes(): Promise<InviteCode[]> {
    return request<InviteCode[]>('/invite-codes')
  },

  // 禁用邀请码
  async deactivateInviteCode(code: string): Promise<void> {
    return request<void>(`/invite-codes/${code}`, {
      method: 'DELETE',
    })
  },
}
