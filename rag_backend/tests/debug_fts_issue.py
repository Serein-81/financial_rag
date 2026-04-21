"""
全文检索问题诊断脚本

诊断查询返回 0 条结果的原因
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def diagnose_fts_issue():
    """诊断全文检索问题"""
    
    print("=" * 70)
    print("全文检索问题诊断")
    print("=" * 70)
    
    try:
        from app.db import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as db:
            # 1. 检查表结构和数据
            print("\n1️⃣ 检查表结构和数据...")
            
            result = await db.execute(text("""
                SELECT 
                    COUNT(*) as total_count,
                    COUNT(fts_vector) as fts_count,
                    COUNT(CASE WHEN fts_vector IS NOT NULL THEN 1 END) as valid_fts
                FROM document_chunks
            """))
            row = result.fetchone()
            print(f"   总 chunks 数: {row[0]}")
            print(f"   fts_vector 非空数: {row[2]}")
            
            # 2. 查看数据样例
            print("\n2️⃣ 查看数据样例（tenant_id）...")
            
            result = await db.execute(text("""
                SELECT DISTINCT tenant_id, COUNT(*) 
                FROM document_chunks 
                GROUP BY tenant_id
            """))
            tenants = result.fetchall()
            
            if tenants:
                print(f"   发现 {len(tenants)} 个租户:")
                for tenant_id, count in tenants:
                    print(f"   - {tenant_id}: {count} 条")
            else:
                print("   ⚠️ 没有数据！")
            
            # 3. 查看内容样例
            print("\n3️⃣ 查看内容样例...")
            
            result = await db.execute(text("""
                SELECT id, content, tenant_id
                FROM document_chunks
                LIMIT 3
            """))
            samples = result.fetchall()
            
            if samples:
                for idx, (chunk_id, content, tenant_id) in enumerate(samples, 1):
                    preview = content[:100] if content and len(content) > 100 else content
                    print(f"\n   样例 {idx}:")
                    print(f"   ID: {chunk_id}")
                    print(f"   Tenant: {tenant_id}")
                    print(f"   内容: {preview}...")
            else:
                print("   ⚠️ 没有数据！")
            
            # 4. 测试分词效果
            print("\n4️⃣ 测试分词效果...")
            
            test_words = ["税务", "企业", "所得税", "筹划"]
            
            for word in test_words:
                result = await db.execute(text("""
                    SELECT 
                        to_tsvector('pg_catalog.simple', :word) as ts_vector
                """), {"word": word})
                row = result.fetchone()
                print(f"   '{word}' -> {row[0]}")
            
            # 5. 测试全文检索
            print("\n5️⃣ 测试全文检索（不使用租户过滤）...")
            
            queries = [
                "税务",
                "企业",
                "所得税",
                "税务筹划",
                "企业所得税"
            ]
            
            for query in queries:
                result = await db.execute(text("""
                    SELECT COUNT(*) as match_count
                    FROM document_chunks
                    WHERE to_tsvector('pg_catalog.simple', content) 
                          @@ to_tsquery('pg_catalog.simple', :query)
                """), {"query": query})
                row = result.fetchone()
                match_count = row[0] if row else 0
                
                print(f"\n   查询: '{query}'")
                print(f"   匹配数: {match_count}")
            
            # 6. 测试带 tenant_id 的查询
            print("\n6️⃣ 测试带租户过滤的查询...")
            
            for tenant_id, count in tenants[:3]:  # 只测试前3个租户
                print(f"\n   租户: {tenant_id} ({count} 条)")
                
                for query in ["税务", "企业"]:
                    result = await db.execute(text("""
                        SELECT COUNT(*)
                        FROM document_chunks
                        WHERE tenant_id = :tenant_id
                        AND to_tsvector('pg_catalog.simple', content) 
                            @@ to_tsquery('pg_catalog.simple', :query)
                    """), {"tenant_id": tenant_id, "query": query})
                    match_count = result.scalar()
                    print(f"   - '{query}': {match_count} 条匹配")
            
            # 7. 查看 fts_vector 的实际内容
            print("\n7️⃣ 查看 fts_vector 实际内容...")
            
            result = await db.execute(text("""
                SELECT 
                    id,
                    fts_vector,
                    left(content, 50) as content_preview
                FROM document_chunks
                WHERE fts_vector IS NOT NULL
                LIMIT 3
            """))
            samples = result.fetchall()
            
            if samples:
                for idx, (chunk_id, fts_vector, content) in enumerate(samples, 1):
                    print(f"\n   样例 {idx}:")
                    print(f"   ID: {chunk_id}")
                    print(f"   fts_vector: {fts_vector}")
                    print(f"   content: {content}...")
            else:
                print("   ⚠️ fts_vector 全部为空！")
            
            # 8. 建议
            print("\n" + "=" * 70)
            print("📋 问题诊断总结")
            print("=" * 70)
            
            print("""
可能的问题和解决方案：

1. 【问题】fts_vector 为空
   【解决】执行以下 SQL：
   UPDATE document_chunks 
   SET fts_vector = to_tsvector('pg_catalog.simple', COALESCE(content, ''))
   WHERE fts_vector IS NULL;

2. 【问题】tenant_id 不匹配
   【解决】在测试中使用正确的 tenant_id

3. 【问题】测试关键词不存在
   【解决】查看实际数据内容，使用存在的关键词测试

4. 【问题】分词效果不佳（中文按字符分词）
   【解决】这是 pg_catalog.simple 的正常行为，
          对于中文需要用更长的词组来查询

5. 【性能】78-108ms 已经很优秀了！
   【确认】GIN 索引已正常工作
""")
            
    except Exception as e:
        print(f"\n❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(diagnose_fts_issue())
