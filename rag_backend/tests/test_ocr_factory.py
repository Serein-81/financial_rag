"""
OCR工厂测试
验证多引擎OCR适配器的集成
注意：此测试需要OCR服务（Tesseract/MinerU），CI环境会跳过
"""
import pytest
import asyncio
import os
import tempfile
from pathlib import Path


@pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="需要OCR服务，仅在本地环境运行"
)
@pytest.mark.asyncio
async def test_ocr_factory_initialization():
    """测试OCR工厂初始化"""
    print("=" * 60)
    print("测试OCR工厂初始化")
    print("=" * 60)
    
    from app.services.ocr_factory import ocr_factory
    
    status = ocr_factory.get_status()
    print(f"\nOCR状态:")
    print(f"  活跃引擎: {status['active_engine']}")
    print(f"  可用引擎: {ocr_factory.available_engines}")
    
    print(f"\n各引擎状态:")
    for name, info in status['engines'].items():
        status_icon = "✅" if info['healthy'] else "❌"
        print(f"  {status_icon} {name}: {info['message']}")
    
    return status


@pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="需要OCR服务，仅在本地环境运行"
)
@pytest.mark.asyncio
async def test_tesseract_adapter():
    """测试Tesseract适配器"""
    print("\n" + "=" * 60)
    print("测试Tesseract适配器")
    print("=" * 60)
    
    from app.services.ocr_adapters import TesseractAdapter
    
    adapter = TesseractAdapter()
    print(f"\n引擎名称: {adapter.engine_name}")
    print(f"优先级: {adapter.priority}")
    
    is_healthy, msg = adapter.check_health()
    print(f"健康状态: {'✅' if is_healthy else '❌'} {msg}")
    
    return is_healthy


@pytest.mark.asyncio
async def test_mineru_adapter():
    """测试MinerU适配器"""
    print("\n" + "=" * 60)
    print("测试MinerU适配器")
    print("=" * 60)
    
    try:
        from app.services.ocr_adapters import MinerUAdapter
        
        adapter = MinerUAdapter()
        print(f"\n引擎名称: {adapter.engine_name}")
        print(f"优先级: {adapter.priority}")
        print(f"后端类型: {adapter.backend_type}")
        
        is_healthy, msg = adapter.check_health()
        print(f"健康状态: {'✅' if is_healthy else '❌'} {msg}")
        
        return is_healthy
    except ImportError as e:
        print(f"⚠️ MinerU未安装: {e}")
        return False


@pytest.mark.asyncio
async def test_paddleocr_adapter():
    """测试PaddleOCR适配器"""
    print("\n" + "=" * 60)
    print("测试PaddleOCR适配器")
    print("=" * 60)
    
    try:
        from app.services.ocr_adapters import PaddleOCRAdapter
        
        adapter = PaddleOCRAdapter()
        print(f"\n引擎名称: {adapter.engine_name}")
        print(f"优先级: {adapter.priority}")
        print(f"算法: {adapter.algorithm}")
        
        is_healthy, msg = adapter.check_health()
        print(f"健康状态: {'✅' if is_healthy else '❌'} {msg}")
        
        return is_healthy
    except ImportError as e:
        print(f"⚠️ PaddleOCR未安装: {e}")
        return False


@pytest.mark.asyncio
async def test_image_ocr():
    """测试图片OCR功能"""
    print("\n" + "=" * 60)
    print("测试图片OCR")
    print("=" * 60)
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        from app.services.ocr_factory import ocr_factory
        import io
        
        print("\n1️⃣ 创建测试图片...")
        img = Image.new('RGB', (400, 100), color='white')
        draw = ImageDraw.Draw(img)
        
        test_text = "Hello RAG System 2024 - OCR Test"
        try:
            draw.text((10, 30), test_text, fill='black')
        except:
            pass
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        image_data = img_bytes.getvalue()
        
        print(f"2️⃣ 使用 {ocr_factory.active_engine} 进行OCR识别...")
        result = await ocr_factory.extract_text_from_image(image_data)
        
        print(f"\n原始文本: {test_text}")
        print(f"识别结果: {result.strip()}")
        
        if result.strip():
            print("✅ 图片OCR成功！")
            return True
        else:
            print("⚠️ OCR结果为空")
            return False
            
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


@pytest.mark.asyncio
async def test_factory_switch():
    """测试引擎切换"""
    print("\n" + "=" * 60)
    print("测试引擎切换")
    print("=" * 60)
    
    from app.services.ocr_factory import ocr_factory
    
    current = ocr_factory.active_engine
    print(f"\n当前引擎: {current}")
    
    available = ocr_factory.available_engines
    print(f"可用引擎: {available}")
    
    if len(available) > 1:
        for engine in available:
            if engine != current:
                print(f"\n尝试切换到 {engine}...")
                success = ocr_factory.set_preferred_engine(engine)
                if success:
                    print(f"✅ 切换成功，当前引擎: {ocr_factory.active_engine}")
                else:
                    print(f"❌ 切换失败")
        
        ocr_factory.set_preferred_engine(current)
        print(f"\n恢复原始引擎: {ocr_factory.active_engine}")
    else:
        print("\n只有一个可用引擎，跳过切换测试")


@pytest.mark.asyncio
async def test_pdf_extraction():
    """测试PDF提取（如果有测试PDF）"""
    print("\n" + "=" * 60)
    print("测试PDF文本提取")
    print("=" * 60)
    
    from app.services.ocr_factory import ocr_factory
    
    test_pdf_path = "/tmp/test_document.pdf"
    
    if os.path.exists(test_pdf_path):
        print(f"\n使用 {ocr_factory.active_engine} 提取PDF文本...")
        try:
            text = await ocr_factory.extract_text(test_pdf_path)
            print(f"提取到 {len(text)} 个字符")
            print(f"前200字符: {text[:200]}...")
            return True
        except Exception as e:
            print(f"❌ PDF提取失败: {e}")
            return False
    else:
        print(f"\n⚠️ 测试PDF不存在: {test_pdf_path}")
        print("跳过PDF提取测试")
        return False


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🚀 开始OCR工厂测试")
    print("=" * 60)
    
    results = {}
    
    results['factory_init'] = await test_ocr_factory_initialization()
    results['tesseract'] = await test_tesseract_adapter()
    results['mineru'] = await test_mineru_adapter()
    results['paddleocr'] = await test_paddleocr_adapter()
    results['image_ocr'] = await test_image_ocr()
    results['engine_switch'] = await test_factory_switch()
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for test_name, result in results.items():
        icon = "✅" if result else "❌"
        print(f"{icon} {test_name}: {'通过' if result else '失败'}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n通过: {passed}/{total}")
    
    if passed == total:
        print("🎉 所有测试通过！")
    else:
        print("⚠️ 部分测试失败，请检查日志")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
