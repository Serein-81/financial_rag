"""
财务数据 MCP 工具

提供 Agent 可调用的财务数据查询工具
包含上下文优化机制，防止数据量过大导致 Token 溢出
"""

import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.services.financial_data_service import (
    FinancialDataQueryService,
    FinancialQueryParams,
    QueryResult,
)

logger = logging.getLogger(__name__)


class QueryFinancialDataInput(BaseModel):
    """查询财务数据输入参数"""
    tenant_id: str = Field(
        description="租户ID，用于隔离不同企业的数据"
    )
    fiscal_year: Optional[int] = Field(
        default=None,
        description="财务年度，如 2024。不填则查询所有年份"
    )
    period_type: Optional[str] = Field(
        default=None,
        description="周期类型：yearly（年度）/ quarterly（季度）/ monthly（月度）"
    )
    data_status: Optional[str] = Field(
        default=None,
        description="数据状态：draft（草稿）/ confirmed（已确认）/ final（最终）"
    )
    limit: int = Field(
        default=100,
        description="最大返回记录数，默认100条",
        ge=1,
        le=1000
    )
    offset: int = Field(
        default=0,
        description="分页偏移量",
        ge=0
    )
    aggregate: bool = Field(
        default=False,
        description="是否返回聚合摘要。数据量大时建议开启，减少Token使用"
    )


class GetFinancialOverviewInput(BaseModel):
    """获取财务概览输入参数"""
    tenant_id: str = Field(
        description="租户ID，用于隔离不同企业的数据"
    )
    fiscal_year: Optional[int] = Field(
        default=None,
        description="财务年度，如 2024。不填则查询最新数据"
    )


class GetFinancialTrendInput(BaseModel):
    """获取财务趋势输入参数"""
    tenant_id: str = Field(
        description="租户ID，用于隔离不同企业的数据"
    )
    fiscal_year: int = Field(
        description="财务年度，如 2024"
    )
    period_type: str = Field(
        default="yearly",
        description="周期类型：yearly（年度）/ quarterly（季度）/ monthly（月度）"
    )


class SearchFinancialDataInput(BaseModel):
    """搜索财务数据输入参数"""
    tenant_id: str = Field(
        description="租户ID，用于隔离不同企业的数据"
    )
    query: str = Field(
        description="搜索关键词，如年份（2024）、指标名称等"
    )
    limit: int = Field(
        default=20,
        description="最大返回记录数，默认20条",
        ge=1,
        le=100
    )


