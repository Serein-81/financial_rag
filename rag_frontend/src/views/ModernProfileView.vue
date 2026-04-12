<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { 
  User, Mail, Lock, ArrowLeft, Upload, Save, Eye, EyeOff,
  Sun, Moon, Monitor, CheckCircle, Building2, Shield,
  KeyRound, Phone, Sparkles, X, Check, AlertCircle, Loader2
} from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

// API Base
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

// 表单数据
const fullName = ref('')
const email = ref('')
const phone = ref('')
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const inviteCode = ref('')

// UI 状态
const showCurrentPassword = ref(false)
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)
const isSaving = ref(false)
const activeTab = ref('profile')
const saveMessage = ref('')
const saveSuccess = ref(false)
const isUploadingAvatar = ref(false)
const selectedTheme = ref<'light' | 'dark' | 'auto'>('light')

// 头像
const avatarFile = ref<File | null>(null)
const avatarPreview = ref<string | null>(null)

// 企业相关
const currentEnterprise = ref<{name: string, tenant_id: string} | null>(null)
const showInviteCodeModal = ref(false)
const isJoiningEnterprise = ref(false)
const inviteCodeValidation = ref<{valid: boolean, message: string, enterprise_name?: string} | null>(null)

// 手机号相关
const showPhoneModal = ref(false)
const newPhone = ref('')
const smsCode = ref('')
const smsSent = ref(false)
const smsCountdown = ref(0)
const smsLoading = ref(false)
const isUpdatingPhone = ref(false)

// 密码修改相关
const passwordStrength = ref(0)
const passwordError = ref('')

// 计算属性
const passwordStrengthText = computed(() => {
  const strength = passwordStrength.value
  if (strength === 0) return ''
  if (strength === 1) return '弱'
  if (strength === 2) return '中等'
  if (strength === 3) return '强'
  if (strength === 4) return '非常强'
  return ''
})

const passwordStrengthClass = computed(() => {
  const strength = passwordStrength.value
  if (strength === 1) return 'strength-weak'
  if (strength === 2) return 'strength-medium'
  if (strength === 3) return 'strength-strong'
  if (strength === 4) return 'strength-very-strong'
  return ''
})

// 生命周期
onMounted(async () => {
  await loadUserProfile()
  const savedTheme = localStorage.getItem('rag_theme') as 'light' | 'dark' | 'auto'
  if (savedTheme) {
    selectedTheme.value = savedTheme
  }
})

// 方法
async function loadUserProfile() {
  try {
    const token = localStorage.getItem('rag_token')
    const response = await fetch(`${API_BASE}/api/v1/auth/me`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    
    if (response.ok) {
      const data = await response.json()
      fullName.value = data.full_name || data.nickname || ''
      email.value = data.email || ''
      phone.value = data.phone || ''
      avatarPreview.value = data.avatar_url || null
      
      if (data.company_name && data.tenant_id) {
        currentEnterprise.value = {
          name: data.company_name,
          tenant_id: data.tenant_id
        }
      }
    }
  } catch (error) {
    console.error('加载用户信息失败:', error)
  }
}

function goBack() {
  router.push('/')
}

function handleAvatarSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file && file.type.startsWith('image/')) {
    avatarFile.value = file
    const reader = new FileReader()
    reader.onload = (e) => {
      avatarPreview.value = e.target?.result as string
    }
    reader.readAsDataURL(file)
  }
}

async function uploadAvatar() {
  if (!avatarFile.value || isUploadingAvatar.value) return

  isUploadingAvatar.value = true
  const formData = new FormData()
  formData.append('file', avatarFile.value)

  try {
    const token = localStorage.getItem('rag_token')
    const response = await fetch(`${API_BASE}/api/v1/auth/avatar`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    })

    if (response.ok) {
      const data = await response.json()
      authStore.setAvatarUrl(data.avatar_url)
      avatarPreview.value = data.avatar_url
      showToast('头像上传成功！', 'success')
      avatarFile.value = null
    } else {
      const errorData = await response.json().catch(() => ({}))
      showToast(`头像上传失败: ${errorData.detail || '未知错误'}`, 'error')
    }
  } catch (error) {
    console.error('头像上传错误:', error)
    showToast('头像上传失败，请检查网络连接', 'error')
  } finally {
    isUploadingAvatar.value = false
  }
}

