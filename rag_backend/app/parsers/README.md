# Parsers（多格式结构化解析）

把上传文件（bytes）解析为结构化文档（章节树 + 块 + 表格 + 图片 marker），供 `app/chunkers/` 分块。统一入口为 `parser_factory.py` 的 `FileParserFactory`，按 MIME 类型分发。

## 接口约定（base_parser.py）

```python
class FileParserStrategy(ABC):
    async def parse(self, file_bytes: bytes) -> str: ...          # 必须实现
    def get_supported_mime_types(self) -> list[str]: ...          # 必须实现
    def set_ingest_context(self, tenant_id, document_id): ...     # 可选：需存储图片的解析器使用
    def validate_file(self, file_bytes) -> bool: ...              # 默认 len > 0
```

## 解析器清单

| 解析器 | 格式 | 解析路径 |
|---|---|---|
| `StructuredPDFParser` | PDF | **三级自适应降级**：① pymupdf4llm 转 Markdown（本地，快）→ ② 文本量 < 文件大小×8% 判定为扫描件，转 Unstructured API（`ENABLE_UNSTRUCTURED` 控制，docker profile `heavy`）→ ③ PyMuPDF 字体大小启发式推断标题。附图片提取 → MinIO 存储 → 正文插入 marker |
| `StructuredWordParser` | DOC/DOCX | python-docx；内置样式 + 字体启发式标题映射；表格转 Markdown；图片提取 → VLM 描述 → MinIO → 替换占位符 |
| `StructuredExcelParser` | XLSX/XLS | openpyxl（data_only + read_only）；多 sheet 各生成 `## 工作表` 标题；限 100 行展示 |
| `StructuredMarkdownParser` | Markdown | 多编码解码（utf-8/utf-8-sig/gbk/gb2312/gb18030/latin-1），保留原格式 |
| `TextParser` | TXT/CSV | 多编码尝试直接解码 |
| `ImageParser` | PNG/JPEG/BMP/TIFF | 委托 `ocr_service`，经 OCR 适配器层处理 |

> `table_parser.py`、`chart_parser.py` 文件存在但未在 `FileParserFactory._initialize()` 注册。

## OCR 适配器层（app/services/ocr_adapters/）

| 适配器 | 引擎 | 适用 |
|---|---|---|
| `paddleocr_adapter` | PaddleOCR | 中文场景主力 |
| `tesseract_adapter` | Tesseract | 英文/通用（Docker 镜像已装中文语言包） |
| `mineru_adapter` | MinerU | PDF 专项（含公式） |
| `unstructured_adapter` | Unstructured | 多格式重型解析 |

## 上下游

- 上游：`services/file_service.py` 从 MinIO 下载文件后委托本模块解析。
- 下游：解析结果交给 `chunkers/`（域检测 → 分块 → 向量化入库）。
- 测试：`pytest tests/integration/test_ocr_integration.py tests/integration/test_data_ingestion.py`
