"""
Agentic RAG 节点实现

实现自主检索 Agent 的核心节点：
1. RetrievalPlanner - 规划检索策略
2. RetrievalExecutor - 执行检索
3. ResultEvaluator - 评估结果质量
4. ContextAggregator - 聚合上下文
"""

import logging
from typing import Dict, Any, List, Optional
import time
from datetime import datetime
from app.langgraph.agentic_rag_state import (
    AgenticRAGState,
    RetrievalStep,
    EvaluationResult
)

logger = logging.getLogger(__name__)


class RetrievalPlanner:
    """
    检索规划节点

    分析查询和当前状态，规划下一步检索策略。
    """

    def __init__(self, llm_service=None):
        """
        初始化规划器

        Args:
            llm_service: LLM 服务（用于复杂规划）
        """
        self.llm_service = llm_service

    async def plan(self, state: AgenticRAGState) -> AgenticRAGState:
        """
        规划检索策略

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        query = state["query"]
        iteration = state.get("iteration_count", 0)
        retrieval_history = state.get("retrieval_history", [])

        logger.info(f"[RetrievalPlanner] 规划第 {iteration + 1} 轮检索，查询: {query[:50]}...")

        # 首轮检索：直接使用原始查询
        if iteration == 0:
            plan = self._plan_first_retrieval(query, state)
        else:
            # 后续检索：基于评估结果规划
            evaluation = state.get("evaluation")
            plan = await self._plan_next_retrieval(query, evaluation, retrieval_history)

        # 更新状态
        state["current_query"] = plan["query"]
        state["next_action"] = plan["action"]

        logger.debug(
            f"[RetrievalPlanner] 计划: action={plan['action']}, "
            f"query={plan['query'][:50]}..."
        )

        return state

    def _plan_first_retrieval(
        self,
        query: str,
        state: AgenticRAGState
    ) -> Dict[str, Any]:
        """
        规划首次检索

        Args:
            query: 用户查询
            state: 当前状态

        Returns:
            检索计划
        """
        # 简单策略：根据查询复杂度选择检索方式
        complexity = self._classify_query_complexity(query)

        if complexity == "simple":
            action = "vector_search"
        elif complexity == "complex":
            action = "hybrid_search"  # 向量 + 图谱
        else:
            action = "multi_step_search"  # 多步检索

        return {
            "action": action,
            "query": query,
            "parameters": {
                "top_k": 10,
                "enable_rerank": True
            }
        }

    async def _plan_next_retrieval(
        self,
        original_query: str,
        evaluation: Optional[EvaluationResult],
        history: List[RetrievalStep]
    ) -> Dict[str, Any]:
        """
        规划后续检索

        Args:
            original_query: 原始查询
            evaluation: 评估结果
            history: 检索历史

        Returns:
            检索计划
        """
        if not evaluation:
            # 没有评估结果，使用默认策略
            return {
                "action": "vector_search",
                "query": original_query,
                "parameters": {"top_k": 10}
            }

        # LLM 智能改写（注入了 llm_service 时优先），失败/为空则回退规则改写
        if self.llm_service is not None:
            try:
                refined = await self._llm_rewrite_query(
                    original_query, evaluation, history
                )
                if refined:
                    return {
                        "action": "vector_search",
                        "query": refined,
                        "parameters": {"top_k": 5},
                    }
            except Exception as e:
                logger.warning(f"[RetrievalPlanner] LLM 查询改写失败，回退规则: {e}")

        # 分析缺失方面
        missing_aspects = evaluation.missing_aspects

        if missing_aspects:
            # 生成针对缺失方面的查询
            refined_query = self._refine_query_for_missing(
                original_query,
                missing_aspects
            )

            return {
                "action": "vector_search",
                "query": refined_query,
                "parameters": {"top_k": 5}
            }

        # 如果覆盖度低，尝试不同的检索方式
        if evaluation.coverage_score < 0.5:
            # 尝试图谱检索
            if not any(step.action == "graph_traverse" for step in history):
                return {
                    "action": "graph_traverse",
                    "query": original_query,
                    "parameters": {"depth": 2}
                }

        # 默认：使用改写后的查询重新检索
        return {
            "action": "vector_search",
            "query": f"详细说明：{original_query}",
            "parameters": {"top_k": 10}
        }

    async def _llm_rewrite_query(
        self,
        original_query: str,
        evaluation: EvaluationResult,
        history: List[RetrievalStep]
    ) -> Optional[str]:
        """用 LLM 基于评估缺失方面改写检索查询。

        返回改写后的查询；若 LLM 不可用、输出异常或与原查询无差异则返回 None。
        """
        prev_queries = [step.query for step in (history or [])][-3:]
        missing = "、".join(evaluation.missing_aspects or []) or "覆盖不足，需要更全面的信息"

        prompt = f"""你是检索查询改写助手。请基于已检索情况，生成一个新的中文检索查询，以补全当前缺失的信息。

