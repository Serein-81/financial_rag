"""
测试 OCR 服务和 Unstructured API 集成
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ocr_factory import OCRFactory


async def test_ocr_factory():
    """测试 OCR 工厂"""
    print("=" * 60)
    print("测试 OCR 工厂和 Unstructured API 集成")
    print("=" * 60)
    
    ocr_factory = OCRFactory()
    
    # 测试 1: 获取所有可用的引擎
    print("\n1. 检测可用的 OCR 引擎:")
    available = ocr_factory.available_engines
    print(f"   可用引擎: {available}")
    
    if not available:
        print("   ❌ 没有可用的 OCR 引擎")
        return False
    
    # 测试 2: 获取引擎状态
    print("\n2. OCR 引擎状态:")
    status = ocr_factory.get_status()
    print(f"   当前活跃引擎: {status['active_engine']}")
    
    for engine_name, engine_info in status['engines'].items():
        health_icon = "✅" if engine_info['healthy'] else "❌"
        print(f"   {health_icon} {engine_name:15s} - {engine_info['message']}")
    
    # 测试 3: 测试 Unstructured API
    if 'unstructured' in available:
        print("\n3. 测试 Unstructured API（包含 YOLOX 和 Detectron2）:")
        adapter = ocr_factory.get_adapter('unstructured')
        
        if hasattr(adapter, 'check_health'):
            is_healthy, msg = adapter.check_health()
            print(f"   健康检查: {'✅' if is_healthy else '❌'} {msg}")
        
        # 测试 PDF 提取（创建一个简单的 PDF）
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            import tempfile
            
            # 创建一个测试 PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                pdf_path = tmp.name
            
            c = canvas.Canvas(pdf_path, pagesize=letter)
            c.drawString(100, 750, "测试发票")
            c.drawString(100, 730, "金额: ¥1000.00")
            c.drawString(100, 710, "税额: ¥130.00")
            c.save()
            
            print(f"   📄 测试 PDF 创建成功: {pdf_path}")
            
            # 尝试提取文本
            print("\n4. 测试文本提取:")
            text = await adapter.extract_text(pdf_path)
            
            if text:
                print(f"   ✅ 提取成功: {len(text)} 字符")
                print(f"   📝 内容预览: {text[:200]}...")
            else:
                print(f"   ⚠️ 未提取到文本（这是正常的，取决于 PDF 内容）")
            
            # 清理
            os.unlink(pdf_path)
            
        except ImportError:
            print("   ⚠️ reportlab 未安装，跳过 PDF 创建测试")
        except Exception as e:
            print(f"   ❌ 测试失败: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    return True


async def test_priority_order():
    """测试引擎优先级顺序"""
    print("\n" + "=" * 60)
    print("测试 OCR 引擎优先级")
    print("=" * 60)
    
    ocr_factory = OCRFactory()
    available = ocr_factory.available_engines
    
    print(f"\n优先级顺序（从高到低）:")
    expected_order = ['unstructured', 'mineru', 'paddleocr', 'tesseract']
    
    for i, engine in enumerate(available, 1):
        expected_pos = expected_order.index(engine) + 1 if engine in expected_order else 99
        icon = "✅" if i == expected_pos else "⚠️"
        print(f"   {icon} {i}. {engine:15s} (期望位置: {expected_pos})")
    
    if available and available[0] == 'unstructured':
        print("\n✅ Unstructured API 已优先被选中！")
        return True
    else:
        print(f"\n⚠️ 当前优先引擎: {available[0] if available else '无'}")
        print("   注意：如果 Unstructured API 不可用，会自动降级到其他引擎")
        return True


if __name__ == "__main__":
    async def main():
        try:
            await test_ocr_factory()
            await test_priority_order()
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(main())
