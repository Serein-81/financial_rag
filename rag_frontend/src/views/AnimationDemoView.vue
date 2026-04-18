<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { gsap } from 'gsap'
import { toast } from 'vue3-toastify'
import { motion } from 'motion'
import confetti from 'canvas-confetti'
import { useAnimationPreference } from '@/composables/useAnimations'
import { Sparkles, Play, CheckCircle, Star, Heart, PartyPopper, Snowflake } from 'lucide-vue-next'

const { shouldAnimate } = useAnimationPreference()

const showLoading = ref(false)
const revenue = ref(0)
const revenueDisplay = ref('¥0')
const messages = ref<{ id: number; text: string }[]>([])
const testBoxRef = ref<HTMLElement>()
const numberRef = ref<HTMLElement>()
const cardRefs = ref<HTMLElement[]>([])
const emojiRef = ref<HTMLElement>()

const testBoxRef2 = ref<HTMLElement>()
const testBoxRef3 = ref<HTMLElement>()
const testBoxRef4 = ref<HTMLElement>()

// Motion 动画测试
const testMotion = async () => {
  const el = testBoxRef.value
  if (!el) return

  el.animate(
    [
      { transform: 'scale(0) rotate(-180deg)', opacity: 0 },
      { transform: 'scale(1) rotate(0deg)', opacity: 1 }
    ],
    {
      duration: 800,
      easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)'
    }
  )
}

// Motion 卡片动画
const testMotionCards = async () => {
  const cards = document.querySelectorAll('.motion-card')
  
  cards.forEach((card, index) => {
    ;(card as HTMLElement).animate(
      [
        { transform: 'translateY(50px)', opacity: 0 },
        { transform: 'translateY(0)', opacity: 1 }
      ],
      {
        duration: 400,
        delay: index * 100,
        easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)'
      }
    )
  })
}

// 彩纸庆祝效果
const testConfetti = () => {
  const duration = 3000
  const animationEnd = Date.now() + duration
  const colors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff']

  const randomIn = (min: number, max: number) => Math.random() * (max - min) + min

  const frame = () => {
    confetti({
      particleCount: 3,
      angle: 60,
      spread: 55,
      origin: { x: 0 },
      colors: colors
    })
    confetti({
      particleCount: 3,
      angle: 120,
      spread: 55,
      origin: { x: 1 },
      colors: colors
    })

    if (Date.now() < animationEnd) {
      requestAnimationFrame(frame)
    }
  }

  frame()
  
  toast.success('🎉 庆祝成功！', { theme: 'colored' })
}

// Emoji 爆炸动画
const testEmojiExplosion = () => {
  if (!emojiRef.value) return
  
  const emojis = ['🎉', '🎊', '✨', '💫', '🌟', '⭐', '🎈', '🎁']
  const container = document.querySelector('.emoji-container') as HTMLElement
  
  if (!container) return

  for (let i = 0; i < 20; i++) {
    const emoji = document.createElement('span')
    emoji.textContent = emojis[Math.floor(Math.random() * emojis.length)]
    emoji.style.cssText = `
      position: absolute;
      font-size: ${randomIn(20, 40)}px;
      left: ${randomIn(0, 100)}%;
      top: 50%;
      pointer-events: none;
      z-index: 100;
    `
    container.appendChild(emoji)
    
    emoji.animate(
      [
        { transform: 'translateY(0) scale(0)', opacity: 1 },
        { transform: `translateY(-${randomIn(100, 300)}px) scale(1) rotate(${randomIn(-180, 180)}deg)`, opacity: 0 }
      ],
      {
        duration: randomIn(1000, 2000),
        easing: 'cubic-bezier(0, 0.5, 0.5, 1)'
      }
    ).onfinish = () => emoji.remove()
  }
}

// 脉冲动画
const testPulse = () => {
  if (!testBoxRef2.value) return
  
  testBoxRef2.value.animate(
    [
      { transform: 'scale(1)', boxShadow: '0 0 0 0 rgba(59, 130, 246, 0.7)' },
      { transform: 'scale(1.05)', boxShadow: '0 0 0 20px rgba(59, 130, 246, 0)' },
      { transform: 'scale(1)', boxShadow: '0 0 0 0 rgba(59, 130, 246, 0.7)' }
    ],
    {
      duration: 1500,
      iterations: Infinity
    }
  )
}

