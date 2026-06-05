<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { AlertCircle, ArrowRight, Eye, EyeOff, FileBarChart, Lock, Mail, Search, Sparkles, User } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

const identifier = ref('')
const password = ref('')
const error = ref('')
const isLoading = ref(false)
const showPassword = ref(false)

const parallaxX = ref(0)
const parallaxY = ref(0)

function handleParallax(event: MouseEvent) {
  parallaxX.value = (event.clientX / window.innerWidth - 0.5) * 24
  parallaxY.value = (event.clientY / window.innerHeight - 0.5) * 18
}

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
  <div
    class="auth-shell relative min-h-screen overflow-hidden bg-slate-50 px-4 py-8 text-slate-900"
    :style="{ '--px': parallaxX + 'px', '--py': parallaxY + 'px' }"
    @mousemove="handleParallax"
  >
    <div class="mesh mesh-one"></div>
    <div class="mesh mesh-two"></div>
    <div class="mesh mesh-three"></div>
    <div class="dot-grid"></div>

    <div class="relative z-10 mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-5xl items-center">
      <section class="auth-frame grid w-full overflow-hidden rounded-3xl border border-white/60 bg-white/70 shadow-2xl backdrop-blur-2xl lg:grid-cols-[0.95fr_1fr]">
        <aside class="hero-panel relative hidden min-h-[640px] overflow-hidden p-10 lg:flex lg:flex-col lg:justify-between">
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

            <p class="eyebrow enter d2">安全登录</p>
            <h1 class="gradient-heading enter mt-5 max-w-sm text-5xl font-semibold leading-tight">
              欢迎回来
            </h1>
            <p class="enter d3 mt-5 max-w-sm text-sm leading-7 text-slate-600">
              登录后继续使用智能问答、财税分析、合同审核与政策服务工作空间。
            </p>

            <div class="enter d4 mt-9 space-y-3">
              <div class="feature-chip">
                <span class="feature-ic"><Search :size="16" /></span>
                <div>
                  <p class="feature-title">知识检索与问答</p>
                  <p class="feature-sub">知识库 · 知识图谱 · 多智能体</p>
                </div>
              </div>
              <div class="feature-chip">
                <span class="feature-ic"><FileBarChart :size="16" /></span>
                <div>
                  <p class="feature-title">财税智能</p>
                  <p class="feature-sub">税务分析 · 财务健康 · 合同审核</p>
                </div>
              </div>
              <div class="feature-chip">
                <span class="feature-ic"><Sparkles :size="16" /></span>
                <div>
                  <p class="feature-title">政策服务</p>
                  <p class="feature-sub">政策匹配 · 通知 · 企业服务</p>
                </div>
              </div>
            </div>
          </div>

          <div class="status-pill enter d5 relative z-10">
            <span class="status-dot"></span>
            连接已加密
            <span class="status-sep">·</span>
            <span class="text-slate-500">多租户隔离</span>
          </div>
        </aside>

        <main class="relative flex min-h-[640px] items-center justify-center p-5 sm:p-8 lg:p-12">
          <div class="form-glow"></div>
          <div class="relative z-10 w-full max-w-md">
            <div class="enter d2 mb-8">
              <p class="eyebrow">登录</p>
              <h2 class="mt-3 text-3xl font-semibold text-slate-900">登录账号</h2>
              <p class="mt-3 text-sm leading-6 text-slate-500">请输入用户名或邮箱，以及你的登录密码。</p>
            </div>

            <div v-if="error" class="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <AlertCircle :size="18" class="mt-0.5 shrink-0" />
              <p>{{ error }}</p>
            </div>

            <div class="auth-card enter d3">
              <div class="auth-card-inner p-5 sm:p-6">
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
            </div>

            <p class="enter d5 mt-6 text-center text-sm text-slate-500">
              还没有账号？
              <router-link to="/register" class="font-semibold text-emerald-700 transition hover:text-emerald-800">
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
    radial-gradient(circle at 20% 20%, rgba(16, 185, 129, 0.10), transparent 36%),
    radial-gradient(circle at 82% 16%, rgba(13, 148, 136, 0.10), transparent 34%),
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

.feature-chip {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(8px);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  animation: chipGlow 9s ease-in-out infinite;
}

.feature-chip:nth-child(2) {
  animation-delay: 3s;
}

.feature-chip:nth-child(3) {
  animation-delay: 6s;
}

.feature-chip:hover {
  transform: translateY(-1px);
  border-color: rgba(16, 185, 129, 0.45);
  box-shadow: 0 10px 24px rgba(16, 185, 129, 0.1);
}

.feature-ic {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 9px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.16), rgba(13, 148, 136, 0.16));
  color: #047857;
}

.feature-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: rgb(15 23 42);
}

.feature-sub {
  font-size: 0.6875rem;
  color: rgb(100 116 139);
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: flex-start;
  padding: 8px 14px;
  border-radius: 9999px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  font-size: 0.75rem;
  color: rgb(4 120 87);
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  animation: ping 2.2s ease-out infinite;
}

.status-sep {
  color: rgb(203 213 225);
}

.form-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 440px;
  height: 440px;
  transform: translate(-50%, -50%);
  border-radius: 9999px;
  background: radial-gradient(circle, rgba(16, 185, 129, 0.12), transparent 70%);
  filter: blur(12px);
  pointer-events: none;
  z-index: 0;
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

@keyframes chipGlow {
  0%, 30%, 100% {
    border-color: rgba(226, 232, 240, 0.9);
    box-shadow: 0 0 0 rgba(16, 185, 129, 0);
  }
  10%, 20% {
    border-color: rgba(16, 185, 129, 0.55);
    box-shadow: 0 10px 24px rgba(16, 185, 129, 0.14);
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
  .feature-chip,
  .status-dot,
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
