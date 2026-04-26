<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { enterpriseApi } from '@/api/enterprise'
import { tenantSettingsApi, type TenantSettings, type TenantSettingsUpdate } from '@/api/tenant-settings'
import { useEnterpriseTheme } from '@/composables/useEnterpriseTheme'
import { useAuthStore } from '@/stores/auth'
import type { EnterpriseUser, InviteCode, EnterpriseResponse } from '@/api/enterprise'
import {
  Users,
  Key,
  Plus,
  Copy,
  Check,
  Trash2,
  Shield,
  Loader2,
  AlertCircle,
  CheckCircle,
  UserX,
  UserCheck,
  Crown,
  Settings,
  Building2,
  Sliders,
  Palette,
  Bell,
  ToggleLeft,
  ToggleRight,
  Save,
  RefreshCw,
  Gift,
  Filter,
  Download,
  Search,
  MoreVertical,
  ChevronDown,
  Eye,
  Edit3,
  X
} from 'lucide-vue-next'

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin || localStorage.getItem('rag_user_role') === 'admin')

const activeTab = ref<'users' | 'invites' | 'settings'>('users')
const isLoading = ref(false)
const error = ref('')
const success = ref('')
const savingSettings = ref(false)

// Enterprise data
const enterpriseInfo = ref<EnterpriseResponse | null>(null)
const users = ref<EnterpriseUser[]>([])
const inviteCodes = ref<InviteCode[]>([])

// Tenant settings data
const tenantSettings = ref<TenantSettings | null>(null)
const settingsForm = ref<TenantSettingsUpdate>({})

// Modal states
const showCreateInviteModal = ref(false)
const inviteCodeForm = ref({
  max_uses: 1,
  expires_in_days: 7
})

const copiedCode = ref('')

// Invite codes filter & pagination
const inviteFilter = ref<'all' | 'valid' | 'exhausted' | 'expired'>('all')
const inviteSearchQuery = ref('')
const invitePagination = ref({
  page: 1,
  pageSize: 20,
  total: 0
})
const showBatchCreateModal = ref(false)
const showDeleteConfirmModal = ref(false)
const deleteTargetCode = ref<string | null>(null)
const batchForm = ref({
  count: 10,
  max_uses: 1,
  expires_in_days: 7
})
const actionMenuCode = ref<string | null>(null)

// Enterprise profile options for policy matching
const profileOptions = {
  industries: ['制造业', '科技', '金融', '房地产', '零售', '医疗', '教育', '能源', '餐饮', '物流', '农业', '建筑'],
  regions: ['全国', '北京', '上海', '广州', '深圳', '浙江', '江苏', '广东', '四川', '湖北', '山东', '福建'],
  scales: ['大型企业', '中型企业', '小型企业', '微型企业'],
  taxTypes: ['增值税', '企业所得税', '个人所得税', '消费税', '关税', '印花税', '土地增值税', '房产税', '车船税']
}

// Computed: Invite code statistics
const inviteStats = computed(() => {
  const codes = inviteCodes.value
  const now = new Date()
  return {
    total: codes.length,
    valid: codes.filter(c => c.is_active && new Date(c.expires_at) > now && c.used_count < c.max_uses).length,
    exhausted: codes.filter(c => c.used_count >= c.max_uses && c.max_uses > 0).length,
    expired: codes.filter(c => new Date(c.expires_at) <= now).length
  }
})

// Computed: Filtered and paginated invite codes
const filteredInviteCodes = computed(() => {
  let codes = [...inviteCodes.value]
  const now = new Date()

  // Apply filter
  switch (inviteFilter.value) {
    case 'valid':
      codes = codes.filter(c => c.is_active && new Date(c.expires_at) > now && c.used_count < c.max_uses)
      break
    case 'exhausted':
      codes = codes.filter(c => c.used_count >= c.max_uses && c.max_uses > 0)
      break
    case 'expired':
      codes = codes.filter(c => !c.is_active || new Date(c.expires_at) <= now)
      break
  }

  // Apply search
  if (inviteSearchQuery.value.trim()) {
    const query = inviteSearchQuery.value.toLowerCase()
    codes = codes.filter(c => c.code.toLowerCase().includes(query))
  }

  return codes
})

const paginatedInviteCodes = computed(() => {
  const start = (invitePagination.value.page - 1) * invitePagination.value.pageSize
  const end = start + invitePagination.value.pageSize
  return filteredInviteCodes.value.slice(start, end)
})

const totalPages = computed(() => {
  return Math.ceil(filteredInviteCodes.value.length / invitePagination.value.pageSize) || 1
})

function normalizeColor(color: string): string {
  if (!color) return '#1890ff'
  color = color.trim()
  if (!color.startsWith('#')) {
    color = '#' + color
  }
  if (color.length === 4) {
    color = '#' + color[1] + color[1] + color[2] + color[2] + color[3] + color[3]
  }
  if (/^#[0-9A-Fa-f]{6}$/.test(color)) {
    return color.toLowerCase()
  }
  if (/^#[0-9A-Fa-f]{3}$/.test(color)) {
    return '#' + color[1] + color[1] + color[2] + color[2] + color[3] + color[3]
  }
  return '#1890ff'
}

onMounted(async () => {
  await loadData()
  if (activeTab.value === 'settings') {
    await loadTenantSettings()
  }
})

async function loadData() {
  try {
    isLoading.value = true
    error.value = ''

    if (isAdmin.value) {
      const [info, usersData, codesData] = await Promise.all([
        enterpriseApi.getEnterprise().catch(() => null),
        enterpriseApi.getUsers().catch(err => {
          console.error('Failed to load users:', err)
          return []
        }),
        enterpriseApi.getInviteCodes().catch(err => {
          console.error('Failed to load invite codes:', err)
          return []
        })
      ])
      enterpriseInfo.value = info
      users.value = usersData
      inviteCodes.value = codesData
    } else {
      enterpriseInfo.value = await enterpriseApi.getEnterprise().catch(err => {
        console.error('Failed to load enterprise info:', err)
        return null
      })
      users.value = []
      inviteCodes.value = []
    }
  } catch (err: any) {
    error.value = err.message || '加载数据失败'
  } finally {
    isLoading.value = false
  }
}

