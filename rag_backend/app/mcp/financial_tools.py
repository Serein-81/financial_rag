"""
财务数据 MCP 工具

提供 Agent 可调用的财务数据查询工具
包含上下文优化机制，防止数据量过大导致 Token 溢出

工具类型：本地 STDIO（访问本地数据库）
"""

import logging
from typing import Optional, List, Dict, Any

from app.mcp.decorators import local_tool
from app.services.financial_data_service import (
    FinancialDataQueryService,
    FinancialQueryParams,
)

logger = logging.getLogger(__name__)


@local_tool(
    description="查询企业财务数据记录，支持按年份、周期类型筛选，数据量大时建议开启 aggregate=true 获取聚合摘要"
)
async def query_financial_data(
    tenant_id: str,
    fiscal_year: Optional[int] = None,
    period_type: Optional[str] = None,
    data_status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    aggregate: bool = False,
) -> Dict[str, Any]:
    """
    查询企业财务数据
    
    用于获取企业的财务数据记录，支持按年份、周期类型筛选。
    如果数据量较大，建议开启 aggregate=true 获取聚合摘要。
    
    Args:
        tenant_id: 租户ID，必填，用于隔离数据
        fiscal_year: 财务年度，如 2024，不填则查询所有年份
        period_type: 周期类型，yearly/quarterly/monthly
        data_status: 数据状态，draft/confirmed/final
        limit: 最大返回记录数，默认100
        offset: 分页偏移量
        aggregate: 是否返回聚合摘要，数据量大时建议开启
    
    Returns:
        包含查询结果和上下文优化信息的字典
    
    Example:
        query_financial_data(tenant_id="xxx", fiscal_year=2024)
        query_financial_data(tenant_id="xxx", aggregate=True)
    """
    try:
        params = FinancialQueryParams(
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            period_type=period_type,
            data_status=data_status,
            limit=limit,
            offset=offset,
            aggregate=aggregate
        )
        
        service = await FinancialDataQueryService.create()
        try:
            result = await service.query_financial_data(params)
            
            if result.success:
                return {
                    "status": "success",
                    "data": result.data,
                    "summary": result.summary,
                    "query_params": result.query_params,
                    "context_info": result.context_info,
                    "message": f"查询成功，共 {result.summary.total_records if result.summary else len(result.data)} 条记录"
                }
            else:
                return {
                    "status": "error",
                    "error": result.error,
                    "message": f"查询失败: {result.error}"
                }
        finally:
            service.close()
            
    except Exception as e:
        logger.error(f"查询财务数据失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"查询财务数据时发生错误: {str(e)}"
        }


