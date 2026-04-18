<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useAuthStore } from '@/stores/auth'
import { chatApi } from '@/api/chat'
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
  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
  const highlighted = hljs.highlight(code, { language }).value
  return `<pre class="hljs"><div class="code-header"><span class="code-lang">${language}</span><button class="copy-btn" onclick="navigator.clipboard.writeText(this.closest('pre').querySelector('code').textContent)"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> 复制</button></div><code class="language-${language}">${highlighted}</code></pre>`
}
marked.use({ renderer })

const sessionStore = useSessionStore()
const knowledgeStore = useKnowledgeStore()
const authStore = useAuthStore()

const userInput = ref('')
const isLoading = ref(false)
const chatContainerRef = ref<HTMLDivElement>()
const showKBModal = ref(false)
const newKBName = ref('')
const newKBDesc = ref('')

const selectedFile = ref<File | null>(null)
const isUploading = ref(false)
const uploadResult = ref<any>(null)

const sourcesCollapsed = ref<Map<number, boolean>>(new Map())
const copiedMessageIndex = ref<number | null>(null)
const likedMessages = ref<Set<number>>(new Set())
const showSessionsPanel = ref(false)
const streamingContent = ref<Map<number, string>>(new Map())

const messages = computed(() => sessionStore.currentMessages)
const sessions = computed(() => sessionStore.sessions)
const knowledgeBases = computed(() => knowledgeStore.knowledgeBases)
const selectedKB = computed(() => knowledgeStore.selectedKnowledgeBase)

onMounted(async () => {
  await Promise.all([
    sessionStore.fetchSessions(),
    knowledgeStore.fetchKnowledgeBases()
  ])
})

watch(() => selectedKB.value?.id, async (newId) => {
  if (newId) {
    await knowledgeStore.fetchDocuments(newId)
  }
})

async function sendMessage() {
  if (!userInput.value.trim() || isLoading.value) return
  if (!selectedKB.value) {
    alert('请先选择一个知识库')
    return
  }

  const query = userInput.value.trim()
  userInput.value = ''

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

  isLoading.value = true
  scrollToBottom()

  try {
    let aiContent = ''
    let currentSources: any[] = []

    for await (const event of chatApi.streamAgentChat({
      query,
      kb_id: selectedKB.value.id,
      session_id: sessionStore.currentSessionId || undefined,
    })) {
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
            // 更新消息的sources，并默认折叠
            if (currentSources.length > 0) {
              const msgIndex = sessionStore.currentMessages.length - 1
              sessionStore.updateLastMessage('', currentSources)
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
        // 直接处理sources类型的事件
        currentSources = event.sources
        if (currentSources.length > 0) {
          const msgIndex = sessionStore.currentMessages.length - 1
          sessionStore.updateLastMessage('', currentSources)
          sourcesCollapsed.value.set(msgIndex, true) // 默认折叠
        }
      } else if (event.type === 'done') {
        console.log('✅ Agent 回答完成')
      }
    }
  } catch (error) {
    console.error('Error:', error)
    sessionStore.updateLastMessage('抱歉，发生了错误，请稍后重试。')
  } finally {
    isLoading.value = false
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight
    }
  })
}

