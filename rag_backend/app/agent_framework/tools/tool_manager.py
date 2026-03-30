# app/agent_framework/tools/tool_manager.py

"""
工具管理器

负责工具的注册、调用和管理
"""

from typing import Dict, Any, Callable, List, Optional
import asyncio
import inspect
import json
import re
import time
from app.services.tool_call_tracer import tool_call_tracer


# LangSmith 追踪器（延迟导入避免循环依赖）
_langsmith_tracer = None


def _get_langsmith_tracer():
    """获取 LangSmith 追踪器（延迟初始化）"""
    global _langsmith_tracer
    if _langsmith_tracer is None:
        try:
            from app.langsmith_integration import get_tracer
            _langsmith_tracer = get_tracer()
        except Exception as e:
            print(f"[ToolManager] 无法加载 LangSmith 追踪器: {e}")
            _langsmith_tracer = None
    return _langsmith_tracer


class ToolManager:
    """
    工具管理器
    
    提供工具注册、调用和描述生成功能
    """
    
    def __init__(self):
        """
        初始化工具管理器
        """
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.tracer = tool_call_tracer
        self.call_stack = []  # 调用栈（支持嵌套调用）
        self.enable_tracing = True
        
        print("🛠️ 工具管理器初始化完成")
    
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
            
            print(f"✅ 注册 LangChain 工具: {name}")
            print(f"   描述: {description}")
            print(f"   参数: {list(params.keys())}")
            
        except Exception as e:
            print(f"❌ 注册 LangChain 工具失败: {str(e)}")
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
                # 🔧 构建带示例的错误提示，引导模型正确重试
                example_json = {k: f"<{k}的具体内容>" for k, v in tool_info["parameters"].items() if v.get("required", False)}
                error_msg = (
                    f"错误: 缺少必需参数: {', '.join(missing_params)}。"
                    f"请使用以下格式重试: "
                    f"Action Input: {json.dumps(example_json, ensure_ascii=False)}"
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
            
            return result
            
        except Exception as e:
            error_msg = f"工具执行错误: {str(e)}"
            print(f"❌ {tool_name} 执行失败: {error_msg}")
            
            # 记录失败
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
            }
        }