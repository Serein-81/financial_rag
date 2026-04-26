import request, { get, put } from '@/utils/request'

export interface TenantSettings {
  id?: string
  tenant_id: string
  created_at?: string
  updated_at?: string
  
  company_name: string
  company_logo?: string
  company_description?: string
  company_website?: string
  company_address?: string
  company_phone?: string
  company_email?: string
  
  admin_name?: string
  admin_email?: string
  admin_phone?: string
  
  // 企业画像（用于政策智能匹配）
  industry?: string
  region?: string
  scale?: string
  tax_types?: string[]
  
  max_users?: number
  max_storage_gb?: number
  max_knowledge_bases?: number
  max_documents?: number
  max_monthly_requests?: number
  
  enable_group_chat?: boolean
  enable_multi_agent?: boolean
  enable_knowledge_graph?: boolean
  enable_human_review?: boolean
  enable_audit?: boolean
  enable_tax_report?: boolean
  enable_financial_data?: boolean
  
  primary_color?: string
  secondary_color?: string
  custom_css?: string
  custom_footer?: string
  
  email_notification?: boolean
  system_notification?: boolean
  notification_email?: string
  
  is_active?: boolean
  is_trial?: boolean
  trial_expires_at?: string
  extra_settings?: any
}

export interface TenantSettingsUpdate {
  company_name?: string
  company_logo?: string
  company_description?: string
  company_website?: string
  company_address?: string
  company_phone?: string
  company_email?: string
  
  admin_name?: string
  admin_email?: string
  admin_phone?: string
  
  // 企业画像（用于政策智能匹配）
  industry?: string
  region?: string
  scale?: string
  tax_types?: string[]
  
  max_users?: number
  max_storage_gb?: number
  max_knowledge_bases?: number
  max_documents?: number
  max_monthly_requests?: number
  
  enable_group_chat?: boolean
  enable_multi_agent?: boolean
  enable_knowledge_graph?: boolean
  enable_human_review?: boolean
  enable_audit?: boolean
  enable_tax_report?: boolean
  enable_financial_data?: boolean
  
  primary_color?: string
  secondary_color?: string
  custom_css?: string
  custom_footer?: string
  
  email_notification?: boolean
  system_notification?: boolean
  notification_email?: string
  
  extra_settings?: any
}

export interface TenantSettingsListResponse {
  settings: TenantSettings[]
  total: number
}

export interface FeatureCheckResponse {
  enable_group_chat: boolean
  enable_multi_agent: boolean
  enable_knowledge_graph: boolean
  enable_human_review: boolean
  enable_audit: boolean
  enable_tax_report: boolean
  enable_financial_data: boolean
}

export interface FeatureToggleRequest {
  feature: string
  enabled: boolean
}

export const tenantSettingsApi = {
  getMySettings: () => {
    return get<TenantSettings>('/tenant-settings/me')
  },

  updateMySettings: (data: TenantSettingsUpdate) => {
    return put<TenantSettings>('/tenant-settings/me', data)
  },

  getPublicSettings: (tenantId: string) => {
    return get<TenantSettings>(`/tenant-settings/public/${tenantId}`)
  },

  getAllSettings: (skip = 0, limit = 20) => {
    return get<TenantSettingsListResponse>('/tenant-settings/', {
      params: { skip, limit }
    })
  },

  createSettings: (data: TenantSettings) => {
    return post<TenantSettings>('/tenant-settings/', data)
  },

  getSettingsByTenantId: (tenantId: string) => {
    return get<TenantSettings>(`/tenant-settings/${tenantId}`)
  },

  updateSettingsByTenantId: (tenantId: string, data: TenantSettingsUpdate) => {
    return put<TenantSettings>(`/tenant-settings/${tenantId}`, data)
  },

  deleteSettings: (tenantId: string) => {
    return del(`/tenant-settings/${tenantId}`)
  },

  toggleFeature: (feature: string, enabled: boolean) => {
    return post<TenantSettings>('/tenant-settings/feature-toggle', {
      feature,
      enabled
    } as FeatureToggleRequest)
  },

  checkFeatures: () => {
    return get<FeatureCheckResponse>('/tenant-settings/features/check')
  },

  checkFeaturesByTenant: (tenantId: string) => {
    return get<FeatureCheckResponse>(`/tenant-settings/features/${tenantId}/check`)
  },

  initializeSettings: (companyName: string) => {
    return post<TenantSettings>('/tenant-settings/initialize', null, {
      params: { company_name: companyName }
    })
  }
}

export default tenantSettingsApi
