"""
质量审查函数 (Quality Review Function)

用于对 AI 生成的回答进行质量评估和反思改进。
这是一个轻量级的 LLM 调用，不需要完整的 Agent 架构。
"""

import json
import logging
from typing import Dict, Any, Optional, List

from app.agent_framework.llm import BaseLLMAdapter as LLMAdapter, create_llm_adapter

logger = logging.getLogger(__name__)


class QualityScore:
    """质量评分结果"""
    accuracy: float = 0.0
    completeness: float = 0.0
    logic: float = 0.0
    readability: float = 0.0
    practicality: float = 0.0

    @property
    def overall(self) -> float:
        weights = {"accuracy": 0.3, "completeness": 0.2, "logic": 0.2, "readability": 0.15, "practicality": 0.15}
        return sum(getattr(self, k) * v for k, v in weights.items())

    def to_dict(self) -> Dict[str, float]:
        return {
            "accuracy": self.accuracy,
            "completeness": self.completeness,
            "logic": self.logic,
            "readability": self.readability,
            "practicality": self.practicality,
            "overall": self.overall
        }


QUALITY_REVIEW_PROMPT = """你是一个专业的质量审查员。请评估以下回答的质量。

## 用户问题
{user_question}

## AI 回答
{ai_answer}

## 评估维度
1. **准确性** (0-1): 回答是否正确？有无误判或错误信息？
2. **完整性** (0-1): 是否涵盖所有要点？是否有遗漏？
3. **逻辑性** (0-1): 逻辑是否自洽？推理是否合理？
4. **可读性** (0-1): 表达是否清晰？格式是否良好？
5. **实用性** (0-1): 回答是否有帮助？是否可操作？

## 输出要求
请以JSON格式输出：
{{
  "is_quality_acceptable": true/false,
  "scores": {{
    "accuracy": 0.0-1.0,
    "completeness": 0.0-1.0,
    "logic": 0.0-1.0,
    "readability": 0.0-1.0,
    "practicality": 0.0-1.0,
    "overall": 0.0-1.0
  }},
  "issues": [
    {{
      "dimension": "accuracy/completeness/logic/readability/practicality",
      "severity": "minor/moderate/severe",
      "description": "问题描述",
      "suggestion": "改进建议"
    }}
  ],
  "improved_answer": "改进后的回答（如果需要改进）",
  "summary": "总体评价（50字内）"
}}
"""


class QualityReviewFunction:
    """质量审查函数"""

    def __init__(self, llm_adapter: Optional[LLMAdapter] = None, quality_threshold: float = 0.7):
        self.llm_adapter = llm_adapter or create_llm_adapter()
        self.quality_threshold = quality_threshold

    async def review(
        self,
        user_question: str,
        ai_answer: str
    ) -> Dict[str, Any]:
        """
        审查回答质量

        Args:
            user_question: 用户问题
            ai_answer: AI 回答

        Returns:
            审查结果
        """
        prompt = QUALITY_REVIEW_PROMPT.format(
            user_question=user_question,
            ai_answer=ai_answer
        )

        try:
            response = await self.llm_adapter.agenerate(prompts=[prompt])
            result = self._parse_response(response.content)

            is_acceptable = result.get("is_quality_acceptable", False)
            logger.info(f"🔍 [QualityReview] 审查完成: acceptable={is_acceptable}, score={result.get('scores', {}).get('overall', 0):.2f}")

            return result

        except Exception as e:
            logger.error(f"❌ [QualityReview] 审查失败: {e}")
            return self._get_default_result()

    async def review_with_improvement(
        self,
        user_question: str,
        ai_answer: str,
        max_iterations: int = 2
    ) -> Dict[str, Any]:
        """
        带改进的质量审查

        Args:
            user_question: 用户问题
            ai_answer: AI 回答
            max_iterations: 最大迭代次数

        Returns:
            最终审查结果
        """
        current_answer = ai_answer

        for i in range(max_iterations):
            result = await self.review(user_question, current_answer)

            if result.get("is_quality_acceptable", False):
                break

            if "improved_answer" in result and result["improved_answer"]:
                current_answer = result["improved_answer"]
                logger.info(f"🔄 [QualityReview] 第{i+1}轮改进完成")
            else:
                break

        result["final_answer"] = current_answer
        return result

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        try:
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end]
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end]

            result = json.loads(response.strip())

            if "scores" in result and "overall" not in result["scores"]:
                scores = result["scores"]
                weights = {"accuracy": 0.3, "completeness": 0.2, "logic": 0.2, "readability": 0.15, "practicality": 0.15}
                result["scores"]["overall"] = sum(scores.get(k, 0) * v for k, v in weights.items())

            return result

        except json.JSONDecodeError:
            logger.warning("⚠️ [QualityReview] JSON解析失败")
            return self._parse_fallback(response)

    def _parse_fallback(self, response: str) -> Dict[str, Any]:
        """备用解析方法"""
        import re

        result = {
            "is_quality_acceptable": True,
            "scores": {
                "accuracy": 0.7,
                "completeness": 0.7,
                "logic": 0.7,
                "readability": 0.7,
                "practicality": 0.7,
                "overall": 0.7
            },
            "issues": [],
            "summary": "解析失败，使用默认值"
        }

        overall_match = re.search(r'"overall":\s*([0-9.]+)', response)
        if overall_match:
            result["scores"]["overall"] = float(overall_match.group(1))
            result["is_quality_acceptable"] = result["scores"]["overall"] >= self.quality_threshold

        return result

    def _get_default_result(self) -> Dict[str, Any]:
        """获取默认结果"""
        return {
            "is_quality_acceptable": True,
            "scores": {
                "accuracy": 0.5,
                "completeness": 0.5,
                "logic": 0.5,
                "readability": 0.5,
                "practicality": 0.5,
                "overall": 0.5
            },
            "issues": [{
                "dimension": "system",
                "severity": "moderate",
                "description": "质量审查服务异常",
                "suggestion": "人工确认"
            }],
            "summary": "服务异常"
        }


_quality_review_instance: Optional[QualityReviewFunction] = None


def get_quality_review_function() -> QualityReviewFunction:
    """获取单例实例"""
    global _quality_review_instance
    if _quality_review_instance is None:
        _quality_review_instance = QualityReviewFunction()
    return _quality_review_instance


async def review_quality(
    user_question: str,
    ai_answer: str,
    with_improvement: bool = False
) -> Dict[str, Any]:
    """
    便捷函数：审查回答质量

    Args:
        user_question: 用户问题
        ai_answer: AI 回答
        with_improvement: 是否自动改进

    Returns:
        审查结果
    """
    review_fn = get_quality_review_function()

    if with_improvement:
        return await review_fn.review_with_improvement(user_question, ai_answer)
    else:
        return await review_fn.review(user_question, ai_answer)


async def batch_review(
    items: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """
    批量质量审查

    Args:
        items: [{"question": "...", "answer": "..."}, ...]

    Returns:
        审查结果列表
    """
    import asyncio
    review_fn = get_quality_review_function()

    tasks = [
        review_fn.review(item.get("question", ""), item.get("answer", ""))
        for item in items
    ]

    return await asyncio.gather(*tasks)