async function updateProfile() {
  if (!fullName.value.trim()) {
    showToast('请输入用户名', 'error')
    return
  }

  isSaving.value = true
  try {
    const token = localStorage.getItem('rag_token')
    const response = await fetch(`${API_BASE}/api/v1/auth/profile`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        full_name: fullName.value.trim()
      })
    })

    if (response.ok) {
      localStorage.setItem('rag_user_name', fullName.value.trim())
      showToast('个人信息更新成功！', 'success')
    } else {
      const errorData = await response.json().catch(() => ({}))
      showToast(`更新失败: ${errorData.detail || '未知错误'}`, 'error')
    }
  } catch (error) {
    console.error('更新个人信息失败:', error)
    showToast('更新失败，请检查网络连接', 'error')
  } finally {
    isSaving.value = false
  }
}

async function updatePassword() {
  passwordError.value = ''

  if (!currentPassword.value) {
    passwordError.value = '请输入当前密码'
    return
  }

  if (newPassword.value.length < 6) {
    passwordError.value = '新密码长度至少为6个字符'
    return
  }

  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = '两次输入的密码不一致'
    return
  }

  isSaving.value = true
  try {
    const token = localStorage.getItem('rag_token')
    const response = await fetch(`${API_BASE}/api/v1/auth/change-password`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        current_password: currentPassword.value,
        new_password: newPassword.value
      })
    })

    if (response.ok) {
      showToast('密码修改成功！', 'success')
      currentPassword.value = ''
      newPassword.value = ''
      confirmPassword.value = ''
      passwordStrength.value = 0
    } else {
      const errorData = await response.json().catch(() => ({}))
      showToast(`密码修改失败: ${errorData.detail || '未知错误'}`, 'error')
    }
  } catch (error) {
    console.error('修改密码失败:', error)
    showToast('密码修改失败，请检查网络连接', 'error')
  } finally {
    isSaving.value = false
  }
}

