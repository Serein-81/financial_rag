<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { multiAgentApi, type HITLApproval, type UserRole, type RBACPolicy, ApprovalStatus, PermissionLevel } from '@/api/multi-agent'
import {
  Shield,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Loader2,
  RefreshCw,
  Eye,
  ChevronDown,
  ChevronUp,
  User,
  History,
  Settings,
  Key,
  AlertCircle,
} from 'lucide-vue-next'

const authStore = useAuthStore()

const isAdmin = computed(() => authStore.isAdmin || localStorage.getItem('rag_user_role') === 'admin')
const activeTab = ref<'pending' | 'history' | 'permissions'>('pending')

function switchTab(tabKey: string) {
  activeTab.value = tabKey as any
}
const isLoading = ref(true)
const isRefreshing = ref(false)

const pendingApprovals = ref<HITLApproval[]>([])
const approvalHistory = ref<HITLApproval[]>([])
const userRoles = ref<UserRole[]>([])
const rbacPolicies = ref<RBACPolicy[]>([])

const selectedApproval = ref<HITLApproval | null>(null)
const reviewNotes = ref('')
const isSubmitting = ref(false)

const riskLevelColors = {
  [PermissionLevel.PUBLIC]: { bg: 'bg-gradient-to-r from-gray-50 to-gray-100', text: 'text-gray-700', border: 'border-gray-200', label: '公开' },
  [PermissionLevel.SENSITIVE]: { bg: 'bg-gradient-to-r from-amber-50 to-yellow-100', text: 'text-amber-700', border: 'border-amber-200', label: '敏感' },
  [PermissionLevel.DANGEROUS]: { bg: 'bg-gradient-to-r from-orange-50 to-orange-100', text: 'text-orange-700', border: 'border-orange-200', label: '危险' },
  [PermissionLevel.CRITICAL]: { bg: 'bg-gradient-to-r from-red-50 to-red-100', text: 'text-red-700', border: 'border-red-200', label: '严重' },
}

const statusColors = {
  [ApprovalStatus.PENDING]: { bg: 'bg-gradient-to-r from-yellow-50 to-yellow-100', text: 'text-yellow-700', border: 'border-yellow-200', icon: Clock },
  [ApprovalStatus.APPROVED]: { bg: 'bg-gradient-to-r from-green-50 to-green-100', text: 'text-green-700', border: 'border-green-200', icon: CheckCircle2 },
  [ApprovalStatus.REJECTED]: { bg: 'bg-gradient-to-r from-red-50 to-red-100', text: 'text-red-700', border: 'border-red-200', icon: XCircle },
  [ApprovalStatus.TIMEOUT]: { bg: 'bg-gradient-to-r from-gray-50 to-gray-100', text: 'text-gray-700', border: 'border-gray-200', icon: AlertTriangle },
}

async function fetchData() {
  try {
    const [pending, history, roles, policies] = await Promise.all([
      multiAgentApi.getPendingApprovals(),
      multiAgentApi.getApprovalHistory({ limit: 50 }),
      multiAgentApi.getUserRoles(),
      multiAgentApi.getRBACPolicies(),
    ])
    pendingApprovals.value = pending
    approvalHistory.value = history
    userRoles.value = roles
    rbacPolicies.value = policies
  } catch (error) {
    console.error('获取HITL数据失败:', error)
  } finally {
    isLoading.value = false
    isRefreshing.value = false
  }
}

async function refresh() {
  isRefreshing.value = true
  await fetchData()
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('zh-CN')
}

