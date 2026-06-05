<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  AlertTriangle,
  RefreshCw,
  Sparkles,
  CheckCircle2,
  Clock,
  XCircle,
  Search,
  Wand2,
  FileX,
  AlertCircle,
} from 'lucide-vue-next'
import { feedbackApi } from '@/api/feedback'
import type { FailureCase, FailureType, FailureStatus, FailureTypeStat } from '@/api/feedback'

const cases = ref<FailureCase[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(12)
const loading = ref(false)

const filterStatus = ref<FailureStatus | ''>('')
const filterType = ref<FailureType | ''>('')

const stats = ref<FailureTypeStat[]>([])
const statsLoading = ref(false)

const batchAnalyzing = ref(false)

// 详情对话框
const detailVisible = ref(false)
const selectedCase = ref<FailureCase | null>(null)

onMounted(async () => {
  await Promise.all([loadList(), loadStats()])
})

async function loadList() {
  loading.value = true
  try {
    const res = await feedbackApi.listFailureCases({
      status: filterStatus.value || undefined,
      failure_type: filterType.value || undefined,
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    })
    // 后端返回键名为 failure_cases（见 feedback.py /failure-cases），兼容旧 cases 键
    cases.value = res.failure_cases ?? (res as any).cases ?? []
    total.value = res.total ?? 0
  } catch (e: any) {
    ElMessage.error('加载失败案例失败：' + (e?.message || ''))
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  statsLoading.value = true
  try {
    const res = await feedbackApi.getFailureTypesStats()
    // 后端返回 {distribution: {类型: 数量}}（见 feedback.py /statistics/failure-types），转为数组；兼容旧 {types: [...]} 形态
    const legacyTypes = (res as any).types
    stats.value = Array.isArray(legacyTypes)
      ? legacyTypes
      : Object.entries(res.distribution ?? {}).map(([type, count]) => ({ type, count: Number(count) || 0 }))
  } catch (e: any) {
    console.warn('loadStats failed:', e)
  } finally {
    statsLoading.value = false
  }
}

const totalCases = computed(() =>
  stats.value.reduce((sum, s) => sum + (s.count || 0), 0)
)

const failureTypeLabels: Record<string, { label: string; color: string; icon: any }> = {
  retrieval: { label: '检索失败', color: 'bg-red-100 text-red-700', icon: Search },
  generation: { label: '生成错误', color: 'bg-amber-100 text-amber-700', icon: Wand2 },
  hallucination: { label: '幻觉', color: 'bg-purple-100 text-purple-700', icon: AlertCircle },
  incomplete: { label: '不完整', color: 'bg-blue-100 text-blue-700', icon: FileX },
  irrelevant: { label: '不相关', color: 'bg-orange-100 text-orange-700', icon: XCircle },
  other: { label: '其他', color: 'bg-gray-100 text-gray-700', icon: AlertTriangle },
}

function typeMeta(t: string) {
  return failureTypeLabels[t] || failureTypeLabels.other
}

const statusLabels: Record<string, { label: string; type: 'warning' | 'info' | 'success' | 'danger' }> = {
  pending: { label: '待分析', type: 'warning' },
  analyzing: { label: '分析中', type: 'info' },
  fixed: { label: '已修复', type: 'success' },
  ignored: { label: '已忽略', type: 'danger' },
}

function statusMeta(s: string) {
  return statusLabels[s] || { label: s, type: 'info' as const }
}

function onFilterChange() {
  page.value = 1
  loadList()
}

function onPageChange(p: number) {
  page.value = p
  loadList()
}

function openDetail(c: FailureCase) {
  selectedCase.value = c
  detailVisible.value = true
}

async function changeStatus(c: FailureCase, status: FailureStatus) {
  try {
    await feedbackApi.updateFailureCase(c.id, { status })
    ElMessage.success('状态已更新')
    await loadList()
    if (selectedCase.value?.id === c.id) {
      selectedCase.value.status = status
    }
  } catch (e: any) {
    ElMessage.error('状态更新失败：' + (e?.message || ''))
  }
}

async function batchAnalyze() {
  try {
    await ElMessageBox.confirm(
      '将对最近的所有未分析负面反馈批量执行根因分析，可能耗时较长。是否继续？',
      '批量分析',
      { confirmButtonText: '开始分析', cancelButtonText: '取消', type: 'info' }
    )
    batchAnalyzing.value = true
    // 后端目前没有专门的"批量分析"端点，前端通过遍历待处理反馈逐个调用创建失败案例
    // P2 阶段可让后端增加 POST /failure-cases/batch-analyze 端点
    ElMessage.warning('批量分析需要后端 POST /failure-cases/batch-analyze 端点支持，请联系后端')
  } catch (e: any) {
    if (e === 'cancel' || e?.message === 'cancel') return
  } finally {
    batchAnalyzing.value = false
  }
}

async function refreshAll() {
  await Promise.all([loadList(), loadStats()])
  ElMessage.success('已刷新')
}

function formatTime(s?: string | null): string {
  if (!s) return '—'
  try {
    return new Date(s).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return s
  }
}

function getSuggestionTexts(c: FailureCase): string[] {
  if (!c.fix_suggestions || !Array.isArray(c.fix_suggestions)) return []
  return c.fix_suggestions.map((s: any) =>
    typeof s === 'string' ? s : (s?.description || s?.text || JSON.stringify(s))
  )
}
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <AlertTriangle :size="24" class="text-amber-600" />
          失败案例分析
        </h1>
        <p class="text-sm text-gray-500 mt-1">基于用户负面反馈的失败案例，自动根因分析与修复建议</p>
      </div>
      <div class="flex gap-2">
        <el-button :icon="Sparkles" type="warning" :loading="batchAnalyzing" @click="batchAnalyze">
          批量分析
        </el-button>
        <el-button :icon="RefreshCw" @click="refreshAll" :loading="loading">刷新</el-button>
      </div>
    </div>

    <!-- 失败类型分布 -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="text-base font-medium text-gray-900">失败类型分布</div>
          <div class="text-xs text-gray-500">共 {{ totalCases }} 个</div>
        </div>
      </template>
      <div v-loading="statsLoading">
        <div v-if="stats.length === 0" class="text-center py-8 text-gray-400">
          <AlertCircle :size="40" class="mx-auto mb-2" />
          <div>暂无失败案例数据</div>
        </div>
        <div v-else class="grid grid-cols-2 lg:grid-cols-6 gap-3">
          <div
            v-for="s in stats"
            :key="s.type"
            class="rounded-lg p-3 border"
            :class="typeMeta(s.type as string).color"
          >
            <div class="flex items-center justify-between mb-2">
              <component :is="typeMeta(s.type as string).icon" :size="16" />
              <div class="text-xl font-bold">{{ s.count }}</div>
            </div>
            <div class="text-xs font-medium">{{ typeMeta(s.type as string).label }}</div>
            <div class="text-[10px] mt-1 opacity-75">
              {{ totalCases > 0 ? Math.round((s.count / totalCases) * 100) : 0 }}%
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- Filter Bar -->
    <el-card shadow="never" class="mb-4">
      <div class="flex items-center gap-3 flex-wrap">
        <el-select
          v-model="filterStatus"
          placeholder="状态"
          clearable
          size="default"
          style="width: 160px"
          @change="onFilterChange"
        >
          <el-option value="" label="全部状态" />
          <el-option value="pending" label="待分析" />
          <el-option value="analyzing" label="分析中" />
          <el-option value="fixed" label="已修复" />
          <el-option value="ignored" label="已忽略" />
        </el-select>

        <el-select
          v-model="filterType"
          placeholder="失败类型"
          clearable
          size="default"
          style="width: 160px"
          @change="onFilterChange"
        >
          <el-option value="" label="全部类型" />
          <el-option v-for="t in Object.keys(failureTypeLabels)" :key="t"
                     :value="t" :label="typeMeta(t).label" />
        </el-select>
      </div>
    </el-card>

    <!-- Card Grid -->
    <div v-loading="loading">
      <div v-if="cases.length === 0 && !loading" class="text-center py-16 text-gray-400">
        <FileX :size="48" class="mx-auto mb-2" />
        <div>暂无失败案例</div>
        <div class="text-xs mt-1">用户提交负面反馈后，可在「反馈管理」中创建为失败案例</div>
      </div>

      <div v-else class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        <el-card
          v-for="c in cases"
          :key="c.id"
          shadow="hover"
          class="cursor-pointer hover:!border-amber-300 transition-all"
          @click="openDetail(c)"
        >
          <!-- Header -->
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <component :is="typeMeta(c.failure_type).icon" :size="14" />
              <span :class="['px-2 py-0.5 rounded text-xs font-medium', typeMeta(c.failure_type).color]">
                {{ typeMeta(c.failure_type).label }}
              </span>
            </div>
            <el-tag size="small" :type="statusMeta(c.status).type">
              {{ statusMeta(c.status).label }}
            </el-tag>
          </div>

          <!-- 置信度 -->
          <div v-if="c.confidence_score !== null && c.confidence_score !== undefined" class="mb-2">
            <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>分析置信度</span>
              <span class="font-medium">{{ c.confidence_score }}%</span>
            </div>
            <el-progress
              :percentage="c.confidence_score"
              :stroke-width="4"
              :show-text="false"
              :status="c.confidence_score >= 80 ? 'success' : c.confidence_score >= 50 ? 'warning' : 'exception'"
            />
          </div>

          <!-- 修复建议 -->
          <div v-if="getSuggestionTexts(c).length > 0" class="mb-3">
            <div class="text-xs text-gray-400 mb-1">修复建议</div>
            <ul class="text-xs text-gray-700 space-y-0.5 pl-4 list-disc">
              <li v-for="(s, idx) in getSuggestionTexts(c).slice(0, 2)" :key="idx" class="line-clamp-2">{{ s }}</li>
              <li v-if="getSuggestionTexts(c).length > 2" class="text-gray-400 list-none">
                还有 {{ getSuggestionTexts(c).length - 2 }} 条建议...
              </li>
            </ul>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-between pt-2 border-t border-gray-100">
            <span class="text-[10px] text-gray-400">{{ formatTime(c.created_at) }}</span>
            <div class="flex gap-1" @click.stop>
              <el-button
                v-if="c.status !== 'fixed'"
                size="small"
                type="success"
                text
                :icon="CheckCircle2"
                @click="changeStatus(c, 'fixed')"
              >
                已修复
              </el-button>
              <el-button
                v-if="c.status !== 'ignored'"
                size="small"
                text
                :icon="XCircle"
                @click="changeStatus(c, 'ignored')"
              >
                忽略
              </el-button>
            </div>
          </div>
        </el-card>
      </div>

      <div class="mt-6 flex justify-end">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next, total"
          background
          @current-change="onPageChange"
        />
      </div>
    </div>

    <!-- Detail Drawer -->
    <el-drawer
      v-model="detailVisible"
      title="失败案例详情"
      direction="rtl"
      size="640px"
    >
      <div v-if="selectedCase" class="space-y-4">
        <!-- 基本 -->
        <el-card shadow="never">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <component :is="typeMeta(selectedCase.failure_type).icon" :size="16" />
              <span :class="['px-2 py-1 rounded text-xs font-medium', typeMeta(selectedCase.failure_type).color]">
                {{ typeMeta(selectedCase.failure_type).label }}
              </span>
            </div>
            <el-tag size="small" :type="statusMeta(selectedCase.status).type">
              {{ statusMeta(selectedCase.status).label }}
            </el-tag>
          </div>
          <div class="text-xs text-gray-500 space-y-1">
            <div><span class="text-gray-400">案例 ID:</span> {{ selectedCase.id }}</div>
            <div><span class="text-gray-400">反馈 ID:</span> {{ selectedCase.feedback_id }}</div>
            <div><span class="text-gray-400">创建时间:</span> {{ formatTime(selectedCase.created_at) }}</div>
            <div v-if="selectedCase.updated_at">
              <span class="text-gray-400">更新时间:</span> {{ formatTime(selectedCase.updated_at) }}
            </div>
            <div v-if="selectedCase.confidence_score !== null">
              <span class="text-gray-400">置信度:</span> {{ selectedCase.confidence_score }}%
            </div>
          </div>
        </el-card>

        <!-- 根因分析 -->
        <el-card v-if="selectedCase.analysis" shadow="never">
          <template #header>
            <div class="text-sm font-medium">根因分析</div>
          </template>
          <pre class="text-xs text-gray-700 bg-gray-50 rounded p-3 overflow-x-auto max-h-72">{{ JSON.stringify(selectedCase.analysis, null, 2) }}</pre>
        </el-card>

        <!-- 修复建议 -->
        <el-card v-if="getSuggestionTexts(selectedCase).length > 0" shadow="never">
          <template #header>
            <div class="text-sm font-medium">修复建议</div>
          </template>
          <ul class="space-y-2 text-sm text-gray-700">
            <li
              v-for="(s, idx) in getSuggestionTexts(selectedCase)"
              :key="idx"
              class="flex gap-2"
            >
              <span class="text-amber-500 mt-0.5">▸</span>
              <span class="flex-1">{{ s }}</span>
            </li>
          </ul>
        </el-card>

        <!-- 状态变更 -->
        <el-card shadow="never">
          <template #header>
            <div class="text-sm font-medium">状态变更</div>
          </template>
          <div class="flex flex-wrap gap-2">
            <el-button
              v-for="s in ['pending', 'analyzing', 'fixed', 'ignored']"
              :key="s"
              size="small"
              :type="selectedCase.status === s ? statusMeta(s).type : 'default'"
              :disabled="selectedCase.status === s"
              @click="changeStatus(selectedCase, s as FailureStatus)"
            >
              {{ statusMeta(s).label }}
            </el-button>
          </div>
          <div class="text-xs text-gray-500 mt-2">
            <Clock :size="12" class="inline mr-1" />
            状态变更会自动更新数据库时间戳
          </div>
        </el-card>
      </div>
    </el-drawer>
  </div>
</template>
