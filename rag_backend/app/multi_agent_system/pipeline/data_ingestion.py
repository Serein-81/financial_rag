"""
数据摄入管道 - 指针模式实现

核心设计:
1. 指针模式: State只存储元数据和切块ID,不存储全文
2. 按需检索: Agent需要时才拉取具体内容
3. 租户隔离: 所有数据带tenant_id标记
4. OCR支持: 支持图片和扫描件识别
"""

from pathlib import Path

from app.parsers import (
    StructuredPDFParser,
    StructuredWordParser,
    TextParser,
    ImageParser,
    FileParserFactory
)
from app.services.chunk_service import ChunkService
from app.services.ocr_service import OCRService
from app.knowledge_graph.entity_extractor import EntityExtractor
from app.services.unified_retriever import UnifiedRetriever
from app.multi_agent_system.state import AuditState


async def data_ingestion_pipeline(state: AuditState) -> AuditState:
    """
    数据摄入管道 - 指针模式
    
    处理流程:
    1. 解析文档(支持PDF/Word/Excel/图片/OCR)
    2. 创建切块并存储(只保留ID指针)
    3. 提取实体(从摘要中提取,避免全文)
    4. 检索知识(租户隔离)
    5. 读取企业长期记忆
    
    Args:
        state: 全局审查状态
        
    Returns:
        更新后的状态(包含document_metadata, chunk_ids, entities, knowledge_base)
    """
    
    # 初始化服务
    chunk_service = ChunkService()
    ocr_service = OCRService()
    entity_extractor = EntityExtractor()
    unified_retriever = UnifiedRetriever()
    parser_factory = FileParserFactory()
    
    # 存储结果
    document_metadata = []
    all_chunk_ids = []
    
    # 1. 解析文档并创建切块(指针模式)
    for doc in state.get('documents', []):
        try:
            # 根据文件类型选择解析器
            file_ext = Path(doc.filename).suffix.lower()
            
            # 解析文档
            if file_ext == '.pdf':
                parser = StructuredPDFParser()
                parsed = await parser.parse(doc.file)
                doc_type = 'pdf'
                text_content = parsed.get('text', '')
                
            elif file_ext in ['.doc', '.docx']:
                parser = StructuredWordParser()
                parsed = await parser.parse(doc.file)
                doc_type = 'word'
                text_content = parsed.get('text', '')
                
            elif file_ext in ['.txt', '.md']:
                parser = TextParser()
                parsed = await parser.parse(doc.file)
                doc_type = 'text'
                text_content = parsed.get('text', '')
                
            elif file_ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
                # OCR识别图片
                parser = ImageParser()
                parsed = await parser.parse(doc.file)
                doc_type = 'image_ocr'
                text_content = parsed.get('text', '')
                
            else:
                # 未知类型,尝试作为文本处理
                parser = TextParser()
                parsed = await parser.parse(doc.file)
                doc_type = 'unknown'
                text_content = parsed.get('text', '')
            
            # 📌 指针模式: 创建切块并存储,只保留ID
            if text_content:
                chunks = await chunk_service.create_chunks(
                    text=text_content,
                    doc_id=doc.id,
                    tenant_id=state['tenant_id'],
                    metadata={
                        'doc_name': doc.filename,
                        'doc_type': doc_type,
                        'user_id': state['user_id']
                    }
                )
                
                chunk_ids = [chunk.id for chunk in chunks]
                all_chunk_ids.extend(chunk_ids)
            else:
                chunk_ids = []
            
            # 📌 只存储元数据(摘要、目录),不存储全文
            summary = text_content[:500] if text_content else ""
            
            metadata = {
                'doc_id': doc.id,
                'doc_name': doc.filename,
                'doc_type': doc_type,
                'summary': summary,  # 只保留前500字摘要
                'chunk_ids': chunk_ids,  # 切块ID指针
                'total_chunks': len(chunk_ids),
                'tenant_id': state['tenant_id'],
                'parsed_structure': parsed.get('structure', {})  # 保留文档结构信息
            }
            
            document_metadata.append(metadata)
            
        except Exception as e:
            # 记录错误但不中断流程
            print(f"解析文档失败: {doc.filename}, 错误: {str(e)}")
            document_metadata.append({
                'doc_id': doc.id,
                'doc_name': doc.filename,
                'doc_type': 'error',
                'summary': f'解析失败: {str(e)}',
                'chunk_ids': [],
                'total_chunks': 0,
                'tenant_id': state['tenant_id'],
                'error': str(e)
            })
    
    # ✅ State只存储轻量化数据
    state['document_metadata'] = document_metadata
    state['chunk_ids'] = all_chunk_ids
    
    # 2. 提取实体(从摘要中提取,避免全文)
    try:
        all_summaries = " ".join([m['summary'] for m in document_metadata if m.get('summary')])
        
        if all_summaries:
            entities = await entity_extractor.extract(
                text=all_summaries,
                tenant_id=state['tenant_id']
            )
            
            # 过滤低置信度实体(< 0.7)
            high_confidence_entities = [
                e for e in entities 
                if e.get('confidence', 0) >= 0.7
            ]
            
            state['entities'] = high_confidence_entities
        else:
            state['entities'] = []
            
    except Exception as e:
        print(f"实体提取失败: {str(e)}")
        state['entities'] = []
    
    # 3. 检索知识(租户隔离)
    try:
        audit_type = state.get('audit_type', '财税审查')
        
        knowledge = await unified_retriever.retrieve(
            query=audit_type,
            kb_id='tax_legal_kb',
            filters={'tenant_id': state['tenant_id']},  # 🔒 租户隔离
            top_k=10
        )
        
        state['knowledge_base'] = knowledge
        
    except Exception as e:
        print(f"知识检索失败: {str(e)}")
        state['knowledge_base'] = []
    
    # 4. 读取企业长期记忆(历史风险和核心事实)
    try:
        state = await _load_enterprise_memory(state)
    except Exception as e:
        print(f"读取企业记忆失败: {str(e)}")
        state['historical_risks'] = []
        state['semantic_facts'] = []
    
    return state


