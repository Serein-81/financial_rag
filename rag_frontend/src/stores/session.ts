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

  function clearMessages() {
    currentMessages.value = []
  }

  function addMessage(message: SessionMessage) {
    const msgs = currentMessages.value
    // 👇 防重：检查最后两条消息是否与新消息完全一致
    // 因为 sendMessage 以 (user, assistant) 成对添加，只检查最后一条会漏掉
    // 例如：已存在 [user:A, assistant:B]，再次 addMessage(user, A) 时
    // 最后一条是 assistant:B，role 不匹配导致去重失效
    const checkCount = Math.min(msgs.length, 2)  // 检查最多 2 条
    for (let i = 1; i <= checkCount; i++) {
      const candidate = msgs[msgs.length - i]
      if (
        candidate.role === message.role &&
        candidate.content === message.content &&
        candidate.created_at === message.created_at
      ) {
        console.warn('[STORE] 检测到重复的addMessage调用，已跳过', message.role)
        return
      }
    }
    currentMessages.value.push(message)
  }

  function updateLastMessage(content: string, sources?: any[]) {
    if (currentMessages.value.length > 0) {
      const lastMsg = currentMessages.value[currentMessages.value.length - 1]
      if (lastMsg.role === 'assistant') {
        if (content !== undefined) {
          // 🔧 前端级内容去重：检测新增内容是否与已有内容重复
          // （防止后端 streaming + post-streaming 重叠产出重复内容）
          const oldContent = lastMsg.content || ''
          if (oldContent && content.length > oldContent.length) {
            const newPart = content.slice(oldContent.length)
            // 如果新增部分已出现在旧内容尾部，说明是重复
            if (newPart && oldContent.endsWith(newPart)) {
              console.warn('[STORE] 前端检测到内容重复，已去重', {
                oldLen: oldContent.length,
                newLen: content.length,
                newPart: newPart.slice(0, 30)
              })
              // 只更新 sources，不更新 content
              if (sources !== undefined) {
                lastMsg.sources = sources
              }
              return
            }
          }
          lastMsg.content = content
        }
        if (sources !== undefined) {
          lastMsg.sources = sources
        }
      }
    }
  }

  // 👇 更新 sources 但保留现有 content（不再用空字符串覆盖）
  function updateLastMessageSources(sources: any[]) {
    if (currentMessages.value.length > 0) {
      const lastMsg = currentMessages.value[currentMessages.value.length - 1]
      if (lastMsg.role === 'assistant' && sources !== undefined) {
        lastMsg.sources = sources
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
    clearMessages,
    setCurrentSession,
    addMessage,
    updateLastMessage,
    updateLastMessageSources,
    removeLastMessage,
    toggleSessionsPanel,
  }
})
