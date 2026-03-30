import { request } from '@/utils/request'
import type {
  AuditTask,
  AuditResult,
  AuditDocument,
  AuditType
} from '@/types'

export interface CreateAuditTaskRequest {
  audit_type: AuditType
  documents: AuditDocument[]
}

export const auditApi = {
  async createTask(data: CreateAuditTaskRequest): Promise<AuditTask> {
    return request<AuditTask>('/audit/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async getTask(taskId: string): Promise<AuditTask> {
    return request<AuditTask>(`/audit/tasks/${taskId}`)
  },

  async getTaskResults(taskId: string): Promise<AuditResult> {
    return request<AuditResult>(`/audit/tasks/${taskId}/results`)
  },

  async getTasks(): Promise<AuditTask[]> {
    return request<AuditTask[]>('/audit/tasks')
  },
}
