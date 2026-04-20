"""
财务工具测试 API

提供简单的接口测试财务智能体的数据库访问功能
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field
from app.services.financial_data_service import (
    FinancialDataQueryService,
    FinancialQueryParams,
)


router = APIRouter(prefix="/financial-tools-test", tags=["财务工具测试"])


class FinancialQueryRequest(BaseModel):
    """财务查询请求"""
    tenant_id: str = Field(description="租户ID")
    fiscal_year: Optional[int] = Field(default=2024, description="财务年度")
    period_type: Optional[str] = Field(default=None, description="周期类型: yearly/quarterly/monthly")
    data_status: Optional[str] = Field(default=None, description="数据状态: draft/confirmed/final")
    aggregate: bool = Field(default=True, description="是否聚合")
    limit: int = Field(default=100, ge=1, le=1000)


class FinancialOverviewRequest(BaseModel):
    """财务概览请求"""
    tenant_id: str = Field(description="租户ID")
    fiscal_year: Optional[int] = Field(default=None, description="财务年度")


class FinancialTrendRequest(BaseModel):
    """财务趋势请求"""
    tenant_id: str = Field(description="租户ID")
    fiscal_year: int = Field(description="财务年度")
    period_type: str = Field(default="yearly", description="周期类型")


class FinancialSearchRequest(BaseModel):
    """财务搜索请求"""
    tenant_id: str = Field(description="租户ID")
    query: str = Field(description="搜索关键词")
    limit: int = Field(default=20, ge=1, le=100)


@router.get("/health")
async def test_connection():
    """
    测试数据库连接
    
    验证财务数据服务能否正常连接数据库
    """
    try:
        service = await FinancialDataQueryService.create()
        return {
            "status": "success",
            "message": "数据库连接正常",
            "service": "FinancialDataQueryService"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")


@router.post("/query")
async def test_query_financial_data(
    request: FinancialQueryRequest,
):
    """测试 query_financial_data 工具"""
    """
    测试 query_financial_data 工具
    
    查询企业的详细财务数据记录
    """
    try:
        params = FinancialQueryParams(
            tenant_id=request.tenant_id,
            fiscal_year=request.fiscal_year,
            period_type=request.period_type,
            data_status=request.data_status,
            limit=request.limit,
            aggregate=request.aggregate,
        )
        
        service = await FinancialDataQueryService.create()
        result = await service.query_financial_data(params)
        
        if result.success:
            return {
                "status": "success",
                "tool": "query_financial_data",
                "data": result.data,
                "summary": result.summary.__dict__ if result.summary else None,
                "context_info": result.context_info,
                "query_params": result.query_params,
            }
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/overview")
async def test_get_financial_overview(
    request: FinancialOverviewRequest,
):
    """测试 get_financial_overview 工具"""
    try:
        service = await FinancialDataQueryService.create()
        
        # 直接构建查询获取概览
        from app.models.user_financial_data import UserFinancialData
        from sqlalchemy import select, func, and_
        
        conditions = [
            UserFinancialData.tenant_id == request.tenant_id,
            UserFinancialData.is_current.is_(True)
        ]
        
        if request.fiscal_year:
            conditions.append(UserFinancialData.fiscal_year == request.fiscal_year)
        
        # 聚合查询
        agg_query = select(
            func.count().label('total_records'),
            func.sum(UserFinancialData.total_revenue).label('total_revenue'),
            func.sum(UserFinancialData.total_expenses).label('total_expenses'),
            func.avg(UserFinancialData.vat_rate).label('avg_vat_rate'),
        ).where(and_(*conditions))
        
        result = await service.db.execute(agg_query)
        row = result.one()
        
        total_revenue = float(row.total_revenue or 0)
        total_expenses = float(row.total_expenses or 0)
        total_profit = total_revenue - total_expenses
        profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        return {
            "status": "success",
            "tool": "get_financial_overview",
            "overview": {
                "total_records": row.total_records or 0,
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "total_profit": total_profit,
                "profit_margin": round(profit_margin, 2),
                "avg_vat_rate": float(row.avg_vat_rate or 0) if row.avg_vat_rate else 0,
                "fiscal_year": request.fiscal_year,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取概览失败: {str(e)}")


@router.post("/trend")
async def test_get_financial_trend(
    request: FinancialTrendRequest,
):
    """测试 get_financial_trend 工具"""
    try:
        from app.services.financial_data_service import FinancialTrendService
        
        service = await FinancialDataQueryService.create()
        trend_service = FinancialTrendService(service.db)
        
        result = await trend_service.get_trend_data(
            tenant_id=request.tenant_id,
            fiscal_year=request.fiscal_year,
            period_type=request.period_type,
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取趋势失败: {str(e)}")


@router.post("/search")
async def test_search_financial_data(
    request: FinancialSearchRequest,
):
    """测试 search_financial_data 工具"""
    try:
        service = await FinancialDataQueryService.create()
        
        result = await service.search_financial_data(
            tenant_id=request.tenant_id,
            query=request.query,
            limit=request.limit,
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/stats")
async def get_financial_stats(
    tenant_id: str = Query(description="租户ID"),
):
    """获取财务数据统计信息"""
    try:
        from app.models.user_financial_data import UserFinancialData
        from sqlalchemy import select, func, distinct
        
        service = await FinancialDataQueryService.create()
        
        # 统计不同年份
        years_query = select(
            func.count(distinct(UserFinancialData.fiscal_year)).label('year_count'),
            func.min(UserFinancialData.fiscal_year).label('earliest_year'),
            func.max(UserFinancialData.fiscal_year).label('latest_year'),
        ).where(UserFinancialData.tenant_id == tenant_id)
        
        years_result = await service.db.execute(years_query)
        years_row = years_result.one()
        
        # 统计记录数
        count_query = select(
            func.count().label('total_records')
        ).where(UserFinancialData.tenant_id == tenant_id)
        
        count_result = await service.db.execute(count_query)
        count_row = count_result.one()
        
        return {
            "status": "success",
            "tenant_id": tenant_id,
            "stats": {
                "total_records": count_row.total_records or 0,
                "year_count": years_row.year_count or 0,
                "earliest_year": years_row.earliest_year,
                "latest_year": years_row.latest_year,
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")
