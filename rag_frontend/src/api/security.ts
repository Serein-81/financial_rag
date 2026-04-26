/**
 * 安全 API
 * 
 * 提供租户隔离、权限控制、Cypher 验证的统一接口
 */

import { request, get, post, del } from '@/utils/request'

// ==================== 租户相关类型 ====================

export interface TenantContext {
  tenant_id: string
  user_id?: string
  roles: string[]
  isolation_level: 'strict' | 'shared' | 'hybrid'
  metadata: Record<string, any>
  created_at: string
  last_accessed: string
  accessed_count: number
}

export interface TenantQuota {
  max_queries: number
  max_concurrent: number
  max_data: number
  used_queries: number
  used_concurrent: number
  used_data: number
  quota_reset_at: string
}

export interface TenantStatistics {
  total_tenants: number
  max_tenants: number
  default_isolation_level: string
  cross_tenant_check_enabled: boolean
}

// ==================== 权限相关类型 ====================

export enum PermissionType {
  READ = 'read',
  WRITE = 'write',
  DELETE = 'delete',
  EXECUTE = 'execute',
  ADMIN = 'admin',
  SUPER_ADMIN = 'super_admin'
}

export enum RoleType {
  GUEST = 'guest',
  USER = 'user',
  PREMIUM_USER = 'premium_user',
  OPERATOR = 'operator',
  ADMIN = 'admin',
  SUPER_ADMIN = 'super_admin'
}

export interface Permission {
  name: string
  permission_type: PermissionType
  resource_type: string
  resource_id?: string
  description: string
}

export interface Role {
  name: string
  role_type: RoleType
  permissions: Permission[]
  parent_role?: string
  description: string
}

export interface UserRoleAssignment {
  user_id: string
  roles: string[]
  assigned_at: string
  assigned_by?: string
}

export interface PermissionStatistics {
  total_roles: number
  total_users: number
  cached_users: number
  roles: string[]
}

// ==================== Cypher 验证相关类型 ====================

export enum ValidationLevel {
  STRICT = 'strict',
  NORMAL = 'normal',
  PERMISSIVE = 'permissive'
}

export interface ValidationResult {
  is_valid: boolean
  errors: string[]
  warnings: string[]
  query_depth: number
  validation_level: string
}

export interface CypherValidatorStats {
  total_validated: number
  validation_level: string
  max_depth: number
  max_result_size: number
  allowed_labels_count: number
  allowed_rels_count: number
  allowed_props_count: number
}

// ==================== 安全审计相关类型 ====================

export interface SecurityEvent {
  event_id: string
  event_type: 'permission_denied' | 'quota_exceeded' | 'cypher_rejected' | 'tenant_access_denied'
  tenant_id?: string
  user_id?: string
  resource_type?: string
  resource_id?: string
  details: Record<string, any>
  timestamp: string
  ip_address?: string
  user_agent?: string
}

export interface SecurityAuditReport {
  total_events: number
  events_by_type: Record<string, number>
  recent_events: SecurityEvent[]
  top_denied_permissions: Array<{
    permission_type: string
    resource_type: string
    count: number
  }>
  top_quota_exceeded_tenants: Array<{
    tenant_id: string
    quota_type: string
    count: number
  }>
  timestamp: string
}

// ==================== API 函数 ====================

