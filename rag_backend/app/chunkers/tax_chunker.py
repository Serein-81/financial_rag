"""
税务领域切块策略 (Tax Chunker)

核心设计：
1. 条款级切片 (Clause-based Slicing)：基于正则识别"第一条"、"第二款"等
2. 生命周期打标：从文档头部提取生效/废止日期、税种、地域
3. PREVIOUS/NEXT 关系：相邻条款链接

一个完整条款就是一个不可分割的 Node。
"""

import re
import logging
from typing import List, Dict, Any
from app.chunkers.base_chunker import ChunkResult, ChunkStrategy
from app.models.structured_document import StructuredDocument

logger = logging.getLogger(__name__)


class TaxChunker:
    """
    税务文档切块器。

    按法条逻辑边界进行切分，替代现有按自然段切分的策略。
    """

    # 条款匹配正则
    CLAUSE_PATTERNS = [
        r"第[一二三四五六七八九十百千]+条",
        r"第\d+条",
        r"第[一二三四五六七八九十]+款",
        r"（[一二三四五六七八九十]+）",
        r"（\d+）",
    ]

    # 组合后的分割正则
    _SPLIT_PATTERN = re.compile(
        "|".join(f"({p})" for p in CLAUSE_PATTERNS)
    )

    def __init__(self):
        self._compiled = self._SPLIT_PATTERN

    def chunk(
        self,
        structured_doc: StructuredDocument,
        chunk_tokens: int = 1024,
        overlap_tokens: int = 50,
    ) -> List[ChunkResult]:
        """
        按条款对税务文档进行切块。

        1. 将全文转为 markdown
        2. 按条款正则分割
        3. 每个条款为一个独立 chunk
        """
        full_text = structured_doc.to_markdown()
        if not full_text.strip():
            return []

        # 提取文档级生命周期元数据
        lifecycle_meta = self._extract_lifecycle_metadata(full_text)

        # 按条款分割
        chunks = self._split_into_clauses(full_text, lifecycle_meta)

        # 标记 domain
        for chunk in chunks:
            chunk.domain = "tax"
            chunk.metadata.update(lifecycle_meta)

        logger.info(
            f"[TaxChunker] 切块完成: {len(chunks)} 个条款"
        )
        return chunks

    def _split_into_clauses(
        self,
        text: str,
        lifecycle_meta: Dict[str, Any],
    ) -> List[ChunkResult]:
        """按条款正则分割文本"""
        # 用正则找到所有条款起始位置
        matches = list(self._compiled.finditer(text))
        if not matches:
            # 无匹配条款时，全文作为一个块
            return [
                ChunkResult(
                    content=text.strip(),
                    start=0,
                    end=len(text),
                    tokens=ChunkStrategy.approx_token_len(text),
                    domain="tax",
                    metadata=lifecycle_meta,
                )
            ]

        chunks = []
        for i, match in enumerate(matches):
            start = match.start()
            # 取当前条款到下一个条款之前的内容
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(text)

            content = text[start:end].strip()
            if content:
                chunks.append(
                    ChunkResult(
                        content=content,
                        start=start,
                        end=end,
                        tokens=ChunkStrategy.approx_token_len(content),
                        heading_path=match.group().strip(),
                        domain="tax",
                        metadata={
                            **lifecycle_meta,
                            "clause_id": match.group().strip(),
                        },
                    )
                )

        return chunks

    @staticmethod
    def _extract_lifecycle_metadata(full_text: str) -> Dict[str, Any]:
        """
        从文档头部提取生命周期元数据。

        提取字段：effective_date, expiry_date, tax_type, region
        """
        metadata: Dict[str, Any] = {
            "expiry_date": "2099-12-31",
        }

        # 只扫描前 50 行
        header = "\n".join(full_text.split("\n")[:50])

        # 发文日期 / 施行日期
        date_patterns = [
            r"(发文|施行|公布)日期[：:]\s*(\d{4})[年/](\d{1,2})[月/](\d{1,2})",
            r"(\d{4})[年/](\d{1,2})[月/](\d{1,2})日起施行",
        ]
        for pattern in date_patterns:
            match = re.search(pattern, header)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    metadata["effective_date"] = (
                        f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
                    )
                elif len(groups) >= 3:
                    metadata["effective_date"] = (
                        f"{groups[-3]}-{groups[-2].zfill(2)}-{groups[-1].zfill(2)}"
                    )
                break

        # 废止日期
        expiry_match = re.search(
            r"(废止|同时废止|有效期至)[^。]*?(\d{4})[年/](\d{1,2})[月/](\d{1,2})",
            header,
        )
        if expiry_match:
            metadata["expiry_date"] = (
                f"{expiry_match.group(2)}-"
                f"{expiry_match.group(3).zfill(2)}-"
                f"{expiry_match.group(4).zfill(2)}"
            )

        # 税种
        for tax_type in [
            "增值税", "企业所得税", "个人所得税", "消费税",
            "关税", "印花税", "房产税", "土地使用税",
            "契税", "城市维护建设税",
        ]:
            if tax_type in header:
                metadata["tax_type"] = tax_type
                break

        # 地域
        for region in [
            "全国", "北京市", "上海市", "广东省",
            "浙江省", "江苏省", "深圳市", "广州市",
        ]:
            if region in header:
                metadata["region"] = region
                break

        return metadata


# 全局单例
tax_chunker = TaxChunker()
