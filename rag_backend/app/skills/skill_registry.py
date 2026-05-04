"""
Skill Registry - 中央技能注册表

职责:
1. 启动时扫描所有 skills/ 目录
2. 解析 SKILL.md 的 YAML frontmatter (Level 1: 仅元数据)
3. 维护技能索引 (名称/领域/embedding)
4. 提供技能查询接口

设计原则:
- 启动时不加载 SKILL.md 正文，仅提取 frontmatter (~100 tokens each)
- 正文由 SkillLoader 按需加载 (Level 2)
- Embedding 预计算，用于语义匹配
"""

import os
import re
import yaml
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =========================================================================
# 数据模型
# =========================================================================

class SkillMetadata(BaseModel):
    """技能元数据 — 从 SKILL.md frontmatter 提取, ~100 tokens"""
    name: str = Field(..., description="技能名称, 与目录名一致")
    description: str = Field(..., description="技能描述, 用于自动发现匹配")
    when_to_use: str = Field("", description="何时触发该技能的提示")
    domain: Optional[str] = Field(None, description="所属领域: finance/tax/legal/general")
    allowed_tools: List[str] = Field(default_factory=list, description="预授权工具列表")
    compatibility: str = Field("", description="环境依赖说明")
    custom: Dict[str, Any] = Field(default_factory=dict, alias="metadata", description="自定义元数据")
    embedding: Optional[List[float]] = Field(None, description="预计算语义向量")


class SkillEntry(BaseModel):
    """技能完整条目"""
    metadata: SkillMetadata
    skill_dir: str = Field(..., description="技能目录绝对路径")
    has_scripts: bool = Field(False, description="是否有 scripts/ 目录")
    has_references: bool = Field(False, description="是否有 references/ 目录")
    has_assets: bool = Field(False, description="是否有 assets/ 目录")


# =========================================================================
# YAML Frontmatter 解析
# =========================================================================

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def parse_frontmatter(file_path: Path) -> Optional[dict]:
    """
    只解析 SKILL.md 的 YAML frontmatter (--- 之间的部分),
    不加载正文, 保证 Level 1 的轻量。
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("无法读取 %s: %s", file_path, e)
        return None

    match = _FRONTMATTER_RE.match(content)
    if not match:
        logger.warning("%s 缺少 YAML frontmatter (---)", file_path)
        return None

    try:
        data = yaml.safe_load(match.group(1))
        if not isinstance(data, dict):
            logger.warning("%s frontmatter 解析结果为空", file_path)
            return None
        return data
    except yaml.YAMLError as e:
        logger.warning("%s frontmatter YAML 解析失败: %s", file_path, e)
        return None


# =========================================================================
# 技能扫描
# =========================================================================

def scan_skill_directory(skill_dir: Path) -> Optional[SkillEntry]:
    """
    扫描单个技能目录, 提取元数据。
    仅扫描目录名与 SKILL.md 中 name 一致 (或目录名作为 name)。
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        logger.debug("跳过 %s: 无 SKILL.md", skill_dir)
        return None

    raw = parse_frontmatter(skill_md)
    if raw is None:
        return None

    # 技能名: 优先用 frontmatter 中的 name, 否则用目录名
    name = raw.get("name", skill_dir.name)
    # 验证名称格式 (小写字母/数字/连字符)
    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", name) and len(name) > 0:
        logger.warning("技能名 '%s' 格式不规范, 使用目录名 '%s'", name, skill_dir.name)
        name = skill_dir.name

    metadata_raw = raw.get("metadata") or {}
    if isinstance(metadata_raw, dict):
        domain = metadata_raw.get("domain")
    else:
        domain = None

    metadata = SkillMetadata(
        name=name,
        description=raw.get("description", ""),
        when_to_use=raw.get("when_to_use", ""),
        domain=domain,
        allowed_tools=(raw.get("allowed-tools") or "").split(),
        compatibility=raw.get("compatibility", ""),
        custom=metadata_raw if isinstance(metadata_raw, dict) else {},
    )

    return SkillEntry(
        metadata=metadata,
        skill_dir=str(skill_dir),
        has_scripts=(skill_dir / "scripts").is_dir(),
        has_references=(skill_dir / "references").is_dir(),
        has_assets=(skill_dir / "assets").is_dir(),
    )


