import { request } from '@/utils/request'

export interface ChatGroup {
  id: string
  tenant_id: string
  name: string
  description?: string
  avatar_url?: string
  status: string
  created_by: string
  created_at: string
  updated_at: string
  member_count?: number
  last_message?: GroupMessage
}

export interface GroupMember {
  id: string
  group_id: string
  user_id: string
  user_name?: string
  avatar_url?: string
  tenant_id: string
  role: 'owner' | 'admin' | 'member'
  status: 'invited' | 'active' | 'left' | 'removed'
  joined_at?: string
  notification_settings?: {
    enabled: boolean
    mentions_only: boolean
  }
}

export interface GroupInvitation {
  id: string
  group_id: string
  group_name?: string
  invitee_id: string
  inviter_id: string
  inviter_name?: string
  tenant_id: string
  status: 'pending' | 'accepted' | 'declined' | 'expired'
  message?: string
  created_at: string
  expires_at?: string
}

export interface GroupMessage {
  id: string
  group_id: string
  sender_id: string
  sender_name?: string
  sender_avatar?: string
  tenant_id: string
  content: string
  content_type: 'text' | 'image' | 'file' | 'system'
  metadata?: Record<string, any>
  created_at: string
  is_deleted?: boolean
}

export interface Notification {
  id: string
  type: 'invitation' | 'message' | 'member_joined' | 'member_left' | 'system'
  title: string
  content: string
  group_id?: string
  group_name?: string
  is_read: boolean
  created_at: string
  data?: Record<string, any>
}

export interface CreateGroupRequest {
  name: string
  description?: string
  avatar_url?: string
}

export interface InviteMembersRequest {
  invitee_ids: string[]
  message?: string
}

export interface SendMessageRequest {
  content: string
  content_type?: 'text' | 'image' | 'file'
}

export const groupChatApi = {
  async getGroups(): Promise<ChatGroup[]> {
    return request.get('/groups/')
  },

  async createGroup(data: CreateGroupRequest): Promise<ChatGroup> {
    return request.post('/groups/', data)
  },

  async getGroup(groupId: string): Promise<ChatGroup> {
    return request.get(`/groups/${groupId}`)
  },

  async updateGroup(groupId: string, data: Partial<CreateGroupRequest>): Promise<ChatGroup> {
    return request.put(`/groups/${groupId}`, data)
  },

  async deleteGroup(groupId: string): Promise<void> {
    return request.delete(`/groups/${groupId}`)
  },

  async getGroupMembers(groupId: string): Promise<GroupMember[]> {
    return request.get(`/groups/${groupId}/members`)
  },

  async inviteMembers(groupId: string, data: InviteMembersRequest): Promise<GroupInvitation[]> {
    return request.post(`/groups/${groupId}/invite`, data)
  },

  async leaveGroup(groupId: string): Promise<void> {
    return request.post(`/groups/${groupId}/leave`)
  },

  async removeMember(groupId: string, userId: string): Promise<void> {
    return request.delete(`/groups/${groupId}/members/${userId}`)
  },

  async updateMemberRole(groupId: string, userId: string, role: 'admin' | 'member'): Promise<GroupMember> {
    return request.put(`/groups/${groupId}/members/${userId}`, { role })
  },

  async getGroupMessages(groupId: string, params?: { limit?: number; before?: string }): Promise<GroupMessage[]> {
    return request.get(`/groups/${groupId}/messages`, { params })
  },

  async sendMessage(groupId: string, data: SendMessageRequest): Promise<GroupMessage> {
    return request.post(`/groups/${groupId}/messages`, data)
  },

  async getPendingInvitations(): Promise<GroupInvitation[]> {
    return request.get('/invitations/pending')
  },

  async acceptInvitation(invitationId: string): Promise<GroupMember> {
    return request.post(`/invitations/${invitationId}/accept`)
  },

  async declineInvitation(invitationId: string): Promise<void> {
    return request.post(`/invitations/${invitationId}/decline`)
  },

  async getNotifications(params?: { limit?: number; unread_only?: boolean }): Promise<Notification[]> {
    return request.get('/notifications/', { params })
  },

  async markNotificationRead(notificationId: string): Promise<void> {
    return request.put(`/notifications/${notificationId}/read`)
  },

  async markAllNotificationsRead(): Promise<void> {
    return request.put('/notifications/read-all')
  },

  async deleteNotification(notificationId: string): Promise<void> {
    return request.delete(`/notifications/${notificationId}`)
  },

  async deleteNotificationsBatch(notificationIds: string[]): Promise<{ deleted_count: number }> {
    return request.post('/notifications/delete-batch', notificationIds)
  },

  async clearAllNotifications(): Promise<void> {
    return request.delete('/notifications/')
  },

  async getOnlineMembers(groupId: string): Promise<string[]> {
    return request.get(`/groups/${groupId}/online-members`)
  },

  createWebSocketConnection(groupId: string): WebSocket {
    const token = localStorage.getItem('rag_token')
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/groups/${groupId}?token=${token}`
    return new WebSocket(wsUrl)
  }
}

export interface WebSocketMessage {
  type: 'new_message' | 'member_joined' | 'member_left' | 'member_removed' | 
        'group_updated' | 'typing' | 'online_status' | 'invitation_received' |
        'notification' | 'error'
  data?: any
  sender_id?: string
  timestamp?: string
}
