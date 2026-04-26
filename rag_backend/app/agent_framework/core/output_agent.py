"""
输出智能体 (Output Agent) - 向后兼容包装器

⚠️ 注意：此类已弃用，请使用 ResultSynthesizer 替代
OutputAgent 已重构为智能组件 ResultSynthesizer，不再作为智能体。

此类提供向后兼容性，实际功能委托给 ResultSynthesizer 实现。

迁移指南：
1. 新代码请使用：from app.agent_framework.components import ResultSynthesizer
2. 旧代码可继续使用 OutputAgent，但会收到弃用警告
"""

import warnings
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator

from app.agent_framework.components import (
    ResultSynthesizer as NewResultSynthesizer,
    SynthesisStrategy,
    ConflictResolution,
    SynthesisInput,
    ConflictInfo,
    SynthesisResult,
    OutputReviewResult
)

logger = logging.getLogger(__name__)

# 发出弃用警告
warnings.warn(
    "OutputAgent 已弃用，请使用 ResultSynthesizer 替代。"
    "OutputAgent 已重构为智能组件，不再作为智能体。",
    DeprecationWarning,
    stacklevel=2
)

# 重新导出 ResultSynthesizer 的枚举和数据类型，保持向后兼容
ConflictResolution = ConflictResolution
SynthesisInput = SynthesisInput
ConflictInfo = ConflictInfo
SynthesisResult = SynthesisResult
OutputReviewResult = OutputReviewResult


class OutputAgent:
    """
    输出智能体 - 向后兼容包装器
    
    注意：此类已弃用，实际功能委托给 ResultSynthesizer 实现。
    新代码请直接使用 ResultSynthesizer。
    """
    
    def __init__(
        self,
        llm_adapter=None,
        default_strategy: SynthesisStrategy = SynthesisStrategy.MERGE,
        conflict_resolution: ConflictResolution = ConflictResolution.HIGHEST_CONFIDENCE,
        max_inputs: int = 10
    ):
        """
        初始化输出智能体（向后兼容）
        
        Args:
            llm_adapter: LLM适配器
            default_strategy: 默认合成策略
            conflict_resolution: 冲突解决策略
            max_inputs: 最大输入数量
        """
        warnings.warn(
            "OutputAgent 已弃用，请使用 ResultSynthesizer 替代。",
            DeprecationWarning,
            stacklevel=2
        )
        
        # 创建实际的 ResultSynthesizer 实例
        self._synthesizer = NewResultSynthesizer(
            llm_adapter=llm_adapter,
            default_strategy=default_strategy,
            conflict_resolution=conflict_resolution,
            max_inputs=max_inputs
        )
        
        # 保持原有属性名
        self.llm = llm_adapter
        self.default_strategy = default_strategy
        self.conflict_resolution = conflict_resolution
        self.max_inputs = max_inputs
        
        logger.info(f"⚠️ [OutputAgent] 使用已弃用的 OutputAgent，建议迁移到 ResultSynthesizer")
    
    def add_input(
        self,
        task_id: str,
        source_agent: str,
        source_type: str,
        content: Any,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """添加输入（委托给 ResultSynthesizer）"""
        return self._synthesizer.add_input(
            task_id=task_id,
            source_agent=source_agent,
            source_type=source_type,
            content=content,
            confidence=confidence,
            metadata=metadata
        )
    
    def add_result(
        self,
        task_id: str,
        source_agent: str,
        source_type: str,
        content: Any,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """添加结果（委托给 ResultSynthesizer）"""
        return self._synthesizer.add_result(
            task_id=task_id,
            source_agent=source_agent,
            source_type=source_type,
            content=content,
            confidence=confidence,
            metadata=metadata
        )
    
    def add_inputs_batch(self, results: List[Dict[str, Any]]) -> int:
        """批量添加输入（委托给 ResultSynthesizer）"""
        return self._synthesizer.add_inputs_batch(results)
    
    def clear_inputs(self) -> None:
        """清空输入（委托给 ResultSynthesizer）"""
        self._synthesizer.clear_inputs()
    
    def get_inputs_summary(self) -> Dict[str, Any]:
        """获取输入摘要（委托给 ResultSynthesizer）"""
        return self._synthesizer.get_inputs_summary()
    
    async def detect_conflicts(self) -> List[ConflictInfo]:
        """检测冲突（委托给 ResultSynthesizer）"""
        return await self._synthesizer.detect_conflicts()
    
    async def resolve_conflicts(self, strategy: Optional[ConflictResolution] = None) -> Dict[str, str]:
        """解决冲突（委托给 ResultSynthesizer）"""
        return await self._synthesizer.resolve_conflicts(strategy)
    
    async def synthesize(
        self,
        user_query: Optional[str] = None,
        strategy: Optional[SynthesisStrategy] = None,
        custom_template: Optional[str] = None
    ) -> SynthesisResult:
        """执行合成（委托给 ResultSynthesizer）"""
        return await self._synthesizer.synthesize(user_query, strategy, custom_template)
    
    def quick_review(self, output: str, user_query: str) -> OutputReviewResult:
        """快速审查（委托给 ResultSynthesizer）"""
        return self._synthesizer.quick_review(output, user_query)
    
    async def synthesize_and_format(
        self,
        specialist_results: Dict[str, Any],
        user_query: str
    ) -> str:
        """整合专家结果并美化输出（委托给 ResultSynthesizer）"""
        return await self._synthesizer.synthesize_and_format(specialist_results, user_query)
    
    async def synthesize_and_format_stream(
        self,
        specialist_results: Dict[str, Any],
        user_query: str,
        buffer_size: int = 10
    ) -> AsyncGenerator[str, None]:
        """流式整合专家结果（委托给 ResultSynthesizer）"""
        async for chunk in self._synthesizer.synthesize_and_format_stream(
            specialist_results, user_query, buffer_size
        ):
            yield chunk
    
    # 兼容性属性
    @property
    def inputs(self) -> List[SynthesisInput]:
        """获取输入列表（只读）"""
        return self._synthesizer._inputs
    
    @property
    def conflicts(self) -> List[ConflictInfo]:
        """获取冲突列表（只读）"""
        return self._synthesizer._conflicts
    
    @property
    def current_task_id(self) -> Optional[str]:
        """获取当前任务ID（只读）"""
        return self._synthesizer._current_task_id