"""
PARENT 节点摘要生成器 (Summary Generator)

三层保护：
1. asyncio.Semaphore 严格控制并发数（单进程级别）
2. Batch Prompt 将多个文本合并为一次 LLM 调用
3. 超时 + 降级：超时或失败时取原文前 50 字符为兜底

注意：仅用于 legal domain 的 PARENT 节点。
分布式环境下应通过 ARQ 任务队列调度（参见 arq_tasks.py）。
"""

import asyncio
import logging
from typing import List
from app.chunkers.base_chunker import ChunkResult
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """
    PARENT 节点摘要生成器。

    为法律文档章节的 PARENT 节点生成 50 字摘要，
    作为检索时的语义锚点。
    """

    def __init__(
        self,
        max_concurrency: int = 10,
        batch_size: int = 5,
        timeout: float = 10.0,
        fallback_chars: int = 50,
    ):
        """
        Args:
            max_concurrency: LLM 并发上限
            batch_size: 每个 batch 的文本数
            timeout: 单个 batch 超时时间（秒）
            fallback_chars: 降级截断长度（字符）
        """
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._batch_size = batch_size
        self._timeout = timeout
        self._fallback_chars = fallback_chars

    async def generate_for_all(
        self,
        parent_chunks: List[ChunkResult],
    ) -> List[ChunkResult]:
        """
        为所有 PARENT 节点生成摘要。

        策略：
        - 将 parent_chunks 按 batch_size 分组
        - 每组作为一个 batch request 发送
        - Semaphore 限制全局并发
        """
        if not parent_chunks:
            return parent_chunks

        # 按 batch 分组
        batches = [
            parent_chunks[i:i + self._batch_size]
            for i in range(0, len(parent_chunks), self._batch_size)
        ]

        logger.info(
            f"[SummaryGenerator] 开始为 {len(parent_chunks)} 个节点生成摘要, "
            f"{len(batches)} 个 batch, 并发上限 {self._semaphore._value}"
        )

        # 并发处理所有 batch（Semaphore 限制实际并发数）
        tasks = [self._process_batch(batch) for batch in batches]
        await asyncio.gather(*tasks)

        success_count = sum(
            1 for c in parent_chunks
            if c.summary and len(c.summary) > 10
        )
        logger.info(
            f"[SummaryGenerator] 完成: {success_count}/{len(parent_chunks)}"
        )
        return parent_chunks

    async def _process_batch(self, batch: List[ChunkResult]):
        """处理一个 batch：受 Semaphore 和 timeout 双重保护"""
        async with self._semaphore:
            try:
                await asyncio.wait_for(
                    self._call_llm_batch(batch),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"[SummaryGenerator] Batch 超时 ({self._timeout}s), "
                    f"回退到截断摘要"
                )
                for chunk in batch:
                    chunk.summary = chunk.content[:self._fallback_chars]
            except Exception as e:
                logger.error(f"[SummaryGenerator] Batch 失败: {e}")
                for chunk in batch:
                    chunk.summary = chunk.content[:self._fallback_chars]

    async def _call_llm_batch(self, batch: List[ChunkResult]):
        """
        一次 LLM 调用生成 batch 内所有文本的摘要。

        Batch Prompt 从 prompts/chunkers/summary_generate_prompt.md 加载。
        {documents} 占位符运行时替换为序号的条款原文。
        """
        lines = []
        for i, chunk in enumerate(batch, 1):
            content = chunk.content[:300]
            lines.append(f"{i}. {content}")

        from app.prompts.loader import load_prompt_template
        prompt = load_prompt_template(
            "chunkers/summary_generate_prompt.md",
            documents="\n".join(lines),
        )

        response = await llm_service.get_answer(prompt, [], [])
        self._parse_batch_response(response, batch)

    def _parse_batch_response(self, response: str, batch: List[ChunkResult]):
        """解析 LLM 的 batch 响应"""
        summaries = {}
        for line in response.strip().split("\n"):
            line = line.strip()
            if "|" in line:
                try:
                    idx_str, summary = line.split("|", 1)
                    idx = int(idx_str.strip())
                    summaries[idx] = summary.strip()
                except (ValueError, IndexError):
                    continue

        for i, chunk in enumerate(batch, 1):
            chunk.summary = summaries.get(
                i, chunk.content[:self._fallback_chars]
            )


# 全局单例
summary_generator = SummaryGenerator()
