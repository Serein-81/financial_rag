<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  AlertCircle,
  ArrowRight,
  Building2,
  CheckCircle,
  Key,
  Lock,
  Mail,
  Phone,
  Shield,
  Sparkles,
  User,
  UserCircle2
} from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

const userType = ref<'normal' | 'admin'>('normal')
const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const fullName = ref('')
const phone = ref('')
const inviteCode = ref('')
const companyName = ref('')
const error = ref('')
const isLoading = ref(false)

const particles = Array.from({ length: 58 }, (_, index) => ({
  id: index,
  left: `${(index * 29) % 100}%`,
  top: `${(index * 47) % 100}%`,
  size: `${2 + (index % 5)}px`,
  delay: `${(index % 11) * 0.36}s`,
  duration: `${9 + (index % 8)}s`,
  opacity: 0.18 + (index % 6) * 0.07
}))

const progress = computed(() => {
  const required = [username.value.trim(), email.value.trim(), password.value, confirmPassword.value]
  const optional = [fullName.value.trim(), phone.value.trim()]
  const admin = userType.value === 'admin' ? [companyName.value.trim()] : []
  const values = [...required, ...optional, ...admin]
  return Math.round((values.filter(Boolean).length / values.length) * 100)
})

function selectUserType(type: 'normal' | 'admin') {
  userType.value = type
  error.value = ''
  inviteCode.value = ''
  companyName.value = ''
}

function getFriendlyRegisterError(err: any): string {
  const detail = err?.response?.data?.detail
  const firstDetail = Array.isArray(detail) ? detail[0] : null
  const field = firstDetail?.loc?.[firstDetail.loc.length - 1]

  if (field === 'username') return '用户名长度至少需要 2 个字符'
  if (field === 'phone') return '手机号格式不正确，请输入 11 位中国大陆手机号'
  if (field === 'email') return '邮箱格式不正确，请检查后重新输入'
  if (field === 'password') return '密码长度至少需要 6 位'
  if (field === 'full_name') return '姓名长度至少需要 2 个字符'
  if (field === 'company_name') return '企业名称长度至少需要 2 个字符'
  if (field === 'invite_code') return '邀请码格式不正确，请检查后重新输入'
  if (typeof detail === 'string') return detail

  return err?.message || '注册失败，请检查信息后重试'
}

