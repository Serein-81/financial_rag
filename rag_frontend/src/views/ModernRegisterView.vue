<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Sparkles, Mail, Lock, User, ArrowRight, AlertCircle, Building2, UserCircle2, Key } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

// 🟢 新增逻辑：用户类型选择
const userType = ref<'normal' | 'admin'>('normal')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const fullName = ref('')
// 🟢 新增逻辑：普通用户可选的邀请码（用于加入企业）
const inviteCode = ref('')
// 🟢 新增逻辑：企业管理员必填的企业名称
const companyName = ref('')
const error = ref('')
const isLoading = ref(false)

// 🟢 新增逻辑：切换用户类型
function selectUserType(type: 'normal' | 'admin') {
  userType.value = type
  error.value = ''
  inviteCode.value = '' // 切换时清空邀请码
  companyName.value = '' // 切换时清空企业名称
}

async function handleRegister() {
  if (!email.value || !password.value || !fullName.value) {
    error.value = '请填写所有必填字段'
    return
  }

  // 🟢 新增逻辑：企业管理员必须填写企业名称
  if (userType.value === 'admin' && !companyName.value) {
    error.value = '请填写企业名称'
    return
  }

  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }

  if (password.value.length < 6) {
    error.value = '密码长度至少为 6 位'
    return
  }

  try {
    isLoading.value = true
    error.value = ''
    
    // 🟢 新增逻辑：根据用户类型调用不同的注册接口
    if (userType.value === 'admin') {
      // 企业管理员注册（不需要邀请码，但需要企业名称）
      await authStore.registerAdmin(email.value, password.value, fullName.value, companyName.value)
    } else {
      // 普通用户注册（可选邀请码）
      await authStore.register(email.value, password.value, fullName.value, inviteCode.value || undefined)
    }
    
    router.push('/')
  } catch (err: any) {
    error.value = err.message || '注册失败，请检查信息后重试'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-100 via-emerald-50/30 to-teal-50/30 flex items-center justify-center p-4 py-8">
    <div class="w-full max-w-md">
      <!-- Logo & Title -->
      <div class="text-center mb-6">
        <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-2xl mb-4 shadow-lg">
          <Sparkles :size="32" class="text-white" />
        </div>
        <h1 class="text-3xl font-bold text-gray-900 mb-2">
          创建账号
        </h1>
        <p class="text-gray-600">开始使用 RAG 知识库系统</p>
      </div>

      <!-- Register Card - 添加最大高度和滚动 -->
      <div class="bg-white rounded-2xl shadow-xl overflow-hidden" style="max-height: calc(100vh - 200px);">
        <!-- 可滚动内容区域 -->
        <div class="overflow-y-auto p-8 space-y-6" style="max-height: calc(100vh - 200px);">
        <!-- 🟢 新增逻辑：用户类型选择 -->
        <div class="space-y-3">
          <label class="text-sm font-medium text-gray-700 block">选择账号类型</label>
          <div class="grid grid-cols-2 gap-3">
            <button
              @click="selectUserType('normal')"
              type="button"
              class="p-4 rounded-xl border-2 transition-all"
              :class="userType === 'normal' 
                ? 'border-emerald-500 bg-emerald-50' 
                : 'border-gray-200 hover:border-gray-300'"
            >
              <div class="flex flex-col items-center gap-2">
                <div class="w-12 h-12 rounded-full flex items-center justify-center"
                  :class="userType === 'normal' ? 'bg-emerald-100' : 'bg-gray-100'"
                >
                  <UserCircle2 :size="24" :class="userType === 'normal' ? 'text-emerald-600' : 'text-gray-500'" />
                </div>
                <span class="font-medium text-sm" :class="userType === 'normal' ? 'text-emerald-700' : 'text-gray-700'">
                  普通用户
                </span>
                <span class="text-xs text-gray-500">个人或企业员工</span>
              </div>
            </button>

            <button
              @click="selectUserType('admin')"
              type="button"
              class="p-4 rounded-xl border-2 transition-all"
              :class="userType === 'admin' 
                ? 'border-emerald-500 bg-emerald-50' 
                : 'border-gray-200 hover:border-gray-300'"
            >
              <div class="flex flex-col items-center gap-2">
                <div class="w-12 h-12 rounded-full flex items-center justify-center"
                  :class="userType === 'admin' ? 'bg-emerald-100' : 'bg-gray-100'"
                >
                  <Building2 :size="24" :class="userType === 'admin' ? 'text-emerald-600' : 'text-gray-500'" />
                </div>
                <span class="font-medium text-sm" :class="userType === 'admin' ? 'text-emerald-700' : 'text-gray-700'">
                  企业管理员
                </span>
                <span class="text-xs text-gray-500">创建企业账号</span>
              </div>
            </button>
          </div>
        </div>

        <!-- Error Message -->
        <div v-if="error" class="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle :size="20" class="text-red-500 flex-shrink-0 mt-0.5" />
          <p class="text-sm text-red-700">{{ error }}</p>
        </div>

        <!-- Full Name Input -->
        <div class="space-y-2">
          <label class="text-sm font-medium text-gray-700 flex items-center gap-2">
            <User :size="16" />
            姓名
          </label>
          <input
            v-model="fullName"
            type="text"
            placeholder="张三"
            class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all outline-none"
          />
        </div>

        <!-- Email Input -->
        <div class="space-y-2">
          <label class="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Mail :size="16" />
            邮箱地址
          </label>
          <input
            v-model="email"
            type="email"
            placeholder="your@email.com"
            class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all outline-none"
          />
        </div>

        <!-- Password Input -->
        <div class="space-y-2">
          <label class="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Lock :size="16" />
            密码
          </label>
          <input
            v-model="password"
            type="password"
            placeholder="至少 6 位"
            class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all outline-none"
          />
        </div>

        <!-- Confirm Password Input -->
        <div class="space-y-2">
          <label class="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Lock :size="16" />
            确认密码
          </label>
          <input
            v-model="confirmPassword"
            type="password"
            placeholder="再次输入密码"
            class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all outline-none"
            @keydown.enter="handleRegister"
          />
        </div>

        <!-- 🟢 新增逻辑：普通用户可选的企业邀请码 -->
        <div v-if="userType === 'normal'" class="space-y-2">
          <label class="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Key :size="16" />
            企业邀请码
            <span class="text-xs text-gray-500 font-normal">（可选）</span>
          </label>
          <input
            v-model="inviteCode"
            type="text"
            placeholder="如有企业邀请码请输入"
            class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all outline-none"
            @keydown.enter="handleRegister"
          />
          <p class="text-xs text-gray-500 flex items-center gap-1">
            <AlertCircle :size="12" />
            有邀请码将加入企业团队，无邀请码将创建个人账号
          </p>
        </div>

        <!-- 🟢 新增逻辑：企业管理员必填的企业名称 -->
        <div v-if="userType === 'admin'" class="space-y-2">
          <label class="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Building2 :size="16" />
            企业名称
            <span class="text-xs text-red-500 font-normal">（必填）</span>
          </label>
          <input
            v-model="companyName"
            type="text"
            placeholder="某某科技有限公司"
            class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all outline-none"
            @keydown.enter="handleRegister"
          />
        </div>

        <!-- Register Button -->
        <button
          @click="handleRegister"
          :disabled="isLoading"
          class="w-full py-3.5 bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-medium rounded-xl hover:from-emerald-700 hover:to-teal-700 focus:ring-4 focus:ring-emerald-200 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl flex items-center justify-center gap-2"
        >
          <span>{{ isLoading ? '注册中...' : '注册' }}</span>
          <ArrowRight :size="18" v-if="!isLoading" />
        </button>

        <!-- Login Link -->
        <div class="text-center pt-4 border-t border-gray-100">
          <p class="text-sm text-gray-600">
            已有账号？
            <router-link
              to="/login"
              class="text-emerald-600 hover:text-emerald-700 font-medium transition-colors"
            >
              立即登录
            </router-link>
          </p>
        </div>
        </div>
        <!-- 结束可滚动内容区域 -->
      </div>

      <!-- Footer -->
      <p class="text-center text-sm text-gray-500 mt-6">
        © 2024 RAG Terminal. 安全可靠的知识库系统
      </p>
    </div>
  </div>
</template>
