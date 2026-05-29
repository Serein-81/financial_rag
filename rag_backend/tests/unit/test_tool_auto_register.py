"""
测试工具自动注册服务
"""

import pytest
from unittest.mock import Mock, MagicMock
from app.services.tool_auto_register import ToolAutoRegister
from app.agent_framework.tools.tool_manager import ToolManager
from app.agent_framework.tools.decorators import (
    auto_register_tool,
    clear_auto_registered_tools
)


@pytest.fixture(autouse=True)
def cleanup():
    """清理注册表"""
    clear_auto_registered_tools()
    yield
    clear_auto_registered_tools()


@pytest.fixture
def mock_tool_manager():
    """创建模拟的工具管理器"""
    manager = Mock(spec=ToolManager)
    manager.tools = {}
    manager.register_function = Mock()
    manager.register_langchain_tool = Mock()
    return manager


@pytest.fixture
def auto_register_service(mock_tool_manager):
    """创建自动注册服务实例"""
    return ToolAutoRegister(
        tool_manager=mock_tool_manager,
        scan_dirs=[]  # 不扫描实际目录
    )


def test_service_initialization(mock_tool_manager):
    """测试服务初始化"""
    service = ToolAutoRegister(mock_tool_manager)

    assert service.tool_manager == mock_tool_manager
    assert service.scanner is not None
    assert service.registered_tools == {}
    assert service.registration_errors == []


def test_register_all_with_decorated_tools(auto_register_service):
    """测试注册装饰器工具"""

    # 创建测试工具
    @auto_register_tool(name="test_tool1", description="测试工具1")
    def tool1():
        return "tool1"

    @auto_register_tool(name="test_tool2", description="测试工具2")
    async def tool2():
        return "tool2"

    # 注册所有工具
    result = auto_register_service.register_all()

    # 验证结果
    assert result["total_discovered"] == 2
    assert result["registered"] == 2
    assert result["skipped"] == 0
    assert result["errors"] == 0

    # 验证工具已注册
    assert "test_tool1" in auto_register_service.registered_tools
    assert "test_tool2" in auto_register_service.registered_tools


def test_register_all_skips_disabled_tools(auto_register_service):
    """测试跳过禁用的工具"""

    @auto_register_tool(name="enabled_tool", enabled=True)
    def enabled():
        pass

    @auto_register_tool(name="disabled_tool", enabled=False)
    def disabled():
        pass

    result = auto_register_service.register_all()

    assert result["registered"] == 1
    assert result["skipped"] == 1
    assert "enabled_tool" in auto_register_service.registered_tools
    assert "disabled_tool" not in auto_register_service.registered_tools


def test_register_all_handles_errors(auto_register_service):
    """测试处理注册错误"""

    @auto_register_tool(name="valid_tool")
    def valid():
        pass

    # 模拟注册失败
    auto_register_service.tool_manager.register_function.side_effect = Exception("注册失败")

    result = auto_register_service.register_all()

    assert result["errors"] > 0
    assert len(auto_register_service.registration_errors) > 0


def test_get_statistics(auto_register_service):
    """测试获取统计信息"""

    @auto_register_tool(name="tool1", category="math", tags=["计算"])
    def tool1():
        pass

    @auto_register_tool(name="tool2", category="math", tags=["计算", "统计"])
    def tool2():
        pass

    @auto_register_tool(name="tool3", category="text", tags=["文本"])
    def tool3():
        pass

    auto_register_service.register_all()
    stats = auto_register_service.get_statistics()

    # 验证统计信息
    assert stats["total_registered"] == 3
    assert stats["by_category"]["math"] == 2
    assert stats["by_category"]["text"] == 1
    assert stats["by_tags"]["计算"] == 2
    assert stats["by_tags"]["统计"] == 1
    assert stats["by_tags"]["文本"] == 1


