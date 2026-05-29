"""
自适应智能分块器

基于语义边界和主题识别进行智能分块，而不是简单的固定大小切分。

支持两种模式:
1. 主题边界识别模式 - 使用 LLM 识别主题转换点
2. 递归切分模式 - 对超大块进行递归处理
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)


@dataclass
class ChunkMetadata:
    """分块元数据"""
    start_pos: int
    end_pos: int
    topic: Optional[str] = None
    importance: float = 0.5
    chunk_type: str = "text"


@dataclass
class AdaptiveChunk:
    """自适应分块结果"""
    content: str
    metadata: ChunkMetadata
    char_count: int
    token_count: Optional[int] = None


class AdaptiveChunker:
    """
    自适应智能分块器

    特点:
    1. 识别语义边界，按主题切分
    2. 保持段落完整性
    3. 递归处理超大块
    4. 生成丰富的元数据
    """

    def __init__(
        self,
        llm_service=None,
        min_chunk_size: int = 200,
        max_chunk_size: int = 1000,
        enable_llm_boundary: bool = False
    ):
        """
        初始化自适应分块器

        Args:
            llm_service: LLM 服务（用于主题识别）
            min_chunk_size: 最小块大小（字符数）
            max_chunk_size: 最大块大小（字符数）
            enable_llm_boundary: 是否启用 LLM 主题边界识别
        """
        self.llm_service = llm_service
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.enable_llm_boundary = enable_llm_boundary and llm_service is not None

    async def chunk(self, document: str) -> List[AdaptiveChunk]:
        """
        对文档进行自适应分块

        Args:
            document: 文档文本

        Returns:
            分块结果列表
        """
        if not document or not document.strip():
            return []

        logger.debug(f"[AdaptiveChunker] 开始分块，文档长度: {len(document)} 字符")

        # 根据配置选择分块策略
        if self.enable_llm_boundary:
            chunks = await self._chunk_with_llm(document)
        else:
            chunks = self._chunk_with_rules(document)

        logger.debug(f"[AdaptiveChunker] 分块完成，共 {len(chunks)} 个块")

        return chunks

    async def _chunk_with_llm(self, document: str) -> List[AdaptiveChunk]:
        """
        使用 LLM 识别主题边界进行分块

        Args:
            document: 文档文本

        Returns:
            分块列表
        """
        logger.debug("[AdaptiveChunker] 使用 LLM 主题边界识别")

        # 调用 LLM 识别主题边界
        boundaries = await self._identify_topic_boundaries(document)

        # 按边界切分
        chunks = []
        start = 0

        for boundary in boundaries + [len(document)]:
            if boundary > start:
                chunk_text = document[start:boundary].strip()

                if chunk_text:
                    # 检查是否超大
                    if len(chunk_text) > self.max_chunk_size:
                        # 递归切分
                        sub_chunks = self._recursive_split(chunk_text, start)
                        chunks.extend(sub_chunks)
                    else:
                        # 创建块
                        chunk = AdaptiveChunk(
                            content=chunk_text,
                            metadata=ChunkMetadata(
                                start_pos=start,
                                end_pos=boundary,
                                chunk_type="text"
                            ),
                            char_count=len(chunk_text)
                        )
                        chunks.append(chunk)

                start = boundary

        return chunks

    async def _identify_topic_boundaries(self, document: str) -> List[int]:
        """
        使用 LLM 识别主题转换边界

        Args:
            document: 文档文本

        Returns:
            边界位置列表（字符索引）
        """
        # 简化处理：如果文档太长，先分段
        if len(document) > 3000:
            # 每 3000 字符处理一次
            segments = [document[i:i+3000] for i in range(0, len(document), 3000)]
        else:
            segments = [document]

        all_boundaries = []
        offset = 0

        for segment in segments:
            try:
                # 构造 Prompt
                prompt = f"""分析以下文本，标记主题转换的位置（大约字符索引）。

文本:
{segment[:2000]}  # 限制长度

请返回 JSON 格式: {{"boundaries": [100, 350, 600, ...]}}

