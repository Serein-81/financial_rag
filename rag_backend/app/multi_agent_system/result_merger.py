"""
结果合并器 (Result Merger)
负责合并多个 Agent 的审查结果
"""

from typing import List, Dict, Any, Tuple
from collections import defaultdict
import hashlib

from .state import Finding, Conflict, RiskLevel


class ResultMerger:
    """
    结果合并器
    
    功能：
    1. 合并多个 Agent 的发现
    2. 去重相似发现
    3. 检测冲突
    4. 计算综合风险分数
    5. 生成优先级排序
    """
    
    def __init__(self):
        """初始化结果合并器"""
        # 相似度阈值
        self.similarity_threshold = 0.8
        
        # 风险等级权重
        self.risk_weights = {
            RiskLevel.CRITICAL: 1.0,
            RiskLevel.HIGH: 0.8,
            RiskLevel.MEDIUM: 0.6,
            RiskLevel.LOW: 0.3
        }
        
        print("🔀 [结果合并器] 初始化完成")
    
    def merge(
        self,
        finance_findings: List[Dict[str, Any]],
        tax_findings: List[Dict[str, Any]],
        legal_findings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        合并审查结果
        
        Args:
            finance_findings: 财务审查发现
            tax_findings: 税务审查发现
            legal_findings: 法务审查发现
            
        Returns:
            合并后的结果
        """
        print("🔀 [结果合并器] 开始合并结果")
        
        # 1. 收集所有发现
        all_findings = []
        all_findings.extend(self._convert_to_findings(finance_findings))
        all_findings.extend(self._convert_to_findings(tax_findings))
        all_findings.extend(self._convert_to_findings(legal_findings))
        
        print(f"   - 原始发现数量: {len(all_findings)}")
        
        # 2. 去重相似发现
        deduplicated_findings = self._deduplicate(all_findings)
        print(f"   - 去重后数量: {len(deduplicated_findings)}")
        
        # 3. 检测冲突
        conflicts = self._detect_conflicts(deduplicated_findings)
        print(f"   - 检测到冲突: {len(conflicts)}")
        
        # 4. 按风险优先级排序
        sorted_findings = self._sort_by_risk_priority(deduplicated_findings)
        
        # 5. 计算综合评分
        overall_score = self._calculate_overall_score(sorted_findings)
        
        # 6. 生成统计信息
        statistics = self._generate_statistics(sorted_findings, conflicts)
        
        result = {
            "merged_findings": [f.to_dict() for f in sorted_findings],
            "conflicts": [c.to_dict() for c in conflicts],
            "overall_risk_score": overall_score,
            "statistics": statistics,
            "summary": self._generate_summary(sorted_findings, conflicts)
        }
        
        print("✅ [结果合并器] 结果合并完成")
        return result
    
    def _convert_to_findings(self, findings_data: List[Dict[str, Any]]) -> List[Finding]:
        """将字典数据转换为 Finding 对象"""
        findings = []
        for data in findings_data:
            try:
                # 确保 risk_level 是 RiskLevel 枚举
                risk_level = data.get("risk_level", "medium")
                if isinstance(risk_level, str):
                    risk_level = RiskLevel(risk_level)
                
                finding = Finding(
                    id=data.get("id", ""),
                    agent_name=data.get("agent_name", "unknown"),
                    category=data.get("category", "general"),
                    description=data.get("description", ""),
                    risk_level=risk_level,
                    risk_score=data.get("risk_score", 0.5),
                    confidence=data.get("confidence", 0.8),
                    evidence=data.get("evidence", []),
                    legal_basis=data.get("legal_basis"),
                    recommendations=data.get("recommendations")
                )
                findings.append(finding)
            except Exception as e:
                print(f"⚠️ [结果合并器] 转换发现失败: {e}")
                continue
        
        return findings
    
    def _deduplicate(self, findings: List[Finding]) -> List[Finding]:
        """
        去重相似发现
        
        Args:
            findings: 原始发现列表
            
        Returns:
            去重后的发现列表
        """
        if not findings:
            return []
        
        # 按相似度分组
        groups = []
        for finding in findings:
            # 寻找相似的组
            added_to_group = False
            for group in groups:
                if self._is_similar(finding, group[0]):
                    group.append(finding)
                    added_to_group = True
                    break
            
            # 如果没有找到相似组，创建新组
            if not added_to_group:
                groups.append([finding])
        
        # 从每组中选择最佳代表
        deduplicated = []
        for group in groups:
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # 合并相似发现
                merged_finding = self._merge_similar_findings(group)
                deduplicated.append(merged_finding)
        
        return deduplicated
    
    def _is_similar(self, finding1: Finding, finding2: Finding) -> bool:
        """
        判断两个发现是否相似
        
        Args:
            finding1: 发现1
            finding2: 发现2
            
        Returns:
            是否相似
        """
        # 1. 类别相同
        if finding1.category == finding2.category:
            return True
        
        # 2. 描述相似度
        similarity = self._calculate_text_similarity(
            finding1.description, finding2.description
        )
        
        return similarity >= self.similarity_threshold
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        计算文本相似度（简化版）
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            相似度 (0-1)
        """
        if not text1 or not text2:
            return 0.0
        
        # 转换为小写并分词
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        # 计算 Jaccard 相似度
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _merge_similar_findings(self, findings: List[Finding]) -> Finding:
        """
        合并相似发现
        
        Args:
            findings: 相似发现列表
            
        Returns:
            合并后的发现
        """
        if len(findings) == 1:
            return findings[0]
        
        # 选择风险分数最高的作为基础
        base_finding = max(findings, key=lambda f: f.risk_score)
        
        # 合并证据
        all_evidence = []
        for finding in findings:
            all_evidence.extend(finding.evidence)
        unique_evidence = list(set(all_evidence))
        
        # 合并建议
        all_recommendations = []
        for finding in findings:
            if finding.recommendations:
                all_recommendations.extend(finding.recommendations)
        unique_recommendations = list(set(all_recommendations))
        
        # 合并法律依据
        all_legal_basis = []
        for finding in findings:
            if finding.legal_basis:
                all_legal_basis.extend(finding.legal_basis)
        unique_legal_basis = list(set(all_legal_basis)) if all_legal_basis else None
        
        # 计算平均置信度
        avg_confidence = sum(f.confidence for f in findings) / len(findings)
        
        # 创建合并后的发现
        merged_finding = Finding(
            id=base_finding.id,
            agent_name=f"merged_{len(findings)}_agents",
            category=base_finding.category,
            description=f"{base_finding.description} (合并了 {len(findings)} 个相似发现)",
            risk_level=base_finding.risk_level,
            risk_score=base_finding.risk_score,
            confidence=avg_confidence,
            evidence=unique_evidence,
            legal_basis=unique_legal_basis,
            recommendations=unique_recommendations
        )
        
        return merged_finding
    
    def _detect_conflicts(self, findings: List[Finding]) -> List[Conflict]:
        """
        检测冲突
        
        Args:
            findings: 发现列表
            
        Returns:
            冲突列表
        """
        conflicts = []
        
        # 按类别分组
        category_groups = defaultdict(list)
        for finding in findings:
            category_groups[finding.category].append(finding)
        
        # 检测每个类别内的冲突
        for category, category_findings in category_groups.items():
            category_conflicts = self._detect_category_conflicts(category_findings)
            conflicts.extend(category_conflicts)
        
        # 检测跨类别冲突
        cross_conflicts = self._detect_cross_category_conflicts(findings)
        conflicts.extend(cross_conflicts)
        
        return conflicts
    
    def _detect_category_conflicts(self, findings: List[Finding]) -> List[Conflict]:
        """检测同类别内的冲突"""
        conflicts = []
        
        for i, finding1 in enumerate(findings):
            for j, finding2 in enumerate(findings[i+1:], i+1):
                # 检测风险评估冲突
                if abs(finding1.risk_score - finding2.risk_score) > 0.5:
                    conflict = Conflict(
                        id=f"conflict_{finding1.id}_{finding2.id}",
                        finding_ids=[finding1.id, finding2.id],
                        conflict_type="risk_assessment_conflict",
                        description=f"风险评估存在显著差异：{finding1.agent_name} 评估为 {finding1.risk_score:.2f}，"
                                   f"{finding2.agent_name} 评估为 {finding2.risk_score:.2f}",
                        severity="medium",
                        resolution_suggestion="需要进一步审查以确定准确的风险等级"
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _detect_cross_category_conflicts(self, findings: List[Finding]) -> List[Conflict]:
        """检测跨类别冲突"""
        conflicts = []
        
        # TODO: 实现更复杂的跨类别冲突检测逻辑
        # 例如：财务数据与税务数据不一致
        
        return conflicts
    
    def _sort_by_risk_priority(self, findings: List[Finding]) -> List[Finding]:
        """
        按风险优先级排序
        
        Args:
            findings: 发现列表
            
        Returns:
            排序后的发现列表
        """
        def risk_priority_key(finding: Finding) -> Tuple[float, float, float]:
            # 1. 风险等级权重
            risk_weight = self.risk_weights.get(finding.risk_level, 0.5)
            
            # 2. 风险分数
            risk_score = finding.risk_score
            
            # 3. 置信度
            confidence = finding.confidence
            
            # 综合优先级分数
            priority_score = risk_weight * risk_score * confidence
            
            return (priority_score, risk_score, confidence)
        
        return sorted(findings, key=risk_priority_key, reverse=True)
    
    def _calculate_overall_score(self, findings: List[Finding]) -> float:
        """
        计算综合风险分数
        
        Args:
            findings: 发现列表
            
        Returns:
            综合风险分数 (0-100)
        """
        if not findings:
            return 0.0
        
        # 加权平均
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for finding in findings:
            weight = self.risk_weights.get(finding.risk_level, 0.5)
            weighted_score = finding.risk_score * weight * finding.confidence
            
            total_weighted_score += weighted_score
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        # 转换为 0-100 分数
        normalized_score = (total_weighted_score / total_weight) * 100
        return min(100.0, max(0.0, normalized_score))
    
    def _generate_statistics(
        self,
        findings: List[Finding],
        conflicts: List[Conflict]
    ) -> Dict[str, Any]:
        """
        生成统计信息
        
        Args:
            findings: 发现列表
            conflicts: 冲突列表
            
        Returns:
            统计信息
        """
        # 按风险等级统计
        risk_level_counts = defaultdict(int)
        for finding in findings:
            risk_level_counts[finding.risk_level.value] += 1
        
        # 按 Agent 统计
        agent_counts = defaultdict(int)
        for finding in findings:
            agent_counts[finding.agent_name] += 1
        
        # 按类别统计
        category_counts = defaultdict(int)
        for finding in findings:
            category_counts[finding.category] += 1
        
        return {
            "total_findings": len(findings),
            "total_conflicts": len(conflicts),
            "risk_level_distribution": dict(risk_level_counts),
            "agent_contribution": dict(agent_counts),
            "category_distribution": dict(category_counts),
            "average_confidence": sum(f.confidence for f in findings) / len(findings) if findings else 0.0,
            "average_risk_score": sum(f.risk_score for f in findings) / len(findings) if findings else 0.0
        }
    
    def _generate_summary(
        self,
        findings: List[Finding],
        conflicts: List[Conflict]
    ) -> str:
        """
        生成摘要
        
        Args:
            findings: 发现列表
            conflicts: 冲突列表
            
        Returns:
            摘要文本
        """
        if not findings:
            return "未发现明显风险问题。"
        
        # 统计各风险等级数量
        critical_count = sum(1 for f in findings if f.risk_level == RiskLevel.CRITICAL)
        high_count = sum(1 for f in findings if f.risk_level == RiskLevel.HIGH)
        medium_count = sum(1 for f in findings if f.risk_level == RiskLevel.MEDIUM)
        low_count = sum(1 for f in findings if f.risk_level == RiskLevel.LOW)
        
        summary_parts = [
            f"共发现 {len(findings)} 个问题"
        ]
        
        if critical_count > 0:
            summary_parts.append(f"严重风险 {critical_count} 个")
        if high_count > 0:
            summary_parts.append(f"高风险 {high_count} 个")
        if medium_count > 0:
            summary_parts.append(f"中风险 {medium_count} 个")
        if low_count > 0:
            summary_parts.append(f"低风险 {low_count} 个")
        
        if conflicts:
            summary_parts.append(f"检测到 {len(conflicts)} 个冲突需要进一步确认")
        
        return "，".join(summary_parts) + "。"