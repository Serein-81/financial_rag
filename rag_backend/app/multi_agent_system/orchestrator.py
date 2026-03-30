"""
智能体编排器 (Agent Orchestrator)
企业智能体系统的核心协调器，负责编排接待、意图识别、专业Agent协作和报告生成
"""

import asyncio
import uuid
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass, field

from .agents.receptionist_agent import ReceptionistAgent
from .agents.intent_agent import IntentAgent, IntentAnalysisResult, IntentCategory, RoutingStrategy
from .agents.finance_specialist import FinanceSpecialist
from .agents.tax_specialist import TaxSpecialist
from .agents.legal_specialist import LegalSpecialist
from .agents.reflection_specialist import ReflectionSpecialist
from .message_bus import MessageBus, MessageType
from .state import AuditState
from .rag_retriever import TenantIsolatedRAGRetriever
from app.agent_framework.llm.factory import LLMAdapterFactory
from app.agent_framework.tools.tool_manager import ToolManager
from app.memory_system.memory_manager import MemoryManager


@dataclass
class OrchestrationContext:
    """编排上下文"""
    session_id: str
    tenant_id: str
    user_id: str
    user_query: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    enable_reflection: bool = True
    confidence_threshold: float = 0.7
    max_specialists: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    intent_result: Optional[IntentAnalysisResult] = None
    specialist_results: List[Dict[str, Any]] = field(default_factory=list)
    reflection_result: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None
    needs_human_review: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentOrchestrator:
    """
    智能体编排器
    
    核心职责：
    1. 初始化和管理所有智能体
    2. 协调接待Agent和意图识别Agent的工作流程
    3. 将任务路由到合适的专业Agent
    4. 管理多Agent并行/串行协作
    5. 调用反思Agent进行质量审核
    6. 管理对话上下文和状态
    
    工作流程：
    用户输入 → 接待Agent → 意图识别Agent → 
    (RAG/单专家/多专家) → 反思Agent → 返回结果
    """
    
    def __init__(
        self,
        tenant_id: str = "default",
        user_id: str = "default",
        enable_reflection: bool = True,
        enable_rag: bool = True,
        max_parallel_agents: int = 3,
        timeout: float = 120.0,
        context: Optional[OrchestrationContext] = None
    ):
        """
        初始化编排器
        
        Args:
            tenant_id: 租户ID（用于数据隔离）
            user_id: 用户ID
            enable_reflection: 是否启用反思审核
            enable_rag: 是否启用RAG检索
            max_parallel_agents: 最大并行Agent数量
            timeout: 超时时间（秒）
            context: 编排上下文（可选）
        """
        if context:
            self.tenant_id = context.tenant_id
            self.user_id = context.user_id
            self.enable_reflection = context.enable_reflection
            self.max_parallel_agents = context.max_specialists
            self.enable_rag = enable_rag
            self.timeout = timeout
            self.context = context
        else:
            self.tenant_id = tenant_id
            self.user_id = user_id
            self.enable_reflection = enable_reflection
            self.enable_rag = enable_rag
            self.max_parallel_agents = max_parallel_agents
            self.timeout = timeout
            self.context = None
        
        self.llm_adapter = None
        self.tool_manager = None
        self.message_bus = MessageBus()
        self.memory_manager = None
        
        self.receptionist: Optional[ReceptionistAgent] = None
        self.intent_agent: Optional[IntentAgent] = None
        self.finance_specialist: Optional[FinanceSpecialist] = None
        self.tax_specialist: Optional[TaxSpecialist] = None
        self.legal_specialist: Optional[LegalSpecialist] = None
        self.reflection_specialist: Optional[ReflectionSpecialist] = None
        
        self.rag_retriever: Optional[TenantIsolatedRAGRetriever] = None
        
        self.initialized = False
        
        print("🎭 [编排器] 初始化完成")
        print(f"   - 租户ID: {tenant_id}")
        print(f"   - 反思审核: {'启用' if enable_reflection else '禁用'}")
        print(f"   - RAG检索: {'启用' if enable_rag else '禁用'}")
    
    async def process_context(
        self,
        context: OrchestrationContext
    ) -> OrchestrationContext:
        """
        使用编排上下文处理请求（API路由专用方法）
        
        Args:
            context: 编排上下文
            
        Returns:
            更新后的编排上下文
        """
        if not self.initialized:
            await self.initialize()
        
        start_time = datetime.now()
        
        print(f"\n{'='*60}")
        print(f"🎭 [编排器] 开始处理请求（API模式）")
        print(f"   会话ID: {context.session_id}")
        print(f"   用户查询: {context.user_query[:100] if context.user_query else 'N/A'}...")
        print(f"   启用反思: {context.enable_reflection}")
        print(f"{'='*60}\n")
        
        try:
            user_input = context.user_query
            
            if not user_input:
                context.final_response = "用户查询不能为空"
                return context
            
            simple_result = await self.receptionist.run(
                user_input=user_input,
                history=[],
                tenant_id=context.tenant_id,
                user_id=context.user_id
            )
            
            if self._is_simple_response(simple_result):
                context.final_response = simple_result
                print(f"✅ [编排器] 直接回答完成")
                return context
            
            print(f"🔄 [编排器] 进入意图识别流程")
            intent_result = await self.intent_agent.run(
                user_input=user_input,
                history=[],
                context={"session_id": context.session_id}
            )
            context.intent_result = intent_result
            
            if intent_result.routing_strategy == RoutingStrategy.DIRECT_ANSWER:
                response = await self._handle_direct_answer(user_input, intent_result)
                context.final_response = response
                return context
            
            if intent_result.routing_strategy == RoutingStrategy.RAG_RETRIEVAL:
                response = await self._handle_rag_retrieval(user_input, intent_result)
                context.final_response = response
                return context
            
            if intent_result.routing_strategy == RoutingStrategy.SINGLE_SPECIALIST:
                specialist_result = await self._handle_single_specialist(
                    user_input, intent_result
                )
                context.specialist_results.append({
                    'specialist_type': specialist_result.get('specialist', 'unknown'),
                    'specialist_name': specialist_result.get('specialist', 'unknown'),
                    'success': specialist_result.get('status') == 'success',
                    'confidence': intent_result.confidence,
                    'analysis': specialist_result.get('result', {}),
                    'entities': intent_result.entities if hasattr(intent_result, 'entities') else [],
                    'recommendations': [],
                    'risks': [],
                    'metadata': {},
                    'processing_time': 0.0,
                    'error_message': specialist_result.get('error')
                })
                
                if context.enable_reflection:
                    context = await self._run_reflection(context, user_input)
                
                context.final_response = self._format_specialist_response(
                    specialist_result,
                    intent_result
                )
                
                return context
            
            if intent_result.routing_strategy in [
                RoutingStrategy.MULTI_SPECIALIST_PARALLEL,
                RoutingStrategy.MULTI_SPECIALIST_SEQUENTIAL
            ]:
                specialist_results = await self._handle_multi_specialist(
                    user_input, intent_result
                )
                
                for specialist_name, result in specialist_results.get('results', {}).items():
                    context.specialist_results.append({
                        'specialist_type': specialist_name,
                        'specialist_name': specialist_name,
                        'success': result.get('status') == 'success',
                        'confidence': intent_result.confidence,
                        'analysis': result.get('result', {}),
                        'entities': [],
                        'recommendations': [],
                        'risks': [],
                        'metadata': {},
                        'processing_time': 0.0,
                        'error_message': result.get('error')
                    })
                
                if context.enable_reflection:
                    context = await self._run_reflection(context, user_input)
                
                context.final_response = self._format_multi_specialist_response(
                    specialist_results,
                    intent_result
                )
                
                return context
            
            if intent_result.routing_strategy == RoutingStrategy.REPORT_QUEUE:
                context.metadata['status'] = 'queued'
                context.metadata['message'] = '报告生成请求已加入队列'
                context.final_response = "报告生成请求已加入队列"
                return context
            
            context.final_response = "抱歉，暂时无法处理您的请求，请稍后重试。"
            return context
            
        except Exception as e:
            print(f"❌ [编排器] 处理异常: {e}", exc_info=True)
            context.final_response = f"处理失败: {str(e)}"
            context.metadata['error'] = str(e)
            return context
    
    async def process(self, context: OrchestrationContext) -> OrchestrationContext:
        """处理请求的别名方法（供API路由调用）
        
        Args:
            context: 编排上下文
            
        Returns:
            更新后的编排上下文
        """
        return await self.process_context(context)
    
    async def initialize(self):
        """
        异步初始化所有智能体和组件
        
        使用方式:
            orchestrator = AgentOrchestrator(tenant_id="xxx")
            await orchestrator.initialize()
        """
        if self.initialized:
            print("⚠️ [编排器] 已经初始化，跳过")
            return
        
        print("🎭 [编排器] 开始初始化所有组件...")
        
        try:
            self.llm_adapter = LLMAdapterFactory.create_adapter("zhipu")
            self.tool_manager = ToolManager()
            
            print("🤖 [编排器] 创建接待智能体...")
            self.receptionist = ReceptionistAgent(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager,
                message_bus=self.message_bus,
                timeout=30.0
            )
            
            print("🧠 [编排器] 创建意图识别智能体...")
            self.intent_agent = IntentAgent(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager,
                confidence_threshold=0.7,
                timeout=30.0
            )
            
            print("💼 [编排器] 创建专业智能体...")
            self.finance_specialist = FinanceSpecialist(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager
            )
            
            self.tax_specialist = TaxSpecialist(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager
            )
            
            self.legal_specialist = LegalSpecialist(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager
            )
            
            if self.enable_reflection:
                print("🔍 [编排器] 创建反思智能体...")
                self.reflection_specialist = ReflectionSpecialist(
                    llm_adapter=self.llm_adapter,
                    tool_manager=self.tool_manager
                )
            
            if self.enable_rag:
                print("📚 [编排器] 初始化RAG检索器...")
                await self._initialize_rag()
            
            print("🧠 [编排器] 初始化记忆管理器...")
            self.memory_manager = MemoryManager(
                tenant_id=self.tenant_id,
                user_id=self.user_id
            )
            
            self.initialized = True
            print("✅ [编排器] 所有组件初始化完成")
            
        except Exception as e:
            print(f"❌ [编排器] 初始化失败: {e}")
            raise
    
    async def _initialize_rag(self):
        """初始化RAG检索器"""
        try:
            from app.services.embedding_service import EmbeddingService
            from app.services.search_service import SearchService
            
            embedding_service = EmbeddingService()
            search_service = SearchService()
            
            self.rag_retriever = TenantIsolatedRAGRetriever(
                qdrant_client=search_service.qdrant_client if hasattr(search_service, 'qdrant_client') else None,
                embedding_service=embedding_service,
                enable_audit=True
            )
            
            print("📚 [编排器] RAG检索器初始化成功")
            
        except Exception as e:
            print(f"⚠️ [编排器] RAG检索器初始化失败: {e}")
            self.rag_retriever = None
    
    async def stream_process_context(
        self,
        context: OrchestrationContext
    ) -> AsyncGenerator[str, None]:
        """
        流式处理编排上下文
        
        Args:
            context: 编排上下文
            
        Yields:
            逐步生成的内容
        """
        result = await self.process_context(context)
        
        if result.final_response:
            yield result.final_response
        else:
            yield "处理失败"
    
    def _is_simple_response(self, response: str) -> bool:
        """判断是否为简单回答（不需要进一步处理）"""
        simple_indicators = [
            "你好", "您好", "hi", "hello",
            "现在", "今天",
            "谢谢", "thanks",
            "不客气", "很高兴"
        ]
        
        return any(indicator in response[:20] for indicator in simple_indicators)
    
    async def _handle_direct_answer(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> str:
        """处理直接回答类型的请求"""
        greeting_responses = {
            IntentCategory.GREETING: "您好！有什么可以帮助您的吗？",
            IntentCategory.CHIT_CHAT: "我们来聊聊吧，有什么感兴趣的话题吗？"
        }
        
        return greeting_responses.get(
            intent_result.intent,
            "好的，我明白了。"
        )
    
    async def _handle_rag_retrieval(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> str:
        """处理RAG检索类型的请求"""
        if not self.rag_retriever:
            return "抱歉，知识库检索功能暂时不可用。"
        
        try:
            results = await self.rag_retriever.search(
                query=user_input,
                top_k=5,
                tenant_id=self.tenant_id
            )
            
            if not results:
                return "抱歉，我在知识库中没有找到相关信息。"
            
            context = "\n".join([
                f"- {r.get('content', '')[:200]}"
                for r in results[:3]
            ])
            
            prompt = f"""根据以下知识库内容回答用户问题：

知识库内容：
{context}

用户问题：{user_input}

请给出准确、简洁的回答。"""
            
            response = await self.llm_adapter.agenerate([prompt])
            return response if response else "抱歉，未能生成回答。"
            
        except Exception as e:
            print(f"⚠️ [编排器] RAG检索失败: {e}")
            return "抱歉，知识库检索失败。"
    
    async def _handle_single_specialist(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> Dict[str, Any]:
        """处理单专家类型的请求"""
        specialist_map = {
            "finance": self.finance_specialist,
            "tax": self.tax_specialist,
            "legal": self.legal_specialist
        }
        
        specialists_needed = intent_result.requires_specialists
        
        if not specialists_needed or specialists_needed == ["general"]:
            return {
                "status": "no_specialist",
                "message": "未找到合适的专家"
            }
        
        specialist_name = specialists_needed[0]
        specialist = specialist_map.get(specialist_name)
        
        if not specialist:
            return {
                "status": "error",
                "message": f"专家 {specialist_name} 不可用"
            }
        
        print(f"💼 [编排器] 调用{ specialist_name }专家...")
        
        try:
            if hasattr(specialist, 'consult'):
                result = await specialist.consult(
                    query=user_input,
                    entities=intent_result.entities,
                    context=intent_result.suggested_params
                )
            else:
                result = await specialist.run(
                    user_input=user_input,
                    context=intent_result.suggested_params
                )
            
            return {
                "status": "success",
                "specialist": specialist_name,
                "result": result
            }
            
        except Exception as e:
            print(f"❌ [编排器] 专家调用失败: {e}")
            return {
                "status": "error",
                "specialist": specialist_name,
                "error": str(e)
            }
    
    async def _handle_multi_specialist(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> Dict[str, Any]:
        """处理多专家类型的请求"""
        specialists_needed = intent_result.requires_specialists
        
        specialist_map = {
            "finance": self.finance_specialist,
            "tax": self.tax_specialist,
            "legal": self.legal_specialist
        }
        
        if intent_result.routing_strategy == RoutingStrategy.MULTI_SPECIALIST_PARALLEL:
            print(f"🔄 [编排器] 并行调用 {len(specialists_needed)} 个专家...")
            
            tasks = []
            for specialist_name in specialists_needed[:self.max_parallel_agents]:
                specialist = specialist_map.get(specialist_name)
                if specialist:
                    if hasattr(specialist, 'consult'):
                        task = specialist.consult(
                            query=user_input,
                            entities=intent_result.entities,
                            context=intent_result.suggested_params
                        )
                    else:
                        task = specialist.run(
                            user_input=user_input,
                            context=intent_result.suggested_params
                        )
                    tasks.append((specialist_name, specialist, task))
            
            results = {}
            for specialist_name, specialist, task in tasks:
                try:
                    result = await task
                    results[specialist_name] = {
                        "status": "success",
                        "result": result
                    }
                except Exception as e:
                    results[specialist_name] = {
                        "status": "error",
                        "error": str(e)
                    }
            
            return {
                "status": "success",
                "mode": "parallel",
                "results": results
            }
        
        else:
            print(f"🔄 [编排器] 串行调用 {len(specialists_needed)} 个专家...")
            
            results = {}
            accumulated_context = {}
            
            for specialist_name in specialists_needed:
                specialist = specialist_map.get(specialist_name)
                if not specialist:
                    continue
                
                try:
                    if hasattr(specialist, 'consult'):
                        result = await specialist.consult(
                            query=user_input,
                            entities=accumulated_context.get("entities", intent_result.entities),
                            context=accumulated_context
                        )
                    else:
                        result = await specialist.run(
                            user_input=user_input,
                            context=accumulated_context
                        )
                    
                    results[specialist_name] = {
                        "status": "success",
                        "result": result
                    }
                    
                    accumulated_context[specialist_name] = result
                    
                except Exception as e:
                    results[specialist_name] = {
                        "status": "error",
                        "error": str(e)
                    }
            
            return {
                "status": "success",
                "mode": "sequential",
                "results": results
            }
    
    async def _run_reflection(
        self,
        context: OrchestrationContext,
        user_input: str
    ) -> OrchestrationContext:
        """运行反思审核"""
        if not self.reflection_specialist:
            return context
        
        print(f"🔍 [编排器] 启动反思审核...")
        
        try:
            reflection_result = await self.reflection_specialist.review(
                user_input=user_input,
                specialist_results=context.specialist_results,
                intent_result=context.intent_result
            )
            
            context.reflection_result = reflection_result
            
            if reflection_result.get("needs_revision"):
                print(f"⚠️ [编排器] 反思审核建议修订")
                context.metadata["revision_suggestions"] = reflection_result.get(
                    "suggestions", []
                )
            
            if reflection_result.get("confidence", 1.0) < 0.7:
                context.needs_human_review = True
                print(f"⚠️ [编排器] 置信度低于阈值，标记需要人工审核")
            
        except Exception as e:
            print(f"⚠️ [编排器] 反思审核失败: {e}")
        
        return context
    
    def _format_specialist_response(
        self,
        specialist_result: Dict[str, Any],
        intent_result: IntentAnalysisResult
    ) -> str:
        """格式化单专家响应"""
        if specialist_result.get("status") == "success":
            result = specialist_result.get("result", "")
            
            specialist_name_map = {
                "finance": "财务专家",
                "tax": "税务专家",
                "legal": "法务专家"
            }
            
            specialist_display = specialist_name_map.get(
                specialist_result.get("specialist", ""),
                "专家"
            )
            
            return f"【{ specialist_display }的回答】\n\n{result}"
        
        return specialist_result.get("error", "处理失败")
    
    def _format_multi_specialist_response(
        self,
        specialist_results: Dict[str, Any],
        intent_result: IntentAnalysisResult
    ) -> str:
        """格式化多专家响应"""
        responses = []
        
        specialist_name_map = {
            "finance": "财务专家",
            "tax": "税务专家",
            "legal": "法务专家"
        }
        
        results = specialist_results.get("results", specialist_results)
        
        for specialist_name, result in results.items():
            if result.get("status") == "success":
                specialist_display = specialist_name_map.get(specialist_name, specialist_name)
                specialist_response = result.get("result", "")
                responses.append(f"【{ specialist_display }】\n{specialist_response}")
        
        if not responses:
            return "抱歉，所有专家处理均失败。"
        
        header = "【综合分析报告】\n\n"
        footer = f"\n\n{'='*40}\n💡 以上内容由多个专业领域综合分析得出。"
        
        return header + "\n\n".join(responses) + footer
    
    def _build_response(
        self,
        context: OrchestrationContext,
        start_time: datetime
    ) -> Dict[str, Any]:
        """构建最终响应"""
        processing_time = (datetime.now() - start_time).total_seconds()
        
        response = {
            "status": "success",
            "session_id": context.session_id,
            "response": context.final_response,
            "intent": context.intent_result.intent.value if context.intent_result else None,
            "confidence": context.intent_result.confidence if context.intent_result else 0.0,
            "requires_specialists": context.intent_result.requires_specialists if context.intent_result else [],
            "processing_time": round(processing_time, 2),
            "needs_human_review": context.needs_human_review
        }
        
        if context.reflection_result:
            response["reflection"] = {
                "confidence": context.reflection_result.get("confidence", 0.0),
                "needs_revision": context.reflection_result.get("needs_revision", False)
            }
        
        print(f"\n✅ [编排器] 处理完成")
        print(f"   处理时间: {processing_time:.2f}秒")
        print(f"   状态: {response['status']}")
        print(f"{'='*60}\n")
        
        return response
    
    async def generate_report(
        self,
        session_id: str,
        report_type: str = "comprehensive",
        format: str = "markdown",
        include_sections: Optional[List[str]] = None
    ) -> str:
        """
        生成报告（API路由专用方法）
        
        Args:
            session_id: 会话ID
            report_type: 报告类型
            format: 输出格式
            include_sections: 包含的章节
            
        Returns:
            报告内容
        """
        print(f"📄 [编排器] 生成报告 - 会话ID: {session_id}")
        
        report_sections = []
        
        report_sections.append(f"# 多智能体分析报告\n")
        report_sections.append(f"**会话ID**: {session_id}\n")
        report_sections.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report_sections.append(f"**报告类型**: {report_type}\n")
        report_sections.append("\n---\n")
        
        if self.context and self.context.intent_result:
            report_sections.append("## 意图分析\n")
            intent = self.context.intent_result
            report_sections.append(f"- **主要意图**: {intent.primary_intent}\n")
            report_sections.append(f"- **复杂度**: {intent.complexity}\n")
            report_sections.append(f"- **路由策略**: {intent.routing_strategy}\n")
            report_sections.append(f"- **置信度**: {intent.confidence:.2%}\n")
            report_sections.append("\n---\n")
        
        if self.context and self.context.specialist_results:
            report_sections.append("## 专家分析结果\n")
            for i, result in enumerate(self.context.specialist_results, 1):
                specialist_name = result.get('specialist_name', '未知专家')
                success = result.get('success', False)
                confidence = result.get('confidence', 0.0)
                
                report_sections.append(f"### {i}. {specialist_name}\n")
                report_sections.append(f"- **状态**: {'成功' if success else '失败'}\n")
                report_sections.append(f"- **置信度**: {confidence:.2%}\n")
                
                if result.get('analysis'):
                    analysis = result['analysis']
                    if isinstance(analysis, dict):
                        for key, value in analysis.items():
                            if isinstance(value, (str, int, float)):
                                report_sections.append(f"- **{key}**: {value}\n")
                            elif isinstance(value, list):
                                report_sections.append(f"- **{key}**:\n")
                                for item in value[:5]:
                                    report_sections.append(f"  - {item}\n")
                
                report_sections.append("\n")
            report_sections.append("\n---\n")
        
        if self.context and self.context.reflection_result:
            report_sections.append("## 质量审核\n")
            reflection = self.context.reflection_result
            quality_score = reflection.get('quality_score', 0.0)
            quality_level = reflection.get('quality_level', '未知')
            needs_revision = reflection.get('needs_revision', False)
            
            report_sections.append(f"- **质量评分**: {quality_score:.2%}\n")
            report_sections.append(f"- **质量级别**: {quality_level}\n")
            report_sections.append(f"- **需要修订**: {'是' if needs_revision else '否'}\n")
            
            if reflection.get('suggestions'):
                report_sections.append("\n### 改进建议\n")
                for suggestion in reflection['suggestions']:
                    report_sections.append(f"- {suggestion}\n")
            
            report_sections.append("\n---\n")
        
        report_sections.append("\n## 最终回复\n")
        if self.context and self.context.final_response:
            report_sections.append(f"{self.context.final_response}\n")
        else:
            report_sections.append("暂无回复内容\n")
        
        report_sections.append("\n---\n")
        report_sections.append(f"*本报告由多智能体系统自动生成*\n")
        
        report_content = "".join(report_sections)
        
        if format == "json":
            import json
            return json.dumps({
                "session_id": session_id,
                "report_type": report_type,
                "content": report_content,
                "generated_at": datetime.now().isoformat()
            }, ensure_ascii=False, indent=2)
        
        return report_content
