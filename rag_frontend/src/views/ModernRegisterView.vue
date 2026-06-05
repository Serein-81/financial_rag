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

const parallaxX = ref(0)
const parallaxY = ref(0)

function handleParallax(event: MouseEvent) {
  parallaxX.value = (event.clientX / window.innerWidth - 0.5) * 24
  parallaxY.value = (event.clientY / window.innerHeight - 0.5) * 18
}

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
  <div
    class="auth-shell relative min-h-screen overflow-x-hidden overflow-y-auto bg-slate-50 px-4 py-6 text-slate-900 lg:py-8"
    :style="{ '--px': parallaxX + 'px', '--py': parallaxY + 'px' }"
    @mousemove="handleParallax"
  >
    <div class="mesh mesh-one"></div>
    <div class="mesh mesh-two"></div>
    <div class="mesh mesh-three"></div>
    <div class="dot-grid"></div>

    <div class="relative z-10 mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-7xl items-center">
      <section class="auth-frame grid max-h-none w-full overflow-hidden rounded-3xl border border-white/60 bg-white/70 shadow-2xl backdrop-blur-2xl lg:max-h-[calc(100vh-4rem)] lg:grid-cols-[0.95fr_1.25fr]">
        <aside class="hero-panel relative hidden min-h-[680px] overflow-hidden p-10 lg:flex lg:flex-col lg:justify-between">
          <svg class="graph-deco" viewBox="0 0 400 600" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <g class="graph-lines">
              <line x1="56" y1="90" x2="150" y2="46" />
              <line x1="150" y1="46" x2="250" y2="120" />
              <line x1="250" y1="120" x2="338" y2="70" />
              <line x1="56" y1="90" x2="110" y2="190" />
              <line x1="150" y1="46" x2="214" y2="238" />
              <line x1="250" y1="120" x2="322" y2="206" />
              <line x1="110" y1="190" x2="214" y2="238" />
              <line x1="214" y1="238" x2="322" y2="206" />
              <line x1="214" y1="238" x2="176" y2="344" />
              <line x1="322" y1="206" x2="300" y2="330" />
              <line x1="176" y1="344" x2="232" y2="442" />
              <line x1="300" y1="330" x2="332" y2="500" />
              <line x1="232" y1="442" x2="120" y2="486" />
              <line x1="64" y1="312" x2="176" y2="344" />
            </g>
            <g class="graph-nodes">
              <circle cx="56" cy="90" r="4" style="animation-delay: 0s" />
              <circle cx="150" cy="46" r="3" style="animation-delay: 0.3s" />
              <circle cx="250" cy="120" r="5" style="animation-delay: 0.6s" />
              <circle cx="338" cy="70" r="3" style="animation-delay: 0.9s" />
              <circle cx="110" cy="190" r="4" style="animation-delay: 1.2s" />
              <circle cx="214" cy="238" r="6" style="animation-delay: 0.2s" />
              <circle cx="322" cy="206" r="4" style="animation-delay: 1.5s" />
              <circle cx="64" cy="312" r="3" style="animation-delay: 0.8s" />
              <circle cx="176" cy="344" r="5" style="animation-delay: 0.5s" />
              <circle cx="300" cy="330" r="4" style="animation-delay: 1.1s" />
              <circle cx="232" cy="442" r="4" style="animation-delay: 0.4s" />
              <circle cx="120" cy="486" r="3" style="animation-delay: 1.3s" />
              <circle cx="332" cy="500" r="4" style="animation-delay: 0.7s" />
            </g>
          </svg>

          <div class="relative z-10">
            <div class="enter d1 mb-12 flex items-center gap-3">
              <div class="brand-mark">
                <Sparkles :size="24" />
              </div>
              <div>
                <p class="text-sm font-semibold tracking-wide text-slate-900">企业财税智能平台</p>
                <p class="text-xs text-emerald-700/80">一站式企业智能服务</p>
              </div>
            </div>

            <p class="eyebrow enter d2">创建账号</p>
            <h1 class="gradient-heading enter mt-5 max-w-md text-5xl font-semibold leading-tight">
              创建你的企业智能工作空间
            </h1>
            <p class="enter d3 mt-6 max-w-md text-sm leading-7 text-slate-600">
              先完成登录所需的核心信息。手机号和姓名可以稍后在个人中心补充，注册完成后将回到登录页。
            </p>
          </div>

          <div class="enter d4 relative z-10 space-y-4">
            <div class="status-card">
              <div class="flex items-center justify-between text-xs text-slate-500">
                <span>资料完整度</span>
                <span class="text-emerald-600">{{ progress }}%</span>
              </div>
              <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
                <div class="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-600 transition-all duration-500" :style="{ width: `${progress}%` }"></div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3 text-xs">
              <div class="metric-card">
                <Shield :size="17" class="mb-2 text-emerald-600" />
                <p>租户隔离</p>
                <strong>独立空间</strong>
              </div>
              <div class="metric-card">
                <CheckCircle :size="17" class="mb-2 text-emerald-600" />
                <p>注册流程</p>
                <strong>注册后登录</strong>
              </div>
            </div>
          </div>
        </aside>

        <main class="register-scroll relative overflow-y-auto p-5 sm:p-8 lg:max-h-[calc(100vh-4rem)] lg:p-10">
          <div class="mx-auto max-w-3xl pb-2">
            <div class="enter d2 mb-7 flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p class="eyebrow">注册</p>
                <h2 class="mt-3 text-3xl font-semibold text-slate-900">注册账号</h2>
                <p class="mt-3 text-sm text-slate-500">用户名、密码和邮箱用于登录；个人资料稍后可修改。</p>
              </div>
              <router-link to="/login" class="text-sm font-semibold text-emerald-700 transition hover:text-emerald-800">
                去登录
              </router-link>
            </div>

            <div class="enter d3 mb-6 grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-2">
              <button
                type="button"
                @click="selectUserType('normal')"
                class="mode-button"
                :class="userType === 'normal' ? 'mode-button-active' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900'"
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
                :class="userType === 'admin' ? 'mode-button-active' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900'"
              >
                <div class="flex items-center gap-2">
                  <Building2 :size="18" />
                  <span class="font-semibold">企业管理员</span>
                </div>
                <p class="mt-1 text-xs opacity-75">创建企业账号</p>
              </button>
            </div>

            <div v-if="error" class="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <AlertCircle :size="18" class="mt-0.5 shrink-0" />
              <p>{{ error }}</p>
            </div>

            <div class="auth-card form-card enter d4">
              <div class="auth-card-inner p-5 sm:p-6">
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
                  <input v-model="email" type="email" placeholder="请输入邮箱地址" class="auth-input" />
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
                class="primary-button mt-7 flex w-full items-center justify-center gap-2 rounded-lg px-5 py-3.5 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span>{{ isLoading ? '注册中...' : '创建账号' }}</span>
                <ArrowRight v-if="!isLoading" :size="18" />
              </button>
              </div>
            </div>

            <p class="enter d5 mt-6 text-center text-sm text-slate-500">
              已有账号？
              <router-link to="/login" class="font-semibold text-emerald-700 transition hover:text-emerald-800">
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
    radial-gradient(circle at 12% 16%, rgba(16, 185, 129, 0.10), transparent 36%),
    radial-gradient(circle at 86% 20%, rgba(13, 148, 136, 0.10), transparent 34%),
    linear-gradient(135deg, #f6fbf9 0%, #eef6f5 50%, #f6fbf9 100%);
}

