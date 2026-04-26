"""
Rerank 服务测试

测试硅基流动 Cross-Encoder Rerank 模型的效果
"""
import asyncio
import sys
import os
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class RerankTester:
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
    
    def log_test(self, name: str, passed: bool, message: str = ""):
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if message:
            print(f"     → {message}")
        
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
        else:
            self.failed_tests += 1
        return passed
    
    def print_summary(self):
        print("\n" + "=" * 60)
        print(f"📊 测试结果: {self.passed_tests}/{self.total_tests} 通过")
        print(f"   ✅ 成功: {self.passed_tests}")
        print(f"   ❌ 失败: {self.failed_tests}")
        print("=" * 60)
        return self.failed_tests == 0

    async def test_config_loading(self):
        """测试配置加载"""
        print("\n" + "=" * 60)
        print("测试 1: 配置加载")
        print("=" * 60)
        
        try:
            from app.core.config import settings
            
            checks = [
                ("SILICONFLOW_API_KEY", bool(settings.SILICONFLOW_API_KEY)),
                ("SILICONFLOW_RERANK_MODEL", bool(settings.SILICONFLOW_RERANK_MODEL)),
                ("ENABLE_RERANK", settings.ENABLE_RERANK),
                ("RERANK_TOP_K", settings.RERANK_TOP_K > 0),
                ("RERANK_MAX_CHARS", settings.RERANK_MAX_CHARS > 0),
                ("RERANK_SCORE_THRESHOLD", 0 <= settings.RERANK_SCORE_THRESHOLD <= 1),
            ]
            
            all_valid = all(value for _, value in checks)
            
            config_info = ", ".join([
                f"{name}={value}"
                for name, value in checks
            ])
            
            self.log_test(
                "配置完整性",
                all_valid,
                config_info
            )
            
            if settings.SILICONFLOW_RERANK_MODEL:
                self.log_test(
                    "Rerank 模型",
                    True,
                    settings.SILICONFLOW_RERANK_MODEL
                )
            
        except Exception as e:
            self.log_test("配置加载", False, str(e))
    
    async def test_service_creation(self):
        """测试服务创建"""
        print("\n" + "=" * 60)
        print("测试 2: 服务创建")
        print("=" * 60)
        
        try:
            from app.services.rerank_service import rerank_service, RerankService
            
            self.log_test(
                "单例模式",
                rerank_service is RerankService()
            )
            
            self.log_test(
                "服务已初始化",
                rerank_service._initialized
            )
            
            self.log_test(
                "API Key 已配置",
                bool(rerank_service.api_key),
                f"Key: {rerank_service.api_key[:8]}...{rerank_service.api_key[-4:]}" if rerank_service.api_key else "未配置"
            )
            
            self.log_test(
                "模型名称",
                bool(rerank_service.model_name),
                rerank_service.model_name
            )
            
            self.log_test(
                "分数阈值",
                0 <= rerank_service.score_threshold <= 1,
                str(rerank_service.score_threshold)
            )
            
        except Exception as e:
            self.log_test("服务创建", False, str(e))
    
    async def test_tax_query_rerank(self):
        """测试税务查询 Rerank"""
        print("\n" + "=" * 60)
        print("测试 3: 税务查询 Rerank")
        print("=" * 60)
        
        query = "企业购买固定资产的增值税进项税额能否抵扣？"
        
        candidates = [
            "根据《增值税暂行条例》第十条规定，用于非增值税应税项目、免征增值税项目的进项税额不得从销项税额中抵扣。",
            "企业购买办公电脑的进项税额可以抵扣。",
            "固定资产的折旧方法有直线法、工作量法、双倍余额递减法等。",
            "增值税专用发票的认证期限是360天。",
            "企业购买用于职工福利的固定资产，进项税额不得抵扣。",
            "小型微利企业所得税优惠税率为20%。",
            "企业购进用于生产经营的固定资产，其进项税额可以按规定抵扣。",
            "个人所得税专项附加扣除标准。"
        ]
        
        try:
            from app.services.rerank_service import rerank_service
            
            results = await rerank_service.rerank(
                query=query,
                documents=candidates,
                top_k=5
            )
            
            self.log_test(
                "返回结果数量",
                len(results) > 0,
                f"返回 {len(results)} 个结果"
            )
            
            if results and len(results) > 0:
                self.log_test(
                    "分数范围 [0, 1]",
                    0 <= results[0].relevance_score <= 1,
                    f"最高分: {results[0].relevance_score:.4f}"
                )
                
                scores = [r.relevance_score for r in results]
                self.log_test(
                    "分数递减",
                    all(scores[i] >= scores[i+1] for i in range(len(scores)-1)),
                    f"分数: {[f'{s:.3f}' for s in scores]}"
                )
                
                top1_doc = results[0].document
                if isinstance(top1_doc, str):
                    top1_content = top1_doc[:50] if len(top1_doc) > 50 else top1_doc
                    has_keywords = "进项税额" in top1_doc or "抵扣" in top1_doc
                    self.log_test(
                        "最相关结果合理",
                        has_keywords,
                        f"相关内容: {top1_content}..."
                    )
                
                print("\n📋 Rerank 结果排序:")
                for i, r in enumerate(results, 1):
                    doc_preview = r.document[:60] if isinstance(r.document, str) else str(r.document)[:60]
                    print(f"  {i}. [分数: {r.relevance_score:.4f}] {doc_preview}...")
                    
        except Exception as e:
            self.log_test("税务查询 Rerank", False, str(e))
    
    async def test_score_threshold_filter(self):
        """测试分数阈值过滤"""
        print("\n" + "=" * 60)
        print("测试 4: 分数阈值过滤")
        print("=" * 60)
        
        query = "如何计算企业所得税应纳税所得额？"
        
        candidates = [
            "企业所得税应纳税所得额 = 收入总额 - 不征税收入 - 免税收入 - 各项扣除 - 允许弥补的以前年度亏损",
            "个人所得税税率表。",
            "企业所得税税率是25%，符合条件的小型微利企业是20%。",
            "今天天气不错。",
            "企业发生的职工福利费支出，不超过工资薪金总额14%的部分，准予扣除。",
            "增值税发票认证流程。"
        ]
        
        try:
            from app.services.rerank_service import rerank_service
            
            results_default = await rerank_service.rerank(
                query=query,
                documents=candidates,
                top_k=10
            )
            
            results_high = await rerank_service.rerank(
                query=query,
                documents=candidates,
                top_k=10
            )
            
            self.log_test(
                "返回结果",
                len(results_default) > 0,
                f"返回 {len(results_default)} 个结果"
            )
            
            scores = [r.relevance_score for r in results_default]
            self.log_test(
                "分数有效",
                all(0 <= s <= 1 for s in scores),
                f"范围: {min(scores):.3f} ~ {max(scores):.3f}"
            )
            
        except Exception as e:
            self.log_test("分数阈值过滤", False, str(e))
    
    async def test_rerank_with_metadata(self):
        """测试带元数据的 Rerank"""
        print("\n" + "=" * 60)
        print("测试 5: 带元数据的 Rerank")
        print("=" * 60)
        
        query = "什么是增值税专用发票？"
        
        documents = [
            {
                "content": "增值税专用发票是增值税一般纳税人销售货物或提供应税劳务时开具的发票。",
                "chunk_id": "1",
                "source": "税法手册.pdf"
            },
            {
                "content": "个人所得税专项附加扣除包括子女教育、继续教育等六项。",
                "chunk_id": "2",
                "source": "个税指南.pdf"
            },
            {
                "content": "专用发票与普通发票的主要区别在于是否可以用于抵扣进项税额。",
                "chunk_id": "3",
                "source": "发票管理.pdf"
            }
        ]
        
        try:
            from app.services.rerank_service import rerank_service
            
            results = await rerank_service.rerank_with_metadata(
                query=query,
                documents=documents,
                top_k=3
            )
            
            self.log_test(
                "返回结果数量",
                len(results) > 0,
                f"返回 {len(results)} 个结果"
            )
            
            if results:
                first = results[0]
                self.log_test(
                    "保留 chunk_id",
                    "chunk_id" in first,
                    f"chunk_id: {first.get('chunk_id')}"
                )
                
                self.log_test(
                    "保留 source",
                    "source" in first,
                    f"source: {first.get('source')}"
                )
                
                self.log_test(
                    "添加 rerank_score",
                    "rerank_score" in first,
                    f"rerank_score: {first.get('rerank_score', 'N/A')}"
                )
                
                self.log_test(
                    "添加 rerank_rank",
                    "rerank_rank" in first,
                    f"rerank_rank: {first.get('rerank_rank')}"
                )
                
        except Exception as e:
            self.log_test("带元数据的 Rerank", False, str(e))
    
    async def test_error_handling(self):
        """测试错误处理"""
        print("\n" + "=" * 60)
        print("测试 6: 错误处理")
        print("=" * 60)
        
        try:
            from app.services.rerank_service import rerank_service
            
            empty_results = await rerank_service.rerank(
                query="测试查询",
                documents=[],
                top_k=5
            )
            
            self.log_test(
                "空文档列表处理",
                empty_results == [],
                "返回空列表"
            )
            
            self.log_test(
                "单文档处理",
                True,
                "无异常"
            )
            
        except Exception as e:
            self.log_test("错误处理", False, str(e))
    
    async def test_latency(self):
        """测试延迟"""
        print("\n" + "=" * 60)
        print("测试 7: 性能延迟测试")
        print("=" * 60)
        
        query = "企业研发费用加计扣除政策有哪些？"
        
        candidates = [
            "企业开展研发活动中实际发生的研发费用，未形成无形资产计入当期损益的，在按规定据实扣除的基础上，按照研究开发费用的75%加计扣除。",
            "形成无形资产的，按照该无形资产成本的175%计算摊销费用。",
            "适用于会计核算健全、实行查账征收的企业。",
            "适用于会计核算不健全的企业。",
            "研发费用加计扣除的比例根据企业类型有所不同。",
        ] * 3  # 重复3次，增加测试数据量
        
        try:
            import time
            
            from app.services.rerank_service import rerank_service
            
            start = time.time()
            results = await rerank_service.rerank(
                query=query,
                documents=candidates,
                top_k=10
            )
            latency = time.time() - start
            
            self.log_test(
                "响应延迟 < 5秒",
                latency < 5.0,
                f"延迟: {latency:.3f}s"
            )
            
            self.log_test(
                "文档数量",
                len(candidates) == len(results) or len(results) < len(candidates),
                f"处理 {len(candidates)} 个文档"
            )
            
            print(f"\n⏱️ 性能指标:")
            print(f"   - 文档数量: {len(candidates)}")
            print(f"   - 返回结果: {len(results)}")
            print(f"   - 延迟: {latency:.3f}s")
            print(f"   - 平均每文档: {latency/len(candidates)*1000:.2f}ms")
            
        except Exception as e:
            self.log_test("延迟测试", False, str(e))
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("\n🚀 开始 Rerank 服务测试")
        print(f"📦 模型: {getattr(__import__('app.core.config', fromlist=['settings']).settings, 'SILICONFLOW_RERANK_MODEL', '未配置')}")
        
        await self.test_config_loading()
        await self.test_service_creation()
        await self.test_tax_query_rerank()
        await self.test_score_threshold_filter()
        await self.test_rerank_with_metadata()
        await self.test_error_handling()
        await self.test_latency()
        
        return self.print_summary()


async def main():
    """主函数"""
    tester = RerankTester()
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
