"""
交易层：税务纯计算引擎

职责：
- 最终税务申报的纯数学计算
- 绝对无 AI 参与
- 纯粹的加、减、乘、除运算

架构原则：
- 当一切准备就绪，用户点击"税务提交"时
- 一个极其冷酷、没有任何 AI 参与的传统代码接口
- 把数据库里干干净净的数字捞出来，做加减乘除
- 完成最终的财务结算

复用组件：
- 无，纯新增
"""

import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class VATResult(BaseModel):
    """增值税计算结果"""
    taxable_amount: float = Field(description="不含税金额")
    tax_rate: float = Field(description="税率")
    tax_amount: float = Field(description="税额")
    total_amount: float = Field(description="价税合计")
    
    model_config = {"json_schema_extra": {"example": {"taxable_amount": 1000000, "tax_rate": 0.13, "tax_amount": 130000, "total_amount": 1130000}}}


class IncomeTaxResult(BaseModel):
    """企业所得税计算结果"""
    revenue: float = Field(description="营业收入")
    deductible_expenses: float = Field(description="可扣除费用")
    taxable_income: float = Field(description="应纳税所得额")
    tax_rate: float = Field(description="税率")
    tax_amount: float = Field(description="税额")
    deduction_amount: float = Field(default=0, description="优惠减免金额")
    
    model_config = {"json_schema_extra": {"example": {"revenue": 5000000, "deductible_expenses": 3000000, "taxable_income": 2000000, "tax_rate": 0.25, "tax_amount": 500000, "deduction_amount": 0}}}


class TaxSubmission(BaseModel):
    """最终税务申报数据"""
    submission_id: str = Field(description="申报ID")
    submission_date: str = Field(description="申报日期")
    
    vat: Optional[VATResult] = Field(None, description="增值税")
    income_tax: Optional[IncomeTaxResult] = Field(None, description="企业所得税")
    
    total_tax_amount: float = Field(description="总税额")
    tax_period: str = Field(description="税务期间")
    
    verified_data: Dict[str, Any] = Field(default_factory=dict, description="已验证的发票数据")
    risk_level: str = Field(description="风险等级")
    human_review_approved: bool = Field(default=False, description="人工审核是否批准")
    
    model_config = {"json_schema_extra": {"example": {"submission_id": "sub_123", "submission_date": "2024-03-25", "total_tax_amount": 630000, "tax_period": "2024-Q1", "risk_level": "low", "human_review_approved": True}}}


