<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { enterpriseApi } from '@/api/enterprise'
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
  Crown
} from 'lucide-vue-next'

const activeTab = ref<'users' | 'invites'>('users')
const isLoading = ref(false)
const error = ref('')
const success = ref('')

const enterpriseInfo = ref<EnterpriseResponse | null>(null)
const users = ref<EnterpriseUser[]>([])
const inviteCodes = ref<InviteCode[]>([])

const showCreateInviteModal = ref(false)
const inviteCodeForm = ref({
  max_uses: 1,
  expires_in_days: 7
})

const copiedCode = ref('')

onMounted(async () => {
  await loadData()
})

async function loadData() {
  try {
    isLoading.value = true
    error.value = ''

    const [info, usersData, codesData] = await Promise.all([
      enterpriseApi.getEnterprise().catch(() => null),
      enterpriseApi.getUsers(),
      enterpriseApi.getInviteCodes()
    ])

    enterpriseInfo.value = info
    users.value = usersData
    inviteCodes.value = codesData
  } catch (err: any) {
    error.value = err.message || '加载数据失败'
  } finally {
    isLoading.value = false
  }
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
  if (!confirm('确定要禁用这个邀请码吗？')) return

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
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-6 py-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Users :size="28" class="text-blue-600" />
            企业管理
          </h1>
          <p v-if="enterpriseInfo" class="text-sm text-gray-500 mt-1">
            {{ enterpriseInfo.name }} · {{ enterpriseInfo.member_count }} 名成员
          </p>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex gap-4 mt-4">
        <button
          @click="activeTab = 'users'"
          :class="[
            'px-4 py-2 font-medium rounded-lg transition-colors flex items-center gap-2',
            activeTab === 'users'
              ? 'bg-blue-100 text-blue-600'
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
              ? 'bg-blue-100 text-blue-600'
              : 'text-gray-600 hover:bg-gray-100'
          ]"
        >
          <Key :size="18" />
          邀请码
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6">
      <!-- Error/Success Messages -->
      <div v-if="error" class="mb-4 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
        <AlertCircle :size="20" class="text-red-500" />
        <p class="text-sm text-red-700">{{ error }}</p>
      </div>

      <div v-if="success" class="mb-4 bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
        <CheckCircle :size="20" class="text-green-500" />
        <p class="text-sm text-green-700">{{ success }}</p>
      </div>

      <!-- Users Tab -->
      <div v-if="activeTab === 'users'" class="space-y-4">
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
                      class="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-medium"
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
                    class="px-2 py-1 text-xs font-medium rounded-full bg-purple-100 text-purple-700 flex items-center gap-1 w-fit"
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

      <!-- Invite Codes Tab -->
      <div v-if="activeTab === 'invites'" class="space-y-4">
        <div class="flex justify-end">
          <button
            @click="showCreateInviteModal = true"
            class="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 flex items-center gap-2"
          >
            <Plus :size="18" />
            生成邀请码
          </button>
        </div>

        <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table class="w-full">
            <thead class="bg-gray-50 border-b border-gray-200">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">邀请码</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">有效期</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">使用情况</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr v-for="code in inviteCodes" :key="code.code" class="hover:bg-gray-50">
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
                  {{ formatDate(code.created_at) }} - {{ formatDate(code.expires_at) }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {{ code.used_count }} / {{ code.max_uses === 0 ? '∞' : code.max_uses }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span
                    :class="[
                      'px-2 py-1 text-xs font-medium rounded-full',
                      code.is_active
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-600'
                    ]"
                  >
                    {{ code.is_active ? '有效' : '已禁用' }}
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-right">
                  <button
                    v-if="code.is_active"
                    @click="deactivateInviteCode(code.code)"
                    class="p-2 hover:bg-red-100 rounded-lg transition-colors text-red-600"
                    title="禁用邀请码"
                  >
                    <Trash2 :size="18" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
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
              class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-500 outline-none"
            />
            <p class="text-xs text-gray-500 mt-1">设为0表示无限制</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">有效期（天）</label>
            <input
              v-model.number="inviteCodeForm.expires_in_days"
              type="number"
              min="1"
              class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-200 focus:border-blue-500 outline-none"
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
            class="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
          >
            <Loader2 v-if="isLoading" :size="16" class="animate-spin" />
            生成
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
