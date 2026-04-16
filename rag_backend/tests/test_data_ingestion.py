"""
数据摄入管道单元测试
"""

import pytest
from app.multi_agent_system.pipeline.data_ingestion import data_ingestion_pipeline
from app.multi_agent_system.state import AuditState


class MockFile:
    """模拟文件对象"""
    def __init__(self, filename: str, content: bytes, file_id: str = "test_id"):
        self.filename = filename
        self.file = content
        self.id = file_id


@pytest.mark.asyncio
async def test_data_ingestion_with_text():
    """测试文本文件摄入"""
    # 准备测试数据
    state = AuditState(
        documents=[
            MockFile("test.txt", b"This is a test document.", "doc1")
        ],
        audit_type="financial_audit",
        user_id=1,
        tenant_id="tenant_test_001"
    )
    
    # 执行摄入
    result = await data_ingestion_pipeline(state)
    
    # 验证结果
    assert 'document_metadata' in result
    assert len(result['document_metadata']) == 1
    assert result['document_metadata'][0]['doc_type'] == 'text'
    assert 'chunk_ids' in result
    assert 'entities' in result


@pytest.mark.asyncio
async def test_指针模式验证():
    """验证指针模式:State不存储全文"""
    # 准备大文本
    large_text = "测试内容 " * 1000  # 创建大文本
    
    state = AuditState(
        documents=[
            MockFile("large.txt", large_text.encode('utf-8'), "doc2")
        ],
        audit_type="tax_audit",
        user_id=1,
        tenant_id="tenant_test_002"
    )
    
    # 执行摄入
    result = await data_ingestion_pipeline(state)
    
    # 验证指针模式
    doc_meta = result['document_metadata'][0]
    
    # 摘要应该被截断到500字符
    assert len(doc_meta['summary']) <= 500
    
    # 应该有切块ID列表
    assert 'chunk_ids' in doc_meta
    assert isinstance(doc_meta['chunk_ids'], list)
    
    # State中不应该有完整文本
    assert 'text' not in doc_meta or len(doc_meta.get('text', '')) <= 500


@pytest.mark.asyncio
async def test_租户隔离():
    """测试租户隔离"""
    tenant_id = "tenant_isolation_test"
    
    state = AuditState(
        documents=[
            MockFile("contract.txt", b"Contract content", "doc3")
        ],
        audit_type="legal_audit",
        user_id=1,
        tenant_id=tenant_id
    )
    
    result = await data_ingestion_pipeline(state)
    
    # 验证所有数据都带有tenant_id
    for doc_meta in result['document_metadata']:
        assert doc_meta['tenant_id'] == tenant_id


@pytest.mark.asyncio
async def test_错误处理():
    """测试错误处理:解析失败不应中断流程"""
    state = AuditState(
        documents=[
            MockFile("invalid.xyz", b"invalid content", "doc4")
        ],
        audit_type="audit",
        user_id=1,
        tenant_id="tenant_test_003"
    )
    
    # 应该不抛出异常
    result = await data_ingestion_pipeline(state)
    
    # 应该有错误记录
    assert len(result['document_metadata']) == 1
    doc_meta = result['document_metadata'][0]
    assert 'error' in doc_meta or doc_meta['doc_type'] == 'unknown'


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
