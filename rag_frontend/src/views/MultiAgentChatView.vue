﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿<script setup lang="ts">

import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'

import { useAuthStore } from '@/stores/auth'
import { useMultiAgentTaskStore } from '@/stores/multiAgentTask'

import {
  Send,
  Sparkles,
  Bot,
  Users,
  Brain,
  FileSearch,
  CheckCircle,
  Loader2,
  User,
  Clock,
  ChevronRight,
  AlertTriangle,
  Zap,
  MessageSquare,
  Settings,
  Copy,
  Check,
  RefreshCw,
  TrendingUp,
  Shield,
  Lightbulb,
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



renderer.code = function({ text, lang }: { text: string; lang?: string }) {

  const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'

  const highlighted = hljs.highlight(text, { language }).value

  return `<pre class="hljs"><div class="code-header"><span class="code-lang">${language}</span><button class="copy-btn" onclick="navigator.clipboard.writeText(this.closest('pre').querySelector('code').textContent)"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> 复制</button></div><code class="language-${language}">${highlighted}</code></pre>`

}



marked.use({ renderer })



interface Message {

  id: string

  role: 'user' | 'assistant' | 'system'

  content: string

  timestamp: Date

  intent?: {

    category: string

    confidence: number

    routing_strategy: string

  }

  specialists?: string[]

  needs_human_review?: boolean

  processing_time?: number

}



interface AgentStage {

  id: string

  name: string

  icon: any

  status: 'pending' | 'active' | 'completed' | 'error'

  description: string

}



const authStore = useAuthStore()
const taskStore = useMultiAgentTaskStore()

const userInput = ref('')
const isLoading = ref(false)
const chatContainerRef = ref<HTMLDivElement>()
const copiedMessageIndex = ref<number | null>(null)
const sessionId = ref<string | null>(null)
const streamInterrupted = ref(false)
const backgroundTaskActive = computed(() => taskStore.hasActiveTask)



const messages = ref<Message[]>([])

const currentResponse = ref('')

const showSettings = ref(false)

const enableReflection = ref(true)

const enableRAG = ref(true)



const currentStage = ref<string | null>(null)

const intentAnalysis = ref<{ category: string; confidence: number; strategy: string } | null>(null)

const activeSpecialists = ref<string[]>([])

const reflectionResult = ref<string | null>(null)
const processingTime = ref<number | null>(null)
const ttftMs = ref<number | null>(null)
const latencySummary = ref<any>(null)
const cacheHitDetected = ref(false)
const progressEvents = ref<any[]>([])



const agentStages: AgentStage[] = [

  { id: 'receptionist', name: '接待Agent', icon: MessageSquare, status: 'pending', description: '接收用户输入' },

  { id: 'intent', name: '意图识别', icon: Brain, status: 'pending', description: '分析问题类型和意图' },

  { id: 'specialists', name: '专业Agent', icon: Users, status: 'pending', description: '多专家协作处理' },

  { id: 'reflection', name: '反思审核', icon: Shield, status: 'pending', description: '质量审核与优化' },

  { id: 'response', name: '生成响应', icon: Sparkles, status: 'pending', description: '整合结果返回' },

]



// 后端节点名称映射到前端节点名称
const backendToFrontendNodeMap: Record<string, string> = {
  'initializing': 'receptionist',
  'processing': 'specialists',  // processing 阶段通常是专家处理阶段
  'intent_analysis': 'intent',
  'executing': 'specialists',
  'executing_specialists': 'specialists',
  'reflection': 'reflection',
  'completed': 'response',
  'clarification': 'intent'
}

function mapBackendNodeToFrontend(node: string | null): string {
  if (!node) return ''
  return backendToFrontendNodeMap[node] || node
}

function getStageStatus(stageId: string): AgentStage['status'] {
  const stageOrder = ['receptionist', 'intent', 'specialists', 'reflection', 'response']
  const currentIndex = currentStage.value ? stageOrder.indexOf(currentStage.value) : -1
  const stageIndex = stageOrder.indexOf(stageId)

  if (stageIndex < currentIndex) return 'completed'
  
  if (stageIndex === currentIndex) {
    if (!isLoading.value && currentStage.value === 'response') {
      return 'completed'
    }
    return 'active'
  }
  
  return 'pending'
}



const progressPercentage = computed(() => {
  const stageOrder = ['receptionist', 'intent', 'specialists', 'reflection', 'response']
  const mappedNode = mapBackendNodeToFrontend(currentStage.value)
  const currentIndex = mappedNode ? stageOrder.indexOf(mappedNode) : -1
  
  if (currentIndex === -1) {
    // 如果节点名称不在标准列表中，根据 progress_percent 推断进度
    // 异步接口返回的 progress_percent 可以直接使用
    const storedProgress = taskStore.taskProgress
    if (storedProgress > 0) {
      return storedProgress
    }
    return 0
  }
  
  const stageProgress = [5, 25, 50, 80, 95]
  const progress = stageProgress[Math.min(currentIndex, stageProgress.length - 1)]
  
  if (!isLoading.value && currentIndex === stageOrder.length - 1) {
    return 100
  }
  return progress
})



function getAgentName(stageId: string): string {

  const agentNames: Record<string, string> = {

    receptionist: '接待Agent',

    intent: '意图识别Agent',

    specialists: '专业Agent',

    reflection: '反思Agent',

    response: '生成Agent'

  }

  return agentNames[stageId] || stageId

}



function getAgentIcon(stageId: string) {

  const agentIcons: Record<string, any> = {

    receptionist: MessageSquare,

    intent: Brain,

    specialists: Users,

    reflection: Shield,

    response: Sparkles

  }

  return agentIcons[stageId] || Bot

}



const STORAGE_KEY = 'multi_agent_chat_state'

const SETTINGS_KEY = 'multi_agent_chat_settings'



function saveState() {

  const state = {

    messages: messages.value,

    sessionId: sessionId.value,

    currentStage: currentStage.value,

    intentAnalysis: intentAnalysis.value,

    activeSpecialists: activeSpecialists.value,

    reflectionResult: reflectionResult.value,

    processingTime: processingTime.value,

    currentResponse: currentResponse.value,

    isLoading: isLoading.value,

    savedAt: Date.now()

  }

  

  try {

    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))

  } catch (e) {

    console.error('保存状态失败', e)

  }

}



function loadState() {

  try {

    const savedState = sessionStorage.getItem(STORAGE_KEY)

    if (!savedState) return false

    

    const state = JSON.parse(savedState)

    

    if (state.messages && state.messages.length > 0) {

      messages.value = state.messages.map((msg: any) => ({

        ...msg,

        timestamp: new Date(msg.timestamp)

      }))

      sessionId.value = state.sessionId

      currentStage.value = state.currentStage

      intentAnalysis.value = state.intentAnalysis

      activeSpecialists.value = state.activeSpecialists || []

      reflectionResult.value = state.reflectionResult

      processingTime.value = state.processingTime

      currentResponse.value = state.currentResponse || ''

      

      const timeSinceSaved = Date.now() - state.savedAt

      if (timeSinceSaved > 5 * 60 * 1000) {

        console.log('会话已超时，清除旧状态')

        clearState()

        return false

      }

      

      if (state.isLoading && !state.currentStage) {

        console.log('检测到之前的请求被中断')

        streamInterrupted.value = true

        messages.value.push({

          id: createMessageId(),

          role: 'assistant',

          content: '⚠️ 之前的请求似乎被中断了。您可以继续输入新的问题，或者等待系统自动恢复',

          timestamp: new Date(),

        })

      } else if (state.isLoading) {

        streamInterrupted.value = true

        messages.value.push({

          id: createMessageId(),

          role: 'assistant',

          content: `之前的请求在「${currentStage.value}」阶段被中断。以下是已生成的部分内容：\n\n${state.currentResponse || '（无内容）'}`,

          timestamp: new Date(),

        })

      }

      

      return true

    }

    return false

  } catch (e) {

    console.error('加载状态失败', e)

    return false

  }

}



