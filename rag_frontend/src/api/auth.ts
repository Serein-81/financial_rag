import { request, requestForm } from '@/utils/request'

export interface SendSMSRequest {
  phone: string
}

export interface SendSMSResponse {
  success: boolean
  message: string
  expire_seconds: number
  debug_code?: string
}

export interface VerifySMSRequest {
  phone: string
  code: string
}

export interface VerifySMSResponse {
  success: boolean
  message: string
}

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

export interface UploadAvatarResponse {
  status: string
  message: string
  avatar_url: string
}

export const authApi = {
  async sendSMS(data: SendSMSRequest): Promise<SendSMSResponse> {
    return request<SendSMSResponse>('/auth/sms/send', {
      method: 'POST',
      data: JSON.stringify(data),
    })
  },

  async verifySMS(data: VerifySMSRequest): Promise<VerifySMSResponse> {
    return request<VerifySMSResponse>('/auth/sms/verify', {
      method: 'POST',
      data: JSON.stringify(data),
    })
  },

  async getMe(): Promise<UserProfile> {
    return request<UserProfile>('/auth/me')
  },

  async updateProfile(data: UpdateProfileRequest): Promise<UserProfile> {
    return request<UserProfile>('/auth/profile', {
      method: 'PUT',
      data: JSON.stringify(data),
    })
  },

  async uploadAvatar(file: File): Promise<UploadAvatarResponse> {
    const formData = new FormData()
    formData.append('file', file)
    return requestForm<UploadAvatarResponse>('/auth/avatar', formData)
  },
}
