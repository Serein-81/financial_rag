"""
多模态分块数据模型

支持文本、表格、图表、图片等多种内容类型。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum


class ChunkType(str, Enum):
    """分块类型枚举"""
    TEXT = "text"
    TABLE = "table"
    CHART = "chart"
    IMAGE = "image"
    MIXED = "mixed"  # 包含多种类型


class TableFormat(str, Enum):
    """表格格式枚举"""
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"
    CSV = "csv"


@dataclass
class ChunkMetadata:
    """分块元数据"""
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    position_in_doc: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableData:
    """
    表格结构化数据

    支持多种格式存储和查询。
    """
    # 原始数据
    headers: List[str]  # 表头
    rows: List[List[str]]  # 数据行

    # 格式化版本
    markdown: str  # Markdown 格式
    json_data: Optional[Dict[str, Any]] = None  # JSON 格式 (键值对)
    html: Optional[str] = None  # HTML 格式

    # 语义理解
    caption: Optional[str] = None  # 表格标题/说明
    summary: Optional[str] = None  # GPT-4V 生成的表格摘要
    key_insights: List[str] = field(default_factory=list)  # 关键发现

    # 统计信息
    num_rows: int = 0
    num_columns: int = 0

    def __post_init__(self):
        """自动计算统计信息"""
        self.num_rows = len(self.rows)
        self.num_columns = len(self.headers)


@dataclass
class ChartData:
    """
    图表结构化数据

    提取图表的关键信息和趋势。
    """
    # 图表类型
    chart_type: str  # bar, line, pie, scatter, etc.

    # 视觉描述
    title: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    legend: List[str] = field(default_factory=list)

    # 数据点 (如果能提取)
    data_points: Optional[List[Dict[str, Any]]] = None

    # GPT-4V 生成的分析
    description: Optional[str] = None  # 图表整体描述
    key_trends: List[str] = field(default_factory=list)  # 关键趋势
    insights: List[str] = field(default_factory=list)  # 关键洞察

    # 数值信息
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None


@dataclass
class ImageData:
    """
    图片结构化数据

    存储图片的描述和分类信息。
    """
    # 图片类型
    image_type: str  # photo, diagram, screenshot, logo, etc.

    # 描述
    caption: Optional[str] = None  # 图片标题
    alt_text: Optional[str] = None  # 替代文本
    description: Optional[str] = None  # GPT-4V 生成的详细描述

    # 分类标签
    tags: List[str] = field(default_factory=list)

    # OCR 文本 (如果图片包含文字)
    ocr_text: Optional[str] = None


@dataclass
class MultiModalChunk:
    """
    多模态分块

    统一的数据结构，支持文本、表格、图表、图片等多种内容。

    Examples:
        >>> # 文本分块
        >>> text_chunk = MultiModalChunk(
        ...     chunk_id="chunk_001",
        ...     chunk_type=ChunkType.TEXT,
        ...     content="企业所得税的标准税率为25%。",
        ...     metadata=ChunkMetadata(page_number=1)
        ... )

        >>> # 表格分块
        >>> table_chunk = MultiModalChunk(
        ...     chunk_id="chunk_002",
        ...     chunk_type=ChunkType.TABLE,
        ...     content="[表格] 企业所得税税率表",
        ...     structured_data=TableData(
        ...         headers=["纳税人类型", "税率"],
        ...         rows=[["一般企业", "25%"], ["小型微利企业", "20%"]],
        ...         markdown="| 纳税人类型 | 税率 |\\n|---|---|\\n| 一般企业 | 25% |"
        ...     ),
        ...     metadata=ChunkMetadata(page_number=2)
        ... )

        >>> # 图表分块
        >>> chart_chunk = MultiModalChunk(
        ...     chunk_id="chunk_003",
        ...     chunk_type=ChunkType.CHART,
        ...     content="[图表] 2020-2023年企业所得税收入趋势",
        ...     structured_data=ChartData(
        ...         chart_type="line",
        ...         description="企业所得税收入呈上升趋势",
        ...         key_trends=["逐年增长", "2022年增速最快"]
        ...     ),
        ...     image_url="https://example.com/chart.png",
        ...     metadata=ChunkMetadata(page_number=3)
        ... )
    """
    chunk_id: str
    chunk_type: ChunkType
    content: str  # 文本描述或内容摘要

    # 结构化数据 (根据类型不同)
    structured_data: Optional[Any] = None  # TableData | ChartData | ImageData

    # 图片 URL (表格、图表、图片都可能有)
    image_url: Optional[str] = None

    # 元数据
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)

    # 向量嵌入 (可选)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "chunk_id": self.chunk_id,
            "chunk_type": self.chunk_type.value,
            "content": self.content,
            "image_url": self.image_url,
            "metadata": {
                "page_number": self.metadata.page_number,
                "section_title": self.metadata.section_title,
                "document_id": self.metadata.document_id,
                "document_name": self.metadata.document_name,
                "position_in_doc": self.metadata.position_in_doc,
                "created_at": self.metadata.created_at.isoformat() if self.metadata.created_at else None,
                "extra": self.metadata.extra
            }
        }

        # 序列化结构化数据
        if self.structured_data:
            if isinstance(self.structured_data, (TableData, ChartData, ImageData)):
                result["structured_data"] = self._serialize_structured_data(self.structured_data)
            else:
                result["structured_data"] = self.structured_data

        if self.embedding:
            result["embedding"] = self.embedding

        return result

    def _serialize_structured_data(self, data: Any) -> Dict[str, Any]:
        """序列化结构化数据"""
        if isinstance(data, TableData):
            return {
                "type": "table",
                "headers": data.headers,
                "rows": data.rows,
                "markdown": data.markdown,
                "json_data": data.json_data,
                "html": data.html,
                "caption": data.caption,
                "summary": data.summary,
                "key_insights": data.key_insights,
                "num_rows": data.num_rows,
                "num_columns": data.num_columns
            }
        elif isinstance(data, ChartData):
            return {
                "type": "chart",
                "chart_type": data.chart_type,
                "title": data.title,
                "x_label": data.x_label,
                "y_label": data.y_label,
                "legend": data.legend,
                "data_points": data.data_points,
                "description": data.description,
                "key_trends": data.key_trends,
                "insights": data.insights,
                "min_value": data.min_value,
                "max_value": data.max_value,
                "mean_value": data.mean_value
            }
        elif isinstance(data, ImageData):
            return {
                "type": "image",
                "image_type": data.image_type,
                "caption": data.caption,
                "alt_text": data.alt_text,
                "description": data.description,
                "tags": data.tags,
                "ocr_text": data.ocr_text
            }
        else:
            return {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MultiModalChunk":
        """从字典创建"""
        metadata = ChunkMetadata(
            page_number=data.get("metadata", {}).get("page_number"),
            section_title=data.get("metadata", {}).get("section_title"),
            document_id=data.get("metadata", {}).get("document_id"),
            document_name=data.get("metadata", {}).get("document_name"),
            position_in_doc=data.get("metadata", {}).get("position_in_doc"),
            extra=data.get("metadata", {}).get("extra", {})
        )

        # 反序列化结构化数据
        structured_data = None
        if "structured_data" in data and data["structured_data"]:
            sd = data["structured_data"]
            sd_type = sd.get("type")

            if sd_type == "table":
                structured_data = TableData(
                    headers=sd.get("headers", []),
                    rows=sd.get("rows", []),
                    markdown=sd.get("markdown", ""),
                    json_data=sd.get("json_data"),
                    html=sd.get("html"),
                    caption=sd.get("caption"),
                    summary=sd.get("summary"),
                    key_insights=sd.get("key_insights", [])
                )
            elif sd_type == "chart":
                structured_data = ChartData(
                    chart_type=sd.get("chart_type", "unknown"),
                    title=sd.get("title"),
                    x_label=sd.get("x_label"),
                    y_label=sd.get("y_label"),
                    legend=sd.get("legend", []),
                    data_points=sd.get("data_points"),
                    description=sd.get("description"),
                    key_trends=sd.get("key_trends", []),
                    insights=sd.get("insights", []),
                    min_value=sd.get("min_value"),
                    max_value=sd.get("max_value"),
                    mean_value=sd.get("mean_value")
                )
            elif sd_type == "image":
                structured_data = ImageData(
                    image_type=sd.get("image_type", "unknown"),
                    caption=sd.get("caption"),
                    alt_text=sd.get("alt_text"),
                    description=sd.get("description"),
                    tags=sd.get("tags", []),
                    ocr_text=sd.get("ocr_text")
                )

        return cls(
            chunk_id=data["chunk_id"],
            chunk_type=ChunkType(data["chunk_type"]),
            content=data["content"],
            structured_data=structured_data,
            image_url=data.get("image_url"),
            metadata=metadata,
            embedding=data.get("embedding")
        )

    def get_searchable_text(self) -> str:
        """
        获取用于搜索的文本

        将所有可搜索的文本内容合并。
        """
        texts = [self.content]

        if self.chunk_type == ChunkType.TABLE and isinstance(self.structured_data, TableData):
            # 添加表格的 Markdown 格式
            texts.append(self.structured_data.markdown)
            if self.structured_data.caption:
                texts.append(self.structured_data.caption)
            if self.structured_data.summary:
                texts.append(self.structured_data.summary)
            texts.extend(self.structured_data.key_insights)

        elif self.chunk_type == ChunkType.CHART and isinstance(self.structured_data, ChartData):
            # 添加图表的描述
            if self.structured_data.title:
                texts.append(self.structured_data.title)
            if self.structured_data.description:
                texts.append(self.structured_data.description)
            texts.extend(self.structured_data.key_trends)
            texts.extend(self.structured_data.insights)

        elif self.chunk_type == ChunkType.IMAGE and isinstance(self.structured_data, ImageData):
            # 添加图片的描述
            if self.structured_data.caption:
                texts.append(self.structured_data.caption)
            if self.structured_data.description:
                texts.append(self.structured_data.description)
            if self.structured_data.ocr_text:
                texts.append(self.structured_data.ocr_text)
            texts.extend(self.structured_data.tags)

        return "\n\n".join(filter(None, texts))

    def get_display_content(self) -> str:
        """
        获取用于展示的内容

        根据类型返回最适合展示的格式。
        """
        if self.chunk_type == ChunkType.TEXT:
            return self.content

        elif self.chunk_type == ChunkType.TABLE and isinstance(self.structured_data, TableData):
            result = []
            if self.structured_data.caption:
                result.append(f"**{self.structured_data.caption}**\n")
            result.append(self.structured_data.markdown)
            if self.structured_data.summary:
                result.append(f"\n*摘要: {self.structured_data.summary}*")
            return "\n".join(result)

        elif self.chunk_type == ChunkType.CHART and isinstance(self.structured_data, ChartData):
            result = [self.content]
            if self.structured_data.description:
                result.append(f"\n描述: {self.structured_data.description}")
            if self.structured_data.key_trends:
                result.append("\n关键趋势:")
                result.extend([f"- {trend}" for trend in self.structured_data.key_trends])
            return "\n".join(result)

        elif self.chunk_type == ChunkType.IMAGE and isinstance(self.structured_data, ImageData):
            result = [self.content]
            if self.structured_data.description:
                result.append(f"\n描述: {self.structured_data.description}")
            if self.structured_data.ocr_text:
                result.append(f"\n文字内容: {self.structured_data.ocr_text}")
            return "\n".join(result)

        else:
            return self.content


def create_text_chunk(
    chunk_id: str,
    content: str,
    metadata: Optional[ChunkMetadata] = None
) -> MultiModalChunk:
    """创建文本分块（便捷函数）"""
    return MultiModalChunk(
        chunk_id=chunk_id,
        chunk_type=ChunkType.TEXT,
        content=content,
        metadata=metadata or ChunkMetadata()
    )


def create_table_chunk(
    chunk_id: str,
    table_data: TableData,
    metadata: Optional[ChunkMetadata] = None
) -> MultiModalChunk:
    """创建表格分块（便捷函数）"""
    content = f"[表格] {table_data.caption or '数据表格'}"
    return MultiModalChunk(
        chunk_id=chunk_id,
        chunk_type=ChunkType.TABLE,
        content=content,
        structured_data=table_data,
        metadata=metadata or ChunkMetadata()
    )


def create_chart_chunk(
    chunk_id: str,
    chart_data: ChartData,
    image_url: Optional[str] = None,
    metadata: Optional[ChunkMetadata] = None
) -> MultiModalChunk:
    """创建图表分块（便捷函数）"""
    content = f"[图表] {chart_data.title or '数据图表'}"
    return MultiModalChunk(
        chunk_id=chunk_id,
        chunk_type=ChunkType.CHART,
        content=content,
        structured_data=chart_data,
        image_url=image_url,
        metadata=metadata or ChunkMetadata()
    )


def create_image_chunk(
    chunk_id: str,
    image_data: ImageData,
    image_url: str,
    metadata: Optional[ChunkMetadata] = None
) -> MultiModalChunk:
    """创建图片分块（便捷函数）"""
    content = f"[图片] {image_data.caption or image_data.description or '图片内容'}"
    return MultiModalChunk(
        chunk_id=chunk_id,
        chunk_type=ChunkType.IMAGE,
        content=content,
        structured_data=image_data,
        image_url=image_url,
        metadata=metadata or ChunkMetadata()
    )
