"""
工具自动注册示例

演示如何使用 @auto_register_tool 装饰器创建自动注册的工具。
"""

from app.agent_framework.tools.decorators import auto_register_tool


@auto_register_tool(
    name="example_calculator",
    description="示例计算器工具，支持基本数学运算",
    category="math",
    tags=["计算", "数学", "示例"],
    enabled=True,
    timeout=10
)
async def example_calculator(
    operation: str,
    a: float,
    b: float
) -> float:
    """
    执行基本数学运算

    Args:
        operation: 操作类型，支持 'add', 'subtract', 'multiply', 'divide'
        a: 第一个数
        b: 第二个数

    Returns:
        运算结果
    """
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else "错误: 除数不能为0"
    }

    if operation not in operations:
        return f"错误: 不支持的操作 '{operation}'"

    result = operations[operation](a, b)
    return result


@auto_register_tool(
    name="example_text_processor",
    description="示例文本处理工具",
    category="text",
    tags=["文本", "处理", "示例"]
)
def example_text_processor(
    text: str,
    operation: str = "upper"
) -> str:
    """
    处理文本

    Args:
        text: 要处理的文本
        operation: 操作类型，支持 'upper', 'lower', 'title', 'reverse'

    Returns:
        处理后的文本
    """
    operations = {
        "upper": lambda t: t.upper(),
        "lower": lambda t: t.lower(),
        "title": lambda t: t.title(),
        "reverse": lambda t: t[::-1]
    }

    if operation not in operations:
        return f"错误: 不支持的操作 '{operation}'"

    return operations[operation](text)


@auto_register_tool(
    name="example_data_formatter",
    description="示例数据格式化工具",
    category="data",
    tags=["数据", "格式化", "示例"]
)
async def example_data_formatter(
    data: str,
    format_type: str = "json"
) -> str:
    """
    格式化数据

    Args:
        data: 要格式化的数据
        format_type: 格式类型，支持 'json', 'xml', 'csv'

    Returns:
        格式化后的数据
    """
    # 这是一个简化示例
    if format_type == "json":
        return f'{{"data": "{data}"}}'
    elif format_type == "xml":
        return f'<data>{data}</data>'
    elif format_type == "csv":
        return f'data\n{data}'
    else:
        return f"错误: 不支持的格式 '{format_type}'"


# 这个函数没有装饰器，不会被自动注册
def internal_helper_function():
    """这是一个内部辅助函数，不会被注册为工具"""
    pass