原始问题：{original_query}
已检索过的查询：{prev_queries}
结果缺失的方面：{missing}
评估理由：{evaluation.reasoning}

要求：
1. 只输出改写后的查询本身，不要解释、不要加引号
2. 聚焦缺失方面，避免与"已检索过的查询"重复
3. 保持简洁，一句话即可"""

        response = await self.llm_service.generate(prompt, max_tokens=100)
        refined = (response or "").strip().strip('"').strip("“”").strip()

        # 防御：空、过短、或与原查询完全相同则视为无效
        if not refined or len(refined) < 2 or refined == original_query.strip():
            return None
        return refined

    def _refine_query_for_missing(
        self,
        original_query: str,
        missing_aspects: List[str]
    ) -> str:
        """
        针对缺失方面改写查询

        Args:
            original_query: 原始查询
            missing_aspects: 缺失方面列表

        Returns:
            改写后的查询
        """
        if not missing_aspects:
            return original_query

        # 简单策略：添加缺失方面到查询中
        aspect = missing_aspects[0]
        return f"{original_query}，特别是关于{aspect}的信息"

    def _classify_query_complexity(self, query: str) -> str:
        """
        分类查询复杂度

        Args:
            query: 查询文本

        Returns:
            "simple" | "complex" | "multi_hop"
        """
        query_lower = query.lower()

        # 多跳推理关键词
        multi_hop_keywords = ["为什么", "如何", "关系", "比较", "区别", "影响", "原因"]
        if any(kw in query_lower for kw in multi_hop_keywords):
            return "multi_hop"

        # 复杂查询关键词
        complex_keywords = ["分析", "详细", "解释", "说明"]
        if any(kw in query_lower for kw in complex_keywords):
            return "complex"

        return "simple"


class RetrievalExecutor:
    """
    检索执行节点

    根据规划执行具体的检索操作。
    """

    def __init__(
        self,
        vector_search_service=None,
        graph_search_service=None
    ):
        """
        初始化执行器

        Args:
            vector_search_service: 向量检索服务
            graph_search_service: 图谱检索服务
        """
        self.vector_search = vector_search_service
        self.graph_search = graph_search_service

    async def execute(self, state: AgenticRAGState) -> AgenticRAGState:
        """
        执行检索

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        action = state.get("next_action", "vector_search")
        query = state["current_query"]
        kb_id = state["kb_id"]
        iteration = state.get("iteration_count", 0)

        logger.info(f"[RetrievalExecutor] 执行检索: action={action}, iteration={iteration}")

        start_time = time.time()

        # 根据动作类型执行检索
        if action == "vector_search":
            results = await self._vector_search(query, kb_id)
        elif action == "hybrid_search":
            results = await self._hybrid_search(query, kb_id)
        elif action == "graph_traverse":
            results = await self._graph_traverse(query, kb_id)
        else:
            logger.warning(f"[RetrievalExecutor] 未知动作: {action}")
            results = []

        duration = time.time() - start_time

        # 记录检索步骤
        step = RetrievalStep(
            step_number=iteration + 1,
            action=action,
            query=query,
            parameters={},
            results=results,
            result_count=len(results),
            timestamp=datetime.now()
        )

        retrieval_history = state.get("retrieval_history", [])
        retrieval_history.append(step)

        # 更新状态
        state["retrieval_history"] = retrieval_history
        state["current_results"] = results
        state["iteration_count"] = iteration + 1

        # 累积结果（去重）
        all_results = state.get("all_results", [])
        existing_ids = {r.get("id") for r in all_results if "id" in r}

        for result in results:
            result_id = result.get("id")
            if result_id and result_id not in existing_ids:
                all_results.append(result)
                existing_ids.add(result_id)
            elif not result_id:
                all_results.append(result)

        state["all_results"] = all_results

        # 更新总检索时间
        total_time = state.get("total_retrieval_time", 0.0)
        state["total_retrieval_time"] = total_time + duration

        logger.debug(f"[RetrievalExecutor] 检索完成: {len(results)} 个结果，耗时 {duration:.2f}s")

        return state

    async def _vector_search(self, query: str, kb_id: str) -> List[Dict[str, Any]]:
        """向量检索"""
        if not self.vector_search:
            return []

        try:
            results = await self.vector_search.search(
                query=query,
                kb_id=kb_id,
                top_k=10
            )
            return results
        except Exception as e:
            logger.error(f"[RetrievalExecutor] 向量检索失败: {e}")
            return []

    async def _hybrid_search(self, query: str, kb_id: str) -> List[Dict[str, Any]]:
        """混合检索"""
        if not self.graph_search:
            return await self._vector_search(query, kb_id)

        try:
            result = await self.graph_search.hybrid_retrieve(
                query=query,
                kb_id=kb_id,
                top_k=10
            )
            return result.vector_chunks
        except Exception as e:
            logger.error(f"[RetrievalExecutor] 混合检索失败: {e}")
            return []

    async def _graph_traverse(self, query: str, kb_id: str) -> List[Dict[str, Any]]:
        """图谱遍历"""
        # 简化实现：返回空列表
        logger.info("[RetrievalExecutor] 图谱遍历功能待实现")
        return []


