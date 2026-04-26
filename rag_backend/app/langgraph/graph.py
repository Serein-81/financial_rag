"""
LangGraph StateGraph 构建器

构建多智能体工作流图
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError

from .state import AgentState, create_initial_state
from ..schemas.multi_agent import SpecialistType, SpecialistResult
from .nodes import AgentNodeFactory, create_retry_node, create_human_review_node
from .conditional import (
    route_by_intent,
    route_by_specialists,
    route_reflection_result,
    create_parallel_routing
)

logger = logging.getLogger(__name__)


class MultiAgentWorkflowBuilder:
    """
    多智能体工作流构建器
    
    使用 LangGraph 构建复杂的多智能体协作工作流
    支持 PostgresSaver 状态持久化，断电/中断后可恢复
    """
    
    def __init__(
        self,
        agents_registry: Dict[str, Any],
        enable_checkpointer: bool = True,
        enable_reflection: bool = True,
        max_iterations: int = 10,
        max_retries: int = 3,
        db_session_factory=None
    ):
        """
        初始化工作流构建器
        
        Args:
            agents_registry: Agent 注册表
            enable_checkpointer: 是否启用状态持久化
            enable_reflection: 是否启用反思审核
            max_iterations: 最大迭代次数
            max_retries: 最大重试次数
            db_session_factory: 数据库会话工厂（用于 PostgresSaver）
        """
        self.agents_registry = agents_registry
        self.enable_checkpointer = enable_checkpointer
        self.enable_reflection = enable_reflection
        self.max_iterations = max_iterations
        self.max_retries = max_retries
        self.db_session_factory = db_session_factory
        
        self.node_factory = AgentNodeFactory(agents_registry)
        self.graph: Optional[StateGraph] = None
        self.compiled_graph: Optional[Any] = None
        self._postgres_saver = None
        
        logger.info("[WorkflowBuilder] 初始化完成")
        logger.info(f"  - Checkpointer: {enable_checkpointer}")
        logger.info(f"  - Reflection: {enable_reflection}")
        logger.info(f"  - Max Iterations: {max_iterations}")
        logger.info(f"  - Max Retries: {max_retries}")
        logger.info(f"  - PostgresSaver: {'启用' if db_session_factory else '未配置(使用 MemorySaver)'}")
    
    def build(self) -> StateGraph:
        """
        构建工作流图
        
        Returns:
            StateGraph 实例
        """
        workflow = StateGraph(AgentState)
        
        self._add_nodes(workflow)
        self._add_edges(workflow)
        self._add_conditional_edges(workflow)
        
        self.graph = workflow
        
        logger.info("[WorkflowBuilder] 工作流图构建完成")
        return workflow
    
    def _add_nodes(self, workflow: StateGraph):
        """添加所有节点"""
        workflow.add_node("receptionist", self.node_factory.create_receptionist_node())
        workflow.add_node("intent", self.node_factory.create_intent_node())
        
        workflow.add_node("rag_retrieval", self.node_factory.create_rag_retrieval_node())
        
        workflow.add_node("finance_specialist", 
                         self.node_factory.create_specialist_node(SpecialistType.FINANCE))
        workflow.add_node("tax_specialist",
                         self.node_factory.create_specialist_node(SpecialistType.TAX))
        workflow.add_node("legal_specialist",
                         self.node_factory.create_specialist_node(SpecialistType.LEGAL))
        workflow.add_node("report_specialist",
                         self.node_factory.create_specialist_node(SpecialistType.REPORT))
        
        workflow.add_node("multi_specialist_coordinator", 
                         self._create_multi_specialist_coordinator())
        
        workflow.add_node("aggregator", self.node_factory.create_aggregator_node())
        workflow.add_node("direct_answer", self.node_factory.create_direct_answer_node())
        
        if self.enable_reflection:
            workflow.add_node("reflection", self.node_factory.create_reflection_node())
        
        workflow.add_node("retry", create_retry_node(self.max_retries))
        workflow.add_node("human_review", create_human_review_node())
        workflow.add_node("final_answer", self.node_factory.create_final_answer_node())
        workflow.add_node("final_answer_with_suggestions",
                         self._create_final_answer_with_suggestions_node())
        workflow.add_node("error_handler", self._create_error_handler_node())
        
        logger.info("[WorkflowBuilder] 节点添加完成")
    
    def _add_edges(self, workflow: StateGraph):
        """添加固定边"""
        workflow.add_edge(START, "receptionist")
        workflow.add_edge("receptionist", "intent")
        
        workflow.add_edge("finance_specialist", "aggregator")
        workflow.add_edge("tax_specialist", "aggregator")
        workflow.add_edge("legal_specialist", "aggregator")
        workflow.add_edge("report_specialist", "aggregator")
        workflow.add_edge("direct_answer", "aggregator")
        
        if self.enable_reflection:
            workflow.add_edge("aggregator", "reflection")
        else:
            workflow.add_edge("aggregator", "final_answer")
        
        workflow.add_edge("final_answer", END)
        workflow.add_edge("final_answer_with_suggestions", END)
        workflow.add_edge("human_review", END)
        workflow.add_edge("error_handler", END)
        
        logger.info("[WorkflowBuilder] 固定边添加完成")
    
    def _add_conditional_edges(self, workflow: StateGraph):
        """添加条件边"""
        workflow.add_conditional_edges(
            "intent",
            route_by_intent,
            {
                "rag_retrieval": "rag_retrieval",
                "single_specialist": "single_specialist_router",
                "multi_specialist": "multi_specialist_router",
                "direct_answer": "direct_answer",
                "human_review": "human_review"
            }
        )
        
        workflow.add_conditional_edges(
            "rag_retrieval",
            lambda state: "single_specialist_router",
            {"single_specialist_router": "single_specialist_router"}
        )
        
        workflow.add_conditional_edges(
            "single_specialist_router",
            route_by_specialists,
            {
                "finance_specialist": "finance_specialist",
                "tax_specialist": "tax_specialist",
                "legal_specialist": "legal_specialist",
                "report_specialist": "report_specialist",
                "direct_answer": "direct_answer"
            }
        )
        
        workflow.add_conditional_edges(
            "multi_specialist_router",
            create_parallel_routing(["finance", "tax", "legal", "report"]),
            ["finance_specialist", "tax_specialist", "legal_specialist", "report_specialist"]
        )
        
        if self.enable_reflection:
            workflow.add_conditional_edges(
                "reflection",
                route_reflection_result,
                {
                    "final_answer": "final_answer",
                    "final_answer_with_suggestions": "final_answer_with_suggestions",
                    "rework": "retry",
                    "human_review": "human_review"
                }
            )
            
            workflow.add_conditional_edges(
                "retry",
                lambda state: "single_specialist_router" if state["retry_count"] < state["max_retries"] else "human_review"
            )
        
        logger.info("[WorkflowBuilder] 条件边添加完成")
    
    def _create_multi_specialist_coordinator(self) -> Callable:
        """创建多专家协调器节点"""
        async def coordinator_node(state: AgentState) -> AgentState:
            """多专家协调器 - 协调多个专家并行执行"""
            specialists = state.get("target_specialists", [])
            logger.info(f"[Coordinator] 协调 {len(specialists)} 个专家")
            
            return {
                **state,
                "metadata": {
                    **state["metadata"],
                    "coordinator_active": True
                }
            }
        
        return coordinator_node
    
    def _create_direct_answer_node(self) -> Callable:
        """创建直接回答节点"""
        async def direct_answer_node(state: AgentState) -> AgentState:
            """直接回答节点 - 处理简单查询"""
            logger.info("[DirectAnswer] 生成直接回答")
            
            try:
                agent = self.node_factory.get_or_create_agent("direct_answer")
                response = await agent.generate(
                    query=state["user_query"],
                    context=state.get("rag_context")
                )
                
                specialist_result = SpecialistResult(
                    specialist_type=SpecialistType.REPORT,
                    specialist_name="direct_answer",
                    success=True,
                    query=state["user_query"],
                    response=response,
                    confidence=0.9
                )
                
                return {
                    **state,
                    "specialist_results": state["specialist_results"] + [specialist_result]
                }
            except Exception as e:
                logger.error(f"[DirectAnswer] 错误: {e}")
                return state
        
        return direct_answer_node
    
    def _create_final_answer_with_suggestions_node(self) -> Callable:
        """创建包含建议的最终答案节点"""
        async def final_answer_with_suggestions_node(state: AgentState) -> AgentState:
            """最终答案节点 - 包含改进建议"""
            logger.info("[FinalAnswerWithSuggestions] 生成带建议的答案")
            
            reflection = state.get("reflection_result")
            aggregated = state.get("aggregated_response", "")
            
            suggestions_text = ""
            if reflection and reflection.suggestions:
                suggestions_text = "\n\n**改进建议：**\n" + "\n".join(
                    f"- {s}" for s in reflection.suggestions
                )
            
            final_answer = aggregated + suggestions_text if suggestions_text else aggregated
            
            return {
                **state,
                "final_answer": final_answer
            }
        
        return final_answer_with_suggestions_node
    
    def _create_error_handler_node(self) -> Callable:
        """创建错误处理节点"""
        async def error_handler_node(state: AgentState) -> AgentState:
            """错误处理节点"""
            error = state.get("error", "Unknown error")
            logger.error(f"[ErrorHandler] 处理错误: {error}")
            
            return {
                **state,
                "final_answer": f"处理您的请求时遇到问题：{error}。请稍后重试或联系人工客服。",
                "needs_human_review": True
            }
        
        return error_handler_node
    
    def _get_postgres_saver(self):
        """获取 PostgresSaver 实例"""
        if self._postgres_saver is None and self.db_session_factory:
            from .postgres_saver import LangGraphPostgresSaver
            self._postgres_saver = LangGraphPostgresSaver(
                db_session_factory=self.db_session_factory,
                table_name="langgraph_checkpoints"
            )
            logger.info("[WorkflowBuilder] PostgresSaver 初始化完成")
        return self._postgres_saver
    
    def compile(self):
        """编译工作流图"""
        if self.graph is None:
            self.build()
        
        checkpointer = None
        if self.enable_checkpointer:
            if self.db_session_factory:
                checkpointer = self._get_postgres_saver()
                if checkpointer:
                    logger.info("[WorkflowBuilder] 使用 PostgresSaver 进行状态持久化")
                else:
                    logger.warning("[WorkflowBuilder] PostgresSaver 初始化失败，使用 MemorySaver")
                    checkpointer = MemorySaver()
            else:
                logger.warning("[WorkflowBuilder] 未配置数据库会话，使用 MemorySaver（断电丢失）")
                checkpointer = MemorySaver()
        
        self.compiled_graph = self.graph.compile(
            checkpointer=checkpointer,
            interrupt_before=["human_review"] if self.enable_reflection else None
        )
        
        logger.info("[WorkflowBuilder] 工作流编译完成")
        return self.compiled_graph
    
    async def invoke(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        user_query: str,
        config: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        **metadata
    ) -> AgentState:
        """
        执行工作流
        
        Args:
            session_id: 会话ID（thread_id）
            tenant_id: 租户ID
            user_id: 用户ID
            user_query: 用户查询
            config: LangGraph 配置
            task_id: 任务ID（用于状态持久化）
            **metadata: 其他元数据
            
        Returns:
            最终状态
        """
        if self.compiled_graph is None:
            self.compile()
        
        initial_state = create_initial_state(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            user_query=user_query,
            max_iterations=self.max_iterations,
            max_retries=self.max_retries,
            **metadata
        )
        
        logger.info("[Workflow] 开始执行工作流")
        logger.info(f"  - Session: {session_id}")
        logger.info(f"  - Query: {user_query[:100]}...")
        
        postgres_saver = self._get_postgres_saver()
        
        if postgres_saver:
            checkpoint_id = f"{session_id}_start_{datetime.now().timestamp()}"
            await postgres_saver.put_checkpoint(
                thread_id=session_id,
                checkpoint_id=checkpoint_id,
                checkpoint_data=initial_state,
                metadata={
                    "task_id": task_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "node": "start",
                    "status": "running"
                }
            )
            logger.info(f"[Workflow] 初始状态已保存: checkpoint_id={checkpoint_id}")
        
        try:
            checkpoint_config = {
                "configurable": {
                    "thread_id": session_id
                }
            }
            if config:
                checkpoint_config["configurable"].update(config.get("configurable", {}))
            
            final_state = await self.compiled_graph.ainvoke(
                initial_state,
                config=checkpoint_config
            )
            
            if postgres_saver:
                checkpoint_id = f"{session_id}_end_{datetime.now().timestamp()}"
                await postgres_saver.put_checkpoint(
                    thread_id=session_id,
                    checkpoint_id=checkpoint_id,
                    checkpoint_data=final_state,
                    metadata={
                        "task_id": task_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "node": "end",
                        "status": "completed"
                    }
                )
            
            logger.info("[Workflow] 工作流执行完成")
            return final_state
            
        except GraphRecursionError:
            logger.warning("[Workflow] 达到最大递归深度")
            return {
                **initial_state,
                "final_answer": "处理超时，请稍后重试。"
            }
        except Exception as e:
            logger.error(f"[Workflow] 执行错误: {e}")
            if postgres_saver:
                checkpoint_id = f"{session_id}_error_{datetime.now().timestamp()}"
                await postgres_saver.put_checkpoint(
                    thread_id=session_id,
                    checkpoint_id=checkpoint_id,
                    checkpoint_data=initial_state,
                    metadata={
                        "task_id": task_id,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "node": "error",
                        "status": "failed",
                        "error": str(e)
                    }
                )
            return {
                **initial_state,
                "error": str(e),
                "final_answer": f"系统错误: {str(e)}"
            }
    
    async def stream(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        user_query: str,
        config: Optional[Dict[str, Any]] = None,
        **metadata
    ):
        """
        流式执行工作流
        
        Args:
            同 invoke
            
        Yields:
            中间状态
        """
        if self.compiled_graph is None:
            self.compile()
        
        initial_state = create_initial_state(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            user_query=user_query,
            max_iterations=self.max_iterations,
            max_retries=self.max_retries,
            **metadata
        )
        
        logger.info("[Workflow] 开始流式执行")
        
        async for state in self.compiled_graph.astream(
            initial_state,
            config=config or {}
        ):
            yield state


class SimpleAgentWorkflow:
    """
    简化版智能体工作流
    
    用于快速创建简单的单 Agent 工作流
    """
    
    def __init__(
        self,
        agent: Any,
        name: str = "simple_agent"
    ):
        """
        初始化简化工作流
        
        Args:
            agent: Agent 实例
            name: 工作流名称
        """
        self.agent = agent
        self.name = name
        self.graph = None
    
    def build(self) -> StateGraph:
        """构建简单工作流"""
        workflow = StateGraph(AgentState)
        
        async def agent_node(state: AgentState) -> AgentState:
            response = await self.agent.run(
                user_input=state["user_query"],
                session_id=state["session_id"]
            )
            
            return {
                **state,
                "final_answer": response,
                "messages": state["messages"] + [
                    {"role": "assistant", "content": response}
                ]
            }
        
        workflow.add_node(self.name, agent_node)
        workflow.add_edge(START, self.name)
        workflow.add_edge(self.name, END)
        
        self.graph = workflow
        return workflow
    
    def compile(self):
        """编译工作流"""
        if self.graph is None:
            self.build()
        return self.graph.compile()
    
    async def invoke(self, **state_kwargs) -> AgentState:
        """执行工作流"""
        compiled = self.compile()
        return await compiled.ainvoke(state_kwargs)
