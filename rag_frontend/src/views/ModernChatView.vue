<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useAuthStore } from '@/stores/auth'
import { useFeedbackStore } from '@/stores/feedback'
import { chatApi, type AgentStreamEvent } from '@/api/chat'
import MessageFeedback from '@/components/chat/MessageFeedback.vue'
import AgenticRagTrace from '@/components/chat/AgenticRagTrace.vue'
import RetrievalSettingsDrawer from '@/components/chat/RetrievalSettingsDrawer.vue'
import { useAutoResizeTextarea } from '@/composables/useAutoResizeTextarea'
import {
  Send,
  Sparkles,
  Database,
  Plus,
  Trash2,
  Loader2,
  FileText,
  User,
  Settings,
  X,
  CheckCircle,
  Clock,
  XCircle,
  ChevronDown,
  ChevronUp,
  Copy,
  RotateCw,
  History,
  Check,
  AlertCircle
} from 'lucide-vue-next'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import { formatChatTime } from '@/utils/time'

marked.setOptions({
  breaks: true,
  gfm: true
})

const renderer = new marked.Renderer()
renderer.code = function(code: string, lang?: string): string {
  let displayLang = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  const isPlaintext = displayLang === 'plaintext'
  const highlighted = hljs.highlight(code, { language: displayLang }).value
  if (isPlaintext) {
    return `<pre class="plain-text-block"><code class="language-plaintext">${highlighted}</code></pre>`
  }
  return `<pre class="hljs"><div class="code-header"><span class="code-lang">${displayLang}</span><button class="copy-btn" onclick="navigator.clipboard.writeText(this.closest('pre').querySelector('code').textContent)"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> 复制</button></div><code class="language-${displayLang}">${highlighted}</code></pre>`
}
marked.use({ renderer })

const sessionStore = useSessionStore()
const knowledgeStore = useKnowledgeStore()
const authStore = useAuthStore()
const feedbackStore = useFeedbackStore()

const userInput = ref('')
const {
  textareaRef: chatInputRef,
  resizeTextarea: resizeChatInput,
  resetTextarea: resetChatInput
} = useAutoResizeTextarea(userInput, { minHeight: 44, maxHeight: 148 })
const isLoading = ref(false)
const sendLock = ref(false) // ⚡ 同步锁：在 JS 事件循环中，同一时刻只有一个同步任务在执行，sendLock 的检查+设置在函数第一行完成，从根本上阻止两次事件同时通过守卫
const isComponentReady = ref(false) // 👈 阻止初始化期间的 sendMessage 调用（防止竞态重复）
const chatContainerRef = ref<HTMLDivElement>()
const showKBModal = ref(false)

// 👇 AbortController 用于组件卸载时中止正在流式请求
let streamAbortController: AbortController | null = null
const newKBName = ref('')
const newKBDesc = ref('')

const selectedFile = ref<File | null>(null)
const isUploading = ref(false)
const uploadResult = ref<any>(null)

const sourcesCollapsed = ref<Map<number, boolean>>(new Map())
const copiedMessageIndex = ref<number | null>(null)

// 检索设置抽屉
const showRetrievalDrawer = ref(false)
const retrievalSettings = ref(loadRetrievalSettings())

interface RetrievalSettings {
  retrieval_method: 'simple' | 'graphrag' | 'agentic'
  max_iterations: number
  top_k: number
  enable_rerank: boolean
  enable_graph_expansion: boolean
}

function loadRetrievalSettings(): RetrievalSettings {
  try {
    const raw = localStorage.getItem('rag_retrieval_settings')
    if (raw) return JSON.parse(raw)
  } catch {}
  return {
    retrieval_method: 'simple',
    max_iterations: 3,
    top_k: 10,
    enable_rerank: true,
    enable_graph_expansion: true,
  }
}

function saveRetrievalSettings(s: RetrievalSettings) {
  retrievalSettings.value = s
  localStorage.setItem('rag_retrieval_settings', JSON.stringify(s))
}

const streamingContent = ref<Map<number, string>>(new Map())

// 🌊 检索/生成进度提示（Agentic 多轮检索期间显示"正在检索第 N 轮…"，首个正文 chunk 到达后清空）
const streamingStatus = ref('')
// 🔖 断点续传：记录本次生成已收到的最大 seq，切页返回后据此从断点继续
const lastSeq = ref(0)

// 👇 后台生成轮询：当页面切换导致 SSE 断开时，用于等待 AI 在后台完成的异步结果
const isPolling = ref(false)
const pollingMessage = ref('')         // "AI 正在思考...（5秒）"
const pollingStartTime = ref(0)
let pollingTimer: ReturnType<typeof setTimeout> | null = null
const POLLING_INTERVAL = 2000          // 轮询间隔 2 秒
const MAX_POLLING_DURATION = 120_000   // 最长等待 2 分钟
let _visibilityHandler: (() => void) | null = null  // 页面可见性监听器引用

const messages = computed(() => sessionStore.currentMessages)
const sessions = computed(() => sessionStore.sessions)
const knowledgeBases = computed(() => knowledgeStore.knowledgeBases)
const selectedKB = computed(() => knowledgeStore.selectedKnowledgeBase)

