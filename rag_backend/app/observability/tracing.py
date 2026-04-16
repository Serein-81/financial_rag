"""
分布式追踪系统

基于 OpenTelemetry 的全链路追踪实现

功能：
1. 自动注入 trace_id 到所有日志和状态
2. 支持异步任务的追踪
3. 多 span 管理
4. 自定义属性和事件
"""

import logging
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from contextvars import ContextVar
from functools import wraps

logger = logging.getLogger(__name__)

# 上下文变量
_current_span: ContextVar[Optional["SpanContext"]] = ContextVar("current_span", default=None)


@dataclass
class SpanContext:
    """
    Span 上下文
    
    用于追踪单个操作的执行
    """
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    operation_name: str = ""
    service_name: str = "rag-backend"
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    status: str = "ok"  # ok | error
    error_message: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.trace_id:
            import uuid
            self.trace_id = uuid.uuid4().hex[:16]
        if not self.span_id:
            import uuid
            self.span_id = uuid.uuid4().hex[:8]
    
    def set_attribute(self, key: str, value: Any):
        """设置属性"""
        self.attributes[key] = value
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """添加事件"""
        self.events.append({
            "name": name,
            "timestamp": datetime.now().isoformat(),
            "attributes": attributes or {}
        })
    
    def set_status(self, status: str, error_message: Optional[str] = None):
        """设置状态"""
        self.status = status
        self.error_message = error_message
    
    def finish(self):
        """结束 span"""
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "service_name": self.service_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error_message": self.error_message,
            "attributes": self.attributes,
            "events": self.events,
            "tags": self.tags
        }


@dataclass
class TracingConfig:
    """追踪配置"""
    service_name: str = "rag-backend"
    service_version: str = "1.0.0"
    environment: str = "development"
    enabled: bool = True
    export_endpoint: Optional[str] = None  # OTLP endpoint
    sample_rate: float = 1.0  # 采样率 0-1
    max_span_attributes: int = 100
    include_stack_trace: bool = True
    propagate_trace_context: bool = True


class TracingManager:
    """
    追踪管理器
    
    管理全链路追踪的生命周期
    """
    
    def __init__(self, config: Optional[TracingConfig] = None):
        """
        初始化追踪管理器
        
        Args:
            config: 追踪配置
        """
        self.config = config or TracingConfig()
        self._spans: List[SpanContext] = []
        self._active_spans: Dict[str, SpanContext] = {}
        self._enabled = self.config.enabled
        self._trace_count = 0
        self._error_count = 0
        
        logger.info(
            f"[Tracing] 初始化: service={self.config.service_name}, "
            f"enabled={self._enabled}"
        )
    
    def start_span(
        self,
        operation_name: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> SpanContext:
        """
        开始一个 span
        
        Args:
            operation_name: 操作名称
            parent_span_id: 父 span ID
            attributes: 属性
            tags: 标签
            
        Returns:
            SpanContext 对象
        """
        if not self._enabled:
            # 返回一个空的 span
            return SpanContext(
                trace_id="",
                span_id="",
                operation_name=operation_name
            )
        
        # 获取当前 span
        current = _current_span.get()
        if current and not parent_span_id:
            parent_span_id = current.span_id
        
        span = SpanContext(
            trace_id=current.trace_id if current else "",
            span_id="",  # 将被 __post_init__ 生成
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            service_name=self.config.service_name,
            attributes=attributes or {},
            tags=tags or {}
        )
        
        self._spans.append(span)
        self._active_spans[span.span_id] = span
        self._trace_count += 1
        
        # 设置为当前 span
        token = _current_span.set(span)
        span._token = token
        
        logger.debug(
            f"[Tracing] 开始 span: {operation_name}, "
            f"trace_id={span.trace_id}, span_id={span.span_id}"
        )
        
        return span
    
    def end_span(self, span: SpanContext, status: str = "ok", error: Optional[str] = None):
        """
        结束 span
        
        Args:
            span: SpanContext 对象
            status: 状态
            error: 错误信息
        """
        if not self._enabled:
            return
        
        span.set_status(status, error)
        span.finish()
        
        if span.span_id in self._active_spans:
            del self._active_spans[span.span_id]
        
        if status == "error":
            self._error_count += 1
        
        logger.debug(
            f"[Tracing] 结束 span: {span.operation_name}, "
            f"duration={span.duration_ms:.2f}ms, status={status}"
        )
    
    def get_current_span(self) -> Optional[SpanContext]:
        """获取当前 span"""
        return _current_span.get()
    
    def get_trace_id(self) -> Optional[str]:
        """获取当前 trace ID"""
        span = self.get_current_span()
        return span.trace_id if span else None
    
    def add_span_attribute(self, key: str, value: Any):
        """为当前 span 添加属性"""
        span = self.get_current_span()
        if span:
            span.set_attribute(key, value)
    
    def add_span_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """为当前 span 添加事件"""
        span = self.get_current_span()
        if span:
            span.add_event(name, attributes)
    
    def record_exception(self, exception: Exception, attributes: Optional[Dict[str, Any]] = None):
        """
        记录异常
        
        Args:
            exception: 异常对象
            attributes: 其他属性
        """
        span = self.get_current_span()
        if span:
            span.set_status("error", str(exception))
            span.add_event("exception", {
                "type": type(exception).__name__,
                "message": str(exception),
                **(attributes or {})
            })
    
    def get_spans(self, trace_id: Optional[str] = None) -> List[SpanContext]:
        """
        获取 span 列表
        
        Args:
            trace_id: 按 trace ID 过滤
            
        Returns:
            SpanContext 列表
        """
        if trace_id:
            return [s for s in self._spans if s.trace_id == trace_id]
        return self._spans
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "enabled": self._enabled,
            "total_traces": self._trace_count,
            "active_spans": len(self._active_spans),
            "total_spans": len(self._spans),
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._trace_count, 1)
        }
    
    def clear(self):
        """清空所有 span"""
        self._spans.clear()
        self._active_spans.clear()
        self._trace_count = 0
        self._error_count = 0


