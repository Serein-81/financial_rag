"""
统一路由函数

可被 LangGraph 条件边和 AgentOrchestrator 共同复用的纯路由函数。
这些函数是"纯函数"——不持有状态，不调用 LLM，只根据输入做决策。

设计原则：
1. 纯函数：输入 → 输出，无副作用
2. 可复用：LangGraph 条件边和 Orchestrator 共用同一份逻辑
3. 可测试：纯函数易于单元测试
4. 可组合：多个路由函数可以组合成复杂路由策略
"""

import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RoutingSource(str, Enum):
    """路由来源"""
    BLACKBOARD_RULE = "blackboard_rule"     # 黑板规则路由
    INTENT_MAP = "intent_map"               # 意图映射路由
    CAPABILITY_MATCH = "capability_match"   # 能力匹配路由
    LLM_ASSISTED = "llm_assisted"           # LLM 辅助路由
    FALLBACK = "fallback"                   # 降级路由


@dataclass
class RoutingDecision:
    """
    路由决策（纯数据类）
    
    只包含"去哪里"的信息，不包含"怎么执行"
    """
    target_nodes: List[str]                  # 目标节点列表
    source: RoutingSource = RoutingSource.FALLBACK
    confidence: float = 0.0
    reasoning: str = ""
    execution_mode: str = "single"           # single | parallel | sequential


def route_by_blackboard_state(
    blackboard: Dict[str, Any],
    available_nodes: Set[str],
) -> Optional[RoutingDecision]:
    """
    黑板状态路由：根据黑板字段做 if/else 判断
    
    这是最高优先级的路由方式，0 成本、0 延迟。
    可被 LangGraph 条件边和 Orchestrator 共同调用。
    
    Args:
        blackboard: 黑板状态字典
        available_nodes: 当前可用的节点集合
        
    Returns:
        路由决策，如果没有匹配的规则则返回 None
    """
    task_status = blackboard.get("task_status", "")
    financial_data = blackboard.get("financial_data")
    tax_data = blackboard.get("tax_data")
    requires_collaboration = blackboard.get("requires_collaboration", False)
    
    if requires_collaboration and "multi_specialist" in available_nodes:
        return RoutingDecision(
            target_nodes=["multi_specialist"],
            source=RoutingSource.BLACKBOARD_RULE,
            confidence=1.0,
            reasoning="黑板标记需要多专家协作",
            execution_mode="parallel",
        )
    
    if task_status == "need_finance" and "finance_specialist" in available_nodes:
        return RoutingDecision(
            target_nodes=["finance_specialist"],
            source=RoutingSource.BLACKBOARD_RULE,
            confidence=1.0,
            reasoning=f"黑板状态 task_status={task_status} -> finance_specialist",
        )
    
    if task_status == "need_tax_analysis" and "tax_specialist" in available_nodes:
        return RoutingDecision(
            target_nodes=["tax_specialist"],
            source=RoutingSource.BLACKBOARD_RULE,
            confidence=1.0,
            reasoning=f"黑板状态 task_status={task_status} -> tax_specialist",
        )
    
    if (
        financial_data is not None
        and isinstance(financial_data, dict)
        and financial_data.get("status") == "ready"
        and "finance_specialist" in available_nodes
    ):
        return RoutingDecision(
            target_nodes=["finance_specialist"],
            source=RoutingSource.BLACKBOARD_RULE,
            confidence=1.0,
            reasoning="财务数据已就绪 -> finance_specialist",
        )
    
    if (
        tax_data is not None
        and isinstance(tax_data, dict)
        and tax_data.get("status") == "ready"
        and "tax_specialist" in available_nodes
    ):
        return RoutingDecision(
            target_nodes=["tax_specialist"],
            source=RoutingSource.BLACKBOARD_RULE,
            confidence=1.0,
            reasoning="税务数据已就绪 -> tax_specialist",
        )
    
    return None


