"""
测试多模态解析器

包括表格解析器和图表解析器的测试。
"""

import pytest
from unittest.mock import Mock, AsyncMock
import json

from app.parsers.table_parser import TableParser, parse_table_with_rules
from app.parsers.chart_parser import ChartParser, parse_chart_with_rules
from app.models.multimodal_chunk import TableData, ChartData


# ==================== 表格解析器测试 ====================

@pytest.mark.asyncio
async def test_table_parser_basic_mode():
    """测试基础模式表格解析"""
    parser = TableParser(mode="basic")

    table_data = [
        ["纳税人类型", "税率", "年收入限额"],
        ["一般企业", "25%", "无限制"],
        ["小型微利企业", "20%", "300万"]
    ]

    result = await parser.parse_table(table_data, caption="企业所得税税率表")

    assert isinstance(result, TableData)
    assert result.headers == ["纳税人类型", "税率", "年收入限额"]
    assert len(result.rows) == 2
    assert result.markdown is not None
    assert result.json_data is not None
    assert result.num_rows == 2
    assert result.num_columns == 3


@pytest.mark.asyncio
async def test_table_parser_rule_based_mode():
    """测试规则分析模式"""
    parser = TableParser(mode="rule_based")

    table_data = [
        ["纳税人类型", "税率"],
        ["一般企业", "25%"],
        ["小型微利企业", "20%"]
    ]

    result = await parser.parse_table(table_data)

    # 应该有摘要和洞察
    assert result.summary is not None
    assert len(result.summary) > 0
    assert isinstance(result.key_insights, list)


@pytest.mark.asyncio
async def test_table_parser_markdown_format():
    """测试Markdown格式化"""
    parser = TableParser(mode="basic")

    table_data = [
        ["A", "B"],
        ["1", "2"],
        ["3", "4"]
    ]

    result = await parser.parse_table(table_data)

    expected = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
    assert result.markdown == expected


@pytest.mark.asyncio
async def test_table_parser_json_format():
    """测试JSON格式化"""
    parser = TableParser(mode="basic")

    table_data = [
        ["Name", "Age"],
        ["Alice", "25"],
        ["Bob", "30"]
    ]

    result = await parser.parse_table(table_data)

    assert result.json_data["Name"] == ["Alice", "Bob"]
    assert result.json_data["Age"] == ["25", "30"]


@pytest.mark.asyncio
async def test_table_parser_numeric_column_analysis():
    """测试数值列分析"""
    parser = TableParser(mode="rule_based")

    table_data = [
        ["产品", "价格"],
        ["产品A", "100"],
        ["产品B", "200"],
        ["产品C", "150"]
    ]

    result = await parser.parse_table(table_data)

    # 应该识别出价格列是数值列，并分析范围
    insights_text = " ".join(result.key_insights)
    assert "100" in insights_text or "200" in insights_text


@pytest.mark.asyncio
async def test_table_parser_percentage_column_analysis():
    """测试百分比列分析"""
    parser = TableParser(mode="rule_based")

    table_data = [
        ["类别", "占比"],
        ["A类", "30%"],
        ["B类", "50%"],
        ["C类", "20%"]
    ]

    result = await parser.parse_table(table_data)

    # 应该识别百分比列
    insights_text = " ".join(result.key_insights)
    assert "%" in insights_text or "百分" in insights_text or "占比" in insights_text


@pytest.mark.asyncio
async def test_table_parser_with_llm():
    """测试LLM增强模式"""
    mock_llm = Mock()
    mock_llm.generate = AsyncMock(return_value=json.dumps({
        "summary": "这是一个AI生成的摘要",
        "key_insights": ["洞察1", "洞察2", "洞察3"]
    }))

    parser = TableParser(mode="ai_enhanced", llm_service=mock_llm)

    table_data = [
        ["列1", "列2"],
        ["数据1", "数据2"]
    ]

    result = await parser.parse_table(table_data)

    # 应该使用AI生成的摘要
    assert result.summary == "这是一个AI生成的摘要"
    assert len(result.key_insights) == 3


@pytest.mark.asyncio
async def test_table_parser_llm_fallback():
    """测试LLM失败时的降级"""
    mock_llm = Mock()
    mock_llm.generate = AsyncMock(side_effect=Exception("LLM Error"))

    parser = TableParser(mode="ai_enhanced", llm_service=mock_llm)

    table_data = [
        ["列1", "列2"],
        ["数据1", "数据2"]
    ]

    result = await parser.parse_table(table_data)

    # 应该降级到规则分析，仍然返回有效结果
    assert isinstance(result, TableData)
    assert result.summary is not None  # 规则生成的摘要


