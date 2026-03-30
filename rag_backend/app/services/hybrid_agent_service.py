# app/services/hybrid_agent_service.py

"""
混合Agent服务 - 集成工具链和智能Agent的企业级服务

支持：
- 智能路由：自动选择工具链或Agent执行
- 工具链执行：高性能的预定义工作流
- Agent执行：复杂问题的智能推理
- 混合模式：工具链+Agent的组合执行
"""

import os
from typing import List, Dict, AsyncGenerator, Optional
from app.core.config import settings

# 导入自定义 Agent 框架
from app.agent_framework import ReActAgent, ZhipuAdapter
from app.agent_framework.tools import (
    ToolManager, 
    LangChainCompatLayer,
    HybridToolManager,
    ExecutionMode
)

# 导入现有的工具
from app.tools import get_all_tools

# 导入提示词加载器（已从简单版升级到高级版）
from app.services.prompt_service import load_agent_system_prompt


class HybridEnterpriseAgentService:
    """
    混合企业级Agent服务
    
    集成工具链和智能Agent，提供：
    - 智能执行模式选择
    - 高性能工具链执行
    - 复杂问题智能推理
    - 流式和非流式输出
    - 执行统计和监控
    """
    
    def __init__(self, use_hybrid: bool = True):
        """
        初始化混合Agent服务
        
        Args:
            use_hybrid: 是否启用混合模式
        """
        self.use_hybrid = use_hybrid
        
        print("=" * 60)
        print("🚀 混合企业级Agent服务初始化")
        print("=" * 60)
        
        if use_hybrid:
            self._init_hybrid_framework()
        else:
            # 降级到原有的Agent框架
            from .agent_service import agent_service
            self.fallback_service = agent_service
        
        print("✅ 混合Agent服务初始化完成！")
        print("=" * 60)
    
    def _init_hybrid_framework(self):
        """初始化混合框架"""
        print("🔀 使用混合Agent框架")
        
        # 1. 初始化 LLM 适配器
        self.llm_adapter = ZhipuAdapter(
            api_key=settings.ZHIPU_API_KEY,
            model_name="glm-4-flash"
        )
        
        # 2. 初始化工具管理器
        self.tool_manager = ToolManager()
        
        # 3. 注册现有的 LangChain 工具
        langchain_tools = get_all_tools()
        compat_layer = LangChainCompatLayer(self.tool_manager)
        compat_layer.register_langchain_tools(langchain_tools)
        
        # 4. 加载系统提示词
        system_prompt = load_agent_system_prompt()
        
        # 5. 创建 ReAct Agent
        self.agent = ReActAgent(
            llm_adapter=self.llm_adapter,
            tool_manager=self.tool_manager,
            system_prompt=system_prompt,
            max_iterations=10,
            timeout=300.0,
            # 启用循环检测和早停
            similarity_threshold=0.7,
            max_consecutive_failures=3,
            early_stop_enabled=True
        )
        
        # 6. 创建混合工具管理器
        self.hybrid_manager = HybridToolManager(
            tool_manager=self.tool_manager,
            agent=self.agent,
            enable_fallback=True
        )
        
        print(f"🛠️ 已注册 {len(self.tool_manager.tools)} 个工具")
        print(f"🔗 已注册 {len(self.hybrid_manager.list_available_chains())} 个工具链")
        
        # 显示工具链信息
        chains = self.hybrid_manager.list_available_chains()
        for i, chain in enumerate(chains, 1):
            print(f"   {i}. {chain['name']}: {chain['description']}")
    
    async def chat(
        self, 
        user_input: str, 
        kb_id: str, 
        session_id: str = None, 
        history: list = None,
        preferred_mode: str = None
    ) -> str:
        """
        非流式对话
        
        Args:
            user_input: 用户输入
            kb_id: 知识库ID
            session_id: 会话ID
            history: 对话历史
            preferred_mode: 首选执行模式 (chain/agent/hybrid)
            
        Returns:
            Agent 回答
        """
        if not self.use_hybrid:
            return await self.fallback_service.chat(user_input, kb_id, session_id, history)
        
        return await self._chat_hybrid(user_input, kb_id, session_id, history, preferred_mode)
    
    async def chat_stream(
        self, 
        user_input: str, 
        kb_id: str, 
        session_id: str, 
        history: list,
        preferred_mode: str = None
    ) -> AsyncGenerator[str, None]:
        """
        流式对话
        
        Args:
            user_input: 用户输入
            kb_id: 知识库ID
            session_id: 会话ID
            history: 对话历史
            preferred_mode: 首选执行模式
            
        Yields:
            逐步生成的内容
        """
        if not self.use_hybrid:
            async for chunk in self.fallback_service.chat_stream(user_input, kb_id, session_id, history):
                yield chunk
            return
        
        async for chunk in self._chat_stream_hybrid(user_input, kb_id, session_id, history, preferred_mode):
            yield chunk
    
    async def _chat_hybrid(
        self, 
        user_input: str, 
        kb_id: str, 
        session_id: str, 
        history: list,
        preferred_mode: str = None
    ) -> str:
        """混合框架的非流式对话"""
        print(f"🔀 [混合框架] 开始处理: {user_input[:50]}...")
        
        # 构建上下文
        context = {
            "kb_id": kb_id,
            "session_id": session_id,
            "history": self._format_history_for_hybrid(history)
        }
        
        try:
            # 使用混合管理器处理请求
            result = await self.hybrid_manager.process_request(
                user_input=user_input,
                context=context,
                preferred_mode=preferred_mode
            )
            
            if result["success"]:
                output = result["output"]
                execution_mode = result.get("execution_mode", "unknown")
                execution_time = result.get("execution_time", 0)
                
                print(f"✅ [混合框架] 处理完成")
                print(f"   执行模式: {execution_mode}")
                print(f"   执行时间: {execution_time}s")
                print(f"   回答长度: {len(output)}")
                
                return output
            else:
                error_msg = result.get("error", "未知错误")
                print(f"❌ [混合框架] 处理失败: {error_msg}")
                return f"抱歉，处理过程中出现错误：{error_msg}"
        
        except Exception as e:
            print(f"❌ [混合框架] 异常: {str(e)}")
            return f"抱歉，处理过程中出现异常：{str(e)}"
    
    async def _chat_stream_hybrid(
        self, 
        user_input: str, 
        kb_id: str, 
        session_id: str, 
        history: list,
        preferred_mode: str = None
    ) -> AsyncGenerator[str, None]:
        """混合框架的流式对话"""
        print(f"🌊 [混合框架] 开始流式处理: {user_input[:50]}...")
        
        # 构建上下文
        context = {
            "kb_id": kb_id,
            "session_id": session_id,
            "history": self._format_history_for_hybrid(history)
        }
        
        try:
            # 使用混合管理器流式处理
            async for chunk in self.hybrid_manager.stream_process_request(
                user_input=user_input,
                context=context,
                preferred_mode=preferred_mode
            ):
                yield chunk
            
            print(f"✅ [混合框架] 流式处理完成")
        
        except Exception as e:
            print(f"❌ [混合框架] 流式处理失败: {str(e)}")
            yield f"\n[处理错误: {str(e)}]"
    
    def _format_history_for_hybrid(self, history: list) -> List[Dict]:
        """
        将历史记录转换为混合框架格式
        
        Args:
            history: 原始历史记录
            
        Returns:
            格式化后的历史记录
        """
        if not history:
            return []
        
        formatted = []
        for msg in history:
            if hasattr(msg, 'content'):
                # LangChain 消息对象
                if hasattr(msg, 'type'):
                    role = "user" if msg.type == "human" else "assistant"
                else:
                    role = "assistant"  # 默认
                
                formatted.append({
                    "role": role,
                    "content": msg.content
                })
            elif isinstance(msg, dict):
                # 字典格式
                formatted.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        return formatted
    
    def get_agent_info(self) -> Dict:
        """
        获取Agent信息
        
        Returns:
            Agent信息字典
        """
        if not self.use_hybrid:
            return self.fallback_service.get_agent_info()
        
        base_info = {
            "framework": "hybrid",
            "agent_type": self.agent.__class__.__name__,
            "llm_model": self.llm_adapter.model_name,
            "tools_count": len(self.tool_manager.tools),
            "chains_count": len(self.hybrid_manager.list_available_chains()),
            "max_iterations": self.agent.max_iterations,
            "timeout": self.agent.timeout,
            "early_stop_enabled": self.agent.early_stop_enabled
        }
        
        # 添加执行统计
        stats = self.hybrid_manager.get_statistics()
        base_info.update(stats)
        
        return base_info
    
    def get_available_chains(self) -> List[Dict[str, str]]:
        """
        获取可用的工具链列表
        
        Returns:
            工具链列表
        """
        if not self.use_hybrid:
            return []
        
        return self.hybrid_manager.list_available_chains()
    
    def get_chain_categories(self) -> Dict[str, List[str]]:
        """
        获取工具链分类
        
        Returns:
            分类字典
        """
        if not self.use_hybrid:
            return {}
        
        return self.hybrid_manager.get_chain_categories()
    
    def get_execution_statistics(self) -> Dict[str, any]:
        """
        获取执行统计信息
        
        Returns:
            统计信息
        """
        if not self.use_hybrid:
            return {"hybrid_enabled": False}
        
        stats = self.hybrid_manager.get_statistics()
        stats["hybrid_enabled"] = True
        
        return stats
    
    async def execute_chain_directly(
        self, 
        chain_name: str, 
        input_data: str, 
        context: Dict[str, any] = None
    ) -> Dict[str, any]:
        """
        直接执行指定的工具链
        
        Args:
            chain_name: 工具链名称
            input_data: 输入数据
            context: 执行上下文
            
        Returns:
            执行结果
        """
        if not self.use_hybrid:
            return {"error": "混合模式未启用"}
        
        return await self.hybrid_manager.chain_manager.execute_chain(
            chain_name, input_data, context
        )


# 创建全局实例
# 可以通过环境变量控制是否使用混合框架
USE_HYBRID_FRAMEWORK = os.getenv("USE_HYBRID_AGENT", "true").lower() == "true"

hybrid_agent_service = HybridEnterpriseAgentService(use_hybrid=USE_HYBRID_FRAMEWORK)