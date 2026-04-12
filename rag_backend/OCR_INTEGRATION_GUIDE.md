# OCR 集成指南

## 概述

本系统集成了 OCR (光学字符识别) 技术，用于从图片和扫描文档中提取文本内容。通过 PaddleOCR 和 EasyOCR 双引擎支持，实现高准确度的文字识别。

## 架构设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OCR 处理流程                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌──────────────┐                                                         │
│    │   上传文件    │                                                         │
│    └──────┬───────┘                                                         │
│           │                                                                 │
│           ▼                                                                 │
│    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │
│    │  文件格式检测 │────▶│  图片预处理   │────▶│   OCR 识别    │            │
│    │              │     │              │     │              │            │
│    │  - 图片      │     │  - 灰度化    │     │  - PaddleOCR │            │
│    │  - PDF       │     │  - 降噪      │     │  - EasyOCR   │            │
│    │  - 扫描件    │     │  - 倾斜校正   │     │  - 表格识别   │            │
│    └──────────────┘     └──────────────┘     └──────┬───────┘            │
│                                                       │                     │
│                                                       ▼                     │
│                                              ┌──────────────┐             │
│                                              │  结果后处理   │             │
│                                              │              │             │
│                                              │  - 文本清洗   │             │
│                                              │  - 布局分析   │             │
│                                              │  - 结构化输出  │             │
│                                              └──────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. 图片解析器 (ImageParser)

```python
from app.parsers import ImageParser

parser = ImageParser()

# 同步识别
result = await parser.parse(file_path="path/to/image.jpg")
print(result.text)  # 识别的文本
print(result.boxes)  # 文本框位置

# 带表格识别
result = await parser.parse(
    file_path="path/to/image.jpg",
    detect_tables=True
)
print(result.tables)  # 识别的表格
```

### 2. PDF 解析器 (PDFParser)

```python
from app.parsers import PDFParser

parser = PDFParser()

# 解析扫描 PDF
result = await parser.parse(file_path="path/to/scanned.pdf")
print(result.text)  # 识别的文本
print(result.pages)  # 分页信息
```

### 3. 结构化 PDF 解析器 (StructuredPDFParser)

```python
from app.parsers import StructuredPDFParser

parser = StructuredPDFParser()

# 解析带表格的 PDF
result = await parser.parse(file_path="path/to/table.pdf")
print(result.structured_data)  # 结构化数据
print(result.tables)  # 表格数据
```

## OCR 引擎

### 1. PaddleOCR

高准确度中文识别，支持多种语言：

```python
from app.parsers.ocr_engines.paddle_ocr import PaddleOCREngine

engine = PaddleOCREngine(
    use_angle_cls=True,  # 方向分类
    lang='ch',           # 中文
    use_gpu=False        # 是否使用 GPU
)

result = await engine.recognize(image_path)
```

**特点**：
- 适合印刷体文字
- 中文识别准确率高
- 支持表格识别
- 支持版面分析

### 2. EasyOCR

支持多语言，轻量级：

```python
from app.parsers.ocr_engines.easy_ocr import EasyOCREngine

engine = EasyOCREngine(
    languages=['ch_sim', 'en'],  # 简体中文 + 英文
    gpu=False
)

result = await engine.recognize(image_path)
```

**特点**：
- 支持多语言
- 易于部署
- 手写体支持较好

### 3. 引擎选择策略

```python
from app.parsers.ocr_engines.factory import OCREngineFactory

# 自动选择最佳引擎
engine = OCREngineFactory.create(
    file_type='image',
    languages=['ch_sim', 'en'],
    prefer_speed=True  # True: 速度优先, False: 精度优先
)
```

## 使用示例

### 基础用法

```python
from app.parsers import ParserFactory

# 获取解析器
parser = ParserFactory.get_parser("image")

# 解析图片
result = await parser.parse("path/to/image.jpg")
print(result.text)
```

### 批量处理

```python
from app.parsers import ParserFactory
import asyncio

async def batch_process(file_paths: list):
    parser = ParserFactory.get_parser("image")

    tasks = [parser.parse(path) for path in file_paths]
    results = await asyncio.gather(*tasks)

    return results

# 使用
results = await batch_process([
    "image1.jpg",
    "image2.png",
    "image3.jpg"
])
```

### 带进度回调

```python
async def process_with_progress(file_path: str):
    parser = ImageParser()

    def progress_callback(message: str):
        print(f"[OCR] {message}")

    result = await parser.parse(
        file_path,
        callback=progress_callback
    )

    return result

# 输出示例:
# [OCR] 开始预处理图片...
# [OCR] 图片预处理完成
# [OCR] 开始 OCR 识别...
# [OCR] 识别完成: 500 个字符
```

