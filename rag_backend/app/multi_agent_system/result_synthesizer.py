"""
智能结果合成器 (Result Synthesizer) - 兼容层（已废弃）

⚠️ 注意：此类已完全废弃，请直接使用 app.agent_framework.components.ResultSynthesizer
此类仅作为兼容层存在，实际功能委托给新的 ResultSynthesizer 组件

@deprecated 请直接使用 app.agent_framework.components.ResultSynthesizer
"""

import logging
import warnings
from typing import Dict, List, Any, Optional, AsyncGenerator

from app.agent_framework.components import (
    ResultSynthesizer as NewResultSynthesizer,
    SynthesisStrategy,
    ConflictResolution,
    SynthesisResult,
    ConflictInfo,
)

logger = logging.getLogger(__name__)


class ResultSynthesizer:
    """
    结果合成器（兼容层，已废弃）
    
    @deprecated 请直接使用 app.agent_framework.components.ResultSynthesizer:
    
    ```python
    from app.agent_framework.components import ResultSynthesizer
    
    # 创建实例
    synthesizer = ResultSynthesizer(llm_adapter=llm_adapter)
    
    # 添加输入
    synthesizer.add_input(task_id, source_agent, source_type, content, confidence)
    
    # 合成
    result = await synthesizer.synthesize(user_query, strategy)
    ```
    """
    
    def __init__(
        self,
        llm_adapter=None,
        default_strategy: SynthesisStrategy = SynthesisStrategy.MERGE,
        conflict_resolution: ConflictResolution = ConflictResolution.HIGHEST_CONFIDENCE,
        max_inputs: int = 10
    ):
        warnings.warn(
            "app.multi_agent_system.result_synthesizer.ResultSynthesizer 已废弃，"
            "请使用 app.agent_framework.components.ResultSynthesizer",
            DeprecationWarning,
            stacklevel=2
        )
        
        self._synthesizer = NewResultSynthesizer(
            llm_adapter=llm_adapter,
            default_strategy=default_strategy,
            conflict_resolution=conflict_resolution,
            max_inputs=max_inputs
        )
    
    def add_result(
        self,
        task_id: str,
        source_agent: str,
        source_type: str,
        content: Any,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        添加单个结果（向后兼容接口）
        
        @deprecated 请使用 synthesizer.add_input()
        """
        self._synthesizer.add_input(
            task_id=task_id,
            source_agent=source_agent,
            source_type=source_type,
            content=content,
            confidence=confidence,
            metadata=metadata
        )
    
    def add_results_batch(self, results: List[Dict[str, Any]]) -> None:
        """
        批量添加结果（向后兼容接口）
        
        @deprecated 请使用 synthesizer.add_inputs_batch()
        """
        self._synthesizer.add_inputs_batch(results)
    
    async def synthesize(
        self,
        user_query: Optional[str] = None,
        strategy: Optional[SynthesisStrategy] = None,
        custom_template: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> SynthesisResult:
        """
        执行合成（向后兼容接口）
        
        @deprecated 请使用 synthesizer.synthesize()
        """
        return await self._synthesizer.synthesize(
            user_query=user_query,
            strategy=strategy,
            custom_template=custom_template
        )
    
    async def detect_conflicts(self) -> List[ConflictInfo]:
        """检测冲突（向后兼容接口）"""
        return await self._synthesizer.detect_conflicts()
    
    async def resolve_conflicts(
        self,
        strategy: Optional[ConflictResolution] = None
    ) -> Dict[str, str]:
        """解决冲突（向后兼容接口）"""
        return await self._synthesizer.resolve_conflicts(strategy)
    
    def get_inputs_summary(self) -> Dict[str, Any]:
        """获取输入摘要（向后兼容接口）"""
        return self._synthesizer.get_inputs_summary()
    
    def clear(self) -> None:
        """清空数据（向后兼容接口）"""
        self._synthesizer.clear_inputs()


class StreamingResultSynthesizer(ResultSynthesizer):
    """
    流式结果合成器（兼容层，已废弃）
    
    @deprecated 请使用 app.agent_framework.components.ResultSynthesizer
    """
    
    async def synthesize_stream(
        self,
        user_query: Optional[str] = None,
        strategy: Optional[SynthesisStrategy] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式合成（向后兼容接口）
        
        @deprecated 请使用 app.agent_framework.components.ResultSynthesizer
        """
        result = await self.synthesize(
            user_query=user_query,
            strategy=strategy,
            **kwargs
        )
        
        yield result.final_response
