"""
多态 Prompt 组装器 (Context Assembler)

按 domain 分发到不同的组装策略：
- legal:    PARENT summary + LEAF content
- tax:      PREVIOUS content + LEAF content + NEXT content
- finance:  PARENT context + TABLE content
- general:  Auto-Merged 完整段落
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ContextAssembler:
    """
    多态 Prompt 组装器。
    """

    async def assemble(
        self,
        chunks: List[Dict],
        domain: Optional[str],
        query: str,
    ) -> str:
        if not chunks:
            return ""

        if domain == "legal":
            return self._assemble_legal(chunks)
        elif domain == "tax":
            return self._assemble_tax(chunks)
        elif domain == "finance":
            return self._assemble_finance(chunks)
        else:
            return self._assemble_general(chunks)

    def _assemble_legal(self, chunks: List[Dict]) -> str:
        parts = ["<KnowledgeBase type='legal'>"]
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"[法务条款 {i}]")
            parent_summary = chunk.get("parent_summary")
            if parent_summary:
                parts.append(f"【章节主旨】: {parent_summary}")
            parts.append(f"【具体条款】: {chunk.get('content', '')[:500]}")
            parts.append("")
        parts.append("</KnowledgeBase>")
        return "\n".join(parts)

    def _assemble_tax(self, chunks: List[Dict]) -> str:
        parts = ["<KnowledgeBase type='tax'>"]
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"[税法规定 {i}]")
            prev = chunk.get("prev_content")
            if prev:
                parts.append(f"【前一条款】: {prev}")
            parts.append(f"【核心命中】: {chunk.get('content', '')[:500]}")
            nxt = chunk.get("next_content")
            if nxt:
                parts.append(f"【后一条款】: {nxt}")
            parts.append("")
        parts.append("</KnowledgeBase>")
        return "\n".join(parts)

    def _assemble_finance(self, chunks: List[Dict]) -> str:
        parts = ["<KnowledgeBase type='finance'>"]
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"[财务报表 {i}]")
            parent_ctx = chunk.get("parent_context")
            if parent_ctx:
                parts.append(f"【表头语境】: {parent_ctx}")
            content = chunk.get("content", "")[:500]
            if chunk.get("block_type") == "table":
                parts.append(f"【核心表格】:\n{content}")
            else:
                parts.append(f"【数据摘要】: {content}")
            parts.append("")
        parts.append("</KnowledgeBase>")
        return "\n".join(parts)

    def _assemble_general(self, chunks: List[Dict]) -> str:
        parts = ["<KnowledgeBase type='general'>"]
        for i, chunk in enumerate(chunks, 1):
            tag = "综合段落" if chunk.get("is_merged") else "具体说明"
            parts.append(f"[参考内容 {i}]")
            parts.append(f"【{tag}】: {chunk.get('content', '')[:800]}")
            parts.append("")
        parts.append("</KnowledgeBase>")
        return "\n".join(parts)


context_assembler = ContextAssembler()
