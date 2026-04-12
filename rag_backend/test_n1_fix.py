#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
N+1 问题修复测试脚本

用于验证 SystemLog 查询中的 N+1 问题是否已修复
通过监控 SQL 查询次数来确认性能优化效果
"""

import asyncio
import sys
import os
import time
import logging
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置 SQL 日志
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
sql_logger = logging.getLogger('sqlalchemy.engine')
sql_logger.setLevel(logging.INFO)


class QueryCounter(logging.Handler):
    """自定义日志处理器，用于统计 SQL 查询次数"""
    def __init__(self):
        super().__init__()
        self.query_count = 0
        self.queries = []
    
    def emit(self, record):
        if 'SELECT' in record.getMessage():
            self.query_count += 1
            self.queries.append(record.getMessage()[:100])
    
    def reset(self):
        self.query_count = 0
        self.queries = []


async def test_n1_fix():
    """测试 N+1 问题修复"""
    print("\n" + "="*80)
    print("N+1 问题修复验证测试")
    print("="*80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 添加查询计数器
    counter = QueryCounter()
    sql_logger.addHandler(counter)
    
    # 导入服务
    from app.services.log_service import log_service
    
    # 测试场景 1：查询 10 条日志
    print("\n[测试场景 1] 查询 10 条系统日志")
    print("-" * 80)
    counter.reset()
    
    start_time = time.time()
    try:
        result = await log_service.get_system_logs(
            user_id=None,
            is_admin=True,
            limit=10
        )
        elapsed_time = time.time() - start_time
        
        print(f"[OK] 查询成功！")
        print(f"   - 返回日志数量: {len(result['logs'])}")
        print(f"   - 总记录数: {result['total']}")
        print(f"   - 查询耗时: {elapsed_time*1000:.2f}ms")
        print(f"   - SQL 查询次数: {counter.query_count}")
        
        # 检查返回的日志是否包含租户信息
        logs_with_tenant = [log for log in result['logs'] if log.get('tenant_name')]
        print(f"   - 包含租户信息的日志: {len(logs_with_tenant)}/{len(result['logs'])}")
        
        # 性能评估
        if counter.query_count <= 5:
            print(f"\n[OK] 查询次数正常！未检测到 N+1 问题")
            print(f"   预期查询次数: 3-4 次（system_logs + users + tenants + count）")
            print(f"   实际查询次数: {counter.query_count} 次")
        else:
            print(f"\n[WARN] 查询次数过多！可能存在 N+1 问题")
            print(f"   预期查询次数: 3-4 次")
            print(f"   实际查询次数: {counter.query_count} 次")
        
    except Exception as e:
        print(f"[ERROR] 查询失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试场景 2：查询 100 条日志（更明显的性能差异）
    print("\n\n[测试场景 2] 查询 100 条系统日志")
    print("-" * 80)
    counter.reset()
    
    start_time = time.time()
    try:
        result = await log_service.get_system_logs(
            user_id=None,
            is_admin=True,
            limit=100
        )
        elapsed_time = time.time() - start_time
        
        print(f"[OK] 查询成功！")
        print(f"   - 返回日志数量: {len(result['logs'])}")
        print(f"   - 总记录数: {result['total']}")
        print(f"   - 查询耗时: {elapsed_time*1000:.2f}ms")
        print(f"   - SQL 查询次数: {counter.query_count}")
        
        # 检查返回的日志是否包含租户信息
        logs_with_tenant = [log for log in result['logs'] if log.get('tenant_name')]
        print(f"   - 包含租户信息的日志: {len(logs_with_tenant)}/{len(result['logs'])}")
        
        # 性能评估
        if counter.query_count <= 5:
            print(f"\n[OK] 查询次数正常！未检测到 N+1 问题")
            print(f"   预期查询次数: 3-4 次（system_logs + users + tenants + count）")
            print(f"   实际查询次数: {counter.query_count} 次")
        else:
            print(f"\n[WARN] 查询次数过多！可能存在 N+1 问题")
            print(f"   预期查询次数: 3-4 次")
            print(f"   实际查询次数: {counter.query_count} 次")
        
    except Exception as e:
        print(f"[ERROR] 查询失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    print("\n【N+1 问题特征】")
    print("  如果存在 N+1 问题，查询 100 条日志会产生 200+ 次 SQL 查询：")
    print("    - 1 次: SELECT system_logs")
    print("    - 100 次: SELECT users (每条日志一次)")
    print("    - 100 次: SELECT tenants (每条日志一次)")
    print()
    print("【优化后特征】")
    print("  修复后应该只有 3-4 次 SQL 查询：")
    print("    - 1 次: SELECT system_logs")
    print("    - 1 次: SELECT users (批量查询)")
    print("    - 1 次: SELECT tenants (批量查询)")
    print("    - 1 次: SELECT COUNT")
    print()
    print("【性能提升】")
    print("  理论性能提升: 200次查询 -> 4次查询 = 50倍提升!")
    print("  实际性能提升取决于网络延迟和数据库性能")
    print("\n" + "="*80)
    
    # 清理
    sql_logger.removeHandler(counter)


if __name__ == "__main__":
    print("\n==> 启动 N+1 问题修复测试...")
    print("提示: 本测试会监控 SQL 查询次数，请查看上方的 SQL 查询统计")
    print()
    
    asyncio.run(test_n1_fix())
