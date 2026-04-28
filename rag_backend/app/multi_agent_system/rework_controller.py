"""
重做控制器 - 管理多智能体审查的重做逻辑
"""

import logging
from typing import List
from .state import AuditState

logger = logging.getLogger(__name__)


class ReworkController:
    """
    重做控制器
    
    决定是否需要重做以及哪些 Agent 需要重做
    """
    
    def __init__(self, max_rework_count: int = 2):
        """
        初始化重做控制器
        
        Args:
            max_rework_count: 最大重做次数
        """
        self.max_rework_count = max_rework_count
        logger.debug("Rework controller initialized: max_rework_count=%s", max_rework_count)
    
    def should_rework(self, state: AuditState) -> bool:
        """
        判断是否需要重做
        
        Args:
            state: 全局状态
            
        Returns:
            是否需要重做
        """
        # 检查是否已达最大重做次数
        current_rework_count = state.get('rework_count', 0)
        if current_rework_count >= self.max_rework_count:
            print(f"🔄 [重做控制器] 已达最大重做次数 ({self.max_rework_count})，不再重做")
            return False
        
        # 检查是否有严重冲突
        conflicts = state.get('conflicts', [])
        has_critical_conflicts = any(
            c.get('severity') == 'critical' 
            for c in conflicts
        )
        
        has_high_conflicts = any(
            c.get('severity') == 'high' 
            for c in conflicts
        )
        
        # 检查置信度是否过低
        confidence_scores = state.get('confidence_scores', {})
        overall_confidence = confidence_scores.get('overall', 1.0)
        low_confidence = overall_confidence < 0.6
        
        # 检查证据缺口
        evidence_gaps = state.get('evidence_gaps', [])
        has_evidence_gaps = len(evidence_gaps) > 0
        
        # 决策逻辑
        need_rework = (
            has_critical_conflicts or 
            has_high_conflicts or 
            low_confidence or 
            has_evidence_gaps
        )
        
        if need_rework:
            reasons = []
            if has_critical_conflicts:
                reasons.append("严重冲突")
            if has_high_conflicts:
                reasons.append("高风险冲突")
            if low_confidence:
                reasons.append(f"低置信度({overall_confidence:.2f})")
            if has_evidence_gaps:
                reasons.append(f"证据缺口({len(evidence_gaps)}个)")
            
            print(f"🔄 [重做控制器] 需要重做，原因: {', '.join(reasons)}")
        else:
            print("🔄 [重做控制器] 无需重做")
        
        return need_rework
    
    def identify_rework_agents(self, state: AuditState) -> List[str]:
        """
        识别需要重做的 Agent
        
        Args:
            state: 全局状态
            
        Returns:
            需要重做的 Agent 列表
        """
        rework_agents = set()
        
        # 从冲突中识别
        conflicts = state.get('conflicts', [])
        for conflict in conflicts:
            if conflict.get('severity') in ['high', 'critical']:
                if 'agent1' in conflict:
                    rework_agents.add(conflict['agent1'])
                if 'agent2' in conflict:
                    rework_agents.add(conflict['agent2'])
        
        # 从证据缺口中识别
        evidence_gaps = state.get('evidence_gaps', [])
        for gap in evidence_gaps:
            gap_lower = gap.lower()
            if 'finance' in gap_lower:
                rework_agents.add('finance')
            if 'tax' in gap_lower:
                rework_agents.add('tax')
            if 'legal' in gap_lower:
                rework_agents.add('legal')
        
        # 从低置信度中识别
        confidence_scores = state.get('confidence_scores', {})
        for agent, score in confidence_scores.items():
            if agent != 'overall' and score < 0.7:
                rework_agents.add(agent)
        
        agents_list = list(rework_agents)
        print(f"🔄 [重做控制器] 需要重做的 Agent: {agents_list}")
        
        return agents_list
    
    def prepare_rework_context(self, state: AuditState, agent_name: str) -> str:
        """
        为重做准备上下文信息
        
        Args:
            state: 全局状态
            agent_name: Agent 名称
            
        Returns:
            上下文信息
        """
        context_parts = []
        
        # 添加相关冲突信息
        conflicts = state.get('conflicts', [])
        relevant_conflicts = [
            c for c in conflicts 
            if c.get('agent1') == agent_name or c.get('agent2') == agent_name
        ]
        
        if relevant_conflicts:
            context_parts.append(f"发现 {len(relevant_conflicts)} 个相关冲突:")
            for conflict in relevant_conflicts[:3]:
                context_parts.append(f"  - {conflict.get('description')}")
        
        # 添加证据缺口信息
        evidence_gaps = state.get('evidence_gaps', [])
        relevant_gaps = [g for g in evidence_gaps if agent_name in g.lower()]
        
        if relevant_gaps:
            context_parts.append(f"\n发现 {len(relevant_gaps)} 个证据缺口:")
            for gap in relevant_gaps[:3]:
                context_parts.append(f"  - {gap}")
        
        # 添加其他 Agent 的发现（跨领域协同）
        context_parts.append("\n其他领域的发现:")
        for other_agent in ['finance', 'tax', 'legal']:
            if other_agent != agent_name:
                field_name = f"{other_agent}_findings"
                findings = state.get(field_name, [])
                if findings:
                    context_parts.append(f"  {other_agent}: {len(findings)} 个发现")
        
        return "\n".join(context_parts)
