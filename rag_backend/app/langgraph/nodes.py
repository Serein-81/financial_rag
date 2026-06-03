"""
LangGraph 节点函数

封装现有的 Agent 为 LangGraph 节点
"""

import re
import time
import logging
from typing import Dict, Any, Callable, Optional

from .state import (
    AgentState,
    SpecialistResult,
    SpecialistType,
    add_specialist_result,
    add_error,
    increment_iteration
)

logger = logging.getLogger(__name__)


# 复杂度推断：trivial 触发 Adaptive RAG 短路
_TRIVIAL_PATTERNS = re.compile(
    r"^(你好|您好|hi|hello|嗨|hey|谢谢|thanks|感谢|再见|bye|拜拜)[\s,，.!！?？]*$",
    re.IGNORECASE,
)
_REASONING_KEYWORDS = ("为什么", "如何", "怎么", "比较", "区别", "原因", "影响", "分析", "评估")


def _build_aggregator_query_with_hint(state: AgentState) -> str:
    """重生成时把 unfaithful 句作为修正信号附加到 query 上。

    第一次进 aggregator 时（regenerate_count == 0），直接返回原 query。
    第二次开始，会把 unfaithful_sentences 拼接为系统提示，让 aggregator 严格
    依据 rag_context 重新作答。
    """
    original = state["user_query"]
    regen = state.get("regenerate_count") or 0
    unfaithful = state.get("unfaithful_sentences") or []

    if regen <= 0 or not unfaithful:
        return original

    hint_lines = "\n".join(f"- {s}" for s in unfaithful[:5])
    return (
        f"{original}\n\n"
        f"[忠实度修正第 {regen} 次] 上一次的答案包含以下未被资料支持的内容，"
        f"请严格基于检索到的资料重新作答，避免编造任何事实：\n{hint_lines}"
    )


def _infer_complexity(query: str, agent_complexity: Optional[Any] = None) -> str:
    """推断 query 复杂度，用于 Adaptive RAG 短路。

    Returns:
        "trivial"   - 闲聊/问候，跳过 RAG
        "factual"   - 单跳事实查询
        "reasoning" - 多跳推理
        "deep"      - 调研型（预留）
    """
    q = (query or "").strip()
    if not q or _TRIVIAL_PATTERNS.match(q) or len(q) <= 4:
        return "trivial"

    # 借用 agent 自身的复杂度信号（若有）
    agent_value = None
    if agent_complexity is not None:
        agent_value = getattr(agent_complexity, "value", None) or str(agent_complexity)
        agent_value = agent_value.lower()

    if agent_value in ("very_high", "very_complex"):
        return "deep"
    if agent_value in ("high", "complex"):
        return "reasoning"

    if any(kw in q for kw in _REASONING_KEYWORDS):
        return "reasoning"
    return "factual"