# 全局追踪管理器
_tracing_manager: Optional[TracingManager] = None


def init_tracing(config: Optional[TracingConfig] = None) -> TracingManager:
    """
    初始化全局追踪管理器
    
    Args:
        config: 追踪配置
        
    Returns:
        TracingManager 实例
    """
    global _tracing_manager
    _tracing_manager = TracingManager(config)
    return _tracing_manager


def get_tracer() -> TracingManager:
    """
    获取全局追踪管理器
    
    Returns:
        TracingManager 实例
    """
    global _tracing_manager
    if _tracing_manager is None:
        _tracing_manager = TracingManager()
    return _tracing_manager


def trace_async(
    operation_name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
) -> Callable:
    """
    异步追踪装饰器
    
    Args:
        operation_name: 操作名称（默认使用函数名）
        attributes: 初始属性
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            name = operation_name or f"{func.__module__}.{func.__name__}"
            
            span = tracer.start_span(name, attributes=attributes)
            
            try:
                result = await func(*args, **kwargs)
                tracer.end_span(span, "ok")
                return result
            except Exception as e:
                tracer.record_exception(e)
                tracer.end_span(span, "error", str(e))
                raise
        
        return wrapper
    
    return decorator


def trace_sync(
    operation_name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
) -> Callable:
    """
    同步追踪装饰器
    
    Args:
        operation_name: 操作名称（默认使用函数名）
        attributes: 初始属性
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            name = operation_name or f"{func.__module__}.{func.__name__}"
            
            span = tracer.start_span(name, attributes=attributes)
            
            try:
                result = func(*args, **kwargs)
                tracer.end_span(span, "ok")
                return result
            except Exception as e:
                tracer.record_exception(e)
                tracer.end_span(span, "error", str(e))
                raise
        
        return wrapper
    
    return decorator


class SpanContextManager:
    """
    Span 上下文管理器
    
    用于 with 语句管理 span 生命周期
    """
    
    def __init__(
        self,
        operation_name: str,
        tracer: Optional[TracingManager] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        初始化
        
        Args:
            operation_name: 操作名称
            tracer: 追踪管理器
            attributes: 初始属性
        """
        self.operation_name = operation_name
        self.tracer = tracer or get_tracer()
        self.attributes = attributes
        self.span: Optional[SpanContext] = None
    
    def __enter__(self) -> SpanContext:
        """进入上下文"""
        self.span = self.tracer.start_span(
            self.operation_name,
            attributes=self.attributes
        )
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        if exc_type:
            self.tracer.record_exception(exc_val)
            self.tracer.end_span(self.span, "error", str(exc_val))
        else:
            self.tracer.end_span(self.span, "ok")
        
        return False


# 便捷函数
def create_span(
    operation_name: str,
    attributes: Optional[Dict[str, Any]] = None
) -> SpanContextManager:
    """
    创建 span 上下文管理器
    
    Args:
        operation_name: 操作名称
        attributes: 初始属性
        
    Returns:
        SpanContextManager 实例
    """
    return SpanContextManager(operation_name, attributes=attributes)
