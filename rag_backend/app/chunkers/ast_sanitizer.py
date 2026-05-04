"""
AST 净化器 (AST Sanitizer)

防御性编程：不相信上游 Parser 输出的标题层级定义。

主要工作：
1. 强制拉平非法层级跳跃（H1→H3 → 自动插入 H2 隐式父节点）
2. 超长标题降级（>50 字符的"标题"强制降级为正文段落）
3. 空标题过滤
"""

import logging
from typing import List
from app.models.structured_document import DocumentSection

logger = logging.getLogger(__name__)


class ASTSanitizer:
    """
    AST 净化器：在 MetadataInjector 的 ContextStack 处理之前，
    对所有 DocumentSection 的标题层级进行"降噪清洗"。
    """

    MAX_HEADING_CHARS = 50     # 超过此长度的标题视为伪标题
    MAX_HEADING_WORDS = 15     # 超过此词数的标题视为伪标题

    def sanitize_sections(
        self,
        sections: List[DocumentSection],
    ) -> List[DocumentSection]:
        """
        清洗并修复一层 sections，递归处理 subsections。

        处理流程：
        1. 过滤超长标题（降级为正文）
        2. 过滤空标题
        3. 修复非法层级跳跃
        4. 递归处理子章节
        """
        if not sections:
            return []

        # 1. 过滤超长标题和空标题
        sanitized = []
        for sec in sections:
            if not sec.heading or not sec.heading.strip():
                logger.debug(f"[ASTSanitizer] 空标题，跳过")
                continue
            if len(sec.heading) > self.MAX_HEADING_CHARS:
                logger.warning(
                    f"[ASTSanitizer] 超长标题({len(sec.heading)}字符)降级为正文: "
                    f"'{sec.heading[:30]}...'"
                )
                continue
            word_count = len(sec.heading.split())
            if word_count > self.MAX_HEADING_WORDS:
                logger.warning(
                    f"[ASTSanitizer] 超长标题({word_count}词)降级为正文: "
                    f"'{sec.heading[:30]}...'"
                )
                continue
            sanitized.append(sec)

        # 2. 修复层级跳跃
        repaired = self._repair_level_jumps(sanitized)

        # 3. 递归处理子章节
        for sec in repaired:
            sec.subsections = self.sanitize_sections(sec.subsections)

        return repaired

    def _repair_level_jumps(
        self,
        sections: List[DocumentSection],
    ) -> List[DocumentSection]:
        """
        修复非法层级跳跃。

        例如: H1 → H3 (缺少 H2)
        修复为: H1 → H2(隐式创建) → H3

        当检测到 level 跳跃超过 1 时，自动插入隐式父节点
        来补全层级链条。
        """
        if len(sections) <= 1:
            return sections

        repaired = []
        # 用第一个 section 的 level 做基准
        current_base_level = sections[0].level

        for sec in sections:
            diff = sec.level - current_base_level

            if diff > 1:
                # 越级跳跃：插入隐式父节点
                logger.info(
                    f"[ASTSanitizer] 修复层级跳跃: "
                    f"level {sec.level} (基准 {current_base_level}), "
                    f"创建隐式父节点"
                )
                implicit = DocumentSection(
                    heading=f"[{sec.heading} 上下文]",
                    level=current_base_level + 1,
                    subsections=[sec],
                )
                repaired.append(implicit)
                # 更新基准层级（但不改变 current_base_level 的追踪）
                current_base_level = sec.level
            else:
                repaired.append(sec)
                if sec.level > current_base_level:
                    current_base_level = sec.level

        return repaired
