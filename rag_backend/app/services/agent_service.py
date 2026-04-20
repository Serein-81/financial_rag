# app/services/agent_service.py

"""
企业级 Agent 服务 - 自定义框架版本

使用自定义 Agent 框架替代 LangChain，提供更好的可控性和学习价值
集成企业记忆系统，支持长期对话记忆和上下文管理
支持工具路由：本地工具（数据库/RAG）和 MCP 远程工具（计算类）
"""

import os
from app.utils.json_compat import json
import asyncio
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional

logger = logging.getLogger(__name__)

ENABLE_INIT_LOGGING = os.getenv("ENABLE_INIT_LOGGING", "false").lower() == "true"

def _log_init(*args, **kwargs):
    """条件初始化日志"""
    if ENABLE_INIT_LOGGING:
        print(*args, **kwargs)

from app.core.config import settings
from app.core.exceptions import (
    ServiceException,
    LLMServiceException,
    ValidationException
)


class _SingletonMeta(type):
    """
    单例元类
    
    确保一个类只有一个实例，并提供全局访问点
    """
    _instances: Dict[type, Any] = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
    
    @classmethod
    def reset_instance(cls, target_cls: type) -> None:
        """重置单例实例（主要用于测试）"""
        if target_cls in cls._instances:
            del cls._instances[target_cls]

# 导入自定义 Agent 框架
from app.agent_framework import ReActAgent, ToolManager
from app.agent_framework.tools import LangChainCompatLayer

# 导入现有的工具
from app.tools import get_all_tools

# 导入统一提示词加载器

# 🆕 导入智能路由和统一检索
from app.services.unified_retriever import unified_retriever
from app.services.smart_router import is_greeting_query

# 🆕 导入提示词管理
from app.prompts import load_greeting_prompt

# 导入输出格式化工具
from app.utils.output_formatter import output_formatter

# 🧠 导入企业记忆系统
from app.memory_system import MemoryManager

