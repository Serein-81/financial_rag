"""
专家会诊节点

在 LangGraph 节点内部使用 Message Bus 实现 Agent 自由辩论

功能：
1. 并行调用多个专家 Agent
2. 通过 Message Bus 实现 Agent 间通信
3. 检测共识达成
4. 处理分歧点
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.state.unified_state import UnifiedState, SpecialistType, IntentCategory
from app.langgraph.hybrid.blackboard_manager import BlackboardManager, BlackboardEntry

logger = logging.getLogger(__name__)


@dataclass
class ExpertConsultationState:
    """
    专家会诊状态
    
    用于管理专家会诊的临时状态
    """
    consultation_topic: str
    active_agents: List[str]
    agent_results: Dict[str, Any] = field(default_factory=dict)
    agent_messages: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    consensus: Optional[str] = None
    disagreements: List[str] = field(default_factory=list)
    key_decisions: List[str] = field(default_factory=list)
    max_rounds: int = 3
    current_round: int = 0
    started_at: datetime = field(default_factory=datetime.now)


class ExpertConsultationNode:
    """
    专家会诊节点
    
    在 LangGraph 的节点内部使用 Message Bus 实现专家自由辩论。
    
    使用流程：
    1. 根据 target_specialists 启动对应的专家 Agent
    2. 通过 BlackboardManager 实现 Agent 间的信息共享
    3. 多轮辩论后，检测是否达成共识
    4. 返回共识结果和分歧点
    
    Attributes:
        blackboard: 黑板管理器，用于 Agent 间通信
        max_rounds: 最大辩论轮数
        consensus_threshold: 共识达成阈值（0-1）
    """
    
    def __init__(
        self,
        blackboard: Optional[BlackboardManager] = None,
        max_rounds: int = 3,
        consensus_threshold: float = 0.8,
        agent_factory: Optional[Callable] = None
    ):
        """
        初始化专家会诊节点
        
        Args:
            blackboard: 黑板管理器实例
            max_rounds: 最大辩论轮数
            consensus_threshold: 共识阈值（0-1）
            agent_factory: Agent 工厂函数，用于创建专家 Agent
        """
        self.blackboard = blackboard or BlackboardManager()
        self.max_rounds = max_rounds
        self.consensus_threshold = consensus_threshold
        self.agent_factory = agent_factory or self._default_agent_factory
    
    def _default_agent_factory(self, agent_name: str) -> Any:
        """
        默认 Agent 工厂
        
        根据 Agent 名称创建对应的 Agent 实例
        
        Args:
            agent_name: Agent 名称（finance, tax, legal）
            
        Returns:
            Agent 实例
        """
        from app.multi_agent_system.agents import (
            FinanceSpecialist,
            TaxSpecialist,
            LegalSpecialist
        )
        
        agent_map = {
            "finance": FinanceSpecialist,
            "tax": TaxSpecialist,
            "legal": LegalSpecialist
        }
        
        agent_class = agent_map.get(agent_name)
        if not agent_class:
            raise ValueError(f"未知的专家类型: {agent_name}")
        
        return agent_class()
    
    async def invoke(
        self,
        state: UnifiedState,
        **kwargs
    ) -> UnifiedState:
        """
        执行专家会诊
        
        这是 LangGraph 节点的主入口函数
        
        Args:
            state: LangGraph 状态
            **kwargs: 其他参数
            
        Returns:
            更新后的状态
        """
        logger.info(
            f"[ExpertConsultation] 开始专家会诊: "
            f"topic={state['user_query']}, "
            f"request_id={state['request_id']}"
        )
        
        # 检查是否需要专家会诊
        if state.get("intent") != IntentCategory.EXPERT_CONSULTATION:
            if not state.get("target_specialists") or len(state["target_specialists"]) < 2:
                logger.info("[ExpertConsultation] 跳过专家会诊（专家数量不足）")
                return state
        
        # 获取目标专家列表
        target_specialists = state.get("target_specialists", [])
        if isinstance(target_specialists[0], SpecialistType):
            agent_names = [s.value for s in target_specialists]
        else:
            agent_names = list(target_specialists)
        
        # 初始化会诊状态
        consultation_state = ExpertConsultationState(
            consultation_topic=state["user_query"],
            active_agents=agent_names,
            max_rounds=self.max_rounds
        )
        
        # 执行多轮辩论
        try:
            consultation_state = await self._run_debate(consultation_state, state)
            
            # 更新状态
            state["message_bus_summary"] = consultation_state.consensus
            state["message_bus_disagreements"] = consultation_state.disagreements
            state["message_bus_key_decisions"] = consultation_state.key_decisions
            state["current_phase"] = "expert_consultation_completed"
            
            logger.info(
                f"[ExpertConsultation] 专家会诊完成: "
                f"rounds={consultation_state.current_round}, "
                f"has_consensus={consultation_state.consensus is not None}, "
                f"disagreements={len(consultation_state.disagreements)}"
            )
            
        except Exception as e:
            logger.error(f"[ExpertConsultation] 专家会诊失败: {e}", exc_info=True)
            state["error"] = f"专家会诊失败: {str(e)}"
            state["warnings"] = state.get("warnings", [])
            state["warnings"].append(f"专家会诊执行出错: {str(e)}")
        
        return state
    
    async def _run_debate(
        self,
        consultation_state: ExpertConsultationState,
        graph_state: UnifiedState
    ) -> ExpertConsultationState:
        """
        执行多轮辩论
        
        Args:
            consultation_state: 会诊状态
            graph_state: LangGraph 状态
            
        Returns:
            更新后的会诊状态
        """
        for round_num in range(consultation_state.current_round, consultation_state.max_rounds):
            logger.info(
                f"[ExpertConsultation] 第 {round_num + 1}/{consultation_state.max_rounds} 轮辩论"
            )
            
            # 并行调用所有专家
            tasks = []
            for agent_name in consultation_state.active_agents:
                task = self._call_agent(
                    agent_name,
                    consultation_state.consultation_topic,
                    consultation_state,
                    graph_state
                )
                tasks.append(task)
            
            # 等待所有专家完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集结果
            for agent_name, result in zip(consultation_state.active_agents, results):
                if isinstance(result, Exception):
                    logger.error(f"[ExpertConsultation] Agent {agent_name} 出错: {result}")
                    consultation_state.agent_results[agent_name] = {
                        "error": str(result),
                        "status": "failed"
                    }
                else:
                    consultation_state.agent_results[agent_name] = result
                    # 发布到黑板
                    self.blackboard.post(
                        agent_name=agent_name,
                        content=result,
                        metadata={"round": round_num}
                    )
            
            # 检查是否达成共识
            consensus = self._check_consensus(consultation_state)
            if consensus:
                consultation_state.consensus = consensus
                consultation_state.current_round = round_num + 1
                logger.info(
                    f"[ExpertConsultation] 第 {round_num + 1} 轮达成共识"
                )
                break
            
            consultation_state.current_round = round_num + 1
        
        # 如果未达成共识，汇总分歧
        if not consultation_state.consensus:
            consultation_state.disagreements = self._extract_disagreements(
                consultation_state
            )
            consultation_state.key_decisions = self._extract_key_decisions(
                consultation_state
            )
        
        return consultation_state
    
    async def _call_agent(
        self,
        agent_name: str,
        topic: str,
        consultation_state: ExpertConsultationState,
        graph_state: UnifiedState
    ) -> Dict[str, Any]:
        """
        调用单个专家 Agent
        
        Args:
            agent_name: Agent 名称
            topic: 讨论话题
            consultation_state: 会诊状态
            graph_state: LangGraph 状态
            
        Returns:
            Agent 的响应结果
        """
        try:
            # 创建 Agent 实例
            agent = self.agent_factory(agent_name)
            
            # 获取黑板上的历史信息
            board_history = self.blackboard.get_history(agent_name)
            
            # 构建提示词
            prompt = self._build_consultation_prompt(
                topic=topic,
                agent_name=agent_name,
                board_history=board_history,
                current_round=consultation_state.current_round
            )
            
            # 调用 Agent（这里应该根据实际 Agent 接口调整）
            if hasattr(agent, "analyze"):
                result = await agent.analyze(prompt)
            elif hasattr(agent, "invoke"):
                result = await agent.invoke({"query": prompt})
            else:
                result = await agent(prompt)
            
            return {
                "status": "success",
                "agent": agent_name,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[ExpertConsultation] 调用 Agent {agent_name} 失败: {e}")
            return {
                "status": "error",
                "agent": agent_name,
                "error": str(e)
            }
    
    def _build_consultation_prompt(
        self,
        topic: str,
        agent_name: str,
        board_history: List[BlackboardEntry],
        current_round: int
    ) -> str:
        """
        构建专家咨询提示词
        
        Args:
            topic: 讨论话题
            agent_name: 当前 Agent 名称
            board_history: 黑板历史记录
            current_round: 当前轮次
            
        Returns:
            提示词字符串
        """
        # 获取其他 Agent 的观点
        other_views = []
        for entry in board_history:
            if entry.agent_name != agent_name:
                other_views.append(f"[{entry.agent_name}]: {entry.content}")
        
        prompt = f"""