async function loadSession(sessionId: string) {
  try {
    await sessionStore.loadSession(sessionId)
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

function toggleSessionsPanel() {
  showSessionsPanel.value = !showSessionsPanel.value
  if (showSessionsPanel.value) {
    sessionStore.fetchSessions()
  }
}

async function loadSessionFromHistory(sessionId: string) {
  try {
    await sessionStore.loadSession(sessionId)
    showSessionsPanel.value = false
  } catch (error) {
    console.error('加载会话失败:', error)
  }
}

function createNewChat() {
  sessionStore.createNewSession()
  sessionStore.fetchSessions()
}
</script>

<template>
  <div class="h-full flex bg-gray-50">
    <!-- Sessions History Panel -->
    <Transition name="slide">
      <div v-if="showSessionsPanel" class="w-80 bg-white border-r border-gray-200 flex flex-col">
        <div class="p-4 border-b border-gray-200">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <History :size="20" class="text-emerald-600" />
              <h3 class="font-semibold text-gray-900">会话历史</h3>
            </div>
            <button @click="toggleSessionsPanel" class="p-1 hover:bg-gray-100 rounded">
              <X :size="18" class="text-gray-500" />
            </button>
          </div>
          <button
            @click="createNewChat"
            class="w-full px-3 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 flex items-center justify-center gap-2 text-sm font-medium"
          >
            <Plus :size="16" />
            新建对话
          </button>
        </div>

        <div class="flex-1 overflow-y-auto">
          <div v-if="sessions.length === 0" class="p-4 text-center text-gray-500 text-sm">
            暂无会话记录
          </div>
          <div v-else class="p-2 space-y-1">
            <div
              v-for="session in sessions"
              :key="session.id"
              class="p-3 rounded-lg cursor-pointer transition-colors hover:bg-gray-50"
              :class="sessionStore.currentSessionId === session.id ? 'bg-emerald-50 border border-emerald-200' : ''"
              @click="loadSessionFromHistory(session.id)"
            >
              <div class="flex items-start justify-between mb-1">
                <h4 class="font-medium text-gray-900 truncate flex-1 text-sm">{{ session.title }}</h4>
              </div>
              <div class="flex items-center gap-2 text-xs text-gray-500">
                <Clock :size="12" />
                {{ formatChatTime(session.updated_at) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Chat Area -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Messages -->
      <div ref="chatContainerRef" class="flex-1 overflow-y-auto p-6 space-y-6">
        <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center">
          <div class="absolute top-4 right-4">
            <button
              @click="toggleSessionsPanel"
              class="px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-2 text-sm text-gray-700 shadow-sm"
            >
              <History :size="16" />
              查看历史会话
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
              <div class="bg-zinc-800 text-white px-4 py-3 rounded-2xl rounded-br-md max-w-xl shadow-sm">
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
                <div v-if="message.content" class="prose prose-sm max-w-none" v-html="renderMarkdown(message.content)"></div>
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
      </div>

      <!-- Input Area -->
      <div class="bg-white border-t border-gray-200 p-4">
        <div class="max-w-3xl mx-auto">
          <!-- Toolbar -->
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <button
                @click="toggleSessionsPanel"
                class="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg flex items-center gap-2 transition-colors"
              >
                <History :size="16" />
                历史会话
              </button>
              <button
                @click="createNewChat"
                class="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg flex items-center gap-2 transition-colors"
              >
                <Plus :size="16" />
                新对话
              </button>
            </div>
            <div v-if="sessionStore.currentSessionId" class="text-xs text-gray-500">
              当前会话: {{ sessionStore.currentSession?.title || '未命名' }}
            </div>
          </div>

          <div class="flex gap-3">
            <div class="flex-1 flex items-center gap-3 bg-slate-50 rounded-xl px-4 py-3 border border-slate-200 focus-within:border-emerald-500 focus-within:ring-2 focus-within:ring-emerald-200 transition-all">
              <Database :size="20" class="text-gray-400" />

              <select
                v-model="knowledgeStore.selectedKnowledgeBaseId"
                class="flex-1 bg-transparent border-none outline-none text-gray-900"
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

              <button
                @click="showKBModal = true"
                class="p-1 hover:bg-gray-200 rounded transition-colors"
                title="创建新知识库"
              >
                <Plus :size="18" class="text-gray-500" />
              </button>
            </div>

            <textarea
              v-model="userInput"
              rows="1"
              placeholder="输入你的问题..."
              class="w-96 px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none resize-none"
              @keydown.enter.exact.prevent="sendMessage"
              :disabled="isLoading"
            />

            <button
              @click="sendMessage"
              :disabled="isLoading || !userInput.trim()"
              class="px-5 py-3 bg-emerald-600 text-white font-medium rounded-xl hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Loader2 v-if="isLoading" :size="18" class="animate-spin" />
              <Send v-else :size="18" />
            </button>
          </div>

          <div class="flex items-center justify-between mt-3 text-xs text-gray-500">
            <span>按 Enter 发送，Shift + Enter 换行</span>
            <span>{{ messages.length }} 条消息</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Sessions Sidebar - Always visible -->
    <div class="w-72 bg-white border-l border-gray-200 flex flex-col">
      <div class="p-4 border-b border-gray-200">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <History :size="18" class="text-emerald-600" />
            <h2 class="font-semibold text-gray-900">会话列表</h2>
          </div>
          <button
            @click="createNewSession"
            class="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
            title="新建会话"
          >
            <Plus :size="18" class="text-gray-500" />
          </button>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto">
        <div v-if="sessions.length === 0" class="p-4 text-center text-gray-500 text-sm">
          暂无会话记录
        </div>
        <div v-else class="p-2 space-y-1">
          <div
            v-for="session in sessions"
            :key="session.id"
            :class="[
              'p-3 rounded-lg cursor-pointer transition-colors group',
              sessionStore.currentSessionId === session.id
                ? 'bg-emerald-50 border border-emerald-200'
                : 'hover:bg-gray-50'
            ]"
            @click="loadSession(session.id)"
          >
            <div class="flex items-start justify-between mb-1">
              <h3 class="font-medium text-gray-900 text-sm truncate flex-1">{{ session.title }}</h3>
              <button
                @click.stop="deleteSession(session.id)"
                class="p-1 hover:bg-red-100 rounded transition-colors opacity-0 group-hover:opacity-100"
              >
                <Trash2 :size="14" class="text-red-500" />
              </button>
            </div>
            <p class="text-xs text-gray-500">
              {{ formatChatTime(session.updated_at) }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Create KB Modal -->
    <div
      v-if="showKBModal"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showKBModal = false"
    >
      <div class="bg-white rounded-xl p-6 w-full max-w-md">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-gray-900">创建知识库</h3>
          <button @click="showKBModal = false" class="p-1 hover:bg-gray-100 rounded">
            <X :size="20" class="text-gray-500" />
          </button>
        </div>

        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">知识库名称</label>
            <input
              v-model="newKBName"
              type="text"
              placeholder="输入知识库名称"
              class="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">描述（可选）</label>
            <textarea
              v-model="newKBDesc"
              rows="3"
              placeholder="输入知识库描述"
              class="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none resize-none"
            />
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button
            @click="showKBModal = false"
            class="px-4 py-2 text-gray-700 font-medium rounded-lg hover:bg-gray-100"
          >
            取消
          </button>
          <button
            @click="createKnowledgeBase"
            class="px-4 py-2 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700"
          >
            创建
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(-100%);
}

/* 消息列表动画 */
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
</style>