// 摇摆动画
const testWiggle = () => {
  if (!testBoxRef3.value) return
  
  testBoxRef3.value.animate(
    [
      { transform: 'rotate(0deg)' },
      { transform: 'rotate(-10deg)' },
      { transform: 'rotate(10deg)' },
      { transform: 'rotate(-10deg)' },
      { transform: 'rotate(10deg)' },
      { transform: 'rotate(0deg)' }
    ],
    {
      duration: 500,
      iterations: 3
    }
  )
}

// 渐变动画
const testGradient = () => {
  if (!testBoxRef4.value) return
  
  testBoxRef4.value.animate(
    [
      { backgroundPosition: '0% 50%' },
      { backgroundPosition: '100% 50%' },
      { backgroundPosition: '0% 50%' }
    ],
    {
      duration: 3000,
      iterations: Infinity
    }
  )
}

const testToast = () => {
  toast.success('🎉 这是一个成功提示！', { autoClose: 3000, theme: 'colored' })
  
  setTimeout(() => {
    toast.info('📢 这是一个信息提示', { autoClose: 2000, theme: 'colored' })
  }, 500)
  
  setTimeout(() => {
    toast.warning('⚠️ 这是一个警告提示', { autoClose: 3000, theme: 'colored' })
  }, 1000)
}

const testLoading = async () => {
  showLoading.value = true
  await new Promise(resolve => setTimeout(resolve, 2000))
  showLoading.value = false
  toast.success('✅ 加载完成！', { autoClose: 2000, theme: 'colored' })
}

const testNumberAnimation = () => {
  revenue.value = 1234567
  
  if (numberRef.value) {
    const obj = { value: 0 }
    gsap.to(obj, {
      value: revenue.value,
      duration: 2,
      ease: 'power2.out',
      onUpdate: () => {
        revenueDisplay.value = `¥${Math.round(obj.value).toLocaleString()}`
      }
    })
  }
}

const testMessages = async () => {
  messages.value = []
  const texts = [
    '欢迎使用智能助手！',
    '我可以帮助你处理各种财务和税务问题。',
    '让我为你演示一些炫酷的动画效果。',
    '消息会逐字显示，就像真正在打字一样。',
    '这就是传说中的打字机效果！'
  ]
  
  for (let i = 0; i < texts.length; i++) {
    messages.value.push({ id: Date.now() + i, text: texts[i] })
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 800))
  }
}

const testVirtualScroll = () => {
  messages.value = Array.from({ length: 100 }, (_, i) => ({
    id: i,
    text: `消息 ${i + 1}: 这是一条流畅滚动的测试消息`
  }))
}

onMounted(() => {
  console.log('🎨 增强版 Animation Demo 页面已加载')
  console.log('动画是否启用:', shouldAnimate.value)
})
</script>