// Toggle tax type selection (for multi-select)
function toggleTaxType(taxType: string) {
  if (!settingsForm.value.tax_types) {
    settingsForm.value.tax_types = []
  }
  const index = settingsForm.value.tax_types.indexOf(taxType)
  if (index === -1) {
    settingsForm.value.tax_types.push(taxType)
  } else {
    settingsForm.value.tax_types.splice(index, 1)
  }
}

async function loadTenantSettings() {
  try {
    isLoading.value = true
    error.value = ''
    
    console.log('[TenantSettings] Loading settings from API')
    const response = await tenantSettingsApi.getMySettings()
    const settings = response.data || response
    console.log('[TenantSettings] Settings loaded:', settings)
    console.log('[TenantSettings] primary_color from API:', settings?.primary_color)
    console.log('[TenantSettings] secondary_color from API:', settings?.secondary_color)
    tenantSettings.value = settings
    
    const primaryColor = normalizeColor(settings?.primary_color || '#1890ff')
    const secondaryColor = normalizeColor(settings?.secondary_color || '#ffffff')
    const baseSettings = JSON.parse(JSON.stringify(settings || {}))
    
    settingsForm.value = {
      ...baseSettings,
      primary_color: primaryColor,
      secondary_color: secondaryColor
    }
    
    console.log('[TenantSettings] After normalize - primary_color:', settingsForm.value.primary_color)
    console.log('[TenantSettings] After normalize - secondary_color:', settingsForm.value.secondary_color)
  } catch (err: any) {
    console.log('[TenantSettings] Load error:', err)
    console.log('[TenantSettings] Error status:', err.response?.status)
    console.log('[TenantSettings] Error message:', err.message)
    
    if (err.response?.status === 404 || err.message?.includes('404') || err.message?.includes('not found')) {
      console.log('[TenantSettings] No existing settings, will create new on save')
      tenantSettings.value = null
      settingsForm.value = {
        company_name: enterpriseInfo.value?.name || '',
        max_users: 10,
        max_storage_gb: 100,
        max_knowledge_bases: 10,
        max_documents: 1000,
        enable_group_chat: true,
        enable_multi_agent: true,
        enable_knowledge_graph: false,
        enable_human_review: true,
        enable_audit: false,
        enable_tax_report: false,
        enable_financial_data: false,
        primary_color: '#1890ff',
        secondary_color: '#ffffff',
        email_notification: true,
        system_notification: true
      }
    } else {
      error.value = err.message || '加载租户设置失败'
    }
  } finally {
    isLoading.value = false
  }
}

async function saveTenantSettings() {
  try {
    savingSettings.value = true
    error.value = ''
    
    const primaryColorRaw = settingsForm.value.primary_color
    const secondaryColorRaw = settingsForm.value.secondary_color
    const primaryColor = normalizeColor(primaryColorRaw || '#1890ff')
    const secondaryColor = normalizeColor(secondaryColorRaw || '#ffffff')
    
    const baseSettings = JSON.parse(JSON.stringify(settingsForm.value))
    const settingsToSave = {
      ...baseSettings,
      primary_color: primaryColor,
      secondary_color: secondaryColor
    }
    
    console.log('[TenantSettings] === SAVE DEBUG ===')
    console.log('[TenantSettings] Raw primary_color:', primaryColorRaw)
    console.log('[TenantSettings] Raw secondary_color:', secondaryColorRaw)
    console.log('[TenantSettings] Normalized primary:', primaryColor)
    console.log('[TenantSettings] Normalized secondary:', secondaryColor)
    console.log('[TenantSettings] Saving settings:', tenantSettings.value ? 'Update existing' : 'Creating new')
    
    if (tenantSettings.value) {
      console.log('[TenantSettings] Calling updateMySettings API')
      try {
        await tenantSettingsApi.updateMySettings(settingsToSave)
        console.log('[TenantSettings] Update successful')
      } catch (updateErr: any) {
        if (updateErr.response?.status === 404) {
          console.log('[TenantSettings] Update failed with 404, trying to initialize instead')
          await tenantSettingsApi.initializeSettings(settingsToSave.company_name || '我的企业')
          console.log('[TenantSettings] Initialize successful')
        } else {
          throw updateErr
        }
      }
    } else {
      console.log('[TenantSettings] No existing settings, initializing new settings')
      await tenantSettingsApi.initializeSettings(settingsToSave.company_name || '我的企业')
      console.log('[TenantSettings] Initialize successful')
    }
    
    console.log('[TenantSettings] Reloading settings')
    await loadTenantSettings()
    console.log('[TenantSettings] Reload successful')
    
    const { applyEnterpriseTheme } = useEnterpriseTheme()
    const newTheme = {
      primary_color: primaryColor,
      secondary_color: secondaryColor
    }
    applyEnterpriseTheme(newTheme)
    console.log('[TenantSettings] Theme directly applied:', newTheme)
    
    success.value = '设置保存成功'
    setTimeout(() => success.value = '', 3000)
  } catch (err: any) {
    console.error('[TenantSettings] Save error:', err)
    console.error('[TenantSettings] Error response:', err.response)
    console.error('[TenantSettings] Error status:', err.response?.status)
    console.error('[TenantSettings] Error data:', err.response?.data)
    
    if (err.response?.status === 403) {
      error.value = '您没有管理员权限，无法保存设置'
    } else if (err.response?.status === 404) {
      error.value = 'API端点不存在，请确保后端服务已启动'
    } else if (err.response?.status === 500) {
      error.value = '服务器错误，请稍后重试'
    } else {
      error.value = err.response?.data?.detail || err.message || '保存设置失败'
    }
  } finally {
    savingSettings.value = false
  }
}

