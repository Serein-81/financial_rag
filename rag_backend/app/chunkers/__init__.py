"""
文本切块器模块 (v2)
支持领域感知切分、节点关系、元数据注入等高级能力

模块结构：
- base_chunker: ChunkResult 数据类 + ChunkStrategy 抽象基类
- domain_detector: 领域检测器
- domain_chunker_factory: 领域切块工厂
- financial_chunker: 财务领域切块策略
- tax_chunker: 税务领域切块策略
- legal_chunker: 法务领域切块策略
- general_chunker: 通用领域切块策略
- ast_sanitizer: AST 净化器
- metadata_injector: AST 上下文栈元数据注入
- entity_resolver: 法务实体显式化器
- summary_generator: PARENT 节点摘要生成器
- relationship_builder: 节点关系构建器
- structured_document_chunker: 结构化文档切块器（保留）
- plain_text_chunker: 纯文本切块器（保留）
"""

from .base_chunker import ChunkStrategy, ChunkResult
from .domain_detector import DomainDetector, domain_detector
from .domain_chunker_factory import DomainChunkerFactory, domain_chunker_factory
from .financial_chunker import FinancialChunker, financial_chunker
from .tax_chunker import TaxChunker, tax_chunker
from .legal_chunker import LegalChunker, legal_chunker
from .general_chunker import GeneralChunker, general_chunker
from .ast_sanitizer import ASTSanitizer
from .metadata_injector import MetadataInjector, ContextStack, metadata_injector
from .entity_resolver import EntityResolver, entity_resolver
from .summary_generator import SummaryGenerator, summary_generator
from .relationship_builder import RelationshipBuilder, relationship_builder
from .structured_document_chunker import StructuredDocumentChunker
from .plain_text_chunker import PlainTextChunkStrategy

__all__ = [
    'ChunkStrategy',
    'ChunkResult',
    'DomainDetector',
    'domain_detector',
    'DomainChunkerFactory',
    'domain_chunker_factory',
    'FinancialChunker',
    'financial_chunker',
    'TaxChunker',
    'tax_chunker',
    'LegalChunker',
    'legal_chunker',
    'GeneralChunker',
    'general_chunker',
    'ASTSanitizer',
    'MetadataInjector',
    'ContextStack',
    'metadata_injector',
    'EntityResolver',
    'entity_resolver',
    'SummaryGenerator',
    'summary_generator',
    'RelationshipBuilder',
    'relationship_builder',
    'StructuredDocumentChunker',
    'PlainTextChunkStrategy',
]
