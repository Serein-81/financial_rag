# app/chunkers/__init__.py
"""
文本切块器模块
使用策略模式实现可扩展的文本切分架构
"""

from .base_chunker import ChunkStrategy, ChunkResult
from .chunk_factory import ChunkStrategyFactory
from .markdown_chunker import MarkdownChunkStrategy
from .plain_text_chunker import PlainTextChunkStrategy

__all__ = [
    'ChunkStrategy',
    'ChunkResult',
    'ChunkStrategyFactory',
    'MarkdownChunkStrategy',
    'PlainTextChunkStrategy'
]
