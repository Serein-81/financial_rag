"""
冲突检测器 - 用于检测多智能体审查结果中的冲突
"""

import uuid
from typing import List, Dict, Any
from .state import Finding, Conflict


class ConflictDetector:
    """
    冲突检测器
    
    使用规则引擎检测常见的跨领域冲突模式
    """
    
    # 冲突模式定义
    CONFLICT_PATTERNS = {
        "income_vs_loan": {
            "finance_keywords": ["营业收入", "主营业务收入", "收入"],
            "legal_keywords": ["借款", "贷款", "融资", "对赌"],
            "severity": "high",
            "description": "财务认为是营业收入，法务认为是借款"
        },
        "tax_rate_mismatch": {
            "tax_keywords": ["13%", "9%", "6%", "税率"],
            "finance_keywords": ["收入类型", "应税项目"],
            "severity": "medium",
            "description": "税率与收入类型不匹配"
        },
        "contract_vs_accounting": {
            "legal_keywords": ["合同", "协议", "约定"],
            "finance_keywords": ["会计处理", "科目", "分类"],
            "severity": "medium",
            "description": "合同约定与会计处理不一致"
        }
    }
    
    def __init__(self):
        """初始化冲突检测器"""
        print("🔍 [冲突检测器] 初始化完成")
    
    async def detect(
        self,
        finance_findings: List[Dict],
        tax_findings: List[Dict],
        legal_findings: List[Dict]
    ) -> List[Conflict]:
        """
        检测冲突
        
        Args:
            finance_findings: 财务发现列表
            tax_findings: 税务发现列表
            legal_findings: 法务发现列表
            
        Returns:
            冲突列表
        """
        conflicts = []
        
        # 转换为 Finding 对象
        finance_objs = [Finding(**f) for f in finance_findings]
        tax_objs = [Finding(**f) for f in tax_findings]
        legal_objs = [Finding(**f) for f in legal_findings]
        
        # 检测各种冲突模式
        conflicts.extend(
            self._detect_pattern_conflicts(
                "income_vs_loan",
                finance_objs,
                legal_objs,
                "finance",
                "legal"
            )
        )
        
        conflicts.extend(
            self._detect_pattern_conflicts(
                "tax_rate_mismatch",
                tax_objs,
                finance_objs,
                "tax",
                "finance"
            )
        )
        
        conflicts.extend(
            self._detect_pattern_conflicts(
                "contract_vs_accounting",
                legal_objs,
                finance_objs,
                "legal",
                "finance"
            )
        )
        
        print(f"🔍 [冲突检测器] 检测到 {len(conflicts)} 个冲突")
        return conflicts
    
    def _detect_pattern_conflicts(
        self,
        pattern_name: str,
        findings1: List[Finding],
        findings2: List[Finding],
        agent1: str,
        agent2: str
    ) -> List[Conflict]:
        """检测特定模式的冲突"""
        conflicts = []
        pattern = self.CONFLICT_PATTERNS.get(pattern_name)
        
        if not pattern:
            return conflicts
        
        # 获取关键词
        keywords1_key = f"{agent1}_keywords"
        keywords2_key = f"{agent2}_keywords"
        
        keywords1 = pattern.get(keywords1_key, [])
        keywords2 = pattern.get(keywords2_key, [])
        
        # 检测冲突
        for f1 in findings1:
            if any(kw in f1.description for kw in keywords1):
                for f2 in findings2:
                    if any(kw in f2.description for kw in keywords2):
                        conflicts.append(Conflict(
                            id=str(uuid.uuid4()),
                            finding_ids=[f1.id, f2.id],
                            conflict_type=pattern_name,
                            description=pattern['description'],
                            severity=pattern['severity'],
                            resolution_suggestion=f"需要{agent1}和{agent2}专家协商确定",
                            agent1=agent1,
                            agent2=agent2,
                            finding1=f1.to_dict(),
                            finding2=f2.to_dict(),
                            resolution_needed=True,
                            resolved=False
                        ))
        
        return conflicts
    
    def calculate_severity_score(self, severity: str) -> float:
        """计算严重性分数"""
        severity_map = {
            "low": 0.25,
            "medium": 0.5,
            "high": 0.75,
            "critical": 1.0
        }
        return severity_map.get(severity, 0.5)
