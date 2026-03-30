"""
LangGraph 监控模块

集成 LangSmith 进行调试和监控
"""

import os
import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from functools import wraps
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class LangSmithMonitor:
    """
    LangSmith 监控器
    
    功能：
    - 追踪每个节点的执行时间和输入输出
    - 记录 token 消耗
    - 可视化工作流执行过程
    - 性能分析
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        project_name: str = "default",
        endpoint: Optional[str] = None,
        enabled: bool = True
    ):
        """
        初始化 LangSmith 监控器
        
        Args:
            api_key: LangSmith API Key（从环境变量 LANGCHAIN_API_KEY 获取）
            project_name: 项目名称
            endpoint: LangSmith 端点（可选，自定义部署）
            enabled: 是否启用
        """
        self.api_key = api_key or os.getenv("LANGCHAIN_API_KEY")
        self.project_name = project_name
        self.endpoint = endpoint or os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
        self.enabled = enabled and bool(self.api_key)
        
        self._traces: List[Dict[str, Any]] = []
        self._current_trace: Optional[Dict[str, Any]] = None
        
        if self.enabled:
            logger.info(f"[LangSmith] 监控已启用 | 项目: {project_name}")
            self._setup_client()
        else:
            logger.warning("[LangSmith] 未配置 API Key，监控已禁用")
    
    def _setup_client(self):
        """设置 LangSmith 客户端"""
        try:
            from langsmith import Client
            self.client = Client(
                api_url=self.endpoint,
                api_key=self.api_key
            )
        except ImportError:
            logger.warning("[LangSmith] langsmith 未安装，监控功能不可用")
            self.enabled = False
        except Exception as e:
            logger.error(f"[LangSmith] 客户端初始化失败: {e}")
            self.enabled = False
    
    @asynccontextmanager
    async def trace(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        追踪上下文管理器
        
        用法：
        async with monitor.trace("intent_node"):
            # 执行代码
        """
        if not self.enabled:
            yield None
            return
        
        trace_data = {
            "name": name,
            "start_time": datetime.now(),
            "metadata": metadata or {},
            "events": []
        }
        
        try:
            self._current_trace = trace_data
            logger.debug(f"[LangSmith] 开始追踪: {name}")
            yield trace_data
        finally:
            trace_data["end_time"] = datetime.now()
            trace_data["duration_ms"] = (
                trace_data["end_time"] - trace_data["start_time"]
            ).total_seconds() * 1000
            
            if self._current_trace == trace_data:
                self._current_trace = None
            
            self._traces.append(trace_data)
            logger.debug(f"[LangSmith] 追踪完成: {name} ({trace_data['duration_ms']:.0f}ms)")
    
    def log_event(self, event_type: str, data: Any, metadata: Optional[Dict] = None):
        """记录事件"""
        if not self.enabled or not self._current_trace:
            return
        
        self._current_trace["events"].append({
            "type": event_type,
            "data": data,
            "metadata": metadata or {},
            "timestamp": datetime.now()
        })
    
    def log_node_start(self, node_name: str, inputs: Dict[str, Any]):
        """记录节点开始"""
        self.log_event("node_start", {"node": node_name, "inputs": inputs})
    
    def log_node_end(self, node_name: str, outputs: Dict[str, Any]):
        """记录节点结束"""
        self.log_event("node_end", {"node": node_name, "outputs": outputs})
    
    def log_token_usage(self, prompt_tokens: int, completion_tokens: int, total_tokens: int):
        """记录 Token 使用"""
        self.log_event(
            "token_usage",
            {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            }
        )
    
    def log_error(self, error: Exception, context: Optional[Dict] = None):
        """记录错误"""
        self.log_event(
            "error",
            {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context or {}
            }
        )
    
    async def flush(self):
        """刷新追踪数据到 LangSmith"""
        if not self.enabled:
            return
        
        try:
            for trace in self._traces:
                await self._upload_trace(trace)
            self._traces.clear()
            logger.debug("[LangSmith] 追踪数据已上传")
        except Exception as e:
            logger.error(f"[LangSmith] 上传失败: {e}")
    
    async def _upload_trace(self, trace: Dict[str, Any]):
        """上传单个追踪"""
        if not hasattr(self, "client"):
            return
        
        try:
            run_id = self.client.create_run(
                name=trace["name"],
                run_type="chain",
                project_name=self.project_name,
                inputs=trace["metadata"].get("inputs", {}),
                outputs=trace["metadata"].get("outputs", {}),
                start_time=trace["start_time"],
                end_time=trace.get("end_time"),
                error=trace.get("error"),
                tags=trace["metadata"].get("tags", [])
            )
            
            for event in trace.get("events", []):
                self.client.create_feedback(
                    run_id=run_id.id,
                    key=f"event_{event['type']}",
                    score=1.0,
                    comment=str(event)
                )
            
            logger.debug(f"[LangSmith] 上传追踪: {trace['name']} -> {run_id.id}")
        except Exception as e:
            logger.error(f"[LangSmith] 追踪上传失败: {e}")
    
    def get_traces_summary(self) -> Dict[str, Any]:
        """获取追踪摘要"""
        total_traces = len(self._traces)
        total_duration = sum(t.get("duration_ms", 0) for t in self._traces)
        
        node_stats: Dict[str, Dict] = {}
        for trace in self._traces:
            name = trace["name"]
            if name not in node_stats:
                node_stats[name] = {
                    "count": 0,
                    "total_duration_ms": 0,
                    "avg_duration_ms": 0
                }
            
            node_stats[name]["count"] += 1
            node_stats[name]["total_duration_ms"] += trace.get("duration_ms", 0)
        
        for stats in node_stats.values():
            if stats["count"] > 0:
                stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["count"]
        
        return {
            "total_traces": total_traces,
            "total_duration_ms": total_duration,
            "node_stats": node_stats
        }


