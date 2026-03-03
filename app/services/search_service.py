import time
from typing import List, Optional
from sqlalchemy import text
from app.db import AsyncSessionLocal
from app.services.embedding_service import embedding_service
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
        核心搜索方法：修复了 pgvector 类型强转问题及 UUID 类型兼容问题
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
                print(f"📈 检测到总结需求：自动调整参数 (top_k={actual_top_k}, threshold={score_threshold})")

            async with AsyncSessionLocal() as db:
                # 3. 动态组装 WHERE 条件 (避免 :kb_id IS NULL 导致的数据库类型推断报错)
                where_clauses = ["(1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) >= :threshold"]
                params = {
                    "vector": "[" + ",".join(map(str, query_vector)) + "]",  # 确保是 pgvector 认识的字符串格式
                    "threshold": float(score_threshold),
                    "limit": int(actual_top_k)
                }

                if kb_id:
                    # 🌟 核心修复：显式 CAST(:kb_id AS UUID)，防止 asyncpg 报类型不匹配错误
                    where_clauses.append("d.kb_id = CAST(:kb_id AS UUID)")
                    params["kb_id"] = str(kb_id)

                where_sql = " AND ".join(where_clauses)

                # 4. 改进 SQL：动态拼接 WHERE
                sql = text(f"""
                    SELECT 
                        c.id, 
                        c.document_id, 
                        c.content, 
                        c.meta_info, 
                        d.filename,
                        (1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) AS similarity
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE {where_sql}
                    ORDER BY similarity DESC
                    LIMIT :limit
                """)

                db_res = await db.execute(sql, params)
                # 使用 mappings() 返回字典形式，比直接用 tuple 的兼容性更好，杜绝 row.id 报错
                rows = db_res.mappings().all()

                for row in rows:
                    # 容错处理：获取 meta_info 时防空
                    meta = row["meta_info"] or {}

                    results.append(SearchResultItem(
                        chunk_id=str(row["id"]),
                        document_id=str(row["document_id"]),
                        score=round(row["similarity"], 4),
                        content=row["content"],
                        source_file=row["filename"],
                        page_number=meta.get("page_number")
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