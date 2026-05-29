<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { BarChart, RefreshCw, TrendingUp, Sparkles, Activity, AlertCircle } from 'lucide-vue-next'
import { multimodalApi } from '@/api/multimodal'
import { useMultimodalStore } from '@/stores/multimodal'
import type { UsageLog, UsageSummary } from '@/api/multimodal'

const store = useMultimodalStore()

const days = ref<number>(7)
const summary = ref<UsageSummary | null>(null)

const logs = ref<UsageLog[]>([])
const logsTotal = ref(0)
const logsPage = ref(1)
const logsPageSize = ref(20)
const logsContentTypeFilter = ref<string>('')
const logsLoading = ref(false)

const summaryLoading = ref(false)
const statsLoading = ref(false)

const contentTypes = ['table', 'chart', 'image']

const totalCallsAllTime = computed(() => store.usageStats?.total_calls ?? 0)
const dailyUsed = computed(() => store.usageStats?.daily_used ?? 0)
const dailyLimit = computed(() => store.usageStats?.daily_limit ?? 0)
const dailyRemaining = computed(() => store.usageStats?.daily_remaining ?? 0)
const successRate = computed(() => summary.value?.success_rate ?? '—')

onMounted(async () => {
  await Promise.all([refreshStats(), loadSummary(), loadLogs()])
})

async function refreshStats() {
  statsLoading.value = true
  try {
    await store.loadUsageStats()
  } catch (e: any) {
    console.warn('loadUsageStats failed:', e)
  } finally {
    statsLoading.value = false
  }
}

async function loadSummary() {
  summaryLoading.value = true
  try {
    summary.value = await multimodalApi.getUsageSummary(days.value)
  } catch (e: any) {
    console.warn('loadSummary failed:', e)
  } finally {
    summaryLoading.value = false
  }
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const res = await multimodalApi.getUsageLogs({
      limit: logsPageSize.value,
      offset: (logsPage.value - 1) * logsPageSize.value,
      content_type: logsContentTypeFilter.value || undefined,
    })
    logs.value = res.logs
    logsTotal.value = res.total
  } catch (e: any) {
    console.warn('loadLogs failed:', e)
  } finally {
    logsLoading.value = false
  }
}

function onDaysChange() {
  loadSummary()
}

function onLogsPageChange(page: number) {
  logsPage.value = page
  loadLogs()
}

function onContentTypeFilterChange() {
  logsPage.value = 1
  loadLogs()
}

async function refreshAll() {
  await Promise.all([refreshStats(), loadSummary(), loadLogs()])
  ElMessage.success('已刷新')
}