def create_financial_tools():
    """
    创建财务数据查询工具列表
    
    供 Agent 调用的工具集合
    
    Returns:
        List[BaseTool]: 工具列表
    """
    from langchain_core.tools import tool
    
    @tool("query_financial_data", parse_docstring=True)
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
            tenant_id: 租户ID，必填
            fiscal_year: 财务年度，如 2024
            period_type: 周期类型，yearly/quarterly/monthly
            data_status: 数据状态，draft/confirmed/final
            limit: 最大返回记录数，默认100
            offset: 分页偏移量
            aggregate: 是否返回聚合摘要
        
        Returns:
            包含查询结果和上下文优化信息的字典
            
        Example:
            # 查询2024年度数据
            query_financial_data(tenant_id="xxx", fiscal_year=2024)
            
            # 获取聚合摘要
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
            result = await service.query_financial_data(params)
            
            if result.success:
                return {
                    "status": "success",
                    "data": result.data,
                    "summary": result.summary,
                    "query_params": result.query_params,
                    "context_info": result.context_info,
                    "message": _format_success_message(result)
                }
            else:
                return {
                    "status": "error",
                    "error": result.error,
                    "message": f"查询失败: {result.error}"
                }
                
        except Exception as e:
            logger.error(f"查询财务数据失败: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "message": f"查询财务数据时发生错误: {str(e)}"
            }
    
    @tool("get_financial_overview", parse_docstring=True)
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
            fiscal_year: 财务年度，如 2024。不填则获取所有年份概览
        
        Returns:
            包含财务概览和摘要信息的字典
            
        Example:
            # 获取2024年财务概览
            get_financial_overview(tenant_id="xxx", fiscal_year=2024)
        """
        try:
            service = await FinancialDataQueryService.create()
            result = await service.get_financial_overview(
                tenant_id=tenant_id,
                years=[fiscal_year] if fiscal_year else None
            )
            
            if result.success and result.summary:
                return {
                    "status": "success",
                    "summary": {
                        "total_records": result.summary.total_records,
                        "fiscal_years": result.summary.fiscal_years,
                        "period_types": result.summary.period_types,
                        "total_revenue": result.summary.total_revenue,
                        "total_expenses": result.summary.total_expenses,
                        "total_profit": result.summary.total_profit,
                        "avg_profit_margin": result.summary.avg_profit_margin,
                        "total_vat": result.summary.total_vat,
                        "total_corporate_tax": result.summary.total_corporate_tax,
                        "avg_tax_burden_rate": result.summary.avg_tax_burden_rate,
                        "earliest_period": result.summary.earliest_period,
                        "latest_period": result.summary.latest_period,
                        "context_optimization": result.summary.context_optimization
                    },
                    "sample_records": result.summary.sample_records,
                    "message": _format_overview_message(result.summary)
                }
            else:
                return {
                    "status": "error",
                    "error": result.error or "未找到财务数据",
                    "message": "未找到匹配的财务数据或查询失败"
                }
                
        except Exception as e:
            logger.error(f"获取财务概览失败: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "message": f"获取财务概览时发生错误: {str(e)}"
            }
    
    @tool("get_financial_trend", parse_docstring=True)
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
            period_type: 周期类型，默认 yearly
        
        Returns:
            包含趋势数据的字典
            
        Example:
            # 获取2024年度趋势
            get_financial_trend(tenant_id="xxx", fiscal_year=2024)
            
            # 获取2024年季度趋势
            get_financial_trend(tenant_id="xxx", fiscal_year=2024, period_type="quarterly")
        """
        try:
            service = await FinancialDataQueryService.create()
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
                    "message": _format_trend_message(trend_data)
                }
            else:
                return {
                    "status": "error",
                    "error": result.error,
                    "message": f"获取趋势数据失败: {result.error}"
                }
                
        except Exception as e:
            logger.error(f"获取财务趋势失败: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "message": f"获取财务趋势时发生错误: {str(e)}"
            }
    
    @tool("search_financial_data", parse_docstring=True)
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
            # 搜索2024年数据
            search_financial_data(tenant_id="xxx", query="2024")
            
            # 搜索特定指标
            search_financial_data(tenant_id="xxx", query="增值税")
        """
        try:
            service = await FinancialDataQueryService.create()
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
                
        except Exception as e:
            logger.error(f"搜索财务数据失败: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "message": f"搜索财务数据时发生错误: {str(e)}"
            }
    
    return [
        query_financial_data,
        get_financial_overview,
        get_financial_trend,
        search_financial_data,
    ]


def _format_success_message(result: QueryResult) -> str:
    """格式化成功消息"""
    if result.summary:
        return (
            f"查询成功，共 {result.summary.total_records} 条记录。"
            f"总营收 {result.summary.total_revenue:,.2f} 元，"
            f"总支出 {result.summary.total_expenses:,.2f} 元，"
            f"平均利润率 {result.summary.avg_profit_margin:.2f}%。"
            f"数据压缩比: {result.summary.context_optimization.get('compression_ratio', 'N/A')}"
        )
    else:
        count = len(result.data) if result.data else 0
        return f"查询成功，返回 {count} 条记录"


def _format_overview_message(summary) -> str:
    """格式化概览消息"""
    return (
        f"财务概览（共 {summary.total_records} 条记录，覆盖 {summary.fiscal_years} 年）：\n"
        f"• 总营收：{summary.total_revenue:,.2f} 元\n"
        f"• 总支出：{summary.total_expenses:,.2f} 元\n"
        f"• 总利润：{summary.total_profit:,.2f} 元\n"
        f"• 平均利润率：{summary.avg_profit_margin:.2f}%\n"
        f"• 增值税合计：{summary.total_vat:,.2f} 元\n"
        f"• 企业所得税：{summary.total_corporate_tax:,.2f} 元\n"
        f"• 平均税负率：{summary.avg_tax_burden_rate:.2f}%\n"
        f"• 数据时间范围：{summary.earliest_period} 至 {summary.latest_period}"
    )


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
    
    if len(revenues) >= 2:
        revenue_change = (revenues[0] - revenues[-1]) / revenues[-1] * 100 if revenues[-1] != 0 else 0
        expense_change = (expenses[0] - expenses[-1]) / expenses[-1] * 100 if expenses[-1] != 0 else 0
        profit_change = (profits[0] - profits[-1]) / abs(profits[-1]) * 100 if profits[-1] != 0 else 0
    
    return {
        "record_count": len(records),
        "period_range": f"{records[-1].get('period_start', 'N/A')} 至 {records[0].get('period_start', 'N/A')}",
        "revenue_change_pct": round(revenue_change, 2),
        "expense_change_pct": round(expense_change, 2),
        "profit_change_pct": round(profit_change, 2),
        "avg_revenue": sum(revenues) / len(revenues),
        "avg_expense": sum(expenses) / len(expenses),
        "avg_profit": sum(profits) / len(profits),
    }


def _format_trend_message(trend_data: Dict[str, Any]) -> str:
    """格式化趋势消息"""
    if not trend_data:
        return "未找到趋势数据"
    
    return (
        f"趋势分析（{trend_data.get('record_count', 0)} 个周期，"
        f"{trend_data.get('period_range', 'N/A')}）：\n"
        f"• 营收变化：{trend_data.get('revenue_change_pct', 0):+.2f}%\n"
        f"• 支出变化：{trend_data.get('expense_change_pct', 0):+.2f}%\n"
        f"• 利润变化：{trend_data.get('profit_change_pct', 0):+.2f}%\n"
        f"• 平均营收：{trend_data.get('avg_revenue', 0):,.2f} 元\n"
        f"• 平均利润：{trend_data.get('avg_profit', 0):,.2f} 元"
    )


FINANCIAL_TOOLS = create_financial_tools()

__all__ = [
    "FINANCIAL_TOOLS",
    "create_financial_tools",
    "query_financial_data",
    "get_financial_overview",
    "get_financial_trend",
    "search_financial_data",
]