## API 接口

### 上传并识别

```
POST /api/v1/knowledge/upload
Content-Type: multipart/form-data

file: (binary)
```

**响应**：
```json
{
  "success": true,
  "data": {
    "file_id": "file_001",
    "file_name": "document.jpg",
    "text": "识别的文本内容...",
    "page_count": 1,
    "tables": [
      {
        "rows": 5,
        "cols": 3,
        "data": [["A", "B", "C"], ["1", "2", "3"]]
      }
    ]
  }
}
```

### 仅 OCR 识别

```
POST /api/v1/ocr/recognize
Content-Type: multipart/form-data

file: (binary)
ocr_engine: paddle  # paddle | easyocr | auto
```

## 配置参数

### 环境变量

```bash
# OCR 配置
OCR_ENGINE=paddle          # 使用引擎: paddle | easyocr | auto
OCR_USE_GPU=false          # 是否使用 GPU
OCR_LANGUAGES=ch_sim,en    # 识别语言
OCR_BATCH_SIZE=10          # 批处理大小

# PaddleOCR 配置
PADDLE_USE_ANGLE_CLS=true   # 方向分类
PADDLE_USE_GPU=false        # Paddle GPU

# EasyOCR 配置
EASYOCR_GPU=false          # EasyOCR GPU
```

### 代码配置

```python
OCR_CONFIG = {
    "engine": "paddle",
    "use_gpu": False,
    "languages": ["ch_sim", "en"],
    "batch_size": 10,
    "table_detection": True,
    "layout_analysis": True
}
```

## 性能优化

### GPU 加速

```bash
# 安装 GPU 版本
pip install paddlepaddle-gpu

# 配置使用 GPU
export OCR_USE_GPU=true
export CUDA_VISIBLE_DEVICES=0
```

### 批处理优化

```python
# 启用批处理
parser = ImageParser(batch_size=20)

# 并行处理
tasks = [parser.parse(f) for f in files]
results = await asyncio.gather(*tasks)
```

### 缓存策略

```python
# 启用识别结果缓存
parser = ImageParser(use_cache=True, cache_ttl=3600)

# 对于相同图片，直接返回缓存结果
result = await parser.parse("same_image.jpg")  # 从缓存读取
```

## 最佳实践

### 1. 图片质量优化

```
✅ 推荐做法：
- 分辨率 >= 300 DPI
- 图片格式：PNG、JPG
- 对比度适中
- 无明显倾斜或变形

❌ 避免：
- 分辨率 < 100 DPI
- 严重倾斜 (> 15度)
- 严重遮挡
- 过曝或欠曝
```

### 2. 预处理建议

```python
from app.parsers.ocr_utils import ImagePreprocessor

preprocessor = ImagePreprocessor()

# 完整预处理
processed = preprocessor.process(image_path, {
    "grayscale": True,
    "denoise": True,
    "deskew": True,
    "enhance_contrast": True,
    "resize": (2000, 2000)  # 最大尺寸
})
```

### 3. 表格识别

```python
# 启用表格识别
result = await parser.parse(
    file_path,
    detect_tables=True,
    table_format="html"  # html | json | excel
)

# 处理表格结果
for table in result.tables:
    print(table.to_dataframe())  # 转为 Pandas DataFrame
```

## 错误处理

### 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `OCRServiceUnavailable` | OCR 服务未启动 | 检查 PaddleOCR/EasyOCR 安装 |
| `UnsupportedFormat` | 不支持的文件格式 | 转换为支持的格式 |
| `ImageTooLarge` | 图片过大 | 压缩或切片处理 |
| `LowQualityImage` | 图片质量过低 | 提升图片质量或使用人工处理 |

### 降级策略

```python
try:
    # 优先使用 PaddleOCR
    result = await paddle_engine.recognize(image)
except OCRServiceUnavailable:
    # 降级到 EasyOCR
    result = await easyocr_engine.recognize(image)
except Exception:
    # 返回空结果或提示用户
    return {"error": "OCR识别失败"}
```

## 相关文档

- [多智能体协作系统设计](./rag_backend/COLLABORATION_SYSTEM_DESIGN.md)
- [MCP 架构设计](./rag_backend/MCP_ARCHITECTURE_DESIGN.md)
- [知识图谱使用指南](./rag_backend/知识图谱使用指南.md)
- [日志系统集成指南](./rag_backend/日志系统集成指南.md)
