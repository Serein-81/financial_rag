"""
元数据注入器 (Metadata Injector)

核心机制：AST 绑定的上下文栈 (ContextStack)

通过 DFS 遍历 DocumentSection 树，为每个 ChunkResult 注入正确的领域元数据。
使用栈结构确保兄弟节点之间零元数据泄漏：进入子节点时 Push，退出时 Pop。
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from app.chunkers.base_chunker import ChunkResult
from app.chunkers.ast_sanitizer import ASTSanitizer
from app.models.structured_document import StructuredDocument, DocumentSection

logger = logging.getLogger(__name__)


# ============================================================
# 上下文帧与上下文栈
# ============================================================

@dataclass
class ContextFrame:
    """一个标题层级的上下文快照"""
    level: int                       # H1=1, H2=2, H3=3
    heading_text: str                # 该层级的标题原文
    metadata: Dict[str, Any] = field(default_factory=dict)  # 在该层级提取到的元数据


class ContextStack:
    """
    上下文栈：绑定到 DocumentSection 树深度的栈结构。

    核心规则：
    - 进入一个 Section → 从父节点继承元数据 + 在当前 heading 中提取 → Push 新 Frame
    - 离开一个 Section → Pop 该层级 Frame，恢复父级元数据

    关键保证：兄弟节点之间零元数据泄漏。
    """

    # Heading 中提取元数据的规则集：(regex, key, optional_transform)
    HEADING_EXTRACTORS: List[Tuple[str, str, Any]] = [
        (r"(\d{4})\s*年", "year", None),
        (r"Q([1-4])", "quarter", lambda m: f"Q{m.group(1)}"),
        (r"第([一二三四])季度", "quarter", lambda m: f"Q{len(m.group(1).encode('utf-8')) - 2}"),
        (r"(利润表|资产负债表|现金流量表|所有者权益变动表)", "report_type", None),
        (r"([\u4e00-\u9fa5]{2,10}(?:公司|集团|有限))", "company", None),
        (r"(人民币|USD|CNY|美元|欧元|港币)", "currency", None),
    ]

    def __init__(self):
        self._stack: List[ContextFrame] = []

    def enter_section(self, level: int, heading: str) -> Dict[str, Any]:
        """
        进入一个新章节。

        返回该章节合并后的完整元数据（父级继承 + 当前提取）。
        """
        # 退栈：丢弃所有 level >= 当前 level 的帧
        while self._stack and self._stack[-1].level >= level:
            self._stack.pop()

        # 从父级继承元数据
        inherited: Dict[str, Any] = {}
        if self._stack:
            inherited = dict(self._stack[-1].metadata)

        # 在当前 heading 中提取新元数据
        extracted = self._extract_from_heading(heading)

        # 合并：extracted 覆盖 inherited 中的同名键
        merged = {**inherited, **extracted}

        # Push 新帧
        self._stack.append(ContextFrame(
            level=level,
            heading_text=heading,
            metadata=merged,
        ))

        return merged

    def get_current_context(self) -> Dict[str, Any]:
        """获取当前栈顶的完整元数据"""
        if not self._stack:
            return {}
        return dict(self._stack[-1].metadata)

    def _extract_from_heading(self, heading: str) -> Dict[str, str]:
        """从标题文本中提取元数据键值对"""
        result: Dict[str, str] = {}
        for pattern, key, transform in self.HEADING_EXTRACTORS:
            match = re.search(pattern, heading)
            if match:
                if transform:
                    try:
                        result[key] = transform(match)
                    except Exception:
                        result[key] = match.group(1)
                else:
                    result[key] = match.group(1)
        return result


# ============================================================
# 元数据注入器
# ============================================================

class MetadataInjector:
    """
    元数据注入器：遍历 DocumentSection 树，为每个 ChunkResult 分配正确的元数据。

    在 chunking 完成之后、embedding 之前调用。
    """

    def __init__(self):
        self._sanitizer = ASTSanitizer()

    def inject(
        self,
        structured_doc: StructuredDocument,
        chunks: List[ChunkResult],
    ) -> List[ChunkResult]:
        """
        为 chunks 注入领域元数据（原地修改）。

        Args:
            structured_doc: 结构化文档（含标题层级树）
            chunks: 已切分的 chunk 列表

        Returns:
            注入元数据后的 chunks（同一对象引用）
        """
        # Step 1: AST 净化（防御性编程）
        structured_doc.sections = self._sanitizer.sanitize_sections(
            structured_doc.sections
        )

        # Step 2: DFS 遍历树，构建 heading_path → metadata 映射
        context_stack = ContextStack()
        section_metadata: Dict[str, Dict] = {}

        self._walk_sections(
            structured_doc.sections, context_stack, section_metadata
        )

        # Step 3: 为每个 chunk 匹配其所在 section 的元数据
        for chunk in chunks:
            if chunk.heading_path and chunk.heading_path in section_metadata:
                # 注入，但保留 chunk 自身 metadata 的优先级
                chunk.metadata = {
                    **section_metadata[chunk.heading_path],
                    **chunk.metadata,
                }
            else:
                # 精确路径不匹配 → 最长前缀匹配
                matched = self._longest_prefix_match(
                    chunk.heading_path, section_metadata
                )
                if matched:
                    chunk.metadata = {
                        **section_metadata[matched],
                        **chunk.metadata,
                    }

        logger.debug(
            f"[MetadataInjector] 为 {len(chunks)} 个 chunk 注入元数据完成"
        )
        return chunks

    def _walk_sections(
        self,
        sections: List[DocumentSection],
        stack: ContextStack,
        output: Dict[str, Dict],
    ):
        """DFS 遍历并构建上下文映射"""
        for section in sections:
            merged = stack.enter_section(section.level, section.heading)
            output[section.heading] = merged

            if section.subsections:
                self._walk_sections(section.subsections, stack, output)

            # 递归返回时不需要显式 pop，
            # ContextStack 在下一个 enter_section 中自动处理退栈

    @staticmethod
    def _longest_prefix_match(
        target: Optional[str],
        mapping: Dict[str, Any],
    ) -> Optional[str]:
        """查找最长的 heading_path 前缀匹配"""
        if not target:
            return None
        parts = target.split(" > ")
        for i in range(len(parts) - 1, 0, -1):
            prefix = " > ".join(parts[:i])
            if prefix in mapping:
                return prefix
        return None


# 全局单例
metadata_injector = MetadataInjector()
