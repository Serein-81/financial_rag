<script setup lang="ts">
import { ref, computed } from 'vue'
import { useGroupChatStore } from '@/stores/group-chat'
import { useAuthStore } from '@/stores/auth'
import {
  Bell,
  X,
  Check,
  CheckCheck,
  Trash2,
  MessageSquare,
  UserPlus,
  UserMinus,
  Info,
  ChevronRight,
  CheckCircle2,
  Circle,
  Trash
} from 'lucide-vue-next'
import { formatChatTime } from '@/utils/time'
import { useRouter } from 'vue-router'

const router = useRouter()
const groupChatStore = useGroupChatStore()
const authStore = useAuthStore()

const showNotifications = ref(false)
const isSelectionMode = ref(false)
const selectedNotifications = ref<Set<string>>(new Set())

const unreadCount = computed(() => groupChatStore.unreadCount)
const notifications = computed(() => groupChatStore.notifications)

function getNotificationIcon(type: string) {
  switch (type) {
    case 'invitation':
      return UserPlus
    case 'message':
      return MessageSquare
    case 'member_joined':
      return UserPlus
    case 'member_left':
      return UserMinus
    default:
      return Info
  }
}

function getNotificationColor(type: string) {
  switch (type) {
    case 'invitation':
      return 'bg-blue-500'
    case 'message':
      return 'bg-green-500'
    case 'member_joined':
      return 'bg-emerald-500'
    case 'member_left':
      return 'bg-gray-500'
    default:
      return 'bg-purple-500'
  }
}

async function handleNotificationClick(notification: any) {
  if (isSelectionMode.value) {
    toggleSelection(notification.id)
    return
  }
  
  await groupChatStore.markNotificationRead(notification.id)
  
  if (notification.group_id) {
    router.push({ name: 'group-chat' })
    if (notification.group_id !== groupChatStore.currentGroup?.id) {
      await groupChatStore.selectGroup(notification.group_id)
    }
  }
}

function toggleSelection(notificationId: string) {
  if (selectedNotifications.value.has(notificationId)) {
    selectedNotifications.value.delete(notificationId)
  } else {
    selectedNotifications.value.add(notificationId)
  }
  selectedNotifications.value = new Set(selectedNotifications.value)
}

function selectAll() {
  if (selectedNotifications.value.size === notifications.value.length) {
    selectedNotifications.value.clear()
  } else {
    selectedNotifications.value = new Set(notifications.value.map(n => n.id))
  }
  selectedNotifications.value = new Set(selectedNotifications.value)
}

async function markSelectedAsRead() {
  for (const id of selectedNotifications.value) {
    await groupChatStore.markNotificationRead(id)
  }
  selectedNotifications.value.clear()
  isSelectionMode.value = false
}

async function deleteSelected() {
  const ids = Array.from(selectedNotifications.value)
  await groupChatStore.deleteNotificationsBatch(ids)
  selectedNotifications.value.clear()
  isSelectionMode.value = false
}

async function handleMarkAllRead() {
  await groupChatStore.markAllNotificationsRead()
}

async function handleClearAll() {
  if (confirm('确定要清空所有通知吗？')) {
    await groupChatStore.clearAllNotifications()
  }
}

function toggleNotifications() {
  showNotifications.value = !showNotifications.value
  if (!showNotifications.value) {
    isSelectionMode.value = false
    selectedNotifications.value.clear()
  }
}

function enterSelectionMode() {
  isSelectionMode.value = true
  selectedNotifications.value.clear()
}

function exitSelectionMode() {
  isSelectionMode.value = false
  selectedNotifications.value.clear()
}
</script>