function loadSettings() {

  try {

    const savedSettings = localStorage.getItem(SETTINGS_KEY)

    if (savedSettings) {

      const settings = JSON.parse(savedSettings)

      enableReflection.value = settings.enableReflection ?? true

      enableRAG.value = settings.enableRAG ?? true

    }

  } catch (e) {

    console.error('加载设置失败:', e)

  }

}



function saveSettings() {

  try {

    const settings = {

      enableReflection: enableReflection.value,

      enableRAG: enableRAG.value

    }

    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))

  } catch (e) {

    console.error('保存设置失败:', e)

  }

}



function clearState() {

  try {

    sessionStorage.removeItem(STORAGE_KEY)

  } catch (e) {

    console.error('清除状态失败', e)

  }

}



async function scrollToBottom() {

  await nextTick()

  if (chatContainerRef.value) {

    chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight

  }

}



function createMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

function sanitizeErrorMessage(errorMsg: string | undefined | null): string {
  if (!errorMsg) return '未知错误，请稍后重试'
  
  const internalErrorPatterns = [
    '处理遇到问题:',
    '处理失败:',
    'AttributeError',
    "'NoneType'",
    'object has no attribute',
    '没有 attribute',
    'enable_report_generation',
    'enable_reflection',
    'enable_rag',
    'AgentOrchestrator',
    'orchestrator.',
    '配置加载失败',
    '智能体初始化'
  ]
  
  const isInternalError = internalErrorPatterns.some(pattern => errorMsg.includes(pattern))
  if (isInternalError) {
    if (errorMsg.includes('enable_report_generation') || 
        errorMsg.includes('enable_reflection') || 
        errorMsg.includes('enable_rag')) {
      return '系统配置加载失败，请刷新页面后重试'
    }
    if (errorMsg.includes('object has no attribute') || errorMsg.includes("'NoneType'")) {
      return '智能体初始化不完整，请稍后重试或刷新页面'
    }
    return '处理过程中遇到问题，请稍后重试'
  }
  
  if (errorMsg.length > 100) {
    return '处理过程中遇到问题，请稍后重试'
  }
  
  return errorMsg
}

onMounted(async () => {
  loadSettings()
  
  const hasRestoredState = loadState()
  
  if (hasRestoredState) {
    console.log('已恢复之前的会话状态')
    nextTick(() => {
      scrollToBottom()
    })
  }
  
  // 检查是否有进行中的后台任务
  const savedTask = taskStore.restoreTask()
  if (savedTask) {
    console.log('发现后台任务正在运行，正在同步状态...')
    
    sessionId.value = savedTask.sessionId
    messages.value = savedTask.messages.map(m => ({
      ...m,
      timestamp: new Date(m.timestamp),
    }))
    currentStage.value = savedTask.currentStage
    intentAnalysis.value = savedTask.intentAnalysis
    activeSpecialists.value = savedTask.activeSpecialists
    reflectionResult.value = savedTask.reflectionResult
    processingTime.value = savedTask.processingTime
    currentResponse.value = savedTask.currentResponse
    enableReflection.value = savedTask.enableReflection
    enableRAG.value = savedTask.enableRAG
    isLoading.value = true
    streamInterrupted.value = true
    
    nextTick(() => {
      scrollToBottom()
    })
    
    console.log('后台任务状态已同步，任务ID:', savedTask.id)
  }
  
  // 检查是否有异步任务需要恢复
  const taskResumeResult = await resumeTaskFromStorage()
  if (taskResumeResult) {
    console.log('发现异步任务需要恢复:', taskResumeResult.type)
    
    if (taskResumeResult.type === 'completed') {
      // 任务已完成，直接显示结果
      const status = taskResumeResult.data
      if (status.final_response) {
        // 创建完成的消息
        const completedMsg: Message = {
          id: createMessageId(),
          role: 'assistant',
          content: status.final_response,
          timestamp: new Date(),
        }
        messages.value.push(completedMsg)
        currentResponse.value = status.final_response
      }
    } else if (taskResumeResult.type === 'failed') {
      const status = taskResumeResult.data
      const errorMsg = sanitizeErrorMessage(status.error_message)
      const failedMsg: Message = {
        id: createMessageId(),
        role: 'assistant',
        content: `?**任务执行失败**\n\n${errorMsg}\n\n💡 请重新发起请求`,
        timestamp: new Date(),
      }
      messages.value.push(failedMsg)
    } else if (taskResumeResult.type === 'running') {
      // 任务进行中，恢复轮询
      const status = taskResumeResult.data
      currentThreadId = status.thread_id
      sessionId.value = status.thread_id
      
      // 恢复轮询
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg) {
        isLoading.value = true
        currentStage.value = status.current_node || 'processing'
        startPolling(lastMsg)
      }
    }
    
    nextTick(() => {
      scrollToBottom()
    })
  }
})



let stateSaveInterval: number | null = null



onBeforeUnmount(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
  if (stateSaveInterval) {
    clearInterval(stateSaveInterval)
  }
  taskStore.saveTaskState()
  saveState()
  saveSettings()
})



watch([messages, currentStage, intentAnalysis, activeSpecialists, reflectionResult, processingTime], () => {

  saveState()

}, { deep: true })



watch([enableReflection, enableRAG], () => {

  saveSettings()

})



// 轮询状态相关变量
let pollInterval: number | null = null
let currentTaskId: string | null = null
let currentThreadId: string | null = null


async function sendMessage() {
  if (!userInput.value.trim() || isLoading.value) return

  streamInterrupted.value = false
  const query = userInput.value.trim()
  userInput.value = ''

  const userMsg: Message = {
    id: createMessageId(),
    role: 'user',
    content: query,
    timestamp: new Date(),
  }
  messages.value.push(userMsg)

  const assistantMsg: Message = {
    id: createMessageId(),
    role: 'assistant',
    content: '',
    timestamp: new Date(),
  }
  messages.value.push(assistantMsg)

  isLoading.value = true
  resetAgentStages()
  currentResponse.value = ''
  scrollToBottom()

  try {
    const token = localStorage.getItem('rag_token')
    
    taskStore.initTask({
      query,
      sessionId: sessionId.value,
      enableReflection: enableReflection.value,
      enableRAG: enableRAG.value,
    })
    
    // 使用新的异步端点
    await submitAsyncQuery(query, assistantMsg)
    
  } catch (error: any) {
    console.error('请求错误:', error)
    
    let errorMessage = error.message || '未知错误'
    
    if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
      errorMessage = '网络连接失败，可能是服务器正在重启或不可访问'
    } else if (errorMessage.includes('timeout') || errorMessage.includes('Timeout')) {
      errorMessage = '请求超时，服务器处理时间过长，请稍后重试'
    } else if (errorMessage.includes('abort')) {
      errorMessage = '请求被取消或连接超时'
    }
    
    assistantMsg.content = `?**请求失败**\n\n${errorMessage}\n\n💡 **建议**：\n1. 检查服务器是否正在运行\n2. 稍后重试您的问题\n3. 如果问题持续存在，请联系管理员`
    taskStore.failTask(errorMessage, currentResponse.value)
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}


