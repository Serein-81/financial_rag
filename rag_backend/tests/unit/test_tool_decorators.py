"""
测试工具自动注册装饰器
"""

import pytest
from app.agent_framework.tools.decorators import (
    auto_register_tool,
    get_auto_registered_tools,
    clear_auto_registered_tools,
    get_tool_by_name
)


@pytest.fixture(autouse=True)
def cleanup():
    """每个测试前清空注册表"""
    clear_auto_registered_tools()
    yield
    clear_auto_registered_tools()


def test_basic_tool_registration():
    """测试基本的工具注册"""

    @auto_register_tool(
        name="test_tool",
        description="测试工具",
        category="test"
    )
    def test_func(param1: str, param2: int = 10):
        return f"{param1}-{param2}"

    # 验证工具已注册
    tools = get_auto_registered_tools()
    assert len(tools) == 1

    tool = tools[0]
    assert tool["name"] == "test_tool"
    assert tool["description"] == "测试工具"
    assert tool["category"] == "test"
    assert tool["enabled"] is True
    assert tool["is_async"] is False


def test_async_tool_registration():
    """测试异步工具注册"""

    @auto_register_tool(
        name="async_tool",
        description="异步测试工具"
    )
    async def async_func(param: str):
        return f"async-{param}"

    tools = get_auto_registered_tools()
    assert len(tools) == 1

    tool = tools[0]
    assert tool["name"] == "async_tool"
    assert tool["is_async"] is True


def test_parameter_extraction():
    """测试参数提取"""

    @auto_register_tool()
    def func_with_params(
        str_param: str,
        int_param: int,
        float_param: float,
        bool_param: bool,
        optional_param: str = "default"
    ):
        pass

    tool = get_auto_registered_tools()[0]
    params = tool["parameters"]

    # 验证参数类型
    assert params["str_param"]["type"] == "string"
    assert params["int_param"]["type"] == "integer"
    assert params["float_param"]["type"] == "number"
    assert params["bool_param"]["type"] == "boolean"

    # 验证必需参数
    assert params["str_param"]["required"] is True
    assert params["optional_param"]["required"] is False
    assert params["optional_param"]["default"] == "default"


def test_auto_name_from_function():
    """测试自动从函数名提取工具名"""

    @auto_register_tool()
    def my_custom_tool():
        pass

    tool = get_auto_registered_tools()[0]
    assert tool["name"] == "my_custom_tool"


def test_auto_description_from_docstring():
    """测试自动从 docstring 提取描述"""

    @auto_register_tool()
    def documented_tool():
        """这是工具的描述信息"""
        pass

    tool = get_auto_registered_tools()[0]
    assert tool["description"] == "这是工具的描述信息"


def test_multiple_tool_registration():
    """测试注册多个工具"""

    @auto_register_tool(name="tool1")
    def func1():
        pass

    @auto_register_tool(name="tool2")
    def func2():
        pass

    @auto_register_tool(name="tool3")
    def func3():
        pass

    tools = get_auto_registered_tools()
    assert len(tools) == 3

    tool_names = [t["name"] for t in tools]
    assert "tool1" in tool_names
    assert "tool2" in tool_names
    assert "tool3" in tool_names


def test_get_tool_by_name():
    """测试根据名称获取工具"""

    @auto_register_tool(name="search_tool")
    def search():
        pass

    tool = get_tool_by_name("search_tool")
    assert tool is not None
    assert tool["name"] == "search_tool"

    # 测试不存在的工具
    assert get_tool_by_name("nonexistent") is None


def test_disabled_tool():
    """测试禁用工具"""

    @auto_register_tool(name="disabled_tool", enabled=False)
    def disabled():
        pass

    tool = get_tool_by_name("disabled_tool")
    assert tool["enabled"] is False


def test_tool_tags():
    """测试工具标签"""

    @auto_register_tool(
        name="tagged_tool",
        tags=["财务", "计算", "税务"]
    )
    def tagged():
        pass

    tool = get_tool_by_name("tagged_tool")
    assert len(tool["tags"]) == 3
    assert "财务" in tool["tags"]
    assert "计算" in tool["tags"]


def test_tool_execution():
    """测试工具执行（确保装饰器不影响原函数）"""

    @auto_register_tool(name="calculator")
    def add(a: int, b: int) -> int:
        return a + b

    # 测试函数仍然可以正常调用
    result = add(5, 3)
    assert result == 8


@pytest.mark.asyncio
async def test_async_tool_execution():
    """测试异步工具执行"""

    @auto_register_tool(name="async_calculator")
    async def async_add(a: int, b: int) -> int:
        return a + b

    # 测试异步函数可以正常调用
    result = await async_add(10, 20)
    assert result == 30


def test_tool_metadata_attached():
    """测试元数据是否附加到函数上"""

    @auto_register_tool(name="meta_tool")
    def func():
        pass

    # 验证元数据附加到函数
    assert hasattr(func, "_auto_register_metadata")
    assert func._auto_register_metadata["name"] == "meta_tool"


def test_custom_timeout():
    """测试自定义超时"""

    @auto_register_tool(name="slow_tool", timeout=60)
    def slow_func():
        pass

    tool = get_tool_by_name("slow_tool")
    assert tool["timeout"] == 60
