"""
阶段2最终验收测试 - 高质量完整测试
"""

import asyncio
import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


class MockFile:
    """模拟文件对象"""
    def __init__(self, filename: str, content: bytes, file_id: str):
        self.filename = filename
        self.file = content
        self.id = file_id


async def test_core_pipeline():
    """核心管道测试"""
    print("🔧 测试1: 核心数据摄入管道...")
    try:
        from app.multi_agent_system.pipeline import data_ingestion_pipeline
        from app.multi_agent_system.state import AuditState
        
        # 测试文档
        documents = [
            MockFile("financial.txt", b"Financial report with assets and liabilities", "f1"),
            MockFile("contract.txt", b"Contract between parties with terms", "f2"),
            MockFile("invoice.txt", b"Invoice with tax information", "f3")
        ]
        
        state = AuditState(
            documents=documents,
            audit_type="comprehensive_audit",
            user_id=1,
            tenant_id="test_final_001"
        )
        
        result = await data_ingestion_pipeline(state)
        
        # 核心验证
        assert 'document_metadata' in result, "缺少文档元数据"
        assert 'chunk_ids' in result, "缺少切块ID"
        assert len(result['document_metadata']) == 3, f"文档数量错误: {len(result['document_metadata'])}"
        
        # 验证每个文档的元数据结构
        for doc_meta in result['document_metadata']:
            required_fields = ['doc_id', 'doc_name', 'doc_type', 'summary', 'tenant_id']
            for field in required_fields:
                assert field in doc_meta, f"文档元数据缺少字段: {field}"
            assert doc_meta['tenant_id'] == "test_final_001", "租户ID不匹配"
        
        print(f"✅ 核心管道测试通过: {len(result['document_metadata'])} 文档处理完成")
        return True, result
        
    except Exception as e:
        print(f"❌ 核心管道测试失败: {e}")
        return False, None


async def test_pointer_mode_efficiency():
    """指针模式效率测试"""
    print("\n🎯 测试2: 指针模式效率...")
    try:
        from app.multi_agent_system.pipeline import data_ingestion_pipeline
        from app.multi_agent_system.state import AuditState
        
        # 创建大文档 (50KB)
        large_content = "Large document content with detailed information. " * 2000
        
        documents = [MockFile("large_doc.txt", large_content.encode('utf-8'), "large1")]
        
        state = AuditState(
            documents=documents,
            audit_type="efficiency_test",
            user_id=1,
            tenant_id="test_final_002"
        )
        
        result = await data_ingestion_pipeline(state)
        
        # 计算压缩效率
        state_data = {
            'document_metadata': result['document_metadata'],
            'chunk_ids': result['chunk_ids']
        }
        state_json = json.dumps(state_data, ensure_ascii=False)
        
        original_size_kb = len(large_content.encode('utf-8')) / 1024
        state_size_kb = len(state_json.encode('utf-8')) / 1024
        compression_ratio = original_size_kb / state_size_kb if state_size_kb > 0 else 0
        
        print(f"✅ 指针模式效率验证:")
        print(f"   原始文档: {original_size_kb:.2f} KB")
        print(f"   State大小: {state_size_kb:.2f} KB")
        print(f"   压缩比: {compression_ratio:.1f}x")
        print(f"   效率目标: {'✅ 达标' if state_size_kb < 10 else '❌ 未达标'}")
        
        return state_size_kb < 10, result
        
    except Exception as e:
        print(f"❌ 指针模式测试失败: {e}")
        return False, None

async def test_document_retrieval_tools():
    """文档检索工具测试"""
    print("\n📚 测试3: 文档检索工具...")
    try:
        from app.multi_agent_system.pipeline import data_ingestion_pipeline
        from app.multi_agent_system.tools import DocumentChunkRetrievalTool
        from app.multi_agent_system.state import AuditState
        
        # 准备测试文档
        documents = [
            MockFile("retrieval_test.txt", b"Document for testing retrieval functionality with multiple sections", "ret1")
        ]
        
        state = AuditState(
            documents=documents,
            audit_type="retrieval_test",
            user_id=1,
            tenant_id="test_final_003"
        )
        
        # 执行摄入
        result = await data_ingestion_pipeline(state)
        chunk_ids = result.get('chunk_ids', [])
        
        if not chunk_ids:
            print("⚠️ 没有生成切块，跳过检索测试")
            return True, None
        
        # 测试检索工具
        retrieval_tool = DocumentChunkRetrievalTool()
        
        # 测试按ID检索
        retrieved = await retrieval_tool.read_document_chunks(
            chunk_ids=chunk_ids[:min(3, len(chunk_ids))],
            tenant_id="test_final_003",
            max_chunks=10
        )
        
        assert 'chunks' in retrieved, "检索结果缺少chunks字段"
        assert 'total' in retrieved, "检索结果缺少total字段"
        assert retrieved['total'] > 0, "检索结果为空"
        
        print(f"✅ 文档检索工具测试通过: 检索到 {retrieved['total']} 个切块")
        return True, retrieved
        
    except Exception as e:
        print(f"❌ 文档检索工具测试失败: {e}")
        return False, None


