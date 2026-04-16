#!/usr/bin/env python
"""
MinerU 安装验证脚本
运行此脚本验证 MinerU 是否正确安装
注意：此脚本需要 MinerU 库，仅在本地环境手动运行
"""
import sys
import os
import pytest

# 检查是否在 CI 环境
is_ci = os.getenv("CI") == "true"

def test_mineru_import():
    """测试 MinerU 是否可以导入"""
    print("=" * 60)
    print("测试 1: 导入 MinerU 包")
    print("=" * 60)
    try:
        import mineru
        print(f"✅ MinerU 导入成功！")
        print(f"   包路径: {mineru.__file__}")
        return True
    except ImportError as e:
        print(f"❌ MinerU 导入失败: {e}")
        return False

def test_backend_import():
    """测试 Backend 是否可以导入"""
    print("\n" + "=" * 60)
    print("测试 2: 导入 MinerU Backend")
    print("=" * 60)
    try:
        from mineru.backend.hybrid.hybrid_backend import HybridBackend
        print(f"✅ HybridBackend 导入成功！")
        return True
    except ImportError as e:
        print(f"❌ Backend 导入失败: {e}")
        return False

def test_adapter_init():
    """测试 OCR 适配器初始化"""
    print("\n" + "=" * 60)
    print("测试 3: 初始化 MinerUAdapter")
    print("=" * 60)
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app.services.ocr_adapters.mineru_adapter import MinerUAdapter
        
        adapter = MinerUAdapter()
        print(f"✅ MinerUAdapter 初始化成功！")
        print(f"   引擎名称: {adapter.engine_name}")
        print(f"   优先级: {adapter.priority}")
        print(f"   后端类型: {adapter.backend_type}")
        return True
    except Exception as e:
        print(f"❌ MinerUAdapter 初始化失败: {e}")
        return False

def test_health_check():
    """测试健康检查"""
    print("\n" + "=" * 60)
    print("测试 4: MinerU 健康检查")
    print("=" * 60)
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app.services.ocr_adapters.mineru_adapter import MinerUAdapter
        
        adapter = MinerUAdapter()
        healthy, message = adapter.check_health()
        
        if healthy:
            print(f"✅ MinerU 健康检查通过！")
            print(f"   状态信息: {message}")
        else:
            print(f"⚠️  MinerU 健康检查未通过")
            print(f"   状态信息: {message}")
        
        return healthy
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("\n🚀 MinerU 安装验证脚本")
    print("=" * 60)
    
    results = {
        "MinerU 包导入": test_mineru_import(),
        "Backend 导入": test_backend_import(),
        "适配器初始化": test_adapter_init(),
        "健康检查": test_health_check()
    }
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:20s}: {status}")
    
    all_passed = all(results.values())
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！MinerU 已正确安装和配置。")
        print("\n💡 接下来您可以：")
        print("   1. 运行完整的集成测试: pytest tests/test_ocr_factory.py")
        print("   2. 在您的应用中使用 OCRFactory")
    else:
        print("⚠️  部分测试失败，请检查上述错误信息。")
        print("\n🔧 常见问题解决方案：")
        print("   1. 如果 MinerU 未安装: pip install git+https://github.com/opendatalab/MinerU.git")
        print("   2. 如果 Backend 导入失败: 可能需要安装额外的依赖")
        print("   3. 如果健康检查失败: 查看 MinerU 的安装文档")
    
    print("=" * 60)
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
