<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { useKnowledgeStore } from '@/stores/knowledge'
import { sessionApi } from '@/api/session'
import type { Session, SessionMessage } from '@/types'
import { formatChatTime } from '@/utils/time'
import {
  History,
  MessageSquare,
  Trash2,
  Clock,
  Search,
  ChevronRight,
  Loader2,
  AlertCircle
} from 'lucide-vue-next'

const router = useRouter()
const sessionStore = useSessionStore()
const knowledgeStore = useKnowledgeStore()

const isLoading = ref(false)
const error = ref('')
const searchQuery = ref('')
const selectedSession = ref<Session | null>(null)
const sessionMessages = ref<SessionMessage[]>([])

const sessions = computed(() => sessionStore.sessions)

const filteredSessions = computed(() => {
  if (!searchQuery.value.trim()) return sessions.value
  return sessions.value.filter(s =>
    s.title.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

onMounted(async () => {
  await loadSessions()
})

async function loadSessions() {
  try {
    isLoading.value = true
    error.value = ''
    await sessionStore.fetchSessions()
  } catch (err: any) {
    error.value = err.message || '加载会话列表失败'
  } finally {
    isLoading.value = false
  }
}

async function selectSession(session: Session) {
  try {
    selectedSession.value = session
    isLoading.value = true
    sessionMessages.value = await sessionApi.getSessionMessages(session.id)
  } catch (err: any) {
    error.value = err.message || '加载会话详情失败'
  } finally {
    isLoading.value = false
  }
}

async function deleteSession(sessionId: string) {
  if (!confirm('确定要删除这个会话吗？')) return

  try {
    isLoading.value = true
    await sessionStore.deleteSession(sessionId)
    if (selectedSession.value?.id === sessionId) {
      selectedSession.value = null
      sessionMessages.value = []
    }
  } catch (err: any) {
    error.value = err.message || '删除会话失败'
  } finally {
    isLoading.value = false
  }
}

function continueChat(sessionId: string) {
  sessionStore.setCurrentSession(sessionId)
  router.push('/')
}

function getMessagePreview(messages: SessionMessage[]): string {
  const lastMessage = messages[messages.length - 1]
  if (!lastMessage) return '暂无消息'
  return lastMessage.content.slice(0, 50) + (lastMessage.content.length > 50 ? '...' : '')
}
</script>

<template>
  <div class="h-full flex">
    <!-- Session List -->
    <div class="w-80 bg-white border-r border-gray-200 flex flex-col">
      <div class="p-4 border-b border-gray-200">
        <div class="flex items-center gap-2 mb-4">
          <History :size="24" class="text-blue-600" />
          <h1 class="text-xl font-bold text-gray-900">会话历史</h1>
        </div>
        <div class="relative">
          <Search :size="18" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索会话..."
            class="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-500 outline-none"
          />
        </div>
      </div>

      <div v-if="error" class="p-4">
        <div class="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-sm text-red-700">
          <AlertCircle :size="16" />
          {{ error }}
        </div>
      </div>

      <div class="flex-1 overflow-y-auto">
        <div v-if="isLoading && sessions.length === 0" class="p-4 flex justify-center">
          <Loader2 :size="24" class="animate-spin text-blue-600" />
        </div>

        <div v-else-if="filteredSessions.length === 0" class="p-8 text-center">
          <MessageSquare :size="48" class="mx-auto text-gray-300 mb-3" />
          <p class="text-gray-500">暂无会话记录</p>
        </div>

        <div v-else class="p-2 space-y-1">
          <div
            v-for="session in filteredSessions"
            :key="session.id"
            :class="[
              'p-3 rounded-lg cursor-pointer transition-colors group',
              selectedSession?.id === session.id
                ? 'bg-blue-50 border border-blue-200'
                : 'hover:bg-gray-50'
            ]"
            @click="selectSession(session)"
          >
            <div class="flex items-start justify-between mb-1">
              <h3 class="font-medium text-gray-900 truncate flex-1">{{ session.title }}</h3>
              <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  @click.stop="deleteSession(session.id)"
                  class="p-1 hover:bg-red-100 rounded transition-colors"
                  title="删除会话"
                >
                  <Trash2 :size="14" class="text-red-500" />
                </button>
              </div>
            </div>
            <div class="flex items-center gap-2 text-xs text-gray-500">
              <Clock :size="12" />
              {{ formatChatTime(session.updated_at) }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Session Detail -->
    <div class="flex-1 flex flex-col bg-gray-50">
      <div v-if="!selectedSession" class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <MessageSquare :size="64" class="mx-auto text-gray-300 mb-4" />
          <p class="text-gray-500">选择一个会话查看详情</p>
        </div>
      </div>

      <template v-else>
        <div class="bg-white border-b border-gray-200 px-6 py-4">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="text-lg font-semibold text-gray-900">{{ selectedSession.title }}</h2>
              <p class="text-sm text-gray-500">创建于 {{ formatChatTime(selectedSession.created_at) }}</p>
            </div>
            <button
              @click="continueChat(selectedSession!.id)"
              class="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 flex items-center gap-2"
            >
              <MessageSquare :size="18" />
              继续对话
            </button>
          </div>
        </div>

        <div class="flex-1 overflow-y-auto p-6">
          <div class="max-w-4xl mx-auto space-y-4">
            <div
              v-for="(message, index) in sessionMessages"
              :key="index"
              :class="[
                'p-4 rounded-xl',
                message.role === 'user'
                  ? 'bg-blue-600 text-white ml-12'
                  : 'bg-white border border-gray-200 mr-12'
              ]"
            >
              <div class="flex items-center gap-2 mb-2">
                <span :class="[
                  'text-xs font-medium px-2 py-0.5 rounded',
                  message.role === 'user'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-600'
                ]">
                  {{ message.role === 'user' ? '用户' : 'AI' }}
                </span>
              </div>
              <p class="whitespace-pre-wrap">{{ message.content }}</p>

              <!-- Sources -->
              <div v-if="message.sources && message.sources.length > 0" class="mt-3 pt-3 border-t border-gray-200">
                <p class="text-xs font-medium mb-2">参考来源：</p>
                <div class="space-y-2">
                  <div
                    v-for="(source, sIndex) in message.sources"
                    :key="sIndex"
                    class="text-xs p-2 bg-gray-50 rounded"
                  >
                    <p class="font-medium text-gray-700">{{ source.filename }}</p>
                    <p class="text-gray-600 mt-1">{{ source.content }}</p>
                    <p class="text-gray-400 mt-1">相似度: {{ (source.score * 100).toFixed(1) }}%</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