class TaxCalculationEngine:
    """
    纯计算引擎（无 AI）
    
    用于最终税务申报，当所有数据都经过验证后
    执行纯粹的数学计算
    """
    
    VAT_RATES = {
        "general": 0.13,
        "small_scale": 0.03,
        "reduced": 0.09
    }
    
    INCOME_TAX_RATES = {
        "standard": 0.25,
        "small_profit": 0.20
    }
    
    @staticmethod
    def calculate_vat(
        taxable_amount: float,
        tax_rate: float = 0.13,
        deductions: List[float] = None
    ) -> VATResult:
        """
        增值税计算（纯数学）
        
        Args:
            taxable_amount: 不含税金额
            tax_rate: 税率（默认 13%）
            deductions: 抵扣项列表（可选）
            
        Returns:
            VATResult: 增值税计算结果
        """
        if taxable_amount < 0:
            raise ValueError("不含税金额不能为负数")
        
        tax_amount = taxable_amount * tax_rate
        
        if deductions:
            total_deduction = sum(d for d in deductions if d > 0)
            tax_amount = max(0, tax_amount - total_deduction)
        
        total_amount = taxable_amount + tax_amount
        
        return VATResult(
            taxable_amount=round(taxable_amount, 2),
            tax_rate=tax_rate,
            tax_amount=round(tax_amount, 2),
            total_amount=round(total_amount, 2)
        )
    
    @staticmethod
    def calculate_vat_from_total(total_amount: float, tax_rate: float = 0.13) -> VATResult:
        """
        从价税合计计算增值税（纯数学）
        
        Args:
            total_amount: 价税合计
            tax_rate: 税率（默认 13%）
            
        Returns:
            VATResult: 增值税计算结果
        """
        if total_amount < 0:
            raise ValueError("价税合计不能为负数")
        
        taxable_amount = total_amount / (1 + tax_rate)
        tax_amount = total_amount - taxable_amount
        
        return VATResult(
            taxable_amount=round(taxable_amount, 2),
            tax_rate=tax_rate,
            tax_amount=round(tax_amount, 2),
            total_amount=round(total_amount, 2)
        )
    
    @staticmethod
    def calculate_income_tax(
        revenue: float,
        deductible_expenses: float,
        tax_rate: float = 0.25,
        small_profit_discount: float = 0.0
    ) -> IncomeTaxResult:
        """
        企业所得税计算（纯数学）
        
        Args:
            revenue: 营业收入
            deductible_expenses: 可扣除费用
            tax_rate: 税率（默认 25%）
            small_profit_discount: 小型微利企业优惠（应纳税所得额×25%，可选）
            
        Returns:
            IncomeTaxResult: 企业所得税计算结果
        """
        if revenue < 0:
            raise ValueError("营业收入不能为负数")
        if deductible_expenses < 0:
            raise ValueError("可扣除费用不能为负数")
        
        taxable_income = max(0, revenue - deductible_expenses)
        tax_amount = taxable_income * tax_rate
        
        deduction_amount = 0.0
        if small_profit_discount > 0:
            deduction_amount = taxable_income * small_profit_discount
            tax_amount = tax_amount - deduction_amount
        
        tax_amount = max(0, tax_amount)
        
        return IncomeTaxResult(
            revenue=round(revenue, 2),
            deductible_expenses=round(deductible_expenses, 2),
            taxable_income=round(taxable_income, 2),
            tax_rate=tax_rate,
            tax_amount=round(tax_amount, 2),
            deduction_amount=round(deduction_amount, 2)
        )
    
    @staticmethod
    def calculate_total_tax(
        vat_amount: float = 0,
        income_tax_amount: float = 0,
        personal_tax_amount: float = 0,
        consumption_tax_amount: float = 0,
        other_taxes: Dict[str, float] = None
    ) -> float:
        """
        计算总税额（纯数学）
        
        Args:
            vat_amount: 增值税
            income_tax_amount: 企业所得税
            personal_tax_amount: 个人所得税
            consumption_tax_amount: 消费税
            other_taxes: 其他税种字典
            
        Returns:
            float: 总税额
        """
        total = vat_amount + income_tax_amount + personal_tax_amount + consumption_tax_amount
        
        if other_taxes:
            total += sum(v for v in other_taxes.values() if v and v > 0)
        
        return round(total, 2)
    
    @staticmethod
    def calculate_tax_burden_rate(
        total_tax: float,
        total_revenue: float
    ) -> float:
        """
        计算税负率（纯数学）
        
        Args:
            total_tax: 总税额
            total_revenue: 总收入
            
        Returns:
            float: 税负率（0-1）
        """
        if total_revenue <= 0:
            return 0.0
        
        return round(total_tax / total_revenue, 4)
    
    @staticmethod
    def build_submission(
        report_id: str,
        verified_data: Dict[str, Any],
        risk_level: str,
        human_review_approved: bool
    ) -> TaxSubmission:
        """
        构建税务申报数据（无 AI）
        
        当人工审核通过后，从已验证的发票数据构建申报数据
        
        Args:
            report_id: 报告ID
            verified_data: 已验证的发票数据
            risk_level: 风险等级
            human_review_approved: 人工审核是否批准
            
        Returns:
            TaxSubmission: 税务申报数据
        """
        logger.info(f"📊 [交易层] 构建税务申报数据...")
        logger.info(f"   - 报告ID: {report_id}")
        logger.info(f"   - 风险等级: {risk_level}")
        logger.info(f"   - 人工审核批准: {human_review_approved}")
        
        vat_result = None
        income_tax_result = None
        
        if "vat" in verified_data:
            vat_data = verified_data["vat"]
            vat_result = TaxCalculationEngine.calculate_vat(
                taxable_amount=vat_data.get("taxable_amount", 0),
                tax_rate=vat_data.get("tax_rate", 0.13),
                deductions=vat_data.get("deductions", [])
            )
        
        if "income_tax" in verified_data:
            it_data = verified_data["income_tax"]
            income_tax_result = TaxCalculationEngine.calculate_income_tax(
                revenue=it_data.get("revenue", 0),
                deductible_expenses=it_data.get("deductible_expenses", 0),
                tax_rate=it_data.get("tax_rate", 0.25),
                small_profit_discount=it_data.get("small_profit_discount", 0)
            )
        
        total_tax = TaxCalculationEngine.calculate_total_tax(
            vat_amount=vat_result.tax_amount if vat_result else 0,
            income_tax_amount=income_tax_result.tax_amount if income_tax_result else 0
        )
        
        submission = TaxSubmission(
            submission_id=f"sub_{report_id[:8]}",
            submission_date=datetime.now().strftime("%Y-%m-%d"),
            vat=vat_result,
            income_tax=income_tax_result,
            total_tax_amount=total_tax,
            tax_period=verified_data.get("tax_period", datetime.now().strftime("%Y-%m")),
            verified_data=verified_data,
            risk_level=risk_level,
            human_review_approved=human_review_approved
        )
        
        logger.info(f"✅ [交易层] 税务申报数据构建完成")
        logger.info(f"   - 总税额: ¥{total_tax:,.2f}")
        
        return submission
    
    @staticmethod
    def validate_submission_data(verified_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证申报数据（纯数学）
        
        检查数据是否符合申报要求
        
        Args:
            verified_data: 已验证的发票数据
            
        Returns:
            Dict: 验证结果 {"valid": bool, "errors": List[str], "warnings": List[str]}
        """
        errors = []
        warnings = []
        
        if not verified_data:
            errors.append("申报数据为空")
            return {"valid": False, "errors": errors, "warnings": warnings}
        
        if "amount" in verified_data:
            amount = verified_data["amount"]
            if amount < 0:
                errors.append("金额不能为负数")
            elif amount == 0:
                warnings.append("金额为零，请确认")
        
        if "tax_amount" in verified_data:
            tax_amount = verified_data["tax_amount"]
            if tax_amount < 0:
                errors.append("税额不能为负数")
        
        if "tax_rate" in verified_data:
            tax_rate = verified_data["tax_rate"]
            if tax_rate < 0 or tax_rate > 1:
                errors.append("税率必须在 0-1 之间")
        
        expected_amount = verified_data.get("amount", 0)
        expected_tax = expected_amount * verified_data.get("tax_rate", 0)
        actual_tax = verified_data.get("tax_amount", 0)
        
        if expected_tax > 0 and abs(expected_tax - actual_tax) > 0.01:
            warnings.append(f"税额计算可能不准确，预期: {expected_tax:.2f}，实际: {actual_tax:.2f}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    @staticmethod
    def generate_submission_report(submission: TaxSubmission) -> str:
        """
        生成申报报告（纯格式化，无 AI）
        
        Args:
            submission: 税务申报数据
            
        Returns:
            str: 格式化的申报报告
        """
        lines = [
            "=" * 50,
            "           税务申报报告",
            "=" * 50,
            "",
            f"申报ID: {submission.submission_id}",
            f"申报日期: {submission.submission_date}",
            f"税务期间: {submission.tax_period}",
            "",
            "-" * 50,
            "           税额明细",
            "-" * 50,
        ]
        
        if submission.vat:
            lines.append("")
            lines.append("【增值税】")
            lines.append(f"  不含税金额: ¥{submission.vat.taxable_amount:,.2f}")
            lines.append(f"  税率: {submission.vat.tax_rate * 100:.1f}%")
            lines.append(f"  税额: ¥{submission.vat.tax_amount:,.2f}")
            lines.append(f"  价税合计: ¥{submission.vat.total_amount:,.2f}")
        
        if submission.income_tax:
            lines.append("")
            lines.append("【企业所得税】")
            lines.append(f"  营业收入: ¥{submission.income_tax.revenue:,.2f}")
            lines.append(f"  可扣除费用: ¥{submission.income_tax.deductible_expenses:,.2f}")
            lines.append(f"  应纳税所得额: ¥{submission.income_tax.taxable_income:,.2f}")
            lines.append(f"  税率: {submission.income_tax.tax_rate * 100:.1f}%")
            lines.append(f"  税额: ¥{submission.income_tax.tax_amount:,.2f}")
            if submission.income_tax.deduction_amount > 0:
                lines.append(f"  优惠减免: ¥{submission.income_tax.deduction_amount:,.2f}")
        
        lines.append("")
        lines.append("-" * 50)
        lines.append(f"【总税额】: ¥{submission.total_tax_amount:,.2f}")
        lines.append("-" * 50)
        lines.append("")
        lines.append(f"风险等级: {submission.risk_level.upper()}")
        lines.append(f"人工审核: {'已批准' if submission.human_review_approved else '未审核'}")
        lines.append("")
        lines.append("=" * 50)
        
        return "\n".join(lines)