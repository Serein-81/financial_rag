"""
语义记忆 (Semantic Memory)

模拟人类的长期知识记忆，存储跨会话的知识和经验
特点：
- 容量大（1000+条）
- 高度结构化
- 向量检索
- 知识提取和归纳
- 数据库持久化
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, update, delete, func
from .base_memory import BaseMemory, MemoryItem
from app.services.embedding_service import embedding_service
from app.db import AsyncSessionLocal
from app.models.semantic_memory import SemanticMemory as SemanticMemoryModel
from app.core.config import settings

# 知识图谱相关导入（可选，根据配置启用）
if settings.ENABLE_KNOWLEDGE_GRAPH:
    from app.services.graph_builder import GraphBuilder
    from app.knowledge_graph.entity_extractor import EntityExtractor
    from app.knowledge_graph.relation_extractor import RelationExtractor
    from app.knowledge_graph.neo4j_manager import Neo4jManager
    from app.agent_framework.llm.factory import LLMAdapterFactory


def _is_valid_uuid(val: str) -> bool:
    """检查字符串是否为有效的UUID"""
    if not val:
        return False
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError):
        return False


class SemanticMemory(BaseMemory):
    """
    语义记忆 - 长期知识库
    
    实现策略：
    1. 存储用户的知识偏好
    2. 存储常见问题和答案
    3. 存储领域知识
    4. 支持知识图谱（未来扩展）
    5. 数据库持久化存储
    """
    
    def __init__(self, user_id: str, capacity: int = 1000):
        """
        初始化语义记忆
        
        Args:
            user_id: 用户ID
            capacity: 容量
        """
        super().__init__(capacity)
        self.user_id = user_id
        self.knowledge_graph: Dict[str, List[str]] = {}  # 简单的知识图谱
        self.loaded = False
        
        # 初始化知识图谱构建器（如果启用）
        self.graph_builder = None
        if settings.ENABLE_KNOWLEDGE_GRAPH:
            try:
                # EntityExtractor 和 RelationExtractor 不需要参数
                entity_extractor = EntityExtractor()
                relation_extractor = RelationExtractor()
                neo4j_manager = Neo4jManager()
                self.graph_builder = GraphBuilder(
                    entity_extractor,
                    relation_extractor,
                    neo4j_manager
                )
                print(f"🕸️ [语义记忆] 知识图谱已启用")
            except Exception as e:
                print(f"⚠️ [语义记忆] 知识图谱初始化失败: {e}")
                self.graph_builder = None
        
        print(f"🧠 [语义记忆] 初始化 | User: {user_id} | 容量: {capacity}")

    async def load_from_db(self) -> None:
        """从数据库加载用户的语义记忆"""
        if self.loaded:
            return

        if not _is_valid_uuid(self.user_id):
            print(f"⚠️ [语义记忆] user_id 不是有效的UUID: {self.user_id}，跳过数据库加载")
            self.loaded = True
            return

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SemanticMemoryModel)
                .where(SemanticMemoryModel.user_id == self.user_id)
                .order_by(SemanticMemoryModel.importance.desc(), SemanticMemoryModel.last_accessed.desc())
                .limit(self.capacity)
            )
            memories = result.scalars().all()
            
            for mem in memories:
                # 💡 修复点 1：安全获取元数据，避免 SQLAlchemy MetaData 对象命名冲突
                # 尝试获取 memory_metadata 或 metadata_，如果都没有才尝试 metadata，且确保它是 dict
                raw_meta = getattr(mem, 'memory_metadata', getattr(mem, 'metadata_', getattr(mem, 'metadata', {})))
                safe_meta = raw_meta if isinstance(raw_meta, dict) else {}

                item = MemoryItem(
                    id=str(mem.id),
                    content=mem.content,
                    role=mem.role,
                    timestamp=mem.created_at,
                    importance=mem.importance,
                    access_count=mem.access_count,
                    last_access=mem.last_accessed,
                    decay_factor=mem.decay_factor,
                    embedding=mem.embedding,
                    metadata={
                        "memory_type": mem.memory_type,
                        "tags": mem.tags or [],
                        "source_session_id": str(mem.source_session_id) if mem.source_session_id else None,
                        **safe_meta
                    }
                )
                self.memories.append(item)

            self.loaded = True
            print(f"📥 [语义记忆] 从数据库加载 {len(memories)} 条记忆")

    async def add(self, item: MemoryItem) -> None:
        """
        添加知识到语义记忆

        策略：
        1. 验证输入参数
        2. 生成向量嵌入
        3. 检查是否已存在相似知识
        4. 如果存在，合并；否则添加
        5. 持久化到数据库
        """
        # 1. 输入验证
        if not item or not item.content or not item.content.strip():
            print("⚠️ [语义记忆] 跳过空内容记忆")
            return

        if item.role not in ["user", "assistant", "system"]:
            print(f"⚠️ [语义记忆] 无效角色: {item.role}，设置为 'system'")
            item.role = "system"

        # 验证重要性范围
        if not (0.0 <= item.importance <= 1.0):
            print(f"⚠️ [语义记忆] 重要性超出范围: {item.importance}，调整为 0.8")
            item.importance = 0.8

        # 2. 确保已加载
        await self.load_from_db()

        if not _is_valid_uuid(self.user_id):
            print(f"⚠️ [语义记忆] user_id 不是有效的UUID: {self.user_id}，跳过数据库保存")
            self.memories.append(item)
            return

        try:
            # 3. 生成向量嵌入
            # 💡 保持之前的修复点：安全判断数组
            if item.embedding is None or len(item.embedding) == 0:
                item.embedding = await embedding_service.get_embedding(item.content.strip())

            # 4. 检查是否存在相似知识
            similar = await self._find_similar(item.embedding, threshold=0.9)

            if similar:
                # 合并知识：增加访问次数，更新重要性
                similar.access_count += 1
                similar.importance = min(1.0, similar.importance + 0.1)
                similar.last_access = datetime.now()

                # 更新数据库
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        update(SemanticMemoryModel)
                        .where(SemanticMemoryModel.id == similar.id)
                        .values(
                            access_count=similar.access_count,
                            importance=similar.importance,
                            last_accessed=similar.last_access
                        )
                    )
                    await db.commit()

                print(f"🔄 [语义记忆] 合并相似知识 | ID: {similar.id}")
            else:
                # 5. 添加新知识到数据库
                async with AsyncSessionLocal() as db:
                    # 添加用户ID到元数据
                    if "user_id" not in item.metadata:
                        item.metadata["user_id"] = self.user_id

                    # 💡 修复点 2：这里构建字典动态传入，兼容你可能的不同模型字段名设计
                    db_kwargs = {
                        "user_id": self.user_id,
                        "content": item.content.strip(),
                        "role": item.role,
                        "embedding": item.embedding,
                        "importance": item.importance,
                        "access_count": item.access_count,
                        "decay_factor": item.decay_factor,
                        "memory_type": item.metadata.get("memory_type", "knowledge"),
                        "tags": item.metadata.get("tags", []),
                        "source_session_id": item.metadata.get("source_session_id")
                    }

                    # 动态探测模型支持的字段名称以避免 metadata 冲突
                    if hasattr(SemanticMemoryModel, 'memory_metadata'):
                        db_kwargs['memory_metadata'] = item.metadata
                    elif hasattr(SemanticMemoryModel, 'metadata_'):
                        db_kwargs['metadata_'] = item.metadata
                    elif hasattr(SemanticMemoryModel, 'metadata'):
                        db_kwargs['metadata'] = item.metadata

                    db_memory = SemanticMemoryModel(**db_kwargs)
                    db.add(db_memory)
                    await db.commit()
                    await db.refresh(db_memory)

                    # 更新 item 的 id
                    item.id = str(db_memory.id)

                # 6. 添加到内存（只有数据库保存成功后才添加）
                self.memories.append(item)
                print(f"➕ [语义记忆] 添加新知识 | 当前数量: {len(self.memories)}/{self.capacity}")

                # 6.5 构建知识图谱（如果启用）
                if self.graph_builder and settings.ENABLE_ENTITY_EXTRACTION:
                    try:
                        await self._build_knowledge_graph_for_memory(
                            memory_id=item.id,
                            content=item.content
                        )
                    except Exception as e:
                        print(f"⚠️ [语义记忆] 知识图谱构建失败: {e}")

                # 7. 如果超过容量，触发巩固
                if len(self.memories) > self.capacity:
                    await self.consolidate()

        except Exception as e:
            print(f"❌ [语义记忆] 添加知识失败: {e}")
            # 向量嵌入或数据库操作失败时，不添加到内存

    async def retrieve(self, query: str, top_k: int = 5,
                      query_embedding: Optional[List[float]] = None,
                      use_graph: bool = True) -> List[MemoryItem]:
        """
        检索语义记忆

        策略：
        1. 使用向量检索找到最相关的知识
        2. 如果启用，使用图检索增强结果
        3. 考虑重要性和访问频率
        4. 更新访问统计

        Args:
            query: 查询文本
            top_k: 返回结果数量
            query_embedding: 查询向量（可选）
            use_graph: 是否使用知识图谱检索
        """
        # 确保已加载
        await self.load_from_db()

        if not self.memories:
            return []

        # 获取查询向量
        # 💡 保持之前的修复点：安全判断数组
        if query_embedding is None or len(query_embedding) == 0:
            query_embedding = await embedding_service.get_embedding(query)

        # 1. 向量检索
        scored_memories = []
        for memory in self.memories:
            # 💡 保持之前的修复点：安全判断数组
            if memory.embedding is not None and len(memory.embedding) > 0:
                score = memory.get_relevance_score(query_embedding)
                scored_memories.append((score, memory))

        # 按分数排序
        scored_memories.sort(key=lambda x: x[0], reverse=True)

        # 获取向量检索结果
        vector_results = [m for _, m in scored_memories[:top_k]]

        # 2. 图检索（如果启用）
        graph_results = []
        if use_graph and self.graph_builder and settings.ENABLE_KNOWLEDGE_GRAPH:
            try:
                graph_results = await self._retrieve_from_graph(query, top_k=top_k)
                print(f"🕸️ [知识图谱] 检索到 {len(graph_results)} 条图谱结果")
            except Exception as e:
                print(f"⚠️ [知识图谱] 检索失败: {e}")

        # 3. 合并结果（去重）
        results = vector_results.copy()
        seen_ids = {m.id for m in vector_results if m.id}

        for graph_mem in graph_results:
            if graph_mem.id not in seen_ids:
                results.append(graph_mem)
                if len(results) >= top_k:
                    break

        # 限制返回数量
        results = results[:top_k]

        # 4. 更新访问统计（仅更新数据库中的记忆）
        db_memory_ids = [m.id for m in results if m.id and m.id.isdigit()]
        if db_memory_ids:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(SemanticMemoryModel)
                    .where(SemanticMemoryModel.id.in_(db_memory_ids))
                    .values(
                        access_count=SemanticMemoryModel.access_count + 1,
                        last_accessed=func.now()
                    )
                )
                await db.commit()

            # 更新内存中的统计
            for memory in results:
                if memory.id in db_memory_ids:
                    memory.access()

        print(f"🔍 [语义记忆] 检索到 {len(results)} 条相关知识 (向量: {len(vector_results)}, 图谱: {len(graph_results)})")
        return results

    async def update(self, item_id: str, updates: Dict[str, Any]) -> bool:
        """更新知识项"""
        # 确保已加载
        await self.load_from_db()

        for memory in self.memories:
            if memory.id == item_id:
                # 更新内存中的数据
                for key, value in updates.items():
                    if hasattr(memory, key):
                        setattr(memory, key, value)

                # 更新数据库
                async with AsyncSessionLocal() as db:
                    update_data = {}
                    if "content" in updates:
                        update_data["content"] = updates["content"]
                        # 如果更新了内容，重新生成向量
                        memory.embedding = await embedding_service.get_embedding(memory.content)
                        update_data["embedding"] = memory.embedding

                    if "importance" in updates:
                        update_data["importance"] = updates["importance"]

                    if "memory_type" in updates:
                        update_data["memory_type"] = updates["memory_type"]

                    if "tags" in updates:
                        update_data["tags"] = updates["tags"]

                    if update_data:
                        update_data["updated_at"] = func.now()
                        await db.execute(
                            update(SemanticMemoryModel)
                            .where(SemanticMemoryModel.id == item_id)
                            .values(**update_data)
                        )
                        await db.commit()

                return True
        return False

    async def forget(self, item_id: str) -> bool:
        """删除指定知识"""
        # 确保已加载
        await self.load_from_db()

        for i, memory in enumerate(self.memories):
            if memory.id == item_id:
                # 从内存中删除
                self.memories.pop(i)

                # 从数据库删除
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        delete(SemanticMemoryModel)
                        .where(SemanticMemoryModel.id == item_id)
                    )
                    await db.commit()

                print(f"🗑️ [语义记忆] 删除知识: {item_id}")
                return True
        return False

    async def consolidate(self) -> None:
        """
        语义记忆巩固

        策略：
        1. 清理低价值记忆（衰减因子 < 0.1）
        2. 合并相似记忆
        3. 更新重要性评分
        """
        await self.load_from_db()

        if not self.memories:
            return

        print("🔄 [语义记忆] 开始记忆巩固...")

        # 1. 清理低价值记忆
        low_value_memories = [m for m in self.memories if m.decay_factor < 0.1]
        if low_value_memories:
            memory_ids = [m.id for m in low_value_memories]
            async with AsyncSessionLocal() as db:
                await db.execute(
                    delete(SemanticMemoryModel)
                    .where(SemanticMemoryModel.id.in_(memory_ids))
                )
                await db.commit()

            # 从内存中移除
            self.memories = [m for m in self.memories if m.decay_factor >= 0.1]
            print(f"🗑️ [语义记忆] 清理低价值记忆: {len(low_value_memories)} 条")

        # 2. 如果仍然超过容量，删除最旧的记忆
        if len(self.memories) > self.capacity:
            # 按重要性和访问频率排序，保留最有价值的
            self.memories.sort(key=lambda m: (m.importance, m.access_count), reverse=True)

            # 删除超出容量的记忆
            excess_memories = self.memories[self.capacity:]
            if excess_memories:
                memory_ids = [m.id for m in excess_memories]
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        delete(SemanticMemoryModel)
                        .where(SemanticMemoryModel.id.in_(memory_ids))
                    )
                    await db.commit()

                self.memories = self.memories[:self.capacity]
                print(f"🗑️ [语义记忆] 删除超出容量的记忆: {len(excess_memories)} 条")

        print(f"✅ [语义记忆] 巩固完成 | 当前数量: {len(self.memories)}")

    async def _find_similar(self, embedding: List[float],
                           threshold: float = 0.9) -> Optional[MemoryItem]:
        """
        查找相似知识

        Args:
            embedding: 向量嵌入
            threshold: 相似度阈值

        Returns:
            相似的记忆项，如果没有则返回 None
        """
        await self.load_from_db()

        import math

        for memory in self.memories:
            # 💡 保持之前的修复点：安全判断数组
            if memory.embedding is None or len(memory.embedding) == 0:
                continue

            # 计算余弦相似度
            dot_product = sum(a * b for a, b in zip(memory.embedding, embedding))
            norm_a = math.sqrt(sum(a * a for a in memory.embedding))
            norm_b = math.sqrt(sum(b * b for b in embedding))

            if norm_a == 0 or norm_b == 0:
                continue

            similarity = dot_product / (norm_a * norm_b)

            if similarity >= threshold:
                return memory

        return None

    async def _build_knowledge_graph_for_memory(
        self,
        memory_id: str,
        content: str
    ) -> None:
        """
        为记忆构建知识图谱

        Args:
            memory_id: 记忆 ID (UUID字符串)
            content: 记忆内容
        """
        if not self.graph_builder:
            return

        try:
            # 使用 graph_builder 构建图谱
            async with AsyncSessionLocal() as db:
                result = await self.graph_builder.build_from_memory(
                    memory_id=memory_id,
                    content=content,
                    db=db
                )

                if result.success:
                    print(f"🕸️ [知识图谱] 为记忆 {memory_id} 创建了 {len(result.entities)} 个实体和 {len(result.relations)} 个关系")
                else:
                    print(f"⚠️ [知识图谱] 构建失败: {result.message}")
        except Exception as e:
            print(f"❌ [知识图谱] 构建异常: {e}")

    async def _retrieve_from_graph(
        self,
        query: str,
        top_k: int = 5
    ) -> List[MemoryItem]:
        """
        从知识图谱检索相关记忆

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            相关的记忆项列表
        """
        if not self.graph_builder:
            return []

        if not _is_valid_uuid(self.user_id):
            print(f"⚠️ [知识图谱] user_id 不是有效的UUID: {self.user_id}，跳过图检索")
            return []

        try:
            # 使用混合检索器
            from app.services.hybrid_retriever import HybridRetriever

            neo4j_manager = self.graph_builder.neo4j_manager
            retriever = HybridRetriever(neo4j_manager)

            # 仅使用图检索
            async with AsyncSessionLocal() as db:
                results, stats = await retriever.retrieve(
                    query=query,
                    db=db,
                    user_id=int(self.user_id) if self.user_id.isdigit() else None,
                    top_k=top_k,
                    vector_weight=0.0,  # 不使用向量检索
                    graph_weight=1.0,   # 仅使用图检索
                    use_graph=True
                )

                # 将 SearchResult 转换为 MemoryItem
                memory_items = []
                for result in results:
                    if result.source == "graph":
                        # 从图检索结果创建临时记忆项
                        item = MemoryItem(
                            content=result.content,
                            role="system",
                            importance=result.score,
                            metadata={
                                "source": "knowledge_graph",
                                **result.metadata
                            }
                        )
                        memory_items.append(item)

                return memory_items
        except Exception as e:
            print(f"⚠️ [知识图谱] 检索失败: {e}")
            return []

    async def extract_knowledge(self, episodic_memories: List[MemoryItem]) -> None:
        """
        从情景记忆中提取知识

        策略：
        1. 识别高频问题
        2. 提取关键信息
        3. 归纳总结
        """
        # 统计问题频率
        question_freq: Dict[str, int] = {}

        for memory in episodic_memories:
            if memory.role == "user":
                # 简化处理：直接使用内容作为 key
                # 实际应该使用语义相似度聚类
                question_freq[memory.content] = question_freq.get(memory.content, 0) + 1

        # 提取高频问题（出现 3 次以上）
        for question, freq in question_freq.items():
            if freq >= 3:
                knowledge_item = MemoryItem(
                    content=f"[常见问题] {question}",
                    role="system",
                    importance=0.8,
                    metadata={
                        "type": "frequent_question",
                        "frequency": freq,
                        "extracted_from": "episodic_memory"
                    }
                )
                await self.add(knowledge_item)

        print(f"📊 [语义记忆] 从情景记忆提取 {len(question_freq)} 个知识点")

    async def build_knowledge_graph(self) -> Dict[str, List[str]]:
        """
        构建简单的知识图谱

        返回实体之间的关系
        """
        # 这里是简化实现，实际应该使用 NER 和关系抽取
        self.knowledge_graph = {}

        for memory in self.memories:
            # 提取关键词（简化处理）
            keywords = memory.content.split()[:5]

            for keyword in keywords:
                if keyword not in self.knowledge_graph:
                    self.knowledge_graph[keyword] = []

                # 添加相关记忆 ID
                self.knowledge_graph[keyword].append(memory.id)

        print(f"🕸️ [语义记忆] 构建知识图谱 | 节点数: {len(self.knowledge_graph)}")
        return self.knowledge_graph

    def get_knowledge_summary(self) -> Dict[str, Any]:
        """获取知识摘要"""
        if not self.memories:
            return {
                "total_knowledge": 0,
                "categories": {},
                "top_topics": []
            }

        # 统计知识类别
        categories: Dict[str, int] = {}
        for memory in self.memories:
            category = memory.metadata.get("type", "general")
            categories[category] = categories.get(category, 0) + 1

        # 找出最重要的知识
        top_knowledge = sorted(
            self.memories,
            key=lambda m: m.importance * (1 + m.access_count),
            reverse=True
        )[:10]

        return {
            "total_knowledge": len(self.memories),
            "categories": categories,
            "top_topics": [
                {
                    "content": k.content[:50] + "...",
                    "importance": k.importance,
                    "access_count": k.access_count
                }
                for k in top_knowledge
            ],
            "graph_nodes": len(self.knowledge_graph)
        }

    async def add_user_memory(
        self,
        content: str,
        memory_category: str,
        confidence: float = 0.8,
        source: str = "",
        extraction_type: str = "fact"
    ) -> bool:
        """
        添加用户记忆（事实、偏好、纠正）
        
        与普通记忆的区别：
        - 记忆类型固定为 user_memory
        - 包含提取类型标签（fact/preference/correction）
        - 高置信度自动设置高重要性
        
        Args:
            content: 记忆内容
            memory_category: 类别（identity/company/business/preference/correction）
            confidence: 置信度（用于计算重要性）
            source: 来源文本
            extraction_type: 提取类型（fact/preference/correction）
            
        Returns:
            是否添加成功
        """
        try:
            # 构建用户记忆内容
            formatted_content = f"[{memory_category.upper()}] {content}"
            if source:
                formatted_content += f" (来源: {source[:100]}...)"
            
            # 根据置信度设置重要性
            importance = min(1.0, confidence + 0.1)
            
            # 创建记忆项
            item = MemoryItem(
                content=formatted_content,
                role="user",
                importance=importance,
                metadata={
                    "memory_type": "user_memory",
                    "extraction_type": extraction_type,
                    "category": memory_category,
                    "confidence": confidence,
                    "source": source,
                    "user_id": self.user_id
                }
            )
            
            # 添加到语义记忆
            await self.add(item)
            
            print(f"✅ [语义记忆] 添加用户记忆 | 类型: {extraction_type} | 类别: {memory_category}")
            return True
            
        except Exception as e:
            print(f"❌ [语义记忆] 添加用户记忆失败: {e}")
            return False

    async def get_user_memories(
        self,
        extraction_type: Optional[str] = None,
        category: Optional[str] = None,
        top_k: int = 20
    ) -> List[MemoryItem]:
        """
        获取用户记忆
        
        Args:
            extraction_type: 过滤类型（fact/preference/correction）
            category: 过滤类别（identity/company/business/preference/correction）
            top_k: 返回数量
            
        Returns:
            符合条件的用户记忆列表
        """
        await self.load_from_db()
        
        filtered_memories = [
            m for m in self.memories
            if m.metadata.get("memory_type") == "user_memory"
        ]
        
        # 按类型过滤
        if extraction_type:
            filtered_memories = [
                m for m in filtered_memories
                if m.metadata.get("extraction_type") == extraction_type
            ]
        
        # 按类别过滤
        if category:
            filtered_memories = [
                m for m in filtered_memories
                if m.metadata.get("category") == category
            ]
        
        # 按重要性排序
        filtered_memories.sort(key=lambda m: m.importance, reverse=True)
        
        # 限制数量
        filtered_memories = filtered_memories[:top_k]
        
        return filtered_memories

    async def get_user_facts(self, top_k: int = 10) -> List[MemoryItem]:
        """获取用户事实记忆"""
        return await self.get_user_memories(extraction_type="fact", top_k=top_k)

    async def get_user_preferences(self, top_k: int = 10) -> List[MemoryItem]:
        """获取用户偏好记忆"""
        return await self.get_user_memories(extraction_type="preference", top_k=top_k)

    async def get_user_corrections(self, top_k: int = 10) -> List[MemoryItem]:
        """获取用户纠正记忆"""
        return await self.get_user_memories(extraction_type="correction", top_k=top_k)