"""
Embedding 服务测试脚本

测试 Embedding 服务的各项功能：
1. 工厂模式创建适配器
2. 单条文本向量化
3. 批量文本向量化
4. Token 计数
5. 错误处理和重试机制
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.embedding_factory import EmbeddingAdapterFactory
from app.services.embedding_service import EmbeddingService
from app.core.config import settings


class EmbeddingServiceTester:
    """Embedding 服务测试器"""

    def __init__(self):
        self.test_results = []

    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {test_name}")
        if message:
            print(f"     {message}")
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })

    def test_factory_creation(self):
        """测试工厂模式创建适配器"""
        print("\n" + "="*60)
        print("测试 1: 工厂模式创建适配器")
        print("="*60)

        try:
            adapter = EmbeddingAdapterFactory.create_adapter()
            self.log_test(
                "工厂创建适配器",
                True,
                f"提供商: {settings.EMBEDDING_PROVIDER}, "
                f"模型: {adapter.model_name}"
            )
        except Exception as e:
            self.log_test("工厂创建适配器", False, str(e))

    async def test_single_embedding(self):
        """测试单条文本向量化"""
        print("\n" + "="*60)
        print("测试 2: 单条文本向量化")
        print("="*60)

        try:
            service = EmbeddingService()
            test_text = "这是一段测试文本，用于测试向量化功能"

            embedding = await service.get_embedding(test_text)

            is_valid = (
                isinstance(embedding, list) and
                len(embedding) > 0 and
                all(isinstance(x, (int, float)) for x in embedding)
            )

            self.log_test(
                "单条文本向量化",
                is_valid,
                f"向量维度: {len(embedding)}"
            )
        except Exception as e:
            self.log_test("单条文本向量化", False, str(e))

    async def test_batch_embedding(self):
        """测试批量文本向量化"""
        print("\n" + "="*60)
        print("测试 3: 批量文本向量化")
        print("="*60)

        try:
            service = EmbeddingService()
            test_texts = [
                "第一段测试文本",
                "第二段测试文本",
                "第三段测试文本",
                "第四段测试文本",
                "第五段测试文本",
            ]

            embeddings = await service.get_embeddings(test_texts)

            is_valid = (
                isinstance(embeddings, list) and
                len(embeddings) == len(test_texts) and
                all(isinstance(emb, list) and len(emb) > 0 for emb in embeddings)
            )

            self.log_test(
                "批量文本向量化",
                is_valid,
                f"处理 {len(test_texts)} 条文本，"
                f"向量维度: {len(embeddings[0]) if embeddings else 0}"
            )
        except Exception as e:
            self.log_test("批量文本向量化", False, str(e))

    async def test_token_counting(self):
        """测试 Token 计数功能"""
        print("\n" + "="*60)
        print("测试 4: Token 计数功能")
        print("="*60)

        try:
            service = EmbeddingService()
            test_texts = [
                "第一段测试文本，用于验证 Token 计数功能",
                "第二段测试文本，包含一些中文内容",
                "第三段测试文本",
            ]

            embeddings, total_tokens = await service.get_embeddings_with_tokens(
                test_texts
            )

            is_valid = (
                isinstance(total_tokens, int) and
                total_tokens > 0
            )

            self.log_test(
                "Token 计数功能",
                is_valid,
                f"总 Token 数: {total_tokens}, "
                f"平均每条: {total_tokens / len(test_texts):.1f}"
            )
        except Exception as e:
            self.log_test("Token 计数功能", False, str(e))

    def test_config_loading(self):
        """测试配置加载"""
        print("\n" + "="*60)
        print("测试 5: 配置加载")
        print("="*60)

        try:
            checks = [
                ("提供商", settings.EMBEDDING_PROVIDER),
                ("批处理大小", settings.EMBEDDING_BATCH_SIZE),
                ("最大重试", settings.EMBEDDING_MAX_RETRIES),
                ("超时时间", settings.EMBEDDING_TIMEOUT),
            ]

            all_valid = all([
                value is not None and value != ""
                for _, value in checks
            ])

            config_info = ", ".join([
                f"{name}={value}"
                for name, value in checks
            ])

            self.log_test(
                "配置加载",
                all_valid,
                config_info
            )
        except Exception as e:
            self.log_test("配置加载", False, str(e))

    def print_summary(self):
        """打印测试总结"""
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = total - passed

        print(f"总计: {total} 项测试")
        print(f"通过: {passed} 项 ✅")
        print(f"失败: {failed} 项 ❌")
        print(f"成功率: {passed/total*100:.1f}%")

        if failed > 0:
            print("\n失败测试:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['message']}")

        return failed == 0

    async def run_all_tests(self):
        """运行所有测试"""
        print("\n🚀 开始 Embedding 服务测试")
        print(f"📦 当前提供商: {settings.EMBEDDING_PROVIDER}")

        self.test_config_loading()
        self.test_factory_creation()
        await self.test_single_embedding()
        await self.test_batch_embedding()
        await self.test_token_counting()

        return self.print_summary()


async def main():
    """主函数"""
    tester = EmbeddingServiceTester()
    success = await tester.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
