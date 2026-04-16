"""
测试文件解析器重构
验证策略模式 + 工厂模式的实现
"""
import asyncio
from app.parsers.parser_factory import FileParserFactory
from app.parsers import PDFParser, WordParser, TextParser, ImageParser


async def test_factory_pattern():
    """测试工厂模式"""
    print("=" * 60)
    print("🧪 测试 1: 工厂模式 - 获取解析器")
    print("=" * 60)
    
    # 测试获取不同类型的解析器
    test_cases = [
        ("application/pdf", PDFParser),
        ("application/msword", WordParser),
        ("text/plain", TextParser),
        ("image/png", ImageParser),
        ("application/unknown", None)
    ]
    
    for mime_type, expected_class in test_cases:
        parser = FileParserFactory.get_parser(mime_type)
        if expected_class is None:
            status = "✅" if parser is None else "❌"
            print(f"{status} {mime_type}: {'不支持' if parser is None else '错误支持'}")
        else:
            status = "✅" if isinstance(parser, expected_class) else "❌"
            print(f"{status} {mime_type}: {parser.__class__.__name__}")
    
    print()


async def test_supported_types():
    """测试支持的文件类型列表"""
    print("=" * 60)
    print("🧪 测试 2: 获取所有支持的文件类型")
    print("=" * 60)
    
    supported_types = FileParserFactory.get_supported_types()
    print(f"✅ 共支持 {len(supported_types)} 种文件类型:")
    for mime_type in supported_types:
        print(f"   - {mime_type}")
    
    print()


async def test_parser_registration():
    """测试动态注册新解析器"""
    print("=" * 60)
    print("🧪 测试 3: 动态注册新解析器")
    print("=" * 60)
    
    from app.parsers.base_parser import FileParserStrategy
    
    # 创建一个自定义解析器
    class CustomParser(FileParserStrategy):
        def get_supported_mime_types(self) -> list[str]:
            return ["application/custom"]
        
        async def parse(self, file_bytes: bytes) -> str:
            return "Custom parser content"
    
    # 注册自定义解析器
    custom_parser = CustomParser()
    FileParserFactory.register_parser(custom_parser)
    
    # 验证注册成功
    parser = FileParserFactory.get_parser("application/custom")
    if isinstance(parser, CustomParser):
        print("✅ 自定义解析器注册成功")
        content = await parser.parse(b"test")
        print(f"✅ 解析结果: {content}")
    else:
        print("❌ 自定义解析器注册失败")
    
    print()


async def test_text_parser():
    """测试文本解析器"""
    print("=" * 60)
    print("🧪 测试 4: 文本解析器")
    print("=" * 60)
    
    parser = FileParserFactory.get_parser("text/plain")
    
    # 测试 UTF-8 编码
    test_content = "这是一个测试文本\nHello World"
    file_bytes = test_content.encode('utf-8')
    
    try:
        result = await parser.parse(file_bytes)
        print(f"✅ UTF-8 解析成功:")
        print(f"   {result}")
    except Exception as e:
        print(f"❌ UTF-8 解析失败: {e}")
    
    # 测试 GBK 编码
    file_bytes_gbk = test_content.encode('gbk')
    try:
        result = await parser.parse(file_bytes_gbk)
        print(f"✅ GBK 解析成功:")
        print(f"   {result}")
    except Exception as e:
        print(f"❌ GBK 解析失败: {e}")
    
    print()


async def test_error_handling():
    """测试错误处理"""
    print("=" * 60)
    print("🧪 测试 5: 错误处理")
    print("=" * 60)
    
    # 测试空文件
    parser = FileParserFactory.get_parser("text/plain")
    try:
        await parser.parse(b"")
        print("❌ 空文件应该抛出异常")
    except ValueError as e:
        print(f"✅ 空文件正确抛出异常: {e}")
    
    # 测试不支持的类型
    parser = FileParserFactory.get_parser("application/unknown")
    if parser is None:
        print("✅ 不支持的类型返回 None")
    else:
        print("❌ 不支持的类型应该返回 None")
    
    print()


async def test_file_service_integration():
    """测试与 FileService 的集成"""
    print("=" * 60)
    print("🧪 测试 6: FileService 集成")
    print("=" * 60)
    
    from app.services.file_service import file_service
    
    # 测试支持的类型检查
    test_cases = [
        ("application/pdf", True),
        ("text/plain", True),
        ("application/unknown", False)
    ]
    
    for mime_type, expected in test_cases:
        result = file_service.is_supported_type(mime_type)
        status = "✅" if result == expected else "❌"
        print(f"{status} {mime_type}: {'支持' if result else '不支持'}")
    
    # 测试获取支持的类型列表
    supported = file_service.get_supported_types()
    print(f"✅ FileService 支持 {len(supported)} 种文件类型")
    
    print()


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🚀 开始测试文件解析器重构（策略模式 + 工厂模式）")
    print("=" * 60 + "\n")
    
    await test_factory_pattern()
    await test_supported_types()
    await test_parser_registration()
    await test_text_parser()
    await test_error_handling()
    await test_file_service_integration()
    
    print("=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
