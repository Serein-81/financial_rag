<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { AlertCircle, ArrowRight, Eye, EyeOff, Lock, Mail, Sparkles, User } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

const identifier = ref('')
const password = ref('')
const error = ref('')
const isLoading = ref(false)
const showPassword = ref(false)

const particles = Array.from({ length: 42 }, (_, index) => ({
  id: index,
  left: `${(index * 37) % 100}%`,
  top: `${(index * 53) % 100}%`,
  size: `${2 + (index % 4)}px`,
  delay: `${(index % 9) * 0.45}s`,
  duration: `${8 + (index % 7)}s`,
  opacity: 0.22 + (index % 5) * 0.08
}))

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
  <div class="auth-shell relative min-h-screen overflow-hidden bg-slate-950 px-4 py-8 text-slate-100">
    <div class="aurora aurora-one"></div>
    <div class="aurora aurora-two"></div>
    <div class="matrix-grid"></div>
    <div class="particle-field" aria-hidden="true">
      <span
        v-for="particle in particles"
        :key="particle.id"
        class="particle"
        :style="{
          left: particle.left,
          top: particle.top,
          width: particle.size,
          height: particle.size,
          animationDelay: particle.delay,
          animationDuration: particle.duration,
          opacity: particle.opacity
        }"
      ></span>
    </div>

    <div class="relative z-10 mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-5xl items-center">
      <section class="auth-frame grid w-full overflow-hidden rounded-2xl border border-white/10 bg-white/[0.055] shadow-2xl shadow-emerald-950/30 backdrop-blur-2xl lg:grid-cols-[0.9fr_1fr]">
        <aside class="hero-panel relative hidden min-h-[620px] overflow-hidden border-r border-white/10 p-10 lg:flex lg:flex-col lg:justify-between">
          <div class="scanline"></div>
          <div class="relative">
            <div class="mb-14 flex items-center gap-3">
              <div class="brand-mark">
                <Sparkles :size="24" />
              </div>
              <div>
                <p class="text-sm font-semibold tracking-wide text-white">RAG Terminal</p>
                <p class="text-xs text-emerald-100/60">知识工作台</p>
              </div>
            </div>

            <p class="eyebrow">安全登录</p>
            <h1 class="mt-5 max-w-sm text-5xl font-semibold leading-tight text-white">
              欢迎回来
            </h1>
            <p class="mt-6 max-w-sm text-sm leading-7 text-slate-300">
              登录后继续使用你的知识库、文档检索和智能问答工作空间。
            </p>
          </div>

          <div class="relative rounded-xl border border-white/10 bg-white/[0.055] p-4 text-sm text-slate-300 backdrop-blur-xl">
            <div class="flex items-center gap-2 text-emerald-300">
              <span class="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_16px_rgba(110,231,183,0.9)]"></span>
              连接已加密
            </div>
            <p class="mt-3 text-xs leading-5 text-slate-400">
              请使用用户名或邮箱登录。
            </p>
          </div>
        </aside>

        <main class="relative flex min-h-[620px] items-center justify-center p-5 sm:p-8 lg:p-12">
          <div class="w-full max-w-md">
            <div class="mb-8">
              <p class="eyebrow">登录</p>
              <h2 class="mt-3 text-3xl font-semibold text-white">登录账号</h2>
              <p class="mt-3 text-sm leading-6 text-slate-400">请输入用户名或邮箱，以及你的登录密码。</p>
            </div>

            <div v-if="error" class="mb-5 flex items-start gap-3 rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
              <AlertCircle :size="18" class="mt-0.5 shrink-0" />
              <p>{{ error }}</p>
            </div>

            <div class="rounded-xl border border-white/10 bg-slate-900/70 p-5 shadow-2xl shadow-slate-950/30 backdrop-blur-xl sm:p-6">
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
                    <Mail :size="17" class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
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
                    <Lock :size="17" class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
                    <button
                      type="button"
                      @click="showPassword = !showPassword"
                      class="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-2 text-slate-400 transition hover:bg-white/10 hover:text-white"
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
                class="primary-button mt-7 flex w-full items-center justify-center gap-2 rounded-lg px-5 py-3.5 text-sm font-semibold text-slate-950 transition disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span>{{ isLoading ? '登录中...' : '登录' }}</span>
                <ArrowRight v-if="!isLoading" :size="18" />
              </button>
            </div>

            <p class="mt-6 text-center text-sm text-slate-400">
              还没有账号？
              <router-link to="/register" class="font-semibold text-emerald-300 transition hover:text-emerald-200">
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
    radial-gradient(circle at 18% 18%, rgba(16, 185, 129, 0.2), transparent 30%),
    radial-gradient(circle at 88% 12%, rgba(59, 130, 246, 0.16), transparent 28%),
    linear-gradient(135deg, #020617 0%, #07111f 48%, #020617 100%);
}

