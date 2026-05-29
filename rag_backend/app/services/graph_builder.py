"""图构建服务（合并 GraphRAG：进度回调 + 错误处理 + 并发支持 + 增量缓存 + LLM摘要）"""
import hashlib
import json
import logging
import time
import asyncio
from typing import List, Dict, Any, Optional, Callable

from app.knowledge_graph.entity_extractor import EntityExtractor
from app.knowledge_graph.relation_extractor import RelationExtractor
from app.knowledge_graph.neo4j_manager import Neo4jManager
from app.schemas.knowledge_graph import (
    EntityResponse, RelationResponse, GraphBuildResponse
)
from app.utils.progress_callback import ProgressCallback

logger = logging.getLogger(__name__)


class ExtractionCache:
    """
    提取结果内存缓存（TTL 1 小时，最大 200 条）

    key: md5(text) → value: {"entities": [...], "relations": [...]}
    部署后可以换成 Redis，接口不变
    """
    def __init__(self, ttl: int = 3600, max_size: int = 200):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}
        self._ttl = ttl
        self._max_size = max_size

    def get(self, text: str) -> Optional[Dict]:
        key = hashlib.md5(text.encode('utf-8')).hexdigest()
        if key in self._cache:
            if time.time() - self._timestamps[key] < self._ttl:
                logger.info(f"[提取缓存] 命中缓存: {text[:30]}...")
                return self._cache[key]
            else:
                del self._cache[key]
                del self._timestamps[key]
        return None

    def set(self, text: str, result: Dict):
        key = hashlib.md5(text.encode('utf-8')).hexdigest()
        if len(self._cache) >= self._max_size:
            # 移除最旧的
            oldest = min(self._timestamps, key=self._timestamps.get)
            del self._cache[oldest]
            del self._timestamps[oldest]
        self._cache[key] = result
        self._timestamps[key] = time.time()
        logger.info(f"[提取缓存] 已缓存: {text[:30]}... ({len(self._cache)}条)")


