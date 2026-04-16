"""
LLM Functions - 轻量级 LLM 调用函数模块

用于简单的 LLM 任务，如分类、评分、格式化等。
这些任务不需要完整的 Agent 架构，只需要提示词 + LLM 调用即可。
"""

from .triage_function import TriageFunction, triage_document
from .quality_review_function import QualityReviewFunction, review_quality

__all__ = [
    "TriageFunction",
    "triage_document",
    "QualityReviewFunction",
    "review_quality",
]
