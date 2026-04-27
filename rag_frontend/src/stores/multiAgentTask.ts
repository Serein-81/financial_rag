import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

export interface TaskMessage {
  id: string
  role: 'user' | 'assistant'
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

export interface TaskState {
  id: string
  sessionId: string | null
  query: string
  messages: TaskMessage[]
  currentStage: string | null
  intentAnalysis: { category: string; confidence: number; strategy: string } | null
  activeSpecialists: string[]
  reflectionResult: string | null
  processingTime: number | null
  currentResponse: string
  isLoading: boolean
  enableReflection: boolean
  enableRAG: boolean
  startedAt: number
  lastUpdatedAt: number
}

export interface StreamProgress {
  stage: string
  timestamp: string
  data?: any
}

const TASK_STORAGE_KEY = 'multi_agent_active_task'

export const useMultiAgentTaskStore = defineStore('multiAgentTask', () => {
  const authStore = useAuthStore()
  
  const activeTask = ref<TaskState | null>(null)
  const isStreamActive = ref(false)
  const abortController = ref<AbortController | null>(null)
  const streamReader = ref<ReadableStreamDefaultReader<Uint8Array> | null>(null)
  const progressEvents = ref<StreamProgress[]>([])
  
  const hasActiveTask = computed(() => activeTask.value !== null && isStreamActive.value)
  const taskProgress = computed(() => {
    if (!activeTask.value) return 0
    const stageOrder = ['receptionist', 'intent', 'specialists', 'reflection', 'response']
    const currentIndex = activeTask.value.currentStage 
      ? stageOrder.indexOf(activeTask.value.currentStage) 
      : -1
    if (currentIndex === -1) return 0
    const stageProgress = [5, 25, 50, 80, 95]
    const progress = stageProgress[Math.min(currentIndex, stageProgress.length - 1)]
    if (!activeTask.value.isLoading && currentIndex === stageOrder.length - 1) {
      return 100
    }
    return progress
  })

  function generateTaskId(): string {
    return `task_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
  }

  function initTask(params: {
    query: string
    sessionId: string | null
    enableReflection: boolean
    enableRAG: boolean
  }): TaskState {
    const taskId = generateTaskId()
    
    const userMsg: TaskMessage = {
      id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      role: 'user',
      content: params.query,
      timestamp: new Date(),
    }
    
    const assistantMsg: TaskMessage = {
      id: `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    }
    
    activeTask.value = {
      id: taskId,
      sessionId: params.sessionId,
      query: params.query,
      messages: [userMsg, assistantMsg],
      currentStage: null,
      intentAnalysis: null,
      activeSpecialists: [],
      reflectionResult: null,
      processingTime: null,
      currentResponse: '',
      isLoading: true,
      enableReflection: params.enableReflection,
      enableRAG: params.enableRAG,
      startedAt: Date.now(),
      lastUpdatedAt: Date.now(),
    }
    
    isStreamActive.value = true
    saveTaskState()
    
    return activeTask.value
  }

  function updateTaskProgress(stage: string, data?: any) {
    if (!activeTask.value) return
    
    activeTask.value.currentStage = stage
    activeTask.value.lastUpdatedAt = Date.now()
    
    progressEvents.value.push({
      stage,
      timestamp: new Date().toISOString(),
      data,
    })
    
    if (data?.specialists) {
      activeTask.value.activeSpecialists = data.specialists
    }
    
    saveTaskState()
  }

  function appendResponseContent(content: string) {
    if (!activeTask.value) return
    
    activeTask.value.currentResponse += content
    
    const assistantMsg = activeTask.value.messages[activeTask.value.messages.length - 1]
    if (assistantMsg && assistantMsg.role === 'assistant') {
      assistantMsg.content = activeTask.value.currentResponse
    }
    
    activeTask.value.lastUpdatedAt = Date.now()
    saveTaskState()
  }

  function completeTask(finalContent: string, metadata?: {
    intent?: { category: string; confidence: number; routing_strategy: string }
    specialists?: string[]
    needs_human_review?: boolean
    processing_time?: number
  }) {
    if (!activeTask.value) return

    activeTask.value.isLoading = false
    activeTask.value.currentStage = 'response'
    activeTask.value.currentResponse = finalContent
    
    const assistantMsg = activeTask.value.messages[activeTask.value.messages.length - 1]
    if (assistantMsg && assistantMsg.role === 'assistant') {
      assistantMsg.content = finalContent
      if (metadata) {
        assistantMsg.intent = metadata.intent
        assistantMsg.specialists = metadata.specialists
        assistantMsg.needs_human_review = metadata.needs_human_review
        assistantMsg.processing_time = metadata.processing_time
      }
    }
    
    activeTask.value.intentAnalysis = metadata?.intent || activeTask.value.intentAnalysis
    activeTask.value.processingTime = metadata?.processing_time || null
    
    if (metadata?.specialists) {
      activeTask.value.activeSpecialists = metadata.specialists
    }
    if (metadata?.needs_human_review !== undefined) {
      activeTask.value.reflectionResult = metadata.needs_human_review ? '需要人工审核' : null
    }
    
    isStreamActive.value = false
    saveTaskState()
  }

  function failTask(error: string, partialContent?: string) {
    if (!activeTask.value) return
    
    activeTask.value.isLoading = false
    
    if (partialContent) {
      activeTask.value.currentResponse = partialContent
      const assistantMsg = activeTask.value.messages[activeTask.value.messages.length - 1]
      if (assistantMsg && assistantMsg.role === 'assistant') {
        assistantMsg.content = partialContent
      }
    }
    
    isStreamActive.value = false
    clearTaskState()
  }

  function setIntentAnalysis(category: string, confidence: number, strategy: string) {
    if (!activeTask.value) return
    
    activeTask.value.intentAnalysis = { category, confidence, strategy }
    activeTask.value.lastUpdatedAt = Date.now()
    saveTaskState()
  }

  function setReflectionResult(result: string) {
    if (!activeTask.value) return
    
    activeTask.value.reflectionResult = result
    activeTask.value.lastUpdatedAt = Date.now()
    saveTaskState()
  }

  function getAbortController(): AbortController {
    if (abortController.value) {
      abortController.value.abort()
    }
    abortController.value = new AbortController()
    return abortController.value
  }

  function abortStream() {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    if (streamReader.value) {
      streamReader.value.cancel()
      streamReader.value = null
    }
    isStreamActive.value = false
    saveTaskState()
  }

  function saveTaskState() {
    if (!activeTask.value) return
    
    try {
      const stateToSave = {
        ...activeTask.value,
        messages: activeTask.value.messages.map(m => ({
          ...m,
          timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : m.timestamp,
        })),
      }
      localStorage.setItem(TASK_STORAGE_KEY, JSON.stringify(stateToSave))
    } catch (e) {
      console.error('Failed to save task state:', e)
    }
  }

  function loadTaskState(): TaskState | null {
    try {
      const saved = localStorage.getItem(TASK_STORAGE_KEY)
      if (!saved) return null
      
      const state = JSON.parse(saved) as TaskState & { messages: TaskMessage[] }
      
      state.messages = state.messages.map(m => ({
        ...m,
        timestamp: new Date(m.timestamp),
      }))
      
      return state
    } catch (e) {
      console.error('Failed to load task state:', e)
      return null
    }
  }

  function restoreTask(): TaskState | null {
    const savedState = loadTaskState()
    if (!savedState) return null
    
    if (savedState.isLoading) {
      activeTask.value = savedState
      return savedState
    }
    
    clearTaskState()
    return null
  }

  function clearTaskState() {
    activeTask.value = null
    localStorage.removeItem(TASK_STORAGE_KEY)
    progressEvents.value = []
  }

  function getTaskState(): TaskState | null {
    return activeTask.value
  }

  return {
    activeTask,
    isStreamActive,
    abortController,
    streamReader,
    progressEvents,
    hasActiveTask,
    taskProgress,
    initTask,
    updateTaskProgress,
    appendResponseContent,
    completeTask,
    failTask,
    setIntentAnalysis,
    setReflectionResult,
    getAbortController,
    abortStream,
    saveTaskState,
    loadTaskState,
    restoreTask,
    clearTaskState,
    getTaskState,
  }
})