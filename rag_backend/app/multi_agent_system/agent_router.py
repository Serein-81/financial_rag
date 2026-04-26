"""
智能体路由器 (Agent Router)

独立的"交警"组件，职责纯粹：
1. 根据当前状态（黑板字段、意图结果）决定下一个 Agent
2. 支持纯规则路由（0 成本）和 LLM 路由两种模式
3. 从 CapabilityRegistry 动态感知 Agent 列表，支持热插拔
4. 不持有任何 Agent 实例引用，不负责 Agent 初始化

设计原则：
- Orchestrator 不知道系统里有哪些 Agent，Router 才知道
- 新增 Agent 只需注册到 CapabilityRegistry，Router 自动感知
- 简单路由走纯规则（查黑板字段），复杂路由走极简 LLM
"""

import re
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from .agent_capability_registry import (
    AgentCapabilityRegistry,
    AgentCapability,
    get_capability_registry,
)
from .agents.intent_router_agent import IntentCategory, RoutingStrategy

logger = logging.getLogger(__name__)


class RouteMode(str, Enum):
    """路由模式"""
    RULE_BASED = "rule_based"          # 纯规则路由（0 成本）
    LLM_ASSISTED = "llm_assisted"     # LLM 辅助路由
    FALLBACK = "fallback"             # 降级路由


@dataclass
class RouteDecision:
    """
    路由决策结果
    
    只包含"去哪里"，不包含"怎么去"
    """
    target_agent_type: str                    # 目标 Agent 类型（如 "finance", "tax"）
    target_agent_ids: List[str]               # 目标 Agent ID 列表（可能有多个候选）
    mode: RouteMode = RouteMode.RULE_BASED    # 路由模式
    confidence: float = 1.0                   # 路由置信度
    reasoning: str = ""                       # 路由理由（用于日志和追踪）
    requires_all: bool = False                # 是否需要所有目标 Agent（多专家模式）
    execution_mode: str = "single"            # single | parallel | sequential


@dataclass
class RoutingRule:
    """
    纯规则路由规则
    
    根据黑板字段状态做 if/else 判断
    """
    name: str
    description: str
    condition: str                           # 条件表达式描述
    check_fn: str                            # 检查函数引用名
    target_agent: str                        # 目标 Agent 类型
    priority: int = 0                        # 优先级（数字越大越优先）
    required_blackboard_fields: List[str] = field(default_factory=list)


