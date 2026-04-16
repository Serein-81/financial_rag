"""
智能体编排器 (Agent Orchestrator)
企业智能体系统的核心协调器，负责编排接待、意图识别、专业Agent协作和报告生成
"""

import asyncio
import json
import uuid
import traceback
import logging
import re
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass, field

from .agents.intent_router_agent import (
    IntentRouterAgent, 
    IntentAnalysisResult, 
    IntentCategory, 
    RoutingStrategy
)
from .agents.finance_specialist import FinanceSpecialist
from .agents.tax_specialist import TaxSpecialist
from .agents.legal_specialist import LegalSpecialist
from app.prompts.llm_functions import review_quality
from .agents.report_generator import ReportGenerator
from .message_bus import MessageBus
from .rag_retriever import TenantIsolatedRAGRetriever
from app.agent_framework.llm.factory import LLMAdapterFactory
from app.agent_framework.tools.tool_manager import ToolManager
from app.agent_framework.core.output_agent import output_agent
from app.memory_system.memory_manager import MemoryManager
from app.core.config import settings
from app.agent_framework.core.output_agent import OutputAgent
from app.services.agent_tracer import agent_tracer


logger = logging.getLogger(__name__)


@dataclass
class OrchestrationContext:
    """编排上下文"""
    session_id: str
    tenant_id: str
    user_id: str
    user_query: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    enable_reflection: bool = False
    enable_rag: bool = True
    enable_report_generation: bool = False
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
        enable_reflection: bool = False,
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
        
        self.intent_router: Optional[IntentRouterAgent] = None
        self.finance_specialist: Optional[FinanceSpecialist] = None
        self.tax_specialist: Optional[TaxSpecialist] = None
        self.legal_specialist: Optional[LegalSpecialist] = None

        self.output_agent: Optional[OutputAgent] = None
        
        self.rag_retriever: Optional[TenantIsolatedRAGRetriever] = None
        
        self._capability_config: Dict[str, Any] = {}
        self._specialist_descriptions: str = ""
        self._intent_mapping: Dict[str, str] = {}
        
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
        trace_id = None
        step_number = 0
        
        try:
            user_input = context.user_query
            
            if not user_input:
                context.final_response = "用户查询不能为空"
                return context
            
            trace_id = await agent_tracer.start_trace(
                agent_type="multi_agent_orchestrator",
                user_query=user_input,
                session_id=context.session_id,
                message_id=context.session_id
            )
            step_number += 1
            await agent_tracer.add_step(
                trace_id=trace_id,
                step_number=step_number,
                step_type="thought",
                content="开始多智能体协作流程"
            )
            
            routing_result = await self.intent_router.run(
                user_input=user_input,
                history=[],
                context={"session_id": context.session_id, "tenant_id": context.tenant_id}
            )
            step_number += 1
            await agent_tracer.add_step(
                trace_id=trace_id,
                step_number=step_number,
                step_type="action",
                content=f"意图路由Agent处理完成: {routing_result.model_dump_json()[:200]}...",
                tool_name="IntentRouterAgent",
                tool_input={"user_input": user_input},
                tool_output=routing_result.model_dump_json()[:500]
            )
            
            if routing_result.is_simple:
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="final_answer",
                    content="直接返回简单响应"
                )
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=routing_result.simple_response,
                    success=True
                )
                context.final_response = routing_result.simple_response
                return context
            
            intent_result = routing_result.intent_result
            context.intent_result = intent_result
            step_number += 1
            await agent_tracer.add_step(
                trace_id=trace_id,
                step_number=step_number,
                step_type="thought",
                content=f"意图识别完成: {intent_result.intent.value}, 置信度: {intent_result.confidence:.2f}, 路由策略: {intent_result.routing_strategy.value}",
                tool_name="IntentRouterAgent",
                tool_input={"user_input": user_input},
                tool_output={
                    "intent": intent_result.intent.value,
                    "confidence": intent_result.confidence,
                    "routing_strategy": intent_result.routing_strategy.value,
                    "requires_specialists": intent_result.requires_specialists
                }
            )
            
            if hasattr(intent_result, 'needs_report_generation') and intent_result.needs_report_generation:
                context.enable_report_generation = True
                print("📄 [编排器] 检测到用户要求生成报告")
            
            from app.services.admin_notification_service import (
                admin_notification_service
            )
            
            risk_check_result = await admin_notification_service.handle_high_risk_operation(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                user_query=user_input,
                context={
                    "confidence": intent_result.confidence,
                    "entities": getattr(intent_result, 'entities', []),
                    "intent": intent_result.intent.value
                }
            )
            
            if risk_check_result["status"] == "pending_approval":
                context.metadata['hitl_pending'] = True
                context.metadata['hitl_approval_id'] = risk_check_result['approval_id']
                context.metadata['hitl_risk_level'] = risk_check_result['risk_level']
                context.final_response = f"⚠️ 检测到高风险操作，当前请求需要管理员审批。审批ID: {risk_check_result['approval_id']}，请等待审批完成。"
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="observation",
                    content="高风险操作，需要人工审批"
                )
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=True
                )
                return context
            
            if intent_result.routing_strategy == RoutingStrategy.DIRECT_ANSWER:
                response = await self._handle_direct_answer(user_input, intent_result)
                context.final_response = response
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="final_answer",
                    content=f"直接回答: {response[:100]}..."
                )
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=response,
                    success=True
                )
                return context
            
            if intent_result.routing_strategy == RoutingStrategy.RAG_RETRIEVAL:
                response = await self._handle_rag_retrieval(user_input, intent_result)
                context.final_response = response
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="final_answer",
                    content=f"RAG检索回答: {response[:100]}..."
                )
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=response,
                    success=True
                )
                return context
            
            if intent_result.routing_strategy == RoutingStrategy.SINGLE_SPECIALIST:
                specialist_result = await self._handle_single_specialist(
                    user_input, intent_result
                )
                step_number += 1
                specialist_name = specialist_result.get('specialist', 'unknown')
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="action",
                    content=f"单专家{specialist_name}处理完成",
                    tool_name=f"{specialist_name.title()}Specialist"
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
                
                if context.enable_report_generation and self.report_generator:
                    context.final_response = await self._generate_report(
                        user_input,
                        context.specialist_results,
                        intent_result
                    )
                    step_number += 1
                    await agent_tracer.add_step(
                        trace_id=trace_id,
                        step_number=step_number,
                        step_type="action",
                        content="生成报告完成",
                        tool_name="ReportGenerator"
                    )
                else:
                    if context.enable_reflection:
                        context = await self._run_reflection(context, user_input)
                        step_number += 1
                        await agent_tracer.add_step(
                            trace_id=trace_id,
                            step_number=step_number,
                            step_type="observation",
                            content="反思审核完成"
                        )
                    
                    context.final_response = await self._synthesize_output(
                        user_input,
                        context.specialist_results,
                        intent_result
                    )
                
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="final_answer",
                    content=f"单专家协作完成: {context.final_response[:100]}..."
                )
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=True
                )
                return context
            
            if intent_result.routing_strategy in [
                RoutingStrategy.MULTI_SPECIALIST_PARALLEL,
                RoutingStrategy.MULTI_SPECIALIST_SEQUENTIAL
            ]:
                specialist_results = await self._handle_multi_specialist(
                    user_input, intent_result
                )
                
                specialists_list = list(specialist_results.get('results', {}).keys())
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="action",
                    content=f"多专家协作完成 [{intent_result.routing_strategy.value}]: {', '.join(specialists_list)}",
                    tool_name="MultiSpecialistCollaboration",
                    tool_input={"specialists": specialists_list, "strategy": intent_result.routing_strategy.value}
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
                
                if context.enable_report_generation and self.report_generator:
                    context.final_response = await self._generate_report(
                        user_input,
                        context.specialist_results,
                        intent_result
                    )
                    step_number += 1
                    await agent_tracer.add_step(
                        trace_id=trace_id,
                        step_number=step_number,
                        step_type="action",
                        content="生成报告完成",
                        tool_name="ReportGenerator"
                    )
                else:
                    if context.enable_reflection:
                        context = await self._run_reflection(context, user_input)
                        step_number += 1
                        await agent_tracer.add_step(
                            trace_id=trace_id,
                            step_number=step_number,
                            step_type="observation",
                            content="反思审核完成"
                        )
                    
                    context.final_response = await self._synthesize_output(
                        user_input,
                        context.specialist_results,
                        intent_result
                    )
                
                step_number += 1
                await agent_tracer.add_step(
                    trace_id=trace_id,
                    step_number=step_number,
                    step_type="final_answer",
                    content=f"多专家协作完成: {context.final_response[:100]}..."
                )
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=True
                )
                return context
            
            if intent_result.routing_strategy == RoutingStrategy.REPORT_QUEUE:
                context.metadata['status'] = 'queued'
                context.metadata['message'] = '报告生成请求已加入队列'
                context.final_response = "报告生成请求已加入队列"
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=True
                )
                return context
            
            context.final_response = "抱歉，暂时无法处理您的请求，请稍后重试。"
            await agent_tracer.end_trace(
                trace_id=trace_id,
                final_answer=context.final_response,
                success=True
            )
            return context
            
        except (ValueError, KeyError) as e:
            print(f"❌ [编排器] 处理数据错误: {e}")
            traceback.print_exc()
            context.final_response = f"处理数据错误: {str(e)}"
            if trace_id:
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=False,
                    error_message=str(e)
                )
        except (OSError, IOError) as e:
            print(f"❌ [编排器] 处理IO错误: {e}")
            traceback.print_exc()
            context.final_response = f"处理IO错误: {str(e)}"
            if trace_id:
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=False,
                    error_message=str(e)
                )
        except Exception as e:
            print(f"❌ [编排器] 处理异常: {e}")
            traceback.print_exc()
            context.final_response = f"处理失败: {str(e)}"
            context.metadata['error'] = str(e)
            if trace_id:
                await agent_tracer.end_trace(
                    trace_id=trace_id,
                    final_answer=context.final_response,
                    success=False,
                    error_message=str(e)
                )
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
            from app.agent_framework.tools.agent_tool_registry import (
                initialize_tool_manager
            )
            
            default_provider = settings.get_llm_provider_for_agent("receptionist")
            print(f"🎭 [编排器] 默认智能体使用 LLM: {default_provider}")
            self.llm_adapter = LLMAdapterFactory.create_adapter(default_provider)
            self.tool_manager = ToolManager()
            
            # 注册 MCP 工具和本地工具
            print("🔧 [编排器] 注册工具...")
            tool_result = await initialize_tool_manager(
                self.tool_manager,
                include_mcp=True,
                include_local=True,
                tenant_id=self.tenant_id
            )
            logger.info(f"已注册 {tool_result['total_count']} 个工具")
            
            print("🤖 [编排器] 创建意图路由智能体（融合接待+意图识别）...")
            self.intent_router = IntentRouterAgent(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager,
                confidence_threshold=0.7,
                timeout=30.0,
                specialist_descriptions=self._specialist_descriptions,
                intent_mapping=self._intent_mapping
            )
            
            print("📊 [编排器] 初始化能力配置...")
            
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
                print("🔍 [编排器] 启用质量审查函数...")
            
            print("📝 [编排器] 创建报告生成器...")
            self.report_generator = ReportGenerator(
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager
            )
            
            print("🎨 [编排器] 创建输出智能体...")
            self.output_agent = OutputAgent(llm_adapter=self.llm_adapter)
            
            if self.enable_rag:
                print("📚 [编排器] 初始化RAG检索器...")
                await self._initialize_rag()
            
            print("🧠 [编排器] 初始化记忆管理器...")
            session_id = f"orchestrator_{self.tenant_id}_{uuid.uuid4().hex[:8]}"
            self.memory_manager = MemoryManager(
                session_id=session_id,
                user_id=self.user_id
            )
            
            self.initialized = True
            print("✅ [编排器] 所有组件初始化完成")
            
        except (ValueError, KeyError) as e:
            print(f"❌ [编排器] 初始化数据错误: {e}")
            raise
        except (OSError, IOError) as e:
            print(f"❌ [编排器] 初始化IO错误: {e}")
            raise
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
                embedding_service=embedding_service,
                enable_audit=True,
                search_service=search_service
            )
            
            print("📚 [编排器] RAG检索器初始化成功 (使用 pgvector)")
            
        except (ValueError, KeyError) as e:
            print(f"⚠️ [编排器] RAG检索器初始化数据错误: {e}")
            self.rag_retriever = None
        except (OSError, IOError) as e:
            print(f"⚠️ [编排器] RAG检索器初始化IO错误: {e}")
            self.rag_retriever = None
        except Exception as e:
            print(f"⚠️ [编排器] RAG检索器初始化失败: {e}")
            self.rag_retriever = None
    
    def _initialize_capabilities(self):
        """
        初始化能力配置（启动时一次性加载）
        
        从配置文件加载专家能力，生成描述文本，用于嵌入意图智能体提示词
        """
        try:
            from .capability_loader import get_capability_loader
            
            loader = get_capability_loader()
            loader.load_from_file()
            self._capability_config = loader._config
            
            self._specialist_descriptions = self._generate_specialist_descriptions()
            self._intent_mapping = loader.get_intent_mapping()
            
            intent_count = len(self._intent_mapping)
            specialist_count = len(set(self._intent_mapping.values()))
            print(f"✅ [编排器] 能力配置加载成功，共 {specialist_count} 个专家，{intent_count} 种意图类型")
            
        except Exception as e:
            print(f"⚠️ [编排器] 能力配置加载失败: {e}")
            self._specialist_descriptions = self._get_default_descriptions()
            self._intent_mapping = {}
    
    def _generate_specialist_descriptions(self) -> str:
        """
        从配置文件生成专家能力描述文本
        
        这些描述会被嵌入到意图智能体的提示词中
        """
        agents_config = self._capability_config.get('agents', {})
        
        descriptions = []
        for agent_type, config in agents_config.items():
            if not config.get('enabled', True):
                continue
            
            name = config.get('agent_name', agent_type)
            domains = [d['display_name'] for d in config.get('domains', [])]
            
            high_keywords = config.get('keywords', {}).get('high_weight', [])
            medium_keywords = config.get('keywords', {}).get('medium_weight', [])
            all_keywords = high_keywords + medium_keywords[:5]
            
            intent_mappings = []
            for intent, specialist in self._intent_mapping.items():
                if specialist == agent_type:
                    intent_mappings.append(intent)
            
            desc = f"""
### {name} ({agent_type})
- **核心领域**: {', '.join(domains[:5])}
- **关键词**: {', '.join(all_keywords[:10])}
- **识别的意图**: {', '.join(intent_mappings[:5]) if intent_mappings else '通用查询'}
"""
            descriptions.append(desc)
        
        return '\n'.join(descriptions)
    
    def _get_default_descriptions(self) -> str:
        """获取默认专家描述（当配置加载失败时使用）"""
        return """
### 财务专家 (finance)
- **核心领域**: 投资分析、贷款融资、预算管理、财务报表分析、成本控制
- **关键词**: 财务、投资、融资、贷款、报表、利润、成本、预算
- **识别的意图**: financial_analysis, accounting_query, investment_advisory

### 税务专家 (tax)
- **核心领域**: 税务计算、税务政策咨询、税务合规、发票管理
- **关键词**: 税务、税收、纳税、申报、抵扣、发票、税率
- **识别的意图**: tax_calculation, tax_planning, tax_compliance

### 法务专家 (legal)
- **核心领域**: 合同审查、法律咨询、合规检查、知识产权保护
- **关键词**: 法律、合同、协议、条款、违约、赔偿、合规
- **识别的意图**: contract_review, legal_consultation, compliance_check

### 通用助手 (general)
- **核心领域**: 通用查询、问候、闲聊
- **关键词**: 你好、请问、帮助
- **识别的意图**: greeting, chit_chat
"""
    
    def _get_prompt_context(self) -> Dict[str, Any]:
        """获取意图智能体提示词的渲染上下文"""
        return {
            "specialist_descriptions": self._specialist_descriptions,
            "intent_mapping": self._intent_mapping,
        }
    
    def _resolve_specialist(
        self,
        query: str,
        intent_result: Optional[IntentAnalysisResult] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        使用意图映射解析专家列表
        
        解析策略：
        1. 如果有意图分析结果，使用意图映射表
        2. 否则返回默认专家
        
        注意：这里只做简单的映射查询，不做运行时匹配计算
        """
        if not self._intent_mapping:
            logger.warning("⚠️ [编排器] 意图映射未初始化，使用默认路由")
            if intent_result and intent_result.requires_specialists:
                return intent_result.requires_specialists[:self.max_parallel_agents]
            return ["general"]
        
        if intent_result and intent_result.intent.value in self._intent_mapping:
            specialist = self._intent_mapping[intent_result.intent.value]
            logger.info(f"📊 [编排器] 意图映射路由: {intent_result.intent.value} -> {specialist}")
            return [specialist]
        
        if intent_result and intent_result.requires_specialists:
            return intent_result.requires_specialists[:self.max_parallel_agents]
        
        return ["general"]
    
    async def _emit_thinking_events(
        self,
        messages: List[Dict[str, Any]],
        interval: float = 2.0
    ) -> AsyncGenerator[str, None]:
        """
        定期发送思考事件
        
        Args:
            messages: 消息列表
            interval: 发送间隔（秒）
        """
        for i, msg in enumerate(messages):
            await asyncio.sleep(interval)
            yield json.dumps({
                "type": "thinking",
                "stage": msg.get("stage", "processing"),
                "message": msg.get("message", "正在思考..."),
                "progress": msg.get("progress", 50)
            }, ensure_ascii=False)
    
    async def _run_thinking_loop(
        self,
        messages: List[Dict[str, Any]],
        interval: float = 2.0,
        queue: Optional[asyncio.Queue] = None,
        stop_event: asyncio.Event|None = None
    ):
        """
        运行思考循环，通过队列发送进度消息直到任务完成
        
        Args:
            messages: 消息列表（会循环发送）
            interval: 发送间隔（秒）
            queue: 用于传递消息的队列
            stop_event: 停止事件（可选）
        """
        import itertools
        
        for msg in itertools.cycle(messages):
            if stop_event and stop_event.is_set():
                break
            
            await asyncio.sleep(interval)
            msg_data = {
                "type": "thinking",
                "stage": msg.get("stage", "processing"),
                "message": msg.get("message", "正在思考..."),
                "progress": msg.get("progress", 50)
            }
            json_msg = json.dumps(msg_data, ensure_ascii=False)
            
            if queue is not None:
                await queue.put(json_msg)
    
    async def stream_process_context(
        self,
        context: OrchestrationContext
    ) -> AsyncGenerator[str, None]:
        """
        流式处理编排上下文
        
        Args:
            context: 编排上下文
            
        Yields:
            逐步生成的内容（统一为JSON格式的stage事件或文本块）
        """
        from datetime import datetime
        
        if not self.initialized:
            await self.initialize()
        
        start_time = datetime.now()
        
        try:
            user_input = context.user_query
            
            yield json.dumps({"type": "stage", "stage": "receptionist"}, ensure_ascii=False)
            
            if not user_input:
                yield json.dumps({
                    "type": "error",
                    "error": "用户查询不能为空"
                }, ensure_ascii=False)
                yield json.dumps({
                    "type": "done",
                    "processing_time": 0
                }, ensure_ascii=False)
                return
            
            routing_result = await self.intent_router.run(
                user_input=user_input,
                history=[],
                context={"session_id": context.session_id, "tenant_id": context.tenant_id}
            )
            
            if routing_result.is_simple:
                yield json.dumps({"type": "stage", "stage": "response"}, ensure_ascii=False)
                yield json.dumps({
                    "type": "text",
                    "content": routing_result.simple_response
                }, ensure_ascii=False)
                
                processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                yield json.dumps({
                    "type": "done",
                    "processing_time": processing_time
                }, ensure_ascii=False)
                return
            
            yield json.dumps({"type": "stage", "stage": "intent"}, ensure_ascii=False)
            
            intent_result = routing_result.intent_result
            context.intent_result = intent_result
            
            if hasattr(intent_result, 'needs_report_generation') and intent_result.needs_report_generation:
                context.enable_report_generation = True
                print("📄 [编排器] 检测到用户要求生成报告")
            
            yield json.dumps({
                "type": "stage",
                "stage": "intent",
                "intent": {
                    "category": intent_result.intent.value,
                    "confidence": intent_result.confidence,
                    "routing_strategy": intent_result.routing_strategy.value
                }
            }, ensure_ascii=False)
            
            from app.services.admin_notification_service import (
                admin_notification_service
            )
            
            risk_check_result = await admin_notification_service.handle_high_risk_operation(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                user_query=user_input,
                context={
                    "confidence": intent_result.confidence,
                    "entities": getattr(intent_result, 'entities', []),
                    "intent": intent_result.intent.value
                }
            )
            
            if risk_check_result["status"] == "pending_approval":
                yield json.dumps({
                    "type": "error",
                    "error": f"⚠️ 检测到高风险操作，当前请求需要管理员审批。审批ID: {risk_check_result['approval_id']}"
                }, ensure_ascii=False)
                yield json.dumps({
                    "type": "done",
                    "processing_time": int((datetime.now() - start_time).total_seconds() * 1000)
                }, ensure_ascii=False)
                return
            
            yield json.dumps({"type": "stage", "stage": "specialists"}, ensure_ascii=False)
            
            if intent_result.routing_strategy == RoutingStrategy.SINGLE_SPECIALIST:
                specialist_type = intent_result.requires_specialists[0] if intent_result.requires_specialists else "finance"
                specialist_name_map = {"finance": "💰 财务专家", "tax": "📋 税务专家", "legal": "⚖️ 法务专家"}
                specialist_display = specialist_name_map.get(specialist_type, specialist_type)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "analyzing",
                    "message": f"正在连接 {specialist_display}...",
                    "progress": 10
                }, ensure_ascii=False)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "retrieving",
                    "message": "正在检索相关数据...",
                    "progress": 25
                }, ensure_ascii=False)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "querying",
                    "message": "正在查询企业财务数据...",
                    "progress": 40
                }, ensure_ascii=False)
                
                thinking_messages = [
                    {"stage": "analyzing", "message": f"{specialist_display}正在思考中...", "progress": 50},
                    {"stage": "processing", "message": "正在分析财务指标...", "progress": 55},
                    {"stage": "analyzing", "message": "正在评估风险因素...", "progress": 60},
                    {"stage": "synthesizing", "message": "正在整合分析结果...", "progress": 65},
                ]
                
                thinking_queue = asyncio.Queue()
                
                specialist_task = asyncio.create_task(
                    self._handle_single_specialist(user_input, intent_result)
                )
                thinking_task = asyncio.create_task(
                    self._run_thinking_loop(thinking_messages, interval=3.0, queue=thinking_queue)
                )
                
                specialist_result = None
                
                while not specialist_task.done():
                    try:
                        msg = await asyncio.wait_for(thinking_queue.get(), timeout=0.5)
                        yield msg
                    except asyncio.TimeoutError:
                        continue
                
                specialist_result = specialist_task.result()
                thinking_task.cancel()
                try:
                    await thinking_task
                except asyncio.CancelledError:
                    pass
                
                specialists_needed = intent_result.requires_specialists[:1] if intent_result.requires_specialists else []
                suggested = intent_result.requires_specialists[0] if intent_result.requires_specialists else None
                yield json.dumps({
                    "type": "stage",
                    "stage": "specialists",
                    "specialists": specialists_needed
                }, ensure_ascii=False)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "analyzing",
                    "message": f"正在分析 {specialist_display} 的回复...",
                    "progress": 70
                }, ensure_ascii=False)
                
                context.specialist_results.append({
                    'specialist_type': suggested,
                    'specialist_name': suggested,
                    'response': specialist_result,
                    'success': specialist_result.get('success', True)
                })
                
                if context.enable_reflection:
                    yield json.dumps({"type": "stage", "stage": "reflection"}, ensure_ascii=False)
                    specialist_result_str = json.dumps(specialist_result, ensure_ascii=False)
                    reflection_result = await review_quality(
                        user_question=user_input,
                        ai_answer=specialist_result_str
                    )
                    context.reflection_result = reflection_result
                    yield json.dumps({
                        "type": "stage",
                        "stage": "reflection",
                        "result": reflection_result.get("issues", [])
                    }, ensure_ascii=False)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "generating",
                    "message": "正在生成最终回复...",
                    "progress": 85
                }, ensure_ascii=False)
                
                yield json.dumps({"type": "stage", "stage": "response"}, ensure_ascii=False)
                
                final_response = await self._format_specialist_response(
                    specialist_result,
                    intent_result,
                    user_input
                )
                yield json.dumps({
                    "type": "text",
                    "content": final_response
                }, ensure_ascii=False)
                
                processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                yield json.dumps({
                    "type": "done",
                    "processing_time": processing_time
                }, ensure_ascii=False)
                return
            
            elif intent_result.routing_strategy in [
                RoutingStrategy.MULTI_SPECIALIST_PARALLEL,
                RoutingStrategy.MULTI_SPECIALIST_SEQUENTIAL
            ]:
                yield json.dumps({
                    "type": "thinking",
                    "stage": "preparing",
                    "message": "正在准备多专家协作分析...",
                    "progress": 15
                }, ensure_ascii=False)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "coordinating",
                    "message": f"正在协调 {len(intent_result.requires_specialists)} 个专业顾问...",
                    "progress": 30
                }, ensure_ascii=False)
                
                specialist_results = await self._handle_multi_specialist(
                    user_input, intent_result
                )
                
                specialists_needed = list(specialist_results.get('results', {}).keys())
                yield json.dumps({
                    "type": "stage",
                    "stage": "specialists",
                    "specialists": specialists_needed
                }, ensure_ascii=False)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "analyzing",
                    "message": "正在综合分析各专家意见...",
                    "progress": 70
                }, ensure_ascii=False)
                
                for specialist_name, result in specialist_results.get('results', {}).items():
                    context.specialist_results.append({
                        'specialist_type': specialist_name,
                        'specialist_name': specialist_name,
                        'response': result,
                        'success': result.get('status') == 'success'
                    })
                
                if context.enable_reflection:
                    yield json.dumps({"type": "stage", "stage": "reflection"}, ensure_ascii=False)
                    specialist_results_str = json.dumps(specialist_results, ensure_ascii=False)
                    reflection_result = await review_quality(
                        user_question=user_input,
                        ai_answer=specialist_results_str
                    )
                    context.reflection_result = reflection_result
                    yield json.dumps({
                        "type": "stage",
                        "stage": "reflection",
                        "result": reflection_result.get("issues", [])
                    }, ensure_ascii=False)
                
                yield json.dumps({
                    "type": "thinking",
                    "stage": "generating",
                    "message": "正在生成综合分析报告...",
                    "progress": 85
                }, ensure_ascii=False)
                
                yield json.dumps({"type": "stage", "stage": "response"}, ensure_ascii=False)
                
                final_response = await self._format_multi_specialist_response(
                    specialist_results,
                    intent_result,
                    user_input
                )
                yield json.dumps({
                    "type": "text",
                    "content": final_response
                }, ensure_ascii=False)
                
                processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                yield json.dumps({
                    "type": "done",
                    "processing_time": processing_time
                }, ensure_ascii=False)
                return
            
            elif intent_result.routing_strategy == RoutingStrategy.REPORT_QUEUE:
                yield json.dumps({
                    "type": "error",
                    "error": "报告生成请求已加入队列"
                }, ensure_ascii=False)
                yield json.dumps({
                    "type": "done",
                    "processing_time": int((datetime.now() - start_time).total_seconds() * 1000)
                }, ensure_ascii=False)
                return
            
            yield json.dumps({
                "type": "error",
                "error": "抱歉，暂时无法处理您的请求，请稍后重试。"
            }, ensure_ascii=False)
            yield json.dumps({
                "type": "done",
                "processing_time": int((datetime.now() - start_time).total_seconds() * 1000)
            }, ensure_ascii=False)
            
        except Exception as e:
            print(f"❌ [编排器] 流式处理错误: {e}")
            traceback.print_exc()
            yield json.dumps({
                "type": "error",
                "error": str(e)
            }, ensure_ascii=False)
            yield json.dumps({
                "type": "done",
                "processing_time": int((datetime.now() - start_time).total_seconds() * 1000)
            }, ensure_ascii=False)
    
    async def stream_process(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式处理请求（API路由专用方法）
        
        Args:
            user_input: 用户输入
            session_id: 会话ID
            history: 历史消息
            
        Yields:
            逐步生成的内容
        """
        context = OrchestrationContext(
            session_id=session_id or str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            user_query=user_input,
            context={"history": history or []},
            enable_reflection=self.enable_reflection,
            enable_rag=self.enable_rag
        )
        
        async for chunk in self.stream_process_context(context):
            yield chunk
    
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
            rag_context = await self.rag_retriever.retrieve(
                query=user_input,
                tenant_id=self.tenant_id,
                top_k=5
            )
            
            results = rag_context.results if rag_context else []
            
            if not results:
                return "抱歉，我在知识库中没有找到相关信息。"
            
            context = "\n".join([
                f"- {r.content[:200]}"
                for r in results[:3]
            ])
            
            prompt = f"""根据以下知识库内容回答用户问题：

知识库内容：
{context}

用户问题：{user_input}

请给出准确、简洁的回答。"""
            
            response = await self.llm_adapter.agenerate([prompt])
            return response.content if response and response.content else "抱歉，未能生成回答。"
            
        except (ValueError, KeyError) as e:
            print(f"⚠️ [编排器] RAG检索数据错误: {e}")
            return "抱歉，知识库检索数据错误。"
        except (OSError, IOError) as e:
            print(f"⚠️ [编排器] RAG检索IO错误: {e}")
            return "抱歉，知识库检索IO错误。"
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
        
        rag_context = None
        if self.enable_rag and self.rag_retriever:
            try:
                print("📚 [编排器] 正在检索企业相关数据...")
                rag_retrieval_context = await self.rag_retriever.retrieve(
                    query=user_input,
                    tenant_id=self.tenant_id,
                    top_k=5
                )
                
                rag_results = rag_retrieval_context.results if rag_retrieval_context else []
                
                if rag_results:
                    print(f"📚 [编排器] 检索到 {len(rag_results)} 条相关数据")
                    rag_context = {
                        "documents": [
                            {
                                "content": r.content,
                                "source": r.source,
                                "doc_type": r.doc_type.value if hasattr(r.doc_type, 'value') else str(r.doc_type),
                                "metadata": r.metadata
                            }
                            for r in rag_results
                        ],
                        "summary": self._generate_rag_summary([
                            {"content": r.content, "source": r.source}
                            for r in rag_results
                        ]),
                        "specialist_type": specialist_name
                    }
                else:
                    print("📚 [编排器] 未检索到相关数据")
                    rag_context = {
                        "documents": [],
                        "summary": "未找到企业相关数据",
                        "specialist_type": specialist_name,
                        "has_data": False,
                        "data_status": "no_data"
                    }
            except Exception as e:
                print(f"⚠️ [编排器] RAG检索失败: {e}")
                rag_context = {
                    "documents": [],
                    "summary": "数据检索失败",
                    "specialist_type": specialist_name,
                    "has_data": False,
                    "data_status": "retrieval_error"
                }
        
        specialist_context = intent_result.suggested_params or {}
        specialist_context["tenant_id"] = self.tenant_id
        specialist_context["user_id"] = self.user_id
        
        has_data = rag_context and rag_context.get("has_data", len(rag_context.get("documents", [])) > 0)
        requires_enterprise_data = self._requires_enterprise_data(user_input, intent_result)
        
        print("🔍 [编排器] 数据可用性检查:")
        print(f"   - requires_enterprise_data: {requires_enterprise_data}")
        print(f"   - has_data: {has_data}")
        print(f"   - rag_context: {rag_context}")
        
        if requires_enterprise_data and not has_data:
            print("📭 [编排器] 检测到需要企业数据但无可用数据，跳过专家调用")
            return {
                "status": "no_data",
                "specialist": specialist_name,
                "result": self._generate_no_data_response(user_input, specialist_name, intent_result),
                "data_status": "insufficient",
                "suggestions": self._generate_data_import_suggestions(user_input, specialist_name)
            }
        
        try:
            if hasattr(specialist, 'consult'):
                result = await specialist.consult(
                    query=user_input,
                    entities=intent_result.entities,
                    context=specialist_context,
                    rag_context=rag_context
                )
            else:
                result = await specialist.run(
                    user_input=user_input,
                    context=specialist_context,
                    rag_context=rag_context
                )
            
            return {
                "status": "success",
                "specialist": specialist_name,
                "result": result
            }
            
        except (ValueError, KeyError) as e:
            print(f"❌ [编排器] 专家调用数据错误: {e}")
            return {
                "status": "error",
                "error": f"专家调用数据错误: {str(e)}"
            }
        except (OSError, IOError) as e:
            print(f"❌ [编排器] 专家调用IO错误: {e}")
            return {
                "status": "error",
                "error": f"专家调用IO错误: {str(e)}"
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
        
        specialist_context = intent_result.suggested_params or {}
        specialist_context["tenant_id"] = self.tenant_id
        specialist_context["user_id"] = self.user_id
        
        if intent_result.routing_strategy == RoutingStrategy.MULTI_SPECIALIST_PARALLEL:
            tasks = []
            for specialist_name in specialists_needed[:self.max_parallel_agents]:
                specialist = specialist_map.get(specialist_name)
                if specialist:
                    if hasattr(specialist, 'consult'):
                        task = specialist.consult(
                            query=user_input,
                            entities=intent_result.entities,
                            context=specialist_context
                        )
                    else:
                        task = specialist.run(
                            user_input=user_input,
                            context=specialist_context
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
                except (ValueError, KeyError) as e:
                    results[specialist_name] = {
                        "status": "error",
                        "error": f"数据错误: {str(e)}"
                    }
                except (OSError, IOError) as e:
                    results[specialist_name] = {
                        "status": "error",
                        "error": f"IO错误: {str(e)}"
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
            results = {}
            accumulated_context = specialist_context.copy()
            
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
                    
                except (ValueError, KeyError) as e:
                    results[specialist_name] = {
                        "status": "error",
                        "error": f"数据错误: {str(e)}"
                    }
                except (OSError, IOError) as e:
                    results[specialist_name] = {
                        "status": "error",
                        "error": f"IO错误: {str(e)}"
                    }
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
    
    def _generate_rag_summary(self, rag_results: List[Dict[str, Any]]) -> str:
        """
        生成RAG检索结果的摘要
        
        Args:
            rag_results: RAG检索结果
            
        Returns:
            摘要文本
        """
        if not rag_results:
            return ""
        
        try:
            summary_parts = []
            
            financial_keywords = ['财务', '投资', '融资', '贷款', '报表', '利润', '成本', '预算', '现金流', '盈利', '亏损', '资产', '负债', '权益']
            tax_keywords = ['税务', '税收', '纳税', '申报', '抵扣', '发票', '税率', '税额', '免税', '退税']
            legal_keywords = ['法律', '合同', '协议', '条款', '违约', '赔偿', '合规', '知识产权', '专利', '商标']
            
            relevant_docs = []
            for doc in rag_results:
                content = doc.get('content', '').lower()
                score = doc.get('score', 0)
                
                if any(kw in content for kw in financial_keywords):
                    relevant_docs.append((doc, score, 'finance'))
                elif any(kw in content for kw in tax_keywords):
                    relevant_docs.append((doc, score, 'tax'))
                elif any(kw in content for kw in legal_keywords):
                    relevant_docs.append((doc, score, 'legal'))
                else:
                    relevant_docs.append((doc, score, 'general'))
            
            relevant_docs.sort(key=lambda x: x[1], reverse=True)
            
            summary_parts.append(f"共检索到 {len(rag_results)} 条相关数据，以下是关键信息摘要：\n")
            
            for i, (doc, score, category) in enumerate(relevant_docs[:3], 1):
                content = doc.get('content', '')[:300]
                metadata = doc.get('metadata', {})
                title = metadata.get('title', f'文档{i}')
                
                summary_parts.append(f"\n**{i}. {title}** (相关性: {score:.2f}, 类型: {category})")
                summary_parts.append(f"   {content}...")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            print(f"⚠️ [编排器] 生成RAG摘要失败: {e}")
            return f"检索到 {len(rag_results)} 条相关数据"
    
    def _requires_enterprise_data(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> bool:
        """
        判断用户查询是否需要企业特定数据
        
        Args:
            user_input: 用户输入
            intent_result: 意图识别结果
            
        Returns:
            是否需要企业数据
        """
        user_input_lower = user_input.lower()
        
        enterprise_patterns = [
            r'我们', r'我司', r'贵公司', r'本公司', r'本企业',
            r'公司', r'企业', r'财务状况', r'经营情况',
            r'税务情况', r'风险分析', r'财务风险', r'税务风险'
        ]
        
        for pattern in enterprise_patterns:
            if re.search(pattern, user_input_lower):
                return True
        
        specialist_keywords = ['finance', 'tax', 'legal', '财务', '税务', '法务', '风险']
        if any(keyword in user_input_lower for keyword in specialist_keywords):
            return True
        
        return False
    
    def _generate_no_data_response(
        self,
        user_input: str,
        specialist_type: str,
        intent_result: IntentAnalysisResult
    ) -> Dict[str, Any]:
        """
        生成数据缺失时的响应
        
        Args:
            user_input: 用户输入
            specialist_type: 专家类型
            intent_result: 意图识别结果
            
        Returns:
            结构化的无数据响应
        """
        specialist_names = {
            "finance": "财务专家",
            "tax": "税务专家",
            "legal": "法务专家"
        }
        
        specialist_name = specialist_names.get(specialist_type, "专家")
        intent_display = intent_result.intent.value.replace("_", " ").title() if intent_result.intent else "分析"
        
        return {
            "specialist_type": specialist_type,
            "status": "no_data",
            "response": f"感谢您的{specialist_name}咨询！根据您的问题「{user_input}」，这是一个需要企业特定{specialist_name}数据才能完成的专业{intent_display}。",
            "summary": f"当前系统中未检索到您的企业相关{specialist_name}数据，无法直接生成{specialist_name}报告。",
            "current_status": "暂无数据",
            "confidence_score": 0.0,
            "limitations": [
                "企业财务/税务数据尚未导入系统",
                "无法进行定量分析",
                "无法生成具体风险评估"
            ],
            "available_actions": [
                "导入企业财务数据",
                "上传税务申报材料",
                "完善企业基础信息"
            ],
            "general_guidance": self._get_general_guidance(specialist_type, user_input)
        }
    
    def _generate_data_import_suggestions(
        self,
        user_input: str,
        specialist_type: str
    ) -> List[Dict[str, Any]]:
        """
        生成数据导入建议
        
        Args:
            user_input: 用户输入
            specialist_type: 专家类型
            
        Returns:
            数据导入建议列表
        """
        suggestions = []
        
        if specialist_type == "finance":
            suggestions.extend([
                {
                    "type": "data_import",
                    "title": "导入财务数据",
                    "description": "通过财务数据上传功能导入您的企业财务报表",
                    "action": "/api/v1/financial/upload",
                    "required_fields": ["资产负债表", "利润表", "现金流量表"],
                    "format": "支持 Excel/CSV 格式"
                },
                {
                    "type": "manual_entry",
                    "title": "手动录入",
                    "description": "如果数据量较小，可以选择手动录入关键财务指标",
                    "action": "/api/v1/financial/manual-entry",
                    "required_fields": ["年度收入", "年度支出", "净利润"]
                }
            ])
        elif specialist_type == "tax":
            suggestions.extend([
                {
                    "type": "document_upload",
                    "title": "上传税务申报材料",
                    "description": "上传增值税申报表、企业所得税申报表等税务材料",
                    "action": "/api/v1/tax/upload",
                    "required_fields": ["增值税申报表", "企业所得税申报表"],
                    "format": "支持 PDF/Excel 格式"
                },
                {
                    "type": "api_integration",
                    "title": "对接电子税务局",
                    "description": "如果您的企业已开通电子税务局接口，可以实现数据自动同步",
                    "action": "/settings/api-integration",
                    "benefits": ["数据自动同步", "实时风险监控", "智能预警"]
                }
            ])
        else:
            suggestions.append({
                "type": "general",
                "title": "完善企业信息",
                "description": "请先完善企业的基本信息和相关业务数据",
                "action": "/settings/enterprise-profile"
            })
        
        return suggestions
    
    def _get_general_guidance(
        self,
        specialist_type: str,
        user_input: str
    ) -> Dict[str, Any]:
        """
        获取通用指导信息（数据缺失时提供）
        
        Args:
            specialist_type: 专家类型
            user_input: 用户输入
            
        Returns:
            通用指导信息
        """
        if specialist_type == "finance":
            return {
                "topic": "企业财务风险分析",
                "general_knowledge": [
                    "财务风险主要包括：流动性风险、信用风险、市场风险、操作风险",
                    "常用的财务风险指标包括：流动比率、速动比率、资产负债率、利息保障倍数等",
                    "建议企业定期进行财务健康度评估，及时发现潜在风险"
                ],
                "best_practices": [
                    "建立完善的财务管理制度",
                    "加强现金流管理，确保流动性充足",
                    "控制负债规模，优化资本结构",
                    "定期进行财务分析和风险评估"
                ],
                "next_steps": "导入财务数据后，系统将为您提供详细的风险评估和改进建议"
            }
        elif specialist_type == "tax":
            return {
                "topic": "企业税务风险分析",
                "general_knowledge": [
                    "企业税务风险主要包括：申报不合规风险、发票管理风险、税收优惠政策适用风险",
                    "常见的税务风险点：进项税额抵扣不规范、税率适用错误、申报时间延误",
                    "建议企业建立税务风险管理体系，定期进行税务健康检查"
                ],
                "best_practices": [
                    "确保发票管理规范，保留完整的抵扣凭证",
                    "关注税收政策变化，及时调整税务筹划",
                    "按时进行税务申报，避免逾期罚款",
                    "建立税务档案，便于后续查阅和审计"
                ],
                "next_steps": "导入税务数据后，系统将为您识别具体的税务风险点并提供改进建议"
            }
        else:
            return {
                "topic": "企业风险分析",
                "general_knowledge": [
                    "企业风险分析需要基于完整的数据才能得出准确结论",
                    "建议完善企业数据后再进行深入分析"
                ],
                "best_practices": [],
                "next_steps": "请先导入相关业务数据"
            }
    
    async def _run_reflection(
        self,
        context: OrchestrationContext,
        user_input: str
    ) -> OrchestrationContext:
        """运行反思审核"""
        if not context.enable_reflection:
            return context

        pass

        try:
            specialist_results_str = json.dumps(context.specialist_results, ensure_ascii=False)
            reflection_result = await review_quality(
                user_question=user_input,
                ai_answer=specialist_results_str
            )

            context.reflection_result = reflection_result

            if not reflection_result.get("is_quality_acceptable", True):
                pass
                context.metadata["revision_suggestions"] = reflection_result.get(
                    "issues", []
                )

            overall_score = reflection_result.get("scores", {}).get("overall", 1.0)
            if overall_score < 0.7:
                context.needs_human_review = True
                pass
            
        except (ValueError, KeyError) as e:
            print(f"⚠️ [编排器] 反思审核数据错误: {e}")
        except (OSError, IOError) as e:
            print(f"⚠️ [编排器] 反思审核IO错误: {e}")
        except Exception as e:
            print(f"⚠️ [编排器] 反思审核失败: {e}")
        
        return context
    
    async def _synthesize_output(
        self,
        user_query: str,
        specialist_results: List[Dict[str, Any]],
        intent_result: IntentAnalysisResult
    ) -> str:
        """使用 OutputAgent 合成多专家结果
        
        Args:
            user_query: 用户原始问题
            specialist_results: 各专家的分析结果
            intent_result: 意图识别结果
            
        Returns:
            合成后的自然语言响应
        """
        try:
            task_id = f"task_{datetime.now().timestamp()}"
            
            for result in specialist_results:
                source_agent = result.get('specialist_type', 'unknown')
                source_type = result.get('specialist_name', 'specialist')
                content = result.get('analysis', {}) or result.get('response', {}).get('result', {})
                confidence = result.get('confidence', 0.8)
                
                if isinstance(content, dict):
                    content = json.dumps(content, ensure_ascii=False)
                
                output_agent.add_input(
                    task_id=task_id,
                    source_agent=source_agent,
                    source_type=source_type,
                    content=content,
                    confidence=confidence,
                    metadata={
                        "intent": intent_result.intent.value,
                        "user_query": user_query
                    }
                )
            
            from app.agent_framework.core.output_agent import SynthesisStrategy
            
            synthesis_result = await output_agent.synthesize(
                user_query=user_query,
                strategy=SynthesisStrategy.MERGE
            )
            
            if synthesis_result and synthesis_result.final_response:
                return synthesis_result.final_response
            
            return self._format_fallback_response(specialist_results, intent_result)
            
        except Exception as e:
            print(f"⚠️ [编排器] OutputAgent 合成失败: {e}")
            return self._format_fallback_response(specialist_results, intent_result)
    
    def _format_fallback_response(
        self,
        specialist_results: List[Dict[str, Any]],
        intent_result: IntentAnalysisResult
    ) -> str:
        """格式化备用响应（当 OutputAgent 失败时使用）
        
        Args:
            specialist_results: 各专家的分析结果
            intent_result: 意图识别结果
            
        Returns:
            格式化的响应文本
        """
        response_parts = []
        
        specialist_name_map = {
            "finance": "💰 财务专家",
            "tax": "📋 税务专家",
            "legal": "⚖️ 法务专家"
        }
        
        for result in specialist_results:
            specialist_type = result.get('specialist_type', 'unknown')
            specialist_display = specialist_name_map.get(specialist_type, "🤖 专家")
            
            analysis = result.get('analysis', {}) or result.get('response', {}).get('result', {})
            
            if not isinstance(analysis, dict):
                continue
            
            response_parts.append(f"## {specialist_display}\n")
            
            if specialist_type == "finance":
                if analysis.get('financial_indicators'):
                    response_parts.append("### 📊 财务指标\n")
                    for key, value in analysis.get('financial_indicators', {}).items():
                        response_parts.append(f"- **{key}**: {value}")
                    response_parts.append("")
                
                if analysis.get('risk_factors'):
                    response_parts.append("### ⚠️ 风险因素\n")
                    for risk in analysis.get('risk_factors', [])[:5]:
                        response_parts.append(f"- {risk}")
                    response_parts.append("")
                
                if analysis.get('recommendations'):
                    response_parts.append("### 💡 建议\n")
                    for rec in analysis.get('recommendations', [])[:5]:
                        response_parts.append(f"- {rec}")
                    response_parts.append("")
            
            elif specialist_type == "tax":
                if analysis.get('tax_type'):
                    response_parts.append(f"**税种**: {analysis.get('tax_type')}\n")
                if analysis.get('risk_points'):
                    response_parts.append("### ⚠️ 风险点\n")
                    for point in analysis.get('risk_points', [])[:5]:
                        response_parts.append(f"- {point}")
                    response_parts.append("")
                if analysis.get('recommendations'):
                    response_parts.append("### 💡 建议\n")
                    for rec in analysis.get('recommendations', [])[:5]:
                        response_parts.append(f"- {rec}")
                    response_parts.append("")
            
            elif specialist_type == "legal":
                if analysis.get('risk_points'):
                    response_parts.append("### ⚠️ 法律风险\n")
                    for risk in analysis.get('risk_points', [])[:5]:
                        response_parts.append(f"- {risk}")
                    response_parts.append("")
                if analysis.get('suggestions'):
                    response_parts.append("### 💡 建议\n")
                    for sug in analysis.get('suggestions', [])[:5]:
                        response_parts.append(f"- {sug}")
                    response_parts.append("")
            
            confidence = analysis.get('confidence', result.get('confidence', 0.8))
            response_parts.append(f"**置信度**: {confidence * 100:.0f}%\n")
            response_parts.append("\n---\n")
        
        return "\n".join(response_parts) if response_parts else "感谢您的提问，请稍后查看分析结果。"
    
    async def _generate_report(
        self,
        user_query: str,
        specialist_results: List[Dict[str, Any]],
        intent_result: IntentAnalysisResult
    ) -> str:
        """生成综合报告
        
        Args:
            user_query: 用户原始问题
            specialist_results: 各专家的分析结果
            intent_result: 意图识别结果
            
        Returns:
            生成的报告文本
        """
        if not self.report_generator:
            print("⚠️ [编排器] ReportGenerator 未初始化，使用 OutputAgent 合成")
            return await self._synthesize_output(user_query, specialist_results, intent_result)
        
        try:
            from app.multi_agent_system.agents.report_generator import ReportType, ReportFormat
            
            report_type = ReportType.COMPREHENSIVE
            report_format = ReportFormat.MARKDOWN
            
            if intent_result.intent == IntentCategory.FINANCIAL_ANALYSIS:
                report_type = ReportType.SPECIALIST
            elif intent_result.intent == IntentCategory.TAX_CALCULATION:
                report_type = ReportType.SPECIALIST
            elif intent_result.intent == IntentCategory.LEGAL_CONSULTATION:
                report_type = ReportType.SPECIALIST
            
            report_result = await self.report_generator.generate(
                user_query=user_query,
                specialist_results=specialist_results,
                intent_result=intent_result,
                report_type=report_type,
                report_format=report_format
            )
            
            if report_result and report_result.get('content'):
                return report_result['content']
            
            return await self._synthesize_output(user_query, specialist_results, intent_result)
            
        except Exception as e:
            print(f"⚠️ [编排器] ReportGenerator 生成失败: {e}")
            return await self._synthesize_output(user_query, specialist_results, intent_result)
    
    def _format_no_data_response(
        self,
        specialist_result: Dict[str, Any],
        intent_result: IntentAnalysisResult,
        user_query: str = ""
    ) -> str:
        """
        格式化数据缺失时的响应
        
        Args:
            specialist_result: 专家结果
            intent_result: 意图识别结果
            user_query: 用户查询
            
        Returns:
            格式化的无数据响应
        """
        result = specialist_result.get("result", {})
        specialist_type = specialist_result.get("specialist", "general")
        suggestions = specialist_result.get("suggestions", [])
        
        specialist_name_map = {
            "finance": "💰 财务专家",
            "tax": "📋 税务专家",
            "legal": "⚖️ 法务专家"
        }
        
        specialist_display = specialist_name_map.get(specialist_type, "📊 专家")
        response_text = result.get("response", "")
        summary = result.get("summary", "")
        general_guidance = result.get("general_guidance", {})
        limitations = result.get("limitations", [])
        available_actions = result.get("available_actions", [])
        
        suggestions_html = ""
        if suggestions:
            suggestions_html = "\n### 📥 数据导入建议\n\n"
            for i, suggestion in enumerate(suggestions, 1):
                suggestions_html += f"{i}. **{suggestion.get('title', '导入数据')}**\n"
                suggestions_html += f"   - {suggestion.get('description', '')}\n"
                if suggestion.get('required_fields'):
                    suggestions_html += f"   - 必填字段: {', '.join(suggestion.get('required_fields', []))}\n"
                if suggestion.get('format'):
                    suggestions_html += f"   - 支持格式: {suggestion.get('format', '')}\n"
        
        limitations_html = ""
        if limitations:
            limitations_html = "\n### ⚠️ 当前限制\n\n"
            for limitation in limitations:
                limitations_html += f"- {limitation}\n"
        
        guidance_html = ""
        if general_guidance:
            guidance_html = f"""
### 📚 {general_guidance.get('topic', '通用指导')}

#### 基础知识
"""
            for knowledge in general_guidance.get('general_knowledge', []):
                guidance_html += f"- {knowledge}\n"
            
            if general_guidance.get('best_practices'):
                guidance_html += "\n#### 最佳实践\n"
                for practice in general_guidance.get('best_practices', []):
                    guidance_html += f"- {practice}\n"
            
            if general_guidance.get('next_steps'):
                guidance_html += f"\n> 💡 **下一步**: {general_guidance.get('next_steps', '')}\n"
        
        response = f"""## {specialist_display}

### 📋 分析说明

{response_text}

{summary}

{limitations_html}
{guidance_html}
{suggestions_html}

---

**💡 温馨提示**: 为了给您提供更准确的分析报告，建议您先导入企业的相关财务/税务数据。您也可以通过左侧导航栏的「数据管理」功能查看数据导入指南。
"""
        
        return response
    
    async def _format_specialist_response(
        self,
        specialist_result: Dict[str, Any],
        intent_result: IntentAnalysisResult,
        user_query: str = ""
    ) -> str:
        """格式化单专家响应（委托给 OutputAgent）"""
        if specialist_result.get("status") == "no_data":
            formatted_no_data = self._format_no_data_response(specialist_result, intent_result, user_query)
            
            if self.output_agent:
                try:
                    specialist_type = specialist_result.get("specialist", "general")
                    specialist_name_map = {
                        "finance": "财务专家",
                        "tax": "税务专家",
                        "legal": "法务专家"
                    }
                    specialist_display = specialist_name_map.get(specialist_type, "专家")
                    
                    logger.info("📤 [输出智能体] 正在美化无数据响应...")
                    formatted = await self.output_agent.synthesize_and_format(
                        {specialist_display: formatted_no_data},
                        user_query
                    )
                    logger.info("📤 [输出智能体] 无数据响应美化完成")
                    return formatted
                except Exception as e:
                    logger.warning(f"⚠️ [输出智能体] 美化无数据响应失败: {e}")
            
            return formatted_no_data
        
        if specialist_result.get("status") == "success":
            specialist_key = specialist_result.get("specialist", "specialist")
            result = specialist_result.get("result", "")

            specialist_name_map = {
                "finance": "财务专家",
                "tax": "税务专家",
                "legal": "法务专家"
            }

            specialist_display = specialist_name_map.get(specialist_key, "专家")

            specialist_results = {specialist_display: result}

            if self.output_agent:
                try:
                    logger.info("📤 [输出智能体] 开始整合专家结果...")
                    formatted = await self.output_agent.synthesize_and_format(
                        specialist_results,
                        user_query
                    )
                    logger.info("📤 [输出智能体] 整合完成")
                    return formatted
                except Exception as e:
                    logger.warning(f"⚠️ [输出智能体] 整合失败: {e}")

            if isinstance(result, dict):
                result = result.get("analysis", result.get("content", str(result)))

            return f"## {specialist_display}\n\n{result}"

        error_msg = specialist_result.get("error", "处理失败")
        specialist_display = specialist_result.get("specialist", "专家")
        specialist_name_map = {"finance": "💰 财务专家", "tax": "📋 税务专家", "legal": "⚖️ 法务专家"}
        
        return f"""## {specialist_name_map.get(specialist_display, specialist_display)}

### ❌ 处理失败

{error_msg}

---

请稍后重试，或联系管理员协助处理。"""
    
    async def _format_multi_specialist_response(
        self,
        specialist_results: Dict[str, Any],
        intent_result: IntentAnalysisResult,
        user_query: str = ""
    ) -> str:
        """格式化多专家响应"""
        specialist_name_map = {
            "finance": "财务专家",
            "tax": "税务专家",
            "legal": "法务专家"
        }

        results = specialist_results.get("results", specialist_results)
        specialist_results_for_synthesis = {}

        for specialist_name, result in results.items():
            is_success = result.get("status") == "success" or result.get("success") is True
            if is_success:
                specialist_display = specialist_name_map.get(specialist_name, specialist_name)
                specialist_response = result.get("result", "")
                if isinstance(specialist_response, dict):
                    specialist_response = specialist_response.get("analysis", specialist_response.get("content", str(specialist_response)))
                specialist_results_for_synthesis[specialist_display] = specialist_response

        if not specialist_results_for_synthesis:
            return "⚠️ 抱歉，所有专家处理均失败。"

        if self.output_agent:
            try:
                logger.info(f"📤 [输出智能体-多专家] 开始整合 {len(specialist_results_for_synthesis)} 位专家结果...")
                formatted_output = await self.output_agent.synthesize_and_format(
                    specialist_results_for_synthesis,
                    user_query
                )
                logger.info("📤 [输出智能体-多专家] 整合完成")
                return formatted_output
            except Exception as e:
                logger.warning(f"⚠️ [输出智能体-多专家] 整合失败: {e}")

        combined_response = "\n\n---\n\n".join(
            f"### {name}\n\n{content}"
            for name, content in specialist_results_for_synthesis.items()
        )
        return combined_response
    
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
        
        report_sections = []
        
        report_sections.append("# 多智能体分析报告\n")
        report_sections.append(f"**会话ID**: {session_id}\n")
        report_sections.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report_sections.append(f"**报告类型**: {report_type}\n")
        report_sections.append("\n---\n")
        
        if self.context and self.context.intent_result:
            report_sections.append("## 意图分析\n")
            intent = self.context.intent_result
            report_sections.append(f"- **主要意图**: {intent.intent}\n")
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
        report_sections.append("*本报告由多智能体系统自动生成*\n")
        
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