class DataIngestionPipeline:
    """数据摄入管道类 - 为测试和API调用提供统一接口"""
    
    def __init__(self):
        self.chunk_service = None
        self.ocr_service = None
        self.entity_extractor = None
        self.unified_retriever = None
        self.parser_factory = None
    
    async def process(self, state: AuditState) -> AuditState:
        """处理数据摄入管道"""
        return await data_ingestion_pipeline(state)
    
    async def initialize(self):
        """初始化服务组件"""
        from app.services.chunk_service import ChunkService
        from app.services.ocr_service import OCRService
        from app.knowledge_graph.entity_extractor import EntityExtractor
        from app.services.unified_retriever import UnifiedRetriever
        from app.parsers import FileParserFactory
        
        self.chunk_service = ChunkService()
        self.ocr_service = OCRService()
        self.entity_extractor = EntityExtractor()
        self.unified_retriever = UnifiedRetriever()
        self.parser_factory = FileParserFactory()


async def _load_enterprise_memory(state: AuditState) -> AuditState:
    """
    读取企业长期记忆
    
    包括:
    1. 情景记忆: 历史审查记录和风险清单
    2. 语义记忆: 已确认的核心事实
    """
    from app.memory_system.episodic_memory import EpisodicMemory
    from app.memory_system.semantic_memory import SemanticMemory
    
    # 读取情景记忆: 上一次审查的风险清单
    try:
        episodic = EpisodicMemory()
        historical_audits = await episodic.search(
            user_id=state['user_id'],
            query=f"企业 {state['tenant_id']} 历史审查风险",
            filters={'tenant_id': state['tenant_id']},  # 🔒 租户隔离
            top_k=5
        )
        state['historical_risks'] = historical_audits
    except Exception as e:
        print(f"读取情景记忆失败: {str(e)}")
        state['historical_risks'] = []
    
    # 读取语义记忆: 已确认的核心事实
    try:
        semantic = SemanticMemory()
        facts = await semantic.search(
            user_id=state['user_id'],
            query=f"企业 {state['tenant_id']} 核心事实",
            filters={'tenant_id': state['tenant_id']},  # 🔒 租户隔离
            top_k=10
        )
        state['semantic_facts'] = facts
    except Exception as e:
        print(f"读取语义记忆失败: {str(e)}")
        state['semantic_facts'] = []
    
    return state
