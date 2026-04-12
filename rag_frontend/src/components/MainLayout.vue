<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'
import { useGroupChatStore } from '@/stores/group-chat'
import { useEnterpriseTheme } from '@/composables/useEnterpriseTheme'
import {
  MessageSquare,
  Database,
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
  BarChart3,
  FileBarChart,
  UsersRound,
  TrendingUp,
  Bot,
  CheckCircle,
  Brain,
  AlertTriangle,
  Bell,
  ChevronDown,
  Eye,
  Wrench,
  PanelLeftClose,
  PanelLeft,
  Target,
  GitBranch,
  Edit3,
  Gift,
  Activity,
  Clock,
  ListChecks,
  FileText,
  Scale,
  DollarSign,
  BellRing,
  PiggyBank,
  BarChart,
  ScrollText,
} from 'lucide-vue-next'
import NotificationBar from './NotificationBar.vue'

type MenuRole = 'user' | 'admin' | 'both'
type MenuPermission = MenuRole | MenuRole[]

interface MenuItem {
  path: string
  icon: any
  label: string
  name: string
  permission?: MenuPermission
}

interface MenuGroup {
  id: string
  title: string
  icon: any
  defaultExpanded?: boolean
  items: MenuItem[]
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const sessionStore = useSessionStore()
const groupChatStore = useGroupChatStore()

const { enterpriseTheme } = useEnterpriseTheme()

const primaryColor = computed(() => enterpriseTheme.value.primary_color)
const secondaryColor = computed(() => enterpriseTheme.value.secondary_color)

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

const isSidebarCollapsed = ref(localStorage.getItem('sidebar_collapsed') === 'true')
const showUserMenu = ref(false)
const showNotificationPanel = ref(false)

const expandedGroups = ref<Set<string>>(new Set(['collaboration', 'knowledge', 'finance']))

onMounted(async () => {
  await groupChatStore.fetchNotifications()
  groupChatStore.startNotificationPoll()
})

onUnmounted(() => {
  groupChatStore.stopNotificationPoll()
})

watch(() => sessionStore.showSessionsPanel, (showSessions) => {
  if (showSessions) {
    isSidebarCollapsed.value = true
  }
})

watch(isSidebarCollapsed, (collapsed) => {
  localStorage.setItem('sidebar_collapsed', collapsed.toString())
  if (collapsed) {
    expandedGroups.value.clear()
  }
})

const isAdmin = computed(() => authStore.isAdmin || localStorage.getItem('rag_user_role') === 'admin')
const userRole = computed<MenuRole>(() => isAdmin.value ? 'admin' : 'user')
const userEmail = computed(() => authStore.userEmail || localStorage.getItem('rag_user_email') || '')

const menuGroups = computed<MenuGroup[]>(() => {
  const groups: MenuGroup[] = [
    {
      id: 'collaboration',
      title: '智能对话',
      icon: MessageSquare,
      defaultExpanded: true,
      items: [
        { path: '/', icon: MessageSquare, label: '智能对话', name: 'chat' },
        { path: '/multi-agent', icon: Brain, label: '多智能体协作', name: 'multi-agent-chat' },
        { path: '/group-chat', icon: UsersRound, label: '群组聊天', name: 'group-chat' },
      ]
    },
    {
      id: 'knowledge',
      title: '知识管理',
      icon: Database,
      defaultExpanded: true,
      items: [
        { path: '/search', icon: Search, label: '知识搜索', name: 'search' },
        { path: '/knowledge', icon: Database, label: '知识库管理', name: 'knowledge' },
        { path: '/knowledge-graph', icon: Network, label: '知识图谱', name: 'knowledge-graph' },
        { path: '/knowledge-graph-editor', icon: Edit3, label: '知识图谱编辑器', name: 'knowledge-graph-editor' },
      ]
    },
    {
      id: 'finance',
      title: '财税业务',
      icon: FileBarChart,
      defaultExpanded: true,
      items: [
        { path: '/financial-data-entry', icon: PiggyBank, label: '财务数据录入', name: 'financial-data-entry' },
        { path: '/tax-intelligence', icon: DollarSign, label: '税务智能分析', name: 'tax-intelligence' },
        { path: '/financial-health', icon: Activity, label: '财务健康监控', name: 'financial-health' },
        { path: '/contract-review', icon: Scale, label: '合同智能审核', name: 'contract-review' },
        { path: '/tax-submission', icon: FileBarChart, label: '税务提交', name: 'tax-submission' },
        { path: '/hitl-approval', icon: CheckCircle, label: 'HITL审批', name: 'hitl-approval', permission: 'admin' },
      ]
    },
    {
      id: 'policy',
      title: '政策服务',
      icon: Sparkles,
      defaultExpanded: true,
      items: [
        { path: '/policy', icon: Sparkles, label: '政策管理', name: 'policy' },
        { path: '/policy-search', icon: Brain, label: '政策匹配', name: 'policy-search' },
        { path: '/policy-notifications', icon: BellRing, label: '政策通知', name: 'policy-notifications' },
        { path: '/enterprise-match', icon: Target, label: '企业匹配', name: 'enterprise-match' },
      ]
    },
    {
      id: 'data',
      title: '数据与监控',
      icon: BarChart3,
      defaultExpanded: true,
      items: [
        { path: '/analytics', icon: TrendingUp, label: '运营分析', name: 'analytics' },
        { path: '/chat-logs', icon: ScrollText, label: '日志详情', name: 'chat-logs' },
        { path: '/task-management', icon: Clock, label: '定时任务', name: 'task-management' },
      ]
    },
    {
      id: 'system',
      title: '系统与开发',
      icon: Wrench,
      defaultExpanded: false,
      items: [
        { path: '/agent-center', icon: Bot, label: '智能体中心', name: 'agent-center', permission: 'admin' },
        { path: '/intent-debug', icon: Brain, label: '意图调试', name: 'intent-debug', permission: 'admin' },
        { path: '/security-audit', icon: AlertTriangle, label: '安全审计', name: 'security-audit', permission: 'admin' },
        { path: '/enterprise', icon: Users, label: '企业管理', name: 'enterprise', permission: 'admin' },
        { path: '/audit/upload', icon: Shield, label: '审计系统', name: 'audit', permission: 'admin' },
      ]
    },
  ]

  return groups
})

const filteredMenuGroups = computed(() => {
  const role = userRole.value
  return menuGroups.value
    .map(group => ({
      ...group,
      items: group.items.filter(item => {
        if (!item.permission) return true
        if (Array.isArray(item.permission)) {
          return item.permission.includes(role)
        }
        return item.permission === role || item.permission === 'both'
      })
    }))
    .filter(group => group.items.length > 0)
})

const flattenedMenuItems = computed(() => {
  return filteredMenuGroups.value.flatMap(group => group.items)
})

const hasActiveGroup = (group: MenuGroup): boolean => {
  return group.items.some(item => isActive(item.path))
}

function isActive(path: string): boolean {
  if (path === '/') {
    return route.path === '/'
  }
  const currentPath = route.path
  if (currentPath === path) return true
  if (path !== '/' && currentPath.startsWith(path + '/')) return true
  return false
}

function toggleGroup(groupId: string) {
  if (isSidebarCollapsed.value) return
  if (expandedGroups.value.has(groupId)) {
    expandedGroups.value.delete(groupId)
  } else {
    expandedGroups.value.add(groupId)
  }
  expandedGroups.value = new Set(expandedGroups.value)
}

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

function toggleNotificationsInSidebar() {
  showNotificationPanel.value = !showNotificationPanel.value
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
  <div class="flex h-screen bg-slate-100">
    <!-- Sidebar -->
    <aside
      :class="[
        'bg-slate-50 flex flex-col transition-all duration-300',
        isSidebarCollapsed ? 'w-16' : 'w-60'
      ]"
    >
      <!-- Theme Color Bar -->
      <div class="h-1 flex flex-shrink-0" :style="{ background: `linear-gradient(90deg, ${primaryColor} 0%, ${secondaryColor} 100%)` }"></div>
      
