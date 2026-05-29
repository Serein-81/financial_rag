"""
Unit tests for app/agent_framework/tools/code_interpreter.py

Covers:
- Correctness: arithmetic, math, statistics, decimal, numpy, pandas, sympy
- Safety: rejects forbidden imports, names, attribute access
- Runtime: timeout, exception inside code, stdout capture & truncation
- Serialization: numpy/pandas/sympy results round-trip cleanly
"""

from __future__ import annotations

import pytest

from app.agent_framework.tools.code_interpreter import (
    execute_python,
    validate_code,
    _safe_serialize,
    _make_safe_globals,
)


# =========================================================================
# Static validation
# =========================================================================

class TestValidation:
    def test_clean_arithmetic_passes(self):
        assert validate_code("x = 1 + 2\nprint(x)") == []

    def test_math_import_passes(self):
        assert validate_code("import math\nmath.sqrt(2)") == []

    def test_numpy_import_passes(self):
        assert validate_code("import numpy as np\nnp.array([1,2,3]).sum()") == []

    @pytest.mark.parametrize("module", ["os", "sys", "subprocess", "socket", "shutil"])
    def test_dangerous_imports_rejected(self, module):
        errors = validate_code(f"import {module}")
        assert errors and any("禁止" in e for e in errors)

    def test_from_import_dangerous_rejected(self):
        errors = validate_code("from os import path")
        assert errors

    def test_relative_import_rejected(self):
        errors = validate_code("from . import foo")
        assert errors

    @pytest.mark.parametrize("name", ["exec", "eval", "compile", "__import__", "open", "input"])
    def test_forbidden_names_rejected(self, name):
        errors = validate_code(f"x = {name}")
        assert errors and any("禁止" in e for e in errors)

    @pytest.mark.parametrize("attr", ["__class__", "__bases__", "__subclasses__", "__globals__"])
    def test_forbidden_attr_access_rejected(self, attr):
        errors = validate_code(f"x = (1).{attr}")
        assert errors and any("禁止" in e for e in errors)

    def test_syntax_error_reported(self):
        errors = validate_code("def foo(:\n")
        assert errors and "语法错误" in errors[0]


# =========================================================================
# Correctness: basic arithmetic
# =========================================================================

class TestArithmetic:
    @pytest.mark.asyncio
    async def test_simple_arithmetic_result(self):
        result = await execute_python("1 + 2 * 3")
        assert result["success"] is True
        assert result["result"] == 7
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_multi_statement(self):
        code = "a = 100\nb = 0.25\na * b"
        result = await execute_python(code)
        assert result["success"] is True
        assert result["result"] == 25.0

    @pytest.mark.asyncio
    async def test_stdout_captured(self):
        result = await execute_python("print('hello')\nprint(42)")
        assert result["success"] is True
        assert "hello" in result["stdout"]
        assert "42" in result["stdout"]

    @pytest.mark.asyncio
    async def test_zero_division_error(self):
        result = await execute_python("1 / 0")
        assert result["success"] is False
        assert "ZeroDivisionError" in result["error"]

    @pytest.mark.asyncio
    async def test_execution_time_reported(self):
        result = await execute_python("sum(range(100))")
        assert result["execution_time_ms"] >= 0


# =========================================================================
# Correctness: scientific libs
# =========================================================================