<template>
  <div class="animation-demo p-6 max-w-7xl mx-auto">
    <h1 class="text-4xl font-bold mb-2 flex items-center gap-3">
      <Sparkles class="w-10 h-10 text-yellow-500 animate-pulse" />
      <span class="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
        炫酷动画效果演示
      </span>
    </h1>
    
    <p class="text-gray-600 mb-8 text-lg">
      测试各种现代动画效果。动画状态: 
      <span :class="shouldAnimate ? 'text-green-500 font-bold' : 'text-gray-400'">
        {{ shouldAnimate ? '✅ 已启用' : '❌ 已禁用' }}
      </span>
    </p>
    
    <!-- Motion 动画展示 -->
    <div class="bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl p-6 mb-8 text-white">
      <h2 class="text-2xl font-bold mb-4 flex items-center gap-2">
        <Star class="w-6 h-6" />
        Motion 原生动画
      </h2>
      <p class="mb-4 opacity-90">使用浏览器原生 Web Animations API，无需额外库，更轻量</p>
      
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <!-- 弹性缩放 -->
        <div class="text-center">
          <div 
            ref="testBoxRef"
            class="w-20 h-20 mx-auto mb-2 bg-white rounded-xl cursor-pointer"
            @click="testMotion"
          ></div>
          <p class="text-sm">弹性缩放</p>
        </div>
        
        <!-- 脉冲效果 -->
        <div class="text-center">
          <div 
            ref="testBoxRef2"
            class="w-20 h-20 mx-auto mb-2 bg-gradient-to-r from-pink-500 to-rose-500 rounded-xl cursor-pointer"
            @click="testPulse"
          ></div>
          <p class="text-sm">脉冲光晕</p>
        </div>
        
        <!-- 摇摆效果 -->
        <div class="text-center">
          <div 
            ref="testBoxRef3"
            class="w-20 h-20 mx-auto mb-2 bg-gradient-to-r from-amber-500 to-orange-500 rounded-xl cursor-pointer"
            @click="testWiggle"
          ></div>
          <p class="text-sm">摇摆动画</p>
        </div>
        
        <!-- 渐变背景 -->
        <div class="text-center">
          <div 
            ref="testBoxRef4"
            class="w-20 h-20 mx-auto mb-2 bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-500 rounded-xl cursor-pointer bg-[length:200%_200%]"
            @click="testGradient"
          ></div>
          <p class="text-sm">渐变流动</p>
        </div>
      </div>
    </div>

    <!-- 庆祝动画 -->
    <div class="bg-gradient-to-br from-yellow-400 to-orange-500 rounded-2xl p-6 mb-8 text-white relative overflow-hidden emoji-container">
      <h2 class="text-2xl font-bold mb-4 flex items-center gap-2">
        <PartyPopper class="w-6 h-6" />
        庆祝彩纸效果
      </h2>
      <p class="mb-4 opacity-90">任务完成时的炫酷彩纸庆祝动画</p>
      
      <div class="flex gap-4">
        <button @click="testConfetti" class="px-6 py-3 bg-white text-orange-600 rounded-xl font-bold hover:bg-gray-100 transition-all hover:scale-105 shadow-lg">
          🎉 彩纸庆祝
        </button>
        <button @click="testEmojiExplosion" class="px-6 py-3 bg-white text-pink-600 rounded-xl font-bold hover:bg-gray-100 transition-all hover:scale-105 shadow-lg">
          💫 Emoji 爆炸
        </button>
      </div>
    </div>
    
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
      <!-- Toast 通知 -->
      <div class="bg-white rounded-2xl shadow-lg p-6">
        <h2 class="text-xl font-bold mb-4 flex items-center gap-2">
          <Heart class="w-6 h-6 text-pink-500" />
          Toast 通知
        </h2>
        <p class="text-gray-600 mb-4">多种通知类型，随意切换</p>
        <div class="flex flex-wrap gap-3">
          <button @click="() => toast.success('成功！🎉')" class="px-4 py-2 bg-gradient-to-r from-green-400 to-emerald-500 text-white rounded-lg hover:opacity-90 transition-opacity font-medium shadow-md">
            ✅ 成功
          </button>
          <button @click="() => toast.error('出错了！❌')" class="px-4 py-2 bg-gradient-to-r from-red-400 to-rose-500 text-white rounded-lg hover:opacity-90 transition-opacity font-medium shadow-md">
            ❌ 错误
          </button>
          <button @click="() => toast.warning('注意！⚠️')" class="px-4 py-2 bg-gradient-to-r from-yellow-400 to-amber-500 text-white rounded-lg hover:opacity-90 transition-opacity font-medium shadow-md">
            ⚠️ 警告
          </button>
          <button @click="() => toast.info('提示信息 💡')" class="px-4 py-2 bg-gradient-to-r from-blue-400 to-indigo-500 text-white rounded-lg hover:opacity-90 transition-opacity font-medium shadow-md">
            💡 信息
          </button>
        </div>
        <button @click="testToast" class="mt-4 px-4 py-2 bg-gradient-to-r from-purple-400 to-violet-500 text-white rounded-lg hover:opacity-90 transition-opacity font-medium shadow-md">
          批量测试
        </button>
      </div>
      
      <!-- 骨架屏 -->
      <div class="bg-white rounded-2xl shadow-lg p-6">
        <h2 class="text-xl font-bold mb-4 flex items-center gap-2">
          <Sparkles class="w-6 h-6 text-indigo-500" />
          骨架屏加载
        </h2>
        <button @click="testLoading" class="mb-4 px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg hover:opacity-90 transition-opacity font-medium shadow-md">
          模拟加载 2 秒
        </button>
        
        <div v-if="showLoading" class="space-y-3">
          <div class="animate-pulse">
            <div class="h-6 bg-gradient-to-r from-gray-200 to-gray-300 rounded-lg w-1/3 mb-3"></div>
            <div class="h-4 bg-gradient-to-r from-gray-200 to-gray-300 rounded w-full mb-2"></div>
            <div class="h-4 bg-gradient-to-r from-gray-200 to-gray-300 rounded w-5/6 mb-2"></div>
            <div class="h-4 bg-gradient-to-r from-gray-200 to-gray-300 rounded w-4/6"></div>
          </div>
        </div>
        
        <div v-else class="text-green-600 flex items-center gap-2 bg-green-50 p-3 rounded-lg">
          <CheckCircle class="w-5 h-5" />
          <span class="font-medium">加载完成</span>
        </div>
      </div>
      
      <!-- 数字滚动 -->
      <div class="bg-white rounded-2xl shadow-lg p-6">
        <h2 class="text-xl font-bold mb-4 flex items-center gap-2">
          <Star class="w-6 h-6 text-yellow-500" />
          数字滚动动画
        </h2>
        <div 
          ref="numberRef"
          class="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-2"
        >
          {{ revenueDisplay }}
        </div>
        <p class="text-gray-600 mb-4">总收入金额</p>
        <button @click="testNumberAnimation" class="px-4 py-2 bg-gradient-to-r from-teal-500 to-cyan-500 text-white rounded-lg hover:opacity-90 transition-opacity font-medium shadow-md">
          播放数字动画
        </button>
      </div>

      <!-- 卡片入场动画 -->
      <div class="bg-white rounded-2xl shadow-lg p-6">
        <h2 class="text-xl font-bold mb-4 flex items-center gap-2">
          <Snowflake class="w-6 h-6 text-cyan-500" />
          卡片批量动画
        </h2>
        <button @click="testMotionCards" class="mb-4 px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 text-white rounded-lg hover:opacity-90 transition-opacity font-medium shadow-md">
          触发卡片动画
        </button>
        
        <div class="grid grid-cols-3 gap-3">
          <div v-for="i in 9" :key="i" class="motion-card aspect-square bg-gradient-to-br from-gray-100 to-gray-200 rounded-xl flex items-center justify-center text-2xl">
            {{ ['📊', '📈', '📉', '💰', '💎', '🏆', '🎯', '⚡', '🔥'][i-1] }}
          </div>
        </div>
      </div>
    </div>
    
    <!-- 消息打字机效果 -->
    <div class="bg-white rounded-2xl shadow-lg p-6 mb-8">
      <h2 class="text-xl font-bold mb-4 flex items-center gap-2">
        <Sparkles class="w-6 h-6 text-pink-500" />
        消息列表动画
      </h2>
      <button @click="testMessages" class="mb-4 px-4 py-2 bg-gradient-to-r from-pink-500 to-rose-500 text-white rounded-lg hover:opacity-90 transition-opacity font-medium shadow-md flex items-center gap-2">
        <Play class="w-4 h-4" />
        开始演示
      </button>
      
      <div class="space-y-2 min-h-[200px]">
        <div
          v-for="(msg, index) in messages"
          :key="msg.id"
          class="bg-gradient-to-r from-gray-50 to-white border border-gray-200 rounded-xl p-4 message-item"
          :style="{ animationDelay: `${index * 0.1}s` }"
        >
          {{ msg.text }}
        </div>
      </div>
    </div>
    
    <!-- 长列表滚动 -->
    <div class="bg-white rounded-2xl shadow-lg p-6">
      <h2 class="text-xl font-bold mb-4 flex items-center gap-2">
        <Star class="w-6 h-6 text-yellow-500" />
        长列表滚动（100条）
      </h2>
      <button @click="testVirtualScroll" class="mb-4 px-4 py-2 bg-gradient-to-r from-yellow-500 to-orange-500 text-white rounded-lg hover:opacity-90 transition-opacity font-medium shadow-md">
        生成100条消息
      </button>
      
      <div v-if="messages.length > 0" class="h-[300px] overflow-y-auto border-2 border-gray-200 rounded-xl">
        <div
          v-for="item in messages"
          :key="item.id"
          class="border-b border-gray-100 p-4 hover:bg-gradient-to-r hover:from-blue-50 hover:to-indigo-50 transition-all cursor-pointer flex items-center gap-3"
        >
          <span class="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white text-sm font-bold">
            {{ item.id + 1 }}
          </span>
          <span class="flex-1">{{ item.text }}</span>
        </div>
      </div>
      
      <div v-else class="text-gray-400 text-center py-8">
        点击按钮生成消息列表
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.message-item {
  animation: slideInUp 0.4s ease-out forwards;
  opacity: 0;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.motion-card {
  transition: all 0.3s ease;
}

.motion-card:hover {
  transform: translateY(-5px) scale(1.05);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
}
</style>
