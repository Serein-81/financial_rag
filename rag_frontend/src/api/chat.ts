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
      // P0 新增：检索控制（前端传给后端，后端可选支持）
      retrieval_method?: 'simple' | 'graphrag' | 'agentic'
      max_iterations?: number
      top_k?: number
      enable_rerank?: boolean
      enable_graph_expansion?: boolean
    },
    signal?: AbortSignal  // 👈 支持外部中止
  ): AsyncGenerator<AgentStreamEvent, void, unknown> {
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

    yield* parseSSEStream(response, signal)
  },

  // 断点续传：切页返回后从 lastSeq 继续接收同一次生成的事件流（GET + SSE）
  async *streamAgentChatResume(
    sessionId: string,
    lastSeq: number = 0,
    signal?: AbortSignal
  ): AsyncGenerator<AgentStreamEvent, void, unknown> {
    const token = localStorage.getItem('rag_token')

    const response = await fetch(
      `/api/v1/chat/agent_chat_resume/${sessionId}?last_seq=${lastSeq}`,
      {
        method: 'GET',
        headers: {
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
        signal,
      }
    )

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    yield* parseSSEStream(response, signal)
  },

  // 主动停止当前会话正在进行的流式生成（点击「停止」按钮）。
  // 后端会取消后台 Agent 任务、关闭上游 LLM 流，并持久化已生成的部分内容。
  async cancelAgentChat(sessionId: string): Promise<{ cancelled: boolean; reason?: string }> {
    const token = localStorage.getItem('rag_token')
    try {
      const response = await fetch(`/api/v1/chat/cancel/${sessionId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
      })
      if (!response.ok) return { cancelled: false, reason: `HTTP ${response.status}` }
      return await response.json()
    } catch (e) {
      console.error('[Chat] 取消生成请求失败:', e)
      return { cancelled: false, reason: 'network_error' }
    }
  },
}

// Agent SSE 事件统一类型（普通流与断点续传共用）
export interface AgentStreamEvent {
  type: 'init' | 'chunk' | 'done' | 'sources' | 'error' | 'meta' | 'progress'
  session_id?: string
  content?: string
  sources?: any[]
  message?: string
  meta?: Record<string, any>
  data?: Record<string, any>
  seq?: number                    // 断点续传序号
  stage?: string                  // progress: 阶段（retrieval/evaluate）
  round?: number                  // progress: 检索轮次
  resume?: string                 // done: 续传收尾标记（no_buffer/already_done）
}

// 复用的 SSE 解析：fetch Response.body → getReader → 按 \n\n 拆 data: 帧
async function* parseSSEStream(
  response: Response,
  signal?: AbortSignal
): AsyncGenerator<AgentStreamEvent, void, unknown> {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No reader available')
  }

  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    if (signal?.aborted) {
      console.log('[SSE] 流已被外部中止')
      break
    }

    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n\n')

    // Keep the last incomplete frame in buffer
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
}
