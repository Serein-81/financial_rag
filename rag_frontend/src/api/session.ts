// Session API
import { request } from '@/utils/request'
import type { Session, SessionMessage } from '@/types'

export const sessionApi = {
  // Get all sessions
  async getSessions(): Promise<Session[]> {
    return request<Session[]>('/sessions/')
  },

  // Get session messages
  async getSessionMessages(session_id: string): Promise<SessionMessage[]> {
    console.log('🌐 [API] 获取会话消息:', session_id)
    console.log('🌐 [API] 请求路径:', `/sessions/${session_id}/messages`)
    const result = await request<SessionMessage[]>(`/sessions/${session_id}/messages`)
    console.log('🌐 [API] 返回结果:', result)
    console.log('🌐 [API] 结果类型:', typeof result)
    console.log('🌐 [API] 是否为数组:', Array.isArray(result))
    return result
  },

  // Delete session
  async deleteSession(session_id: string): Promise<void> {
    return request<void>(`/sessions/${session_id}`, {
      method: 'DELETE',
    })
  },
}
