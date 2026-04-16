"""
Orchestrator LangGraph 适配器

将现有的 AgentOrchestrator 与 LangGraph 集成
"""

import logging
from langgraph.graph import StateGraph, END, START

from .state import AgentState, create_initial_state
from .conditional import route_by_intent, route_reflection_result, route_by_specialists
from ..schemas.multi_agent import SpecialistType, IntentCategory, SpecialistResult
from ..multi_agent_system.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)


class OrchestratorAdapter:
    """
    Orchestrator LangGraph 适配器
    
    将现有的 AgentOrchestrator 包装为 LangGraph 节点
    """
    
    def __init__(self, orchestrator: AgentOrchestrator):
        """
        初始化适配器
        
        Args:
            orchestrator: 现有的 AgentOrchestrator 实例
        """
        self.orchestrator = orchestrator
    
    async def reception_node(self, state: AgentState) -> AgentState:
        """接待员节点"""
        logger.info("[Adapter:Reception] 处理请求")
        
        if not self.orchestrator.initialized:
            await self.orchestrator.initialize()
        
        try:
            response = await self.orchestrator.receptionist.run(
                user_input=state["user_query"],
                session_id=state["session_id"]
            )
            
            return {
                **state,
                "metadata": {
                    **state["metadata"],
                    "reception_response": response
                }
            }
        except Exception as e:
            logger.error(f"[Adapter:Reception] 错误: {e}")
            return {
                **state,
                "error": str(e)
            }
    
    async def intent_node(self, state: AgentState) -> AgentState:
        """意图识别节点"""
        logger.info("[Adapter:Intent] 识别意图")
        
        try:
            intent_result = await self.orchestrator.intent_agent.analyze(
                user_input=state["user_query"]
            )
            
            specialists = []
            for specialist_type in intent_result.target_specialists:
                type_map = {
                    "finance": SpecialistType.FINANCE,
                    "tax": SpecialistType.TAX,
                    "legal": SpecialistType.LEGAL,
                    "report": SpecialistType.REPORT
                }
                specialists.append(type_map.get(specialist_type, SpecialistType.REPORT))
            
            return {
                **state,
                "intent": IntentCategory(intent_result.category.value),
                "intent_confidence": intent_result.confidence,
                "routing_strategy": intent_result.routing_strategy,
                "target_specialists": specialists
            }
        except Exception as e:
            logger.error(f"[Adapter:Intent] 错误: {e}")
            return {
                **state,
                "error": str(e)
            }
    
    async def finance_specialist_node(self, state: AgentState) -> AgentState:
        """财务专家节点"""
        logger.info("[Adapter:Finance] 执行任务")
        
        try:
            start_time = self.orchestrator._get_time_ms()
            response = await self.orchestrator.finance_specialist.run(
                user_input=state["user_query"],
                session_id=state["session_id"]
            )
            execution_time = self.orchestrator._get_time_ms() - start_time
            
            result = SpecialistResult(
                specialist_type=SpecialistType.FINANCE,
                specialist_name="finance_specialist",
                success=True,
                query=state["user_query"],
                response=response,
                confidence=0.8,
                execution_time_ms=execution_time
            )
            
            return {
                **state,
                "specialist_results": state["specialist_results"] + [result]
            }
        except Exception as e:
            logger.error(f"[Adapter:Finance] 错误: {e}")
            return {
                **state,
                "error": str(e)
            }
    
    async def tax_specialist_node(self, state: AgentState) -> AgentState:
        """税务专家节点"""
        logger.info("[Adapter:Tax] 执行任务")
        
        try:
            start_time = self.orchestrator._get_time_ms()
            response = await self.orchestrator.tax_specialist.run(
                user_input=state["user_query"],
                session_id=state["session_id"]
            )
            execution_time = self.orchestrator._get_time_ms() - start_time
            
            result = SpecialistResult(
                specialist_type=SpecialistType.TAX,
                specialist_name="tax_specialist",
                success=True,
                query=state["user_query"],
                response=response,
                confidence=0.8,
                execution_time_ms=execution_time
            )
            
            return {
                **state,
                "specialist_results": state["specialist_results"] + [result]
            }
        except Exception as e:
            logger.error(f"[Adapter:Tax] 错误: {e}")
            return {
                **state,
                "error": str(e)
            }
    
    async def legal_specialist_node(self, state: AgentState) -> AgentState:
        """法务专家节点"""
        logger.info("[Adapter:Legal] 执行任务")
        
        try:
            start_time = self.orchestrator._get_time_ms()
            response = await self.orchestrator.legal_specialist.run(
                user_input=state["user_query"],
                session_id=state["session_id"]
            )
            execution_time = self.orchestrator._get_time_ms() - start_time
            
            result = SpecialistResult(
                specialist_type=SpecialistType.LEGAL,
                specialist_name="legal_specialist",
                success=True,
                query=state["user_query"],
                response=response,
                confidence=0.8,
                execution_time_ms=execution_time
            )
            
            return {
                **state,
                "specialist_results": state["specialist_results"] + [result]
            }
        except Exception as e:
            logger.error(f"[Adapter:Legal] 错误: {e}")
            return {
                **state,
                "error": str(e)
            }
    
    async def reflection_node(self, state: AgentState) -> AgentState:
        """反思节点"""
        logger.info("[Adapter:Reflection] 质量审核")
        
        try:
            from app.prompts.llm_functions import review_quality
            import json
            
            specialist_results_str = json.dumps(state["specialist_results"], ensure_ascii=False)
            reflection_result = await review_quality(
                user_question=state["user_query"],
                ai_answer=specialist_results_str
            )
            
            return {
                **state,
                "reflection_result": reflection_result,
                "needs_human_review": not reflection_result.get("is_quality_acceptable", True)
            }
        except Exception as e:
            logger.error(f"[Adapter:Reflection] 错误: {e}")
            return {
                **state,
                "error": str(e)
            }
    
    async def final_answer_node(self, state: AgentState) -> AgentState:
        """最终答案节点"""
        logger.info("[Adapter:FinalAnswer] 生成最终答案")
        
        if state.get("needs_human_review"):
            final_answer = "您的请求需要人工专家审核。"
        elif state["specialist_results"]:
            final_answer = state["specialist_results"][-1].response
        else:
            final_answer = "无法处理您的请求。"
        
        return {
            **state,
            "final_answer": final_answer
        }


