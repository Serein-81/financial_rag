"""
图谱检索服务 - 从Neo4j中检索实体和关系

设计原则：
1. 复用现有的Neo4jManager
2. 支持租户隔离
3. 异步设计
4. 完整的错误处理和日志
5. 使用 jieba 进行中文分词实体提取
"""

import re
import logging
from typing import List, Dict, Any, Optional
from app.knowledge_graph.neo4j_manager import Neo4jManager
from app.core.config import settings

import jieba

logger = logging.getLogger(__name__)


class GraphRetriever:
    """
    图谱检索器
    
    从Neo4j知识图谱中检索实体和关系，为对话系统提供图谱上下文
    """
    
    ENTITY_PATTERNS: List[str] = [
        r'[A-Z][a-zA-Z]{2,}(?:\s*[A-Z][a-zA-Z]{2,})*',
    ]

    # 中文停用词：常见非实体词汇，过滤实体提取结果
    CN_STOP_WORDS: set = {
        '什么', '怎么', '如何', '为什么', '哪些', '哪个', '这个', '那个',
        '关系', '合作', '情况', '我们', '他们', '你们', '自己', '之间',
        '可以', '需要', '应该', '能够', '是否', '没有', '不是', '就是',
        '进行', '提供', '使用', '通过', '关于', '对于', '根据', '按照',
        '因为', '所以', '但是', '然而', '虽然', '如果', '而且', '或者',
        '一个', '这种', '这样', '那里', '这里', '方面', '方式', '方法',
        '步骤', '说明', '介绍', '描述', '包括', '属于', '具有', '采用',
        '最大', '最小', '全部', '所有', '主要', '重要', '基本', '相关',
        '人员', '信息', '内容', '数据', '文件', '更多', '其他', '不同',
        '以上', '以下', '目前', '当前', '已经', '正在', '多少', '多大',
        '多久', '何时', '什么', '怎么', '几点', '功能', '教程', '代码',
        '示例', '原理', '定义', '解释', '意思',
    }
    
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
        """
        基于 jieba 分词 + 正则的实体提取

        策略:
        1. 提取英文实体名（如 "Google", "Microsoft"）
        2. 使用 jieba 分词提取中文实体，过滤停用词和单字
        3. 去重
        """
        entities = []

        # 1. 提取英文实体
        for pattern in self.ENTITY_PATTERNS:
            matches = re.findall(pattern, query)
            entities.extend(matches)

        # 2. jieba 精确模式中文分词，保留长度 ≥ 2 的非停用词片段
        words = jieba.lcut(query)
        for word in words:
            word = word.strip()
            if len(word) >= 2 and word not in self.CN_STOP_WORDS and not any(stop in word for stop in self.CN_STOP_WORDS):
                entities.append(word)

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