class AgentRouter:
    """
    智能体路由器
    
    职责纯粹：只做路由决策，不涉及 Agent 初始化或执行。
    
    路由优先级：
    1. 黑板字段规则路由（最高优先级，0 成本）
    2. 意图+能力匹配路由
    3. LLM 辅助路由（最低优先级，有成本）
    
    使用示例：
        router = AgentRouter(capability_registry=registry)
        
        # 纯规则路由
        decision = router.route_by_blackboard(blackboard_state)
        
        # 意图路由
        decision = router.route_by_intent(intent_result)
        
        # 完整路由
        decision = await router.route(
            user_input=query,
            blackboard=blackboard,
            intent_result=intent_result
        )
    """
    
    def __init__(
        self,
        capability_registry: Optional[AgentCapabilityRegistry] = None,
        llm_adapter: Optional[Any] = None,
    ):
        self.capability_registry = capability_registry or get_capability_registry()
        self.llm_adapter = llm_adapter
        
        self._rules: List[RoutingRule] = []
        self._intent_to_agent: Dict[str, str] = {}
        self._agent_type_map: Dict[str, AgentCapability] = {}
        
        self._build_rules()
        self._build_intent_mapping()
        self._refresh_agent_map()
        
        logger.info("🚦 [AgentRouter] 初始化完成")
        logger.info(f"   - 规则路由: {len(self._rules)} 条")
        logger.info(f"   - 意图映射: {len(self._intent_to_agent)} 条")
        logger.info(f"   - 已注册 Agent: {len(self._agent_type_map)} 个")
    
    def _build_rules(self):
        """构建内置规则路由"""
        self._rules = [
            RoutingRule(
                name="financial_data_missing",
                description="黑板中有 financial_data 但为空 → 路由到数据导入建议",
                condition="blackboard.financial_data is empty",
                check_fn="_check_financial_data_missing",
                target_agent="data_import_advisor",
                priority=100,
                required_blackboard_fields=["financial_data"],
            ),
            RoutingRule(
                name="tax_data_ready_for_analysis",
                description="黑板中有 tax_data 且 task_status=need_tax_analysis → 路由到税务专家",
                condition="blackboard.tax_data exists AND task_status=need_tax_analysis",
                check_fn="_check_tax_data_ready",
                target_agent="tax",
                priority=90,
                required_blackboard_fields=["tax_data", "task_status"],
            ),
            RoutingRule(
                name="finance_data_ready_for_analysis",
                description="黑板中有 finance_data 且 task_status=need_finance → 路由到财务专家",
                condition="blackboard.finance_data exists AND task_status=need_finance",
                check_fn="_check_finance_data_ready",
                target_agent="finance",
                priority=90,
                required_blackboard_fields=["finance_data", "task_status"],
            ),
            RoutingRule(
                name="multi_agent_collaboration",
                description="黑板标记需要多专家协作 → 路由到多个专家",
                condition="blackboard.requires_collaboration=true",
                check_fn="_check_requires_collaboration",
                target_agent="multi",
                priority=80,
                required_blackboard_fields=["requires_collaboration"],
            ),
        ]
    
    def _build_intent_mapping(self):
        """构建意图到 Agent 的映射"""
        self._intent_to_agent = {
            IntentCategory.FINANCIAL_ANALYSIS.value: "finance",
            IntentCategory.ACCOUNTING_QUERY.value: "finance",
            IntentCategory.INVESTMENT_ADVISORY.value: "finance",
            IntentCategory.COST_CONTROL.value: "finance",
            IntentCategory.RISK_ANALYSIS.value: "finance",
            IntentCategory.TAX_CALCULATION.value: "tax",
            IntentCategory.TAX_PLANNING.value: "tax",
            IntentCategory.TAX_COMPLIANCE.value: "tax",
            IntentCategory.TAX_DECLARATION.value: "tax",
            IntentCategory.CONTRACT_REVIEW.value: "legal",
            IntentCategory.LEGAL_CONSULTATION.value: "legal",
            IntentCategory.COMPLIANCE_CHECK.value: "compliance",
            IntentCategory.IP_PROTECTION.value: "legal",
        }
    
    def _refresh_agent_map(self):
        """刷新 Agent 类型映射（从 CapabilityRegistry 动态加载）"""
        self._agent_type_map = {}
        for cap in self.capability_registry.get_all_capabilities():
            if cap.enabled:
                self._agent_type_map[cap.agent_type] = cap
        logger.debug(f"🚦 [AgentRouter] 刷新 Agent 映射: {list(self._agent_type_map.keys())}")
    
    def register_rule(self, rule: RoutingRule):
        """注册自定义路由规则"""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"🚦 [AgentRouter] 注册规则: {rule.name}")
    
    def register_intent_mapping(self, intent_value: str, agent_type: str):
        """注册意图到 Agent 的映射"""
        self._intent_to_agent[intent_value] = agent_type
        logger.info(f"🚦 [AgentRouter] 注册意图映射: {intent_value} -> {agent_type}")
    
    def route_by_blackboard(
        self,
        blackboard: Dict[str, Any],
    ) -> Optional[RouteDecision]:
        """
        纯规则路由：根据黑板字段状态做 if/else 判断
        
        这是最高优先级的路由方式，0 成本、0 延迟。
        
        Args:
            blackboard: 黑板状态字典
            
        Returns:
            路由决策，如果没有匹配的规则则返回 None
        """
        for rule in self._rules:
            check_fn = getattr(self, rule.check_fn, None)
            if check_fn is None:
                continue
            
            try:
                if check_fn(blackboard):
                    agent_ids = self._resolve_agent_ids(rule.target_agent)
                    if agent_ids:
                        logger.info(
                            f"🚦 [AgentRouter] 规则命中: {rule.name} "
                            f"-> {rule.target_agent} (confidence=1.0)"
                        )
                        return RouteDecision(
                            target_agent_type=rule.target_agent,
                            target_agent_ids=agent_ids,
                            mode=RouteMode.RULE_BASED,
                            confidence=1.0,
                            reasoning=f"规则路由: {rule.description}",
                        )
            except Exception as e:
                logger.warning(f"🚦 [AgentRouter] 规则检查失败: {rule.name}, {e}")
                continue
        
        return None
    
    def route_by_intent(
        self,
        intent_result: Any,
    ) -> Optional[RouteDecision]:
        """
        意图路由：根据意图分类结果路由到对应 Agent
        
        Args:
            intent_result: 意图分析结果（IntentAnalysisResult 或类似结构）
            
        Returns:
            路由决策
        """
        intent_value = None
        routing_strategy = None
        requires_specialists = []
        
        if hasattr(intent_result, "intent"):
            intent_value = (
                intent_result.intent.value
                if hasattr(intent_result.intent, "value")
                else str(intent_result.intent)
            )
        if hasattr(intent_result, "routing_strategy"):
            routing_strategy = (
                intent_result.routing_strategy.value
                if hasattr(intent_result.routing_strategy, "value")
                else str(intent_result.routing_strategy)
            )
        if hasattr(intent_result, "requires_specialists"):
            requires_specialists = intent_result.requires_specialists or []
        
        if routing_strategy in (
            "DIRECT_ANSWER",
            "RAG_RETRIEVAL",
            "REPORT_QUEUE",
        ):
            return RouteDecision(
                target_agent_type=routing_strategy.lower(),
                target_agent_ids=[],
                mode=RouteMode.RULE_BASED,
                confidence=1.0,
                reasoning=f"非专家路由策略: {routing_strategy}",
            )
        
        if requires_specialists:
            agent_ids = []
            for st in requires_specialists:
                ids = self._resolve_agent_ids(st)
                agent_ids.extend(ids)
            
            if agent_ids:
                is_multi = len(requires_specialists) > 1
                return RouteDecision(
                    target_agent_type=requires_specialists[0] if not is_multi else "multi",
                    target_agent_ids=agent_ids,
                    mode=RouteMode.RULE_BASED,
                    confidence=float(getattr(intent_result, "confidence", 0.8)),
                    reasoning=(
                        f"意图路由: {intent_value}, "
                        f"策略: {routing_strategy}, "
                        f"专家: {requires_specialists}"
                    ),
                    requires_all=is_multi,
                    execution_mode=(
                        "parallel"
                        if routing_strategy
                        in ("MULTI_SPECIALIST_PARALLEL",)
                        else "sequential"
                        if routing_strategy in ("MULTI_SPECIALIST_SEQUENTIAL",)
                        else "single"
                    ),
                )
        
        if intent_value and intent_value in self._intent_to_agent:
            agent_type = self._intent_to_agent[intent_value]
            agent_ids = self._resolve_agent_ids(agent_type)
            if agent_ids:
                return RouteDecision(
                    target_agent_type=agent_type,
                    target_agent_ids=agent_ids,
                    mode=RouteMode.RULE_BASED,
                    confidence=float(getattr(intent_result, "confidence", 0.7)),
                    reasoning=f"意图映射: {intent_value} -> {agent_type}",
                )
        
        return None
    
    async def route_by_llm(
        self,
        user_input: str,
        blackboard: Dict[str, Any],
        available_agents: List[str],
    ) -> Optional[RouteDecision]:
        """
        LLM 辅助路由：当规则路由无法决策时，用极简 LLM 做路由
        
        LLM 的 Prompt 只有两句话：
        "根据当前状态，输出下一步节点名称。只能从 [A, B, C] 中选。"
        
        Args:
            user_input: 用户输入
            blackboard: 黑板状态
            available_agents: 可用的 Agent 类型列表
            
        Returns:
            路由决策
        """
        if not self.llm_adapter or not available_agents:
            return None
        
        agents_str = ", ".join(available_agents)
        prompt = (
            f"根据用户输入和当前状态，选择最合适的处理节点。\n"
            f"只能从以下选项中选择一个: [{agents_str}]\n\n"
            f"用户输入: {user_input}\n"
            f"当前状态: {blackboard}\n\n"
            f"只返回节点名称，不要任何解释。"
        )
        
        try:
            response = await self.llm_adapter.agenerate(
                prompts=[prompt],
                temperature=0.1,
                max_tokens=50,
            )
            
            chosen = response.content.strip().lower()
            
            if chosen in available_agents:
                agent_ids = self._resolve_agent_ids(chosen)
                logger.info(
                    f"🚦 [AgentRouter] LLM 路由: {chosen} "
                    f"(confidence=0.8, available={available_agents})"
                )
                return RouteDecision(
                    target_agent_type=chosen,
                    target_agent_ids=agent_ids or [],
                    mode=RouteMode.LLM_ASSISTED,
                    confidence=0.8,
                    reasoning=f"LLM 辅助路由: 用户输入 '{user_input[:30]}...' -> {chosen}",
                )
            
            logger.warning(
                f"🚦 [AgentRouter] LLM 返回无效节点: {chosen}, "
                f"可用节点: {available_agents}"
            )
        except Exception as e:
            logger.error(f"🚦 [AgentRouter] LLM 路由失败: {e}")
        
        return None
    
    async def route(
        self,
        user_input: str,
        blackboard: Optional[Dict[str, Any]] = None,
        intent_result: Optional[Any] = None,
    ) -> RouteDecision:
        """
        完整路由流程（三级路由）
        
        优先级：
        1. 黑板规则路由（0 成本）
        2. 意图路由（低成本）
        3. LLM 辅助路由（有成本）
        
        Args:
            user_input: 用户输入
            blackboard: 黑板状态
            intent_result: 意图分析结果
            
        Returns:
            路由决策
        """
        self._refresh_agent_map()
        
        if blackboard:
            decision = self.route_by_blackboard(blackboard)
            if decision is not None:
                return decision
        
        if intent_result is not None:
            decision = self.route_by_intent(intent_result)
            if decision is not None:
                return decision
        
        available = list(self._agent_type_map.keys())
        if available:
            decision = await self.route_by_llm(user_input, blackboard or {}, available)
            if decision is not None:
                return decision
        
        return RouteDecision(
            target_agent_type="fallback",
            target_agent_ids=[],
            mode=RouteMode.FALLBACK,
            confidence=0.0,
            reasoning="所有路由方式均无法决策，使用降级路由",
        )
    
    def get_available_agents(self) -> List[str]:
        """获取当前可用的 Agent 类型列表"""
        self._refresh_agent_map()
        return [
            cap.agent_type
            for cap in self._agent_type_map.values()
            if cap.enabled
        ]
    
    def get_agent_capability(self, agent_type: str) -> Optional[AgentCapability]:
        """获取指定 Agent 的能力描述"""
        self._refresh_agent_map()
        return self._agent_type_map.get(agent_type)
    
    def _resolve_agent_ids(self, agent_type: str) -> List[str]:
        """根据 Agent 类型解析出具体的 Agent ID 列表"""
        self._refresh_agent_map()
        cap = self._agent_type_map.get(agent_type)
        if cap and cap.enabled:
            return [cap.agent_id]
        return []
    
    def _check_financial_data_missing(self, blackboard: Dict[str, Any]) -> bool:
        """检查财务数据是否缺失"""
        financial_data = blackboard.get("financial_data")
        return financial_data is None or (
            isinstance(financial_data, (list, dict)) and len(financial_data) == 0
        )
    
    def _check_tax_data_ready(self, blackboard: Dict[str, Any]) -> bool:
        """检查税务数据是否就绪"""
        tax_data = blackboard.get("tax_data")
        task_status = blackboard.get("task_status")
        return (
            tax_data is not None
            and isinstance(tax_data, (list, dict))
            and len(tax_data) > 0
            and task_status == "need_tax_analysis"
        )

    def _check_finance_data_ready(self, blackboard: Dict[str, Any]) -> bool:
        """检查财务数据是否就绪"""
        finance_data = blackboard.get("finance_data")
        task_status = blackboard.get("task_status")
        return (
            finance_data is not None
            and isinstance(finance_data, (list, dict))
            and len(finance_data) > 0
            and task_status == "need_finance"
        )

    def _check_requires_collaboration(self, blackboard: Dict[str, Any]) -> bool:
        """检查是否需要多专家协作"""
        return blackboard.get("requires_collaboration", False) is True