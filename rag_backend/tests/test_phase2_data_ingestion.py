"""
阶段2数据摄入管道测试
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


class MockFile:
    """模拟文件对象"""
    def __init__(self, filename: str, content: bytes, file_id: str):
        self.filename = filename
        self.file = content
        self.id = file_id


async def test_basic_ingestion():
    """测试基础数据摄入"""
    print("测试1: 基础数据摄入...")
    try:
        from app.multi_agent_system.pipeline import data_ingestion_pipeline
        from app.multi_agent_system.state import AuditState
        
        # 准备测试文档
        documents = [
            MockFile("test1.txt", b"Test financial report content", "doc1"),
            MockFile("test2.txt", b"Test contract content", "doc2")
        ]
        
        # 创建状态
        state = AuditState(
            documents=documents,
            audit_type="financial_audit",
            user_id=1,
            tenant_id="test_tenant_001"
        )
        
        # 执行数据摄入
        result = await data_ingestion_pipeline(state)
        
        # 验证结果
        assert 'document_metadata' in result
        assert 'chunk_ids' in result
        assert len(result['document_metadata']) == 2
        
        print(f"✅ 摄入完成: {len(result['document_metadata'])} 个文档, {len(result['chunk_ids'])} 个切块")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_pointer_mode():
    """测试指针模式"""
    print("\n测试2: 指针模式...")
    try:
        from app.multi_agent_system.pipeline import data_ingestion_pipeline
        from app.multi_agent_system.state import AuditState
        import json
        
        # 创建大文档
        large_content = "Large document content. " * 1000
        
        documents = [
            MockFile("large.txt", large_content.encode('utf-8'), "doc_large")
        ]
        
        state = AuditState(
            documents=documents,
            audit_type="audit",
            user_id=1,
            tenant_id="test_tenant_002"
        )
        
        # 执行摄入
        result = await data_ingestion_pipeline(state)
        
        # 计算State大小
        state_json = json.dumps({
            'document_metadata': result['document_metadata'],
            'chunk_ids': result['chunk_ids']
        }, ensure_ascii=False)
        
        state_size_kb = len(state_json.encode('utf-8')) / 1024
        original_size_kb = len(large_content.encode('utf-8')) / 1024
        
        print(f"✅ 指针模式验证:")
        print(f"   原始大小: {original_size_kb:.2f} KB")
        print(f"   State大小: {state_size_kb:.2f} KB")
        print(f"   压缩比: {original_size_kb / state_size_kb:.1f}x")
        print(f"   是否 < 10KB: {'是' if state_size_kb < 10 else '否'}")
        
        return state_size_kb < 10
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


async def test_document_retrieval():
    """测试文档检索工具"""
    print("\n测试3: 文档检索工具...")
    try:
        from app.multi_agent_system.pipeline import data_ingestion_pipeline
        from app.multi_agent_system.tools import DocumentChunkRetrievalTool
        from app.multi_agent_system.state import AuditState
        
        # 准备文档
        documents = [
            MockFile("retrieval_test.txt", b"Test document for retrieval functionality", "doc_ret")
        ]
        
        state = AuditState(
            documents=documents,
            audit_type="audit",
            user_id=1,
            tenant_id="test_tenant_003"
        )
        
        # 执行摄入
        result = await data_ingestion_pipeline(state)
        chunk_ids = result['chunk_ids']
        
        if chunk_ids:
            # 创建检索工具
            retrieval_tool = DocumentChunkRetrievalTool()
            
            # 按需读取切块
            retrieved = await retrieval_tool.read_document_chunks(
                chunk_ids=chunk_ids[:3],
                tenant_id="test_tenant_003",
                max_chunks=10
            )
            
            print(f"✅ 检索成功: {retrieved['total']} 个切块")
            return True
        else:
            print("❌ 没有切块可检索")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


async def test_tenant_isolation():
    """测试租户隔离"""
    print("\n测试4: 租户隔离...")
    try:
        from app.multi_agent_system.pipeline import data_ingestion_pipeline
        from app.multi_agent_system.state import AuditState
        
        # 租户A的文档
        state_a = AuditState(
            documents=[MockFile("tenant_a.txt", b"Tenant A data", "doc_a")],
            audit_type="audit",
            user_id=1,
            tenant_id="tenant_a"
        )
        result_a = await data_ingestion_pipeline(state_a)
        
        # 租户B的文档
        state_b = AuditState(
            documents=[MockFile("tenant_b.txt", b"Tenant B data", "doc_b")],
            audit_type="audit",
            user_id=2,
            tenant_id="tenant_b"
        )
        result_b = await data_ingestion_pipeline(state_b)
        
        # 验证隔离
        tenant_a_id = result_a['document_metadata'][0]['tenant_id']
        tenant_b_id = result_b['document_metadata'][0]['tenant_id']
        
        # 检查切块ID是否重复
        chunk_ids_a = set(result_a['chunk_ids'])
        chunk_ids_b = set(result_b['chunk_ids'])
        overlap = chunk_ids_a.intersection(chunk_ids_b)
        
        print(f"✅ 租户隔离验证:")
        print(f"   租户A ID: {tenant_a_id}")
        print(f"   租户B ID: {tenant_b_id}")
        print(f"   切块重复: {len(overlap)} 个")
        print(f"   隔离状态: {'正常' if len(overlap) == 0 else '异常'}")
        
        return len(overlap) == 0 and tenant_a_id != tenant_b_id
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("=" * 60)
    print("阶段2数据摄入管道测试")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(await test_basic_ingestion())
    results.append(await test_pointer_mode())
    results.append(await test_document_retrieval())
    results.append(await test_tenant_isolation())
    
    # 统计结果
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed}/{total} 通过")
    print("=" * 60)
    
    if passed == total:
        print("✅ 所有测试通过!")
        return 0
    else:
        print(f"❌ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)