def route_by_intent_result(
    intent_value: str,
    routing_strategy: Optional[str] = None,
    requires_specialists: Optional[List[str]] = None,
    confidence: float = 0.0,
    available_nodes: Optional[Set[str]] = None,
) -> Optional[RoutingDecision]:
    """
    意图结果路由：根据意图分类结果路由到对应节点
    
    可被 LangGraph 条件边和 Orchestrator 共同调用。
    
    Args:
        intent_value: 意图分类值
        routing_strategy: 路由策略
        requires_specialists: 需要的专家列表
        confidence: 置信度
        available_nodes: 当前可用的节点集合
        
    Returns:
        路由决策
    """
    if confidence < 0.5:
        return RoutingDecision(
            target_nodes=["human_review"],
            source=RoutingSource.INTENT_MAP,
            confidence=confidence,
            reasoning=f"置信度过低 ({confidence:.2f})，需要人工审核",
        )
    
    if routing_strategy in ("DIRECT_ANSWER", "direct_answer"):
        return RoutingDecision(
            target_nodes=["direct_answer"],
            source=RoutingSource.INTENT_MAP,
            confidence=confidence,
            reasoning="直接回答策略",
        )
    
    if routing_strategy in ("RAG_RETRIEVAL", "rag_retrieval"):
        return RoutingDecision(
            target_nodes=["rag_retrieval"],
            source=RoutingSource.INTENT_MAP,
            confidence=confidence,
            reasoning="RAG 检索策略",
        )
    
    if routing_strategy in ("REPORT_QUEUE", "report_queue"):
        return RoutingDecision(
            target_nodes=["report_queue"],
            source=RoutingSource.INTENT_MAP,
            confidence=confidence,
            reasoning="报告队列策略",
        )
    
    if requires_specialists:
        node_map = {
            "finance": "finance_specialist",
            "tax": "tax_specialist",
            "legal": "legal_specialist",
        }
        
        target_nodes = []
        for s in requires_specialists:
            node = node_map.get(s, s)
            if available_nodes is None or node in available_nodes:
                target_nodes.append(node)
        
        if target_nodes:
            is_multi = len(target_nodes) > 1
            return RoutingDecision(
                target_nodes=target_nodes,
                source=RoutingSource.INTENT_MAP,
                confidence=confidence,
                reasoning=f"意图 {intent_value} -> {target_nodes}",
                execution_mode=(
                    "parallel"
                    if routing_strategy
                    in ("MULTI_SPECIALIST_PARALLEL", "multi_specialial_parallel")
                    else "sequential"
                    if routing_strategy
                    in ("MULTI_SPECIALIST_SEQUENTIAL", "multi_specialist_sequential")
                    else "single"
                ),
            )
    
    intent_to_node = {
        "financial_analysis": "finance_specialist",
        "accounting_query": "finance_specialist",
        "investment_advisory": "finance_specialist",
        "cost_control": "finance_specialist",
        "risk_analysis": "finance_specialist",
        "tax_calculation": "tax_specialist",
        "tax_planning": "tax_specialist",
        "tax_compliance": "tax_specialist",
        "tax_declaration": "tax_specialist",
        "contract_review": "legal_specialist",
        "legal_consultation": "legal_specialist",
        "compliance_check": "compliance_specialist",
        "ip_protection": "legal_specialist",
        "knowledge_query": "rag_retrieval",
        "document_search": "rag_retrieval",
        "greeting": "direct_answer",
        "chit_chat": "direct_answer",
    }
    
    node = intent_to_node.get(intent_value)
    if node:
        if available_nodes is None or node in available_nodes:
            return RoutingDecision(
                target_nodes=[node],
                source=RoutingSource.INTENT_MAP,
                confidence=confidence,
                reasoning=f"意图映射: {intent_value} -> {node}",
            )
    
    return None


def route_by_agent_capability(
    query: str,
    capabilities: List[Any],
    min_confidence: float = 0.6,
) -> Optional[RoutingDecision]:
    """
    能力匹配路由：根据 Agent 能力描述匹配最佳节点
    
    可被 LangGraph 条件边和 Orchestrator 共同调用。
    
    Args:
        query: 用户查询
        capabilities: Agent 能力列表（AgentCapability 对象列表）
        min_confidence: 最小置信度阈值
        
    Returns:
        路由决策
    """
    if not capabilities:
        return None
    
    query_lower = query.lower()
    scores: List[tuple] = []
    
    for cap in capabilities:
        if not cap.enabled:
            continue
        
        score = 0.0
        matched_keywords = []
        
        for keyword in cap.keywords:
            if keyword.lower() in query_lower:
                weight = cap.metadata.get("keyword_weights", {}).get(keyword.lower(), 0.6)
                score += weight
                matched_keywords.append(keyword)
        
        for domain in cap.domains:
            if domain.lower() in query_lower:
                score += 2.0
        
        if score > 0:
            scores.append((cap.agent_type, score, matched_keywords))
    
    if not scores:
        return None
    
    scores.sort(key=lambda x: x[1], reverse=True)
    best_type, best_score, keywords = scores[0]
    
    normalized_score = min(best_score / 5.0, 1.0)
    
    if normalized_score < min_confidence:
        return None
    
    node_map = {
        "finance": "finance_specialist",
        "tax": "tax_specialist",
        "legal": "legal_specialist",
    }
    
    node = node_map.get(best_type, f"{best_type}_specialist")
    
    return RoutingDecision(
        target_nodes=[node],
        source=RoutingSource.CAPABILITY_MATCH,
        confidence=normalized_score,
        reasoning=f"能力匹配: 关键词 {keywords} -> {best_type} (score={best_score:.1f})",
    )
