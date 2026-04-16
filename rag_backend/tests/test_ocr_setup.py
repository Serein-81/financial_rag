#!/usr/bin/env python
"""
OCR 集成验证脚本
测试 MinerU、Tesseract 和工厂功能
"""
import sys
import os

def test_tesseract():
    """测试 Tesseract OCR"""
    print("=" * 60)
    print("测试 1: Tesseract OCR")
    print("=" * 60)
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        print(f"✅ Tesseract 版本: {version}")
        return True
    except Exception as e:
        print(f"❌ Tesseract 测试失败: {e}")
        return False

def test_mineru_cli():
    """测试 MinerU CLI"""
    print("\n" + "=" * 60)
    print("测试 2: MinerU CLI")
    print("=" * 60)
    try:
        import subprocess
        result = subprocess.run(
            ['mineru', '--help'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if 'mineru' in result.stdout.lower() or result.returncode == 0:
            print("✅ MinerU CLI 可用")
            return True
        else:
            print(f"⚠️ MinerU CLI 返回异常")
            print(f"   stdout: {result.stdout[:200]}")
            print(f"   stderr: {result.stderr[:200]}")
            return False
    except FileNotFoundError:
        print("❌ MinerU CLI 未找到")
        print("   💡 安装命令: pip install git+https://github.com/opendatalab/MinerU.git")
        return False
    except Exception as e:
        print(f"❌ MinerU CLI 测试失败: {e}")
        return False

def test_adapter_init():
    """测试 OCR 适配器初始化"""
    print("\n" + "=" * 60)
    print("测试 3: OCR 适配器初始化")
    print("=" * 60)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from app.services.ocr_adapters.tesseract_adapter import TesseractAdapter
        tesseract = TesseractAdapter()
        print(f"✅ TesseractAdapter 初始化成功")
        print(f"   引擎: {tesseract.engine_name}")
        print(f"   优先级: {tesseract.priority}")
        
        from app.services.ocr_adapters.mineru_adapter import MinerUAdapter
        mineru = MinerUAdapter()
        print(f"✅ MinerUAdapter 初始化成功")
        print(f"   引擎: {mineru.engine_name}")
        print(f"   优先级: {mineru.priority}")
        
        return True
    except Exception as e:
        print(f"❌ 适配器初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_factory():
    """测试 OCR 工厂"""
    print("\n" + "=" * 60)
    print("测试 4: OCR 工厂")
    print("=" * 60)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app.services.ocr_factory import ocr_factory
        
        status = ocr_factory.get_status()
        print(f"✅ OCR 工厂初始化成功")
        print(f"   活跃引擎: {status['active_engine']}")
        print(f"   可用引擎: {list(status['engines'].keys())}")
        
        print(f"\n   各引擎状态:")
        for name, info in status['engines'].items():
            icon = "✅" if info['healthy'] else "❌"
            print(f"   {icon} {name}: {info['message']}")
        
        return True
    except Exception as e:
        print(f"❌ OCR 工厂测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "=" * 60)
    print("🚀 OCR 集成验证")
    print("=" * 60)
    
    results = {
        "Tesseract OCR": test_tesseract(),
        "MinerU CLI": test_mineru_cli(),
        "适配器初始化": test_adapter_init(),
        "OCR 工厂": test_factory()
    }
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for test_name, result in results.items():
        icon = "✅" if result else "❌"
        print(f"{icon} {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！")
        print("\n💡 接下来可以运行:")
        print("   pytest tests/test_ocr_factory.py -v")
    else:
        print("⚠️  部分测试失败")
        print("\n🔧 解决方案:")
        if not results["Tesseract OCR"]:
            print("   1. 安装 Tesseract: pip install pytesseract")
            print("   2. Windows 用户还需要安装 Tesseract OCR 引擎")
        if not results["MinerU CLI"]:
            print("   3. 安装 MinerU: pip install git+https://github.com/opendatalab/MinerU.git")
    
    print("=" * 60)
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