async function toggleFeature(feature: string) {
  if (!settingsForm.value) return
  
  const featureKey = feature as keyof typeof settingsForm.value
  const currentValue = settingsForm.value[featureKey] as boolean
  settingsForm.value[featureKey] = !currentValue
  
  try {
    await tenantSettingsApi.toggleFeature(feature, !currentValue)
    success.value = `${getFeatureName(feature)}已${!currentValue ? '启用' : '禁用'}`
    setTimeout(() => success.value = '', 3000)
  } catch (err: any) {
    settingsForm.value[featureKey] = currentValue
    error.value = err.message || '切换功能失败'
  }
}

function getFeatureName(feature: string): string {
  const names: Record<string, string> = {
    enable_group_chat: '群聊功能',
    enable_multi_agent: '多Agent功能',
    enable_knowledge_graph: '知识图谱',
    enable_human_review: '人工审核',
    enable_audit: '审计功能',
    enable_tax_report: '税务报表',
    enable_financial_data: '财务数据'
  }
  return names[feature] || feature
}

async function createInviteCode() {
  try {
    isLoading.value = true
    const newCode = await enterpriseApi.createInviteCode({
      max_uses: inviteCodeForm.value.max_uses,
      expires_in_days: inviteCodeForm.value.expires_in_days
    })
    inviteCodes.value.unshift(newCode)
    showCreateInviteModal.value = false
    success.value = '邀请码创建成功'
    setTimeout(() => success.value = '', 3000)
  } catch (err: any) {
    error.value = err.message || '创建邀请码失败'
  } finally {
    isLoading.value = false
  }
}

async function deactivateInviteCode(code: string) {
  try {
    await enterpriseApi.deactivateInviteCode(code)
    inviteCodes.value = inviteCodes.value.filter(c => c.code !== code)
    success.value = '邀请码已删除'
    setTimeout(() => success.value = '', 3000)
  } catch (err: any) {
    error.value = err.message || '删除邀请码失败'
  }
}

async function disableInviteCode(code: string) {
  try {
    await enterpriseApi.deactivateInviteCode(code)
    const index = inviteCodes.value.findIndex(c => c.code === code)
    if (index !== -1) {
      inviteCodes.value[index].is_active = false
    }
    success.value = '邀请码已禁用'
    setTimeout(() => success.value = '', 3000)
  } catch (err: any) {
    error.value = err.message || '禁用邀请码失败'
  }
}

async function batchCreateInviteCodes() {
  try {
    isLoading.value = true
    const promises = []
    for (let i = 0; i < batchForm.value.count; i++) {
      promises.push(enterpriseApi.createInviteCode({
        max_uses: batchForm.value.max_uses,
        expires_in_days: batchForm.value.expires_in_days
      }))
    }
    const newCodes = await Promise.all(promises)
    inviteCodes.value = [...newCodes, ...inviteCodes.value]
    showBatchCreateModal.value = false
    success.value = `成功创建 ${newCodes.length} 个邀请码`
    setTimeout(() => success.value = '', 3000)
  } catch (err: any) {
    error.value = err.message || '批量创建邀请码失败'
  } finally {
    isLoading.value = false
  }
}

function exportInviteCodes() {
  const data = filteredInviteCodes.value.map(c => ({
    code: c.code,
    created_at: formatDate(c.created_at),
    expires_at: formatDate(c.expires_at),
    max_uses: c.max_uses,
    used_count: c.used_count,
    status: c.is_active ? '有效' : '已禁用'
  }))

  const headers = ['邀请码', '创建时间', '过期时间', '最大使用次数', '已使用次数', '状态']
  const csvContent = [
    headers.join(','),
    ...data.map(row => [
      row.code,
      row.created_at,
      row.expires_at,
      row.max_uses,
      row.used_count,
      row.status
    ].join(','))
  ].join('\n')

  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `邀请码_${new Date().toISOString().split('T')[0]}.csv`
  link.click()
  URL.revokeObjectURL(link.href)
}

function getInviteCodeStatus(code: InviteCode): { label: string; class: string } {
  const now = new Date()
  if (code.used_count >= code.max_uses && code.max_uses > 0) {
    return { label: '已用完', class: 'bg-purple-100 text-purple-700' }
  }
  if (!code.is_active) {
    return { label: '已禁用', class: 'bg-gray-100 text-gray-600' }
  }
  if (new Date(code.expires_at) <= now) {
    return { label: '已过期', class: 'bg-red-100 text-red-700' }
  }
  return { label: '有效', class: 'bg-green-100 text-green-700' }
}

function changePage(page: number) {
  invitePagination.value.page = Math.max(1, Math.min(page, totalPages.value))
}

function toggleActionMenu(code: string | null) {
  actionMenuCode.value = actionMenuCode.value === code ? null : code
}

function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (!target.closest('.action-menu-container')) {
    actionMenuCode.value = null
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

async function toggleUserStatus(user: EnterpriseUser) {
  try {
    await enterpriseApi.updateUserStatus(user.id, !user.is_active)
    user.is_active = !user.is_active
    success.value = user.is_active ? '用户已启用' : '用户已禁用'
    setTimeout(() => success.value = '', 3000)
  } catch (err: any) {
    error.value = err.message || '更新用户状态失败'
  }
}

async function deleteUser(userId: string) {
  if (!confirm('确定要删除这个用户吗？')) return

  try {
    await enterpriseApi.deleteUser(userId)
    users.value = users.value.filter(u => u.id !== userId)
    success.value = '用户已删除'
    setTimeout(() => success.value = '', 3000)
  } catch (err: any) {
    error.value = err.message || '删除用户失败'
  }
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text)
  copiedCode.value = text
  setTimeout(() => copiedCode.value = '', 2000)
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('zh-CN')
}

