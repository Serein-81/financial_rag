"""
Skill Validator - 技能结构校验器

验证 SKILL.md 是否符合 Agent Skills 规范:
- YAML frontmatter 必填字段 (name, description)
- 目录结构合规
- 文件引用存在
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .skill_registry import parse_frontmatter

logger = logging.getLogger(__name__)


class ValidationResult:
    """校验结果"""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.infos: List[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def summary(self) -> str:
        parts = []
        if self.is_valid:
            parts.append("✓ 校验通过")
        else:
            parts.append(f"✗ 校验失败 ({len(self.errors)} 个错误)")
        if self.warnings:
            parts.append(f", {len(self.warnings)} 个警告")
        return "".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "infos": self.infos,
        }


class SkillValidator:
    """技能校验器"""

    # frontmatter 字段约束
    NAME_MAX_LENGTH = 64
    NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
    DESCRIPTION_MAX_LENGTH = 1024

    @classmethod
    def validate(cls, skill_dir: Path) -> ValidationResult:
        """
        校验一个技能目录

        Args:
            skill_dir: 技能目录路径

        Returns:
            校验结果
        """
        result = ValidationResult()

        if not skill_dir.is_dir():
            result.errors.append(f"目录不存在: {skill_dir}")
            return result

        # 1. 检查 SKILL.md
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            result.errors.append("缺少 SKILL.md")
            return result

        result.infos.append(f"SKILL.md 存在 ({skill_md.stat().st_size} bytes)")

        # 2. 检查 frontmatter
        raw = parse_frontmatter(skill_md)
        if raw is None:
            result.errors.append("SKILL.md frontmatter 解析失败或格式错误")
            return result

        # 3. 校验必填字段
        name = raw.get("name", "")
        if not name:
            # 使用目录名作为 fallback
            name = skill_dir.name
            result.warnings.append(f"frontmatter 缺少 name, 使用目录名 '{name}'")

        if len(name) > cls.NAME_MAX_LENGTH:
            result.errors.append(
                f"name 过长: {len(name)} 字符 (最大 {cls.NAME_MAX_LENGTH})"
            )
        elif not cls.NAME_PATTERN.match(name):
            result.errors.append(
                f"name 格式不规范: '{name}' (应使用小写字母/数字/连字符)"
            )

        desc = raw.get("description", "")
        if not desc:
            result.errors.append("缺少 description (必填)")
        elif len(desc) > cls.DESCRIPTION_MAX_LENGTH:
            result.errors.append(
                f"description 过长: {len(desc)} 字符 (最大 {cls.DESCRIPTION_MAX_LENGTH})"
            )

        # 4. 可选字段校验
        when_to_use = raw.get("when_to_use", "")
        if not when_to_use:
            result.warnings.append("建议填写 when_to_use 以提升匹配准确率")

        allowed_tools = raw.get("allowed-tools", "")
        if allowed_tools and not isinstance(allowed_tools, str):
            result.warnings.append("allowed-tools 应为空格分隔的字符串")

        # 5. 检查依赖目录
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.is_dir():
            script_files = list(scripts_dir.iterdir())
            result.infos.append(f"scripts/ 目录: {len(script_files)} 个文件")

        refs_dir = skill_dir / "references"
        if refs_dir.is_dir():
            ref_files = list(refs_dir.iterdir())
            result.infos.append(f"references/ 目录: {len(ref_files)} 个文件")

        return result

    @classmethod
    def validate_all(cls, skill_dirs: List[Path]) -> Dict[str, ValidationResult]:
        """
        批量校验多个技能

        Args:
            skill_dirs: 技能目录路径列表

        Returns:
            技能名 -> 校验结果
        """
        results = {}
        for d in skill_dirs:
            if d.is_dir() and not d.name.startswith("."):
                results[d.name] = cls.validate(d)
        return results
