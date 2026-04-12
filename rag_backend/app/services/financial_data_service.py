"""
财务数据查询服务

提供高效的数据库财务数据查询功能
包含上下文优化机制，防止数据量过大导致 Agent 上下文溢出
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from dataclasses import dataclass, asdict
from decimal import Decimal
import json

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_financial_data import UserFinancialData
from app.db.session import get_db_context

logger = logging.getLogger(__name__)


@dataclass
class FinancialQueryParams:
    """财务数据查询参数"""
    tenant_id: str
    fiscal_year: Optional[int] = None
    period_type: Optional[str] = None
    data_status: Optional[str] = None
    limit: int = 100
    offset: int = 0
    aggregate: bool = False


@dataclass
class FinancialDataSummary:
    """财务数据摘要"""
    total_records: int
    fiscal_years: List[int]
    period_types: List[str]
    
    total_revenue: float
    total_expenses: float
    total_profit: float
    avg_profit_margin: float
    
    total_vat: float
    total_corporate_tax: float
    avg_tax_burden_rate: float
    
    latest_period: str
    earliest_period: str
    
    sample_records: List[Dict[str, Any]]
    
    context_optimization: Dict[str, Any]


@dataclass
class QueryResult:
    """查询结果"""
    success: bool
    data: Any
    summary: Optional[FinancialDataSummary] = None
    error: Optional[str] = None
    query_params: Optional[Dict[str, Any]] = None
    context_info: Optional[Dict[str, Any]] = None


class FinancialDataQueryService:
    """
    财务数据查询服务
    
    核心功能：
    1. 基础查询：按年份、周期类型、数据状态查询
    2. 聚合查询：生成财务数据摘要
    3. 上下文优化：防止数据量过大
    """
    
    MAX_CONTEXT_TOKENS = 8000
    ESTIMATED_TOKENS_PER_RECORD = 200
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    @classmethod
    async def create(cls) -> "FinancialDataQueryService":
        """工厂方法：创建服务实例并获取数据库会话"""
        async with get_db_context() as session:
            return cls(session)
    
    async def query_financial_data(
        self,
        params: FinancialQueryParams
    ) -> QueryResult:
        """
        查询财务数据
        
        Args:
            params: 查询参数
            
        Returns:
            QueryResult: 包含查询结果和上下文优化信息
        """
        try:
            conditions = [
                UserFinancialData.tenant_id == params.tenant_id,
                UserFinancialData.is_current == True
            ]
            
            if params.fiscal_year:
                conditions.append(
                    UserFinancialData.fiscal_year == params.fiscal_year
                )
            
            if params.period_type:
                conditions.append(
                    UserFinancialData.period_type == params.period_type
                )
            
            if params.data_status:
                conditions.append(
                    UserFinancialData.data_status == params.data_status
                )
            
            base_query = select(UserFinancialData).where(and_(*conditions))
            
            total_count_query = select(func.count()).select_from(
                UserFinancialData
            ).where(and_(*conditions))
            total_result = await self.db.execute(total_count_query)
            total_count = total_result.scalar() or 0
            
            query = base_query.order_by(
                desc(UserFinancialData.period_start)
            ).limit(params.limit).offset(params.offset)
            
            result = await self.db.execute(query)
            records = result.scalars().all()
            
            records_data = [self._serialize_record(r) for r in records]
            
            summary = None
            if params.aggregate and records:
                summary = await self._generate_summary(
                    tenant_id=params.tenant_id,
                    records=records,
                    total_count=total_count
                )
            
            max_records = self.MAX_CONTEXT_TOKENS // self.ESTIMATED_TOKENS_PER_RECORD
            needs_optimization = total_count > max_records
            
            context_info = {
                "total_count": total_count,
                "returned_count": len(records),
                "limit": params.limit,
                "offset": params.offset,
                "max_context_tokens": self.MAX_CONTEXT_TOKENS,
                "estimated_tokens": len(records) * self.ESTIMATED_TOKENS_PER_RECORD,
                "needs_optimization": needs_optimization,
                "recommendation": self._get_optimization_recommendation(
                    total_count, len(records), params
                ) if needs_optimization else None
            }
            
            return QueryResult(
                success=True,
                data=records_data,
                summary=summary,
                query_params=asdict(params),
                context_info=context_info
            )
            
        except Exception as e:
            logger.error(f"财务数据查询失败: {e}", exc_info=True)
            return QueryResult(
                success=False,
                data=None,
                error=f"查询失败: {str(e)}"
            )
    
    async def _generate_summary(
        self,
        tenant_id: str,
        records: List[UserFinancialData],
        total_count: int
    ) -> FinancialDataSummary:
        """生成财务数据摘要"""
        fiscal_years = sorted(set(r.fiscal_year for r in records))
        period_types = sorted(set(r.period_type for r in records))
        
        total_revenue = sum(r.total_revenue or 0 for r in records)
        total_expenses = sum(r.total_expenses or 0 for r in records)
        total_profit = total_revenue - total_expenses
        
        profit_margins = []
        for r in records:
            if r.total_revenue and r.total_revenue > 0:
                margin = (r.total_revenue - r.total_expenses) / r.total_revenue
                profit_margins.append(margin)
        
        avg_profit_margin = sum(profit_margins) / len(profit_margins) if profit_margins else 0
        
        total_vat = sum(
            (r.output_tax or 0) - (r.input_tax or 0)
            for r in records
        )
        
        corporate_taxes = []
        for r in records:
            if r.taxable_income:
                if r.is_small_enterprise and r.taxable_income <= 1000000:
                    corporate_taxes.append(r.taxable_income * 0.05)
                elif r.is_small_enterprise and r.taxable_income <= 3000000:
                    corporate_taxes.append(r.taxable_income * 0.05)
                else:
                    corporate_taxes.append(r.taxable_income * r.corporate_tax_rate)
        
        total_corporate_tax = sum(corporate_taxes)
        
        tax_burden_rates = []
        for r in records:
            if r.total_revenue and r.total_revenue > 0:
                vat = (r.output_tax or 0) - (r.input_tax or 0)
                corporate_tax = corporate_taxes[records.index(r)] if records.index(r) < len(corporate_taxes) else 0
                rate = (vat + corporate_tax) / r.total_revenue
                tax_burden_rates.append(rate)
        
        avg_tax_burden_rate = sum(tax_burden_rates) / len(tax_burden_rates) if tax_burden_rates else 0
        
        sorted_by_period = sorted(records, key=lambda r: r.period_start)
        earliest = sorted_by_period[0].period_start if sorted_by_period else None
        latest = sorted_by_period[-1].period_start if sorted_by_period else None
        
        sample_size = min(3, len(records))
        sample_records = [
            self._serialize_record(r, detailed=False)
            for r in records[:sample_size]
        ]
        
        context_optimization = {
            "original_records": total_count,
            "summarized_records": sample_size,
            "compression_ratio": f"{sample_size}/{total_count}" if total_count > 0 else "N/A",
            "tokens_saved": (total_count - sample_size) * self.ESTIMATED_TOKENS_PER_RECORD
        }
        
        return FinancialDataSummary(
            total_records=total_count,
            fiscal_years=fiscal_years,
            period_types=period_types,
            total_revenue=round(total_revenue, 2),
            total_expenses=round(total_expenses, 2),
            total_profit=round(total_profit, 2),
            avg_profit_margin=round(avg_profit_margin * 100, 2),
            total_vat=round(total_vat, 2),
            total_corporate_tax=round(total_corporate_tax, 2),
            avg_tax_burden_rate=round(avg_tax_burden_rate * 100, 2),
            latest_period=str(latest) if latest else None,
            earliest_period=str(earliest) if earliest else None,
            sample_records=sample_records,
            context_optimization=context_optimization
        )
    
    def _serialize_record(
        self,
        record: UserFinancialData,
        detailed: bool = True
    ) -> Dict[str, Any]:
        """序列化财务记录"""
        data = {
            "id": str(record.id),
            "fiscal_year": record.fiscal_year,
            "period_type": record.period_type,
            "period_start": str(record.period_start),
            "period_end": str(record.period_end),
            "total_revenue": record.total_revenue,
            "total_expenses": record.total_expenses,
            "profit": round(record.total_revenue - record.total_expenses, 2),
            "profit_margin": round(
                (record.total_revenue - record.total_expenses) / record.total_revenue * 100, 2
            ) if record.total_revenue and record.total_revenue > 0 else 0,
            "output_tax": record.output_tax,
            "input_tax": record.input_tax,
            "vat": round((record.output_tax or 0) - (record.input_tax or 0), 2),
            "taxable_income": record.taxable_income,
            "is_small_enterprise": record.is_small_enterprise,
            "data_status": record.data_status,
        }
        
        if detailed:
            data.update({
                "taxable_sales": record.taxable_sales,
                "deductible_expenses": record.deductible_expenses,
                "corporate_tax_rate": record.corporate_tax_rate,
                "calculated_vat": record.calculated_vat,
                "calculated_corporate_tax": record.calculated_corporate_tax,
                "tax_burden_rate": record.tax_burden_rate,
                "total_invoices": record.total_invoices,
                "cost_breakdown": record.cost_breakdown,
            })
        
        return data
    
    def _get_optimization_recommendation(
        self,
        total_count: int,
        returned_count: int,
        params: FinancialQueryParams
    ) -> Dict[str, Any]:
        """获取优化建议"""
        recommendations = []
        
        if total_count > self.MAX_CONTEXT_TOKENS // self.ESTIMATED_TOKENS_PER_RECORD:
            recommendations.append({
                "type": "aggregation",
                "reason": "数据量超过上下文限制，建议使用聚合查询",
                "action": "设置 aggregate=true 获取摘要"
            })
        
        if params.fiscal_year is None:
            recommendations.append({
                "type": "filter",
                "reason": f"当前返回 {total_count} 条记录",
                "action": f"建议按年份筛选：添加 fiscal_year 参数"
            })
        
        if params.period_type is None:
            recommendations.append({
                "type": "filter",
                "reason": "包含多种周期类型数据",
                "action": "建议指定周期类型：period_type=yearly/quarterly/monthly"
            })
        
        return {
            "recommendations": recommendations,
            "alternative_query": {
                "aggregate": True,
                "fiscal_year": params.fiscal_year or fiscal_years[0] if params.fiscal_year else None,
                "period_type": params.period_type
            }
        }
    
    async def get_financial_overview(
        self,
        tenant_id: str,
        years: Optional[List[int]] = None
    ) -> QueryResult:
        """
        获取财务概览（优化版）
        
        适用于需要快速了解企业财务状况的场景
        自动聚合数据，减少上下文使用
        """
        params = FinancialQueryParams(
            tenant_id=tenant_id,
            aggregate=True,
            limit=1000
        )
        
        if years:
            params.fiscal_year = years[0] if len(years) == 1 else None
        
        return await self.query_financial_data(params)
    
    async def get_financial_trend(
        self,
        tenant_id: str,
        fiscal_year: int,
        period_type: str = "yearly"
    ) -> QueryResult:
        """
        获取财务趋势数据
        
        用于分析财务指标的变化趋势
        """
        params = FinancialQueryParams(
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            period_type=period_type,
            limit=50
        )
        
        return await self.query_financial_data(params)
    
    async def search_financial_data(
        self,
        tenant_id: str,
        query: str,
        limit: int = 20
    ) -> QueryResult:
        """
        智能搜索财务数据
        
        基于关键词搜索财务记录
        适用于用户询问特定财务指标或时期
        """
        try:
            conditions = [
                UserFinancialData.tenant_id == tenant_id,
                UserFinancialData.is_current == True,
                or_(
                    UserFinancialData.notes.ilike(f"%{query}%"),
                    UserFinancialData.data_source.ilike(f"%{query}%")
                )
            ]
            
            try:
                year = int(query)
                conditions.append(UserFinancialData.fiscal_year == year)
            except ValueError:
                pass
            
            query_stmt = select(UserFinancialData).where(
                and_(*conditions)
            ).order_by(desc(UserFinancialData.period_start)).limit(limit)
            
            result = await self.db.execute(query_stmt)
            records = result.scalars().all()
            
            records_data = [self._serialize_record(r) for r in records]
            
            return QueryResult(
                success=True,
                data=records_data,
                query_params={
                    "tenant_id": tenant_id,
                    "query": query,
                    "limit": limit,
                    "returned_count": len(records)
                },
                context_info={
                    "search_mode": "keyword",
                    "returned_count": len(records),
                    "estimated_tokens": len(records) * self.ESTIMATED_TOKENS_PER_RECORD,
                    "needs_optimization": len(records) * self.ESTIMATED_TOKENS_PER_RECORD > self.MAX_CONTEXT_TOKENS
                }
            )
            
        except Exception as e:
            logger.error(f"财务数据搜索失败: {e}", exc_info=True)
            return QueryResult(
                success=False,
                data=None,
                error=f"搜索失败: {str(e)}"
            )
