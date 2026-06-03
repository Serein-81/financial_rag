<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { AlertCircle, ArrowRight, Bot, Eye, EyeOff, Lock, Mail, Network, Search, Sparkles, User } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

const identifier = ref('')
const password = ref('')
const error = ref('')
const isLoading = ref(false)
const showPassword = ref(false)

function getFriendlyLoginError(err: any): string {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (err?.response?.status === 401) return '账号或密码不正确，请重新输入'
  return err?.message ? `登录失败：${err.message}` : '登录失败，请检查账号和密码'
}

async function handleLogin() {
  const loginIdentifier = identifier.value.trim()

  if (!loginIdentifier) {
    error.value = '请填写用户名或邮箱'
    return
  }

  if (!password.value) {
    error.value = '请填写密码'
    return
  }

  try {
    isLoading.value = true
    error.value = ''
    await authStore.login(loginIdentifier, password.value)
    router.push('/')
  } catch (err: any) {
    error.value = getFriendlyLoginError(err)
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="auth-shell relative min-h-screen overflow-hidden bg-slate-50 px-4 py-8 text-slate-900">
    <div class="aurora aurora-one"></div>
    <div class="aurora aurora-two"></div>

    <div class="relative z-10 mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-5xl items-center">
      <section class="auth-frame grid w-full overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-xl lg:grid-cols-[0.9fr_1fr]">
        <aside class="hero-panel relative hidden min-h-[620px] overflow-hidden border-r border-slate-200/80 p-10 lg:flex lg:flex-col lg:justify-between">
          <div class="relative">
            <div class="mb-14 flex items-center gap-3">
              <div class="brand-mark">
                <Sparkles :size="24" />
              </div>
              <div>
                <p class="text-sm font-semibold tracking-wide text-slate-900">RAG Terminal</p>
                <p class="text-xs text-emerald-600/80">知识工作台</p>
              </div>
            </div>

            <p class="eyebrow">安全登录</p>
            <h1 class="mt-5 max-w-sm text-5xl font-semibold leading-tight text-slate-900">
              欢迎回来
            </h1>
            <p class="mt-6 max-w-sm text-sm leading-7 text-slate-600">
              登录后继续使用你的知识库、文档检索和智能问答工作空间。
            </p>
          </div>

          <div class="relative rounded-xl border border-slate-200 bg-white/80 p-4 text-sm text-slate-600 backdrop-blur-xl">
            <div class="flex items-center gap-2 text-emerald-600">
              <span class="h-2 w-2 rounded-full bg-emerald-500"></span>
              连接已加密
            </div>
            <p class="mt-3 text-xs leading-5 text-slate-500">
              请使用用户名或邮箱登录。
            </p>
          </div>
        </aside>

        <main class="relative flex min-h-[620px] items-center justify-center p-5 sm:p-8 lg:p-12">
          <div class="w-full max-w-md">
            <div class="mb-8">
              <p class="eyebrow">登录</p>
              <h2 class="mt-3 text-3xl font-semibold text-slate-900">登录账号</h2>
              <p class="mt-3 text-sm leading-6 text-slate-500">请输入用户名或邮箱，以及你的登录密码。</p>
            </div>

            <div v-if="error" class="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <AlertCircle :size="18" class="mt-0.5 shrink-0" />
              <p>{{ error }}</p>
            </div>

            <div class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <div class="space-y-5">
                <label class="block space-y-2">
                  <span class="auth-label"><User :size="16" /> 用户名或邮箱</span>
                  <div class="relative">
                    <input
                      v-model="identifier"
                      type="text"
                      placeholder="请输入用户名或邮箱"
                      class="auth-input pl-11"
                      @keydown.enter="handleLogin"
                    />
                    <Mail :size="17" class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                  </div>
                </label>

                <label class="block space-y-2">
                  <span class="auth-label"><Lock :size="16" /> 密码</span>
                  <div class="relative">
                    <input
                      v-model="password"
                      :type="showPassword ? 'text' : 'password'"
                      placeholder="请输入密码"
                      class="auth-input pl-11 pr-12"
                      @keydown.enter="handleLogin"
                    />
                    <Lock :size="17" class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                    <button
                      type="button"
                      @click="showPassword = !showPassword"
                      class="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                      aria-label="切换密码显示"
                    >
                      <Eye v-if="!showPassword" :size="18" />
                      <EyeOff v-else :size="18" />
                    </button>
                  </div>
                </label>
              </div>

              <button
                type="button"
                @click="handleLogin"
                :disabled="isLoading"
                class="primary-button mt-7 flex w-full items-center justify-center gap-2 rounded-lg px-5 py-3.5 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span>{{ isLoading ? '登录中...' : '登录' }}</span>
                <ArrowRight v-if="!isLoading" :size="18" />
              </button>
            </div>

            <p class="mt-6 text-center text-sm text-slate-500">
              还没有账号？
              <router-link to="/register" class="font-semibold text-emerald-600 transition hover:text-emerald-700">
                立即注册
              </router-link>
            </p>
          </div>
        </main>
      </section>
    </div>
  </div>
</template>

<style scoped>
.auth-shell {
  background:
    radial-gradient(circle at 18% 18%, rgba(16, 185, 129, 0.10), transparent 32%),
    radial-gradient(circle at 88% 12%, rgba(14, 165, 233, 0.08), transparent 30%),
    linear-gradient(135deg, #f8fafc 0%, #eef6f5 48%, #f8fafc 100%);
}

.aurora {
  position: absolute;
  filter: blur(60px);
  pointer-events: none;
}

.aurora-one {
  left: 8%;
  top: 8%;
  width: 360px;
  height: 360px;
  background: rgba(16, 185, 129, 0.10);
  animation: drift 12s ease-in-out infinite alternate;
}

.aurora-two {
  right: 6%;
  bottom: 4%;
  width: 420px;
  height: 420px;
  background: rgba(14, 165, 233, 0.08);
  animation: drift 16s ease-in-out infinite alternate-reverse;
}

.auth-frame {
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.hero-panel {
  background:
    linear-gradient(160deg, rgba(255, 255, 255, 0.96), rgba(240, 253, 250, 0.9)),
    radial-gradient(circle at 74% 18%, rgba(16, 185, 129, 0.10), transparent 36%);
}

.brand-mark {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #059669, #0d9488);
  color: #ffffff;
  box-shadow: 0 12px 26px rgba(16, 185, 129, 0.22);
}

.eyebrow {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgb(5 150 105);
}

.auth-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: rgb(51 65 85);
}

.auth-input {
  width: 100%;
  border-radius: 0.75rem;
  border: 1px solid rgb(226 232 240);
  background: #ffffff;
  padding-top: 0.9rem;
  padding-bottom: 0.9rem;
  color: #0f172a;
  outline: none;
  transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.auth-input::placeholder {
  color: rgb(148 163 184);
}

.auth-input:focus {
  border-color: rgb(16 185 129);
  background: #ffffff;
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.12);
  transform: translateY(-1px);
}

.primary-button {
  background: linear-gradient(135deg, #059669, #0d9488);
  box-shadow: 0 12px 28px rgba(16, 185, 129, 0.24);
}

.primary-button:hover {
  background: linear-gradient(135deg, #047857, #0f766e);
  transform: translateY(-1px);
  box-shadow: 0 16px 34px rgba(16, 185, 129, 0.30);
}

@keyframes drift {
  from {
    transform: translate3d(0, 0, 0) scale(1);
  }
  to {
    transform: translate3d(34px, -24px, 0) scale(1.08);
  }
}
</style>
