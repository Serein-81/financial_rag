"""
税务规则知识库配置
用于配置税务审核场景的规则、阈值和验证逻辑
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class TaxRuleCategory(str, Enum):
    """税务规则分类"""
    VAT = "vat"                          # 增值税
    CIT = "cit"                          # 企业所得税
    IIT = "iit"                          # 个人所得税
    STAMP_DUTY = "stamp_duty"            # 印花税
    CONSUMPTION_TAX = "consumption_tax"  # 消费税
    COMPLIANCE = "compliance"            # 合规性


class SeverityLevel(str, Enum):
    """严重等级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TaxRule:
    """税务规则定义"""
    rule_id: str
    category: TaxRuleCategory
    name: str
    description: str
    legal_basis: List[str]
    validation_logic: str
    severity: SeverityLevel
    keywords: List[str]
    remediation: str


class TaxRulesKnowledgeBase:
    """
    税务规则知识库
    
    包含：
    1. 税务规则定义
    2. 验证阈值配置
    3. 法律依据映射
    """
    
    def __init__(self):
        self.rules = self._initialize_rules()
        self.indicator_thresholds = self._initialize_thresholds()
    
    def _initialize_rules(self) -> List[TaxRule]:
        """初始化税务规则"""
        return [
            TaxRule(
                rule_id="VAT-001",
                category=TaxRuleCategory.VAT,
                name="进项税额不得为负",
                description="进项税额填报值不应为负数",
                legal_basis=[
                    "《增值税暂行条例》第四条",
                    "《增值税暂行条例实施细则》第十一条"
                ],
                validation_logic="input_tax >= 0",
                severity=SeverityLevel.HIGH,
                keywords=["进项税额", "负数", "不得为负"],
                remediation="检查进项税额填报是否正确，如有红字发票冲销需单独处理"
            ),
            TaxRule(
                rule_id="VAT-002",
                category=TaxRuleCategory.VAT,
                name="销项税额不得为负",
                description="销项税额填报值不应为负数",
                legal_basis=[
                    "《增值税暂行条例》第四条",
                    "《增值税暂行条例实施细则》第十一条"
                ],
                validation_logic="output_tax >= 0",
                severity=SeverityLevel.HIGH,
                keywords=["销项税额", "负数", "不得为负"],
                remediation="检查销项税额填报是否正确"
            ),
            TaxRule(
                rule_id="VAT-003",
                category=TaxRuleCategory.VAT,
                name="税率适用准确性",
                description="不同业务类型应适用正确税率",
                legal_basis=[
                    "《增值税暂行条例》第二条",
                    "《增值税税率和征收率表》"
                ],
                validation_logic="rate in [0.13, 0.09, 0.06, 0.05, 0.03, 0.00]",
                severity=SeverityLevel.MEDIUM,
                keywords=["税率", "13%", "9%", "6%", "适用"],
                remediation="核实业务类型和对应税率"
            ),
            TaxRule(
                rule_id="VAT-004",
                category=TaxRuleCategory.VAT,
                name="税额计算准确性",
                description="税额 = 销售额 × 税率",
                legal_basis=[
                    "《增值税暂行条例》第四条"
                ],
                validation_logic="abs(tax_amount - sales * rate) / tax_amount < 0.01",
                severity=SeverityLevel.HIGH,
                keywords=["税额计算", "销售额", "税率"],
                remediation="重新计算税额"
            ),
            TaxRule(
                rule_id="CIT-001",
                category=TaxRuleCategory.CIT,
                name="收入扣除勾稽",
                description="应税收入 = 总收入 - 总扣除",
                legal_basis=[
                    "《企业所得税法》第五条"
                ],
                validation_logic="taxable_income = total_income - total_deductions",
                severity=SeverityLevel.HIGH,
                keywords=["收入", "扣除", "勾稽"],
                remediation="核对收入和扣除项目"
            ),
            TaxRule(
                rule_id="CIT-002",
                category=TaxRuleCategory.CIT,
                name="税前扣除标准",
                description="各项费用扣除需符合税法规定标准",
                legal_basis=[
                    "《企业所得税法》第八条",
                    "《企业所得税法实施条例》第二十七条"
                ],
                validation_logic="expense <= allowable_limit",
                severity=SeverityLevel.MEDIUM,
                keywords=["税前扣除", "费用", "标准"],
                remediation="核实扣除项目是否符合标准"
            ),
            TaxRule(
                rule_id="CIT-003",
                category=TaxRuleCategory.CIT,
                name="企业所得税计算准确性",
                description="企业所得税 = 应纳税所得额 × 税率",
                legal_basis=[
                    "《企业所得税法》第四条"
                ],
                validation_logic="abs(cit_amount - taxable_income * rate) / cit_amount < 0.01",
                severity=SeverityLevel.HIGH,
                keywords=["企业所得税", "计算", "应纳税"],
                remediation="重新计算企业所得税"
            ),
            TaxRule(
                rule_id="COM-001",
                category=TaxRuleCategory.COMPLIANCE,
                name="发票与申报一致性",
                description="发票开具金额与申报金额应基本一致",
                legal_basis=[
                    "《发票管理办法》",
                    "《税务登记管理办法》"
                ],
                validation_logic="abs(invoice_amount - declared_amount) / invoice_amount < 0.05",
                severity=SeverityLevel.MEDIUM,
                keywords=["发票", "申报", "一致"],
                remediation="核对发票与申报数据"
            ),
        ]
    
    def _initialize_thresholds(self) -> Dict[str, Tuple[float, float]]:
        """初始化指标阈值"""
        return {
            "tax_load_rate": (0.03, 0.08),
            "gross_margin": (0.15, 0.50),
            "input_tax_ratio": (0.60, 1.20),
            "output_tax_ratio": (0.80, 1.50),
            "vat_net_rate": (-0.05, 0.03),
        }
    
    def get_rules_by_category(self, category: TaxRuleCategory) -> List[TaxRule]:
        """按分类获取规则"""
        return [r for r in self.rules if r.category == category]
    
    def get_rules_by_severity(self, severity: SeverityLevel) -> List[TaxRule]:
        """按严重等级获取规则"""
        return [r for r in self.rules if r.severity == severity]
    
    def search_rules(self, query: str) -> List[TaxRule]:
        """搜索规则"""
        query_lower = query.lower()
        results = []
        
        for rule in self.rules:
            if query_lower in rule.name.lower():
                results.append(rule)
            elif query_lower in rule.description.lower():
                results.append(rule)
            elif any(query_lower in kw.lower() for kw in rule.keywords):
                results.append(rule)
        
        return results
    
    def get_rule_by_id(self, rule_id: str) -> TaxRule:
        """根据ID获取规则"""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    def get_legal_basis_for_category(self, category: TaxRuleCategory) -> List[str]:
        """获取某分类的所有法律依据"""
        legal_bases = set()
        for rule in self.rules:
            if rule.category == category:
                legal_bases.update(rule.legal_basis)
        return list(legal_bases)


tax_rules_kb = TaxRulesKnowledgeBase()
