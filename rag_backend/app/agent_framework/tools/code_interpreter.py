"""
Code Interpreter 工具

为 Agent 提供受限的 Python 执行沙箱，专为财税法务场景的数值计算设计。

关键安全机制（**多层防御**）：
1. AST 校验：在编译前拒绝危险节点（导入非白名单模块、访问 dunder 属性等）
2. 受限 builtins：__builtins__ 只暴露白名单内的安全函数
3. 白名单 imports：math/statistics/decimal/numpy/pandas/sympy 等数值库
4. 超时控制：通过 asyncio.wait_for + ThreadPoolExecutor 强制中断
5. 输出截断：stdout 上限 10KB，防止 prompt 爆炸

适用场景：
- 财务：折旧表、现金流贴现、比率分析
- 税务：分级税额、税收优惠测算、汇算清缴
- 法务：罚款计算、违约金、时效推算

不适用：网络/文件 I/O、动态 import、长任务
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import io
import logging
import time as _time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from .decorators import auto_register_tool

logger = logging.getLogger(__name__)


# =========================================================================
# 安全配置
# =========================================================================

# 允许 import 的顶级模块
ALLOWED_IMPORTS = {
    # 数值与精度
    "math", "statistics", "decimal", "fractions", "cmath",
    # 时间
    "datetime", "calendar", "time",
    # 数据
    "json", "re", "itertools", "collections", "functools", "operator",
    # 科学计算
    "numpy", "pandas", "sympy", "scipy",
}

# 禁止使用的标识符
FORBIDDEN_NAMES = {
    "__import__", "exec", "eval", "compile",
    "open", "input", "breakpoint",
    "globals", "locals", "vars", "dir", "help",
    "__builtins__",
}

# 禁止访问的属性（用于穿透沙箱的常见手段）
FORBIDDEN_ATTRS = {
    "__class__", "__bases__", "__mro__", "__subclasses__",
    "__globals__", "__code__", "__closure__", "__func__",
    "__getattribute__", "__setattr__", "__delattr__",
    "__dict__", "__init_subclass__",
}

# 暴露给沙箱的安全 builtins
_SAFE_BUILTIN_NAMES = {
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
    "chr", "complex", "dict", "divmod", "enumerate", "filter", "float",
    "format", "frozenset", "hash", "hex", "int", "isinstance", "issubclass",
    "iter", "len", "list", "map", "max", "min", "next", "oct", "ord",
    "pow", "print", "range", "repr", "reversed", "round", "set", "slice",
    "sorted", "str", "sum", "tuple", "zip", "id",
    # 异常类（让 try/except 可用）
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "ZeroDivisionError", "ArithmeticError", "OverflowError", "RuntimeError",
    "AttributeError", "StopIteration", "NotImplementedError",
    # 常量
    "True", "False", "None",
}

MAX_STDOUT_BYTES = 10_000
MAX_TIMEOUT_SECONDS = 30.0
DEFAULT_TIMEOUT_SECONDS = 10.0


# =========================================================================
# AST 校验器
# =========================================================================

class _SandboxValidator(ast.NodeVisitor):
    """AST 遍历器，识别危险节点。"""

    def __init__(self):
        self.errors: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top not in ALLOWED_IMPORTS:
                self.errors.append(f"禁止导入模块 '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            top = node.module.split(".")[0]
            if top not in ALLOWED_IMPORTS:
                self.errors.append(f"禁止从模块 '{node.module}' 导入")
        else:
            # `from . import x` 无 module，相对导入禁止
            self.errors.append("禁止相对导入")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_NAMES:
            self.errors.append(f"禁止使用名称 '{node.id}'")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.attr, str) and node.attr in FORBIDDEN_ATTRS:
            self.errors.append(f"禁止访问属性 '{node.attr}'")
        self.generic_visit(node)

    # with/async with 可能调用 __enter__ — 不直接禁，但属性校验会兜底
    # global/nonlocal 不构成穿透途径，允许


def validate_code(code: str) -> List[str]:
    """AST 校验：返回错误列表，空列表表示通过。"""
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        return [f"语法错误: {e.msg} (line {e.lineno})"]
    validator = _SandboxValidator()
    validator.visit(tree)
    return validator.errors


# =========================================================================
# 沙箱执行环境
# =========================================================================

def _restricted_import(name: str, globals=None, locals=None, fromlist=(), level=0):
    """白名单 import：runtime 兜底防护。

    AST 校验已经在静态阶段拦截非白名单 import，这里再加一道运行时检查，
    防止任何绕过 AST 的途径（理论上不应发生）。
    """
    top = name.split(".")[0]
    if top not in ALLOWED_IMPORTS:
        raise ImportError(f"模块 '{name}' 不在沙箱白名单中")
    import builtins as _b
    return _b.__import__(name, globals, locals, fromlist, level)


def _safe_builtins() -> Dict[str, Any]:
    """构造受限的 builtins 字典。

    包含两类：
    - SAFE_BUILTIN_NAMES：白名单内的安全函数
    - __import__：受限版本，强制走 ALLOWED_IMPORTS 白名单
    """
    import builtins as _b
    result = {"__import__": _restricted_import}
    for name in _SAFE_BUILTIN_NAMES:
        if hasattr(_b, name):
            result[name] = getattr(_b, name)
    return result


def _make_safe_globals() -> Dict[str, Any]:
    """构造沙箱全局命名空间：预导入白名单模块 + 受限 builtins。"""
    import math
    import statistics
    import decimal
    import fractions
    import datetime as _dt
    import calendar
    import time as _t
    import json
    import re
    import itertools
    import collections
    import functools
    import operator
    import numpy as np
    import pandas as pd
    import sympy

    return {
        "__builtins__": _safe_builtins(),
        "math": math,
        "statistics": statistics,
        "decimal": decimal,
        "fractions": fractions,
        "datetime": _dt,
        "calendar": calendar,
        "time": _t,
        "json": json,
        "re": re,
        "itertools": itertools,
        "collections": collections,
        "functools": functools,
        "operator": operator,
        "np": np,
        "numpy": np,
        "pd": pd,
        "pandas": pd,
        "sympy": sympy,
    }


_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="code_sandbox")


def _safe_serialize(value: Any) -> Any:
    """把 numpy/pandas/sympy 等对象转成可 JSON 序列化的形式。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_serialize(v) for k, v in value.items()}

    # numpy
    try:
        import numpy as np
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
    except ImportError:
        pass

    # pandas
    try:
        import pandas as pd
        if isinstance(value, pd.DataFrame):
            return value.head(50).to_dict(orient="records")
        if isinstance(value, pd.Series):
            return value.head(100).to_list()
    except ImportError:
        pass

    # sympy expression
    try:
        import sympy
        if isinstance(value, sympy.Basic):
            return str(value)
    except ImportError:
        pass

    return repr(value)