# 专家会诊讨论

## 讨论话题
{topic}

## 你的角色
{agent_name} 专家

## 当前轮次
第 {current_round + 1} 轮

## 其他专家的观点
{chr(10).join(other_views) if other_views else "（这是第一轮，暂无其他观点）"}

## 任务
1. 阅读其他专家的观点
2. 基于你的专业知识发表你的看法
3. 如果同意其他观点，请说明理由
4. 如果不同意，请提出你的不同意见和理由
5. 尝试寻找共识点

## 输出格式
请输出你的分析和建议：
"""
        
        return prompt
    
    def _check_consensus(
        self,
        consultation_state: ExpertConsultationState
    ) -> Optional[str]:
        """
        检查是否达成共识
        
        Args:
            consultation_state: 会诊状态
            
        Returns:
            共识内容，如果未达成则返回 None
        """
        if len(consultation_state.agent_results) < 2:
            return None
        
        # 简单策略：检查所有 Agent 是否都标记为成功
        success_count = sum(
            1 for r in consultation_state.agent_results.values()
            if r.get("status") == "success"
        )
        
        if success_count < len(consultation_state.active_agents):
            return None
        
        # TODO: 实现更复杂的共识检测逻辑
        # 可以使用以下方法：
        # 1. LLM 判断是否达成共识
        # 2. 投票机制
        # 3. 语义相似度计算
        
        return None
    
    def _extract_disagreements(
        self,
        consultation_state: ExpertConsultationState
    ) -> List[str]:
        """
        提取分歧点
        
        Args:
            consultation_state: 会诊状态
            
        Returns:
            分歧点列表
        """
        disagreements = []
        
        # 简单实现：收集所有 Agent 结果中的不同意见
        # TODO: 使用更智能的方法检测真正的分歧
        
        return disagreements
    
    def _extract_key_decisions(
        self,
        consultation_state: ExpertConsultationState
    ) -> List[str]:
        """
        提取关键决策
        
        Args:
            consultation_state: 会诊状态
            
        Returns:
            关键决策列表
        """
        decisions = []
        
        # 简单实现：从 Agent 结果中提取关键决策
        # TODO: 使用更智能的方法提取决策
        
        return decisions


def expert_consultation_node_func(
    state: UnifiedState,
    **kwargs
) -> UnifiedState:
    """
    LangGraph 节点函数包装器
    
    将 ExpertConsultationNode 转换为 LangGraph 兼容的节点函数
    
    Args:
        state: LangGraph 状态
        **kwargs: 其他参数
        
    Returns:
        更新后的状态
    """
    node = ExpertConsultationNode(**kwargs)
    return asyncio.run(node.invoke(state, **kwargs))
