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
  is_online?: boolean
  last_seen?: string
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

export interface SentInvitation {
  id: string
  group_id: string
  group_name: string
  invitee_id: string
  invitee_name: string
  message?: string
  status: 'pending' | 'accepted' | 'declined' | 'expired'
  created_at: string
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
  status?: 'sending' | 'sent' | 'queued' | 'failed'
}

export interface Notification {
  id: string
  type: 'invitation' | 'message' | 'member_joined' | 'member_left' | 'system'
  title: string
  content: string
  group_id?: string
  group_name?: string
  inviter_id?: string
  inviter_name?: string
  invitation_id?: string
  message?: string
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
  user_ids: string[]
  message?: string
}

export interface SendMessageRequest {
  content: string
  content_type?: 'text' | 'image' | 'file'
}

export const groupChatApi = {
  async getGroups(): Promise<ChatGroup[]> {
    return request<ChatGroup[]>('/groups/')
  },

  async createGroup(data: CreateGroupRequest): Promise<ChatGroup> {
    return request<ChatGroup>('/groups/', {
      method: 'POST',
      data: data,
    })
  },

  async getGroup(groupId: string): Promise<ChatGroup> {
    return request<ChatGroup>(`/groups/${groupId}`)
  },

  async updateGroup(groupId: string, data: Partial<CreateGroupRequest>): Promise<ChatGroup> {
    return request<ChatGroup>(`/groups/${groupId}`, {
      method: 'PUT',
      data: data,
    })
  },

  async deleteGroup(groupId: string): Promise<void> {
    return request<void>(`/groups/${groupId}`, {
      method: 'DELETE',
    })
  },

  async getGroupMembers(groupId: string): Promise<GroupMember[]> {
    return request<GroupMember[]>(`/groups/${groupId}/members`)
  },

  async inviteMembers(groupId: string, data: InviteMembersRequest): Promise<GroupInvitation[]> {
    return request<GroupInvitation[]>(`/groups/${groupId}/invite`, {
      method: 'POST',
      data: data,
    })
  },

  async leaveGroup(groupId: string): Promise<void> {
    return request<void>(`/groups/${groupId}/leave`, {
      method: 'POST',
    })
  },

  async removeMember(groupId: string, userId: string): Promise<void> {
    return request<void>(`/groups/${groupId}/members/${userId}`, {
      method: 'DELETE',
    })
  },

  async updateMemberRole(groupId: string, userId: string, role: 'admin' | 'member'): Promise<GroupMember> {
    return request<GroupMember>(`/groups/${groupId}/members/${userId}`, {
      method: 'PUT',
      data: { role },
    })
  },

  async getGroupMessages(groupId: string, params?: { limit?: number; before?: string }): Promise<GroupMessage[]> {
    return request<GroupMessage[]>(`/groups/${groupId}/messages`, { params })
  },

  async sendMessage(groupId: string, data: SendMessageRequest): Promise<GroupMessage> {
    return request<GroupMessage>(`/groups/${groupId}/messages`, {
      method: 'POST',
      data: data,
    })
  },

  async getPendingInvitations(): Promise<GroupInvitation[]> {
    return request<GroupInvitation[]>('/invitations/pending')
  },

  async getSentInvitations(): Promise<SentInvitation[]> {
    return request<SentInvitation[]>('/invitations/sent')
  },

  async acceptInvitation(invitationId: string): Promise<GroupMember> {
    return request<GroupMember>(`/invitations/${invitationId}/accept`, {
      method: 'POST',
    })
  },

  async declineInvitation(invitationId: string): Promise<void> {
    return request<void>(`/invitations/${invitationId}/decline`, {
      method: 'POST',
    })
  },

  async getNotifications(params?: { limit?: number; unread_only?: boolean }): Promise<Notification[]> {
    return request<Notification[]>('/notifications/', { params })
  },

  async markNotificationRead(notificationId: string): Promise<void> {
    return request<void>(`/notifications/${notificationId}/read`, {
      method: 'PUT',
    })
  },

  async markAllNotificationsRead(): Promise<void> {
    return request<void>('/notifications/read-all', {
      method: 'PUT',
    })
  },

  async deleteNotification(notificationId: string): Promise<void> {
    return request<void>(`/notifications/${notificationId}`, {
      method: 'DELETE',
    })
  },

  async deleteNotificationsBatch(notificationIds: string[]): Promise<{ deleted_count: number }> {
    return request<{ deleted_count: number }>('/notifications/delete-batch', {
      method: 'POST',
      data: notificationIds,
    })
  },

  async clearAllNotifications(): Promise<void> {
    return request<void>('/notifications/clear-all', {
      method: 'POST',
    })
  },

  async resendInvitationNotification(invitationId: string): Promise<void> {
    return request<void>(`/notifications/resend-invitation/${invitationId}`, {
      method: 'POST',
    })
  },

  async getOnlineMembers(groupId: string): Promise<string[]> {
    return request<string[]>(`/groups/${groupId}/online-members`)
  },

  createWebSocketConnection(groupId: string): WebSocket {
    const token = localStorage.getItem('rag_token')
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws-api/v1/ws/groups/${groupId}?token=${token}`
    console.log('WebSocket connecting to:', wsUrl)
    return new WebSocket(wsUrl)
  }
}

export interface WebSocketMessage {
  type: 'new_message' | 'group_message' | 'member_joined' | 'member_left' | 'member_removed' |
        'member_online' | 'member_offline' | 'members_sync' | 'group_updated' | 'typing' |
        'online_status' | 'invitation_received' | 'notification' | 'messages_read' | 'user_typing' | 'error'
  data?: any
  sender_id?: string
  timestamp?: string
}
