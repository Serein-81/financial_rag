# app/agent_framework/tools/hybrid_manager.py

"""
混合工具管理器 - 智能路由工具链和Agent执行
"""

from typing import Dict, Any, Optional, List, AsyncGenerator, TYPE_CHECKING
import re
import time
import logging
from .tool_chain import ToolChainManager, ToolChain
from .tool_manager import ToolManager

if TYPE_CHECKING:
    from ..core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ExecutionMode:
    """执行模式"""
    CHAIN = "chain"          # 工具链模式
    AGENT = "agent"          # 智能Agent模式
    HYBRID = "hybrid"        # 混合模式


class HybridToolManager:
    """
    混合工具管理器
    
    智能路由用户请求到合适的执行方式：
    - 标准化场景 -> 工具链
    - 复杂场景 -> 智能Agent
    - 混合场景 -> 工具链+Agent
    """
    
    def __init__(
        self, 
        tool_manager: ToolManager, 
        agent: Optional['BaseAgent'] = None,
        enable_fallback: bool = True
    ):
        """
        初始化混合工具管理器
        
        Args:
            tool_manager: 基础工具管理器
            agent: 智能Agent实例
            enable_fallback: 是否启用降级机制
        """
        self.tool_manager = tool_manager
        self.agent = agent
        self.enable_fallback = enable_fallback
        
        # 初始化工具链管理器
        self.chain_manager = ToolChainManager(tool_manager)
        
        # 执行统计
        self.execution_stats = {
            "chain_executions": 0,
            "agent_executions": 0,
            "hybrid_executions": 0,
            "fallback_executions": 0
        }
        
        print("🔀 混合工具管理器初始化完成")
        self._register_default_chains()
    
    def _register_default_chains(self):
        """注册默认的工具链"""
        # 1. 天气查询工具链
        weather_chain = self._create_weather_chain()
        self.chain_manager.register_chain(weather_chain)
        
        # 2. 位置+天气组合查询
        location_weather_chain = self._create_location_weather_chain()
        self.chain_manager.register_chain(location_weather_chain)
        
        # 3. 企业知识库搜索链
        knowledge_chain = self._create_knowledge_search_chain()
        self.chain_manager.register_chain(knowledge_chain)
        
        # 4. 综合研究工具链
        research_chain = self._create_comprehensive_research_chain()
        self.chain_manager.register_chain(research_chain)
        
        logger.info(f"已注册 {len(self.chain_manager.chains)} 个默认工具链")
    
    def _create_weather_chain(self) -> ToolChain:
        """创建天气查询工具链"""
        chain = ToolChain(
            name="weather_info",
            description="快速获取城市天气信息",
            category="weather"
        )
        
        chain.add_tool_step(
            step_id="get_weather",
            tool_name="get_weather",
            input_template='{input}',  # 修复：移除多余的引号
            output_key="weather_result"
        )
        
        return chain
    
    def _create_location_weather_chain(self) -> ToolChain:
        """创建位置+天气组合查询链"""
        chain = ToolChain(
            name="location_weather",
            description="获取地址信息并查询当地天气",
            category="weather"
        )
        
        # 步骤1: 获取位置信息
        chain.add_tool_step(
            step_id="get_location",
            tool_name="get_location_info",
            input_template='{input}',  # 修复
            output_key="location_result",
            error_handling="continue"
        )
        
        # 步骤2: 基于位置查询天气
        chain.add_tool_step(
            step_id="get_weather",
            tool_name="get_weather", 
            input_template='{input}',  # 修复
            output_key="weather_result"
        )
        
        # 步骤3: 合并结果
        def combine_results(context):
            location = context.get("location_result", "未知位置")
            weather = context.get("weather_result", "天气信息获取失败")
            return f"位置信息：{location}\n\n天气信息：{weather}"
        
        chain.add_transform_step(
            step_id="combine_info",
            transform_func=combine_results,
            output_key="final_result"
        )
        
        return chain
    
    def _create_knowledge_search_chain(self) -> ToolChain:
        """创建企业知识库搜索链"""
        chain = ToolChain(
            name="knowledge_search",
            description="企业知识库文档搜索和整理",
            category="knowledge"
        )
        
        chain.add_tool_step(
            step_id="search_docs",
            tool_name="search_enterprise_knowledge",
            input_template='{input}',  # 修复
            output_key="search_result"
        )
        
        # 添加结果格式化
        def format_search_result(context):
            result = context.get("search_result", "")
            if "未找到相关内容" in result:
                return "📋 搜索结果：暂未找到相关文档内容，建议：\n1. 尝试使用不同的关键词\n2. 检查知识库是否包含相关文档\n3. 联系管理员确认文档状态"
            else:
                return f"📋 企业知识库搜索结果：\n\n{result}\n\n💡 如需更多信息，请尝试更具体的搜索关键词。"
        
        chain.add_transform_step(
            step_id="format_result",
            transform_func=format_search_result,
            output_key="formatted_result"
        )
        
        return chain
    
    def _create_comprehensive_research_chain(self) -> ToolChain:
        """创建综合研究工具链"""
        chain = ToolChain(
            name="comprehensive_research",
            description="综合信息研究：企业知识库+网络搜索",
            category="research"
        )
        
        # 步骤1: 搜索企业知识库
        chain.add_tool_step(
            step_id="internal_search",
            tool_name="search_enterprise_knowledge",
            input_template='{input}',  # 修复
            output_key="internal_result",
            error_handling="continue"
        )
        
        # 步骤2: 网络搜索补充
        chain.add_tool_step(
            step_id="web_search",
            tool_name="search_web",
            input_template='{input}',  # 修复
            output_key="web_result",
            error_handling="continue"
        )
        
        # 步骤3: 综合分析
        def comprehensive_analysis(context):
            internal = context.get("internal_result", "")
            web = context.get("web_result", "")
            
            analysis = "📊 综合研究报告\n\n"
            
            # 内部资料部分
            if "未找到相关内容" not in internal:
                analysis += "🏢 企业内部资料：\n"
                analysis += internal[:500] + ("..." if len(internal) > 500 else "")
                analysis += "\n\n"
            
            # 外部信息部分
            if web and "错误" not in web:
                analysis += "🌐 外部信息补充：\n"
                analysis += web[:500] + ("..." if len(web) > 500 else "")
                analysis += "\n\n"
            
            analysis += "💡 建议：结合内外部信息，建议进一步深入了解相关细节。"
            
            return analysis
        
        chain.add_transform_step(
            step_id="analyze_results",
            transform_func=comprehensive_analysis,
            output_key="final_analysis"
        )
        
        return chain
    
    async def process_request(
        self, 
        user_input: str, 
        context: Dict[str, Any] = None,
        preferred_mode: str = None
    ) -> Dict[str, Any]:
        """
        处理用户请求，智能选择执行方式
        
        Args:
            user_input: 用户输入
            context: 请求上下文
            preferred_mode: 首选执行模式
            
        Returns:
            处理结果
        """
        start_time = time.time()
        context = context or {}
        
        print(f"🔀 处理请求: {user_input[:50]}...")
        
        # 1. 确定执行模式
        execution_mode = preferred_mode or self._determine_execution_mode(user_input)
        
        print(f"   选择执行模式: {execution_mode}")
        
        try:
            if execution_mode == ExecutionMode.CHAIN:
                result = await self._execute_chain_mode(user_input, context)
                self.execution_stats["chain_executions"] += 1
                
            elif execution_mode == ExecutionMode.AGENT:
                result = await self._execute_agent_mode(user_input, context)
                self.execution_stats["agent_executions"] += 1
                
            elif execution_mode == ExecutionMode.HYBRID:
                result = await self._execute_hybrid_mode(user_input, context)
                self.execution_stats["hybrid_executions"] += 1
                
            else:
                raise ValueError(f"不支持的执行模式: {execution_mode}")
        
        except Exception as e:
            print(f"❌ 执行失败: {str(e)}")
            
            # 降级处理
            if self.enable_fallback and execution_mode != ExecutionMode.AGENT:
                print("🔄 启用降级机制，切换到Agent模式")
                result = await self._execute_agent_mode(user_input, context)
                self.execution_stats["fallback_executions"] += 1
                result["fallback_used"] = True
            else:
                result = {
                    "success": False,
                    "error": str(e),
                    "execution_mode": execution_mode
                }
        
        # 添加执行元信息
        result["execution_time"] = round(time.time() - start_time, 2)
        result["execution_mode"] = execution_mode
        
        return result
    
    def _determine_execution_mode(self, user_input: str) -> str:
        """
        智能确定执行模式
        
        Args:
            user_input: 用户输入
            
        Returns:
            执行模式
        """
        user_input_lower = user_input.lower()
        
        # 1. 检查是否匹配预定义工具链
        matched_chain = self.chain_manager.match_chain_by_pattern(user_input)
        if matched_chain:
            print(f"   匹配到工具链: {matched_chain}")
            return ExecutionMode.CHAIN
        
        # 2. 简单模式判断规则
        simple_patterns = [
            r"^.{1,20}天气",           # 简单天气查询
            r"^.{1,20}在哪里",         # 简单位置查询
            r"^查询.{1,30}$",          # 简单查询
        ]
        
        for pattern in simple_patterns:
            if re.search(pattern, user_input_lower):
                return ExecutionMode.CHAIN
        
        # 3. 复杂模式判断
        complex_patterns = [
            r"分析.*并.*",             # 需要分析和组合
            r"比较.*和.*",             # 需要比较
            r"如何.*以及.*",           # 复杂问题
            r"详细.*解释.*",           # 需要详细解释
        ]
        
        for pattern in complex_patterns:
            if re.search(pattern, user_input_lower):
                return ExecutionMode.AGENT
        
        # 4. 混合模式判断
        hybrid_patterns = [
            r".*趋势.*发展",           # 趋势分析
            r".*研究.*情况",           # 研究类问题
            r".*调研.*分析",           # 调研分析
        ]
        
        for pattern in hybrid_patterns:
            if re.search(pattern, user_input_lower):
                return ExecutionMode.HYBRID
        
        # 5. 默认使用Agent模式
        return ExecutionMode.AGENT
    
    async def _execute_chain_mode(
        self, 
        user_input: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行工具链模式"""
        # 匹配合适的工具链
        chain_name = self.chain_manager.match_chain_by_pattern(user_input)
        
        if not chain_name:
            # 尝试默认的知识搜索链
            chain_name = "knowledge_search"
        
        result = await self.chain_manager.execute_chain(chain_name, user_input, context)
        
        # 安全地格式化输出
        formatted_output = "工具链执行完成，但未获得预期结果。"
        success = False
        
        if isinstance(result, dict):
            success = result.get("success", False)
            
            if success and "output" in result:
                formatted_output = result["output"]
            elif "context" in result and isinstance(result["context"], dict):
                context_data = result["context"]
                if "final_result" in context_data:
                    formatted_output = context_data["final_result"]
                elif "formatted_result" in context_data:
                    formatted_output = context_data["formatted_result"]
        else:
            # 如果result不是字典，尝试将其转换为字符串
            formatted_output = str(result) if result else "工具链执行完成，但返回了无效的结果格式。"
        
        return {
            "success": success,
            "output": formatted_output,
            "chain_used": chain_name,
            "execution_log": result.get("execution_log", []) if isinstance(result, dict) else []
        }
    
    async def _execute_agent_mode(
        self, 
        user_input: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行智能Agent模式"""
        if not self.agent:
            raise ValueError("Agent未配置，无法使用Agent模式")
        
        # 从上下文提取历史记录
        history = context.get("history", [])
        kb_id = context.get("kb_id", "default")
        user_id = context.get("user_id")
        tenant_id = context.get("tenant_id")
        
        # 调用Agent
        agent_result = await self.agent.run(
            user_input=user_input,
            history=history,
            kb_id=kb_id,
            user_id=user_id,
            tenant_id=tenant_id
        )
        
        return {
            "success": True,
            "output": agent_result,
            "agent_used": self.agent.__class__.__name__
        }
    
    async def _execute_hybrid_mode(
        self, 
        user_input: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行混合模式"""
        # 先尝试工具链获取基础信息
        try:
            chain_result = await self._execute_chain_mode(user_input, context)
            base_info = chain_result.get("output", "")
        except Exception:
            # 工具链失败时继续使用Agent模式
            base_info = ""
        
        # 然后使用Agent进行深度分析
        enhanced_input = f"基于以下信息进行深度分析：\n{base_info}\n\n原始问题：{user_input}"
        
        agent_result = await self._execute_agent_mode(enhanced_input, context)
        
        return {
            "success": True,
            "output": agent_result["output"],
            "base_info": base_info,
            "hybrid_approach": "chain_then_agent"
        }
    
    async def stream_process_request(
        self, 
        user_input: str, 
        context: Dict[str, Any] = None,
        preferred_mode: str = None
    ) -> AsyncGenerator[str, None]:
        """
        流式处理请求
        
        Args:
            user_input: 用户输入
            context: 请求上下文
            preferred_mode: 首选执行模式
            
        Yields:
            逐步生成的内容
        """
        context = context or {}
        execution_mode = preferred_mode or self._determine_execution_mode(user_input)
        
        yield f"🔀 选择执行模式: {execution_mode}\n\n"
        
        if execution_mode == ExecutionMode.AGENT and self.agent:
            # Agent模式支持流式输出
            history = context.get("history", [])
            kb_id = context.get("kb_id", "default")
            
            async for chunk in self.agent.stream_run(
                user_input=user_input,
                history=history,
                kb_id=kb_id
            ):
                yield chunk
        else:
            # 工具链模式，一次性输出结果
            result = await self.process_request(user_input, context, execution_mode)
            yield result.get("output", "处理完成")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取执行统计信息"""
        total = sum(self.execution_stats.values())
        
        stats = self.execution_stats.copy()
        stats["total_executions"] = total
        
        if total > 0:
            stats["chain_percentage"] = round(stats["chain_executions"] / total * 100, 1)
            stats["agent_percentage"] = round(stats["agent_executions"] / total * 100, 1)
            stats["hybrid_percentage"] = round(stats["hybrid_executions"] / total * 100, 1)
            stats["fallback_percentage"] = round(stats["fallback_executions"] / total * 100, 1)
        
        return stats
    
    def list_available_chains(self) -> List[Dict[str, str]]:
        """列出可用的工具链"""
        return self.chain_manager.list_chains()
    
    def get_chain_categories(self) -> Dict[str, List[str]]:
        """获取工具链分类"""
        return self.chain_manager.get_categories()