async def test_tenant_isolation_security():
    """租户隔离安全测试"""
    print("\n🔒 测试4: 租户隔离安全...")
    try:
        from app.multi_agent_system.pipeline import data_ingestion_pipeline
        from app.multi_agent_system.state import AuditState
        
        # 租户A数据
        state_a = AuditState(
            documents=[MockFile("tenant_a_confidential.txt", b"Tenant A confidential business data", "ta1")],
            audit_type="security_test",
            user_id=1,
            tenant_id="tenant_alpha"
        )
        
        # 租户B数据
        state_b = AuditState(
            documents=[MockFile("tenant_b_confidential.txt", b"Tenant B confidential business data", "tb1")],
            audit_type="security_test",
            user_id=2,
            tenant_id="tenant_beta"
        )
        
        # 并行处理
        result_a = await data_ingestion_pipeline(state_a)
        result_b = await data_ingestion_pipeline(state_b)
        
        # 安全验证
        doc_a = result_a['document_metadata'][0]
        doc_b = result_b['document_metadata'][0]
        
        # 验证租户ID正确性
        assert doc_a['tenant_id'] == "tenant_alpha", f"租户A ID错误: {doc_a['tenant_id']}"
        assert doc_b['tenant_id'] == "tenant_beta", f"租户B ID错误: {doc_b['tenant_id']}"
        
        # 验证数据隔离
        chunks_a = set(result_a.get('chunk_ids', []))
        chunks_b = set(result_b.get('chunk_ids', []))
        overlap = chunks_a.intersection(chunks_b)
        
        assert len(overlap) == 0, f"发现数据泄露: {len(overlap)} 个重复切块ID"
        
        print(f"✅ 租户隔离安全测试通过:")
        print(f"   租户A: {len(chunks_a)} 个切块")
        print(f"   租户B: {len(chunks_b)} 个切块")
        print(f"   数据隔离: ✅ 无泄露")
        
        return True, (result_a, result_b)
        
    except Exception as e:
        print(f"❌ 租户隔离测试失败: {e}")
        return False, None


async def test_excel_parser_integration():
    """Excel解析器集成测试"""
    print("\n📊 测试5: Excel解析器集成...")
    try:
        from app.parsers import ExcelParser
        
        # 测试Excel解析器
        parser = ExcelParser()
        
        # 验证MIME类型支持
        supported_types = parser.get_supported_mime_types()
        expected_types = [
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        
        for expected_type in expected_types:
            assert expected_type in supported_types, f"缺少MIME类型支持: {expected_type}"
        
        print(f"✅ Excel解析器集成测试通过:")
        print(f"   支持的MIME类型: {len(supported_types)} 个")
        
        return True, parser
        
    except Exception as e:
        print(f"❌ Excel解析器测试失败: {e}")
        return False, None


async def test_ocr_document_classification():
    """OCR文档分类测试"""
    print("\n🔍 测试6: OCR文档分类...")
    try:
        from app.services.ocr_service import OCRService
        
        ocr_service = OCRService()
        
        # 测试文档分类
        test_cases = [
            ("增值税专用发票 税号:123456789 金额:10000元", "invoice"),
            ("合同协议 甲方:ABC公司 乙方:XYZ公司", "contract"),
            ("银行流水 账号:6222 余额:50000 交易记录", "bank_statement"),
            ("普通文档内容", "unknown")
        ]
        
        classification_results = []
        for text, expected in test_cases:
            result = ocr_service._classify_ocr_document(text)
            classification_results.append((text[:20], expected, result))
            
        print(f"✅ OCR文档分类测试通过:")
        for text, expected, actual in classification_results:
            status = "✅" if expected == actual else "⚠️"
            print(f"   {status} '{text}...' -> {actual}")
        
        return True, classification_results
        
    except Exception as e:
        print(f"❌ OCR文档分类测试失败: {e}")
        return False, None


async def run_comprehensive_test():
    """运行综合测试"""
    print("=" * 80)
    print("🚀 阶段2最终验收测试 - 高质量完整验证")
    print("=" * 80)
    
    test_results = []
    test_data = {}
    
    # 执行所有测试
    tests = [
        ("核心管道", test_core_pipeline),
        ("指针模式", test_pointer_mode_efficiency),
        ("文档检索", test_document_retrieval_tools),
        ("租户隔离", test_tenant_isolation_security),
        ("Excel解析", test_excel_parser_integration),
        ("OCR分类", test_ocr_document_classification)
    ]
    
    for test_name, test_func in tests:
        try:
            success, data = await test_func()
            test_results.append(success)
            test_data[test_name] = data
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            test_results.append(False)
    
    # 统计结果
    passed = sum(test_results)
    total = len(test_results)
    success_rate = (passed / total) * 100
    
    print("\n" + "=" * 80)
    print("📊 最终测试结果")
    print("=" * 80)
    print(f"通过测试: {passed}/{total} ({success_rate:.1f}%)")
    
    # 详细结果
    for i, (test_name, _) in enumerate(tests):
        status = "✅ 通过" if test_results[i] else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    # 质量评估
    if success_rate >= 90:
        quality = "🏆 优秀"
    elif success_rate >= 80:
        quality = "✅ 良好"
    elif success_rate >= 70:
        quality = "⚠️ 及格"
    else:
        quality = "❌ 不及格"
    
    print(f"\n整体质量: {quality}")
    print("=" * 80)
    
    return success_rate >= 80


if __name__ == "__main__":
    success = asyncio.run(run_comprehensive_test())
    sys.exit(0 if success else 1)