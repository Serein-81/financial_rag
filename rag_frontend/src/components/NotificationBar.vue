<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useUnifiedNotifications, type UnifiedNotification } from '@/composables/useUnifiedNotifications'
import { isAuthenticated } from '@/utils/request'
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
  AlertTriangle,
  CheckCircle,
  XCircle,
  FileText,
  Clock,
  ChevronRight,
  CheckCircle2,
  Circle,
  PanelRight
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const router = useRouter()
const {
  notifications,
  stats,
  isLoading,
  unreadCount,
  loadNotifications,
  markAsRead,
  markAllAsRead,
  deleteNotification,
  acceptInvitation,
  declineInvitation,
  refresh
} = useUnifiedNotifications()

const isSelectionMode = ref(false)
const selectedNotifications = ref<Set<string>>(new Set())
const activeCategory = ref<'all' | 'chat' | 'policy' | 'system' | 'task'>('all')

onMounted(() => {
  if (isAuthenticated()) {
    loadNotifications()
  }
})

watch(() => props.modelValue, (isOpen) => {
  if (isOpen && isAuthenticated()) {
    loadNotifications()
  }
})

function close() {
  emit('update:modelValue', false)
}

function goToNotificationCenter() {
  close()
  router.push({ name: 'notifications' })
}

const filteredNotifications = computed(() => {
  if (activeCategory.value === 'all') {
    return notifications.value
  }
  return notifications.value.filter(n => n.category === activeCategory.value)
})

const categories = [
  { id: 'all', label: '全部通知', icon: Bell },
  { id: 'chat', label: '群聊消息', icon: MessageSquare },
  { id: 'policy', label: '政策更新', icon: FileText },
  { id: 'task', label: '任务提醒', icon: Clock },
  { id: 'system', label: '系统通知', icon: Info }
]

function getNotificationIcon(iconName: string) {
  const iconMap: Record<string, any> = {
    Bell,
    MessageSquare,
    UserPlus,
    UserMinus,
    UserCheck: UserPlus,
    Info,
    AlertTriangle,
    CheckCircle,
    XCircle,
    FileText,
    Clock
  }
  return iconMap[iconName] || Bell
}

function getCategoryBadge(category: string): string {
  const badges: Record<string, string> = {
    chat: 'bg-green-100 text-green-700',
    policy: 'bg-blue-100 text-blue-700',
    task: 'bg-purple-100 text-purple-700',
    system: 'bg-gray-100 text-gray-700'
  }
  return badges[category] || 'bg-gray-100 text-gray-700'
}

function getCategoryLabel(category: string): string {
  const labels: Record<string, string> = {
    chat: '群聊',
    policy: '政策',
    task: '任务',
    system: '系统'
  }
  return labels[category] || '其他'
}

