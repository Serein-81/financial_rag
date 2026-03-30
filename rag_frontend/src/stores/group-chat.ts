import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { groupChatApi, type ChatGroup, type GroupMessage, type GroupMember, type GroupInvitation, type Notification, type WebSocketMessage } from '@/api/group-chat'

export const useGroupChatStore = defineStore('groupChat', () => {
  const groups = ref<ChatGroup[]>([])
  const currentGroup = ref<ChatGroup | null>(null)
  const messages = ref<Map<string, GroupMessage[]>>(new Map())
  const members = ref<Map<string, GroupMember[]>>(new Map())
  const onlineMembers = ref<Set<string>>(new Set())
  const invitations = ref<GroupInvitation[]>([])
  const notifications = ref<Notification[]>([])
  const unreadCount = ref(0)
  
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const currentMessages = computed(() => {
    if (!currentGroup.value) return []
    return messages.value.get(currentGroup.value.id) || []
  })

  const currentMembers = computed(() => {
    if (!currentGroup.value) return []
    return members.value.get(currentGroup.value.id) || []
  })

  const pendingInvitations = computed(() => {
    return invitations.value.filter(inv => inv.status === 'pending')
  })

  const unreadNotifications = computed(() => {
    return notifications.value.filter(n => !n.is_read)
  })

  async function fetchGroups() {
    try {
      isLoading.value = true
      error.value = null
      groups.value = await groupChatApi.getGroups()
    } catch (e: any) {
      error.value = e.message || '获取群组列表失败'
      console.error('Failed to fetch groups:', e)
    } finally {
      isLoading.value = false
    }
  }

  async function createGroup(name: string, description?: string) {
    try {
      isLoading.value = true
      error.value = null
      const newGroup = await groupChatApi.createGroup({ name, description })
      groups.value.unshift(newGroup)
      return newGroup
    } catch (e: any) {
      error.value = e.message || '创建群组失败'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function selectGroup(groupId: string) {
    try {
      isLoading.value = true
      error.value = null
      currentGroup.value = await groupChatApi.getGroup(groupId)
      
      if (!messages.value.has(groupId)) {
        const groupMessages = await groupChatApi.getGroupMessages(groupId)
        messages.value.set(groupId, groupMessages.reverse())
      }
      
      if (!members.value.has(groupId)) {
        const groupMembers = await groupChatApi.getGroupMembers(groupId)
        members.value.set(groupId, groupMembers)
      }

      connectWebSocket(groupId)
    } catch (e: any) {
      error.value = e.message || '加载群组失败'
      console.error('Failed to select group:', e)
    } finally {
      isLoading.value = false
    }
  }

  async function loadMessages(groupId: string, before?: string) {
    try {
      const olderMessages = await groupChatApi.getGroupMessages(groupId, { limit: 50, before })
      const existing = messages.value.get(groupId) || []
      messages.value.set(groupId, [...olderMessages.reverse(), ...existing])
      return olderMessages
    } catch (e) {
      console.error('Failed to load messages:', e)
      return []
    }
  }

  async function sendMessage(content: string, contentType: 'text' | 'image' | 'file' = 'text') {
    if (!currentGroup.value) return null
    
    try {
      error.value = null
      const message = await groupChatApi.sendMessage(currentGroup.value.id, {
        content,
        content_type: contentType
      })
      
      const groupMessages = messages.value.get(currentGroup.value.id) || []
      groupMessages.push(message)
      messages.value.set(currentGroup.value.id, groupMessages)
      
      return message
    } catch (e: any) {
      error.value = e.message || '发送消息失败'
      throw e
    }
  }

  async function inviteMembers(inviteeIds: string[], message?: string) {
    if (!currentGroup.value) return []
    
    try {
      error.value = null
      const newInvitations = await groupChatApi.inviteMembers(currentGroup.value.id, {
        invitee_ids: inviteeIds,
        message
      })
      return newInvitations
    } catch (e: any) {
      error.value = e.message || '邀请成员失败'
      throw e
    }
  }

  async function leaveGroup(groupId: string) {
    try {
      error.value = null
      await groupChatApi.leaveGroup(groupId)
      
      groups.value = groups.value.filter(g => g.id !== groupId)
      
      if (currentGroup.value?.id === groupId) {
        currentGroup.value = null
        disconnectWebSocket()
      }
    } catch (e: any) {
      error.value = e.message || '退出群组失败'
      throw e
    }
  }

  async function fetchPendingInvitations() {
    try {
      invitations.value = await groupChatApi.getPendingInvitations()
    } catch (e) {
      console.error('Failed to fetch invitations:', e)
    }
  }

  async function acceptInvitation(invitationId: string) {
    try {
      await groupChatApi.acceptInvitation(invitationId)
      invitations.value = invitations.value.filter(i => i.id !== invitationId)
      await fetchGroups()
    } catch (e: any) {
      error.value = e.message || '接受邀请失败'
      throw e
    }
  }

  async function declineInvitation(invitationId: string) {
    try {
      await groupChatApi.declineInvitation(invitationId)
      invitations.value = invitations.value.filter(i => i.id !== invitationId)
    } catch (e: any) {
      error.value = e.message || '拒绝邀请失败'
      throw e
    }
  }

  async function fetchNotifications() {
    try {
      notifications.value = await groupChatApi.getNotifications({ unread_only: false })
      unreadCount.value = notifications.value.filter(n => !n.is_read).length
    } catch (e) {
      console.error('Failed to fetch notifications:', e)
    }
  }

  async function markNotificationRead(notificationId: string) {
    try {
      await groupChatApi.markNotificationRead(notificationId)
      const notification = notifications.value.find(n => n.id === notificationId)
      if (notification) {
        notification.is_read = true
        unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
    } catch (e) {
      console.error('Failed to mark notification as read:', e)
    }
  }

  async function markAllNotificationsRead() {
    try {
      await groupChatApi.markAllNotificationsRead()
      notifications.value.forEach(n => n.is_read = true)
      unreadCount.value = 0
    } catch (e) {
      console.error('Failed to mark all notifications as read:', e)
    }
  }

  async function deleteNotification(notificationId: string) {
    try {
      await groupChatApi.deleteNotification(notificationId)
      const index = notifications.value.findIndex(n => n.id === notificationId)
      if (index !== -1) {
        const wasUnread = !notifications.value[index].is_read
        notifications.value.splice(index, 1)
        if (wasUnread) {
          unreadCount.value = Math.max(0, unreadCount.value - 1)
        }
      }
    } catch (e) {
      console.error('Failed to delete notification:', e)
    }
  }

  async function deleteNotificationsBatch(notificationIds: string[]) {
    try {
      await groupChatApi.deleteNotificationsBatch(notificationIds)
      const toDelete = new Set(notificationIds)
      notifications.value = notifications.value.filter(n => {
        if (toDelete.has(n.id)) {
          if (!n.is_read) {
            unreadCount.value = Math.max(0, unreadCount.value - 1)
          }
          return false
        }
        return true
      })
    } catch (e) {
      console.error('Failed to delete notifications batch:', e)
    }
  }

  async function clearAllNotifications() {
    try {
      await groupChatApi.clearAllNotifications()
      notifications.value = []
      unreadCount.value = 0
    } catch (e) {
      console.error('Failed to clear all notifications:', e)
    }
  }

  function connectWebSocket(groupId: string) {
    disconnectWebSocket()
    
    ws.value = groupChatApi.createWebSocketConnection(groupId)
    
    ws.value.onopen = () => {
      isConnected.value = true
      console.log('WebSocket connected')
    }
    
    ws.value.onmessage = (event) => {
      try {
        const msg: WebSocketMessage = JSON.parse(event.data)
        handleWebSocketMessage(msg)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }
    
    ws.value.onerror = (error) => {
      console.error('WebSocket error:', error)
      isConnected.value = false
    }
    
    ws.value.onclose = () => {
      isConnected.value = false
      console.log('WebSocket disconnected')
    }
  }

  function handleWebSocketMessage(msg: WebSocketMessage) {
    switch (msg.type) {
      case 'new_message':
        if (currentGroup.value && msg.data) {
          const groupMessages = messages.value.get(currentGroup.value.id) || []
          const exists = groupMessages.some(m => m.id === msg.data.id)
          if (!exists) {
            groupMessages.push(msg.data)
            messages.value.set(currentGroup.value.id, groupMessages)
          }
        }
        break
        
      case 'member_joined':
      case 'member_left':
      case 'member_removed':
        if (currentGroup.value) {
          const groupMembers = members.value.get(currentGroup.value.id) || []
          if (msg.type === 'member_joined' && msg.data) {
            const exists = groupMembers.some(m => m.id === msg.data.id)
            if (!exists) {
              groupMembers.push(msg.data)
            }
          } else if (msg.type !== 'member_joined' && msg.sender_id) {
            const index = groupMembers.findIndex(m => m.user_id === msg.sender_id)
            if (index !== -1) {
              groupMembers.splice(index, 1)
            }
          }
          members.value.set(currentGroup.value.id, groupMembers)
        }
        break
        
      case 'online_status':
        if (msg.data?.online_users) {
          onlineMembers.value = new Set(msg.data.online_users)
        }
        break
        
      case 'notification':
        if (msg.data) {
          notifications.value.unshift(msg.data)
          if (!msg.data.is_read) {
            unreadCount.value++
          }
        }
        break
    }
  }

  function disconnectWebSocket() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
      isConnected.value = false
    }
  }

  function clearCurrentGroup() {
    currentGroup.value = null
    disconnectWebSocket()
  }

  return {
    groups,
    currentGroup,
    messages,
    members,
    onlineMembers,
    invitations,
    notifications,
    unreadCount,
    isConnected,
    isLoading,
    error,
    currentMessages,
    currentMembers,
    pendingInvitations,
    unreadNotifications,
    fetchGroups,
    createGroup,
    selectGroup,
    loadMessages,
    sendMessage,
    inviteMembers,
    leaveGroup,
    fetchPendingInvitations,
    acceptInvitation,
    declineInvitation,
    fetchNotifications,
    markNotificationRead,
    markAllNotificationsRead,
    deleteNotification,
    deleteNotificationsBatch,
    clearAllNotifications,
    connectWebSocket,
    disconnectWebSocket,
    clearCurrentGroup
  }
})