async function handleRegister() {
  const trimmedUsername = username.value.trim()
  const trimmedEmail = email.value.trim()
  const trimmedPhone = phone.value.trim()
  const trimmedFullName = fullName.value.trim()
  const trimmedCompanyName = companyName.value.trim()
  const trimmedInviteCode = inviteCode.value.trim()

  if (!trimmedUsername || !password.value || !trimmedEmail) {
    error.value = '请填写用户名、密码和邮箱'
    return
  }

  if (trimmedUsername.length < 2) {
    error.value = '用户名长度至少需要 2 个字符'
    return
  }

  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }

  if (password.value.length < 6) {
    error.value = '密码长度至少需要 6 位'
    return
  }

  if (trimmedPhone && !/^1[3-9]\d{9}$/.test(trimmedPhone)) {
    error.value = '手机号格式不正确，请输入 11 位中国大陆手机号'
    return
  }

  if (userType.value === 'admin' && !trimmedCompanyName) {
    error.value = '请填写企业名称'
    return
  }

  try {
    isLoading.value = true
    error.value = ''

    if (userType.value === 'admin') {
      await authStore.registerAdmin(
        trimmedUsername,
        trimmedEmail,
        password.value,
        trimmedFullName || trimmedUsername,
        trimmedCompanyName,
        trimmedPhone || undefined
      )
    } else {
      await authStore.register(
        trimmedUsername,
        trimmedEmail,
        password.value,
        trimmedFullName || undefined,
        trimmedInviteCode || undefined,
        trimmedPhone || undefined
      )
    }

    router.push('/login')
  } catch (err: any) {
    error.value = getFriendlyRegisterError(err)
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="auth-shell relative min-h-screen overflow-x-hidden overflow-y-auto bg-slate-950 px-4 py-6 text-slate-100 lg:py-8">
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

    <div class="relative z-10 mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-7xl items-center">
      <section class="auth-frame grid max-h-none w-full overflow-hidden rounded-2xl border border-white/10 bg-white/[0.055] shadow-2xl shadow-emerald-950/30 backdrop-blur-2xl lg:max-h-[calc(100vh-4rem)] lg:grid-cols-[0.95fr_1.25fr]">
        <aside class="hero-panel relative hidden min-h-[680px] overflow-hidden border-r border-white/10 p-10 lg:flex lg:flex-col lg:justify-between">
          <div class="scanline"></div>
          <div class="relative">
            <div class="mb-12 flex items-center gap-3">
              <div class="brand-mark">
                <Sparkles :size="24" />
              </div>
              <div>
                <p class="text-sm font-semibold tracking-wide text-white">RAG Terminal</p>
                <p class="text-xs text-emerald-100/60">Enterprise Knowledge Workspace</p>
              </div>
            </div>

            <p class="eyebrow">Account Provisioning</p>
            <h1 class="mt-5 max-w-md text-5xl font-semibold leading-tight text-white">
              创建你的知识协作空间
            </h1>
            <p class="mt-6 max-w-md text-sm leading-7 text-slate-300">
              先完成登录所需的核心信息。手机号和姓名可以稍后在个人中心补充，注册完成后将回到登录页。
            </p>
          </div>

          <div class="relative space-y-4">
            <div class="status-card">
              <div class="flex items-center justify-between text-xs text-slate-400">
                <span>Profile readiness</span>
                <span class="text-emerald-300">{{ progress }}%</span>
              </div>
              <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-800">
                <div class="h-full rounded-full bg-gradient-to-r from-emerald-400 to-cyan-300 transition-all duration-500" :style="{ width: `${progress}%` }"></div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3 text-xs">
              <div class="metric-card">
                <Shield :size="17" class="mb-2 text-emerald-300" />
                <p>租户隔离</p>
                <strong>Scoped</strong>
              </div>
              <div class="metric-card">
                <CheckCircle :size="17" class="mb-2 text-emerald-300" />
                <p>注册流程</p>
                <strong>Login First</strong>
              </div>
            </div>
          </div>
        </aside>

        <main class="register-scroll relative overflow-y-auto p-5 sm:p-8 lg:max-h-[calc(100vh-4rem)] lg:p-10">
          <div class="mx-auto max-w-3xl pb-2">
            <div class="mb-7 flex flex-col gap-4 border-b border-white/10 pb-6 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p class="eyebrow">Create account</p>
                <h2 class="mt-3 text-3xl font-semibold text-white">注册账号</h2>
                <p class="mt-3 text-sm text-slate-400">用户名、密码和邮箱用于登录；个人资料稍后可修改。</p>
              </div>
              <router-link to="/login" class="text-sm font-semibold text-emerald-300 transition hover:text-emerald-200">
                去登录
              </router-link>
            </div>

            <div class="mb-6 grid grid-cols-2 gap-3 rounded-xl border border-white/10 bg-slate-900/60 p-2 backdrop-blur-xl">
              <button
                type="button"
                @click="selectUserType('normal')"
                class="mode-button"
                :class="userType === 'normal' ? 'mode-button-active' : 'text-slate-400 hover:bg-white/5 hover:text-white'"
              >
                <div class="flex items-center gap-2">
                  <UserCircle2 :size="18" />
                  <span class="font-semibold">普通用户</span>
                </div>
                <p class="mt-1 text-xs opacity-75">个人或企业成员</p>
              </button>

              <button
                type="button"
                @click="selectUserType('admin')"
                class="mode-button"
                :class="userType === 'admin' ? 'mode-button-active' : 'text-slate-400 hover:bg-white/5 hover:text-white'"
              >
                <div class="flex items-center gap-2">
                  <Building2 :size="18" />
                  <span class="font-semibold">企业管理员</span>
                </div>
                <p class="mt-1 text-xs opacity-75">创建企业账号</p>
              </button>
            </div>

            <div v-if="error" class="mb-5 flex items-start gap-3 rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
              <AlertCircle :size="18" class="mt-0.5 shrink-0" />
              <p>{{ error }}</p>
            </div>

            <div class="form-card rounded-xl border border-white/10 bg-slate-900/70 p-5 shadow-2xl shadow-slate-950/30 backdrop-blur-xl sm:p-6">
              <div class="grid gap-5 sm:grid-cols-2">
                <label class="space-y-2 sm:col-span-2">
                  <span class="auth-label"><User :size="16" /> 用户名 <b>*</b></span>
                  <input v-model="username" type="text" placeholder="请输入用户名" class="auth-input" />
                </label>

                <label class="space-y-2">
                  <span class="auth-label"><Lock :size="16" /> 密码 <b>*</b></span>
                  <input v-model="password" type="password" placeholder="至少 6 位" class="auth-input" />
                </label>

                <label class="space-y-2">
                  <span class="auth-label"><Lock :size="16" /> 确认密码 <b>*</b></span>
                  <input v-model="confirmPassword" type="password" placeholder="再次输入密码" class="auth-input" @keydown.enter="handleRegister" />
                </label>

                <label class="space-y-2 sm:col-span-2">
                  <span class="auth-label"><Mail :size="16" /> 邮箱地址 <b>*</b></span>
                  <input v-model="email" type="email" placeholder="your@email.com" class="auth-input" />
                </label>

                <label class="space-y-2">
                  <span class="auth-label"><User :size="16" /> 姓名 <em>选填</em></span>
                  <input v-model="fullName" type="text" placeholder="可在个人中心修改" class="auth-input" />
                </label>

                <label class="space-y-2">
                  <span class="auth-label"><Phone :size="16" /> 手机号码 <em>选填</em></span>
                  <input v-model="phone" type="tel" placeholder="可在个人中心补充" class="auth-input" />
                </label>

                <label v-if="userType === 'normal'" class="space-y-2 sm:col-span-2">
                  <span class="auth-label"><Key :size="16" /> 企业邀请码 <em>选填</em></span>
                  <input v-model="inviteCode" type="text" placeholder="如有企业邀请码请输入" class="auth-input" @keydown.enter="handleRegister" />
                </label>

                <label v-if="userType === 'admin'" class="space-y-2 sm:col-span-2">
                  <span class="auth-label"><Building2 :size="16" /> 企业名称 <b>*</b></span>
                  <input v-model="companyName" type="text" placeholder="请输入企业名称" class="auth-input" @keydown.enter="handleRegister" />
                </label>
              </div>

              <button
                type="button"
                @click="handleRegister"
                :disabled="isLoading"
                class="primary-button mt-7 flex w-full items-center justify-center gap-2 rounded-lg px-5 py-3.5 text-sm font-semibold text-slate-950 transition disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span>{{ isLoading ? '注册中...' : '创建账号' }}</span>
                <ArrowRight v-if="!isLoading" :size="18" />
              </button>
            </div>

            <p class="mt-6 text-center text-sm text-slate-400">
              已有账号？
              <router-link to="/login" class="font-semibold text-emerald-300 transition hover:text-emerald-200">
                立即登录
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
    radial-gradient(circle at 12% 16%, rgba(16, 185, 129, 0.2), transparent 30%),
    radial-gradient(circle at 86% 20%, rgba(59, 130, 246, 0.16), transparent 28%),
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
  right: 5%;
  bottom: 8%;
  width: 440px;
  height: 440px;
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

.register-scroll {
  scrollbar-width: thin;
  scrollbar-color: rgba(52, 211, 153, 0.45) rgba(15, 23, 42, 0.5);
}

.register-scroll::-webkit-scrollbar {
  width: 8px;
}

.register-scroll::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.45);
}

.register-scroll::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(52, 211, 153, 0.78), rgba(103, 232, 249, 0.58));
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

.status-card,
.metric-card {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.055);
  padding: 0.9rem;
  backdrop-filter: blur(16px);
}

.metric-card p {
  color: rgb(148 163 184);
}

.metric-card strong {
  margin-top: 0.25rem;
  display: block;
  color: white;
}

.mode-button {
  border-radius: 0.6rem;
  padding: 0.85rem 1rem;
  text-align: left;
  transition: background-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.mode-button-active {
  background: linear-gradient(135deg, rgba(52, 211, 153, 0.95), rgba(103, 232, 249, 0.92));
  color: #020617;
  box-shadow: 0 14px 34px rgba(16, 185, 129, 0.22);
}

.auth-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: rgb(203 213 225);
}

.auth-label b {
  color: rgb(248 113 113);
}

.auth-label em {
  font-style: normal;
  font-size: 0.75rem;
  font-weight: 400;
  color: rgb(100 116 139);
}

.auth-input {
  width: 100%;
  border-radius: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(15, 23, 42, 0.76);
  padding: 0.9rem 1rem;
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
