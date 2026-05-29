"""
质量保障节点（Agentic RAG 闭环）

实现 2026 业界标准的 RAG 智能化模式：
- RetrievalGrader: CRAG 风格检索评估
- QueryRewriter: 基于缺失方面改写 query，回流 rag_retrieval
- FaithfulnessChecker: Self-RAG 风格忠实度检查，识别幻觉句

这三个节点共同构成 Agentic RAG 的"自我纠错"闭环：
    rag_retrieval → grader → [rewrite → 回到 retrieval] → ... → faithfulness → [regenerate]
"""

import json
import logging
import re
from typing import Callable, List, Dict, Any, Optional, Tuple

from .state import AgentState

logger = logging.getLogger(__name__)


# =========================================================================
# RetrievalGrader: 检索结果评估器
# =========================================================================

class RetrievalGrader:
    """检索结果评估器（CRAG 风格）

    判断当前 rag_context 是否足以回答用户问题。
    充足 → 放行下游；不足 → 触发 QueryRewriter 回流重检。
    """

    SUFFICIENCY_THRESHOLD = 0.6

    def __init__(self, llm_service=None, threshold: float = SUFFICIENCY_THRESHOLD):
        self.llm_service = llm_service
        self.threshold = threshold

    def as_node(self) -> Callable:
        async def grade_node(state: AgentState) -> AgentState:
            return await self.grade(state)
        return grade_node

    async def grade(self, state: AgentState) -> AgentState:
        query = state.user_query
        chunks = state.rag_context or []

        logger.info(
            f"[RetrievalGrader] query={query[:40]!r}, chunks={len(chunks)}"
        )

        if not chunks:
            state.retrieval_quality_score = 0.0
            state.missing_aspects = ["没有检索到任何文档"]
            logger.info("[RetrievalGrader] 空检索，score=0.0")
            return state

        if self.llm_service is not None:
            score, missing = await self._grade_with_llm(query, chunks)
        else:
            score, missing = self._grade_with_rules(query, chunks)

        state.retrieval_quality_score = score
        state.missing_aspects = missing
        logger.info(
            f"[RetrievalGrader] score={score:.2f}, missing={missing[:2]}, "
            f"iter={state.retrieval_iterations}/{state.max_retrieval_iterations}"
        )
        return state

    async def _grade_with_llm(
        self, query: str, chunks: List[Dict[str, Any]]
    ) -> Tuple[float, List[str]]:
        chunk_text = "\n\n".join(
            f"[{i+1}] {c.get('content', '')[:300]}"
            for i, c in enumerate(chunks[:5])
        )
        prompt = f"""你是一个检索质量评估专家。判断下面的检索结果是否足够回答用户问题。

问题：{query}

检索结果：
{chunk_text}

请按下列 JSON 格式返回（只返回 JSON，不要其他文字）：
{{
  "score": 0.85,
  "is_sufficient": true,
  "missing_aspects": ["可能缺失的方面1", "可能缺失的方面2"]
}}

评分标准：
- score >= 0.8：完全充足，可以直接生成答案
- 0.6 <= score < 0.8：基本充足，少量缺失
- score < 0.6：不充足，必须补检"""

        try:
            response = await self.llm_service.generate(prompt, max_tokens=300)
            data = self._extract_json(response)
            score = float(data.get("score", 0.0))
            missing = data.get("missing_aspects", []) or []
            return max(0.0, min(1.0, score)), [str(m) for m in missing[:5]]
        except Exception as e:
            logger.warning(f"[RetrievalGrader] LLM 评估失败，降级到规则: {e}")
            return self._grade_with_rules(query, chunks)

    def _grade_with_rules(
        self, query: str, chunks: List[Dict[str, Any]]
    ) -> Tuple[float, List[str]]:
        if not chunks:
            return 0.0, ["没有检索到任何文档"]

        # 关键词覆盖率
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return 0.5, []

        matched_chunks = 0
        for c in chunks[:5]:
            content = (c.get("content", "") or "").lower()
            hits = sum(1 for t in query_tokens if t in content)
            if hits >= max(1, len(query_tokens) // 3):
                matched_chunks += 1

        coverage = matched_chunks / min(5, len(chunks))
        count_factor = min(1.0, len(chunks) / 5.0)
        score = 0.6 * coverage + 0.4 * count_factor

        missing: List[str] = []
        if score < self.threshold:
            missing.append("结果与问题关键词匹配度低，需补检")
        return score, missing

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        # 中英混合简易分词：单字 + 连续英文/数字
        tokens: List[str] = []
        for m in re.findall(r"[a-zA-Z0-9]+|[一-鿿]", text or ""):
            t = m.lower()
            if len(t) > 1 or "一" <= t <= "鿿":
                tokens.append(t)
        # 去停用词（极简）
        stop = {"的", "是", "了", "在", "和", "与", "或", "the", "a", "an", "is", "are"}
        return [t for t in tokens if t not in stop]

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        if not text:
            return {}
        # 尝试直接 parse
        try:
            return json.loads(text)
        except Exception:
            pass
        # 抽取第一个 {...} 块
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
        return {}


# =========================================================================
# QueryRewriter: 查询改写器
# =========================================================================

class QueryRewriter:
    """基于缺失方面改写 query，回流到 rag_retrieval 重检。

    改写后清空 rag_context，递增 retrieval_iterations。
    """

    def __init__(self, llm_service=None):
        self.llm_service = llm_service

    def as_node(self) -> Callable:
        async def rewrite_node(state: AgentState) -> AgentState:
            return await self.rewrite(state)
        return rewrite_node

    async def rewrite(self, state: AgentState) -> AgentState:
        original = state.user_query
        missing = state.missing_aspects or []
        iter_count = state.retrieval_iterations

        logger.info(
            f"[QueryRewriter] iter={iter_count}, "
            f"missing={missing[:2]}, original={original[:40]!r}"
        )

        if self.llm_service is not None and missing:
            rewritten = await self._rewrite_with_llm(original, missing)
        else:
            rewritten = self._rewrite_with_rules(original, missing)

        state.rewritten_query = rewritten
        state.retrieval_iterations = iter_count + 1
        # 清空旧上下文，下一轮 rag_retrieval 用新 query 重检
        state.rag_context = []
        # 清空旧评估
        state.retrieval_quality_score = None
        state.missing_aspects = []

        logger.info(f"[QueryRewriter] rewritten={rewritten[:60]!r}")
        return state

    async def _rewrite_with_llm(self, query: str, missing: List[str]) -> str:
        missing_text = "、".join(missing[:3])
        prompt = f"""请改写下面的检索查询，让它能更好地命中缺失的信息方面。

原始查询：{query}
当前缺失的方面：{missing_text}

要求：
- 保持原始意图不变
- 显式包含缺失方面的关键词
- 不要加额外解释，直接返回改写后的查询文本"""

        try:
            response = await self.llm_service.generate(prompt, max_tokens=120)
            text = (response or "").strip().strip('"').strip("'")
            return text or self._rewrite_with_rules(query, missing)
        except Exception as e:
            logger.warning(f"[QueryRewriter] LLM 改写失败: {e}")
            return self._rewrite_with_rules(query, missing)

    @staticmethod
    def _rewrite_with_rules(query: str, missing: List[str]) -> str:
        if not missing:
            return f"详细说明：{query}"
        aspect = missing[0]
        return f"{query}，特别是关于{aspect}的具体信息"


# =========================================================================
# FaithfulnessChecker: 忠实度检查器
# =========================================================================

class FaithfulnessChecker:
    """逐句核对生成答案是否在 rag_context 中有依据（Self-RAG 风格）。

    score < threshold 且未达 regenerate 上限 → 触发重生成。
    """

    DEFAULT_THRESHOLD = 0.7

    def __init__(self, llm_service=None, threshold: float = DEFAULT_THRESHOLD):
        self.llm_service = llm_service
        self.threshold = threshold

    def as_node(self) -> Callable:
        async def check_node(state: AgentState) -> AgentState:
            return await self.check(state)
        return check_node

    async def check(self, state: AgentState) -> AgentState:
        answer = state.aggregated_response or ""
        chunks = state.rag_context or []

        # 没答案或没引用上下文 → 跳过
        if not answer.strip() or not chunks:
            state.faithfulness_score = 1.0
            state.unfaithful_sentences = []
            logger.info("[FaithfulnessChecker] 无答案或无 context，跳过")
            return state

        if self.llm_service is not None:
            score, unfaithful = await self._check_with_llm(answer, chunks)
        else:
            score, unfaithful = self._check_with_rules(answer, chunks)

        state.faithfulness_score = score
        state.unfaithful_sentences = unfaithful

        logger.info(
            f"[FaithfulnessChecker] score={score:.2f}, "
            f"unfaithful={len(unfaithful)}, "
            f"regen={state.regenerate_count}/{state.max_regenerate_count}"
        )
        return state

    async def _check_with_llm(
        self, answer: str, chunks: List[Dict[str, Any]]
    ) -> Tuple[float, List[str]]:
        chunk_text = "\n\n".join(
            f"[{i+1}] {c.get('content', '')[:300]}"
            for i, c in enumerate(chunks[:8])
        )
        prompt = f"""你是事实核查专家。判断下面的"答案"中是否每一句话都有"参考资料"作为依据。

答案：
{answer}

参考资料：
{chunk_text}

请按下列 JSON 格式返回（只返回 JSON）：
{{
  "score": 0.85,
  "unfaithful_sentences": ["没有依据的句子1", "没有依据的句子2"]
}}

评分标准：
- 1.0：每句都有依据
- 0.7-0.9：少量句子缺乏明确依据
- <0.7：存在明显幻觉或编造"""

        try:
            response = await self.llm_service.generate(prompt, max_tokens=400)
            data = RetrievalGrader._extract_json(response)
            score = float(data.get("score", 1.0))
            unfaithful = data.get("unfaithful_sentences", []) or []
            return (
                max(0.0, min(1.0, score)),
                [str(s) for s in unfaithful[:10]],
            )
        except Exception as e:
            logger.warning(f"[FaithfulnessChecker] LLM 核查失败，降级到规则: {e}")
            return self._check_with_rules(answer, chunks)

    def _check_with_rules(
        self, answer: str, chunks: List[Dict[str, Any]]
    ) -> Tuple[float, List[str]]:
        # 简单规则：按句拆分答案，统计每句的关键词在 context 中是否出现
        sentences = self._split_sentences(answer)
        if not sentences:
            return 1.0, []

        context_text = " ".join(
            (c.get("content", "") or "").lower() for c in chunks
        )

        faithful = 0
        unfaithful: List[str] = []
        for s in sentences:
            tokens = RetrievalGrader._tokenize(s)
            if not tokens:
                faithful += 1
                continue
            hits = sum(1 for t in tokens if t in context_text)
            ratio = hits / len(tokens)
            if ratio >= 0.4:
                faithful += 1
            else:
                unfaithful.append(s.strip()[:120])

        score = faithful / len(sentences)
        return score, unfaithful[:5]

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        # 中英文句号、问号、叹号、换行
        parts = re.split(r"(?<=[。！？!?\.])\s*|\n+", text or "")
        return [p for p in (s.strip() for s in parts) if p]
