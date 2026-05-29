// 多模态配置 Pinia Store
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { multimodalApi } from '@/api/multimodal'
import type {
  MultimodalConfig,
  MultimodalConfigCreate,
  MultimodalConfigUpdate,
  UsageStats,
  CostEstimate,
  AvailableModels,
  UsageSummary,
} from '@/api/multimodal'

export const useMultimodalStore = defineStore('multimodal', () => {
  const config = ref<MultimodalConfig | null>(null)
  const usageStats = ref<UsageStats | null>(null)
  const costEstimate = ref<CostEstimate | null>(null)
  const availableModels = ref<AvailableModels | null>(null)
  const usageSummary = ref<UsageSummary | null>(null)

  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)

  // Computed
  const isAIEnhanced = computed(() => {
    if (!config.value) return false
    const m = config.value.modes
    return m.table === 'ai_enhanced' || m.chart === 'ai_enhanced' || m.image === 'ai_enhanced'
  })

  const usagePercent = computed(() => {
    if (!usageStats.value) return 0
    if (!usageStats.value.daily_limit) return 0
    return Math.round((usageStats.value.daily_used / usageStats.value.daily_limit) * 100)
  })

  const usageRemainingText = computed(() => {
    if (!usageStats.value) return '加载中...'
    if (usageStats.value.daily_remaining < 0) return '无限制'
    return `${usageStats.value.daily_used} / ${usageStats.value.daily_limit}`
  })

  // Actions
  async function loadConfig() {
    loading.value = true
    error.value = null
    try {
      config.value = await multimodalApi.getConfig()
    } catch (e: any) {
      error.value = e?.message || '加载配置失败'
    } finally {
      loading.value = false
    }
  }

  async function saveConfig(payload: MultimodalConfigCreate) {
    saving.value = true
    error.value = null
    try {
      const res = await multimodalApi.upsertConfig(payload)
      config.value = res.config
      // 保存后刷新成本估算
      await loadCostEstimate()
      return res
    } catch (e: any) {
      error.value = e?.message || '保存配置失败'
      throw e
    } finally {
      saving.value = false
    }
  }

  async function patchConfig(payload: MultimodalConfigUpdate) {
    saving.value = true
    error.value = null
    try {
      const res = await multimodalApi.patchConfig(payload)
      config.value = res.config
      await loadCostEstimate()
      return res
    } catch (e: any) {
      error.value = e?.message || '更新配置失败'
      throw e
    } finally {
      saving.value = false
    }
  }

  async function resetConfig() {
    saving.value = true
    error.value = null
    try {
      await multimodalApi.deleteConfig()
      await loadConfig()
    } catch (e: any) {
      error.value = e?.message || '恢复默认失败'
      throw e
    } finally {
      saving.value = false
    }
  }

  async function loadUsageStats() {
    try {
      usageStats.value = await multimodalApi.getUsageStats()
    } catch (e: any) {
      console.warn('loadUsageStats failed:', e)
    }
  }

  async function loadCostEstimate() {
    try {
      costEstimate.value = await multimodalApi.getCostEstimate()
    } catch (e: any) {
      console.warn('loadCostEstimate failed:', e)
    }
  }

  async function loadAvailableModels() {
    if (availableModels.value) return  // 缓存
    try {
      availableModels.value = await multimodalApi.getAvailableModels()
    } catch (e: any) {
      console.warn('loadAvailableModels failed:', e)
    }
  }

  async function loadUsageSummary(days = 7) {
    try {
      usageSummary.value = await multimodalApi.getUsageSummary(days)
    } catch (e: any) {
      console.warn('loadUsageSummary failed:', e)
    }
  }

  async function refresh() {
    await Promise.all([loadConfig(), loadUsageStats(), loadCostEstimate()])
  }

  return {
    config,
    usageStats,
    costEstimate,
    availableModels,
    usageSummary,
    loading,
    saving,
    error,
    isAIEnhanced,
    usagePercent,
    usageRemainingText,
    loadConfig,
    saveConfig,
    patchConfig,
    resetConfig,
    loadUsageStats,
    loadCostEstimate,
    loadAvailableModels,
    loadUsageSummary,
    refresh,
  }
})
