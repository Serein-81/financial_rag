"""
测试自适应分块器
"""

import pytest
from unittest.mock import Mock, AsyncMock
from app.chunkers.adaptive_chunker import (
    AdaptiveChunker,
    PropositionChunker,
    AdaptiveChunk,
    ChunkMetadata
)


@pytest.fixture
def mock_llm_service():
    """模拟 LLM 服务"""
    service = Mock()
    service.generate = AsyncMock(return_value='{"boundaries": [100, 200, 300]}')
    return service


@pytest.fixture
def chunker():
    """创建自适应分块器实例（不使用 LLM）"""
    return AdaptiveChunker(
        llm_service=None,
        min_chunk_size=100,
        max_chunk_size=500,
        enable_llm_boundary=False
    )


@pytest.fixture
def chunker_with_llm(mock_llm_service):
    """创建带 LLM 的自适应分块器"""
    return AdaptiveChunker(
        llm_service=mock_llm_service,
        min_chunk_size=100,
        max_chunk_size=500,
        enable_llm_boundary=True
    )


@pytest.mark.asyncio
async def test_chunk_empty_document(chunker):
    """测试空文档"""
    chunks = await chunker.chunk("")
    assert chunks == []

    chunks = await chunker.chunk("   ")
    assert chunks == []


@pytest.mark.asyncio
async def test_chunk_short_document(chunker):
    """测试短文档"""
    document = "这是一个简短的文档。"

    chunks = await chunker.chunk(document)

    assert len(chunks) >= 1
    assert chunks[0].content == document.strip()
    assert chunks[0].char_count == len(document.strip())


@pytest.mark.asyncio
async def test_chunk_with_paragraphs(chunker):
    """测试包含多个段落的文档"""
    document = """第一段内容。
这是第一段的延续。

第二段内容。
这是第二段的延续。

第三段内容。"""

    chunks = await chunker.chunk(document)

    # 应该生成多个块
    assert len(chunks) >= 2

    # 验证每个块都有元数据
    for chunk in chunks:
        assert isinstance(chunk, AdaptiveChunk)
        assert isinstance(chunk.metadata, ChunkMetadata)
        assert chunk.char_count > 0


@pytest.mark.asyncio
async def test_chunk_with_headings(chunker):
    """测试包含标题的文档"""
    document = """# 主标题

这是主标题下的内容。

## 子标题1

这是子标题1下的内容。

## 子标题2

这是子标题2下的内容。"""

    chunks = await chunker.chunk(document)

    # 标题应该作为分隔符
    assert len(chunks) >= 2


@pytest.mark.asyncio
async def test_chunk_large_document(chunker):
    """测试大文档（会触发递归切分）"""
    # 创建一个超过 max_chunk_size 的文档
    long_paragraph = "这是一个很长的句子。" * 100  # 约 1000 字符

    chunks = await chunker.chunk(long_paragraph)

    # 应该被切分为多个块
    assert len(chunks) >= 2

    # 每个块不应超过最大大小（允许少量超出）
    for chunk in chunks:
        assert chunk.char_count <= chunker.max_chunk_size * 1.1


@pytest.mark.asyncio
async def test_split_by_natural_boundaries(chunker):
    """测试按自然边界切分"""
    document = """第一章 引言

这是引言部分的内容。

第二章 主体

这是主体部分的内容。"""

    segments = chunker._split_by_natural_boundaries(document)

    # 应该识别出多个段落
    assert len(segments) >= 2


@pytest.mark.asyncio
async def test_recursive_split(chunker):
    """测试递归切分"""
    # 创建一个长文本
    long_text = "这是一个句子。" * 150  # 约 1050 字符

    chunks = chunker._recursive_split(long_text, base_offset=0)

    # 应该被切分为多个块
    assert len(chunks) >= 2

    # 验证块的大小
    for chunk in chunks:
        assert chunk.char_count <= chunker.max_chunk_size * 1.1


@pytest.mark.asyncio
async def test_merge_and_resize_segments(chunker):
    """测试合并和调整段落"""
    segments = [
        ("短段落1", 0),
        ("短段落2", 20),
        ("短段落3", 40),
        ("这是一个很长的段落" * 50, 60)  # 超大段落
    ]

    chunks = chunker._merge_and_resize_segments(segments)

    # 小段落应该被合并，大段落应该被切分
    assert len(chunks) >= 2