// 使用异步端点提交查询（支持页面切换不断开）
async function submitAsyncQuery(query: string, assistantMsg: Message) {
  const token = localStorage.getItem('rag_token')
  
  try {
    // 1. 提交任务到异步端点
    const response = await fetch('/api/v1/chat/orchestrator_chat_async', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
      },
      body: JSON.stringify({
        query,
        session_id: sessionId.value,
        enable_reflection: enableReflection.value,
        enable_rag: enableRAG.value,
      }),
    })
    
    if (!response.ok) {
      throw new Error(`服务器返回错误 HTTP ${response.status}`)
    }
    
    const result = await response.json()
    
    currentTaskId = result.task_id
    currentThreadId = result.thread_id
    sessionId.value = result.thread_id || result.session_id
    
    console.log('✅ 异步任务已提交:', result)
    
    // 2. 保存任务ID到 localStorage，用于页面刷新后恢复
    localStorage.setItem('multi_agent_task_id', currentTaskId)
    localStorage.setItem('multi_agent_thread_id', currentThreadId)
    
    // 3. 更新进度显示
    currentStage.value = 'receptionist'
    assistantMsg.content = '⏳ 任务已提交后台，正在处理中...\n\n请勿关闭此页面'
    
    // 4. 开始轮询状态
    startPolling(assistantMsg)
    
  } catch (error) {
    console.error('❌ 异步提交失败，回退到SSE模式:', error)
    // 如果异步端点失败，回退到SSE模式
    await submitWithSSE(query, assistantMsg)
  }
}


// 轮询任务状态
function startPolling(assistantMsg: Message) {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
  
  pollInterval = setInterval(async () => {
    try {
      const token = localStorage.getItem('rag_token')
      
      const response = await fetch(`/api/v1/agent-task/status/${currentThreadId}`, {
        headers: {
          ...(token && { 'Authorization': `Bearer ${token}` }),
        },
      })
      
      if (!response.ok) {
        console.error('轮询状态失败:', response.status)
        return
      }
      
      const status = await response.json()
      
      console.log('📊 轮询状态:', status.status, status.progress_percent + '%', status.current_node)
      
      // 更新进度显示
      updateProgressDisplay(status)
      
      // 优先检查追问状态
      if (status.needs_clarification && status.clarification_request) {
        clearInterval(pollInterval!)
        pollInterval = null
        
        const clarificationData = {
          question: status.clarification_request.question || '请详细描述您的问题',
          suggestions: status.clarification_request.suggestions || [],
          reason: status.clarification_request.reason || '您的输入需要更多信息来帮助您',
          required: status.clarification_request.required !== false,
          placeholder: status.clarification_request.placeholder || ''
        }
        
        showClarificationDialog(clarificationData)
        isLoading.value = false
        localStorage.removeItem('multi_agent_task_id')
        localStorage.removeItem('multi_agent_thread_id')
        return
      }
      
      // 根据状态处理
      if (status.status === 'completed') {
        clearInterval(pollInterval!)
        pollInterval = null
        
        // 任务完成，显示结果
        assistantMsg.content = status.final_response || '处理完成'
        currentResponse.value = status.final_response || ''
        currentStage.value = 'response'
        
        taskStore.completeTask(status.final_response, {
          intent: intentAnalysis.value ? {
            category: intentAnalysis.value.category,
            confidence: intentAnalysis.value.confidence,
            routing_strategy: intentAnalysis.value.strategy,
          } : undefined,
        })
        
        // 清理 localStorage
        localStorage.removeItem('multi_agent_task_id')
        localStorage.removeItem('multi_agent_thread_id')
        
      } else if (status.status === 'failed') {
        clearInterval(pollInterval!)
        pollInterval = null
        
        const errorMsg = sanitizeErrorMessage(status.error_message)
        assistantMsg.content = `?**任务执行失败**\n\n${errorMsg}\n\n💡 请稍后重试`
        taskStore.failTask(errorMsg, currentResponse.value)
        
        localStorage.removeItem('multi_agent_task_id')
        localStorage.removeItem('multi_agent_thread_id')
        
      } else if (status.status === 'cancelled') {
        clearInterval(pollInterval!)
        pollInterval = null
        
        assistantMsg.content = '❌ 任务已被取消'
        localStorage.removeItem('multi_agent_task_id')
        localStorage.removeItem('multi_agent_thread_id')
      }
      // running 或 pending 状态继续轮询
      
    } catch (error) {
      console.error('轮询请求失败:', error)
    }
  }, 2000) // 每2秒轮询一次
}


// 更新进度显示
function updateProgressDisplay(status: any) {
  if (status.current_node) {
    // 使用映射函数将后端节点名称转换为前端节点名称
    currentStage.value = mapBackendNodeToFrontend(status.current_node) || status.current_node
    
    if (status.progress_message) {
      currentResponse.value = status.progress_message
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.role === 'assistant' && !lastMsg.content) {
        lastMsg.content = `⏳ ${status.progress_message}`
      }
    }
    
    if (status.intent_analysis) {
      intentAnalysis.value = {
        category: status.intent_analysis.category || '分析中',
        confidence: status.intent_analysis.confidence || 0.5,
        strategy: status.intent_analysis.routing_strategy || 'multi_agent'
      }
    }
    
    if (status.specialist_progress) {
      activeSpecialists.value = Object.keys(status.specialist_progress)
    }
    
    // 如果有 progress_percent，也更新到 taskStore
    if (status.progress_percent !== undefined && status.progress_percent > 0) {
      taskStore.updateTaskProgress('progress', { percent: status.progress_percent })
    }
  }
}

// 恢复进行中的任务（页面加载时调用）
async function resumeTaskFromStorage() {
  const taskId = localStorage.getItem('multi_agent_task_id')
  const threadId = localStorage.getItem('multi_agent_thread_id')
  
  if (!taskId || !threadId) return null
  
  try {
    const token = localStorage.getItem('rag_token')
    
    const response = await fetch(`/api/v1/agent-task/status/${threadId}`, {
      headers: {
        ...(token && { 'Authorization': `Bearer ${token}` }),
      },
    })
    
    if (!response.ok) {
      localStorage.removeItem('multi_agent_task_id')
      localStorage.removeItem('multi_agent_thread_id')
      return null
    }
    
    const status = await response.json()
    
    if (status.status === 'completed') {
      // 任务已完成，返回结果
      localStorage.removeItem('multi_agent_task_id')
      localStorage.removeItem('multi_agent_thread_id')
      return { type: 'completed', data: status }
    } else if (status.status === 'failed') {
      // 任务失败
      localStorage.removeItem('multi_agent_task_id')
      localStorage.removeItem('multi_agent_thread_id')
      return { type: 'failed', data: status }
    } else {
      // 任务进行中，返回状态供恢复
      return { type: 'running', data: status }
    }
    
  } catch (error) {
    console.error('恢复任务失败:', error)
    localStorage.removeItem('multi_agent_task_id')
    localStorage.removeItem('multi_agent_thread_id')
    return null
  }
}