class GraphBuilder:
    """图构建器（融合 GraphRAG 优势：支持进度回调和错误处理 + LLM摘要 + 增量缓存）"""

    def __init__(
        self,
        entity_extractor: EntityExtractor,
        relation_extractor: RelationExtractor,
        neo4j_manager: Neo4jManager
    ):
        self.entity_extractor = entity_extractor
        self.relation_extractor = relation_extractor
        self.neo4j_manager = neo4j_manager
        self.max_concurrency = 3
        self._cache = ExtractionCache()

    async def build_from_text(
        self,
        text: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        extract_entities: bool = True,
        extract_relations: bool = True,
        callback: Optional[Callable] = None
    ) -> GraphBuildResponse:
        """
        从文本构建知识图谱（增强版：带进度回调）

        Args:
            text: 输入文本
            user_id: 用户 ID
            session_id: 会话 ID
            tenant_id: 租户 ID（多租户隔离必需）
            extract_entities: 是否提取实体
            extract_relations: 是否提取关系
            callback: 进度回调函数
        """
        progress = ProgressCallback(callback)

        try:
            entities_data = []
            relations_data = []

            # 缓存检查：相同文本的提取结果直接复用
            cached = self._cache.get(text)
            if cached and extract_entities:
                entities_data = cached.get("entities", [])
                relations_data = cached.get("relations", [])
                progress.info(f"📦 缓存命中! 复用 {len(entities_data)} 个实体, {len(relations_data)} 个关系")
                # 缓存命中：跳过 LLM，直接写入 Neo4j
            else:
                if extract_entities:
                    progress.info(f"📤 开始提取实体，文本长度: {len(text)}")
                    entities_data = await self.entity_extractor.extract(text)

                    if not entities_data:
                        progress.warning("⚠️ 未提取到任何实体")
                    else:
                        progress.success(f"✅ 提取到 {len(entities_data)} 个实体")

                if extract_relations and entities_data:
                    progress.info("📤 开始提取关系")
                    relations_data = await self.relation_extractor.extract(
                        text, entities_data
                    )

                    if not relations_data:
                        progress.warning("⚠️ 未提取到任何关系")
                    else:
                        progress.success(f"✅ 提取到 {len(relations_data)} 个关系")

                # 写入缓存
                self._cache.set(text, {
                    "entities": entities_data,
                    "relations": relations_data
                })

            created_entities = []
            if entities_data:
                progress.info(f"📤 创建 {len(entities_data)} 个实体到图数据库")
                created_entities = await self._batch_create_entities(
                    entities_data, user_id, session_id, tenant_id, progress
                )
                progress.success(f"✅ 成功创建 {len(created_entities)} 个实体")

            created_relations = []
            if relations_data:
                progress.info(f"📤 创建 {len(relations_data)} 个关系到图数据库")
                created_relations = await self._batch_create_relations(
                    relations_data, user_id, session_id, tenant_id, progress
                )
                progress.success(f"✅ 成功创建 {len(created_relations)} 个关系")

            total_entities = len(created_entities)
            total_relations = len(created_relations)

            progress.success(
                f"🎉 知识图谱构建完成！"
                f"实体: {total_entities}, 关系: {total_relations}"
            )

            return GraphBuildResponse(
                entities=[EntityResponse(**e) for e in created_entities],
                relations=[RelationResponse(**r) for r in created_relations],
                success=True,
                message=f"成功创建 {total_entities} 个实体和 {total_relations} 个关系"
            )

        except (ValueError, KeyError) as e:
            error_msg = f"图构建数据错误: {str(e)}"
            progress.error(error_msg)
        except (OSError, IOError) as e:
            error_msg = f"图构建IO错误: {str(e)}"
            progress.error(error_msg)
        except Exception as e:
            error_msg = f"图构建失败: {str(e)}"
            progress.error(error_msg)
            logger.error(error_msg, exc_info=True)

            return GraphBuildResponse(
                success=False,
                message=error_msg
            )

    async def build_from_texts_batch(
        self,
        texts: List[str],
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        callback: Optional[Callable] = None
    ) -> GraphBuildResponse:
        """
        从多个文本批量构建知识图谱（新增）

        融合 RAG 项目的并发处理能力
        """
        progress = ProgressCallback(callback)

        try:
            progress.info(f"🚀 开始批量构建知识图谱，共 {len(texts)} 个文本")

            all_entities = []
            all_relations = []

            for idx, text in enumerate(texts):
                progress.progress(idx + 1, len(texts), f"处理文本 {idx + 1}")

                try:
                    entities_data = await self.entity_extractor.extract(text)
                    all_entities.extend(entities_data)

                    if entities_data:
                        relations_data = await self.relation_extractor.extract(
                            text, entities_data
                        )
                        all_relations.extend(relations_data)

                except (ValueError, KeyError) as e:
                    progress.warning(f"处理文本 {idx + 1} 数据错误: {e}")
                    continue
                except (OSError, IOError) as e:
                    progress.warning(f"处理文本 {idx + 1} IO错误: {e}")
                    continue
                except Exception as e:
                    progress.warning(f"处理文本 {idx + 1} 失败: {e}")
                    continue

            progress.info("📊 合并实体和关系")
            merged_entities = self.entity_extractor._merge_entities(all_entities)
            merged_relations = self.relation_extractor._merge_relations(all_relations)

            progress.info(f"📤 创建 {len(merged_entities)} 个实体")
            created_entities = await self._batch_create_entities(
                merged_entities, user_id, session_id, progress
            )

            progress.info(f"📤 创建 {len(merged_relations)} 个关系")
            created_relations = await self._batch_create_relations(
                merged_relations, user_id, session_id, progress
            )

            progress.success(
                f"🎉 批量构建完成！"
                f"实体: {len(created_entities)}, 关系: {len(created_relations)}"
            )

            return GraphBuildResponse(
                entities=[EntityResponse(**e) for e in created_entities],
                relations=[RelationResponse(**r) for r in created_relations],
                success=True,
                message=f"成功创建 {len(created_entities)} 个实体和 {len(created_relations)} 个关系"
            )

        except (ValueError, KeyError) as e:
            error_msg = f"批量构建数据错误: {str(e)}"
            progress.error(error_msg)
        except (OSError, IOError) as e:
            error_msg = f"批量构建IO错误: {str(e)}"
            progress.error(error_msg)
        except Exception as e:
            error_msg = f"批量构建失败: {str(e)}"
            progress.error(error_msg)
            logger.error(error_msg, exc_info=True)

            return GraphBuildResponse(
                success=False,
                message=error_msg
            )

    async def _batch_create_entities(
        self,
        entities: List[Dict[str, Any]],
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        progress: Optional[ProgressCallback] = None
    ) -> List[Dict[str, Any]]:
        """批量创建实体（UNWIND 一次往返，支持消歧和置信度）"""
        if not entities:
            return []

        # 预处理实体数据，构造 UNWIND 所需的 rows
        rows = []
        for entity in entities:
            properties = entity.get("properties", {}) or {}
            if isinstance(properties, str):
                properties = {}
            if user_id:
                properties["user_id"] = str(user_id)
            if session_id:
                properties["session_id"] = str(session_id)
            if "confidence" in entity:
                properties["confidence"] = entity["confidence"]
            if "original_name" in entity:
                properties["original_name"] = entity["original_name"]

            entity_name = entity["name"]
            unique_key = f"{entity_name}_{entity['type']}"
            if "original_name" in entity:
                unique_key = f"{entity['original_name']}_{entity_name}_{entity['type']}"

            rows.append({
                "name": entity_name,
                "entity_type": entity["type"],
                "tenant_id": tenant_id,
                "properties": properties,
                "unique_key": unique_key,
                "confidence": entity.get("confidence", 1.0),
            })

        # 单次 UNWIND 写入
        created_count = self.neo4j_manager.batch_create_entities(rows, tenant_id)

        # 构造返回列表（不依赖 Neo4j 返回的 ID）
        created = []
        for row in rows:
            created.append({
                "name": row["name"],
                "type": row["entity_type"],
                "properties": row["properties"],
                "id": row.get("unique_key"),
                "confidence": row["confidence"],
            })
            if progress:
                progress.debug(f"✅ 创建实体: {row['name']} ({row['entity_type']})")

        logger.info(f"UNWIND批量创建实体完成: {created_count}/{len(entities)}")
        return created

    async def _batch_create_relations(
        self,
        relations: List[Dict[str, Any]],
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        progress: Optional[ProgressCallback] = None
    ) -> List[Dict[str, Any]]:
        """批量创建关系（UNWIND 一次往返）"""
        if not relations:
            return []

        # 预处理关系数据
        rows = []
        for relation in relations:
            properties = relation.get("properties", {})
            if user_id:
                properties["user_id"] = str(user_id)
            if session_id:
                properties["session_id"] = str(session_id)

            rows.append({
                "source": relation["source"],
                "target": relation["target"],
                "type": relation["type"],
                "properties": properties,
            })

        # 单次 UNWIND 写入
        created_count = self.neo4j_manager.batch_create_relations(rows, tenant_id)

        created = []
        for row in rows:
            created.append({
                "source": row["source"],
                "target": row["target"],
                "type": row["type"],
                "properties": row["properties"],
                "id": None,  # UNWIND 不返回单个 ID
            })
            if progress:
                progress.debug(
                    f"创建关系: {row['source']} -[{row['type']}]-> {row['target']}"
                )

        logger.info(f"UNWIND批量创建关系完成: {created_count}/{len(relations)}")
        return created

    async def build_from_memory(
        self,
        memory_id: str,
        content: str,
        db: Any
    ) -> GraphBuildResponse:
        """从记忆构建图谱（集成到 semantic_memory）"""
        import uuid as uuid_lib
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.models.semantic_memory import SemanticMemory
        from app.models.user import User
        
        try:
            memory_uuid = uuid_lib.UUID(memory_id)
        except (ValueError, TypeError):
            return GraphBuildResponse(
                success=False,
                message=f"无效的 memory_id: {memory_id}"
            )

        if isinstance(db, AsyncSession):
            stmt = select(SemanticMemory).where(SemanticMemory.id == memory_uuid)
            result = await db.execute(stmt)
            memory = result.scalar_one_or_none()
            
            tenant_id = None
            if memory and memory.user_id:
                user_stmt = select(User).where(User.id == memory.user_id)
                user_result = await db.execute(user_stmt)
                user = user_result.scalar_one_or_none()
                if user:
                    tenant_id = str(user.tenant_id)
        else:
            memory = db.query(SemanticMemory).filter(
                SemanticMemory.id == memory_uuid
            ).first()
            tenant_id = str(memory.user.tenant_id) if memory and memory.user else None

        if not memory:
            return GraphBuildResponse(
                success=False,
                message=f"记忆 {memory_id} 不存在"
            )

        return await self.build_from_text(
            text=content,
            user_id=str(memory.user_id) if memory.user_id else None,
            session_id=str(memory.source_session_id) if memory.source_session_id else None,
            tenant_id=tenant_id
        )

    async def build_with_enhancements(
        self,
        texts: List[str],
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        generate_descriptions: bool = True,
        callback: Optional[Callable] = None
    ) -> GraphBuildResponse:
        """
        使用 LLM 摘要增强构建知识图谱（新增）

        融合 GraphRAG 的完整工作流：
        1. 异步并发提取实体和关系
        2. 智能合并重复节点和边
        3. LLM 生成实体和关系描述
        4. 完善的错误处理和进度回调
        """
        progress = ProgressCallback(callback)

        try:
            progress.info(f"🚀 开始增强构建知识图谱，共 {len(texts)} 个文本")
            progress.info(f"📝 启用 LLM 摘要: {generate_descriptions}")

            all_entities = []
            all_relations = []

            limiter = asyncio.Semaphore(self.max_concurrency)

            async def process_text(text: str, idx: int):
                async with limiter:
                    progress.progress(idx + 1, len(texts), f"处理文本 {idx + 1}")

                    try:
                        if generate_descriptions:
                            entities = await self.entity_extractor.extract_with_descriptions(
                                text,
                                texts_context=texts,
                                callback=lambda msg: progress.debug(f"[文本{idx+1}] {msg}")
                            )
                        else:
                            entities = await self.entity_extractor.extract(
                                text,
                                resolve_coreference=True,
                                callback=lambda msg: progress.debug(f"[文本{idx+1}] {msg}")
                            )

                        all_entities.extend(entities)

                        if entities:
                            if generate_descriptions:
                                relations = await self.relation_extractor.extract_with_descriptions(
                                    text,
                                    entities,
                                    texts_context=texts,
                                    callback=lambda msg: progress.debug(f"[文本{idx+1}] {msg}")
                                )
                            else:
                                relations = await self.relation_extractor.extract(
                                    text,
                                    entities,
                                    callback=lambda msg: progress.debug(f"[文本{idx+1}] {msg}")
                                )

                            all_relations.extend(relations)

                        progress.debug(f"✅ 文本 {idx + 1} 处理完成: {len(entities)} 实体, {len(relations) if entities else 0} 关系")

                    except asyncio.CancelledError:
                        progress.warning(f"⚠️ 文本 {idx + 1} 处理被取消")
                        raise
                    except (ValueError, KeyError) as e:
                        progress.warning(f"⚠️ 文本 {idx + 1} 处理数据错误: {e}")
                        logger.error(f"处理文本 {idx + 1} 数据错误: {e}", exc_info=True)
                    except (OSError, IOError) as e:
                        progress.warning(f"⚠️ 文本 {idx + 1} 处理IO错误: {e}")
                        logger.error(f"处理文本 {idx + 1} IO错误: {e}", exc_info=True)
                    except Exception as e:
                        progress.warning(f"⚠️ 文本 {idx + 1} 处理失败: {e}")
                        logger.error(f"处理文本 {idx + 1} 失败: {e}", exc_info=True)

            tasks = [
                asyncio.create_task(process_text(text, i))
                for i, text in enumerate(texts)
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

            progress.info("📊 合并实体和关系")

            merged_entities = self.entity_extractor._merge_entities(all_entities)
            merged_relations = self.relation_extractor._merge_relations(all_relations)

            progress.info(f"✅ 合并完成: {len(merged_entities)} 个实体, {len(merged_relations)} 个关系")

            progress.info("📤 创建实体到图数据库")
            created_entities = await self._batch_create_entities(
                merged_entities, user_id, session_id, tenant_id, progress
            )
            progress.success(f"✅ 成功创建 {len(created_entities)} 个实体")

            progress.info("📤 创建关系到图数据库")
            created_relations = await self._batch_create_relations(
                merged_relations, user_id, session_id, tenant_id, progress
            )
            progress.success(f"✅ 成功创建 {len(created_relations)} 个关系")

            progress.success(
                f"🎉 增强构建完成！"
                f"实体: {len(created_entities)}, 关系: {len(created_relations)}"
            )

            return GraphBuildResponse(
                entities=[EntityResponse(**e) for e in created_entities],
                relations=[RelationResponse(**r) for r in created_relations],
                success=True,
                message=f"成功创建 {len(created_entities)} 个实体和 {len(created_relations)} 个关系"
            )

        except asyncio.CancelledError:
            error_msg = "知识图谱构建任务被取消"
            progress.warning(f"⚠️ {error_msg}")
            logger.warning(error_msg)

            return GraphBuildResponse(
                success=False,
                message=error_msg
            )

        except (ValueError, KeyError) as e:
            error_msg = f"增强构建数据错误: {str(e)}"
            progress.error(error_msg)
        except (OSError, IOError) as e:
            error_msg = f"增强构建IO错误: {str(e)}"
            progress.error(error_msg)
        except Exception as e:
            error_msg = f"增强构建失败: {str(e)}"
            progress.error(error_msg)
            logger.error(error_msg, exc_info=True)

            return GraphBuildResponse(
                success=False,
                message=error_msg
            )

    def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """获取图统计信息"""
        return self.neo4j_manager.get_graph_stats(tenant_id)
