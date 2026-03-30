<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useGroupChatStore } from '@/stores/group-chat'
import { useAuthStore } from '@/stores/auth'
import {
  Users,
  Plus,
  Search,
  Settings,
  ChevronLeft,
  ChevronRight,
  Send,
  MoreVertical,
  UserPlus,
  LogOut,
  Wifi,
  WifiOff,
  Bell,
  X,
  Check,
  Clock,
  MessageSquare
} from 'lucide-vue-next'
import { formatChatTime } from '@/utils/time'

const groupChatStore = useGroupChatStore()
const authStore = useAuthStore()

const showCreateModal = ref(false)
const showInviteModal = ref(false)
const showMembersPanel = ref(false)
const showNotifications = ref(false)
const newGroupName = ref('')
const newGroupDesc = ref('')
const newMessage = ref('')
const searchQuery = ref('')
const messagesContainerRef = ref<HTMLDivElement>()

const filteredGroups = computed(() => {
  if (!searchQuery.value.trim()) {
    return groupChatStore.groups
  }
  const query = searchQuery.value.toLowerCase()
  return groupChatStore.groups.filter(g => 
    g.name.toLowerCase().includes(query) ||
    g.description?.toLowerCase().includes(query)
  )
})

const currentUserId = computed(() => authStore.userEmail || '')

onMounted(async () => {
  await Promise.all([
    groupChatStore.fetchGroups(),
    groupChatStore.fetchPendingInvitations(),
    groupChatStore.fetchNotifications()
  ])
  
  nextTick(() => {
    if (groupChatStore.currentGroup) {
      scrollToBottom()
    }
  })
})

onUnmounted(() => {
  groupChatStore.clearCurrentGroup()
})

watch(() => groupChatStore.currentMessages.length, () => {
  nextTick(() => {
    scrollToBottom()
  })
})

watch(() => groupChatStore.currentGroup?.id, () => {
  nextTick(() => {
    scrollToBottom()
  })
})

function scrollToBottom() {
  if (messagesContainerRef.value) {
    messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight
  }
}

async function handleCreateGroup() {
  if (!newGroupName.value.trim()) return
  
  try {
    const group = await groupChatStore.createGroup(
      newGroupName.value.trim(),
      newGroupDesc.value.trim() || undefined
    )
    showCreateModal.value = false
    newGroupName.value = ''
    newGroupDesc.value = ''
    await groupChatStore.selectGroup(group.id)
  } catch (e) {
    console.error('创建群组失败:', e)
  }
}

async function handleSelectGroup(groupId: string) {
  await groupChatStore.selectGroup(groupId)
  nextTick(() => {
    scrollToBottom()
  })
}

async function handleSendMessage() {
  if (!newMessage.value.trim()) return
  
  try {
    await groupChatStore.sendMessage(newMessage.value.trim())
    newMessage.value = ''
    scrollToBottom()
  } catch (e) {
    console.error('发送消息失败:', e)
  }
}

async function handleLeaveGroup() {
  if (!groupChatStore.currentGroup) return
  
  if (confirm(`确定要退出群组「${groupChatStore.currentGroup.name}」吗？`)) {
    try {
      await groupChatStore.leaveGroup(groupChatStore.currentGroup.id)
    } catch (e) {
      console.error('退出群组失败:', e)
    }
  }
}

function getInitials(name: string): string {
  return name.charAt(0).toUpperCase()
}

function getAvatarColor(name: string): string {
  const colors = [
    'from-blue-500 to-indigo-600',
    'from-purple-500 to-pink-600',
    'from-green-500 to-emerald-600',
    'from-orange-500 to-red-600',
    'from-cyan-500 to-blue-600',
    'from-rose-500 to-purple-600'
  ]
  const index = name.charCodeAt(0) % colors.length
  return colors[index]
}

function isOwnMessage(senderId: string): boolean {
  return senderId === currentUserId.value
}

function getRoleBadgeClass(role: string): string {
  switch (role) {
    case 'owner':
      return 'bg-amber-100 text-amber-700'
    case 'admin':
      return 'bg-blue-100 text-blue-700'
    default:
      return 'bg-gray-100 text-gray-600'
  }
}

function getRoleLabel(role: string): string {
  switch (role) {
    case 'owner':
      return '群主'
    case 'admin':
      return '管理员'
    default:
      return '成员'
  }
}
</script>

