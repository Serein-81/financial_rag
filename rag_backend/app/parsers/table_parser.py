"""
表格解析器

三层架构：
1. 基础提取 - 提取结构化数据（headers, rows）
2. 规则分析 - 基于规则的统计分析（无需模型）
3. AI增强 - LLM生成摘要和洞察（可选）
"""

import logging
import re
from typing import List, Dict, Any, Optional
from app.models.multimodal_chunk import TableData

logger = logging.getLogger(__name__)


class TableParser:
    """
    表格解析器

    支持三种模式：
    - basic: 仅提取结构化数据（默认，免费）
    - rule_based: 基础 + 规则分析（免费）
    - ai_enhanced: 基础 + 规则 + AI分析（需要LLM服务）
    """

    def __init__(
        self,
        mode: str = "rule_based",
        llm_service: Optional[Any] = None
    ):
        """
        初始化表格解析器

        Args:
            mode: 解析模式 ("basic" | "rule_based" | "ai_enhanced")
            llm_service: LLM服务实例（仅mode="ai_enhanced"时需要）
        """
        self.mode = mode
        self.llm_service = llm_service

        if mode == "ai_enhanced" and not llm_service:
            logger.warning("AI增强模式需要LLM服务，降级到规则分析模式")
            self.mode = "rule_based"

    async def parse_table(
        self,
        table_data: List[List[str]],
        caption: Optional[str] = None
    ) -> TableData:
        """
        解析表格

        Args:
            table_data: 表格数据（二维列表）
            caption: 表格标题/说明（可选）

        Returns:
            TableData: 表格结构化数据
        """
        if not table_data or len(table_data) < 2:
            raise ValueError("表格数据为空或只有表头")

        # ─────────────────────────────────────
        # 第1层：基础提取（必需，免费）
        # ─────────────────────────────────────
        headers = table_data[0]
        rows = table_data[1:]

        # 生成Markdown格式
        markdown = self._format_as_markdown(headers, rows)

        # 生成JSON格式（键值对，方便结构化查询）
        json_data = self._format_as_json(headers, rows)

        # 统计信息
        num_rows = len(rows)
        num_columns = len(headers)

        # ─────────────────────────────────────
        # 第2层：规则分析（免费）
        # ─────────────────────────────────────
        summary = None
        key_insights = []

        if self.mode in ["rule_based", "ai_enhanced"]:
            summary = self._generate_rule_based_summary(
                headers, rows, num_rows, num_columns, caption
            )
            key_insights = self._extract_rule_based_insights(headers, rows)

        # ─────────────────────────────────────
        # 第3层：AI增强（可选，需要模型）
        # ─────────────────────────────────────
        if self.mode == "ai_enhanced" and self.llm_service:
            try:
                ai_analysis = await self._analyze_with_llm(markdown, caption)

                # AI摘要优先，规则分析作为fallback
                if ai_analysis.get("summary"):
                    summary = ai_analysis["summary"]

                # 合并AI洞察和规则洞察
                if ai_analysis.get("key_insights"):
                    key_insights = ai_analysis["key_insights"][:5]  # 取前5个

            except Exception as e:
                logger.warning(f"AI分析失败，使用规则分析结果: {e}")

        return TableData(
            headers=headers,
            rows=rows,
            markdown=markdown,
            json_data=json_data,
            caption=caption,
            summary=summary,
            key_insights=key_insights,
            num_rows=num_rows,
            num_columns=num_columns
        )

    def _format_as_markdown(self, headers: List[str], rows: List[List[str]]) -> str:
        """格式化为Markdown表格"""
        lines = []

        # 表头
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # 数据行
        for row in rows:
            # 确保行长度与表头一致
            padded_row = row + [""] * (len(headers) - len(row))
            lines.append("| " + " | ".join(padded_row[:len(headers)]) + " |")

        return "\n".join(lines)

    def _format_as_json(
        self,
        headers: List[str],
        rows: List[List[str]]
    ) -> Dict[str, List[Any]]:
        """
        格式化为JSON（列导向）

        Example:
            {
                "纳税人类型": ["一般企业", "小型微利企业"],
                "税率": ["25%", "20%"]
            }
        """
        json_data = {header: [] for header in headers}

        for row in rows:
            for i, header in enumerate(headers):
                value = row[i] if i < len(row) else ""
                json_data[header].append(value)

        return json_data

    def _generate_rule_based_summary(
        self,
        headers: List[str],
        rows: List[List[str]],
        num_rows: int,
        num_columns: int,
        caption: Optional[str] = None
    ) -> str:
        """
        基于规则生成摘要（无需模型）

        逻辑：
        1. 如果有caption，使用caption
        2. 否则生成 "该表包含X行Y列数据，展示了..."
        """
        if caption:
            return f"{caption}（{num_rows}行 × {num_columns}列）"

        # 尝试从表头推断主题
        header_text = "、".join(headers[:3])  # 取前3列

        # 检测是否包含数值列
        has_numeric = any(
            self._is_numeric_column(headers[i], [row[i] for row in rows if i < len(row)])
            for i in range(len(headers))
        )

        if has_numeric:
            summary = f"该表包含 {num_rows} 行 × {num_columns} 列数据，展示了 {header_text} 等相关信息及数值统计"
        else:
            summary = f"该表包含 {num_rows} 行 × {num_columns} 列数据，展示了 {header_text} 等信息"

        return summary

    def _extract_rule_based_insights(
        self,
        headers: List[str],
        rows: List[List[str]]
    ) -> List[str]:
        """
        基于规则提取关键发现（无需模型）

        规则：
        1. 数值列 - 提取最大值、最小值
        2. 百分比列 - 提取最高/最低百分比
        3. 分类列 - 统计类别数量
        """
        insights = []

        for col_idx, header in enumerate(headers):
            column_values = [
                row[col_idx] for row in rows if col_idx < len(row)
            ]

            # 跳过空列
            if not column_values or all(not v.strip() for v in column_values):
                continue

            # 检测列类型
            if self._is_numeric_column(header, column_values):
                # 数值列
                insight = self._analyze_numeric_column(header, column_values)
                if insight:
                    insights.append(insight)

            elif self._is_percentage_column(column_values):
                # 百分比列
                insight = self._analyze_percentage_column(header, column_values)
                if insight:
                    insights.append(insight)

            elif len(set(column_values)) <= 10:
                # 分类列（类别数 <= 10）
                insight = self._analyze_categorical_column(header, column_values)
                if insight:
                    insights.append(insight)

        return insights[:5]  # 最多返回5个洞察

    def _is_numeric_column(self, header: str, values: List[str]) -> bool:
        """判断是否为数值列"""
        # 表头包含数值关键词
        numeric_keywords = ["数量", "金额", "收入", "支出", "价格", "费用", "额度", "值"]
        if any(kw in header for kw in numeric_keywords):
            return True

        # 超过50%的值是数字
        numeric_count = sum(1 for v in values if self._extract_number(v) is not None)
        return numeric_count >= len(values) * 0.5

    def _is_percentage_column(self, values: List[str]) -> bool:
        """判断是否为百分比列"""
        percentage_count = sum(1 for v in values if "%" in v)
        return percentage_count >= len(values) * 0.5

    def _extract_number(self, value: str) -> Optional[float]:
        """从字符串中提取数字"""
        # 移除常见单位和符号
        cleaned = re.sub(r'[元万亿,，\s]', '', value)

        # 提取数字
        match = re.search(r'-?\d+\.?\d*', cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None

    def _analyze_numeric_column(
        self,
        header: str,
        values: List[str]
    ) -> Optional[str]:
        """分析数值列"""
        numbers = [self._extract_number(v) for v in values]
        numbers = [n for n in numbers if n is not None]

        if not numbers:
            return None

        max_val = max(numbers)
        min_val = min(numbers)
        avg_val = sum(numbers) / len(numbers)

        # 找到最大值对应的行
        max_idx = next(
            i for i, v in enumerate(values)
            if self._extract_number(v) == max_val
        )

        return f"{header}的范围为 {min_val:.2f} ~ {max_val:.2f}，平均值为 {avg_val:.2f}"

    def _analyze_percentage_column(
        self,
        header: str,
        values: List[str]
    ) -> Optional[str]:
        """分析百分比列"""
        percentages = []
        for v in values:
            match = re.search(r'(\d+\.?\d*)%', v)
            if match:
                percentages.append(float(match.group(1)))

        if not percentages:
            return None

        max_pct = max(percentages)
        min_pct = min(percentages)

        return f"{header}的范围为 {min_pct}% ~ {max_pct}%"

    def _analyze_categorical_column(
        self,
        header: str,
        values: List[str]
    ) -> Optional[str]:
        """分析分类列"""
        # 统计每个类别的数量
        from collections import Counter
        category_counts = Counter(values)

        if len(category_counts) <= 1:
            return None

        most_common = category_counts.most_common(1)[0]

        return f"{header}共有 {len(category_counts)} 个类别，其中「{most_common[0]}」出现次数最多（{most_common[1]}次）"

    async def _analyze_with_llm(
        self,
        markdown: str,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        使用LLM分析表格（可选）

        Args:
            markdown: 表格的Markdown格式
            caption: 表格标题

        Returns:
            Dict: {"summary": str, "key_insights": List[str]}
        """
        prompt = f"""请分析以下表格：

{f'标题：{caption}' if caption else ''}

{markdown}

请提供：
1. 简短摘要（1句话，20字以内）
2. 3个关键发现（每个10-15字）

返回JSON格式：
{{
    "summary": "表格摘要",
    "key_insights": ["发现1", "发现2", "发现3"]
}}
"""

        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                temperature=0.3,
                max_tokens=300
            )

            # 解析JSON响应
            import json
            analysis = json.loads(response)

            return {
                "summary": analysis.get("summary", ""),
                "key_insights": analysis.get("key_insights", [])
            }

        except Exception as e:
            logger.error(f"LLM分析表格失败: {e}")
            return {"summary": None, "key_insights": []}

    def parse_table_from_markdown(self, markdown: str) -> TableData:
        """
        从Markdown格式解析表格

        Args:
            markdown: Markdown格式的表格

        Returns:
            TableData: 表格结构化数据
        """
        lines = [line.strip() for line in markdown.strip().split("\n") if line.strip()]

        if len(lines) < 3:
            raise ValueError("Markdown表格格式无效（至少需要表头、分隔符、数据行）")

        # 解析表头
        header_line = lines[0]
        headers = [
            cell.strip()
            for cell in header_line.split("|")[1:-1]  # 去掉首尾的空字符串
        ]

        # 解析数据行（跳过分隔符行）
        rows = []
        for line in lines[2:]:
            cells = [
                cell.strip()
                for cell in line.split("|")[1:-1]
            ]
            rows.append(cells)

        return self.parse_table(headers + rows)


# 便捷函数

def parse_table_basic(table_data: List[List[str]]) -> TableData:
    """基础解析（仅提取结构化数据）"""
    parser = TableParser(mode="basic")
    import asyncio
    return asyncio.run(parser.parse_table(table_data))


async def parse_table_with_rules(
    table_data: List[List[str]],
    caption: Optional[str] = None
) -> TableData:
    """规则解析（结构化数据 + 规则分析）"""
    parser = TableParser(mode="rule_based")
    return await parser.parse_table(table_data, caption)


async def parse_table_with_ai(
    table_data: List[List[str]],
    caption: Optional[str] = None,
    llm_service = None
) -> TableData:
    """AI增强解析（结构化数据 + 规则分析 + LLM分析）"""
    parser = TableParser(mode="ai_enhanced", llm_service=llm_service)
    return await parser.parse_table(table_data, caption)
