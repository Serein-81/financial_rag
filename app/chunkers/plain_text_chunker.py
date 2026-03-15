# app/chunkers/plain_text_chunker.py
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .base_chunker import ChunkStrategy, ChunkResult


class PlainTextChunkStrategy(ChunkStrategy):
    """
    纯文本切块策略(兼容现有实现)
    
    使用 LangChain 的 RecursiveCharacterTextSplitter
    保持向后兼容性
    """
    
    def get_supported_types(self) -> List[str]:
        return ["plain_text", "text", "default"]
    
    def chunk(
        self, 
        text: str, 
        chunk_tokens: int = 500, 
        overlap_tokens: int = 50
    ) -> List[ChunkResult]:
        """
        使用递归字符切分策略
        
        注意: 这里仍使用字符数而非 Token 数,保持向后兼容
        """
        if not text or not text.strip():
            return []
        
        # 使用 LangChain 的切分器
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_tokens,  # 这里实际是字符数
            chunk_overlap=overlap_tokens,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""],
            length_function=len,
        )
        
        chunks_text = text_splitter.split_text(text)
        
        # 转换为 ChunkResult 格式
        results = []
        current_pos = 0
        
        for chunk_text in chunks_text:
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue
            
            # 查找切片在原文中的位置
            start = text.find(chunk_text, current_pos)
            if start == -1:
                start = current_pos
            
            end = start + len(chunk_text)
            tokens = self.approx_token_len(chunk_text)
            
            results.append(ChunkResult(
                content=chunk_text,
                start=start,
                end=end,
                tokens=tokens,
                heading_path=None,
                metadata={}
            ))
            
            current_pos = end
        
        return results
