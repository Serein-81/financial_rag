import { ref, watch, onMounted } from 'vue'

type Theme = 'light' | 'dark'

const THEME_KEY = 'rag-theme'

// 全局响应式主题状态
const isDark = ref(false)

// 初始化主题
function initializeTheme() {
  const savedTheme = localStorage.getItem(THEME_KEY) as Theme | null
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches

  if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
    isDark.value = true
  } else {
    isDark.value = false
  }

  applyTheme()
}

// 应用主题到 DOM
function applyTheme() {
  const html = document.documentElement
  if (isDark.value) {
    html.classList.add('dark')
  } else {
    html.classList.remove('dark')
  }
  // 保存到 localStorage
  localStorage.setItem(THEME_KEY, isDark.value ? 'dark' : 'light')
}

// 切换主题
function toggleTheme() {
  isDark.value = !isDark.value
  applyTheme()
}

// 设置主题
function setTheme(theme: Theme) {
  isDark.value = theme === 'dark'
  applyTheme()
}

// 监听系统主题变化
function watchSystemTheme() {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  mediaQuery.addEventListener('change', (e) => {
    // 只在没有手动设置时才跟随系统
    const savedTheme = localStorage.getItem(THEME_KEY)
    if (!savedTheme) {
      isDark.value = e.matches
      applyTheme()
    }
  })
}

export function useTheme() {
  // 组件挂载时初始化
  onMounted(() => {
    initializeTheme()
    watchSystemTheme()
  })

  // 监听主题变化，自动应用
  watch(isDark, applyTheme)

  return {
    isDark,
    toggleTheme,
    setTheme,
  }
}
