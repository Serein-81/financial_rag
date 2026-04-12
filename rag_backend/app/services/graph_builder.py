"""图构建服务（融合 GraphRAG：进度回调 + 错误处理 + 并发支持 + LLM摘要 + 语义合并）"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from sqlalchemy.orm import Session

from app.knowledge_graph.entity_extractor import EntityExtractor
from app.knowledge_graph.relation_extractor import RelationExtractor
from app.knowledge_graph.neo4j_manager import Neo4jManager
from app.schemas.knowledge_graph import (
    EntityResponse, RelationResponse, GraphBuildResponse
)
from app.utils.progress_callback import ProgressCallback

logger = logging.getLogger(__name__)


class GraphBuilder:
    """图构建器（融合 GraphRAG 优势：支持进度回调和错误处理 + LLM摘要）"""

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

            progress.info(f"📊 合并实体和关系")
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
        """批量创建实体（支持消歧和置信度）"""
        created = []

        for idx, entity in enumerate(entities):
            try:
                if progress:
                    progress.debug(f"创建实体: {entity.get('name', 'unknown')}")

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

                result = self.neo4j_manager.create_entity(
                    name=entity_name,
                    entity_type=entity["type"],
                    tenant_id=tenant_id,
                    properties=properties,
                    unique_key=unique_key
                )

                if result:
                    created.append({
                        "name": entity_name,
                        "type": entity["type"],
                        "properties": properties,
                        "id": result.get("id"),
                        "confidence": entity.get("confidence", 1.0)
                    })

                    if progress:
                        progress.debug(f"✅ 创建实体: {entity_name} ({entity['type']})")

            except (ValueError, KeyError) as e:
                if progress:
                    progress.warning(f"创建实体数据错误 {entity.get('name', 'unknown')}: {e}")
            except (OSError, IOError) as e:
                if progress:
                    progress.warning(f"创建实体IO错误 {entity.get('name', 'unknown')}: {e}")
            except (ValueError, KeyError) as e:
                if progress:
                    progress.warning(f"创建关系数据错误: {e}")
            except (OSError, IOError) as e:
                if progress:
                    progress.warning(f"创建关系IO错误: {e}")
            except Exception as e:
                if progress:
                    progress.warning(f"创建实体失败 {entity.get('name', 'unknown')}: {e}")
                else:
                    logger.warning(f"创建实体失败 {entity.get('name', 'unknown')}: {e}")
                continue

        logger.info(f"批量创建实体完成: {len(created)}/{len(entities)}")
        return created

    async def _batch_create_relations(
        self,
        relations: List[Dict[str, Any]],
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        progress: Optional[ProgressCallback] = None
    ) -> List[Dict[str, Any]]:
        """批量创建关系"""
        created = []

        for relation in relations:
            try:
                if progress:
                    progress.debug(
                        f"创建关系: {relation['source']} -[{relation['type']}]-> {relation['target']}"
                    )

                properties = relation.get("properties", {})
                if user_id:
                    properties["user_id"] = str(user_id)
                if session_id:
                    properties["session_id"] = str(session_id)

                result = self.neo4j_manager.create_relation(
                    source_name=relation["source"],
                    target_name=relation["target"],
                    relation_type=relation["type"],
                    tenant_id=tenant_id,
                    properties=properties
                )

                if result:
                    created.append({
                        "source": relation["source"],
                        "target": relation["target"],
                        "type": relation["type"],
                        "properties": properties,
                        "id": result.get("id")
                    })

            except Exception as e:
                if progress:
                    progress.warning(
                        f"创建关系失败 {relation['source']}->{relation['target']}: {e}"
                    )
                else:
                    logger.warning(
                        f"创建关系失败 {relation['source']}->{relation['target']}: {e}"
                    )
                continue

        logger.info(f"批量创建关系完成: {len(created)}/{len(relations)}")
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

            progress.info(f"📊 合并实体和关系")

            merged_entities = self.entity_extractor._merge_entities(all_entities)
            merged_relations = self.relation_extractor._merge_relations(all_relations)

            progress.info(f"✅ 合并完成: {len(merged_entities)} 个实体, {len(merged_relations)} 个关系")

            progress.info(f"📤 创建实体到图数据库")
            created_entities = await self._batch_create_entities(
                merged_entities, user_id, session_id, tenant_id, progress
            )
            progress.success(f"✅ 成功创建 {len(created_entities)} 个实体")

            progress.info(f"📤 创建关系到图数据库")
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

    def get_stats(self) -> Dict[str, Any]:
        """获取图统计信息"""
        return self.neo4j_manager.get_graph_stats()
