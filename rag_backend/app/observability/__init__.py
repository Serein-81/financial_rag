"""
可观测性模块

基于 OpenTelemetry 的全链路追踪系统

功能：
1. 分布式追踪
2. 指标收集
3. 日志关联
4. 性能监控

作者：Senior Python Backend Architect
版本：1.0.0
"""

from app.observability.tracing import (
    TracingConfig,
    TracingManager,
    get_tracer,
    trace_async,
    trace_sync,
    SpanContext,
)
from app.observability.metrics import (
    MetricsCollector,
    MetricsConfig,
    Counter,
    Histogram,
    Gauge,
)
from app.observability.logger import (
    ObservabilityLogger,
    LogConfig,
    StructuredLogger,
)

__all__ = [
    # 追踪
    "TracingConfig",
    "TracingManager",
    "get_tracer",
    "trace_async",
    "trace_sync",
    "SpanContext",
    # 指标
    "MetricsCollector",
    "MetricsConfig",
    "Counter",
    "Histogram",
    "Gauge",
    # 日志
    "ObservabilityLogger",
    "LogConfig",
    "StructuredLogger",
]