      <!-- Logo -->
      <div class="h-14 flex items-center justify-between px-4">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-slate-900 rounded-lg flex items-center justify-center flex-shrink-0 shadow-sm">
            <Database :size="16" class="text-white" />
          </div>
          <span v-if="!isSidebarCollapsed" class="font-bold text-slate-900 tracking-tight text-sm">企业财税智能平台</span>
        </div>
        <button
          @click="toggleSidebar"
          :class="[
            'rounded-md transition-colors',
            isSidebarCollapsed ? 'p-2 w-full flex justify-center hover:bg-slate-200' : 'p-1.5 hover:bg-slate-200'
          ]"
          :title="isSidebarCollapsed ? '展开菜单' : '收起菜单'"
        >
          <PanelLeft v-if="isSidebarCollapsed" :size="16" class="text-slate-500" />
          <PanelLeftClose v-else :size="16" class="text-slate-500" />
        </button>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 py-2 px-3 overflow-y-auto custom-scrollbar">
        <!-- Collapsed State: Show only icons with tooltips -->
        <template v-if="isSidebarCollapsed">
          <div class="space-y-0.5">
            <router-link
              v-for="item in flattenedMenuItems"
              :key="item.path"
              :to="item.path"
              :class="[
                'relative w-full flex items-center justify-center h-10 rounded-lg transition-all duration-150 group text-slate-400 hover:text-slate-900'
              ]"
              :style="isActive(item.path) ? { color: primaryColor } : {}"
            >
              <component :is="item.icon" :size="18" />
              <div
                class="absolute left-full ml-2 px-2 py-1 bg-slate-900 text-white text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50"
              >
                {{ item.label }}
              </div>
            </router-link>
          </div>
        </template>

        <!-- Expanded State: Show grouped accordion menu -->
        <template v-else>
          <div v-for="group in filteredMenuGroups" :key="group.id" class="mt-5 first:mt-0">
            <!-- Level 1: Parent Category Header -->
            <div class="mb-1.5 px-3">
              <button
                @click="toggleGroup(group.id)"
                :class="[
                  'flex items-center justify-between w-full px-3 py-2.5 rounded-lg transition-all duration-200',
                  hasActiveGroup(group)
                    ? 'bg-slate-50 text-slate-900 font-bold'
                    : 'text-slate-600 font-medium hover:bg-slate-100/70'
                ]"
              >
                <div class="flex items-center gap-3">
                  <component
                    :is="group.icon"
                    :size="16"
                    :class="'text-slate-400'"
                    :style="hasActiveGroup(group) ? { color: primaryColor } : {}"
                  />
                  <span>{{ group.title }}</span>
                </div>
                <ChevronDown
                  :size="14"
                  :class="[
                    'transition-transform duration-200',
                    hasActiveGroup(group) ? 'rotate-180 text-slate-900' : 'text-slate-400'
                  ]"
                />
              </button>
            </div>

            <!-- Level 2: Child Items Container with Tree Line -->
            <div
              v-show="expandedGroups.has(group.id)"
              class="ml-5 mt-0.5 pl-4 border-l border-slate-200 flex flex-col gap-0.5"
            >
              <router-link
                v-for="item in group.items"
                :key="item.path"
                :to="item.path"
                :class="[
                  'group relative flex items-center w-full py-2 px-3 rounded-md text-sm transition-all duration-150',
                  isActive(item.path)
                    ? 'font-semibold'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100/50'
                ]"
                :style="isActive(item.path) ? { backgroundColor: hexToRgba(primaryColor, 0.1) } : {}"
              >
                <div
                  v-if="isActive(item.path)"
                  class="absolute -left-[17px] top-1/2 -translate-y-1/2 w-[2px] h-full rounded-r-full"
                  :style="{ backgroundColor: primaryColor }"
                ></div>
                <component
                  :is="item.icon"
                  :size="15"
                  class="mr-2.5 transition-colors text-slate-400 group-hover:text-slate-600"
                  :style="isActive(item.path) ? { color: primaryColor } : {}"
                />
                <span>{{ item.label }}</span>
              </router-link>
            </div>
          </div>
        </template>
      </nav>

      <!-- Bottom Section: Notification + User -->
      <div class="mt-auto border-t border-slate-200/60">
        <!-- Notification Button -->
        <button
          @click="toggleNotificationsInSidebar"
          :class="[
            'w-full flex items-center gap-3 px-4 h-11 transition-colors relative',
            isSidebarCollapsed ? 'justify-center' : ''
          ]"
        >
          <Bell :size="17" class="text-slate-400" />
          <span v-if="!isSidebarCollapsed" class="text-sm text-slate-600">通知中心</span>
          <span
            v-if="groupChatStore.unreadCount > 0"
            class="absolute right-3 top-1/2 -translate-y-1/2 min-w-[16px] h-[16px] bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center px-1"
            :style="isSidebarCollapsed ? 'position: absolute; top: 2px; right: 2px;' : ''"
          >
            {{ groupChatStore.unreadCount > 99 ? '99+' : groupChatStore.unreadCount }}
          </span>
        </button>

        <!-- User Section -->
        <div class="p-3">
          <div v-if="!isSidebarCollapsed" class="flex items-center gap-2.5">
            <div class="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-700 font-medium text-sm flex-shrink-0">
              {{ authStore.userName?.charAt(0)?.toUpperCase() || 'U' }}
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-slate-900 truncate">{{ authStore.userName }}</p>
              <p class="text-xs text-slate-500 truncate">{{ userEmail }}</p>
            </div>
            <div class="relative">
              <button
                @click="showUserMenu = !showUserMenu"
                class="p-1.5 rounded-md transition-colors"
                :class="showUserMenu ? 'bg-slate-200 text-slate-600' : 'text-slate-300 hover:text-slate-600 hover:bg-slate-100'"
                title="设置"
              >
                <Settings :size="15" />
              </button>
              <div
                v-if="showUserMenu"
                class="absolute bottom-full right-0 mb-2 w-44 bg-white rounded-lg shadow-lg border border-slate-200/80 py-1 z-50"
              >
                <button
                  @click="goToProfile"
                  class="w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                >
                  <User :size="14" />
                  个人中心
                </button>
                <button
                  v-if="isAdmin"
                  @click="router.push('/enterprise'); showUserMenu = false"
                  class="w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                >
                  <Users :size="14" />
                  企业管理
                </button>
                <button
                  @click="logout"
                  class="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-slate-50 flex items-center gap-2"
                >
                  <LogOut :size="14" />
                  退出登录
                </button>
              </div>
            </div>
          </div>
          <div v-else class="flex flex-col items-center gap-1.5">
            <div class="relative group">
              <div class="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-700 font-medium text-sm cursor-pointer">
                {{ authStore.userName?.charAt(0)?.toUpperCase() || 'U' }}
              </div>
              <div class="absolute left-full ml-2 px-2 py-1 bg-slate-900 text-white text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                {{ authStore.userName }}
              </div>
            </div>
            <button
              @click="logout"
              class="p-1.5 rounded-md transition-colors relative group text-slate-300 hover:text-slate-600 hover:bg-slate-100"
              title="退出登录"
            >
              <LogOut :size="15" />
              <div class="absolute left-full ml-2 px-2 py-1 bg-slate-900 text-white text-xs rounded-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                退出登录
              </div>
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 overflow-y-auto relative">
      <router-view />
    </main>

    <!-- Notification Panel -->
    <div @click.stop>
      <NotificationBar
        v-model="showNotificationPanel"
      />
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 3px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #cbd5e1;
  border-radius: 2px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: #94a3b8;
}
</style>
