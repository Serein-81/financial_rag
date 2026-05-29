"""
生成评估器

评估 RAG 系统的生成质量，使用 LLM-as-Judge 和传统指标。
"""

import logging
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GenerationMetrics:
    """
    生成评估指标

    包含准确性、完整性、相关性、流畅性等指标。
    """
    accuracy_score: float = 0.0  # 准确性 0-5
    completeness_score: float = 0.0  # 完整性 0-5
    relevance_score: float = 0.0  # 相关性 0-5
    fluency_score: float = 0.0  # 流畅性 0-5
    overall_score: float = 0.0  # 综合评分 0-5
    has_hallucination: bool = False  # 是否有幻觉
    reasoning: str = ""  # 评估理由

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "accuracy_score": self.accuracy_score,
            "completeness_score": self.completeness_score,
            "relevance_score": self.relevance_score,
            "fluency_score": self.fluency_score,
            "overall_score": self.overall_score,
            "has_hallucination": self.has_hallucination,
            "reasoning": self.reasoning
        }


class GenerationEvaluator:
    """
    生成评估器

    使用 LLM 评估生成质量。
    """

    def __init__(self, llm_service=None):
        """
        初始化评估器

        Args:
            llm_service: LLM 服务（用于 LLM-as-Judge）
        """
        self.llm_service = llm_service

    async def evaluate(
        self,
        query: str,
        generated_answer: str,
        expected_answer: str,
        context: Optional[str] = None
    ) -> GenerationMetrics:
        """
        评估生成答案

        Args:
            query: 用户查询
            generated_answer: 生成的答案
            expected_answer: 期望答案
            context: 上下文（可选）

        Returns:
            GenerationMetrics: 评估指标
        """
        if self.llm_service:
            return await self._evaluate_with_llm(
                query, generated_answer, expected_answer, context
            )
        else:
            return self._evaluate_with_rules(
                query, generated_answer, expected_answer
            )

    async def _evaluate_with_llm(
        self,
        query: str,
        generated_answer: str,
        expected_answer: str,
        context: Optional[str] = None
    ) -> GenerationMetrics:
        """
        使用 LLM 评估 (LLM-as-Judge)

        Args:
            query: 用户查询
            generated_answer: 生成的答案
            expected_answer: 期望答案
            context: 上下文

        Returns:
            GenerationMetrics: 评估指标
        """
        prompt = self._build_evaluation_prompt(
            query, generated_answer, expected_answer, context
        )

        try:
            response = await self.llm_service.generate(prompt, max_tokens=800)

            # 解析 JSON 响应
            result = json.loads(response)

            metrics = GenerationMetrics(
                accuracy_score=result.get("accuracy_score", 0),
                completeness_score=result.get("completeness_score", 0),
                relevance_score=result.get("relevance_score", 0),
                fluency_score=result.get("fluency_score", 0),
                overall_score=result.get("overall_score", 0),
                has_hallucination=result.get("has_hallucination", False),
                reasoning=result.get("reasoning", "")
            )

            return metrics

        except Exception as e:
            logger.error(f"[GenerationEvaluator] LLM 评估失败: {e}")
            # 降级到规则评估
            return self._evaluate_with_rules(query, generated_answer, expected_answer)

    def _build_evaluation_prompt(
        self,
        query: str,
        generated_answer: str,
        expected_answer: str,
        context: Optional[str] = None
    ) -> str:
        """
        构建评估 Prompt

        Args:
            query: 用户查询
            generated_answer: 生成的答案
            expected_answer: 期望答案
            context: 上下文

        Returns:
            评估 Prompt
        """
        prompt = f"""你是一个专业的 RAG 系统评估专家。请评估生成答案的质量。

用户查询: {query}

生成的答案:
{generated_answer}

期望答案:
{expected_answer}
"""

        if context:
            prompt += f"""
上下文信息:
{context[:500]}...
"""

        prompt += """
请从以下维度评估生成答案的质量（0-5 分）:

1. **准确性 (Accuracy)**: 答案的事实是否准确？
   - 5分: 完全准确，所有事实正确
   - 3分: 基本准确，有少量错误
   - 0分: 严重错误或完全不准确

2. **完整性 (Completeness)**: 答案是否完整回答了问题？
   - 5分: 完整回答，涵盖所有要点
   - 3分: 部分回答，缺少一些要点
   - 0分: 严重不完整或未回答问题

3. **相关性 (Relevance)**: 答案是否与问题相关？
   - 5分: 高度相关，紧扣问题
   - 3分: 基本相关，有些偏离
   - 0分: 不相关或答非所问

4. **流畅性 (Fluency)**: 答案的语言是否流畅？
   - 5分: 语言流畅，表达清晰
   - 3分: 基本流畅，有些生硬
   - 0分: 不流畅或难以理解

5. **幻觉检测 (Hallucination)**: 答案是否包含上下文中不存在的信息？
   - true: 存在幻觉（编造信息）
   - false: 无幻觉

返回 JSON 格式:
{
    "accuracy_score": 5,
    "completeness_score": 4,
    "relevance_score": 5,
    "fluency_score": 5,
    "overall_score": 4.75,
    "has_hallucination": false,
    "reasoning": "评估理由..."
}

只返回 JSON，不要其他内容。
"""

        return prompt

    def _evaluate_with_rules(
        self,
        query: str,
        generated_answer: str,
        expected_answer: str
    ) -> GenerationMetrics:
        """
        使用规则评估（简化版）

        Args:
            query: 用户查询
            generated_answer: 生成的答案
            expected_answer: 期望答案

        Returns:
            GenerationMetrics: 评估指标
        """
        metrics = GenerationMetrics()

        # 简单的关键词匹配评估
        query_lower = query.lower()
        generated_lower = generated_answer.lower()
        expected_lower = expected_answer.lower()

        # 相关性: 检查答案是否包含查询的关键词
        query_words = set(query_lower.split())
        generated_words = set(generated_lower.split())
        relevance_ratio = len(query_words & generated_words) / len(query_words) if query_words else 0
        metrics.relevance_score = min(5.0, relevance_ratio * 5)

        # 完整性: 长度比较
        length_ratio = len(generated_answer) / len(expected_answer) if expected_answer else 0
        if 0.5 <= length_ratio <= 1.5:
            metrics.completeness_score = 4.0
        elif 0.3 <= length_ratio <= 2.0:
            metrics.completeness_score = 3.0
        else:
            metrics.completeness_score = 2.0

        # 准确性: 期望答案关键词覆盖
        expected_words = set(expected_lower.split())
        if expected_words:
            coverage_ratio = len(expected_words & generated_words) / len(expected_words)
            metrics.accuracy_score = coverage_ratio * 5
        else:
            metrics.accuracy_score = 3.0

        # 流畅性: 简单检查长度和标点
        if len(generated_answer) > 10 and any(p in generated_answer for p in "。！？,.!?"):
            metrics.fluency_score = 4.0
        else:
            metrics.fluency_score = 2.5

        # 综合评分
        metrics.overall_score = (
            metrics.accuracy_score +
            metrics.completeness_score +
            metrics.relevance_score +
            metrics.fluency_score
        ) / 4

        metrics.reasoning = "基于规则的简化评估"

        return metrics

    async def evaluate_batch(
        self,
        batch_cases: list[tuple[str, str, str, Optional[str]]]
    ) -> list[GenerationMetrics]:
        """
        批量评估

        Args:
            batch_cases: (query, generated, expected, context) 元组列表

        Returns:
            评估指标列表
        """
        results = []

        for query, generated, expected, context in batch_cases:
            metrics = await self.evaluate(query, generated, expected, context)
            results.append(metrics)

        return results

    def calculate_average_metrics(
        self,
        metrics_list: list[GenerationMetrics]
    ) -> GenerationMetrics:
        """
        计算平均指标

        Args:
            metrics_list: 指标列表

        Returns:
            平均指标
        """
        if not metrics_list:
            return GenerationMetrics()

        avg_metrics = GenerationMetrics(
            accuracy_score=sum(m.accuracy_score for m in metrics_list) / len(metrics_list),
            completeness_score=sum(m.completeness_score for m in metrics_list) / len(metrics_list),
            relevance_score=sum(m.relevance_score for m in metrics_list) / len(metrics_list),
            fluency_score=sum(m.fluency_score for m in metrics_list) / len(metrics_list),
            overall_score=sum(m.overall_score for m in metrics_list) / len(metrics_list),
            has_hallucination=sum(1 for m in metrics_list if m.has_hallucination) > len(metrics_list) * 0.3,
            reasoning=f"Average of {len(metrics_list)} evaluations"
        )

        return avg_metrics

    def print_metrics(self, metrics: GenerationMetrics, title: str = "生成评估结果"):
        """
        打印评估指标

        Args:
            metrics: 评估指标
            title: 标题
        """
        print(f"\n{'='*60}")
        print(f"{title:^60}")
        print(f"{'='*60}\n")

        print(f"准确性 (Accuracy): {metrics.accuracy_score:.2f}/5")
        print(f"完整性 (Completeness): {metrics.completeness_score:.2f}/5")
        print(f"相关性 (Relevance): {metrics.relevance_score:.2f}/5")
        print(f"流畅性 (Fluency): {metrics.fluency_score:.2f}/5")
        print(f"综合评分 (Overall): {metrics.overall_score:.2f}/5")
        print()
        print(f"幻觉检测: {'是' if metrics.has_hallucination else '否'}")
        print()
        if metrics.reasoning:
            print(f"评估理由: {metrics.reasoning}")

        print(f"\n{'='*60}\n")


# 辅助函数

async def evaluate_generation(
    query: str,
    generated_answer: str,
    expected_answer: str,
    context: Optional[str] = None,
    llm_service=None
) -> GenerationMetrics:
    """
    评估生成答案（快捷函数）

    Args:
        query: 用户查询
        generated_answer: 生成的答案
        expected_answer: 期望答案
        context: 上下文
        llm_service: LLM 服务

    Returns:
        GenerationMetrics: 评估指标
    """
    evaluator = GenerationEvaluator(llm_service=llm_service)
    return await evaluator.evaluate(query, generated_answer, expected_answer, context)
