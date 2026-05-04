"""
质量审查函数 (Quality Review Function)

用于对 AI 生成的回答进行质量评估和反思改进。
这是一个轻量级的 LLM 调用，不需要完整的 Agent 架构。
"""

import os
import re
from app.utils.json_compat import json
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


def _load_quality_review_prompt() -> str:
    """从文件加载质量审查提示词"""
    prompt_file = os.path.join(
        os.path.dirname(__file__),
        "quality_review.md"
    )
    
    if os.path.exists(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as f:
            template = f.read()
        logger.info(f"✅ [QualityReview] 从文件加载提示词: {prompt_file}")
        return template
    else:
        logger.warning(f"⚠️ [QualityReview] 提示词文件不存在，使用内置提示词: {prompt_file}")
        return _get_default_quality_review_prompt()


def _get_default_quality_review_prompt() -> str:
    """获取默认质量审查提示词"""
    return """你是一个专业的质量审查员。请评估以下回答的质量。

## 用户问题
{user_question}

## AI 回答
{ai_answer}

## 数据来源说明
{data_source_info}

## 评估维度
1. **准确性** (0-1): 回答是否正确？有无误判或错误信息？
2. **完整性** (0-1): 是否涵盖所有要点？是否有遗漏？
3. **逻辑性** (0-1): 逻辑是否自洽？推理是否合理？
4. **可读性** (0-1): 表达是否清晰？格式是否良好？
5. **实用性** (0-1): 回答是否有帮助？是否可操作？

## 重要评估原则
1. **数据真实性判断**：
   - 如果回答中使用了标注为"来自真实数据库"的数据，这是真实数据，不是虚构的
   - 只有在没有数据来源标注时，才能判断为"虚构数据"
2. **基于数据的分析**：
   - 如果系统查询到了真实财务数据并进行了分析，这是合格的
   - 质疑数据真实性前，请先检查 `data_source_info` 部分
3. **阈值标准**：
   - overall score >= 0.6 时，`is_quality_acceptable` 应为 true
   - 不要因为数据"看似极端"就判定为虚构（可能是企业真实数据）

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
}}"""


QUALITY_REVIEW_PROMPT = _load_quality_review_prompt()


class QualityReviewFunction:
    """质量审查函数"""

    def __init__(self, llm_adapter: Optional[LLMAdapter] = None, quality_threshold: float = 0.6):
        self.llm_adapter = llm_adapter or create_llm_adapter()
        self.quality_threshold = quality_threshold
        self._prompt_template = None

    @property
    def prompt_template(self) -> str:
        """延迟加载提示词模板"""
        if self._prompt_template is None:
            self._prompt_template = _load_quality_review_prompt()
        return self._prompt_template

    async def review(
        self,
        user_question: str,
        ai_answer: str,
        data_source_info: str = "无数据来源信息"
    ) -> Dict[str, Any]:
        """
        审查回答质量

        Args:
            user_question: 用户问题
            ai_answer: AI 回答
            data_source_info: 数据来源信息（如"来自企业数据库"）

        Returns:
            审查结果
        """
        # ⚠️ 防御：专家回复中可能包含 { } 花括号（如 JSON 示例），会导致
        # str.format() 误判为格式占位符而抛出 KeyError。
        # 对用户输入进行花括号转义后再格式化模板。
        def _escape_braces(s: str) -> str:
            return s.replace("{", "{{").replace("}", "}}")

        prompt = self.prompt_template.format(
            user_question=_escape_braces(user_question),
            ai_answer=_escape_braces(ai_answer),
            data_source_info=_escape_braces(data_source_info)
        )

        try:
            response = await self.llm_adapter.agenerate(prompts=[prompt])
            result = self._parse_response(response.content)

            is_acceptable = result.get("is_quality_acceptable", False)
            score = result.get('scores', {}).get('overall', result.get('score', 0.0))
            logger.info(f"🔍 [QualityReview] 审查完成: acceptable={is_acceptable}, score={score:.2f}")

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
            if not response or not isinstance(response, str):
                logger.warning("⚠️ [QualityReview] LLM返回空响应或非字符串")
                return self._get_default_result()

            cleaned = response.strip()

            # 提取 ```json ... ``` 或 ``` ... ``` 包裹的内容
            if "```json" in cleaned:
                start = cleaned.find("```json") + 7
                end = cleaned.find("```", start)
                cleaned = cleaned[start:end].strip()
            elif "```" in cleaned:
                start = cleaned.find("```") + 3
                end = cleaned.find("```", start)
                cleaned = cleaned[start:end].strip()

            # 尝试完整的 JSON 解析
            try:
                result = json.loads(cleaned)
            except json.JSONDecodeError:
                logger.warning("⚠️ [QualityReview] JSON解析失败，尝试智能提取")
                return self._parse_fallback(cleaned)

            # ✅ 关键检查：确保 result 是 dict，否则走 fallback
            if not isinstance(result, dict):
                logger.warning("⚠️ [QualityReview] JSON解析结果不是字典类型(type=%s)，使用 fallback", type(result).__name__)
                return self._parse_fallback(cleaned)

            if "scores" in result and isinstance(result["scores"], dict) and "overall" not in result["scores"]:
                scores = result["scores"]
                weights = {"accuracy": 0.3, "completeness": 0.2, "logic": 0.2, "readability": 0.15, "practicality": 0.15}
                result["scores"]["overall"] = sum(scores.get(k, 0) * v for k, v in weights.items())

            return result

        except Exception as e:
            logger.warning("⚠️ [QualityReview] 解析异常: %s", e)
            return self._get_default_result()

    def _parse_fallback(self, response: str) -> Dict[str, Any]:
        """智能备用解析方法 — 用正则从截断的 JSON 中提取各维度分数"""
        import re

        result = {
            "is_quality_acceptable": True,
            "scores": {
                "accuracy": 0.5,
                "completeness": 0.5,
                "logic": 0.5,
                "readability": 0.5,
                "practicality": 0.5,
                "overall": 0.5
            },
            "issues": [],
            "summary": "解析失败，使用默认值"
        }

        if not response or not isinstance(response, str):
            return result

        # 提取各维度分数
        score_fields = {
            "accuracy": r'"accuracy":?\s*([0-9.]+)',
            "completeness": r'"completeness":?\s*([0-9.]+)',
            "logic": r'"logic":?\s*([0-9.]+)',
            "readability": r'"readability":?\s*([0-9.]+)',
            "practicality": r'"practicality":?\s*([0-9.]+)',
        }

        for field, pattern in score_fields.items():
            match = re.search(pattern, response)
            if match:
                try:
                    result["scores"][field] = min(1.0, max(0.0, float(match.group(1))))
                except (ValueError, TypeError):
                    pass

        # 优先使用提取到的 overall，否则加权计算
        overall_match = re.search(r'"overall":?\s*([0-9.]+)', response)
        if overall_match:
            try:
                result["scores"]["overall"] = min(1.0, max(0.0, float(overall_match.group(1))))
            except (ValueError, TypeError):
                result["scores"]["overall"] = sum(result["scores"].values()) / 5
        else:
            result["scores"]["overall"] = sum(result["scores"].values()) / 5

        # 提取 is_quality_acceptable
        acceptable_match = re.search(r'"is_quality_acceptable":?\s*(true|false|True|False)', response)
        if acceptable_match:
            result["is_quality_acceptable"] = acceptable_match.group(1).lower() == "true"
        else:
            result["is_quality_acceptable"] = result["scores"]["overall"] >= self.quality_threshold

        logger.info(
            "🔍 [QualityReview] 备用解析完成: acceptable=%s, overall=%.2f (from %d fields)",
            result["is_quality_acceptable"],
            result["scores"]["overall"],
            sum(1 for f in score_fields if re.search(score_fields[f], response))
        )

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
    data_source_info: str = "无数据来源信息",
    with_improvement: bool = False
) -> Dict[str, Any]:
    """
    便捷函数：审查回答质量

    Args:
        user_question: 用户问题
        ai_answer: AI 回答
        data_source_info: 数据来源信息
        with_improvement: 是否自动改进

    Returns:
        审查结果
    """
    review_fn = get_quality_review_function()

    if with_improvement:
        return await review_fn.review_with_improvement(user_question, ai_answer)
    else:
        return await review_fn.review(user_question, ai_answer, data_source_info)


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
