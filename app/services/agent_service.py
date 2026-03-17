# app/services/agent_service.py

"""
企业级 Agent 服务 - 自定义框架版本

使用自定义 Agent 框架替代 LangChain，提供更好的可控性和学习价值
集成企业记忆系统，支持长期对话记忆和上下文管理
"""

import os
from typing import List, Dict, AsyncGenerator
from app.core.config import settings

# 导入自定义 Agent 框架
from app.agent_framework import ReActAgent, ToolManager, ZhipuAdapter
from app.agent_framework.tools import LangChainCompatLayer

# 导入现有的工具
from app.tools import get_all_tools

# 导入提示词加载器
from app.utils.prompt_loader import load_agent_system_prompt

# 🆕 导入智能路由和统一检索
from app.services.unified_retriever import unified_retriever

# 🧠 导入企业记忆系统
from app.memory_system import MemoryManager


class EnterpriseAgentService:
    """
    企业级 Agent 服务
    
    基于自定义框架的 Agent 实现，支持：
    - ReAct 推理模式
    - 工具调用
    - 流式输出
    - LangChain 工具兼容
    - 🧠 企业记忆系统集成
    """
    
    def __init__(self, use_custom_framework: bool = True):
        """
        初始化 Agent 服务
        
        Args:
            use_custom_framework: 是否使用自定义框架（True）还是 LangChain（False）
        """
        self.use_custom_framework = use_custom_framework
        
        # 🧠 初始化记忆管理器字典 (session_id -> MemoryManager)
        self.memory_managers: Dict[str, MemoryManager] = {}
        
        print("=" * 60)
        print("🧠 企业级 Agent 服务初始化")
        print("=" * 60)
        
        if use_custom_framework:
            self._init_custom_framework()
        else:
            self._init_langchain_framework()
        
        print("✅ Agent 服务初始化完成！")
        print("=" * 60)
    
    def _init_custom_framework(self):
        """
        初始化自定义框架
        """
        print("🎯 使用自定义 Agent 框架")
        
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
            timeout=300.0
        )
        
        print(f"🛠️ 已注册 {len(self.tool_manager.tools)} 个工具:")
        for i, tool_name in enumerate(self.tool_manager.get_tool_names(), 1):
            tool_info = self.tool_manager.tools[tool_name]
            print(f"   {i}. {tool_name}: {tool_info['description'][:50]}...")
    
    def _get_memory_manager(self, session_id: str, user_id: str) -> MemoryManager:
        """
        获取或创建记忆管理器
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
            
        Returns:
            记忆管理器实例
        """
        if session_id not in self.memory_managers:
            print(f"🧠 创建新的记忆管理器: session={session_id[:8]}..., user={user_id}")
            self.memory_managers[session_id] = MemoryManager(session_id, user_id)
        
        return self.memory_managers[session_id]
    
    def _init_langchain_framework(self):
        """
        初始化 LangChain 框架（备用方案）
        """
        print("🔗 使用 LangChain 框架")
        
        # 导入原有的 LangChain 实现
        from .agent_service_langchain import EnterpriseAgentService as LangChainAgentService
        
        # 创建 LangChain Agent 实例
        langchain_service = LangChainAgentService()
        self.agent = langchain_service.agent
        self.llm = langchain_service.llm
        self.tools = langchain_service.tools
    
    async def chat(self, user_input: str, kb_id: str, session_id: str = None, history: list = None, user_id: str = None) -> str:
        """
        非流式对话（集成记忆系统）
        
        Args:
            user_input: 用户输入
            kb_id: 知识库ID
            session_id: 会话ID
            history: 对话历史（已废弃，使用记忆系统替代）
            user_id: 用户ID
            
        Returns:
            Agent 回答
        """
        if self.use_custom_framework:
            return await self._chat_custom(user_input, kb_id, session_id, history, user_id)
        else:
            return await self._chat_langchain(user_input, kb_id, session_id, history, user_id)
    
    async def chat_stream(self, user_input: str, kb_id: str, session_id: str, history: list, user_id: str = None) -> AsyncGenerator[str, None]:
        """
        流式对话（集成记忆系统）
        
        Args:
            user_input: 用户输入
            kb_id: 知识库ID
            session_id: 会话ID
            history: 对话历史（已废弃，使用记忆系统替代）
            user_id: 用户ID
            
        Yields:
            逐步生成的内容
        """
        if self.use_custom_framework:
            async for chunk in self._chat_stream_custom(user_input, kb_id, session_id, history, user_id):
                yield chunk
        else:
            async for chunk in self._chat_stream_langchain(user_input, kb_id, session_id, history, user_id):
                yield chunk
    
    async def _chat_custom(self, user_input: str, kb_id: str, session_id: str, history: list, user_id: str) -> str:
        """
        自定义框架的非流式对话（集成智能路由和记忆系统）
        """
        print(f"🎯 [自定义框架] 开始处理: {user_input[:50]}...")
        
        # 🧠 获取记忆管理器
        if session_id and user_id:
            memory_manager = self._get_memory_manager(session_id, user_id)
            
            # 添加用户消息到记忆系统
            await memory_manager.add_message("user", user_input)
            
            # 从记忆系统获取增强的上下文（使用新的上下文构建器）
            memory_context = await memory_manager.get_formatted_context(
                query=user_input,
                max_tokens=1500,  # 控制上下文长度
                knowledge_context=kb_context,
                system_instructions=f"当前检索模式：{route_mode}。如需调用search_enterprise_knowledge工具，请传入知识库ID：{kb_id}"
            )
            
            print(f"🧠 [记忆系统] 获取增强上下文: {len(memory_context)} 字符")
        else:
            memory_manager = None
            memory_context = ""
            print("⚠️ [记忆系统] 缺少session_id或user_id，跳过记忆系统")
        
        # 🆕 使用统一检索器（自动智能路由）
        try:
            # 调用统一检索器
            retrieval_result = await unified_retriever.retrieve(
                query=user_input,
                kb_id=kb_id,
                session_id=session_id or "default_session",
                user_id=user_id or "default_user",
                top_k=5,
                enable_routing=True  # 启用智能路由
            )
            
            # 获取合并后的上下文
            kb_context = retrieval_result["combined_context"]
            route_mode = retrieval_result["mode"]
            
            print(f"📊 [检索模式] {route_mode}")
            
        except Exception as e:
            print(f"⚠️ [统一检索] 失败，使用默认模式: {e}")
            kb_context = ""
            route_mode = "FALLBACK"
        
        # 构建增强的用户输入（简化版，主要逻辑已在上下文构建器中）
        enhanced_input = f"""用户问题：{user_input}

{memory_context}

请基于以上上下文信息回答用户问题。"""
        
        # 不再使用手动历史记录，改用记忆系统的上下文
        formatted_history = []
        
        try:
            # 调用自定义 Agent
            result = await self.agent.run(
                user_input=enhanced_input,
                history=formatted_history,
                kb_id=kb_id
            )
            
            # 🧠 将AI回答添加到记忆系统
            if memory_manager:
                await memory_manager.add_message("assistant", result)
                print(f"🧠 [记忆系统] 已保存AI回答")
            
            print(f"✅ [自定义框架] 处理完成，回答长度: {len(result)}")
            return result
            
        except Exception as e:
            print(f"❌ [自定义框架] 处理失败: {str(e)}")
            return f"抱歉，处理过程中出现错误：{str(e)}"
    
    async def _chat_stream_custom(self, user_input: str, kb_id: str, session_id: str, history: list, user_id: str) -> AsyncGenerator[str, None]:
        """
        自定义框架的流式对话（集成记忆系统）
        """
        print(f"🌊 [自定义框架] 开始流式处理: {user_input[:50]}...")
        
        # 🧠 获取记忆管理器
        if session_id and user_id:
            memory_manager = self._get_memory_manager(session_id, user_id)
            
            # 添加用户消息到记忆系统
            await memory_manager.add_message("user", user_input)
            
            # 从记忆系统获取上下文
            memory_context = await memory_manager.get_formatted_context(
                query=user_input,
                max_tokens=1500
            )
            
            print(f"🧠 [记忆系统] 获取上下文: {len(memory_context)} 字符")
        else:
            memory_manager = None
            memory_context = ""
            print("⚠️ [记忆系统] 缺少session_id或user_id，跳过记忆系统")
        
        # 构建增强的用户输入
        enhanced_input = f"""用户问题：{user_input}

【记忆上下文】
{memory_context}

【系统指令】：
1. 如需调用 search_enterprise_knowledge 工具，请务必传入知识库ID：{kb_id}
2. 请优先使用上述记忆上下文回答问题
3. 记忆上下文包含了用户的历史对话和重要信息，请充分利用"""
        
        # 不再使用手动历史记录
        formatted_history = []
        
        # 用于收集完整回答
        full_response = ""
        
        try:
            # 调用自定义 Agent 的流式方法
            async for chunk in self.agent.stream_run(
                user_input=enhanced_input,
                history=formatted_history,
                kb_id=kb_id
            ):
                full_response += chunk
                yield chunk
            
            # 🧠 将完整的AI回答添加到记忆系统
            if memory_manager and full_response:
                await memory_manager.add_message("assistant", full_response)
                print(f"🧠 [记忆系统] 已保存AI回答")
            
            print(f"✅ [自定义框架] 流式处理完成")
            
        except Exception as e:
            print(f"❌ [自定义框架] 流式处理失败: {str(e)}")
            yield f"\n[处理错误: {str(e)}]"
    
    async def _chat_langchain(self, user_input: str, kb_id: str, session_id: str, history: list, user_id: str) -> str:
        """
        LangChain 框架的非流式对话（备用）
        """
        print(f"🔗 [LangChain] 开始处理: {user_input[:50]}...")
        
        # 调用原有的 LangChain 实现
        # 这里需要根据原有实现调整
        pass
    
    async def _chat_stream_langchain(self, user_input: str, kb_id: str, session_id: str, history: list, user_id: str) -> AsyncGenerator[str, None]:
        """
        LangChain 框架的流式对话（备用）
        """
        print(f"🌊 [LangChain] 开始流式处理: {user_input[:50]}...")
        
        # 调用原有的 LangChain 实现
        # 这里需要根据原有实现调整
        yield "LangChain 备用模式暂未实现"
    
    def _format_history_for_custom(self, history: list) -> List[Dict]:
        """
        将历史记录转换为自定义框架格式
        
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
        获取 Agent 信息
        
        Returns:
            Agent 信息字典
        """
        if self.use_custom_framework:
            return {
                "framework": "custom",
                "agent_type": self.agent.__class__.__name__,
                "llm_model": self.llm_adapter.model_name,
                "tools_count": len(self.tool_manager.tools),
                "max_iterations": self.agent.max_iterations,
                "timeout": self.agent.timeout,
                "memory_sessions": len(self.memory_managers),
                "memory_enabled": True
            }
        else:
            return {
                "framework": "langchain",
                "agent_type": "LangChain Agent",
                "llm_model": "glm-4-flash",
                "tools_count": len(getattr(self, 'tools', [])),
                "memory_sessions": len(self.memory_managers),
                "memory_enabled": True
            }


# 创建全局实例
# 可以通过环境变量控制使用哪个框架
USE_CUSTOM_FRAMEWORK = os.getenv("USE_CUSTOM_AGENT", "true").lower() == "true"

agent_service = EnterpriseAgentService(use_custom_framework=USE_CUSTOM_FRAMEWORK)