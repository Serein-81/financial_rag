"""
Skill Matcher - 意图-技能匹配器

多策略匹配栈:
1. 显式匹配: 用户输入 /skill-name 直接激活
2. 语义匹配: Embedding 余弦相似度 (主策略)
3. 关键词匹配: when_to_use 字段的关键词扫描 (回退)
4. 领域匹配: 结合 IntentRouter 的输出, 优先匹配同领域技能

使用方式:
    matcher = SkillMatcher()
    matches = await matcher.match(query="录入财务数据", domain="finance")
"""

import logging
from typing import List, Optional
from .skill_registry import SkillRegistry, SkillEntry

logger = logging.getLogger(__name__)


class SkillMatcher:
    """
    意图-技能匹配器

    与 IntentRouterAgent 协同工作:
    - IntentRouter 识别 domain (finance/tax/legal/general)
    - SkillMatcher 在该 domain 内做技能匹配
    """

    def __init__(self, registry: Optional[SkillRegistry] = None):
        self._registry = registry or SkillRegistry

    # =========================================================================
    # 主匹配入口
    # =========================================================================

    async def match(
        self,
        query: str,
        domain: Optional[str] = None,
        top_k: int = 3,
    ) -> List[SkillEntry]:
        """
        匹配技能: 多策略组合

        Args:
            query: 用户查询文本
            domain: 限定领域 (来自 IntentRouter)
            top_k: 返回数量

        Returns:
            按相关性降序的技能列表
        """
        # 策略 1: 显式 /skill-name 调用
        explicit = self._match_explicit(query)
        if explicit:
            return [explicit]

        # 策略 2: 语义匹配
        semantic = await self._registry.match(
            query=query,
            top_k=top_k,
            domain=domain,
        )
        return semantic

    # =========================================================================
    # 策略 1: 显式匹配
    # =========================================================================

    @staticmethod
    def _match_explicit(query: str) -> Optional[SkillEntry]:
        """
        检查用户是否通过 /skill-name 显式调用技能

        例如: "使用 financial-data-entry 录入数据" 或 "/financial-data-entry"
        """
        # 格式 1: 以 / 开头
        if query.startswith("/"):
            name = query[1:].split()[0].strip()
            return SkillRegistry.get_skill(name)

        # 格式 2: 包含 "使用 skill-name" 模式
        import re
        m = re.search(r"(?:使用|调用|启动|激活)\s+([a-z][a-z0-9-]*)", query)
        if m:
            return SkillRegistry.get_skill(m.group(1))

        return None

    # =========================================================================
    # 工具方法
    # =========================================================================

    @staticmethod
    def format_skill_catalog(
        skills: List[SkillEntry],
        include_domain: bool = True,
    ) -> str:
        """
        格式化技能目录文本, 供 Agent system prompt 使用

        Args:
            skills: 技能列表
            include_domain: 是否包含领域信息

        Returns:
            格式化的 markdown 文本
        """
        if not skills:
            return ""

        lines = ["## Available Skills"]
        if include_domain:
            # 按领域分组
            from collections import defaultdict
            by_domain = defaultdict(list)
            for s in skills:
                # 兼容 SkillEntry (有 skill_dir) 和 SkillMetadata 两种对象
                if hasattr(s, 'skill_dir'):
                    domain = s.metadata.domain or "general"
                else:
                    domain = s.domain or "general"
                by_domain[domain].append(s)

            for domain in sorted(by_domain.keys()):
                lines.append(f"\n### {domain.title()}")
                for s in by_domain[domain]:
                    if hasattr(s, 'skill_dir'):
                        name = s.metadata.name
                        desc = s.metadata.description
                    else:
                        name = s.name
                        desc = s.description
                    lines.append(f"- **{name}**: {desc}")
        else:
            for s in skills:
                if hasattr(s, 'skill_dir'):
                    name = s.metadata.name
                    desc = s.metadata.description
                else:
                    name = s.name
                    desc = s.description
                lines.append(f"- **{name}**: {desc}")

        return "\n".join(lines)
