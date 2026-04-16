"""
阶段2简单测试 - 验证核心功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


async def test_imports():
    """测试导入"""
    print("测试1: 导入模块...")
    try:
        from app.multi_agent_system.pipeline import data_ingestion_pipeline
        from app.multi_agent_system.tools import DocumentChunkRetrievalTool
        from app.parsers import ExcelParser
        print("✅ 所有模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_excel_parser():
    """测试Excel解析器"""
    print("\n测试2: Excel解析器...")
    try:
        from app.parsers import ExcelParser
        parser = ExcelParser()
        print(f"✅ Excel解析器创建成功")
        print(f"   支持的MIME类型: {parser.get_supported_mime_types()}")
        return True
    except Exception as e:
        print(f"❌ Excel解析器测试失败: {e}")
        return False


async def test_document_retrieval_tool():
    """测试文档检索工具"""
    print("\n测试3: 文档检索工具...")
    try:
        from app.multi_agent_system.tools import DocumentChunkRetrievalTool
        tool = DocumentChunkRetrievalTool()
        print("✅ 文档检索工具创建成功")
        return True
    except Exception as e:
        print(f"❌ 文档检索工具测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_ocr_classification():
    """测试OCR文档分类"""
    print("\n测试4: OCR文档分类...")
    try:
        from app.services.ocr_service import OCRService
        ocr = OCRService()
        
        # 测试分类
        invoice_text = "增值税专用发票 税号:123456"
        contract_text = "合同 甲方 乙方"
        
        invoice_type = ocr._classify_ocr_document(invoice_text)
        contract_type = ocr._classify_ocr_document(contract_text)
        
        print(f"✅ OCR分类功能正常")
        print(f"   发票识别: {invoice_type}")
        print(f"   合同识别: {contract_type}")
        
        assert invoice_type == 'invoice', f"发票识别错误: {invoice_type}"
        assert contract_type == 'contract', f"合同识别错误: {contract_type}"
        
        return True
    except Exception as e:
        print(f"❌ OCR分类测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("=" * 60)
    print("阶段2核心功能测试")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(await test_imports())
    results.append(await test_excel_parser())
    results.append(await test_document_retrieval_tool())
    results.append(await test_ocr_classification())
    
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
