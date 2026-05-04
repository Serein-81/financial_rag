// Chat API V2
import { request } from '@/utils/request'
import type { ChatRequestV2, SessionMessage } from '@/types'
import type { Source } from '@/types'

export const chatApi = {
  // Stream chat with V2 API (普通 RAG)
  async *streamChatV2(requestData: ChatRequestV2): AsyncGenerator<{
    type: 'sources' | 'content' | 'session'
    data?: Source[]
    delta?: string
    id?: string
  }, void, unknown> {
    const token = localStorage.getItem('rag_token')

    const response = await fetch('/api/v1/chat/completions_stream_v2', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
      },
      body: JSON.stringify(requestData),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('No reader available')
    }

    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')

      // Keep the last incomplete line in buffer
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.trim()) {
          try {
            const event = JSON.parse(line)
            yield event
          } catch (error) {
            console.error('Failed to parse stream line:', line, error)
          }
        }
      }
    }
  },

  // Stream chat with Agent (智能 Agent)
  async *streamAgentChat(
    requestData: {
      kb_id: string
      query: string
      session_id?: string | null
      idempotency_key?: string
    },
    signal?: AbortSignal  // 👈 支持外部中止
  ): AsyncGenerator<{
    type: 'init' | 'chunk' | 'done' | 'sources' | 'error'
    session_id?: string
    content?: string
    sources?: any[]
    message?: string
  }, void, unknown> {
    const token = localStorage.getItem('rag_token')

    const response = await fetch('/api/v1/chat/agent_chat_stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
      },
      body: JSON.stringify(requestData),
      signal, // 👈 透传 abort signal
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('No reader available')
    }

    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      // 👇 每次迭代检查是否已中止
      if (signal?.aborted) {
        console.log('[SSE] 流已被外部中止')
        break
      }

      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')

      // Keep the last incomplete line in buffer
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const jsonStr = line.slice(6) // Remove 'data: ' prefix
            const event = JSON.parse(jsonStr)
            yield event
          } catch (error) {
            console.error('Failed to parse SSE line:', line, error)
          }
        }
      }
    }
  },
}
