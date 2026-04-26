// Auth Store
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister, registerAdmin as apiRegisterAdmin, logout as apiLogout, isAuthenticated, getToken, request } from '@/utils/request'
import { authApi } from '@/api/auth'
import type { UserProfile } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const userName = ref<string | null>(localStorage.getItem('rag_user_name'))
  const userEmail = ref<string | null>(localStorage.getItem('rag_user_email'))
  const userId = ref<string | null>(localStorage.getItem('rag_user_id'))
  const avatarUrl = ref<string | null>(localStorage.getItem('rag_avatar_url'))
  const userProfile = ref<UserProfile | null>(null)
  const isAdmin = ref<boolean>(localStorage.getItem('rag_user_role') === 'admin')

  // 如果没有头像 URL 但有用户名，生成默认头像
  if (!avatarUrl.value && userName.value) {
    const colors = [
      '3B82F6', 'EF4444', 'F59E0B', '10B981', '8B5CF6',
      'EC4899', '06B6D4', 'F97316', '6366F1', '84CC16'
    ]
    const color = colors[userName.value.charCodeAt(0) % colors.length]
    const defaultAvatar = `https://ui-avatars.com/api/?name=${encodeURIComponent(userName.value)}&size=200&background=${color}&color=ffffff&bold=true`
    avatarUrl.value = defaultAvatar
    localStorage.setItem('rag_avatar_url', defaultAvatar)
  }

  const isLoggedIn = computed(() => !!token.value)

  // 获取用户完整信息（包括头像）
  async function fetchUserProfile() {
    try {
      userProfile.value = await authApi.getMe()
      if (userProfile.value.id) {
        userId.value = userProfile.value.id
        localStorage.setItem('rag_user_id', userProfile.value.id)
      }
      if (userProfile.value.avatar_url) {
        avatarUrl.value = userProfile.value.avatar_url
        localStorage.setItem('rag_avatar_url', userProfile.value.avatar_url)
      }
      if (userProfile.value.full_name) {
        userName.value = userProfile.value.full_name
        localStorage.setItem('rag_user_name', userProfile.value.full_name)
      }
      isAdmin.value = userProfile.value.is_admin
      localStorage.setItem('rag_user_role', userProfile.value.is_admin ? 'admin' : 'user')
    } catch (error) {
      console.error('获取用户信息失败:', error)
    }
  }

  // 初始化时，如果token存在但avatar不存在，异步获取用户信息
  if (token.value && !avatarUrl.value) {
    console.log('🔄 [STORE] Token存在但头像为空，尝试获取用户信息...')
    fetchUserProfile()
  }

  // 生成默认头像 URL
  function getDefaultAvatarUrl(name: string): string {
    const colors = [
      '3B82F6', 'EF4444', 'F59E0B', '10B981', '8B5CF6', 
      'EC4899', '06B6D4', 'F97316', '6366F1', '84CC16'
    ]
    const color = colors[name.charCodeAt(0) % colors.length]
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&size=200&background=${color}&color=ffffff&bold=true`
  }

  async function login(email: string, password: string) {
    console.log('🔐 [STORE] authStore.login 被调用')
    console.log('👤 [STORE] 邮箱:', email)
    const data = await apiLogin(email, password)
    console.log('✅ [STORE] API 调用成功，设置 token')
    token.value = data.access_token
    userName.value = data.user_name
    userEmail.value = email
    localStorage.setItem('rag_user_name', data.user_name)
    localStorage.setItem('rag_user_email', email)
    console.log('🔑 [STORE] Token 已设置，长度:', token.value?.length)
    
    // 保存头像 URL
    if (data.avatar_url) {
      avatarUrl.value = data.avatar_url
      localStorage.setItem('rag_avatar_url', data.avatar_url)
      console.log('📸 [STORE] 头像 URL 已保存:', data.avatar_url)
    }
    
    // 获取用户完整信息（包括 user_id）
    await fetchUserProfile()
  }

  async function register(email: string, password: string, full_name: string, invite_code?: string, phone?: string) {
    const data = await apiRegister(email, password, full_name, invite_code, phone)
    token.value = data.access_token
    userName.value = data.user_name || full_name
    userEmail.value = email
    localStorage.setItem('rag_user_name', userName.value)
    localStorage.setItem('rag_user_email', email)
    
    // 保存头像 URL
    if (data.avatar_url) {
      avatarUrl.value = data.avatar_url
      localStorage.setItem('rag_avatar_url', data.avatar_url)
    }
    
    // 获取用户完整信息（包括 user_id）
    await fetchUserProfile()
  }

  // 企业管理员注册
  async function registerAdmin(email: string, password: string, full_name: string, company_name: string, phone?: string) {
    const data = await apiRegisterAdmin(email, password, full_name, company_name, phone)
    token.value = data.access_token
    userName.value = data.user_name || full_name
    userEmail.value = email
    localStorage.setItem('rag_user_name', userName.value)
    localStorage.setItem('rag_user_email', email)
    localStorage.setItem('rag_user_role', 'admin')
    isAdmin.value = true
    
    // 保存头像 URL
    if (data.avatar_url) {
      avatarUrl.value = data.avatar_url
      localStorage.setItem('rag_avatar_url', data.avatar_url)
    }
    
    // 获取用户完整信息（包括 user_id）
    await fetchUserProfile()
  }

  // 发送短信验证码
  async function sendSMS(phone: string) {
    return await authApi.sendSMS({ phone })
  }

  // 验证短信验证码
  async function verifySMS(phone: string, code: string) {
    return await authApi.verifySMS({ phone, code })
  }

  // 更新用户资料
  async function updateProfile(data: { full_name?: string; nickname?: string; bio?: string }) {
    const updatedProfile = await authApi.updateProfile(data)
    userProfile.value = updatedProfile
    if (updatedProfile.id) {
      userId.value = updatedProfile.id
      localStorage.setItem('rag_user_id', updatedProfile.id)
    }
    if (updatedProfile.full_name) {
      userName.value = updatedProfile.full_name
      localStorage.setItem('rag_user_name', updatedProfile.full_name)
    }
    return updatedProfile
  }

  // 上传头像
  async function uploadAvatar(file: File) {
    const response = await authApi.uploadAvatar(file)
    avatarUrl.value = response.avatar_url
    localStorage.setItem('rag_avatar_url', response.avatar_url)
    return response
  }

  function logout() {
    apiLogout()
    token.value = null
    userName.value = null
    userEmail.value = null
    userId.value = null
    avatarUrl.value = null
    userProfile.value = null
    isAdmin.value = false
    localStorage.removeItem('rag_user_name')
    localStorage.removeItem('rag_user_email')
    localStorage.removeItem('rag_user_id')
    localStorage.removeItem('rag_avatar_url')
    localStorage.removeItem('rag_user_role')
  }

  function setAvatarUrl(url: string) {
    console.log('💾 setAvatarUrl 被调用:', url)
    avatarUrl.value = url
    localStorage.setItem('rag_avatar_url', url)
    console.log('✅ 头像 URL 已保存')
    console.log('  - avatarUrl.value:', avatarUrl.value)
    console.log('  - localStorage:', localStorage.getItem('rag_avatar_url'))
  }

  // Initialize on store creation
  if (!isAuthenticated()) {
    token.value = null
  }

  return {
    token,
    userName,
    userEmail,
    userId,
    avatarUrl,
    userProfile,
    isAdmin,
    isLoggedIn,
    login,
    fetchUserProfile,
    register,
    registerAdmin,
    sendSMS,
    verifySMS,
    updateProfile,
    uploadAvatar,
    logout,
    setAvatarUrl,
    getDefaultAvatarUrl,
  }
})
