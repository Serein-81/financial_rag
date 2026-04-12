<script setup lang="ts">

import { ref, computed, onMounted, watch } from 'vue'

import { useUnifiedNotifications, type UnifiedNotification, type NotificationCategory } from '@/composables/useUnifiedNotifications'

import { isAuthenticated } from '@/utils/request'

import {

  Bell,

  RefreshCw,

  CheckCheck,

  Trash2,

  Check,

  X,

  Search,

  Filter,

  MessageSquare,

  FileText,

  Info,

  Clock,

  AlertTriangle,

  CheckCircle,

  XCircle,

  Settings,

  Download,

  ChevronDown,

  LayoutGrid,

  List

} from 'lucide-vue-next'

import { ElMessage, ElMessageBox } from 'element-plus'

import { useRouter } from 'vue-router'



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

  refresh

} = useUnifiedNotifications()



const activeCategory = ref<NotificationCategory>('all')

const searchQuery = ref('')

const sortOrder = ref<'newest' | 'oldest' | 'priority'>('newest')

const viewMode = ref<'card' | 'list'>('card')

const selectedNotifications = ref<Set<string>>(new Set())

const isSelectionMode = ref(false)

const showFilters = ref(false)



const filters = ref({

  priority: '' as string,

  isRead: '' as string

})



const categories = [

  { id: 'all', label: '全部通知', icon: Bell, count: computed(() => stats.value.byCategory.all) },

  { id: 'chat', label: '群聊消息', icon: MessageSquare, count: computed(() => stats.value.byCategory.chat) },

  { id: 'policy', label: '政策更新', icon: FileText, count: computed(() => stats.value.byCategory.policy) },

  { id: 'task', label: '任务提醒', icon: Clock, count: computed(() => stats.value.byCategory.task) },

  { id: 'system', label: '系统通知', icon: Info, count: computed(() => stats.value.byCategory.system) }

]



const filteredNotifications = computed(() => {

  let result = notifications.value



  if (activeCategory.value !== 'all') {

    result = result.filter(n => n.category === activeCategory.value)

  }



  if (searchQuery.value) {

    const query = searchQuery.value.toLowerCase()

    result = result.filter(n =>

      n.title.toLowerCase().includes(query) ||

      n.message.toLowerCase().includes(query)

    )

  }



  if (filters.value.priority) {

    result = result.filter(n => n.priority === filters.value.priority)

  }



  if (filters.value.isRead !== '') {

    const isRead = filters.value.isRead === 'true'

    result = result.filter(n => n.isRead === isRead)

  }



  if (sortOrder.value === 'newest') {

    result = [...result].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())

  } else if (sortOrder.value === 'oldest') {

    result = [...result].sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())

  } else if (sortOrder.value === 'priority') {

    const priorityOrder = { urgent: 0, high: 1, medium: 2, low: 3 }

    result = [...result].sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority])

  }



  return result

})



onMounted(() => {
  if (isAuthenticated()) {
    loadNotifications()
  }
})



function getCategoryIcon(category: string) {

  const icons: Record<string, any> = {

    chat: MessageSquare,

    policy: FileText,

    task: Clock,

    system: Info

  }

  return icons[category] || Bell

}



function getCategoryColor(category: string): { bg: string; text: string } {

  const colors: Record<string, { bg: string; text: string }> = {

    chat: { bg: 'bg-green-100', text: 'text-green-700' },

    policy: { bg: 'bg-blue-100', text: 'text-blue-700' },

    task: { bg: 'bg-purple-100', text: 'text-purple-700' },

    system: { bg: 'bg-gray-100', text: 'text-gray-700' }

  }

  return colors[category] || { bg: 'bg-gray-100', text: 'text-gray-700' }

}



function getPriorityConfig(priority: string) {

  const configs: Record<string, { label: string; bg: string; text: string; icon: any }> = {

    urgent: { label: '紧急', bg: 'bg-red-100', text: 'text-red-700', icon: XCircle },

    high: { label: '高', bg: 'bg-orange-100', text: 'text-orange-700', icon: AlertTriangle },

    medium: { label: '中', bg: 'bg-blue-100', text: 'text-blue-700', icon: Bell },

    low: { label: '低', bg: 'bg-gray-100', text: 'text-gray-700', icon: Info }

  }

  return configs[priority] || configs.medium

}