def discover_skills(scan_paths: List[Path]) -> Dict[str, SkillEntry]:
    """
    扫描所有 skills/ 目录, 发现技能。

    支持两种目录结构 (可混合):
    1. 域范围:  skills/{domain}/{skill_name}/SKILL.md  (推荐)
       domain 从父目录名推断, 支持 finance/tax/legal/public
    2. 扁平:    skills/{skill_name}/SKILL.md  (向后兼容)
       domain 从 frontmatter metadata.domain 读取

    每个技能目录下必须有 SKILL.md。
    """
    skills: Dict[str, SkillEntry] = {}

    # 合法的领域目录名
    DOMAIN_DIRS = {"finance", "tax", "legal", "public"}

    for base_path in scan_paths:
        if not base_path.exists():
            logger.debug("技能扫描路径不存在: %s", base_path)
            continue

        for child in sorted(base_path.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith(".") or child.name.startswith("_"):
                continue

            dir_name = child.name

            # 判断是否是领域目录 (skills/finance/ 等)
            if dir_name in DOMAIN_DIRS:
                # 域范围结构: skills/{domain}/{skill_name}/
                domain_from_dir = dir_name
                for sub in sorted(child.iterdir()):
                    if not sub.is_dir() or sub.name.startswith("."):
                        continue
                    entry = scan_skill_directory(sub)
                    if entry is not None:
                        # 用目录结构推断 domain, 覆盖 metadata 中的 domain
                        entry.metadata.domain = domain_from_dir
                        _register_skill(skills, entry)
            else:
                # 扁平结构: skills/{skill_name}/
                entry = scan_skill_directory(child)
                if entry is not None:
                    _register_skill(skills, entry)

    logger.info("技能扫描完成: 发现 %d 个技能", len(skills))
    return skills


def _register_skill(skills: Dict[str, SkillEntry], entry: SkillEntry):
    """注册一个技能到字典, 冲突时覆盖"""
    existing = skills.get(entry.metadata.name)
    if existing:
        logger.warning(
            "技能名 '%s' 冲突: %s <-> %s, 后者覆盖前者",
            entry.metadata.name, existing.skill_dir, entry.skill_dir,
        )
    skills[entry.metadata.name] = entry
    logger.debug(
        "发现技能: name=%s, domain=%s, scripts=%s, refs=%s",
        entry.metadata.name, entry.metadata.domain,
        entry.has_scripts, entry.has_references,
    )


# =========================================================================
# Embedding 辅助 (懒加载, 避免循环导入)
# =========================================================================

def _compute_embedding(text: str) -> Optional[List[float]]:
    """计算文本的语义向量, 失败时返回 None"""
    try:
        from app.services.embedding_service import EmbeddingService
        service = EmbeddingService()
        result = service.get_embedding(text)
        if isinstance(result, list) and result and isinstance(result[0], (int, float)):
            return result
        return None
    except Exception as e:
        logger.debug("Embedding 计算失败 (非关键): %s", e)
        return None


# =========================================================================
# 中央注册表
# =========================================================================

class SkillRegistry:
    """
    中央技能注册表 (单例模式)

    使用方式:
        await SkillRegistry.initialize([Path("skills/"), ...])

        # 查询
        skill = SkillRegistry.get_skill("financial-data-entry")
        all_skills = SkillRegistry.list_skills()
        matches = await SkillRegistry.match("录入财务数据")
    """

    _skills: Dict[str, SkillEntry] = {}
    _initialized: bool = False

    # ---- 初始化 ----

    @classmethod
    async def initialize(
        cls,
        scan_paths: Optional[List[Path]] = None,
        compute_embeddings: bool = True,
    ) -> int:
        """
        初始化注册表: 扫描目录 + 预计算 embedding

        Args:
            scan_paths: 要扫描的技能目录列表
            compute_embeddings: 是否预计算语义向量

        Returns:
            发现的技能数量
        """
        if cls._initialized:
            logger.info("SkillRegistry 已初始化, 跳过")
            return len(cls._skills)

        if scan_paths is None:
            # 默认搜索路径
            project_root = Path(__file__).resolve().parent.parent.parent  # rag_backend/
            scan_paths = [
                project_root / "skills",                    # 项目技能
                Path.home() / ".claude" / "skills",         # 用户技能 (可选)
            ]

        cls._skills = discover_skills(scan_paths)
        cls._initialized = True

        if compute_embeddings and cls._skills:
            await cls._compute_all_embeddings()

        logger.info("SkillRegistry 初始化完成: %d 个技能", len(cls._skills))
        return len(cls._skills)

    @classmethod
    async def _compute_all_embeddings(cls):
        """为所有技能描述预计算 embedding"""
        texts = []
        entries = []
        for name, entry in cls._skills.items():
            text = f"{entry.metadata.description} {entry.metadata.when_to_use}"
            texts.append(text)
            entries.append(entry)

        try:
            from app.services.embedding_service import EmbeddingService
            service = EmbeddingService()
            embeddings = await service.get_embeddings(texts)
            for i, entry in enumerate(entries):
                if embeddings and i < len(embeddings):
                    entry.metadata.embedding = embeddings[i]
            logger.debug("已为 %d 个技能计算 embedding", len(entries))
        except Exception as e:
            logger.warning("批量 embedding 计算失败 (非关键): %s", e)

    # ---- 查询 ----

    @classmethod
    def get_skill(cls, name: str) -> Optional[SkillEntry]:
        """按名称获取技能"""
        return cls._skills.get(name)

    @classmethod
    def list_skills(cls) -> List[SkillMetadata]:
        """列出所有技能元数据 (Level 1)"""
        return [entry.metadata for entry in cls._skills.values()]

    @classmethod
    def list_skills_by_domain(cls, domain: str) -> List[SkillEntry]:
        """按领域列出技能"""
        return [
            entry for entry in cls._skills.values()
            if entry.metadata.domain == domain
        ]

    @classmethod
    def list_domains(cls) -> List[str]:
        """列出所有领域"""
        domains = set()
        for entry in cls._skills.values():
            if entry.metadata.domain:
                domains.add(entry.metadata.domain)
        return sorted(domains)

    @classmethod
    def format_domain_skill_descriptions(cls, domain: str) -> str:
        """
        格式化指定领域的技能描述文本。

        这是 Level 1 的轻量注入, 仅包含技能名称和简短描述。
        完整技能正文在激活时才按需加载 (Level 2)。

        输出格式:
        ## Available Skills
        ### Finance
        - **financial-data-entry**: 引导用户录入财务数据, 含验证、分类、持久化
        - **financial-analysis**: 财务报表分析与比率计算

        返回空字符串 if no skills found for domain.
        """
        skills = cls.list_skills_by_domain(domain)

        # 也包含 public 领域的通用技能
        public_skills = cls.list_skills_by_domain("public")
        all_skills = skills + public_skills

        if not all_skills:
            return ""

        lines = [f"## {domain.title()} Skills"]
        for s in all_skills:
            desc = s.metadata.description
            if len(desc) > 150:
                desc = desc[:147] + "..."
            lines.append(f"- **{s.metadata.name}**: {desc}")

        return "\n".join(lines)

    @classmethod
    def get_all_entries(cls) -> Dict[str, SkillEntry]:
        """获取全部技能条目"""
        return dict(cls._skills)

    @classmethod
    def is_initialized(cls) -> bool:
        return cls._initialized

    # ---- 语义匹配 ----

    @classmethod
    async def match(
        cls,
        query: str,
        top_k: int = 5,
        domain: Optional[str] = None,
    ) -> List[SkillEntry]:
        """
        语义匹配: 用 query embedding 和技能 description embedding 做余弦相似度

        Args:
            query: 用户查询
            top_k: 返回前 k 个
            domain: 限定领域 (可选)

        Returns:
            按相似度降序排列的技能列表
        """
        candidates = list(cls._skills.values())
        if domain:
            candidates = [e for e in candidates if e.metadata.domain == domain]

        if not candidates:
            return []

        try:
            from app.services.embedding_service import EmbeddingService
            service = EmbeddingService()
            query_emb = await service.get_embedding(query)
            if not query_emb:
                return candidates[:top_k]

            import numpy as np
            q = np.array(query_emb, dtype=np.float32)

            scored = []
            for entry in candidates:
                e_emb = entry.metadata.embedding
                if e_emb is not None:
                    e = np.array(e_emb, dtype=np.float32)
                    sim = float(np.dot(q, e) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-10))
                else:
                    sim = 0.0
                scored.append((entry, sim))

            scored.sort(key=lambda x: x[1], reverse=True)
            return [entry for entry, _ in scored[:top_k]]

        except Exception as e:
            logger.warning("语义匹配失败, 回退到关键词匹配: %s", e)
            return cls._keyword_match(query, candidates, top_k)

    @classmethod
    def _keyword_match(
        cls,
        query: str,
        candidates: List[SkillEntry],
        top_k: int,
    ) -> List[SkillEntry]:
        """关键词回退匹配"""
        q_lower = query.lower()
        scored = []
        for entry in candidates:
            score = 0
            desc = entry.metadata.description.lower()
            when = entry.metadata.when_to_use.lower()
            score += desc.count(q_lower) * 2
            score += when.count(q_lower) * 3
            if entry.metadata.name in q_lower:
                score += 10
            scored.append((entry, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [entry for entry, _ in scored[:top_k]]

    # ---- 重置 ----

    @classmethod
    def reset(cls):
        """重置注册表 (用于测试)"""
        cls._skills = {}
        cls._initialized = False
