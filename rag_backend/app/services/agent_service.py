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
from app.core.config import settings

logger = logging.getLogger(__name__)

ENABLE_INIT_LOGGING = settings.STARTUP_VERBOSE or os.getenv("ENABLE_INIT_LOGGING", "false").lower() == "true"

def _log_init(*args, **kwargs):
    """条件初始化日志"""
    if ENABLE_INIT_LOGGING:
        print(*args, **kwargs)

from app.core.exceptions import (
    ServiceException,
    LLMServiceException,
    ValidationException
)


class _AgenticLLMBridge:
    """把 BaseLLMAdapter 适配成 Agentic 节点期望的 ``generate(prompt, max_tokens) -> str``。

    RetrievalPlanner / ResultEvaluator 约定 llm_service.generate 返回纯文本字符串，
    而底层适配器返回 LLMResponse 对象，这里做一层薄封装。
    """

    def __init__(self, adapter):
        self._adapter = adapter

    async def generate(self, prompt: str, max_tokens: int = 300) -> str:
        resp = await self._adapter.generate(prompt, temperature=0.1, max_tokens=max_tokens)
        return resp.content if hasattr(resp, "content") else str(resp)


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


def _clean_stream_content_for_persistence(text: str) -> str:
    """Clean completed stream output and tolerate older formatter instances."""
    clean_stream_content = getattr(output_formatter, "clean_stream_content", None)
    if callable(clean_stream_content):
        return clean_stream_content(text)

    print("[WARNING] [OutputFormatter] clean_stream_content missing; using compatibility cleanup")
    cleaned = output_formatter.strip_react_markers_from_buffer(text)
    cleaned = output_formatter.extract_final_answer(cleaned)
    return output_formatter.clean_output(cleaned)

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
        logger.debug("使用自定义 Agent 框架")
        
        default_provider = settings.get_llm_provider_for_agent("chat")
        logger.debug(f"[SETUP] [Agent服务] 默认智能体使用 LLM: {default_provider}")
        
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
                try:
                    mcp_tools = loop.run_until_complete(get_all_mcp_tools_as_langchain_tools())
                finally:
                    loop.close()
            
            if mcp_tools and isinstance(mcp_tools, list):
                compat_layer.register_langchain_tools(mcp_tools)
                logger.info(f"已注册 {len(mcp_tools)} 个 MCP 远程工具")
            elif mcp_tools:
                try:
                    mcp_tools_list = list(mcp_tools)
                    if mcp_tools_list:
                        compat_layer.register_langchain_tools(mcp_tools_list)
                        logger.info(f"已注册 {len(mcp_tools_list)} 个 MCP 远程工具")
                except (TypeError, AttributeError) as e:
                    logger.warning(f"MCP 工具列表转换失败: {e}")
        except ImportError as e:
            logger.debug(f"MCP工具模块导入失败: {e}")
        except RuntimeError as e:
            logger.debug(f"异步运行时错误(MCP工具): {e}")
        except (ValueError, KeyError) as e:
            logger.debug(f"MCP 工具注册数据错误: {e}")
        except (OSError, IOError) as e:
            logger.debug(f"MCP 工具注册IO错误: {e}")
        except Exception as e:
            logger.debug(f"MCP 工具注册失败: {e}")
        
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
        
        logger.info(f"[TOOL] 已注册 {len(self.tool_manager.tools)} 个工具: {', '.join(self.tool_manager.get_tool_names())}")
    
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
                logger.info(f"已注册 {len(mcp_tools)} 个 MCP 远程工具")
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
    
    async def chat(self, user_input: str, kb_id: str, session_id: str = None, history: list = None, user_id: str = None, tenant_id: str = None) -> str:
        """
        非流式对话（集成记忆系统）

        Args:
            user_input: 用户输入
            kb_id: 知识库ID
            session_id: 会话ID
            history: 对话历史（已废弃，使用记忆系统替代）
            user_id: 用户ID
            tenant_id: 租户ID（用于图谱检索和租户隔离）

        Returns:
            Agent 回答
        """
        if self.use_custom_framework:
            return await self._chat_custom(user_input, kb_id, session_id, history, user_id, tenant_id)
        else:
            return await self._chat_langchain(user_input, kb_id, session_id, history, user_id)
    
    async def chat_stream(
        self,
        user_input: str,
        kb_id: str,
        session_id: str,
        history: list,
        user_id: str = None,
        tenant_id: str = None,
        retrieval_method: Optional[str] = None,
        max_iterations: Optional[int] = None,
        top_k: Optional[int] = None,
        enable_rerank: Optional[bool] = None,
        enable_graph_expansion: Optional[bool] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式对话（集成记忆系统）

        Args:
            user_input: 用户输入
            kb_id: 知识库ID
            session_id: 会话ID
            history: 对话历史（已废弃，使用记忆系统替代）
            user_id: 用户ID
            tenant_id: 租户ID（用于图谱检索）
            retrieval_method: 检索方法覆写（simple/graphrag/agentic，None 走自动路由）
            max_iterations: Agentic 最大迭代轮数（仅 agentic 生效）
            top_k: 引用片段数量（None 走默认 5）
            enable_rerank: 是否启用重排序（None 按 .env 配置）
            enable_graph_expansion: 是否启用图谱扩展（None 按默认）

        Yields:
            逐步生成的内容；额外通过 `__META_EVENT__:` 上报检索元数据
        """
        if self.use_custom_framework:
            async for chunk in self._chat_stream_custom(
                user_input, kb_id, session_id, history, user_id, tenant_id,
                retrieval_method=retrieval_method,
                max_iterations=max_iterations,
                top_k=top_k,
                enable_rerank=enable_rerank,
                enable_graph_expansion=enable_graph_expansion,
            ):
                yield chunk
        else:
            async for chunk in self._chat_stream_langchain(user_input, kb_id, session_id, history, user_id):
                yield chunk

    async def _chat_custom(self, user_input: str, kb_id: str, session_id: str, history: list, user_id: str, tenant_id: str = None) -> str:
        """
        自定义框架的非流式对话（集成智能路由、记忆系统和图谱路径推理）
        """
        print(f"[START] [自定义框架] 开始处理: {user_input[:50]}...")

        # 问候语检测 - 跳过所有检索，直接回答
        if is_greeting_query(user_input):
            logger.debug("[CHAT] [问候语检测] 跳过 RAG 和记忆系统，直接调用 LLM")
            
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
                enable_routing=True,
                tenant_id=tenant_id
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

            logger.info(f"[记忆系统] 获取增强上下文完成，字符数: {len(memory_context)}")
        else:
            memory_manager = None
            memory_context = ""
            logger.warning("[记忆系统] 缺少session_id或user_id，跳过记忆系统")

        # 🔗 图谱路径检索（"X和Y有什么关系"类问题）
        import re as _re
        graph_path_text = ""
        entity_pairs = _re.findall(r'([\u4e00-\u9fa5]{2,6})和([\u4e00-\u9fa5]{2,6})', user_input)
        if entity_pairs:
            try:
                from app.knowledge_graph.neo4j_manager import Neo4jManager as _N
                _n = _N(uri=settings.NEO4J_URI, user=settings.NEO4J_USER, password=settings.NEO4J_PASSWORD)
                if _n.driver:
                    _parts = []
                    for _s, _t in entity_pairs:
                        _paths = _n.find_path_between(source_name=_s, target_name=_t, tenant_id=tenant_id, max_depth=4)
                        if _paths:
                            _parts.append(f"{_s} ↔ {_t}：")
                            for _i, _p in enumerate(_paths[:3], 1):
                                _chain = " → ".join(f"{_e['name']}({_e['type']})" for _e in _p.get('entities', []))
                                _rels = " → ".join(_p.get('relations', []))
                                _parts.append(f"  路径{_i}: {_chain}" + (f"\n         关系: {_rels}" if _rels else ""))
                    _n.close()
                    if _parts:
                        graph_path_text = "\n".join(_parts)
                        logger.info(f"[图谱路径] 智能对话注入: {graph_path_text[:60]}...")
            except Exception as _e:
                logger.warning(f"[图谱路径] 智能对话检索失败: {_e}")

        # 🆕 构建增强的用户输入 - 包含RAG上下文 + 图谱路径 + 记忆上下文
        # 注意：使用 XML 格式标记，OutputFormatter 会自动清理

        # 构建增强输入（知识库状态已通过模板条件渲染处理）
        if kb_context and kb_context.strip() and kb_context != '（无相关文档）':
            # 知识库有内容时的正常流程
            enhanced_input = f"""用户问题：{user_input}

<InternalContext>
<KnowledgeBase>
{kb_context}
</KnowledgeBase>

<GraphPathContext>
{graph_path_text if graph_path_text else '（无相关图谱路径）'}
</GraphPathContext>

<MemoryContext>
{memory_context if memory_context else '（无相关记忆）'}
</MemoryContext>

<SystemInstructions>
0. 如果 <GraphPathContext> 包含实体关系路径，请优先用图谱路径回答"X和Y有什么关系"类问题
1. 请优先使用上述知识库文档回答问题
2. 如果知识库没有相关信息，再参考记忆上下文
3. 如需调用 search_enterprise_knowledge 工具，请务必传入知识库ID：{kb_id}
4. 请同时参考每段资料的"相似度/可回答性/证据质量"：相似度只表示语义接近，可回答性和证据质量用于判断是否足以回答用户问题
5. 如果资料标记为"缺少明确流程步骤"、"偏代码/方案片段"或"上下文不足"，不要把它当成完整答案；只能回答其中能确认的部分，并明确说明"知识库未提供完整流程/细节"
6. 只有完全没有相关信息时，才回答"我不知道"，不要编造答案
</SystemInstructions>
</InternalContext>"""
        else:
            # 知识库无内容时，仅提供用户问题和记忆上下文 + 图谱路径
            # 关于工具使用的指令已在模板中通过条件渲染自动加载
            enhanced_input = f"""用户问题：{user_input}

<InternalContext>
<MemoryContext>
{memory_context if memory_context else '（无相关记忆）'}
</MemoryContext>

<GraphPathContext>
{graph_path_text if graph_path_text else '（无相关图谱路径）'}
</GraphPathContext>

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

            # 🧠 AI回答已通过 API 层（chat.py）保存到数据库
            # 记忆系统只用于构建上下文，不存储消息

            print(f"[OK] [自定义框架] 处理完成，回答长度: {len(result)}")
            return result

        except LLMServiceException as e:
            logger.debug(f"[ERROR] [自定义框架] LLM服务异常: {e}")
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
    
    async def _chat_stream_custom(
        self,
        user_input: str,
        kb_id: str,
        session_id: str,
        history: list,
        user_id: str,
        tenant_id: str = None,
        retrieval_method: Optional[str] = None,
        max_iterations: Optional[int] = None,
        top_k: Optional[int] = None,
        enable_rerank: Optional[bool] = None,
        enable_graph_expansion: Optional[bool] = None,
    ) -> AsyncGenerator[str, None]:
        """
        自定义框架的流式对话（集成记忆系统）
        """
        print(f"[STREAM] [自定义框架] 开始流式处理: {user_input[:50]}...")
        # G3: 检索参数覆写（None 走默认）；G1/G2: 元数据收集
        _method = (retrieval_method or "").lower().strip()
        _effective_top_k = top_k if (top_k is not None and top_k > 0) else 5
        _effective_enable_rerank = True if enable_rerank is None else bool(enable_rerank)
        _effective_enable_graph = True if enable_graph_expansion is None else bool(enable_graph_expansion)
        # 迭代轮数：仅 agentic 生效，缺省 3，限制在 1-10
        _effective_max_iter = max_iterations if (max_iterations and max_iterations > 0) else 3
        _effective_max_iter = min(max(_effective_max_iter, 1), 10)
        # retrieval_method 对图谱的语义覆写：
        #   simple   → 纯向量混合检索，强制关闭图谱
        #   graphrag → 强制开启图谱
        #   agentic / 未指定 → 沿用 enable_graph_expansion 开关
        if _method == "simple":
            _effective_enable_graph = False
        elif _method == "graphrag":
            _effective_enable_graph = True
        
        # 问候语检测 - 跳过所有检索，直接流式回答
        if is_greeting_query(user_input):
            logger.debug("[CHAT] [问候语检测] 跳过 RAG 和记忆系统，直接调用 LLM")
            
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
        _agentic_history: list = []
        _agentic_evaluation = None
        try:
            if _method == "agentic":
                # Agentic RAG：多轮自主检索（plan → retrieve → evaluate → 循环 → aggregate）
                # _agentic_retrieve 为异步生成器：检索期间 yield ("progress", {...}) 实时进度，
                # 最终 yield ("result", {...})。progress 经 __PROGRESS_EVENT__ 通道透给 SSE 端点。
                retrieval_result = {}
                async for _kind, _payload in self._agentic_retrieve(
                    query=user_input,
                    kb_id=kb_id,
                    session_id=session_id or "default_session",
                    user_id=user_id or "default_user",
                    tenant_id=tenant_id,
                    max_iterations=_effective_max_iter,
                    top_k=_effective_top_k,
                    enable_rerank=_effective_enable_rerank,
                    enable_graph=_effective_enable_graph,
                ):
                    if _kind == "progress":
                        yield f"__PROGRESS_EVENT__:{json.dumps(_payload, ensure_ascii=False)}"
                    else:
                        retrieval_result = _payload
                _agentic_history = retrieval_result.get("retrieval_history", [])
                _agentic_evaluation = retrieval_result.get("evaluation")
            else:
                retrieval_result = await unified_retriever.retrieve(
                    query=user_input,
                    kb_id=kb_id,
                    session_id=session_id or "default_session",
                    user_id=user_id or "default_user",
                    top_k=_effective_top_k,
                    enable_routing=True,
                    enable_graph=_effective_enable_graph,
                    enable_rerank=_effective_enable_rerank,
                    tenant_id=tenant_id
                )
            rag_results = retrieval_result.get("rag_results", [])
            kb_context = retrieval_result.get("combined_context", "")
            route_mode = retrieval_result.get("mode", "HYBRID")
            print(f"[STATS] [检索模式] {route_mode}，获取到 {len(rag_results)} 条 RAG 结果")

            # G1/G2: 上报检索元数据给上层（chat.py SSE 端点），统一在 done 事件里合并到 meta
            _meta_payload = {
                "retrieval_method": (_method or (route_mode or "simple").lower()),
                "kb_id": kb_id,
                "top_k": _effective_top_k,
                "enable_rerank": _effective_enable_rerank,
                "enable_graph_expansion": _effective_enable_graph,
                "max_iterations": _effective_max_iter,
                # Agentic RAG 多轮检索轨迹（非 agentic 模式为空）
                "retrieval_history": _agentic_history,
                "evaluation": _agentic_evaluation,
            }
            yield f"__META_EVENT__:{json.dumps(_meta_payload, ensure_ascii=False)}"
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
        # 仅在 RAG 模式（非 MEMORY_ONLY）且检索到结果时才展示参考文档
        if rag_results and route_mode not in ("MEMORY_ONLY", "FALLBACK"):
            # 只取前 5 条，按 rerank_score 降序
            _top = sorted(
                rag_results,
                key=lambda r: r.get("rerank_score", 0) if isinstance(r, dict) else getattr(r, "rerank_score", 0),
                reverse=True
            )[:5]
            # 归一化分数到 0-100 范围（避免 rerank 原始分过低显示为 1%）
            _max_score = max(
                (r.get("rerank_score", 0) if isinstance(r, dict) else getattr(r, "rerank_score", 0))
                for r in _top
            )
            _norm = _max_score if _max_score > 0 else 1.0
            sources_data = [
                {
                    "filename": res.get("source_file", "") if isinstance(res, dict) else getattr(res, "source_file", ""),
                    "score": (res.get("rerank_score", 0) if isinstance(res, dict) else getattr(res, "rerank_score", 0)) / _norm,
                    "answerability_score": res.get("answerability_score", None) if isinstance(res, dict) else getattr(res, "answerability_score", None),
                    "evidence_flags": res.get("evidence_flags", None) if isinstance(res, dict) else getattr(res, "evidence_flags", None),
                    "content": (res.get("content", "")[:200] + "..." if isinstance(res, dict) and len(res.get("content", "")) > 200 else res.get("content", "")) if isinstance(res, dict) else ((res.content[:200] + "..." if len(res.content) > 200 else res.content) if hasattr(res, "content") else ""),
                }
                for res in _top
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

            logger.info(f"[记忆系统] 获取上下文完成，字符数: {len(memory_context)}")
        else:
            memory_manager = None
            memory_context = ""
            logger.warning("[记忆系统] 缺少session_id或user_id，跳过记忆系统")
        
        # 🔗 图谱路径检索（"X和Y有什么关系"类问题）
        import re as _re
        graph_path_text = ""
        entity_pairs = _re.findall(r'([\u4e00-\u9fa5]{2,6})和([\u4e00-\u9fa5]{2,6})', user_input)
        if entity_pairs:
            try:
                from app.knowledge_graph.neo4j_manager import Neo4jManager as _N
                _n = _N(uri=settings.NEO4J_URI, user=settings.NEO4J_USER, password=settings.NEO4J_PASSWORD)
                if _n.driver:
                    _parts = []
                    for _s, _t in entity_pairs:
                        _paths = _n.find_path_between(source_name=_s, target_name=_t, tenant_id=tenant_id, max_depth=4)
                        if _paths:
                            _parts.append(f"{_s} ↔ {_t}：")
                            for _i, _p in enumerate(_paths[:3], 1):
                                _chain = " → ".join(f"{_e['name']}({_e['type']})" for _e in _p.get('entities', []))
                                _rels = " → ".join(_p.get('relations', []))
                                _parts.append(f"  路径{_i}: {_chain}" + (f"\n         关系: {_rels}" if _rels else ""))
                    _n.close()
                    if _parts:
                        graph_path_text = "\n".join(_parts)
                        logger.info(f"[图谱路径] 智能对话注入: {graph_path_text[:60]}...")
            except Exception as _e:
                logger.warning(f"[图谱路径] 智能对话检索失败: {_e}")

        # 🆕 构建增强的用户输入 - 包含RAG上下文 + 图谱路径 + 记忆上下文
        # 注意：使用 XML 格式标记，OutputFormatter 会自动清理

        # 构建增强输入（知识库状态已通过模板条件渲染处理）
        if kb_context and kb_context.strip() and kb_context != '（无相关文档）':
            # 知识库有内容时的正常流程
            enhanced_input = f"""用户问题：{user_input}

<InternalContext>
<KnowledgeBase>
{kb_context}
</KnowledgeBase>

<GraphPathContext>
{graph_path_text if graph_path_text else '（无相关图谱路径）'}
</GraphPathContext>

<MemoryContext>
{memory_context if memory_context else '（无相关记忆）'}
</MemoryContext>

<SystemInstructions>
0. 如果 <GraphPathContext> 包含实体关系路径，请优先用图谱路径回答"X和Y有什么关系"类问题
1. 请优先使用上述知识库文档回答问题
2. 如果知识库没有相关信息，再参考记忆上下文
3. 如需调用 search_enterprise_knowledge 工具，请务必传入知识库ID：{kb_id}
4. 请同时参考每段资料的"相似度/可回答性/证据质量"：相似度只表示语义接近，可回答性和证据质量用于判断是否足以回答用户问题
5. 如果资料标记为"缺少明确流程步骤"、"偏代码/方案片段"或"上下文不足"，不要把它当成完整答案；只能回答其中能确认的部分，并明确说明"知识库未提供完整流程/细节"
6. 只有完全没有相关信息时，才回答"我不知道"，不要编造答案
</SystemInstructions>
</InternalContext>"""
        else:
            # 知识库无内容时，仅提供用户问题和记忆上下文 + 图谱路径
            # 关于工具使用的指令已在模板中通过条件渲染自动加载
            enhanced_input = f"""用户问题：{user_input}

<InternalContext>
<MemoryContext>
{memory_context if memory_context else '（无相关记忆）'}
</MemoryContext>

<GraphPathContext>
{graph_path_text if graph_path_text else '（无相关图谱路径）'}
</GraphPathContext>

<SystemInstructions>
请基于用户问题和记忆上下文回答
</SystemInstructions>
</InternalContext>"""

        # 不再使用手动历史记录
        formatted_history = []

        # 用于收集完整回答
        full_response = ""
        # 跟踪已输出的乾淨内容长度（用于缓冲区标记剥离后的增量输出）
        last_clean_output_length = 0

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

                    # 🔒 安全网：从缓冲区剥离 ReAct 内部标记段
                    # 防止 react_agent.py 的流式检测未能拦截的 ## Action/## Thought 泄露
                    clean_buffer = output_formatter.strip_react_markers_from_buffer(full_response)

                    # 计算新的干净内容并输出（增量输出，避免重复）
                    if len(clean_buffer) > last_clean_output_length:
                        new_clean_content = clean_buffer[last_clean_output_length:]
                        last_clean_output_length = len(clean_buffer)
                        if new_clean_content:
                            # 🔧 修复内容重复：检查增量内容是否已经在之前的输出中出现过
                            # （当 streaming 阶段与 post-streaming Final Answer 阶段输出重叠时）
                            # 注意：仅对长度 >= 5 的增量做去重，避免单字符（标点/英文）被错误过滤
                            if len(new_clean_content) >= 5 and new_clean_content in clean_buffer[:-len(new_clean_content)]:
                                print(f"[DEDUP] 增量内容重复，跳过 yield | content={repr(new_clean_content[:60])}")
                                continue
                            yield new_clean_content
                    # 如果剥离后内容变少（标记被移除），更新输出位置但不输出任何内容
                    elif len(clean_buffer) < last_clean_output_length:
                        last_clean_output_length = len(clean_buffer)
                # 记录回答到监控（使用清理后的完整内容）
                full_response = clean_buffer  # 使用剥离后的干净内容

                # 🔧 修复内容重复：检查 clean_buffer 是否包含重复的文本
                # （当 streaming 阶段与 post-streaming Final Answer 阶段输出重叠时会发生）
                half = len(full_response) // 2
                if half > 5 and full_response[:half] == full_response[half:2*half]:
                    dup_text = full_response[:half]
                    print(f"[DEDUP] 检测到内容完全重复，移除后半段 | 重复内容: {repr(dup_text[:50])}")
                    full_response = dup_text
                elif half > 5:
                    # 也检查后半段是否包含前半段（部分重叠）
                    from difflib import SequenceMatcher
                    first_half = full_response[:half]
                    second_half = full_response[half:]
                    matcher = SequenceMatcher(None, first_half, second_half)
                    ratio = matcher.ratio()
                    if ratio > 0.85:
                        print(f"[DEDUP] 检测到内容高度重复 (ratio={ratio:.3f})，去重")
                        # 保留较长的那一段
                        full_response = max(first_half, second_half, key=len)

                trace.set_result(full_response)
            
            # 🧠 完整的AI回答已通过 API 层（chat.py）保存到数据库
            # 记忆系统只用于构建上下文，不存储消息

            # 🆕 延迟图抽取：对话完成后后台提取实体（不阻塞对话流）
            if settings.ENABLE_DEFERRED_GRAPH_EXTRACTION and user_input and full_response:
                asyncio.create_task(
                    self._deferred_graph_extraction_task(
                        user_input=user_input,
                        ai_response=full_response,
                        session_id=session_id or "default_session",
                        user_id=user_id or "default_user",
                        tenant_id=tenant_id
                    )
                )
                print("[GRAPH] [延迟图抽取] 已触发后台任务")

            print("[OK] [自定义框架] 流式处理完成")
            
        except LLMServiceException as e:
            logger.debug(f"[ERROR] [自定义框架] 流式处理LLM服务异常: {e}")
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

    # ──────────────────────────────────────────────────────
    # Agentic RAG：多轮自主检索循环
    # 复用 RetrievalPlanner（查询规划/改写）+ ResultEvaluator（结果评估），
    # 以真实的 unified_retriever 作为执行引擎，逐轮累积结果直到足够或到达上限。
    # ──────────────────────────────────────────────────────
    async def _build_agentic_llm_bridge(self, tenant_id: Optional[str]):
        """解析 Agentic 评估/改写所用 LLM：租户 DB 配置覆盖，env 兜底；不回写。

        失败时返回 None，由 RetrievalPlanner/ResultEvaluator 自动回退到规则版。
        """
        try:
            from app.agent_framework.llm.specialist_llm_router import SpecialistLLMRouter
            from app.agent_framework.llm.agent_llm_config import AgentType

            adapter = None
            if tenant_id:
                from app.db.session import AsyncSessionLocal
                async with AsyncSessionLocal() as _db:
                    adapter = await SpecialistLLMRouter.get_adapter_for_specialist(
                        AgentType.CHAT, tenant_id=tenant_id, db=_db
                    )
            else:
                adapter = SpecialistLLMRouter.get_default_adapter()

            if adapter is None:
                return None
            return _AgenticLLMBridge(adapter)
        except Exception as e:
            logger.warning(f"[Agentic] LLM bridge 初始化失败，回退规则评估/改写: {e}")
            return None

    async def _agentic_retrieve(
        self,
        query: str,
        kb_id: str,
        session_id: str,
        user_id: str,
        tenant_id: Optional[str],
        max_iterations: int,
        top_k: int,
        enable_rerank: bool,
        enable_graph: bool,
    ) -> AsyncGenerator[tuple, None]:
        """多轮自主检索（异步生成器）。

        检索期间 yield ("progress", {...}) 进度事件供上层实时下发；
        全部完成后 yield ("result", {...})，其结果字典与 unified_retriever.retrieve 兼容，
        额外携带 retrieval_history（前端轨迹）与 evaluation（最终评估）。"""
        import time as _time
        from app.langgraph.agentic_rag_nodes import RetrievalPlanner, ResultEvaluator
        from app.langgraph.agentic_rag_state import AgenticRAGState, RetrievalStep

        # LLM 智能评估 + 查询改写（DB 覆盖 + env 兜底；失败则回退规则版）
        llm_bridge = await self._build_agentic_llm_bridge(tenant_id)
        planner = RetrievalPlanner(llm_service=llm_bridge)
        evaluator = ResultEvaluator(llm_service=llm_bridge, threshold=0.7)

        state: AgenticRAGState = {
            "query": query,
            "kb_id": kb_id,
            "iteration_count": 0,
            "max_iterations": max_iterations,
            "retrieval_history": [],
            "all_results": [],
        }

        history_payload: List[Dict[str, Any]] = []
        last_context = ""

        while True:
            # 进度：开始本轮检索（round = 当前已完成轮数 + 1）
            _round = state.get("iteration_count", 0) + 1
            yield ("progress", {
                "stage": "retrieval",
                "round": _round,
                "message": f"正在检索第 {_round} 轮…",
            })
            # ── 规划本轮查询（首轮原样，后续按评估缺失方面改写）──
            state = await planner.plan(state)
            cur_q = state.get("current_query") or query
            action = state.get("next_action") or "vector_search"
            # 规则评估给出的泛化缺失方面（“需要更多相关信息”）无检索价值，退回原始查询
            if "需要更多相关信息" in cur_q or "没有找到相关信息" in cur_q:
                cur_q = query

            iteration = state.get("iteration_count", 0)
            t0 = _time.time()
            try:
                res = await unified_retriever.retrieve(
                    query=cur_q,
                    kb_id=kb_id,
                    session_id=session_id,
                    user_id=user_id,
                    top_k=top_k,
                    enable_routing=False,   # agentic 自己控制流程，强制走 KB 检索
                    enable_graph=enable_graph,
                    enable_rerank=enable_rerank,
                    tenant_id=tenant_id,
                )
            except Exception as e:
                logger.warning(f"[Agentic] 第 {iteration + 1} 轮检索失败: {e}")
                res = {"rag_results": [], "combined_context": ""}

            round_results = res.get("rag_results", []) or []
            if res.get("combined_context"):
                last_context = res["combined_context"]
            dt_ms = int((_time.time() - t0) * 1000)

            # 记录步骤（dataclass 进 state 供评估器使用）
            step = RetrievalStep(
                step_number=iteration + 1,
                action=action,
                query=cur_q,
                parameters={"top_k": top_k},
                results=round_results,
                result_count=len(round_results),
            )
            state.setdefault("retrieval_history", []).append(step)
            state["current_results"] = round_results
            state["iteration_count"] = iteration + 1

            # 累积去重（按 id，回退到 content 前 100 字）
            all_results = state.get("all_results", [])
            seen = {(r.get("id") or (r.get("content", "")[:100])) for r in all_results}
            for r in round_results:
                key = r.get("id") or (r.get("content", "")[:100])
                if key not in seen:
                    all_results.append(r)
                    seen.add(key)
            state["all_results"] = all_results

            # 前端轨迹
            history_payload.append({
                "step_number": iteration + 1,
                "action": action,
                "query": cur_q,
                "result_count": len(round_results),
                "duration_ms": dt_ms,
            })

            # 进度：检索完成，开始评估
            yield ("progress", {
                "stage": "evaluate",
                "round": _round,
                "message": "正在评估检索结果…",
            })
            # ── 评估是否足够，决定是否继续 ──
            state = await evaluator.evaluate(state)
            if not state.get("should_continue"):
                break

        # ── 聚合：合并全部结果，按分数排序取 top_k ──
        merged = state.get("all_results", [])
        merged_sorted = sorted(
            merged,
            key=lambda r: (r.get("rerank_score") if r.get("rerank_score") is not None else r.get("score", 0)) or 0,
            reverse=True,
        )
        final_chunks = merged_sorted[: max(1, top_k)]

        combined_context = "\n\n".join(
            f"{i + 1}. {(c.get('content') or '').strip()}"
            for i, c in enumerate(final_chunks)
            if (c.get("content") or "").strip()
        )
        if not combined_context.strip():
            combined_context = last_context

        ev = state.get("evaluation")
        evaluation_payload = None
        if ev is not None:
            evaluation_payload = {
                "is_sufficient": ev.is_sufficient,
                "coverage_score": ev.coverage_score,
                "relevance_score": ev.relevance_score,
                "completeness_score": ev.completeness_score,
                "overall_score": ev.overall_score,
                "missing_aspects": ev.missing_aspects,
                "reasoning": ev.reasoning,
            }
            if history_payload:
                history_payload[-1]["reasoning"] = ev.reasoning

        logger.info(
            f"[Agentic] 完成 {state.get('iteration_count', 0)} 轮检索，"
            f"累计 {len(merged)} 条，最终 {len(final_chunks)} 条"
        )

        yield ("result", {
            "rag_results": final_chunks,
            "combined_context": combined_context,
            "mode": "AGENTIC",
            "retrieval_history": history_payload,
            "evaluation": evaluation_payload,
        })

    # ──────────────────────────────────────────────────────
    # 延迟图抽取：对话完成后后台提取实体到 Neo4j
    # ──────────────────────────────────────────────────────

    async def _deferred_graph_extraction_task(
        self,
        user_input: str,
        ai_response: str,
        session_id: str,
        user_id: str,
        tenant_id: Optional[str] = None
    ):
        """
        后台任务：对话完成后延迟判断并提取实体到知识图谱

        设计原则：
        1. 完全异步不阻塞，使用 asyncio.create_task 触发
        2. 先用轻量LLM快速判断对话是否包含可提取的实体关系
        3. 只有确认有价值时才运行完整的实体/关系提取管线
        4. 所有异常被捕获，不影响主流程
        """
        try:
            combined = f"用户：{user_input}\nAI：{ai_response}"

            # 第1步: 轻量LLM预检查 - 判断是否值得提取
            should_extract = await self._check_conversation_for_graph_extraction(combined)
            if not should_extract:
                logger.debug(
                    f"[延迟图抽取] 对话无需提取: {user_input[:40]}..."
                )
                return

            logger.info(
                f"[延迟图抽取] 开始提取: {user_input[:40]}..."
            )

            # 第2步: 初始化图构建组件
            from app.knowledge_graph.entity_extractor import EntityExtractor
            from app.knowledge_graph.relation_extractor import RelationExtractor
            from app.knowledge_graph.neo4j_manager import Neo4jManager
            from app.services.graph_builder import GraphBuilder

            neo4j_manager = Neo4jManager(
                uri=settings.NEO4J_URI,
                user=settings.NEO4J_USER,
                password=settings.NEO4J_PASSWORD
            )
            entity_extractor = EntityExtractor()
            relation_extractor = RelationExtractor()
            graph_builder = GraphBuilder(
                entity_extractor, relation_extractor, neo4j_manager
            )

            # 第3步: 构建知识图谱（写入Neo4j）
            result = await graph_builder.build_from_text(
                text=combined,
                user_id=user_id,
                session_id=session_id,
                tenant_id=tenant_id,
                extract_entities=True,
                extract_relations=True
            )

            if result.success:
                logger.info(
                    f"[延迟图抽取] 完成 | 实体: {len(result.entities)}, "
                    f"关系: {len(result.relations)}"
                )
            else:
                logger.warning(
                    f"[延迟图抽取] 构建失败: {result.message}"
                )

        except Exception as e:
            logger.warning(
                f"[延迟图抽取] 后台任务异常(不影响对话): {e}"
            )

    async def _check_conversation_for_graph_extraction(
        self, conversation_text: str
    ) -> bool:
        """
        轻量LLM快速判断对话内容是否包含可提取的企业实体

        使用极简Prompt直接判断实体存在性（而非价值判断），
        避免LLM因"是否值得"等主观表述而误判。
        注意: 不传 model 参数，避免 DeepSeek Adapter 的 LangSmith 路径冲突。
        """
        try:
            from app.services.llm_service import llm_service

            # 只取用户问题的前200字符和AI回答的前200字符
            # 避免AI的"未找到相关信息"类回答干扰实体判断
            user_part, ai_part = "", ""
            parts = conversation_text.split("\nAI：", 1)
            if len(parts) == 2:
                user_part = parts[0][:200]
                ai_part = "AI：" + parts[1][:200]
            else:
                user_part = conversation_text[:400]

            prompt = (
                f"分析这段对话是否包含【具体的企业实体信息】。\n"
                f"包含以下任一就回答 YES：企业名(如华为/腾讯)、人名(如张三/马化腾)、"
                f"合同/签约/金额等具体商业信息。\n"
                f"没有具体实体信息就回答 NO。\n\n"
                f"对话：\n{user_part}\n{ai_part}\n\n"
                f"回答（YES 或 NO）："
            )

            result = await llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                history=[],
            )
            answer = result.strip().upper()
            should_extract = "YES" in answer
            logger.info(
                f"[延迟图抽取] 预检查结果: {answer[:10]} → "
                f"{'提取' if should_extract else '跳过'}"
            )
            return should_extract

        except Exception as e:
            logger.warning(
                f"[延迟图抽取] LLM预检查失败(默认不提取): {e}"
            )
            return False

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
