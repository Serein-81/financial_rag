<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Sparkles, User, Mail, Lock, ArrowRight, AlertCircle, Shield } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const isLoading = ref(false)
const isCardVisible = ref(false)
const particles = ref<Array<{ x: number; y: number; size: number; duration: number; delay: number }>>([])

onMounted(() => {
  generateParticles()
  setTimeout(() => {
    isCardVisible.value = true
  }, 100)
})

function generateParticles() {
  for (let i = 0; i < 50; i++) {
    particles.value.push({
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 6 + 2,
      duration: Math.random() * 20 + 15,
      delay: Math.random() * 5
    })
  }
}

async function handleLogin() {
  if (!password.value) {
    error.value = '请填写密码'
    return
  }

  if (!username.value && !email.value) {
    error.value = '请填写用户名或邮箱'
    return
  }

  try {
    isLoading.value = true
    error.value = ''
    const loginIdentifier = username.value || email.value
    await authStore.login(loginIdentifier, password.value)
    router.push('/')
  } catch (err: any) {
    if (err.response?.data?.detail) {
      error.value = '登录失败：' + (err.response.data.detail || '用户名或密码错误')
    } else if (err.message) {
      error.value = '登录失败：' + err.message
    } else {
      error.value = '登录失败，请检查用户名和密码'
    }
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-100 via-emerald-50/30 to-teal-50/30 relative overflow-hidden flex items-center justify-center p-4">
    <!-- Animated Background -->
    <div class="absolute inset-0 overflow-hidden">
      <div class="absolute top-1/4 -left-10 w-72 h-72 bg-emerald-400/20 rounded-full blur-3xl animate-pulse"></div>
      <div class="absolute bottom-1/4 -right-10 w-72 h-72 bg-teal-400/20 rounded-full blur-3xl animate-pulse" style="animation-delay: 1s;"></div>
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-gradient-to-r from-emerald-300/10 to-teal-300/10 rounded-full blur-3xl"></div>
    </div>

    <!-- Floating Particles -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div
        v-for="(particle, index) in particles"
        :key="index"
        class="absolute rounded-full bg-gradient-to-r from-emerald-400/30 to-teal-400/30"
        :style="{
          left: particle.x + '%',
          top: particle.y + '%',
          width: particle.size + 'px',
          height: particle.size + 'px',
          animation: `float ${particle.duration}s ease-in-out infinite`,
          animationDelay: particle.delay + 's'
        }"
      ></div>
    </div>

    <div class="w-full max-w-md relative z-10">
      <!-- Logo & Title with Animation -->
      <div class="text-center mb-8" :class="{ 'animate-fade-in-down': isCardVisible }">
        <div class="relative inline-block group cursor-pointer">
          <div class="absolute -inset-4 bg-gradient-to-r from-emerald-400 to-teal-400 rounded-3xl blur-lg opacity-30 group-hover:opacity-50 transition-opacity duration-500"></div>
          <div class="relative inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-2xl shadow-2xl transform group-hover:scale-105 group-hover:rotate-3 transition-all duration-300">
            <Sparkles :size="40" class="text-white animate-pulse" />
          </div>
        </div>
        <h1 class="text-4xl font-bold text-gray-900 mb-3 mt-6 tracking-tight">
          欢迎回来
        </h1>
        <p class="text-gray-600 text-lg">登录到智能 RAG 知识库系统</p>
        <div class="flex items-center justify-center gap-2 mt-4 text-emerald-600">
          <Shield :size="16" />
          <span class="text-sm font-medium">安全加密连接</span>
        </div>
      </div>

      <!-- Login Card with 3D Effect -->
      <div
        class="bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-10 space-y-8 border border-white/50 transform transition-all duration-700"
        :class="{
          'translate-y-0 opacity-100': isCardVisible,
          'translate-y-8 opacity-0': !isCardVisible
        }"
      >
        <!-- Error Message with Animation -->
        <div
          v-if="error"
          class="bg-red-50/80 backdrop-blur border border-red-200 rounded-2xl p-5 flex items-start gap-4 transform transition-all duration-300 hover:scale-[1.02]"
        >
          <div class="flex-shrink-0 w-10 h-10 bg-red-100 rounded-xl flex items-center justify-center">
            <AlertCircle :size="20" class="text-red-500 animate-bounce" />
          </div>
          <p class="text-sm text-red-700 font-medium pt-2">{{ error }}</p>
        </div>

        <!-- Username Input with Enhanced Animation -->
        <div class="space-y-3 group">
          <label class="text-sm font-semibold text-gray-700 flex items-center gap-3 group-hover:text-emerald-600 transition-colors">
            <div class="w-10 h-10 bg-gradient-to-br from-emerald-50 to-teal-50 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
              <User :size="18" />
            </div>
            用户名
            <span class="text-xs text-gray-500 font-normal">（可选）</span>
          </label>
          <div class="relative">
            <input
              v-model="username"
              type="text"
              placeholder="请输入用户名"
              class="w-full px-5 py-4 bg-slate-50/80 border-2 border-slate-200 rounded-2xl text-slate-900 placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-4 focus:ring-emerald-200/50 transition-all outline-none text-base group-hover:border-emerald-300"
              @keydown.enter="handleLogin"
            />
            <div class="absolute inset-0 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-500 opacity-0 group-focus-within:opacity-10 transition-opacity pointer-events-none"></div>
          </div>
        </div>

        <!-- Email Input with Enhanced Animation -->
        <div class="space-y-3 group">
          <label class="text-sm font-semibold text-gray-700 flex items-center gap-3 group-hover:text-emerald-600 transition-colors">
            <div class="w-10 h-10 bg-gradient-to-br from-emerald-50 to-teal-50 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
              <Mail :size="18" />
            </div>
            邮箱地址
            <span class="text-xs text-gray-500 font-normal">（可选）</span>
          </label>
          <div class="relative">
            <input
              v-model="email"
              type="email"
              placeholder="your@email.com"
              class="w-full px-5 py-4 bg-slate-50/80 border-2 border-slate-200 rounded-2xl text-slate-900 placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-4 focus:ring-emerald-200/50 transition-all outline-none text-base group-hover:border-emerald-300"
              @keydown.enter="handleLogin"
            />
            <div class="absolute inset-0 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-500 opacity-0 group-focus-within:opacity-10 transition-opacity pointer-events-none"></div>
          </div>
          <p class="text-xs text-gray-500 mt-1">
            请填写用户名或邮箱地址至少一项
          </p>
        </div>

        <!-- Password Input with Enhanced Animation -->
        <div class="space-y-3 group">
          <label class="text-sm font-semibold text-gray-700 flex items-center gap-3 group-hover:text-emerald-600 transition-colors">
            <div class="w-10 h-10 bg-gradient-to-br from-emerald-50 to-teal-50 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
              <Lock :size="18" />
            </div>
            密码
          </label>
          <div class="relative">
            <input
              v-model="password"
              type="password"
              placeholder="••••••••"
              class="w-full px-5 py-4 bg-slate-50/80 border-2 border-slate-200 rounded-2xl text-slate-900 placeholder-slate-400 focus:bg-white focus:border-emerald-500 focus:ring-4 focus:ring-emerald-200/50 transition-all outline-none text-base group-hover:border-emerald-300"
              @keydown.enter="handleLogin"
            />
            <div class="absolute inset-0 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-500 opacity-0 group-focus-within:opacity-10 transition-opacity pointer-events-none"></div>
          </div>
        </div>

        <!-- Login Button with Loading Animation -->
        <button
          @click="handleLogin"
          :disabled="isLoading"
          class="w-full py-4 bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-semibold rounded-2xl hover:from-emerald-700 hover:to-teal-700 focus:ring-4 focus:ring-emerald-200 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-2xl transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center gap-3 text-lg relative overflow-hidden group"
        >
          <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-1000"></div>
          <span v-if="isLoading" class="flex items-center gap-3">
            <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            登录中...
          </span>
          <span v-else class="flex items-center gap-3">
            登录
            <ArrowRight :size="20" class="group-hover:translate-x-1 transition-transform" />
          </span>
        </button>

        <!-- Register Link with Enhanced Styling -->
        <div class="text-center pt-6 border-t border-gray-100/80">
          <p class="text-gray-600 group">
            还没有账号？
            <router-link
              to="/register"
              class="text-emerald-600 hover:text-emerald-700 font-semibold transition-all hover:underline underline-offset-4 ml-2 inline-flex items-center gap-1"
            >
              立即注册
              <ArrowRight :size="14" class="group-hover:translate-x-1 transition-transform" />
            </router-link>
          </p>
        </div>

        <!-- Decorative Elements -->
        <div class="absolute -bottom-6 -right-6 w-24 h-24 bg-gradient-to-br from-emerald-200/30 to-teal-200/30 rounded-full blur-2xl"></div>
        <div class="absolute -top-6 -left-6 w-20 h-20 bg-gradient-to-br from-teal-200/30 to-emerald-200/30 rounded-full blur-2xl"></div>
      </div>

      <!-- Footer with Animation -->
      <div
        class="text-center mt-10 space-y-2"
        :class="{
          'animate-fade-in-up': isCardVisible,
          'opacity-0': !isCardVisible
        }"
        style="transition-delay: 0.3s;"
      >
        <p class="text-sm text-gray-500 font-medium">
          © 2026 RAG Terminal. 安全可靠的知识库系统
        </p>
        <div class="flex items-center justify-center gap-4 text-xs text-gray-400">
          <span class="flex items-center gap-1">
            <Shield :size="12" class="text-emerald-500" />
            SSL 加密
          </span>
          <span class="w-1 h-1 bg-gray-300 rounded-full"></span>
          <span>数据安全</span>
          <span class="w-1 h-1 bg-gray-300 rounded-full"></span>
          <span>隐私保护</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes float {
  0%, 100% {
    transform: translateY(0) translateX(0);
    opacity: 0.3;
  }
  50% {
    transform: translateY(-20px) translateX(10px);
    opacity: 0.6;
  }
}

@keyframes fade-in-down {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in-down {
  animation: fade-in-down 0.8s ease-out forwards;
}

.animate-fade-in-up {
  animation: fade-in-up 0.8s ease-out forwards;
}
</style>
