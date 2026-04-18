import { ref, computed, readonly } from 'vue'
import { notificationsApi, type Notification as GeneralNotification } from '@/api/notifications'
import { groupChatApi } from '@/api/group-chat'
import { policyApi } from '@/api/policy'
import { ElMessage } from 'element-plus'

export type NotificationCategory = 'all' | 'system' | 'policy' | 'task' | 'chat'

export interface UnifiedNotification {
  id: string
  category: NotificationCategory
  title: string
  message: string
  icon: string
  iconColor: string
  bgColor: string
  isRead: boolean
  priority: 'low' | 'medium' | 'high' | 'urgent'
  actionUrl?: string
  metadata?: Record<string, any>
  createdAt: string
  sourceId?: string
}

export interface UnifiedStats {
  total: number
  unread: number
  today: number
  byCategory: Record<NotificationCategory, number>
  byPriority: Record<string, number>
}

const notifications = ref<UnifiedNotification[]>([])
const stats = ref<UnifiedStats>({
  total: 0,
  unread: 0,
  today: 0,
  byCategory: { all: 0, system: 0, policy: 0, task: 0, chat: 0 },
  byPriority: { low: 0, medium: 0, high: 0, urgent: 0 }
})
const isLoading = ref(false)
const isInitialized = ref(false)

