"""
只测试聚合查询
"""

import asyncio
from app.db.session import AsyncSessionLocal
from app.services.financial_data_service import FinancialDataQueryService, FinancialQueryParams


async def test_query_with_aggregation():
    """测试带聚合的查询"""
    async with AsyncSessionLocal() as session:
        service = FinancialDataQueryService(session)
        params = FinancialQueryParams(
            tenant_id='default',
            fiscal_year=2024,
            aggregate=True
        )
        result = await service.query_financial_data(params)
        
        print("=" * 60)
        print("财务数据查询结果 (带聚合)")
        print("=" * 60)
        print(f"Success: {result.success}")
        
        if result.success:
            print(f"Records: {len(result.data) if result.data else 0}")
            
            if result.context_info:
                print("\n[Context Info]")
                print(f"  Total count: {result.context_info.get('total_count', 'N/A')}")
                print(f"  Returned count: {result.context_info.get('returned_count', 'N/A')}")
            
            if result.summary:
                print("\n[Summary]")
                print(f"  Total Revenue: {result.summary.total_revenue:,.2f}")
                print(f"  Total Expenses: {result.summary.total_expenses:,.2f}")
                print(f"  Net Profit: {result.summary.total_profit:,.2f}")
                if result.summary.avg_profit_margin:
                    print(f"  Avg Profit Margin: {result.summary.avg_profit_margin:.2%}")
                if result.summary.total_vat:
                    print(f"  Total VAT: {result.summary.total_vat:,.2f}")
                print(f"  Period Types: {result.summary.period_types}")
                print(f"  Fiscal Years: {result.summary.fiscal_years}")
            else:
                print("\n[No summary available]")
        else:
            print(f"Error: {result.error}")


if __name__ == "__main__":
    asyncio.run(test_query_with_aggregation())
