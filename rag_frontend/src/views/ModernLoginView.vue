<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Sparkles, Mail, Lock, ArrowRight, AlertCircle } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const error = ref('')
const isLoading = ref(false)

async function handleLogin() {
  if (!email.value || !password.value) {
    error.value = '请填写邮箱和密码'
    return
  }

  try {
    isLoading.value = true
    error.value = ''
    await authStore.login(email.value, password.value)
    router.push('/')
  } catch (err) {
    error.value = '登录失败，请检查邮箱和密码'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex items-center justify-center p-4">
    <div class="w-full max-w-md">
      <!-- Logo & Title -->
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl mb-4 shadow-lg">
          <Sparkles :size="32" class="text-white" />
        </div>
        <h1 class="text-3xl font-bold text-gray-900 mb-2">
          欢迎回来
        </h1>
        <p class="text-gray-600">登录到你的 RAG 知识库系统</p>
      </div>

      <!-- Login Card -->
      <div class="bg-white rounded-2xl shadow-xl p-8 space-y-6">
        <!-- Error Message -->
        <div v-if="error" class="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle :size="20" class="text-red-500 flex-shrink-0 mt-0.5" />
          <p class="text-sm text-red-700">{{ error }}</p>
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
            class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none"
            @keydown.enter="handleLogin"
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
            placeholder="••••••••"
            class="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 placeholder-gray-400 focus:bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none"
            @keydown.enter="handleLogin"
          />
        </div>

        <!-- Login Button -->
        <button
          @click="handleLogin"
          :disabled="isLoading"
          class="w-full py-3.5 bg-gradient-to-r from-blue-500 to-purple-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-purple-700 focus:ring-4 focus:ring-blue-200 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl flex items-center justify-center gap-2"
        >
          <span>{{ isLoading ? '登录中...' : '登录' }}</span>
          <ArrowRight :size="18" v-if="!isLoading" />
        </button>

        <!-- Register Link -->
        <div class="text-center pt-4 border-t border-gray-100">
          <p class="text-sm text-gray-600">
            还没有账号？
            <router-link
              to="/register"
              class="text-blue-600 hover:text-blue-700 font-medium transition-colors"
            >
              立即注册
            </router-link>
          </p>
        </div>
      </div>

      <!-- Footer -->
      <p class="text-center text-sm text-gray-500 mt-8">
        © 2024 RAG Terminal. 安全可靠的知识库系统
      </p>
    </div>
  </div>
</template>
