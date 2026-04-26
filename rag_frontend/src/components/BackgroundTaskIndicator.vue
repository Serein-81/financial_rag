<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMultiAgentTaskStore } from '@/stores/multiAgentTask'
import { Loader2, Brain, X, ChevronRight, CheckCircle } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const taskStore = useMultiAgentTaskStore()

const hasTask = computed(() => taskStore.activeTask !== null)
const currentStage = computed(() => taskStore.activeTask?.currentStage || null)

const isCompleted = computed(() => 
  taskStore.activeTask !== null && 
  !taskStore.activeTask.isLoading && 
  taskStore.activeTask.currentStage === 'response'
)

const isMultiAgentPage = computed(() => route.name === 'multi-agent-chat')

const stageLabels: Record<string, string> = {
  receptionist: '接收输入',
  intent: '意图识别',
  specialists: '专家协作',
  reflection: '质量审核',
  response: '生成响应',
}

const stageColors: Record<string, string> = {
  receptionist: 'bg-blue-500',
  intent: 'bg-cyan-500',
  specialists: 'bg-teal-500',
  reflection: 'bg-green-500',
  response: 'bg-gray-500',
}

const backendToFrontendNodeMap: Record<string, string> = {
  'initializing': 'receptionist',
  'processing': 'specialists',
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

const taskProgress = computed(() => {
  if (!taskStore.activeTask) return 0
  
  const stageOrder = ['receptionist', 'intent', 'specialists', 'reflection', 'response']
  const mappedStage = mapBackendNodeToFrontend(taskStore.activeTask.currentStage)
  const currentIndex = mappedStage ? stageOrder.indexOf(mappedStage) : -1
  
  if (currentIndex === -1) {
    return 0
  }
  
  const stageProgress = [5, 25, 50, 80, 95]
  const progress = stageProgress[Math.min(currentIndex, stageProgress.length - 1)]
  
  if (!taskStore.activeTask.isLoading && currentIndex === stageOrder.length - 1) {
    return 100
  }
  return progress
})

function goToMultiAgent() {
  router.push('/multi-agent')
}

function dismissTask() {
  taskStore.clearTaskState()
}
</script>

<template>
  <Transition name="slide-up">
    <div 
      v-if="hasTask && !isMultiAgentPage"
      class="fixed bottom-4 right-4 z-50 max-w-sm bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden"
    >
      <div 
        class="px-4 py-3 flex items-center justify-between"
        :class="isCompleted ? 'bg-gradient-to-r from-green-500 to-emerald-600' : 'bg-gradient-to-r from-blue-600 to-cyan-600'"
      >
        <div class="flex items-center gap-2">
          <Loader2 v-if="!isCompleted" :size="18" class="text-white animate-spin" />
          <CheckCircle v-else :size="18" class="text-white" />
          <span class="text-white font-medium text-sm">{{ isCompleted ? '处理完成' : '后台任务运行中' }}</span>
        </div>
        <button 
          @click="dismissTask" 
          class="text-white/80 hover:text-white transition-colors"
        >
          <X :size="16" />
        </button>
      </div>
      
      <div class="p-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <Brain :size="16" class="text-blue-600" />
            <span class="text-sm font-medium text-gray-700">多智能体协作</span>
          </div>
          <span class="text-xs text-gray-500">{{ taskProgress }}%</span>
        </div>
        
        <div class="mb-3">
          <div class="flex justify-between text-xs text-gray-500 mb-1">
            <span>{{ isCompleted ? '已完成' : (currentStage ? stageLabels[currentStage] : '准备中') }}</span>
            <span>{{ taskProgress }}%</span>
          </div>
          <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div 
              class="h-full transition-all duration-300"
              :class="isCompleted ? 'bg-green-500' : (currentStage ? stageColors[currentStage] : 'bg-cyan-500')"
              :style="{ width: `${taskProgress}%` }"
            ></div>
          </div>
        </div>
        
        <button 
          @click="goToMultiAgent"
          class="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg transition-colors text-sm font-medium"
        >
          <span>{{ isCompleted ? '查看详情' : '查看进度' }}</span>
          <ChevronRight :size="16" />
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
  opacity: 0;
}
</style>