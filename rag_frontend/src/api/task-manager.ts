import { request } from '@/utils/request'

export interface ScheduledTask {
  id: string
  name: string
  description: string
  task_type: 'tax_reminder' | 'financial_report' | 'policy_update' | 'anomaly_check' | 'custom'
  frequency: 'once' | 'daily' | 'weekly' | 'monthly' | 'quarterly'
  next_run_time: string
  last_run_time?: string
  enabled: boolean
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused'
  params: Record<string, any>
  result?: {
    status: string
    message?: string
    data?: any
  }
  created_at: string
  updated_at: string
}

export interface TaskExecutionLog {
  id: string
  task_id: string
  scheduled_task_id?: string
  task_name?: string
  task_type?: string
  status: 'started' | 'completed' | 'failed' | 'cancelled'
  start_time: string
  end_time?: string
  duration?: number
  result?: {
    success: boolean
    message?: string
    data?: any
  }
  error?: string
  error_traceback?: string
  execution_type?: 'scheduled' | 'manual'
  triggered_manually?: boolean
  created_at: string
}

export interface CreateTaskParams {
  name: string
  description?: string
  task_type: ScheduledTask['task_type']
  frequency: ScheduledTask['frequency']
  next_run_time: string
  params?: Record<string, any>
}

export interface TaskStatistics {
  total_tasks: number
  active_tasks: number
  paused_tasks: number
  completed_today: number
  failed_today: number
  upcoming_tasks: ScheduledTask[]
}

export const taskManagerApi = {
  listTasks: async (params: {
    task_type?: string
    status?: string
    enabled?: boolean
    page?: number
    page_size?: number
  } = {}): Promise<{
    tasks: ScheduledTask[]
    total: number
    page: number
    page_size: number
  }> => {
    return request('/task-manager/list', {
      method: 'GET',
      params
    })
  },

  createTask: async (params: CreateTaskParams): Promise<ScheduledTask> => {
    return request('/task-manager/create', {
      method: 'POST',
      data: params
    })
  },

  updateTask: async (taskId: string, params: Partial<CreateTaskParams>): Promise<ScheduledTask> => {
    return request(`/task-manager/task/${taskId}`, {
      method: 'PUT',
      data: params
    })
  },

  deleteTask: async (taskId: string): Promise<void> => {
    return request(`/task-manager/task/${taskId}`, {
      method: 'DELETE'
    })
  },

  toggleTask: async (taskId: string, enabled: boolean): Promise<void> => {
    return request(`/task-manager/task/${taskId}/toggle`, {
      method: 'POST',
      data: { enabled }
    })
  },

  runTaskNow: async (taskId: string): Promise<{ execution_id: string }> => {
    return request(`/task-manager/task/${taskId}/run`, {
      method: 'POST'
    })
  },

  getExecutionLogs: async (params: {
    task_id?: string
    status?: string
    start_date?: string
    end_date?: string
    page?: number
    page_size?: number
  } = {}): Promise<{
    logs: TaskExecutionLog[]
    total: number
    page: number
    page_size: number
  }> => {
    return request('/task-manager/logs', {
      method: 'GET',
      params
    })
  },

  getLogDetail: async (logId: string): Promise<TaskExecutionLog> => {
    return request(`/task-manager/logs/${logId}`, {
      method: 'GET'
    })
  },

  getStatistics: async (): Promise<TaskStatistics> => {
    return request('/task-manager/statistics', {
      method: 'GET'
    })
  },

  setupTaxReminder: async (params: {
    tax_type: string
    due_date: string
  }): Promise<ScheduledTask> => {
    return request('/task-manager/setup/tax-reminder', {
      method: 'POST',
      data: params
    })
  },

  setupPeriodicReport: async (params: {
    report_type: string
    frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly'
  }): Promise<ScheduledTask> => {
    return request('/task-manager/setup/periodic-report', {
      method: 'POST',
      data: params
    })
  },

  setupPolicyUpdate: async (params: {
    policy_id: string
    frequency: 'daily' | 'weekly' | 'monthly'
  }): Promise<ScheduledTask> => {
    return request('/task-manager/setup/policy-update', {
      method: 'POST',
      data: params
    })
  },

  setupAnomalyCheck: async (params: {
    frequency: 'hourly' | 'daily' | 'weekly'
  }): Promise<ScheduledTask> => {
    return request('/task-manager/setup/anomaly-check', {
      method: 'POST',
      data: params
    })
  }
}
