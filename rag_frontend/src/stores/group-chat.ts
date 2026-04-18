import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { groupChatApi, type ChatGroup, type GroupMessage, type GroupMember, type GroupInvitation, type SentInvitation, type Notification, type WebSocketMessage } from '@/api/group-chat'
import { getUserIdFromToken } from '@/utils/request'

const HEARTBEAT_INTERVAL = 30000
const MAX_RECONNECT_DELAY = 30000
const BASE_RECONNECT_DELAY = 1000
const MAX_RECONNECT_ATTEMPTS = 5

interface QueuedMessage {
  groupId: string
  content: string
  content_type: 'text' | 'image' | 'file'
  timestamp: number
}

export const useGroupChatStore = defineStore('groupChat', () => {
  const groups = ref<ChatGroup[]>([])
  const currentGroup = ref<ChatGroup | null>(null)
  const messages = ref<Map<string, GroupMessage[]>>(new Map())
  const members = ref<Map<string, GroupMember[]>>(new Map())
  const onlineMembers = ref<Set<string>>(new Set())
  const invitations = ref<GroupInvitation[]>([])
  const notifications = ref<Notification[]>([])
  const unreadCount = ref(0)
  const readReceipts = ref<Map<string, Set<string>>>(new Map())

  const processedMessageIds = new Set<string>()

  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let notificationPollTimer: ReturnType<typeof setInterval> | null = null
  let reconnectAttempts = 0
  let notificationErrorCount = 0
  let currentGroupId: string | null = null
  let currentRequestId: number = 0
  const messageQueue = ref<QueuedMessage[]>([])
  const connectionStatus = ref<'connected' | 'disconnected' | 'error'>('disconnected')

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

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      if (ws.value && ws.value.readyState === WebSocket.OPEN) {
        ws.value.send(JSON.stringify({ event: 'pong' }))
      }
    }, HEARTBEAT_INTERVAL)
  }

  function stopHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function startNotificationPoll() {
    stopNotificationPoll()
    notificationPollTimer = setInterval(() => {
      fetchNotifications()
    }, 10000)
  }

  function stopNotificationPoll() {
    if (notificationPollTimer) {
      clearInterval(notificationPollTimer)
      notificationPollTimer = null
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.log('Max reconnect attempts reached')
      error.value = '连接失败，请刷新页面重试'
      return
    }

    const delay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts),
      MAX_RECONNECT_DELAY
    )

    console.log(`Scheduling reconnect in ${delay}ms (attempt ${reconnectAttempts + 1})`)

    reconnectTimer = setTimeout(() => {
      reconnectAttempts++
      if (currentGroupId) {
        connectWebSocket(currentGroupId)
      }
    }, delay)
  }

  async function flushMessageQueue() {
    if (messageQueue.value.length === 0) return

    const queue = [...messageQueue.value]
    messageQueue.value = []

    await Promise.all(queue.map(async (msg) => {
      try {
        await groupChatApi.sendMessage(msg.groupId, {
          content: msg.content,
          content_type: msg.content_type
        })
      } catch (e) {
        console.error('Failed to send queued message:', e)
        messageQueue.value.push(msg)
      }
    }))
  }

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
    const requestId = ++currentRequestId

    try {
      isLoading.value = true
      error.value = null
      currentGroupId = groupId

      if (requestId !== currentRequestId) return

      const fetchedGroup = await groupChatApi.getGroup(groupId)
      if (requestId !== currentRequestId) return
      currentGroup.value = fetchedGroup
      console.log('selectGroup: group loaded', currentGroup.value)

      if (requestId !== currentRequestId) return

      if (!messages.value.has(groupId)) {
        console.log('selectGroup: loading messages from API')
        const groupMessages = await groupChatApi.getGroupMessages(groupId)
        if (requestId !== currentRequestId) return
        console.log('selectGroup: messages loaded', groupMessages.length)
        if (groupMessages.length > 0) {
          console.log('[DEBUG] First message data:', JSON.stringify(groupMessages[0], null, 2))
        }
        messages.value.set(groupId, groupMessages)
      } else {
        console.log('selectGroup: using cached messages, forcing reload')
        const groupMessages = await groupChatApi.getGroupMessages(groupId)
        if (requestId !== currentRequestId) return
        if (groupMessages.length > 0) {
          console.log('[DEBUG] First message data (reload):', JSON.stringify(groupMessages[0], null, 2))
          console.log('[DEBUG] currentUserId from token:', getUserIdFromToken())
          console.log('[DEBUG] sender_id:', groupMessages[0].sender_id)
          console.log('[DEBUG] isOwnMessage:', String(groupMessages[0].sender_id) === String(getUserIdFromToken()))
        }
        messages.value.set(groupId, groupMessages)
        console.log('selectGroup: using cached messages', messages.value.get(groupId)?.length)
      }

      if (requestId !== currentRequestId) return

      if (!members.value.has(groupId)) {
        const groupMembers = await groupChatApi.getGroupMembers(groupId)
        if (requestId !== currentRequestId) return
        members.value.set(groupId, groupMembers)
        
        const onlineFromApi = groupMembers
          .filter(m => m.is_online)
          .map(m => m.user_id)
        if (onlineFromApi.length > 0) {
          onlineMembers.value = new Set(onlineFromApi)
          console.log('[DEBUG] Initialized online members from API:', onlineFromApi)
        }
      }

      connectWebSocket(groupId)
    } catch (e: any) {
      if (requestId !== currentRequestId) return
      error.value = e.message || '加载群组失败'
      console.error('Failed to select group:', e)
    } finally {
      if (requestId === currentRequestId) {
        isLoading.value = false
      }
    }
  }

  async function loadMessages(groupId: string, before?: string) {
    try {
      const olderMessages = await groupChatApi.getGroupMessages(groupId, { limit: 50, before })
      const existing = messages.value.get(groupId) || []
      messages.value.set(groupId, [...olderMessages, ...existing])
      return olderMessages
    } catch (e) {
      console.error('Failed to load messages:', e)
      return []
    }
  }

  async function sendMessage(content: string, contentType: 'text' | 'image' | 'file' = 'text') {
    if (!currentGroup.value) {
      console.log('sendMessage: no current group')
      return null
    }

    const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    const groupId = currentGroup.value.id
    const senderId = getUserIdFromToken() || 'unknown'
    const tempMessage: GroupMessage = {
      id: tempId,
      group_id: groupId,
      sender_id: senderId,
      sender_name: localStorage.getItem('rag_user_name') || '我',
      content,
      content_type: contentType,
      tenant_id: '',
      created_at: new Date().toISOString(),
      status: 'sending'
    }

    const existingMessages = messages.value.get(groupId) || []
    messages.value.set(groupId, [...existingMessages, tempMessage])

    try {
      error.value = null
      const sentMessage = await groupChatApi.sendMessage(groupId, {
        content,
        content_type: contentType
      })

      const msgs = messages.value.get(groupId) || []
      messages.value.set(groupId, msgs.map(m => m.id === tempId ? { ...sentMessage, status: 'sent' } : m))

      return sentMessage
    } catch (e: any) {
      console.error('sendMessage error:', e)

      const isNetworkError = !e.response && (e.name === 'TypeError' || e.message?.includes('fetch') || e.code === 'ERR_NETWORK' || e.code === 'ECONNRESET')

      if (isNetworkError) {
        messageQueue.value.push({
          groupId,
          content,
          content_type: contentType,
          timestamp: Date.now()
        })

        const msgs = messages.value.get(groupId) || []
        messages.value.set(groupId, msgs.map(m => m.id === tempId ? { ...m, status: 'queued' } : m))
      } else {
        const msgs = messages.value.get(groupId) || []
        messages.value.set(groupId, msgs.map(m => m.id === tempId ? { ...m, status: 'failed' } : m))
        error.value = e.message || '发送消息失败'
      }

      throw e
    }
  }

  function sendTypingIndicator() {
    if (ws.value && ws.value.readyState === WebSocket.OPEN && currentGroup.value) {
      ws.value.send(JSON.stringify({
        event: 'typing',
        data: { group_id: currentGroup.value.id }
      }))
    }
  }

  function markMessagesRead(messageIds: string[]) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN && currentGroup.value) {
      ws.value.send(JSON.stringify({
        event: 'mark_read',
        data: { message_ids: messageIds }
      }))

      messageIds.forEach(id => {
        const receipt = readReceipts.value.get(id) || new Set()
        receipt.add('me')
        readReceipts.value.set(id, receipt)
      })
    }
  }

  async function inviteMembers(inviteeIds: string[], message?: string) {
    if (!currentGroup.value) return []

    try {
      error.value = null
      const newInvitations = await groupChatApi.inviteMembers(currentGroup.value.id, {
        user_ids: inviteeIds,
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
        currentGroupId = null
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

  const sentInvitations = ref<SentInvitation[]>([])

  async function fetchSentInvitations() {
    try {
      sentInvitations.value = await groupChatApi.getSentInvitations()
    } catch (e) {
      console.error('Failed to fetch sent invitations:', e)
    }
  }

  async function acceptInvitation(invitationId: string) {
    try {
      const result = await groupChatApi.acceptInvitation(invitationId)
      console.log('acceptInvitation result:', result)
      invitations.value = invitations.value.filter(i => i.id !== invitationId)
      await fetchGroups()
      
      if (result?.group_id) {
        console.log('Auto selecting group after accept invitation:', result.group_id)
        await selectGroup(result.group_id)
      }
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

  async function resendInvitationNotification(invitationId: string) {
    try {
      await groupChatApi.resendInvitationNotification(invitationId)
    } catch (e: any) {
      error.value = e.message || '重新发送邀请失败'
      throw e
    }
  }

  async function fetchNotifications() {
    try {
      notifications.value = await groupChatApi.getNotifications({ unread_only: false })
      unreadCount.value = notifications.value.filter(n => !n.is_read).length
      notificationErrorCount.value = 0
    } catch (e) {
      notificationErrorCount.value++

      if (notificationErrorCount.value >= 3) {
        console.warn('Notification fetch failed 3 times, pausing polling...')
        stopNotificationPoll()
      } else {
        console.error(`Failed to fetch notifications (attempt ${notificationErrorCount.value}):`, e)
      }
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
      throw e
    }
  }

  function connectWebSocket(groupId: string) {
    disconnectWebSocket()

    ws.value = groupChatApi.createWebSocketConnection(groupId)

    ws.value.onopen = () => {
      isConnected.value = true
      connectionStatus.value = 'connected'
      reconnectAttempts = 0
      console.log('WebSocket connected')
      startHeartbeat()
      flushMessageQueue()
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
      connectionStatus.value = 'error'
    }

    ws.value.onclose = (event) => {
      isConnected.value = false
      connectionStatus.value = 'disconnected'
      stopHeartbeat()
      console.log(`WebSocket disconnected: ${event.code} - ${event.reason}`)

      if (currentGroupId === groupId && !event.wasClean) {
        scheduleReconnect()
      }
    }
  }

  function handleWebSocketMessage(msg: WebSocketMessage) {
    const msgType = msg.type || (msg as any).event
    
    switch (msgType) {
      case 'new_message':
      case 'group_message':
        if (currentGroup.value && msg.data) {
          if (processedMessageIds.has(msg.data.id)) {
            break
          }
          const existingMessages = messages.value.get(currentGroup.value.id) || []
          const exists = existingMessages.some(m => m.id === msg.data.id)
          if (!exists) {
            messages.value.set(currentGroup.value.id, [...existingMessages, msg.data])
            processedMessageIds.add(msg.data.id)
          }
        }
        break

      case 'member_joined':
      case 'member_left':
      case 'member_removed':
        if (currentGroup.value) {
          const groupMembers = members.value.get(currentGroup.value.id) || []
          if (msgType === 'member_joined' && msg.data) {
            const exists = groupMembers.some(m => m.id === msg.data.id)
            if (!exists) {
              members.value.set(currentGroup.value.id, [...groupMembers, msg.data])
            }
          } else if (msgType !== 'member_joined' && msg.sender_id) {
            const exists = groupMembers.some(m => m.user_id === msg.sender_id)
            if (exists) {
              members.value.set(currentGroup.value.id, groupMembers.filter(m => m.user_id !== msg.sender_id))
            }
          }
        }
        break

      case 'member_offline':
        if (msg.data?.user_id) {
          console.log('[DEBUG] member_offline event:', msg.data.user_id)
          onlineMembers.value.delete(msg.data.user_id)
          console.log('[DEBUG] onlineMembers after offline:', Array.from(onlineMembers.value))
        }
        break

      case 'member_online':
        if (msg.data?.user_id) {
          console.log('[DEBUG] member_online event:', msg.data.user_id)
          onlineMembers.value.add(msg.data.user_id)
          console.log('[DEBUG] onlineMembers after online:', Array.from(onlineMembers.value))
        }
        break

      case 'online_status':
        if (msg.data?.online_users) {
          onlineMembers.value = new Set(msg.data.online_users)
        } else if (msg.data?.online) {
          onlineMembers.value = new Set(msg.data.online)
        }
        break

      case 'members_sync':
        if (msg.data) {
          if (msg.data.members && currentGroup.value) {
            members.value.set(currentGroup.value.id, msg.data.members)
            console.log('[DEBUG] members_sync - members count:', msg.data.members.length)
          }
          if (msg.data.online) {
            onlineMembers.value = new Set(msg.data.online)
            console.log('[DEBUG] members_sync - online members:', msg.data.online)
          }
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

      case 'messages_read':
        if (msg.data?.message_ids && msg.data?.user_id) {
          msg.data.message_ids.forEach((id: string) => {
            const receipt = readReceipts.value.get(id) || new Set()
            receipt.add(msg.data.user_id)
            readReceipts.value.set(id, receipt)
          })
        }
        break

      case 'user_typing':
        break
    }
  }

  function disconnectWebSocket() {
    stopHeartbeat()
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws.value) {
      ws.value.close(1000, 'User disconnected')
      ws.value = null
    }
    isConnected.value = false
    reconnectAttempts = 0
  }

  function clearCurrentGroup() {
    currentGroup.value = null
    currentGroupId = null
    processedMessageIds.clear()
    disconnectWebSocket()
  }

  function isMessageRead(messageId: string, userId: string): boolean {
    const receipt = readReceipts.value.get(messageId)
    return receipt ? receipt.has(userId) : false
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
    readReceipts,
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
    sendTypingIndicator,
    markMessagesRead,
    isMessageRead,
    inviteMembers,
    leaveGroup,
    fetchPendingInvitations,
    sentInvitations,
    fetchSentInvitations,
    acceptInvitation,
    declineInvitation,
    resendInvitationNotification,
    fetchNotifications,
    markNotificationRead,
    markAllNotificationsRead,
    deleteNotification,
    deleteNotificationsBatch,
    clearAllNotifications,
    startNotificationPoll,
    stopNotificationPoll,
    connectWebSocket,
    disconnectWebSocket,
    clearCurrentGroup
  }
})
