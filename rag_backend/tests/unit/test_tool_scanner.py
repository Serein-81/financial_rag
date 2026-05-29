"""
测试工具扫描器
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from app.agent_framework.tools.scanner import ToolScanner, scan_tools
from app.agent_framework.tools.decorators import clear_auto_registered_tools


@pytest.fixture
def temp_tool_dir():
    """创建临时工具目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture(autouse=True)
def cleanup():
    """清理注册表"""
    clear_auto_registered_tools()
    yield
    clear_auto_registered_tools()


def create_tool_file(directory: Path, filename: str, content: str):
    """创建工具文件"""
    file_path = directory / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_scanner_initialization():
    """测试扫描器初始化"""
    scanner = ToolScanner()
    assert scanner.scan_dirs == ["app/tools", "app/skills"]

    custom_scanner = ToolScanner(scan_dirs=["custom/path"])
    assert custom_scanner.scan_dirs == ["custom/path"]


def test_scan_nonexistent_directory():
    """测试扫描不存在的目录"""
    scanner = ToolScanner(scan_dirs=["nonexistent/directory"])
    tools = scanner.scan()
    assert tools == []


def test_scan_empty_directory(temp_tool_dir):
    """测试扫描空目录"""
    scanner = ToolScanner(scan_dirs=[temp_tool_dir])
    tools = scanner.scan()
    assert tools == []


def test_scan_single_tool_file(temp_tool_dir):
    """测试扫描包含单个工具的文件"""
    # 创建工具文件
    tool_content = """
from app.agent_framework.tools.decorators import auto_register_tool

@auto_register_tool(name="test_tool", description="测试工具")
def test_function():
    return "test"
"""
    create_tool_file(Path(temp_tool_dir), "test_tool.py", tool_content)

    scanner = ToolScanner(scan_dirs=[temp_tool_dir])
    tools = scanner.scan()

    assert len(tools) == 1
    assert tools[0]["name"] == "test_tool"
    assert tools[0]["description"] == "测试工具"


def test_scan_multiple_tools_in_file(temp_tool_dir):
    """测试扫描包含多个工具的文件"""
    tool_content = """
from app.agent_framework.tools.decorators import auto_register_tool

@auto_register_tool(name="tool1")
def func1():
    pass

@auto_register_tool(name="tool2")
def func2():
    pass

@auto_register_tool(name="tool3")
def func3():
    pass
"""
    create_tool_file(Path(temp_tool_dir), "multi_tools.py", tool_content)

    scanner = ToolScanner(scan_dirs=[temp_tool_dir])
    tools = scanner.scan()

    assert len(tools) == 3
    tool_names = [t["name"] for t in tools]
    assert "tool1" in tool_names
    assert "tool2" in tool_names
    assert "tool3" in tool_names


def test_scan_nested_directories(temp_tool_dir):
    """测试扫描嵌套目录"""
    # 创建嵌套目录结构
    nested_dir = Path(temp_tool_dir) / "subdir"
    nested_dir.mkdir()

    # 在根目录创建工具
    create_tool_file(
        Path(temp_tool_dir),
        "root_tool.py",
        """
from app.agent_framework.tools.decorators import auto_register_tool

@auto_register_tool(name="root_tool")
def root_func():
    pass
"""
    )

    # 在子目录创建工具
    create_tool_file(
        nested_dir,
        "nested_tool.py",
        """
from app.agent_framework.tools.decorators import auto_register_tool

@auto_register_tool(name="nested_tool")
def nested_func():
    pass
"""
    )

    scanner = ToolScanner(scan_dirs=[temp_tool_dir])
    tools = scanner.scan()

    assert len(tools) == 2
    tool_names = [t["name"] for t in tools]
    assert "root_tool" in tool_names
    assert "nested_tool" in tool_names


def test_skip_private_files(temp_tool_dir):
    """测试跳过私有文件"""
    # 创建私有文件（应该被跳过）
    create_tool_file(
        Path(temp_tool_dir),
        "_private.py",
        """
from app.agent_framework.tools.decorators import auto_register_tool

@auto_register_tool(name="private_tool")
def private_func():
    pass
"""
    )

    # 创建普通文件
    create_tool_file(
        Path(temp_tool_dir),
        "public.py",
        """
from app.agent_framework.tools.decorators import auto_register_tool

@auto_register_tool(name="public_tool")
def public_func():
    pass
"""
    )

    scanner = ToolScanner(scan_dirs=[temp_tool_dir])
    tools = scanner.scan()

    # 只有 public_tool 应该被发现
    assert len(tools) == 1
    assert tools[0]["name"] == "public_tool"