# =========================================================================
# 工具入口
# =========================================================================

@auto_register_tool(
    name="execute_python",
    description=(
        "在受限沙箱中执行 Python 代码，可用 math/statistics/decimal/numpy/pandas/"
        "sympy。返回 stdout 与最后一个表达式的值。适合精确的财务/税务/法务数值"
        "计算（折旧、税额、利息、贴现等），LLM 自身的算术不可信场景请优先调用此工具。"
    ),
    category="computation",
    tags=["math", "calculator", "finance", "tax", "legal"],
    timeout=35,
)
async def execute_python(code: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """在沙箱中执行 Python 代码。

    Args:
        code: 待执行的 Python 代码，支持多行
        timeout: 超时秒数，0.5-30 之间

    Returns:
        {
            "success": bool,            # 是否执行成功
            "stdout": str,              # 标准输出（截断至 10KB）
            "result": Any,              # 最后一个表达式的求值结果（可序列化）
            "error": str | None,        # 错误信息（success=False 时给出）
            "execution_time_ms": float, # 实际执行耗时（毫秒）
        }
    """
    timeout = max(0.5, min(MAX_TIMEOUT_SECONDS, float(timeout)))

    errors = validate_code(code)
    if errors:
        logger.info(f"[execute_python] 校验失败: {errors}")
        return {
            "success": False,
            "stdout": "",
            "result": None,
            "error": "代码安全校验失败：" + "; ".join(errors),
            "execution_time_ms": 0.0,
        }

    # 把最后一个表达式拆出来单独 eval，以便 result 字段非空
    tree = ast.parse(code, mode="exec")
    result_expr: ast.Expression | None = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        result_expr = ast.Expression(tree.body[-1].value)
        tree.body = tree.body[:-1]

    safe_globals = _make_safe_globals()
    stdout = io.StringIO()

    def _run() -> Any:
        with contextlib.redirect_stdout(stdout):
            if tree.body:
                exec(compile(tree, "<sandbox>", "exec"), safe_globals)
            if result_expr is not None:
                return eval(compile(result_expr, "<sandbox>", "eval"), safe_globals)
            return None

    start = _time.perf_counter()
    try:
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(_executor, _run)
        result = await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        elapsed_ms = timeout * 1000
        return {
            "success": False,
            "stdout": _truncate(stdout.getvalue()),
            "result": None,
            "error": f"代码执行超时（{timeout}s）",
            "execution_time_ms": elapsed_ms,
        }
    except Exception as e:
        elapsed_ms = (_time.perf_counter() - start) * 1000
        return {
            "success": False,
            "stdout": _truncate(stdout.getvalue()),
            "result": None,
            "error": f"{type(e).__name__}: {e}",
            "execution_time_ms": elapsed_ms,
        }

    elapsed_ms = (_time.perf_counter() - start) * 1000
    return {
        "success": True,
        "stdout": _truncate(stdout.getvalue()),
        "result": _safe_serialize(result),
        "error": None,
        "execution_time_ms": elapsed_ms,
    }


def _truncate(text: str) -> str:
    if len(text) <= MAX_STDOUT_BYTES:
        return text
    return text[:MAX_STDOUT_BYTES] + f"\n... [stdout 截断，原长 {len(text)} 字节]"