watch(activeTab, async (newTab) => {
  if (newTab === 'settings' && !tenantSettings.value) {
    await loadTenantSettings()
  }
})

watch(() => settingsForm.value.primary_color, (newVal) => {
  if (newVal && /^#[0-9A-Fa-f]{6}$/.test(newVal)) {
    return
  }
  if (newVal) {
    const normalized = normalizeColor(newVal)
    if (normalized !== newVal) {
      settingsForm.value.primary_color = normalized
    }
  } else {
    settingsForm.value.primary_color = '#1890ff'
  }
})

watch(() => settingsForm.value.secondary_color, (newVal) => {
  if (newVal && /^#[0-9A-Fa-f]{6}$/.test(newVal)) {
    return
  }
  if (newVal) {
    const normalized = normalizeColor(newVal)
    if (normalized !== newVal) {
      settingsForm.value.secondary_color = normalized
    }
  } else {
    settingsForm.value.secondary_color = '#ffffff'
  }
})
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-6 py-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Users :size="28" class="text-emerald-600" />
            企业管理
          </h1>
          <p v-if="enterpriseInfo" class="text-sm text-gray-500 mt-1">
            {{ enterpriseInfo.name }} · {{ enterpriseInfo.member_count }} 名成员
          </p>
        </div>
      </div>

      <!-- Tabs -->
      <div v-if="isAdmin" class="flex gap-4 mt-4">
        <button
          @click="activeTab = 'users'"
          :class="[
            'px-4 py-2 font-medium rounded-lg transition-colors flex items-center gap-2',
            activeTab === 'users'
              ? 'bg-emerald-100 text-emerald-600'
              : 'text-gray-600 hover:bg-gray-100'
          ]"
        >
          <Users :size="18" />
          用户管理
        </button>
        <button
          @click="activeTab = 'invites'"
          :class="[
            'px-4 py-2 font-medium rounded-lg transition-colors flex items-center gap-2',
            activeTab === 'invites'
              ? 'bg-emerald-100 text-emerald-600'
              : 'text-gray-600 hover:bg-gray-100'
          ]"
        >
          <Key :size="18" />
          邀请码
        </button>
        <button
          @click="activeTab = 'settings'"
          :class="[
            'px-4 py-2 font-medium rounded-lg transition-colors flex items-center gap-2',
            activeTab === 'settings'
              ? 'bg-emerald-100 text-emerald-600'
              : 'text-gray-600 hover:bg-gray-100'
          ]"
        >
          <Settings :size="18" />
          企业设置
        </button>
      </div>
      
      <div v-else class="mt-4 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div class="flex items-start gap-3">
          <div class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
            <Users :size="20" class="text-blue-600" />
          </div>
          <div>
            <h3 class="text-lg font-semibold text-blue-900 mb-2">欢迎加入企业团队</h3>
            <p class="text-sm text-blue-700 mb-3">您当前是企业成员，可享受企业提供的各项服务。如需管理功能，请联系企业管理员。</p>
            <div class="flex items-center gap-2 text-sm text-blue-600">
              <Building2 :size="16" />
              <span>{{ enterpriseInfo?.name || '加载中...' }}</span>
              <span v-if="enterpriseInfo?.member_count"> · {{ enterpriseInfo.member_count }} 名成员</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6">
      <!-- Error/Success Messages -->
      <div v-if="error" class="mb-4 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
        <AlertCircle :size="20" class="text-red-500" />
        <p class="text-sm text-red-700">{{ error }}</p>
        <button @click="error = ''" class="ml-auto text-red-500 hover:text-red-700">×</button>
      </div>

      <div v-if="success" class="mb-4 bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
        <CheckCircle :size="20" class="text-green-500" />
        <p class="text-sm text-green-700">{{ success }}</p>
        <button @click="success = ''" class="ml-auto text-green-500 hover:text-green-700">×</button>
      </div>

      <!-- Users Tab (Admin Only) -->
      <div v-if="isAdmin && activeTab === 'users'" class="space-y-4">
        <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table class="w-full">
            <thead class="bg-gray-50 border-b border-gray-200">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">邮箱</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">职位</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">角色</th>
                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr v-for="user in users" :key="user.id" class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex items-center gap-3">
                    <img
                      v-if="user.avatar_url"
                      :src="user.avatar_url"
                      :alt="user.full_name"
                      class="w-10 h-10 rounded-full"
                    />
                    <div
                      v-else
                      class="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-600 to-teal-600 flex items-center justify-center text-white font-medium"
                    >
                      {{ user.full_name.charAt(0) }}
                    </div>
                    <div>
                      <div class="font-medium text-gray-900">{{ user.full_name }}</div>
                      <div v-if="user.nickname" class="text-sm text-gray-500">{{ user.nickname }}</div>
                    </div>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{{ user.email }}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{{ user.company_position || '-' }}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span
                    :class="[
                      'px-2 py-1 text-xs font-medium rounded-full',
                      user.is_active
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    ]"
                  >
                    {{ user.is_active ? '启用' : '禁用' }}
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span
                    v-if="user.is_admin"
                    class="px-2 py-1 text-xs font-medium rounded-full bg-teal-100 text-teal-700 flex items-center gap-1 w-fit"
                  >
                    <Crown :size="12" />
                    管理员
                  </span>
                  <span v-else class="text-sm text-gray-500">成员</span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm">
                  <div class="flex items-center justify-end gap-2">
                    <button
                      @click="toggleUserStatus(user)"
                      :class="[
                        'p-2 rounded-lg transition-colors',
                        user.is_active
                          ? 'hover:bg-red-100 text-red-600'
                          : 'hover:bg-green-100 text-green-600'
                      ]"
                      :title="user.is_active ? '禁用用户' : '启用用户'"
                    >
                      <UserX v-if="user.is_active" :size="18" />
                      <UserCheck v-else :size="18" />
                    </button>
                    <button
                      v-if="!user.is_admin"
                      @click="deleteUser(user.id)"
                      class="p-2 hover:bg-red-100 rounded-lg transition-colors text-red-600"
                      title="删除用户"
                    >
                      <Trash2 :size="18" />
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Invite Codes Tab (Admin Only) -->
      <div v-if="isAdmin && activeTab === 'invites'" class="space-y-4">
        <!-- Statistics Cards -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="bg-white rounded-xl border border-gray-200 p-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-gray-500">总邀请码</p>
                <p class="text-2xl font-bold text-gray-900 mt-1">{{ inviteStats.total }}</p>
              </div>
              <div class="p-3 bg-blue-100 rounded-lg">
                <Key :size="24" class="text-blue-600" />
              </div>
            </div>
          </div>
          <div class="bg-white rounded-xl border border-gray-200 p-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-gray-500">有效</p>
                <p class="text-2xl font-bold text-green-600 mt-1">{{ inviteStats.valid }}</p>
              </div>
              <div class="p-3 bg-green-100 rounded-lg">
                <CheckCircle :size="24" class="text-green-600" />
              </div>
            </div>
          </div>
          <div class="bg-white rounded-xl border border-gray-200 p-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-gray-500">已用完</p>
                <p class="text-2xl font-bold text-purple-600 mt-1">{{ inviteStats.exhausted }}</p>
              </div>
              <div class="p-3 bg-purple-100 rounded-lg">
                <Gift :size="24" class="text-purple-600" />
              </div>
            </div>
          </div>
          <div class="bg-white rounded-xl border border-gray-200 p-4">
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-gray-500">已过期</p>
                <p class="text-2xl font-bold text-red-600 mt-1">{{ inviteStats.expired }}</p>
              </div>
              <div class="p-3 bg-red-100 rounded-lg">
                <AlertCircle :size="24" class="text-red-600" />
              </div>
            </div>
          </div>
        </div>

        <!-- Toolbar -->
        <div class="bg-white rounded-xl border border-gray-200 p-4">
          <div class="flex flex-wrap items-center gap-4">
            <!-- Filter Buttons -->
            <div class="flex items-center gap-2">
              <Filter :size="18" class="text-gray-400" />
              <button
                v-for="filter in [
                  { key: 'all', label: '全部' },
                  { key: 'valid', label: '有效' },
                  { key: 'exhausted', label: '已用完' },
                  { key: 'expired', label: '已过期' }
                ]"
                :key="filter.key"
                @click="inviteFilter = filter.key as any; invitePagination.page = 1"
                :class="[
                  'px-3 py-1.5 text-sm font-medium rounded-lg transition-colors',
                  inviteFilter === filter.key
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'text-gray-600 hover:bg-gray-100'
                ]"
              >
                {{ filter.label }}
              </button>
            </div>

            <!-- Search -->
            <div class="flex-1 min-w-[200px] max-w-md">
              <div class="relative">
                <Search :size="18" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  v-model="inviteSearchQuery"
                  type="text"
                  placeholder="搜索邀请码..."
                  class="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                  @input="invitePagination.page = 1"
                />
              </div>
            </div>

            <!-- Actions -->
            <div class="flex items-center gap-2">
              <button
                @click="exportInviteCodes"
                :disabled="filteredInviteCodes.length === 0"
                class="px-4 py-2 bg-white border border-gray-200 text-gray-700 font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50 flex items-center gap-2"
              >
                <Download :size="18" />
                导出
              </button>
              <button
                @click="showBatchCreateModal = true"
                class="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 flex items-center gap-2"
              >
                <Plus :size="18" />
                批量生成
              </button>
              <button
                @click="showCreateInviteModal = true"
                class="px-4 py-2 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 flex items-center gap-2"
              >
                <Plus :size="18" />
                单个生成
              </button>
            </div>
          </div>
        </div>

        <!-- Table -->
        <div class="bg-white rounded-xl border border-gray-200 overflow-visible">
          <table class="w-full">
            <thead class="bg-gray-50 border-b border-gray-200">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">邀请码</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">创建时间</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">过期时间</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">使用情况</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr v-for="code in paginatedInviteCodes" :key="code.code" class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="flex items-center gap-3">
                    <code class="text-sm font-mono bg-gray-100 px-3 py-1 rounded">{{ code.code }}</code>
                    <button
                      @click="copyToClipboard(code.code)"
                      class="p-1 hover:bg-gray-200 rounded transition-colors"
                    >
                      <Check v-if="copiedCode === code.code" :size="16" class="text-green-600" />
                      <Copy v-else :size="16" class="text-gray-500" />
                    </button>
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {{ formatDate(code.created_at) }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {{ formatDate(code.expires_at) }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {{ code.used_count }} / {{ code.max_uses === 0 ? '∞' : code.max_uses }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span :class="['px-2 py-1 text-xs font-medium rounded-full', getInviteCodeStatus(code).class]">
                    {{ getInviteCodeStatus(code).label }}
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-right">
                  <div class="action-menu-container relative inline-block">
                    <button
                      @click.stop="toggleActionMenu(code.code)"
                      class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                      <MoreVertical :size="18" class="text-gray-500" />
                    </button>
                    <!-- Action Menu Dropdown -->
                    <div
                      v-if="actionMenuCode === code.code"
                      class="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-50 min-w-[140px]"
                    >
                      <button
                        @click="copyToClipboard(code.code); toggleActionMenu(null)"
                        class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                      >
                        <Copy :size="14" />
                        复制邀请码
                      </button>
                      <button
                        v-if="code.is_active"
                        @click="disableInviteCode(code.code); toggleActionMenu(null)"
                        class="w-full px-4 py-2 text-left text-sm text-orange-600 hover:bg-orange-50 flex items-center gap-2"
                      >
                        <X :size="14" />
                        禁用邀请码
                      </button>
                      <button
                        v-else
                        @click="toggleActionMenu(null)"
                        class="w-full px-4 py-2 text-left text-sm text-green-600 flex items-center gap-2 cursor-default"
                      >
                        <Check :size="14" />
                        已禁用
                      </button>
                      <div class="border-t border-gray-100 my-1"></div>
                      <button
                        @click="deleteTargetCode = code.code; showDeleteConfirmModal = true; toggleActionMenu(null)"
                        class="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                      >
                        <Trash2 :size="14" />
                        删除邀请码
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
              <tr v-if="paginatedInviteCodes.length === 0">
                <td colspan="6" class="px-6 py-12 text-center text-gray-500">
                  <Key :size="48" class="mx-auto text-gray-300 mb-3" />
                  <p>暂无邀请码</p>
                  <p class="text-sm text-gray-400 mt-1">点击「生成邀请码」按钮创建</p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-between bg-white rounded-xl border border-gray-200 px-6 py-4">
          <div class="text-sm text-gray-500">
            显示 {{ (invitePagination.page - 1) * invitePagination.pageSize + 1 }} -
            {{ Math.min(invitePagination.page * invitePagination.pageSize, filteredInviteCodes.length) }}
            共 {{ filteredInviteCodes.length }} 条
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="changePage(invitePagination.page - 1)"
              :disabled="invitePagination.page === 1"
              class="px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              上一页
            </button>
            <div class="flex items-center gap-1">
              <button
                v-for="page in Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const start = Math.max(1, invitePagination.page - 2)
                  return Math.min(start + i, totalPages)
                })"
                :key="page"
                @click="changePage(page)"
                :class="[
                  'w-10 h-10 rounded-lg font-medium',
                  invitePagination.page === page
                    ? 'bg-emerald-600 text-white'
                    : 'border border-gray-200 hover:bg-gray-50'
                ]"
              >
                {{ page }}
              </button>
            </div>
            <button
              @click="changePage(invitePagination.page + 1)"
              :disabled="invitePagination.page === totalPages"
              class="px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              下一页
            </button>
          </div>
        </div>
      </div>

      <!-- Tenant Settings Tab (Admin Only) -->
      <div v-if="isAdmin && activeTab === 'settings'" class="space-y-6">
        <!-- Loading State -->
        <div v-if="isLoading" class="flex items-center justify-center py-12">
          <Loader2 :size="32" class="animate-spin text-emerald-600" />
          <span class="ml-3 text-gray-600">加载中...</span>
        </div>

        <!-- Settings Form -->
        <div v-else-if="settingsForm" class="space-y-6">
          <!-- 1. Enterprise Basic Information -->
          <div class="bg-white rounded-xl border border-gray-200 p-6">
            <h3 class="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <Building2 :size="20" class="text-emerald-600" />
              企业基本信息
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">企业名称 *</label>
                <input
                  v-model="settingsForm.company_name"
                  type="text"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                  placeholder="请输入企业名称"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">企业Logo URL</label>
                <input
                  v-model="settingsForm.company_logo"
                  type="url"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                  placeholder="https://example.com/logo.png"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">联系电话</label>
                <input
                  v-model="settingsForm.company_phone"
                  type="tel"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                  placeholder="400-123-4567"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">联系邮箱</label>
                <input
                  v-model="settingsForm.company_email"
                  type="email"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                  placeholder="contact@example.com"
                />
              </div>
              <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">企业网站</label>
                <input
                  v-model="settingsForm.company_website"
                  type="url"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                  placeholder="https://www.example.com"
                />
              </div>
              <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">企业简介</label>
                <textarea
                  v-model="settingsForm.company_description"
                  rows="3"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none resize-none"
                  placeholder="请输入企业简介"
                ></textarea>
              </div>
              <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">企业地址</label>
                <input
                  v-model="settingsForm.company_address"
                  type="text"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                  placeholder="请输入企业地址"
                />
              </div>
            </div>
          </div>

          <!-- Enterprise Profile for Policy Matching -->
          <div class="bg-white rounded-xl border border-purple-200 p-6">
            <h3 class="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <Building2 :size="20" class="text-purple-600" />
              企业画像配置
              <span class="text-xs font-normal text-purple-600 bg-purple-50 px-2 py-1 rounded">用于政策智能匹配</span>
            </h3>
            <p class="text-sm text-gray-600 mb-4">
              设置您的企业画像，帮助AI系统更准确地为您推荐相关政策。企业画像会被用于政策匹配算法中的行业、地区、规模、税种等维度的筛选。
            </p>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <!-- Industry -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">企业所属行业 *</label>
                <select
                  v-model="settingsForm.industry"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-200 focus:border-purple-500 outline-none"
                >
                  <option value="">请选择行业</option>
                  <option v-for="industry in profileOptions.industries" :key="industry" :value="industry">
                    {{ industry }}
                  </option>
                </select>
              </div>

              <!-- Region -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">企业所在地区 *</label>
                <select
                  v-model="settingsForm.region"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-200 focus:border-purple-500 outline-none"
                >
                  <option value="">请选择地区</option>
                  <option v-for="region in profileOptions.regions" :key="region" :value="region">
                    {{ region }}
                  </option>
                </select>
              </div>

              <!-- Scale -->
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">企业规模 *</label>
                <select
                  v-model="settingsForm.scale"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-200 focus:border-purple-500 outline-none"
                >
                  <option value="">请选择规模</option>
                  <option v-for="scale in profileOptions.scales" :key="scale" :value="scale">
                    {{ scale }}
                  </option>
                </select>
              </div>

              <!-- Tax Types (Multi-select) -->
              <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-2">适用税种类型（可多选）</label>
                <div class="flex flex-wrap gap-2 p-4 border border-gray-200 rounded-lg bg-gray-50">
                  <button
                    v-for="taxType in profileOptions.taxTypes"
                    :key="taxType"
                    @click="toggleTaxType(taxType)"
                    :class="[
                      'px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
                      settingsForm.tax_types?.includes(taxType)
                        ? 'bg-purple-600 text-white shadow-md'
                        : 'bg-white text-gray-700 border border-gray-200 hover:border-purple-300'
                    ]"
                  >
                    {{ taxType }}
                  </button>
                </div>
                <p class="text-xs text-gray-500 mt-2">
                  已选择 {{ settingsForm.tax_types?.length || 0 }} 个税种类型
                </p>
              </div>
            </div>
          </div>

          <!-- 2. System Limits -->
          <div class="bg-white rounded-xl border border-gray-200 p-6">
            <h3 class="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <Sliders :size="20" class="text-emerald-600" />
              系统限制配置
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">最大用户数</label>
                <input
                  v-model.number="settingsForm.max_users"
                  type="number"
                  min="1"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">存储空间限制 (GB)</label>
                <input
                  v-model.number="settingsForm.max_storage_gb"
                  type="number"
                  min="1"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">知识库数量限制</label>
                <input
                  v-model.number="settingsForm.max_knowledge_bases"
                  type="number"
                  min="1"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">文档数量限制</label>
                <input
                  v-model.number="settingsForm.max_documents"
                  type="number"
                  min="1"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">月度请求次数限制</label>
                <input
                  v-model.number="settingsForm.max_monthly_requests"
                  type="number"
                  min="0"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                  placeholder="0表示无限制"
                />
              </div>
            </div>
          </div>

          <!-- 3. Feature Toggles -->
          <div class="bg-white rounded-xl border border-gray-200 p-6">
            <h3 class="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <ToggleLeft :size="20" class="text-emerald-600" />
              功能开关
            </h3>
            <p class="text-sm text-gray-500 mb-4">启用或禁用平台的各种功能模块</p>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div
                v-for="(feature, key) in {
                  enable_group_chat: '群聊功能',
                  enable_multi_agent: '多Agent功能',
                  enable_knowledge_graph: '知识图谱',
                  enable_human_review: '人工审核',
                  enable_audit: '审计功能',
                  enable_tax_report: '税务报表',
                  enable_financial_data: '财务数据'
                }"
                :key="key"
                class="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div>
                  <div class="font-medium text-gray-900">{{ feature }}</div>
                  <div class="text-xs text-gray-500 mt-0.5">{{ getFeatureDescription(key) }}</div>
                </div>
                <button
                  @click="toggleFeature(key)"
                  :class="[
                    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                    settingsForm[key as keyof typeof settingsForm] ? 'bg-emerald-600' : 'bg-gray-300'
                  ]"
                >
                  <span
                    :class="[
                      'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                      settingsForm[key as keyof typeof settingsForm] ? 'translate-x-6' : 'translate-x-1'
                    ]"
                  />
                </button>
              </div>
            </div>
          </div>

          <!-- 4. Theme Customization -->
          <div class="bg-white rounded-xl border border-gray-200 p-6">
            <h3 class="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <Palette :size="20" class="text-emerald-600" />
              主题定制
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">主色调</label>
                <div class="flex items-center gap-3">
                  <input
                    v-model="settingsForm.primary_color"
                    @input="(e) => { const c = normalizeColor((e.target as HTMLInputElement).value); if (c !== settingsForm.primary_color) settingsForm.primary_color = c }"
                    @invalid.prevent="() => {}"
                    type="color"
                    class="w-12 h-10 border border-gray-200 rounded-lg cursor-pointer"
                  />
                  <input
                    v-model="settingsForm.primary_color"
                    @blur="(e) => settingsForm.primary_color = normalizeColor((e.target as HTMLInputElement).value)"
                    type="text"
                    class="flex-1 px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none font-mono"
                    placeholder="#1890ff"
                  />
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">次要色调</label>
                <div class="flex items-center gap-3">
                  <input
                    v-model="settingsForm.secondary_color"
                    @input="(e) => { const c = normalizeColor((e.target as HTMLInputElement).value); if (c !== settingsForm.secondary_color) settingsForm.secondary_color = c }"
                    @invalid.prevent="() => {}"
                    type="color"
                    class="w-12 h-10 border border-gray-200 rounded-lg cursor-pointer"
                  />
                  <input
                    v-model="settingsForm.secondary_color"
                    @blur="(e) => settingsForm.secondary_color = normalizeColor((e.target as HTMLInputElement).value)"
                    type="text"
                    class="flex-1 px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none font-mono"
                    placeholder="#ffffff"
                  />
                </div>
              </div>
              <!-- Color Preview -->
              <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-2">主题预览</label>
                <div 
                  class="h-16 rounded-lg border border-gray-200 overflow-hidden flex items-center justify-center"
                  :style="{ background: `linear-gradient(135deg, ${settingsForm.primary_color} 0%, ${settingsForm.secondary_color} 100%)` }"
                >
                  <span 
                    class="px-4 py-2 rounded-md text-sm font-medium"
                    :style="{ backgroundColor: settingsForm.secondary_color, color: settingsForm.primary_color }"
                  >
                    预览效果
                  </span>
                </div>
              </div>
              <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">自定义CSS</label>
                <textarea
                  v-model="settingsForm.custom_css"
                  rows="3"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none resize-none font-mono text-sm"
                  placeholder="/* 自定义CSS样式 */"
                ></textarea>
              </div>
              <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">自定义页脚</label>
                <textarea
                  v-model="settingsForm.custom_footer"
                  rows="2"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none resize-none"
                  placeholder="© 2024 企业名称. 保留所有权利."
                ></textarea>
              </div>
            </div>
          </div>

          <!-- 5. Notification Settings -->
          <div class="bg-white rounded-xl border border-gray-200 p-6">
            <h3 class="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <Bell :size="20" class="text-emerald-600" />
              通知设置
            </h3>
            <div class="space-y-4">
              <div class="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <div class="font-medium text-gray-900">邮件通知</div>
                  <div class="text-xs text-gray-500 mt-0.5">接收重要信息的邮件通知</div>
                </div>
                <button
                  @click="settingsForm.email_notification = !settingsForm.email_notification"
                  :class="[
                    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                    settingsForm.email_notification ? 'bg-emerald-600' : 'bg-gray-300'
                  ]"
                >
                  <span
                    :class="[
                      'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                      settingsForm.email_notification ? 'translate-x-6' : 'translate-x-1'
                    ]"
                  />
                </button>
              </div>
              <div class="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <div class="font-medium text-gray-900">系统通知</div>
                  <div class="text-xs text-gray-500 mt-0.5">在平台内显示系统通知</div>
                </div>
                <button
                  @click="settingsForm.system_notification = !settingsForm.system_notification"
                  :class="[
                    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                    settingsForm.system_notification ? 'bg-emerald-600' : 'bg-gray-300'
                  ]"
                >
                  <span
                    :class="[
                      'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                      settingsForm.system_notification ? 'translate-x-6' : 'translate-x-1'
                    ]"
                  />
                </button>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">通知接收邮箱</label>
                <input
                  v-model="settingsForm.notification_email"
                  type="email"
                  class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
                  placeholder="notification@example.com"
                />
              </div>
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="flex justify-end gap-3">
            <button
              @click="loadTenantSettings"
              class="px-6 py-2 text-gray-700 font-medium rounded-lg hover:bg-gray-100 flex items-center gap-2 transition-colors"
            >
              <RefreshCw :size="16" />
              重置
            </button>
            <button
              @click="saveTenantSettings"
              :disabled="savingSettings"
              class="px-6 py-2 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2 transition-colors"
            >
              <Loader2 v-if="savingSettings" :size="16" class="animate-spin" />
              <Save v-else :size="16" />
              {{ savingSettings ? '保存中...' : '保存设置' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Invite Modal -->
    <div
      v-if="showCreateInviteModal"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showCreateInviteModal = false"
    >
      <div class="bg-white rounded-xl p-6 w-full max-w-md">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">生成邀请码</h3>

        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">最大使用次数</label>
            <input
              v-model.number="inviteCodeForm.max_uses"
              type="number"
              min="0"
              class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
            />
            <p class="text-xs text-gray-500 mt-1">设为0表示无限制</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">有效期（天）</label>
            <input
              v-model.number="inviteCodeForm.expires_in_days"
              type="number"
              min="1"
              class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
            />
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button
            @click="showCreateInviteModal = false"
            class="px-4 py-2 text-gray-700 font-medium rounded-lg hover:bg-gray-100 transition-colors"
          >
            取消
          </button>
          <button
            @click="createInviteCode"
            :disabled="isLoading"
            class="px-4 py-2 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Loader2 v-if="isLoading" :size="16" class="animate-spin" />
            生成
          </button>
        </div>
      </div>
    </div>

    <!-- Batch Create Invite Modal -->
    <div
      v-if="showBatchCreateModal"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showBatchCreateModal = false"
    >
      <div class="bg-white rounded-xl p-6 w-full max-w-md">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">批量生成邀请码</h3>

        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">生成数量</label>
            <input
              v-model.number="batchForm.count"
              type="number"
              min="1"
              max="100"
              class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
            />
            <p class="text-xs text-gray-500 mt-1">建议不超过100个</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">每个码最大使用次数</label>
            <input
              v-model.number="batchForm.max_uses"
              type="number"
              min="0"
              class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
            />
            <p class="text-xs text-gray-500 mt-1">设为0表示无限制</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">有效期（天）</label>
            <input
              v-model.number="batchForm.expires_in_days"
              type="number"
              min="1"
              class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-500 outline-none"
            />
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button
            @click="showBatchCreateModal = false"
            class="px-4 py-2 text-gray-700 font-medium rounded-lg hover:bg-gray-100 transition-colors"
          >
            取消
          </button>
          <button
            @click="batchCreateInviteCodes"
            :disabled="isLoading || batchForm.count < 1"
            class="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Loader2 v-if="isLoading" :size="16" class="animate-spin" />
            确认生成
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirm Modal -->
    <div
      v-if="showDeleteConfirmModal"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showDeleteConfirmModal = false; deleteTargetCode = null"
    >
      <div class="bg-white rounded-xl p-6 w-full max-w-sm">
        <h3 class="text-lg font-semibold text-gray-900 mb-2">确认删除</h3>
        <p class="text-gray-600 mb-6">确定要删除邀请码 <code class="bg-gray-100 px-2 py-0.5 rounded">{{ deleteTargetCode }}</code> 吗？此操作不可恢复。</p>
        <div class="flex justify-end gap-3">
          <button
            @click="showDeleteConfirmModal = false; deleteTargetCode = null"
            class="px-4 py-2 text-gray-700 font-medium rounded-lg hover:bg-gray-100 transition-colors"
          >
            取消
          </button>
          <button
            @click="() => { if (deleteTargetCode) deactivateInviteCode(deleteTargetCode); showDeleteConfirmModal = false; deleteTargetCode = null }"
            class="px-4 py-2 bg-red-600 text-white font-medium rounded-lg hover:bg-red-700 flex items-center gap-2"
          >
            确认删除
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
function getFeatureDescription(feature: string): string {
  const descriptions: Record<string, string> = {
    enable_group_chat: '允许多用户群组聊天',
    enable_multi_agent: '启用多个AI代理协作',
    enable_knowledge_graph: '构建知识图谱关系',
    enable_human_review: '需要人工审批操作',
    enable_audit: '记录详细操作日志',
    enable_tax_report: '启用税务报表功能',
    enable_financial_data: '启用财务数据功能'
  }
  return descriptions[feature] || ''
}
</script>
