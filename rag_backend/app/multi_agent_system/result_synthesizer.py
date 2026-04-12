"""
智能结果合成器 (Result Synthesizer) - 兼容层

此类已废弃，推荐直接使用 OutputAgent
保留了 ResultSynthesizer 的接口以确保向后兼容

@deprecated 请使用 OutputAgent.synthesize() 替代
"""

import uuid
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from app.agent_framework.core.output_agent import (
    OutputAgent,
    SynthesisStrategy,
    ConflictResolution,
    SynthesisInput,
    SynthesisResult,
    ConflictInfo,
)

logger = logging.getLogger(__name__)


class ResultSynthesizer:
    """
    结果合成器（兼容层）
    
    @deprecated 请直接使用 OutputAgent:
    
    ```python
    from app.agent_framework.core.output_agent import output_agent
    
    # 添加输入
    output_agent.add_input(task_id, source_agent, source_type, content, confidence)
    
    # 合成
    result = await output_agent.synthesize(user_query, strategy)
    ```
    """
    
    def __init__(
        self,
        llm_adapter=None,
        default_strategy: SynthesisStrategy = SynthesisStrategy.MERGE,
        conflict_resolution: ConflictResolution = ConflictResolution.HIGHEST_CONFIDENCE,
        max_inputs: int = 10
    ):
        logger.warning(
            "⚠️ [ResultSynthesizer] ResultSynthesizer 已废弃，请使用 OutputAgent.synthesize() 替代"
        )
        
        self._output_agent = OutputAgent(
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
        
        @deprecated 请使用 output_agent.add_input()
        """
        self._output_agent.add_input(
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
        
        @deprecated 请使用 output_agent.add_inputs_batch()
        """
        self._output_agent.add_inputs_batch(results)
    
    async def synthesize(
        self,
        user_query: Optional[str] = None,
        strategy: Optional[SynthesisStrategy] = None,
        custom_template: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> SynthesisResult:
        """
        执行合成（向后兼容接口）
        
        @deprecated 请使用 output_agent.synthesize()
        """
        return await self._output_agent.synthesize(
            user_query=user_query,
            strategy=strategy,
            custom_template=custom_template
        )
    
    async def detect_conflicts(self) -> List[ConflictInfo]:
        """检测冲突（向后兼容接口）"""
        return await self._output_agent.detect_conflicts()
    
    async def resolve_conflicts(
        self,
        strategy: Optional[ConflictResolution] = None
    ) -> Dict[str, str]:
        """解决冲突（向后兼容接口）"""
        return await self._output_agent.resolve_conflicts(strategy)
    
    def get_inputs_summary(self) -> Dict[str, Any]:
        """获取输入摘要（向后兼容接口）"""
        return self._output_agent.get_inputs_summary()
    
    def clear(self) -> None:
        """清空数据（向后兼容接口）"""
        self._output_agent.clear_inputs()


class StreamingResultSynthesizer(ResultSynthesizer):
    """
    流式结果合成器（兼容层）
    
    @deprecated 请使用 OutputAgent
    """
    
    async def synthesize_stream(
        self,
        user_query: Optional[str] = None,
        strategy: Optional[SynthesisStrategy] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式合成（向后兼容接口）
        
        @deprecated 请使用 OutputAgent
        """
        result = await self.synthesize(
            user_query=user_query,
            strategy=strategy,
            **kwargs
        )
        
        yield result.final_response
