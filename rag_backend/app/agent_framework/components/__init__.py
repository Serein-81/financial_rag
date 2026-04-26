"""
智能组件模块

提供非智能体的功能性组件，如结果合成器、输出格式化器等。
这些组件不具备智能体的自主性和推理能力，而是提供特定的功能服务。
"""

from .result_synthesizer import (
    ResultSynthesizer,
    SynthesisStrategy,
    ConflictResolution,
    SynthesisInput,
    ConflictInfo,
    SynthesisResult,
    OutputReviewResult
)

__all__ = [
    "ResultSynthesizer",
    "SynthesisStrategy",
    "ConflictResolution",
    "SynthesisInput",
    "ConflictInfo",
    "SynthesisResult",
    "OutputReviewResult"
]