onMounted(async () => {
  // 👇 关键修复：组件挂载时清理可能残留的旧消息
  // Pinia store 可能保留着上次访问的 currentMessages，导致后续 addMessage 追加到旧消息后产生重复
  // 策略：先清空消息（消除旧消息闪烁），再异步加载，完成后才允许用户交互
  isComponentReady.value = false
  sourcesCollapsed.value = new Map()

  // 第一步：无条件清空消息，防止旧消息在加载期间被渲染
  sessionStore.clearMessages()

  if (sessionStore.currentSessionId) {
    try {
      // 第二步：从服务器重新加载消息
      await sessionStore.loadSession(sessionStore.currentSessionId)
      // 初始化 sources 折叠状态
      sessionStore.currentMessages.forEach((msg, idx) => {
        if (msg.sources && msg.sources.length > 0) {
          sourcesCollapsed.value.set(idx, true)
        }
      })
      // 如果最后一条消息是用户的，说明 AI 可能在后台继续生成中
      // （页面切换导致流中断，但后端以后台 asyncio.Task 继续运行）
      // 优先走断点续传实时显示，缓冲不可用时回退轮询
      const lastMsg = sessionStore.currentMessages[sessionStore.currentMessages.length - 1]
      if (lastMsg && lastMsg.role === 'user') {
        recoverGeneratingSession()
      }
    } catch (err) {
      // loadSession 失败（如 token 过期、会话被删除）
      // 注意：不调用 createNewSession() — 否则会清空 currentSessionId，
      // 导致后续 auto-recovery 虽然拿到 sessions 列表，但加载时再次失败又进 catch，
      // 形成死循环。让 auto-recovery 自然重试即可。
      console.warn('[ChatView] 加载会话失败，等待重试:', err)
    }
  }

  // 第三步：并行加载侧边栏数据
  await Promise.all([
    sessionStore.fetchSessions(),
    knowledgeStore.fetchKnowledgeBases()
  ])

  // 如果 currentSessionId 仍为空但存在历史会话（init 事件可能因快速切页未被处理），
  // 自动加载最新会话，让用户看到对话记录
  if (!sessionStore.currentSessionId && sessionStore.sessions.length > 0) {
    const latestSession = sessionStore.sessions[0]
    try {
      await sessionStore.loadSession(latestSession.id)
      sessionStore.currentMessages.forEach((msg, idx) => {
        if (msg.sources && msg.sources.length > 0) {
          sourcesCollapsed.value.set(idx, true)
        }
      })
      const lastMsg = sessionStore.currentMessages[sessionStore.currentMessages.length - 1]
      if (lastMsg && lastMsg.role === 'user') {
        recoverGeneratingSession()
      }
    } catch (err) {
      console.warn('[ChatView] 自动加载最新会话失败:', err)
    }
  }

  // 第四步：标记组件就绪，允许用户交互
  isComponentReady.value = true

  // ── 注册页面可见性变化监听 ──
  // 用户切换到其他标签页再回来时，自动检查任务状态并恢复
  _visibilityHandler = async () => {
    if (document.visibilityState !== 'visible') return
    if (!sessionStore.currentSessionId) return
    if (isPolling.value || isLoading.value) return
    // 走统一恢复入口：completed→loadSession，generating+resumable→断点续传，否则轮询
    await recoverGeneratingSession()
  }
  document.addEventListener('visibilitychange', _visibilityHandler)
})

onBeforeUnmount(() => {
  // 移除页面可见性监听
  if (_visibilityHandler) {
    document.removeEventListener('visibilitychange', _visibilityHandler)
    _visibilityHandler = null
  }
  // 停止轮询（如果有）
  stopPolling()
  // 👇 组件卸载时中止正在进行的流式请求，防止后台继续修改store
  if (streamAbortController) {
    console.log('[ChatView] 组件卸载，中止流式请求')
    streamAbortController.abort()
    streamAbortController = null
  }
})

watch(() => selectedKB.value?.id, async (newId) => {
  if (newId) {
    await knowledgeStore.fetchDocuments(newId)
  }
})

// 流式累积状态（sendMessage 与断点续传共用）
interface StreamState { aiContent: string; currentSources: any[] }

// 处理单个 Agent SSE 事件，写入末尾 assistant 气泡。返回 true 表示流已结束（done/error）。
function handleAgentEvent(event: AgentStreamEvent, state: StreamState): boolean {
  if (typeof event.seq === 'number' && event.seq > lastSeq.value) {
    lastSeq.value = event.seq
  }
  switch (event.type) {
    case 'init':
      if (event.session_id) {
        sessionStore.setCurrentSession(event.session_id)
        sessionStore.fetchSessions()
      }
      break
    case 'progress':
      // 检索/评估进度，显示在气泡内（首个正文 chunk 到达后清空）
      streamingStatus.value = event.message || '处理中…'
      break
    case 'chunk':
      if (event.content) {
        // 兼容旧的 sources 前缀通道
        if (typeof event.content === 'string' &&
            (event.content.startsWith('__SOURCES__:') || event.content.startsWith('__SOURCES_EVENT__:'))) {
          try {
            const sourcesJson = event.content.replace(/^__(SOURCES|SOURCES_EVENT)__:/, '')
            state.currentSources = JSON.parse(sourcesJson)
            if (state.currentSources.length > 0) {
              const msgIndex = sessionStore.currentMessages.length - 1
              const lastMsg = sessionStore.currentMessages[msgIndex]
              if (lastMsg?.role === 'assistant') lastMsg.sources = state.currentSources
              sourcesCollapsed.value.set(msgIndex, true)
            }
          } catch (e) {
            console.error('解析sources失败:', e)
          }
        } else {
          streamingStatus.value = ''  // 首个正文到达，清空进度提示
          state.aiContent += event.content
          sessionStore.updateLastMessage(state.aiContent, state.currentSources.length > 0 ? state.currentSources : undefined)
          scrollToBottom(false)
        }
      }
      break
    case 'sources':
      if (event.sources) {
        state.currentSources = event.sources
        if (state.currentSources.length > 0) {
          const msgIndex = sessionStore.currentMessages.length - 1
          const lastMsg = sessionStore.currentMessages[msgIndex]
          if (lastMsg?.role === 'assistant') lastMsg.sources = state.currentSources
          sourcesCollapsed.value.set(msgIndex, true)
        }
      }
      break
    case 'done': {
      streamingStatus.value = ''
      const meta = (event as any).meta || (event as any).message_meta
      if (meta) {
        const msgIndex = sessionStore.currentMessages.length - 1
        const lastMsg = sessionStore.currentMessages[msgIndex] as any
        if (lastMsg?.role === 'assistant') {
          lastMsg.meta = meta
          if (meta.message_id) lastMsg.id = meta.message_id
        }
      }
      return true
    }
    case 'meta': {
      const meta = (event as any).data || (event as any).meta
      const msgIndex = sessionStore.currentMessages.length - 1
      const lastMsg = sessionStore.currentMessages[msgIndex] as any
      if (lastMsg?.role === 'assistant' && meta) {
        lastMsg.meta = meta
        if (meta.message_id) lastMsg.id = meta.message_id
      }
      break
    }
    case 'error': {
      streamingStatus.value = ''
      const errorMessage = event.message || '抱歉，AI 服务连接中断或网络不稳定，本次回答没有完整生成。请稍后重试。'
      sessionStore.updateLastMessage(errorMessage)
      state.aiContent = errorMessage
      console.error('Agent stream error:', errorMessage)
      return true
    }
  }
  return false
}

