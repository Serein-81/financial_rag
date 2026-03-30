// Session Store
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { sessionApi } from '@/api/session'
import type { Session, SessionMessage } from '@/types'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(null)
  const currentMessages = ref<SessionMessage[]>([])
  const isLoading = ref(false)
  const showSessionsPanel = ref(false)

  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value)
  )

  async function fetchSessions() {
    try {
      isLoading.value = true
      sessions.value = await sessionApi.getSessions()
    } catch (error) {
      console.error('Failed to fetch sessions:', error)
    } finally {
      isLoading.value = false
    }
  }

  async function loadSession(session_id: string) {
    try {
      console.log('🔄 [STORE] 开始加载会话:', session_id)
      isLoading.value = true
      currentSessionId.value = session_id
      console.log('📡 [STORE] 调用 API 获取消息...')
      currentMessages.value = await sessionApi.getSessionMessages(session_id)
      console.log('✅ [STORE] API 返回消息数:', currentMessages.value.length)
      console.log('📝 [STORE] 消息详情:', currentMessages.value)
    } catch (error) {
      console.error('❌ [STORE] 加载会话失败:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function deleteSession(session_id: string) {
    try {
      await sessionApi.deleteSession(session_id)
      sessions.value = sessions.value.filter(s => s.id !== session_id)

      if (currentSessionId.value === session_id) {
        currentSessionId.value = null
        currentMessages.value = []
      }
    } catch (error) {
      console.error('Failed to delete session:', error)
      throw error
    }
  }

  function createNewSession() {
    currentSessionId.value = null
    currentMessages.value = []
  }

  function setCurrentSession(session_id: string) {
    currentSessionId.value = session_id
  }

  function addMessage(message: SessionMessage) {
    currentMessages.value.push(message)
  }

  function updateLastMessage(content: string, sources?: any[]) {
    if (currentMessages.value.length > 0) {
      const lastMsg = currentMessages.value[currentMessages.value.length - 1]
      if (lastMsg.role === 'assistant') {
        if (content !== undefined) {
          lastMsg.content = content
        }
        if (sources !== undefined) {
          lastMsg.sources = sources
        }
      }
    }
  }

  function removeLastMessage() {
    if (currentMessages.value.length > 0) {
      currentMessages.value.pop()
    }
  }

  function toggleSessionsPanel() {
    showSessionsPanel.value = !showSessionsPanel.value
  }

  return {
    sessions,
    currentSessionId,
    currentMessages,
    currentSession,
    isLoading,
    showSessionsPanel,
    fetchSessions,
    loadSession,
    deleteSession,
    createNewSession,
    setCurrentSession,
    addMessage,
    updateLastMessage,
    removeLastMessage,
    toggleSessionsPanel,
  }
})
