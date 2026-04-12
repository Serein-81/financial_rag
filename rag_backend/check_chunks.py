"""
检查chunks内容和搜索结果
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db import AsyncSessionLocal


async def check_chunks():
    kb_id = "e94afd3e-c877-49fe-a5df-1269f4b84aa0"
    tenant_id = "test_tenant_001"
    user_id = "8cbd5945-6712-40ce-9e35-e30083ef93e8"

    print("=" * 80)
    print("检查Chunks内容")
    print("=" * 80)

    async with AsyncSessionLocal() as db:
        # 检查文档中包含"后端"的chunks
        print("\n[1] 包含'后端'的chunks:")
        result = await db.execute(text("""
            SELECT c.id, c.content, d.filename
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            JOIN knowledge_bases kb ON d.kb_id = kb.id
            WHERE d.tenant_id = :tenant_id
            AND d.kb_id = CAST(:kb_id AS UUID)
            AND (
                UPPER(kb.visibility) = 'ENTERPRISE'
                OR (UPPER(kb.visibility) = 'PRIVATE' AND kb.user_id = CAST(:user_id AS UUID))
            )
            AND (
                UPPER(d.visibility) = 'PUBLIC'
                OR (UPPER(d.visibility) = 'PRIVATE' AND d.user_id = CAST(:user_id AS UUID))
            )
            AND c.content ILIKE :pattern
        """), {"tenant_id": tenant_id, "kb_id": kb_id, "user_id": user_id, "pattern": "%后端%"})
        rows = result.mappings().all()
        print(f"  找到 {len(rows)} 个包含'后端'的chunks")
        for i, row in enumerate(rows):
            print(f"\n  --- Chunk {i+1} ---")
            print(f"  文件: {row['filename']}")
            print(f"  内容: {row['content'][:500]}...")
            print()

        # 检查文档中包含"功能"的chunks
        print("\n" + "=" * 80)
        print("[2] 包含'功能'的chunks:")
        result = await db.execute(text("""
            SELECT c.id, c.content, d.filename
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            JOIN knowledge_bases kb ON d.kb_id = kb.id
            WHERE d.tenant_id = :tenant_id
            AND d.kb_id = CAST(:kb_id AS UUID)
            AND (
                UPPER(kb.visibility) = 'ENTERPRISE'
                OR (UPPER(kb.visibility) = 'PRIVATE' AND kb.user_id = CAST(:user_id AS UUID))
            )
            AND (