<template>
  <div class="relative inline-block">
    <!-- 通知按钮 -->
    <button
      @click="toggleNotifications"
      class="relative p-2.5 hover:bg-gray-100 rounded-xl transition-colors group bg-white shadow-sm border border-gray-200"
    >
      <Bell
        :size="22"
        :class="[
          'transition-colors',
          unreadCount > 0 ? 'text-blue-600' : 'text-gray-600 group-hover:text-gray-900'
        ]"
      />
      <span
        v-if="unreadCount > 0"
        class="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center px-1"
      >
        {{ unreadCount > 99 ? '99+' : unreadCount }}
      </span>
    </button>

    <!-- 通知面板 -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 scale-95 -translate-y-2"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 -translate-y-2"
    >
      <div
        v-if="showNotifications"
        class="fixed right-4 top-16 w-[440px] max-w-[95vw] bg-white rounded-2xl shadow-2xl border border-gray-200 z-50 overflow-hidden"
        style="height: calc(100vh - 140px);"
      >
        <!-- 头部 -->
        <div class="px-5 py-4 bg-gradient-to-r from-slate-50 to-white border-b border-gray-200">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 bg-blue-100 rounded-xl flex items-center justify-center">
                <Bell :size="18" class="text-blue-600" />
              </div>
              <div>
                <h3 class="font-bold text-gray-900 text-base">通知中心</h3>
                <p class="text-xs text-gray-500">{{ notifications.length }} 条通知</p>
              </div>
            </div>
            <button
              @click="showNotifications = false"
              class="p-2 hover:bg-gray-100 rounded-lg text-gray-500 transition-colors"
            >
              <X :size="18" />
            </button>
          </div>
          
          <!-- 操作栏 -->
          <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
            <div class="flex items-center gap-2">
              <template v-if="isSelectionMode">
                <button
                  @click="selectAll"
                  class="px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  <CheckCircle2 :size="14" />
                  {{ selectedNotifications.size === notifications.length ? '取消全选' : '全选' }}
                </button>
              </template>
              <template v-else>
                <button
                  v-if="unreadCount > 0"
                  @click="handleMarkAllRead"
                  class="px-3 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  <CheckCheck :size="14" />
                  全部已读
                </button>
                <button
                  @click="enterSelectionMode"
                  class="px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  <Check :size="14" />
                  选择
                </button>
              </template>
            </div>
            
            <div class="flex items-center gap-2">
              <template v-if="isSelectionMode">
                <button
                  @click="markSelectedAsRead"
                  :disabled="selectedNotifications.size === 0"
                  :class="[
                    'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5',
                    selectedNotifications.size > 0
                      ? 'text-blue-600 hover:bg-blue-50'
                      : 'text-gray-300 cursor-not-allowed'
                  ]"
                >
                  <CheckCheck :size="14" />
                  已读
                </button>
                <button
                  @click="deleteSelected"
                  :disabled="selectedNotifications.size === 0"
                  :class="[
                    'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5',
                    selectedNotifications.size > 0
                      ? 'text-red-600 hover:bg-red-50'
                      : 'text-gray-300 cursor-not-allowed'
                  ]"
                >
                  <Trash2 :size="14" />
                  删除 ({{ selectedNotifications.size }})
                </button>
                <button
                  @click="exitSelectionMode"
                  class="px-3 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  取消
                </button>
              </template>
              <template v-else>
                <button
                  v-if="notifications.length > 0"
                  @click="handleClearAll"
                  class="px-3 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  <Trash :size="14" />
                  清空
                </button>
              </template>
            </div>
          </div>
        </div>

        <!-- 通知列表 -->
        <div class="overflow-y-auto" style="height: calc(100% - 130px);">
          <div
            v-for="notification in notifications"
            :key="notification.id"
            @click="handleNotificationClick(notification)"
            :class="[
              'px-5 py-4 border-b border-gray-100 cursor-pointer transition-all hover:bg-gray-50 flex items-start gap-3',
              !notification.is_read ? 'bg-blue-50/30' : '',
              selectedNotifications.has(notification.id) ? 'bg-blue-100/50' : ''
            ]"
          >
            <!-- 选择框 -->
            <div v-if="isSelectionMode" class="flex-shrink-0 mt-1">
              <component
                :is="selectedNotifications.has(notification.id) ? CheckCircle2 : Circle"
                :size="20"
                :class="selectedNotifications.has(notification.id) ? 'text-blue-600' : 'text-gray-400'"
              />
            </div>
            
            <!-- 图标 -->
            <div :class="['w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0', getNotificationColor(notification.type)]">
              <component :is="getNotificationIcon(notification.type)" :size="18" class="text-white" />
            </div>

            <!-- 内容 -->
            <div class="flex-1 min-w-0">
              <div class="flex items-start justify-between gap-2">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <p class="font-semibold text-gray-900 text-sm truncate">{{ notification.title }}</p>
                    <span v-if="!notification.is_read" class="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0"></span>
                  </div>
                  <p class="text-sm text-gray-600 mt-1 leading-relaxed whitespace-pre-wrap break-words line-clamp-2">{{ notification.content }}</p>
                </div>
              </div>
              <div class="flex items-center justify-between mt-2">
                <p class="text-xs text-gray-400">{{ formatChatTime(notification.created_at) }}</p>
                <div
                  v-if="notification.group_name"
                  class="flex items-center gap-0.5 text-xs text-blue-600"
                >
                  <span class="truncate max-w-[120px]">{{ notification.group_name }}</span>
                  <ChevronRight :size="12" />
                </div>
              </div>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="notifications.length === 0" class="py-16 text-center">
            <div class="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Bell :size="36" class="text-gray-400" />
            </div>
            <p class="text-gray-600 font-medium text-base mb-1">暂无通知</p>
            <p class="text-gray-400 text-sm">你将在此处收到群组消息和邀请</p>
          </div>
        </div>

        <!-- 底部 -->
        <div v-if="notifications.length > 0" class="px-5 py-3 bg-gray-50 border-t border-gray-200">
          <button
            @click="router.push({ name: 'notifications' })"
            class="w-full py-2.5 text-sm text-blue-600 hover:text-blue-700 font-medium hover:bg-blue-100 rounded-lg transition-colors flex items-center justify-center gap-1"
          >
            查看全部通知
            <ChevronRight :size="14" />
          </button>
        </div>
      </div>
    </Transition>

    <!-- 点击外部关闭 -->
    <div
      v-if="showNotifications"
      class="fixed inset-0 z-40"
      @click="showNotifications = false"
    ></div>
  </div>
</template>