// 断点续传：切页返回且后端仍在生成时，从 lastSeq 继续接收同一次生成的事件，追加到既有气泡（不新建，防重复）
async function resumeAgentStream() {
  const sid = sessionStore.currentSessionId
  if (!sid) return

  // 定位/复用末尾的 assistant 气泡；末尾若不是 assistant（如刚 loadSession 只有 user）则补一个空气泡
  const msgs = sessionStore.currentMessages
  const last = msgs[msgs.length - 1]
  let baseContent = ''
  let baseSources: any[] = []
  if (last && last.role === 'assistant') {
    baseContent = last.content || ''
    baseSources = (last.sources as any[]) || []
  } else {
    sessionStore.addMessage({
      role: 'assistant',
      content: '',
      sender_name: 'AI助手',
      sender_avatar: undefined,
      created_at: new Date().toISOString(),
    })
  }
  const state: StreamState = { aiContent: baseContent, currentSources: baseSources }

  streamAbortController = new AbortController()
  const signal = streamAbortController.signal
  isLoading.value = true
  streamingStatus.value = '正在恢复生成…'
  try {
    for await (const event of chatApi.streamAgentChatResume(sid, lastSeq.value, signal)) {
      if (signal.aborted) break
      // 续传收尾标记：后台已结束/缓冲已清，转 loadSession 兜底拉取完整回答
      if (event.type === 'done' && (event.resume === 'no_buffer' || event.resume === 'already_done')) {
        await sessionStore.loadSession(sid)
        scrollToBottom()
        break
      }
      if (handleAgentEvent(event, state)) break
    }
  } catch (err: any) {
    if (err?.name === 'AbortError') return
    console.warn('[ChatView] 续传失败，回退轮询:', err)
    startPolling()
  } finally {
    isLoading.value = false
    streamingStatus.value = ''
    streamAbortController = null
  }
}

