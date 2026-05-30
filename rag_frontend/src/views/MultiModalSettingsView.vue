<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Sparkles, Eye, EyeOff, RefreshCw, Save, RotateCcw, Info } from 'lucide-vue-next'
import { useMultimodalStore } from '@/stores/multimodal'
import type { ParseMode, MultimodalConfigCreate } from '@/api/multimodal'

const store = useMultimodalStore()

// ────────────────── API Key 显示控制 ──────────────────

const showApiKey = ref(false)

// ────────────────── 主表单状态 ──────────────────

const local = ref<MultimodalConfigCreate>({
  enabled: true,
  table_mode: 'rule_based',
  chart_mode: 'rule_based',
  image_mode: 'basic',
  vision_model: 'gpt-4o',
  llm_model: 'gpt-4o-mini',
  use_own_api_key: false,
  user_api_key: '',
  daily_ai_limit: 100,
  enable_cache: true,
  ai_timeout: 30,
  max_concurrent: 3,
})

onMounted(async () => {
  await Promise.all([
    store.loadConfig(),
    store.loadUsageStats(),
    store.loadCostEstimate(),
    store.loadAvailableModels(),
  ])
  syncFromStore()
})

watch(() => store.config, () => syncFromStore())

function syncFromStore() {
  if (!store.config) return
  const c = store.config
  local.value = {
    enabled: c.enabled,
    table_mode: c.modes.table,
    chart_mode: c.modes.chart,
    image_mode: c.modes.image,
    vision_model: c.models.vision,
    llm_model: c.models.llm,
    use_own_api_key: c.use_own_api_key,
    user_api_key: '',
    daily_ai_limit: c.cost_control.daily_limit,
    enable_cache: c.performance.enable_cache,
    ai_timeout: c.performance.ai_timeout,
    max_concurrent: c.performance.max_concurrent,
  }
}

/** 是否已在后端保存过用户自己的 API Key */
const hasUserApiKey = computed(() => store.config?.use_own_api_key && (store.config as any)?.has_user_api_key)

// ────────────────── 计算属性 ──────────────────

// 图片 ai_enhanced 后端未实现，不计入判断
const isAIEnhanced = computed(() =>
  local.value.table_mode === 'ai_enhanced'
  || local.value.chart_mode === 'ai_enhanced'
)

const usagePercent = computed(() => store.usagePercent)

interface ModeOption {
  value: ParseMode
  label: string
  tier: string
  desc: string
}

// 表格 / 图表：三种模式均有后端实现
const tableModeOptions: ModeOption[] = [
  { value: 'basic',       label: '基础提取', tier: '基础', desc: '结构化提取，仅保留原始数据' },
  { value: 'rule_based',  label: '规则增强', tier: '标准', desc: '结构化提取 + 规则统计分析（推荐默认）' },
  { value: 'ai_enhanced', label: 'AI 理解',  tier: '高级', desc: '调用 LLM API 深度摘要与洞察' },
]

const chartModeOptions: ModeOption[] = [
  { value: 'basic',       label: '基础提取', tier: '基础', desc: 'OCR 文字提取' },
  { value: 'rule_based',  label: '规则增强', tier: '标准', desc: 'OCR + 规则检测图表类型与趋势（推荐默认）' },
  { value: 'ai_enhanced', label: 'AI 理解',  tier: '高级', desc: '调用 Vision API 深度理解图表语义' },
]

// 图片：rule_based / ai_enhanced 后端尚未实现，禁用并标注待开发
const imageModeOptions: (ModeOption & { todo?: boolean })[] = [
  { value: 'basic',       label: '基础提取', tier: '基础', desc: 'OCR 文字提取（当前可用）' },
  { value: 'rule_based',  label: '规则增强', tier: '标准', desc: '规则分析',       todo: true },
  { value: 'ai_enhanced', label: 'AI 理解',  tier: '高级', desc: 'Vision 模型识别', todo: true },
]

// ────────────────── 操作 ──────────────────