async function validateInviteCode() {
  if (!inviteCode.value.trim()) {
    inviteCodeValidation.value = { valid: false, message: '请输入邀请码' }
    return
  }

  try {
    const token = localStorage.getItem('rag_token')
    const response = await fetch(`${API_BASE}/api/v1/invite-codes/validate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ code: inviteCode.value.trim() })
    })

    if (response.ok) {
      const data = await response.json()
      if (data.is_valid) {
        inviteCodeValidation.value = {
          valid: true,
          message: '邀请码有效',
          enterprise_name: data.enterprise_name
        }
      } else {
        inviteCodeValidation.value = {
          valid: false,
          message: data.message || '邀请码无效或已过期'
        }
      }
    } else {
      inviteCodeValidation.value = {
        valid: false,
        message: '验证失败，请稍后重试'
      }
    }
  } catch (error) {
    console.error('验证邀请码失败:', error)
    inviteCodeValidation.value = {
      valid: false,
      message: '验证失败，请检查网络连接'
    }
  }
}

async function joinEnterprise() {
  if (!inviteCodeValidation.value?.valid) {
    showToast('请先验证邀请码', 'error')
    return
  }

  isJoiningEnterprise.value = true
  try {
    const token = localStorage.getItem('rag_token')
    const response = await fetch(`${API_BASE}/api/v1/auth/apply-invite-code`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        invite_code: inviteCode.value.trim()
      })
    })

    if (response.ok) {
      const data = await response.json()
      showToast(`成功加入 ${data.company_name || '企业'}！`, 'success')
      currentEnterprise.value = {
        name: data.company_name || '',
        tenant_id: data.tenant_id || ''
      }
      showInviteCodeModal.value = false
      inviteCode.value = ''
      inviteCodeValidation.value = null
    } else {
      const errorData = await response.json().catch(() => ({}))
      showToast(`加入企业失败: ${errorData.detail || '未知错误'}`, 'error')
    }
  } catch (error) {
    console.error('加入企业失败:', error)
    showToast('加入企业失败，请检查网络连接', 'error')
  } finally {
    isJoiningEnterprise.value = false
  }
}

async function sendSMSCode() {
  if (!newPhone.value.trim()) {
    showToast('请输入手机号', 'error')
    return
  }

  if (!/^1[3-9]\d{9}$/.test(newPhone.value)) {
    showToast('请输入有效的手机号', 'error')
    return
  }

  smsLoading.value = true
  try {
    const token = localStorage.getItem('rag_token')
    const response = await fetch(`${API_BASE}/api/v1/auth/sms/send`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ phone: newPhone.value.trim() })
    })

    if (response.ok) {
      const data = await response.json()
      smsSent.value = true
      smsCountdown.value = data.expire_seconds || 60
      showToast(`验证码已发送${data.debug_code ? `（调试码：${data.debug_code}）` : ''}`, 'success')
      
      const timer = setInterval(() => {
        smsCountdown.value--
        if (smsCountdown.value <= 0) {
          clearInterval(timer)
        }
      }, 1000)
    } else {
      const errorData = await response.json().catch(() => ({}))
      showToast(`发送验证码失败: ${errorData.detail || '未知错误'}`, 'error')
    }
  } catch (error) {
    console.error('发送验证码失败:', error)
    showToast('发送验证码失败，请检查网络连接', 'error')
  } finally {
    smsLoading.value = false
  }
}

async function updatePhone() {
  if (!smsCode.value.trim()) {
    showToast('请输入验证码', 'error')
    return
  }

  isUpdatingPhone.value = true
  try {
    const token = localStorage.getItem('rag_token')
    
    // 验证验证码
    const verifyResponse = await fetch(`${API_BASE}/api/v1/auth/sms/verify`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        phone: newPhone.value.trim(),
        code: smsCode.value.trim()
      })
    })

    if (!verifyResponse.ok) {
      const errorData = await verifyResponse.json().catch(() => ({}))
      showToast(`验证码错误: ${errorData.detail || '未知错误'}`, 'error')
      isUpdatingPhone.value = false
      return
    }

    // 更新手机号
    const updateResponse = await fetch(`${API_BASE}/api/v1/auth/profile`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        phone: newPhone.value.trim()
      })
    })

    if (updateResponse.ok) {
      phone.value = newPhone.value.trim()
      showToast('手机号更新成功！', 'success')
      showPhoneModal.value = false
      newPhone.value = ''
      smsCode.value = ''
      smsSent.value = false
      smsCountdown.value = 0
    } else {
      const errorData = await updateResponse.json().catch(() => ({}))
      showToast(`手机号更新失败: ${errorData.detail || '未知错误'}`, 'error')
    }
  } catch (error) {
    console.error('更新手机号失败:', error)
    showToast('手机号更新失败，请检查网络连接', 'error')
  } finally {
    isUpdatingPhone.value = false
  }
}

function checkPasswordStrength() {
  const password = newPassword.value
  let strength = 0
  
  if (password.length >= 8) strength++
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++
  if (/\d/.test(password)) strength++
  if (/[^a-zA-Z0-9]/.test(password)) strength++
  
  passwordStrength.value = strength
}

function changeTheme(theme: 'light' | 'dark' | 'auto') {
  selectedTheme.value = theme
  localStorage.setItem('rag_theme', theme)
  
  if (theme === 'dark') {
    document.documentElement.classList.add('dark')
  } else if (theme === 'light') {
    document.documentElement.classList.remove('dark')
  } else {
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }
  
  showToast('主题设置已保存', 'success')
}

function showToast(message: string, type: 'success' | 'error' | 'info') {
  saveMessage.value = message
  saveSuccess.value = type === 'success'
  
  setTimeout(() => {
    saveMessage.value = ''
  }, 3000)
}

// 监听新密码变化
watch(newPassword, checkPasswordStrength)
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-teal-50 via-white to-cyan-50">
    <!-- Header -->
    <div class="bg-white/80 backdrop-blur-md border-b border-teal-100 shadow-sm sticky top-0 z-50">
      <div class="max-w-5xl mx-auto px-6 py-4">
        <div class="flex items-center gap-4">
          <button
            @click="goBack"
            class="p-2.5 hover:bg-teal-50 rounded-xl transition-all duration-200 hover:scale-105"
          >
            <ArrowLeft :size="20" class="text-teal-700" />
          </button>
          <div>
            <h1 class="text-2xl font-bold text-gray-900">个人设置</h1>
            <p class="text-sm text-gray-500">管理你的账户、企业和偏好设置</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab Navigation -->
    <div class="max-w-5xl mx-auto px-6 pt-6">
      <div class="flex gap-2 bg-white/60 backdrop-blur-sm rounded-2xl p-1.5 shadow-sm border border-gray-100">
        <button
          v-for="tab in ['profile', 'security', 'enterprise']"
          :key="tab"
          @click="activeTab = tab"
          class="flex-1 py-2.5 px-4 rounded-xl text-sm font-medium transition-all duration-200"
          :class="activeTab === tab 
            ? 'bg-gradient-to-r from-teal-500 to-cyan-500 text-white shadow-md' 
            : 'text-gray-600 hover:bg-gray-100'"
        >
          <div class="flex items-center justify-center gap-2">
            <User v-if="tab === 'profile'" :size="18" />
            <Shield v-if="tab === 'security'" :size="18" />
            <Building2 v-if="tab === 'enterprise'" :size="18" />
            <span>{{ tab === 'profile' ? '基本信息' : tab === 'security' ? '安全设置' : '企业管理' }}</span>
          </div>
        </button>
      </div>
    </div>

    <!-- Toast Notification -->
    <Transition
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="translate-y-4 opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="translate-y-0 opacity-100"
      leave-to-class="translate-y-4 opacity-0"
    >
      <div
        v-if="saveMessage"
        class="fixed top-24 right-6 z-50 max-w-sm p-4 rounded-2xl shadow-lg border backdrop-blur-md"
        :class="saveSuccess 
          ? 'bg-teal-50/95 border-teal-200 text-teal-900' 
          : 'bg-red-50/95 border-red-200 text-red-900'"
      >
        <div class="flex items-center gap-3">
          <div :class="saveSuccess ? 'text-teal-600' : 'text-red-600'">
            <CheckCircle v-if="saveSuccess" :size="20" />
            <AlertCircle v-else :size="20" />
          </div>
          <p class="text-sm font-medium">{{ saveMessage }}</p>
        </div>
      </div>
    </Transition>

    <!-- Content -->
    <div class="max-w-5xl mx-auto px-6 py-8">
      <!-- Profile Tab -->
      <div v-show="activeTab === 'profile'" class="space-y-6">
        <!-- Avatar Card -->
        <div class="bg-white rounded-3xl p-8 shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
          <h2 class="text-xl font-bold text-gray-900 mb-6 flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-400 to-cyan-500 flex items-center justify-center">
              <User :size="20" class="text-white" />
            </div>
            头像设置
          </h2>
          
          <div class="flex items-center gap-10">
            <div class="relative group">
              <div class="w-36 h-36 rounded-3xl overflow-hidden bg-gradient-to-br from-emerald-500 via-teal-500 to-teal-600 flex items-center justify-center shadow-xl transition-transform group-hover:scale-105">
                <img 
                  v-if="avatarPreview" 
                  :src="avatarPreview" 
                  class="w-full h-full object-cover"
                  alt="用户头像"
                />
                <span v-else class="text-white font-bold text-5xl">
                  {{ (fullName || '用户').slice(0, 2) }}
                </span>
              </div>
              <div class="absolute inset-0 bg-black/20 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <span class="text-white text-sm font-medium">预览</span>
              </div>
            </div>
            
            <div class="flex-1">
              <input
                ref="avatarInput"
                type="file"
                class="hidden"
                accept="image/*"
                @change="handleAvatarSelect"
              />
              
              <button
                @click="$refs.avatarInput?.click()"
                class="px-6 py-3 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-xl hover:from-teal-600 hover:to-cyan-600 transition-all shadow-lg hover:shadow-xl flex items-center gap-2 mb-3"
              >
                <Upload :size="18" />
                选择新头像
              </button>
              
              <button
                v-if="avatarFile"
                @click="uploadAvatar"
                :disabled="isUploadingAvatar"
                class="px-6 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl hover:from-green-600 hover:to-emerald-600 transition-all shadow-lg hover:shadow-xl flex items-center gap-2 disabled:opacity-50"
              >
                <Loader2 v-if="isUploadingAvatar" :size="18" class="animate-spin" />
                <Save v-else :size="18" />
                {{ isUploadingAvatar ? '上传中...' : '上传头像' }}
              </button>
              
              <p class="text-sm text-gray-500 mt-4">
                支持 JPG、PNG、GIF 格式，建议尺寸 200x200 像素
              </p>
            </div>
          </div>
        </div>

        <!-- Basic Info Card -->
        <div class="bg-white rounded-3xl p-8 shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
          <h2 class="text-xl font-bold text-gray-900 mb-6 flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <User :size="20" class="text-white" />
            </div>
            基本信息
          </h2>
          
          <div class="space-y-5">
            <div>
              <label class="text-sm font-semibold text-gray-700 mb-2 block">用户名</label>
              <input
                v-model="fullName"
                type="text"
                placeholder="请输入用户名"
                class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
              />
            </div>
            
            <div>
              <label class="text-sm font-semibold text-gray-700 mb-2 block">邮箱</label>
              <div class="relative">
                <Mail :size="20" class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  v-model="email"
                  type="email"
                  disabled
                  class="w-full pl-12 pr-4 py-3 bg-gray-100 border border-gray-200 rounded-xl text-gray-500 cursor-not-allowed"
                />
              </div>
              <p class="text-xs text-gray-400 mt-1.5">邮箱不可修改</p>
            </div>

            <div>
              <label class="text-sm font-semibold text-gray-700 mb-2 block">手机号</label>
              <div class="flex gap-3">
                <div class="relative flex-1">
                  <Phone :size="20" class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    :value="phone || '未设置'"
                    type="text"
                    disabled
                    class="w-full pl-12 pr-4 py-3 bg-gray-100 border border-gray-200 rounded-xl text-gray-500 cursor-not-allowed"
                  />
                </div>
                <button
                  @click="showPhoneModal = true"
                  class="px-6 py-3 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-xl hover:from-teal-600 hover:to-cyan-600 transition-all shadow-lg hover:shadow-xl flex items-center gap-2"
                >
                  <Sparkles :size="18" />
                  {{ phone ? '更换手机号' : '绑定手机号' }}
                </button>
              </div>
            </div>
            
            <button
              @click="updateProfile"
              :disabled="isSaving"
              class="w-full py-3.5 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-xl hover:from-teal-600 hover:to-cyan-600 transition-all shadow-lg hover:shadow-xl flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <Loader2 v-if="isSaving" :size="18" class="animate-spin" />
              <Save v-else :size="18" />
              {{ isSaving ? '保存中...' : '保存修改' }}
            </button>
          </div>
        </div>

        <!-- Theme Card -->
        <div class="bg-white rounded-3xl p-8 shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
          <h2 class="text-xl font-bold text-gray-900 mb-6 flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
              <Sun :size="20" class="text-white" />
            </div>
            主题设置
          </h2>
          
          <div class="grid grid-cols-3 gap-4">
            <button
              @click="changeTheme('light')"
              class="p-6 rounded-2xl border-2 transition-all hover:shadow-lg"
              :class="selectedTheme === 'light' 
                ? 'border-teal-500 bg-teal-50 shadow-md' 
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'"
            >
              <Sun :size="36" class="mx-auto mb-3" :class="selectedTheme === 'light' ? 'text-teal-600' : 'text-gray-400'" />
              <p class="font-semibold text-gray-900">浅色</p>
              <p class="text-xs text-gray-500 mt-1">明亮清爽</p>
            </button>
            
            <button
              @click="changeTheme('dark')"
              class="p-6 rounded-2xl border-2 transition-all hover:shadow-lg"
              :class="selectedTheme === 'dark' 
                ? 'border-teal-500 bg-teal-50 shadow-md' 
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'"
            >
              <Moon :size="36" class="mx-auto mb-3" :class="selectedTheme === 'dark' ? 'text-teal-600' : 'text-gray-400'" />
              <p class="font-semibold text-gray-900">深色</p>
              <p class="text-xs text-gray-500 mt-1">护眼舒适</p>
            </button>
            
            <button
              @click="changeTheme('auto')"
              class="p-6 rounded-2xl border-2 transition-all hover:shadow-lg"
              :class="selectedTheme === 'auto' 
                ? 'border-teal-500 bg-teal-50 shadow-md' 
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'"
            >
              <Monitor :size="36" class="mx-auto mb-3" :class="selectedTheme === 'auto' ? 'text-teal-600' : 'text-gray-400'" />
              <p class="font-semibold text-gray-900">自动</p>
              <p class="text-xs text-gray-500 mt-1">跟随系统</p>
            </button>
          </div>
        </div>
      </div>

      <!-- Security Tab -->
      <div v-show="activeTab === 'security'" class="space-y-6">
        <!-- Password Card -->
        <div class="bg-white rounded-3xl p-8 shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
          <h2 class="text-xl font-bold text-gray-900 mb-6 flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-400 to-red-500 flex items-center justify-center">
              <Lock :size="20" class="text-white" />
            </div>
            修改密码
          </h2>
          
          <div class="space-y-5">
            <div>
              <label class="text-sm font-semibold text-gray-700 mb-2 block">当前密码</label>
              <div class="relative">
                <Lock :size="20" class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  v-model="currentPassword"
                  :type="showCurrentPassword ? 'text' : 'password'"
                  placeholder="请输入当前密码"
                  class="w-full pl-12 pr-12 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
                />
                <button
                  @click="showCurrentPassword = !showCurrentPassword"
                  class="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <Eye v-if="showCurrentPassword" :size="20" />
                  <EyeOff v-else :size="20" />
                </button>
              </div>
            </div>
            
            <div>
              <label class="text-sm font-semibold text-gray-700 mb-2 block">新密码</label>
              <div class="relative">
                <KeyRound :size="20" class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  v-model="newPassword"
                  :type="showNewPassword ? 'text' : 'password'"
                  placeholder="请输入新密码（至少6个字符）"
                  class="w-full pl-12 pr-12 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
                />
                <button
                  @click="showNewPassword = !showNewPassword"
                  class="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <Eye v-if="showNewPassword" :size="20" />
                  <EyeOff v-else :size="20" />
                </button>
              </div>
              
              <!-- Password Strength Indicator -->
              <div v-if="newPassword" class="mt-3">
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-xs text-gray-500">密码强度：</span>
                  <span class="text-xs font-semibold" :class="{
                    'text-red-600': passwordStrength === 1,
                    'text-amber-600': passwordStrength === 2,
                    'text-green-600': passwordStrength >= 3
                  }">
                    {{ passwordStrengthText }}
                  </span>
                </div>
                <div class="flex gap-1.5">
                  <div 
                    v-for="i in 4" 
                    :key="i"
                    class="h-1.5 flex-1 rounded-full transition-all"
                    :class="i <= passwordStrength ? passwordStrengthClass : 'bg-gray-200'"
                  ></div>
                </div>
                <p class="text-xs text-gray-400 mt-2">
                  建议：包含大小写字母、数字和特殊字符
                </p>
              </div>
            </div>
            
            <div>
              <label class="text-sm font-semibold text-gray-700 mb-2 block">确认新密码</label>
              <div class="relative">
                <KeyRound :size="20" class="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  v-model="confirmPassword"
                  :type="showConfirmPassword ? 'text' : 'password'"
                  placeholder="请再次输入新密码"
                  class="w-full pl-12 pr-12 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
                />
                <button
                  @click="showConfirmPassword = !showConfirmPassword"
                  class="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <Eye v-if="showConfirmPassword" :size="20" />
                  <EyeOff v-else :size="20" />
                </button>
              </div>
              
              <!-- Password Match Indicator -->
              <div v-if="confirmPassword" class="mt-2 flex items-center gap-2">
                <div :class="newPassword === confirmPassword ? 'text-green-600' : 'text-red-600'">
                  <CheckCircle v-if="newPassword === confirmPassword" :size="14" />
                  <AlertCircle v-else :size="14" />
                </div>
                <span class="text-xs" :class="newPassword === confirmPassword ? 'text-green-600' : 'text-red-600'">
                  {{ newPassword === confirmPassword ? '密码匹配' : '密码不匹配' }}
                </span>
              </div>
            </div>

            <!-- Error Message -->
            <div v-if="passwordError" class="p-3 bg-red-50 border border-red-200 rounded-xl flex items-center gap-2">
              <AlertCircle :size="16" class="text-red-600" />
              <p class="text-sm text-red-700">{{ passwordError }}</p>
            </div>
            
            <button
              @click="updatePassword"
              :disabled="isSaving"
              class="w-full py-3.5 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-xl hover:from-teal-600 hover:to-cyan-600 transition-all shadow-lg hover:shadow-xl flex items-center justify-center gap-2 disabled:opacity-50"
            >
              <Loader2 v-if="isSaving" :size="18" class="animate-spin" />
              <Lock v-else :size="18" />
              {{ isSaving ? '修改中...' : '修改密码' }}
            </button>
          </div>
        </div>

        <!-- Security Tips -->
        <div class="bg-gradient-to-br from-teal-50 to-cyan-50 rounded-3xl p-6 border border-teal-100">
          <h3 class="font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Shield :size="20" class="text-teal-600" />
            安全建议
          </h3>
          <ul class="space-y-2 text-sm text-gray-700">
            <li class="flex items-start gap-2">
              <Check :size="16" class="text-teal-600 mt-0.5 flex-shrink-0" />
              密码长度至少为8个字符
            </li>
            <li class="flex items-start gap-2">
              <Check :size="16" class="text-teal-600 mt-0.5 flex-shrink-0" />
              包含大小写字母、数字和特殊字符
            </li>
            <li class="flex items-start gap-2">
              <Check :size="16" class="text-teal-600 mt-0.5 flex-shrink-0" />
              避免使用与其他网站相同的密码
            </li>
            <li class="flex items-start gap-2">
              <Check :size="16" class="text-teal-600 mt-0.5 flex-shrink-0" />
              定期更换密码，建议每3个月更换一次
            </li>
          </ul>
        </div>
      </div>

      <!-- Enterprise Tab -->
      <div v-show="activeTab === 'enterprise'" class="space-y-6">
        <!-- Current Enterprise Card -->
        <div class="bg-white rounded-3xl p-8 shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
          <h2 class="text-xl font-bold text-gray-900 mb-6 flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <Building2 :size="20" class="text-white" />
            </div>
            当前企业
          </h2>
          
          <div v-if="currentEnterprise" class="p-6 bg-gradient-to-br from-emerald-50 to-teal-50 rounded-2xl border border-emerald-100">
            <div class="flex items-center gap-4">
              <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg">
                <Building2 :size="32" class="text-white" />
              </div>
              <div class="flex-1">
                <h3 class="text-xl font-bold text-gray-900">{{ currentEnterprise.name }}</h3>
                <p class="text-sm text-gray-500 mt-1">企业 ID：{{ currentEnterprise.tenant_id }}</p>
              </div>
              <div class="px-4 py-2 bg-green-100 text-green-700 rounded-xl text-sm font-semibold">
                已加入
              </div>
            </div>
          </div>
          
          <div v-else class="p-6 bg-gray-50 rounded-2xl border border-gray-200 text-center">
            <div class="w-16 h-16 mx-auto rounded-2xl bg-gray-200 flex items-center justify-center mb-4">
              <Building2 :size="32" class="text-gray-400" />
            </div>
            <p class="text-gray-500 mb-4">您还没有加入任何企业</p>
            <button
              @click="showInviteCodeModal = true"
              class="px-6 py-3 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-xl hover:from-teal-600 hover:to-cyan-600 transition-all shadow-lg hover:shadow-xl flex items-center gap-2 mx-auto"
            >
              <Sparkles :size="18" />
              加入企业
            </button>
          </div>
        </div>

        <!-- Switch Enterprise Card -->
        <div class="bg-white rounded-3xl p-8 shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
          <h2 class="text-xl font-bold text-gray-900 mb-6 flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-400 to-cyan-500 flex items-center justify-center">
              <Building2 :size="20" class="text-white" />
            </div>
            {{ currentEnterprise ? '切换企业' : '加入新企业' }}
          </h2>
          
          <div class="text-center py-8">
            <div class="w-20 h-20 mx-auto rounded-3xl bg-gradient-to-br from-teal-100 to-cyan-100 flex items-center justify-center mb-4">
              <Sparkles :size="40" class="text-teal-600" />
            </div>
            <p class="text-gray-600 mb-6 max-w-md mx-auto">
              {{ currentEnterprise 
                ? '如果您想加入另一个企业，可以使用新的邀请码进行切换' 
                : '请使用企业邀请码加入企业' }}
            </p>
            <button
              @click="showInviteCodeModal = true"
              class="px-8 py-4 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-2xl hover:from-teal-600 hover:to-cyan-600 transition-all shadow-lg hover:shadow-xl text-lg font-semibold flex items-center gap-2 mx-auto"
            >
              <Sparkles :size="20" />
              {{ currentEnterprise ? '使用新邀请码' : '输入邀请码加入' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Back Button -->
      <div class="mt-8">
        <button
          @click="goBack"
          class="w-full py-4 bg-white border-2 border-gray-200 text-gray-700 rounded-2xl hover:bg-gray-50 hover:border-gray-300 transition-all font-medium shadow-sm flex items-center justify-center gap-2"
        >
          <ArrowLeft :size="18" />
          返回首页
        </button>
      </div>
    </div>

    <!-- Invite Code Modal -->
    <Transition
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="showInviteCodeModal"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        @click.self="showInviteCodeModal = false"
      >
        <div class="bg-white rounded-3xl shadow-2xl max-w-md w-full p-8">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-xl font-bold text-gray-900 flex items-center gap-2">
              <Building2 :size="24" class="text-teal-600" />
              加入企业
            </h3>
            <button
              @click="showInviteCodeModal = false"
              class="p-2 hover:bg-gray-100 rounded-xl transition-colors"
            >
              <X :size="20" class="text-gray-500" />
            </button>
          </div>
          
          <div class="space-y-4">
            <div>
              <label class="text-sm font-semibold text-gray-700 mb-2 block">邀请码</label>
              <input
                v-model="inviteCode"
                type="text"
                placeholder="请输入8位邀请码"
                class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all uppercase tracking-wider"
                @input="inviteCode = inviteCode.toUpperCase()"
              />
            </div>
            
            <div v-if="inviteCodeValidation" class="p-4 rounded-xl border flex items-start gap-3" :class="inviteCodeValidation.valid ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'">
              <div :class="inviteCodeValidation.valid ? 'text-green-600' : 'text-red-600'">
                <CheckCircle v-if="inviteCodeValidation.valid" :size="20" />
                <AlertCircle v-else :size="20" />
              </div>
              <div class="flex-1">
                <p class="text-sm font-medium" :class="inviteCodeValidation.valid ? 'text-green-900' : 'text-red-900'">
                  {{ inviteCodeValidation.message }}
                </p>
                <p v-if="inviteCodeValidation.enterprise_name" class="text-sm text-green-700 mt-1">
                  企业名称：{{ inviteCodeValidation.enterprise_name }}
                </p>
              </div>
            </div>
            
            <div class="flex gap-3 pt-2">
              <button
                @click="validateInviteCode"
                class="flex-1 py-3 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-all font-medium"
              >
                验证邀请码
              </button>
              <button
                @click="joinEnterprise"
                :disabled="!inviteCodeValidation?.valid || isJoiningEnterprise"
                class="flex-1 py-3 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-xl hover:from-teal-600 hover:to-cyan-600 transition-all shadow-lg hover:shadow-xl font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                <Loader2 v-if="isJoiningEnterprise" :size="18" class="animate-spin" />
                <Sparkles v-else :size="18" />
                {{ isJoiningEnterprise ? '加入中...' : '确认加入' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Phone Update Modal -->
    <Transition
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="showPhoneModal"
        class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        @click.self="showPhoneModal = false"
      >
        <div class="bg-white rounded-3xl shadow-2xl max-w-md w-full p-8">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-xl font-bold text-gray-900 flex items-center gap-2">
              <Phone :size="24" class="text-teal-600" />
              {{ phone ? '更换手机号' : '绑定手机号' }}
            </h3>
            <button
              @click="showPhoneModal = false"
              class="p-2 hover:bg-gray-100 rounded-xl transition-colors"
            >
              <X :size="20" class="text-gray-500" />
            </button>
          </div>
          
          <div class="space-y-4">
            <div>
              <label class="text-sm font-semibold text-gray-700 mb-2 block">新手机号</label>
              <input
                v-model="newPhone"
                type="tel"
                placeholder="请输入11位手机号"
                class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
              />
            </div>
            
            <div>
              <label class="text-sm font-semibold text-gray-700 mb-2 block">验证码</label>
              <div class="flex gap-3">
                <input
                  v-model="smsCode"
                  type="text"
                  placeholder="请输入验证码"
                  class="flex-1 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
                  maxlength="6"
                />
                <button
                  @click="sendSMSCode"
                  :disabled="smsCountdown > 0 || smsLoading"
                  class="px-4 py-3 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-xl hover:from-teal-600 hover:to-cyan-600 transition-all shadow-lg hover:shadow-xl font-medium disabled:opacity-50 whitespace-nowrap"
                >
                  <Loader2 v-if="smsLoading" :size="18" class="animate-spin" />
                  <span v-else-if="smsCountdown > 0">{{ smsCountdown }}s</span>
                  <span v-else>发送验证码</span>
                </button>
              </div>
            </div>
            
            <button
              @click="updatePhone"
              :disabled="!smsSent || !smsCode || isUpdatingPhone"
              class="w-full py-3.5 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-xl hover:from-teal-600 hover:to-cyan-600 transition-all shadow-lg hover:shadow-xl font-medium disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <Loader2 v-if="isUpdatingPhone" :size="18" class="animate-spin" />
              <Check v-else :size="18" />
              {{ isUpdatingPhone ? '更新中...' : '确认更新' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Password Strength Colors */
.strength-weak {
  @apply bg-red-500;
}

.strength-medium {
  @apply bg-amber-500;
}

.strength-strong {
  @apply bg-green-500;
}

.strength-very-strong {
  @apply bg-emerald-500;
}

/* Animations */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in-up {
  animation: fadeInUp 0.3s ease-out;
}

/* Transitions */
* {
  @apply transition-all duration-200;
}

/* Focus styles */
input:focus {
  @apply outline-none ring-2 ring-teal-500 ring-opacity-50;
}

/* Button hover effects */
button:not(:disabled):hover {
  @apply transform scale-[1.02];
}

button:not(:disabled):active {
  @apply transform scale-[0.98];
}

/* Modal backdrop */
.modal-backdrop {
  @apply bg-black/50 backdrop-blur-sm;
}

/* Toast animations */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
</style>
