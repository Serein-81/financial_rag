"""
A2A Orchestrator Node

Orchestrator 节点示例
展示如何使用 AgentCard 作为动态 Prompt 生成器
"""

import logging
from typing import Dict, Any, Optional, List, TypedDict

from .transports.factory import build_prompt_with_agent_cards
from .registry import AgentRegistry, AgentCard
from .models import TaskStatus

logger = logging.getLogger(__name__)


class OrchestratorDecision(TypedDict):
    """编排器决策结果"""
    target_agent: Optional[str]
    action: str
    reasoning: str
    confidence: float


async def orchestrator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrator 节点

    职责：
    1. 动态拉取所有可用 Agent 能力卡
    2. 将能力卡拼接给大模型作为上下文
    3. 大模型思考后决定调用哪个 Agent
    4. 生成 A2A 意图并写入状态黑板

    Args:
        state: LangGraph 状态（包含 user_query 等）

    Returns:
        更新后的状态（包含 routing_decision 等）
    """
    user_query = state.get("user_query", "")
    current_messages = state.get("messages", [])

    logger.info(f"🎯 Orchestrator 开始决策: {user_query[:50]}...")

    registry = AgentRegistry.get_instance()

    available_agents = registry.list_all_agents()

    if not available_agents:
        logger.warning("⚠️ 未发现可用 Agent，使用降级策略")
        return {
            **state,
            "routing_decision": {
                "target_agent": None,
                "action": "fallback",
                "reasoning": "无可用 Agent",
                "confidence": 0.0
            },
            "current_agent": "fallback"
        }

    agent_prompt = build_prompt_with_agent_cards(available_agents)

    system_prompt = f"""你是一个智能编排器，负责根据用户问题选择最合适的专家智能体。

{agent_prompt}

用户问题：{user_query}

请分析用户问题，选择最合适的专家智能体，并说明理由。
"""

    state["available_agents"] = [
        {
            "name": card.name,
            "description": card.description,
            "skills": [s.id for s in card.skills]
        }
        for card in available_agents
    ]

    decision = await _make_routing_decision(
        user_query=user_query,
        available_agents=available_agents,
        agent_prompt=agent_prompt
    )

    logger.info(f"✅ 路由决策: {decision['target_agent']} (confidence={decision['confidence']:.2f})")

    return {
        **state,
        "routing_decision": decision,
        "current_agent": decision.get("target_agent")
    }


async def _make_routing_decision(
    user_query: str,
    available_agents: List[AgentCard],
    agent_prompt: str
) -> OrchestratorDecision:
    """
    做出路由决策

    简化版本：基于关键词匹配
    完整版本：调用 LLM 进行智能路由

    Args:
        user_query: 用户查询
        available_agents: 可用 Agent 列表
        agent_prompt: Agent 能力提示

    Returns:
        路由决策
    """
    query_lower = user_query.lower()

    keyword_mapping = {
        "tax": ["税务", "税", "增值税", "所得税", "tax", "taxation"],
        "finance": ["财务", "利润", "资产", "负债", "报表", "finance", "financial"],
        "legal": ["法律", "合同", "合规", "法规", "legal", "contract"],
        "finance_specialist": ["投资", "融资", "估值", "并购", "investment"],
        "tax_specialist": ["报税", "抵扣", "优惠", "tax", "taxation"],
        "legal_specialist": ["审查", "风险", "条款", "legal", "compliance"]
    }

    for agent_name, keywords in keyword_mapping.items():
        for keyword in keywords:
            if keyword in query_lower:
                matching_agent = next(
                    (card for card in available_agents if agent_name in card.name.lower()),
                    available_agents[0] if available_agents else None
                )

                if matching_agent:
                    return OrchestratorDecision(
                        target_agent=matching_agent.name,
                        action="route_to_specialist",
                        reasoning=f"关键词 '{keyword}' 匹配 {matching_agent.name}",
                        confidence=0.85
                    )

    if available_agents:
        default_agent = available_agents[0]
        return OrchestratorDecision(
            target_agent=default_agent.name,
            action="route_to_default",
            reasoning="无特定关键词，使用默认 Agent",
            confidence=0.5
        )

    return OrchestratorDecision(
        target_agent=None,
        action="no_agent_available",
        reasoning="系统中没有可用 Agent",
        confidence=0.0
    )


async def multi_agent_orchestrator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    多专家协作编排器节点

    当任务需要多个专家协作时使用此节点

    Args:
        state: LangGraph 状态

    Returns:
        更新后的状态（包含多个目标 Agent）
    """
    user_query = state.get("user_query", "")
    requires_collaboration = state.get("requires_multi_agent", False)

    registry = AgentRegistry.get_instance()
    available_agents = registry.list_all_agents()

    if not requires_collaboration:
        return await orchestrator_node(state)

    logger.info("🔄 多专家协作模式")

    complex_keywords = [
        "税务和财务", "税务和合同", "财务和法律",
        "并购税务", "投资税务", "融资合规"
    ]

    needs_multi = any(kw in user_query for kw in complex_keywords)

    if needs_multi:
        target_agents = [
            card.name for card in available_agents
            if any(kw in card.name.lower() for kw in ["tax", "finance", "legal"])
        ]

        if len(target_agents) >= 2:
            logger.info(f"🤝 多专家协作: {target_agents}")
            return {
                **state,
                "routing_decision": {
                    "target_agents": target_agents,
                    "action": "multi_agent_parallel",
                    "reasoning": f"复杂问题需要 {len(target_agents)} 个专家协作",
                    "confidence": 0.9
                },
                "current_agent": "multi_agent_coordinator"
            }

    return await orchestrator_node(state)


