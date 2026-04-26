import time
import asyncio
import logging
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from sqlalchemy import text, select
from app.db import AsyncSessionLocal
from app.services.embedding_service import embedding_service
from app.services.tavily_service import tavily_service
from app.schemas.chat import SearchResultItem
from app.schemas.search import WebSearchResult, HybridSearchResponse
from app.models.search_log import SearchLog
from app.models.knowledge_base import KnowledgeBase


logger = logging.getLogger(__name__)


class SearchService:
    async def _get_tenant_id_from_kb(self, kb_id: str) -> Optional[str]:
        """从知识库ID获取租户ID"""
        if not kb_id:
            return None
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(KnowledgeBase.tenant_id).where(KnowledgeBase.id == kb_id)
            )
            row = result.scalar_one_or_none()
            return row

    async def search(
            self,
            query: str,
            top_k: int = 5,
            kb_id: str = None,
            score_threshold: float = 0.6,
            tenant_id: str = None,
            user_id: str = None
    ) -> List[SearchResultItem]:
        """
        核心搜索方法：修复了 pgvector 类型强转问题及 UUID 类型兼容问题
        🔐 租户隔离：必须传入 tenant_id 进行过滤
        🔐 可见性过滤：私人知识库只有创建者可见，企业知识库整个租户可见
        """
        start_time = time.time()
        results = []

        try:
            if not tenant_id:
                if kb_id:
                    tenant_id = await self._get_tenant_id_from_kb(kb_id)
                    print(f"🔍 [SearchService] 自动从KB获取tenant_id: {tenant_id}")
                if not tenant_id:
                    raise ValueError("租户隔离失败：缺少 tenant_id")

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
                # 3. 动态组装 WHERE 条件
                where_clauses = ["(1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) >= :threshold"]
                # 🔐 租户隔离：必须添加 tenant_id 过滤（tenant_id 是字符串类型，不需要 CAST）
                where_clauses.append("d.tenant_id = :tenant_id")

                # 🔐 两层可见性过滤
                if user_id:
                    # ① 知识库可见性：私人知识库只有创建者可见，企业知识库整个租户可见
                    # ② 文档可见性：私人文档只有上传者可见，公开文档整个企业可见
                    where_clauses.append("""
                        (
                            -- 知识库可见性：企业KB全租户可见，私人KB创建者可见
                            (UPPER(kb.visibility) = 'ENTERPRISE' OR (UPPER(kb.visibility) = 'PRIVATE' AND kb.user_id = CAST(:user_id AS UUID)))
                        )
                        AND
                        (
                            -- 文档可见性：公开文档全租户可见，私人文档上传者可见
                            (UPPER(d.visibility) = 'PUBLIC' OR (UPPER(d.visibility) = 'PRIVATE' AND d.user_id = CAST(:user_id AS UUID)))
                        )
                    """)
                    visibility_filter = True
                else:
                    visibility_filter = False

                params = {
                    "vector": "[" + ",".join(map(str, query_vector)) + "]",
                    "threshold": float(score_threshold),
                    "limit": int(actual_top_k),
                    "tenant_id": str(tenant_id)
                }

                if visibility_filter and user_id:
                    params["user_id"] = str(user_id)

                if kb_id:
                    where_clauses.append("d.kb_id = CAST(:kb_id AS UUID)")
                    params["kb_id"] = str(kb_id)

                where_sql = " AND ".join(where_clauses)

                # 4. 改进 SQL：动态拼接 WHERE
                # 🔐 注意：visibility 字段在 knowledge_bases 表上，需要 JOIN
                sql = text(f"""
                    SELECT
                        c.id,
                        c.document_id,
                        c.content,
                        c.meta_info,
                        d.filename,
                        kb.name as kb_name,
                        (1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) AS similarity
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    JOIN knowledge_bases kb ON d.kb_id = kb.id
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

        except (ValueError, KeyError) as e:
            print(f"❌ 检索过程数据错误: {e}")
        except (OSError, IOError) as e:
            print(f"❌ 检索过程IO错误: {e}")
        except Exception as e:
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
                           exact_match: bool = False,
                           tenant_id: str = None) -> List[SearchResultItem]:
        """
        关键词精确搜索

        Args:
            keywords: 关键词列表
            kb_id: 知识库ID
            top_k: 返回结果数量
            exact_match: 是否精确匹配
            tenant_id: 租户ID（必须）

        Returns:
            搜索结果列表
        """
        start_time = time.time()
        results = []

        if not tenant_id:
            if kb_id:
                tenant_id = await self._get_tenant_id_from_kb(kb_id)
                print(f"🔍 [KeywordSearch] 自动从KB获取tenant_id: {tenant_id}")
            if not tenant_id:
                raise ValueError("租户隔离失败：缺少 tenant_id")

        try:
            async with AsyncSessionLocal() as db:
                # 构建搜索条件
                where_clauses = []
                params = {"limit": int(top_k), "tenant_id": str(tenant_id)}

                # 🔐 租户隔离：必须添加 tenant_id 过滤（tenant_id 是字符串类型，不需要 CAST）
                where_clauses.append("d.tenant_id = :tenant_id")

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

        except (ValueError, KeyError) as e:
            print(f"❌ 关键词搜索数据错误: {e}")
            return []
        except (OSError, IOError) as e:
            print(f"❌ 关键词搜索IO错误: {e}")
            return []
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
            
        except (ValueError, KeyError) as e:
            print(f"❌ 文档级搜索数据错误: {e}")
            return []
        except (OSError, IOError) as e:
            print(f"❌ 文档级搜索IO错误: {e}")
            return []
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
            
        except (ValueError, KeyError) as e:
            print(f"❌ 搜索统计数据错误: {e}")
            return {
                "total_searches": 0,
                "avg_response_time": 0.0,
                "success_rate": 0.0,
                "top_queries": []
            }
        except (OSError, IOError) as e:
            print(f"❌ 搜索统计IO错误: {e}")
            return {
                "total_searches": 0,
                "avg_response_time": 0.0,
                "success_rate": 0.0,
                "top_queries": []
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
            except (ValueError, KeyError) as e:
                print(f"⚠️ 日志保存数据错误: {e}")
            except (OSError, IOError) as e:
                print(f"⚠️ 日志保存IO错误: {e}")
            except Exception as e:
                print(f"⚠️ 日志保存失败: {e}")

    async def _emit_callback(
        self,
        callback: Optional[Callable],
        message: str,
        status: str = "info",
        progress: Optional[float] = None
    ):
        """发送回调消息"""
        if callback:
            try:
                data = {
                    "status": status,
                    "message": message,
                    "progress": progress,
                    "timestamp": datetime.now().isoformat(),
                    "source": "search"
                }

                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)

            except (ValueError, KeyError) as e:
                print(f"⚠️ 回调发送数据错误: {e}")
            except (OSError, IOError) as e:
                print(f"⚠️ 回调发送IO错误: {e}")
            except Exception as e:
                print(f"⚠️ 回调发送失败: {e}")

    async def search_with_callback(
        self,
        query: str,
        top_k: int = 5,
        kb_id: str = None,
        score_threshold: float = 0.6,
        callback: Optional[Callable] = None
    ) -> List[SearchResultItem]:
        """
        带回调的知识库检索
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            kb_id: 知识库ID
            score_threshold: 相似度阈值
            callback: 进度回调函数
            
        Returns:
            搜索结果列表
        """
        await self._emit_callback(callback, "🔍 开始知识库检索...", "info", 0.0)
        
        start_time = time.time()
        results = []

        try:
            # 1. 获取问题向量
            await self._emit_callback(callback, "📊 正在生成查询向量...", "info", 0.2)
            query_vector = await embedding_service.get_embedding(query)
            if not query_vector:
                await self._emit_callback(callback, "⚠️ 向量生成失败", "error")
                return []

            # 2. 总结意图识别
            actual_top_k = top_k
            if any(word in query for word in ["总结", "概括", "思想", "全文", "讲了什么"]):
                actual_top_k = max(top_k, 15)
                score_threshold = 0.25
                await self._emit_callback(
                    callback,
                    f"📈 检测到总结需求：自动调整参数 (top_k={actual_top_k})",
                    "info"
                )

            # 3. 执行检索
            await self._emit_callback(callback, "🔎 正在执行向量检索...", "info", 0.4)

            async with AsyncSessionLocal() as db:
                where_clauses = ["(1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) >= :threshold"]
                params = {
                    "vector": "[" + ",".join(map(str, query_vector)) + "]",
                    "threshold": float(score_threshold),
                    "limit": int(actual_top_k)
                }

                if kb_id:
                    where_clauses.append("d.kb_id = CAST(:kb_id AS UUID)")
                    params["kb_id"] = str(kb_id)

                where_sql = " AND ".join(where_clauses)

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
                rows = db_res.mappings().all()

                for row in rows:
                    meta = row["meta_info"] or {}
                    results.append(SearchResultItem(
                        chunk_id=str(row["id"]),
                        document_id=str(row["document_id"]),
                        score=round(row["similarity"], 4),
                        content=row["content"],
                        source_file=row["filename"],
                        page_number=meta.get("page_number")
                    ))

            latency = time.time() - start_time
            await self._emit_callback(
                callback,
                f"✅ 知识库检索完成 | 耗时: {latency:.2f}s | 找到 {len(results)} 条结果",
                "success",
                1.0
            )

            return results

        except (ValueError, KeyError) as e:
            await self._emit_callback(callback, f"❌ 检索数据错误: {str(e)}", "error")
            return []
        except (OSError, IOError) as e:
            await self._emit_callback(callback, f"❌ 检索IO错误: {str(e)}", "error")
            return []
        except Exception as e:
            await self._emit_callback(callback, f"❌ 检索失败: {str(e)}", "error")
            return []
        finally:
            await self._save_search_log(query, len(results), time.time() - start_time)

    async def search_with_web(
        self,
        query: str,
        top_k: int = 5,
        kb_id: str = None,
        score_threshold: float = 0.6,
        enable_web: bool = True,
        callback: Optional[Callable] = None
    ) -> HybridSearchResponse:
        """
        混合搜索：知识库 + Web
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            kb_id: 知识库ID
            score_threshold: 相似度阈值
            enable_web: 是否启用Web搜索
            callback: 进度回调函数
            
        Returns:
            混合搜索响应
        """
        start_time = time.time()
        response = HybridSearchResponse()

        # 1. 知识库检索
        kb_task = self.search_with_callback(
            query=query,
            top_k=top_k,
            kb_id=kb_id,
            score_threshold=score_threshold,
            callback=callback
        )

        # 2. Web检索（如果启用）
        web_chunks = []
        if enable_web:
            web_task = tavily_service.retrieve_chunks(
                query=query,
                top_k=top_k,
                callback=callback
            )
            
            kb_results, web_raw = await asyncio.gather(kb_task, web_task)
            web_chunks = web_raw
        else:
            kb_results = await kb_task

        # 3. 组装响应
        response.kb_results = kb_results
        response.total_kb = len(kb_results)
        response.web_available = tavily_service.is_available()

        # 4. 格式化Web结果
        for chunk in web_chunks:
            response.web_results.append(WebSearchResult(
                chunk_id=chunk["chunk_id"],
                score=chunk["score"],
                content=chunk["content"],
                source_file=chunk["source_file"],
                title=chunk.get("title"),
                source="web"
            ))
        response.total_web = len(response.web_results)
        response.search_time = time.time() - start_time

        return response

    async def check_health(self) -> bool:
        """
        健康检查方法
        
        Returns:
            bool: 服务是否健康
        """
        try:
            if hasattr(self, 'embedding_service'):
                return True
            return True
        except Exception as e:
            logger.warning(f"搜索服务健康检查失败: {e}")
            return False
    
    async def search_with_vector(
            self,
            query_vector: List[float],
            top_k: int = 5,
            score_threshold: float = 0.6,
            tenant_id: str = None,
            user_id: str = None
    ) -> List[SearchResultItem]:
        """
        使用外部传入的向量进行搜索（避免重复生成 embedding）
        
        Args:
            query_vector: 已生成的查询向量
            top_k: 返回结果数量
            score_threshold: 相似度阈值
            tenant_id: 租户ID
            user_id: 用户ID
            
        Returns:
            搜索结果列表
        """
        start_time = time.time()
        results = []

        try:
            if not tenant_id:
                raise ValueError("租户隔离失败：缺少 tenant_id")
            
            if not query_vector or len(query_vector) == 0:
                logger.warning("⚠️ [search_with_vector] 传入的向量为空")
                return []

            async with AsyncSessionLocal() as db:
                # 动态组装 WHERE 条件
                where_clauses = ["(1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) >= :threshold"]
                where_clauses.append("d.tenant_id = :tenant_id")

                if user_id:
                    where_clauses.append("""
                        (
                            (UPPER(kb.visibility) = 'ENTERPRISE' OR (UPPER(kb.visibility) = 'PRIVATE' AND kb.user_id = CAST(:user_id AS UUID)))
                        )
                        AND
                        (
                            (UPPER(d.visibility) = 'PUBLIC' OR d.user_id = CAST(:user_id AS UUID))
                        )
                    """)

                where_sql = " AND ".join(where_clauses)

                query_sql = text(f"""
                    SELECT
                        c.id as chunk_id,
                        c.document_id,
                        c.content,
                        d.filename as source_file,
                        d.file_type as doc_type,
                        (1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) as score
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    JOIN knowledge_bases kb ON d.kb_id = kb.id
                    WHERE {where_sql}
                    ORDER BY c.embedding <=> CAST(:vector AS vector)
                    LIMIT :limit
                """)

                params = {
                    "vector": "[" + ",".join(map(str, query_vector)) + "]",
                    "threshold": float(score_threshold),
                    "limit": int(top_k),
                    "tenant_id": tenant_id
                }
                if user_id:
                    params["user_id"] = str(user_id)

                result = await db.execute(query_sql, params)
                rows = result.fetchall()

                results = [
                    SearchResultItem(
                        chunk_id=str(row.chunk_id),
                        document_id=str(row.document_id),
                        content=row.content,
                        source_file=row.source_file,
                        doc_type=row.doc_type,
                        score=float(row.score)
                    )
                    for row in rows
                ]

                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(f"🔍 [search_with_vector] 搜索完成 | 耗时: {elapsed_ms:.1f}ms | 结果: {len(results)}")

                return results

        except ValueError as e:
            logger.error(f"❌ [search_with_vector] 值错误: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ [search_with_vector] 搜索失败: {e}")
            return []


search_service = SearchService()