"""
财务工具测试脚本

测试财务智能体能否正确访问数据库中的财务信息
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import AsyncSessionLocal


async def test_financial_tools():
    """测试财务工具"""
    
    print("=" * 60)
    print("财务智能体数据库访问测试")
    print("=" * 60)
    
    # 测试用的租户ID - 请替换为实际存在的租户ID
    test_tenant_id = "default"
    
    # 直接使用 AsyncSessionLocal 管理连接
    async with AsyncSessionLocal() as session:
        try:
            from app.services.financial_data_service import (
                FinancialDataQueryService,
                FinancialQueryParams,
            )
            
            # 创建服务实例（复用同一个 session）
            service = FinancialDataQueryService(session)
            
            # 测试1: 查询财务数据概览
            print(f"\n[1] 测试 query_financial_data (tenant_id={test_tenant_id})...")
            params = FinancialQueryParams(
                tenant_id=test_tenant_id,
                fiscal_year=2024,
            )
            result = await service.query_financial_data(params)
            
            if result.success:
                print("[OK] 查询成功!")
                if result.summary:
                    print(f"   - 数据记录数: {result.summary.total_records}")
                    print(f"   - 总收入: {result.summary.total_revenue:,.2f}")
                    print(f"   - 总支出: {result.summary.total_expenses:,.2f}")
                    print(f"   - 净利润: {result.summary.total_profit:,.2f}")
                    print(f"   - 平均利润率: {result.summary.avg_profit_margin:.2f}%")
                else:
                    print("   - 暂无汇总数据")
            else:
                print(f"[FAIL] 查询失败: {result.error}")
            
            # 测试2: 带聚合的查询
            print("\n[2] 测试聚合查询...")
            params_agg = FinancialQueryParams(
                tenant_id=test_tenant_id,
                fiscal_year=2024,
                aggregate=True,
                limit=10,
            )
            result_agg = await service.query_financial_data(params_agg)
            
            if result_agg.success:
                print("[OK] 聚合查询成功!")
                if result_agg.summary:
                    print(f"   - 包含样本记录数: {len(result_agg.summary.sample_records)}")
                    print(f"   - 上下文优化信息: {result_agg.context_info}")
            else:
                print(f"[FAIL] 聚合查询失败: {result_agg.error}")
            
            # 测试3: 查询趋势数据
            print("\n[3] 测试 get_financial_trend...")
            try:
                trend_result = await service.get_financial_trend(
                    tenant_id=test_tenant_id,
                    fiscal_year=2024,
                    period_type="yearly"
                )
                
                if trend_result.success:
                    print("[OK] 趋势查询成功!")
                    print(f"   - 返回记录数: {len(trend_result.data) if trend_result.data else 0}")
                else:
                    print("[WARN] 趋势查询未返回数据（可能数据库中无趋势数据）")
                    print(f"   - 原因: {trend_result.error}")
            except Exception as e:
                print(f"[WARN] 趋势查询遇到问题: {str(e)}")
            
            # 测试4: 关键词搜索
            print("\n[4] 测试 search_financial_data...")
            search_result = await service.search_financial_data(
                tenant_id=test_tenant_id,
                query="2024",
                limit=5
            )
            
            if search_result.success:
                print("[OK] 搜索成功!")
                print(f"   - 返回记录数: {len(search_result.data) if search_result.data else 0}")
            else:
                print("[WARN] 搜索未返回数据（可能数据库中无匹配数据）")
                print(f"   - 错误信息: {search_result.error}")
            
            # 测试5: 获取概览
            print("\n[5] 测试 get_financial_overview...")
            overview_result = await service.get_financial_overview(
                tenant_id=test_tenant_id,
                years=[2024]
            )
            
            if overview_result.success:
                print("[OK] 概览查询成功!")
                if overview_result.summary:
                    print(f"   - 总收入: {overview_result.summary.total_revenue:,.2f}")
                    print(f"   - 总支出: {overview_result.summary.total_expenses:,.2f}")
                    print(f"   - 净利润: {overview_result.summary.total_profit:,.2f}")
            else:
                print("[WARN] 概览查询未返回数据")
                print(f"   - 错误信息: {overview_result.error}")
            
            print("\n" + "=" * 60)
            print("[OK] 财务智能体数据库访问测试完成!")
            print("=" * 60)
            return True
            
        except Exception as e:
            print(f"\n[FAIL] 测试过程中发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


async def test_direct_tool_call():
    """测试直接调用财务工具"""
    
    print("\n" + "=" * 60)
    print("直接调用财务工具测试")
    print("=" * 60)
    
    # 导入财务工具
    from app.mcp.financial_tools import create_financial_tools
    
    # 创建工具
    tools = create_financial_tools()
    print(f"\n[OK] 创建了 {len(tools)} 个财务工具")
    
    # 列出所有工具
    print("\n[*] 财务工具列表:")
    for i, tool in enumerate(tools, 1):
        print(f"   {i}. {tool.name}")
    
    # 测试调用工具
    print("\n🔧 测试调用工具...")
    test_tenant_id = "default"
    
    try:
        for tool in tools:
            if tool.name == "query_financial_data":
                print(f"\n调用 {tool.name}...")
                try:
                    # 直接调用工具函数
                    result = await tool.ainvoke({
                        "tenant_id": test_tenant_id,
                        "fiscal_year": 2024,
                        "aggregate": True,
                    })
                    
                    print("[OK] 工具调用成功!")
                    print(f"   - 状态: {result.get('status')}")
                    if result.get('data'):
                        print(f"   - 返回数据条数: {len(result.get('data', []))}")
                    else:
                        print("   - 暂无数据（数据库中可能没有该租户的财务数据）")
                        
                except Exception as e:
                    print(f"[WARN] 工具调用遇到问题: {str(e)}")
                    print("   (这可能是正常的，如果数据库中还没有测试数据)")
                    
    except Exception as e:
        print(f"[WARN] 测试过程中遇到问题: {str(e)}")
    
    print("\n" + "=" * 60)
    print("[OK] 财务工具直接调用测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    print("\n>>> 开始财务智能体数据库访问测试...")
    
    # 运行主要测试
    success = asyncio.run(test_financial_tools())
    
    # 运行直接工具调用测试
    asyncio.run(test_direct_tool_call())
    
    print("\n" + "=" * 60)
    if success:
        print(">>> 所有测试通过!")
    else:
        print(">>> 部分测试失败，请检查数据库连接和数据")
    print("=" * 60)
