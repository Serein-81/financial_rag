"""
Pytest 配置文件
用于配置 pytest-asyncio 等测试插件
"""
import pytest
import os
import sys


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """设置测试环境变量"""
    # 设置UTF-8编码环境变量
    utf8_env_vars = {
        "PYTHONIOENCODING": "utf-8",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONUTF8": "1",
    }
    
    test_env_vars = {
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_password",
        "POSTGRES_SERVER": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "test_db",
        "SECRET_KEY": "test_secret_key_for_testing_only",
        **utf8_env_vars,  # 合并UTF-8环境变量
    }
    
    # 保存原始环境变量
    original_env = {}
    for key, value in test_env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    # 设置标准流的编码
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    
    yield
    
    # 恢复原始环境变量
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


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