class OrchestratorWorkflowBuilder:
    """
    基于现有 Orchestrator 的工作流构建器
    
    将 AgentOrchestrator 包装为 LangGraph 工作流
    """
    
    def __init__(
        self,
        orchestrator: AgentOrchestrator,
        enable_reflection: bool = True
    ):
        """
        初始化构建器
        
        Args:
            orchestrator: AgentOrchestrator 实例
            enable_reflection: 是否启用反思
        """
        self.orchestrator = orchestrator
        self.enable_reflection = enable_reflection
        self.adapter = OrchestratorAdapter(orchestrator)
    
    def build(self) -> StateGraph:
        """构建工作流图"""
        workflow = StateGraph(AgentState)
        
        workflow.add_node("reception", self.adapter.reception_node)
        workflow.add_node("intent", self.adapter.intent_node)
        workflow.add_node("finance_specialist", self.adapter.finance_specialist_node)
        workflow.add_node("tax_specialist", self.adapter.tax_specialist_node)
        workflow.add_node("legal_specialist", self.adapter.legal_specialist_node)
        
        if self.enable_reflection:
            workflow.add_node("reflection", self.adapter.reflection_node)
        
        workflow.add_node("final_answer", self.adapter.final_answer_node)
        
        workflow.add_edge(START, "reception")
        workflow.add_edge("reception", "intent")
        
        workflow.add_conditional_edges(
            "intent",
            route_by_intent,
            {
                "single_specialist": "specialist_router",
                "multi_specialist": "specialist_router",
                "direct_answer": "final_answer",
                "human_review": "final_answer"
            }
        )
        
        workflow.add_conditional_edges(
            "specialist_router",
            route_by_specialists,
            {
                "finance_specialist": "finance_specialist",
                "tax_specialist": "tax_specialist",
                "legal_specialist": "legal_specialist"
            }
        )
        
        specialists = ["finance_specialist", "tax_specialist", "legal_specialist"]
        
        if self.enable_reflection:
            for specialist in specialists:
                workflow.add_edge(specialist, "reflection")
            workflow.add_conditional_edges(
                "reflection",
                route_reflection_result,
                {
                    "final_answer": "final_answer",
                    "rework": "specialist_router",
                    "human_review": "final_answer"
                }
            )
        else:
            for specialist in specialists:
                workflow.add_edge(specialist, "final_answer")
        
        workflow.add_edge("final_answer", END)
        
        return workflow
    
    def compile(self):
        """编译工作流"""
        graph = self.build()
        return graph.compile()
    
    async def invoke(self, session_id: str, user_query: str, **config) -> AgentState:
        """
        执行工作流
        
        Args:
            session_id: 会话ID
            user_query: 用户查询
            **config: 其他配置
            
        Returns:
            最终状态
        """
        compiled = self.compile()
        
        initial_state = create_initial_state(
            session_id=session_id,
            tenant_id=self.orchestrator.tenant_id,
            user_id=self.orchestrator.user_id,
            user_query=user_query,
            max_iterations=10,
            max_retries=3
        )
        
        return await compiled.ainvoke(initial_state, config=config)
