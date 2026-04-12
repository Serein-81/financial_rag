# app/agent_framework/tools/tool_manager.py

"""
工具管理器

负责工具的注册、调用和管理
"""

from typing import Dict, Any, Callable, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import inspect
import json
import re
import time
import logging
from app.services.tool_call_tracer import tool_call_tracer
from app.services.tool_dependency_graph import tool_dependency_graph

logger = logging.getLogger(__name__)


@dataclass
class ToolFailureRecord:
    """工具失败记录"""
    tool_name: str
    error_type: str
    error_message: str
    timestamp: datetime
    retry_count: int = 0
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolFailureStats:
    """工具失败统计"""
    total_failures: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None
    last_error_type: Optional[str] = None
    last_error_message: Optional[str] = None
    recent_failures: List[ToolFailureRecord] = field(default_factory=list)
    cooldown_until: Optional[datetime] = None


# LangSmith 追踪器（延迟导入避免循环依赖）
_langsmith_tracer = None


def _get_langsmith_tracer():
    """获取 LangSmith 追踪器（延迟初始化）"""
    global _langsmith_tracer
    if _langsmith_tracer is None:
        try:
            from app.langsmith_integration import get_tracer
            _langsmith_tracer = get_tracer()
        except (ValueError, KeyError) as e:
            logger.warning(f"[ToolManager] 无法加载 LangSmith 追踪器数据错误: {e}")
            _langsmith_tracer = None
        except (OSError, IOError) as e:
            logger.warning(f"[ToolManager] 无法加载 LangSmith 追踪器IO错误: {e}")
            _langsmith_tracer = None
        except Exception as e:
            logger.warning(f"[ToolManager] 无法加载 LangSmith 追踪器: {e}")
            _langsmith_tracer = None
    return _langsmith_tracer


