"""
图表解析器

三层架构：
1. 基础提取 - OCR文字识别
2. 规则分析 - 基于关键词和模式识别（无需模型）
3. AI增强 - Vision模型理解图表（可选）
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from app.models.multimodal_chunk import ChartData

logger = logging.getLogger(__name__)


class ChartParser:
    """
    图表解析器

    支持三种模式：
    - basic: 仅OCR文字提取（默认，免费）
    - rule_based: OCR + 规则分析（免费）
    - ai_enhanced: OCR + 规则 + Vision模型（需要GPT-4V/Claude等）
    """

    def __init__(
        self,
        mode: str = "rule_based",
        vision_service: Optional[Any] = None,
        ocr_service: Optional[Any] = None
    ):
        """
        初始化图表解析器

        Args:
            mode: 解析模式 ("basic" | "rule_based" | "ai_enhanced")
            vision_service: Vision模型服务（GPT-4V/Claude，仅ai_enhanced模式需要）
            ocr_service: OCR服务（可选，默认使用内置OCR）
        """
        self.mode = mode
        self.vision_service = vision_service
        self.ocr_service = ocr_service

        if mode == "ai_enhanced" and not vision_service:
            logger.warning("AI增强模式需要Vision服务，降级到规则分析模式")
            self.mode = "rule_based"

    async def parse_chart(
        self,
        image_bytes: bytes,
        title: Optional[str] = None
    ) -> ChartData:
        """
        解析图表

        Args:
            image_bytes: 图表图片字节流
            title: 图表标题（可选）

        Returns:
            ChartData: 图表结构化数据
        """
        if not image_bytes:
            raise ValueError("图表图片为空")

        # ─────────────────────────────────────
        # 第1层：基础提取（OCR文字识别）
        # ─────────────────────────────────────
        ocr_text = await self._extract_text_with_ocr(image_bytes)

        # ─────────────────────────────────────
        # 第2层：规则分析（免费）
        # ─────────────────────────────────────
        chart_type = "unknown"
        description = None
        key_trends = []
        insights = []
        min_value = None
        max_value = None
        mean_value = None

        if self.mode in ["rule_based", "ai_enhanced"]:
            # 基于OCR文本和规则识别
            chart_type = self._detect_chart_type_by_rules(ocr_text, title)
            description = self._generate_rule_based_description(
                chart_type, ocr_text, title
            )
            key_trends = self._extract_trends_by_rules(ocr_text, chart_type)
            insights = self._extract_insights_by_rules(ocr_text, chart_type)

            # 提取数值信息
            numbers = self._extract_numbers_from_text(ocr_text)
            if numbers:
                min_value = min(numbers)
                max_value = max(numbers)
                mean_value = sum(numbers) / len(numbers)

        # ─────────────────────────────────────
        # 第3层：AI增强（可选，需要Vision模型）
        # ─────────────────────────────────────
        x_label = None
        y_label = None
        legend = []

        if self.mode == "ai_enhanced" and self.vision_service:
            try:
                ai_analysis = await self._analyze_with_vision(image_bytes, title)

                # AI分析优先
                if ai_analysis.get("chart_type"):
                    chart_type = ai_analysis["chart_type"]
                if ai_analysis.get("description"):
                    description = ai_analysis["description"]
                if ai_analysis.get("key_trends"):
                    key_trends = ai_analysis["key_trends"]
                if ai_analysis.get("insights"):
                    insights = ai_analysis["insights"]

                # 额外信息
                x_label = ai_analysis.get("x_label")
                y_label = ai_analysis.get("y_label")
                legend = ai_analysis.get("legend", [])

            except Exception as e:
                logger.warning(f"Vision分析失败，使用规则分析结果: {e}")

        return ChartData(
            chart_type=chart_type,
            title=title,
            x_label=x_label,
            y_label=y_label,
            legend=legend,
            description=description,
            key_trends=key_trends,
            insights=insights,
            min_value=min_value,
            max_value=max_value,
            mean_value=mean_value
        )

    async def _extract_text_with_ocr(self, image_bytes: bytes) -> str:
        """
        使用OCR提取图表中的文字

        Args:
            image_bytes: 图片字节流

        Returns:
            str: OCR识别的文本
        """
        if self.ocr_service:
            # 使用外部OCR服务
            try:
                return await self.ocr_service.extract_text_from_image_bytes(image_bytes)
            except Exception as e:
                logger.warning(f"外部OCR服务失败: {e}，尝试内置OCR")

        # 使用内置OCR (Tesseract)
        try:
            from PIL import Image
            import pytesseract
            import io

            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')
            return text.strip()

        except ImportError:
            logger.warning("Tesseract未安装，OCR功能不可用")
            return ""
        except Exception as e:
            logger.error(f"OCR识别失败: {e}")
            return ""

    def _detect_chart_type_by_rules(
        self,
        ocr_text: str,
        title: Optional[str] = None
    ) -> str:
        """
        基于规则检测图表类型

        规则：
        1. 标题包含关键词 -> 对应类型
        2. OCR文本包含特征词 -> 对应类型
        3. 默认 -> unknown
        """
        text = (title or "") + " " + ocr_text
        text = text.lower()

        # 图表类型关键词映射
        type_keywords = {
            "line": ["折线图", "趋势图", "line chart", "trend"],
            "bar": ["柱状图", "柱形图", "条形图", "bar chart"],
            "pie": ["饼图", "pie chart", "占比"],
            "scatter": ["散点图", "scatter"],
            "area": ["面积图", "area chart"],
            "radar": ["雷达图", "radar"],
            "heatmap": ["热力图", "heatmap"],
            "funnel": ["漏斗图", "funnel"]
        }

        for chart_type, keywords in type_keywords.items():
            if any(kw in text for kw in keywords):
                return chart_type

        # 基于数值模式推断
        numbers = self._extract_numbers_from_text(ocr_text)
        if len(numbers) >= 5:
            # 多个数据点，可能是折线图或柱状图
            if any(kw in text for kw in ["年", "月", "日", "时间"]):
                return "line"  # 时间序列 -> 折线图
            else:
                return "bar"  # 分类数据 -> 柱状图

        return "unknown"

    def _generate_rule_based_description(
        self,
        chart_type: str,
        ocr_text: str,
        title: Optional[str] = None
    ) -> str:
        """
        基于规则生成图表描述

        逻辑：
        1. 如果有标题，使用标题作为主要描述
        2. 根据图表类型生成通用描述
        3. 加入数值范围信息
        """
        parts = []

        if title:
            parts.append(title)

        # 图表类型描述
        type_desc = {
            "line": "展示数据随时间的变化趋势",
            "bar": "比较不同类别的数值大小",
            "pie": "展示各部分占比关系",
            "scatter": "展示两个变量之间的相关性",
            "area": "展示数值的累积变化",
            "radar": "多维度对比分析",
            "unknown": "展示数据可视化信息"
        }
        parts.append(type_desc.get(chart_type, type_desc["unknown"]))

        # 数值范围
        numbers = self._extract_numbers_from_text(ocr_text)
        if numbers:
            min_val = min(numbers)
            max_val = max(numbers)
            parts.append(f"（数值范围: {min_val:.2f} - {max_val:.2f}）")

        return "，".join(parts)

    def _extract_trends_by_rules(
        self,
        ocr_text: str,
        chart_type: str
    ) -> List[str]:
        """
        基于规则提取趋势

        规则：
        1. 检测趋势关键词（上升、下降、波动、稳定）
        2. 分析数值序列的变化模式
        3. 识别时间信息
        """
        trends = []

        # 趋势关键词检测
        trend_keywords = {
            "上升": ["增长", "上升", "提高", "攀升", "增加", "rise", "increase", "grow"],
            "下降": ["下降", "减少", "降低", "下滑", "decrease", "decline", "drop"],
            "波动": ["波动", "震荡", "fluctuate", "volatile"],
            "稳定": ["稳定", "平稳", "持平", "stable", "steady"]
        }

        for trend_name, keywords in trend_keywords.items():
            if any(kw in ocr_text for kw in keywords):
                trends.append(f"呈{trend_name}态势")

        # 分析数值序列
        numbers = self._extract_numbers_from_text(ocr_text)
        if len(numbers) >= 3:
            # 计算变化率
            changes = [numbers[i] - numbers[i-1] for i in range(1, len(numbers))]
            positive_changes = sum(1 for c in changes if c > 0)
            negative_changes = sum(1 for c in changes if c < 0)

            if positive_changes > len(changes) * 0.7:
                trends.append("整体呈上升趋势")
            elif negative_changes > len(changes) * 0.7:
                trends.append("整体呈下降趋势")
            else:
                trends.append("呈波动态势")

        # 时间相关趋势
        years = re.findall(r'(20\d{2}|19\d{2})年?', ocr_text)
        if len(years) >= 2:
            trends.append(f"{years[0]}至{years[-1]}期间数据变化")

        return trends[:3]  # 最多返回3个趋势

    def _extract_insights_by_rules(
        self,
        ocr_text: str,
        chart_type: str
    ) -> List[str]:
        """
        基于规则提取洞察

        规则：
        1. 识别极值（最大、最小、峰值）
        2. 识别关键时间点
        3. 识别对比关系
        """
        insights = []

        # 极值关键词
        if any(kw in ocr_text for kw in ["最高", "最大", "峰值", "peak", "highest"]):
            insights.append("出现峰值")

        if any(kw in ocr_text for kw in ["最低", "最小", "谷值", "lowest", "minimum"]):
            insights.append("出现最低点")

        # 增速关键词
        if any(kw in ocr_text for kw in ["快速", "急剧", "大幅", "显著", "rapid"]):
            insights.append("变化幅度显著")

        # 对比关系
        if any(kw in ocr_text for kw in ["超过", "高于", "低于", "领先"]):
            insights.append("存在明显差异")

        # 数值分析
        numbers = self._extract_numbers_from_text(ocr_text)
        if numbers:
            max_val = max(numbers)
            min_val = min(numbers)
            range_ratio = (max_val - min_val) / max_val if max_val > 0 else 0

            if range_ratio > 0.5:
                insights.append(f"数值波动较大（{range_ratio*100:.0f}%）")
            else:
                insights.append("数值相对稳定")

        return insights[:3]  # 最多返回3个洞察

    def _extract_numbers_from_text(self, text: str) -> List[float]:
        """从文本中提取所有数字"""
        # 移除常见单位
        cleaned = re.sub(r'[元万亿%,，\s]', '', text)

        # 提取数字
        numbers = []
        for match in re.finditer(r'-?\d+\.?\d*', cleaned):
            try:
                num = float(match.group())
                # 过滤异常值（年份等）
                if 1900 <= num <= 2100:
                    continue
                numbers.append(num)
            except ValueError:
                continue

        return numbers

    async def _analyze_with_vision(
        self,
        image_bytes: bytes,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        使用Vision模型分析图表（可选）

        Args:
            image_bytes: 图片字节流
            title: 图表标题

        Returns:
            Dict: 分析结果
        """
        prompt = f"""请分析这个图表：

{f'标题：{title}' if title else ''}

请提供：
1. 图表类型（line/bar/pie/scatter/area等）
2. 简短描述（15-20字）
3. 2-3个关键趋势
4. 1-2个关键洞察
5. X轴和Y轴标签（如果有）
6. 图例信息（如果有）

返回JSON格式：
{{
    "chart_type": "line",
    "description": "图表描述",
    "key_trends": ["趋势1", "趋势2"],
    "insights": ["洞察1"],
    "x_label": "X轴标签",
    "y_label": "Y轴标签",
    "legend": ["系列1", "系列2"]
}}
"""

        try:
            # 调用Vision模型（GPT-4V / Claude 3.5 Sonnet等）
            response = await self.vision_service.analyze_image(
                image_bytes=image_bytes,
                prompt=prompt,
                temperature=0.3,
                max_tokens=500
            )

            # 解析JSON响应
            import json
            analysis = json.loads(response)

            return analysis

        except Exception as e:
            logger.error(f"Vision模型分析失败: {e}")
            return {}


# 便捷函数

async def parse_chart_basic(image_bytes: bytes) -> ChartData:
    """基础解析（仅OCR文字提取）"""
    parser = ChartParser(mode="basic")
    return await parser.parse_chart(image_bytes)


async def parse_chart_with_rules(
    image_bytes: bytes,
    title: Optional[str] = None
) -> ChartData:
    """规则解析（OCR + 规则分析）"""
    parser = ChartParser(mode="rule_based")
    return await parser.parse_chart(image_bytes, title)


async def parse_chart_with_vision(
    image_bytes: bytes,
    title: Optional[str] = None,
    vision_service = None
) -> ChartData:
    """Vision增强解析（OCR + 规则 + Vision模型）"""
    parser = ChartParser(mode="ai_enhanced", vision_service=vision_service)
    return await parser.parse_chart(image_bytes, title)
