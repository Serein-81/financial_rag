import time
from typing import List, Optional, Dict, Any
from sqlalchemy import text, func
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

    async def keyword_search(self,
                           keywords: List[str],
                           kb_id: str = None,
                           top_k: int = 20,
                           exact_match: bool = False) -> List[SearchResultItem]:
        """
        关键词精确搜索
        
        Args:
            keywords: 关键词列表
            kb_id: 知识库ID
            top_k: 返回结果数量
            exact_match: 是否精确匹配
            
        Returns:
            搜索结果列表
        """
        start_time = time.time()
        results = []
        
        try:
            async with AsyncSessionLocal() as db:
                # 构建搜索条件
                where_clauses = []
                params = {"limit": int(top_k)}
                
                # 知识库过滤
                if kb_id:
                    where_clauses.append("d.kb_id = CAST(:kb_id AS UUID)")
                    params["kb_id"] = str(kb_id)
                
                # 关键词匹配条件
                if exact_match:
                    # 精确匹配：使用正则表达式
                    keyword_conditions = []
                    for i, keyword in enumerate(keywords):
                        keyword_conditions.append(f"c.content ~* :keyword_{i}")
                        params[f"keyword_{i}"] = f"\\b{keyword}\\b"
                    where_clauses.append(f"({' OR '.join(keyword_conditions)})")
                else:
                    # 模糊匹配：使用 ILIKE
                    keyword_conditions = []
                    for i, keyword in enumerate(keywords):
                        keyword_conditions.append(f"c.content ILIKE :keyword_{i}")
                        params[f"keyword_{i}"] = f"%{keyword}%"
                    where_clauses.append(f"({' OR '.join(keyword_conditions)})")
                
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                # 构建SQL查询
                sql = text(f"""
                    SELECT 
                        c.id,
                        c.document_id,
                        c.content,
                        c.meta_info,
                        d.filename,
                        -- 计算关键词匹配分数
                        (
                            {' + '.join([f"(CASE WHEN c.content ILIKE :keyword_{i} THEN 1 ELSE 0 END)" for i in range(len(keywords))])}
                        ) as keyword_score
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE {where_sql}
                    ORDER BY keyword_score DESC, c.created_at DESC
                    LIMIT :limit
                """)
                
                db_res = await db.execute(sql, params)
                rows = db_res.mappings().all()
                
                for row in rows:
                    meta = row["meta_info"] or {}
                    
                    results.append(SearchResultItem(
                        chunk_id=str(row["id"]),
                        document_id=str(row["document_id"]),
                        score=float(row["keyword_score"]),
                        content=row["content"],
                        source_file=row["filename"],
                        page_number=meta.get("page_number")
                    ))
            
            return results
            
        except Exception as e:
            print(f"❌ 关键词搜索失败: {e}")
            return []
        finally:
            latency = time.time() - start_time
            print(f"🔍 关键词搜索完成 | 耗时: {latency:.4f}s | 命中片段: {len(results)}")
            await self._save_search_log(f"keywords: {', '.join(keywords)}", len(results), latency)

    async def document_level_search(self,
                                  query: str,
                                  kb_id: str = None,
                                  top_k: int = 10) -> List[Dict[str, Any]]:
        """
        文档级别搜索，返回包含关键词的文档列表
        
        Args:
            query: 搜索查询
            kb_id: 知识库ID
            top_k: 返回文档数量
            
        Returns:
            文档摘要列表
        """
        start_time = time.time()
        results = []
        
        try:
            async with AsyncSessionLocal() as db:
                # 构建查询条件
                where_clauses = ["c.content ILIKE :query"]
                params = {
                    "query": f"%{query}%",
                    "limit": int(top_k)
                }
                
                if kb_id:
                    where_clauses.append("d.kb_id = CAST(:kb_id AS UUID)")
                    params["kb_id"] = str(kb_id)
                
                where_sql = " AND ".join(where_clauses)
                
                # 文档级聚合查询
                sql = text(f"""
                    SELECT 
                        d.id,
                        d.filename,
                        d.file_type,
                        d.file_size,
                        d.created_at,
                        COUNT(c.id) as match_count,
                        STRING_AGG(
                            SUBSTRING(c.content, 1, 100), 
                            ' | ' 
                            ORDER BY c.chunk_index
                        ) as preview,
                        AVG(c.chunk_index) as avg_position
                    FROM documents d
                    JOIN document_chunks c ON d.id = c.document_id
                    WHERE {where_sql}
                    GROUP BY d.id, d.filename, d.file_type, d.file_size, d.created_at
                    ORDER BY match_count DESC, avg_position ASC
                    LIMIT :limit
                """)
                
                db_res = await db.execute(sql, params)
                rows = db_res.mappings().all()
                
                for row in rows:
                    results.append({
                        "document_id": str(row["id"]),
                        "filename": row["filename"],
                        "file_type": row["file_type"],
                        "file_size": row["file_size"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                        "match_count": row["match_count"],
                        "preview": row["preview"],
                        "avg_position": float(row["avg_position"]) if row["avg_position"] else 0
                    })
            
            return results
            
        except Exception as e:
            print(f"❌ 文档级搜索失败: {e}")
            return []
        finally:
            latency = time.time() - start_time
            print(f"🔍 文档级搜索完成 | 耗时: {latency:.4f}s | 匹配文档: {len(results)}")
            await self._save_search_log(f"document_search: {query}", len(results), latency)

    async def search_statistics(self,
                              keyword: str,
                              kb_id: str = None) -> Dict[str, Any]:
        """
        搜索统计信息
        
        Args:
            keyword: 关键词
            kb_id: 知识库ID
            
        Returns:
            统计信息字典
        """
        start_time = time.time()
        
        try:
            async with AsyncSessionLocal() as db:
                # 构建查询条件
                where_clauses = ["c.content ILIKE :keyword"]
                params = {"keyword": f"%{keyword}%"}
                
                if kb_id:
                    where_clauses.append("d.kb_id = CAST(:kb_id AS UUID)")
                    params["kb_id"] = str(kb_id)
                
                where_sql = " AND ".join(where_clauses)
                
                # 统计查询
                sql = text(f"""
                    SELECT 
                        COUNT(DISTINCT d.id) as document_count,
                        COUNT(c.id) as chunk_count,
                        SUM(
                            array_length(
                                regexp_split_to_array(
                                    c.content, 
                                    :keyword_pattern, 
                                    'gi'
                                ), 
                                1
                            ) - 1
                        ) as total_occurrences,
                        AVG(LENGTH(c.content)) as avg_chunk_length,
                        STRING_AGG(DISTINCT d.file_type, ', ') as file_types
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE {where_sql}
                """)
                
                params["keyword_pattern"] = keyword
                
                db_res = await db.execute(sql, params)
                row = db_res.mappings().first()
                
                if row:
                    stats = {
                        "keyword": keyword,
                        "document_count": row["document_count"] or 0,
                        "chunk_count": row["chunk_count"] or 0,
                        "total_occurrences": row["total_occurrences"] or 0,
                        "avg_chunk_length": float(row["avg_chunk_length"]) if row["avg_chunk_length"] else 0,
                        "file_types": row["file_types"] or "",
                        "search_time": time.time() - start_time
                    }
                    
                    # 计算密度
                    if stats["chunk_count"] > 0:
                        stats["occurrence_density"] = stats["total_occurrences"] / stats["chunk_count"]
                    else:
                        stats["occurrence_density"] = 0
                    
                    return stats
                else:
                    return {
                        "keyword": keyword,
                        "document_count": 0,
                        "chunk_count": 0,
                        "total_occurrences": 0,
                        "avg_chunk_length": 0,
                        "file_types": "",
                        "occurrence_density": 0,
                        "search_time": time.time() - start_time
                    }
            
        except Exception as e:
            print(f"❌ 搜索统计失败: {e}")
            return {
                "keyword": keyword,
                "error": str(e),
                "search_time": time.time() - start_time
            }
        finally:
            latency = time.time() - start_time
            print(f"📊 搜索统计完成 | 耗时: {latency:.4f}s")

    async def _save_search_log(self, query: str, count: int, latency: float):
        async with AsyncSessionLocal() as db:
            try:
                log = SearchLog(query=query, result_count=count, latency=latency)
                db.add(log)
                await db.commit()
            except Exception as e:
                print(f"⚠️ 日志保存失败: {e}")


search_service = SearchService()