function getNotificationIcon(iconName: string) {

  const icons: Record<string, any> = {

    Bell,

    MessageSquare,

    UserPlus: MessageSquare,

    UserMinus: MessageSquare,

    UserCheck: Check,

    Info,

    AlertTriangle,

    CheckCircle,

    XCircle,

    FileText,

    Clock

  }

  return icons[iconName] || Bell

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

  } else if (notification.category === 'chat') {

    router.push({ name: 'group-chat' })

  }

}



function toggleSelection(id: string) {

  if (selectedNotifications.value.has(id)) {

    selectedNotifications.value.delete(id)

  } else {

    selectedNotifications.value.add(id)

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

  ElMessage.success('已标记为已读')

}



async function deleteSelected() {

  try {

    await ElMessageBox.confirm(

      `确定要删除选中${selectedNotifications.value.size}条通知吗？`,

      '确认删除',

      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }

    )



    for (const id of selectedNotifications.value) {

      await deleteNotification(id)

    }

    selectedNotifications.value.clear()

    isSelectionMode.value = false

  } catch {

  }

}



async function handleMarkAllRead() {

  await markAllAsRead(activeCategory.value)

}



async function handleDeleteAll() {

  try {

    await ElMessageBox.confirm(

      `确定要清空所有${activeCategory.value === 'all' ? '' : categories.find(c => c.id === activeCategory.value)?.label}通知吗？`,

      '确认清空',

      { confirmButtonText: '清空', cancelButtonText: '取消', type: 'warning' }

    )



    for (const notification of filteredNotifications.value) {

      await deleteNotification(notification.id)

    }

  } catch {

  }

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

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })

}



function clearFilters() {

  searchQuery.value = ''

  filters.value = { priority: '', isRead: '' }

}

</script>