// 统一的"恢复生成态"入口：查任务状态决定 loadSession / 续传 / 轮询
async function recoverGeneratingSession() {
  const sid = sessionStore.currentSessionId
  if (!sid) return
  try {
    const token = localStorage.getItem('rag_token')
    const res = await fetch(`/api/v1/chat/task/status/${sid}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
    const data = await res.json()
    if (data.status === 'completed') {
      await sessionStore.loadSession(sid)
      scrollToBottom()
    } else if (data.status === 'generating') {
      if (data.resumable) {
        await resumeAgentStream()
      } else {
        startPolling()
      }
    }
  } catch (err) {
    console.warn('[ChatView] 恢复生成态检查失败，回退轮询:', err)
    startPolling()
  }
}

// 执行一次 Agent 流式生成（sendMessage 与「重新生成」共用）。
// 约定：调用方已准备好末尾的空 assistant 气泡，并已置 isLoading=true。
async function _streamAgentResponse(query: string) {
  // 👇 创建新的 AbortController（停止/卸载/切会话时中止）
  streamAbortController = new AbortController()
  const signal = streamAbortController.signal
  try {
    // 重置本次生成的续传状态
    lastSeq.value = 0
    streamingStatus.value = ''
    const streamState: StreamState = { aiContent: '', currentSources: [] }

    const idempotencyKey = crypto.randomUUID?.() // 幂等键：防止重复请求写库
    for await (const event of chatApi.streamAgentChat({
      query,
      kb_id: selectedKB.value!.id,
      session_id: sessionStore.currentSessionId || undefined,
      idempotency_key: idempotencyKey,
      retrieval_method: retrievalSettings.value.retrieval_method,
      max_iterations: retrievalSettings.value.max_iterations,
      top_k: retrievalSettings.value.top_k,
      enable_rerank: retrievalSettings.value.enable_rerank,
      enable_graph_expansion: retrievalSettings.value.enable_graph_expansion,
    }, signal)) {
      if (signal.aborted) {
        console.log('[ChatView] 流已被中止，停止处理事件')
        break
      }
      if (handleAgentEvent(event, streamState)) break
    }
  } catch (error: any) {
    // 👇 忽略因 abort（停止/卸载）触发的错误
    if (error?.name === 'AbortError') {
      console.log('[ChatView] 流式请求被中止')
      return
    }
    console.error('Error:', error)
    let errorMessage = '抱歉，发生了错误，请稍后重试。'
    if (error.message) {
      if (error.message.includes('429')) {
        errorMessage = '请求过于频繁，请稍后再试。如果问题持续存在，请联系管理员调整限流配置。'
      } else if (error.message.includes('401')) {
        errorMessage = '登录已过期，请重新登录。'
      } else if (error.message.includes('403')) {
        errorMessage = '没有权限访问，请检查您的权限设置。'
      } else if (error.message.includes('500')) {
        errorMessage = '服务器错误，请稍后重试。'
      }
    }
    sessionStore.updateLastMessage(errorMessage)
  } finally {
    isLoading.value = false
    streamAbortController = null
  }
}

// 用户主动停止生成：中止本地流 + 通知后端取消后台任务（停止烧 token）
async function stopGeneration() {
  // 1) 中止本地 SSE/续传读取（sendMessage 与 resumeAgentStream 共用同一 controller）
  if (streamAbortController) {
    streamAbortController.abort()
    streamAbortController = null
  }
  // 2) 停止可能在进行的后台轮询
  isPolling.value = false
  if (pollingTimer) { clearTimeout(pollingTimer); pollingTimer = null }
  // 3) 通知后端取消后台生成（关闭上游 LLM 流，持久化已生成的部分）
  const sid = sessionStore.currentSessionId
  if (sid) {
    try { await chatApi.cancelAgentChat(sid) } catch {}
  }
  // 4) 复位 UI 状态
  isLoading.value = false
  streamingStatus.value = ''
}

// 重新生成最后一条 AI 回答：清空末尾气泡并用上一条用户问题重新流式生成
async function regenerateLast() {
  if (isLoading.value || !isComponentReady.value) return
  if (!selectedKB.value) { alert('请先选择一个知识库'); return }
  const msgs = sessionStore.currentMessages
  if (msgs.length < 2) return
  const lastMsg = msgs[msgs.length - 1]
  if (!lastMsg || lastMsg.role !== 'assistant') return
  // 取最近一条用户消息作为重新生成的 query
  const prevUser = [...msgs].reverse().find(m => m.role === 'user')
  const q = prevUser?.content?.trim()
  if (!q) return
  // 复用末尾 assistant 气泡：清空内容/来源/meta，准备重新填充
  sessionStore.updateLastMessage('')
  const am = sessionStore.currentMessages[sessionStore.currentMessages.length - 1] as any
  if (am) { am.sources = undefined; am.meta = undefined; am.id = undefined }
  isLoading.value = true
  scrollToBottom()
  await _streamAgentResponse(q)
}

async function sendMessage() {
  // ⚡ 同步锁：在 JS 事件循环中，同步代码按调用栈顺序原子执行，
  // 不存在被其他事件中断的可能。此检查+设置作为函数**第一行**，
  // 确保任一事件到达时 sendLock 都已锁定，从根源杜绝二次重入
  if (sendLock.value) return
  sendLock.value = true
  try {
  // 👇 组件未就绪时阻止所有交互（防止 onMounted 竞态导致消息重复）
  if (!isComponentReady.value) return
  if (!userInput.value.trim() || isLoading.value) return
  if (!selectedKB.value) {
    alert('请先选择一个知识库')
    return
  }

  const query = userInput.value.trim()
  userInput.value = ''
  resetChatInput()

  // 👇 关键修复：在 addMessage 之前设置 isLoading，消除事件重入窗口
  isLoading.value = true

  const now = new Date().toISOString()
  sessionStore.addMessage({
    role: 'user',
    content: query,
    sender_name: authStore.userName || '用户',
    sender_avatar: authStore.avatarUrl || undefined,
    created_at: now
  })
  sessionStore.addMessage({
    role: 'assistant',
    content: '',
    sender_name: 'AI助手',
    sender_avatar: undefined,
    created_at: now
  })

  scrollToBottom()

  // 流式生成（与「重新生成」共用同一执行体）
  await _streamAgentResponse(query)
  } finally {
    sendLock.value = false
  }
}

function scrollToBottom(force = true) {
  nextTick(() => {
    const el = chatContainerRef.value
    if (!el) return
    // force=false（流式逐 token）时，仅当用户已在底部附近才自动滚动，
    // 避免用户上滑查看历史时被强制拽回底部。
    if (!force) {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
      if (!nearBottom) return
    }
    el.scrollTop = el.scrollHeight
  })
}

// ── 轮询等待 AI 后台生成 ──
// 页面切换导致 SSE 断开后，AI 以后台 asyncio.Task 继续运行。
// 此函数定时重新加载会话，直到 AI 回答出现或超时。
function startPolling() {
  if (!sessionStore.currentSessionId) return

  // 检查最近一条用户消息是否足够新（<30秒），否则后台任务早已不存在
  const _allMsgs = sessionStore.currentMessages
  const _lastUser = [..._allMsgs].reverse().find(m => m.role === 'user')
  if (_lastUser && _lastUser.created_at) {
    const _age = Date.now() - new Date(_lastUser.created_at).getTime()
    if (_age > 30000) {
      console.log('[ChatView] 用户消息已超过 30 秒，后台任务已结束，不启动轮询')
      return
    }
  }

  isPolling.value = true
  pollingStartTime.value = Date.now()
  pollingMessage.value = '正在等待 AI 继续生成...'

  const poll = async () => {
    if (!isPolling.value || !sessionStore.currentSessionId) return

    // 超时保护
    const elapsed = Date.now() - pollingStartTime.value
    if (elapsed >= MAX_POLLING_DURATION) {
      console.warn('[ChatView] 轮询超时，AI 生成可能失败')
      pollingMessage.value = 'AI 生成超时，请重新提问'
      isPolling.value = false
      return
    }

    try {
      await sessionStore.loadSession(sessionStore.currentSessionId)
      const msgs = sessionStore.currentMessages

      // 检查是否所有问题都有回答：比较 user 和 assistant 的数量
      // [user]                          → user=1, assistant=0 → 等待
      // [user, assistant]               → user=1, assistant=1 → 完成
      // [user, assistant, user]         → user=2, assistant=1 → 等待（新问题未答）
      // [user, assistant, user, asst]   → user=2, assistant=2 → 完成
      const userCount = msgs.filter(m => m.role === 'user').length
      const asstCount = msgs.filter(m => m.role === 'assistant' && m.content).length
      if (userCount > 0 && userCount <= asstCount) {
        console.log('[ChatView] 轮询成功，所有问题已回答')
        pollingMessage.value = ''
        isPolling.value = false
        scrollToBottom()
        return
      }

      // 更新等待提示，显示已等待时间
      const seconds = Math.floor(elapsed / 1000)
      pollingMessage.value = `AI 正在思考中...（${seconds}秒）`

      // 继续下一轮
      pollingTimer = setTimeout(poll, POLLING_INTERVAL)
    } catch (err) {
      console.warn('[ChatView] 轮询加载失败，继续等待:', err)
      pollingTimer = setTimeout(poll, POLLING_INTERVAL)
    }
  }

  // 首轮延迟后开始
  pollingTimer = setTimeout(poll, POLLING_INTERVAL)
}

function stopPolling() {
  isPolling.value = false
  pollingMessage.value = ''
  if (pollingTimer !== null) {
    clearTimeout(pollingTimer)
    pollingTimer = null
  }
}

async function loadSession(sessionId: string) {
  // 👇 组件初始化期间不处理会话切换
  if (!isComponentReady.value) {
    console.warn('[ChatView] 组件尚未就绪，跳过会话切换请求')
    return
  }
  // 👇 如果正在流式请求，先中止它，防止继续污染store
  if (streamAbortController) {
    console.log('[ChatView] 切换会话，中止当前流式请求')
    streamAbortController.abort()
    streamAbortController = null
  }

  try {
    await sessionStore.loadSession(sessionId)
    // 👇 清除旧的 sources 折叠状态，避免索引错乱
    sourcesCollapsed.value = new Map()
    // 初始化所有历史消息的sources为折叠状态
    const msgs = sessionStore.currentMessages
    msgs.forEach((msg, idx) => {
      if (msg.sources && msg.sources.length > 0) {
        sourcesCollapsed.value.set(idx, true)
      }
    })
    await nextTick()
    scrollToBottom()
  } catch (error) {
    console.error('❌ 加载会话失败:', error)
    alert('加载会话失败: ' + error)
  }
}

async function deleteSession(sessionId: string) {
  if (confirm('确定要删除这个会话吗？')) {
    await sessionStore.deleteSession(sessionId)
  }
}

function createNewSession() {
  sessionStore.createNewSession()
}

function renderMarkdown(content: string): string {
  let html = marked(content) as string
  
  html = DOMPurify.sanitize(html, {
    ADD_TAGS: ['button', 'svg', 'path', 'rect'],
    ADD_ATTR: ['onclick', 'target', 'xmlns', 'viewBox', 'fill', 'stroke', 'stroke-width', 'd', 'rx', 'ry', 'x', 'y', 'width', 'height', 'class']
  })
  
  html = html.replace(/<table>/g, '<table class="ai-table">')
  html = html.replace(/<blockquote>/g, '<blockquote class="ai-blockquote">')
  html = html.replace(/<ul>/g, '<ul class="ai-list">')
  html = html.replace(/<ol>/g, '<ol class="ai-list ai-list-ordered">')
  html = html.replace(/<li>/g, '<li class="ai-list-item">')
  html = html.replace(/<h1>/g, '<h1 class="ai-heading ai-h1">')
  html = html.replace(/<h2>/g, '<h2 class="ai-heading ai-h2">')
  html = html.replace(/<h3>/g, '<h3 class="ai-heading ai-h3">')
  html = html.replace(/<h4>/g, '<h4 class="ai-heading ai-h4">')
  html = html.replace(/<hr>/g, '<hr class="ai-hr">')
  html = html.replace(/<strong>/g, '<strong class="ai-bold">')
  html = html.replace(/<em>/g, '<em class="ai-italic">')
  html = html.replace(/<a /g, '<a class="ai-link" target="_blank" rel="noopener noreferrer" ')
  html = html.replace(/<code>(?!<)/g, '<code class="ai-inline-code">')

  return html
}

// 流式中用轻量渲染：仅转义 HTML + 换行，避免每个 token 都对整段累积文本重跑
// marked + DOMPurify + hljs（原实现是 O(n²) 卡顿）。流结束后再由 renderMarkdown 完整渲染一次。
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderStreamingText(content: string): string {
  return escapeHtml(content).replace(/\n/g, '<br>')
}

// 根据是否正在流式，选择轻量/完整渲染
function renderMessageBody(content: string, index: number): string {
  return isStreamingMessage(index) ? renderStreamingText(content) : renderMarkdown(content)
}

async function createKnowledgeBase() {
  if (!newKBName.value.trim()) return

  try {
    await knowledgeStore.createKnowledgeBase(newKBName.value, newKBDesc.value)
    newKBName.value = ''
    newKBDesc.value = ''
    showKBModal.value = false
  } catch (error) {
    alert('创建失败')
  }
}

function toggleSourcesCollapse(index: number) {
  const current = sourcesCollapsed.value.get(index)
  sourcesCollapsed.value.set(index, !current)
}

function copyMessage(content: string, index: number) {
  navigator.clipboard.writeText(content)
  copiedMessageIndex.value = index
  setTimeout(() => {
    copiedMessageIndex.value = null
  }, 2000)
}

// 获取消息之前的用户提问（用于反馈携带 query 上下文）
function getPreviousUserQuery(index: number): string {
  for (let i = index - 1; i >= 0; i--) {
    const m = sessionStore.currentMessages[i]
    if (m.role === 'user') return m.content
  }
  return ''
}

function onRetrievalSettingsSave(s: RetrievalSettings) {
  saveRetrievalSettings(s)
  showRetrievalDrawer.value = false
}

// 会话切换时同步加载历史反馈，让点赞/评分状态正确回显
watch(
  () => sessionStore.currentSessionId,
  async (sid) => {
    feedbackStore.clear()
    if (sid) {
      try {
        await feedbackStore.loadSessionFeedbacks(sid)
      } catch (e) {
        console.warn('加载历史反馈失败:', e)
      }
    }
  },
  { immediate: true }
)

function getStatusIcon(status: string) {
  switch (status) {
    case 'completed':
      return CheckCircle
    case 'processing':
      return Loader2
    case 'failed':
      return XCircle
    default:
      return Clock
  }
}

function getStatusColor(status: string) {
  switch (status) {
    case 'completed':
      return 'text-green-600'
    case 'processing':
      return 'text-blue-600 animate-spin'
    case 'failed':
      return 'text-red-600'
    default:
      return 'text-gray-600'
  }
}

function getInitials(name: string): string {
  return name.charAt(0).toUpperCase()
}

function isStreamingMessage(index: number): boolean {
  const message = messages.value[index]
  return isLoading.value && index === messages.value.length - 1 && message?.role === 'assistant'
}

function getAvatarColor(name: string): string {
  const colors = [
    'from-emerald-500 to-teal-600',
    'from-teal-500 to-emerald-600',
    'from-green-500 to-emerald-600',
    'from-orange-500 to-red-600',
    'from-cyan-500 to-teal-600',
    'from-lime-500 to-emerald-600'
  ]
  const index = name.charCodeAt(0) % colors.length
  return colors[index]
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function createNewChat() {
  // 👇 如果正在流式请求，先中止它
  if (streamAbortController) {
    streamAbortController.abort()
    streamAbortController = null
  }
  sessionStore.createNewSession()
  sessionStore.fetchSessions()
  // 👇 清除旧的 sources 折叠状态
  sourcesCollapsed.value = new Map()
}
</script>

<template>
  <div class="h-full flex bg-gradient-to-br from-slate-50 to-white">
    <!-- Chat Area -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Messages -->
      <div ref="chatContainerRef" class="flex-1 overflow-y-auto px-4 py-5 sm:px-5 sm:py-6 space-y-4">
        <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center">
          <div class="absolute top-4 right-4">
            <button
              @click="createNewChat"
              class="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-emerald-300 flex items-center gap-2 text-sm text-gray-700 shadow-sm transition-all"
            >
              <Plus :size="16" />
              新建对话
            </button>
          </div>
          <div class="w-20 h-20 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-2xl flex items-center justify-center mb-6 shadow-lg">
            <Sparkles :size="40" class="text-white" />
          </div>
          <h2 class="text-2xl font-bold text-gray-900 mb-2">欢迎使用 RAG 知识库系统</h2>
          <p class="text-gray-500 mb-8 max-w-md">
            请选择一个知识库，然后开始智能对话。我将根据知识库中的内容为你提供准确的答案。
          </p>

          <!-- Quick Actions -->
          <div class="grid grid-cols-2 gap-4 max-w-lg">
            <div class="p-4 bg-white rounded-xl border border-gray-200 text-left">
              <h3 class="font-semibold text-gray-900 mb-1">选择知识库</h3>
              <p class="text-sm text-gray-500">从下拉菜单选择要查询的知识库</p>
            </div>
            <div class="p-4 bg-white rounded-xl border border-gray-200 text-left">
              <h3 class="font-semibold text-gray-900 mb-1">开始对话</h3>
              <p class="text-sm text-gray-500">输入问题，获取基于知识库的智能回答</p>
            </div>
          </div>
        </div>

        <div v-for="(message, index) in messages" :key="index" class="animate-message">
          <!-- User Message - 深灰色气泡 -->
          <div v-if="message.role === 'user'" class="flex gap-3 max-w-4xl ml-auto items-end">
            <!-- Message Content -->
            <div class="flex-1 flex flex-col items-end">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs text-gray-400">{{ message.created_at ? formatChatTime(message.created_at) : '' }}</span>
                <span class="text-sm font-medium text-gray-700">{{ message.sender_name || authStore.userName || '用户' }}</span>
              </div>
              <div class="bg-white border border-gray-200 text-gray-900 px-4 py-3 rounded-2xl rounded-br-md max-w-xl shadow-sm">
                <p class="whitespace-pre-wrap">{{ message.content }}</p>
              </div>
            </div>

            <!-- Avatar (Right side for user's messages) -->
            <div class="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold flex-shrink-0 overflow-hidden bg-gradient-to-br from-emerald-500 to-teal-600">
              <img
                v-if="message.sender_avatar"
                :src="message.sender_avatar"
                :alt="message.sender_name || 'User'"
                class="w-full h-full object-cover"
                @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }"
              />
              <span v-else>{{ getInitials(message.sender_name || authStore.userName || 'U') }}</span>
            </div>
          </div>

          <!-- Assistant Message - 白色气泡 -->
          <div v-else class="flex gap-3 max-w-4xl animate-message">
            <!-- Avatar -->
            <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white font-bold flex-shrink-0 shadow-sm">
              <Sparkles :size="18" />
            </div>

            <!-- Message Content -->
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-sm font-medium text-gray-700">{{ message.sender_name || 'AI助手' }}</span>
                <span class="text-xs text-gray-400">{{ message.created_at ? formatChatTime(message.created_at) : '' }}</span>
              </div>
              <div class="bg-white border border-gray-200 px-4 py-3 rounded-2xl rounded-bl-md">
                <div v-if="message.content" class="prose prose-sm max-w-none">
                  <span v-html="renderMessageBody(message.content, index)"></span>
                  <span v-if="isStreamingMessage(index)" class="streaming-cursor" aria-hidden="true"></span>
                </div>
                <div v-else class="flex items-center gap-2">
                  <!-- 检索/生成进度（Agentic 多轮检索期间）：有进度文案则显示文案，否则骨架屏 -->
                  <div v-if="isStreamingMessage(index) && streamingStatus" class="flex items-center gap-2 text-sm text-gray-500">
                    <Loader2 :size="16" class="animate-spin text-emerald-500" />
                    <span>{{ streamingStatus }}</span>
                  </div>
                  <!-- 骨架屏加载动画 -->
                  <div v-else class="space-y-2 animate-pulse">
                    <div class="flex gap-2">
                      <div class="h-4 bg-gray-200 rounded w-24"></div>
                      <div class="h-4 bg-gray-200 rounded w-32"></div>
                    </div>
                    <div class="h-4 bg-gray-200 rounded w-48"></div>
                    <div class="h-4 bg-gray-200 rounded w-36"></div>
                  </div>
                </div>

                <!-- Sources -->
                <div v-if="message.sources && message.sources.length > 0" class="mt-4 pt-4 border-t border-gray-200">
                  <button
                    @click="toggleSourcesCollapse(index)"
                    class="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
                  >
                    <div class="flex items-center gap-2">
                      <FileText :size="16" />
                      <span class="bg-gradient-to-r from-emerald-600 to-teal-600 bg-clip-text text-transparent font-semibold">
                        参考文档 ({{ message.sources.length }})
                      </span>
                    </div>
                    <ChevronDown v-if="!sourcesCollapsed.get(index)" :size="16" class="text-gray-500" />
                    <ChevronUp v-else :size="16" class="text-gray-500" />
                  </button>

                  <div v-if="!sourcesCollapsed.get(index)" class="mt-3 space-y-2">
                    <div
                      v-for="(source, sIndex) in message.sources"
                      :key="sIndex"
                      class="p-4 bg-gradient-to-br from-gray-50 to-emerald-50 rounded-xl border border-gray-200 hover:border-emerald-300 transition-all text-sm"
                    >
                      <div class="flex items-start justify-between mb-2">
                        <div class="flex items-center gap-2">
                          <FileText :size="14" class="text-emerald-600" />
                          <span class="font-medium text-gray-900">{{ source.filename }}</span>
                        </div>
                        <span class="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs rounded-full font-medium">
                          {{ (source.score * 100).toFixed(0) }}% 匹配
                        </span>
                      </div>
                      <p class="text-gray-600 leading-relaxed">{{ source.content }}</p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Agentic RAG 步骤可视化 (assistant 消息 + 含 retrieval_history 时显示) -->
              <AgenticRagTrace
                v-if="message.role === 'assistant' && (message as any).meta?.retrieval_history?.length"
                :history="(message as any).meta.retrieval_history"
                :evaluation="(message as any).meta?.evaluation"
                :retrieval-method="(message as any).meta?.retrieval_method"
                class="mt-3"
              />

              <!-- Message Actions -->
              <div v-if="message.content && message.role === 'assistant'" class="flex items-center gap-2 mt-3">
                <MessageFeedback
                  :message="message as any"
                  :previous-user-query="getPreviousUserQuery(index)"
                  :session-id="sessionStore.currentSessionId"
                />
                <div class="w-px h-4 bg-gray-200 mx-1"></div>
                <button
                  @click="copyMessage(message.content, index)"
                  class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  :title="copiedMessageIndex === index ? '已复制' : '复制'"
                >
                  <CheckCircle v-if="copiedMessageIndex === index" :size="16" class="text-green-600" />
                  <Copy v-else :size="16" class="text-gray-400 hover:text-gray-600" />
                </button>
                <!-- 重新生成（仅最后一条 AI 回答，空闲时可用）-->
                <button
                  v-if="index === messages.length - 1 && !isLoading"
                  @click="regenerateLast"
                  class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  title="重新生成"
                >
                  <RotateCw :size="16" class="text-gray-400 hover:text-gray-600" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- ── 等待 AI 后台生成的友好提示 ──
             页面切换后 SSE 断开，AI 以 asyncio.Task 在后台继续运行，
             前端轮询等待结果写入 DB 后自动显示 -->
        <div
          v-if="isPolling"
          class="flex flex-col items-center justify-center py-8 text-center animate-message"
        >
          <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg mb-4">
            <Loader2 :size="24" class="text-white animate-spin" />
          </div>
          <p class="text-sm text-gray-500 mb-1">{{ pollingMessage }}</p>
          <p class="text-xs text-gray-400">正在从后台获取 AI 的回答，请耐心等待</p>
        </div>
      </div>

      <!-- Input Area -->
      <div class="shrink-0 bg-white/90 backdrop-blur-sm border-t border-gray-200/80 px-4 py-3">
        <div class="max-w-5xl mx-auto">
          <!-- Toolbar -->
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <button
                @click="createNewChat"
                class="px-2.5 py-1 text-xs text-gray-600 hover:text-emerald-700 hover:bg-emerald-50 rounded-lg flex items-center gap-1.5 transition-all"
              >
                <Plus :size="14" />
                新对话
              </button>
              <button
                @click="showRetrievalDrawer = true"
                class="px-2.5 py-1 text-xs text-gray-600 hover:text-emerald-700 hover:bg-emerald-50 rounded-lg flex items-center gap-1.5 transition-all"
                title="检索设置"
              >
                <Settings :size="14" />
                <span>{{
                  retrievalSettings.retrieval_method === 'simple' ? '简单向量' :
                  retrievalSettings.retrieval_method === 'graphrag' ? 'GraphRAG' :
                  'Agentic RAG'
                }}</span>
              </button>
            </div>
            <div v-if="sessionStore.currentSessionId" class="text-xs text-gray-500">
              当前会话: {{ sessionStore.currentSession?.title || '未命名' }}
            </div>
          </div>

          <div class="flex flex-col gap-2 lg:flex-row lg:items-end">
            <div class="lg:w-72 flex items-center gap-2 bg-slate-50/80 rounded-xl px-3 py-2.5 border border-slate-200/80 focus-within:border-emerald-500 focus-within:ring-2 focus-within:ring-emerald-200/60 transition-all shadow-sm">
              <Database :size="18" class="text-gray-400 flex-shrink-0" />

              <select
                v-model="knowledgeStore.selectedKnowledgeBaseId"
                class="min-w-0 flex-1 bg-transparent border-none outline-none text-gray-900 text-sm"
              >
                <option :value="null" disabled>选择知识库...</option>
                <option
                  v-for="kb in knowledgeBases"
                  :key="kb.id"
                  :value="kb.id"
                >
                  {{ kb.name }}
                </option>
              </select>

              <span class="w-px h-5 bg-slate-200" />

              <button
                @click="showKBModal = true"
                class="p-1.5 hover:bg-slate-200/80 rounded-lg transition-all hover:text-emerald-600 text-gray-400 flex-shrink-0"
                title="创建新知识库"
              >
                <Plus :size="18" />
              </button>
            </div>

            <textarea
              ref="chatInputRef"
              v-model="userInput"
              rows="1"
              placeholder="输入你的问题..."
              class="min-h-[44px] max-h-[148px] flex-1 px-4 py-2.5 bg-slate-50/80 border border-slate-200/80 rounded-xl focus:ring-2 focus:ring-emerald-200/60 focus:border-emerald-500 outline-none resize-none shadow-sm transition-all leading-6"
              @input="resizeChatInput"
              @keydown.enter.exact.prevent="sendMessage"
              :disabled="isLoading || !isComponentReady"
            />

            <!-- 生成中显示「停止」按钮，否则显示「发送」 -->
            <button
              v-if="isLoading"
              @click="stopGeneration"
              class="h-11 px-4 bg-gradient-to-r from-rose-500 to-red-600 text-white font-medium rounded-xl hover:from-rose-600 hover:to-red-700 flex items-center justify-center gap-2 shadow-md hover:shadow-lg transition-all"
              title="停止生成"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
              <span class="hidden sm:inline">停止</span>
            </button>
            <button
              v-else
              @click="sendMessage"
              :disabled="!userInput.trim()"
              class="h-11 px-4 bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-medium rounded-xl hover:from-emerald-700 hover:to-teal-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-md hover:shadow-lg transition-all"
            >
              <Send :size="18" />
            </button>
          </div>

          <div class="hidden sm:flex items-center justify-between mt-2 text-xs text-gray-500">
            <span class="flex items-center gap-1.5">
              <kbd class="px-1.5 py-0.5 bg-slate-100 rounded text-[10px] font-mono font-medium text-slate-500">Enter</kbd>
              发送
              <kbd class="px-1.5 py-0.5 bg-slate-100 rounded text-[10px] font-mono font-medium text-slate-500">Shift + Enter</kbd>
              换行
            </span>
            <span>{{ messages.length }} 条消息</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Sessions Sidebar -->
    <div class="w-72 bg-white/80 backdrop-blur-sm border-l border-gray-200/80 flex flex-col">
      <div class="p-4 border-b border-gray-200/80 bg-gradient-to-r from-white to-emerald-50/30">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <History :size="14" class="text-white" />
            </div>
            <h2 class="font-semibold text-gray-900 text-sm">会话列表</h2>
          </div>
          <button
            @click="createNewSession"
            class="p-1.5 hover:bg-white rounded-lg transition-all hover:shadow-sm hover:text-emerald-600 text-gray-500"
            title="新建会话"
          >
            <Plus :size="18" />
          </button>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto custom-scrollbar">
        <div v-if="sessions.length === 0" class="p-6 text-center text-gray-500 text-sm">
          暂无会话记录
        </div>
        <div v-else class="p-2 space-y-0.5">
          <div
            v-for="session in sessions"
            :key="session.id"
            :class="[
              'p-3 rounded-lg cursor-pointer transition-all duration-150 group',
              sessionStore.currentSessionId === session.id
                ? 'bg-gradient-to-r from-emerald-50 to-teal-50/50 border border-emerald-200/80 shadow-sm'
                : 'hover:bg-gray-50 border border-transparent'
            ]"
            @click="loadSession(session.id)"
          >
            <div class="flex items-start justify-between mb-1">
              <h3 class="font-medium text-gray-900 text-sm truncate flex-1">{{ session.title }}</h3>
              <button
                @click.stop="deleteSession(session.id)"
                class="p-1 hover:bg-red-100 rounded transition-all opacity-0 group-hover:opacity-100"
              >
                <Trash2 :size="14" class="text-red-400 hover:text-red-500" />
              </button>
            </div>
            <p class="text-xs text-gray-500 flex items-center gap-1.5">
              <Clock :size="11" />
              {{ formatChatTime(session.updated_at) }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Create KB Modal -->
    <Teleport to="body">
      <div
        v-if="showKBModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
        @click.self="showKBModal = false"
      >
        <div class="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl border border-slate-200/80 animate-message">
          <div class="flex items-center justify-between mb-6">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-sm">
                <Database :size="20" class="text-white" />
              </div>
              <div>
                <h3 class="text-lg font-semibold text-gray-900">创建知识库</h3>
                <p class="text-xs text-gray-500">添加一个新的知识库</p>
              </div>
            </div>
            <button @click="showKBModal = false" class="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-gray-100 transition-colors">
              <X :size="20" class="text-gray-500" />
            </button>
          </div>

          <div class="space-y-5">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">知识库名称</label>
              <input
                v-model="newKBName"
                type="text"
                placeholder="输入知识库名称"
                class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none transition-all bg-slate-50/50"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">描述 <span class="text-gray-400 font-normal">（可选）</span></label>
              <textarea
                v-model="newKBDesc"
                rows="3"
                placeholder="输入知识库描述"
                class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none resize-none transition-all bg-slate-50/50"
              />
            </div>
          </div>

          <div class="flex justify-end gap-3 mt-8 pt-4 border-t border-slate-100">
            <button
              @click="showKBModal = false"
              class="px-5 py-2 text-gray-700 font-medium rounded-xl hover:bg-gray-100 transition-colors"
            >
              取消
            </button>
            <button
              @click="createKnowledgeBase"
              class="px-5 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-medium rounded-xl hover:from-emerald-700 hover:to-teal-700 transition-all shadow-md hover:shadow-lg"
            >
              创建
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 检索设置抽屉 -->
    <RetrievalSettingsDrawer
      v-model="showRetrievalDrawer"
      :settings="retrievalSettings"
      @save="onRetrievalSettingsSave"
    />
  </div>
</template>

<style>
.message-list-enter-active {
  animation: messageSlideIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.message-list-leave-active {
  animation: messageFadeOut 0.2s ease-out;
}

.message-list-move {
  transition: transform 0.3s ease;
}

@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes messageFadeOut {
  from {
    opacity: 1;
    transform: scale(1);
  }
  to {
    opacity: 0;
    transform: scale(0.95);
  }
}

/* 单条消息动画 */
.animate-message {
  animation: messageAppear 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes messageAppear {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.ai-table {
  @apply w-full border-collapse my-4;
}
.ai-table th {
  @apply bg-gradient-to-r from-emerald-50 to-teal-50 text-left px-4 py-3 font-semibold text-gray-700 border border-gray-200;
}
.ai-table td {
  @apply px-4 py-3 border border-gray-200 text-gray-600;
}
.ai-table tr:hover td {
  @apply bg-emerald-50/50;
}

.ai-blockquote {
  @apply border-l-4 border-emerald-500 pl-4 py-2 my-4 bg-emerald-50/80 rounded-r-lg text-gray-700 italic;
}

.ai-list {
  @apply my-3 space-y-2;
}
.ai-list-ordered {
  @apply list-decimal;
}
.ai-list-item {
  @apply ml-4 text-gray-700 leading-relaxed;
}
.ai-list-item::marker {
  @apply text-emerald-500 font-medium;
}

.ai-heading {
  @apply font-bold text-gray-900 mb-3 mt-6;
}
.ai-h1 { @apply text-2xl border-b pb-2; }
.ai-h2 { @apply text-xl; }
.ai-h3 { @apply text-lg; }
.ai-h4 { @apply text-base; }

.ai-hr {
  @apply my-6 border-gray-200;
}

.ai-bold {
  @apply font-bold text-gray-900;
}
.ai-italic {
  @apply italic text-gray-600;
}
.ai-link {
  @apply text-emerald-600 hover:text-emerald-800 underline decoration-emerald-300 hover:decoration-emerald-500 transition-colors;
}
.ai-inline-code {
  @apply bg-gray-100 text-teal-600 px-1.5 py-0.5 rounded text-sm font-mono;
}

pre.plain-text-block {
  @apply bg-gray-100 rounded-lg my-3 p-3 text-sm font-mono text-gray-700 overflow-x-auto border border-gray-200;
}
pre.plain-text-block code {
  @apply bg-transparent text-inherit p-0;
}

pre.hljs {
  @apply bg-gray-900 rounded-lg my-4 overflow-hidden;
}
pre.hljs .code-header {
  @apply flex justify-between items-center px-4 py-2 bg-gray-800 border-b border-gray-700;
}
pre.hljs .code-lang {
  @apply text-xs text-gray-400 font-mono uppercase tracking-wide;
}
pre.hljs .copy-btn {
  @apply flex items-center gap-1.5 text-xs text-gray-400 hover:text-white bg-transparent hover:bg-gray-700 px-2 py-1 rounded transition-colors;
}
pre.hljs code {
  @apply block px-4 py-3 text-sm font-mono text-gray-100 overflow-x-auto;
}
.hljs-keyword { @apply text-teal-400; }
.hljs-string { @apply text-emerald-400; }
.hljs-number { @apply text-amber-400; }
.hljs-comment { @apply text-gray-500 italic; }
.hljs-function { @apply text-sky-400; }
.hljs-class { @apply text-amber-300; }
.hljs-variable { @apply text-orange-400; }
.hljs-operator { @apply text-teal-400; }
.hljs-built_in { @apply text-cyan-400; }

.ai-paragraph {
  @apply my-3 text-gray-700 leading-relaxed;
}

.streaming-cursor {
  display: inline-block;
  width: 7px;
  height: 1.1em;
  margin-left: 3px;
  vertical-align: -0.15em;
  border-radius: 9999px;
  background: #059669;
  animation: streamingBlink 0.9s ease-in-out infinite;
}

@keyframes streamingBlink {
  0%, 100% {
    opacity: 0.25;
  }
  50% {
    opacity: 1;
  }
}
</style>
