"""
上下文压缩节点（Summarizer Node）

将大量辩论上下文压缩为简洁的共识和分歧点

功能：
1. 接收 Message Bus 产生的辩论记录
2. 使用 LLM 进行上下文压缩
3. 生成结构化的共识和分歧点

4. 释放内存，保留关键信息
"""


from app.utils.json_compat import json
import logging
from typing import Dict, Any, List, Optional, TypedDict
from dataclasses import dataclass


# LLM 依赖为可选
try:
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatOpenAI = None

logger = logging.getLogger(__name__)


class SummarizerState(TypedDict):
    """
    Summarizer 状态
    
    用于管理上下文压缩的临时状态
    """
    debate_context: List[Dict[str, Any]]  # 原始辩论记录
    consensus: Optional[str]  # 压缩后的共识
    disagreements: List[str]  # 未解决的分歧点
    key_decisions: List[str]  # 关键决策列表
    abandoned_arguments: List[str]  # 被放弃的观点
    compression_ratio: float  # 压缩率
    processing_time_ms: float  # 处理时间
    original_tokens: int  # 原始 token 数
    compressed_tokens: int  # 压缩后 token 数


@dataclass
class CompressionResult:
    """
    压缩结果
    
    存储上下文压缩的详细结果
    """
    consensus: str
    disagreements: List[str]
    key_decisions: List[str]
    abandoned_arguments: List[str]
    compression_ratio: float
    original_size: int
    compressed_size: int
    processing_time_ms: float