.mesh {
  position: absolute;
  border-radius: 9999px;
  filter: blur(72px);
  pointer-events: none;
  opacity: 0.75;
  transition: translate 0.3s ease-out;
}

.mesh-one {
  left: -4%;
  top: -8%;
  width: 380px;
  height: 380px;
  background: rgba(16, 185, 129, 0.20);
  translate: calc(var(--px, 0px) * 0.8) calc(var(--py, 0px) * 0.8);
  animation: float1 10s ease-in-out infinite alternate;
}

.mesh-two {
  right: -6%;
  top: 14%;
  width: 420px;
  height: 420px;
  background: rgba(13, 148, 136, 0.16);
  translate: calc(var(--px, 0px) * -0.6) calc(var(--py, 0px) * -0.6);
  animation: float2 13s ease-in-out infinite alternate;
}

.mesh-three {
  left: 28%;
  bottom: -14%;
  width: 460px;
  height: 460px;
  background: rgba(56, 189, 248, 0.12);
  translate: calc(var(--px, 0px) * 0.4) calc(var(--py, 0px) * 0.4);
  animation: float1 16s ease-in-out infinite alternate-reverse;
}

.dot-grid {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(15, 23, 42, 0.05) 1px, transparent 1px);
  background-size: 22px 22px;
  -webkit-mask-image: radial-gradient(circle at 50% 38%, black 0%, transparent 72%);
  mask-image: radial-gradient(circle at 50% 38%, black 0%, transparent 72%);
}

.auth-frame {
  box-shadow: 0 30px 80px rgba(15, 23, 42, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.register-scroll {
  scrollbar-width: thin;
  scrollbar-color: rgba(16, 185, 129, 0.45) rgba(226, 232, 240, 0.6);
}

.register-scroll::-webkit-scrollbar {
  width: 8px;
}

.register-scroll::-webkit-scrollbar-track {
  background: rgba(226, 232, 240, 0.5);
}

.register-scroll::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(16, 185, 129, 0.7), rgba(13, 148, 136, 0.55));
}

.hero-panel {
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.6), rgba(236, 253, 245, 0.66) 58%, rgba(240, 253, 250, 0.5));
  border-right: 1px solid rgba(255, 255, 255, 0.6);
}

.graph-deco {
  position: absolute;
  right: -30px;
  top: 28px;
  width: 330px;
  height: 540px;
  opacity: 0.5;
  pointer-events: none;
  z-index: 0;
  translate: calc(var(--px, 0px) * -0.4) calc(var(--py, 0px) * -0.4);
  transition: translate 0.3s ease-out;
  animation: decoFloat 14s ease-in-out infinite alternate;
}

