"""
税务计算与合规工具集

整合税务计算、税务合规检查和风险评估功能
提供全面的企业税务管理能力
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from .base import ToolBase

logger = logging.getLogger(__name__)


class TaxCalculationTool(ToolBase):
    """
    税务计算工具
    
    提供多种税务计算功能：
    - 增值税
    - 企业所得税
    - 个人所得税
    """
    
    def __init__(self):
        super().__init__(
            name="tax_calculator",
            description="计算企业税务金额，包括增值税、企业所得税、个人所得税等",
            timeout=30,
            tags=["税务", "计算", "财务"]
        )
        
        self.vat_rates = {
            "general": 0.13,
            "transport": 0.09,
            "service": 0.06,
            "small": 0.03
        }
        
        self.corporate_tax_rates = {
            "standard": 0.25,
            "small": 0.20,
            "high_tech": 0.15
        }
    
    async def execute(
        self,
        tax_type: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行税务计算
        
        Args:
            tax_type: 税种类型 (vat/corporate_income_tax/individual_income_tax)
            **kwargs: 根据税种类型传入相应参数
            
        Returns:
            税务计算结果
        """
        try:
            if tax_type == "vat":
                return self._calculate_vat(
                    kwargs.get("sales_amount", 0),
                    kwargs.get("vat_rate", 0.13),
                    kwargs.get("input_vat", 0),
                    kwargs.get("tenant_id")
                )
            elif tax_type == "corporate_income_tax":
                return self._calculate_corporate_income_tax(
                    kwargs.get("taxable_income", 0),
                    kwargs.get("tax_rate", 0.25),
                    kwargs.get("tenant_id")
                )
            elif tax_type == "individual_income_tax":
                return self._calculate_individual_income_tax(
                    kwargs.get("monthly_salary", 0),
                    kwargs.get("special_deductions", 0),
                    kwargs.get("tenant_id")
                )
            else:
                return {
                    "error": f"不支持的税种类型: {tax_type}",
                    "supported_types": ["vat", "corporate_income_tax", "individual_income_tax"]
                }
        except Exception as e:
            logger.error(f"税务计算失败: {str(e)}", exc_info=True)
            return {
                "error": f"税务计算失败: {str(e)}",
                "tax_type": tax_type
            }
    
    def _calculate_vat(
        self,
        sales_amount: float,
        vat_rate: float,
        input_vat: float = 0,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """计算增值税"""
        try:
            output_vat = sales_amount * vat_rate
            payable_vat = output_vat - input_vat
            
            risk_issues = []
            
            if vat_rate not in [0.13, 0.09, 0.06, 0.03]:
                risk_issues.append("使用的增值税税率可能不正确")
            
            if input_vat > output_vat * 0.8:
                risk_issues.append("进项税额占比过高，需要核查")
            
            if payable_vat < 0:
                risk_issues.append("存在留抵税额，需要关注资金流")
            
            return {
                "tax_type": "vat",
                "tenant_id": tenant_id,
                "sales_amount": sales_amount,
                "vat_rate": vat_rate,
                "output_vat": round(output_vat, 2),
                "input_vat": input_vat,
                "payable_vat": round(payable_vat, 2),
                "risk_issues": risk_issues,
                "recommendations": self._get_vat_recommendations(risk_issues),
                "calculation_date": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "tax_type": "vat",
                "tenant_id": tenant_id,
                "error": f"增值税计算失败: {str(e)}",
                "calculation_date": datetime.now().isoformat()
            }
    
    def _calculate_corporate_income_tax(
        self,
        taxable_income: float,
        tax_rate: float = 0.25,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """计算企业所得税"""
        try:
            tax_payable = taxable_income * tax_rate
            
            risk_issues = []
            
            if tax_rate not in [0.25, 0.20, 0.15]:
                risk_issues.append("企业所得税税率可能不正确")
            
            if taxable_income < 0:
                risk_issues.append("应纳税所得额为负，可能存在亏损")
            
            if taxable_income <= 1000000 and tax_rate > 0.20:
                risk_issues.append("可能符合小型微利企业条件，建议核查优惠政策")
            
            return {
                "tax_type": "corporate_income_tax",
                "tenant_id": tenant_id,
                "taxable_income": taxable_income,
                "tax_rate": tax_rate,
                "tax_payable": round(tax_payable, 2),
                "effective_rate": round(tax_payable / taxable_income * 100, 2) if taxable_income > 0 else 0,
                "risk_issues": risk_issues,
                "recommendations": self._get_corporate_tax_recommendations(risk_issues, taxable_income),
                "calculation_date": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "tax_type": "corporate_income_tax",
                "tenant_id": tenant_id,
                "error": f"企业所得税计算失败: {str(e)}",
                "calculation_date": datetime.now().isoformat()
            }
    
    def _calculate_individual_income_tax(
        self,
        monthly_salary: float,
        special_deductions: float = 0,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """计算个人所得税"""
        try:
            basic_deduction = 5000
            taxable_income = monthly_salary - basic_deduction - special_deductions
            
            if taxable_income <= 0:
                return {
                    "tax_type": "individual_income_tax",
                    "tenant_id": tenant_id,
                    "monthly_salary": monthly_salary,
                    "taxable_income": 0,
                    "tax_payable": 0,
                    "after_tax_income": monthly_salary,
                    "effective_rate": 0,
                    "calculation_date": datetime.now().isoformat()
                }
            
            tax_payable = self._calculate_progressive_tax(taxable_income)
            after_tax_income = monthly_salary - tax_payable
            effective_rate = (tax_payable / monthly_salary * 100) if monthly_salary > 0 else 0
            
            risk_issues = []
            if special_deductions > monthly_salary * 0.3:
                risk_issues.append("专项附加扣除金额较高，需要核查凭证")
            
            return {
                "tax_type": "individual_income_tax",
                "tenant_id": tenant_id,
                "monthly_salary": monthly_salary,
                "basic_deduction": basic_deduction,
                "special_deductions": special_deductions,
                "taxable_income": round(taxable_income, 2),
                "tax_payable": round(tax_payable, 2),
                "after_tax_income": round(after_tax_income, 2),
                "effective_rate": round(effective_rate, 2),
                "risk_issues": risk_issues,
                "calculation_date": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "tax_type": "individual_income_tax",
                "tenant_id": tenant_id,
                "error": f"个人所得税计算失败: {str(e)}",
                "calculation_date": datetime.now().isoformat()
            }
    
    def _calculate_progressive_tax(self, taxable_income: float) -> float:
        """计算超额累进税率"""
        tax_payable = 0
        
        if taxable_income > 0:
            tax_payable += min(taxable_income, 3000) * 0.03
        
        if taxable_income > 3000:
            tax_payable += min(taxable_income - 3000, 9000) * 0.10
        
        if taxable_income > 12000:
            tax_payable += min(taxable_income - 12000, 13000) * 0.20
        
        if taxable_income > 25000:
            tax_payable += (taxable_income - 25000) * 0.25
        
        return tax_payable
    
    def _get_vat_recommendations(self, risk_issues: List[str]) -> List[str]:
        """获取增值税建议"""
        recommendations = []
        
        if not risk_issues:
            recommendations.append("增值税计算正常，请按时申报缴纳")
            return recommendations
        
        if any("税率" in issue for issue in risk_issues):
            recommendations.append("请核实增值税税率的适用，确保符合税法规定")
        if any("进项税额" in issue for issue in risk_issues):
            recommendations.append("请关注进项税额抵扣的合规性，确保取得合法发票")
        if any("留抵" in issue for issue in risk_issues):
            recommendations.append("请关注增值税留抵情况，合理安排资金流")
        
        return recommendations
    
    def _get_corporate_tax_recommendations(self, risk_issues: List[str], taxable_income: float) -> List[str]:
        """获取企业所得税建议"""
        recommendations = []
        
        if not risk_issues:
            recommendations.append("企业所得税计算正常，请按时申报缴纳")
            return recommendations
        
        if any("税率" in issue for issue in risk_issues):
            recommendations.append("请确认企业所得税税率适用，考虑优惠政策")
        if any("亏损" in issue for issue in risk_issues):
            recommendations.append("亏损可以在未来年度弥补，请关注盈利情况")
        if any("小型微利" in issue for issue in risk_issues):
            recommendations.append("建议核查是否满足小型微利企业条件，可享受更低税率")
        
        return recommendations


class TaxComplianceChecker(ToolBase):
    """
    税务合规检查工具
    
    提供税务合规性检查和风险评估
    """
    
    def __init__(self):
        super().__init__(
            name="tax_compliance_checker",
            description="检查企业税务合规性，评估税务风险并提供改进建议",
            timeout=30,
            tags=["税务", "合规", "检查", "风险"]
        )
    
    async def execute(
        self,
        tax_data: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        执行税务合规检查
        
        Args:
            tax_data: 税务数据字典
            tenant_id: 租户ID
            
        Returns:
            合规检查结果
        """
        try:
            compliance_issues = []
            compliance_score = 100
            
            if "vat" in tax_data:
                vat_data = tax_data["vat"]
                vat_issues = self._check_vat_compliance(vat_data, tenant_id)
                compliance_issues.extend(vat_issues["issues"])
                compliance_score = self._adjust_score(compliance_score, vat_issues["severity"])
            
            if "corporate_tax" in tax_data:
                corp_data = tax_data["corporate_tax"]
                corp_issues = self._check_corporate_tax_compliance(corp_data, tenant_id)
                compliance_issues.extend(corp_issues["issues"])
                compliance_score = self._adjust_score(compliance_score, corp_issues["severity"])
            
            if "individual_tax" in tax_data:
                ind_data = tax_data["individual_tax"]
                ind_issues = self._check_individual_tax_compliance(ind_data, tenant_id)
                compliance_issues.extend(ind_issues["issues"])
                compliance_score = self._adjust_score(compliance_score, ind_issues["severity"])
            
            compliance_level = self._get_compliance_level(compliance_score)
            
            return {
                "tenant_id": tenant_id,
                "compliance_score": compliance_score,
                "compliance_level": compliance_level,
                "total_issues": len(compliance_issues),
                "issues": compliance_issues,
                "recommendations": self._generate_compliance_recommendations(compliance_issues),
                "check_date": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"税务合规检查失败: {str(e)}", exc_info=True)
            return {
                "tenant_id": tenant_id,
                "error": f"税务合规检查失败: {str(e)}",
                "compliance_score": 0,
                "check_date": datetime.now().isoformat()
            }
    
    def _check_vat_compliance(self, vat_data: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """检查增值税合规性"""
        issues = []
        max_severity = "low"
        
        if vat_data.get("rate", 0) not in [0.13, 0.09, 0.06, 0.03]:
            issues.append({
                "type": "增值税税率",
                "issue": "使用了非标准增值税税率",
                "severity": "high",
                "legal_basis": "《增值税暂行条例》"
            })
            max_severity = "high"
        
        output_vat = vat_data.get("output_vat", 0)
        input_vat = vat_data.get("input_vat", 0)
        if input_vat > output_vat:
            issues.append({
                "type": "增值税进项",
                "issue": "进项税额超过销项税额，存在留抵",
                "severity": "medium",
                "legal_basis": "《增值税暂行条例》"
            })
            if max_severity != "high":
                max_severity = "medium"
        
        return {"issues": issues, "severity": max_severity}
    
    def _check_corporate_tax_compliance(self, corp_data: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """检查企业所得税合规性"""
        issues = []
        max_severity = "low"
        
        if corp_data.get("rate", 0) not in [0.25, 0.20, 0.15]:
            issues.append({
                "type": "企业所得税税率",
                "issue": "使用了非标准企业所得税税率",
                "severity": "high",
                "legal_basis": "《企业所得税法》"
            })
            max_severity = "high"
        
        return {"issues": issues, "severity": max_severity}
    
    def _check_individual_tax_compliance(self, ind_data: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """检查个人所得税合规性"""
        issues = []
        max_severity = "low"
        
        salary = ind_data.get("salary", 0)
        deductions = ind_data.get("special_deductions", 0)
        if deductions > salary * 0.5:
            issues.append({
                "type": "个人所得税扣除",
                "issue": "专项附加扣除金额过高",
                "severity": "medium",
                "legal_basis": "《个人所得税法》"
            })
            max_severity = "medium"
        
        return {"issues": issues, "severity": max_severity}
    
    def _adjust_score(self, current_score: int, severity: str) -> int:
        """根据严重程度调整分数"""
        if severity == "critical":
            return max(0, current_score - 25)
        elif severity == "high":
            return max(0, current_score - 20)
        elif severity == "medium":
            return max(0, current_score - 10)
        return current_score
    
    def _get_compliance_level(self, score: int) -> str:
        """确定合规等级"""
        if score >= 90:
            return "优秀"
        elif score >= 80:
            return "良好"
        elif score >= 70:
            return "一般"
        else:
            return "较差"
    
    def _generate_compliance_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """生成合规建议"""
        recommendations = []
        
        if not issues:
            recommendations.append("税务合规情况良好，请继续保持")
            return recommendations
        
        for issue in issues:
            if issue["type"] == "增值税税率":
                recommendations.append("请核实增值税税率的适用，确保符合税法规定")
            elif issue["type"] == "增值税进项":
                recommendations.append("请关注增值税进项税额抵扣的合规性")
            elif issue["type"] == "企业所得税税率":
                recommendations.append("请确认企业所得税税率适用，考虑优惠政策")
            elif issue["type"] == "个人所得税扣除":
                recommendations.append("请核查专项附加扣除的真实性和合规性")
        
        recommendations.append("建议定期进行税务自查，确保合规运营")
        
        return recommendations
