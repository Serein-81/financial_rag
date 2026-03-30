"""
LangGraph 条件边路由

定义工作流中的条件路由逻辑
"""

import logging
from typing import Literal, List, Callable
from .state import AgentState, IntentCategory, SpecialistType, QualityLevel

logger = logging.getLogger(__name__)


def route_by_intent(state: AgentState) -> str:
    """
    根据意图路由到下一个节点
    
    Args:
        state: 当前状态
        
    Returns:
        目标节点名称
    """
    intent = state.get("intent")
    intent_confidence = state.get("intent_confidence", 0.0)
    
    logger.info(f"[路由] Intent={intent}, Confidence={intent_confidence:.2f}")
    
    if intent_confidence < 0.5:
        logger.info("[路由] 置信度过低，转向人工审核")
        return "human_review"
    
    if intent is None:
        logger.info("[路由] 无意图信息，转向人工审核")
        return "human_review"
    
    route_map = {
        IntentCategory.RAG_RETRIEVAL: "rag_retrieval",
        IntentCategory.SINGLE_SPECIALIST: "single_specialist",
        IntentCategory.MULTI_SPECIALIST: "multi_specialist",
        IntentCategory.DIRECT_ANSWER: "direct_answer",
        IntentCategory.HUMAN_REVIEW: "human_review",
        IntentCategory.UNKNOWN: "human_review"
    }
    
    target = route_map.get(intent, "human_review")
    logger.info(f"[路由] 路由到: {target}")
    
    return target


def route_by_specialists(state: AgentState) -> str:
    """
    根据专家列表路由
    
    Args:
        state: 当前状态
        
    Returns:
        目标专家节点
    """
    specialists = state.get("target_specialists", [])
    
    if not specialists:
        logger.info("[路由] 无目标专家，转向直接回答")
        return "direct_answer"
    
    if len(specialists) == 1:
        specialist = specialists[0]
        route_map = {
            SpecialistType.FINANCE: "finance_specialist",
            SpecialistType.TAX: "tax_specialist",
            SpecialistType.LEGAL: "legal_specialist",
            SpecialistType.REPORT: "report_specialist"
        }
        target = route_map.get(specialist, "direct_answer")
        logger.info(f"[路由] 单专家路由: {target}")
        return target
    
    logger.info(f"[路由] 多专家路由: {len(specialists)} 个专家")
    return "multi_specialist_start"


def route_reflection_result(state: AgentState) -> str:
    """
    根据反思结果路由
    
    Args:
        state: 当前状态
        
    Returns:
        目标节点
    """
    reflection = state.get("reflection_result")
    
    if reflection is None:
        logger.info("[路由] 无反思结果，转向最终答案")
        return "final_answer"
    
    quality = reflection.quality_level
    score = reflection.overall_score
    
    logger.info(f"[路由] 质量评估: {quality.value}, 分数: {score:.2f}")
    
    if reflection.needs_human_review:
        logger.info("[路由] 需要人工审核")
        return "human_review"
    
    if quality == QualityLevel.EXCELLENT or quality == QualityLevel.GOOD:
        if score >= 0.8:
            logger.info("[路由] 质量优秀，直接输出")
            return "final_answer"
    
    if quality == QualityLevel.POOR or quality == QualityLevel.UNACCEPTABLE:
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        
        if retry_count < max_retries:
            logger.info(f"[路由] 质量不达标，重试 ({retry_count + 1}/{max_retries})")
            return "rework"
        else:
            logger.info("[路由] 超过最大重试次数，转向人工审核")
            return "human_review"
    
    if quality == QualityLevel.ACCEPTABLE:
        logger.info("[路由] 质量可接受，包含建议后输出")
        return "final_answer_with_suggestions"
    
    return "final_answer"


def create_parallel_routing(
    specialist_nodes: List[str]
) -> Callable[[AgentState], List[str]]:
    """
    创建并行路由函数
    
    用于多专家并行执行
    
    Args:
        specialist_nodes: 专家节点列表
        
    Returns:
        路由函数
    """
    def parallel_route(state: AgentState) -> List[str]:
        specialists = state.get("target_specialists", [])
        
        route_map = {
            SpecialistType.FINANCE: "finance_specialist",
            SpecialistType.TAX: "tax_specialist",
            SpecialistType.LEGAL: "legal_specialist",
            SpecialistType.REPORT: "report_specialist"
        }
        
        selected = []
        for specialist in specialists:
            node = route_map.get(specialist)
            if node:
                selected.append(node)
        
        if not selected:
            return ["direct_answer"]
        
        logger.info(f"[路由] 并行执行 {len(selected)} 个专家: {selected}")
        return selected
    
    return parallel_route


def create_iteration_check(max_iterations: int) -> Callable[[AgentState], str]:
    """
    创建迭代检查路由
    
    Args:
        max_iterations: 最大迭代次数
        
    Returns:
        路由函数
    """
    def check_iteration(state: AgentState) -> str:
        current = state.get("iteration", 0)
        
        if current >= max_iterations:
            logger.warning(f"[路由] 达到最大迭代次数 {max_iterations}")
            return "max_iterations_exceeded"
        
        logger.info(f"[路由] 迭代检查: {current}/{max_iterations}")
        return "continue"
    
    return check_iteration


def create_error_check() -> Callable[[AgentState], str]:
    """
    创建错误检查路由
    
    Returns:
        路由函数
    """
    def check_error(state: AgentState) -> str:
        error = state.get("error")
        
        if error:
            logger.warning(f"[路由] 检测到错误: {error}")
            return "error_handler"
        
        return "continue"
    
    return check_error