async function save() {
  // 选择了使用自己的 Key 但未填且未保存过，则警告
  if (local.value.use_own_api_key && !local.value.user_api_key && !hasUserApiKey.value) {
    ElMessage.warning('请填写您的 API Key')
    return
  }

  try {
    const payload: MultimodalConfigCreate = { ...local.value }
    // user_api_key 为空表示不修改已保存的值
    if (!payload.user_api_key) delete payload.user_api_key

    await store.saveConfig(payload)
    ElMessage.success('配置已保存')
    store.refresh().catch(() => {})
  } catch (e: any) {
    ElMessage.error('保存失败：' + (e?.message || '未知错误'))
  }
}

async function reset() {
  try {
    await ElMessageBox.confirm('确定要恢复为默认配置吗？您的自定义配置将被删除。', '提示', {
      confirmButtonText: '确定恢复',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await store.resetConfig()
    ElMessage.success('已恢复默认配置')
    syncFromStore()
  } catch {
    // 用户取消
  }
}

async function refreshStats() {
  await store.loadUsageStats()
  ElMessage.success('用量已刷新')
}
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Sparkles :size="24" class="text-emerald-600" />
          多模态配置
        </h1>
        <p class="text-sm text-gray-500 mt-1">
          配置表格、图表、图片的解析方式。默认全部免费，AI 增强模式按需启用
        </p>
      </div>
      <div class="flex gap-2">
        <el-button :icon="RefreshCw" @click="refreshStats">刷新用量</el-button>
        <el-button :icon="RotateCcw" @click="reset">恢复默认</el-button>
      </div>
    </div>

    <!-- 今日用量 -->
    <div v-if="store.usageStats" class="mb-6 p-4 bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-xl">
      <div class="flex items-center justify-between mb-2">
        <div class="text-sm font-medium text-gray-700">今日 AI 用量</div>
        <div class="text-xs text-gray-500">
          {{ store.usageRemainingText }}
        </div>
      </div>
      <el-progress
        :percentage="usagePercent"
        :stroke-width="8"
        :status="usagePercent > 90 ? 'exception' : usagePercent > 70 ? 'warning' : 'success'"
      />
    </div>

    <!-- Main Settings -->
    <div v-loading="store.loading" class="space-y-4">
      <!-- 启用开关 -->
      <el-card shadow="never">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-base font-medium text-gray-900">启用多模态功能</div>
            <div class="text-sm text-gray-500 mt-0.5">关闭后所有文档只做文本解析</div>
          </div>
          <el-switch v-model="local.enabled" size="large" />
        </div>
      </el-card>

      <!-- 解析模式 -->
      <el-card shadow="never">
        <template #header>
          <div class="text-base font-medium text-gray-900">解析模式</div>
        </template>
        <div class="space-y-5">
          <!-- 表格（三种模式均已实现） -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">📊 表格解析</label>
            <el-radio-group v-model="local.table_mode" class="w-full">
              <el-radio
                v-for="opt in tableModeOptions"
                :key="opt.value"
                :value="opt.value"
                class="!mr-3"
              >
                {{ opt.label }}
                <span class="text-xs ml-1 text-gray-400">({{ opt.tier }})</span>
              </el-radio>
            </el-radio-group>
            <div class="text-xs text-gray-500 mt-1">
              {{ tableModeOptions.find(o => o.value === local.table_mode)?.desc }}
            </div>
          </div>

          <!-- 图表（三种模式均已实现） -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">📈 图表解析</label>
            <el-radio-group v-model="local.chart_mode" class="w-full">
              <el-radio
                v-for="opt in chartModeOptions"
                :key="opt.value"
                :value="opt.value"
                class="!mr-3"
              >
                {{ opt.label }}
                <span class="text-xs ml-1 text-gray-400">({{ opt.tier }})</span>
              </el-radio>
            </el-radio-group>
            <div class="text-xs text-gray-500 mt-1">
              {{ chartModeOptions.find(o => o.value === local.chart_mode)?.desc }}
            </div>
          </div>

          <!-- 图片（rule_based / ai_enhanced 后端未实现，禁用） -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">🖼️ 图片解析</label>
            <div class="flex flex-wrap gap-3">
              <label
                v-for="opt in imageModeOptions"
                :key="opt.value"
                class="flex items-center gap-1.5"
                :class="opt.todo ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'"
              >
                <input
                  type="radio"
                  :value="opt.value"
                  v-model="local.image_mode"
                  :disabled="opt.todo"
                  class="accent-blue-500"
                />
                <span class="text-sm" :class="opt.todo ? 'text-gray-400' : ''">
                  {{ opt.label }}
                  <span class="text-xs text-gray-400">({{ opt.tier }})</span>
                  <el-tag v-if="opt.todo" size="small" type="info" effect="plain" class="ml-1 !text-xs">待开发</el-tag>
                </span>
              </label>
            </div>
            <div class="text-xs text-gray-500 mt-1">
              {{ imageModeOptions.find(o => o.value === local.image_mode)?.desc }}
            </div>
          </div>
        </div>
      </el-card>

      <!-- AI 模型选择（仅 ai_enhanced 模式生效） -->
      <el-card v-if="isAIEnhanced" shadow="never">
        <template #header>
          <div class="text-base font-medium text-gray-900">AI 模型选择</div>
        </template>
        <div class="space-y-4">
          <!-- Vision 模型 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Vision 模型（图表/图片）</label>
            <el-select v-model="local.vision_model" class="w-full" placeholder="选择 Vision 模型">
              <el-option
                v-for="m in store.availableModels?.vision_models || []"
                :key="m.id"
                :value="m.id"
                :label="m.name"
              >
                <span>{{ m.name }}</span>
                <span class="text-xs text-gray-400 ml-2">{{ m.provider }} · 成本{{ m.cost }} · 质量{{ m.quality }}</span>
                <el-tag v-if="m.recommended" size="small" type="success" class="ml-2">推荐</el-tag>
              </el-option>
            </el-select>
          </div>

          <!-- LLM 模型 -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">LLM 模型（表格摘要）</label>
            <el-select v-model="local.llm_model" class="w-full" placeholder="选择 LLM 模型">
              <el-option
                v-for="m in store.availableModels?.llm_models || []"
                :key="m.id"
                :value="m.id"
                :label="m.name"
              >
                <span>{{ m.name }}</span>
                <span class="text-xs text-gray-400 ml-2">{{ m.provider }} · 成本{{ m.cost }} · 质量{{ m.quality }}</span>
                <el-tag v-if="m.recommended" size="small" type="success" class="ml-2">推荐</el-tag>
              </el-option>
            </el-select>
          </div>
        </div>
      </el-card>

      <!-- API Key 配置（始终显示，便于提前配置） -->
      <el-card shadow="never">
        <template #header>
          <div class="flex items-center justify-between">
            <div class="text-base font-medium text-gray-900">API Key 配置</div>
            <el-tag v-if="isAIEnhanced" type="warning" size="small">AI 增强模式已启用</el-tag>
            <el-tag v-else type="info" size="small" effect="plain">选填预配置</el-tag>
          </div>
        </template>
        <div class="space-y-4">
          <div class="flex items-start gap-2 p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
            <Info :size="16" class="mt-0.5 flex-shrink-0" />
            <span>
              各 LLM Provider 的 API Key 在
              <router-link to="/settings/models" class="underline font-medium">模型配置中心</router-link>
              统一管理。此处仅在 AI 增强模式下，允许用户提供自己的 API Key 覆盖平台默认密钥（计入您自己的账单）。
            </span>
          </div>

          <!-- 计费来源选择 -->
          <el-radio-group v-model="local.use_own_api_key">
            <el-radio :value="false">使用平台配置的 API Key</el-radio>
            <el-radio :value="true">使用我自己的 API Key（覆盖平台默认）</el-radio>
          </el-radio-group>

          <!-- 自己的 Key 输入框 -->
          <div v-if="local.use_own_api_key" class="space-y-2">
            <label class="block text-sm font-medium text-gray-700">
              API Key
              <el-tag v-if="isAIEnhanced" size="small" type="danger" class="ml-1">AI 增强模式必填</el-tag>
              <el-tag v-else size="small" type="info" effect="plain" class="ml-1">选填</el-tag>
            </label>
            <el-input
              v-model="local.user_api_key"
              :type="showApiKey ? 'text' : 'password'"
              :placeholder="hasUserApiKey ? '已保存（留空则不修改）' : '填写您的 API Key'"
            >
              <template #suffix>
                <button class="text-gray-400 hover:text-gray-600 p-1" @click="showApiKey = !showApiKey">
                  <component :is="showApiKey ? EyeOff : Eye" :size="14" />
                </button>
              </template>
            </el-input>
            <div class="flex items-start gap-1 text-xs text-gray-500">
              <Info :size="12" class="mt-0.5 flex-shrink-0" />
              <span>加密存储，仅用于 AI 增强模式的 Vision/LLM 调用，不会用于其他用途</span>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 成本控制 -->
      <el-card shadow="never">
        <template #header>
          <div class="text-base font-medium text-gray-900">成本控制</div>
        </template>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              每日 AI 调用上限
              <span class="text-xs text-gray-400 ml-1">(0 = 无限制)</span>
            </label>
            <el-input-number
              v-model="local.daily_ai_limit"
              :min="0"
              :max="100000"
              :step="50"
              class="w-full max-w-xs"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">AI 超时时间（秒）</label>
            <el-input-number v-model="local.ai_timeout" :min="5" :max="300" :step="5" class="w-full max-w-xs" />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">最大并发数</label>
            <el-input-number v-model="local.max_concurrent" :min="1" :max="20" :step="1" class="w-full max-w-xs" />
          </div>

          <div class="flex items-center justify-between pt-2">
            <div>
              <div class="text-sm font-medium text-gray-700">启用缓存</div>
              <div class="text-xs text-gray-500">相同内容的解析结果可复用</div>
            </div>
            <el-switch v-model="local.enable_cache" />
          </div>
        </div>
      </el-card>

      <!-- 成本估算 -->
      <el-card v-if="store.costEstimate" shadow="never" class="bg-amber-50/30">
        <template #header>
          <div class="text-base font-medium text-gray-900">预估成本（每 1000 个文档）</div>
        </template>
        <div class="grid grid-cols-3 gap-4">
          <div class="text-center">
            <div class="text-xs text-gray-500">表格</div>
            <div class="text-lg font-semibold text-gray-800 mt-1">{{ store.costEstimate.cost_per_1k_objects.table }}</div>
          </div>
          <div class="text-center">
            <div class="text-xs text-gray-500">图表</div>
            <div class="text-lg font-semibold text-gray-800 mt-1">{{ store.costEstimate.cost_per_1k_objects.chart }}</div>
          </div>
          <div class="text-center">
            <div class="text-xs text-gray-500">图片</div>
            <div class="text-lg font-semibold text-gray-800 mt-1">{{ store.costEstimate.cost_per_1k_objects.image }}</div>
          </div>
        </div>
        <el-divider />
        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-700">总计</span>
          <span class="text-lg font-bold text-amber-600">{{ store.costEstimate.total_cost_per_1k_docs }}</span>
        </div>
        <div v-if="store.costEstimate.note" class="text-xs text-gray-500 mt-2">
          {{ store.costEstimate.note }}
        </div>
      </el-card>
    </div>

    <!-- Save Button (sticky) -->
    <div class="sticky bottom-0 bg-white border-t border-gray-200 -mx-6 px-6 py-4 mt-6">
      <div class="flex items-center justify-end gap-2">
        <el-button @click="syncFromStore">取消修改</el-button>
        <el-button type="primary" :icon="Save" :loading="store.saving" @click="save">保存配置</el-button>
      </div>
    </div>
  </div>
</template>
