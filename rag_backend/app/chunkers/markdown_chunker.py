# app/chunkers/markdown_chunker.py
from typing import List, Dict, Tuple
from .base_chunker import ChunkStrategy, ChunkResult


class MarkdownChunkStrategy(ChunkStrategy):
    """
    Markdown 文档智能切块策略
    
    特性:
    1. 识别标题层级(#, ##, ###等)
    2. 按文档结构进行切分
    3. 保留标题路径信息
    4. 基于 Token 数量进行智能合并
    """
    
    def get_supported_types(self) -> List[str]:
        return ["markdown", "md"]
    
    def chunk(
        self, 
        text: str, 
        chunk_tokens: int = 500, 
        overlap_tokens: int = 50
    ) -> List[ChunkResult]:
        """
        对 Markdown 文本进行智能切分
        
        流程:
        1. 解析 Markdown 结构,提取段落和标题
        2. 基于 Token 数量合并段落
        3. 处理重叠策略
        4. 生成带元数据的切块结果
        """
        if not text or not text.strip():
            return []
        
        # 1. 解析 Markdown 结构
        paragraphs = self._split_paragraphs_with_headings(text)
        
        if not paragraphs:
            return []
        
        # 2. 基于 Token 数量进行切块
        chunks = self._chunk_paragraphs(paragraphs, chunk_tokens, overlap_tokens)
        
        return chunks
    
    def _split_paragraphs_with_headings(self, text: str) -> List[Dict]:
        """
        将 Markdown 文本分割为段落,并保留标题信息
        
        Returns:
            List[Dict]: 段落列表,每个段落包含:
                - content: 段落内容
                - heading_path: 标题路径
                - start: 起始位置
                - end: 结束位置
        """
        lines = text.splitlines()
        heading_stack: List[Tuple[int, str]] = []  # (level, title)
        paragraphs: List[Dict] = []
        buf: List[str] = []
        char_pos = 0
        
        def flush_buf(end_pos: int):
            """将缓冲区内容刷新为一个段落"""
            if not buf:
                return
            
            content = "\n".join(buf).strip()
            if not content:
                buf.clear()
                return
            
            # 构建标题路径
            heading_path = " > ".join(title for _, title in heading_stack) if heading_stack else None
            
            paragraphs.append({
                "content": content,
                "heading_path": heading_path,
                "start": char_pos - len(content),
                "end": end_pos
            })
            buf.clear()
        
        for line in lines:
            # 检测标题行
            if line.strip().startswith('#'):
                # 刷新之前的缓冲区
                flush_buf(char_pos)
                
                # 解析标题
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                
                if level <= 0:
                    level = 1
                
                # 更新标题栈
                # 移除比当前级别深的标题
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                
                heading_stack.append((level, title))
                char_pos += len(line) + 1
                continue
            
            # 检测段落分隔(空行)
            if line.strip() == "":
                flush_buf(char_pos)
                char_pos += 1
                continue
            
            # 普通行,加入缓冲区
            buf.append(line)
            char_pos += len(line) + 1
        
        # 刷新最后的缓冲区
        flush_buf(char_pos)
        
        # 如果没有段落,返回整个文本作为一个段落
        if not paragraphs:
            paragraphs = [{
                "content": text,
                "heading_path": None,
                "start": 0,
                "end": len(text)
            }]
        
        return paragraphs
    
    def _chunk_paragraphs(
        self, 
        paragraphs: List[Dict], 
        chunk_tokens: int, 
        overlap_tokens: int
    ) -> List[ChunkResult]:
        """
        基于 Token 数量将段落合并为切块
        
        策略:
        1. 尽量将段落合并到接近 chunk_tokens
        2. 如果单个段落超过 chunk_tokens,单独成块
        3. 支持重叠策略
        """
        chunks: List[ChunkResult] = []
        current_chunk: List[Dict] = []
        current_tokens = 0
        i = 0
        
        while i < len(paragraphs):
            p = paragraphs[i]
            p_tokens = self.approx_token_len(p["content"]) or 1
            
            # 如果当前段落加入后不超过限制,则加入
            if current_tokens + p_tokens <= chunk_tokens or not current_chunk:
                current_chunk.append(p)
                current_tokens += p_tokens
                i += 1
            else:
                # 生成当前切块
                if current_chunk:
                    chunks.append(self._create_chunk_result(current_chunk, current_tokens))
                
                # 处理重叠:从当前切块末尾取部分段落
                if overlap_tokens > 0:
                    kept: List[Dict] = []
                    kept_tokens = 0
                    
                    # 从后往前取段落,直到达到 overlap_tokens
                    for x in reversed(current_chunk):
                        t = self.approx_token_len(x["content"])
                        if kept_tokens + t > overlap_tokens:
                            break
                        kept.insert(0, x)
                        kept_tokens += t
                    
                    current_chunk = kept
                    current_tokens = kept_tokens
                else:
                    current_chunk = []
                    current_tokens = 0
        
        # 处理最后一个切块
        if current_chunk:
            chunks.append(self._create_chunk_result(current_chunk, current_tokens))
        
        return chunks
    
    def _create_chunk_result(self, paragraphs: List[Dict], tokens: int) -> ChunkResult:
        """
        从段落列表创建切块结果
        """
        content = "\n\n".join(p["content"] for p in paragraphs)
        start = paragraphs[0]["start"]
        end = paragraphs[-1]["end"]
        
        # 获取标题路径(使用第一个段落的标题路径)
        heading_path = paragraphs[0].get("heading_path")
        
        # 如果有多个不同的标题路径,取最深的那个
        for p in paragraphs:
            if p.get("heading_path") and (
                not heading_path or 
                len(p["heading_path"]) > len(heading_path)
            ):
                heading_path = p["heading_path"]
        
        return ChunkResult(
            content=content,
            start=start,
            end=end,
            tokens=tokens,
            heading_path=heading_path,
            metadata={"paragraph_count": len(paragraphs)}
        )