def test_get_tool_info(auto_register_service):
    """测试获取工具信息"""

    @auto_register_tool(
        name="info_tool",
        description="信息工具",
        category="test",
        tags=["测试"]
    )
    def info():
        pass

    auto_register_service.register_all()

    # 获取工具信息
    info = auto_register_service.get_tool_info("info_tool")

    assert info is not None
    assert info["name"] == "info_tool"
    assert info["description"] == "信息工具"
    assert info["category"] == "test"
    assert "测试" in info["tags"]

    # 不存在的工具
    assert auto_register_service.get_tool_info("nonexistent") is None


def test_unregister_tool(auto_register_service):
    """测试注销工具"""

    @auto_register_tool(name="removable_tool")
    def removable():
        pass

    auto_register_service.register_all()

    # 验证工具已注册
    assert "removable_tool" in auto_register_service.registered_tools

    # 注销工具
    result = auto_register_service.unregister_tool("removable_tool")

    assert result is True
    assert "removable_tool" not in auto_register_service.registered_tools

    # 注销不存在的工具
    result = auto_register_service.unregister_tool("nonexistent")
    assert result is False


def test_enable_tool(auto_register_service):
    """测试启用工具"""

    @auto_register_tool(name="toggleable_tool", enabled=False)
    def toggleable():
        pass

    auto_register_service.register_all()

    # 启用工具
    result = auto_register_service.enable_tool("toggleable_tool")

    assert result is True
    tool_meta = auto_register_service.registered_tools["toggleable_tool"]
    assert tool_meta["enabled"] is True

    # 启用不存在的工具
    result = auto_register_service.enable_tool("nonexistent")
    assert result is False


def test_disable_tool(auto_register_service):
    """测试禁用工具"""

    @auto_register_tool(name="disableable_tool", enabled=True)
    def disableable():
        pass

    auto_register_service.register_all()

    # 禁用工具
    result = auto_register_service.disable_tool("disableable_tool")

    assert result is True
    tool_meta = auto_register_service.registered_tools["disableable_tool"]
    assert tool_meta["enabled"] is False


def test_reload_tools(auto_register_service):
    """测试热重载工具"""

    @auto_register_tool(name="original_tool")
    def original():
        pass

    # 首次注册
    result1 = auto_register_service.register_all()
    assert result1["registered"] == 1

    # 添加新工具
    @auto_register_tool(name="new_tool")
    def new():
        pass

    # 热重载
    result2 = auto_register_service.reload_tools()

    assert result2["reloaded"] is True
    assert result2["previous_count"] == 1
    # 注意：实际扫描可能找不到新工具（因为是动态定义的）


def test_registration_with_async_tool(auto_register_service):
    """测试注册异步工具"""

    @auto_register_tool(name="async_test_tool")
    async def async_tool(param: str):
        return f"async-{param}"

    result = auto_register_service.register_all()

    assert result["registered"] == 1
    tool_meta = auto_register_service.registered_tools["async_test_tool"]
    assert tool_meta["is_async"] is True


def test_registration_with_sync_tool(auto_register_service):
    """测试注册同步工具"""

    @auto_register_tool(name="sync_test_tool")
    def sync_tool(param: str):
        return f"sync-{param}"

    result = auto_register_service.register_all()

    assert result["registered"] == 1
    tool_meta = auto_register_service.registered_tools["sync_test_tool"]
    assert tool_meta["is_async"] is False


def test_register_tools_with_same_name(auto_register_service):
    """测试注册同名工具（应该去重）"""

    @auto_register_tool(name="duplicate_tool")
    def tool1():
        return "tool1"

    @auto_register_tool(name="duplicate_tool")
    def tool2():
        return "tool2"

    result = auto_register_service.register_all()

    # 应该只注册一个（后者覆盖前者）
    assert result["total_discovered"] == 1
    assert result["registered"] == 1


def test_empty_registration(auto_register_service):
    """测试没有工具时的注册"""

    result = auto_register_service.register_all()

    assert result["total_discovered"] == 0
    assert result["registered"] == 0
    assert result["skipped"] == 0
    assert result["errors"] == 0
