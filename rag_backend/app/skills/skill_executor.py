"""
Skill Executor - 技能脚本执行器

执行 skills/<name>/scripts/ 目录下的可执行脚本。
脚本通过 subprocess 在隔离的进程中运行, 结果通过 stdout 返回。

设计原则:
- 脚本不注入 Agent 上下文, 只返回 stdout 结果
- "LLM 负责大脑编排, 脚本负责肢体执行"
- 脚本应自包含或明确声明依赖
- 超时机制防止脚本 hang
"""

import os
import sys
import json
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, List

from .skill_registry import SkillEntry

logger = logging.getLogger(__name__)


class SkillExecutionError(Exception):
    """技能脚本执行错误"""
    pass


class SkillScriptNotFoundError(Exception):
    """脚本文件未找到"""
    pass


class SkillExecutor:
    """
    技能脚本执行器

    支持:
    - 通过 subprocess 执行独立脚本
    - 统一的参数传递 (JSON 文件)
    - 超时和安全控制
    """

    DEFAULT_TIMEOUT = 60  # 默认超时 60 秒

    # =========================================================================
    # 主执行接口
    # =========================================================================

    @classmethod
    async def run_script(
        cls,
        skill_entry: SkillEntry,
        script_name: str = "",
        args: Optional[Dict[str, Any]] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> str:
        """
        运行技能脚本 (异步包装)

        Args:
            skill_entry: 技能条目
            script_name: 脚本文件名 (如 main.py), 为空时自动检测
            args: 参数字典, 通过 JSON 文件传给脚本
            timeout: 超时秒数

        Returns:
            脚本 stdout 输出

        Raises:
            SkillScriptNotFoundError: 脚本不存在
            SkillExecutionError: 执行失败
        """
        skill_dir = Path(skill_entry.skill_dir)
        scripts_dir = skill_dir / "scripts"

        if not scripts_dir.is_dir():
            raise SkillScriptNotFoundError(f"技能 {skill_entry.metadata.name} 没有 scripts/ 目录")

        # 自动检测脚本
        if not script_name:
            script_name = cls._auto_detect_script(scripts_dir)
            if not script_name:
                raise SkillScriptNotFoundError(
                    f"技能 {skill_entry.metadata.name} scripts/ 中无可用脚本"
                )

        script_path = scripts_dir / script_name
        if not script_path.exists():
            raise SkillScriptNotFoundError(
                f"脚本不存在: {script_path}"
            )

        args = args or {}

        # 根据脚本类型选择执行方式
        suffix = script_path.suffix.lower()
        handler = cls._get_handler(suffix)
        if handler is None:
            raise SkillExecutionError(f"不支持的脚本类型: {suffix}")

        try:
            result = await handler(script_path, args, timeout, skill_dir)
            return result
        except subprocess.TimeoutExpired:
            raise SkillExecutionError(f"脚本执行超时 ({timeout}s): {script_name}")
        except Exception as e:
            raise SkillExecutionError(f"脚本执行失败: {e}")

    # =========================================================================
    # 自动检测
    # =========================================================================

    @staticmethod
    def _auto_detect_script(scripts_dir: Path) -> Optional[str]:
        """自动检测可执行脚本, 优先级: main.py > run.py > index.py > *.py"""
        priority = ["main.py", "run.py", "index.py"]
        for name in priority:
            if (scripts_dir / name).exists():
                return name
        # 回退: 找第一个 .py 文件
        py_files = sorted(scripts_dir.glob("*.py"))
        return py_files[0].name if py_files else None

    # =========================================================================
    # 执行处理器
    # =========================================================================

    @classmethod
    def _get_handler(cls, suffix: str):
        handlers = {
            ".py": cls._run_python,
            ".sh": cls._run_shell,
            ".bat": cls._run_bat,
            ".ps1": cls._run_powershell,
            ".js": cls._run_node,
        }
        return handlers.get(suffix)

    @staticmethod
    async def _run_python(
        script_path: Path,
        args: Dict[str, Any],
        timeout: int,
        cwd: Path,
    ) -> str:
        """运行 Python 脚本"""
        # 参数通过临时 JSON 文件传递 (避免 shell 注入)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(args, f, ensure_ascii=False)
            param_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, str(script_path), "--params", param_file],
                capture_output=True,
                text=False,  # 使用 bytes 模式避免编码问题
                timeout=timeout,
                cwd=str(cwd),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )

            stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

            if result.returncode != 0:
                raise SkillExecutionError(
                    f"脚本退出码 {result.returncode}: {stderr[:500]}"
                )

            return stdout.strip()
        finally:
            try:
                os.unlink(param_file)
            except Exception:
                pass

    @staticmethod
    async def _run_shell(
        script_path: Path,
        args: Dict[str, Any],
        timeout: int,
        cwd: Path,
    ) -> str:
        """运行 Shell 脚本"""
        env_param = json.dumps(args, ensure_ascii=False)
        result = subprocess.run(
            ["bash", str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
            env={**os.environ, "SKILL_PARAMS": env_param},
        )
        if result.returncode != 0:
            raise SkillExecutionError(
                f"脚本退出码 {result.returncode}: {result.stderr.strip()[:500]}"
            )
        return result.stdout.strip()

    @staticmethod
    async def _run_bat(
        script_path: Path,
        args: Dict[str, Any],
        timeout: int,
        cwd: Path,
    ) -> str:
        """运行 Windows Batch 脚本"""
        env_param = json.dumps(args, ensure_ascii=False)
        result = subprocess.run(
            [str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
            shell=True,
            env={**os.environ, "SKILL_PARAMS": env_param},
        )
        if result.returncode != 0:
            raise SkillExecutionError(
                f"脚本退出码 {result.returncode}: {result.stderr.strip()[:500]}"
            )
        return result.stdout.strip()

    @staticmethod
    async def _run_powershell(
        script_path: Path,
        args: Dict[str, Any],
        timeout: int,
        cwd: Path,
    ) -> str:
        """运行 PowerShell 脚本"""
        env_param = json.dumps(args, ensure_ascii=False)
        result = subprocess.run(
            ["powershell", "-File", str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
            env={**os.environ, "SKILL_PARAMS": env_param},
        )
        if result.returncode != 0:
            raise SkillExecutionError(
                f"脚本退出码 {result.returncode}: {result.stderr.strip()[:500]}"
            )
        return result.stdout.strip()

    @staticmethod
    async def _run_node(
        script_path: Path,
        args: Dict[str, Any],
        timeout: int,
        cwd: Path,
    ) -> str:
        """运行 Node.js 脚本"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(args, f, ensure_ascii=False)
            param_file = f.name

        try:
            result = subprocess.run(
                ["node", str(script_path), "--params", param_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd),
            )
            if result.returncode != 0:
                raise SkillExecutionError(
                    f"脚本退出码 {result.returncode}: {result.stderr.strip()[:500]}"
                )
            return result.stdout.strip()
        finally:
            try:
                os.unlink(param_file)
            except Exception:
                pass

    # =========================================================================
    # 列出可用脚本
    # =========================================================================

    @classmethod
    def list_scripts(cls, skill_entry: SkillEntry) -> List[Dict[str, Any]]:
        """列出技能的所有可用脚本及其基本信息"""
        skill_dir = Path(skill_entry.skill_dir)
        scripts_dir = skill_dir / "scripts"
        if not scripts_dir.is_dir():
            return []

        scripts = []
        for f in sorted(scripts_dir.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            scripts.append({
                "name": f.name,
                "type": f.suffix.lower(),
                "size": f.stat().st_size,
            })
        return scripts