def create_orchestrator_with_llm(llm_adapter: Any) -> callable:
    """
    创建基于 LLM 的编排器

    Args:
        llm_adapter: LLM 适配器

    Returns:
        编排器函数
    """
    async def llm_orchestrator_node(state: Dict[str, Any]) -> Dict[str, Any]:
        user_query = state.get("user_query", "")

        registry = AgentRegistry.get_instance()
        available_agents = registry.list_all_agents()

        if not available_agents:
            return {
                **state,
                "routing_decision": {
                    "target_agent": None,
                    "action": "fallback",
                    "reasoning": "无可用 Agent",
                    "confidence": 0.0
                }
            }

        agent_prompt = build_prompt_with_agent_cards(available_agents)

        system_prompt = f"""你是一个专业的智能编排器。

当前可用的专家智能体：
{agent_prompt}

根据用户问题，选择最合适的专家智能体。

分析步骤：
1. 理解用户问题的领域（税务、财务、法律等）
2. 评估问题复杂度（简单查询 vs 多专家协作）
3. 选择最匹配的专家智能体

请以 JSON 格式输出决策：
{{"target_agent": "agent_name", "action": "route|fallback", "reasoning": "原因", "confidence": 0.0-1.0}}
"""

        try:
            response = await llm_adapter.agenerate(
                prompts=[f"{system_prompt}\n\n用户问题：{user_query}"],
                temperature=0.1,
                max_tokens=500
            )

            import json
            content = response.content if hasattr(response, 'content') else str(response)

            try:
                decision = json.loads(content)
            except json.JSONDecodeError:
                decision = {
                    "target_agent": available_agents[0].name if available_agents else None,
                    "action": "route",
                    "reasoning": "LLM 响应解析失败，使用默认决策",
                    "confidence": 0.6
                }

            return {
                **state,
                "routing_decision": decision,
                "current_agent": decision.get("target_agent")
            }

        except Exception as e:
            logger.error(f"❌ LLM 编排器失败: {e}")
            return {
                **state,
                "routing_decision": {
                    "target_agent": available_agents[0].name if available_agents else None,
                    "action": "route",
                    "reasoning": f"LLM 调用失败，降级到规则匹配: {str(e)}",
                    "confidence": 0.4
                }
            }

    return llm_orchestrator_node