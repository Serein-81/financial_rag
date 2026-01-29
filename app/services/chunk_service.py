from typing import List


class ChunkService:
    @staticmethod
    def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        简单的文本切分算法
        :param text: 原始长文本
        :param chunk_size: 每段大约多少字
        :param overlap: 重叠多少字 (防止切断关键句子)
        """
        if not text:
            return []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            # 截取一段
            end = start + chunk_size
            chunk = text[start:end]

            # 存入列表
            chunks.append(chunk)

            # 移动指针 (步长 = 块大小 - 重叠部分)
            # 这样下一段的开头会包含上一段的结尾，保证上下文连贯
            start += (chunk_size - overlap)

        return chunks


chunk_service = ChunkService()