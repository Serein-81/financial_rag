"""
LangGraph 节点函数

封装现有的 Agent 为 LangGraph 节点
"""

import time
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool as langchain_tool_decorator

from .state import (
    AgentState, 
    SpecialistResult, 
    SpecialistType,
    create_initial_state,
    add_specialist_result,
    add_error,
    increment_iteration
)

logger = logging.getLogger(__name__)


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
            """意图识别节点 - 分类用户意图"""
            logger.info(f"[Intent] 分析意图: {state['user_query'][:50]}...")
            
            try:
                agent = self.get_or_create_agent("intent")
                intent_result = await agent.analyze(
                    user_input=state["user_query"],
                    context=state["metadata"].get("receptionist_response")
                )
                
                return {
                    **state,
                    "intent": intent_result.category,
                    "intent_confidence": intent_result.confidence,
                    "routing_strategy": intent_result.routing_strategy,
                    "target_specialists": intent_result.target_specialists
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
        
        封装 ReflectionSpecialist 进行质量审核
        """
        async def reflection_node(state: AgentState) -> AgentState:
            """反思节点 - 质量审核"""
            logger.info(f"[Reflection] 开始质量审核")
            
            try:
                agent = self.get_or_create_agent("reflection")
                
                reflection_result = await agent.review(
                    query=state["user_query"],
                    specialist_responses=state["specialist_results"],
                    confidence_threshold=state["metadata"].get("confidence_threshold", 0.7)
                )
                
                return {
                    **state,
                    "reflection_result": reflection_result,
                    "needs_human_review": reflection_result.needs_human_review
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
            """RAG 检索节点"""
            logger.info(f"[RAG] 执行知识检索")
            
            try:
                rag_retriever = self.get_or_create_agent("rag_retriever")
                
                docs = await rag_retriever.retrieve(
                    query=state["user_query"],
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
            """聚合节点 - 汇总专家回答"""
            logger.info(f"[Aggregator] 汇总 {len(state['specialist_results'])} 个专家结果")
            
            try:
                agent = self.get_or_create_agent("aggregator")
                
                aggregated = await agent.aggregate(
                    query=state["user_query"],
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
            logger.info(f"[FinalAnswer] 生成最终答案")
            
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
        return increment_iteration(state)
    
    return retry_node


def create_human_review_node() -> Callable:
    """
    创建人工审核节点 - 标记需要人工介入
    """
    async def human_review_node(state: AgentState) -> AgentState:
        """人工审核节点"""
        logger.info(f"[HumanReview] 请求人工审核")
        
        return {
            **state,
            "needs_human_review": True,
            "metadata": {
                **state["metadata"],
                "review_reason": state["reflection_result"].issues if state.get("reflection_result") else ["未知原因"]
            }
        }
    
    return human_review_node
