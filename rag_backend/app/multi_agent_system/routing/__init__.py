"""
统一路由模块

提供可被 LangGraph 条件边和 AgentOrchestrator 共同复用的路由函数。
确保路由逻辑只有一份定义，无论走 LangGraph 还是直接调用都保持一致。
"""

from .unified_router import (
    RoutingDecision,
    RoutingSource,
    route_by_blackboard_state,
    route_by_intent_result,
    route_by_agent_capability,
)

__all__ = [
    "RoutingDecision",
    "RoutingSource",
    "route_by_blackboard_state",
    "route_by_intent_result",
    "route_by_agent_capability",
]
