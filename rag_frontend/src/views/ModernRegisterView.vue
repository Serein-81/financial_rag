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
  <div class="auth-shell relative min-h-screen overflow-x-hidden overflow-y-auto bg-slate-50 px-4 py-6 text-slate-900 lg:py-8">
    <div class="aurora aurora-one"></div>
    <div class="aurora aurora-two"></div>

    <div class="relative z-10 mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-7xl items-center">
      <section class="auth-frame grid max-h-none w-full overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-xl lg:max-h-[calc(100vh-4rem)] lg:grid-cols-[0.95fr_1.25fr]">
        <aside class="hero-panel relative hidden min-h-[680px] overflow-hidden border-r border-slate-200/80 p-10 lg:flex lg:flex-col lg:justify-between">
          <div class="relative">
            <div class="mb-12 flex items-center gap-3">
              <div class="brand-mark">
                <Sparkles :size="24" />
              </div>
              <div>
                <p class="text-sm font-semibold tracking-wide text-slate-900">RAG Terminal</p>
                <p class="text-xs text-emerald-600/80">Enterprise Knowledge Workspace</p>
              </div>
            </div>

            <p class="eyebrow">Account Provisioning</p>
            <h1 class="mt-5 max-w-md text-5xl font-semibold leading-tight text-slate-900">
              创建你的知识协作空间
            </h1>
            <p class="mt-6 max-w-md text-sm leading-7 text-slate-600">
              先完成登录所需的核心信息。手机号和姓名可以稍后在个人中心补充，注册完成后将回到登录页。
            </p>
          </div>

          <div class="relative space-y-4">
            <div class="status-card">
              <div class="flex items-center justify-between text-xs text-slate-500">
                <span>Profile readiness</span>
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
                <strong>Scoped</strong>
              </div>
              <div class="metric-card">
                <CheckCircle :size="17" class="mb-2 text-emerald-600" />
                <p>注册流程</p>
                <strong>Login First</strong>
              </div>
            </div>
          </div>
        </aside>

        <main class="register-scroll relative overflow-y-auto p-5 sm:p-8 lg:max-h-[calc(100vh-4rem)] lg:p-10">
          <div class="mx-auto max-w-3xl pb-2">
            <div class="mb-7 flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p class="eyebrow">Create account</p>
                <h2 class="mt-3 text-3xl font-semibold text-slate-900">注册账号</h2>
                <p class="mt-3 text-sm text-slate-500">用户名、密码和邮箱用于登录；个人资料稍后可修改。</p>
              </div>
              <router-link to="/login" class="text-sm font-semibold text-emerald-600 transition hover:text-emerald-700">
                去登录
              </router-link>
            </div>

            <div class="mb-6 grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-2">
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

            <div class="form-card rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
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
                class="primary-button mt-7 flex w-full items-center justify-center gap-2 rounded-lg px-5 py-3.5 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span>{{ isLoading ? '注册中...' : '创建账号' }}</span>
                <ArrowRight v-if="!isLoading" :size="18" />
              </button>
            </div>

            <p class="mt-6 text-center text-sm text-slate-500">
              已有账号？
              <router-link to="/login" class="font-semibold text-emerald-600 transition hover:text-emerald-700">
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
    radial-gradient(circle at 12% 16%, rgba(16, 185, 129, 0.10), transparent 32%),
    radial-gradient(circle at 86% 20%, rgba(14, 165, 233, 0.08), transparent 30%),
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
  right: 5%;
  bottom: 8%;
  width: 440px;
  height: 440px;
  background: rgba(14, 165, 233, 0.08);
  animation: drift 16s ease-in-out infinite alternate-reverse;
}

.auth-frame {
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.9);
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

.status-card,
.metric-card {
  border: 1px solid rgb(226 232 240);
  border-radius: 10px;
  background: #ffffff;
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
