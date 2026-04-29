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

  // 濡傛灉娌℃湁澶村儚 URL 浣嗘湁鐢ㄦ埛鍚嶏紝鐢熸垚榛樿澶村儚
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

  // 鑾峰彇鐢ㄦ埛瀹屾暣淇℃伅锛堝寘鎷ご鍍忥級
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
      console.error('鑾峰彇鐢ㄦ埛淇℃伅澶辫触:', error)
    }
  }

  // 鍒濆鍖栨椂锛屽鏋渢oken瀛樺湪浣哸vatar涓嶅瓨鍦紝寮傛鑾峰彇鐢ㄦ埛淇℃伅
  if (token.value && !avatarUrl.value) {
    console.log('馃攧 [STORE] Token瀛樺湪浣嗗ご鍍忎负绌猴紝灏濊瘯鑾峰彇鐢ㄦ埛淇℃伅...')
    fetchUserProfile()
  }

  // 鐢熸垚榛樿澶村儚 URL
  function getDefaultAvatarUrl(name: string): string {
    const colors = [
      '3B82F6', 'EF4444', 'F59E0B', '10B981', '8B5CF6', 
      'EC4899', '06B6D4', 'F97316', '6366F1', '84CC16'
    ]
    const color = colors[name.charCodeAt(0) % colors.length]
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&size=200&background=${color}&color=ffffff&bold=true`
  }

  async function login(email: string, password: string) {
    console.log('[STORE] authStore.login called')
    console.log('[STORE] login identifier:', email)
    const data = await apiLogin(email, password)
    console.log('[STORE] login API succeeded, setting token')
    token.value = data.access_token
    userName.value = data.user_name
    userEmail.value = email
    localStorage.setItem('rag_user_name', data.user_name)
    localStorage.setItem('rag_user_email', email)
    console.log('[STORE] token length:', token.value?.length)
    
    // 淇濆瓨澶村儚 URL
    if (data.avatar_url) {
      avatarUrl.value = data.avatar_url
      localStorage.setItem('rag_avatar_url', data.avatar_url)
      console.log('[STORE] avatar URL saved:', data.avatar_url)
    }
    
    // 鑾峰彇鐢ㄦ埛瀹屾暣淇℃伅锛堝寘鎷?user_id锛?
    await fetchUserProfile()
  }

  async function register(username: string, email: string, password: string, full_name?: string, invite_code?: string, phone?: string) {
    await apiRegister(username, email, password, full_name, invite_code, phone)
  }

  // 企业管理员注册
  async function registerAdmin(username: string, email: string, password: string, full_name: string, company_name: string, phone?: string) {
    await apiRegisterAdmin(username, email, password, full_name, company_name, phone)
  }

  // 发送短信验证码
  async function sendSMS(phone: string) {
    return await authApi.sendSMS({ phone })
  }

  // 楠岃瘉鐭俊楠岃瘉鐮?
  async function verifySMS(phone: string, code: string) {
    return await authApi.verifySMS({ phone, code })
  }

  // 鏇存柊鐢ㄦ埛璧勬枡
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

  // 涓婁紶澶村儚
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
    console.log('[STORE] setAvatarUrl called:', url)
    avatarUrl.value = url
    localStorage.setItem('rag_avatar_url', url)
    console.log('[STORE] avatar URL saved')
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

