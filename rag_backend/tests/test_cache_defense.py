"""
缓存防御功能测试脚本

测试三个缓存问题的防御机制：
1. 缓存穿透防御（NULL Cache）
2. 缓存击穿防御（互斥锁）
3. 缓存雪崩防御（随机 TTL）
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.resource_manager import ResourceManager
from app.memory_system.memory_cache import MemoryCache, NULL_CACHE_MARKER, NULL_CACHE_TTL

resource_manager: ResourceManager = None


async def init_resource_manager():
    """初始化 ResourceManager"""
    global resource_manager
    try:
        from app.core.resource_manager import ResourceManager
        import app.core.resource_manager as rm_module
        
        resource_manager = ResourceManager()
        await resource_manager.initialize()
        
        rm_module._resource_manager_instance = resource_manager
        
        print("[OK] ResourceManager 初始化成功")
        return True
    except Exception as e:
        print(f"[WARNING] ResourceManager 初始化失败: {e}")
        return False


async def cleanup_resource_manager():
    """清理 ResourceManager"""
    global resource_manager
    if resource_manager is not None:
        try:
            import app.core.resource_manager as rm_module
            rm_module._resource_manager_instance = None
            
            await resource_manager.close()
            print("[OK] ResourceManager 清理完成")
        except Exception as e:
            print(f"[WARNING] ResourceManager 清理失败: {e}")
        finally:
            resource_manager = None


class TestResults:
    """测试结果收集器"""
    
    def __init__(self):
        self.passed = []
        self.failed = []
    
    def add_pass(self, test_name: str, message: str = ""):
        self.passed.append((test_name, message))
        print(f"[OK] {test_name} - {message}")
    
    def add_fail(self, test_name: str, message: str):
        self.failed.append((test_name, message))
        print(f"[FAIL] {test_name} - {message}")
    
    def summary(self):
        total = len(self.passed) + len(self.failed)
        print("\n" + "=" * 80)
        print("测试总结")
        print("=" * 80)
        print(f"总计: {total} | 通过: {len(self.passed)} | 失败: {len(self.failed)}")
        if self.failed:
            print("\n失败的测试:")
            for name, msg in self.failed:
                print(f"  - {name}: {msg}")
        print("=" * 80)
        return len(self.failed) == 0


async def test_null_cache_marker_exists():
    """测试1: 验证 NULL_CACHE_MARKER 常量存在"""
    print("\n[测试 1] 验证空值缓存标记常量")
    print("-" * 80)
    
    results = TestResults()
    
    try:
        assert NULL_CACHE_MARKER == "__NULL__", "NULL_CACHE_MARKER 值不正确"
        results.add_pass("常量存在性", f"NULL_CACHE_MARKER = '{NULL_CACHE_MARKER}'")
    except AssertionError as e:
        results.add_fail("常量存在性", str(e))
    
    try:
        assert NULL_CACHE_TTL == 60, "NULL_CACHE_TTL 值不正确"
        results.add_pass("TTL 常量", f"NULL_CACHE_TTL = {NULL_CACHE_TTL}s")
    except AssertionError as e:
        results.add_fail("TTL 常量", str(e))
    
    return results


async def test_randomized_ttl():
    """测试2: 验证随机化 TTL 功能（缓存雪崩防御）"""
    print("\n[测试 2] 验证随机化 TTL 功能（缓存雪崩防御）")
    print("-" * 80)
    
    results = TestResults()
    cache = MemoryCache()
    
    try:
        ttls = [cache._get_randomized_ttl() for _ in range(100)]
        
        base_ttl = cache._ttl
        min_expected = int(base_ttl * 0.5)
        max_expected = int(base_ttl * 1.1)
        
        all_in_range = all(min_expected <= ttl <= max_expected for ttl in ttls)
        
        if all_in_range:
            results.add_pass("TTL 范围", f"所有 TTL 在 {min_expected}-{max_expected}s 范围内")
        else:
            out_of_range = [ttl for ttl in ttls if not (min_expected <= ttl <= max_expected)]
            results.add_fail("TTL 范围", f"{len(out_of_range)} 个 TTL 超出范围")
        
        unique_ttls = len(set(ttls))
        if unique_ttls > 1:
            results.add_pass("TTL 随机性", f"100 次调用产生 {unique_ttls} 个不同的 TTL 值")
        else:
            results.add_fail("TTL 随机性", "TTL 值不够随机")
        
    except Exception as e:
        results.add_fail("随机化 TTL", f"异常: {str(e)}")
    
    return results


async def test_per_key_lock():
    """测试3: 验证 per-key 锁机制（缓存击穿防御）"""
    print("\n[测试 3] 验证 per-key 锁机制（缓存击穿防御）")
    print("-" * 80)
    
    results = TestResults()
    cache = MemoryCache()
    
    try:
        lock1 = cache._get_key_lock("session1", "short_term")
        lock2 = cache._get_key_lock("session1", "short_term")
        
        assert lock1 is lock2, "相同 key 应返回同一锁对象"
        results.add_pass("锁复用", "相同 session_id 和 memory_type 返回同一锁对象")
        
        lock3 = cache._get_key_lock("session1", "long_term")
        assert lock1 is not lock3, "不同 memory_type 应返回不同锁对象"
        results.add_pass("细粒度锁", "不同 memory_type 返回不同锁对象")
        
        lock4 = cache._get_key_lock("session2", "short_term")
        assert lock1 is not lock4, "不同 session_id 应返回不同锁对象"
        results.add_pass("会话隔离", "不同 session_id 返回不同锁对象")
        
    except AssertionError as e:
        results.add_fail("锁机制", f"断言失败: {str(e)}")
    except Exception as e:
        results.add_fail("锁机制", f"异常: {str(e)}")
    
    return results


async def test_set_null_cache():
    """测试4: 验证 set_null_cache 方法（缓存穿透防御）"""
    print("\n[测试 4] 验证空值缓存写入功能（缓存穿透防御）")
    print("-" * 80)
    
    results = TestResults()
    
    if resource_manager is None:
        results.add_fail("空值缓存写入", "ResourceManager 未初始化，跳过测试")
        return results
    
    cache = MemoryCache(resource_manager.redis)
    
    test_session_id = f"test_null_cache_{datetime.now().timestamp()}"
    test_memory_type = "short_term"
    
    try:
        success = await cache.set_null_cache(test_session_id, test_memory_type)
        
        if success:
            results.add_pass("空值缓存写入", "set_null_cache 方法调用成功")
            
            cached = await cache.get_memories(test_session_id, test_memory_type)
            
            if cached == []:
                results.add_pass("空值缓存读取", f"查询返回空列表（检测到 {NULL_CACHE_MARKER}）")
            else:
                results.add_fail("空值缓存读取", f"期望空列表，实际: {cached}")
            
            await cache.invalidate(test_session_id, test_memory_type)
            results.add_pass("缓存清理", "测试后清理完成")
        else:
            results.add_fail("空值缓存写入", "set_null_cache 方法返回 False")
            
    except Exception as e:
        results.add_fail("空值缓存测试", f"异常: {str(e)}")
    
    return results


async def test_empty_memories_cache():
    """测试5: 验证空记忆列表缓存（缓存穿透防御）"""
    print("\n[测试 5] 验证空记忆列表缓存（缓存穿透防御）")
    print("-" * 80)
    
    results = TestResults()
    
    if resource_manager is None:
        results.add_fail("空列表缓存", "ResourceManager 未初始化，跳过测试")
        return results
    
    cache = MemoryCache(resource_manager.redis)
    
    test_session_id = f"test_empty_cache_{datetime.now().timestamp()}"
    test_memory_type = "all"
    
    try:
        success = await cache.set_memories(test_session_id, [], test_memory_type)
        
        if success:
            results.add_pass("空列表缓存", "set_memories 接受空列表并返回成功")
            
            cached = await cache.get_memories(test_session_id, test_memory_type)
            
            if cached == []:
                results.add_pass("空列表读取", "查询空记忆返回空列表（NULL Cache 防御生效）")
            else:
                results.add_fail("空列表读取", f"期望空列表，实际: {cached}")
            
            await cache.invalidate(test_session_id, test_memory_type)
            results.add_pass("缓存清理", "测试后清理完成")
        else:
            results.add_fail("空列表缓存", "set_memories 对空列表返回失败")
            
    except Exception as e:
        results.add_fail("空列表缓存测试", f"异常: {str(e)}")
    
    return results


async def main():
    """主测试函数"""
    print("=" * 80)
    print("缓存防御功能测试套件")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version}")
    
    await init_resource_manager()
    
    try:
        all_results = []
        test_results_1 = await test_null_cache_marker_exists()
        all_results.append(test_results_1)
        
        test_results_2 = await test_randomized_ttl()
        all_results.append(test_results_2)
        
        test_results_3 = await test_per_key_lock()
        all_results.append(test_results_3)
        
        test_results_4 = await test_set_null_cache()
        all_results.append(test_results_4)
        
        test_results_5 = await test_empty_memories_cache()
        all_results.append(test_results_5)
        
        final_results = TestResults()
        for results in all_results:
            for test_name, msg in results.passed:
                final_results.passed.append((test_name, msg))
            for test_name, msg in results.failed:
                final_results.failed.append((test_name, msg))
        
        success = final_results.summary()
        
        return 0 if success else 1
    finally:
        await cleanup_resource_manager()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
