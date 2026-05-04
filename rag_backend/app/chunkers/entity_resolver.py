"""
法务实体显式化器 (Entity Resolver)

双路策略 (Two-Pass Hybrid)：
- Pass 1 (LLM 结构化提取)：从合同头部提取实体映射表 {"甲方": "XX科技有限公司"}
- Pass 2 (纯 str.replace)：对全文 chunk 执行字符串替换

理解能力和执行能力分离，各自的弱点不会叠加。
"""

import json
import logging
from typing import List, Dict
from app.chunkers.base_chunker import ChunkResult
from app.models.structured_document import StructuredDocument
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class EntityResolver:
    """
    法务实体显式化器。

    在入库前将合同中的"甲方""乙方"等简称替换为真实公司名。
    """

    # 实体标记模板：替换后的格式为 "XX科技有限公司(原称:甲方)"
    ENTITY_MARKER_TEMPLATE = "{real_name}(原称:{original})"

    async def resolve(
        self,
        structured_doc: StructuredDocument,
        chunks: List[ChunkResult],
    ) -> List[ChunkResult]:
        """
        双路解析主入口。

        Args:
            structured_doc: 结构化文档（含未替换的原始文本）
            chunks: 已切分的 chunk 列表

        Returns:
            已执行实体替换的 chunks
        """
        # Step 1: 提取合同前 20 blocks（或前 3000 字符）
        preamble = self._extract_preamble(structured_doc)
        if not preamble:
            logger.warning("[EntityResolver] 未提取到头文本，跳过实体替换")
            return chunks

        # Step 2: LLM 构建字典
        entity_map = await self._extract_entity_map(preamble)
        if not entity_map:
            logger.warning("[EntityResolver] LLM 未提取到实体映射，跳过")
            return chunks

        logger.info(
            f"[EntityResolver] 提取到 {len(entity_map)} 个映射: {entity_map}"
        )

        # Step 3: 按原始词长度降序排序（避免"甲方"先于"甲"被匹配）
        sorted_terms = sorted(entity_map.keys(), key=len, reverse=True)

        # Step 4: 对每个 chunk 执行纯字符串替换
        for chunk in chunks:
            for term in sorted_terms:
                real_name = entity_map[term]
                replacement = self.ENTITY_MARKER_TEMPLATE.format(
                    real_name=real_name, original=term
                )
                chunk.content = chunk.content.replace(term, replacement)

        # 将映射表存入 metadata 以便追溯
        if chunks:
            chunks[0].entity_map = entity_map

        logger.info(
            f"[EntityResolver] 实体替换完成: "
            f"{len(entity_map)} 个映射, {len(chunks)} 个 chunk"
        )
        return chunks

    async def _extract_entity_map(self, preamble: str) -> Dict[str, str]:
        """
        调用 LLM 提取实体映射表。

        Prompt 从 prompts/chunkers/entity_resolve_prompt.md 加载。
        {preamble} 占位符运行时替换为合同开头文本。
        """
        from app.prompts.loader import load_prompt_template
        prompt = load_prompt_template(
            "chunkers/entity_resolve_prompt.md",
            preamble=preamble[:3000],
        )

        try:
            response = await llm_service.get_answer(prompt, [], [])
            response = response.strip()

            # 清理 markdown 代码块标记（如果 LLM 不听话）
            if response.startswith("```"):
                response = response.split("\n", 1)[-1]
                response = response.rsplit("```", 1)[0]

            entity_map = json.loads(response.strip())
            if isinstance(entity_map, dict):
                # 过滤掉非字符串值
                return {
                    k: v for k, v in entity_map.items()
                    if isinstance(k, str) and isinstance(v, str)
                }
            return {}
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[EntityResolver] LLM 提取失败: {e}")
            return {}

    @staticmethod
    def _extract_preamble(doc: StructuredDocument) -> str:
        """提取合约开头文本：取前 20 个 block 或第一个 section"""
        blocks = doc.raw_blocks[:20] if doc.raw_blocks else []
        if not blocks and doc.sections:
            blocks = doc.sections[0].blocks[:20]
        return "\n".join(b.content for b in blocks if b.content)[:3000]


# 全局单例
entity_resolver = EntityResolver()
