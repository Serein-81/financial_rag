"""
Skill Loader - 三级渐进式技能加载器

遵循 Agent Skills 规范:
- Level 1 (元数据): name + description, ~100 tokens — SkillRegistry 负责
- Level 2 (正文): 完整 SKILL.md, <5K tokens 推荐 — load_full_body()
- Level 3 (资源): references/ + scripts/ + assets/, 按需 — load_reference()

设计原则:
- 永远不提前加载 Level 3 内容到 Agent 上下文
- 正文建议控制在 100~200 行, 详细知识放到 references/
- 脚本不加载到上下文, 而是通过 subprocess 执行并读取 stdout
"""

import logging
from pathlib import Path
from typing import Optional, List
from .skill_registry import SkillEntry

logger = logging.getLogger(__name__)


class SkillLoader:
    """三级渐进式技能加载器"""

    # =========================================================================
    # Level 1: 元数据 (由 SkillRegistry 完成)
    # =========================================================================
    # SkillRegistry.list_skills() 返回 SkillMetadata 列表, 每个约 100 tokens
    # Agent 的 system prompt 中只注入元数据, 用于技能发现

    # =========================================================================
    # Level 2: 正文
    # =========================================================================

    @staticmethod
    def load_full_body(skill_entry: SkillEntry) -> Optional[str]:
        """
        加载完整 SKILL.md 正文 (Level 2)

        只返回 --- 后面的 markdown 正文, 不包含 frontmatter。
        """
        skill_dir = Path(skill_entry.skill_dir)
        skill_md = skill_dir / "SKILL.md"

        if not skill_md.exists():
            logger.warning("SKILL.md 不存在: %s", skill_md)
            return None

        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("读取 SKILL.md 失败: %s", e)
            return None

        # 去掉 YAML frontmatter, 只保留正文
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body = parts[2].strip()
            else:
                body = content
        else:
            body = content

        logger.debug("加载技能正文: %s (%d chars)", skill_entry.metadata.name, len(body))
        return body

    @staticmethod
    def load_full_skill_md(skill_entry: SkillEntry) -> Optional[str]:
        """
        加载完整的 SKILL.md (包含 frontmatter + 正文)
        用于 API 展示场景
        """
        skill_dir = Path(skill_entry.skill_dir)
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None
        try:
            return skill_md.read_text(encoding="utf-8")
        except Exception:
            return None

    # =========================================================================
    # Level 3: 资源 (按需加载)
    # =========================================================================

    @staticmethod
    def load_reference(
        skill_entry: SkillEntry,
        ref_name: str,
    ) -> Optional[str]:
        """
        按需加载 references/ 下的引用文档 (Level 3)

        Args:
            skill_entry: 技能条目
            ref_name: 引用文件名 (如 "gaap_standards.md")

        Returns:
            文件内容, 或 None (如果文件不存在)
        """
        skill_dir = Path(skill_entry.skill_dir)
        ref_path = skill_dir / "references" / ref_name

        if not ref_path.exists():
            logger.warning("引用文件不存在: %s", ref_path)
            return None

        try:
            content = ref_path.read_text(encoding="utf-8")
            logger.debug("加载引用: %s (%d chars)", ref_name, len(content))
            return content
        except Exception as e:
            logger.warning("读取引用文件失败: %s: %s", ref_path, e)
            return None

    @staticmethod
    def list_references(skill_entry: SkillEntry) -> List[str]:
        """列出技能的所有引用文件"""
        skill_dir = Path(skill_entry.skill_dir)
        ref_dir = skill_dir / "references"
        if not ref_dir.is_dir():
            return []
        return sorted(
            f.name for f in ref_dir.iterdir() if f.is_file()
        )

    @staticmethod
    def list_scripts(skill_entry: SkillEntry) -> List[str]:
        """列出技能的所有脚本文件"""
        skill_dir = Path(skill_entry.skill_dir)
        scripts_dir = skill_dir / "scripts"
        if not scripts_dir.is_dir():
            return []
        return sorted(
            f.name for f in scripts_dir.iterdir() if f.is_file() and not f.name.startswith(".")
        )

    @staticmethod
    def load_asset(
        skill_entry: SkillEntry,
        asset_name: str,
        binary: bool = False,
    ) -> Optional[bytes]:
        """
        加载 assets/ 下的资源文件 (Level 3)

        Args:
            skill_entry: 技能条目
            asset_name: 资源文件名
            binary: 是否以二进制模式读取

        Returns:
            文件内容 (bytes)
        """
        skill_dir = Path(skill_entry.skill_dir)
        asset_path = skill_dir / "assets" / asset_name

        if not asset_path.exists():
            return None

        try:
            if binary:
                return asset_path.read_bytes()
            return asset_path.read_bytes()
        except Exception as e:
            logger.warning("读取资源文件失败: %s: %s", asset_path, e)
            return None
