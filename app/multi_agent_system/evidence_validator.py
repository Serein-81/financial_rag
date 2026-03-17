"""
证据验证器 - 验证审查发现的证据完整性
"""

from typing import List, Dict, Any
from .state import Finding


class EvidenceValidator:
    """
    证据验证器
    
    验证每个审查发现是否有充分的证据支持
    """
    
    def __init__(self):
        """初始化证据验证器"""
        print("📋 [证据验证器] 初始化完成")
    
    async def validate(self, findings: List[Dict]) -> List[str]:
        """
        验证证据完整性
        
        Args:
            findings: 发现列表
            
        Returns:
            证据缺口列表
        """
        gaps = []
        
        for finding_data in findings:
            finding = Finding(**finding_data)
            
            # 验证法律依据
            legal_basis_gap = self.validate_legal_basis(finding)
            if legal_basis_gap:
                gaps.append(legal_basis_gap)
            
            # 验证证据链
            evidence_gap = self.validate_evidence_chain(finding)
            if evidence_gap:
                gaps.append(evidence_gap)
        
        print(f"📋 [证据验证器] 发现 {len(gaps)} 个证据缺口")
        return gaps
    
    def validate_legal_basis(self, finding: Finding) -> str:
        """
        验证法律依据
        
        Args:
            finding: 审查发现
            
        Returns:
            缺口描述（如果有）
        """
        # 检查是否有法律依据
        if not finding.legal_basis or len(finding.legal_basis) == 0:
            return f"{finding.agent_name}: {finding.description[:50]}... 缺少法律依据"
        
        # 检查法律依据格式
        for basis in finding.legal_basis:
            if not self._is_valid_legal_reference(basis):
                return f"{finding.agent_name}: 法律依据格式不正确 - {basis}"
        
        return ""
    
    def validate_evidence_chain(self, finding: Finding) -> str:
        """
        验证证据链
        
        Args:
            finding: 审查发现
            
        Returns:
            缺口描述（如果有）
        """
        # 检查是否有具体证据
        if not finding.evidence or len(finding.evidence) == 0:
            return f"{finding.agent_name}: {finding.description[:50]}... 缺少具体证据"
        
        # 检查证据与结论的关联性
        # TODO: 实现更复杂的关联性检查
        
        return ""
    
    def _is_valid_legal_reference(self, reference: str) -> bool:
        """
        检查法律引用格式是否正确
        
        Args:
            reference: 法律引用
            
        Returns:
            是否有效
        """
        # 简单的格式检查
        valid_patterns = [
            "法", "条例", "准则", "规定", "办法", "通知",
            "第", "条", "款", "项"
        ]
        
        return any(pattern in reference for pattern in valid_patterns)
    
    def generate_evidence_report(self, gaps: List[str]) -> Dict[str, Any]:
        """
        生成证据缺口报告
        
        Args:
            gaps: 证据缺口列表
            
        Returns:
            报告字典
        """
        # 按 Agent 分组
        by_agent = {}
        for gap in gaps:
            agent = gap.split(":")[0] if ":" in gap else "unknown"
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append(gap)
        
        return {
            "total_gaps": len(gaps),
            "by_agent": by_agent,
            "severity": "high" if len(gaps) > 5 else "medium" if len(gaps) > 0 else "low"
        }
