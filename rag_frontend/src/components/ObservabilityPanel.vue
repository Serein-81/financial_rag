<template>
  <div class="observability-panel">
    <!-- 标签页 -->
    <div class="flex gap-2 mb-4">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id"
        :class="[
          'px-4 py-2 rounded-lg font-medium transition-all text-sm',
          activeTab === tab.id
            ? 'bg-indigo-500 text-white'
            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
        ]"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 追踪视图 -->
    <div v-if="activeTab === 'traces'" class="space-y-4">
      <div class="flex gap-4 items-center">
        <input
          v-model="traceSearch"
          type="text"
          placeholder="搜索追踪 ID..."
          class="flex-1 px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          @click="loadTraces"
          class="px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600"
        >
          搜索
        </button>
      </div>

      <!-- 追踪列表 -->
      <div class="grid gap-3">
        <div
          v-for="trace in traces"
          :key="trace.trace_id"
          class="bg-white border border-slate-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
          @click="selectedTrace = trace"
        >
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <span class="font-mono text-sm text-indigo-600 font-semibold">
                {{ formatTraceId(trace.trace_id) }}
              </span>
              <el-tag size="small" :type="trace.status === 'ok' ? 'success' : 'danger'">
                {{ trace.status === 'ok' ? '成功' : '失败' }}
              </el-tag>
            </div>
            <span class="text-sm text-slate-500">
              {{ formatDuration(trace.total_duration_ms) }}
            </span>
          </div>
          <div class="flex gap-4 text-sm text-slate-600">
            <span>{{ trace.span_count }} 个 Span</span>
            <span>{{ new Date(trace.spans[0]?.start_time || 0).toLocaleString() }}</span>
          </div>
        </div>
      </div>

      <!-- 追踪详情 -->
      <el-card v-if="selectedTrace" class="mt-4">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-semibold">追踪详情: {{ selectedTrace.trace_id }}</span>
            <el-button size="small" @click="selectedTrace = null">关闭</el-button>
          </div>
        </template>
        
        <div class="space-y-3">
          <div v-for="span in selectedTrace.spans" :key="span.span_id" class="border-l-2 border-indigo-300 pl-4 py-2">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-mono text-xs">{{ span.operation_name }}</span>
              <el-tag size="small" :type="span.status === 'ok' ? 'success' : 'danger'">
                {{ formatDuration(span.duration_ms || 0) }}
              </el-tag>
            </div>
            <div class="text-xs text-slate-500">
              <span>Span ID: {{ formatTraceId(span.span_id) }}</span>
              <span v-if="span.parent_span_id" class="ml-2">Parent: {{ formatTraceId(span.parent_span_id) }}</span>
            </div>
            <div v-if="span.error_message" class="mt-1 text-xs text-red-600">
              {{ span.error_message }}
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 指标视图 -->
    <div v-if="activeTab === 'metrics'" class="space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="bg-white border border-slate-200 rounded-lg p-4">
          <div class="text-sm text-slate-600 mb-1">请求数</div>
          <div class="text-2xl font-bold text-slate-900">
            {{ getMetricValue('counter', 'rag.requests.total') }}
          </div>
        </div>
        <div class="bg-white border border-slate-200 rounded-lg p-4">
          <div class="text-sm text-slate-600 mb-1">Agent 调用数</div>
          <div class="text-2xl font-bold text-slate-900">
            {{ getMetricValue('counter', 'rag.agents.invocations') }}
          </div>
        </div>
        <div class="bg-white border border-slate-200 rounded-lg p-4">
          <div class="text-sm text-slate-600 mb-1">运行中任务</div>
          <div class="text-2xl font-bold text-slate-900">
            {{ getMetricValue('gauge', 'rag.tasks.running') }}
          </div>
        </div>
      </div>

      <!-- 指标列表 -->
      <el-card>
        <template #header>
          <span class="font-semibold">指标详情</span>
        </template>
        <el-tabs>
          <el-tab-pane label="计数器">
            <div class="space-y-2">
              <div v-for="counter in metricsSummary?.counters" :key="counter.name" class="flex justify-between items-center py-2 border-b">
                <div>
                  <div class="font-medium">{{ counter.name }}</div>
                  <div class="text-xs text-slate-500">{{ counter.description }}</div>
                </div>
                <div class="text-lg font-bold">{{ counter.value }}</div>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="直方图">
            <div class="space-y-2">
              <div v-for="histogram in metricsSummary?.histograms" :key="histogram.name" class="py-2 border-b">
                <div class="font-medium">{{ histogram.name }}</div>
                <div class="text-sm text-slate-600">
                  计数: {{ histogram.count }}, 总和: {{ histogram.sum.toFixed(2) }}
                </div>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="仪表">
            <div class="space-y-2">
              <div v-for="gauge in metricsSummary?.gauges" :key="gauge.name" class="flex justify-between items-center py-2 border-b">
                <div>
                  <div class="font-medium">{{ gauge.name }}</div>
                  <div class="text-xs text-slate-500">{{ gauge.description }}</div>
                </div>
                <div class="text-lg font-bold">{{ gauge.value }}</div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </div>

    <!-- 日志视图 -->
    <div v-if="activeTab === 'logs'" class="space-y-4">
      <div class="flex gap-4 items-center">
        <el-select v-model="logLevel" placeholder="日志级别" class="w-32">
          <el-option label="全部" value="" />
          <el-option label="DEBUG" value="DEBUG" />
          <el-option label="INFO" value="INFO" />
          <el-option label="WARNING" value="WARNING" />
          <el-option label="ERROR" value="ERROR" />
        </el-select>
        <button
          @click="loadLogs"
          class="px-4 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600"
        >
          刷新
        </button>
      </div>

      <div class="space-y-2">
        <div
          v-for="log in logs"
          :key="log.timestamp"
          class="bg-white border border-slate-200 rounded-lg p-3 font-mono text-sm"
        >
          <div class="flex items-center gap-2 mb-1">
            <el-tag size="small" :type="getLogLevelColor(log.level)">
              {{ log.level }}
            </el-tag>
            <span class="text-slate-500 text-xs">
              {{ new Date(log.timestamp).toLocaleString() }}
            </span>
            <span v-if="log.trace_id" class="text-indigo-600 text-xs">
              [{{ formatTraceId(log.trace_id) }}]
            </span>
          </div>
          <div class="text-slate-800">{{ log.message }}</div>
        </div>
      </div>
    </div>

    <!-- 健康检查视图 -->
    <div v-if="activeTab === 'health'" class="space-y-4">
      <div v-if="healthReport" class="space-y-3">
        <div class="flex items-center gap-3 mb-4">
          <el-tag :type="getStatusColor(healthReport.overall_status)" size="large">
            {{ healthReport.overall_status === 'healthy' ? '健康' : 
               healthReport.overall_status === 'degraded' ? '降级' : '故障' }}
          </el-tag>
          <span class="text-sm text-slate-500">
            最后更新: {{ new Date(healthReport.timestamp).toLocaleString() }}
          </span>
        </div>

        <div
          v-for="component in healthReport.components"
          :key="component.name"
          class="bg-white border border-slate-200 rounded-lg p-4"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="font-medium">{{ component.name }}</span>
            <el-tag :type="getStatusColor(component.status)" size="small">
              {{ component.status }}
            </el-tag>
          </div>
          <div v-if="component.latency_ms" class="text-sm text-slate-600">
            延迟: {{ component.latency_ms }}ms
          </div>
          <div v-if="component.error_rate" class="text-sm text-slate-600">
            错误率: {{ (component.error_rate * 100).toFixed(2) }}%
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  observabilityApi,
  formatTraceId,
  formatDuration,
  getLogLevelColor,
  getStatusColor,
  type TraceInfo,
  type MetricsSummary,
  type LogEntry,
  type HealthReport
} from '@/api/observability'

