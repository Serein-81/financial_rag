/**
 * 可观测性 API
 * 
 * 提供追踪、指标和日志的统一接口
 */

import { request, get } from '@/utils/request'

// ==================== 追踪相关类型 ====================

export interface SpanContext {
  trace_id: string
  span_id: string
  parent_span_id?: string
  operation_name: string
  service_name: string
  start_time: string
  end_time?: string
  duration_ms?: number
  status: 'ok' | 'error'
  error_message?: string
  attributes: Record<string, any>
  events: TraceEvent[]
  tags: Record<string, string>
}

export interface TraceEvent {
  name: string
  timestamp: string
  attributes?: Record<string, any>
}

export interface TraceInfo {
  trace_id: string
  spans: SpanContext[]
  total_duration_ms: number
  span_count: number
}

// ==================== 指标相关类型 ====================

export interface MetricPoint {
  timestamp: string
  value: number
  labels: Record<string, string>
}

export interface CounterMetric {
  name: string
  description: string
  value: number
  labels: Record<string, string>
}

export interface HistogramMetric {
  name: string
  description: string
  count: number
  sum: number
  buckets: Record<string, number>
  labels: Record<string, string>
}

export interface GaugeMetric {
  name: string
  description: string
  value: number
  labels: Record<string, string>
}

export interface MetricsSummary {
  counters: CounterMetric[]
  histograms: HistogramMetric[]
  gauges: GaugeMetric[]
  total_metrics: number
}

// ==================== 日志相关类型 ====================

export interface LogEntry {
  timestamp: string
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
  message: string
  trace_id?: string
  span_id?: string
  service: string
  attributes: Record<string, any>
}

export interface LogQuery {
  start_time?: string
  end_time?: string
  level?: string
  trace_id?: string
  service?: string
  limit?: number
}

// ==================== 系统健康相关 ====================

export interface ComponentHealth {
  name: string
  status: 'healthy' | 'degraded' | 'down'
  latency_ms?: number
  error_rate?: number
  metadata?: Record<string, any>
}

export interface HealthReport {
  overall_status: 'healthy' | 'degraded' | 'down'
  components: ComponentHealth[]
  timestamp: string
}

// ==================== API 函数 ====================

export const observabilityApi = {
  // 追踪相关
  async getTraces(params: {
    start_time?: string
    end_time?: string
    service_name?: string
    operation_name?: string
    limit?: number
  }): Promise<TraceInfo[]> {
    return get('/observability/traces', { params })
  },

  async getTrace(trace_id: string): Promise<TraceInfo> {
    return get(`/observability/traces/${trace_id}`)
  },

  async getSpan(trace_id: string, span_id: string): Promise<SpanContext> {
    return get(`/observability/traces/${trace_id}/spans/${span_id}`)
  },

  // 指标相关
  async getMetrics(params?: {
    service_name?: string
    metric_type?: string
  }): Promise<MetricsSummary> {
    return get('/observability/metrics', { params })
  },

  async getPrometheusMetrics(): Promise<string> {
    return get('/observability/metrics/prometheus', {
      responseType: 'text'
    })
  },

  // 日志相关
  async getLogs(params: LogQuery): Promise<LogEntry[]> {
    return get('/observability/logs', { params })
  },

  async searchLogs(query: string, params?: Partial<LogQuery>): Promise<LogEntry[]> {
    return get('/observability/logs/search', {
      params: { query, ...params }
    })
  },

  // 健康检查
  async getHealth(): Promise<HealthReport> {
    return get('/observability/health')
  },

  // 统计信息
  async getStatistics(): Promise<{
    total_traces: number
    total_spans: number
    total_metrics: number
    total_logs: number
    active_traces: number
  }> {
    return get('/observability/statistics')
  }
}

// 便捷函数
export function formatTraceId(trace_id: string): string {
  return trace_id.length > 16 ? `${trace_id.slice(0, 8)}...${trace_id.slice(-8)}` : trace_id
}

export function formatDuration(duration_ms: number): string {
  if (duration_ms < 1) {
    return `${(duration_ms * 1000).toFixed(2)}µs`
  } else if (duration_ms < 1000) {
    return `${duration_ms.toFixed(2)}ms`
  } else if (duration_ms < 60000) {
    return `${(duration_ms / 1000).toFixed(2)}s`
  } else {
    return `${(duration_ms / 60000).toFixed(2)}m`
  }
}

export function getLogLevelColor(level: string): string {
  const colors: Record<string, string> = {
    DEBUG: 'gray',
    INFO: 'blue',
    WARNING: 'yellow',
    ERROR: 'red'
  }
  return colors[level] || 'gray'
}

export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    healthy: 'green',
    degraded: 'yellow',
    down: 'red',
    ok: 'green',
    error: 'red'
  }
  return colors[status] || 'gray'
}