<template>

  <div class="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/20">

    <div class="max-w-7xl mx-auto px-6 py-8">

      <div class="mb-8">

        <div class="flex items-center justify-between">

          <div>

            <h1 class="text-3xl font-bold bg-gradient-to-r from-gray-900 via-blue-800 to-indigo-800 bg-clip-text text-transparent">

              通知中心

            </h1>

            <p class="text-gray-500 mt-1">统一管理您的所有通知和提醒</p>

          </div>

          <div class="flex items-center gap-3">

            <button

              @click="refresh"

              :disabled="isLoading"

              class="px-4 py-2 bg-white border border-gray-200 rounded-xl text-gray-600 hover:bg-gray-50 transition-colors flex items-center gap-2 shadow-sm"

            >

              <RefreshCw :size="16" :class="{ 'animate-spin': isLoading }" />

              刷新

            </button>

          </div>

        </div>

      </div>



      <div class="grid grid-cols-12 gap-6">

        <div class="col-span-12 lg:col-span-3">

          <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden sticky top-6">

            <div class="p-4 border-b border-gray-100">

              <div class="flex items-center justify-between mb-3">

                <h3 class="font-semibold text-gray-900">通知分类</h3>

                <span class="text-xs text-gray-400">{{ notifications.length }} 条</span>

              </div>

              <div class="relative">

                <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />

                <input

                  v-model="searchQuery"

                  type="text"

                  placeholder="搜索通知..."

                  class="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-300 transition-all"

                />

              </div>

            </div>



            <div class="p-2">

              <button

                v-for="cat in categories"

                :key="cat.id"

                @click="activeCategory = cat.id as NotificationCategory"

                :class="[

                  'w-full px-4 py-3 rounded-xl text-left transition-all flex items-center justify-between group',

                  activeCategory === cat.id

                    ? 'bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-lg shadow-blue-500/25'

                    : 'hover:bg-gray-50'

                ]"

              >

                <div class="flex items-center gap-3">

                  <div :class="[

                    'w-9 h-9 rounded-lg flex items-center justify-center transition-colors',

                    activeCategory === cat.id ? 'bg-white/20' : 'bg-gray-100 group-hover:bg-gray-200'

                  ]">

                    <component :is="cat.icon" :size="18" :class="activeCategory === cat.id ? 'text-white' : 'text-gray-600'" />

                  </div>

                  <span :class="['font-medium', activeCategory === cat.id ? 'text-white' : 'text-gray-700']">

                    {{ cat.label }}

                  </span>

                </div>

                <span v-if="cat.count.value > 0" :class="[

                  'px-2 py-0.5 text-xs font-bold rounded-full',

                  activeCategory === cat.id

                    ? 'bg-white/30 text-white'

                    : 'bg-blue-100 text-blue-600'

                ]">

                  {{ cat.count.value > 99 ? '99+' : cat.count.value }}

                </span>

              </button>

            </div>



            <div class="p-4 border-t border-gray-100">

              <h4 class="font-medium text-gray-700 mb-3 text-sm">快捷操作</h4>

              <div class="space-y-2">

                <button

                  v-if="unreadCount > 0"

                  @click="handleMarkAllRead"

                  class="w-full px-4 py-2 bg-blue-50 text-blue-600 rounded-xl text-sm font-medium hover:bg-blue-100 transition-colors flex items-center justify-center gap-2"

                >

                  <CheckCheck :size="16" />

                  全部标为已读

                </button>

                <button

                  v-if="filteredNotifications.length > 0"

                  @click="handleDeleteAll"

                  class="w-full px-4 py-2 bg-red-50 text-red-600 rounded-xl text-sm font-medium hover:bg-red-100 transition-colors flex items-center justify-center gap-2"

                >

                  <Trash2 :size="16" />

                  清空当前分类

                </button>

              </div>

            </div>

          </div>

        </div>



        <div class="col-span-12 lg:col-span-9">

          <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">

            <div class="p-4 border-b border-gray-100">

              <div class="flex items-center justify-between flex-wrap gap-4">

                <div class="flex items-center gap-3">

                  <button

                    v-if="!isSelectionMode"

                    @click="isSelectionMode = true"

                    class="px-4 py-2 bg-gray-100 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-200 transition-colors"

                  >

                    选择

                  </button>

                  <template v-else>

                    <button

                      @click="selectAll"

                      class="px-4 py-2 bg-blue-50 text-blue-600 rounded-xl text-sm font-medium hover:bg-blue-100 transition-colors"

                    >

                      {{ selectedNotifications.size === filteredNotifications.length ? '取消全选' : '全选' }}

                    </button>

                    <button

                      @click="markSelectedAsRead"

                      :disabled="selectedNotifications.size === 0"

                      class="px-4 py-2 bg-green-50 text-green-600 rounded-xl text-sm font-medium hover:bg-green-100 transition-colors disabled:opacity-50"

                    >

                      标记已读 ({{ selectedNotifications.size }})

                    </button>

                    <button

                      @click="deleteSelected"

                      :disabled="selectedNotifications.size === 0"

                      class="px-4 py-2 bg-red-50 text-red-600 rounded-xl text-sm font-medium hover:bg-red-100 transition-colors disabled:opacity-50"

                    >

                      删除 ({{ selectedNotifications.size }})

                    </button>

                    <button

                      @click="isSelectionMode = false; selectedNotifications.clear()"

                      class="px-4 py-2 bg-gray-100 text-gray-600 rounded-xl text-sm font-medium hover:bg-gray-200 transition-colors"

                    >

                      取消

                    </button>

                  </template>

                </div>



                <div class="flex items-center gap-3">

                  <select

                    v-model="sortOrder"

                    class="px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20"

                  >

                    <option value="newest">最新优先</option>

                  <option value="oldest">最早优先</option>

                    <option value="priority">按优先级</option>

                  </select>



                  <button

                    @click="showFilters = !showFilters"

                    :class="[

                      'px-4 py-2 rounded-xl text-sm font-medium transition-colors flex items-center gap-2',

                      showFilters || filters.priority || filters.isRead

                        ? 'bg-blue-100 text-blue-600'

                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'

                    ]"

                  >

                    <Filter :size="16" />

                    筛选                  </button>

                </div>

              </div>



              <div v-if="showFilters" class="mt-4 p-4 bg-gray-50 rounded-xl">

                <div class="flex items-center gap-4 flex-wrap">

                  <div class="flex items-center gap-2">

                    <label class="text-sm text-gray-600">优先级</label>

                    <select

                      v-model="filters.priority"

                      class="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm"

                    >

                      <option value="">全部</option>

                      <option value="urgent">紧急</option>

                      <option value="high">高</option>

                      <option value="medium">中</option>

                      <option value="low">低</option>

                    </select>

                  </div>

                  <div class="flex items-center gap-2">

                    <label class="text-sm text-gray-600">状态</label>

                    <select

                      v-model="filters.isRead"

                      class="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm"

                    >

                      <option value="">全部</option>

                      <option value="false">未读</option>

                      <option value="true">已读</option>

                    </select>

                  </div>

                  <button

                    @click="clearFilters"

                    class="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700"

                  >

                    清除筛选                  </button>

                </div>

              </div>

            </div>



            <div v-if="isLoading" class="flex items-center justify-center py-20">

              <div class="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>

            </div>



            <div v-else-if="filteredNotifications.length === 0" class="flex flex-col items-center justify-center py-20">

              <div class="w-20 h-20 bg-gradient-to-br from-blue-100 to-indigo-100 rounded-2xl flex items-center justify-center mb-4">

                <Bell :size="36" class="text-blue-400" />

              </div>

              <h3 class="text-lg font-medium text-gray-900">暂无通知</h3>

              <p class="text-gray-500 mt-1">

                {{ searchQuery || filters.priority || filters.isRead ? '没有符合筛选条件的通知' : '您目前没有任何通知' }}

              </p>

            </div>



            <div v-else class="p-4 space-y-3">

              <div

                v-for="notification in filteredNotifications"

                :key="notification.id"

                @click="handleNotificationClick(notification)"

                :class="[

                  'relative p-5 rounded-2xl border transition-all cursor-pointer group',

                  selectedNotifications.has(notification.id)

                    ? 'bg-blue-50 border-blue-200'

                    : notification.isRead

                      ? 'bg-white border-gray-100 hover:border-gray-200 hover:shadow-sm'

                      : 'bg-gradient-to-r from-blue-50/50 to-indigo-50/50 border-blue-100 hover:border-blue-200'

                ]"

              >

                <div class="flex items-start gap-4">

                  <div v-if="isSelectionMode" class="flex-shrink-0 mt-1">

                    <div :class="[

                      'w-5 h-5 rounded-md border-2 flex items-center justify-center transition-colors',

                      selectedNotifications.has(notification.id)

                        ? 'bg-blue-500 border-blue-500'

                        : 'border-gray-300 group-hover:border-gray-400'

                    ]">

                      <Check v-if="selectedNotifications.has(notification.id)" :size="12" class="text-white" />

                    </div>

                  </div>



                  <div :class="[

                    'w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0',

                    notification.bgColor

                  ]">

                    <component :is="getNotificationIcon(notification.icon)" :size="22" :class="notification.iconColor" />

                  </div>



                  <div class="flex-1 min-w-0">

                    <div class="flex items-start justify-between gap-3">

                      <div class="flex-1 min-w-0">

                        <div class="flex items-center gap-2 mb-1">

                          <h4 :class="['font-semibold text-base', notification.isRead ? 'text-gray-700' : 'text-gray-900']">

                            {{ notification.title }}

                          </h4>

                          <span v-if="!notification.isRead" class="px-2 py-0.5 bg-blue-500 text-white text-xs rounded-full font-medium">

                            NEW

                          </span>

                        </div>

                        <p class="text-sm text-gray-600 leading-relaxed">{{ notification.message }}</p>

                      </div>



                      <div class="flex items-center gap-2 flex-shrink-0">

                        <span :class="[

                          'px-2.5 py-1 text-xs rounded-lg font-medium flex items-center gap-1',

                          getPriorityConfig(notification.priority).bg,

                          getPriorityConfig(notification.priority).text

                        ]">

                          <component :is="getPriorityConfig(notification.priority).icon" :size="12" />

                          {{ getPriorityConfig(notification.priority).label }}

                        </span>

                      </div>

                    </div>



                    <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-100/50">

                      <div class="flex items-center gap-3">

                        <span :class="[

                          'px-2.5 py-1 text-xs rounded-lg font-medium',

                          getCategoryColor(notification.category).bg,

                          getCategoryColor(notification.category).text

                        ]">

                          {{ categories.find(c => c.id === notification.category)?.label }}

                        </span>

                        <span class="text-xs text-gray-400">{{ formatTime(notification.createdAt) }}</span>

                      </div>



                      <div v-if="!isSelectionMode" class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">

                        <button

                          v-if="!notification.isRead"

                          @click.stop="markAsRead(notification.id)"

                          class="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"

                          title="标为已读"

                        >

                          <CheckCheck :size="16" />

                        </button>

                        <button

                          @click.stop="deleteNotification(notification.id)"

                          class="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"

                          title="删除"

                        >

                          <Trash2 :size="16" />

                        </button>

                      </div>

                    </div>

                  </div>

                </div>

              </div>

            </div>



            <div v-if="filteredNotifications.length > 0" class="p-4 border-t border-gray-100 bg-gray-50/50">

              <div class="flex items-center justify-between text-sm text-gray-500">

                <span>{{ filteredNotifications.length }} 条通知</span>

                <span>

                  {{ filteredNotifications.filter(n => !n.isRead).length }} 条未读                </span>

              </div>

            </div>

          </div>

        </div>

      </div>

    </div>

  </div>

</template>

