# app/multi_agent_system/report_generator.py
"""
报告生成器 - Phase 7
从 AuditState 生成结构化审查报告
"""
from typing import Dict, List, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict
import json

from .state import AuditState, Finding, Conflict


@dataclass
class AuditReport:
    """审查报告数据结构"""
    # 基本信息
    task_id: str
    tenant_id: str
    audit_type: str
    created_at: datetime = field(default_factory=datetime.now)
    
    # 执行摘要
    summary: str = ""
    overall_risk_score: float = 0.0  # 0-100
    total_findings: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    low_risk_count: int = 0
    
    # 详细发现
    finance_findings: List[Dict] = field(default_factory=list)
    tax_findings: List[Dict] = field(default_factory=list)
    legal_findings: List[Dict] = field(default_factory=list)
    
    # 反思结果
    conflicts: List[Dict] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    reflection_summary: str = ""
    
    # 改进建议
    immediate_actions: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # 法律依据
    legal_references: List[Dict] = field(default_factory=list)
    
    # 元数据
    processing_time: float = 0.0
    rework_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 转换 datetime 为字符串
        data['created_at'] = self.created_at.isoformat()
        return data
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        print("[报告生成器] 初始化完成")
    
    async def generate(
        self, 
        state: AuditState,
        task_id: str,
        processing_time: float = 0.0
    ) -> AuditReport:
        """
        从 AuditState 生成审查报告
        
        Args:
            state: 审查全局状态
            task_id: 任务 ID
            processing_time: 处理时间（秒）
        
        Returns:
            AuditReport: 结构化报告
        """
        print(f"[报告生成器] 开始生成报告: {task_id}")
        
        # 创建报告对象
        report = AuditReport(
            task_id=task_id,
            tenant_id=state.get('tenant_id', 'unknown'),
            audit_type=state.get('audit_type', 'comprehensive'),
            processing_time=processing_time
        )
        
        # 1. 汇总发现
        report.finance_findings = self._serialize_findings(
            state.get('finance_findings', [])
        )
        report.tax_findings = self._serialize_findings(
            state.get('tax_findings', [])
        )
        report.legal_findings = self._serialize_findings(
            state.get('legal_findings', [])
        )
        
        # 2. 统计数量
        all_findings = (
            report.finance_findings + 
            report.tax_findings + 
            report.legal_findings
        )
        report.total_findings = len(all_findings)
        
        # 3. 分类风险等级
        risk_counts = self._classify_risk_levels(all_findings)
        report.high_risk_count = risk_counts['high']
        report.medium_risk_count = risk_counts['medium']
        report.low_risk_count = risk_counts['low']
        
        # 4. 计算综合风险分数
        report.overall_risk_score = self._calculate_risk_score(
            report.high_risk_count,
            report.medium_risk_count,
            report.low_risk_count
        )
        
        # 5. 反思结果
        report.conflicts = self._serialize_conflicts(
            state.get('conflicts', [])
        )
        report.confidence_scores = state.get('confidence_scores', {})
        report.reflection_summary = state.get('reflection_summary', '')
        report.rework_count = state.get('rework_count', 0)
        
        # 6. 生成执行摘要
        report.summary = self._generate_summary(report)
        
        # 7. 生成改进建议
        report.immediate_actions = self._generate_immediate_actions(all_findings)
        report.recommendations = self._generate_recommendations(all_findings)
        
        # 8. 提取法律依据
        report.legal_references = self._extract_legal_references(all_findings)
        
        print("[报告生成器] 报告生成完成")
        print(f"  - 总发现数: {report.total_findings}")
        print(f"  - 风险分数: {report.overall_risk_score:.1f}")
        print(f"  - 高风险: {report.high_risk_count}, 中风险: {report.medium_risk_count}, 低风险: {report.low_risk_count}")
        
        return report
    
    def _serialize_findings(self, findings: List[Finding]) -> List[Dict]:
        """序列化发现列表"""
        result = []
        for finding in findings:
            if isinstance(finding, dict):
                result.append(finding)
            else:
                # 如果是 Finding 对象，转换为字典
                result.append({
                    'type': getattr(finding, 'type', 'info'),
                    'message': getattr(finding, 'message', ''),
                    'severity': getattr(finding, 'severity', 'low'),
                    'evidence': getattr(finding, 'evidence', ''),
                    'legal_basis': getattr(finding, 'legal_basis', ''),
                    'confidence': getattr(finding, 'confidence', 1.0)
                })
        return result
    
    def _serialize_conflicts(self, conflicts: List[Conflict]) -> List[Dict]:
        """序列化冲突列表"""
        result = []
        for conflict in conflicts:
            if isinstance(conflict, dict):
                result.append(conflict)
            else:
                result.append({
                    'type': getattr(conflict, 'type', 'unknown'),
                    'agent1': getattr(conflict, 'agent1', ''),
                    'agent2': getattr(conflict, 'agent2', ''),
                    'description': getattr(conflict, 'description', ''),
                    'severity': getattr(conflict, 'severity', 'medium'),
                    'resolved': getattr(conflict, 'resolved', False)
                })
        return result
    
    def _classify_risk_levels(self, findings: List[Dict]) -> Dict[str, int]:
        """分类风险等级"""
        counts = {'high': 0, 'medium': 0, 'low': 0}
        
        for finding in findings:
            severity = finding.get('severity', 'low').lower()
            
            # 映射不同的严重性表示
            if severity in ['high', 'critical', 'error', 'risk']:
                counts['high'] += 1
            elif severity in ['medium', 'warning', 'moderate']:
                counts['medium'] += 1
            else:
                counts['low'] += 1
        
        return counts
    
    def _calculate_risk_score(
        self, 
        high: int, 
        medium: int, 
        low: int
    ) -> float:
        """
        计算综合风险分数 (0-100)
        
        算法: 高风险 × 10 + 中风险 × 5 + 低风险 × 1
        然后归一化到 0-100
        """
        if high + medium + low == 0:
            return 0.0
        
        # 加权计算
        weighted_score = high * 10 + medium * 5 + low * 1
        
        # 归一化到 0-100（假设最多 20 个发现）
        max_possible = 20 * 10  # 20 个高风险
        normalized = min(100.0, (weighted_score / max_possible) * 100)
        
        return round(normalized, 2)
    
    def _generate_summary(self, report: AuditReport) -> str:
        """生成执行摘要"""
        summary_parts = []
        
        # 基本信息
        summary_parts.append(
            f"本次审查共发现 {report.total_findings} 个问题，"
            f"综合风险评分为 {report.overall_risk_score:.1f}/100。"
        )
        
        # 风险分布
        if report.high_risk_count > 0:
            summary_parts.append(
                f"其中高风险问题 {report.high_risk_count} 个，需要立即处理。"
            )
        
        if report.medium_risk_count > 0:
            summary_parts.append(
                f"中风险问题 {report.medium_risk_count} 个，建议尽快处理。"
            )
        
        # 领域分布
        domain_summary = []
        if report.finance_findings:
            domain_summary.append(f"财务领域 {len(report.finance_findings)} 个")
        if report.tax_findings:
            domain_summary.append(f"税务领域 {len(report.tax_findings)} 个")
        if report.legal_findings:
            domain_summary.append(f"法务领域 {len(report.legal_findings)} 个")
        
        if domain_summary:
            summary_parts.append(
                f"问题分布：{', '.join(domain_summary)}。"
            )
        
        # 反思结果
        if report.conflicts:
            summary_parts.append(
                f"检测到 {len(report.conflicts)} 个跨领域冲突，已进行协调处理。"
            )
        
        # 置信度
        if report.confidence_scores:
            overall_confidence = report.confidence_scores.get('overall', 0)
            if overall_confidence > 0:
                summary_parts.append(
                    f"整体置信度：{overall_confidence:.0%}。"
                )
        
        return " ".join(summary_parts)
    
    def _generate_immediate_actions(self, findings: List[Dict]) -> List[str]:
        """生成立即整改建议"""
        actions = []
        
        # 提取高风险问题
        high_risk_findings = [
            f for f in findings 
            if f.get('severity', '').lower() in ['high', 'critical', 'error', 'risk']
        ]
        
        for finding in high_risk_findings[:5]:  # 最多 5 个
            message = finding.get('message', '')
            if message:
                actions.append(f"立即处理：{message}")
        
        return actions
    
    def _generate_recommendations(self, findings: List[Dict]) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 提取中低风险问题
        medium_low_findings = [
            f for f in findings 
            if f.get('severity', '').lower() in ['medium', 'low', 'warning', 'info']
        ]
        
        for finding in medium_low_findings[:5]:  # 最多 5 个
            message = finding.get('message', '')
            if message:
                recommendations.append(f"建议优化：{message}")
        
        return recommendations
    
    def _extract_legal_references(self, findings: List[Dict]) -> List[Dict]:
        """提取法律依据"""
        references = []
        seen = set()
        
        for finding in findings:
            legal_basis = finding.get('legal_basis', '')
            if legal_basis and legal_basis not in seen:
                references.append({
                    'law': legal_basis,
                    'context': finding.get('message', '')[:100]  # 前 100 字
                })
                seen.add(legal_basis)
        
        return references


# 导出
__all__ = ['ReportGenerator', 'AuditReport']
