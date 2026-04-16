"""
Pytest 配置文件
用于配置 pytest-asyncio 等测试插件
"""
import pytest


def pytest_configure(config):
    """配置 pytest 标记"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )


# 配置 pytest-asyncio
pytest_plugins = ['pytest_asyncio']