class ToolManager:
    """
    工具管理器
    
    提供工具注册、调用和描述生成功能
    """
    
    def __init__(
        self,
        max_consecutive_failures: int = 3,
        failure_cooldown_minutes: int = 5,
        max_failure_records: int = 100
    ):
        """
        初始化工具管理器
        
        Args:
            max_consecutive_failures: 最大连续失败次数，超过后标记工具
            failure_cooldown_minutes: 失败冷却时间（分钟）
            max_failure_records: 最大失败记录保留数
        """
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.tracer = tool_call_tracer
        self.call_stack = []
        self.enable_tracing = True
        
        self._failure_stats: Dict[str, ToolFailureStats] = defaultdict(ToolFailureStats)
        self._max_consecutive_failures = max_consecutive_failures
        self._failure_cooldown_minutes = failure_cooldown_minutes
        self._max_failure_records = max_failure_records
        self._disabled_tools: Set[str] = set()
        
        self._dependency_graph = tool_dependency_graph
        self._call_history: List[List[str]] = []
        self._current_sequence: List[str] = []
        self._max_history_size = 1000
        
        logger.info("🛠️ 工具管理器初始化完成 (失败标记已启用, 依赖图谱已加载)")
    
    def register_function(
        self, 
        name: str, 
        func: Callable, 
        description: str,
        args_schema: Optional[Dict] = None
    ):
        """
        注册普通函数为工具
        
        Args:
            name: 工具名称
            func: 工具函数
            description: 工具描述
            args_schema: 参数模式（可选）
        """
        # 自动提取函数签名
        sig = inspect.signature(func)
        params = {}
        
        for param_name, param in sig.parameters.items():
            param_info = {
                "type": "string",  # 默认类型
                "required": param.default == inspect.Parameter.empty
            }
            
            # 尝试从类型注解获取类型
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == str:
                    param_info["type"] = "string"
                elif param.annotation == int:
                    param_info["type"] = "integer"
                elif param.annotation == float:
                    param_info["type"] = "number"
                elif param.annotation == bool:
                    param_info["type"] = "boolean"
            
            params[param_name] = param_info
        
        # 注册工具
        self.tools[name] = {
            "func": func,
            "description": description,
            "parameters": params,
            "args_schema": args_schema,
            "type": "function"
        }
        
        print(f"✅ 注册工具: {name}")
        print(f"   描述: {description}")
        print(f"   参数: {list(params.keys())}")
    
    def register_langchain_tool(self, langchain_tool):
        """
        注册 LangChain 工具
        
        Args:
            langchain_tool: LangChain 工具对象
        """
        try:
            name = langchain_tool.name
            description = langchain_tool.description
            
            # 提取可调用函数，优先级：coroutine > func > _run > invoke
            func = None
            if hasattr(langchain_tool, 'coroutine') and langchain_tool.coroutine:
                func = langchain_tool.coroutine
            elif hasattr(langchain_tool, 'func') and langchain_tool.func:
                func = langchain_tool.func
            elif hasattr(langchain_tool, '_run'):
                func = langchain_tool._run
            elif hasattr(langchain_tool, 'invoke'):
                func = langchain_tool.invoke
            
            if func is None:
                raise ValueError(f"无法从 LangChain 工具 {name} 中提取可调用函数")
            
            # 提取参数信息
            params = {}
            if hasattr(langchain_tool, 'args_schema') and langchain_tool.args_schema:
                # 从 Pydantic 模型提取参数
                schema = langchain_tool.args_schema.model_json_schema()
                if 'properties' in schema:
                    for param_name, param_info in schema['properties'].items():
                        params[param_name] = {
                            "type": param_info.get("type", "string"),
                            "description": param_info.get("description", ""),
                            "required": param_name in schema.get("required", [])
                        }
            
            # 注册工具
            self.tools[name] = {
                "func": func,
                "description": description,
                "parameters": params,
                "args_schema": langchain_tool.args_schema if hasattr(langchain_tool, 'args_schema') else None,
                "type": "langchain",
                "original_tool": langchain_tool
            }
            
            logger.debug(f"✅ 注册 LangChain 工具: {name}")
            logger.debug(f"   描述: {description}")
            logger.debug(f"   参数: {list(params.keys())}")
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 注册 LangChain 工具数据错误: {str(e)}")
            raise
        except (OSError, IOError) as e:
            logger.error(f"❌ 注册 LangChain 工具IO错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ 注册 LangChain 工具失败: {str(e)}")
            raise
    
    async def call_tool(self, tool_name: str, trace_id: str = None, **kwargs) -> str:
        """
        调用工具（带追踪）
        
        Args:
            tool_name: 工具名称
            trace_id: Agent 追踪 ID
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name not in self.tools:
            available_tools = ", ".join(self.tools.keys())
            return f"错误: 工具 '{tool_name}' 不存在。可用工具: {available_tools}"
        
        tool_info = self.tools[tool_name]
        func = tool_info["func"]
        
        # 开始追踪
        call_id = None
        if self.enable_tracing:
            try:
                call_id = await self.tracer.start_call(
                    tool_name=tool_name,
                    tool_type=tool_info["type"],
                    input_params=kwargs,
                    trace_id=trace_id,
                    parent_call_id=self.call_stack[-1] if self.call_stack else None
                )
                self.call_stack.append(call_id)
            except (ValueError, KeyError) as e:
                print(f"⚠️ 开始工具追踪数据错误: {e}")
            except (OSError, IOError) as e:
                print(f"⚠️ 开始工具追踪IO错误: {e}")
            except Exception as e:
                print(f"⚠️ 开始工具追踪失败: {e}")
        
        start_time = time.time()
        
        try:
            # 检查必需参数
            missing_params = []
            for param_name, param_info in tool_info["parameters"].items():
                if param_info.get("required", False) and param_name not in kwargs:
                    missing_params.append(param_name)
            
            if missing_params:
                example_json = {k: f"<{k}的具体内容>" for k, v in tool_info["parameters"].items() if v.get("required", False)}
                error_msg = (
                    f"错误: 缺少必需参数: {', '.join(missing_params)}。"
                    f"请使用以下格式重试: "
                    f"Action Input: {json.dumps(example_json, ensure_ascii=False)}"
                )
                
                self._record_failure(
                    tool_name, 
                    "MissingParameters", 
                    f"缺少参数: {', '.join(missing_params)}"
                )
                
                if call_id:
                    await self.tracer.end_call(
                        call_id=call_id,
                        duration=(time.time() - start_time) * 1000,
                        status="error",
                        error_message=error_msg
                    )
                return error_msg
            
            # 调用工具函数
            if asyncio.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = func(**kwargs)
            
            # 确保返回字符串
            if not isinstance(result, str):
                result = str(result)
            
            # 记录成功
            if call_id:
                await self.tracer.end_call(
                    call_id=call_id,
                    output_result=result,
                    duration=(time.time() - start_time) * 1000,
                    status="success"
                )
            
            # LangSmith 追踪
            langsmith_tracer = _get_langsmith_tracer()
            if langsmith_tracer and langsmith_tracer.client:
                langsmith_tracer.trace_tool_call(
                    tool_name=tool_name,
                    arguments=kwargs,
                    result=result
                )
            
            self._record_success(tool_name)
            self._current_sequence.append(tool_name)
            
            return result
            
        except (ValueError, KeyError) as e:
            error_msg = f"工具执行数据错误: {str(e)}"
            logger.error(f"❌ {tool_name} 执行数据错误: {error_msg}")
        except (OSError, IOError) as e:
            error_msg = f"工具执行IO错误: {str(e)}"
            logger.error(f"❌ {tool_name} 执行IO错误: {error_msg}")
        except Exception as e:
            error_msg = f"工具执行错误: {str(e)}"
            logger.error(f"❌ {tool_name} 执行失败: {error_msg}")
            
            self._record_failure(tool_name, type(e).__name__, error_msg)
            
            if call_id:
                await self.tracer.end_call(
                    call_id=call_id,
                    duration=(time.time() - start_time) * 1000,
                    status="error",
                    error_message=error_msg
                )
            
            # LangSmith 追踪错误
            langsmith_tracer = _get_langsmith_tracer()
            if langsmith_tracer and langsmith_tracer.client:
                langsmith_tracer.trace_tool_call(
                    tool_name=tool_name,
                    arguments=kwargs,
                    result=None,
                    error=error_msg
                )
            
            return error_msg
        finally:
            # 弹出调用栈
            if call_id and self.call_stack and self.call_stack[-1] == call_id:
                self.call_stack.pop()
    
    def get_tools_description(self) -> str:
        """
        获取所有工具的描述（用于提示词）
        包含 JSON 调用示例，帮助模型正确格式化 Action Input
        """
        if not self.tools:
            return "当前没有可用的工具。"

        descriptions = []
        for name, info in self.tools.items():
            desc_parts = [f"- {name}: {info['description']}"]

            # 添加参数说明
            if info["parameters"]:
                required_params = []
                optional_params = []
                example_json = {}

                for param_name, param_info in info["parameters"].items():
                    param_desc = f"{param_name}({param_info['type']})"
                    if param_info.get("required", False):
                        required_params.append(param_desc)
                        example_json[param_name] = f"<{param_name}的值>"
                    else:
                        optional_params.append(param_desc)

                if required_params:
                    desc_parts.append(f"  必需参数: {', '.join(required_params)}")
                if optional_params:
                    desc_parts.append(f"  可选参数: {', '.join(optional_params)}")

                # 🔧 新增：展示 JSON 调用格式示例
                desc_parts.append(
                    f"  调用示例: Action: {name}\n"
                    f"           Action Input: {json.dumps(example_json, ensure_ascii=False)}"
                )

            descriptions.append("\n".join(desc_parts))

        return "\n".join(descriptions)
    
    def get_tool_names(self) -> List[str]:
        """
        获取所有工具名称
        
        Returns:
            工具名称列表
        """
        return list(self.tools.keys())
    
    def parse_tool_call_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        从文本中解析工具调用
        
        支持多种格式:
        1. Action: tool_name
           Action Input: {"param": "value"}
        
        2. 使用工具: tool_name
           参数: {"param": "value"}
        
        Args:
            text: 包含工具调用的文本
            
        Returns:
            解析出的工具调用信息，如果没有找到则返回 None
        """
        # 模式1: Action/Action Input 格式
        action_pattern = r'Action:\s*(\w+)'
        input_pattern = r'Action Input:\s*(\{.*?\})'
        
        action_match = re.search(action_pattern, text, re.IGNORECASE)
        input_match = re.search(input_pattern, text, re.DOTALL)
        
        if action_match:
            tool_name = action_match.group(1)
            
            # 解析参数
            params = {}
            if input_match:
                try:
                    params = json.loads(input_match.group(1))
                except json.JSONDecodeError:
                    print(f"⚠️ 无法解析工具参数: {input_match.group(1)}")
            
            return {
                "tool_name": tool_name,
                "parameters": params
            }
        
        # 模式3: MiniMax XML 格式
        # <invoke name="tool_name">
        #   <parameter name="param_name">value</parameter>
        # </invoke>
        xml_pattern = r'<invoke\s+name="([^"]+)"'
        xml_params_pattern = r'<parameter\s+name="([^"]+)">([^<]*)</parameter>'
        
        xml_match = re.search(xml_pattern, text, re.IGNORECASE)
        if xml_match:
            tool_name = xml_match.group(1)
            
            # 提取所有参数
            params = {}
            for param_match in re.finditer(xml_params_pattern, text, re.DOTALL):
                param_name = param_match.group(1)
                param_value = param_match.group(2).strip()
                params[param_name] = param_value
            
            return {
                "tool_name": tool_name,
                "parameters": params
            }
        
        # 模式2: 中文格式
        chinese_pattern = r'使用工具:\s*(\w+)'
        chinese_params_pattern = r'参数:\s*(\{.*?\})'
        
        chinese_match = re.search(chinese_pattern, text)
        chinese_params_match = re.search(chinese_params_pattern, text, re.DOTALL)
        
        if chinese_match:
            tool_name = chinese_match.group(1)
            
            params = {}
            if chinese_params_match:
                try:
                    params = json.loads(chinese_params_match.group(1))
                except json.JSONDecodeError:
                    print(f"⚠️ 无法解析工具参数: {chinese_params_match.group(1)}")
            
            return {
                "tool_name": tool_name,
                "parameters": params
            }
        
        return None
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取工具管理器摘要
        
        Returns:
            摘要信息
        """
        return {
            "total_tools": len(self.tools),
            "tool_names": list(self.tools.keys()),
            "tool_types": {
                "function": len([t for t in self.tools.values() if t["type"] == "function"]),
                "langchain": len([t for t in self.tools.values() if t["type"] == "langchain"])
            },
            "failure_tracking": {
                "total_tracked_tools": len(self._failure_stats),
                "disabled_tools": list(self._disabled_tools),
                "total_failures": sum(s.total_failures for s in self._failure_stats.values())
            }
        }
    
    def _record_failure(
        self,
        tool_name: str,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        记录工具失败
        
        Args:
            tool_name: 工具名称
            error_type: 错误类型
            error_message: 错误消息
            context: 额外上下文
        """
        if tool_name not in self.tools:
            return
        
        now = datetime.now()
        stats = self._failure_stats[tool_name]
        
        stats.total_failures += 1
        stats.consecutive_failures += 1
        stats.last_failure_time = now
        stats.last_error_type = error_type
        stats.last_error_message = error_message
        
        record = ToolFailureRecord(
            tool_name=tool_name,
            error_type=error_type,
            error_message=error_message,
            timestamp=now,
            context=context or {}
        )
        
        stats.recent_failures.append(record)
        
        if len(stats.recent_failures) > self._max_failure_records:
            stats.recent_failures = stats.recent_failures[-self._max_failure_records:]
        
        if stats.consecutive_failures >= self._max_consecutive_failures:
            stats.cooldown_until = now + timedelta(minutes=self._failure_cooldown_minutes)
            self._disabled_tools.add(tool_name)
            logger.warning(
                f"⚠️ 工具 {tool_name} 连续失败 {stats.consecutive_failures} 次，"
                f"已暂时禁用直到 {stats.cooldown_until}"
            )
    
    def _record_success(self, tool_name: str):
        """
        记录工具成功执行
        
        Args:
            tool_name: 工具名称
        """
        if tool_name not in self.tools:
            return
        
        stats = self._failure_stats[tool_name]
        stats.consecutive_failures = 0
        
        if tool_name in self._disabled_tools:
            stats.cooldown_until = None
            self._disabled_tools.discard(tool_name)
            logger.info(f"✅ 工具 {tool_name} 已重新启用")
    
    def is_tool_available(self, tool_name: str) -> Tuple[bool, Optional[str]]:
        """
        检查工具是否可用
        
        Args:
            tool_name: 工具名称
            
        Returns:
            (是否可用, 不可用原因)
        """
        if tool_name not in self.tools:
            return False, f"工具不存在: {tool_name}"
        
        if tool_name in self._disabled_tools:
            stats = self._failure_stats.get(tool_name)
            if stats and stats.cooldown_until:
                now = datetime.now()
                if now < stats.cooldown_until:
                    remaining = (stats.cooldown_until - now).seconds // 60 + 1
                    return False, f"工具冷却中，剩余 {remaining} 分钟"
                else:
                    self._disabled_tools.discard(tool_name)
                    stats.cooldown_until = None
        
        return True, None
    
    def get_tool_failure_stats(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具失败统计
        
        Args:
            tool_name: 工具名称
            
        Returns:
            失败统计信息
        """
        if tool_name not in self.tools:
            return None
        
        stats = self._failure_stats.get(tool_name)
        if not stats:
            return None
        
        return {
            "total_failures": stats.total_failures,
            "consecutive_failures": stats.consecutive_failures,
            "last_failure_time": stats.last_failure_time.isoformat() if stats.last_failure_time else None,
            "last_error_type": stats.last_error_type,
            "last_error_message": stats.last_error_message,
            "recent_failure_count": len(stats.recent_failures),
            "is_disabled": tool_name in self._disabled_tools,
            "cooldown_until": stats.cooldown_until.isoformat() if stats.cooldown_until else None
        }
    
    def get_all_failure_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有工具的失败统计
        
        Returns:
            所有工具的失败统计
        """
        return {
            tool_name: self.get_tool_failure_stats(tool_name)
            for tool_name in self._failure_stats.keys()
            if self.get_tool_failure_stats(tool_name) is not None
        }
    
    def reset_tool_failures(self, tool_name: str):
        """
        重置工具失败记录
        
        Args:
            tool_name: 工具名称
        """
        if tool_name in self._failure_stats:
            stats = self._failure_stats[tool_name]
            stats.total_failures = 0
            stats.consecutive_failures = 0
            stats.recent_failures.clear()
            stats.cooldown_until = None
        
        if tool_name in self._disabled_tools:
            self._disabled_tools.discard(tool_name)
            logger.info(f"🔄 工具 {tool_name} 失败记录已重置")
    
    def enable_tool(self, tool_name: str):
        """
        手动启用工具
        
        Args:
            tool_name: 工具名称
        """
        if tool_name in self._disabled_tools:
            self._disabled_tools.discard(tool_name)
            if tool_name in self._failure_stats:
                self._failure_stats[tool_name].cooldown_until = None
                self._failure_stats[tool_name].consecutive_failures = 0
            logger.info(f"✅ 工具 {tool_name} 已手动启用")
        else:
            logger.warning(f"工具 {tool_name} 未被禁用，无需启用")
    
    def disable_tool(self, tool_name: str, reason: str = "手动禁用"):
        """
        手动禁用工具
        
        Args:
            tool_name: 工具名称
            reason: 禁用原因
        """
        if tool_name not in self.tools:
            logger.error(f"无法禁用不存在的工具: {tool_name}")
            return
        
        self._disabled_tools.add(tool_name)
        stats = self._failure_stats[tool_name]
        stats.cooldown_until = datetime.max
        stats.consecutive_failures = self._max_consecutive_failures
        
        logger.warning(f"⚠️ 工具 {tool_name} 已手动禁用: {reason}")
    
    def get_healthy_tools(self) -> List[str]:
        """
        获取所有健康可用的工具
        
        Returns:
            可用工具名称列表
        """
        return [
            name for name in self.tools.keys()
            if name not in self._disabled_tools
        ]
    
    def get_tool_health_report(self) -> Dict[str, Any]:
        """
        获取工具健康状态报告
        
        Returns:
            健康报告
        """
        total = len(self.tools)
        healthy = len(self.get_healthy_tools())
        disabled = len(self._disabled_tools)
        
        most_failing = sorted(
            self._failure_stats.items(),
            key=lambda x: x[1].consecutive_failures,
            reverse=True
        )[:5]
        
        return {
            "summary": {
                "total": total,
                "healthy": healthy,
                "disabled": disabled,
                "health_ratio": healthy / total if total > 0 else 1.0
            },
            "most_failing": [
                {
                    "tool": name,
                    "consecutive_failures": stats.consecutive_failures,
                    "last_error": stats.last_error_type
                }
                for name, stats in most_failing
                if stats.consecutive_failures > 0
            ],
            "recent_disabled": list(self._disabled_tools)
        }
    
    def get_execution_order(self, required_tools: List[str]) -> List[str]:
        """
        获取工具执行顺序（基于依赖图谱）
        
        Args:
            required_tools: 需要执行的工具列表
            
        Returns:
            排序后的执行顺序
        """
        available_tools = set(self.get_healthy_tools())
        valid_tools = [t for t in required_tools if t in available_tools]
        
        return self._dependency_graph.suggest_execution_order(valid_tools)
    
    def plan_execution(self, required_tools: List[str], max_parallel: int = 3) -> Dict[str, Any]:
        """
        规划工具执行（考虑依赖和并行）
        
        Args:
            required_tools: 需要执行的工具列表
            max_parallel: 最大并行数
            
        Returns:
            执行计划
        """
        available_tools = set(self.get_healthy_tools())
        valid_tools = [t for t in required_tools if t in available_tools]
        
        plan = self._dependency_graph.plan_execution(valid_tools, max_parallel)
        
        return {
            "execution_order": plan.execution_order,
            "parallel_groups": plan.parallel_groups,
            "total_tools": plan.total_tools,
            "estimated_parallelism": len(plan.parallel_groups)
        }
    
    def learn_dependencies(self):
        """
        从调用历史学习工具依赖关系
        """
        if len(self._call_history) < 3:
            logger.warning("调用历史不足，无法学习依赖关系")
            return
        
        tool_schemas = {}
        for name, info in self.tools.items():
            tool_schemas[name] = {
                "input_schema": {"properties": info.get("parameters", {})},
                "output_schema": {}
            }
        
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    self._dependency_graph.learn_from_history(
                        self._call_history,
                        tool_schemas
                    )
                )
            else:
                loop.run_until_complete(
                    self._dependency_graph.learn_from_history(
                        self._call_history,
                        tool_schemas
                    )
                )
        except (ValueError, KeyError) as e:
            logger.error(f"学习依赖关系数据错误: {e}")
        except (OSError, IOError) as e:
            logger.error(f"学习依赖关系IO错误: {e}")
        except Exception as e:
            logger.error(f"学习依赖关系失败: {e}")
    
    def finish_sequence(self):
        """
        结束当前调用序列，记录到历史
        """
        if self._current_sequence:
            self._call_history.append(self._current_sequence.copy())
            
            if len(self._call_history) > self._max_history_size:
                self._call_history = self._call_history[-self._max_history_size:]
            
            logger.info(f"工具调用序列完成: {' -> '.join(self._current_sequence)}")
            self._current_sequence = []
    
    def get_current_sequence(self) -> List[str]:
        """
        获取当前调用序列
        
        Returns:
            当前序列中的工具列表
        """
        return self._current_sequence.copy()
    
    def get_call_history(self) -> List[List[str]]:
        """
        获取调用历史
        
        Returns:
            调用历史序列列表
        """
        return self._call_history.copy()
    
    def get_tool_dependencies(self, tool_name: str) -> Optional[List[str]]:
        """
        获取工具的依赖关系
        
        Args:
            tool_name: 工具名称
            
        Returns:
            依赖的工具列表
        """
        deps = self._dependency_graph.get_dependencies(tool_name)
        return deps.depends_on if deps else None
    
    def get_all_dependencies(self) -> Dict[str, List[str]]:
        """
        获取所有工具的依赖关系
        
        Returns:
            依赖关系字典
        """
        return self._dependency_graph.get_all_dependencies()
    
    def analyze_dependencies_with_llm(self, tools: List[Dict[str, Any]]):
        """
        使用 LLM 分析工具依赖
        
        Args:
            tools: 工具定义列表
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    self._dependency_graph.analyze_with_llm(tools)
                )
            else:
                loop.run_until_complete(
                    self._dependency_graph.analyze_with_llm(tools)
                )
        except (ValueError, KeyError) as e:
            logger.error(f"LLM 分析依赖数据错误: {e}")
        except (OSError, IOError) as e:
            logger.error(f"LLM 分析依赖IO错误: {e}")
        except Exception as e:
            logger.error(f"LLM 分析依赖失败: {e}")
    
    def get_dependency_health_score(self, tool_name: str) -> float:
        """
        获取基于依赖的工具健康分数
        
        Args:
            tool_name: 工具名称
            
        Returns:
            健康分数 0.0 - 1.0
        """
        return self._dependency_graph.get_tool_health_score(tool_name)
    
    def get_dependency_report(self) -> Dict[str, Any]:
        """
        获取依赖图谱报告
        
        Returns:
            依赖图谱报告
        """
        all_deps = self._dependency_graph.get_all_dependencies()
        
        return {
            "total_tools": len(self.tools),
            "tools_with_dependencies": len(all_deps),
            "dependency_map": all_deps,
            "most_dependent": sorted(
                [(name, len(deps)) for name, deps in all_deps.items()],
                key=lambda x: x[1],
                reverse=True
            )[:10],
            "independent_tools": [
                name for name in self.tools.keys()
                if name not in all_deps
            ]
        }