<template>
  <div class="flex h-full bg-gray-50">
    <!-- 群组列表侧边栏 -->
    <aside class="w-80 bg-white border-r border-gray-200 flex flex-col">
      <!-- 头部 -->
      <div class="h-16 px-4 flex items-center justify-between border-b border-gray-200">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 bg-gradient-to-br from-violet-500 to-purple-600 rounded-xl flex items-center justify-center">
            <Users :size="20" class="text-white" />
          </div>
          <div>
            <h1 class="font-bold text-gray-900">群组聊天</h1>
            <p class="text-xs text-gray-500">{{ groupChatStore.groups.length }} 个群组</p>
          </div>
        </div>
        <button
          @click="showCreateModal = true"
          class="w-9 h-9 bg-blue-500 hover:bg-blue-600 rounded-xl flex items-center justify-center text-white transition-all hover:scale-105"
        >
          <Plus :size="20" />
        </button>
      </div>

      <!-- 搜索 -->
      <div class="px-4 py-3">
        <div class="relative">
          <Search :size="18" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索群组..."
            class="w-full pl-10 pr-4 py-2.5 bg-gray-100 border-0 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all"
          />
        </div>
      </div>

      <!-- 邀请通知 -->
      <div v-if="groupChatStore.pendingInvitations.length > 0" class="px-4 pb-3">
        <div class="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-3">
          <div class="flex items-center gap-2 mb-2">
            <Bell :size="16" class="text-amber-600" />
            <span class="text-sm font-medium text-amber-800">待处理邀请</span>
            <span class="px-1.5 py-0.5 bg-amber-500 text-white text-xs rounded-full">
              {{ groupChatStore.pendingInvitations.length }}
            </span>
          </div>
          <div class="space-y-2">
            <div
              v-for="inv in groupChatStore.pendingInvitations.slice(0, 2)"
              :key="inv.id"
              class="flex items-center justify-between gap-2"
            >
              <span class="text-sm text-amber-700 truncate">{{ inv.group_name || '群组邀请' }}</span>
              <div class="flex gap-1">
                <button
                  @click="groupChatStore.acceptInvitation(inv.id)"
                  class="p-1 bg-green-500 hover:bg-green-600 text-white rounded-lg transition-colors"
                >
                  <Check :size="14" />
                </button>
                <button
                  @click="groupChatStore.declineInvitation(inv.id)"
                  class="p-1 bg-gray-300 hover:bg-gray-400 text-white rounded-lg transition-colors"
                >
                  <X :size="14" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 群组列表 -->
      <div class="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        <button
          v-for="group in filteredGroups"
          :key="group.id"
          @click="handleSelectGroup(group.id)"
          :class="[
            'w-full p-3 rounded-xl flex items-center gap-3 transition-all',
            groupChatStore.currentGroup?.id === group.id
              ? 'bg-blue-50 border-2 border-blue-200'
              : 'hover:bg-gray-100 border-2 border-transparent'
          ]"
        >
          <div :class="['w-12 h-12 bg-gradient-to-br rounded-xl flex items-center justify-center text-white font-bold text-lg', getAvatarColor(group.name)]">
            {{ getInitials(group.name) }}
          </div>
          <div class="flex-1 min-w-0 text-left">
            <div class="flex items-center justify-between">
              <p class="font-medium text-gray-900 truncate">{{ group.name }}</p>
              <span v-if="group.last_message" class="text-xs text-gray-400">
                {{ formatChatTime(group.last_message.created_at) }}
              </span>
            </div>
            <p v-if="group.last_message" class="text-sm text-gray-500 truncate">
              {{ group.last_message.sender_name }}: {{ group.last_message.content }}
            </p>
            <p v-else class="text-sm text-gray-400 italic">暂无消息</p>
          </div>
        </button>

        <div v-if="filteredGroups.length === 0" class="py-12 text-center">
          <Users :size="48" class="mx-auto text-gray-300 mb-3" />
          <p class="text-gray-500">暂无群组</p>
          <button
            @click="showCreateModal = true"
            class="mt-3 text-blue-500 hover:text-blue-600 font-medium"
          >
            创建第一个群组
          </button>
        </div>
      </div>
    </aside>

    <!-- 聊天区域 -->
    <main class="flex-1 flex flex-col">
      <!-- 空状态 -->
      <div v-if="!groupChatStore.currentGroup" class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="w-20 h-20 bg-gradient-to-br from-violet-100 to-purple-100 rounded-3xl flex items-center justify-center mx-auto mb-4">
            <MessageSquare :size="40" class="text-violet-500" />
          </div>
          <h2 class="text-xl font-bold text-gray-900 mb-2">选择一个群组开始聊天</h2>
          <p class="text-gray-500 mb-4">在左侧选择一个群组，或创建新的群组</p>
          <button
            @click="showCreateModal = true"
            class="px-6 py-2.5 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-xl transition-colors"
          >
            创建群组
          </button>
        </div>
      </div>

      <!-- 聊天内容 -->
      <template v-else>
        <!-- 聊天头部 -->
        <header class="h-16 px-6 bg-white border-b border-gray-200 flex items-center justify-between">
          <div class="flex items-center gap-4">
            <button @click="groupChatStore.clearCurrentGroup()" class="lg:hidden p-2 hover:bg-gray-100 rounded-lg">
              <ChevronLeft :size="20" />
            </button>
            <div :class="['w-10 h-10 bg-gradient-to-br rounded-lg flex items-center justify-center text-white font-bold', getAvatarColor(groupChatStore.currentGroup.name)]">
              {{ getInitials(groupChatStore.currentGroup.name) }}
            </div>
            <div>
              <h2 class="font-bold text-gray-900">{{ groupChatStore.currentGroup.name }}</h2>
              <div class="flex items-center gap-2 text-xs text-gray-500">
                <span>{{ groupChatStore.currentMembers.length }} 位成员</span>
                <span class="w-1 h-1 bg-gray-300 rounded-full"></span>
                <div class="flex items-center gap-1">
                  <component :is="groupChatStore.isConnected ? Wifi : WifiOff" :size="12" :class="groupChatStore.isConnected ? 'text-green-500' : 'text-red-500'" />
                  <span :class="groupChatStore.isConnected ? 'text-green-500' : 'text-red-500'">
                    {{ groupChatStore.isConnected ? '已连接' : '未连接' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="showInviteModal = true"
              class="p-2 hover:bg-gray-100 rounded-lg text-gray-600 hover:text-blue-600 transition-colors"
              title="邀请成员"
            >
              <UserPlus :size="20" />
            </button>
            <button
              @click="showMembersPanel = !showMembersPanel"
              :class="['p-2 rounded-lg transition-colors', showMembersPanel ? 'bg-blue-50 text-blue-600' : 'hover:bg-gray-100 text-gray-600']"
              title="群成员"
            >
              <Users :size="20" />
            </button>
            <button
              @click="handleLeaveGroup"
              class="p-2 hover:bg-red-50 rounded-lg text-gray-600 hover:text-red-600 transition-colors"
              title="退出群组"
            >
              <LogOut :size="20" />
            </button>
          </div>
        </header>

        <!-- 消息区域 -->
        <div ref="messagesContainerRef" class="flex-1 overflow-y-auto p-6 space-y-4">
          <div
            v-for="message in groupChatStore.currentMessages"
            :key="message.id"
            :class="['flex gap-3', isOwnMessage(message.sender_id) ? 'flex-row-reverse' : '']"
          >
            <!-- 头像 -->
            <div
              :class="[
                'w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold flex-shrink-0',
                isOwnMessage(message.sender_id) ? 'bg-gradient-to-br from-blue-500 to-indigo-600' : 'bg-gradient-to-br from-gray-400 to-gray-500'
              ]"
            >
              {{ message.sender_name?.charAt(0).toUpperCase() || '?' }}
            </div>

            <!-- 消息内容 -->
            <div :class="['max-w-[70%] flex flex-col', isOwnMessage(message.sender_id) ? 'items-end' : 'items-start']">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-sm font-medium text-gray-700">{{ message.sender_name }}</span>
                <span class="text-xs text-gray-400">{{ formatChatTime(message.created_at) }}</span>
              </div>
              <div
                :class="[
                  'px-4 py-3 rounded-2xl max-w-full',
                  isOwnMessage(message.sender_id)
                    ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white rounded-br-md'
                    : 'bg-white border border-gray-200 text-gray-800 rounded-bl-md'
                ]"
              >
                <p class="whitespace-pre-wrap break-words">{{ message.content }}</p>
              </div>
            </div>
          </div>

          <div v-if="groupChatStore.currentMessages.length === 0" class="text-center py-12">
            <MessageSquare :size="48" class="mx-auto text-gray-300 mb-3" />
            <p class="text-gray-500">还没有消息，开始聊天吧</p>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="p-4 bg-white border-t border-gray-200">
          <div class="flex items-end gap-3">
            <div class="flex-1 relative">
              <textarea
                v-model="newMessage"
                @keydown.enter.exact.prevent="handleSendMessage"
                placeholder="输入消息..."
                rows="1"
                class="w-full px-4 py-3 bg-gray-100 border-0 rounded-xl resize-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all"
              ></textarea>
            </div>
            <button
              @click="handleSendMessage"
              :disabled="!newMessage.trim()"
              :class="[
                'p-3 rounded-xl transition-all',
                newMessage.trim()
                  ? 'bg-blue-500 hover:bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              ]"
            >
              <Send :size="20" />
            </button>
          </div>
        </div>
      </template>
    </main>

    <!-- 成员列表侧边栏 -->
    <aside
      v-if="showMembersPanel && groupChatStore.currentGroup"
      class="w-72 bg-white border-l border-gray-200 flex flex-col"
    >
      <div class="h-14 px-4 flex items-center justify-between border-b border-gray-200">
        <h3 class="font-bold text-gray-900">群成员</h3>
        <button @click="showMembersPanel = false" class="p-1 hover:bg-gray-100 rounded-lg">
          <X :size="18" />
        </button>
      </div>
      <div class="flex-1 overflow-y-auto p-3 space-y-1">
        <div
          v-for="member in groupChatStore.currentMembers"
          :key="member.id"
          class="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50"
        >
          <div class="relative">
            <div :class="['w-10 h-10 bg-gradient-to-br rounded-xl flex items-center justify-center text-white font-bold', getAvatarColor(member.user_name || 'U')]">
              {{ getInitials(member.user_name || 'User') }}
            </div>
            <div
              v-if="groupChatStore.onlineMembers.has(member.user_id)"
              class="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-500 border-2 border-white rounded-full"
            ></div>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <p class="font-medium text-gray-900 truncate">{{ member.user_name || '未知用户' }}</p>
              <span :class="['px-1.5 py-0.5 text-xs rounded-md', getRoleBadgeClass(member.role)]">
                {{ getRoleLabel(member.role) }}
              </span>
            </div>
            <p class="text-xs text-gray-500">
              {{ groupChatStore.onlineMembers.has(member.user_id) ? '在线' : '离线' }}
            </p>
          </div>
        </div>
      </div>
    </aside>

    <!-- 创建群组弹窗 -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/50" @click="showCreateModal = false"></div>
        <div class="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 animate-in fade-in zoom-in duration-200">
          <h2 class="text-xl font-bold text-gray-900 mb-4">创建新群组</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">群组名称</label>
              <input
                v-model="newGroupName"
                type="text"
                placeholder="输入群组名称"
                class="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">群组描述（可选）</label>
              <textarea
                v-model="newGroupDesc"
                placeholder="输入群组描述"
                rows="3"
                class="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              ></textarea>
            </div>
          </div>
          <div class="flex justify-end gap-3 mt-6">
            <button
              @click="showCreateModal = false"
              class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-xl transition-colors"
            >
              取消
            </button>
            <button
              @click="handleCreateGroup"
              :disabled="!newGroupName.trim()"
              :class="[
                'px-6 py-2 rounded-xl font-medium transition-colors',
                newGroupName.trim()
                  ? 'bg-blue-500 hover:bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              ]"
            >
              创建
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 邀请成员弹窗 -->
    <Teleport to="body">
      <div v-if="showInviteModal" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/50" @click="showInviteModal = false"></div>
        <div class="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 animate-in fade-in zoom-in duration-200">
          <h2 class="text-xl font-bold text-gray-900 mb-4">邀请成员</h2>
          <p class="text-sm text-gray-500 mb-4">邀请企业成员加入「{{ groupChatStore.currentGroup?.name }}」</p>
          
          <div class="space-y-3 max-h-64 overflow-y-auto">
            <div class="p-3 bg-amber-50 border border-amber-200 rounded-xl">
              <p class="text-sm text-amber-700">邀请功能将通过系统通知发送给企业成员</p>
            </div>
          </div>
          
          <div class="flex justify-end gap-3 mt-6">
            <button
              @click="showInviteModal = false"
              class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-xl transition-colors"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