def test_skip_test_files(temp_tool_dir):
    """测试跳过测试文件"""
    create_tool_file(
        Path(temp_tool_dir),
        "test_something.py",
        """
from app.agent_framework.tools.decorators import auto_register_tool

@auto_register_tool(name="test_tool")
def test_func():
    pass
"""
    )

    scanner = ToolScanner(scan_dirs=[temp_tool_dir])
    tools = scanner.scan()

    # 测试文件应该被跳过
    assert len(tools) == 0


def test_scan_tools_convenience_function(temp_tool_dir):
    """测试便捷函数 scan_tools"""
    create_tool_file(
        Path(temp_tool_dir),
        "convenience_tool.py",
        """
from app.agent_framework.tools.decorators import auto_register_tool

@auto_register_tool(name="convenience_tool")
def convenience_func():
    pass
"""
    )

    tools = scan_tools(directories=[temp_tool_dir])
    assert len(tools) == 1
    assert tools[0]["name"] == "convenience_tool"


def test_scan_file_with_syntax_error(temp_tool_dir):
    """测试扫描包含语法错误的文件"""
    # 创建有语法错误的文件
    create_tool_file(
        Path(temp_tool_dir),
        "invalid_syntax.py",
        "this is not valid python syntax @#$%"
    )

    # 创建正常文件
    create_tool_file(
        Path(temp_tool_dir),
        "valid.py",
        """
from app.agent_framework.tools.decorators import auto_register_tool

@auto_register_tool(name="valid_tool")
def valid_func():
    pass
"""
    )

    scanner = ToolScanner(scan_dirs=[temp_tool_dir])
    tools = scanner.scan()

    # 应该只发现有效的工具，跳过错误文件
    assert len(tools) == 1
    assert tools[0]["name"] == "valid_tool"


def test_scan_file_without_tools(temp_tool_dir):
    """测试扫描不包含工具的文件"""
    create_tool_file(
        Path(temp_tool_dir),
        "no_tools.py",
        """
# 这个文件没有任何工具
def regular_function():
    return "not a tool"

class RegularClass:
    pass
"""
    )

    scanner = ToolScanner(scan_dirs=[temp_tool_dir])
    tools = scanner.scan()

    assert len(tools) == 0


def test_scan_with_import_error(temp_tool_dir):
    """测试扫描导入失败的文件"""
    create_tool_file(
        Path(temp_tool_dir),
        "import_error.py",
        """
import nonexistent_module

from app.agent_framework.tools.decorators import auto_register_tool

@auto_register_tool(name="tool_with_import_error")
def func():
    pass
"""
    )

    scanner = ToolScanner(scan_dirs=[temp_tool_dir])
    tools = scanner.scan()

    # 导入失败的文件应该被跳过
    assert len(tools) == 0


def test_scan_single_file_method(temp_tool_dir):
    """测试 scan_single_file 方法"""
    file_path = create_tool_file(
        Path(temp_tool_dir),
        "single_file_tool.py",
        """
from app.agent_framework.tools.decorators import auto_register_tool

@auto_register_tool(name="single_file_tool")
def single_func():
    pass
"""
    )

    scanner = ToolScanner()
    tools = scanner.scan_single_file(str(file_path))

    assert len(tools) == 1
    assert tools[0]["name"] == "single_file_tool"


def test_scan_nonexistent_single_file():
    """测试扫描不存在的单个文件"""
    scanner = ToolScanner()
    tools = scanner.scan_single_file("nonexistent_file.py")
    assert tools == []


def test_scan_non_python_file(temp_tool_dir):
    """测试扫描非 Python 文件"""
    txt_file = Path(temp_tool_dir) / "not_python.txt"
    txt_file.write_text("This is a text file")

    scanner = ToolScanner()
    tools = scanner.scan_single_file(str(txt_file))
    assert tools == []
