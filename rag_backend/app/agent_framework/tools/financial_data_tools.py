"""
财务数据查询工具
用于在Agent中查询用户的财务数据和税务信息
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.agent_framework.tools.base import ToolBase, registry

logger = logging.getLogger(__name__)


class FinancialDataQueryTool(ToolBase):
    """财务数据查询工具"""

    def __init__(self):
        super().__init__(
            name="query_user_financial_data",
            description="查询用户的财务数据和税务信息。根据指定年度查询用户的收入、支出、税务数据等。",
            timeout=30
        )

    async def execute(
        self,
        user_id: str,
        tenant_id: str,
        fiscal_year: Optional[int] = None,
        include_vat: bool = True,
        include_corporate_tax: bool = True,
        include_personal_tax: bool = False
    ) -> Dict[str, Any]:
        """
        查询用户财务数据

        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            fiscal_year: 财务年度，默认今年
            include_vat: 是否包含增值税
            include_corporate_tax: 是否包含企业所得税
            include_personal_tax: 是否包含个人所得税

        Returns:
            包含财务数据和税务信息的字典
        """
        from app.db import AsyncSessionLocal
        from sqlalchemy import select, and_
        from sqlalchemy.exc import ProgrammingError
        from app.models.user_financial_data import UserFinancialData
        import uuid

        try:
            async with AsyncSessionLocal() as db:
                query_years = []
                if fiscal_year:
                    query_years.append(fiscal_year)
                    query_years.append(fiscal_year - 1)
                else:
                    current_year = datetime.now().year
                    for y in range(current_year, current_year - 5, -1):
                        query_years.append(y)
                
                user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
                
                result = await db.execute(
                    select(UserFinancialData).where(
                        and_(
                            UserFinancialData.user_id == user_uuid,
                            UserFinancialData.tenant_id == tenant_id,
                            UserFinancialData.fiscal_year.in_(query_years)
                        )
                    ).order_by(UserFinancialData.fiscal_year.desc())
                )
                financial_data = result.scalars().first()
                
                if not financial_data:
                    logger.warning(f"⚠️ [财务数据查询] 未找到财务数据: user_id={user_id}, tenant_id={tenant_id}, 查询年份={query_years}")
                    return {
                        "status": "error",
                        "message": f"未找到任何可用年度的财务数据，请先录入财务数据",
                        "fiscal_year": fiscal_year,
                        "user_id": user_id,
                        "required_action": "请先录入财务数据"
                    }
                
                actual_year = financial_data.fiscal_year
                logger.info(f"✅ [财务数据查询] 成功获取 {actual_year} 年度财务数据")

                tax_results = []

                if include_vat:
                    calculated_vat = financial_data.calculated_vat
                    vat_rate = calculated_vat / financial_data.taxable_sales if financial_data.taxable_sales > 0 else 0
                    tax_results.append({
                        "tax_type": "增值税",
                        "amount": calculated_vat,
                        "rate": round(vat_rate * 100, 2),
                        "details": {
                            "taxable_sales": financial_data.taxable_sales,
                            "output_tax": financial_data.output_tax,
                            "input_tax": financial_data.input_tax
                        }
                    })

                if include_corporate_tax:
                    calculated_corporate_tax = financial_data.calculated_corporate_tax
                    effective_rate = calculated_corporate_tax / financial_data.taxable_income if financial_data.taxable_income > 0 else 0
                    tax_results.append({
                        "tax_type": "企业所得税",
                        "amount": calculated_corporate_tax,
                        "rate": round(effective_rate * 100, 2),
                        "details": {
                            "taxable_income": financial_data.taxable_income,
                            "corporate_tax_rate": financial_data.corporate_tax_rate,
                            "is_small_enterprise": financial_data.is_small_enterprise
                        }
                    })

                if include_personal_tax and financial_data.total_payroll > 0:
                    tax_results.append({
                        "tax_type": "个人所得税（代扣代缴）",
                        "amount": 0.0,
                        "rate": 0.0,
                        "details": {
                            "total_payroll": financial_data.total_payroll,
                            "special_deductions": financial_data.special_deductions
                        }
                    })

                return {
                    "status": "success",
                    "fiscal_year": actual_year,
                    "fiscal_year_hint": f"查询了 {query_years}，使用最新可用年份",
                    "financial_data": {
                        "total_revenue": financial_data.total_revenue,
                        "taxable_sales": financial_data.taxable_sales,
                        "tax_free_sales": financial_data.tax_free_sales,
                        "total_expenses": financial_data.total_expenses,
                        "deductible_expenses": financial_data.deductible_expenses,
                        "input_tax": financial_data.input_tax,
                        "output_tax": financial_data.output_tax,
                        "vat_rate": financial_data.vat_rate,
                        "taxable_income": financial_data.taxable_income,
                        "corporate_tax_rate": financial_data.corporate_tax_rate,
                        "is_small_enterprise": financial_data.is_small_enterprise
                    },
                    "tax_results": tax_results,
                    "total_tax": sum(t["amount"] for t in tax_results),
                    "tax_burden_rate": financial_data.tax_burden_rate,
                    "data_status": financial_data.data_status
                }
        
        except ProgrammingError as e:
            error_str = str(e)
            if "does not exist" in error_str or "UndefinedTableError" in error_str:
                logger.warning(f"⚠️ 财务数据表不存在，跳过查询")
                return {
                    "status": "unavailable",
                    "message": "财务数据功能暂时不可用，请先配置数据库表",
                    "fiscal_year": fiscal_year,
                    "required_action": "请联系管理员创建财务数据表"
                }
            logger.error(f"查询财务数据失败: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"数据库错误: {str(e)}",
                "fiscal_year": fiscal_year
            }
        except Exception as e:
            logger.error(f"查询财务数据失败: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"查询失败: {str(e)}",
                "fiscal_year": fiscal_year
            }


class TaxCalculationTool(ToolBase):
    """税务计算工具"""

    def __init__(self):
        super().__init__(
            name="calculate_tax",
            description="计算税务金额。根据提供的财务数据计算增值税、企业所得税等。",
            timeout=30
        )

    async def execute(
        self,
        tax_type: str,
        taxable_amount: float,
        tax_rate: float,
        input_tax: float = 0.0,
        deductions: float = 0.0,
        is_small_enterprise: bool = False
    ) -> Dict[str, Any]:
        """
        计算税务金额

        Args:
            tax_type: 税种类型（vat/corporate_income/personal_income）
            taxable_amount: 应税金额
            tax_rate: 税率
            input_tax: 进项税额（仅增值税）
            deductions: 扣除金额（仅个人所得税）
            is_small_enterprise: 是否小微企业（仅企业所得税）

        Returns:
            包含计算结果的字典
        """
        try:
            if tax_type.lower() == "vat":
                output_tax = taxable_amount * tax_rate
                net_tax = output_tax - input_tax
                return {
                    "tax_type": "增值税",
                    "taxable_amount": taxable_amount,
                    "tax_rate": tax_rate,
                    "output_tax": round(output_tax, 2),
                    "input_tax": input_tax,
                    "net_tax_payable": round(net_tax, 2),
                    "effective_rate": round(net_tax / taxable_amount * 100, 2) if taxable_amount > 0 else 0
                }

            elif tax_type.lower() == "corporate_income":
                if is_small_enterprise and taxable_amount <= 1000000:
                    effective_rate = 0.05
                elif is_small_enterprise and taxable_amount <= 3000000:
                    effective_rate = 0.05
                else:
                    effective_rate = tax_rate

                tax_amount = taxable_amount * effective_rate
                return {
                    "tax_type": "企业所得税",
                    "taxable_income": taxable_amount,
                    "standard_rate": tax_rate,
                    "effective_rate": effective_rate,
                    "tax_amount": round(tax_amount, 2),
                    "savings": round(taxable_amount * (tax_rate - effective_rate), 2),
                    "is_small_enterprise": is_small_enterprise
                }

            elif tax_type.lower() == "personal_income":
                from decimal import Decimal, ROUND_HALF_UP

                taxable_income = taxable_amount - deductions
                if taxable_income <= 0:
                    return {
                        "tax_type": "个人所得税",
                        "gross_income": taxable_amount,
                        "deductions": deductions,
                        "taxable_income": 0,
                        "tax_amount": 0,
                        "effective_rate": 0,
                        "message": "扣除专项附加扣除后无需缴纳个税"
                    }

                tax_brackets = [
                    (36000, 0.03, 0),
                    (144000, 0.10, 2520),
                    (300000, 0.20, 16920),
                    (420000, 0.25, 31920),
                    (660000, 0.30, 52920),
                    (960000, 0.35, 85920),
                    (float('inf'), 0.45, 181920)
                ]

                quick_deduction = 0
                for bracket, rate, deduction in tax_brackets:
                    if taxable_income <= bracket:
                        quick_deduction = deduction
                        tax_amount = taxable_income * rate - quick_deduction
                        break

                return {
                    "tax_type": "个人所得税",
                    "gross_income": taxable_amount,
                    "deductions": deductions,
                    "taxable_income": taxable_income,
                    "tax_amount": round(float(Decimal(str(tax_amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)), 2),
                    "effective_rate": round(tax_amount / taxable_amount * 100, 2) if taxable_amount > 0 else 0,
                    "monthly_tax": round(tax_amount / 12, 2)
                }

            else:
                return {
                    "status": "error",
                    "message": f"不支持的税种类型: {tax_type}"
                }

        except Exception as e:
            logger.error(f"税务计算失败: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"计算失败: {str(e)}"
            }


class TaxRecommendationTool(ToolBase):
    """税务筹划建议工具"""

    def __init__(self):
        super().__init__(
            name="get_tax_recommendations",
            description="根据财务数据提供税务筹划建议和风险提示。",
            timeout=30
        )

    async def execute(
        self,
        financial_data: Dict[str, Any],
        tax_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        生成税务筹划建议

        Args:
            financial_data: 财务数据字典
            tax_results: 税务计算结果列表

        Returns:
            包含建议和风险提示的字典
        """
        recommendations = []
        risk_alerts = []
        opportunities = []

        try:
            total_vat = next((t["amount"] for t in tax_results if t["tax_type"] == "增值税"), 0)
            total_corporate_tax = next((t["amount"] for t in tax_results if t["tax_type"] == "企业所得税"), 0)

            if financial_data.get("input_tax", 0) < financial_data.get("output_tax", 0) * 0.7:
                risk_alerts.append("进项税额抵扣不足，建议加强供应商管理，确保取得足额增值税专用发票")
                recommendations.append("建议与能提供增值税专用发票的供应商合作，增加进项税额抵扣")

            if financial_data.get("is_small_enterprise"):
                opportunities.append("已享受小微企业税收优惠政策，符合条件的企业所得税率为5%")

            if financial_data.get("tax_free_sales", 0) > 0:
                recommendations.append("免税销售额的处理符合规定，继续保持")

            if financial_data.get("deductible_expenses", 0) < financial_data.get("total_expenses", 0) * 0.8:
                risk_alerts.append("部分支出可能无法税前抵扣，建议规范发票管理")
                recommendations.append("建议审查成本结构，确保所有合规支出取得合法凭证")

            if total_vat > financial_data.get("taxable_sales", 1) * 0.05:
                risk_alerts.append("增值税税负率略高于行业平均水平")
                recommendations.append("建议关注进项发票管理，优化供应链")

            if not recommendations:
                recommendations.append("继续保持良好的税务合规管理，定期进行税务健康检查")

            return {
                "status": "success",
                "recommendations": recommendations,
                "risk_alerts": risk_alerts,
                "opportunities": opportunities,
                "summary": f"总税额约{total_vat + total_corporate_tax:.2f}元，建议关注进项发票管理和成本合规性"
            }

        except Exception as e:
            logger.error(f"生成税务建议失败: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"生成建议失败: {str(e)}"
            }
