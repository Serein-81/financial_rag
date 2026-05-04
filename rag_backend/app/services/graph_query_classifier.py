"""
图谱查询分类器 - 判断是否需要调用图谱检索

设计原则：
1. 轻量LLM优先判断 - 使用简洁Prompt快速判断，提高准确性
2. 关键词规则回退 - LLM失败时使用原有的关键词匹配
3. 查询缓存 - 相同/相似查询避免重复调用LLM
4. 性能优先 - 默认走RAG，避免不必要的图谱调用
"""

import re
import time
import hashlib
import logging
from enum import Enum
from typing import List, Tuple, Optional, Dict
from app.core.config import settings

import jieba

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

    采用多级判断策略（可配置模式）：

    llm_first（默认）:
      1. 快速规则匹配 - RAG强模式（直接跳过，不走LLM）
      2. 缓存检查 - 相同查询避免重复调用LLM
      3. 轻量LLM判断 - 极简Prompt，快速返回GRAPH/RAG
      4. 关键词规则回退 - LLM超时/失败时降级使用
      5. 默认走RAG

    keyword_only（原有关键词模式，向后兼容）:
      1. 快速规则匹配 - RAG强模式（直接跳过）
      2. 图谱强模式匹配
      3. 实体检测 + 关键词判断
      4. 默认走RAG
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
        self._mode = getattr(settings, 'GRAPH_CLASSIFIER_MODE', 'llm_first')
        self._cache_ttl = getattr(settings, 'GRAPH_CLASSIFIER_CACHE_TTL', 300)
        self._classifier_model = getattr(
            settings, 'GRAPH_CLASSIFIER_MODEL', 'deepseek/deepseek-chat'
        )
        # 分类结果缓存: {md5_hash: (result_bool, timestamp)}
        self._cache: Dict[str, Tuple[bool, float]] = {}
        logger.info(
            f"[GraphQueryClassifier] 初始化完成 | 模式: {self._mode} | "
            f"缓存TTL: {self._cache_ttl}s | 模型: {self._classifier_model}"
        )

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

    def _get_cache_key(self, query: str) -> str:
        """生成缓存key（对查询内容hash）"""
        normalized = query.strip().lower()
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    def _get_cached(self, query: str) -> Optional[bool]:
        """从缓存获取分类结果，过期自动失效"""
        key = self._get_cache_key(query)
        if key in self._cache:
            result, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return result
            # 过期删除
            del self._cache[key]
        return None

    def _set_cache(self, query: str, result: bool):
        """设置缓存结果，缓存超过上限时清理过期条目"""
        key = self._get_cache_key(query)
        self._cache[key] = (result, time.time())
        if len(self._cache) > 1000:
            self._evict_expired()

    def _evict_expired(self):
        """清理过期缓存条目"""
        now = time.time()
        expired_keys = [
            k for k, (_, ts) in self._cache.items()
            if now - ts >= self._cache_ttl
        ]
        for k in expired_keys:
            del self._cache[k]
        if expired_keys:
            logger.debug(
                f"[GraphQueryClassifier] 清理了 {len(expired_keys)} 条过期缓存"
            )

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
            # 所有模式通用: RAG强模式优先检查（快速跳过不需要图谱的查询）
            # 放在最前面可以避免不必要的LLM调用
            if self._matches_rag_strong_patterns(query):
                logger.debug(
                    f"[GraphQueryClassifier] RAG强模式匹配，跳过图谱: {query[:30]}..."
                )
                return GraphQueryType.NONE, False

            if self._mode == 'llm_first':
                return await self._classify_llm_first(query)
            else:
                return self._classify_keyword_only(query)

        except Exception as e:
            logger.error(f"[GraphQueryClassifier] 分类失败: {e}", exc_info=True)
            return GraphQueryType.NONE, False

    async def _classify_llm_first(self, query: str) -> Tuple[GraphQueryType, bool]:
        """LLM优先模式：缓存→轻量LLM→关键词回退"""
        # 第1步: 检查缓存
        cached = self._get_cached(query)
        if cached is not None:
            if cached:
                logger.info(
                    f"[GraphQueryClassifier] 缓存命中，使用图谱: {query[:30]}..."
                )
                return GraphQueryType.ENTITY_RELATION, True
            else:
                logger.debug(
                    f"[GraphQueryClassifier] 缓存命中，跳过图谱: {query[:30]}..."
                )
                return GraphQueryType.NONE, False

        # 第2步: 轻量LLM判断
        llm_result = await self._llm_classify_lightweight(query)
        if llm_result is not None:
            self._set_cache(query, llm_result)
            if llm_result:
                logger.info(
                    f"[GraphQueryClassifier] LLM判定使用图谱: {query[:30]}..."
                )
                return GraphQueryType.ENTITY_RELATION, True
            else:
                logger.debug(
                    f"[GraphQueryClassifier] LLM判定跳过图谱: {query[:30]}..."
                )
                return GraphQueryType.NONE, False

        # 第3步: LLM失败/超时，回退到关键词规则
        logger.debug(
            f"[GraphQueryClassifier] LLM回退到关键词规则: {query[:30]}..."
        )
        return self._classify_keyword_only(query)

    def _classify_keyword_only(self, query: str) -> Tuple[GraphQueryType, bool]:
        """纯关键词模式：原有的规则匹配逻辑"""
        has_graph_keywords = self._has_graph_keywords(query)
        has_entities = bool(self._extract_entities(query))

        if has_graph_keywords and has_entities:
            logger.info(
                f"[GraphQueryClassifier] 关键词+实体，使用图谱: {query[:30]}..."
            )
            return GraphQueryType.ENTITY_RELATION, True

        if self._matches_graph_strong_patterns(query):
            logger.info(
                f"[GraphQueryClassifier] 图谱强模式匹配，使用图谱: {query[:30]}..."
            )
            return GraphQueryType.ENTITY_RELATION, True

        logger.debug(
            f"[GraphQueryClassifier] 默认RAG模式，不使用图谱: {query[:30]}..."
        )
        return GraphQueryType.NONE, False

    async def _llm_classify_lightweight(self, query: str) -> Optional[bool]:
        """
        轻量级LLM分类判断

        使用极简Prompt快速判断查询是否与实体关系相关。
        返回 True = 需要图谱, False = 不需要, None = LLM失败（触发回退）。

        注意: 不传 model 参数，使用 LLM 服务的默认模型。
        传参会导致 DeepSeek Adapter 的 LangSmith 路径产生 model 参数冲突。
        """
        try:
            from app.services.llm_service import llm_service

            prompt = (
                f"判断问题是否涉及【实体关系】（需要查知识图谱）。\n"
                f"需要图谱：查公司/人事/客户/合同关系\n"
                f"不需要：问知识/功能/教程/定义\n\n"
                f"问题：{query}\n"
                f"回答（GRAPH 或 RAG）："
            )

            result = await llm_service.get_answer(
                query=prompt,
                context_chunks=[],
                history=[],
            )
            answer = result.strip().upper()
            if "GRAPH" in answer:
                return True
            elif "RAG" in answer:
                return False
            # LLM返回了意外内容，触发回退
            logger.debug(
                f"[GraphQueryClassifier] LLM返回意外结果: "
                f"{answer[:30]}, 触发关键词回退"
            )
            return None

        except Exception as e:
            logger.warning(
                f"[GraphQueryClassifier] LLM分类失败(将回退到关键词): {e}"
            )
            return None

    # === 基础规则方法 ===

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

    # 中文停用词：非实体词汇，过滤实体提取结果
    CN_STOP_WORDS: set = {
        '什么', '怎么', '如何', '为什么', '哪些', '哪个', '这个', '那个',
        '关系', '合作', '情况', '我们', '他们', '你们', '自己', '之间',
        '可以', '需要', '应该', '能够', '是否', '没有', '不是', '就是',
        '进行', '提供', '使用', '通过', '关于', '对于', '根据', '按照',
        '因为', '所以', '但是', '然而', '虽然', '如果', '而且', '或者',
        '一个', '这种', '这样', '那里', '这里', '方面', '方式', '方法',
        '步骤', '说明', '介绍', '描述', '包括', '属于', '具有', '采用',
        '人员', '信息', '内容', '数据', '文件', '更多', '其他', '不同',
        '以上', '以下', '目前', '当前', '已经', '正在', '多少', '多大',
        '多久', '何时', '几点', '功能', '教程', '代码', '示例', '原理',
        '定义', '解释', '意思',
    }

    def _extract_entities(self, query: str) -> List[str]:
        """
        提取查询中可能的实体名

        策略:
        1. 提取英文实体名（如 "Google"）
        2. 使用 jieba 分词提取中文实体，过滤停用词和单字
        """
        entities = []

        # 1. 英文实体
        for match in re.findall(r'[A-Z][a-zA-Z]{2,}(?:\s*[A-Z][a-zA-Z]{2,})*', query):
            entities.append(match)

        # 2. jieba 精确模式中文分词，保留长度 ≥ 2 的非停用词片段
        words = jieba.lcut(query)
        for word in words:
            word = word.strip()
            if len(word) >= 2 and word not in self.CN_STOP_WORDS and not any(stop in word for stop in self.CN_STOP_WORDS):
                entities.append(word)

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


graph_query_classifier = GraphQueryClassifier()