class TestScientificLibs:
    @pytest.mark.asyncio
    async def test_math_module(self):
        result = await execute_python("import math\nmath.sqrt(16)")
        assert result["success"] is True
        assert result["result"] == 4.0

    @pytest.mark.asyncio
    async def test_decimal_precise_arithmetic(self):
        code = (
            "from decimal import Decimal\n"
            "Decimal('0.1') + Decimal('0.2')"
        )
        result = await execute_python(code)
        assert result["success"] is True
        # Decimal 序列化为 repr
        assert "0.3" in str(result["result"])

    @pytest.mark.asyncio
    async def test_statistics_mean(self):
        code = "import statistics\nstatistics.mean([10, 20, 30, 40])"
        result = await execute_python(code)
        assert result["success"] is True
        assert result["result"] == 25

    @pytest.mark.asyncio
    async def test_numpy_array(self):
        code = "import numpy as np\nnp.array([1, 2, 3, 4, 5]).sum()"
        result = await execute_python(code)
        assert result["success"] is True
        assert result["result"] == 15

    @pytest.mark.asyncio
    async def test_numpy_via_pre_imported_alias(self):
        # np 已在 globals 中预导入，无需 import 语句
        result = await execute_python("np.mean([2.0, 4.0, 6.0])")
        assert result["success"] is True
        assert result["result"] == 4.0

    @pytest.mark.asyncio
    async def test_pandas_dataframe_serializes(self):
        code = (
            "import pandas as pd\n"
            "pd.DataFrame({'year': [2022, 2023], 'revenue': [100, 120]})"
        )
        result = await execute_python(code)
        assert result["success"] is True
        rows = result["result"]
        assert isinstance(rows, list)
        assert rows[0]["year"] == 2022
        assert rows[1]["revenue"] == 120

    @pytest.mark.asyncio
    async def test_sympy_symbolic(self):
        code = (
            "import sympy\n"
            "x = sympy.Symbol('x')\n"
            "sympy.expand((x + 1) ** 2)"
        )
        result = await execute_python(code)
        assert result["success"] is True
        assert "x**2" in str(result["result"]) and "2*x" in str(result["result"])


# =========================================================================
# Realistic finance/tax scenarios
# =========================================================================

class TestFinanceScenarios:
    @pytest.mark.asyncio
    async def test_corporate_income_tax_tier(self):
        """小型微利企业分级所得税额计算"""
        code = """
income = 3_000_000  # 应纳税所得额（元）
# 100万以下部分按 5% 计；100-300万按 10% 计
tier1 = min(income, 1_000_000) * 0.05
tier2 = max(0, min(income, 3_000_000) - 1_000_000) * 0.10
total = tier1 + tier2
print(f'第一档税额: {tier1}')
print(f'第二档税额: {tier2}')
total
"""
        result = await execute_python(code)
        assert result["success"] is True
        # 50000 + 200000 = 250000
        assert result["result"] == 250_000.0
        assert "250000" in result["stdout"] or "第一档" in result["stdout"]

    @pytest.mark.asyncio
    async def test_npv_calculation(self):
        """NPV 现值计算（贴现率 8%）"""
        code = """
import numpy as np
cash_flows = [-1000, 300, 400, 500, 200]
rate = 0.08
npv = sum(cf / (1 + rate) ** i for i, cf in enumerate(cash_flows))
round(npv, 2)
"""
        result = await execute_python(code)
        assert result["success"] is True
        # 独立计算：-1000 + 300/1.08 + 400/1.08² + 500/1.08³ + 200/1.08⁴ ≈ 164.64
        assert 160 < result["result"] < 170

    @pytest.mark.asyncio
    async def test_straight_line_depreciation(self):
        """直线法折旧表"""
        code = """
cost = 100_000
salvage = 10_000
years = 5
annual = (cost - salvage) / years
schedule = [(y, annual, cost - annual * y) for y in range(1, years + 1)]
schedule
"""
        result = await execute_python(code)
        assert result["success"] is True
        assert len(result["result"]) == 5
        assert result["result"][0] == [1, 18000.0, 82000.0]
        assert result["result"][4] == [5, 18000.0, 10000.0]


# =========================================================================
# Safety: confirm bypass attempts fail
# =========================================================================