@local_tool(
    description="快速获取企业财务状况的高层摘要，自动聚合数据，适合需要快速了解整体财务状况的场景"
)
async def get_financial_overview(
    tenant_id: str,
    fiscal_year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    获取企业财务概览
    
    快速获取企业财务状况的高层摘要，
    自动聚合数据，适合需要快速了解整体财务状况的场景。
    
    Args:
        tenant_id: 租户ID，必填
        fiscal_year: 财务年度，如 2024，不填则获取所有年份概览
    
    Returns:
        包含财务概览和摘要信息的字典
    
    Example:
        get_financial_overview(tenant_id="xxx", fiscal_year=2024)
    """
    logger.info(f"📊 [MCP财务工具] get_financial_overview 被调用")
    logger.info(f"   - tenant_id: {tenant_id}")
    logger.info(f"   - fiscal_year: {fiscal_year}")
    
    try:
        service = await FinancialDataQueryService.create()
        try:
            logger.info(f"📊 [MCP财务工具] 开始查询财务概览...")
            
            result = await service.get_financial_overview(
                tenant_id=tenant_id,
                years=[fiscal_year] if fiscal_year else None
            )
            
            logger.info(f"📊 [MCP财务工具] 查询结果: success={result.success}")
            if result.summary:
                logger.info(f"   - total_records: {result.summary.total_records}")
                logger.info(f"   - fiscal_years: {result.summary.fiscal_years}")
                logger.info(f"   - total_revenue: {result.summary.total_revenue:,.2f}")
                logger.info(f"   - total_profit: {result.summary.total_profit:,.2f}")
                logger.info(f"   - avg_profit_margin: {result.summary.avg_profit_margin:.4f}")
            else:
                logger.warning(f"📊 [MCP财务工具] result.summary 为 None")
            
            if result.success and result.summary:
                # 🔧 数据清洗：过滤掉没有实际数据的年份
                valid_years = _filter_valid_years(result.summary.fiscal_years, result.data if result.data else [])
                
                return {
                    "status": "success",
                    "data": {
                        "total_records": result.summary.total_records,
                        "fiscal_years": valid_years,
                        "period_types": result.summary.period_types,
                        "total_revenue": result.summary.total_revenue,
                        "total_expenses": result.summary.total_expenses,
                        "total_profit": result.summary.total_profit,
                        "avg_profit_margin": result.summary.avg_profit_margin,
                        "total_vat": result.summary.total_vat,
                        "total_corporate_tax": result.summary.total_corporate_tax,
                        "avg_tax_burden_rate": result.summary.avg_tax_burden_rate,
                        "earliest_period": str(result.summary.earliest_period) if result.summary.earliest_period else None,
                        "latest_period": str(result.summary.latest_period) if result.summary.latest_period else None,
                    },
                    "summary": {
                        "total_records": result.summary.total_records,
                        "fiscal_years": valid_years,
                        "period_types": result.summary.period_types,
                        "total_revenue": result.summary.total_revenue,
                        "total_expenses": result.summary.total_expenses,
                        "total_profit": result.summary.total_profit,
                        "avg_profit_margin": result.summary.avg_profit_margin,
                        "total_vat": result.summary.total_vat,
                        "total_corporate_tax": result.summary.total_corporate_tax,
                        "avg_tax_burden_rate": result.summary.avg_tax_burden_rate,
                        "earliest_period": str(result.summary.earliest_period) if result.summary.earliest_period else None,
                        "latest_period": str(result.summary.latest_period) if result.summary.latest_period else None,
                    },
                    "sample_records": result.summary.sample_records,
                    "message": f"财务概览：总营收 {result.summary.total_revenue:,.2f} 元，利润 {result.summary.total_profit:,.2f} 元"
                }
            else:
                logger.warning(f"📊 [MCP财务工具] 查询失败或无数据: error={result.error}")
                return {
                    "status": "error",
                    "error": result.error or "未找到财务数据",
                    "message": "未找到匹配的财务数据或查询失败"
                }
        finally:
            service.close()
                
    except Exception as e:
        logger.error(f"获取财务概览失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"获取财务概览时发生错误: {str(e)}"
        }


@local_tool(
    description="分析财务指标在特定时间段内的变化趋势，适用于趋势分析、同比/环比变化等问题"
)
async def get_financial_trend(
    tenant_id: str,
    fiscal_year: int,
    period_type: str = "yearly",
) -> Dict[str, Any]:
    """
    获取财务趋势数据
    
    用于分析财务指标在特定时间段内的变化趋势。
    适用于用户询问"趋势分析"、"同比/环比变化"等问题。
    
    Args:
        tenant_id: 租户ID，必填
        fiscal_year: 财务年度，必填，如 2024
        period_type: 周期类型，默认 yearly，可选 yearly/quarterly/monthly
    
    Returns:
        包含趋势数据的字典
    
    Example:
        get_financial_trend(tenant_id="xxx", fiscal_year=2024)
        get_financial_trend(tenant_id="xxx", fiscal_year=2024, period_type="quarterly")
    """
    try:
        service = await FinancialDataQueryService.create()
        try:
            result = await service.get_financial_trend(
                tenant_id=tenant_id,
                fiscal_year=fiscal_year,
                period_type=period_type
            )
            
            if result.success:
                trend_data = _analyze_trend(result.data)
                
                return {
                    "status": "success",
                    "trend_data": trend_data,
                    "records": result.data,
                    "query_params": result.query_params,
                    "message": f"趋势分析：营收变化 {trend_data.get('revenue_change_pct', 0):+.2f}%，利润变化 {trend_data.get('profit_change_pct', 0):+.2f}%"
                }
            else:
                return {
                    "status": "error",
                    "error": result.error,
                    "message": f"获取趋势数据失败: {result.error}"
                }
        finally:
            service.close()
                
    except Exception as e:
        logger.error(f"获取财务趋势失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"获取财务趋势时发生错误: {str(e)}"
        }


@local_tool(
    description="基于关键词搜索财务记录，适用于询问特定财务指标、时期等问题"
)
async def search_financial_data(
    tenant_id: str,
    query: str,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    搜索财务数据
    
    基于关键词搜索财务记录。
    适用于用户询问特定财务指标、时期等问题。
    
    Args:
        tenant_id: 租户ID，必填
        query: 搜索关键词，支持年份（2024）、备注关键词等
        limit: 最大返回记录数，默认20
    
    Returns:
        包含搜索结果的字典
    
    Example:
        search_financial_data(tenant_id="xxx", query="2024")
        search_financial_data(tenant_id="xxx", query="增值税")
    """
    try:
        service = await FinancialDataQueryService.create()
        try:
            result = await service.search_financial_data(
                tenant_id=tenant_id,
                query=query,
                limit=limit
            )
            
            if result.success:
                return {
                    "status": "success",
                    "results": result.data,
                    "query_params": result.query_params,
                    "context_info": result.context_info,
                    "message": f"找到 {len(result.data)} 条匹配记录"
                }
            else:
                return {
                    "status": "error",
                    "error": result.error,
                    "message": f"搜索失败: {result.error}"
                }
        finally:
            service.close()
                
    except Exception as e:
        logger.error(f"搜索财务数据失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"搜索财务数据时发生错误: {str(e)}"
        }


def _analyze_trend(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """分析趋势数据"""
    if not records:
        return {}
    
    revenues = [r.get("total_revenue", 0) for r in records]
    expenses = [r.get("total_expenses", 0) for r in records]
    profits = [r.get("profit", 0) for r in records]
    
    revenue_change = 0
    expense_change = 0
    profit_change = 0
    
    if len(revenues) >= 2 and revenues[-1] != 0:
        revenue_change = (revenues[0] - revenues[-1]) / revenues[-1] * 100
    if len(expenses) >= 2 and expenses[-1] != 0:
        expense_change = (expenses[0] - expenses[-1]) / expenses[-1] * 100
    if len(profits) >= 2 and profits[-1] != 0:
        profit_change = (profits[0] - profits[-1]) / abs(profits[-1]) * 100
    
    return {
        "record_count": len(records),
        "period_range": f"{records[-1].get('period_start', 'N/A')} 至 {records[0].get('period_start', 'N/A')}",
        "revenue_change_pct": round(revenue_change, 2),
        "expense_change_pct": round(expense_change, 2),
        "profit_change_pct": round(profit_change, 2),
        "avg_revenue": sum(revenues) / len(revenues) if revenues else 0,
        "avg_expense": sum(expenses) / len(expenses) if expenses else 0,
        "avg_profit": sum(profits) / len(profits) if profits else 0,
    }


def _filter_valid_years(fiscal_years: List[int], records: List[Dict[str, Any]]) -> List[int]:
    """
    🔧 数据清洗管道：过滤掉没有实际财务数据的年份
    
    数据库中可能存在占位符年份（空值），这些不应该展示给用户。
    
    Args:
        fiscal_years: 所有年份列表
        records: 原始记录列表
        
    Returns:
        只包含有实际数据的年份列表
    """
    if not records:
        return fiscal_years
    
    year_to_has_data = {}
    for year in fiscal_years:
        year_to_has_data[year] = False
    
    for record in records:
        year = record.get('fiscal_year')
        if year and not year_to_has_data.get(year, True):
            if record.get('total_revenue') is not None and record.get('total_revenue', 0) > 0:
                year_to_has_data[year] = True
    
    valid_years = [year for year, has_data in year_to_has_data.items() if has_data]
    valid_years.sort()
    
    if len(valid_years) < len(fiscal_years):
        logger.info(f"🔧 [数据清洗] 过滤空数据年份: {len(fiscal_years)} -> {len(valid_years)} 个有效年份")
        logger.info(f"   - 原始年份: {fiscal_years[:5]}... 共 {len(fiscal_years)} 个")
        logger.info(f"   - 有效年份: {valid_years[:5]}... 共 {len(valid_years)} 个")
    
    return valid_years if valid_years else fiscal_years


def get_tax_compliance_assessment(taxable_income: float, corporate_tax: float) -> Dict[str, Any]:
    """
    🔧 税务合规硬编码规则引擎
    
    税务合规判断必须基于代码逻辑，而非 LLM 自由发挥。
    
    Args:
        taxable_income: 应纳税所得额（元）
        corporate_tax: 企业所得税（元）
        
    Returns:
        税务合规评估结果
    """
    SMALL_ENTERPRISE_INCOME_LIMIT = 3000000  # 小微企业年应纳税所得额上限 300万
    TENTATIVE_TAX_RATE = 0.20  # 预征税率 20%
    BENEFIT_TAX_RATE = 0.05    # 优惠税率 5%（小微企业）
    
    result = {
        "is_small_enterprise": False,
        "meets_benefit_conditions": False,
        "taxable_income": taxable_income,
        "effective_tax_rate": 0.0,
        "assessed_tax": 0.0,
        "benefit_description": "",
        "risk_level": "低风险",
        "risk_description": ""
    }
    
    if taxable_income > 0 and corporate_tax > 0:
        result["effective_tax_rate"] = corporate_tax / taxable_income
    
    if taxable_income <= SMALL_ENTERPRISE_INCOME_LIMIT:
        result["is_small_enterprise"] = True
        result["meets_benefit_conditions"] = True
        result["assessed_tax"] = taxable_income * BENEFIT_TAX_RATE
        result["benefit_description"] = f"年应纳税所得额 {taxable_income:,.2f} 元 ≤ {SMALL_ENTERPRISE_INCOME_LIMIT:,} 元，符合小微企业优惠条件"
        result["risk_level"] = "低风险"
        result["risk_description"] = "税务合规，应享尽享小微企业税收优惠"
    else:
        result["is_small_enterprise"] = False
        result["meets_benefit_conditions"] = False
        result["assessed_tax"] = taxable_income * TENTATIVE_TAX_RATE
        result["benefit_description"] = f"年应纳税所得额 {taxable_income:,.2f} 元 > {SMALL_ENTERPRISE_INCOME_LIMIT:,} 元，不符合小微企业优惠条件"
        result["risk_level"] = "中风险"
        result["risk_description"] = "应纳税所得额超过小微企业标准，无法享受5%优惠税率"
    
    return result


def create_financial_tools():
    """创建财务工具列表"""
    return [
        query_financial_data,
        get_financial_overview,
        get_financial_trend,
        search_financial_data,
    ]
