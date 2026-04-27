<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import gsap from 'gsap'
import { Sparkles, User, Mail, Lock, ArrowRight, AlertCircle, Shield, Eye, EyeOff } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const isLoading = ref(false)
const showPassword = ref(false)

// 模板引用
const logoRef = ref<HTMLElement | null>(null)
const logoSymbolRef = ref<HTMLElement | null>(null)
const cardRef = ref<HTMLElement | null>(null)
const particleContainerRef = ref<HTMLElement | null>(null)
const footerRef = ref<HTMLElement | null>(null)

// GSAP 时间线
let entranceTimeline: gsap.core.Timeline | null = null
let particleTweens: gsap.core.Tween[] = []
let mouseTween: gsap.core.Tween | null = null
let logoFloatTween: gsap.core.Tween | null = null

onMounted(() => {
  setupEntranceAnimation()
  setupParticles()
  setupLogoFloat()

  window.addEventListener('mousemove', handleMouseMove)
})

onBeforeUnmount(() => {
  entranceTimeline?.kill()
  particleTweens.forEach(t => t.kill())
  mouseTween?.kill()
  logoFloatTween?.kill()
  window.removeEventListener('mousemove', handleMouseMove)
})

function handleMouseMove(e: MouseEvent) {
  if (!cardRef.value) return
  const x = (e.clientX / window.innerWidth - 0.5) * 2
  const y = (e.clientY / window.innerHeight - 0.5) * 2
  if (mouseTween) mouseTween.kill()
  mouseTween = gsap.to(cardRef.value, {
    rotationX: -y * 3,
    rotationY: x * 3,
    duration: 1.2,
    ease: 'power2.out',
    overwrite: 'auto'
  })
}

function setupEntranceAnimation() {
  const logo = logoRef.value
  const logoSymbol = logoSymbolRef.value
  const card = cardRef.value
  const footer = footerRef.value

  if (!card) return

  entranceTimeline = gsap.timeline({ defaults: { ease: 'power3.out' } })

  // 1. 背景不动，直接可见

  // 2. Logo 区域淡入下移 + 脉冲
  if (logo) {
    entranceTimeline.fromTo(logo,
      { opacity: 0, y: -30 },
      { opacity: 1, y: 0, duration: 0.8 },
      0.15
    )
  }

  if (logoSymbol) {
    entranceTimeline.fromTo(logoSymbol,
      { scale: 0.6, rotation: -15 },
      { scale: 1, rotation: 0, duration: 0.6, ease: 'back.out(2)' },
      0.2
    )
  }

  // 3. 卡片淡入上移
  entranceTimeline.fromTo(card,
    { opacity: 0, y: 40 },
    { opacity: 1, y: 0, duration: 0.7 },
    0.35
  )

  // 4. 卡内元素交错入场
  const inputGroups = card.querySelectorAll('[data-anim="input"]')
  entranceTimeline.fromTo(inputGroups,
    { opacity: 0, x: -15 },
    { opacity: 1, x: 0, duration: 0.4, stagger: 0.08 },
    0.5
  )

  const button = card.querySelector('[data-anim="button"]')
  if (button) {
    entranceTimeline.fromTo(button,
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.4 },
      0.75
    )
  }

  // 5. Footer
  if (footer) {
    entranceTimeline.fromTo(footer,
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: 0.5 },
      0.85
    )
  }
}

function setupParticles() {
  const container = particleContainerRef.value
  if (!container) return

  for (let i = 0; i < 60; i++) {
    const particle = document.createElement('div')
    const size = Math.random() * 6 + 2
    particle.style.cssText = `
      position: absolute;
      width: ${size}px;
      height: ${size}px;
      border-radius: 50%;
      background: radial-gradient(circle at 30% 30%, rgba(52, 211, 153, 0.6), rgba(45, 212, 191, 0.3));
      left: ${Math.random() * 100}%;
      top: ${Math.random() * 100}%;
      pointer-events: none;
    `
    container.appendChild(particle)

    // 每个粒子独立 GSAP 动画：沿着随机路径浮动
    const xRange = gsap.utils.random(-80, 80)
    const yRange = gsap.utils.random(-80, 80)
    const duration = gsap.utils.random(12, 25)
    const delay = gsap.utils.random(0, 8)

    const tween = gsap.to(particle, {
      x: xRange,
      y: yRange,
      opacity: gsap.utils.random(0.25, 0.65),
      duration,
      delay,
      repeat: -1,
      yoyo: true,
      ease: 'sine.inOut',
      overwrite: false
    })

    particleTweens.push(tween)
  }
}