class TestSafety:
    @pytest.mark.asyncio
    async def test_blocks_os_import(self):
        result = await execute_python("import os\nos.listdir('.')")
        assert result["success"] is False
        assert "安全校验" in result["error"]

    @pytest.mark.asyncio
    async def test_blocks_open(self):
        result = await execute_python("open('/etc/passwd').read()")
        assert result["success"] is False
        assert "安全校验" in result["error"]

    @pytest.mark.asyncio
    async def test_blocks_eval(self):
        result = await execute_python("eval('1+1')")
        assert result["success"] is False
        assert "安全校验" in result["error"]

    @pytest.mark.asyncio
    async def test_blocks_dunder_class_escape(self):
        # 经典逃逸：通过 __class__ → __bases__ → __subclasses__ 找到 os
        code = "(1).__class__.__bases__[0].__subclasses__()"
        result = await execute_python(code)
        assert result["success"] is False
        assert "安全校验" in result["error"]

    @pytest.mark.asyncio
    async def test_blocks_subprocess(self):
        result = await execute_python("import subprocess\nsubprocess.run(['ls'])")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_runtime_open_via_builtins_fails(self):
        # 没有 __builtins__ 暴露给沙箱，runtime 调用 open 也会报错
        # (即使 AST 校验绕过，runtime 也拒)
        result = await execute_python("globals()['open']('x')")
        assert result["success"] is False


# =========================================================================
# Runtime control: timeout, exceptions
# =========================================================================

class TestRuntime:
    @pytest.mark.asyncio
    async def test_timeout_kills_infinite_loop(self):
        code = "while True:\n    x = 1"
        result = await execute_python(code, timeout=0.6)
        assert result["success"] is False
        assert "超时" in result["error"]

    @pytest.mark.asyncio
    async def test_timeout_clamped(self):
        # timeout=999 应被 clamp 到 30，且不会真的等 999s
        # 用一个能秒回的简单代码确认 clamp 不影响正常路径
        result = await execute_python("1 + 1", timeout=999)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_runtime_exception_captured(self):
        result = await execute_python("[][0]")
        assert result["success"] is False
        assert "IndexError" in result["error"]

    @pytest.mark.asyncio
    async def test_stdout_truncated(self):
        code = "for _ in range(5000):\n    print('x' * 10)"
        result = await execute_python(code)
        assert result["success"] is True
        # 上限 10KB
        assert len(result["stdout"]) <= 10_200
        assert "截断" in result["stdout"]


# =========================================================================
# Serialization helpers
# =========================================================================

class TestSerializer:
    def test_serialize_primitives(self):
        assert _safe_serialize(None) is None
        assert _safe_serialize(42) == 42
        assert _safe_serialize("foo") == "foo"
        assert _safe_serialize(True) is True

    def test_serialize_nested_list(self):
        assert _safe_serialize([1, [2, 3], (4, 5)]) == [1, [2, 3], [4, 5]]

    def test_serialize_dict(self):
        assert _safe_serialize({"a": 1, "b": [2, 3]}) == {"a": 1, "b": [2, 3]}

    def test_serialize_numpy_ndarray(self):
        import numpy as np
        assert _safe_serialize(np.array([1, 2, 3])) == [1, 2, 3]

    def test_serialize_numpy_scalar(self):
        import numpy as np
        result = _safe_serialize(np.float64(3.14))
        assert isinstance(result, float)
        assert result == pytest.approx(3.14)

    def test_serialize_pandas_series(self):
        import pandas as pd
        result = _safe_serialize(pd.Series([10, 20, 30]))
        assert result == [10, 20, 30]


# =========================================================================
# Sanity: safe globals don't leak builtins
# =========================================================================

class TestSafeGlobals:
    def test_builtins_dict_is_restricted(self):
        g = _make_safe_globals()
        bi = g["__builtins__"]
        # safe
        assert "len" in bi
        assert "sum" in bi
        # forbidden
        assert "open" not in bi
        assert "eval" not in bi
        assert "exec" not in bi
        # __import__ is present, but it's the restricted version
        assert "__import__" in bi
        with pytest.raises(ImportError):
            bi["__import__"]("os")

    def test_whitelisted_modules_preimported(self):
        g = _make_safe_globals()
        for mod in ("math", "statistics", "decimal", "numpy", "pandas", "sympy", "np", "pd"):
            assert mod in g, f"missing {mod}"