_langsmith_monitor: Optional[LangSmithMonitor] = None


def setup_langsmith(
    api_key: Optional[str] = None,
    project_name: str = "multi-agent-system",
    enabled: bool = True
) -> LangSmithMonitor:
    """
    设置 LangSmith 监控
    
    Args:
        api_key: API Key
        project_name: 项目名称
        enabled: 是否启用
        
    Returns:
        LangSmithMonitor 实例
    """
    global _langsmith_monitor
    
    _langsmith_monitor = LangSmithMonitor(
        api_key=api_key,
        project_name=project_name,
        enabled=enabled
    )
    
    return _langsmith_monitor


def get_langsmith_monitor() -> Optional[LangSmithMonitor]:
    """获取 LangSmith 监控器"""
    global _langsmith_monitor
    
    if _langsmith_monitor is None:
        api_key = os.getenv("LANGCHAIN_API_KEY")
        if api_key:
            _langsmith_monitor = setup_langsmith(api_key=api_key)
    
    return _langsmith_monitor


def traced(trace_name: str = None):
    """
    追踪装饰器
    
    用法：
    @traced("my_function")
    async def my_function():
        ...
    """
    def decorator(func: Callable):
        name = trace_name or func.__name__
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            monitor = get_langsmith_monitor()
            
            if monitor and monitor.enabled:
                async with monitor.trace(name):
                    return await func(*args, **kwargs)
            else:
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class NodeTracer:
    """
    节点追踪器
    
    用于追踪 LangGraph 节点的执行
    """
    
    def __init__(self, monitor: Optional[LangSmithMonitor] = None):
        self.monitor = monitor or get_langsmith_monitor()
    
    def wrap_node(self, node_func: Callable, node_name: str) -> Callable:
        """
        包装节点函数
        
        Args:
            node_func: 原始节点函数
            node_name: 节点名称
            
        Returns:
            包装后的节点函数
        """
        @wraps(node_func)
        async def wrapped(state: Dict[str, Any]) -> Dict[str, Any]:
            if not self.monitor or not self.monitor.enabled:
                return await node_func(state)
            
            async with self.monitor.trace(node_name, {"state_keys": list(state.keys())}):
                self.monitor.log_node_start(node_name, {"state_snapshot": str(state)[:500]})
                
                try:
                    result = await node_func(state)
                    self.monitor.log_node_end(node_name, {"result_keys": list(result.keys())})
                    return result
                except Exception as e:
                    self.monitor.log_error(e, {"node": node_name})
                    raise
        
        return wrapped
    
    def create_traced_builder(self, builder) -> Any:
        """
        为工作流构建器创建追踪版本
        
        Args:
            builder: MultiAgentWorkflowBuilder 实例
            
        Returns:
            追踪版本的工作流构建器
        """
        if not self.monitor or not self.monitor.enabled:
            return builder
        
        original_add_node = builder.graph.add_node if hasattr(builder, 'graph') and builder.graph else None
        
        def traced_add_node(name: str, node_func: Callable):
            traced_func = self.wrap_node(node_func, name)
            if original_add_node:
                original_add_node(name, traced_func)
            else:
                builder.graph.add_node(name, traced_func)
        
        if hasattr(builder, 'graph') and builder.graph:
            builder.graph.add_node = traced_add_node
        
        return builder