const tabs = [
  { id: 'traces', label: '追踪' },
  { id: 'metrics', label: '指标' },
  { id: 'logs', label: '日志' },
  { id: 'health', label: '健康' }
]

const activeTab = ref('traces')
const traceSearch = ref('')
const selectedTrace = ref<TraceInfo | null>(null)
const traces = ref<TraceInfo[]>([])
const metricsSummary = ref<MetricsSummary | null>(null)
const logs = ref<LogEntry[]>([])
const logLevel = ref('')
const healthReport = ref<HealthReport | null>(null)

function getMetricValue(type: 'counter' | 'gauge', name: string): number {
  if (!metricsSummary.value) return 0
  const source = type === 'counter' ? metricsSummary.value.counters : metricsSummary.value.gauges
  return source.find(metric => metric.name === name)?.value || 0
}

async function loadTraces() {
  try {
    const now = new Date()
    const start = new Date(now.getTime() - 24 * 60 * 60 * 1000)
    
    traces.value = await observabilityApi.getTraces({
      start_time: start.toISOString(),
      end_time: now.toISOString(),
      limit: 50
    })
  } catch (error: any) {
    ElMessage.error('加载追踪失败: ' + error.message)
  }
}

async function loadMetrics() {
  try {
    metricsSummary.value = await observabilityApi.getMetrics()
  } catch (error: any) {
    ElMessage.error('加载指标失败: ' + error.message)
  }
}

async function loadLogs() {
  try {
    const params: any = {
      limit: 100
    }
    if (logLevel.value) {
      params.level = logLevel.value
    }
    logs.value = await observabilityApi.getLogs(params)
  } catch (error: any) {
    ElMessage.error('加载日志失败: ' + error.message)
  }
}

async function loadHealth() {
  try {
    healthReport.value = await observabilityApi.getHealth()
  } catch (error: any) {
    ElMessage.error('加载健康状态失败: ' + error.message)
  }
}

onMounted(() => {
  loadTraces()
  loadMetrics()
  loadLogs()
  loadHealth()
})
</script>

<style scoped>
.observability-panel {
  @apply p-4;
}
</style>
