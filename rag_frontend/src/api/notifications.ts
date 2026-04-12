import { request } from '@/utils/request'

export interface Notification {
  id: string
  user_id: string
  title: string
  message: string
  notification_type: 'info' | 'warning' | 'error' | 'success'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  is_read: boolean
  is_archived: boolean
  metadata?: Record<string, any>
  source: 'system' | 'task' | 'policy' | 'financial' | 'contract' | 'manual'
  action_url?: string
  created_at: string
  read_at?: string
}

export interface NotificationPreferences {
  in_app: boolean
  email: boolean
  sms: boolean
  webhook: boolean
  email_address?: string
  phone_number?: string
  webhook_url?: string
  quiet_hours_start?: string
  quiet_hours_end?: string
  notification_types: {
    info: boolean
    warning: boolean
    error: boolean
    success: boolean
  }
  priority_threshold: 'low' | 'medium' | 'high' | 'urgent'
}

export interface CreateNotificationParams {
  user_id: string
  title: string
  message: string
  notification_type?: 'info' | 'warning' | 'error' | 'success'
  priority?: 'low' | 'medium' | 'high' | 'urgent'
  metadata?: Record<string, any>
  email?: string
  phone?: string
  webhook_url?: string
}

export interface NotificationFilter {
  is_read?: boolean
  notification_type?: string
  priority?: string
  source?: string
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}

export interface NotificationStats {
  total: number
  unread: number
  today: number
  by_type: Record<string, number>
  by_priority: Record<string, number>
}

export const notificationsApi = {
  listNotifications: async (params: NotificationFilter = {}): Promise<{
    notifications: Notification[]
    total: number
    page: number
    page_size: number
  }> => {
    return request('/notifications/list', {
      method: 'GET',
      params
    })
  },

  getUnreadCount: async (): Promise<{ count: number }> => {
    return request('/notifications/unread-count', {
      method: 'GET'
    })
  },

  markAsRead: async (notificationId: string): Promise<void> => {
    return request(`/notifications/${notificationId}/read`, {
      method: 'POST'
    })
  },

  markAllAsRead: async (): Promise<void> => {
    return request('/notifications/mark-all-read', {
      method: 'POST'
    })
  },

  archiveNotification: async (notificationId: string): Promise<void> => {
    return request(`/notifications/${notificationId}/archive`, {
      method: 'POST'
    })
  },

  deleteNotification: async (notificationId: string): Promise<void> => {
    return request(`/notifications/${notificationId}`, {
      method: 'DELETE'
    })
  },

  sendNotification: async (params: CreateNotificationParams): Promise<Notification> => {
    return request('/notifications/send', {
      method: 'POST',
      data: params
    })
  },

  getPreferences: async (): Promise<NotificationPreferences> => {
    return request('/notifications/preferences', {
      method: 'GET'
    })
  },

  updatePreferences: async (preferences: Partial<NotificationPreferences>): Promise<void> => {
    return request('/notifications/preferences', {
      method: 'PUT',
      data: preferences
    })
  },

  getStatistics: async (): Promise<NotificationStats> => {
    return request('/notifications/statistics', {
      method: 'GET'
    })
  },

  getNotificationsBySource: async (source: string, params: { page?: number; page_size?: number } = {}): Promise<{
    notifications: Notification[]
    total: number
  }> => {
    return request(`/notifications/source/${source}`, {
      method: 'GET',
      params
    })
  },

  testNotification: async (channel: 'email' | 'sms' | 'webhook'): Promise<{ success: boolean; message: string }> => {
    return request('/notifications/test', {
      method: 'POST',
      data: { channel }
    })
  }
}