function setupLogoFloat() {
  const logo = logoRef.value?.querySelector('.logo-icon-wrapper')
  if (!logo) return

  logoFloatTween = gsap.to(logo, {
    y: -8,
    duration: 3,
    repeat: -1,
    yoyo: true,
    ease: 'sine.inOut'
  })
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
  <div class="min-h-screen bg-gradient-to-br from-slate-100 via-emerald-50/30 to-teal-50/30 relative overflow-hidden flex items-center justify-center p-4" :style="{ perspective: '1200px' }">

    <!-- Animated Gradient Orbs -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute rounded-full bg-gradient-to-br from-emerald-400/20 to-emerald-500/6 blur-3xl"
        style="left:15%;top:20%;width:320px;height:320px;animation:orbFloat 7s ease-in-out infinite" />
      <div class="absolute rounded-full bg-gradient-to-br from-teal-400/18 to-teal-500/6 blur-3xl"
        style="left:75%;top:70%;width:360px;height:360px;animation:orbFloat 9s ease-in-out infinite 1.2s" />
      <div class="absolute rounded-full bg-gradient-to-br from-emerald-300/10 to-teal-300/5 blur-3xl"
        style="left:45%;top:45%;width:420px;height:420px;animation:orbFloat 11s ease-in-out infinite 0.6s" />
      <div class="absolute rounded-full bg-gradient-to-br from-cyan-400/12 to-emerald-500/5 blur-3xl"
        style="left:65%;top:20%;width:240px;height:240px;animation:orbFloat 6s ease-in-out infinite 2s" />
    </div>

    <!-- GSAP Particles Container -->
    <div ref="particleContainerRef" class="absolute inset-0 overflow-hidden pointer-events-none" />

    <div class="w-full max-w-md relative z-10">
      <!-- Logo & Title -->
      <div ref="logoRef" class="text-center mb-10" style="opacity:0;">
        <div class="relative inline-block group cursor-pointer">
          <div class="absolute -inset-6 bg-gradient-to-r from-emerald-400 via-teal-300 to-emerald-400 rounded-3xl blur-2xl opacity-25 group-hover:opacity-45 transition-all duration-700" style="animation:pulseGlow 3s ease-in-out infinite"></div>
          <div class="absolute -inset-3 bg-gradient-to-r from-emerald-500 to-teal-500 rounded-2xl blur-lg opacity-30 group-hover:opacity-50 transition-all duration-500" style="animation:pulseGlow 2.5s ease-in-out infinite 0.5s"></div>
          <div ref="logoSymbolRef"
            class="logo-icon-wrapper relative inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-emerald-600 via-emerald-500 to-teal-600 rounded-2xl shadow-2xl group-hover:scale-110 group-hover:rotate-6 transition-all duration-500"
          >
            <Sparkles :size="40" class="text-white" style="animation:pulseIcon 2s ease-in-out infinite" />
            <div class="absolute inset-0 rounded-2xl bg-gradient-to-tr from-white/20 to-transparent"></div>
          </div>
        </div>
        <h1 class="text-4xl font-bold text-gray-900 mb-3 mt-6 tracking-tight">欢迎回来</h1>
        <p class="text-gray-500 text-base">登录到智能 RAG 知识库系统</p>
        <div class="flex items-center justify-center gap-2 mt-4">
          <Shield :size="14" class="text-emerald-500" />
          <span class="text-xs font-medium text-emerald-600 tracking-wide uppercase">安全加密连接</span>
        </div>
      </div>

      <!-- Login Card -->
      <div ref="cardRef" class="relative bg-white/70 backdrop-blur-2xl rounded-3xl shadow-2xl p-10 space-y-6 border border-white/60 card-glow" style="opacity:0;">
        <div class="absolute inset-0 rounded-3xl bg-gradient-to-b from-emerald-500/8 via-transparent to-teal-500/8 pointer-events-none" />

        <!-- Error Message -->
        <Transition name="error-shake">
          <div v-if="error" class="relative bg-red-50/90 backdrop-blur border border-red-200/80 rounded-2xl p-4 flex items-start gap-3">
            <div class="flex-shrink-0 w-9 h-9 bg-red-100 rounded-xl flex items-center justify-center">
              <AlertCircle :size="18" class="text-red-500" />
            </div>
            <p class="text-sm text-red-700 font-medium pt-1.5">{{ error }}</p>
          </div>
        </Transition>

        <!-- Username Input -->
        <div data-anim="input" class="space-y-2 input-group">
          <label class="text-sm font-semibold text-gray-700 flex items-center gap-2.5">
            <div class="w-9 h-9 rounded-xl flex items-center justify-center bg-slate-100 transition-all duration-300 group-focus-within:bg-gradient-to-br group-focus-within:from-emerald-50 group-focus-within:to-teal-50 group-focus-within:scale-110 group-focus-within:shadow-sm group-hover:bg-slate-200 group-[.input-group]:group-focus-within:[&>*]:text-emerald-600">
              <User :size="16" class="text-slate-500 transition-colors duration-300 group-focus-within:text-emerald-600" />
            </div>
            用户名 <span class="text-xs text-gray-400 font-normal">（可选）</span>
          </label>
          <div class="relative">
            <input
              v-model="username" type="text" placeholder="请输入用户名"
              class="w-full px-5 py-3.5 bg-white/80 border-2 rounded-2xl text-slate-900 placeholder-slate-400 outline-none text-base transition-all duration-300 border-slate-200 hover:border-slate-300 focus:border-emerald-400 focus:shadow-lg focus:shadow-emerald-500/10 focus:ring-4 focus:ring-emerald-100/60"
              @keydown.enter="handleLogin"
            />
          </div>
        </div>

        <!-- Email Input -->
        <div data-anim="input" class="space-y-2 input-group">
          <label class="text-sm font-semibold text-gray-700 flex items-center gap-2.5">
            <div class="w-9 h-9 rounded-xl flex items-center justify-center bg-slate-100 transition-all duration-300">
              <Mail :size="16" class="text-slate-500 transition-colors duration-300 group-focus-within:text-emerald-600" />
            </div>
            邮箱地址 <span class="text-xs text-gray-400 font-normal">（可选）</span>
          </label>
          <div class="relative">
            <input
              v-model="email" type="email" placeholder="your@email.com"
              class="w-full px-5 py-3.5 bg-white/80 border-2 rounded-2xl text-slate-900 placeholder-slate-400 outline-none text-base transition-all duration-300 border-slate-200 hover:border-slate-300 focus:border-emerald-400 focus:shadow-lg focus:shadow-emerald-500/10 focus:ring-4 focus:ring-emerald-100/60"
              @keydown.enter="handleLogin"
            />
          </div>
          <p class="text-xs text-slate-400 pl-1">请填写用户名或邮箱地址至少一项</p>
        </div>

        <!-- Password Input -->
        <div data-anim="input" class="space-y-2 input-group">
          <label class="text-sm font-semibold text-gray-700 flex items-center gap-2.5">
            <div class="w-9 h-9 rounded-xl flex items-center justify-center bg-slate-100 transition-all duration-300">
              <Lock :size="16" class="text-slate-500 transition-colors duration-300 group-focus-within:text-emerald-600" />
            </div>
            密码
          </label>
          <div class="relative">
            <input
              v-model="password" :type="showPassword ? 'text' : 'password'" placeholder="••••••••"
              class="w-full px-5 py-3.5 bg-white/80 border-2 rounded-2xl text-slate-900 placeholder-slate-400 outline-none text-base transition-all duration-300 pr-12 border-slate-200 hover:border-slate-300 focus:border-emerald-400 focus:shadow-lg focus:shadow-emerald-500/10 focus:ring-4 focus:ring-emerald-100/60"
              @keydown.enter="handleLogin"
            />
            <button
              type="button" @click="showPassword = !showPassword"
              class="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-lg hover:bg-slate-100 transition-all text-slate-400 hover:text-slate-600"
            >
              <Eye v-if="!showPassword" :size="18" />
              <EyeOff v-else :size="18" />
            </button>
          </div>
        </div>

        <!-- Login Button -->
        <div data-anim="button">
          <button
            @click="handleLogin" :disabled="isLoading"
            class="relative w-full py-3.5 bg-gradient-to-r from-emerald-600 via-emerald-500 to-teal-600 text-white font-semibold rounded-2xl focus:ring-4 focus:ring-emerald-200/60 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-2xl transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center gap-3 text-base overflow-hidden group/btn"
          >
            <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/15 to-transparent -translate-x-full group-hover/btn:translate-x-full transition-transform duration-700 pointer-events-none"></div>
            <div class="absolute inset-0 rounded-2xl bg-gradient-to-r from-emerald-400/20 to-teal-400/20 opacity-0 group-hover/btn:opacity-100 transition-opacity blur-sm pointer-events-none"></div>

            <span v-if="isLoading" class="relative flex items-center gap-3">
              <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              登录中...
            </span>
            <span v-else class="relative flex items-center gap-3">
              登录 <ArrowRight :size="18" class="group-hover/btn:translate-x-1 transition-transform duration-200" />
            </span>
          </button>
        </div>

        <!-- Register Link -->
        <div class="text-center pt-4 border-t border-slate-100/80">
          <p class="text-gray-500 text-sm">
            还没有账号？
            <router-link to="/register" class="text-emerald-600 hover:text-emerald-700 font-semibold transition-all hover:underline underline-offset-4 inline-flex items-center gap-1">
              立即注册 <ArrowRight :size="14" />
            </router-link>
          </p>
        </div>

        <!-- Decorative Elements -->
        <div class="absolute -bottom-8 -right-8 w-32 h-32 bg-gradient-to-br from-emerald-200/25 to-teal-200/25 rounded-full blur-3xl" style="animation:pulseGlow 4s ease-in-out infinite"></div>
        <div class="absolute -top-8 -left-8 w-28 h-28 bg-gradient-to-br from-teal-200/25 to-emerald-200/25 rounded-full blur-3xl" style="animation:pulseGlow 3s ease-in-out infinite 1s"></div>
      </div>

      <!-- Footer -->
      <div ref="footerRef" class="text-center mt-8 space-y-2" style="opacity:0;">
        <p class="text-sm text-gray-500 font-medium">&copy; 2026 RAG Terminal &middot; 安全可靠的知识库系统</p>
        <div class="flex items-center justify-center gap-4 text-xs text-gray-400">
          <span class="flex items-center gap-1"><Shield :size="12" class="text-emerald-500" /> SSL 加密</span>
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
/* Card animated border glow */
.card-glow::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: 1.5rem;
  background: conic-gradient(
    from 0deg,
    transparent,
    rgba(16, 185, 129, 0.08),
    transparent,
    rgba(20, 184, 166, 0.08),
    transparent
  );
  animation: borderRotate 6s linear infinite;
  pointer-events: none;
  mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  padding: 1px;
}

@keyframes borderRotate {
  to { transform: rotate(360deg); }
}

@keyframes orbFloat {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.5; }
  33% { transform: translate(-40%, -60%) scale(1.15); opacity: 0.75; }
  66% { transform: translate(-60%, -40%) scale(0.9); opacity: 0.4; }
}

@keyframes pulseGlow {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 0.45; }
}

@keyframes pulseIcon {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.85; transform: scale(1.05); }
}

.input-icon-bg.active {
  background: linear-gradient(135deg, #ecfdf5, #f0fdfa) !important;
  transform: scale(1.1);
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.15);
}

.input-icon-bg.active .input-icon {
  color: #059669 !important;
}

.error-shake-enter-active {
  animation: shakeIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.error-shake-leave-active {
  animation: fadeOut 0.2s ease-out;
}

@keyframes shakeIn {
  0% { opacity: 0; transform: translateX(-10px); }
  25% { transform: translateX(6px); }
  50% { transform: translateX(-4px); }
  75% { transform: translateX(2px); }
  100% { opacity: 1; transform: translateX(0); }
}

@keyframes fadeOut {
  from { opacity: 1; }
  to { opacity: 0; }
}
</style>
