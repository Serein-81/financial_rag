"""
测试切块策略重构
验证 Markdown 智能切分和 Token 计数
"""
from app.chunkers import ChunkStrategyFactory, MarkdownChunkStrategy, PlainTextChunkStrategy


def test_token_counting():
    """测试 Token 计数功能"""
    print("=" * 60)
    print("🧪 测试 1: Token 计数")
    print("=" * 60)
    
    strategy = MarkdownChunkStrategy()
    
    test_cases = [
        ("这是中文测试", 6),  # 6个中文字符 = 6 tokens
        ("Hello World", 2),   # 2个英文单词 = 2 tokens
        ("中英混合 Mixed Text", 7),  # 4中文 + 2英文 + 1空格 = 7 tokens
        ("", 0),
    ]
    
    for text, expected in test_cases:
        result = strategy.approx_token_len(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{text}': {result} tokens (期望: {expected})")
    
    print()


def test_markdown_chunking():
    """测试 Markdown 结构化切分"""
    print("=" * 60)
    print("🧪 测试 2: Markdown 结构化切分")
    print("=" * 60)
    
    markdown_text = """# 第一章 用户认证

## 1.1 登录流程

用户输入账号密码后，系统会进行验证。验证通过后，生成 JWT Token 返回给客户端。

## 1.2 注册流程

用户填写注册信息，包括用户名、邮箱、密码等。系统会检查用户名是否重复。

# 第二章 权限管理

## 2.1 角色定义

系统支持多种角色：管理员、普通用户、访客等。
"""
    
    strategy = MarkdownChunkStrategy()
    chunks = strategy.chunk(markdown_text, chunk_tokens=100, overlap_tokens=20)
    
    print(f"✅ 共生成 {len(chunks)} 个切块\n")
    
    for i, chunk in enumerate(chunks, 1):
        print(f"--- 切块 {i} ---")
        print(f"标题路径: {chunk.heading_path or '(无)'}")
        print(f"Token 数: {chunk.tokens}")
        print(f"位置: {chunk.start}-{chunk.end}")
        print(f"内容预览: {chunk.content[:50]}...")
        print()


def test_plain_text_chunking():
    """测试纯文本切分(向后兼容)"""
    print("=" * 60)
    print("🧪 测试 3: 纯文本切分(向后兼容)")
    print("=" * 60)
    
    text = "这是一段测试文本。" * 50  # 生成较长文本
    
    strategy = PlainTextChunkStrategy()
    chunks = strategy.chunk(text, chunk_tokens=100, overlap_tokens=20)
    
    print(f"✅ 共生成 {len(chunks)} 个切块")
    print(f"第一个切块 Token 数: {chunks[0].tokens}")
    print(f"第一个切块内容长度: {len(chunks[0].content)} 字符")
    print()


def test_factory_pattern():
    """测试工厂模式"""
    print("=" * 60)
    print("🧪 测试 4: 工厂模式 - 策略选择")
    print("=" * 60)
    
    test_cases = [
        ("markdown", MarkdownChunkStrategy),
        ("md", MarkdownChunkStrategy),
        ("text", PlainTextChunkStrategy),
        ("plain_text", PlainTextChunkStrategy),
        ("unknown", PlainTextChunkStrategy),  # 默认策略
    ]
    
    for doc_type, expected_class in test_cases:
        strategy = ChunkStrategyFactory.get_strategy(doc_type)
        status = "✅" if isinstance(strategy, expected_class) else "❌"
        print(f"{status} {doc_type}: {strategy.__class__.__name__}")
    
    print()


def test_heading_path_preservation():
    """测试标题路径保留"""
    print("=" * 60)
    print("🧪 测试 5: 标题路径保留")
    print("=" * 60)
    
    markdown_text = """# 第一章

## 1.1 小节

这是第一章第一节的内容。

### 1.1.1 子小节

这是更深层级的内容。

## 1.2 第二节

这是第一章第二节的内容。
"""
    
    strategy = MarkdownChunkStrategy()
    chunks = strategy.chunk(markdown_text, chunk_tokens=50, overlap_tokens=10)
    
    print(f"✅ 共生成 {len(chunks)} 个切块\n")
    
    for i, chunk in enumerate(chunks, 1):
        print(f"切块 {i}: {chunk.heading_path or '(无标题)'}")
    
    print()


def test_chunk_result_format():
    """测试切块结果格式"""
    print("=" * 60)
    print("🧪 测试 6: 切块结果格式")
    print("=" * 60)
    
    text = "# 测试标题\n\n这是测试内容。"
    
    strategy = MarkdownChunkStrategy()
    chunks = strategy.chunk(text, chunk_tokens=100)
    
    if chunks:
        chunk_dict = chunks[0].to_dict()
        print("✅ 切块结果包含以下字段:")
        for key, value in chunk_dict.items():
            print(f"   - {key}: {type(value).__name__}")
    
    print()


def test_empty_text_handling():
    """测试空文本处理"""
    print("=" * 60)
    print("🧪 测试 7: 空文本处理")
    print("=" * 60)
    
    strategy = MarkdownChunkStrategy()
    
    test_cases = [
        ("", "空字符串"),
        ("   ", "只有空格"),
        ("\n\n\n", "只有换行"),
    ]
    
    for text, desc in test_cases:
        chunks = strategy.chunk(text)
        status = "✅" if len(chunks) == 0 else "❌"
        print(f"{status} {desc}: {len(chunks)} 个切块")
    
    print()


def test_overlap_strategy():
    """测试重叠策略"""
    print("=" * 60)
    print("🧪 测试 8: 重叠策略")
    print("=" * 60)
    
    text = """# 第一段

这是第一段内容。

# 第二段

这是第二段内容。

# 第三段

这是第三段内容。
"""
    
    strategy = MarkdownChunkStrategy()
    
    # 无重叠
    chunks_no_overlap = strategy.chunk(text, chunk_tokens=30, overlap_tokens=0)
    print(f"✅ 无重叠: {len(chunks_no_overlap)} 个切块")
    
    # 有重叠
    chunks_with_overlap = strategy.chunk(text, chunk_tokens=30, overlap_tokens=10)
    print(f"✅ 有重叠: {len(chunks_with_overlap)} 个切块")
    
    print()


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🚀 开始测试切块策略重构")
    print("=" * 60 + "\n")
    
    test_token_counting()
    test_markdown_chunking()
    test_plain_text_chunking()
    test_factory_pattern()
    test_heading_path_preservation()
    test_chunk_result_format()
    test_empty_text_handling()
    test_overlap_strategy()
    
    print("=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