.aurora {
  position: absolute;
  filter: blur(54px);
  pointer-events: none;
}

.aurora-one {
  left: 8%;
  top: 8%;
  width: 360px;
  height: 360px;
  background: rgba(16, 185, 129, 0.16);
  animation: drift 12s ease-in-out infinite alternate;
}

.aurora-two {
  right: 6%;
  bottom: 4%;
  width: 420px;
  height: 420px;
  background: rgba(14, 165, 233, 0.14);
  animation: drift 16s ease-in-out infinite alternate-reverse;
}

.matrix-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.055) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: radial-gradient(circle at center, black 0%, transparent 78%);
}

.particle {
  position: absolute;
  border-radius: 999px;
  background: rgb(167 243 208);
  box-shadow: 0 0 18px rgba(110, 231, 183, 0.9);
  animation: floatParticle linear infinite;
}

.auth-frame {
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.42), inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.hero-panel {
  background:
    linear-gradient(160deg, rgba(15, 23, 42, 0.94), rgba(4, 47, 46, 0.72)),
    radial-gradient(circle at 74% 18%, rgba(16, 185, 129, 0.28), transparent 34%);
}

.scanline {
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent 0%, rgba(255, 255, 255, 0.13) 48%, transparent 58%);
  transform: translateX(-120%);
  animation: scan 7s ease-in-out infinite;
}

.brand-mark {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #34d399, #67e8f9);
  color: #020617;
  box-shadow: 0 16px 36px rgba(16, 185, 129, 0.3);
}

.eyebrow {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgb(110 231 183);
}

.auth-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: rgb(203 213 225);
}

.auth-input {
  width: 100%;
  border-radius: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(15, 23, 42, 0.76);
  padding-top: 0.9rem;
  padding-bottom: 0.9rem;
  color: white;
  outline: none;
  transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.auth-input::placeholder {
  color: rgb(100 116 139);
}

.auth-input:focus {
  border-color: rgb(52 211 153);
  background: rgba(2, 6, 23, 0.86);
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.14), 0 0 32px rgba(16, 185, 129, 0.12);
  transform: translateY(-1px);
}

.primary-button {
  background: linear-gradient(135deg, #34d399, #67e8f9);
  box-shadow: 0 16px 38px rgba(16, 185, 129, 0.28);
}

.primary-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 20px 46px rgba(16, 185, 129, 0.36);
}

@keyframes floatParticle {
  0% {
    transform: translate3d(0, 0, 0) scale(0.8);
  }
  50% {
    transform: translate3d(18px, -38px, 0) scale(1.25);
  }
  100% {
    transform: translate3d(-8px, -76px, 0) scale(0.85);
  }
}

@keyframes drift {
  from {
    transform: translate3d(0, 0, 0) scale(1);
  }
  to {
    transform: translate3d(34px, -24px, 0) scale(1.08);
  }
}

@keyframes scan {
  0%, 42% {
    transform: translateX(-120%);
  }
  68%, 100% {
    transform: translateX(120%);
  }
}
</style>
