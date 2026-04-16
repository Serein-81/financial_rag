"""
租户隔离测试脚本
验证多租户隔离是否正常工作
"""

import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal as async_session_maker
import uuid


async def test_tenant_isolation():
    """测试租户隔离"""
    
    print("=" * 60)
    print("租户隔离测试")
    print("=" * 60)
    
    # 创建两个测试租户
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    
    print(f"\n📋 测试租户:")
    print(f"  租户 A: {tenant_a}")
    print(f"  租户 B: {tenant_b}")
    
    async with async_session_maker() as session:
        try:
            # 测试 1: 检查 tenant_id 字段是否存在
            print("\n[测试 1] 检查 tenant_id 字段...")
            result = await session.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'tenant_id'
            """))
            row = result.fetchone()
            if row:
                print(f"  ✅ users 表有 tenant_id 字段: {row[1]}")
            else:
                print("  ❌ users 表缺少 tenant_id 字段")
                return
            
            # 测试 2: 检查新表是否创建
            print("\n[测试 2] 检查新表...")
            tables = ['audit_tasks', 'audit_results', 'agent_collaborations', 'tenant_audit_logs']
            for table in tables:
                result = await session.execute(text(f"""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_name = '{table}'
                """))
                row = result.fetchone()
                if row:
                    print(f"  ✅ {table} 表已创建")
                else:
                    print(f"  ❌ {table} 表未创建")
            
            # 测试 3: 检查 RLS 是否启用
            print("\n[测试 3] 检查 Row-Level Security...")
            result = await session.execute(text("""
                SELECT tablename, rowsecurity 
                FROM pg_tables 
                WHERE tablename IN ('audit_tasks', 'audit_results', 'documents')
            """))
            rows = result.fetchall()
            for row in rows:
                status = "✅ 已启用" if row[1] else "❌ 未启用"
                print(f"  {status}: {row[0]}")
            
            # 测试 4: 检查租户隔离策略
            print("\n[测试 4] 检查租户隔离策略...")
            result = await session.execute(text("""
                SELECT tablename, policyname 
                FROM pg_policies 
                WHERE policyname = 'tenant_isolation_policy'
            """))
            rows = result.fetchall()
            if rows:
                for row in rows:
                    print(f"  ✅ {row[0]}: {row[1]}")
            else:
                print("  ❌ 未找到租户隔离策略")
            
            # 测试 5: 测试 session variable 设置
            print("\n[测试 5] 测试 session variable...")
            await session.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_a}'"))
            result = await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
            current_tenant = result.scalar()
            if current_tenant == tenant_a:
                print(f"  ✅ Session variable 设置成功: {current_tenant}")
            else:
                print(f"  ❌ Session variable 设置失败")
            
            await session.commit()
            
            print("\n" + "=" * 60)
            print("测试完成！")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            await session.rollback()


async def test_cross_tenant_access():
    """测试跨租户访问（需要先有测试数据）"""
    
    print("\n" + "=" * 60)
    print("跨租户访问测试")
    print("=" * 60)
    print("\n⚠️  此测试需要先创建测试数据")
    print("请在完成数据创建后运行此测试")
    

if __name__ == "__main__":
    asyncio.run(test_tenant_isolation())
