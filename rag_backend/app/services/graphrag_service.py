"""
GraphRAG 服务

将向量检索和知识图谱深度融合，提供增强的检索能力。

核心功能:
1. 向量检索获取相关文档块
2. 从文档块中提取实体
3. 在知识图谱中遍历关系
4. 合并向量上下文和图谱上下文
5. Rerank 排序返回最佳结果
"""

import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class GraphRAGContext:
    """GraphRAG 检索上下文"""
    # 向量检索结果
    vector_chunks: List[Dict[str, Any]]

    # 图谱遍历结果
    graph_entities: List[Dict[str, Any]]
    graph_relations: List[Dict[str, Any]]

    # 合并后的上下文
    merged_context: str

    # 元数据
    total_chunks: int
    total_entities: int
    total_relations: int
    retrieval_method: str  # "vector_only" | "graph_only" | "hybrid"


class GraphRAGService:
    """
    GraphRAG 服务

    融合向量检索和知识图谱，提供更准确的检索结果。
    """

    def __init__(
        self,
        vector_search_service=None,
        neo4j_manager=None,
        rerank_service=None
    ):
        """
        初始化 GraphRAG 服务

        Args:
            vector_search_service: 向量检索服务
            neo4j_manager: Neo4j 管理器
            rerank_service: Rerank 服务
        """
        self.vector_search = vector_search_service
        self.neo4j = neo4j_manager
        self.rerank = rerank_service

    async def hybrid_retrieve(
        self,
        query: str,
        kb_id: str,
        top_k: int = 10,
        graph_depth: int = 2,
        max_graph_nodes: int = 20,
        enable_rerank: bool = True
    ) -> GraphRAGContext:
        """
        混合检索：向量 + 图谱

        Args:
            query: 查询文本
            kb_id: 知识库 ID
            top_k: 返回结果数量
            graph_depth: 图谱遍历深度
            max_graph_nodes: 最大图谱节点数
            enable_rerank: 是否启用 Rerank

        Returns:
            GraphRAG 检索上下文
        """
        logger.info(f"[GraphRAG] 开始混合检索: query='{query[:50]}...', kb_id={kb_id}")

        # 1. 向量检索获取相关文档块
        vector_chunks = await self._vector_retrieve(query, kb_id, top_k=top_k * 2)
        logger.debug(f"[GraphRAG] 向量检索获得 {len(vector_chunks)} 个结果")

        # 2. 提取文档块中的实体
        entities = self._extract_entities_from_chunks(vector_chunks)
        logger.debug(f"[GraphRAG] 从文档块提取 {len(entities)} 个实体")

        # 3. 图谱遍历
        graph_context = await self._traverse_graph(
            entities,
            depth=graph_depth,
            max_nodes=max_graph_nodes
        )
        logger.debug(
            f"[GraphRAG] 图谱遍历获得 {len(graph_context['entities'])} 个实体, "
            f"{len(graph_context['relations'])} 个关系"
        )

        # 4. 合并上下文
        merged_context = self._merge_contexts(vector_chunks, graph_context)

        # 5. Rerank (可选)
        if enable_rerank and self.rerank:
            vector_chunks = await self._rerank_results(query, vector_chunks)
            logger.debug(f"[GraphRAG] Rerank 完成，保留 Top-{top_k}")

        # 6. 截取 Top-K
        final_chunks = vector_chunks[:top_k]

        # 构造返回结果
        result = GraphRAGContext(
            vector_chunks=final_chunks,
            graph_entities=graph_context["entities"],
            graph_relations=graph_context["relations"],
            merged_context=merged_context,
            total_chunks=len(final_chunks),
            total_entities=len(graph_context["entities"]),
            total_relations=len(graph_context["relations"]),
            retrieval_method="hybrid"
        )

        logger.info(
            f"[GraphRAG] 检索完成: {result.total_chunks} chunks, "
            f"{result.total_entities} entities, {result.total_relations} relations"
        )

        return result

    async def _vector_retrieve(
        self,
        query: str,
        kb_id: str,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        向量检索

        Args:
            query: 查询文本
            kb_id: 知识库 ID
            top_k: 返回数量

        Returns:
            文档块列表
        """
        if not self.vector_search:
            logger.warning("[GraphRAG] 向量检索服务未配置")
            return []

        try:
            # 调用向量检索服务
            results = await self.vector_search.search(
                query=query,
                kb_id=kb_id,
                top_k=top_k
            )
            return results

        except Exception as e:
            logger.error(f"[GraphRAG] 向量检索失败: {e}")
            return []

    def _extract_entities_from_chunks(
        self,
        chunks: List[Dict[str, Any]]
    ) -> List[str]:
        """
        从文档块中提取实体

        Args:
            chunks: 文档块列表

        Returns:
            实体名称列表
        """
        entities: Set[str] = set()

        for chunk in chunks:
            # 方法1: 从元数据中获取
            metadata = chunk.get("metadata", {})
            if "entity_mentions" in metadata:
                entity_mentions = metadata["entity_mentions"]
                if isinstance(entity_mentions, list):
                    entities.update(entity_mentions)

            # 方法2: 从 chunk 关联的实体获取（如果有）
            if "entities" in chunk:
                chunk_entities = chunk["entities"]
                if isinstance(chunk_entities, list):
                    entities.update(chunk_entities)

        return list(entities)

    async def _traverse_graph(
        self,
        entry_entities: List[str],
        depth: int = 2,
        max_nodes: int = 20
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        在知识图谱中遍历

        Args:
            entry_entities: 入口实体列表
            depth: 遍历深度
            max_nodes: 最大节点数

        Returns:
            图谱上下文 {"entities": [...], "relations": [...]}
        """
        if not self.neo4j or not entry_entities:
            return {"entities": [], "relations": []}

        try:
            # 构造 Cypher 查询
            cypher = f"""
                MATCH path = (start)-[*1..{depth}]-(connected)
                WHERE start.name IN $entry_entities
                WITH DISTINCT start, connected, relationships(path) as rels
                LIMIT {max_nodes}
                RETURN
                    collect(DISTINCT {{
                        id: id(start),
                        name: start.name,
                        type: labels(start)[0]
                    }}) as start_nodes,
                    collect(DISTINCT {{
                        id: id(connected),
                        name: connected.name,
                        type: labels(connected)[0]
                    }}) as connected_nodes,
                    collect(DISTINCT {{
                        source: start.name,
                        target: connected.name,
                        type: type(rels[0])
                    }}) as relations
            """

            # 执行查询
            with self.neo4j.driver.session(database="neo4j") as session:
                result = session.run(cypher, entry_entities=entry_entities)
                record = result.single()

                if record:
                    start_nodes = record["start_nodes"]
                    connected_nodes = record["connected_nodes"]
                    relations = record["relations"]

                    # 合并实体
                    all_entities = start_nodes + connected_nodes

                    # 去重
                    unique_entities = {}
                    for entity in all_entities:
                        if entity and "name" in entity:
                            unique_entities[entity["name"]] = entity

                    return {
                        "entities": list(unique_entities.values()),
                        "relations": relations
                    }

            return {"entities": [], "relations": []}

        except Exception as e:
            logger.error(f"[GraphRAG] 图谱遍历失败: {e}")
            return {"entities": [], "relations": []}

    def _merge_contexts(
        self,
        vector_chunks: List[Dict[str, Any]],
        graph_context: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        合并向量上下文和图谱上下文

        Args:
            vector_chunks: 向量检索结果
            graph_context: 图谱上下文

        Returns:
            合并后的文本上下文
        """
        merged_parts = []

        # 1. 文档块内容
        if vector_chunks:
            merged_parts.append("# 相关文档片段\n")
            for i, chunk in enumerate(vector_chunks[:10], 1):
                content = chunk.get("content", "")
                merged_parts.append(f"{i}. {content}\n")

        # 2. 实体信息
        entities = graph_context.get("entities", [])
        if entities:
            merged_parts.append("\n# 相关实体\n")
            for entity in entities[:10]:
                name = entity.get("name", "")
                entity_type = entity.get("type", "Entity")
                merged_parts.append(f"- {name} ({entity_type})\n")

        # 3. 关系信息
        relations = graph_context.get("relations", [])
        if relations:
            merged_parts.append("\n# 实体关系\n")
            for rel in relations[:10]:
                source = rel.get("source", "")
                target = rel.get("target", "")
                rel_type = rel.get("type", "RELATED_TO")
                merged_parts.append(f"- {source} --[{rel_type}]--> {target}\n")

        return "".join(merged_parts)

    async def _rerank_results(
        self,
        query: str,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rerank 检索结果

        Args:
            query: 查询文本
            chunks: 文档块列表

        Returns:
            重排序后的文档块列表
        """
        if not self.rerank:
            return chunks

        try:
            # 调用 Rerank 服务
            reranked = await self.rerank.rerank(
                query=query,
                documents=[c.get("content", "") for c in chunks]
            )

            # 按新的顺序重组
            reordered_chunks = []
            for item in reranked:
                index = item.get("index", 0)
                if 0 <= index < len(chunks):
                    chunk = chunks[index].copy()
                    chunk["rerank_score"] = item.get("score", 0.0)
                    reordered_chunks.append(chunk)

            return reordered_chunks

        except Exception as e:
            logger.error(f"[GraphRAG] Rerank 失败: {e}")
            return chunks

    async def vector_only_retrieve(
        self,
        query: str,
        kb_id: str,
        top_k: int = 10
    ) -> GraphRAGContext:
        """
        仅使用向量检索（快速模式）

        Args:
            query: 查询文本
            kb_id: 知识库 ID
            top_k: 返回数量

        Returns:
            检索上下文
        """
        vector_chunks = await self._vector_retrieve(query, kb_id, top_k=top_k)

        return GraphRAGContext(
            vector_chunks=vector_chunks,
            graph_entities=[],
            graph_relations=[],
            merged_context=self._chunks_to_text(vector_chunks),
            total_chunks=len(vector_chunks),
            total_entities=0,
            total_relations=0,
            retrieval_method="vector_only"
        )

    def _chunks_to_text(self, chunks: List[Dict[str, Any]]) -> str:
        """将文档块列表转为文本"""
        texts = []
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            texts.append(f"{i}. {content}")
        return "\n\n".join(texts)

    def classify_query_complexity(self, query: str) -> str:
        """
        分类查询复杂度

        Args:
            query: 查询文本

        Returns:
            "simple" | "complex" | "multi_hop"
        """
        # 简单规则分类（可以用 LLM 优化）
        query_lower = query.lower()

        # 多跳推理关键词
        multi_hop_keywords = ["为什么", "如何", "关系", "比较", "区别", "影响"]
        if any(kw in query_lower for kw in multi_hop_keywords):
            return "multi_hop"

        # 复杂查询关键词
        complex_keywords = ["分析", "详细", "解释", "说明", "原因"]
        if any(kw in query_lower for kw in complex_keywords):
            return "complex"

        # 默认简单查询
        return "simple"
