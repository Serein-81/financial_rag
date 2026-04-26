"""
快速测试日志输出
用于验证增强的日志记录是否正常工作
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置日志级别
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def test_logging():
    """测试日志输出"""
    from app.api.v1.endpoints.tax_report import _extract_with_ocr
    
    print("=" * 60)
    print("测试增强的日志输出")
    print("=" * 60)
    
    # 创建一个模拟的 PDF 文件内容
    test_pdf_content = b'%PDF-1.4\nfake pdf content for testing'
    
    print("\n测试 OCR 处理（模拟 PDF 文件）...")
    print("-" * 60)
    
    result = await _extract_with_ocr(test_pdf_content)
    
    print("-" * 60)
    print(f"\n处理结果: {'成功' if result else '失败'}")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_logging())
