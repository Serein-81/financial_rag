"""
Phase 8: 性能测试与优化
验证系统性能达标，优化瓶颈
"""

import asyncio
import sys
import time
import psutil
import threading
import uuid  # 修复：添加uuid导入
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User
from app.multi_agent_system import MultiAgentCoordinator  # 修复：使用正确的导入


class PerformanceTester:
    """性能测试器"""
    
    def __init__(self):
        self.db: Session = SessionLocal()
        self.tenant_id = "tenant_perf_test"
        self.user_id = uuid.uuid4()  # 修复：使用UUID而不是整数
        self.results = []
        self.process = psutil.Process()
        
    def setup(self):
        """测试环境准备"""
        print("=" * 80)
        print("Phase 8: 性能测试与优化")
        print("=" * 80)
        
        # 创建测试用户
        user = self.db.query(User).filter(User.id == self.user_id).first()
        if not user:
            user = User(
                id=self.user_id,
                username="perf_test_user",  # 修复：使用正确的字段名
                email="perf@test.com",
                hashed_password="test",
                tenant_id=self.tenant_id
            )
            self.db.add(user)
            self.db.commit()
        
        print(f"✓ 测试租户: {self.tenant_id}")
        print(f"✓ 初始内存: {self.get_memory_usage():.2f} MB")
        
    def get_memory_usage(self):
        """获取当前内存使用（MB）"""
        return self.process.memory_info().rss / 1024 / 1024
        
    async def test_response_time(self):
        """测试响应时间"""
        print("\n" + "=" * 80)
        print("测试 1: 响应时间测试")
        print("=" * 80)
        
        test_cases = [
            {
                "name": "单文档审查",
                "content": "这是一份简单的财务报表，营业收入100万元，净利润30万元。",
                "target": 30,  # 目标时间（秒）
                "query": "请审查这份财务报表"
            },
            {
                "name": "中等文档审查",
                "content": "财务报表：" + "营业收入数据。" * 50,
                "target": 60,
                "query": "请详细审查这份财务报表"
            }
        ]
        
        for test_case in test_cases:
            print(f"\n测试: {test_case['name']}")
            print(f"目标时间: < {test_case['target']}秒")
            
            start_time = time.time()
            start_memory = self.get_memory_usage()
            
            try:
                coordinator = MultiAgentCoordinator(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    db=self.db
                )
                
                result = await coordinator.coordinate_review(
                    query=test_case['query'],
                    documents=[{
                        "content": test_case['content'],
                        "filename": "test.pdf",
                        "doc_type": "financial"
                    }]
                )
                
                end_time = time.time()
                end_memory = self.get_memory_usage()
                
                duration = end_time - start_time
                memory_delta = end_memory - start_memory
                
                passed = duration < test_case['target']
                status_icon = "✓" if passed else "✗"
                
                print(f"{status_icon} 实际时间: {duration:.2f}秒")
                print(f"  内存增量: {memory_delta:.2f} MB")
                
                self.results.append({
                    "test": f"响应时间 - {test_case['name']}",
                    "status": "PASS" if passed else "FAIL",
                    "duration": duration,
                    "target": test_case['target'],
                    "memory_delta": memory_delta
                })
                
            except Exception as e:
                print(f"✗ 测试失败: {str(e)}")
                self.results.append({
                    "test": f"响应时间 - {test_case['name']}",
                    "status": "ERROR",
                    "error": str(e)
                })
                
    async def test_concurrent_requests(self):
        """测试并发请求"""
        print("\n" + "=" * 80)
        print("测试 2: 并发测试")
        print("=" * 80)
        
        concurrent_count = 5  # 并发数
        print(f"并发数: {concurrent_count}")
        
        async def single_request(request_id):
            """单个请求"""
            try:
                coordinator = MultiAgentCoordinator(
                    tenant_id=f"{self.tenant_id}_{request_id}",
                    user_id=self.user_id,
                    db=SessionLocal()
                )
                
                start = time.time()
                result = await coordinator.coordinate_review(
                    query="快速审查",
                    documents=[{
                        "content": f"测试文档 {request_id}",
                        "filename": f"test_{request_id}.pdf",
                        "doc_type": "financial"
                    }]
                )
                duration = time.time() - start
                
                return {
                    "request_id": request_id,
                    "status": "SUCCESS",
                    "duration": duration
                }
            except Exception as e:
                return {
                    "request_id": request_id,
                    "status": "FAILED",
                    "error": str(e)
                }
        
        start_time = time.time()
        start_memory = self.get_memory_usage()
        
        # 并发执行
        tasks = [single_request(i) for i in range(concurrent_count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        end_memory = self.get_memory_usage()
        
        total_duration = end_time - start_time
        memory_delta = end_memory - start_memory
        
        # 统计结果
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "SUCCESS")
        failed_count = concurrent_count - success_count
        
        print(f"\n总耗时: {total_duration:.2f}秒")
        print(f"成功: {success_count}/{concurrent_count}")
        print(f"失败: {failed_count}/{concurrent_count}")
        print(f"内存增量: {memory_delta:.2f} MB")
        
        if success_count > 0:
            avg_duration = sum(r.get("duration", 0) for r in results if isinstance(r, dict) and r.get("status") == "SUCCESS") / success_count
            print(f"平均响应时间: {avg_duration:.2f}秒")
        
        passed = failed_count == 0
        
        self.results.append({
            "test": "并发测试",
            "status": "PASS" if passed else "FAIL",
            "concurrent_count": concurrent_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "total_duration": total_duration,
            "memory_delta": memory_delta
        })
        
    def test_memory_usage(self):
        """测试内存使用"""
        print("\n" + "=" * 80)
        print("测试 3: 内存使用测试")
        print("=" * 80)
        
        initial_memory = self.get_memory_usage()
        print(f"初始内存: {initial_memory:.2f} MB")
        
        # 模拟多次操作
        memory_samples = []
        iterations = 10
        
        for i in range(iterations):
            # 创建一些对象
            data = {
                "iteration": i,
                "content": "测试数据" * 1000
            }
            
            current_memory = self.get_memory_usage()
            memory_samples.append(current_memory)
            
            # 清理
            del data
            
        final_memory = self.get_memory_usage()
        peak_memory = max(memory_samples)
        avg_memory = sum(memory_samples) / len(memory_samples)
        
        print(f"峰值内存: {peak_memory:.2f} MB")
        print(f"平均内存: {avg_memory:.2f} MB")
        print(f"最终内存: {final_memory:.2f} MB")
        print(f"内存增长: {final_memory - initial_memory:.2f} MB")
        
        # 检查内存泄漏（最终内存不应该显著高于初始内存）
        memory_leak = (final_memory - initial_memory) > 100  # 100MB 阈值
        
        if memory_leak:
            print("⚠ 警告: 可能存在内存泄漏")
        else:
            print("✓ 无明显内存泄漏")
        
        self.results.append({
            "test": "内存使用",
            "status": "FAIL" if memory_leak else "PASS",
            "initial_memory": initial_memory,
            "peak_memory": peak_memory,
            "final_memory": final_memory,
            "memory_growth": final_memory - initial_memory
        })
        
    def test_database_performance(self):
        """测试数据库性能"""
        print("\n" + "=" * 80)
        print("测试 4: 数据库性能测试")
        print("=" * 80)
        
        # 测试查询性能
        query_times = []
        
        for i in range(10):
            start = time.time()
            users = self.db.query(User).filter(User.tenant_id == self.tenant_id).all()
            duration = time.time() - start
            query_times.append(duration * 1000)  # 转换为毫秒
        
        avg_query_time = sum(query_times) / len(query_times)
        max_query_time = max(query_times)
        
        print(f"平均查询时间: {avg_query_time:.2f} ms")
        print(f"最大查询时间: {max_query_time:.2f} ms")
        
        # 目标: < 100ms
        passed = avg_query_time < 100
        status_icon = "✓" if passed else "✗"
        print(f"{status_icon} 查询性能: {'达标' if passed else '未达标'}")
        
        self.results.append({
            "test": "数据库性能",
            "status": "PASS" if passed else "FAIL",
            "avg_query_time": avg_query_time,
            "max_query_time": max_query_time,
            "target": 100
        })
        
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 80)
        print("性能测试摘要")
        print("=" * 80)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = total - passed
        
        print(f"\n总测试数: {total}")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"通过率: {passed/total*100:.1f}%")
        
        print("\n详细结果:")
        for i, result in enumerate(self.results, 1):
            status_icon = "✓" if result["status"] == "PASS" else "✗"
            print(f"{i}. {status_icon} {result['test']}: {result['status']}")
            
            if "duration" in result:
                print(f"   耗时: {result['duration']:.2f}秒 (目标: <{result.get('target', 'N/A')}秒)")
            if "memory_delta" in result:
                print(f"   内存: {result['memory_delta']:.2f} MB")
        
        # 性能评级
        if passed == total:
            rating = "A (优秀)"
        elif passed >= total * 0.8:
            rating = "B (良好)"
        else:
            rating = "C (需优化)"
        
        print(f"\n性能评级: {rating}")
        
        # 保存结果
        with open("test_phase8_performance_results.json", "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n✓ 性能测试结果已保存到: test_phase8_performance_results.json")
        
    def cleanup(self):
        """清理测试环境"""
        if self.db:
            self.db.close()
        print("\n✓ 测试环境已清理")


async def main():
    """主测试函数"""
    tester = PerformanceTester()
    
    try:
        tester.setup()
        
        # 运行所有性能测试
        await tester.test_response_time()
        await tester.test_concurrent_requests()
        tester.test_memory_usage()
        tester.test_database_performance()
        
        # 打印摘要
        tester.print_summary()
        
    except Exception as e:
        print(f"\n性能测试执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
