import time
from typing import List, Optional
from sqlalchemy import text
from app.db import AsyncSessionLocal
from app.services import embedding_service
from app.schemas.chat import SearchResultItem
from app.models.search_log import SearchLog

class SearchService:
    async def search(
        self,
        query: str,
        top_k: int = 5,
        kb_id: str = None,
        score_threshold: float = 0.3
    ) -> List[SearchResultItem]:
        """
        核心搜索方法：修复了 pgvector 类型强转问题
        """
        start_time = time.time()
        results = []

        try:
            # 1. 获取问题向量
            query_vector = await embedding_service.get_embedding(query)
            if not query_vector:
                return []

            # 2. 总结意图识别
            actual_top_k = top_k
            if any(word in query for word in ["总结", "概括", "思想", "全文", "讲了什么"]):
                actual_top_k = max(top_k, 15)
                score_threshold = 0.25
                print(f"📈 检测到总结需求：自动调整参数")

            async with AsyncSessionLocal() as db:
                # 3. 改进 SQL：显式使用 CAST 函数代替 :: 缩写，避免与占位符冒号冲突
                sql = text("""
                    SELECT 
                        c.id, 
                        c.document_id, 
                        c.content, 
                        c.meta_info, 
                        d.filename,
                        (1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) AS similarity
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE (d.kb_id = :kb_id OR :kb_id IS NULL) 
                      AND (1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) >= :threshold
                    ORDER BY similarity DESC
                    LIMIT :limit
                """)

                # 确保 query_vector 是字符串格式
                vector_str = "[" + ",".join(map(str, query_vector)) + "]"

                params = {
                    "vector": vector_str,
                    "kb_id": kb_id,
                    "threshold": float(score_threshold),
                    "limit": int(actual_top_k)
                }

                db_res = await db.execute(sql, params)
                rows = db_res.all()

                for row in rows:
                    results.append(SearchResultItem(
                        chunk_id=str(row.id),
                        document_id=str(row.document_id),
                        score=round(row.similarity, 4),
                        content=row.content,
                        source_file=row.filename,
                        page_number=row.meta_info.get("page_number") if row.meta_info else None
                    ))

            return results

        except Exception as e:
            # 这里会捕获具体的 SQL 错误并打印
            print(f"❌ 检索过程发生错误: {e}")
            return []
        finally:
            latency = time.time() - start_time
            print(f"🔍 搜索完成 | 耗时: {latency:.4f}s | 命中片段: {len(results)}")
            await self._save_search_log(query, len(results), latency)

    async def _save_search_log(self, query: str, count: int, latency: float):
        async with AsyncSessionLocal() as db:
            try:
                log = SearchLog(query=query, result_count=count, latency=latency)
                db.add(log)
                await db.commit()
            except Exception as e:
                print(f"⚠️ 日志保存失败: {e}")

search_service = SearchService()