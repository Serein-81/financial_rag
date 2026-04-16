"""
阶段2集成测试 - 数据摄入管道完整流程测试
"""

import pytest
import asyncio
from pathlib import Path
from app.multi_agent_system.pipeline.data_ingestion import data_ingestion_pipeline
from app.multi_agent_system.tools.document_retrieval import DocumentChunkRetrievalTool
from app.multi_agent_system.state import AuditState


class MockFile:
    """模拟文件对象"""
    def __init__(self, filename: str, content: bytes, file_id: str):
        self.filename = filename
        self.file = content
        self.id = file_id


@pytest.mark.asyncio
async def test_完整数据摄入流程():
    """测试完整的数据摄入流程"""
    # 准备多种类型的文档
    documents = [
        MockFile("财务报表.txt", b"Test financial report content", "doc1"),
        MockFile("合同.txt", b"Test contract content", "doc2"),
        MockFile("发票.txt", b"Test invoice content", "doc3")
    ]
    
    state = AuditState(
        documents=documents,
        audit_type="comprehensive_audit",
        user_id=1,
        tenant_id="tenant_integration_001"
    )
    
    # 执行数据摄入
    result = await data_ingestion_pipeline(state)
    
    # 验证结果结构
    assert 'document_metadata' in result
    assert 'chunk_ids' in result
    assert 'entities' in result
    assert 'knowledge_base' in result
    
    # 验证文档数量
    assert len(result['document_metadata']) == 3
    
    # 验证每个文档都有元数据
    for doc_meta in result['document_metadata']:
        assert 'doc_id' in doc_meta
        assert 'doc_name' in doc_meta
        assert 'doc_type' in doc_meta
        assert 'summary' in doc_meta
        assert 'chunk_ids' in doc_meta
        assert 'tenant_id' in doc_meta
        assert doc_meta['tenant_id'] == "tenant_integration_001"


@pytest.mark.asyncio
async def test_指针模式生效():
    """验证指针模式:State大小应该很小"""
    import sys
    
    # 创建大文档
    large_content = "这是一个很长的文档内容。" * 1000
    
    state = AuditState(
        documents=[
            MockFile("large_doc.txt", large_content.encode('utf-8'), "doc_large")
        ],
        audit_type="audit",
        user_id=1,
        tenant_id="tenant_pointer_test"
    )
    
    # 执行摄入
    result = await data_ingestion_pipeline(state)
    
    # 计算State大小(粗略估计)
    import json
    state_json = json.dumps({
        'document_metadata': result['document_metadata'],
        'chunk_ids': result['chunk_ids']
    }, ensure_ascii=False)
    
    state_size_kb = len(state_json.encode('utf-8')) / 1024
    
    # State大小应该小于10KB
    print(f"State大小: {state_size_kb:.2f} KB")
    assert state_size_kb < 10, f"State太大: {state_size_kb:.2f} KB"


@pytest.mark.asyncio
async def test_按需检索工具():
    """测试按需检索工具"""
    # 先执行摄入
    state = AuditState(
        documents=[
            MockFile("test_doc.txt", b"Test content for retrieval", "doc_retrieval")
        ],
        audit_type="audit",
        user_id=1,
        tenant_id="tenant_retrieval_test"
    )
    
    result = await data_ingestion_pipeline(state)
    
    # 获取切块ID
    chunk_ids = result['chunk_ids']
    
    if chunk_ids:
        # 测试按需检索
        retrieval_tool = DocumentChunkRetrievalTool()
        
        retrieved = await retrieval_tool.read_document_chunks(
            chunk_ids=chunk_ids[:5],  # 只读取前5个
            tenant_id="tenant_retrieval_test",
            max_chunks=10
        )
        
        # 验证检索结果
        assert 'chunks' in retrieved
        assert 'total' in retrieved
        assert retrieved['total'] <= 5


@pytest.mark.asyncio
async def test_租户隔离验证():
    """验证租户隔离:不同租户的数据应该隔离"""
    # 租户A的数据
    state_a = AuditState(
        documents=[
            MockFile("tenant_a_doc.txt", "Tenant A content".encode('utf-8'), "doc_a")
        ],
        audit_type="audit",
        user_id=1,
        tenant_id="tenant_a"
    )
    
    # 租户B的数据
    state_b = AuditState(
        documents=[
            MockFile("tenant_b_doc.txt", "Tenant B content".encode('utf-8'), "doc_b")
        ],
        audit_type="audit",
        user_id=2,
        tenant_id="tenant_b"
    )
    
    # 分别执行摄入
    result_a = await data_ingestion_pipeline(state_a)
    result_b = await data_ingestion_pipeline(state_b)
    
    # 验证租户ID正确
    assert result_a['document_metadata'][0]['tenant_id'] == "tenant_a"
    assert result_b['document_metadata'][0]['tenant_id'] == "tenant_b"
    
    # 验证切块ID不重复
    chunk_ids_a = set(result_a['chunk_ids'])
    chunk_ids_b = set(result_b['chunk_ids'])
    assert len(chunk_ids_a.intersection(chunk_ids_b)) == 0


@pytest.mark.asyncio
async def test_实体提取集成():
    """测试实体提取集成"""
    state = AuditState(
        documents=[
            MockFile(
                "entity_test.txt",
                "ABC公司与XYZ公司签订合同，金额为100万元，日期为2024年1月1日。".encode('utf-8'),
                "doc_entity"
            )
        ],
        audit_type="audit",
        user_id=1,
        tenant_id="tenant_entity_test"
    )
    
    result = await data_ingestion_pipeline(state)
    
    # 应该提取到实体
    assert 'entities' in result
    # 注意:实际提取结果取决于EntityExtractor的实现


@pytest.mark.asyncio
async def test_知识检索集成():
    """测试知识检索集成"""
    state = AuditState(
        documents=[
            MockFile("kb_test.txt", b"Test content", "doc_kb")
        ],
        audit_type="tax_audit",
        user_id=1,
        tenant_id="tenant_kb_test"
    )
    
    result = await data_ingestion_pipeline(state)
    
    # 应该有知识库检索结果
    assert 'knowledge_base' in result
    # 注意:实际结果取决于知识库内容


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
