#!/bin/bash
# ==========================================
# Docker 容器内测试脚本
# ==========================================

set -e

echo "=========================================="
echo "  Docker 测试环境准备"
echo "=========================================="

# 激活虚拟环境
source /opt/venv/bin/activate

# 检查 pytest-asyncio
echo ""
echo "检查 pytest-asyncio 版本..."
pip show pytest-asyncio | grep Version

# 检查 pytest
echo ""
echo "检查 pytest 版本..."
pip show pytest | grep Version

# 检查 Python 版本
echo ""
echo "Python 版本:"
python --version

echo ""
echo "=========================================="
echo "  开始运行测试"
echo "=========================================="

# 运行所有测试
cd /app

# 运行核心模块测试（显示详细输出）
echo ""
echo "运行统一状态管理测试..."
pytest tests/test_unified_state.py -v --tb=short

echo ""
echo "运行混合编排系统测试..."
pytest tests/test_hybrid_orchestration.py -v --tb=short

echo ""
echo "运行异步任务处理测试..."
pytest tests/test_task_processing.py -v --tb=short

echo ""
echo "运行多租户安全测试..."
pytest tests/test_security.py -v --tb=short

echo ""
echo "=========================================="
echo "  测试完成！"
echo "=========================================="

# 显示测试覆盖率（如果安装了 pytest-cov）
echo ""
echo "检查测试覆盖率..."
pytest tests/ --cov=app --cov-report=term-missing --cov-report=html -q || true

echo ""
echo "测试脚本执行完毕！"