# 📊 导入监控服务
from app.services.monitor_service import monitor_service
 

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
        
        _log_init("=" * 60)
        _log_init("企业级 Agent 服务初始化")
        _log_init("=" * 60)
        
        if use_custom_framework:
            self._init_custom_framework()
        else:
            self._init_langchain_framework()
        
        _log_init("Agent 服务初始化完成！")
        _log_init("=" * 60)
    
    def _init_custom_framework(self):
        """
        初始化自定义框架
        """
        print("使用自定义 Agent 框架")
        
        default_provider = settings.get_llm_provider_for_agent("chat")
        print(f"[SETUP] [Agent服务] 默认智能体使用 LLM: {default_provider}")
        
        from app.agent_framework.llm.factory import LLMAdapterFactory
        self.llm_adapter = LLMAdapterFactory.create_adapter(default_provider)
        
        # 2. 初始化工具管理器
        self.tool_manager = ToolManager()
        
        # 3. 注册本地工具
        langchain_tools = get_all_tools()
        compat_layer = LangChainCompatLayer(self.tool_manager)
        compat_layer.register_langchain_tools(langchain_tools)
        
        # 4. 注册 MCP 工具（异步）
        mcp_tools = []
        try:
            from app.mcp.mcp_tool_proxy import get_all_mcp_tools_as_langchain_tools
            
            try:
                loop = asyncio.get_running_loop()
                logger.warning(
                    "在异步环境中调用AgentService.__init__，跳过MCP工具注册。"
                    "如需MCP工具，请使用 await initialize_mcp_tools(self) 单独初始化。"
                )
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                mcp_tools = loop.run_until_complete(get_all_mcp_tools_as_langchain_tools())
                loop.close()
            
            if mcp_tools and isinstance(mcp_tools, list):
                compat_layer.register_langchain_tools(mcp_tools)
                print(f"[CLOUD] 已注册 {len(mcp_tools)} 个 MCP 远程工具")
            elif mcp_tools:
                try:
                    mcp_tools_list = list(mcp_tools)
                    if mcp_tools_list:
                        compat_layer.register_langchain_tools(mcp_tools_list)
                        print(f"[CLOUD] 已注册 {len(mcp_tools_list)} 个 MCP 远程工具")
                except (TypeError, AttributeError) as e:
                    logger.warning(f"MCP 工具列表转换失败: {e}")
        except ImportError as e:
            print(f"[WARNING] MCP工具模块导入失败，跳过MCP工具注册: {e}")
        except RuntimeError as e:
            print(f"[WARNING] 异步运行时错误(MCP工具): {e}")
        except (ValueError, KeyError) as e:
            print(f"[WARNING] MCP 工具注册数据错误: {e}")
        except (OSError, IOError) as e:
            print(f"[WARNING] MCP 工具注册IO错误: {e}")
        except Exception as e:
            print(f"[WARNING] MCP 工具注册失败: {e}")
        
        # 5. 创建 ReAct Agent（使用结构化提示词系统）
        # agent_name="react" 会让 Agent 从 app/prompts/agents/react/system.md 加载提示词
        # 通过 PromptEngine 动态渲染变量和条件
        self.agent = ReActAgent(
            llm_adapter=self.llm_adapter,
            tool_manager=self.tool_manager,
            agent_name="react",
            max_iterations=10,
            timeout=300.0
        )
        
        print(f"[TOOL] 已注册 {len(self.tool_manager.tools)} 个工具:")
        for i, tool_name in enumerate(self.tool_manager.get_tool_names(), 1):
            tool_info = self.tool_manager.tools[tool_name]
            tool_type = "[LOCAL]" if tool_info.get("type") == "langchain" else "[MCP]"
            print(f"   {i}. [{tool_type}] {tool_name}: {tool_info['description'][:40]}...")
    
    async def initialize_mcp_tools_async(self) -> int:
        """
        异步初始化 MCP 工具
        
        如果在异步环境中创建了 AgentService，可以使用此方法单独初始化 MCP 工具。
        
        Returns:
            注册的 MCP 工具数量
        """
        if not hasattr(self, 'tool_manager') or not hasattr(self, 'llm_adapter'):
            logger.error("AgentService 未正确初始化，无法注册 MCP 工具")
            return 0
        
        try:
            from app.mcp.mcp_tool_proxy import get_all_mcp_tools_as_langchain_tools
            from app.agent_framework.tools import LangChainCompatLayer
            
            compat_layer = LangChainCompatLayer(self.tool_manager)
            mcp_tools = await get_all_mcp_tools_as_langchain_tools()
            
            if mcp_tools and isinstance(mcp_tools, list):
                compat_layer.register_langchain_tools(mcp_tools)
                print(f"[CLOUD] [异步] 已注册 {len(mcp_tools)} 个 MCP 远程工具")
                return len(mcp_tools)
            else:
                logger.warning("MCP 工具列表为空")
                return 0
        except ImportError as e:
            logger.warning(f"MCP 工具模块导入失败: {e}")
            return 0
        except Exception as e:
            logger.error(f"MCP 工具异步初始化失败: {e}")
            return 0
    
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
            print(f"[MEMORY] 创建新的记忆管理器: session={session_id[:8]}..., user={user_id}")
            self.memory_managers[session_id] = MemoryManager(session_id, user_id)
        
        return self.memory_managers[session_id]
    
    def _init_langchain_framework(self):
        """
        初始化 LangChain 框架（备用方案）
        """
        print("使用 LangChain 框架")
        
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
        print(f"[START] [自定义框架] 开始处理: {user_input[:50]}...")

        # 问候语检测 - 跳过所有检索，直接回答
        if is_greeting_query(user_input):
            print("[CHAT] [问候语检测] 跳过 RAG 和记忆系统，直接调用 LLM")
            
            from app.agent_framework.llm.specialist_llm_router import SpecialistLLMRouter
            greeting_adapter = SpecialistLLMRouter.get_greeting_adapter()
            print(f"[CHAT] [问候语检测] 使用模型: {greeting_adapter.model_name}")
            
            greeting_system_prompt = """你是一个友好的AI助手。用户向你问好时，请只回复一句简短、热情的问候语。

要求：
1. 绝对不要提及任何"知识库"、"文档"、"资料"、"企业"等词汇
2. 不要列出任何期刊、论文、文档名称
3. 只回复一句简单的问候，如"你好！很高兴见到你。"
4. 如果用户说"你是谁"，回复"我是你的AI助手，很高兴为你服务。"
5. 回复要简短，不要超过20个字

用户消息：""" + user_input
            
            async with monitor_service.trace_agent(
                user_id=user_id or "anonymous",
                query=user_input,
                kb_id=kb_id,
                session_id=session_id
            ) as trace:
                result = await greeting_adapter.chat(
                    messages=[
                        {"role": "system", "content": greeting_system_prompt},
                        {"role": "user", "content": user_input}
                    ],
                    stream=False
                )
                trace.set_result(result)
            return result.content if hasattr(result, 'content') else str(result)
            
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

        except ValidationException as e:
            print(f"[WARNING] [统一检索] 验证失败: {e}")
            kb_context = ""
            route_mode = "FALLBACK"
        except ServiceException as e:
            print(f"[WARNING] [统一检索] 服务异常: {e}")
            kb_context = ""
            route_mode = "FALLBACK"
        except (ValueError, KeyError) as e:
            print(f"[WARNING] [统一检索] 数据错误: {e}")
            kb_context = ""
        except (OSError, IOError) as e:
            print(f"[WARNING] [统一检索] IO错误: {e}")
            kb_context = ""
        except Exception as e:
            print(f"[WARNING] [统一检索] 失败: {e}")
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

            print(f"[MEMORY] [记忆系统] 获取增强上下文: {len(memory_context)} 字符")
        else:
            memory_manager = None
            memory_context = ""
            print("[WARNING] [记忆系统] 缺少session_id或user_id，跳过记忆系统")

        # 🆕 构建增强的用户输入 - 包含RAG上下文和记忆上下文
        # 提示：RAG上下文优先级高于记忆上下文，因为来自知识库文档
        # 注意：使用 XML 格式标记，OutputFormatter 会自动清理
        
        # 构建增强输入（知识库状态已通过模板条件渲染处理）
        if kb_context and kb_context.strip() and kb_context != '（无相关文档）':
            # 知识库有内容时的正常流程
            enhanced_input = f"""用户问题：{user_input}

<InternalContext>
<KnowledgeBase>
{kb_context}
</KnowledgeBase>

<MemoryContext>
{memory_context if memory_context else '（无相关记忆）'}
</MemoryContext>

<SystemInstructions>
1. 请优先使用上述知识库文档回答问题
2. 如果知识库没有相关信息，再参考记忆上下文
3. 如需调用 search_enterprise_knowledge 工具，请务必传入知识库ID：{kb_id}
4. 如果知识库和记忆都没有相关信息，请直接回答"我不知道"，不要编造答案
</SystemInstructions>
</InternalContext>"""
        else:
            # 知识库无内容时，仅提供用户问题和记忆上下文
            # 关于工具使用的指令已在模板中通过条件渲染自动加载
            enhanced_input = f"""用户问题：{user_input}

<InternalContext>
<MemoryContext>
{memory_context if memory_context else '（无相关记忆）'}
</MemoryContext>

<SystemInstructions>
请基于用户问题和记忆上下文回答
</SystemInstructions>
</InternalContext>"""

        # 不再使用手动历史记录，改用记忆系统的上下文
        formatted_history = []

        try:
            async with monitor_service.trace_agent(
                user_id=user_id or "anonymous",
                query=user_input,
                kb_id=kb_id,
                session_id=session_id
            ) as trace:
                # 调用自定义 Agent
                result = await self.agent.run(
                    user_input=enhanced_input,
                    history=formatted_history,
                    kb_id=kb_id
                )
                
                # 确保结果是字符串
                if result is None:
                    result = "抱歉，未能获取到有效回答。"
                elif not isinstance(result, str):
                    result = str(result)
                
                # 记录回答到监控
                trace.set_result(result)

            # 🧠 将AI回答添加到记忆系统
            if memory_manager and result:
                await memory_manager.add_message("assistant", result)
                print("[MEMORY] [记忆系统] 已保存AI回答")

            print(f"[OK] [自定义框架] 处理完成，回答长度: {len(result)}")
            return result

        except LLMServiceException as e:
            print(f"[ERROR] [自定义框架] LLM服务异常: {e}")
            return "抱歉，AI服务暂时不可用，请稍后再试。"
        except ValidationException as e:
            print(f"[ERROR] [自定义框架] 输入验证失败: {e}")
            return f"抱歉，输入参数验证失败：{str(e)}"
        except ServiceException as e:
            print(f"[ERROR] [自定义框架] 服务异常: {e}")
            return f"抱歉，服务处理失败：{str(e)}"
        except (ValueError, KeyError) as e:
            print(f"[ERROR] [自定义框架] 数据错误: {str(e)}")
            return f"抱歉，数据处理错误：{str(e)}"
        except (OSError, IOError) as e:
            print(f"[ERROR] [自定义框架] IO错误: {str(e)}")
            return f"抱歉，IO处理错误：{str(e)}"
        except Exception as e:
            print(f"[ERROR] [自定义框架] 处理失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"抱歉，处理过程中出现错误：{str(e)}"
    
    async def _chat_stream_custom(self, user_input: str, kb_id: str, session_id: str, history: list, user_id: str) -> AsyncGenerator[str, None]:
        """
        自定义框架的流式对话（集成记忆系统）
        """
        print(f"[STREAM] [自定义框架] 开始流式处理: {user_input[:50]}...")
        
        # 问候语检测 - 跳过所有检索，直接流式回答
        if is_greeting_query(user_input):
            print("[CHAT] [问候语检测] 跳过 RAG 和记忆系统，直接调用 LLM")
            
            from app.agent_framework.llm.specialist_llm_router import SpecialistLLMRouter
            greeting_adapter = SpecialistLLMRouter.get_greeting_adapter()
            print(f"[CHAT] [问候语检测] 使用模型: {greeting_adapter.model_name}")
            
            greeting_system_prompt = load_greeting_prompt()
            
            messages = [
                {"role": "system", "content": greeting_system_prompt},
                {"role": "user", "content": user_input}
            ]
            
            response = await greeting_adapter.chat(messages, stream=False)
            full_text = response.content if hasattr(response, 'content') else str(response)
            
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
            print(f"[STATS] [检索模式] {route_mode}，获取到 {len(rag_results)} 条 RAG 结果")
        except ValidationException as e:
            print(f"[WARNING] [统一检索] 验证失败: {e}")
            kb_context = ""
            route_mode = "FALLBACK"
        except ServiceException as e:
            print(f"[WARNING] [统一检索] 服务异常: {e}")
            kb_context = ""
            route_mode = "FALLBACK"
        except (ValueError, KeyError) as e:
            print(f"[WARNING] [统一检索] 数据错误: {e}")
            kb_context = ""
        except (OSError, IOError) as e:
            print(f"[WARNING] [统一检索] IO错误: {e}")
            kb_context = ""
        except Exception as e:
            print(f"[WARNING] [统一检索] 失败: {e}")
            kb_context = ""
            route_mode = "FALLBACK"
        
        # 🆕 在流式开始前，先发送 sources 信息
        # 使用特殊标记让 chat.py 可以识别并单独处理
        if rag_results:
            sources_data = [
                {
                    "filename": res.source_file,
                    "score": res.score,
                    "content": res.content[:200] + "..." if len(res.content) > 200 else res.content
                }
                for res in rag_results
            ]
            yield f"__SOURCES_EVENT__:{json.dumps(sources_data, ensure_ascii=False)}"
        
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

            print(f"[MEMORY] [记忆系统] 获取上下文: {len(memory_context)} 字符")
        else:
            memory_manager = None
            memory_context = ""
            print("[WARNING] [记忆系统] 缺少session_id或user_id，跳过记忆系统")
        
        # 🆕 构建增强的用户输入 - 包含RAG上下文和记忆上下文
        # 提示：RAG上下文优先级高于记忆上下文，因为来自知识库文档
        # 注意：使用 XML 格式标记，OutputFormatter 会自动清理
        
        # 构建增强输入（知识库状态已通过模板条件渲染处理）
        if kb_context and kb_context.strip() and kb_context != '（无相关文档）':
            # 知识库有内容时的正常流程
            enhanced_input = f"""用户问题：{user_input}

<InternalContext>
<KnowledgeBase>
{kb_context}
</KnowledgeBase>

<MemoryContext>
{memory_context if memory_context else '（无相关记忆）'}
</MemoryContext>

<SystemInstructions>
1. 请优先使用上述知识库文档回答问题
2. 如果知识库没有相关信息，再参考记忆上下文
3. 如需调用 search_enterprise_knowledge 工具，请务必传入知识库ID：{kb_id}
4. 如果知识库和记忆都没有相关信息，请直接回答"我不知道"，不要编造答案
</SystemInstructions>
</InternalContext>"""
        else:
            # 知识库无内容时，仅提供用户问题和记忆上下文
            # 关于工具使用的指令已在模板中通过条件渲染自动加载
            enhanced_input = f"""用户问题：{user_input}

<InternalContext>
<MemoryContext>
{memory_context if memory_context else '（无相关记忆）'}
</MemoryContext>

<SystemInstructions>
请基于用户问题和记忆上下文回答
</SystemInstructions>
</InternalContext>"""

        # 不再使用手动历史记录
        formatted_history = []
        
        # 用于收集完整回答
        full_response = ""
        
        try:
            async with monitor_service.trace_agent(
                user_id=user_id or "anonymous",
                query=user_input,
                kb_id=kb_id,
                session_id=session_id
            ) as trace:
                # 调用自定义 Agent 的流式方法
                # 注意：需要将 context 作为 kwargs 传递，让 ReAct Agent 的系统提示词能正确使用
                async for chunk in self.agent.stream_run(
                    user_input=user_input,  # 只传原始问题，不要包含上下文的 enhanced_input
                    history=formatted_history,
                    kb_id=kb_id,
                    context=enhanced_input  # 将上下文作为 kwargs 传递
                ):
                    # 对每个 chunk 进行实时清理，移除内部标记
                    cleaned_chunk = output_formatter.clean_stream_chunk(chunk)
                    full_response += cleaned_chunk
                    # 输出清理后的内容
                    if cleaned_chunk:
                        yield cleaned_chunk
                # 记录回答到监控（使用清理后的完整内容）
                trace.set_result(full_response)
            
            # 🧠 将完整的AI回答添加到记忆系统（使用深度清理后的内容）
            if memory_manager and full_response:
                # 对完整回答进行深度清理后再保存
                cleaned_full_response = output_formatter.clean_stream_content(full_response)
                if cleaned_full_response != full_response:
                    print(f"[FORMAT] [OutputFormatter] 深度清理完成 | 原始: {len(full_response)} → 清理后: {len(cleaned_full_response)}")
                    full_response = cleaned_full_response
                await memory_manager.add_message("assistant", full_response)
                print("[MEMORY] [记忆系统] 已保存AI回答")
            
            print("[OK] [自定义框架] 流式处理完成")
            
        except LLMServiceException as e:
            print(f"[ERROR] [自定义框架] 流式处理LLM服务异常: {e}")
            yield output_formatter.format_error_answer("AI服务暂时不可用，请稍后再试。")
        except ValidationException as e:
            print(f"[ERROR] [自定义框架] 流式处理输入验证失败: {e}")
            yield output_formatter.format_error_answer(f"输入参数验证失败：{str(e)}")
        except ServiceException as e:
            print(f"[ERROR] [自定义框架] 流式处理服务异常: {e}")
            yield output_formatter.format_error_answer(f"服务处理失败：{str(e)}")
        except (ValueError, KeyError) as e:
            print(f"[ERROR] [自定义框架] 流式处理数据错误: {str(e)}")
            yield output_formatter.format_error_answer(f"数据处理错误：{str(e)}")
        except (OSError, IOError) as e:
            print(f"[ERROR] [自定义框架] 流式处理IO错误: {str(e)}")
            yield output_formatter.format_error_answer(f"IO处理错误：{str(e)}")
        except Exception as e:
            print(f"[ERROR] [自定义框架] 流式处理失败: {str(e)}")
            yield output_formatter.format_error_answer(str(e))
    
    async def _chat_langchain(self, user_input: str, kb_id: str, session_id: str, history: list, user_id: str) -> str:
        """
        LangChain 框架的非流式对话（备用）
        """
        print(f"[LANGCHAIN] 开始处理: {user_input[:50]}...")
        
        # 调用原有的 LangChain 实现
        # 这里需要根据原有实现调整
        pass
    
    async def _chat_stream_langchain(self, user_input: str, kb_id: str, session_id: str, history: list, user_id: str) -> AsyncGenerator[str, None]:
        """
        LangChain 框架的流式对话（备用）
        """
        print(f"[LANGCHAIN] 开始流式处理: {user_input[:50]}...")
        
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


def get_agent_service(use_custom_framework: bool = None) -> EnterpriseAgentService:
    """
    获取 Agent 服务单例实例（依赖注入函数）
    
    推荐使用此函数获取 Agent 服务，而不是直接导入 agent_service 变量
    
    Args:
        use_custom_framework: 是否强制使用自定义框架（可选，默认使用环境变量配置）
        
    Returns:
        EnterpriseAgentService 单例实例
        
    Example:
        ```python
        from app.services.agent_service import get_agent_service
        
        async def my_endpoint():
            agent = get_agent_service()
            result = await agent.chat(...)
        ```
    """
    global _agent_service_instance
    
    if _agent_service_instance is None:
        if use_custom_framework is None:
            use_custom_framework = os.getenv("USE_CUSTOM_AGENT", "true").lower() == "true"
        _agent_service_instance = EnterpriseAgentService(use_custom_framework=use_custom_framework)
    
    return _agent_service_instance


def reset_agent_service() -> None:
    """
    重置 Agent 服务单例实例
    
    主要用于测试或需要重新初始化 Agent 服务的场景
    
    Warning:
        调用此函数后，之前的 agent_service 引用将变为无效
    """
    global _agent_service_instance
    _agent_service_instance = None
    _SingletonMeta.reset_instance(EnterpriseAgentService)


def create_agent_service_dependency():
    """
    创建 FastAPI 依赖注入函数
    
    Returns:
        FastAPI 依赖函数
        
    Example:
        ```python
        from fastapi import Depends
        from app.services.agent_service import create_agent_service_dependency
        
        get_agent = create_agent_service_dependency()
        
        @app.post("/chat")
        async def chat_endpoint(agent: EnterpriseAgentService = Depends(get_agent)):
            ...
        ```
    """
    
    async def _get_agent_service() -> EnterpriseAgentService:
        return get_agent_service()
    
    return _get_agent_service


_agent_service_instance: Optional[EnterpriseAgentService] = None

USE_CUSTOM_FRAMEWORK = os.getenv("USE_CUSTOM_AGENT", "true").lower() == "true"
agent_service = get_agent_service(use_custom_framework=USE_CUSTOM_FRAMEWORK)