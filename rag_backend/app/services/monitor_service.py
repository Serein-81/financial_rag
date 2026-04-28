# app/services/monitor_service.py

"""
自定义监控追踪系统

技术亮点：
1. 完整的调用链追踪（Trace）
2. 性能指标监控（耗时、Token 使用量）
3. 工具调用记录（参数、返回值、状态）
4. 错误异常捕获
5. 结构化日志输出
6. 支持异步上下文管理
7. 支持多维度统计分析
"""

import time
import uuid
import json
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum
from contextlib import asynccontextmanager
from functools import wraps
import traceback
import logging


logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型枚举"""
    AGENT_START = "agent_start"           # Agent 开始执行
    AGENT_END = "agent_end"               # Agent 执行结束
    TOOL_CALL_START = "tool_call_start"   # 工具调用开始
    TOOL_CALL_END = "tool_call_end"       # 工具调用结束
    LLM_START = "llm_start"               # LLM 调用开始
    LLM_END = "llm_end"                   # LLM 调用结束
    ERROR = "error"                       # 错误事件
    CUSTOM = "custom"                     # 自定义事件


class CallStatus(Enum):
    """调用状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class MonitorEvent:
    """
    监控事件
    
    记录单次操作的完整信息
    """
    
    def __init__(
        self,
        event_type: EventType,
        event_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None
    ):
        self.event_id = event_id or str(uuid.uuid4())
        self.trace_id = trace_id or str(uuid.uuid4())
        self.parent_id = parent_id
        self.event_type = event_type
        
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration: Optional[float] = None
        
        self.status: Optional[CallStatus] = None
        self.metadata: Dict[str, Any] = {}
        self.error: Optional[str] = None
        
    def end(self, status: CallStatus = CallStatus.SUCCESS, **metadata):
        """结束事件并记录元数据"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.status = status
        self.metadata.update(metadata)
    
    def set_error(self, error: Exception):
        """记录错误信息"""
        self.status = CallStatus.FAILED
        self.error = f"{type(error).__name__}: {str(error)}"
        self.metadata["traceback"] = traceback.format_exc()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "event_type": self.event_type.value,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration": round(self.duration, 3) if self.duration else None,
            "status": self.status.value if self.status else None,
            "metadata": self.metadata,
            "error": self.error
        }


class MonitorService:
    """
    监控服务
    
    设计理念：
    - 轻量级：不影响主业务性能
    - 结构化：所有数据都有明确的结构
    - 可扩展：支持自定义事件和元数据
    - 易分析：提供统计分析功能
    
    使用示例：
        monitor = MonitorService()
        
        # 方式1：使用上下文管理器
        async with monitor.trace_agent("user_123", "查询天气") as trace:
            # 执行 Agent 逻辑
            async with trace.trace_tool("get_weather", city="北京") as tool_trace:
                result = await get_weather("北京")
                tool_trace.set_result(result)
        
        # 方式2：使用装饰器
        @monitor.trace_function("tool_call")
        async def my_tool(city: str):
            return await get_weather(city)
    """
    
    def __init__(self, enable_console_log: bool = True):
        """
        初始化监控服务
        
        Args:
            enable_console_log: 是否启用控制台日志输出
        """
        self.enable_console_log = enable_console_log
        self.events: List[MonitorEvent] = []
        self.active_traces: Dict[str, MonitorEvent] = {}
        
        logger.debug("MonitorService initialized")
    
    @asynccontextmanager
    async def trace_agent(
        self, 
        user_id: str, 
        query: str,
        kb_id: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """
        追踪 Agent 执行
        
        Args:
            user_id: 用户ID
            query: 用户问题
            kb_id: 知识库ID
            session_id: 会话ID
        
        示例：
            async with monitor.trace_agent("user_123", "查询天气") as trace:
                result = await agent.chat(query)
                trace.set_result(result)
        """
        event = MonitorEvent(
            event_type=EventType.AGENT_START,
            trace_id=str(uuid.uuid4())
        )
        
        event.metadata.update({
            "user_id": user_id,
            "query": query,
            "kb_id": kb_id,
            "session_id": session_id,
            "query_length": len(query)
        })
        
        self.active_traces[event.trace_id] = event
        
        if self.enable_console_log:
            print(f"[START] [Monitor] Agent 开始 | Trace: {event.trace_id[:8]} | 用户: {user_id} | 问题: {query[:50]}")
        
        try:
            # 创建追踪上下文对象
            trace_context = AgentTraceContext(self, event)
            yield trace_context
            
            # 正常结束
            event.end(CallStatus.SUCCESS)
            
            if self.enable_console_log:
                print(f"[OK] [Monitor] Agent 完成 | 耗时: {event.duration:.2f}s | 回答长度: {event.metadata.get('answer_length', 0)}")
        
        except (ValueError, KeyError) as e:
            event.set_error(e)
        except (OSError, IOError) as e:
            event.set_error(e)
        except Exception as e:
            event.set_error(e)# 异常结束
            event.set_error(e)
            event.end(CallStatus.FAILED)
            
            if self.enable_console_log:
                print(f"[ERROR] [Monitor] Agent 失败 | 错误: {event.error}")
            
            raise
        
        finally:
            # 记录事件
            self.events.append(event)
            self.active_traces.pop(event.trace_id, None)
    
    @asynccontextmanager
    async def trace_tool(
        self,
        tool_name: str,
        trace_id: str,
        parent_id: Optional[str] = None,
        **kwargs
    ):
        """
        追踪工具调用
        
        Args:
            tool_name: 工具名称
            trace_id: 追踪ID（继承自 Agent）
            parent_id: 父事件ID
            **kwargs: 工具调用参数
        
        示例：
            async with monitor.trace_tool("get_weather", trace_id, city="北京") as tool_trace:
                result = await get_weather("北京")
                tool_trace.set_result(result)
        """
        event = MonitorEvent(
            event_type=EventType.TOOL_CALL_START,
            trace_id=trace_id,
            parent_id=parent_id
        )
        
        event.metadata.update({
            "tool_name": tool_name,
            "parameters": kwargs
        })
        
        if self.enable_console_log:
            params_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
            print(f"[TOOL] [Monitor] 工具调用 | {tool_name}({params_str})")
        
        try:
            # 创建工具追踪上下文
            tool_context = ToolTraceContext(self, event)
            yield tool_context
            
            # 正常结束
            event.end(CallStatus.SUCCESS)
            
            if self.enable_console_log:
                result_preview = str(event.metadata.get('result', ''))[:100]
                print(f"[OK] [Monitor] 工具完成 | {tool_name} | 耗时: {event.duration:.2f}s | 结果: {result_preview}")
        
        except (ValueError, KeyError) as e:
            event.set_error(e)
        except (OSError, IOError) as e:
            event.set_error(e)
        except Exception as e:
            event.set_error(e)# 异常结束
            event.set_error(e)
            event.end(CallStatus.FAILED)
            
            if self.enable_console_log:
                print(f"[ERROR] [Monitor] 工具失败 | {tool_name} | 错误: {event.error}")
            
            raise
        
        finally:
            # 记录事件
            self.events.append(event)
    
    @asynccontextmanager
    async def trace_llm(
        self,
        model_name: str,
        trace_id: str,
        parent_id: Optional[str] = None,
        prompt: Optional[str] = None
    ):
        """
        追踪 LLM 调用
        
        Args:
            model_name: 模型名称
            trace_id: 追踪ID
            parent_id: 父事件ID
            prompt: 提示词
        
        示例:
            async with monitor.trace_llm("glm-4-flash", trace_id, prompt=prompt) as llm_trace:
                response = await llm.ainvoke(messages)
                llm_trace.set_tokens(input_tokens=100, output_tokens=50)
        """
        event = MonitorEvent(
            event_type=EventType.LLM_START,
            trace_id=trace_id,
            parent_id=parent_id
        )
        
        event.metadata.update({
            "model_name": model_name,
            "prompt_length": len(prompt) if prompt else 0
        })
        
        if self.enable_console_log:
            print(f"[BOT] [Monitor] LLM 调用 | 模型: {model_name}")
        
        try:
            llm_context = LLMTraceContext(self, event)
            yield llm_context
            
            event.end(CallStatus.SUCCESS)
            
            if self.enable_console_log:
                tokens = event.metadata.get('total_tokens', 0)
                print(f"[OK] [Monitor] LLM 完成 | 耗时: {event.duration:.2f}s | Tokens: {tokens}")
        
        except (ValueError, KeyError) as e:
            event.set_error(e)
            event.end(CallStatus.FAILED)
        except (OSError, IOError) as e:
            event.set_error(e)
            event.end(CallStatus.FAILED)
        except Exception as e:
            event.set_error(e)
            event.end(CallStatus.FAILED)
            
            if self.enable_console_log:
                print(f"[ERROR] [Monitor] LLM 失败 | 错误: {event.error}")
            
            raise
        
        finally:
            self.events.append(event)
    
    def trace_function(self, event_type: str = "custom"):
        """
        装饰器：追踪函数调用
        
        示例：
            @monitor.trace_function("custom_operation")
            async def my_function(arg1, arg2):
                return result
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                event = MonitorEvent(
                    event_type=EventType.CUSTOM,
                    trace_id=str(uuid.uuid4())
                )
                
                event.metadata.update({
                    "function_name": func.__name__,
                    "event_type": event_type,
                    "args": str(args)[:200],
                    "kwargs": str(kwargs)[:200]
                })
                
                try:
                    result = await func(*args, **kwargs)
                    event.end(CallStatus.SUCCESS, result=str(result)[:200])
                    return result
                
                except (ValueError, KeyError) as e:
                    event.set_error(e)
                    event.end(CallStatus.FAILED)
                except (OSError, IOError) as e:
                    event.set_error(e)
                    event.end(CallStatus.FAILED)
                except Exception as e:
                    event.set_error(e)
                    event.end(CallStatus.FAILED)
                    raise
                
                finally:
                    self.events.append(event)
            
            return wrapper
        return decorator
    
    def get_trace_events(self, trace_id: str) -> List[MonitorEvent]:
        """获取指定追踪ID的所有事件"""
        return [e for e in self.events if e.trace_id == trace_id]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        返回：
        - 总调用次数
        - 成功/失败次数
        - 平均耗时
        - 工具调用统计
        - 错误统计
        """
        if not self.events:
            return {"message": "暂无监控数据"}
        
        total_count = len(self.events)
        success_count = sum(1 for e in self.events if e.status == CallStatus.SUCCESS)
        failed_count = sum(1 for e in self.events if e.status == CallStatus.FAILED)
        
        # 计算平均耗时
        durations = [e.duration for e in self.events if e.duration]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # 工具调用统计
        tool_calls = [e for e in self.events if e.event_type == EventType.TOOL_CALL_START]
        tool_stats = {}
        for event in tool_calls:
            tool_name = event.metadata.get("tool_name", "unknown")
            if tool_name not in tool_stats:
                tool_stats[tool_name] = {"count": 0, "success": 0, "failed": 0, "avg_duration": 0}
            
            tool_stats[tool_name]["count"] += 1
            if event.status == CallStatus.SUCCESS:
                tool_stats[tool_name]["success"] += 1
            else:
                tool_stats[tool_name]["failed"] += 1
        
        # 错误统计
        errors = [e.error for e in self.events if e.error]
        error_types = {}
        for error in errors:
            error_type = error.split(":")[0]
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            "total_events": total_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": f"{success_count / total_count * 100:.1f}%" if total_count > 0 else "0%",
            "avg_duration": round(avg_duration, 3),
            "tool_statistics": tool_stats,
            "error_types": error_types
        }
    
    def export_trace(self, trace_id: str) -> Dict[str, Any]:
        """
        导出完整的追踪链
        
        返回结构化的追踪数据，可用于可视化或分析
        """
        events = self.get_trace_events(trace_id)
        
        if not events:
            return {"error": "追踪ID不存在"}
        
        return {
            "trace_id": trace_id,
            "event_count": len(events),
            "events": [e.to_dict() for e in events],
            "timeline": self._build_timeline(events)
        }
    
    def _build_timeline(self, events: List[MonitorEvent]) -> List[Dict]:
        """构建时间线（用于可视化）"""
        if not events:
            return []
        
        base_time = min(e.start_time for e in events)
        
        timeline = []
        for event in sorted(events, key=lambda e: e.start_time):
            timeline.append({
                "event_type": event.event_type.value,
                "start_offset": round(event.start_time - base_time, 3),
                "duration": round(event.duration, 3) if event.duration else 0,
                "status": event.status.value if event.status else None,
                "metadata": event.metadata
            })
        
        return timeline
    
    def clear_events(self):
        """清空所有事件记录"""
        self.events.clear()
        print("🗑️ [Monitor] 事件记录已清空")
    
    def export_to_json(self, filepath: str):
        """导出所有事件到 JSON 文件"""
        data = {
            "export_time": datetime.now().isoformat(),
            "total_events": len(self.events),
            "events": [e.to_dict() for e in self.events],
            "statistics": self.get_statistics()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[FILE] [Monitor] 已导出到: {filepath}")


class AgentTraceContext:
    """Agent 追踪上下文"""
    
    def __init__(self, monitor: MonitorService, event: MonitorEvent):
        self.monitor = monitor
        self.event = event
    
    def set_result(self, answer):
        """设置 Agent 回答
        
        Args:
            answer: Agent 的回答，可以是字符串、LLMResponse 对象或其他类型
        """
        if answer is None:
            answer_str = "[无回答]"
            answer_length = 0
        elif hasattr(answer, 'content'):
            # LLMResponse 对象，提取 content 属性
            answer_str = str(answer.content)[:500]
            answer_length = len(answer.content) if answer.content else 0
        elif isinstance(answer, str):
            answer_str = answer[:500]
            answer_length = len(answer)
        else:
            # 其他类型，转换为字符串
            answer_str = str(answer)[:500]
            answer_length = len(answer_str)
        
        self.event.metadata["answer"] = answer_str
        self.event.metadata["answer_length"] = answer_length
    
    def set_sources(self, sources: List[Dict]):
        """设置参考来源"""
        self.event.metadata["sources_count"] = len(sources)
        self.event.metadata["sources"] = sources
    
    async def trace_tool(self, tool_name: str, **kwargs):
        """在 Agent 上下文中追踪工具调用"""
        return self.monitor.trace_tool(
            tool_name=tool_name,
            trace_id=self.event.trace_id,
            parent_id=self.event.event_id,
            **kwargs
        )
    
    async def trace_llm(self, model_name: str, prompt: Optional[str] = None):
        """在 Agent 上下文中追踪 LLM 调用"""
        return self.monitor.trace_llm(
            model_name=model_name,
            trace_id=self.event.trace_id,
            parent_id=self.event.event_id,
            prompt=prompt
        )


class ToolTraceContext:
    """工具追踪上下文"""
    
    def __init__(self, monitor: MonitorService, event: MonitorEvent):
        self.monitor = monitor
        self.event = event
    
    def set_result(self, result: Any):
        """设置工具返回结果"""
        result_str = str(result)
        self.event.metadata["result"] = result_str[:500]  # 只保存前500字符
        self.event.metadata["result_length"] = len(result_str)


class LLMTraceContext:
    """LLM 追踪上下文"""
    
    def __init__(self, monitor: MonitorService, event: MonitorEvent):
        self.monitor = monitor
        self.event = event
    
    def set_tokens(self, input_tokens: int, output_tokens: int):
        """设置 Token 使用量"""
        self.event.metadata["input_tokens"] = input_tokens
        self.event.metadata["output_tokens"] = output_tokens
        self.event.metadata["total_tokens"] = input_tokens + output_tokens
    
    def set_response(self, response: str):
        """设置 LLM 响应"""
        self.event.metadata["response"] = response[:500]
        self.event.metadata["response_length"] = len(response)


# 全局单例
monitor_service = MonitorService(enable_console_log=False)


# ==========================================
# 便捷函数
# ==========================================

async def trace_agent(user_id: str, query: str, **kwargs):
    """便捷的 Agent 追踪函数"""
    return monitor_service.trace_agent(user_id, query, **kwargs)


async def trace_tool(tool_name: str, trace_id: str, **kwargs):
    """便捷的工具追踪函数"""
    return monitor_service.trace_tool(tool_name, trace_id, **kwargs)


def get_statistics() -> Dict[str, Any]:
    """获取监控统计信息"""
    return monitor_service.get_statistics()


def export_trace(trace_id: str) -> Dict[str, Any]:
    """导出追踪链"""
    return monitor_service.export_trace(trace_id)