async function handleNotificationClick(notification: UnifiedNotification) {
  if (isSelectionMode.value) {
    toggleSelection(notification.id)
    return
  }

  if (!notification.isRead) {
    await markAsRead(notification.id)
  }

  if (notification.actionUrl) {
    router.push(notification.actionUrl)
    close()
  } else if (notification.category === 'chat') {
    router.push({ name: 'group-chat' })
    close()
  } else if (notification.category === 'policy') {
    goToNotificationCenter()
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
  if (selectedNotifications.value.size === filteredNotifications.value.length) {
    selectedNotifications.value.clear()
  } else {
    selectedNotifications.value = new Set(filteredNotifications.value.map(n => n.id))
  }
  selectedNotifications.value = new Set(selectedNotifications.value)
}

async function markSelectedAsRead() {
  for (const id of selectedNotifications.value) {
    await markAsRead(id)
  }
  selectedNotifications.value.clear()
  isSelectionMode.value = false
}

async function deleteSelected() {
  for (const id of selectedNotifications.value) {
    await deleteNotification(id)
  }
  selectedNotifications.value.clear()
  isSelectionMode.value = false
}

async function handleMarkAllRead() {
  await markAllAsRead(activeCategory.value)
}

async function handleClearAll() {
  if (confirm('确定要清空所有通知吗？')) {
    for (const notification of filteredNotifications.value) {
      await deleteNotification(notification.id)
    }
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

function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return date.toLocaleDateString('zh-CN')
}

function isInvitationNotification(notification: UnifiedNotification): boolean {
  return notification.category === 'chat' && notification.metadata?.type === 'invitation'
}

async function handleAcceptInvitation(notification: UnifiedNotification, event: Event) {
  event.stopPropagation()
  const invitationId = notification.metadata?.invitation_id || notification.metadata?.id
  if (invitationId) {
    await acceptInvitation(invitationId)
    refresh()
  }
}

async function handleDeclineInvitation(notification: UnifiedNotification, event: Event) {
  event.stopPropagation()
  const invitationId = notification.metadata?.invitation_id || notification.metadata?.id
  if (invitationId) {
    await declineInvitation(invitationId)
    refresh()
  }
}
</script>

<template>
  <div v-if="modelValue" class="fixed top-20 right-6 z-[100]">
    <div
      class="w-[600px] bg-white/95 backdrop-blur-lg rounded-2xl shadow-2xl border border-gray-200/50 overflow-hidden"
      style="height: 750px; max-height: calc(100vh - 80px);"
      @click.stop
    >
      <div class="px-5 py-4 bg-gradient-to-r from-slate-50 to-white border-b border-gray-200">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/30">
              <Bell :size="18" class="text-white" />
            </div>
            <div>
              <h3 class="font-bold text-gray-900 text-base">通知中心</h3>
              <p class="text-xs text-gray-500">
                <span v-if="unreadCount > 0" class="text-blue-600 font-medium">{{ unreadCount }} 条未读</span>
                <span v-else>暂无未读通知</span>
              </p>
            </div>
          </div>
          <div class="flex items-center gap-1">
            <button
              @click.stop="goToNotificationCenter"
              class="p-2 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-blue-600 transition-colors"
              title="详情"
            >
              <PanelRight :size="18" />
            </button>
            <button
              @click.stop="close"
              class="p-2 hover:bg-gray-100 rounded-lg text-gray-500 transition-colors"
            >
              <X :size="18" />
            </button>
          </div>
        </div>

        <div class="flex gap-1 mt-3 p-1 bg-gray-100/80 rounded-xl">
          <button
            v-for="cat in categories"
            :key="cat.id"
            @click.stop="activeCategory = cat.id as any"
            :class="[
              'flex-1 px-2 py-1.5 text-xs font-medium rounded-lg transition-all flex items-center justify-center gap-1',
              activeCategory === cat.id
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            ]"
          >
            <component :is="cat.icon" :size="14" />
            <span>{{ cat.label }}</span>
            <span
              v-if="cat.id === 'all' && unreadCount > 0"
              class="w-4 h-4 bg-blue-500 text-white text-[10px] rounded-full flex items-center justify-center"
            >
              {{ unreadCount > 9 ? '9+' : unreadCount }}
            </span>
          </button>
        </div>

        <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
          <div class="flex items-center gap-2">
            <template v-if="isSelectionMode">
              <button
                @click.stop="selectAll"
                class="px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-1.5"
              >
                <CheckCircle2 :size="14" />
                {{ selectedNotifications.size === filteredNotifications.length ? '取消全选' : '全选' }}
              </button>
            </template>
            <template v-else>
              <button
                v-if="unreadCount > 0"
                @click.stop="handleMarkAllRead"
                class="px-3 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors flex items-center gap-1.5"
              >
                <CheckCheck :size="14" />
                全部已读
              </button>
              <button
                @click.stop="enterSelectionMode"
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
                @click.stop="markSelectedAsRead"
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
                @click.stop="deleteSelected"
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
                @click.stop="exitSelectionMode"
                class="px-3 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-100 rounded-lg transition-colors"
              >
                取消
              </button>
            </template>
            <template v-else>
              <button
                v-if="filteredNotifications.length > 0"
                @click.stop="handleClearAll"
                class="px-3 py-1.5 text-xs font-medium text-red-500 hover:bg-red-50 rounded-lg transition-colors flex items-center gap-1.5"
              >
                <Trash2 :size="14" />
                清空
              </button>
            </template>
          </div>
        </div>
      </div>

      <div class="overflow-y-auto" style="height: calc(100% - 170px);">
        <div v-if="isLoading" class="flex items-center justify-center py-20">
          <div class="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        </div>

        <div v-else-if="filteredNotifications.length === 0" class="flex flex-col items-center justify-center py-20">
          <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
            <Bell :size="28" class="text-gray-400" />
          </div>
          <p class="text-gray-500 text-sm">暂无通知</p>
          <p class="text-gray-400 text-xs mt-1">
            {{ activeCategory === 'all' ? '去发现更多内容吧' : '没有' + (categories.find(c => c.id === activeCategory)?.label || '') + '类通知' }}
          </p>
        </div>

        <div v-else>
          <div
            v-for="notification in filteredNotifications"
            :key="notification.id"
            @click.stop="handleNotificationClick(notification)"
            :class="[
              'px-5 py-4 border-b border-gray-100 cursor-pointer transition-all hover:bg-gray-50 flex items-start gap-3',
              !notification.isRead ? 'bg-blue-50/30' : '',
              selectedNotifications.has(notification.id) ? 'bg-blue-100/50' : ''
            ]"
          >
            <div v-if="isSelectionMode" class="flex-shrink-0 mt-1">
              <component
                :is="selectedNotifications.has(notification.id) ? CheckCircle2 : Circle"
                :size="20"
                :class="selectedNotifications.has(notification.id) ? 'text-blue-600' : 'text-gray-400'"
              />
            </div>

            <div :class="['w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0', notification.bgColor]">
              <component :is="getNotificationIcon(notification.icon)" :size="20" :class="notification.iconColor" />
            </div>

            <div class="flex-1 min-w-0">
              <div class="flex items-start justify-between gap-2">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <p :class="['font-semibold text-sm truncate', notification.isRead ? 'text-gray-600' : 'text-gray-900']">
                      {{ notification.title }}
                    </p>
                    <span v-if="!notification.isRead" class="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0"></span>
                  </div>
                  <p class="text-sm text-gray-500 mt-1 leading-relaxed line-clamp-2">{{ notification.message }}</p>
                </div>
              </div>
              <div class="flex items-center justify-between mt-2">
                <div class="flex items-center gap-2">
                  <span :class="['px-2 py-0.5 text-xs rounded-full font-medium', getCategoryBadge(notification.category)]">
                    {{ getCategoryLabel(notification.category) }}
                  </span>
                  <span class="text-xs text-gray-400">{{ formatTime(notification.createdAt) }}</span>
                </div>
                <div v-if="isInvitationNotification(notification)" class="flex items-center gap-1.5">
                  <button
                    @click="handleDeclineInvitation(notification, $event)"
                    class="px-2.5 py-1 text-xs font-medium bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg transition-colors"
                  >
                    拒绝
                  </button>
                  <button
                    @click="handleAcceptInvitation(notification, $event)"
                    class="px-2.5 py-1 text-xs font-medium bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg transition-colors"
                  >
                    接受
                  </button>
                </div>
                <div
                  v-else-if="notification.actionUrl || notification.category === 'chat'"
                  class="flex items-center gap-0.5 text-xs text-blue-600"
                >
                  <span>查看详情</span>
                  <ChevronRight :size="12" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="px-5 py-3 bg-gray-50/80 border-t border-gray-200">
        <button
          @click.stop="goToNotificationCenter"
          class="w-full py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <span>查看全部通知</span>
          <ChevronRight :size="16" />
        </button>
      </div>
    </div>
  </div>
</template>
