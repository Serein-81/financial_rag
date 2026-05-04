"""
财务领域切块策略 (Financial Chunker v2)

核心设计：
1. 表格级原子化：禁止按字数切断表格，保留完整表头
2. 上下文剥离：正文段落与表格分开切块，通过 PARENT/CHILD 关系连接
3. 大表格 Sub-Table 拆分：保留表头，按逻辑行组分块
4. 财务指标实体提取：从表格和文本中识别财务指标（研发费用、营收等）
   写入 chunk.meta_info["metrics"]，用于 GraphRAG 式跨行检索

复用现有的 StructuredDocumentChunker 作为基础切块引擎。
"""

import re
import logging
from typing import List, Dict, Set
from app.chunkers.base_chunker import ChunkResult
from app.models.structured_document import StructuredDocument
from app.chunkers.structured_document_chunker import StructuredDocumentChunker

logger = logging.getLogger(__name__)

# 常见财务指标关键词（用于实体提取）
FINANCIAL_METRICS: Set[str] = {
    # 利润表
    "营业收入", "营业成本", "营业利润", "利润总额", "净利润",
    "毛利润", "毛利率", "净利率",
    "研发费用", "销售费用", "管理费用", "财务费用",
    "投资收益", "公允价值变动收益", "资产减值损失",
    "营业税金及附加", "所得税费用",
    # 资产负债表
    "总资产", "总负债", "净资产", "流动资产", "流动负债",
    "货币资金", "应收账款", "存货", "固定资产", "无形资产",
    "短期借款", "长期借款", "应付账款", "预收账款",
    "股东权益", "归属于母公司股东权益",
    "股本", "资本公积", "盈余公积", "未分配利润",
    # 现金流量表
    "经营活动现金流", "投资活动现金流", "筹资活动现金流",
    "经营活动现金流量净额", "投资活动现金流量净额", "筹资活动现金流量净额",
    "自由现金流", "资本支出",
    # 财务指标
    "每股收益", "每股净资产", "净资产收益率", "总资产报酬率",
    "资产负债率", "流动比率", "速动比率",
    "应收账款周转率", "存货周转率",
    "销售增长率", "利润增长率", "营收增长率",
    # 常见简称
    "营收", "净利", "毛利", "总收", "总利",
}

# 财务数字匹配
VALUE_PATTERN = re.compile(
    r"([+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(亿|万|千|元|万元|亿元|%)"
)

# 表格行模式（Markdown 表格行）
TABLE_ROW_PATTERN = re.compile(r"^\|.+\|$")


class FinancialChunker:
    """
    财务文档切块器 (v2 含指标实体提取)。

    包装现有的 StructuredDocumentChunker，在其输出上叠加
    表格原子化、上下文剥离和财务指标实体提取。
    """

    MAX_TABLE_HEADER_ROWS = 20
    MAX_TABLE_TOTAL_ROWS = 200
    SUB_TABLE_GROUP_SIZE = 30

    def __init__(self):
        self._inner = StructuredDocumentChunker()

    def chunk(
        self,
        structured_doc: StructuredDocument,
        chunk_tokens: int = 800,
        overlap_tokens: int = 80,
    ) -> List[ChunkResult]:
        """对财务文档执行领域感知切块 + 指标实体提取。"""
        raw_chunks = self._inner.chunk_structured_document(
            structured_doc,
            chunk_tokens=chunk_tokens,
            overlap_tokens=overlap_tokens,
        )

        for chunk in raw_chunks:
            chunk.domain = "finance"

        # 表格原子化后处理
        chunks = []
        for chunk in raw_chunks:
            block_types = chunk.metadata.get("block_types", [])
            if "table" in block_types:
                table_chunks = self._split_financial_table(chunk)
                chunks.extend(table_chunks)
            else:
                chunks.append(chunk)

        # 财务指标实体提取 + 关系构建
        chunks = self._extract_financial_metrics(chunks)

        logger.info(
            f"[FinancialChunker] 切块完成: {len(chunks)} 个 chunk"
        )
        return chunks

    # ================================================================
    # 财务指标实体提取
    # ================================================================

    def _extract_financial_metrics(self, chunks: List[ChunkResult]) -> List[ChunkResult]:
        """
        从 chunk 中提取财务指标实体，写入 meta_info["metrics"]。

        对表格 chunk：解析表头行，提取指标名→值映射
        对文本 chunk：匹配已知指标关键词

        提取结果写入：
        - meta_info["metrics"]: ["研发费用", "营业收入", ...]
        - meta_info["has_metrics"]: True
        """
        for chunk in chunks:
            metrics_found: List[str] = []
            content = chunk.content or ""

            if chunk.block_type == "table":
                # 表格块：解析 Markdown 表格提取指标
                metrics_found = self._extract_metrics_from_table(content)
            else:
                # 文本块：关键词匹配
                metrics_found = self._extract_metrics_from_text(content)

            if metrics_found:
                if "metrics" not in chunk.metadata:
                    chunk.metadata["metrics"] = []
                # 去重合并
                existing = set(chunk.metadata.get("metrics", []))
                for m in metrics_found:
                    if m not in existing:
                        chunk.metadata["metrics"].append(m)
                        existing.add(m)
                chunk.metadata["has_metrics"] = True

        return chunks

    def _extract_metrics_from_table(self, content: str) -> List[str]:
        """
        从 Markdown 表格中提取财务指标。

        策略：
        1. 取表头行（第一行），解析每个单元格
        2. 检查每个单元格是否包含已知财务指标关键词
        3. 检查数据行第一列是否为指标名
        """
        metrics: List[str] = []
        lines = content.strip().split("\n")

        if not lines:
            return metrics

        # 第一行是表头
        header_cells = self._parse_table_row(lines[0])
        for cell in header_cells:
            found = self._match_metrics(cell)
            metrics.extend(found)

        # 数据行的第一列也可能是指标名
        for line in lines[2:]:  # 跳过表头和第二行的 --- 分隔线
            if not line.strip().startswith("|"):
                continue
            cells = self._parse_table_row(line)
            if cells:
                first_cell = cells[0].strip()
                if first_cell in FINANCIAL_METRICS:
                    metrics.append(first_cell)

        return list(set(metrics))

    def _extract_metrics_from_text(self, content: str) -> List[str]:
        """从纯文本中匹配财务指标关键词。"""
        found: List[str] = []
        for metric in FINANCIAL_METRICS:
            if metric in content:
                found.append(metric)
        return found

    def _parse_table_row(self, line: str) -> List[str]:
        """解析 Markdown 表格行。"""
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            return []
        cells = line.split("|")[1:-1]
        return [c.strip() for c in cells]

    def _match_metrics(self, text: str) -> List[str]:
        """从文本中匹配已知财务指标。"""
        found = []
        for metric in FINANCIAL_METRICS:
            if metric in text:
                found.append(metric)
        return found

    def _split_financial_table(self, chunk: ChunkResult) -> List[ChunkResult]:
        """表格原子化拆分。"""
        chunk.block_type = "table"
        # 同时写入 meta_info，确保数据库可查询
        if "block_types" not in chunk.metadata:
            chunk.metadata["block_types"] = []
        if "table" not in chunk.metadata["block_types"]:
            chunk.metadata["block_types"].append("table")
        chunk.metadata["block_type"] = "table"
        return [chunk]


financial_chunker = FinancialChunker()
