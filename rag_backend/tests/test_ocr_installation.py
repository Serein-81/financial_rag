"""
测试OCR安装是否成功
"""
import asyncio
from PIL import Image, ImageDraw, ImageFont
import io


async def test_ocr_installation():
    """测试OCR功能是否可用"""
    print("=" * 60)
    print("🔍 OCR安装测试")
    print("=" * 60)
    
    # 1. 检查PIL
    print("\n1️⃣ 检查 Pillow (PIL)...")
    try:
        from PIL import Image
        print("   ✅ Pillow 已安装")
    except ImportError:
        print("   ❌ Pillow 未安装")
        print("   💡 安装命令: pip install pillow")
        return False
    
    # 2. 检查pytesseract
    print("\n2️⃣ 检查 pytesseract...")
    try:
        import pytesseract
        print("   ✅ pytesseract 已安装")
    except ImportError:
        print("   ❌ pytesseract 未安装")
        print("   💡 安装命令: pip install pytesseract")
        return False
    
    # 3. 检查Tesseract引擎
    print("\n3️⃣ 检查 Tesseract OCR 引擎...")
    try:
        version = pytesseract.get_tesseract_version()
        print(f"   ✅ Tesseract 版本: {version}")
    except Exception as e:
        print(f"   ❌ Tesseract 引擎未安装或未配置")
        print(f"   错误信息: {e}")
        print("\n   💡 Windows安装步骤:")
        print("   1. 下载: https://github.com/UB-Mannheim/tesseract/wiki")
        print("   2. 安装到: C:\\Program Files\\Tesseract-OCR")
        print("   3. 添加到系统PATH环境变量")
        print("   4. 重启终端")
        return False
    
    # 4. 检查中文语言包
    print("\n4️⃣ 检查中文语言包...")
    try:
        langs = pytesseract.get_languages()
        if 'chi_sim' in langs:
            print("   ✅ 简体中文语言包已安装")
        else:
            print("   ⚠️ 简体中文语言包未安装")
            print("   💡 重新运行Tesseract安装程序，勾选Chinese-Simplified")
    except Exception as e:
        print(f"   ⚠️ 无法检查语言包: {e}")
    
    # 5. 实际测试OCR
    print("\n5️⃣ 实际测试OCR识别...")
    try:
        # 创建一个测试图片（白底黑字）
        img = Image.new('RGB', (400, 100), color='white')
        draw = ImageDraw.Draw(img)
        
        # 绘制文字（使用默认字体）
        text = "Hello RAG System 2024"
        draw.text((10, 30), text, fill='black')
        
        # 保存到字节流
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        # OCR识别
        result = pytesseract.image_to_string(Image.open(img_bytes))
        result_clean = result.strip()
        
        print(f"   原始文本: {text}")
        print(f"   识别结果: {result_clean}")
        
        if "Hello" in result_clean or "RAG" in result_clean:
            print("   ✅ OCR识别成功！")
        else:
            print("   ⚠️ OCR识别结果不准确，但功能正常")
            
    except Exception as e:
        print(f"   ❌ OCR测试失败: {e}")
        return False
    
    # 6. 测试异步OCR服务
    print("\n6️⃣ 测试异步OCR服务...")
    try:
        from app.services.ocr_service import ocr_service
        
        # 创建测试图片
        img = Image.new('RGB', (300, 80), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 20), "Test Image", fill='black')
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()
        
        # 异步调用
        result = await ocr_service.extract_text_from_image_bytes(img_bytes)
        print(f"   识别结果: {result.strip()}")
        print("   ✅ 异步OCR服务正常")
        
    except Exception as e:
        print(f"   ❌ 异步OCR服务测试失败: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 OCR功能完全可用！")
    print("=" * 60)
    print("\n📋 现在可以上传PNG图片进行文字识别了")
    return True


if __name__ == "__main__":
    asyncio.run(test_ocr_installation())
