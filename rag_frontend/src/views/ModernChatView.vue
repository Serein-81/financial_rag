<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useAuthStore } from '@/stores/auth'
import { chatApi } from '@/api/chat'
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
  ThumbsUp,
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
const likedMessages = ref<Set<number>>(new Set())

const streamingContent = ref<Map<number, string>>(new Map())

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
      // 启动轮询，每隔 2 秒重新加载消息，直到 AI 回答出现或超时
      const lastMsg = sessionStore.currentMessages[sessionStore.currentMessages.length - 1]
      if (lastMsg && lastMsg.role === 'user') {
        startPolling()
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
        startPolling()
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

    try {
      const _token = localStorage.getItem('rag_token')
      const res = await fetch(`/api/v1/chat/task/status/${sessionStore.currentSessionId}`, {
        headers: _token ? { Authorization: `Bearer ${_token}` } : undefined,
      })
      const data = await res.json()
      if (data.status === 'completed') {
        // 后台任务已完成，加载最新消息
        await sessionStore.loadSession(sessionStore.currentSessionId)
        scrollToBottom()
      } else if (data.status === 'generating') {
        // 后台仍在生成，启动轮询
        startPolling()
      }
    } catch (err) {
      console.warn('[ChatView] 页面可见性检查失败:', err)
    }
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

  // 👇 创建新的 AbortController
  streamAbortController = new AbortController()
  const signal = streamAbortController.signal

  try {
    let aiContent = ''
    let currentSources: any[] = []

    const idempotencyKey = crypto.randomUUID?.() // 幂等键：防止重复请求写库
    for await (const event of chatApi.streamAgentChat({
      query,
      kb_id: selectedKB.value.id,
      session_id: sessionStore.currentSessionId || undefined,
      idempotency_key: idempotencyKey,
    }, signal)) {
      if (signal.aborted) {
        console.log('[ChatView] 流已被中止，停止处理事件')
        break
      }

      if (event.type === 'init' && event.session_id) {
        sessionStore.setCurrentSession(event.session_id)
        await sessionStore.fetchSessions()
      } else if (event.type === 'chunk' && event.content) {
        // 检查是否是sources数据（支持两种前缀）
        if (typeof event.content === 'string' &&
            (event.content.startsWith('__SOURCES__:') || event.content.startsWith('__SOURCES_EVENT__:'))) {
          try {
            const sourcesJson = event.content.replace(/^__(SOURCES|SOURCES_EVENT)__:/, '')
            currentSources = JSON.parse(sourcesJson)
            // 👇 修复：仅更新sources，不再用空字符串覆盖内容
            if (currentSources.length > 0) {
              const msgIndex = sessionStore.currentMessages.length - 1
              // 保留现有内容，只更新sources
              const lastMsg = sessionStore.currentMessages[msgIndex]
              if (lastMsg?.role === 'assistant') {
                lastMsg.sources = currentSources
              }
              sourcesCollapsed.value.set(msgIndex, true) // 默认折叠
            }
          } catch (e) {
            console.error('解析sources失败:', e)
          }
        } else {
          aiContent += event.content
          sessionStore.updateLastMessage(aiContent, currentSources.length > 0 ? currentSources : undefined)
          scrollToBottom()
        }
      } else if (event.type === 'sources' && event.sources) {
        // 👇 修复：仅更新sources，不再用空字符串覆盖内容
        currentSources = event.sources
        if (currentSources.length > 0) {
          const msgIndex = sessionStore.currentMessages.length - 1
          const lastMsg = sessionStore.currentMessages[msgIndex]
          if (lastMsg?.role === 'assistant') {
            // 保留现有内容，只更新sources
            lastMsg.sources = currentSources
          }
          sourcesCollapsed.value.set(msgIndex, true) // 默认折叠
        }
      } else if (event.type === 'done') {
        console.log('✅ Agent 回答完成')
      } else if (event.type === 'error') {
        const errorMessage = event.message || '抱歉，AI 服务连接中断或网络不稳定，本次回答没有完整生成。请稍后重试。'
        sessionStore.updateLastMessage(errorMessage)
        aiContent = errorMessage
        console.error('Agent stream error:', errorMessage)
      }
    }
  } catch (error: any) {
    // 👇 忽略因 abort 触发的错误
    if (error?.name === 'AbortError') {
      console.log('[ChatView] 流式请求被中止（组件卸载）')
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
  } finally {
    sendLock.value = false
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight
    }
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

function toggleLike(index: number) {
  if (likedMessages.value.has(index)) {
    likedMessages.value.delete(index)
  } else {
    likedMessages.value.add(index)
  }
  // 触发响应式更新
  likedMessages.value = new Set(likedMessages.value)
}

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
                  <span v-html="renderMarkdown(message.content)"></span>
                  <span v-if="isStreamingMessage(index)" class="streaming-cursor" aria-hidden="true"></span>
                </div>
                <div v-else class="flex items-center gap-2">
                  <!-- 骨架屏加载动画 -->
                  <div class="space-y-2 animate-pulse">
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

              <!-- Message Actions -->
              <div v-if="message.content" class="flex items-center gap-2 mt-3">
                <button
                  @click="toggleLike(index)"
                  class="p-2 hover:bg-gray-100 rounded-lg transition-all"
                  :title="likedMessages.has(index) ? '取消点赞' : '点赞'"
                  :class="likedMessages.has(index) ? 'bg-red-50' : ''"
                >
                  <ThumbsUp
                    :size="16"
                    :class="likedMessages.has(index) ? 'text-red-500 fill-current' : 'text-gray-400 hover:text-red-500'"
                  />
                </button>
                <button
                  @click="copyMessage(message.content, index)"
                  class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  :title="copiedMessageIndex === index ? '已复制' : '复制'"
                >
                  <CheckCircle v-if="copiedMessageIndex === index" :size="16" class="text-green-600" />
                  <Copy v-else :size="16" class="text-gray-400 hover:text-gray-600" />
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

            <button
              @click="sendMessage"
              :disabled="isLoading || !userInput.trim()"
              class="h-11 px-4 bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-medium rounded-xl hover:from-emerald-700 hover:to-teal-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-md hover:shadow-lg transition-all"
            >
              <Loader2 v-if="isLoading" :size="18" class="animate-spin" />
              <Send v-else :size="18" />
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