export function useUnifiedNotifications() {
  const unreadCount = computed(() => {
    return notifications.value.filter(n => !n.isRead).length
  })

  async function loadNotifications(category: NotificationCategory = 'all', force = false) {
    if (isLoading.value) return
    if (isInitialized.value && !force) return

    isLoading.value = true
    try {
      const [generalRes, chatRes, policyRes] = await Promise.allSettled([
        category === 'all' || category === 'system' || category === 'task'
          ? notificationsApi.listNotifications({ page_size: 100 })
          : Promise.resolve(null),
        category === 'all' || category === 'chat'
          ? groupChatApi.getNotifications()
          : Promise.resolve([]),
        category === 'all' || category === 'policy'
          ? policyApi.getNotifications(undefined, undefined, 50)
          : Promise.resolve({ notifications: [] })
      ])

      const unified: UnifiedNotification[] = []

      if (generalRes.status === 'rejected') {
        throw generalRes.reason
      }
      if (chatRes.status === 'rejected') {
        throw chatRes.reason
      }
      if (policyRes.status === 'rejected') {
        throw policyRes.reason
      }

      if (generalRes.status === 'fulfilled' && generalRes.value) {
        const general = generalRes.value.notifications || []
        unified.push(...general.map(n => transformGeneralNotification(n)))
      }

      if (chatRes.status === 'fulfilled' && chatRes.value) {
        const chats = Array.isArray(chatRes.value) ? chatRes.value : []
        unified.push(...chats.map(n => transformChatNotification(n)))
      }

      if (policyRes.status === 'fulfilled' && policyRes.value) {
        const policies = policyRes.value.notifications || []
        unified.push(...policies.map(n => transformPolicyNotification(n)))
      }

      unified.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())

      notifications.value = unified
      calculateStats()
      isInitialized.value = true
    } catch (error: any) {
      console.error('Failed to load notifications:', error)
      if (error?.response?.status === 401 || error?.response?.status === 403) {
        throw error
      }
      ElMessage.error('加载通知失败')
    } finally {
      isLoading.value = false
    }
  }

  function transformGeneralNotification(n: GeneralNotification): UnifiedNotification {
    const priorityConfig = getPriorityConfig(n.priority)
    return {
      id: `general-${n.id}`,
      category: n.source === 'task' ? 'task' : 'system',
      title: n.title,
      message: n.message,
      icon: getNotificationIcon(n.notification_type),
      iconColor: priorityConfig.iconColor,
      bgColor: priorityConfig.bgColor,
      isRead: n.is_read,
      priority: n.priority,
      actionUrl: n.action_url,
      metadata: n.metadata,
      createdAt: n.created_at,
      sourceId: n.id
    }
  }

  function transformChatNotification(n: any): UnifiedNotification {
    const iconMap: Record<string, { icon: string; iconColor: string; bgColor: string }> = {
      invitation: { icon: 'UserPlus', iconColor: 'text-blue-600', bgColor: 'bg-blue-100' },
      message: { icon: 'MessageSquare', iconColor: 'text-green-600', bgColor: 'bg-green-100' },
      member_joined: { icon: 'UserCheck', iconColor: 'text-emerald-600', bgColor: 'bg-emerald-100' },
      member_left: { icon: 'UserMinus', iconColor: 'text-gray-600', bgColor: 'bg-gray-100' }
    }
    const config = iconMap[n.type] || iconMap.message

    return {
      id: `chat-${n.id}`,
      category: 'chat',
      title: n.title || getChatNotificationTitle(n),
      message: n.message || n.content || '',
      icon: config.icon,
      iconColor: config.iconColor,
      bgColor: config.bgColor,
      isRead: n.is_read || false,
      priority: 'medium',
      metadata: n,
      createdAt: n.created_at || n.timestamp,
      sourceId: n.id
    }
  }

  function transformPolicyNotification(n: any): UnifiedNotification {
    const statusConfig: Record<string, { iconColor: string; bgColor: string }> = {
      pending: { iconColor: 'text-amber-600', bgColor: 'bg-amber-100' },
      sent: { iconColor: 'text-blue-600', bgColor: 'bg-blue-100' },
      acknowledged: { iconColor: 'text-emerald-600', bgColor: 'bg-emerald-100' },
      dismissed: { iconColor: 'text-gray-600', bgColor: 'bg-gray-100' }
    }
    const config = statusConfig[n.status] || statusConfig.pending

    return {
      id: `policy-${n.id}`,
      category: 'policy',
      title: n.title || '政策更新通知',
      message: n.message || n.content || '',
      icon: 'FileText',
      iconColor: config.iconColor,
      bgColor: config.bgColor,
      isRead: n.status === 'acknowledged' || n.status === 'dismissed',
      priority: 'high',
      actionUrl: n.policy_id ? `/policy/${n.policy_id}` : undefined,
      metadata: n,
      createdAt: n.created_at,
      sourceId: n.id
    }
  }

  function getChatNotificationTitle(n: any): string {
    const titles: Record<string, string> = {
      invitation: '收到群聊邀请',
      message: '收到新消息',
      member_joined: '新成员加入',
      member_left: '成员离开'
    }
    return titles[n.type] || '群聊通知'
  }

  function getNotificationIcon(type: string): string {
    const icons: Record<string, string> = {
      info: 'Info',
      warning: 'Warning',
      error: 'XCircle',
      success: 'CheckCircle'
    }
    return icons[type] || 'Bell'
  }

  function getPriorityConfig(priority: string): { iconColor: string; bgColor: string } {
    const configs: Record<string, { iconColor: string; bgColor: string }> = {
      urgent: { iconColor: 'text-red-600', bgColor: 'bg-red-100' },
      high: { iconColor: 'text-orange-600', bgColor: 'bg-orange-100' },
      medium: { iconColor: 'text-blue-600', bgColor: 'bg-blue-100' },
      low: { iconColor: 'text-gray-600', bgColor: 'bg-gray-100' }
    }
    return configs[priority] || configs.medium
  }

  function calculateStats() {
    const now = new Date()
    const today = now.toDateString()

    stats.value = {
      total: notifications.value.length,
      unread: notifications.value.filter(n => !n.isRead).length,
      today: notifications.value.filter(n => new Date(n.createdAt).toDateString() === today).length,
      byCategory: {
        all: notifications.value.length,
        system: notifications.value.filter(n => n.category === 'system').length,
        policy: notifications.value.filter(n => n.category === 'policy').length,
        task: notifications.value.filter(n => n.category === 'task').length,
        chat: notifications.value.filter(n => n.category === 'chat').length
      },
      byPriority: {
        urgent: notifications.value.filter(n => n.priority === 'urgent').length,
        high: notifications.value.filter(n => n.priority === 'high').length,
        medium: notifications.value.filter(n => n.priority === 'medium').length,
        low: notifications.value.filter(n => n.priority === 'low').length
      }
    }
  }

  async function markAsRead(notificationId: string) {
    const notification = notifications.value.find(n => n.id === notificationId)
    if (!notification) return

    try {
      const [prefix, id] = notificationId.split('-')
      if (prefix === 'general' && id) {
        await notificationsApi.markAsRead(id)
      } else if (prefix === 'chat' && id) {
        await groupChatApi.markNotificationRead(id)
      } else if (prefix === 'policy' && id) {
        await policyApi.acknowledgeNotification(id)
      }
      notification.isRead = true
      calculateStats()
    } catch (error) {
      console.error('Failed to mark as read:', error)
    }
  }

  async function markAllAsRead(category?: NotificationCategory) {
    try {
      if (!category || category === 'all' || category === 'system' || category === 'task') {
        await notificationsApi.markAllAsRead()
      }

      const unreadNotifications = notifications.value.filter(n =>
        !category || category === 'all' || n.category === category
      )

      for (const n of unreadNotifications) {
        if (!n.isRead) {
          await markAsRead(n.id)
        }
      }

      notifications.value.forEach(n => {
        if (!category || category === 'all' || n.category === category) {
          n.isRead = true
        }
      })
      calculateStats()
      ElMessage.success('已全部标为已读')
    } catch (error) {
      console.error('Failed to mark all as read:', error)
      ElMessage.error('操作失败')
    }
  }

  async function deleteNotification(notificationId: string) {
    const notification = notifications.value.find(n => n.id === notificationId)
    if (!notification) return

    try {
      const [prefix, id] = notificationId.split('-')
      if (prefix === 'general' && id) {
        await notificationsApi.deleteNotification(id)
      } else if (prefix === 'chat' && id) {
        await groupChatApi.deleteNotification(id)
      } else if (prefix === 'policy' && id) {
        await policyApi.dismissNotification(id, '用户删除')
      }
      notifications.value = notifications.value.filter(n => n.id !== notificationId)
      calculateStats()
      ElMessage.success('删除成功')
    } catch (error) {
      console.error('Failed to delete notification:', error)
      ElMessage.error('删除失败')
    }
  }

  function filterByCategory(category: NotificationCategory): UnifiedNotification[] {
    if (category === 'all') {
      return notifications.value
    }
    return notifications.value.filter(n => n.category === category)
  }

  function filterUnread(): UnifiedNotification[] {
    return notifications.value.filter(n => !n.isRead)
  }

  function refresh() {
    isInitialized.value = false
    loadNotifications('all', true)
  }

  async function acceptInvitation(invitationId: string) {
    try {
      await groupChatApi.acceptInvitation(invitationId)
      notifications.value = notifications.value.filter(n => n.id !== `chat-${invitationId}`)
      calculateStats()
      ElMessage.success('已接受邀请')
      return true
    } catch (error) {
      console.error('Failed to accept invitation:', error)
      ElMessage.error('接受邀请失败')
      return false
    }
  }

  async function declineInvitation(invitationId: string) {
    try {
      await groupChatApi.declineInvitation(invitationId)
      notifications.value = notifications.value.filter(n => n.id !== `chat-${invitationId}`)
      calculateStats()
      ElMessage.success('已拒绝邀请')
      return true
    } catch (error) {
      console.error('Failed to decline invitation:', error)
      ElMessage.error('拒绝邀请失败')
      return false
    }
  }

  return {
    notifications: readonly(notifications),
    stats: readonly(stats),
    isLoading: readonly(isLoading),
    unreadCount,
    loadNotifications,
    markAsRead,
    markAllAsRead,
    deleteNotification,
    acceptInvitation,
    declineInvitation,
    filterByCategory,
    filterUnread,
    refresh
  }
}
