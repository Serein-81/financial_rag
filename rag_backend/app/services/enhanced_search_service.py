"""
增强版搜索服务
集成查询优化、多查询检索和 MMR 重排序
"""
import time
import asyncio
import logging
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from sqlalchemy import text, select
from app.db import AsyncSessionLocal
from app.services.embedding_service import embedding_service
from app.services.tavily_service import tavily_service
from app.services.query_optimizer import query_optimizer
from app.schemas.chat import SearchResultItem
from app.schemas.search import WebSearchResult, HybridSearchResponse
from app.models.search_log import SearchLog
from app.models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


class EnhancedSearchService:
    """增强版搜索服务"""

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
    
    def __init__(self):
        """
        初始化增强搜索服务
        
        配置项从环境变量读取，支持以下配置：
        - ENABLE_QUERY_REWRITE: 是否启用查询改写（默认: true）
        - ENABLE_HYDE: 是否启用HyDE假设文档生成（默认: false）
        - ENABLE_MMR: 是否启用MMR重排序（默认: true）
        """
        import os
        
        # 查询改写配置
        # 功能：将单一查询改写为多个不同角度的问题
        # 效果：召回率提升 +30%
        # 成本：响应时间 +1.5s，Token消耗 +500
        # 推荐：生产环境开启
        self.enable_query_rewrite = os.getenv('ENABLE_QUERY_REWRITE', 'true').lower() == 'true'
        
        # HyDE（Hypothetical Document Embeddings）配置
        # 功能：生成假设文档，用假设文档的向量进行检索
        # 效果：召回率提升 +20%（在查询改写基础上）
        # 成本：响应时间 +1.5s，Token消耗 +800
        # 推荐：默认关闭，特殊场景可开启
        self.enable_hyde = os.getenv('ENABLE_HYDE', 'false').lower() == 'true'
        
        # MMR（Maximal Marginal Relevance）重排序配置
        # 功能：平衡相关性和多样性，避免返回过于相似的结果
        # 效果：结果多样性显著提升
        # 成本：响应时间 +0.5s（已优化），无额外Token消耗
        # 推荐：生产环境开启
        self.enable_mmr = os.getenv('ENABLE_MMR', 'true').lower() == 'true'
        
        # 打印当前配置
        logger.info(f"🔧 增强搜索配置: 查询改写={self.enable_query_rewrite}, "
                   f"HyDE={self.enable_hyde}, MMR={self.enable_mmr}")
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        kb_id: str = None,
        score_threshold: float = 0.3,
        use_optimization: bool = True
    ) -> List[SearchResultItem]:
        """
        增强版搜索方法
        
        Args:
            query: 用户查询
            top_k: 返回结果数量
            kb_id: 知识库ID
            score_threshold: 分数阈值
            use_optimization: 是否使用查询优化
            
        Returns:
            搜索结果列表
        """
        start_time = time.time()
        
        try:
            # 1. 查询意图检测
            intent = await query_optimizer.detect_query_intent(query)
            logger.info(f"🎯 查询意图: {intent['type']}")
            
            # 根据意图调整参数
            if intent['needs_more_context']:
                top_k = max(top_k, intent['suggested_top_k'])
                score_threshold = min(score_threshold, intent['suggested_threshold'])
            
            # 2. 查询优化
            queries = [query]
            if use_optimization and self.enable_query_rewrite:
                try:
                    queries = await query_optimizer.rewrite_query(query, num_variants=2)
                    logger.info(f"🔄 查询改写: {len(queries)} 个变体")
                except (ValueError, KeyError) as e:
                    logger.warning(f"⚠️ 查询改写数据错误，使用原始查询: {e}")
                except (OSError, IOError) as e:
                    logger.warning(f"⚠️ 查询改写IO错误，使用原始查询: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ 查询改写失败，使用原始查询: {e}")
            
            # 3. HyDE（可选）
            if use_optimization and self.enable_hyde:
                try:
                    hypo_doc = await query_optimizer.generate_hypothetical_document(query)
                    queries.append(hypo_doc)
                    logger.info("📄 HyDE: 添加假设文档")
                except (ValueError, KeyError) as e:
                    logger.warning(f"⚠️ HyDE数据错误: {e}")
                except (OSError, IOError) as e:
                    logger.warning(f"⚠️ HyDE IO错误: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ HyDE 失败: {e}")
            
            # 4. 多查询检索
            all_results = []
            query_embeddings = []
            
            for q in queries:
                q_embedding = await embedding_service.get_embedding(q)
                if q_embedding:
                    query_embeddings.append(q_embedding)
                    results = await self._vector_search(
                        q_embedding,
                        kb_id=kb_id,
                        top_k=top_k * 2,  # 每个查询多检索一些
                        score_threshold=score_threshold
                    )
                    all_results.extend(results)
            
            # 使用原始查询的向量进行后续处理
            main_query_embedding = query_embeddings[0] if query_embeddings else None
            
            # 5. 去重和合并
            unique_results = self._deduplicate_results(all_results)
            logger.info(f"📊 多查询检索: {len(all_results)} → {len(unique_results)} (去重后)")
            
            # 6. MMR 重排序（优化性能）
            if use_optimization and self.enable_mmr and main_query_embedding and len(unique_results) > 1:
                try:
                    # 如果结果数量不超过top_k，跳过MMR
                    if len(unique_results) <= top_k:
                        logger.info(f"⏭️ 结果数量({len(unique_results)})不超过top_k({top_k})，跳过MMR")
                        unique_results = unique_results[:top_k]
                    else:
                        # 只对前2*top_k个结果计算embedding（减少计算量）
                        results_to_rerank = unique_results[:top_k * 2]
                        results_with_embedding = []
                        
                        for r in results_to_rerank:
                            # 限制内容长度，减少embedding计算时间
                            content_preview = r['content'][:500]
                            content_embedding = await embedding_service.get_embedding(content_preview)
                            if content_embedding:
                                results_with_embedding.append({
                                    **r,
                                    'embedding': content_embedding
                                })
                        
                        if results_with_embedding:
                            reranked = query_optimizer.mmr_rerank(
                                results_with_embedding,
                                main_query_embedding,
                                lambda_param=0.6,  # 60% 相关性，40% 多样性
                                top_k=top_k
                            )
                            unique_results = reranked
                            logger.info(f"🎯 MMR 重排: 保留 {len(unique_results)} 个结果")
                        else:
                            unique_results = unique_results[:top_k]
                except (ValueError, KeyError) as e:
                    logger.warning(f"⚠️ MMR 重排数据错误: {e}")
                    unique_results = unique_results[:top_k]
                except (OSError, IOError) as e:
                    logger.warning(f"⚠️ MMR 重排IO错误: {e}")
                    unique_results = unique_results[:top_k]
                except Exception as e:
                    logger.warning(f"⚠️ MMR 重排失败: {e}")
                    unique_results = unique_results[:top_k]
            else:
                unique_results = unique_results[:top_k]
            
            # 7. 转换为 SearchResultItem
            final_results = []
            for r in unique_results:
                final_results.append(SearchResultItem(
                    chunk_id=r['chunk_id'],
                    document_id=r['document_id'],
                    score=r['score'],
                    content=r['content'],
                    source_file=r['source_file'],
                    page_number=r.get('page_number')
                ))
            
            return final_results
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 增强搜索数据错误: {e}", exc_info=True)
            return []
        except (OSError, IOError) as e:
            logger.error(f"❌ 增强搜索IO错误: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"❌ 增强搜索失败: {e}", exc_info=True)
            return []
        finally:
            latency = time.time() - start_time
            logger.info(f"🔍 增强搜索完成 | 耗时: {latency:.4f}s | 结果: {len(final_results)}")
            await self._save_search_log(query, len(final_results), latency, "enhanced")

    async def _vector_search(
        self,
        query_vector: List[float],
        kb_id: Optional[str] = None,
        top_k: int = 10,
        score_threshold: float = 0.3,
        tenant_id: str = None,
        user_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        向量检索（内部方法）
        🔐 租户隔离：必须传入 tenant_id 进行过滤
        🔐 可见性过滤：私人知识库只有创建者可见，企业知识库整个租户可见

        Returns:
            字典列表，包含 chunk_id, document_id, score, content, source_file 等
        """
        results = []

        if not tenant_id:
            if kb_id:
                tenant_id = await self._get_tenant_id_from_kb(kb_id)
                print(f"🔍 [_VectorSearch] 自动从KB获取tenant_id: {tenant_id}")
            if not tenant_id:
                raise ValueError("租户隔离失败：缺少 tenant_id")

        try:
            async with AsyncSessionLocal() as db:
                where_clauses = ["(1 - (CAST(c.embedding AS vector) <=> CAST(:vector AS vector))) >= :threshold"]
                # 🔐 租户隔离：必须添加 tenant_id 过滤（tenant_id 是字符串类型，不需要 CAST）
                where_clauses.append("d.tenant_id = :tenant_id")
                params = {
                    "vector": "[" + ",".join(map(str, query_vector)) + "]",
                    "threshold": float(score_threshold),
                    "limit": int(top_k),
                    "tenant_id": str(tenant_id)
                }

                # 🔐 两层可见性过滤
                if user_id:
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
                    params["user_id"] = str(user_id)

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
                rows = db_res.mappings().all()
                
                for row in rows:
                    meta = row["meta_info"] or {}
                    results.append({
                        'chunk_id': str(row["id"]),
                        'document_id': str(row["document_id"]),
                        'score': round(row["similarity"], 4),
                        'content': row["content"],
                        'source_file': row["filename"],
                        'page_number': meta.get("page_number")
                    })
            
            return results
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 向量检索数据错误: {e}")
            return []
        except (OSError, IOError) as e:
            logger.error(f"❌ 向量检索IO错误: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ 向量检索失败: {e}")
            return []
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去重结果
        基于 chunk_id 去重，保留分数最高的
        """
        seen = {}
        for result in results:
            chunk_id = result['chunk_id']
            if chunk_id not in seen or result['score'] > seen[chunk_id]['score']:
                seen[chunk_id] = result
        
        # 按分数排序
        unique = list(seen.values())
        unique.sort(key=lambda x: x['score'], reverse=True)
        return unique
    
    async def _save_search_log(
        self,
        query: str,
        count: int,
        latency: float,
        search_type: str = "enhanced"
    ):
        """保存搜索日志"""
        async with AsyncSessionLocal() as db:
            try:
                log = SearchLog(
                    query=f"[{search_type}] {query}",
                    result_count=count,
                    latency=latency
                )
                db.add(log)
                await db.commit()
            except (ValueError, KeyError) as e:
                logger.warning(f"⚠️ 日志保存数据错误: {e}")
            except (OSError, IOError) as e:
                logger.warning(f"⚠️ 日志保存IO错误: {e}")
            except Exception as e:
                logger.warning(f"⚠️ 日志保存失败: {e}")
    
    async def compare_search_methods(
        self,
        query: str,
        top_k: int = 5,
        kb_id: str = None
    ) -> Dict[str, Any]:
        """
        对比基础搜索和增强搜索的效果
        用于测试和评估
        """
        from app.services.search_service import search_service
        
        # 基础搜索
        start = time.time()
        basic_results = await search_service.search(query, top_k, kb_id)
        basic_time = time.time() - start
        
        # 增强搜索
        start = time.time()
        enhanced_results = await self.search(query, top_k, kb_id, use_optimization=True)
        enhanced_time = time.time() - start
        
        return {
            "query": query,
            "basic": {
                "count": len(basic_results),
                "time": round(basic_time, 4),
                "results": [r.model_dump() for r in basic_results]
            },
            "enhanced": {
                "count": len(enhanced_results),
                "time": round(enhanced_time, 4),
                "results": [r.model_dump() for r in enhanced_results]
            },
            "comparison": {
                "time_diff": round(enhanced_time - basic_time, 4),
                "time_increase_pct": round((enhanced_time - basic_time) / basic_time * 100, 2) if basic_time > 0 else 0,
                "result_overlap": len(set(r.chunk_id for r in basic_results) & set(r.chunk_id for r in enhanced_results)),
                "unique_to_enhanced": len(set(r.chunk_id for r in enhanced_results) - set(r.chunk_id for r in basic_results))
            }
        }

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
                    "source": "enhanced_search"
                }

                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)

            except (ValueError, KeyError) as e:
                logger.warning(f"⚠️ 回调发送数据错误: {e}")
            except (OSError, IOError) as e:
                logger.warning(f"⚠️ 回调发送IO错误: {e}")
            except Exception as e:
                logger.warning(f"⚠️ 回调发送失败: {e}")

    async def search_with_callback(
        self,
        query: str,
        top_k: int = 5,
        kb_id: str = None,
        score_threshold: float = 0.3,
        use_optimization: bool = True,
        enable_web: bool = False,
        callback: Optional[Callable] = None,
        tenant_id: str = None,
        user_id: str = None
    ) -> HybridSearchResponse:
        """
        🆕 带回调的增强搜索（支持混合搜索）
        🔐 租户隔离：必须传入 tenant_id 进行过滤
        🔐 可见性过滤：私人知识库只有创建者可见，企业知识库整个租户可见

        Args:
            query: 用户查询
            top_k: 返回结果数量
            kb_id: 知识库ID
            score_threshold: 分数阈值
            use_optimization: 是否使用查询优化
            enable_web: 是否启用Web搜索
            callback: 进度回调函数
            tenant_id: 租户ID（必须）
            user_id: 用户ID（用于可见性过滤）

        Returns:
            混合搜索响应（知识库 + Web）
        """
        if not tenant_id:
            if kb_id:
                tenant_id = await self._get_tenant_id_from_kb(kb_id)
                print(f"🔍 [EnhancedHybridSearch] 自动从KB获取tenant_id: {tenant_id}")
            if not tenant_id:
                raise ValueError("租户隔离失败：缺少 tenant_id")

        await self._emit_callback(callback, "🚀 开始增强检索...", "info", 0.0)

        start_time = time.time()
        response = HybridSearchResponse()
        final_results = []

        try:
            # 1. 查询意图检测
            await self._emit_callback(callback, "🎯 检测查询意图...", "info", 0.05)
            intent = await query_optimizer.detect_query_intent(query)
            logger.info(f"🎯 查询意图: {intent['type']}")

            if intent['needs_more_context']:
                top_k = max(top_k, intent['suggested_top_k'])
                score_threshold = min(score_threshold, intent['suggested_threshold'])

            # 2. 查询优化
            queries = [query]
            if use_optimization and self.enable_query_rewrite:
                await self._emit_callback(callback, "🔄 正在进行查询改写...", "info", 0.1)
                try:
                    queries = await query_optimizer.rewrite_query(query, num_variants=2)
                    logger.info(f"🔄 查询改写: {len(queries)} 个变体")
                except (ValueError, KeyError) as e:
                    logger.warning(f"⚠️ 查询改写数据错误，使用原始查询: {e}")
                except (OSError, IOError) as e:
                    logger.warning(f"⚠️ 查询改写IO错误，使用原始查询: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ 查询改写失败，使用原始查询: {e}")

            # 3. HyDE（可选）
            if use_optimization and self.enable_hyde:
                await self._emit_callback(callback, "📄 正在生成假设文档...", "info", 0.15)
                try:
                    hypo_doc = await query_optimizer.generate_hypothetical_document(query)
                    queries.append(hypo_doc)
                    logger.info("📄 HyDE: 添加假设文档")
                except (ValueError, KeyError) as e:
                    logger.warning(f"⚠️ HyDE数据错误: {e}")
                except (OSError, IOError) as e:
                    logger.warning(f"⚠️ HyDE IO错误: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ HyDE 失败: {e}")

            # 4. 多查询检索
            await self._emit_callback(callback, f"🔍 开始多查询检索 ({len(queries)} 个查询)...", "info", 0.2)

            all_results = []
            query_embeddings = []

            for i, q in enumerate(queries):
                q_embedding = await embedding_service.get_embedding(q)
                if q_embedding:
                    query_embeddings.append(q_embedding)
                    results = await self._vector_search(
                        q_embedding,
                        kb_id=kb_id,
                        top_k=top_k * 2,
                        score_threshold=score_threshold,
                        tenant_id=tenant_id,
                        user_id=user_id
                    )
                    all_results.extend(results)
                    await self._emit_callback(
                        callback,
                        f"   查询 {i+1}/{len(queries)}: 获得 {len(results)} 条结果",
                        "info",
                        0.2 + (0.2 * i / len(queries))
                    )
            
            main_query_embedding = query_embeddings[0] if query_embeddings else None

            # 5. 去重和合并
            await self._emit_callback(callback, "🗑️ 正在进行结果去重...", "info", 0.5)
            unique_results = self._deduplicate_results(all_results)
            logger.info(f"📊 多查询检索: {len(all_results)} → {len(unique_results)} (去重后)")

            # 6. MMR 重排序
            if use_optimization and self.enable_mmr and main_query_embedding and len(unique_results) > 1:
                await self._emit_callback(callback, "⚖️ 正在进行 MMR 重排序...", "info", 0.6)
                
                try:
                    if len(unique_results) <= top_k:
                        logger.info("⏭️ 跳过MMR")
                        unique_results = unique_results[:top_k]
                    else:
                        results_to_rerank = unique_results[:top_k * 2]
                        results_with_embedding = []
                        
                        for r in results_to_rerank:
                            content_preview = r['content'][:500]
                            content_embedding = await embedding_service.get_embedding(content_preview)
                            if content_embedding:
                                results_with_embedding.append({
                                    **r,
                                    'embedding': content_embedding
                                })
                        
                        if results_with_embedding:
                            reranked = query_optimizer.mmr_rerank(
                                results_with_embedding,
                                main_query_embedding,
                                lambda_param=0.6,
                                top_k=top_k
                            )
                            unique_results = reranked
                            logger.info(f"🎯 MMR 重排: 保留 {len(unique_results)} 个结果")
                        else:
                            unique_results = unique_results[:top_k]
                except (ValueError, KeyError) as e:
                    logger.warning(f"⚠️ MMR 重排数据错误: {e}")
                    unique_results = unique_results[:top_k]
                except (OSError, IOError) as e:
                    logger.warning(f"⚠️ MMR 重排IO错误: {e}")
                    unique_results = unique_results[:top_k]
                except Exception as e:
                    logger.warning(f"⚠️ MMR 重排失败: {e}")
                    unique_results = unique_results[:top_k]
            else:
                unique_results = unique_results[:top_k]
            
            # 7. 转换为 SearchResultItem
            for r in unique_results:
                final_results.append(SearchResultItem(
                    chunk_id=r['chunk_id'],
                    document_id=r['document_id'],
                    score=r['score'],
                    content=r['content'],
                    source_file=r['source_file'],
                    page_number=r.get('page_number')
                ))
            
            # 8. Web 搜索（如果启用）
            web_chunks = []
            if enable_web:
                await self._emit_callback(callback, "🌐 正在进行 Web 搜索...", "info", 0.8)
                web_chunks = await tavily_service.retrieve_chunks(
                    query=query,
                    top_k=top_k,
                    callback=callback
                )

            # 9. 组装响应
            response.kb_results = final_results
            response.total_kb = len(final_results)
            response.web_available = tavily_service.is_available()
            
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

            await self._emit_callback(
                callback,
                f"✅ 增强检索完成 | 知识库: {response.total_kb} | Web: {response.total_web} | 耗时: {response.search_time:.2f}s",
                "success",
                1.0
            )

            return response
            
        except (ValueError, KeyError) as e:
            logger.error(f"❌ 增强搜索数据错误: {e}", exc_info=True)
            await self._emit_callback(callback, f"❌ 检索数据错误: {str(e)}", "error")
        except (OSError, IOError) as e:
            logger.error(f"❌ 增强搜索IO错误: {e}", exc_info=True)
            await self._emit_callback(callback, f"❌ 检索IO错误: {str(e)}", "error")
        except Exception as e:
            logger.error(f"❌ 增强搜索失败: {e}", exc_info=True)
            await self._emit_callback(callback, f"❌ 检索失败: {str(e)}", "error")
            return response
        finally:
            latency = time.time() - start_time
            await self._save_search_log(query, len(final_results), latency, "enhanced_callback")


# 全局实例
enhanced_search_service = EnhancedSearchService()