export const securityApi = {
  // 租户管理
  async getTenants(): Promise<TenantContext[]> {
    return get('/security/tenants')
  },

  async getTenant(tenant_id: string): Promise<TenantContext> {
    return get(`/security/tenants/${tenant_id}`)
  },

  async registerTenant(data: {
    tenant_id: string
    user_id?: string
    roles?: string[]
    metadata?: Record<string, any>
  }): Promise<TenantContext> {
    return post('/security/tenants', data)
  },

  async getTenantQuota(tenant_id: string): Promise<TenantQuota> {
    return get(`/security/tenants/${tenant_id}/quota`)
  },

  async checkTenantQuota(
    tenant_id: string,
    quota_type: string,
    increment?: number
  ): Promise<{ allowed: boolean; current: number; limit: number }> {
    return post(`/security/tenants/${tenant_id}/quota/check`, {
      quota_type,
      increment: increment || 1
    })
  },

  async validateDataAccess(
    tenant_id: string,
    resource_type: string,
    resource_id: string
  ): Promise<{ allowed: boolean; reason?: string }> {
    return post('/security/tenants/validate-access', {
      tenant_id,
      resource_type,
      resource_id
    })
  },

  async getTenantStatistics(): Promise<TenantStatistics> {
    return get('/security/tenants/statistics')
  },

  // 权限管理
  async getRoles(): Promise<Role[]> {
    return get('/security/roles')
  },

  async getRole(role_name: string): Promise<Role> {
    return get(`/security/roles/${role_name}`)
  },

  async createRole(data: Omit<Role, 'name'>): Promise<Role> {
    return post('/security/roles', data)
  },

  async getUserRoles(user_id: string): Promise<string[]> {
    return get(`/security/users/${user_id}/roles`)
  },

  async assignRole(user_id: string, role_name: string): Promise<void> {
    return post(`/security/users/${user_id}/roles`, { role_name })
  },

  async revokeRole(user_id: string, role_name: string): Promise<void> {
    return del(`/security/users/${user_id}/roles/${role_name}`)
  },

  async checkPermission(
    user_id: string,
    permission_type: PermissionType,
    resource_type: string,
    resource_id?: string
  ): Promise<{ allowed: boolean }> {
    return post('/security/permissions/check', {
      user_id,
      permission_type,
      resource_type,
      resource_id
    })
  },

  async getAccessibleResources(
    user_id: string,
    permission_type: PermissionType,
    resource_type: string
  ): Promise<string[]> {
    return get(`/security/users/${user_id}/accessible-resources`, {
      params: { permission_type, resource_type }
    })
  },

  async getPermissionStatistics(): Promise<PermissionStatistics> {
    return get('/security/statistics')
  },

  // Cypher 验证
  async validateCypher(query: string): Promise<ValidationResult> {
    return post('/security/cypher/validate', { query })
  },

  async getCypherValidatorStats(): Promise<CypherValidatorStats> {
    return get('/security/cypher/statistics')
  },

  // 安全审计
  async getSecurityEvents(params?: {
    start_time?: string
    end_time?: string
    event_type?: string
    limit?: number
  }): Promise<SecurityEvent[]> {
    const response = await get<{ events: SecurityEvent[]; total: number }>('/security/audit/events', { params })
    return response.events || []
  },

  async getSecurityAuditReport(params?: {
    start_time?: string
    end_time?: string
  }): Promise<SecurityAuditReport> {
    return get('/security/audit/report', { params })
  }
}

// 便捷函数
export function getRoleLabel(role_type: RoleType): string {
  const labels: Record<RoleType, string> = {
    [RoleType.GUEST]: '访客',
    [RoleType.USER]: '普通用户',
    [RoleType.PREMIUM_USER]: '高级用户',
    [RoleType.OPERATOR]: '运营人员',
    [RoleType.ADMIN]: '管理员',
    [RoleType.SUPER_ADMIN]: '超级管理员'
  }
  return labels[role_type] || role_type
}

export function getPermissionLabel(permission_type: PermissionType): string {
  const labels: Record<PermissionType, string> = {
    [PermissionType.READ]: '读取',
    [PermissionType.WRITE]: '写入',
    [PermissionType.DELETE]: '删除',
    [PermissionType.EXECUTE]: '执行',
    [PermissionType.ADMIN]: '管理',
    [PermissionType.SUPER_ADMIN]: '超级管理员'
  }
  return labels[permission_type] || permission_type
}

export function formatQuotaUsage(used: number, max: number): string {
  const percentage = max > 0 ? (used / max) * 100 : 0
  return `${used}/${max} (${percentage.toFixed(1)}%)`
}

export function getQuotaStatus(used: number, max: number): 'success' | 'warning' | 'danger' {
  const percentage = max > 0 ? (used / max) * 100 : 0
  if (percentage < 70) return 'success'
  if (percentage < 90) return 'warning'
  return 'danger'
}