class SummarizerNode:
    """
    Summarizer 节点
    
    将大量辩论上下文压缩为简洁的共识和分歧点。
    这是混合编排模式中的关键节点，用于解决上下文截断危机。
    
    使用场景：
    当 Message Bus 中的 Agent 辩论产生大量上下文时，
    在将控制权交回 LangGraph 之前，必须经过 Summarizer 进行压缩。
    
    Attributes:
        llm: LLM 实例用于压缩
        max_context_length: 最大上下文长度
        compression_target: 压缩目标（目标压缩到多少字）
    """
    
    def __init__(
        self,
        llm: Optional[Any] = None,
        model: str = "gpt-4o",
        temperature: float = 0.3,
        max_context_length: int = 50000,
        compression_target: int = 1000
    ):
        """
        初始化 Summarizer 节点
        
        Args:
            llm: LLM 实例，如果为 None 则自动创建（需要 langchain_openai）
            model: 模型名称
            temperature: 温度参数
            max_context_length: 最大上下文长度
            compression_target: 压缩目标字数
        """
        if llm is not None:
            self.llm = llm
        elif LANGCHAIN_AVAILABLE:
            self.llm = ChatOpenAI(model=model, temperature=temperature)
        else:
            self.llm = None
            logger.warning(
                "[Summarizer] langchain_openai 未安装，将使用简单的压缩策略"
            )
        
        self.max_context_length = max_context_length
        self.compression_target = compression_target
        self.model = model
    
    async def invoke(
        self,
        state: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行上下文压缩
        
        这是 LangGraph 节点的主入口函数
        
        Args:
            state: LangGraph 状态
            **kwargs: 其他参数
            
        Returns:
            更新后的状态
        """
        import time
        start_time = time.time()
        
        logger.info(
            f"[Summarizer] 开始上下文压缩: "
            f"request_id={state.get('request_id', 'unknown')}"
        )
        
        # 获取辩论上下文
        debate_context = state.get("debate_context", [])
        
        if not debate_context:
            logger.info("[Summarizer] 没有辩论上下文需要压缩")
            state["warnings"] = state.get("warnings", [])
            state["warnings"].append("Summarizer: 没有辩论上下文")
            return state
        
        logger.info(f"[Summarizer] 待压缩的辩论记录数量: {len(debate_context)}")
        
        # 执行压缩
        try:
            result = await self._compress_context(debate_context)
            
            # 更新状态
            state["message_bus_summary"] = result.consensus
            state["message_bus_disagreements"] = result.disagreements
            state["message_bus_key_decisions"] = result.key_decisions
            state["metadata"] = state.get("metadata", {})
            state["metadata"]["summarizer_result"] = {
                "compression_ratio": result.compression_ratio,
                "original_size": result.original_size,
                "compressed_size": result.compressed_size,
                "processing_time_ms": result.processing_time_ms,
                "abandoned_arguments": result.abandoned_arguments
            }
            
            # 清理原始上下文（释放内存）
            state["debate_context"] = []
            
            processing_time = (time.time() - start_time) * 1000
            logger.info(
                f"[Summarizer] 压缩完成: "
                f"original={result.original_size}字, "
                f"compressed={result.compressed_size}字, "
                f"ratio={result.compression_ratio:.2%}, "
                f"time={processing_time:.2f}ms"
            )
            
        except Exception as e:
            logger.error(f"[Summarizer] 压缩失败: {e}", exc_info=True)
            state["warnings"] = state.get("warnings", [])
            state["warnings"].append(f"上下文压缩失败: {str(e)}")
            # 不抛出异常，让流程继续
        
        return state
    
    async def _compress_context(
        self,
        debate_context: List[Dict[str, Any]]
    ) -> CompressionResult:
        """
        执行上下文压缩
        
        Args:
            debate_context: 辩论上下文列表
            
        Returns:
            压缩结果
        """
        import time
        start_time = time.time()
        
        # 构建辩论文本
        debate_text = self._format_debate_context(debate_context)
        original_size = len(debate_text)
        
        # 构建压缩提示词
        summary_prompt = self._build_summary_prompt(debate_text, len(debate_context))
        
        # 调用 LLM 进行压缩
        try:
            if self.llm is None:
                # 没有 LLM，使用简单压缩策略
                return await self._simple_compress(debate_context, original_size, start_time)
            
            response = await self.llm.ainvoke([
                HumanMessage(content=summary_prompt)
            ])
            
            # 解析响应
            summary = self._parse_summary_response(response.content)
            
            compressed_size = len(response.content)
            processing_time = (time.time() - start_time) * 1000
            compression_ratio = compressed_size / max(original_size, 1)
            
            return CompressionResult(
                consensus=summary.get("consensus", ""),
                disagreements=summary.get("disagreements", []),
                key_decisions=summary.get("key_decisions", []),
                abandoned_arguments=summary.get("abandoned_arguments", []),
                compression_ratio=compression_ratio,
                original_size=original_size,
                compressed_size=compressed_size,
                processing_time_ms=processing_time
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"[Summarizer] 解析压缩结果失败: {e}")
            # 返回默认结果
            return CompressionResult(
                consensus="压缩失败，返回原始摘要",
                disagreements=[],
                key_decisions=[],
                abandoned_arguments=[],
                compression_ratio=0.5,
                original_size=original_size,
                compressed_size=original_size // 2,
                processing_time_ms=(time.time() - start_time) * 1000
            )
    
    async def _simple_compress(
        self,
        debate_context: List[Dict[str, Any]],
        original_size: int,
        start_time: float
    ) -> CompressionResult:
        """
        简单的压缩策略（当没有 LLM 时使用）
        
        Args:
            debate_context: 辩论上下文
            original_size: 原始大小
            start_time: 开始时间
            
        Returns:
            压缩结果
        """
        # 简单策略：提取第一条和最后一条内容作为摘要
        if len(debate_context) == 0:
            consensus = "没有辩论记录"
        elif len(debate_context) == 1:
            consensus = f"单一观点: {debate_context[0].get('content', '')[:500]}"
        else:
            first = debate_context[0].get('content', '')[:300]
            last = debate_context[-1].get('content', '')[:300]
            consensus = f"辩论开始: {first}... 辩论结束: {last}"
        
        return CompressionResult(
            consensus=consensus,
            disagreements=["（未检测到分歧）"],
            key_decisions=["（未提取决策）"],
            abandoned_arguments=[],
            compression_ratio=0.1,
            original_size=original_size,
            compressed_size=len(consensus),
            processing_time_ms=(time.time() - start_time) * 1000
        )
    
    def _format_debate_context(
        self,
        debate_context: List[Dict[str, Any]]
    ) -> str:
        """
        格式化辩论上下文
        
        Args:
            debate_context: 辩论上下文列表
            
        Returns:
            格式化后的文本
        """
        formatted_parts = []
        
        for entry in debate_context:
            agent = entry.get("agent", "unknown")
            content = entry.get("content", "")
            timestamp = entry.get("timestamp", "")
            round_num = entry.get("round", "")
            
            formatted_parts.append(
                f"[轮次 {round_num}] {agent}:\n{content}\n"
            )
        
        return "\n---\n".join(formatted_parts)
    
    def _build_summary_prompt(
        self,
        debate_text: str,
        num_entries: int
    ) -> str:
        """
        构建压缩提示词
        
        Args:
            debate_text: 辩论文本
            num_entries: 辩论记录数量
            
        Returns:
            提示词字符串
        """
        prompt = f"""
你是一个财税法咨询团队的多轮辩论记录压缩器。

## 任务
将以下辩论记录压缩为结构化的共识和分歧点。

## 重要原则
1. 只保留对后续流程有价值的信息
2. 删除冗余的论证过程
3. 保留关键的数据引用和法规依据
4. 标注任何需要后续验证的分歧点
5. 识别被放弃的观点和理由

## 辩论记录（共 {num_entries} 条）
---
{debate_text}
---

## 输出要求
请输出以下格式的JSON（不要有任何额外文字）：

{{
    "consensus": "核心共识（用2-3段话总结辩论达成的共识，不要超过{self.compression_target}字）",
    "disagreements": ["未解决的分歧点1", "未解决的分歧点2"],
    "key_decisions": ["关键决策1", "关键决策2"],
    "abandoned_arguments": ["被放弃的观点1（附理由）", "被放弃的观点2（附理由）"]
}}

注意：
- consensus 应该简洁有力，能让后续流程直接使用
- disagreements 应该标注涉及的关键问题
- abandoned_arguments 应该说明为什么被放弃
"""
        
        return prompt
    
    def _parse_summary_response(self, response_content: str) -> Dict[str, Any]:
        """
        解析 LLM 响应
        
        Args:
            response_content: LLM 响应内容
            
        Returns:
            解析后的字典
        """
        # 尝试提取 JSON
        try:
            # 尝试直接解析
            return json.loads(response_content)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json ... ``` 块
        import re
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        matches = re.findall(json_pattern, response_content)
        
        if matches:
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue
        
        # 尝试提取 { ... } 块
        brace_pattern = r'\{[\s\S]*\}'
        matches = re.findall(brace_pattern, response_content)
        
        if matches:
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        # 如果都无法解析，返回默认值
        logger.warning("[Summarizer] 无法解析 LLM 响应，返回默认结构")
        return {
            "consensus": response_content[:500] if len(response_content) > 500 else response_content,
            "disagreements": [],
            "key_decisions": [],
            "abandoned_arguments": []
        }
    
    def estimate_tokens(self, text: str) -> int:
        """
        估算 token 数量
        
        简单的估算方法：中文约 1.5 字一个 token，英文约 4 字符一个 token
        
        Args:
            text: 文本内容
            
        Returns:
            估算的 token 数量
        """
        chinese_chars = sum(1 for c in text if '\u4e00' <= ord(c) <= '\u9fff')
        english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        other_chars = len(text) - chinese_chars - english_chars
        
        return int(chinese_chars / 1.5 + english_chars / 4 + other_chars / 4)


def summarizer_node_func(
    state: Dict[str, Any],
    **kwargs
) -> Dict[str, Any]:
    """
    LangGraph 节点函数包装器
    
    将 SummarizerNode 转换为 LangGraph 兼容的节点函数
    
    Args:
        state: LangGraph 状态
        **kwargs: 其他参数
        
    Returns:
        更新后的状态
    """
    import asyncio
    
    node = SummarizerNode(**kwargs)
    return asyncio.run(node.invoke(state, **kwargs))