class ResultEvaluator:
    """
    结果评估节点

    评估检索结果是否足够回答问题。
    """

    def __init__(self, llm_service=None, threshold: float = 0.7, min_useful_score: float = 0.2):
        """
        初始化评估器

        Args:
            llm_service: LLM 服务
            threshold: 充分性阈值
        """
        self.llm_service = llm_service
        self.threshold = threshold
        # 前置短路阈值：某一轮结果整体分低于此值，视为"知识库基本无相关内容"，
        # 再检索/改写也无意义 → 提前停止，避免对通用知识类问题白跑后续轮次。
        # 取值保守（远低于充分性阈值 threshold），真正相关的企业问题分数会明显更高，不受影响。
        self.min_useful_score = min_useful_score

    async def evaluate(self, state: AgenticRAGState) -> AgenticRAGState:
        """
        评估检索结果

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        query = state["query"]
        all_results = state.get("all_results", [])
        iteration = state.get("iteration_count", 0)

        logger.info(f"[ResultEvaluator] 评估第 {iteration} 轮结果，共 {len(all_results)} 个")

        # 评估
        if self.llm_service:
            evaluation = await self._evaluate_with_llm(query, all_results)
        else:
            evaluation = self._evaluate_with_rules(query, all_results)

        # 更新状态
        state["evaluation"] = evaluation
        state["is_sufficient"] = evaluation.is_sufficient

        # 决策是否继续
        max_iterations = state.get("max_iterations", 3)
        should_continue = (
            not evaluation.is_sufficient and
            iteration < max_iterations
        )

        # 🔌 前置短路：本轮整体分极低（知识库基本无相关内容，如通用知识类问题），
        # 继续改写/检索也无意义，提前停止，避免白跑后续轮次的 检索+rerank+评估 LLM。
        short_circuited = False
        if should_continue and evaluation.overall_score < self.min_useful_score:
            should_continue = False
            short_circuited = True

        state["should_continue"] = should_continue

        logger.info(
            f"[ResultEvaluator] 评估结果: "
            f"sufficient={evaluation.is_sufficient}, "
            f"score={evaluation.overall_score:.2f}, "
            f"continue={should_continue}"
            + (f" | 🔌 前置短路(score<{self.min_useful_score})" if short_circuited else "")
        )

        return state

    @staticmethod
    def _extract_json(text: str) -> str:
        """从 LLM 输出中提取 JSON 串：去除 ```json``` 代码围栏、截取首个 { 到末个 }。"""
        if not text:
            return "{}"
        s = text.strip()
        if s.startswith("```"):
            # 去掉首行围栏（```json / ```）及结尾围栏
            s = s.split("\n", 1)[1] if "\n" in s else s
            if s.endswith("```"):
                s = s[: -3]
            s = s.strip()
        # 截取最外层花括号，容忍前后多余文字
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return s[start : end + 1]
        return s

    async def _evaluate_with_llm(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> EvaluationResult:
        """
        使用 LLM 评估结果

        Args:
            query: 查询
            results: 检索结果

        Returns:
            评估结果
        """
        # 构造评估 Prompt
        results_text = "\n\n".join([
            f"{i+1}. {r.get('content', '')[:200]}"
            for i, r in enumerate(results[:5])
        ])

        prompt = f"""评估以下检索结果是否足够回答问题。

问题: {query}

检索结果:
{results_text}