@pytest.mark.asyncio
async def test_table_parser_empty_table():
    """测试空表格处理"""
    parser = TableParser(mode="basic")

    with pytest.raises(ValueError):
        await parser.parse_table([])


@pytest.mark.asyncio
async def test_table_parser_only_header():
    """测试只有表头的表格"""
    parser = TableParser(mode="basic")

    with pytest.raises(ValueError):
        await parser.parse_table([["A", "B"]])


# ==================== 图表解析器测试 ====================

@pytest.mark.asyncio
async def test_chart_parser_basic_mode():
    """测试基础模式图表解析"""
    parser = ChartParser(mode="basic")

    # 模拟图表图片（实际应该是bytes，这里用简单字符串模拟）
    image_bytes = b"fake image data"

    # Mock OCR服务
    mock_ocr = Mock()
    mock_ocr.extract_text_from_image_bytes = AsyncMock(
        return_value="2020 100 2021 120 2022 150"
    )
    parser.ocr_service = mock_ocr

    result = await parser.parse_chart(image_bytes, title="数据趋势")

    assert isinstance(result, ChartData)
    assert result.title == "数据趋势"


@pytest.mark.asyncio
async def test_chart_parser_rule_based_mode():
    """测试规则分析模式"""
    parser = ChartParser(mode="rule_based")

    # Mock OCR返回包含趋势关键词的文本
    mock_ocr = Mock()
    mock_ocr.extract_text_from_image_bytes = AsyncMock(
        return_value="2020年 100亿 2021年 120亿 2022年 150亿 增长 趋势"
    )
    parser.ocr_service = mock_ocr

    image_bytes = b"fake image"
    result = await parser.parse_chart(image_bytes)

    # 应该识别出图表类型和趋势
    assert result.chart_type in ["line", "bar", "unknown"]
    assert result.description is not None
    assert len(result.key_trends) > 0


@pytest.mark.asyncio
async def test_chart_parser_detect_line_chart():
    """测试折线图识别"""
    parser = ChartParser(mode="rule_based")

    mock_ocr = Mock()
    mock_ocr.extract_text_from_image_bytes = AsyncMock(
        return_value="折线图 2020 2021 2022 趋势"
    )
    parser.ocr_service = mock_ocr

    result = await parser.parse_chart(b"fake")

    assert result.chart_type == "line"


@pytest.mark.asyncio
async def test_chart_parser_detect_bar_chart():
    """测试柱状图识别"""
    parser = ChartParser(mode="rule_based")

    mock_ocr = Mock()
    mock_ocr.extract_text_from_image_bytes = AsyncMock(
        return_value="柱状图 A类 B类 C类"
    )
    parser.ocr_service = mock_ocr

    result = await parser.parse_chart(b"fake")

    assert result.chart_type == "bar"


@pytest.mark.asyncio
async def test_chart_parser_extract_trends():
    """测试趋势提取"""
    parser = ChartParser(mode="rule_based")

    mock_ocr = Mock()
    mock_ocr.extract_text_from_image_bytes = AsyncMock(
        return_value="数据持续上升，增长迅速，波动较小"
    )
    parser.ocr_service = mock_ocr

    result = await parser.parse_chart(b"fake")

    # 应该提取到趋势
    trends_text = " ".join(result.key_trends)
    assert "上升" in trends_text or "增长" in trends_text


@pytest.mark.asyncio
async def test_chart_parser_extract_numbers():
    """测试数值提取"""
    parser = ChartParser(mode="rule_based")

    mock_ocr = Mock()
    mock_ocr.extract_text_from_image_bytes = AsyncMock(
        return_value="最小值 50 最大值 200 平均值 125"
    )
    parser.ocr_service = mock_ocr

    result = await parser.parse_chart(b"fake")

    # 应该提取到数值范围
    assert result.min_value is not None or result.max_value is not None


