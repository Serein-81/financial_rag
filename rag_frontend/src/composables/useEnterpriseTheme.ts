import { ref, watch, onMounted, getCurrentInstance } from 'vue'
import { tenantSettingsApi } from '@/api/tenant-settings'

const ENTERPRISE_THEME_KEY = 'rag-enterprise-theme'

interface EnterpriseTheme {
  primary_color: string
  secondary_color: string
}

const enterpriseTheme = ref<EnterpriseTheme>({
  primary_color: '#1890ff',
  secondary_color: '#ffffff'
})

const isInitialized = ref(false)

function applyEnterpriseTheme(theme: EnterpriseTheme) {
  const root = document.documentElement
  root.style.setProperty('--enterprise-primary-color', theme.primary_color)
  root.style.setProperty('--enterprise-secondary-color', theme.secondary_color)
  localStorage.setItem(ENTERPRISE_THEME_KEY, JSON.stringify(theme))
}

async function loadEnterpriseTheme() {
  try {
    console.log('[EnterpriseTheme] Loading theme from API')
    const response = await tenantSettingsApi.getMySettings()
    const settings = response?.data || response
    console.log('[EnterpriseTheme] Settings received:', settings)
    
    if (settings) {
      const primaryColor = settings.primary_color || '#1890ff'
      const secondaryColor = settings.secondary_color || '#ffffff'
      
      enterpriseTheme.value = {
        primary_color: primaryColor,
        secondary_color: secondaryColor
      }
      console.log('[EnterpriseTheme] Applying theme:', enterpriseTheme.value)
      applyEnterpriseTheme(enterpriseTheme.value)
      isInitialized.value = true
    }
  } catch (error) {
    console.warn('[EnterpriseTheme] Failed to load theme from API:', error)
    const saved = localStorage.getItem(ENTERPRISE_THEME_KEY)
    if (saved) {
      try {
        enterpriseTheme.value = JSON.parse(saved)
        console.log('[EnterpriseTheme] Loaded from localStorage:', enterpriseTheme.value)
        applyEnterpriseTheme(enterpriseTheme.value)
        isInitialized.value = true
        return
      } catch {
        console.warn('[EnterpriseTheme] Failed to parse localStorage theme')
      }
    }
    console.log('[EnterpriseTheme] Using default theme')
    applyEnterpriseTheme(enterpriseTheme.value)
    isInitialized.value = true
  }
}

export function useEnterpriseTheme() {
  const instance = getCurrentInstance()
  
  if (instance && !isInitialized.value) {
    onMounted(() => {
      loadEnterpriseTheme()
    })
  } else if (isInitialized.value) {
    applyEnterpriseTheme(enterpriseTheme.value)
  } else {
    loadEnterpriseTheme()
  }

  watch(enterpriseTheme, (newTheme) => {
    applyEnterpriseTheme(newTheme)
  }, { deep: true })

  return {
    enterpriseTheme,
    loadEnterpriseTheme,
    applyEnterpriseTheme
  }
}