.graph-deco .graph-lines line {
  stroke: rgba(13, 148, 136, 0.28);
  stroke-width: 1;
  stroke-dasharray: 260;
  stroke-dashoffset: 260;
  animation: drawLine 1.8s ease 0.4s forwards;
}

.graph-deco .graph-nodes circle {
  fill: #10b981;
  filter: drop-shadow(0 0 5px rgba(16, 185, 129, 0.55));
  transform-box: fill-box;
  transform-origin: center;
  animation: nodePulse 3.2s ease-in-out infinite;
}

.brand-mark {
  position: relative;
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border-radius: 13px;
  background: linear-gradient(135deg, #059669, #0d9488);
  color: #ffffff;
  box-shadow: 0 14px 30px rgba(16, 185, 129, 0.3);
}

.brand-mark::after {
  content: '';
  position: absolute;
  inset: -5px;
  border-radius: 17px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.5), rgba(13, 148, 136, 0));
  filter: blur(9px);
  z-index: -1;
}

.eyebrow {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgb(5 150 105);
}

.gradient-heading {
  background: linear-gradient(120deg, #0f172a 0%, #047857 45%, #0d9488 70%, #0f172a 100%);
  background-size: 220% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.gradient-heading.enter {
  animation:
    enterUp 0.7s 0.22s cubic-bezier(0.22, 1, 0.36, 1) both,
    gradientShift 7s ease-in-out 1.4s infinite alternate;
}

.status-card,
.metric-card {
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
  padding: 0.9rem;
}

.metric-card p {
  color: rgb(100 116 139);
}

.metric-card strong {
  margin-top: 0.25rem;
  display: block;
  color: rgb(15 23 42);
}

.mode-button {
  border-radius: 0.6rem;
  padding: 0.85rem 1rem;
  text-align: left;
  transition: background-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.mode-button-active {
  background: linear-gradient(135deg, #059669, #0d9488);
  color: #ffffff;
  box-shadow: 0 12px 28px rgba(16, 185, 129, 0.22);
}

.auth-card {
  border-radius: 18px;
  padding: 1px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.5), rgba(13, 148, 136, 0.16) 42%, rgba(226, 232, 240, 0.7));
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.1);
}

.auth-card-inner {
  border-radius: 17px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
}

.auth-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: rgb(51 65 85);
}

.auth-label b {
  color: rgb(220 38 38);
}

.auth-label em {
  font-style: normal;
  font-size: 0.75rem;
  font-weight: 400;
  color: rgb(148 163 184);
}

.auth-input {
  width: 100%;
  border-radius: 0.75rem;
  border: 1px solid rgb(226 232 240);
  background: #ffffff;
  padding: 0.9rem 1rem;
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
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #059669, #0d9488);
  box-shadow: 0 14px 32px rgba(16, 185, 129, 0.28);
}

.primary-button::after {
  content: '';
  position: absolute;
  top: 0;
  left: -130%;
  width: 60%;
  height: 100%;
  background: linear-gradient(120deg, transparent, rgba(255, 255, 255, 0.45), transparent);
  transform: skewX(-20deg);
  animation: sheen 4.6s ease-in-out 1.6s infinite;
}

.primary-button:hover {
  background: linear-gradient(135deg, #047857, #0f766e);
  transform: translateY(-1px);
  box-shadow: 0 18px 40px rgba(16, 185, 129, 0.36);
}

@keyframes float1 {
  from {
    transform: translate(0, 0) scale(1);
  }
  to {
    transform: translate(42px, -34px) scale(1.12);
  }
}

@keyframes float2 {
  from {
    transform: translate(0, 0) scale(1);
  }
  to {
    transform: translate(-46px, 30px) scale(1.1);
  }
}

@keyframes nodePulse {
  0%, 100% {
    opacity: 0.4;
    transform: scale(0.85);
  }
  50% {
    opacity: 1;
    transform: scale(1.25);
  }
}

@keyframes drawLine {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes decoFloat {
  from {
    transform: translateY(0);
  }
  to {
    transform: translateY(-14px);
  }
}

@keyframes gradientShift {
  from {
    background-position: 0% 50%;
  }
  to {
    background-position: 100% 50%;
  }
}

@keyframes sheen {
  0% {
    left: -130%;
  }
  30% {
    left: 130%;
  }
  100% {
    left: 130%;
  }
}

@keyframes enterUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.enter {
  animation: enterUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.d1 {
  animation-delay: 0.05s;
}

.d2 {
  animation-delay: 0.15s;
}

.d3 {
  animation-delay: 0.3s;
}

.d4 {
  animation-delay: 0.42s;
}

.d5 {
  animation-delay: 0.55s;
}

@media (prefers-reduced-motion: reduce) {
  .mesh,
  .graph-deco,
  .graph-deco .graph-lines line,
  .graph-deco .graph-nodes circle,
  .gradient-heading.enter,
  .primary-button::after,
  .enter {
    animation: none !important;
  }

  .enter {
    opacity: 1;
  }

  .graph-deco .graph-lines line {
    stroke-dashoffset: 0;
  }
}

@keyframes ping {
  0% {
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.5);
  }
  70% {
    box-shadow: 0 0 0 8px rgba(16, 185, 129, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
  }
}
</style>