@pytest.mark.asyncio
async def test_chunk_with_llm_boundary(chunker_with_llm, mock_llm_service):
    """测试使用 LLM 边界识别"""
    document = "这是一个测试文档。" * 50

    chunks = await chunker_with_llm.chunk(document)

    # LLM 服务应该被调用
    mock_llm_service.generate.assert_called()

    # 应该生成分块
    assert len(chunks) >= 1


@pytest.mark.asyncio
async def test_identify_topic_boundaries(chunker_with_llm, mock_llm_service):
    """测试主题边界识别"""
    document = "测试文档内容" * 100

    boundaries = await chunker_with_llm._identify_topic_boundaries(document)

    # 应该返回边界位置列表
    assert isinstance(boundaries, list)

    # LLM 应该被调用
    mock_llm_service.generate.assert_called()


@pytest.mark.asyncio
async def test_identify_topic_boundaries_long_doc(chunker_with_llm):
    """测试长文档的主题边界识别"""
    # 创建超过 3000 字符的文档
    document = "这是测试内容。" * 500

    boundaries = await chunker_with_llm._identify_topic_boundaries(document)

    # 应该分段处理
    assert isinstance(boundaries, list)


@pytest.mark.asyncio
async def test_chunk_with_chinese_punctuation(chunker):
    """测试中文标点符号处理"""
    document = """这是第一句话。这是第二句话！这是第三句话？
这是第四句话。

这是新的一段。"""

    chunks = await chunker.chunk(document)

    # 应该正确识别中文标点
    assert len(chunks) >= 1


@pytest.mark.asyncio
async def test_chunk_preserves_content(chunker):
    """测试分块不丢失内容"""
    document = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 20

    chunks = await chunker.chunk(document)

    # 合并所有块的内容
    merged = "".join(chunk.content for chunk in chunks)

    # 去除空白后应该包含所有原始内容
    assert document.replace("\n", "").replace(" ", "") in merged.replace("\n", "").replace(" ", "")


@pytest.mark.asyncio
async def test_chunk_metadata(chunker):
    """测试分块元数据"""
    document = """第一段内容。

第二段内容。"""

    chunks = await chunker.chunk(document)

    # 验证元数据
    for chunk in chunks:
        assert chunk.metadata.start_pos >= 0
        assert chunk.metadata.end_pos > chunk.metadata.start_pos
        assert chunk.metadata.chunk_type == "text"


@pytest.fixture
def proposition_chunker(mock_llm_service):
    """创建命题分块器"""
    mock_llm_service.generate = AsyncMock(return_value='''
    {
        "propositions": [
            {"id": 1, "text": "企业所得税税率为25%", "type": "fact"},
            {"id": 2, "text": "小型微利企业享受优惠", "type": "rule"}
        ]
    }
    ''')
    return PropositionChunker(llm_service=mock_llm_service)


@pytest.mark.asyncio
async def test_proposition_chunker_basic(proposition_chunker):
    """测试命题分块器基本功能"""
    document = "企业所得税标准税率为25%，小型微利企业适用20%优惠税率。"

    propositions = await proposition_chunker.chunk(document)

    # 应该提取出命题
    assert len(propositions) >= 1


@pytest.mark.asyncio
async def test_proposition_chunker_empty(proposition_chunker):
    """测试命题分块器处理空文档"""
    propositions = await proposition_chunker.chunk("")
    assert propositions == []


@pytest.mark.asyncio
async def test_proposition_chunker_long_doc(proposition_chunker):
    """测试命题分块器处理长文档"""
    document = "这是测试内容。" * 500  # 超过 2000 字符

    propositions = await proposition_chunker.chunk(document)

    # 应该分段处理
    assert isinstance(propositions, list)


@pytest.mark.asyncio
async def test_proposition_extract_error_handling(mock_llm_service):
    """测试命题提取错误处理"""
    mock_llm_service.generate = AsyncMock(side_effect=Exception("LLM 错误"))

    chunker = PropositionChunker(llm_service=mock_llm_service)
    propositions = await chunker.chunk("测试文档")

    # 错误时应该返回空列表
    assert propositions == []


@pytest.mark.asyncio
async def test_adaptive_chunker_handles_various_sizes(chunker):
    """测试自适应分块器处理各种大小的文档"""
    test_cases = [
        ("短文档", 50),
        ("中等文档" * 10, 500),
        ("长文档" * 50, 2500)
    ]

    for doc_type, length in test_cases:
        document = doc_type[:length]
        chunks = await chunker.chunk(document)

        # 应该正确处理
        assert len(chunks) >= 1

        # 验证块大小合理
        for chunk in chunks:
            assert chunk.char_count <= chunker.max_chunk_size * 1.2