请评估:
1. 覆盖度 (0-1): 结果是否覆盖问题的主要方面
2. 相关性 (0-1): 结果与问题的相关程度
3. 完整性 (0-1): 是否有足够信息回答问题

返回 JSON:
{{
  "coverage_score": 0.8,
  "relevance_score": 0.9,
  "completeness_score": 0.7,
  "is_sufficient": true,
  "missing_aspects": ["缺失的方面1"],
  "reasoning": "简要说明"
}}

只返回 JSON，不要其他内容。"""

        try:
            response = await self.llm_service.generate(prompt, max_tokens=300)

            import json
            result = json.loads(self._extract_json(response))

            return EvaluationResult(
                is_sufficient=result.get("is_sufficient", False),
                coverage_score=result.get("coverage_score", 0.0),
                relevance_score=result.get("relevance_score", 0.0),
                completeness_score=result.get("completeness_score", 0.0),
                overall_score=(
                    result.get("coverage_score", 0.0) +
                    result.get("relevance_score", 0.0) +
                    result.get("completeness_score", 0.0)
                ) / 3,
                missing_aspects=result.get("missing_aspects", []),
                reasoning=result.get("reasoning", "")
            )

        except Exception as e:
            logger.error(f"[ResultEvaluator] LLM 评估失败: {e}")
            return self._evaluate_with_rules(query, results)

    def _evaluate_with_rules(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> EvaluationResult:
        """
        使用规则评估结果

        Args:
            query: 查询
            results: 检索结果

        Returns:
            评估结果
        """
        if not results:
            return EvaluationResult(
                is_sufficient=False,
                coverage_score=0.0,
                relevance_score=0.0,
                completeness_score=0.0,
                overall_score=0.0,
                missing_aspects=["没有找到相关信息"],
                reasoning="没有检索到任何结果"
            )

        # 简单规则：基于结果数量和查询关键词覆盖
        result_count = len(results)

        # 覆盖度：基于结果数量
        coverage_score = min(1.0, result_count / 5.0)

        # 相关性：基于查询关键词在结果中的出现
        query_keywords = set(query.lower().split())
        matched_count = 0

        for result in results[:5]:
            content = result.get("content", "").lower()
            if any(kw in content for kw in query_keywords):
                matched_count += 1

        relevance_score = matched_count / min(5, len(results)) if results else 0.0

        # 完整性：综合判断
        completeness_score = (coverage_score + relevance_score) / 2

        overall_score = (coverage_score + relevance_score + completeness_score) / 3

        is_sufficient = overall_score >= self.threshold

        return EvaluationResult(
            is_sufficient=is_sufficient,
            coverage_score=coverage_score,
            relevance_score=relevance_score,
            completeness_score=completeness_score,
            overall_score=overall_score,
            missing_aspects=[] if is_sufficient else ["需要更多相关信息"],
            reasoning=f"基于规则评估：{result_count} 个结果，综合评分 {overall_score:.2f}"
        )


class ContextAggregator:
    """
    上下文聚合节点

    将多轮检索的结果聚合为最终上下文。
    """

    async def aggregate(self, state: AgenticRAGState) -> AgenticRAGState:
        """
        聚合上下文

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        all_results = state.get("all_results", [])

        logger.info(f"[ContextAggregator] 聚合 {len(all_results)} 个检索结果")

        # 去重和排序
        unique_results = self._deduplicate_results(all_results)

        # 选择 Top-K
        top_k = 10
        final_chunks = unique_results[:top_k]

        # 生成最终上下文
        final_context = self._generate_context(final_chunks)

        # 更新状态
        state["final_chunks"] = final_chunks
        state["final_context"] = final_context
        state["retrieval_method"] = "agentic_rag"

        logger.debug(f"[ContextAggregator] 聚合完成: {len(final_chunks)} 个最终结果")

        return state

    def _deduplicate_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        去重结果

        Args:
            results: 结果列表

        Returns:
            去重后的结果
        """
        seen_contents = set()
        unique_results = []

        for result in results:
            content = result.get("content", "")
            # 使用内容前100字符作为去重标识
            content_key = content[:100]

            if content_key not in seen_contents:
                seen_contents.add(content_key)
                unique_results.append(result)

        # 按分数排序（如果有）
        unique_results.sort(
            key=lambda x: x.get("score", 0.0),
            reverse=True
        )

        return unique_results

    def _generate_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        生成最终上下文文本

        Args:
            chunks: 文档块列表

        Returns:
            上下文文本
        """
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            context_parts.append(f"{i}. {content}")

        return "\n\n".join(context_parts)