function modeColor(mode: string) {
  if (mode === 'ai_enhanced') return 'warning'
  if (mode === 'rule_based') return 'success'
  return 'info'
}
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <BarChart :size="24" class="text-emerald-600" />
          多模态用量统计
        </h1>
        <p class="text-sm text-gray-500 mt-1">查看 AI 调用消耗、成功率、按内容类型/模式分布</p>
      </div>
      <el-button :icon="RefreshCw" @click="refreshAll" :loading="statsLoading">刷新</el-button>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <el-card shadow="never" class="!border-emerald-200 bg-emerald-50/30">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <Activity :size="20" class="text-emerald-600" />
          </div>
          <div>
            <div class="text-xs text-gray-500">今日已用</div>
            <div class="text-2xl font-bold text-gray-900">{{ dailyUsed }}</div>
          </div>
        </div>
      </el-card>
      <el-card shadow="never" class="!border-blue-200 bg-blue-50/30">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
            <Sparkles :size="20" class="text-blue-600" />
          </div>
          <div>
            <div class="text-xs text-gray-500">今日剩余</div>
            <div class="text-2xl font-bold text-gray-900">
              {{ dailyRemaining < 0 ? '∞' : dailyRemaining }}
            </div>
          </div>
        </div>
      </el-card>
      <el-card shadow="never" class="!border-amber-200 bg-amber-50/30">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
            <TrendingUp :size="20" class="text-amber-600" />
          </div>
          <div>
            <div class="text-xs text-gray-500">每日上限</div>
            <div class="text-2xl font-bold text-gray-900">
              {{ dailyLimit === 0 ? '∞' : dailyLimit }}
            </div>
          </div>
        </div>
      </el-card>
      <el-card shadow="never" class="!border-purple-200 bg-purple-50/30">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
            <BarChart :size="20" class="text-purple-600" />
          </div>
          <div>
            <div class="text-xs text-gray-500">累计调用</div>
            <div class="text-2xl font-bold text-gray-900">{{ totalCallsAllTime.toLocaleString() }}</div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- Summary section -->
    <el-card shadow="never" class="mb-6">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="text-base font-medium text-gray-900">用量汇总</div>
          <el-radio-group v-model="days" size="small" @change="onDaysChange">
            <el-radio-button :value="7">7 天</el-radio-button>
            <el-radio-button :value="30">30 天</el-radio-button>
            <el-radio-button :value="90">90 天</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <div v-loading="summaryLoading">
        <div v-if="!summary" class="text-center py-8 text-gray-400">
          <AlertCircle :size="40" class="mx-auto mb-2" />
          <div>暂无数据</div>
        </div>
        <template v-else>
          <div class="mb-4 flex items-center gap-6">
            <div>
              <div class="text-xs text-gray-500">{{ summary.period }} 总调用</div>
              <div class="text-3xl font-bold text-gray-900">{{ summary.total_calls.toLocaleString() }}</div>
            </div>
            <div>
              <div class="text-xs text-gray-500">成功率</div>
              <div class="text-3xl font-bold text-emerald-600">{{ successRate }}</div>
            </div>
          </div>

          <!-- 按内容类型 -->
          <div class="mb-6">
            <div class="text-sm font-medium text-gray-700 mb-2">按内容类型分布</div>
            <el-table :data="summary.by_content_type" stripe size="small" empty-text="暂无数据">
              <el-table-column prop="content_type" label="内容类型" />
              <el-table-column prop="count" label="调用次数" />
              <el-table-column prop="total_tokens" label="Token 总数" />
              <el-table-column prop="avg_response_time_ms" label="平均响应 (ms)" />
            </el-table>
          </div>

          <!-- 按模式 -->
          <div>
            <div class="text-sm font-medium text-gray-700 mb-2">按解析模式分布</div>
            <div class="flex gap-3 flex-wrap">
              <div
                v-for="item in summary.by_mode"
                :key="item.mode"
                class="px-4 py-2 rounded-lg border"
                :class="{
                  'border-emerald-300 bg-emerald-50': item.mode === 'rule_based',
                  'border-amber-300 bg-amber-50': item.mode === 'ai_enhanced',
                  'border-gray-300 bg-gray-50': item.mode === 'basic',
                }"
              >
                <div class="text-xs text-gray-500">{{ item.mode }}</div>
                <div class="text-xl font-bold text-gray-900 mt-1">{{ item.count }}</div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </el-card>

    <!-- Logs -->
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="text-base font-medium text-gray-900">使用日志</div>
          <el-select
            v-model="logsContentTypeFilter"
            placeholder="按内容类型筛选"
            clearable
            size="small"
            style="width: 200px"
            @change="onContentTypeFilterChange"
          >
            <el-option v-for="t in contentTypes" :key="t" :value="t" :label="t" />
          </el-select>
        </div>
      </template>

      <el-table :data="logs" v-loading="logsLoading" stripe size="small" empty-text="暂无日志">
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column prop="content_type" label="内容类型" width="100" />
        <el-table-column label="模式" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="modeColor(row.parse_mode)">{{ row.parse_mode }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model_used" label="模型" width="180" />
        <el-table-column prop="total_tokens" label="Tokens" width="100" />
        <el-table-column prop="response_time_ms" label="响应时间 (ms)" width="130" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.success ? 'success' : 'danger'">
              {{ row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" show-overflow-tooltip />
      </el-table>

      <div class="mt-4 flex justify-end">
        <el-pagination
          v-model:current-page="logsPage"
          :page-size="logsPageSize"
          :total="logsTotal"
          layout="prev, pager, next, total"
          background
          @current-change="onLogsPageChange"
        />
      </div>
    </el-card>
  </div>
</template>