只返回 JSON，不要其他内容。"""

                # 调用 LLM
                response = await self.llm_service.generate(prompt, max_tokens=200)

                # 解析结果
                import json
                try:
                    result = json.loads(response)
                    boundaries = result.get("boundaries", [])

                    # 添加偏移量
                    for b in boundaries:
                        if isinstance(b, (int, float)):
                            all_boundaries.append(offset + int(b))

                except json.JSONDecodeError:
                    logger.warning(f"[AdaptiveChunker] LLM 返回格式错误: {response[:100]}")

            except Exception as e:
                logger.error(f"[AdaptiveChunker] LLM 主题识别失败: {e}")

            offset += len(segment)

        return sorted(set(all_boundaries))

    def _chunk_with_rules(self, document: str) -> List[AdaptiveChunk]:
        """
        使用规则进行分块（不依赖 LLM）

        规则:
        1. 按段落切分
        2. 识别自然边界（标题、空行）
        3. 合并小段落
        4. 切分大段落

        Args:
            document: 文档文本

        Returns:
            分块列表
        """
        logger.debug("[AdaptiveChunker] 使用规则分块")

        # 1. 按自然边界切分（双换行、标题等）
        segments = self._split_by_natural_boundaries(document)

        # 2. 合并和调整大小
        chunks = self._merge_and_resize_segments(segments)

        return chunks

    def _split_by_natural_boundaries(self, document: str) -> List[Tuple[str, int]]:
        """
        按自然边界切分文档

        Args:
            document: 文档文本

        Returns:
            (文本片段, 起始位置) 列表
        """
        segments = []

        # 定义自然边界模式
        patterns = [
            # 标题模式
            r'\n#{1,6}\s+.+?\n',  # Markdown 标题
            r'\n第[一二三四五六七八九十\d]+章.+?\n',  # 章节标题
            r'\n第[一二三四五六七八九十\d]+节.+?\n',  # 节标题

            # 段落分隔
            r'\n\s*\n',  # 双换行
        ]

        # 合并模式
        boundary_pattern = '|'.join(patterns)

        # 查找所有边界
        matches = list(re.finditer(boundary_pattern, document))

        if not matches:
            # 没有找到边界，整体作为一个段落
            return [(document, 0)]

        # 按边界切分
        start = 0
        for match in matches:
            boundary_pos = match.start()

            if boundary_pos > start:
                segment = document[start:boundary_pos].strip()
                if segment:
                    segments.append((segment, start))

            start = match.end()

        # 添加最后一段
        if start < len(document):
            segment = document[start:].strip()
            if segment:
                segments.append((segment, start))

        return segments

    def _merge_and_resize_segments(
        self,
        segments: List[Tuple[str, int]]
    ) -> List[AdaptiveChunk]:
        """
        合并小段落，切分大段落

        Args:
            segments: (文本, 起始位置) 列表

        Returns:
            分块列表
        """
        chunks = []
        buffer = []
        buffer_start = 0
        buffer_size = 0

        for segment, start_pos in segments:
            segment_size = len(segment)

            # 情况1: 段落太大，直接切分
            if segment_size > self.max_chunk_size:
                # 先处理缓冲区
                if buffer:
                    chunk = self._create_chunk_from_buffer(buffer, buffer_start)
                    chunks.append(chunk)
                    buffer = []
                    buffer_size = 0

                # 递归切分大段落
                sub_chunks = self._recursive_split(segment, start_pos)
                chunks.extend(sub_chunks)

            # 情况2: 加入缓冲区后会超过最大大小
            elif buffer_size + segment_size > self.max_chunk_size:
                # 先输出缓冲区
                if buffer:
                    chunk = self._create_chunk_from_buffer(buffer, buffer_start)
                    chunks.append(chunk)

                # 重新开始
                buffer = [segment]
                buffer_start = start_pos
                buffer_size = segment_size

            # 情况3: 正常加入缓冲区
            else:
                if not buffer:
                    buffer_start = start_pos

                buffer.append(segment)
                buffer_size += segment_size

        # 处理剩余缓冲区
        if buffer:
            chunk = self._create_chunk_from_buffer(buffer, buffer_start)
            chunks.append(chunk)

        return chunks

    def _create_chunk_from_buffer(
        self,
        buffer: List[str],
        start_pos: int
    ) -> AdaptiveChunk:
        """从缓冲区创建分块"""
        content = "\n\n".join(buffer)

        return AdaptiveChunk(
            content=content,
            metadata=ChunkMetadata(
                start_pos=start_pos,
                end_pos=start_pos + len(content),
                chunk_type="text"
            ),
            char_count=len(content)
        )

    def _recursive_split(
        self,
        text: str,
        base_offset: int = 0
    ) -> List[AdaptiveChunk]:
        """
        递归切分超大文本

        Args:
            text: 文本
            base_offset: 基准偏移量

        Returns:
            分块列表
        """
        chunks = []

        # 按句子切分
        sentences = re.split(r'([。！？\.!?])', text)

        # 重新组合句子（保留标点）
        combined_sentences = []
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else "")
            combined_sentences.append(sentence)

        # 组装成合适大小的块
        current_chunk = []
        current_size = 0
        current_start = base_offset

        for sentence in combined_sentences:
            sentence_size = len(sentence)

            if current_size + sentence_size > self.max_chunk_size and current_chunk:
                # 输出当前块
                content = "".join(current_chunk)
                chunk = AdaptiveChunk(
                    content=content,
                    metadata=ChunkMetadata(
                        start_pos=current_start,
                        end_pos=current_start + len(content),
                        chunk_type="text"
                    ),
                    char_count=len(content)
                )
                chunks.append(chunk)

                # 重置
                current_chunk = [sentence]
                current_size = sentence_size
                current_start += len(content)
            else:
                current_chunk.append(sentence)
                current_size += sentence_size

        # 处理剩余
        if current_chunk:
            content = "".join(current_chunk)
            chunk = AdaptiveChunk(
                content=content,
                metadata=ChunkMetadata(
                    start_pos=current_start,
                    end_pos=current_start + len(content),
                    chunk_type="text"
                ),
                char_count=len(content)
            )
            chunks.append(chunk)

        return chunks


class PropositionChunker:
    """
    命题提取分块器

    将文档分解为原子命题（atomic propositions），每个命题是一个独立的事实。
    这是一种更精细的分块方式，特别适合事实密集的文档。
    """

    def __init__(self, llm_service):
        """
        初始化命题分块器

        Args:
            llm_service: LLM 服务
        """
        self.llm_service = llm_service

    async def chunk(self, document: str) -> List[Dict[str, Any]]:
        """
        将文档分解为命题

        Args:
            document: 文档文本

        Returns:
            命题列表
        """
        if not document or not document.strip():
            return []

        logger.debug(f"[PropositionChunker] 开始提取命题，文档长度: {len(document)}")

        # 如果文档太长，先切分
        if len(document) > 2000:
            segments = [document[i:i+2000] for i in range(0, len(document), 1500)]
        else:
            segments = [document]

        all_propositions = []

        for segment in segments:
            propositions = await self._extract_propositions(segment)
            all_propositions.extend(propositions)

        logger.debug(f"[PropositionChunker] 提取完成，共 {len(all_propositions)} 个命题")

        return all_propositions

    async def _extract_propositions(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中提取命题

        Args:
            text: 文本片段

        Returns:
            命题列表
        """
        prompt = f"""将以下文本分解为独立的原子命题（facts）。

原则:
1. 每个命题包含一个完整的事实
2. 命题之间相互独立
3. 保留关键数值和时间

文本:
{text}

返回 JSON 格式:
{{
  "propositions": [
    {{"id": 1, "text": "企业所得税标准税率为25%", "type": "fact"}},
    {{"id": 2, "text": "小型微利企业适用20%税率", "type": "rule"}}
  ]
}}

只返回 JSON，不要其他内容。"""

        try:
            response = await self.llm_service.generate(prompt, max_tokens=500)

            import json
            result = json.loads(response)
            propositions = result.get("propositions", [])

            return propositions

        except Exception as e:
            logger.error(f"[PropositionChunker] 提取命题失败: {e}")
            return []
