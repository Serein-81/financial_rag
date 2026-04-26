"""
图谱检索服务 - 从Neo4j中检索实体和关系

设计原则：
1. 复用现有的Neo4jManager
2. 支持租户隔离
3. 异步设计
4. 完整的错误处理和日志
5. 可选的LLM辅助实体提取
"""

import re
import logging
from typing import List, Dict, Any, Optional
from app.knowledge_graph.neo4j_manager import Neo4jManager
from app.core.config import settings

logger = logging.getLogger(__name__)


class GraphRetriever:
    """
    图谱检索器
    
    从Neo4j知识图谱中检索实体和关系，为对话系统提供图谱上下文
    """
    
    ENTITY_PATTERNS: List[str] = [
        r'[A-Z][a-zA-Z]{2,}(?:\s*[A-Z][a-zA-Z]{2,})*',
        r'[\u4e00-\u9fa5]{2,4}(?:\s*[\u4e00-\u9fa5]{2,4})*',
    ]
    
    def __init__(self):
        self._neo4j_manager: Optional[Neo4jManager] = None
        self._max_depth = getattr(settings, 'GRAPH_RETRIEVAL_DEPTH', 2)
        self._max_entities = getattr(settings, 'GRAPH_MAX_ENTITIES', 10)
        self._enable_llm_extraction = getattr(settings, 'GRAPH_LLM_EXTRACTION', False)
        logger.info(f"[GraphRetriever] 初始化完成，深度:{self._max_depth}, 最大实体:{self._max_entities}")
    
    @property
    def neo4j_manager(self) -> Neo4jManager:
        """延迟初始化Neo4j管理器"""
        if self._neo4j_manager is None:
            self._neo4j_manager = Neo4jManager(
                uri=settings.NEO4J_URI,
                user=settings.NEO4J_USER,
                password=settings.NEO4J_PASSWORD
            )
        return self._neo4j_manager
    
    async def extract_entities_from_query(self, query: str) -> List[str]:
        """
        从查询中提取可能的实体名
        
        Args:
            query: 用户查询文本
            
        Returns:
            可能的实体名列表
        """
        entities = self._rule_based_extraction(query)
        
        if not entities and self._enable_llm_extraction:
            entities = await self._llm_extraction(query)
        
        return entities[:5]
    
    def _rule_based_extraction(self, query: str) -> List[str]:
        """基于规则的实体提取"""
        entities = []
        
        for pattern in self.ENTITY_PATTERNS:
            matches = re.findall(pattern, query)
            entities.extend(matches)
        
        seen = set()
        unique_entities = []
        for e in entities:
            normalized = e.strip()
            if normalized not in seen and len(normalized) >= 2:
                seen.add(normalized)
                unique_entities.append(normalized)
        
        return unique_entities
    
    async def _llm_extraction(self, query: str) -> List[str]:
        """使用LLM提取实体（可选）"""
        try:
            from app.services.llm_service import llm_service
            
            prompt = f"""从以下查询中提取可能的企业/客户/人名实体：
            
查询："{query}"

只返回实体名称，多个实体用逗号分隔。如果没有找到实体，返回"无"。"""
            
            response = await llm_service.get_answer(prompt, [], [])
            
            if "无" in response or not response.strip():
                return []
            
            entities = [e.strip() for e in response.split(",")]
            return [e for e in entities if e]
            
        except Exception as e:
            logger.warning(f"[GraphRetriever] LLM实体提取失败: {e}")
            return []
    
    async def retrieve_context(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 5,
        max_depth: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        检索图谱上下文
        
        Args:
            query: 用户查询
            tenant_id: 租户ID（必需，用于租户隔离）
            top_k: 返回结果数
            max_depth: 图遍历深度（可选）
            
        Returns:
            {
                "entities": [...],
                "relations": [...],
                "context": "...",
                "found": bool
            }
        """
        if not getattr(settings, 'ENABLE_KNOWLEDGE_GRAPH', False):
            logger.debug("[GraphRetriever] 知识图谱未启用")
            return self._empty_result()
        
        if not tenant_id:
            logger.warning("[GraphRetriever] 缺少tenant_id，无法检索")
            return self._empty_result()
        
        try:
            depth = max_depth or self._max_depth
            
            entity_names = await self.extract_entities_from_query(query)
            
            if not entity_names:
                logger.debug(f"[GraphRetriever] 未从查询中提取到实体: {query[:30]}...")
                return self._empty_result()
            
            logger.info(f"[GraphRetriever] 从查询中提取到实体: {entity_names}")
            
            all_entities = []
            all_relations = []
            
            for entity_name in entity_names[:3]:
                related = self.neo4j_manager.find_related_entities(
                    entity_name=entity_name,
                    tenant_id=str(tenant_id),
                    max_depth=depth,
                    limit=top_k
                )
                
                for entity in related:
                    entity_info = {
                        "name": entity.get("name", ""),
                        "type": entity.get("type", "UNKNOWN"),
                        "distance": entity.get("distance", 0),
                        "properties": entity.get("properties") or {}
                    }
                    all_entities.append(entity_info)
                    
                    if entity.get("distance", 0) == 1:
                        relation_desc = f"{entity_name} → {entity.get('name', '')}"
                        all_relations.append(relation_desc)
            
            seen = set()
            unique_entities = []
            for e in all_entities:
                key = f"{e['name']}_{e['type']}"
                if key not in seen:
                    seen.add(key)
                    unique_entities.append(e)
            
            context = self._format_context(unique_entities, all_relations, query)
            
            result = {
                "entities": unique_entities[:top_k],
                "relations": all_relations[:top_k * 2],
                "context": context,
                "found": len(unique_entities) > 0,
                "query_entities": entity_names
            }
            
            logger.info(f"[GraphRetriever] 返回 {len(unique_entities)} 个实体")
            return result
            
        except Exception as e:
            logger.error(f"[GraphRetriever] 检索失败: {e}", exc_info=True)
            return self._empty_result()
    
    def _format_context(
        self,
        entities: List[Dict],
        relations: List[str],
        query: str
    ) -> str:
        """格式化图谱上下文"""
        if not entities:
            return ""
        
        context_parts = ["【知识图谱信息】\n"]
        
        type_groups = {}
        for entity in entities:
            entity_type = entity.get("type", "UNKNOWN")
            if entity_type not in type_groups:
                type_groups[entity_type] = []
            type_groups[entity_type].append(entity)
        
        context_parts.append("相关实体：\n")
        for entity_type, type_entities in type_groups.items():
            names = [e["name"] for e in type_entities[:5]]
            context_parts.append(f"  [{entity_type}] {', '.join(names)}\n")
        
        if relations:
            context_parts.append("\n关系信息：\n")
            for relation in relations[:10]:
                context_parts.append(f"  - {relation}\n")
        
        return "".join(context_parts)
    
    def _empty_result(self) -> Dict[str, Any]:
        """返回空结果"""
        return {
            "entities": [],
            "relations": [],
            "context": "",
            "found": False,
            "query_entities": []
        }


graph_retriever = GraphRetriever()
