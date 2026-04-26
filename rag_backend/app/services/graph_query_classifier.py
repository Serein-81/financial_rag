"""
图谱查询分类器 - 判断是否需要调用图谱检索

设计原则：
1. 快速规则匹配优先 - 处理常见模式，避免LLM调用开销
2. 可选的LLM辅助判断 - 处理复杂场景
3. 实体检测 - 识别查询中的实体名
4. 性能优先 - 默认走RAG，避免不必要的图谱调用
"""

import re
import logging
from enum import Enum
from typing import List, Tuple, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class GraphQueryType(str, Enum):
    """图谱查询类型"""
    ENTITY_RELATION = "ENTITY_RELATION"
    ENTITY_ATTRIBUTE = "ENTITY_ATTRIBUTE"
    GRAPH_PATH = "GRAPH_PATH"
    NONE = "NONE"


class GraphQueryClassifier:
    """
    图谱查询分类器
    
    判断用户查询是否需要调用图谱检索，采用多级判断策略：
    1. 快速规则匹配 - RAG强模式（直接跳过）
    2. 快速规则匹配 - 图谱强模式
    3. 实体检测 + 关键词判断
    4. LLM辅助判断（可选，默认关闭以提升性能）
    """
    
    GRAPH_STRONG_PATTERNS: List[str] = [
        r'关系',
        r'和.*合作',
        r'跟.*合作',
        r'[续签]?[约合同]',
        r'签约',
        r'客户.*有哪些',
        r'供应商',
        r'供应链',
        r'合作伙伴',
        r'联系人',
        r'上下游',
        r'关联.*公司',
        r'股东',
        r'法人',
        r'客户.*合作',
        r'签约.*客户',
    ]
    
    RAG_STRONG_PATTERNS: List[str] = [
        r'是什么',
        r'怎么做',
        r'怎么用',
        r'教程',
        r'功能',
        r'解释',
        r'定义',
        r'原理',
        r'步骤',
        r'方法',
        r'代码',
        r'示例',
        r'政策.*解读',
        r'文档',
        r'帮助',
        r'介绍',
        r'使用.*指南',
    ]
    
    GRAPH_KEYWORDS: List[str] = [
        '关系', '合作', '签约', '客户', '供应商', '联系人',
        '上下游', '关联', '股东', '法人', '续约', '续签',
    ]
    
    def __init__(self):
        self._compiled_graph_patterns: Optional[List[re.Pattern]] = None
        self._compiled_rag_patterns: Optional[List[re.Pattern]] = None
        self._enable_llm_fallback = getattr(settings, 'GRAPH_CLASSIFIER_LLM_FALLBACK', False)
        logger.info(f"[GraphQueryClassifier] 初始化完成，LLM回退: {self._enable_llm_fallback}")
    
    @property
    def graph_patterns(self) -> List[re.Pattern]:
        """延迟编译图谱模式"""
        if self._compiled_graph_patterns is None:
            self._compiled_graph_patterns = [
                re.compile(pattern, re.IGNORECASE) 
                for pattern in self.GRAPH_STRONG_PATTERNS
            ]
        return self._compiled_graph_patterns
    
    @property
    def rag_patterns(self) -> List[re.Pattern]:
        """延迟编译RAG模式"""
        if self._compiled_rag_patterns is None:
            self._compiled_rag_patterns = [
                re.compile(pattern, re.IGNORECASE) 
                for pattern in self.RAG_STRONG_PATTERNS
            ]
        return self._compiled_rag_patterns
    
    async def classify(self, query: str) -> Tuple[GraphQueryType, bool]:
        """
        分类查询并返回是否需要图谱检索
        
        Args:
            query: 用户查询
            
        Returns:
            (GraphQueryType, 是否需要图谱)
        """
        if not getattr(settings, 'ENABLE_KNOWLEDGE_GRAPH', False):
            logger.debug("[GraphQueryClassifier] 知识图谱未启用，跳过")
            return GraphQueryType.NONE, False
        
        if not query or not query.strip():
            logger.debug("[GraphQueryClassifier] 空查询，跳过")
            return GraphQueryType.NONE, False
        
        query = query.strip()
        
        try:
            has_graph_keywords = self._has_graph_keywords(query)
            has_entities = bool(self._extract_entities(query))
            
            if has_graph_keywords and has_entities:
                logger.info(f"[GraphQueryClassifier] 检测到图谱关键词+实体，使用图谱: {query[:30]}...")
                return GraphQueryType.ENTITY_RELATION, True
            
            graph_result = self._matches_graph_strong_patterns(query)
            if graph_result:
                logger.info(f"[GraphQueryClassifier] 图谱强模式匹配，使用图谱: {query[:30]}...")
                return GraphQueryType.ENTITY_RELATION, True
            
            rag_result = self._matches_rag_strong_patterns(query)
            if rag_result:
                logger.debug(f"[GraphQueryClassifier] RAG强模式匹配，跳过图谱: {query[:30]}...")
                return GraphQueryType.NONE, False
            
            if self._enable_llm_fallback:
                llm_result = await self._llm_classify(query)
                if llm_result:
                    return GraphQueryType.ENTITY_RELATION, True
            
            logger.debug(f"[GraphQueryClassifier] 默认RAG模式，不使用图谱: {query[:30]}...")
            return GraphQueryType.NONE, False
            
        except Exception as e:
            logger.error(f"[GraphQueryClassifier] 分类失败: {e}", exc_info=True)
            return GraphQueryType.NONE, False
    
    def _matches_rag_strong_patterns(self, query: str) -> bool:
        """检查是否匹配RAG强模式"""
        for pattern in self.rag_patterns:
            if pattern.search(query):
                return True
        return False
    
    def _matches_graph_strong_patterns(self, query: str) -> bool:
        """检查是否匹配图谱强模式"""
        for pattern in self.graph_patterns:
            if pattern.search(query):
                return True
        return False
    
    def _extract_entities(self, query: str) -> List[str]:
        """提取查询中的实体名"""
        entities = []
        patterns = [
            r'[A-Z][a-zA-Z]{2,}(?:\s*[A-Z][a-zA-Z]{2,})*',
            r'[\u4e00-\u9fa5]{2,4}(?:\s*[\u4e00-\u9fa5]{2,4})*',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query)
            entities.extend(matches)
        
        seen = set()
        unique_entities = []
        for e in entities:
            if e not in seen and len(e) >= 2:
                seen.add(e)
                unique_entities.append(e)
        
        return unique_entities
    
    def _has_graph_keywords(self, query: str) -> bool:
        """检查是否包含图谱相关关键词"""
        for keyword in self.GRAPH_KEYWORDS:
            if keyword in query:
                return True
        return False
    
    async def _llm_classify(self, query: str) -> bool:
        """使用LLM判断是否需要图谱（可选）"""
        try:
            from app.services.llm_service import llm_service
            
            prompt = f"""判断以下用户问题是否需要查询知识图谱。

【知识图谱】存储实体（客户、公司、人）和关系（合作、签约、供应链）
【知识库】存储文档内容（政策、教程、手册）

需要图谱："谁和谁合作"、"客户A的合同有哪些"
不需要图谱："什么是XXX"、"怎么做"、"项目功能"

问题：{query}

回答 GRAPH 或 RAG："""
            
            result = await llm_service.get_answer(prompt, [], [])
            return "GRAPH" in result.upper()
            
        except Exception as e:
            logger.warning(f"[GraphQueryClassifier] LLM判断失败: {e}")
            return False


graph_query_classifier = GraphQueryClassifier()
