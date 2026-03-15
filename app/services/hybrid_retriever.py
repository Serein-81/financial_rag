"""
混合检索服务
实现向量检索 + 图检索的融合
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.knowledge_graph.neo4j_manager import Neo4jManager
from app.models.semantic_memory import SemanticMemory
from app.schemas.knowledge_graph import SearchResult

logger = logging.getLogger(__name__)


class HybridRetriever:
    """混合检索器"""
    
    def __init__(self, neo4j_manager: Neo4jManager):
        self.neo4j_manager = neo4j_manager
    
    async def retrieve(
        self,
        query: str,
        db: Session,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        top_k: int = 5,
        vector_weight: float = 0.7,
        graph_weight: float = 0.3,
        use_graph: bool = True
    ) -> Tuple[List[SearchResult], Dict[str, int]]:
        """
        混合检索
        
        Args:
            query: 查询文本
            db: 数据库会话
            user_id: 用户 ID
            session_id: 会话 ID
            top_k: 返回结果数量
            vector_weight: 向量检索权重
            graph_weight: 图检索权重
            use_graph: 是否使用图检索
        
        Returns:
            (检索结果列表, 统计信息)
        """
        results = []
        stats = {"vector": 0, "graph": 0, "total": 0}
        
        try:
            # 1. 向量检索
            vector_results = await self._vector_retrieve(
                query, db, user_id, session_id, top_k
            )
            stats["vector"] = len(vector_results)
            logger.info(f"向量检索返回 {len(vector_results)} 条结果")
            
            # 2. 图检索（如果启用）
            graph_results = []
            if use_graph:
                graph_results = await self._graph_retrieve(
                    query, user_id, session_id, top_k
                )
                stats["graph"] = len(graph_results)
                logger.info(f"图检索返回 {len(graph_results)} 条结果")
            
            # 3. 结果融合
            results = self._merge_results(
                vector_results,
                graph_results,
                vector_weight,
                graph_weight,
                top_k
            )
            stats["total"] = len(results)
            
            logger.info(f"混合检索完成，返回 {len(results)} 条结果")
            return results, stats
            
        except Exception as e:
            logger.error(f"混合检索失败: {e}", exc_info=True)
            return [], stats
    
    async def _vector_retrieve(
        self,
        query: str,
        db: Session,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        top_k: int = 5
    ) -> List[SearchResult]:
        """向量检索（基于现有的语义记忆）"""
        try:
            # 构建查询
            query_obj = db.query(SemanticMemory)
            
            if user_id:
                query_obj = query_obj.filter(SemanticMemory.user_id == user_id)
            if session_id:
                query_obj = query_obj.filter(SemanticMemory.session_id == session_id)
            
            # 简单的文本匹配（实际应该用向量相似度）
            # TODO: 集成向量数据库进行相似度检索
            memories = query_obj.filter(
                SemanticMemory.content.ilike(f"%{query}%")
            ).limit(top_k).all()
            
            results = []
            for memory in memories:
                results.append(SearchResult(
                    content=memory.content,
                    score=0.8,  # 默认分数
                    source="vector",
                    metadata={
                        "memory_id": memory.id,
                        "user_id": memory.user_id,
                        "session_id": memory.session_id,
                        "created_at": memory.created_at.isoformat() if memory.created_at else None
                    }
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"向量检索失败: {e}", exc_info=True)
            return []
    
    async def _graph_retrieve(
        self,
        query: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        top_k: int = 5
    ) -> List[SearchResult]:
        """图检索（基于知识图谱）"""
        try:
            # 1. 从查询中提取关键实体
            # TODO: 使用 NER 或 LLM 提取查询中的实体
            # 这里简化处理，直接用查询文本作为实体名
            
            # 2. 在图中查找相关实体
            related_entities = self.neo4j_manager.find_related_entities(
                entity_name=query,
                max_depth=2,
                limit=top_k
            )
            
            results = []
            for entity in related_entities:
                # 构建内容描述
                content = f"{entity['name']} ({entity['type']})"
                if entity.get("distance"):
                    content += f" - 距离: {entity['distance']}"
                
                results.append(SearchResult(
                    content=content,
                    score=1.0 / (entity.get("distance", 1) + 1),  # 距离越近分数越高
                    source="graph",
                    metadata={
                        "entity_name": entity["name"],
                        "entity_type": entity["type"],
                        "distance": entity.get("distance", 0)
                    }
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"图检索失败: {e}", exc_info=True)
            return []
    
    def _merge_results(
        self,
        vector_results: List[SearchResult],
        graph_results: List[SearchResult],
        vector_weight: float,
        graph_weight: float,
        top_k: int
    ) -> List[SearchResult]:
        """
        融合向量和图检索结果
        使用加权分数排序
        """
        # 调整分数
        for result in vector_results:
            result.score *= vector_weight
        
        for result in graph_results:
            result.score *= graph_weight
        
        # 合并并去重
        all_results = vector_results + graph_results
        
        # 按分数排序
        all_results.sort(key=lambda x: x.score, reverse=True)
        
        # 返回 top_k
        return all_results[:top_k]
    
    async def retrieve_by_entity(
        self,
        entity_name: str,
        max_depth: int = 2,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """根据实体检索相关信息"""
        try:
            return self.neo4j_manager.find_related_entities(
                entity_name=entity_name,
                max_depth=max_depth,
                limit=limit
            )
        except Exception as e:
            logger.error(f"实体检索失败: {e}", exc_info=True)
            return []
