"""
邀请码API测试

注意：此文件需要修复为pytest测试格式或使用mock
"""

import pytest


pytestmark = pytest.mark.skip(reason="需要修复: 这是脚本而非pytest测试，应使用mock或集成测试")


def test_invite_api_skipped():
    """邀请码API测试（跳过）"""
    pytest.skip("这是脚本而非pytest测试")
