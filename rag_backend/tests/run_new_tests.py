#!/usr/bin/env python
"""
新测试文件快速运行脚本
运行所有新编写的综合测试文件
"""

import sys
import subprocess
from pathlib import Path


def run_command(cmd, description):
    """运行命令并打印结果"""
    print(f"\n{'=' * 80}")
    print(f"运行: {description}")
    print(f"命令: {cmd}")
    print('=' * 80)
    
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=Path(__file__).parent.parent
    )
    
    return result.returncode == 0


def main():
    """主函数"""
    print("开始运行新测试文件...")
    
    test_files = [
        ("test_multi_agent_core_comprehensive.py", "多智能体系统核心测试"),
        ("test_a2a_protocol_comprehensive.py", "A2A协议通信测试"),
        ("test_mcp_protocol_comprehensive.py", "MCP协议工具测试"),
        ("test_workflow_monitoring_comprehensive.py", "工作流监控测试"),
        ("test_api_endpoints_integration.py", "API端点集成测试"),
        ("test_memory_system_comprehensive.py", "记忆系统测试")
    ]
    
    results = {}
    
    for test_file, description in test_files:
        cmd = f"pytest tests/{test_file} -v --tb=short"
        success = run_command(cmd, description)
        results[description] = "✓ 通过" if success else "✗ 失败"
    
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    
    for description, result in results.items():
        print(f"{description}: {result}")
    
    passed = sum(1 for r in results.values() if "通过" in r)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 通过")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