function getTimeRemaining(expiresAt: string): string {
  const now = new Date()
  const expires = new Date(expiresAt)
  const diff = expires.getTime() - now.getTime()
  if (diff <= 0) return '已过期'
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes}分钟后过期`
  const hours = Math.floor(minutes / 60)
  return `${hours}小时后过期`
}

function selectApproval(approval: HITLApproval) {
  selectedApproval.value = selectedApproval.value?.approval_id === approval.approval_id ? null : approval
  reviewNotes.value = ''
}

async function handleReview(approvalId: string, action: 'approve' | 'reject') {
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    await multiAgentApi.reviewApproval(approvalId, action, reviewNotes.value || undefined)
    await fetchData()
    selectedApproval.value = null
    reviewNotes.value = ''
  } catch (error) {
    console.error('操作失败:', error)
  } finally {
    isSubmitting.value = false
  }
}

function getStatusLabel(status: ApprovalStatus): string {
  return {
    [ApprovalStatus.PENDING]: '待处理',
    [ApprovalStatus.APPROVED]: '已通过',
    [ApprovalStatus.REJECTED]: '已拒绝',
    [ApprovalStatus.TIMEOUT]: '已超时',
  }[status]
}

function getPermissionLabel(level: PermissionLevel): string {
  return {
    [PermissionLevel.PUBLIC]: '公开',
    [PermissionLevel.SENSITIVE]: '敏感',
    [PermissionLevel.DANGEROUS]: '危险',
    [PermissionLevel.CRITICAL]: '严重',
  }[level]
}

function getPolicyForRole(roleId: string) {
  return rbacPolicies.value.find(p => p.role === roleId)
}

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 via-white to-emerald-50 p-6">
    <div class="max-w-7xl mx-auto">
      <div class="flex items-center justify-between mb-8">
        <div class="flex items-center gap-4">
          <div class="p-3 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-2xl shadow-lg shadow-emerald-500/20">
            <Shield :size="28" class="text-white" />
          </div>
          <div>
            <h1 class="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent">
              安全审批中心
            </h1>
            <p class="text-sm text-gray-500 mt-1 flex items-center gap-2">
              <span v-if="isAdmin" class="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium">
                <Shield :size="12" />
                管理员
              </span>
              <span v-else class="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                <User :size="12" />
                用户
              </span>
              <span v-if="isAdmin">高风险操作需要您审批</span>
              <span v-else>高风险操作需要管理员审批</span>
            </p>
          </div>
        </div>
        <button
          @click="refresh"
          :disabled="isRefreshing"
          class="group flex items-center gap-2 px-5 py-2.5 bg-white border border-gray-200 rounded-xl hover:bg-emerald-50 hover:border-emerald-300 hover:shadow-lg hover:shadow-emerald-500/10 transition-all duration-200 disabled:opacity-50 disabled:hover:bg-white disabled:hover:shadow-none"
        >
          <RefreshCw :size="18" :class="{ 'animate-spin': isRefreshing }" class="text-gray-600 group-hover:text-emerald-600 transition-colors" />
          <span class="text-sm font-medium text-gray-700 group-hover:text-emerald-700 transition-colors">刷新</span>
        </button>
      </div>

      <div class="flex gap-3 mb-8">
        <button
          v-for="tab in [
            { key: 'pending', label: '待处理', badge: pendingApprovals.length, icon: AlertCircle },
            { key: 'history', label: '操作记录', icon: History },
            { key: 'permissions', label: '权限管理', icon: Shield },
          ]"
          :key="tab.key"
          @click="switchTab(tab.key)"
          :class="[
            'px-5 py-2.5 rounded-xl font-medium transition-all duration-200 flex items-center gap-2 shadow-sm',
            activeTab === tab.key
              ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-500/30 transform scale-105'
              : 'bg-white text-gray-600 hover:bg-gray-50 hover:shadow-md'
          ]"
        >
          <component :is="tab.icon" :size="18" />
          {{ tab.label }}
          <span
            v-if="tab.badge && tab.badge > 0"
            class="px-2 py-0.5 text-xs rounded-full font-bold animate-pulse"
            :class="activeTab === tab.key ? 'bg-emerald-300 text-white' : 'bg-red-500 text-white'"
          >
            {{ tab.badge }}
          </span>
        </button>
      </div>

      <div v-if="isLoading" class="flex flex-col items-center justify-center h-64 space-y-4">
        <Loader2 :size="40" class="animate-spin text-emerald-600" />
        <p class="text-gray-500 text-sm">加载中...</p>
      </div>

      <template v-else>
        <template v-if="activeTab === 'pending'">
          <div v-if="pendingApprovals.length === 0" class="bg-white rounded-2xl p-16 border border-gray-100 text-center shadow-lg shadow-gray-100/50">
            <div class="w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-green-100 to-emerald-100 rounded-full flex items-center justify-center">
              <CheckCircle2 :size="40" class="text-emerald-600" />
            </div>
            <h3 class="text-xl font-semibold text-gray-900 mb-2">太棒了！</h3>
            <p class="text-gray-500">暂无待处理的高风险操作</p>
          </div>

          <div v-else class="space-y-4">
            <div
              v-for="approval in pendingApprovals"
              :key="approval.approval_id"
              class="bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm hover:shadow-lg hover:shadow-gray-200/50 transition-all duration-300"
            >
              <div
                @click="selectApproval(approval)"
                class="p-6 cursor-pointer hover:bg-gradient-to-r hover:from-emerald-50/50 hover:to-teal-50/50 transition-all duration-200"
              >
                <div class="flex items-start justify-between">
                  <div class="flex-1">
                    <div class="flex items-center gap-3 mb-3">
                      <span :class="['px-3 py-1.5 rounded-lg text-xs font-bold border', riskLevelColors[approval.risk_level as PermissionLevel]?.bg, riskLevelColors[approval.risk_level as PermissionLevel]?.text, riskLevelColors[approval.risk_level as PermissionLevel]?.border]">
                        {{ riskLevelColors[approval.risk_level as PermissionLevel]?.label }}
                      </span>
                      <span class="text-sm text-gray-400 font-mono bg-gray-50 px-2 py-1 rounded">
                        {{ approval.user_id.slice(0, 8) }}...
                      </span>
                    </div>
                    <p class="font-semibold text-gray-900 text-lg mb-1">{{ approval.operation }}</p>
                    <p class="text-sm text-gray-500 font-mono">
                      任务: {{ approval.task_id.slice(0, 16) }}...
                    </p>
                  </div>
                  <div class="flex items-center gap-4">
                    <div class="text-right bg-orange-50 px-4 py-2 rounded-lg border border-orange-100">
                      <p class="text-sm text-orange-600 font-semibold flex items-center gap-1">
                        <Clock :size="14" />
                        {{ getTimeRemaining(approval.expires_at) }}
                      </p>
                    </div>
                    <div class="p-2 bg-gray-50 rounded-lg group-hover:bg-emerald-50 transition-colors">
                      <component :is="selectedApproval?.approval_id === approval.approval_id ? ChevronUp : ChevronDown" :size="20" class="text-gray-400 group-hover:text-emerald-600 transition-colors" />
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="selectedApproval?.approval_id === approval.approval_id" class="border-t border-gray-100 p-6 bg-gradient-to-b from-gray-50/50 to-white">
                <div class="bg-white rounded-xl p-5 mb-5 border border-gray-100 shadow-sm">
                  <div class="flex items-center gap-2 mb-3">
                    <Eye :size="16" class="text-gray-500" />
                    <h4 class="text-sm font-semibold text-gray-700">操作详情</h4>
                  </div>
                  <pre class="text-xs text-gray-600 bg-gradient-to-r from-gray-50 to-gray-100 p-4 rounded-lg overflow-x-auto border border-gray-100">{{ JSON.stringify(approval.details, null, 2) }}</pre>
                </div>

                <div v-if="approval.reviewer_notes" class="bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl p-4 mb-5 border border-emerald-100">
                  <h4 class="text-sm font-semibold text-emerald-700 mb-1 flex items-center gap-2">
                    <CheckCircle2 :size="14" />
                    审批备注
                  </h4>
                  <p class="text-sm text-emerald-600">{{ approval.reviewer_notes }}</p>
                </div>

                <div v-if="isAdmin" class="flex gap-3 mb-4">
                  <button
                    @click.stop="handleReview(approval.approval_id, 'approve')"
                    :disabled="isSubmitting"
                    class="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl hover:from-green-600 hover:to-emerald-600 transition-all duration-200 shadow-lg shadow-green-500/30 hover:shadow-green-500/40 disabled:opacity-50 font-semibold"
                  >
                    <CheckCircle2 :size="20" />
                    批准通过
                  </button>
                  <button
                    @click.stop="handleReview(approval.approval_id, 'reject')"
                    :disabled="isSubmitting"
                    class="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-red-500 to-rose-500 text-white rounded-xl hover:from-red-600 hover:to-rose-600 transition-all duration-200 shadow-lg shadow-red-500/30 hover:shadow-red-500/40 disabled:opacity-50 font-semibold"
                  >
                    <XCircle :size="20" />
                    拒绝操作
                  </button>
                </div>

                <div v-else class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-4 mb-4 border border-blue-100">
                  <p class="text-sm text-blue-700 text-center">
                    <Shield :size="16" class="inline mr-1" />
                    此操作需要管理员审批后才能执行
                  </p>
                </div>

                <div v-if="isAdmin" class="mt-4">
                  <label class="block text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                    <Key :size="14" />
                    添加备注（可选）
                  </label>
                  <textarea
                    v-model="reviewNotes"
                    rows="3"
                    class="w-full px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-300 transition-all resize-none"
                    placeholder="记录审批原因或备注信息..."
                  />
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-if="activeTab === 'history'">
          <div class="bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
            <table class="w-full">
              <thead class="bg-gradient-to-r from-gray-50 to-gray-100 border-b border-gray-100">
                <tr>
                  <th class="px-6 py-4 text-left text-sm font-bold text-gray-700">操作</th>
                  <th class="px-6 py-4 text-left text-sm font-bold text-gray-700">风险等级</th>
                  <th class="px-6 py-4 text-left text-sm font-bold text-gray-700">状态</th>
                  <th class="px-6 py-4 text-left text-sm font-bold text-gray-700">申请人</th>
                  <th class="px-6 py-4 text-left text-sm font-bold text-gray-700">处理时间</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-50">
                <tr
                  v-for="approval in approvalHistory"
                  :key="approval.approval_id"
                  class="hover:bg-gradient-to-r hover:from-emerald-50/30 hover:to-teal-50/30 transition-all duration-200"
                >
                  <td class="px-6 py-4">
                    <p class="font-semibold text-gray-900">{{ approval.operation }}</p>
                    <p class="text-xs text-gray-400 font-mono mt-1">{{ approval.task_id.slice(0, 16) }}...</p>
                  </td>
                  <td class="px-6 py-4">
                    <span :class="['px-3 py-1 rounded-lg text-xs font-bold border', riskLevelColors[approval.risk_level as PermissionLevel]?.bg, riskLevelColors[approval.risk_level as PermissionLevel]?.text, riskLevelColors[approval.risk_level as PermissionLevel]?.border]">
                      {{ riskLevelColors[approval.risk_level as PermissionLevel]?.label }}
                    </span>
                  </td>
                  <td class="px-6 py-4">
                    <span :class="['px-3 py-1 rounded-lg text-xs font-bold flex items-center gap-1.5 w-fit border', statusColors[approval.status]?.bg, statusColors[approval.status]?.text, statusColors[approval.status]?.border]">
                      <component :is="statusColors[approval.status]?.icon" :size="12" />
                      {{ getStatusLabel(approval.status) }}
                    </span>
                  </td>
                  <td class="px-6 py-4">
                    <span class="text-sm text-gray-600 font-mono bg-gray-50 px-2 py-1 rounded">{{ approval.user_id.slice(0, 8) }}...</span>
                  </td>
                  <td class="px-6 py-4 text-sm text-gray-500">
                    {{ approval.reviewed_at ? formatDate(approval.reviewed_at) : formatDate(approval.created_at) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <template v-if="activeTab === 'permissions'">
          <div class="space-y-8">
            <div class="mb-6">
              <div class="flex items-center gap-3 mb-4">
                <div class="w-1 h-6 bg-gradient-to-b from-emerald-500 to-teal-500 rounded-full"></div>
                <h2 class="text-lg font-bold text-gray-900">系统权限配置</h2>
                <span class="text-sm text-gray-500 ml-auto">共 2 种角色</span>
              </div>
              <p class="text-sm text-gray-500">清晰展示每个角色的权限等级和允许/禁止的操作</p>
            </div>
            
            <div
              v-for="role in userRoles"
              :key="role.role_id"
              :class="[
                'bg-white rounded-2xl border-2 overflow-hidden shadow-lg transition-all duration-300 hover:shadow-xl',
                role.role_id === 'admin' 
                  ? 'border-emerald-200' 
                  : 'border-blue-200'
              ]"
            >
              <div :class="[
                'px-6 py-5 border-b-2 flex items-center gap-4',
                role.role_id === 'admin' 
                  ? 'bg-gradient-to-r from-emerald-50 to-teal-50 border-emerald-200' 
                  : 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200'
              ]">
                <div :class="[
                  'p-3 rounded-xl shadow-lg',
                  role.role_id === 'admin' 
                    ? 'bg-gradient-to-br from-emerald-500 to-teal-600 shadow-emerald-500/30' 
                    : 'bg-gradient-to-br from-blue-500 to-indigo-600 shadow-blue-500/30'
                ]">
                  <Shield v-if="role.role_id === 'admin'" :size="24" class="text-white" />
                  <User v-else :size="24" class="text-white" />
                </div>
                <div class="flex-1">
                  <h3 class="font-bold text-gray-900 text-xl">{{ role.role_name }}</h3>
                  <p class="text-sm text-gray-500 mt-0.5">
                    {{ role.role_id === 'admin' ? '拥有最高权限，可审批所有高风险操作' : '基础权限，需管理员审批高风险操作' }}
                  </p>
                </div>
                <div class="flex items-center gap-2">
                  <span class="px-3 py-1 rounded-full text-xs font-bold bg-white border-2"
                    :class="role.role_id === 'admin' 
                      ? 'text-emerald-700 border-emerald-300' 
                      : 'text-blue-700 border-blue-300'"
                  >
                    {{ role.role_id }}
                  </span>
                </div>
              </div>
              
              <div class="p-6">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <div class="lg:col-span-1">
                    <div class="flex items-center gap-2 mb-4">
                      <div class="w-2 h-2 rounded-full bg-gradient-to-r from-purple-400 to-pink-500"></div>
                      <h4 class="text-sm font-bold text-gray-900">权限等级</h4>
                      <span class="ml-auto text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-full">{{ role.permissions.length }} 个</span>
                    </div>
                    
                    <div class="grid grid-cols-2 gap-3">
                      <div
                        v-for="perm in role.permissions"
                        :key="perm"
                        :class="[
                          'flex items-center gap-2 px-3 py-2.5 rounded-xl border-2 transition-all duration-200 hover:scale-105',
                          riskLevelColors[perm as PermissionLevel]?.bg,
                          riskLevelColors[perm as PermissionLevel]?.text,
                          riskLevelColors[perm as PermissionLevel]?.border,
                        ]"
                      >
                        <CheckCircle2 :size="14" :class="riskLevelColors[perm as PermissionLevel]?.text" />
                        <span class="text-xs font-bold">{{ getPermissionLabel(perm as PermissionLevel) }}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div class="lg:col-span-1">
                    <div class="flex items-center gap-2 mb-4">
                      <div class="w-2 h-2 rounded-full bg-gradient-to-r from-green-400 to-emerald-500"></div>
                      <h4 class="text-sm font-bold text-gray-900">允许的操作</h4>
                    </div>
                    
                    <div v-if="getPolicyForRole(role.role_id)?.allowed_operations[0] === '*'" class="p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl border border-green-200">
                      <div class="flex items-center gap-3">
                        <div class="p-2 bg-green-100 rounded-lg">
                          <CheckCircle2 :size="18" class="text-green-600" />
                        </div>
                        <div>
                          <p class="font-bold text-green-800">完全访问权限</p>
                          <p class="text-xs text-green-600 mt-0.5">可执行所有操作</p>
                        </div>
                      </div>
                    </div>
                    
                    <div v-else class="space-y-2">
                      <div
                        v-for="(op, idx) in getPolicyForRole(role.role_id)?.allowed_operations || []"
                        :key="idx"
                        class="flex items-center gap-2 p-2.5 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-100 hover:shadow-md transition-all duration-200"
                      >
                        <CheckCircle2 :size="14" class="text-green-600 flex-shrink-0" />
                        <span class="text-xs font-medium text-green-800 truncate">{{ op }}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div class="lg:col-span-1">
                    <div class="flex items-center gap-2 mb-4">
                      <div class="w-2 h-2 rounded-full bg-gradient-to-r from-red-400 to-rose-500"></div>
                      <h4 class="text-sm font-bold text-gray-900">禁止的操作</h4>
                    </div>
                    
                    <div v-if="!getPolicyForRole(role.role_id)?.denied_operations || getPolicyForRole(role.role_id)?.denied_operations.length === 0" class="p-4 bg-gradient-to-r from-gray-50 to-gray-100 rounded-xl border border-gray-200">
                      <div class="flex items-center gap-3">
                        <div class="p-2 bg-gray-100 rounded-lg">
                          <Shield :size="18" class="text-gray-500" />
                        </div>
                        <div>
                          <p class="font-bold text-gray-700">无限制</p>
                          <p class="text-xs text-gray-500 mt-0.5">该角色无禁止操作</p>
                        </div>
                      </div>
                    </div>
                    
                    <div v-else class="space-y-2">
                      <div
                        v-for="(op, idx) in getPolicyForRole(role.role_id)?.denied_operations || []"
                        :key="idx"
                        class="flex items-center gap-2 p-2.5 bg-gradient-to-r from-red-50 to-rose-50 rounded-lg border border-red-100 hover:shadow-md transition-all duration-200"
                      >
                        <XCircle :size="14" class="text-red-600 flex-shrink-0" />
                        <span class="text-xs font-medium text-red-800 truncate">{{ op }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                
                <div class="mt-6 pt-4 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                  <div class="flex items-center gap-2">
                    <Clock :size="12" />
                    <span>配置时间: {{ formatDate(getPolicyForRole(role.role_id)?.created_at || new Date().toISOString()) }}</span>
                  </div>
                  <div class="flex items-center gap-3">
                    <span class="px-2 py-1 bg-green-50 text-green-600 rounded-md border border-green-200 font-medium">
                      {{ getPolicyForRole(role.role_id)?.allowed_operations?.length || 0 }} 允许
                    </span>
                    <span class="px-2 py-1 bg-red-50 text-red-600 rounded-md border border-red-200 font-medium">
                      {{ getPolicyForRole(role.role_id)?.denied_operations?.length || 0 }} 禁止
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>
