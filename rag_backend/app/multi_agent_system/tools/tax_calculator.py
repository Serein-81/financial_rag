"""
税务计算工具
提供税务计算和合规检查功能
"""

from typing import Dict, Any, Optional, List
import re
from decimal import InvalidOperation
from datetime import datetime


class TaxCalculator:
    """税务计算工具"""
    
    def __init__(self):
        self.name = "tax_calculator"
        self.description = "计算税务指标和进行税务合规检查"
        
        # 税率配置
        self.vat_rates = {
            "general": 0.13,      # 一般货物
            "transport": 0.09,    # 交通运输
            "service": 0.06,      # 现代服务业
            "basic": 0.03         # 小规模纳税人
        }
        
        self.corporate_tax_rates = {
            "standard": 0.25,     # 标准税率
            "small": 0.20,        # 小型微利企业
            "high_tech": 0.15     # 高新技术企业
        }
    
    def calculate_vat(
        self,
        sales_amount: float,
        vat_rate: float,
        input_vat: float = 0,
        tenant_id: str = None
    ) -> Dict[str, Any]:
        """
        计算增值税
        
        Args:
            sales_amount: 销售额
            vat_rate: 增值税税率
            input_vat: 进项税额
            tenant_id: 租户ID
            
        Returns:
            增值税计算结果
        """
        try:
            # 计算销项税额
            output_vat = sales_amount * vat_rate
            
            # 计算应纳税额
            payable_vat = output_vat - input_vat
            
            # 风险评估
            risk_issues = []
            
            # 检查税率合理性
            if vat_rate not in [0.13, 0.09, 0.06, 0.03]:
                risk_issues.append("使用的增值税税率可能不正确")
            
            # 检查进项税额合理性
            if input_vat > output_vat * 0.8:
                risk_issues.append("进项税额占比过高，需要核查")
            
            # 检查应纳税额
            if payable_vat < 0:
                risk_issues.append("存在留抵税额，需要关注资金流")
            
            return {
                "tenant_id": tenant_id,  # 🔒 租户隔离
                "sales_amount": sales_amount,
                "vat_rate": vat_rate,
                "output_vat": round(output_vat, 2),
                "input_vat": input_vat,
                "payable_vat": round(payable_vat, 2),
                "risk_issues": risk_issues,
                "calculation_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "tenant_id": tenant_id,
                "error": f"增值税计算失败: {str(e)}",
                "sales_amount": sales_amount,
                "calculation_date": datetime.now().isoformat()
            }
    
    def calculate_corporate_income_tax(
        self,
        taxable_income: float,
        tax_rate: float = 0.25,
        tenant_id: str = None
    ) -> Dict[str, Any]:
        """
        计算企业所得税
        
        Args:
            taxable_income: 应纳税所得额
            tax_rate: 企业所得税税率
            tenant_id: 租户ID
            
        Returns:
            企业所得税计算结果
        """
        try:
            # 计算应纳税额
            tax_payable = taxable_income * tax_rate
            
            # 风险评估
            risk_issues = []
            
            # 检查税率合理性
            if tax_rate not in [0.25, 0.20, 0.15]:
                risk_issues.append("企业所得税税率可能不正确")
            
            # 检查应纳税所得额合理性
            if taxable_income < 0:
                risk_issues.append("应纳税所得额为负，可能存在亏损")
            
            # 小型微利企业优惠检查
            if taxable_income <= 1000000 and tax_rate > 0.20:
                risk_issues.append("可能符合小型微利企业条件，建议核查优惠政策")
            
            return {
                "tenant_id": tenant_id,  # 🔒 租户隔离
                "taxable_income": taxable_income,
                "tax_rate": tax_rate,
                "tax_payable": round(tax_payable, 2),
                "effective_rate": round(tax_payable / taxable_income * 100, 2) if taxable_income > 0 else 0,
                "risk_issues": risk_issues,
                "calculation_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "tenant_id": tenant_id,
                "error": f"企业所得税计算失败: {str(e)}",
                "taxable_income": taxable_income,
                "calculation_date": datetime.now().isoformat()
            }
    
    def calculate_individual_income_tax(
        self,
        monthly_salary: float,
        special_deductions: float = 0,
        tenant_id: str = None
    ) -> Dict[str, Any]:
        """
        计算个人所得税（工资薪金）
        
        Args:
            monthly_salary: 月工资
            special_deductions: 专项附加扣除
            tenant_id: 租户ID
            
        Returns:
            个人所得税计算结果
        """
        try:
            # 基本减除费用
            basic_deduction = 5000
            
            # 计算应纳税所得额
            taxable_income = monthly_salary - basic_deduction - special_deductions
            
            if taxable_income <= 0:
                return {
                    "tenant_id": tenant_id,
                    "monthly_salary": monthly_salary,
                    "taxable_income": 0,
                    "tax_payable": 0,
                    "after_tax_income": monthly_salary,
                    "effective_rate": 0,
                    "calculation_date": datetime.now().isoformat()
                }
            
            # 累进税率计算
            tax_payable = 0
            
            # 3%税率
            if taxable_income > 0:
                tax_3_percent = min(taxable_income, 3000) * 0.03
                tax_payable += tax_3_percent
            
            # 10%税率
            if taxable_income > 3000:
                tax_10_percent = min(taxable_income - 3000, 9000) * 0.10
                tax_payable += tax_10_percent
            
            # 20%税率
            if taxable_income > 12000:
                tax_20_percent = min(taxable_income - 12000, 13000) * 0.20
                tax_payable += tax_20_percent
            
            # 更高税率（简化处理）
            if taxable_income > 25000:
                tax_higher = (taxable_income - 25000) * 0.25
                tax_payable += tax_higher
            
            after_tax_income = monthly_salary - tax_payable
            effective_rate = (tax_payable / monthly_salary * 100) if monthly_salary > 0 else 0
            
            # 风险评估
            risk_issues = []
            if special_deductions > monthly_salary * 0.3:
                risk_issues.append("专项附加扣除金额较高，需要核查凭证")
            
            return {
                "tenant_id": tenant_id,  # 🔒 租户隔离
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
                "tenant_id": tenant_id,
                "error": f"个人所得税计算失败: {str(e)}",
                "monthly_salary": monthly_salary,
                "calculation_date": datetime.now().isoformat()
            }
    
    def check_tax_compliance(
        self,
        tax_data: Dict[str, Any],
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        税务合规检查
        
        Args:
            tax_data: 税务数据
            tenant_id: 租户ID
            
        Returns:
            合规检查结果
        """
        try:
            compliance_issues = []
            compliance_score = 100
            
            # 增值税合规检查
            if "vat" in tax_data:
                vat_data = tax_data["vat"]
                
                # 检查税率
                if vat_data.get("rate", 0) not in [0.13, 0.09, 0.06, 0.03]:
                    compliance_issues.append({
                        "type": "增值税税率",
                        "issue": "使用了非标准增值税税率",
                        "severity": "high"
                    })
                    compliance_score -= 20
                
                # 检查进项税额
                output_vat = vat_data.get("output_vat", 0)
                input_vat = vat_data.get("input_vat", 0)
                if input_vat > output_vat:
                    compliance_issues.append({
                        "type": "增值税进项",
                        "issue": "进项税额超过销项税额，存在留抵",
                        "severity": "medium"
                    })
                    compliance_score -= 10
            
            # 企业所得税合规检查
            if "corporate_tax" in tax_data:
                corp_data = tax_data["corporate_tax"]
                
                # 检查税率
                if corp_data.get("rate", 0) not in [0.25, 0.20, 0.15]:
                    compliance_issues.append({
                        "type": "企业所得税税率",
                        "issue": "使用了非标准企业所得税税率",
                        "severity": "high"
                    })
                    compliance_score -= 20
            
            # 个人所得税合规检查
            if "individual_tax" in tax_data:
                ind_data = tax_data["individual_tax"]
                
                # 检查专项扣除
                salary = ind_data.get("salary", 0)
                deductions = ind_data.get("special_deductions", 0)
                if deductions > salary * 0.5:
                    compliance_issues.append({
                        "type": "个人所得税扣除",
                        "issue": "专项附加扣除金额过高",
                        "severity": "medium"
                    })
                    compliance_score -= 15
            
            # 确定合规等级
            if compliance_score >= 90:
                compliance_level = "优秀"
            elif compliance_score >= 80:
                compliance_level = "良好"
            elif compliance_score >= 70:
                compliance_level = "一般"
            else:
                compliance_level = "较差"
            
            return {
                "tenant_id": tenant_id,  # 🔒 租户隔离
                "compliance_score": compliance_score,
                "compliance_level": compliance_level,
                "total_issues": len(compliance_issues),
                "issues": compliance_issues,
                "recommendations": self._generate_tax_recommendations(compliance_issues),
                "check_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "tenant_id": tenant_id,
                "error": f"税务合规检查失败: {str(e)}",
                "compliance_score": 0,
                "check_date": datetime.now().isoformat()
            }
    
    def _generate_tax_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """生成税务建议"""
        recommendations = []
        
        for issue in issues:
            if issue["type"] == "增值税税率":
                recommendations.append("请核实增值税税率的适用，确保符合税法规定")
            elif issue["type"] == "增值税进项":
                recommendations.append("请关注增值税留抵情况，合理安排资金流")
            elif issue["type"] == "企业所得税税率":
                recommendations.append("请确认企业所得税税率适用，考虑优惠政策")
            elif issue["type"] == "个人所得税扣除":
                recommendations.append("请核查专项附加扣除的真实性和合规性")
        
        if not recommendations:
            recommendations.append("税务合规情况良好，请继续保持")
        
        return recommendations
    
    def extract_tax_data(
        self,
        text: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        从文本中提取税务数据
        
        Args:
            text: 税务文档文本
            tenant_id: 租户ID
            
        Returns:
            提取的税务数据
        """
        try:
            extracted_data = {
                "vat_data": {
                    "sales_amount": self._extract_amount(text, ["销售额", "不含税销售额"]),
                    "output_vat": self._extract_amount(text, ["销项税额"]),
                    "input_vat": self._extract_amount(text, ["进项税额"]),
                    "payable_vat": self._extract_amount(text, ["应纳税额", "应缴增值税"])
                },
                "corporate_tax_data": {
                    "taxable_income": self._extract_amount(text, ["应纳税所得额"]),
                    "tax_payable": self._extract_amount(text, ["应纳所得税额"])
                },
                "tenant_id": tenant_id  # 🔒 租户隔离
            }
            
            return {
                "success": True,
                "data": extracted_data,
                "message": "税务数据提取完成"
            }
            
        except Exception as e:
            return {
                "success": False,
                "data": {},
                "message": f"税务数据提取失败: {str(e)}"
            }
    
    def _extract_amount(self, text: str, keywords: List[str]) -> Optional[float]:
        """从文本中提取金额"""
        for keyword in keywords:
            pattern = rf"{keyword}[：:\s]*([0-9,]+\.?[0-9]*)"
            match = re.search(pattern, text)
            if match:
                try:
                    amount_str = match.group(1).replace(",", "")
                    return float(amount_str)
                except (ValueError, InvalidOperation):
                    continue
        return None