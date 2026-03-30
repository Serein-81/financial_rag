# app/services/agent_service.py

"""
企业级 Agent 服务 - 自定义框架版本

使用自定义 Agent 框架替代 LangChain，提供更好的可控性和学习价值
集成企业记忆系统，支持长期对话记忆和上下文管理
支持工具路由：本地工具（数据库/RAG）和 MCP 远程工具（计算类）
"""

import os
import json
from typing import List, Dict, AsyncGenerator
from app.core.config import settings

# 导入自定义 Agent 框架
from app.agent_framework import ReActAgent, ToolManager, ZhipuAdapter
from app.agent_framework.tools import LangChainCompatLayer

# 导入现有的工具
from app.tools import get_all_tools

# 导入提示词加载器（已从简单版升级到高级版）
from app.services.prompt_service import load_agent_system_prompt

# 🆕 导入智能路由和统一检索
from app.services.unified_retriever import unified_retriever
from app.services.smart_router import is_greeting_query

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
        
        # 3. 注册本地工具
        from app.tools import get_tool_system_instruction
        langchain_tools = get_all_tools()
        compat_layer = LangChainCompatLayer(self.tool_manager)
        compat_layer.register_langchain_tools(langchain_tools)
        
        # 4. 注册 MCP 工具（异步）
        import asyncio
        try:
            from app.mcp.mcp_tool_proxy import get_all_mcp_tools_as_langchain_tools
            loop = asyncio.get_event_loop()
            if loop.is_running():
                mcp_tools = asyncio.create_task(get_all_mcp_tools_as_langchain_tools())
            else:
                mcp_tools = loop.run_until_complete(get_all_mcp_tools_as_langchain_tools())
            
            if asyncio.iscoroutine(mcp_tools):
                mcp_tools = loop.run_until_complete(mcp_tools)
            
            if mcp_tools:
                compat_layer.register_langchain_tools(mcp_tools)
                print(f"☁️ 已注册 {len(mcp_tools)} 个 MCP 远程工具")
        except Exception as e:
            print(f"⚠️ MCP 工具注册失败: {e}")
        
        # 5. 加载系统提示词并添加工具使用策略
        system_prompt = load_agent_system_prompt()
        tool_instruction = get_tool_system_instruction()
        system_prompt = system_prompt + "\n\n" + tool_instruction
        
        # 6. 创建 ReAct Agent
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
            tool_type = "📍本地" if tool_info.get("type") == "langchain" else "☁️MCP"
            print(f"   {i}. [{tool_type}] {tool_name}: {tool_info['description'][:40]}...")
    
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

        # 问候语检测 - 跳过所有检索，直接回答
        if is_greeting_query(user_input):
            print("💬 [问候语检测] 跳过 RAG 和记忆系统，直接调用 LLM")
            
            greeting_system_prompt = """你是一个友好的AI助手。用户向你问好时，请只回复一句简短、热情的问候语。

要求：
1. 绝对不要提及任何"知识库"、"文档"、"资料"、"企业"等词汇
2. 不要列出任何期刊、论文、文档名称
3. 只回复一句简单的问候，如"你好！很高兴见到你。"
4. 如果用户说"你是谁"，回复"我是你的AI助手，很高兴为你服务。"
5. 回复要简短，不要超过20个字

用户消息：""" + user_input
            
            result = await self.llm_adapter.chat(
                messages=[
                    {"role": "system", "content": greeting_system_prompt},
                    {"role": "user", "content": user_input}
                ],
                stream=False
            )
            return result
            
        # 🆕 第一步：先使用统一检索器（自动智能路由），提取外部知识
        try:
            retrieval_result = await unified_retriever.retrieve(
                query=user_input,
                kb_id=kb_id,
                session_id=session_id or "default_session",
                user_id=user_id or "default_user",
                top_k=5,
                enable_routing=True
            )

            kb_context = retrieval_result["combined_context"]
            route_mode = retrieval_result["mode"]

        except Exception as e:
            print(f"⚠️ [统一检索] 失败: {e}")
            kb_context = ""
            route_mode = "FALLBACK"

        # 🧠 第二步：获取记忆管理器
        memory_manager = None
        memory_context = ""
        if session_id and user_id:
            memory_manager = self._get_memory_manager(session_id, user_id)
            memory_context = await memory_manager.get_formatted_context(
                query=user_input,
                max_tokens=1500,
                knowledge_context=kb_context,
                system_instructions=f"当前检索模式：{route_mode}。如需调用search_enterprise_knowledge工具，请传入知识库ID：{kb_id}"
            )

            # 构建完上下文后，再将用户消息持久化到记忆系统
            await memory_manager.add_message("user", user_input)

            print(f"🧠 [记忆系统] 获取增强上下文: {len(memory_context)} 字符")
        else:
            memory_manager = None
            memory_context = ""
            print("⚠️ [记忆系统] 缺少session_id或user_id，跳过记忆系统")

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
        
        # 问候语检测 - 跳过所有检索，直接流式回答
        if is_greeting_query(user_input):
            print("💬 [问候语检测] 跳过 RAG 和记忆系统，直接调用 LLM")
            
            greeting_system_prompt = """你是一个友好的AI助手。用户向你问好时，请只回复一句简短、热情的问候语。

要求：
1. 绝对不要提及任何"知识库"、"文档"、"资料"、"企业"等词汇
2. 不要列出任何期刊、论文、文档名称
3. 只回复一句简单的问候，如"你好！很高兴见到你。"
4. 如果用户说"你是谁"，回复"我是你的AI助手，很高兴为你服务。"
5. 回复要简短，不要超过20个字

用户消息：""" + user_input
            
            messages = [
                {"role": "system", "content": greeting_system_prompt},
                {"role": "user", "content": user_input}
            ]
            
            # 非流式调用，然后模拟流式输出
            response = await self.llm_adapter.chat(messages, stream=False)
            full_text = response.content if hasattr(response, 'content') else str(response)
            
            # 模拟流式输出（每次yield一小段）
            for i in range(0, len(full_text), 10):
                yield full_text[i:i+10]
            return
        
        # 🆕 第一步：使用统一检索器获取外部知识（包括 sources）
        rag_results = []
        try:
            retrieval_result = await unified_retriever.retrieve(
                query=user_input,
                kb_id=kb_id,
                session_id=session_id or "default_session",
                user_id=user_id or "default_user",
                top_k=5,
                enable_routing=True
            )
            rag_results = retrieval_result.get("rag_results", [])
            kb_context = retrieval_result.get("combined_context", "")
            route_mode = retrieval_result.get("mode", "HYBRID")
            print(f"📊 [检索模式] {route_mode}，获取到 {len(rag_results)} 条 RAG 结果")
        except Exception as e:
            print(f"⚠️ [统一检索] 失败: {e}")
            kb_context = ""
            route_mode = "FALLBACK"
        
        # 🆕 在流式开始前，先发送 sources 信息
        if rag_results:
            sources_data = [
                {
                    "filename": res.source_file,
                    "score": res.score,
                    "content": res.content[:200] + "..." if len(res.content) > 200 else res.content
                }
                for res in rag_results
            ]
            yield f"__SOURCES__:{json.dumps(sources_data, ensure_ascii=False)}"
        
        # 🧠 获取记忆管理器
        if session_id and user_id:
            memory_manager = self._get_memory_manager(session_id, user_id)

            # 🔧 Bug1修复：先构建上下文（检索历史记忆），再保存当次消息
            # 避免当次输入被立刻存入情景记忆后又被检索出来，造成自引用
            memory_context = await memory_manager.get_formatted_context(
                query=user_input,
                max_tokens=1500
            )

            # 构建完上下文后，再将用户消息持久化到记忆系统
            await memory_manager.add_message("user", user_input)

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