@pytest.mark.asyncio
async def test_chart_parser_with_vision():
    """测试Vision增强模式"""
    mock_vision = Mock()
    mock_vision.analyze_image = AsyncMock(return_value=json.dumps({
        "chart_type": "line",
        "description": "AI识别的图表描述",
        "key_trends": ["趋势1", "趋势2"],
        "insights": ["洞察1"],
        "x_label": "年份",
        "y_label": "金额",
        "legend": ["系列1"]
    }))

    parser = ChartParser(mode="ai_enhanced", vision_service=mock_vision)

    # Mock OCR
    mock_ocr = Mock()
    mock_ocr.extract_text_from_image_bytes = AsyncMock(return_value="")
    parser.ocr_service = mock_ocr

    result = await parser.parse_chart(b"fake")

    assert result.chart_type == "line"
    assert result.description == "AI识别的图表描述"
    assert result.x_label == "年份"
    assert result.y_label == "金额"


@pytest.mark.asyncio
async def test_chart_parser_vision_fallback():
    """测试Vision失败时的降级"""
    mock_vision = Mock()
    mock_vision.analyze_image = AsyncMock(side_effect=Exception("Vision Error"))

    parser = ChartParser(mode="ai_enhanced", vision_service=mock_vision)

    mock_ocr = Mock()
    mock_ocr.extract_text_from_image_bytes = AsyncMock(
        return_value="折线图 趋势"
    )
    parser.ocr_service = mock_ocr

    result = await parser.parse_chart(b"fake")

    # 应该降级到规则分析
    assert isinstance(result, ChartData)


# ==================== 便捷函数测试 ====================

@pytest.mark.asyncio
async def test_parse_table_with_rules_function():
    """测试便捷函数"""
    table_data = [
        ["A", "B"],
        ["1", "2"]
    ]

    result = await parse_table_with_rules(table_data, caption="测试表格")

    assert isinstance(result, TableData)
    assert result.caption == "测试表格"


@pytest.mark.asyncio
async def test_parse_chart_with_rules_function():
    """测试便捷函数"""
    result = await parse_chart_with_rules(b"fake", title="测试图表")

    assert isinstance(result, ChartData)
    assert result.title == "测试图表"


# ==================== 边界情况测试 ====================

@pytest.mark.asyncio
async def test_table_parser_with_uneven_rows():
    """测试不规则表格（行长度不一致）"""
    parser = TableParser(mode="basic")

    table_data = [
        ["A", "B", "C"],
        ["1", "2"],  # 少一列
        ["3", "4", "5"]
    ]

    result = await parser.parse_table(table_data)

    # 应该能处理并补齐
    assert isinstance(result, TableData)


@pytest.mark.asyncio
async def test_chart_parser_with_empty_ocr():
    """测试OCR返回空文本"""
    parser = ChartParser(mode="rule_based")

    mock_ocr = Mock()
    mock_ocr.extract_text_from_image_bytes = AsyncMock(return_value="")
    parser.ocr_service = mock_ocr

    result = await parser.parse_chart(b"fake")

    assert isinstance(result, ChartData)
    assert result.chart_type == "unknown"


# ==================== 性能测试 ====================

@pytest.mark.asyncio
async def test_table_parser_performance():
    """测试表格解析性能"""
    import time

    parser = TableParser(mode="rule_based")

    # 大表格 (100行)
    table_data = [["列1", "列2", "列3"]]
    for i in range(100):
        table_data.append([f"数据{i}", f"{i}", f"{i*2}"])

    start = time.time()
    result = await parser.parse_table(table_data)
    elapsed = time.time() - start

    # 应该在1秒内完成
    assert elapsed < 1.0
    assert result.num_rows == 100


# ==================== 集成测试 ====================

@pytest.mark.asyncio
async def test_table_to_chart_workflow():
    """测试表格到图表的完整流程"""
    # 1. 解析表格
    table_parser = TableParser(mode="rule_based")
    table_data = [
        ["年份", "收入"],
        ["2020", "100"],
        ["2021", "120"],
        ["2022", "150"]
    ]

    table_result = await table_parser.parse_table(table_data)

    assert table_result.num_rows == 3

    # 2. 如果要将表格数据可视化为图表
    # 可以从table_result中提取数据生成图表描述
    chart_data = ChartData(
        chart_type="line",
        title="收入趋势",
        description=f"基于表格数据：{table_result.caption or '数据表'}",
        key_trends=["逐年增长"],
        min_value=100,
        max_value=150
    )

    assert chart_data.chart_type == "line"
    assert chart_data.max_value == 150
