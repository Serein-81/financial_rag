import time
import numpy as np
from typing import List
from sqlalchemy import select
from sklearn.metrics.pairwise import cosine_similarity

from app.db import AsyncSessionLocal
from app.models import DocumentChunk
from app.models import Document
from app.services import embedding_service
from app.schemas import SearchResultItem
from app.models.search_log import SearchLog


class SearchService:
    async def search(self, query: str, top_k: int = 5) -> List[SearchResultItem]:
        start_time = time.time()
        results = []  # 先初始化为空列表

        try:
            # 1. 把用户的问题变成向量 (Query Embedding)
            query_vector = await embedding_service.get_embedding(query)
            if not query_vector:
                return []

            # 2. 从数据库取出所有切片 (Plan B: 内存计算模式)
            # 注意：生产环境数据量大时，这里必须用 pgvector 插件在数据库层做索引搜索
            async with AsyncSessionLocal() as db:
                # 联表查询：我们需要 Chunk 的向量，也需要 Document 的文件名
                stmt = select(DocumentChunk, Document).join(Document, DocumentChunk.document_id == Document.id)
                result = await db.execute(stmt)
                rows = result.all()

            if not rows:
                return []

            # 3. 内存计算相似度
            # 准备数据进行计算
            # rows 里的结构是 [(Chunk对象, Document对象), ...]
            chunk_vectors = []
            chunk_data = []
            for chunk, doc in rows:
                if chunk.embedding:
                    chunk_vectors.append(chunk.embedding)
                    chunk_data.append({"chunk": chunk, "doc": doc})

            if chunk_vectors:
                # 4. 使用 Numpy 批量计算余弦相似度 (Cosine Similarity)
                # 转换成 numpy 矩阵
                vec_matrix = np.array(chunk_vectors)
                q_vec = np.array([query_vector])

                # 计算相似度
                similarities = cosine_similarity(q_vec, vec_matrix)[0]

                # 排序取 Top K
                top_indices = similarities.argsort()[::-1][:top_k]

                # 组装结果
                for idx in top_indices:
                    score = float(similarities[idx])
                    data = chunk_data[idx]
                    if score < 0.2: continue # 过滤掉相关度太低的结果 (比如 0.3 以下通常就是瞎蒙的)

                    results.append(SearchResultItem(
                        chunk_id=str(data["chunk"].id),
                        document_id=str(data["doc"].id),
                        score=round(score, 4),
                        content=data["chunk"].content,
                        source_file=data["doc"].filename,
                        page_number=data["chunk"].meta_info.get("page_number")
                    ))

            return results

        finally:
            # 📝 【核心新增】记录日志
            # 无论上面代码是成功return了，还是报错了(报错时results为空)，这里都会执行
            latency = time.time() - start_time
            print(f"🔍 搜索完成，耗时: {latency:.4f}s，结果数: {len(results)}")

            # 启动一个异步任务去写库 (fire-and-forget)，或者直接在这里 await
            # 为了简单起见，我们直接在这里 await 写库
            await self._save_search_log(query, len(results), latency)

    # ➕ 【新增】内部辅助方法 (Protected)：写日志
    # 这里的逻辑只由 search 方法内部调用，不建议外部直接使用
    async def _save_search_log(self, query: str, count: int, latency: float):
        async with AsyncSessionLocal() as db:
            try:
                log = SearchLog(
                    query=query,
                    result_count=count,
                    latency=latency
                )
                db.add(log)
                await db.commit()
            except Exception as e:
                # 日记写失败不要影响主流程，打印个错误就行
                print(f"❌ 搜索日志保存失败: {e}")


search_service = SearchService()