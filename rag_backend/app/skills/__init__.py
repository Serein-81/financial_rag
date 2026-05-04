"""
Skills System - Agent Skill Framework

遵循 Agent Skills 开放标准，提供三层次渐进式技能加载：
- Level 1 (元数据): 仅 name + description, ~100 tokens each
- Level 2 (正文): 完整 SKILL.md, ~5K tokens
- Level 3 (资源): references/ + scripts/ 按需加载

Skills 与 Tools 的区别：
- Tools: 基础操作/API调用，由 ToolManager 统一管理
- Skills: 复杂业务能力（数据录入、合规搜索等），由 SkillRegistry 管理
  Skills 可以编排多个 Tool 调用，也可以承载业务规则和流程指导
"""

from .skill_registry import SkillRegistry, SkillEntry, SkillMetadata
from .skill_loader import SkillLoader
from .skill_matcher import SkillMatcher
from .skill_executor import SkillExecutor
from .skill_validator import SkillValidator
from .skill_decorator import skill

__all__ = [
    "SkillRegistry",
    "SkillEntry",
    "SkillMetadata",
    "SkillLoader",
    "SkillMatcher",
    "SkillExecutor",
    "SkillValidator",
    "skill",
]
