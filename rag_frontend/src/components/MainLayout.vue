<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'
import {
  MessageSquare,
  Database,
  FileText,
  Search,
  Users,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  User,
  Network,
  History,
  Shield,
  Upload,
  BarChart3,
  FileBarChart,
  UsersRound,
  TrendingUp
} from 'lucide-vue-next'
import NotificationBar from './NotificationBar.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const sessionStore = useSessionStore()

const isSidebarCollapsed = ref(localStorage.getItem('sidebar_collapsed') === 'true')
const showUserMenu = ref(false)

watch(() => sessionStore.showSessionsPanel, (showSessions) => {
  if (showSessions) {
    isSidebarCollapsed.value = true
  }
})

watch(isSidebarCollapsed, (collapsed) => {
  localStorage.setItem('sidebar_collapsed', collapsed.toString())
})

const isAdmin = computed(() => authStore.isAdmin || localStorage.getItem('rag_user_role') === 'admin')
const userEmail = computed(() => authStore.userEmail || localStorage.getItem('rag_user_email') || '')

const menuItems = computed(() => {
  const items = [
    { path: '/', icon: MessageSquare, label: '智能对话', name: 'chat' },
    { path: '/group-chat', icon: UsersRound, label: '群组聊天', name: 'group-chat' },
    { path: '/search', icon: Search, label: '知识搜索', name: 'search' },
    { path: '/knowledge', icon: Database, label: '知识库管理', name: 'knowledge' },
    { path: '/sessions', icon: History, label: '会话历史', name: 'sessions' },
    { path: '/chat-logs', icon: BarChart3, label: '日志详情', name: 'chat-logs' },
    { path: '/knowledge-graph', icon: Network, label: '知识图谱', name: 'knowledge-graph' },
    { path: '/tax-submission', icon: FileBarChart, label: '税务提交', name: 'tax-submission' },
    { path: '/analytics', icon: TrendingUp, label: '运营分析', name: 'analytics' },
  ]

  if (isAdmin.value) {
    items.push(
      { path: '/enterprise', icon: Users, label: '企业管理', name: 'enterprise' },
      { path: '/audit/upload', icon: Shield, label: '审计系统', name: 'audit' }
    )
  }

  items.push({ path: '/profile', icon: User, label: '个人中心', name: 'profile' })

  return items
})

function isActive(path: string): boolean {
  if (path === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(path)
}

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

function logout() {
  authStore.logout()
  router.push('/login')
}

function goToProfile() {
  router.push('/profile')
  showUserMenu.value = false
}
</script>

<template>
  <div class="flex h-screen bg-gray-50">
    <!-- Sidebar -->
    <aside
      :class="[
        'bg-white border-r border-gray-200 flex flex-col transition-all duration-300',
        isSidebarCollapsed ? 'w-16' : 'w-64'
      ]"
    >
      <!-- Logo -->
      <div class="h-16 flex items-center justify-between px-4 border-b border-gray-200">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <Sparkles :size="18" class="text-white" />
          </div>
          <span v-if="!isSidebarCollapsed" class="font-bold text-gray-900">RAG Terminal</span>
        </div>
        <button
          @click="toggleSidebar"
          class="p-1.5 hover:bg-gray-100 rounded-md transition-colors"
        >
          <ChevronLeft v-if="!isSidebarCollapsed" :size="18" class="text-gray-500" />
          <ChevronRight v-else :size="18" class="text-gray-500" />
        </button>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          :class="[
            'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors group relative',
            isActive(item.path)
              ? 'bg-blue-50 text-blue-600'
              : 'text-gray-600 hover:bg-gray-100'
          ]"
        >
          <component :is="item.icon" :size="20" :class="isActive(item.path) ? 'text-blue-600' : 'text-gray-500 group-hover:text-gray-700'" />
          <span v-if="!isSidebarCollapsed" class="font-medium">{{ item.label }}</span>
          <div
            v-if="isSidebarCollapsed"
            class="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-white text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50"
          >
            {{ item.label }}
          </div>
        </router-link>
      </nav>

      <!-- User Section -->
      <div class="border-t border-gray-200 p-4">
        <div v-if="!isSidebarCollapsed" class="flex items-center gap-3">
          <img
            :src="authStore.avatarUrl || authStore.userName?.charAt(0)"
            :alt="authStore.userName"
            class="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-medium"
          />
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-900 truncate">{{ authStore.userName }}</p>
            <p class="text-xs text-gray-500 truncate">{{ userEmail }}</p>
          </div>
          <div class="relative">
            <button
              @click="showUserMenu = !showUserMenu"
              class="p-1.5 hover:bg-gray-100 rounded-md transition-colors"
            >
              <Settings :size="18" class="text-gray-500" />
            </button>
            <div
              v-if="showUserMenu"
              class="absolute bottom-full right-0 mb-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1"
            >
              <button
                @click="goToProfile"
                class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
              >
                <User :size="16" />
                个人中心
              </button>
              <button
                @click="logout"
                class="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-gray-100 flex items-center gap-2"
              >
                <LogOut :size="16" />
                退出登录
              </button>
            </div>
          </div>
        </div>
        <div v-else class="flex flex-col items-center gap-2">
          <div class="relative group">
            <img
              :src="authStore.avatarUrl || authStore.userName?.charAt(0)"
              :alt="authStore.userName"
              class="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-medium cursor-pointer"
            />
            <div class="absolute left-full ml-2 bottom-0 px-2 py-1 bg-gray-900 text-white text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
              {{ authStore.userName }}
            </div>
          </div>
          <button
            @click="logout"
            class="p-2 hover:bg-gray-100 rounded-lg transition-colors relative group"
          >
            <LogOut :size="20" class="text-gray-500" />
            <div class="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-white text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
              退出登录
            </div>
          </button>
        </div>
      </div>
    </aside>

    <!-- Notification Center - positioned relative to viewport -->
    <NotificationBar v-if="!isSidebarCollapsed" class="fixed top-4 right-4 z-50" />

    <!-- Main Content -->
    <main class="flex-1 overflow-hidden">
      <router-view />
    </main>
  </div>
</template>
