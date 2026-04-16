"""
混合图构建器

将 LangGraph 和 Message Bus 黑板模式整合为统一的混合编排系统

功能：
1. 构建包含混合节点的 LangGraph
2. 配置节点间的边和条件路由
3. 管理 ExpertConsultation 和 Summarizer 节点的生命周期
4. 提供编译和执行接口
"""

import logging
from typing import Dict, Any, Optional, List, Callable

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from app.state.unified_state import UnifiedState
from app.langgraph.hybrid.expert_consultation_node import ExpertConsultationNode
from app.langgraph.hybrid.summarizer_node import SummarizerNode
from app.langgraph.hybrid.blackboard_manager import BlackboardManager

logger = logging.getLogger(__name__)


class HybridGraphBuilder:
    """
    混合图构建器
    
    将 LangGraph 顶层编排与 Message Bus 黑板模式整合。
    
    图结构：
    1. 顶层使用 LangGraph 的 StateGraph 进行流程控制
    2. 复杂协作场景（如专家会诊）使用 ExpertConsultationNode
    3. 上下文压缩使用 SummarizerNode
    4. Agent 间通信使用 BlackboardManager
    
    使用示例：
    ```python
    # 创建构建器
    builder = HybridGraphBuilder(
        agents_registry=agents,
        enable_checkpointer=True
    )
    
    # 构建图
    graph = builder.build()
    
    # 编译图
    compiled = builder.compile()
    
    # 执行
    result = await compiled.ainvoke(initial_state)
    ```
    """
    
    def __init__(
        self,
        agents_registry: Optional[Dict[str, Any]] = None,
        enable_checkpointer: bool = True,
        enable_reflection: bool = True,
        enable_expert_consultation: bool = True,
        enable_summarization: bool = True,
        max_expert_rounds: int = 3,
        summarization_threshold: int = 5000,
        max_iterations: int = 10
    ):
        """
        初始化混合图构建器
        
        Args:
            agents_registry: Agent 注册表
            enable_checkpointer: 是否启用状态持久化
            enable_reflection: 是否启用反思审核
            enable_expert_consultation: 是否启用专家会诊
            enable_summarization: 是否启用上下文压缩
            max_expert_rounds: 专家会诊最大轮数
            summarization_threshold: 上下文压缩阈值（字节数）
            max_iterations: 最大迭代次数
        """
        self.agents_registry = agents_registry or {}
        self.enable_checkpointer = enable_checkpointer
        self.enable_reflection = enable_reflection
        self.enable_expert_consultation = enable_expert_consultation
        self.enable_summarization = enable_summarization
        self.max_expert_rounds = max_expert_rounds
        self.summarization_threshold = summarization_threshold
        self.max_iterations = max_iterations
        
        # 创建共享的黑板管理器
        self.blackboard = BlackboardManager()
        
        # 创建节点实例
        self._create_nodes()
        
        # LangGraph 相关
        self.graph: Optional[StateGraph] = None
        self.compiled_graph: Optional[Any] = None
        
        logger.info("[HybridGraphBuilder] 初始化完成")
        logger.info(f"  - Expert Consultation: {enable_expert_consultation}")
        logger.info(f"  - Summarization: {enable_summarization}")
        logger.info(f"  - Max Expert Rounds: {max_expert_rounds}")
        logger.info(f"  - Summarization Threshold: {summarization_threshold} bytes")
    
    def _create_nodes(self):
        """创建混合节点"""
        # 专家会诊节点
        self.expert_consultation_node = None
        if self.enable_expert_consultation:
            self.expert_consultation_node = ExpertConsultationNode(
                blackboard=self.blackboard,
                max_rounds=self.max_expert_rounds,
                agent_factory=self._get_agent_factory()
            )
        
        # Summarizer 节点
        self.summarizer_node = None
        if self.enable_summarization:
            self.summarizer_node = SummarizerNode(
                compression_target=1000
            )
    
    def _get_agent_factory(self) -> Optional[Callable]:
        """
        获取 Agent 工厂函数
        
        Returns:
            Agent 工厂函数
        """
        if not self.agents_registry:
            return None
        
        def factory(agent_name: str) -> Any:
            """创建 Agent 实例"""
            agent_class = self.agents_registry.get(agent_name)
            if not agent_class:
                raise ValueError(f"未知的 Agent: {agent_name}")
            return agent_class()
        
        return factory
    
    def build(self) -> StateGraph:
        """
        构建混合图
        
        Returns:
            StateGraph 实例
        """
        workflow = StateGraph(UnifiedState)
        
        # 添加标准节点
        self._add_core_nodes(workflow)
        
        # 添加混合节点
        if self.enable_expert_consultation:
            self._add_expert_consultation_node(workflow)
        
        if self.enable_summarization:
            self._add_summarizer_node(workflow)
        
        # 添加边
        self._add_edges(workflow)
        
        # 添加条件边
        self._add_conditional_edges(workflow)
        
        self.graph = workflow
        
        logger.info("[HybridGraphBuilder] 混合图构建完成")
        return workflow
    
    def _add_core_nodes(self, workflow: StateGraph):
        """
        添加核心节点
        
        Args:
            workflow: StateGraph 实例
        """
        # 接待节点
        workflow.add_node("receptionist", self._create_receptionist_node())
        
        # 意图识别节点
        workflow.add_node("intent_classifier", self._create_intent_node())
        
        # RAG 检索节点
        workflow.add_node("rag_retrieval", self._create_rag_retrieval_node())
        
        # 生成节点
        workflow.add_node("response_generator", self._create_generator_node())
        
        # 反思节点
        if self.enable_reflection:
            workflow.add_node("reflection", self._create_reflection_node())
        
        # 结束节点
        workflow.add_node("finalize", self._create_finalize_node())
    
    def _add_expert_consultation_node(self, workflow: StateGraph):
        """
        添加专家会诊节点
        
        Args:
            workflow: StateGraph 实例
        """
        if self.expert_consultation_node:
            workflow.add_node(
                "expert_consultation",
                self._wrap_expert_consultation_node()
            )
            logger.info("[HybridGraphBuilder] 添加专家会诊节点")
    
    def _add_summarizer_node(self, workflow: StateGraph):
        """
        添加 Summarizer 节点
        
        Args:
            workflow: StateGraph 实例
        """
        if self.summarizer_node:
            workflow.add_node(
                "context_summarizer",
                self._wrap_summarizer_node()
            )
            logger.info("[HybridGraphBuilder] 添加上下文压缩节点")
    
    def _wrap_expert_consultation_node(self):
        """
        包装专家会诊节点为 LangGraph 节点函数
        
        Returns:
            LangGraph 兼容的节点函数
        """
        import asyncio
        node = self.expert_consultation_node
        
        async def expert_consultation_func(state: UnifiedState) -> UnifiedState:
            return await node.invoke(state)
        
        return expert_consultation_func
    
    def _wrap_summarizer_node(self):
        """
        包装 Summarizer 节点为 LangGraph 节点函数
        
        Returns:
            LangGraph 兼容的节点函数
        """
        import asyncio
        node = self.summarizer_node
        
        async def summarizer_func(state: UnifiedState) -> UnifiedState:
            return await node.invoke(state)
        
        return summarizer_func
    
    def _add_edges(self, workflow: StateGraph):
        """添加边"""
        # 基础流程
        workflow.add_edge(START, "receptionist")
        workflow.add_edge("receptionist", "intent_classifier")
        workflow.add_edge("intent_classifier", "rag_retrieval")
        workflow.add_edge("rag_retrieval", "response_generator")
        
        # 专家会诊和压缩（如果启用）
        if self.enable_expert_consultation:
            workflow.add_edge("response_generator", "expert_consultation")
            workflow.add_edge("expert_consultation", "context_summarizer")
        
        if self.enable_summarization and not self.enable_expert_consultation:
            workflow.add_edge("response_generator", "context_summarizer")
        
        # 反思（如果启用）
        if self.enable_reflection:
            workflow.add_edge("context_summarizer", "reflection")
            workflow.add_edge("reflection", "finalize")
        else:
            workflow.add_edge("context_summarizer", "finalize")
        
        workflow.add_edge("finalize", END)
    
    def _add_conditional_edges(self, workflow: StateGraph):
        """添加条件边"""
        
        def should_run_expert_consultation(state: UnifiedState) -> str:
            """
            判断是否需要运行专家会诊
            
            Args:
                state: 当前状态
                
            Returns:
                "expert_consultation" 或 "context_summarizer"
            """
            intent = state.get("intent", "")
            target_specialists = state.get("target_specialists", [])
            
            # 检查是否是多专家协作场景
            if len(target_specialists) >= 2:
                return "expert_consultation"
            
            # 检查意图是否需要多专家
            from app.state.unified_state import IntentCategory
            expert_intents = [
                IntentCategory.EXPERT_CONSULTATION,
                IntentCategory.COMPREHENSIVE_ANALYSIS
            ]
            
            if intent in expert_intents:
                return "expert_consultation"
            
            return "context_summarizer"
        
        def should_summarize(state: UnifiedState) -> str:
            """
            判断是否需要上下文压缩
            
            Args:
                state: 当前状态
                
            Returns:
                "context_summarizer" 或下一节点
            """
            # 检查上下文大小
            debate_context = state.get("debate_context", [])
            total_size = sum(len(str(entry)) for entry in debate_context)
            
            if total_size >= self.summarization_threshold:
                return "context_summarizer"
            
            return "finalize"
        
        # 添加条件边
        workflow.add_conditional_edges(
            "response_generator",
            should_run_expert_consultation,
            {
                "expert_consultation": "expert_consultation",
                "context_summarizer": "context_summarizer"
            }
        )
    
    def _create_receptionist_node(self):
        """创建接待节点"""
        async def receptionist_func(state: UnifiedState) -> UnifiedState:
            logger.info(
                f"[Receptionist] 处理请求: request_id={state['request_id']}"
            )
            state["current_phase"] = "reception"
            return state
        
        return receptionist_func
    
    def _create_intent_node(self):
        """创建意图识别节点"""
        async def intent_func(state: UnifiedState) -> UnifiedState:
            logger.info(
                f"[IntentClassifier] 识别意图: {state['user_query']}"
            )
            state["current_phase"] = "intent_classification"
            
            # TODO: 调用 LLM 进行意图识别
            # 这里简化处理
            from app.state.unified_state import IntentCategory
            state["intent"] = IntentCategory.QUESTION
            
            return state
        
        return intent_func
    
    def _create_rag_retrieval_node(self):
        """创建 RAG 检索节点"""
        async def rag_func(state: UnifiedState) -> UnifiedState:
            logger.info(
                f"[RAGRetrieval] 执行检索: {state['user_query']}"
            )
            state["current_phase"] = "retrieval"
            
            # TODO: 调用 RAG 检索
            state["retrieved_documents"] = []
            
            return state
        
        return rag_func
    
    def _create_generator_node(self):
        """创建生成节点"""
        async def generator_func(state: UnifiedState) -> UnifiedState:
            logger.info(
                f"[Generator] 生成响应"
            )
            state["current_phase"] = "generation"
            
            # TODO: 调用 LLM 生成响应
            state["final_response"] = "这是模拟的响应"
            
            return state
        
        return generator_func
    
    def _create_reflection_node(self):
        """创建反思节点"""
        async def reflection_func(state: UnifiedState) -> UnifiedState:
            logger.info(
                f"[Reflection] 执行反思"
            )
            state["current_phase"] = "reflection"
            
            # TODO: 调用反思机制
            state["reflection_result"] = {"quality": "acceptable"}
            
            return state
        
        return reflection_func
    
    def _create_finalize_node(self):
        """创建结束节点"""
        async def finalize_func(state: UnifiedState) -> UnifiedState:
            logger.info(
                f"[Finalize] 完成处理: request_id={state['request_id']}"
            )
            state["current_phase"] = "finalized"
            state["status"] = "completed"
            
            return state
        
        return finalize_func
    
    def compile(self) -> Any:
        """
        编译图
        
        Returns:
            编译后的图
        """
        if not self.graph:
            raise RuntimeError("必须先调用 build() 方法")
        
        # 配置检查点
        checkpointer = None
        if self.enable_checkpointer:
            checkpointer = MemorySaver()
        
        # 编译
        self.compiled_graph = self.graph.compile(checkpointer=checkpointer)
        
        logger.info("[HybridGraphBuilder] 图编译完成")
        return self.compiled_graph
    
    async def ainvoke(
        self,
        state: UnifiedState,
        config: Optional[Dict[str, Any]] = None
    ) -> UnifiedState:
        """
        异步执行图
        
        Args:
            state: 初始状态
            config: 配置
            
        Returns:
            最终状态
        """
        if not self.compiled_graph:
            self.compile()
        
        return await self.compiled_graph.ainvoke(state, config)
    
    def invoke(
        self,
        state: UnifiedState,
        config: Optional[Dict[str, Any]] = None
    ) -> UnifiedState:
        """
        同步执行图
        
        Args:
            state: 初始状态
            config: 配置
            
        Returns:
            最终状态
        """
        import asyncio
        
        return asyncio.run(self.ainvoke(state, config))
    
    def get_graph_diagram(self) -> Dict[str, Any]:
        """
        获取图的图表描述
        
        Returns:
            包含图结构的字典
        """
        if not self.graph:
            return {"error": "必须先调用 build() 方法"}
        
        return {
            "nodes": list(self.graph.nodes.keys()) if hasattr(self.graph, 'nodes') else [],
            "edges": self._get_edges_info(),
            "blackboard_stats": self.blackboard.get_statistics()
        }
    
    def _get_edges_info(self) -> List[Dict[str, str]]:
        """
        获取边信息
        
        Returns:
            边列表
        """
        edges = []
        
        # 从图中提取边信息
        if hasattr(self.graph, 'builder') and hasattr(self.graph.builder, 'edges'):
            for edge in self.graph.builder.edges:
                edges.append({
                    "from": edge[0] if len(edge) > 0 else "unknown",
                    "to": edge[1] if len(edge) > 1 else "unknown"
                })
        
        return edges