class AgentNodeFactory:
    """
    Agent 节点工厂
    
    封装现有 Agent 为 LangGraph 可用的节点函数
    """
    
    def __init__(self, agents_registry: Dict[str, Any]):
        """
        初始化节点工厂
        
        Args:
            agents_registry: Agent 注册表 {"finance": FinanceSpecialist, ...}
        """
        self.agents_registry = agents_registry
        self._agent_instances: Dict[str, Any] = {}
    
    def get_or_create_agent(self, agent_type: str, **config) -> Any:
        """
        获取或创建 Agent 实例
        
        Args:
            agent_type: Agent 类型
            **config: Agent 配置
            
        Returns:
            Agent 实例
        """
        if agent_type not in self._agent_instances:
            agent_class = self.agents_registry.get(agent_type)
            if agent_class:
                self._agent_instances[agent_type] = agent_class(**config)
            else:
                raise ValueError(f"Unknown agent type: {agent_type}")
        return self._agent_instances[agent_type]
    
    def create_receptionist_node(self) -> Callable:
        """
        创建接待员节点
        
        封装 IntentRouterAgent
        """
        async def receptionist_node(state: AgentState) -> AgentState:
            """接待员节点 - 解析用户意图和上下文"""
            logger.info(f"[Receptionist] 处理查询: {state['user_query'][:50]}...")
            
            try:
                agent = self.get_or_create_agent("receptionist")
                response = await agent.run(
                    user_input=state["user_query"],
                    session_id=state["session_id"],
                    tenant_id=state["tenant_id"]
                )
                
                return {
                    **state,
                    "messages": state["messages"] + [
                        {"role": "assistant", "content": response}
                    ],
                    "metadata": {
                        **state["metadata"],
                        "receptionist_response": response
                    }
                }
            except Exception as e:
                logger.error(f"[Receptionist] 错误: {e}")
                return add_error(state, f"Receptionist 错误: {str(e)}")
        
        return receptionist_node
    
    def create_intent_node(self) -> Callable:
        """
        创建意图识别节点

        封装 IntentRouterAgent
        """
        async def intent_node(state: AgentState) -> AgentState:
            """意图识别节点 - 分类用户意图 + 复杂度评估（Adaptive RAG）"""
            logger.info(f"[Intent] 分析意图: {state['user_query'][:50]}...")

            try:
                agent = self.get_or_create_agent("intent")
                intent_result = await agent.analyze(
                    user_input=state["user_query"],
                    context=state["metadata"].get("receptionist_response")
                )

                # Adaptive RAG：从 agent 结果或启发式规则推断复杂度
                complexity = _infer_complexity(
                    state["user_query"],
                    getattr(intent_result, "complexity", None)
                )

                return {
                    **state,
                    "intent": intent_result.category,
                    "intent_confidence": intent_result.confidence,
                    "routing_strategy": intent_result.routing_strategy,
                    "target_specialists": intent_result.target_specialists,
                    "complexity": complexity,
                }
            except Exception as e:
                logger.error(f"[Intent] 错误: {e}")
                return add_error(state, f"Intent 错误: {str(e)}")

        return intent_node
    
    def create_specialist_node(self, specialist_type: SpecialistType) -> Callable:
        """
        创建专家节点
        
        封装各领域专家 Agent
        
        Args:
            specialist_type: 专家类型
        """
        async def specialist_node(state: AgentState) -> AgentState:
            """专家节点 - 执行领域任务"""
            logger.info(f"[{specialist_type.value}] 执行专家任务")
            
            start_time = time.time()
            try:
                agent = self.get_or_create_agent(specialist_type.value)
                
                response = await agent.run(
                    user_input=state["user_query"],
                    rag_context=state.get("rag_context"),
                    session_id=state["session_id"]
                )
                
                execution_time = (time.time() - start_time) * 1000
                
                specialist_result = SpecialistResult(
                    specialist_type=specialist_type,
                    query=state["user_query"],
                    response=response,
                    confidence=0.8,
                    execution_time_ms=execution_time
                )
                
                return add_specialist_result(state, specialist_result)
                
            except Exception as e:
                logger.error(f"[{specialist_type.value}] 错误: {e}")
                return add_error(state, f"{specialist_type.value} 错误: {str(e)}")
        
        return specialist_node
    
    def create_reflection_node(self) -> Callable:
        """
        创建反思节点
        
        使用 review_quality 函数进行质量审核
        """
        async def reflection_node(state: AgentState) -> AgentState:
            """反思节点 - 质量审核"""
            logger.info("[Reflection] 开始质量审核")
            
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
                logger.error(f"[Reflection] 错误: {e}")
                return add_error(state, f"Reflection 错误: {str(e)}")
        
        return reflection_node
    
    def create_rag_retrieval_node(self) -> Callable:
        """
        创建 RAG 检索节点
        """
        async def rag_node(state: AgentState) -> AgentState:
            """RAG 检索节点

            优先使用 rewritten_query（来自 QueryRewriter 的回流），否则用原始 user_query。
            """
            effective_query = state.get("rewritten_query") or state["user_query"]
            iter_count = state.get("retrieval_iterations") or 0
            logger.info(
                f"[RAG] 执行知识检索 (iter={iter_count}, query={effective_query[:50]!r})"
            )

            try:
                rag_retriever = self.get_or_create_agent("rag_retriever")

                docs = await rag_retriever.retrieve(
                    query=effective_query,
                    tenant_id=state["tenant_id"],
                    top_k=state["metadata"].get("rag_top_k", 5)
                )
                
                return {
                    **state,
                    "rag_context": docs
                }
                
            except Exception as e:
                logger.error(f"[RAG] 错误: {e}")
                return add_error(state, f"RAG 错误: {str(e)}")
        
        return rag_node
    
    def create_aggregator_node(self) -> Callable:
        """
        创建聚合节点 - 汇总多个专家的结果
        """
        async def aggregator_node(state: AgentState) -> AgentState:
            """聚合节点 - 汇总专家回答

            支持忠实度重生成：当 regenerate_count > 0 时，把上一次的 unfaithful 句
            作为修正信号附加到 query 上，引导 aggregator 严格依据资料重答。
            """
            logger.info(f"[Aggregator] 汇总 {len(state['specialist_results'])} 个专家结果")

            try:
                agent = self.get_or_create_agent("aggregator")

                effective_query = _build_aggregator_query_with_hint(state)
                aggregated = await agent.aggregate(
                    query=effective_query,
                    specialist_results=state["specialist_results"],
                    rag_context=state.get("rag_context")
                )

                return {
                    **state,
                    "aggregated_response": aggregated
                }

            except Exception as e:
                logger.error(f"[Aggregator] 错误: {e}")
                return add_error(state, f"Aggregator 错误: {str(e)}")

        return aggregator_node
    
    def create_final_answer_node(self) -> Callable:
        """
        创建最终答案节点 - 输出最终结果
        """
        async def final_answer_node(state: AgentState) -> AgentState:
            """最终答案节点"""
            logger.info("[FinalAnswer] 生成最终答案")
            
            try:
                if state.get("needs_human_review"):
                    final_answer = "您的请求需要人工专家审核，我们已将其转交给专业人员。"
                elif state.get("aggregated_response"):
                    final_answer = state["aggregated_response"]
                elif state["specialist_results"]:
                    final_answer = state["specialist_results"][-1].response
                else:
                    final_answer = "抱歉，无法处理您的请求。"
                
                return {
                    **state,
                    "final_answer": final_answer,
                    "messages": state["messages"] + [
                        {"role": "assistant", "content": final_answer}
                    ]
                }
                
            except Exception as e:
                logger.error(f"[FinalAnswer] 错误: {e}")
                return add_error(state, f"FinalAnswer 错误: {str(e)}")
        
        return final_answer_node


def create_retry_node(max_retries: int = 3) -> Callable:
    """
    创建重试节点 - 处理失败重试
    
    Args:
        max_retries: 最大重试次数
    """
    async def retry_node(state: AgentState) -> AgentState:
        """重试节点"""
        current_retry = state["retry_count"]
        
        if current_retry >= max_retries:
            logger.warning(f"[Retry] 达到最大重试次数 {max_retries}")
            return {
                **state,
                "final_answer": "处理失败，请稍后重试或联系人工客服。"
            }
        
        logger.info(f"[Retry] 重试 {current_retry + 1}/{max_retries}")
        return {**increment_iteration(state), "retry_count": current_retry + 1}
    
    return retry_node


def create_human_review_node() -> Callable:
    """
    创建人工审核节点 - 标记需要人工介入
    """
    async def human_review_node(state: AgentState) -> AgentState:
        """人工审核节点"""
        logger.info("[HumanReview] 请求人工审核")
        
        return {
            **state,
            "needs_human_review": True,
            "metadata": {
                **state["metadata"],
                "review_reason": state["reflection_result"].issues if state.get("reflection_result") else ["未知原因"]
            }
        }
    
    return human_review_node
