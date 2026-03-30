"""
税务计算工具
"""

import logging
from typing import Any, Dict, Optional
from decimal import Decimal, ROUND_HALF_UP

from app.tools.base import ToolBase, registry

logger = logging.getLogger(__name__)


class VATCalculatorTool(ToolBase):
    """增值税计算工具"""

    def __init__(self):
        super().__init__(
            name="calculate_tax_vat",
            description="计算增值税（Value Added Tax）。根据销售额、进项税额、增值税率计算应纳税额。",
            timeout=30
        )

    async def execute(
        self,
        sales_amount: float,
        vat_rate: float = 0.13,
        input_vat: float = 0.0,
        tax_rate: Optional[float] = None,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        计算增值税

        Args:
            sales_amount: 销售额（含税）
            vat_rate: 增值税率，默认 13%
            input_vat: 进项税额
            tax_rate: 兼容旧参数，会覆盖 vat_rate
            tenant_id: 租户ID（用于审计）

        Returns:
            包含税额计算结果的字典
        """
        effective_rate = tax_rate if tax_rate is not None else vat_rate

        tax_amount = sales_amount * effective_rate
        output_vat = tax_amount
        net_vat = output_vat - input_vat

        tax_amount_decimal = Decimal(str(tax_amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        net_vat_decimal = Decimal(str(net_vat)).quantize(Decimal("0.01"), ROUND_HALF_UP)

        risk_level = self._assess_risk(net_vat, sales_amount)

        return {
            "sales_amount": round(sales_amount, 2),
            "vat_rate": effective_rate,
            "tax_amount": float(tax_amount_decimal),
            "output_vat": float(tax_amount_decimal),
            "input_vat": float(input_vat),
            "net_vat_payable": float(net_vat_decimal),
            "risk_level": risk_level,
            "tenant_id": tenant_id
        }

    def _assess_risk(self, net_vat: float, sales_amount: float) -> str:
        """评估税务风险"""
        if net_vat < 0:
            return "high"
        ratio = abs(net_vat) / sales_amount if sales_amount > 0 else 0
        if ratio > 0.2:
            return "medium"
        return "low"


class CorporateIncomeTaxTool(ToolBase):
    """企业所得税计算工具"""

    def __init__(self):
        super().__init__(
            name="calculate_corporate_tax",
            description="计算企业所得税（Corporate Income Tax）。根据应纳税所得额和税率计算企业所得税。",
            timeout=30
        )

    async def execute(
        self,
        taxable_income: float,
        tax_rate: float = 0.25,
        small_business: bool = False,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        计算企业所得税

        Args:
            taxable_income: 应纳税所得额
            tax_rate: 企业所得税税率，默认 25%
            small_business: 是否为小型微利企业
            tenant_id: 租户ID

        Returns:
            包含税额计算结果的字典
        """
        if taxable_income <= 0:
            return {
                "taxable_income": taxable_income,
                "tax_rate": tax_rate,
                "tax_amount": 0.0,
                "effective_rate": 0.0,
                "is_small_business": small_business,
                "discount": 0.0,
                "final_tax": 0.0,
                "risk_level": "low",
                "tenant_id": tenant_id
            }

        effective_rate = tax_rate
        discount = 0.0

        if small_business:
            if taxable_income <= 1000000:
                effective_rate = 0.05
                discount = tax_rate - 0.05
            elif taxable_income <= 3000000:
                effective_rate = 0.05
                discount = tax_rate - 0.05
            else:
                effective_rate = tax_rate

        tax_amount = taxable_income * tax_rate
        final_tax = taxable_income * effective_rate

        tax_amount_decimal = Decimal(str(tax_amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        final_tax_decimal = Decimal(str(final_tax)).quantize(Decimal("0.01"), ROUND_HALF_UP)

        return {
            "taxable_income": round(taxable_income, 2),
            "original_tax_rate": tax_rate,
            "effective_rate": effective_rate,
            "original_tax_amount": float(tax_amount_decimal),
            "discount": float(discount),
            "final_tax": float(final_tax_decimal),
            "is_small_business": small_business,
            "risk_level": "low",
            "tenant_id": tenant_id
        }


class PersonalIncomeTaxTool(ToolBase):
    """个人所得税计算工具"""

    def __init__(self):
        super().__init__(
            name="calculate_personal_tax",
            description="计算个人所得税（Personal Income Tax）。根据月工资薪金和专项附加扣除计算个税。",
            timeout=30
        )

    async def execute(
        self,
        monthly_salary: float,
        special_deductions: float = 0.0,
        other_income: float = 0.0,
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        计算个人所得税

        Args:
            monthly_salary: 月工资薪金
            special_deductions: 专项附加扣除（如子女教育、住房贷款等）
            other_income: 其他综合所得
            tenant_id: 租户ID

        Returns:
            包含税额计算结果的字典
        """
        threshold = 5000
        social_insurance_rate = 0.105

        insurance_deduction = monthly_salary * social_insurance_rate

        tax_free_threshold = threshold
        total_deductions = insurance_deduction + special_deductions + tax_free_threshold

        taxable_income = max(0, monthly_salary + other_income - total_deductions)

        tax_amount = self._calculate_progressive_tax(taxable_income)

        after_tax_income = monthly_salary - insurance_deduction - tax_amount

        return {
            "gross_salary": round(monthly_salary, 2),
            "social_insurance": round(insurance_deduction, 2),
            "special_deductions": round(special_deductions, 2),
            "tax_free_threshold": tax_free_threshold,
            "total_deductions": round(total_deductions, 2),
            "taxable_income": round(taxable_income, 2),
            "tax_amount": round(tax_amount, 2),
            "after_tax_income": round(after_tax_income, 2),
            "effective_tax_rate": round(tax_amount / monthly_salary * 100, 2) if monthly_salary > 0 else 0,
            "risk_level": "low",
            "tenant_id": tenant_id
        }

    def _calculate_progressive_tax(self, monthly_taxable: float) -> float:
        """计算超额累进税率"""
        if monthly_taxable <= 0:
            return 0.0

        brackets = [
            (3000, 0.03, 0),
            (12000, 0.10, 210),
            (25000, 0.20, 1410),
            (35000, 0.25, 2660),
            (55000, 0.30, 4410),
            (80000, 0.35, 7160),
            (float('inf'), 0.45, 15160)
        ]

        for limit, rate, deduction in brackets:
            if monthly_taxable <= limit:
                return monthly_taxable * rate - deduction

        return 0.0


def register_tax_tools():
    """注册所有税务工具"""
    registry.register(VATCalculatorTool())
    registry.register(CorporateIncomeTaxTool())
    registry.register(PersonalIncomeTaxTool())


tax_tools = [VATCalculatorTool(), CorporateIncomeTaxTool(), PersonalIncomeTaxTool()]