// SSE 模式（备用）
async function submitWithSSE(query: string, assistantMsg: Message) {
  const token = localStorage.getItem('rag_token')
  
  const controller = taskStore.getAbortController()
  const timeoutId = setTimeout(() => controller.abort(), 180000)

  const response = await fetch('/api/v1/chat/orchestrator_chat_stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
    },
    body: JSON.stringify({
      query,
      session_id: sessionId.value,
      enable_reflection: enableReflection.value,
      enable_rag: enableRAG.value,
    }),
    signal: controller.signal
  })

  clearTimeout(timeoutId)

  if (!response.ok) {
    throw new Error(`服务器返回错误 HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('无法读取响应')

  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let receivedDone = false

  while (true) {
    try {
      const { done, value } = await reader.read()
      
      if (done) {
        break
      }
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.trim() && line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            await handleStreamEvent(data)
            
            if (data.type === 'done') {
              receivedDone = true
            }
          } catch (e) {
            console.error('解析SSE事件失败:', e)
          }
        }
      }

    } catch (readError: any) {
      if (readError.name === 'AbortError') {
        throw new Error('请求超时（10分钟），服务器可能正在重启或处理时间过长')
      }
      throw readError
    }
  }

  try {
  if (!receivedDone && currentResponse.value) {
    assistantMsg.content = currentResponse.value + '\n\n⚠️ **连接意外中断**\n\n系统可能在处理过程中重启。请检查上方内容是否完整，如有需要可以重新发起请求'
  } else if (!receivedDone && !currentResponse.value) {
    throw new Error('连接意外中断，未收到任何响应')
  } else {
    if (sessionId.value) {
      assistantMsg.intent = intentAnalysis.value ? {
        category: intentAnalysis.value.category,
        confidence: intentAnalysis.value.confidence,
        routing_strategy: intentAnalysis.value.strategy,
      } : undefined
      assistantMsg.specialists = [...activeSpecialists.value]
      assistantMsg.needs_human_review = reflectionResult.value?.includes('需要人工审核') || false
      assistantMsg.processing_time = processingTime.value || undefined
    }
  }
  } catch (error: any) {
    console.error('流式请求错误:', error)
    
    let errorMessage = error.message || '未知错误'
    
    if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
      errorMessage = '网络连接失败，可能是服务器正在重启或不可访问'
    } else if (errorMessage.includes('timeout') || errorMessage.includes('Timeout')) {
      errorMessage = '请求超时，服务器处理时间过长，请稍后重试'
    } else if (errorMessage.includes('abort')) {
      errorMessage = '请求被取消或连接超时'
    }
    
    assistantMsg.content = `?**请求失败**\n\n${errorMessage}\n\n💡 **建议**：\n1. 检查服务器是否正在运行\n2. 稍后重试您的问题\n3. 如果问题持续存在，请联系管理员`
    taskStore.failTask(errorMessage, currentResponse.value)
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}



async function handleStreamEvent(data: any) {
  const lastMsg = messages.value[messages.value.length - 1]

  switch (data.type) {
    case 'init':
      sessionId.value = data.session_id
      break

    case 'stage':
      currentStage.value = data.stage
      taskStore.updateTaskProgress(data.stage, data)
      if (data.stage === 'intent' && data.intent) {
        intentAnalysis.value = {
          category: data.intent.category,
          confidence: data.intent.confidence,
          strategy: data.intent.routing_strategy,
        }
        taskStore.setIntentAnalysis(data.intent.category, data.intent.confidence, data.intent.routing_strategy)
      }
      if (data.stage === 'specialists' && data.specialists) {
        activeSpecialists.value = data.specialists
      }
      if (data.stage === 'reflection' && data.result) {
        reflectionResult.value = data.result
        taskStore.setReflectionResult(data.result)
      }
      break

    case 'text':
      currentResponse.value += data.content
      lastMsg.content = currentResponse.value
      taskStore.appendResponseContent(data.content)
      scrollToBottom()
      break

    case 'chunk':
      currentResponse.value += data.content
      lastMsg.content = currentResponse.value
      taskStore.appendResponseContent(data.content)
      scrollToBottom()
      break



    case 'sources':
      break

    case 'ttft':
      if (data.ttft_ms !== undefined) {
        ttftMs.value = data.ttft_ms
        console.log(`🎯 TTFT 事件: ${data.ttft_ms}ms, 阶段: ${data.stage}`)
      }
      // TTFT 消息不追加到响应内容，只记录日志
      break

    case 'cache_hit':
      cacheHitDetected.value = true
      console.log('💾 缓存命中！结果:', data.result)
      if (data.result) {
        currentResponse.value = typeof data.result === 'string' 
          ? data.result 
          : JSON.stringify(data.result)
        lastMsg.content = currentResponse.value
        taskStore.appendResponseContent(currentResponse.value)
      }
      if (data.latency_ms !== undefined) {
        console.log(`⏱️ 缓存响应延迟: ${data.latency_ms}ms`)
      }
      scrollToBottom()
      break

    case 'progress':
      progressEvents.value.push({
        timestamp: data.timestamp || new Date().toISOString(),
        completed_chunks: data.completed_chunks,
        stream_id: data.stream_id
      })
      console.log(`📊 进度更新: 已完成 ${data.completed_chunks} 个块`)
      break

    case 'thinking':
      // 智能体思考中，显示进度但不追加到最终响应
      console.log('🤔 智能体思考中:', data.message, '进度:', data.progress)
      // 思考消息只显示在控制台，不追加到响应内容
      break

    case 'done':
      currentStage.value = 'response'
      processingTime.value = data.processing_time
      taskStore.updateTaskProgress('response', data)
      if (data.latency_summary) {
        latencySummary.value = data.latency_summary
        console.log('📊 延迟摘要:', data.latency_summary)
      }
      if (data.from_cache) {
        cacheHitDetected.value = true
        console.log('💾 响应来自缓存')
      }
      lastMsg.content = currentResponse.value
      isLoading.value = false
      
      taskStore.completeTask(currentResponse.value, {
        intent: intentAnalysis.value ? {
          category: intentAnalysis.value.category,
          confidence: intentAnalysis.value.confidence,
          routing_strategy: intentAnalysis.value.strategy,
        } : undefined,
        specialists: [...activeSpecialists.value],
        needs_human_review: reflectionResult.value?.includes('需要人工审核') || false,
        processing_time: data.processing_time,
      })
      
      console.log('✅ 流式响应完成，处理时间:', data.processing_time, 'ms')
      break

    case 'error':
      console.error('❌ 流式响应错误:', data.error)
      lastMsg.content = `⚠️ **错误**: ${data.error}`
      isLoading.value = false
      break

    case 'clarification':
      console.log('💬 收到追问请求:', data.data)
      showClarificationDialog(data.data)
      break

    default:
      console.warn('⚠️ 未知的 SSE 事件类型:', data.type, data)
  }
}



function showClarificationDialog(data: any) {
  if (!data) return
  
  const question = data.question || '请详细描述您的问题'
  const suggestions = data.suggestions || []
  const reason = data.reason || ''
  const required = data.required !== false
  const placeholder = data.placeholder || ''
  
  isLoading.value = false
  
  const lastMsgIndex = messages.value.length - 1
  if (lastMsgIndex >= 0 && messages.value[lastMsgIndex].role === 'assistant') {
    messages.value[lastMsgIndex].content = ''
  }
  
  const clarificationHtml = `
    <div class="clarification-container">
      ${reason ? `<div class="reason-badge">💡 ${reason}</div>` : ''}
      <div class="question-text">${question}</div>
      ${suggestions.length > 0 ? `
        <div class="suggestions">
          ${suggestions.map((s: string) => `
            <button class="suggestion-btn" onclick="window.handleClarificationSelect('${s.replace(/'/g, "\\'")}')">${s}</button>
          `).join('')}
        </div>
      ` : ''}
      <div class="custom-input-section">
        <input 
          type="text" 
          id="clarification-input" 
          class="clarification-input" 
          placeholder="${placeholder || '或者直接输入您的具体问题...'}"
          onkeyup="if(event.key==='Enter') window.handleClarificationSubmit()"
        />
        <button class="submit-btn" onclick="window.handleClarificationSubmit()">发送</button>
      </div>
      ${required ? '' : '<button class="dismiss-btn" onclick="window.handleClarificationDismiss()">稍后再说</button>'}
    </div>
  `
  
  currentResponse.value = clarificationHtml
  if (messages.value[lastMsgIndex]) {
    messages.value[lastMsgIndex].content = clarificationHtml
  }
  
  window.handleClarificationSelect = (suggestion: string) => {
    handleUserClarification(suggestion)
  }
  
  window.handleClarificationSubmit = () => {
    const input = document.getElementById('clarification-input') as HTMLInputElement
    if (input && input.value.trim()) {
      handleUserClarification(input.value.trim())
    }
  }
  
  window.handleClarificationDismiss = () => {
    currentStage.value = null
    intentAnalysis.value = null
    resetAgentStages()
  }
  
  scrollToBottom()
}

function handleUserClarification(text: string) {
  delete window.handleClarificationSelect
  delete window.handleClarificationSubmit
  delete window.handleClarificationDismiss
  
  const userMsg: Message = {
    id: createMessageId(),
    role: 'user',
    content: text,
    timestamp: new Date(),
  }
  messages.value.push(userMsg)
  
  const assistantMsg: Message = {
    id: createMessageId(),
    role: 'assistant',
    content: '',
    timestamp: new Date(),
  }
  messages.value.push(assistantMsg)
  
  isLoading.value = true
  currentStage.value = null
  currentResponse.value = ''
  
  submitWithSSE(text, assistantMsg)
}

function resetAgentStages() {
  currentStage.value = null
  intentAnalysis.value = null
  activeSpecialists.value = []
  reflectionResult.value = null
  processingTime.value = null
  ttftMs.value = null
  latencySummary.value = null
  cacheHitDetected.value = false
  progressEvents.value = []
  streamInterrupted.value = false
}



function clearChat() {

  messages.value = []

  sessionId.value = null

  currentResponse.value = ''

  resetAgentStages()

  clearState()

}



function copyMessage(content: string, index: number) {

  navigator.clipboard.writeText(content)

  copiedMessageIndex.value = index

  setTimeout(() => {

    copiedMessageIndex.value = null

  }, 2000)

}



function getStageIcon(stage: AgentStage) {

  return stage.icon

}



function getStatusColor(status: AgentStage['status']) {

  switch (status) {

    case 'completed': return 'text-green-600 bg-green-50'

    case 'active': return 'text-blue-600 bg-blue-50 animate-pulse'

    case 'error': return 'text-red-600 bg-red-50'

    default: return 'text-gray-400 bg-gray-50'

  }

}



function getStatusIcon(status: AgentStage['status']) {

  switch (status) {

    case 'completed': return CheckCircle

    case 'active': return Loader2

    case 'error': return AlertCircle

    default: return Clock

  }

}



function renderMarkdown(content: string): string {
  try {
    const html = marked.parse(content) as string
    if (DOMPurify?.sanitize) {
      return DOMPurify.sanitize(html, {
        ALLOWED_TAGS: [
          'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
          'p', 'br', 'hr',
          'ul', 'ol', 'li',
          'strong', 'b', 'em', 'i', 'u', 's',
          'code', 'pre', 'kbd',
          'blockquote',
          'table', 'thead', 'tbody', 'tr', 'th', 'td',
          'a', 'img',
          'span', 'div'
        ],
        ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'id', 'style']
      }) || html || content
    }
    return html || content
  } catch {
    return content
  }
}

</script>



<template>

  <div class="flex h-full bg-gray-50 overflow-hidden">

    <div class="flex-1 flex flex-col min-h-0">

      <div class="bg-white border-b border-gray-200 px-6 py-4">

        <div class="flex items-center justify-between">

          <div class="flex items-center gap-3">

            <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-lg flex items-center justify-center">

              <Brain :size="20" class="text-white" />

            </div>

            <div>

              <h1 class="text-lg font-semibold text-gray-900">多智能体协作</h1>

              <p class="text-sm text-gray-500">多专家协作 · 智能路由 · 质量审核</p>

            </div>

          </div>

          <div class="flex items-center gap-3">

            <button

              @click="clearChat"

              class="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"

            >

              清空对话

            </button>

            <button

              @click="showSettings = !showSettings"

              class="p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"

            >

              <Settings :size="18" />

            </button>

          </div>

        </div>



        <div v-if="showSettings" class="mt-4 pt-4 border-t border-gray-100">

          <div class="flex items-center gap-6">

            <label class="flex items-center gap-2 cursor-pointer">

              <input

                type="checkbox"

                v-model="enableReflection"

                class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"

              />

              <span class="text-sm text-gray-700">启用反思审核</span>

            </label>

            <label class="flex items-center gap-2 cursor-pointer">

              <input

                type="checkbox"

                v-model="enableRAG"

                class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"

              />

              <span class="text-sm text-gray-700">启用知识检索</span>

            </label>

          </div>

        </div>

      </div>



      <div class="flex-1 overflow-y-auto p-4" ref="chatContainerRef">

        <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full space-y-5">
          <div class="w-20 h-20 bg-gradient-to-br from-blue-100 via-cyan-100 to-teal-100 rounded-full flex items-center justify-center shadow-xl">
            <Brain :size="40" class="text-blue-600" />
          </div>
          <div class="text-center space-y-2">
            <h2 class="text-xl font-bold text-gray-900 bg-gradient-to-r from-blue-600 to-cyan-600 bg-clip-text text-transparent">
              多智能体协作助手
            </h2>
            <p class="text-gray-500 text-sm max-w-lg">
              由多个专业智能体协作处理您的问题，自动路由到合适的专家，并进行质量审核
            </p>
          </div>
          <div class="flex flex-wrap justify-center gap-2 mt-3">
            <button
              v-for="example in ['分析企业税务风险', '财务健康诊断', '合同合规审查', '政策解读咨询']"
              :key="example"
              @click="userInput = example"
              class="px-4 py-2 bg-white border-2 border-blue-200 rounded-full text-sm text-gray-700 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-all shadow-sm hover:shadow-md"
            >
              {{ example }}
            </button>
          </div>
          <div class="mt-6 p-3 bg-gradient-to-r from-blue-50 to-cyan-50 rounded-xl max-w-2xl">
            <p class="text-xs text-gray-600 text-center">
              🚀 <strong>系统特点</strong>：智能路由 · 多专家协作 · 实时反思审核 · 高质量输出
            </p>
          </div>
        </div>



        <div v-else class="space-y-6 w-full px-6 lg:px-12">
          <div
            v-for="(msg, index) in messages"
            :key="msg.id"
            class="flex gap-4 animate-message"
            :class="msg.role === 'user' ? 'flex-row-reverse' : ''"
          >
            <div
              class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md overflow-hidden"
              :class="msg.role === 'user' ? 'bg-gradient-to-br from-blue-500 to-blue-600' : 'bg-gradient-to-br from-blue-500 to-cyan-600'"
            >
              <img
                v-if="msg.role === 'user' && authStore.avatarUrl"
                :src="authStore.avatarUrl"
                alt="User Avatar"
                class="w-full h-full object-cover"
                @error="(e) => { (e.target as HTMLImageElement).style.display = 'none' }"
              />
              <User v-else-if="msg.role === 'user'" :size="18" class="text-white" />
              <Bot v-else :size="18" class="text-white" />
            </div>

            <div class="flex flex-col max-w-[75%]" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
              <div class="flex items-center gap-2 mb-1" :class="msg.role === 'user' ? 'flex-row-reverse' : ''">
                <span class="text-sm font-medium text-gray-700">{{ msg.role === 'user' ? authStore.userName : 'AI助手' }}</span>
                <span class="text-xs text-gray-400">{{ formatChatTime(msg.timestamp) }}</span>
              </div>
              <div
                class="p-3 rounded-xl text-left shadow-sm hover:shadow-md transition-shadow"
                :class="msg.role === 'user' ? 'bg-blue-50 border border-blue-100' : 'bg-white border border-gray-200'"
              >
                <div v-if="msg.role === 'assistant' && msg.content" class="prose prose-sm max-w-none markdown-content" v-html="renderMarkdown(msg.content)"></div>
                <div v-else-if="msg.role === 'assistant' && isLoading && index === messages.length - 1" class="flex items-center gap-2 text-gray-500">
                  <Loader2 :size="16" class="animate-spin" />
                  <span>思考中...</span>
                </div>
                <div v-else class="text-gray-900" v-html="renderMarkdown(msg.content)"></div>
              </div>



              <div v-if="msg.role === 'assistant' && msg.intent" class="mt-2 flex flex-wrap gap-1.5 justify-start">
                <span
                  v-if="msg.intent.category"
                  class="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium"
                >
                  <Brain :size="10" />
                  {{ msg.intent.category }}
                </span>
                <span
                  v-if="msg.intent.confidence"
                  class="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium"
                >
                  <TrendingUp :size="10" />
                  {{ (msg.intent.confidence * 100).toFixed(0) }}%
                </span>
                <span
                  v-if="msg.needs_human_review"
                  class="inline-flex items-center gap-1 px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs font-medium"
                >
                  <AlertTriangle :size="10" />
                  需审核
                </span>
                <span
                  v-if="msg.processing_time"
                  class="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs font-medium"
                >
                  <Clock :size="10" />
                  {{ msg.processing_time }}ms
                </span>
                
                <span
                  v-if="ttftMs !== null"
                  class="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium"
                >
                  <Zap :size="10" />
                  TTFT: {{ ttftMs }}ms
                </span>
                
                <span
                  v-if="cacheHitDetected"
                  class="inline-flex items-center gap-1 px-2 py-0.5 bg-cyan-100 text-cyan-700 rounded text-xs font-medium"
                >
                  <CheckCircle :size="10" />
                  缓存
                </span>
              </div>

              <div v-if="msg.role === 'assistant' && msg.specialists?.length" class="mt-1.5 flex flex-wrap gap-1.5 justify-start">
                <span
                  v-for="specialist in msg.specialists"
                  :key="specialist"
                  class="inline-flex items-center gap-1 px-2 py-0.5 bg-cyan-100 text-cyan-700 rounded text-xs font-medium"
                >
                  <Users :size="10" />
                  {{ specialist }}
                </span>
              </div>

              <div class="mt-1.5 flex items-center gap-2 justify-start">
                <button
                  @click="copyMessage(msg.content, index)"
                  class="flex items-center gap-1 px-2 py-0.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-all text-xs"
                >
                  <Check v-if="copiedMessageIndex === index" :size="12" class="text-green-500" />
                  <Copy v-else :size="12" />
                  {{ copiedMessageIndex === index ? '已复制' : '复制' }}
                </button>
                <span class="text-xs text-gray-400">{{ formatChatTime(msg.timestamp) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>



      <div class="bg-gradient-to-t from-white to-gray-50 border-t border-gray-200 p-3">
        <div class="w-full px-6 lg:px-12">
          <div class="flex items-center gap-3 bg-white rounded-2xl border border-gray-200 p-3 shadow-sm hover:shadow-md transition-shadow">
            <textarea
              v-model="userInput"
              @keydown.enter.exact.prevent="sendMessage"
              placeholder="输入您的问题，多智能体系统会自动选择合适的专家处理..."
              class="flex-1 p-2 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-700 placeholder-gray-400 text-sm"
              rows="1"
            ></textarea>
            <button
              @click="sendMessage"
              :disabled="!userInput.trim() || isLoading"
              class="p-3 bg-gradient-to-r from-blue-600 to-cyan-600 text-white rounded-xl hover:from-blue-700 hover:to-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl disabled:shadow-none flex items-center justify-center min-w-[48px]"
            >
              <Loader2 v-if="isLoading" :size="20" class="animate-spin" />
              <Send v-else :size="20" />
            </button>
          </div>
          <div class="mt-2 flex items-center justify-between text-xs text-gray-500">
            <span>💡 Enter 发送 · Shift+Enter 换行</span>
            <div class="flex items-center gap-3">
              <span v-if="messages.length > 0" class="text-blue-600 font-medium">
                {{ Math.ceil(messages.length / 2) }} 轮对话
              </span>
              <span v-if="activeSpecialists.length > 0" class="text-cyan-600 font-medium">
                {{ activeSpecialists.length }} 个专家
              </span>
            </div>
          </div>
        </div>
      </div>

    </div>



    <div class="w-80 flex-shrink-0 bg-gradient-to-b from-white to-gray-50 border-l border-gray-200 flex flex-col h-full">
      <div class="p-4 border-b border-gray-200 bg-white relative overflow-hidden shrink-0">
        <div class="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-blue-500 via-cyan-500 to-teal-500 opacity-80"></div>

        <div class="flex items-center justify-between mb-3">
          <h3 class="font-bold text-gray-800 flex items-center gap-2">
            <div class="relative w-8 h-8 bg-gray-900 rounded-xl flex items-center justify-center shadow-lg border border-gray-700">
              <Brain :size="14" class="text-cyan-400" />
              <div v-if="isLoading" class="absolute inset-0 border border-cyan-500 rounded-xl animate-ping opacity-30"></div>
            </div>
            <div class="flex flex-col">
              <span class="text-sm tracking-widest text-gray-900">协同引擎</span>
              <span class="text-[10px] font-mono text-gray-400 mt-0.5">多智能体核心</span>
            </div>
          </h3>

          <div class="flex items-center">
            <span v-if="isLoading" class="flex items-center gap-1.5 px-2 py-1 bg-gray-900 border border-gray-700 text-cyan-400 text-[10px] font-mono rounded shadow-inner tracking-wider">
              <span class="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse shadow-[0_0_5px_rgba(6,182,212,0.8)]"></span>
              处理中
            </span>
            <span v-else-if="progressPercentage === 100" class="flex items-center gap-1.5 px-2 py-1 bg-gray-900 border border-gray-700 text-green-400 text-[10px] font-mono rounded shadow-inner tracking-wider">
              <span class="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_5px_rgba(34,197,94,0.8)]"></span>
              待机
            </span>
          </div>
        </div>

        <div v-if="currentStage" class="mt-2">
          <div class="flex items-center justify-between text-[10px] font-mono text-gray-500 uppercase tracking-wider mb-1.5">
            <span>系统负载</span>
            <span class="text-cyan-600 font-bold">{{ Math.round(progressPercentage) }}%</span>
          </div>
          <div class="relative w-full h-1.5 bg-gray-200 rounded-full overflow-hidden shadow-inner">
            <div 
              class="absolute top-0 left-0 h-full bg-gradient-to-r from-blue-500 via-cyan-500 to-teal-500 rounded-full transition-all duration-700 ease-out flex items-center justify-end" 
              :style="{ width: `${progressPercentage}%` }" 
            >
              <div class="w-3 h-full bg-white opacity-60 shadow-[0_0_10px_rgba(255,255,255,1)]"></div>
            </div>
          </div>
        </div>
      </div>



      <div class="flex-1 overflow-y-auto p-3">
        <div class="relative min-h-full flex flex-col justify-between pb-2">
          <div class="absolute left-[13.5px] top-4 bottom-8 w-[3px] bg-gray-100 rounded-full overflow-hidden">
            <div v-if="isLoading" class="w-full h-1/2 bg-gradient-to-b from-transparent via-cyan-400 to-transparent animate-pulse shadow-[0_0_8px_rgba(6,182,212,0.6)]" style="animation-duration: 1.2s;"></div>
          </div>

          <div
            v-for="(stage, index) in agentStages"
            :key="stage.id"
            class="relative flex items-start gap-2 group"
          >
            <div
              class="relative z-10 w-7 h-7 rounded flex items-center justify-center transition-all duration-300 shadow-sm"
              :class="[
                getStatusColor(getStageStatus(stage.id)),
                getStageStatus(stage.id) === 'active' ? 'ring-2 ring-blue-100 scale-105' : '',
                getStageStatus(stage.id) === 'completed' ? 'shadow-md' : ''
              ]"
            >
              <component
                :is="getStatusIcon(getStageStatus(stage.id))"
                :size="12"
                :class="{ 'animate-spin': getStageStatus(stage.id) === 'active' }"
              />
            </div>

            <div class="flex-1 pt-0.5 bg-white/50 group-hover:bg-white/80 transition-all rounded p-2 -ml-1 shadow-sm">
              <div class="flex items-center gap-1 mb-0.5">
                <span class="font-medium text-gray-900 text-xs">{{ stage.name }}</span>
                <CheckCircle
                  v-if="getStageStatus(stage.id) === 'completed'"
                  :size="10"
                  class="text-green-500"
                />
                <ChevronRight
                  v-if="getStageStatus(stage.id) === 'active'"
                  :size="10"
                  class="text-blue-500 animate-pulse"
                />
              </div>
              <p class="text-xs text-gray-500">{{ stage.description }}</p>

              <div v-if="getStageStatus(stage.id) === 'active'" class="mt-1.5">
                <div class="flex items-center gap-1 mb-1 p-1 bg-blue-50 rounded">
                  <component :is="getAgentIcon(stage.id)" :size="10" class="text-blue-600" />
                  <span class="text-xs text-blue-700 font-medium">{{ getAgentName(stage.id) }}</span>
                </div>
                <div class="flex items-center gap-1">
                  <span class="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
                  <span class="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
                  <span class="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
                  <span class="ml-1 text-xs text-blue-600">处理中...</span>
                </div>
              </div>

              <div v-if="getStageStatus(stage.id) === 'completed'" class="mt-1 animate-fadeIn space-y-1">
                <div v-if="stage.id === 'intent' && intentAnalysis" class="p-1 bg-gradient-to-br from-blue-50 to-blue-100 rounded border border-blue-200">
                  <div class="flex items-center justify-between mb-0.5">
                    <span class="text-xs font-medium text-blue-700">{{ intentAnalysis.category }}</span>
                    <span class="text-xs font-bold text-blue-900">{{ (intentAnalysis.confidence * 100).toFixed(0) }}%</span>
                  </div>
                  <div class="w-full bg-blue-200 rounded-full h-0.5">
                    <div 
                      class="bg-blue-600 h-0.5 rounded-full"
                      :style="{ width: `${intentAnalysis.confidence * 100}%` }"
                    ></div>
                  </div>
                </div>

                <div v-if="stage.id === 'specialists' && activeSpecialists.length" class="p-1 bg-gradient-to-br from-cyan-50 to-cyan-100 rounded border border-cyan-200">
                  <span class="text-xs font-medium text-cyan-700 block mb-0.5">已激活专家</span>
                  <div class="flex flex-wrap gap-0.5">
                    <span
                      v-for="specialist in activeSpecialists"
                      :key="specialist"
                      class="px-1 py-0.5 bg-cyan-200 text-cyan-800 rounded text-xs"
                    >
                      {{ specialist }}
                    </span>
                  </div>
                </div>

                <div v-if="stage.id === 'reflection' && reflectionResult" class="p-1 bg-gradient-to-br from-green-50 to-green-100 rounded border border-green-200">
                  <span class="text-xs font-medium text-green-700 block mb-0.5">审核结果</span>
                  <p class="text-xs text-green-900 line-clamp-2">{{ reflectionResult }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>



      <div v-if="messages.length > 0" class="p-3 border-t border-gray-200 space-y-2 shrink-0 bg-white">
        <div v-if="streamInterrupted" class="flex items-start gap-1.5 p-1.5 bg-yellow-50 rounded border border-yellow-200">
          <AlertTriangle :size="12" class="text-yellow-600 flex-shrink-0 mt-0.5" />
          <div class="flex-1">
            <p class="text-xs font-medium text-yellow-800 mb-0.5">⚠️ 请求被中断</p>
            <p class="text-xs text-yellow-700">系统已自动保存状态</p>
          </div>
        </div>
        
        <div class="grid grid-cols-2 gap-1.5">
          <div class="bg-gradient-to-br from-blue-50 to-blue-100 p-1.5 rounded">
            <div class="flex items-center gap-1 mb-0.5">
              <MessageSquare :size="10" class="text-blue-600" />
              <span class="text-xs text-blue-700 font-medium">轮次</span>
            </div>
            <p class="text-lg font-bold text-blue-900">{{ Math.ceil(messages.length / 2) }}</p>
          </div>
          
          <div class="bg-gradient-to-br from-cyan-50 to-cyan-100 p-1.5 rounded">
            <div class="flex items-center gap-1 mb-0.5">
              <Clock :size="10" class="text-cyan-600" />
              <span class="text-xs text-cyan-700 font-medium">耗时</span>
            </div>
            <p class="text-lg font-bold text-cyan-900">{{ processingTime ? `${processingTime}ms` : '-' }}</p>
          </div>
        </div>
        
        <div v-if="activeSpecialists.length > 0" class="bg-gradient-to-br from-cyan-50 to-cyan-100 p-1.5 rounded">
          <div class="flex items-center gap-1 mb-0.5">
            <Users :size="10" class="text-cyan-600" />
            <span class="text-xs text-cyan-700 font-medium">专业Agent</span>
          </div>
          <p class="text-sm font-bold text-cyan-900">{{ activeSpecialists.length }} 个</p>
          <p class="text-xs text-cyan-700 mt-0.5">{{ activeSpecialists.join('、') }}</p>
        </div>
        
        <div v-if="intentAnalysis" class="bg-gradient-to-br from-green-50 to-green-100 p-1.5 rounded">
          <div class="flex items-center gap-1 mb-0.5">
            <TrendingUp :size="10" class="text-green-600" />
            <span class="text-xs text-green-700 font-medium">意图识别</span>
          </div>
          <p class="text-xs font-semibold text-green-900 mb-0.5">{{ intentAnalysis.category }}</p>
          <div class="flex items-center justify-between">
            <span class="text-xs text-green-700">置信度</span>
            <span class="text-sm font-bold text-green-900">{{ (intentAnalysis.confidence * 100).toFixed(0) }}%</span>
          </div>
          <div class="w-full bg-green-200 rounded-full h-0.5 mt-1">
            <div 
              class="bg-green-600 h-0.5 rounded-full transition-all"
              :style="{ width: `${intentAnalysis.confidence * 100}%` }"
            ></div>
          </div>
        </div>
        
        <div class="grid grid-cols-2 gap-1.5">
          <div v-if="ttftMs !== null" class="bg-gradient-to-br from-amber-50 to-amber-100 p-1.5 rounded">
            <div class="flex items-center gap-1 mb-0.5">
              <Zap :size="10" class="text-amber-600" />
              <span class="text-xs text-amber-700 font-medium">TTFT</span>
            </div>
            <p class="text-sm font-bold text-amber-900">{{ ttftMs }}ms</p>
          </div>
          
          <div v-if="cacheHitDetected" class="bg-gradient-to-br from-cyan-50 to-cyan-100 p-1.5 rounded">
            <div class="flex items-center gap-1 mb-0.5">
              <CheckCircle :size="10" class="text-cyan-600" />
              <span class="text-xs text-cyan-700 font-medium">缓存</span>
            </div>
            <p class="text-sm font-bold text-cyan-900">命中</p>
          </div>
          
          <div v-if="latencySummary" class="col-span-2 bg-gradient-to-br from-teal-50 to-teal-100 p-1.5 rounded">
            <div class="flex items-center gap-1 mb-0.5">
              <TrendingUp :size="10" class="text-teal-600" />
              <span class="text-xs text-teal-700 font-medium">性能指标</span>
            </div>
            <div class="grid grid-cols-3 gap-1 mt-1">
              <div v-if="latencySummary.total_time" class="text-center">
                <p class="text-xs font-bold text-teal-900">{{ latencySummary.total_time }}ms</p>
                <p class="text-xs text-teal-700">总耗时</p>
              </div>
              <div v-if="latencySummary.llm_calls" class="text-center">
                <p class="text-xs font-bold text-teal-900">{{ latencySummary.llm_calls }}</p>
                <p class="text-xs text-teal-700">LLM调用</p>
              </div>
              <div v-if="latencySummary.retrieval_time" class="text-center">
                <p class="text-xs font-bold text-teal-900">{{ latencySummary.retrieval_time }}ms</p>
                <p class="text-xs text-teal-700">检索</p>
              </div>
            </div>
          </div>
        </div>
        
        <div v-if="reflectionResult" class="bg-gradient-to-br from-pink-50 to-pink-100 p-1.5 rounded">
          <div class="flex items-center gap-1 mb-0.5">
            <Shield :size="10" class="text-pink-600" />
            <span class="text-xs text-pink-700 font-medium">反思审核</span>
          </div>
          <p class="text-xs text-pink-900 line-clamp-2">{{ reflectionResult }}</p>
        </div>
        
        <div v-if="sessionId" class="bg-gradient-to-br from-gray-50 to-gray-100 p-1.5 rounded border border-gray-200">
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs text-gray-600 font-medium">会话信息</span>
            <span class="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">进行中</span>
          </div>
          <div class="space-y-0.5">
            <p class="text-xs text-gray-500">会话ID: <span class="font-mono text-gray-700">{{ sessionId.substring(0, 8) }}...</span></p>
            <p class="text-xs text-gray-500">消息数: <span class="font-semibold text-gray-700">{{ messages.length }}</span></p>
          </div>
        </div>
        
        <div class="pt-2 border-t border-gray-200">
          <p class="text-xs text-gray-500 mb-1.5 font-medium">快捷操作</p>
          <div class="grid grid-cols-2 gap-1.5">
            <button
              @click="clearChat"
              class="flex items-center justify-center gap-1 px-2 py-1.5 bg-white border border-gray-200 rounded text-xs text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-all"
            >
              <RefreshCw :size="10" />
              新建对话
            </button>
            <button
              @click="showSettings = !showSettings"
              class="flex items-center justify-center gap-1 px-2 py-1.5 bg-white border border-gray-200 rounded text-xs text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-all"
            >
              <Settings :size="10" />
              设置
            </button>
          </div>
        </div>
      </div>
      
      <div v-else class="p-3 border-t border-gray-200 space-y-2 shrink-0 bg-white">
        <div class="bg-gradient-to-br from-blue-50 to-cyan-50 p-3 rounded">
          <div class="flex items-center gap-2 mb-2">
            <Brain :size="14" class="text-blue-600" />
            <span class="text-xs font-medium text-blue-700">多智能体协作说明</span>
          </div>
          <div class="space-y-1.5 text-xs text-gray-600">
            <div class="flex items-start gap-1.5">
              <div class="w-4 h-4 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span class="text-blue-600 font-bold text-xs">1</span>
              </div>
              <p>接待Agent接收问题</p>
            </div>
            <div class="flex items-start gap-1.5">
              <div class="w-4 h-4 bg-cyan-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span class="text-cyan-600 font-bold text-xs">2</span>
              </div>
              <p>意图识别分析类型</p>
            </div>
            <div class="flex items-start gap-1.5">
              <div class="w-4 h-4 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span class="text-blue-600 font-bold text-xs">3</span>
              </div>
              <p>专业Agent协作处理</p>
            </div>
            <div class="flex items-start gap-1.5">
              <div class="w-4 h-4 bg-green-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                <span class="text-green-600 font-bold text-xs">4</span>
              </div>
              <p>反思审核确保质量</p>
            </div>
          </div>
        </div>
        
        <div class="bg-gradient-to-br from-amber-50 to-orange-50 p-2 rounded border border-amber-200">
          <div class="flex items-start gap-1.5">
            <Lightbulb :size="12" class="text-amber-600 flex-shrink-0 mt-0.5" />
            <div class="space-y-0.5">
              <p class="text-xs font-medium text-amber-800">使用建议</p>
              <p class="text-xs text-amber-700">尝试提出具体问题，如"分析某企业的税务风险"，系统会自动匹配最合适的专家Agent协作处理。</p>
            </div>
          </div>
        </div>
        
        <div class="grid grid-cols-2 gap-1.5">
          <div class="bg-white p-1.5 rounded border border-gray-200">
            <div class="flex items-center gap-1 mb-0.5">
              <FileSearch :size="10" class="text-blue-600" />
              <span class="text-xs font-medium text-gray-700">RAG检索</span>
            </div>
            <p class="text-xs text-gray-500">知识库检索</p>
          </div>
          <div class="bg-white p-1.5 rounded border border-gray-200">
            <div class="flex items-center gap-1 mb-0.5">
              <Shield :size="10" class="text-green-600" />
              <span class="text-xs font-medium text-gray-700">质量审核</span>
            </div>
            <p class="text-xs text-gray-500">AI反思机制</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>



<style>

@keyframes fadeIn {

  from { opacity: 0; transform: translateY(-4px); }

  to { opacity: 1; transform: translateY(0); }

}



.animate-fadeIn {

  animation: fadeIn 0.3s ease-out;

}



.line-clamp-3 {

  display: -webkit-box;

  -webkit-line-clamp: 3;

  -webkit-box-orient: vertical;

  overflow: hidden;

}



.markdown-content {

  line-height: 1.8 !important;

  letter-spacing: 0.02em;

}



.markdown-content h1,

.markdown-content h2,

.markdown-content h3,

.markdown-content h4,

.markdown-content h5,

.markdown-content h6 {

  margin-top: 1.5rem;

  margin-bottom: 0.75rem;

  font-weight: 600;

  line-height: 1.4;

}



.markdown-content p {

  margin-bottom: 1rem;

  line-height: 1.8;

}



.markdown-content ul,

.markdown-content ol {

  margin: 1rem 0;

  padding-left: 1.5rem;

}



.markdown-content li {

  margin: 0.5rem 0;

  line-height: 1.6;

}



.markdown-content blockquote {

  margin: 1rem 0;

  padding: 0.75rem 1rem;

  border-left: 4px solid #3b82f6;

  background-color: #f9fafb;

  font-style: italic;

}



.markdown-content pre {

  margin: 1rem 0;

  overflow-x: auto;

  background-color: #f6f8fa;

  border-radius: 0.375rem;

}



.markdown-content code {

  font-family: 'Courier New', Courier, monospace;

  background-color: #f3f4f6;

  padding: 0.125rem 0.25rem;

  border-radius: 0.25rem;

  font-size: 0.875em;

}



.markdown-content pre code {

  background-color: transparent;

  padding: 0;

}



.markdown-content hr {

  margin: 1.5rem 0;

  border: none;

  border-top: 1px solid #e5e7eb;

}



.markdown-content table {

  width: 100%;

  border-collapse: collapse;

  margin: 1rem 0;

}



.markdown-content th,

.markdown-content td {

  border: 1px solid #e5e7eb;

  padding: 0.5rem;

  text-align: left;

}



.markdown-content th {
  background-color: #f9fafb;
  font-weight: 600;
}

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

@keyframes clarificationPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.clarification-container {
  background: linear-gradient(135deg, #2563eb 0%, #0891b2 100%);
  border-radius: 16px;
  padding: 24px;
  color: white;
  margin: 16px 0;
  box-shadow: 0 10px 40px rgba(6, 145, 178, 0.3);
  animation: clarificationPulse 2s ease-in-out infinite;
}

.clarification-container .reason-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.15);
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  margin-bottom: 16px;
  width: fit-content;
}

.clarification-container .question-text {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
  line-height: 1.5;
}

.clarification-container .suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
}

.clarification-container .suggestion-btn {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.4);
  color: white;
  padding: 12px 20px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 14px;
  font-weight: 500;
}

.clarification-container .suggestion-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.clarification-container .custom-input-section {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}

.clarification-container .clarification-input {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  color: white;
  font-size: 14px;
  outline: none;
  transition: all 0.2s ease;
}

.clarification-container .clarification-input::placeholder {
  color: rgba(255, 255, 255, 0.6);
}

.clarification-container .clarification-input:focus {
  border-color: rgba(255, 255, 255, 0.6);
  background: rgba(255, 255, 255, 0.15);
}

.clarification-container .submit-btn {
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.9);
  color: #0891b2;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.clarification-container .submit-btn:hover {
  background: white;
  transform: scale(1.02);
}

.clarification-container .dismiss-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: rgba(255, 255, 255, 0.8);
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s ease;
  margin-top: 12px;
}

.clarification-container .dismiss-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}
</style>

