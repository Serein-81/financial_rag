# app/agent_framework/tools/tool_chain.py

"""
工具链管理器 - 支持预定义工作流和智能Agent的混合架构
"""

from typing import List, Dict, Any, Optional, Callable, Union
import re
import json
import asyncio
from dataclasses import dataclass
from enum import Enum
from .tool_manager import ToolManager


class ChainStepType(Enum):
    """工具链步骤类型"""
    TOOL_CALL = "tool_call"        # 工具调用
    CONDITION = "condition"        # 条件判断
    TRANSFORM = "transform"        # 数据转换
    PARALLEL = "parallel"          # 并行执行


@dataclass
class ChainStep:
    """工具链步骤定义"""
    step_id: str
    step_type: ChainStepType
    tool_name: Optional[str] = None
    input_template: Optional[str] = None
    output_key: Optional[str] = None
    condition_func: Optional[Callable] = None
    transform_func: Optional[Callable] = None
    parallel_steps: Optional[List['ChainStep']] = None
    error_handling: str = "stop"  # stop, continue, retry


class ToolChain:
    """
    工具链 - 支持复杂的多步骤执行流程
    """
    
    def __init__(self, name: str, description: str, category: str = "general"):
        """
        初始化工具链
        
        Args:
            name: 工具链名称
            description: 工具链描述
            category: 工具链分类
        """
        self.name = name
        self.description = description
        self.category = category
        self.steps: List[ChainStep] = []
        self.variables: Dict[str, Any] = {}
        
        print(f"🔗 创建工具链: {name}")
    
    def add_tool_step(
        self, 
        step_id: str,
        tool_name: str, 
        input_template: str, 
        output_key: str = None,
        error_handling: str = "stop"
    ):
        """
        添加工具调用步骤
        
        Args:
            step_id: 步骤ID
            tool_name: 工具名称
            input_template: 输入模板，支持变量替换
            output_key: 输出结果的键名
            error_handling: 错误处理策略
        """
        step = ChainStep(
            step_id=step_id,
            step_type=ChainStepType.TOOL_CALL,
            tool_name=tool_name,
            input_template=input_template,
            output_key=output_key or f"{step_id}_result",
            error_handling=error_handling
        )
        self.steps.append(step)
        print(f"  ➕ 添加工具步骤: {step_id} -> {tool_name}")
    
    def add_condition_step(
        self,
        step_id: str,
        condition_func: Callable[[Dict[str, Any]], bool],
        true_steps: List[ChainStep],
        false_steps: List[ChainStep] = None
    ):
        """
        添加条件判断步骤
        
        Args:
            step_id: 步骤ID
            condition_func: 条件判断函数
            true_steps: 条件为真时执行的步骤
            false_steps: 条件为假时执行的步骤
        """
        step = ChainStep(
            step_id=step_id,
            step_type=ChainStepType.CONDITION,
            condition_func=condition_func
        )
        # 这里可以扩展支持条件分支
        self.steps.append(step)
        print(f"  ➕ 添加条件步骤: {step_id}")
    
    def add_transform_step(
        self,
        step_id: str,
        transform_func: Callable[[Dict[str, Any]], Dict[str, Any]],
        output_key: str = None
    ):
        """
        添加数据转换步骤
        
        Args:
            step_id: 步骤ID
            transform_func: 转换函数
            output_key: 输出键名
        """
        step = ChainStep(
            step_id=step_id,
            step_type=ChainStepType.TRANSFORM,
            transform_func=transform_func,
            output_key=output_key or f"{step_id}_result"
        )
        self.steps.append(step)
        print(f"  ➕ 添加转换步骤: {step_id}")
    
    async def execute(
        self, 
        tool_manager: ToolManager, 
        initial_input: str, 
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        执行工具链
        
        Args:
            tool_manager: 工具管理器
            initial_input: 初始输入
            context: 执行上下文
            
        Returns:
            执行结果
        """
        context = context or {}
        context["input"] = initial_input
        context.update(self.variables)
        
        print(f"🔗 开始执行工具链: {self.name}")
        print(f"   输入: {initial_input[:100]}...")
        
        execution_log = []
        
        for i, step in enumerate(self.steps, 1):
            try:
                print(f"  步骤 {i}: {step.step_id} ({step.step_type.value})")
                
                if step.step_type == ChainStepType.TOOL_CALL:
                    result = await self._execute_tool_step(step, tool_manager, context)
                    
                elif step.step_type == ChainStepType.TRANSFORM:
                    result = await self._execute_transform_step(step, context)
                    
                elif step.step_type == ChainStepType.CONDITION:
                    result = await self._execute_condition_step(step, context)
                    
                else:
                    result = f"不支持的步骤类型: {step.step_type}"
                
                # 记录执行结果
                if step.output_key:
                    context[step.output_key] = result
                
                execution_log.append({
                    "step_id": step.step_id,
                    "step_type": step.step_type.value,
                    "result": result[:200] if isinstance(result, str) else str(result)[:200],
                    "success": True
                })
                
                print(f"    ✅ 完成，结果长度: {len(str(result))} 字符")
                
            except Exception as e:
                error_msg = f"步骤 {step.step_id} 执行失败: {str(e)}"
                print(f"    ❌ {error_msg}")
                
                execution_log.append({
                    "step_id": step.step_id,
                    "step_type": step.step_type.value,
                    "error": error_msg,
                    "success": False
                })
                
                # 根据错误处理策略决定是否继续
                if step.error_handling == "stop":
                    context["error"] = error_msg
                    break
                elif step.error_handling == "continue":
                    context[step.output_key] = f"[错误] {error_msg}"
                    continue
        
        # 构建最终结果
        final_result = {
            "chain_name": self.name,
            "success": "error" not in context,
            "context": context,
            "execution_log": execution_log
        }
        
        # 获取最后一个成功步骤的结果作为主要输出
        if self.steps and self.steps[-1].output_key in context:
            final_result["output"] = context[self.steps[-1].output_key]
        
        print(f"🎉 工具链 '{self.name}' 执行完成")
        return final_result
    
    async def _execute_tool_step(
        self, 
        step: ChainStep, 
        tool_manager: ToolManager, 
        context: Dict[str, Any]
    ) -> str:
        """执行工具调用步骤"""
        # 解析输入模板
        try:
            tool_input = step.input_template.format(**context)
        except KeyError as e:
            raise ValueError(f"模板变量 {e} 未找到")
        
        # 解析工具参数（支持JSON格式）
        try:
            # 尝试解析为JSON参数
            if tool_input.strip().startswith('{'):
                params = json.loads(tool_input)
                result = await tool_manager.call_tool(step.tool_name, **params)
            else:
                # 简单字符串参数，尝试推断参数名
                result = await self._call_tool_with_string_input(
                    tool_manager, step.tool_name, tool_input
                )
        except json.JSONDecodeError:
            # 不是JSON格式，作为简单参数处理
            result = await self._call_tool_with_string_input(
                tool_manager, step.tool_name, tool_input
            )
        
        return result
    
    async def _call_tool_with_string_input(
        self, 
        tool_manager: ToolManager, 
        tool_name: str, 
        input_str: str
    ) -> str:
        """
        使用字符串输入调用工具（自动推断参数）
        """
        if tool_name not in tool_manager.tools:
            raise ValueError(f"工具 {tool_name} 不存在")
        
        tool_info = tool_manager.tools[tool_name]
        params = tool_info["parameters"]
        
        # 简单的参数推断逻辑
        if len(params) == 1:
            # 只有一个参数，直接使用
            param_name = list(params.keys())[0]
            return await tool_manager.call_tool(tool_name, **{param_name: input_str})
        
        elif len(params) == 2 and "query" in params and "kb_id" in params:
            # 企业知识库搜索的特殊处理
            return await tool_manager.call_tool(
                tool_name, 
                query=input_str, 
                kb_id="default"  # 可以从上下文获取
            )
        
        else:
            # 多参数情况，需要更复杂的解析
            raise ValueError(f"工具 {tool_name} 需要明确的参数格式")
    
    async def _execute_transform_step(
        self, 
        step: ChainStep, 
        context: Dict[str, Any]
    ) -> Any:
        """执行数据转换步骤"""
        if step.transform_func:
            return step.transform_func(context)
        return context
    
    async def _execute_condition_step(
        self, 
        step: ChainStep, 
        context: Dict[str, Any]
    ) -> bool:
        """执行条件判断步骤"""
        if step.condition_func:
            return step.condition_func(context)
        return True


class ToolChainManager:
    """
    工具链管理器 - 管理和执行预定义的工具链
    """
    
    def __init__(self, tool_manager: ToolManager):
        """
        初始化工具链管理器
        
        Args:
            tool_manager: 工具管理器实例
        """
        self.tool_manager = tool_manager
        self.chains: Dict[str, ToolChain] = {}
        self.categories: Dict[str, List[str]] = {}
        
        print("🔗 工具链管理器初始化完成")
    
    def register_chain(self, chain: ToolChain):
        """
        注册工具链
        
        Args:
            chain: 工具链实例
        """
        self.chains[chain.name] = chain
        
        # 按分类组织
        if chain.category not in self.categories:
            self.categories[chain.category] = []
        self.categories[chain.category].append(chain.name)
        
        print(f"✅ 工具链 '{chain.name}' 已注册到分类 '{chain.category}'")
    
    async def execute_chain(
        self, 
        chain_name: str, 
        input_data: str, 
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        执行指定的工具链
        
        Args:
            chain_name: 工具链名称
            input_data: 输入数据
            context: 执行上下文
            
        Returns:
            执行结果
        """
        if chain_name not in self.chains:
            return {
                "success": False,
                "error": f"工具链 '{chain_name}' 不存在",
                "available_chains": list(self.chains.keys())
            }
        
        chain = self.chains[chain_name]
        return await chain.execute(self.tool_manager, input_data, context)
    
    def list_chains(self, category: str = None) -> List[Dict[str, str]]:
        """
        列出所有工具链
        
        Args:
            category: 可选的分类过滤
            
        Returns:
            工具链列表
        """
        chains = []
        
        for name, chain in self.chains.items():
            if category is None or chain.category == category:
                chains.append({
                    "name": name,
                    "description": chain.description,
                    "category": chain.category,
                    "steps_count": len(chain.steps)
                })
        
        return chains
    
    def get_categories(self) -> Dict[str, List[str]]:
        """获取所有分类和对应的工具链"""
        return self.categories.copy()
    
    def match_chain_by_pattern(self, user_input: str) -> Optional[str]:
        """
        根据用户输入匹配合适的工具链
        
        Args:
            user_input: 用户输入
            
        Returns:
            匹配的工具链名称，如果没有匹配则返回None
        """
        user_input_lower = user_input.lower()
        
        # 定义匹配模式
        patterns = {
            "weather_info": [r"天气", r"气温", r"下雨", r"晴天", r"阴天"],
            "location_weather": [r".*地.*天气", r".*市.*天气"],
            "knowledge_search": [r"查询.*文档", r"搜索.*资料", r"找.*信息"],
            "comprehensive_research": [r"分析.*趋势", r"研究.*发展", r"调研.*情况"]
        }
        
        for chain_name, pattern_list in patterns.items():
            if chain_name in self.chains:
                for pattern in pattern_list:
                    if re.search(pattern, user_input_lower):
                        return chain_name
        
        return None