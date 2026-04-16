"""
异步任务处理模块测试

测试三层防护机制、熔断器和任务调度器
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

from app.tasks.three_layer_protection import (
    ThreeLayerProtection,
    TimeoutProtection,
    RetryProtection,
    ResourceProtection,
    ProtectionResult,
    ProtectionStatus,
)
from app.tasks.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
)
from app.tasks.task_scheduler import (
    TaskScheduler,
    TaskConfig,
    TaskStatus,
)


class TestProtectionResult:
    """测试防护结果"""
    
    def test_create_success_result(self):
        """测试创建成功结果"""
        result = ProtectionResult(
            status=ProtectionStatus.SUCCESS,
            result={"data": "test"},
            execution_time_ms=100.0
        )
        
        assert result.is_success()
        assert result.result == {"data": "test"}
        assert result.status == ProtectionStatus.SUCCESS
    
    def test_create_error_result(self):
        """测试创建错误结果"""
        result = ProtectionResult(
            status=ProtectionStatus.TIMEOUT,
            error="Task timeout",
            execution_time_ms=30000.0,
            timeout_occurred=True  # 需要显式设置
        )
        
        assert not result.is_success()
        assert result.error == "Task timeout"
        assert result.timeout_occurred
    
    def test_to_dict(self):
        """测试转换为字典"""
        result = ProtectionResult(
            status=ProtectionStatus.SUCCESS,
            result={"data": "test"},
            execution_time_ms=100.0
        )
        
        data = result.to_dict()
        
        assert "status" in data
        assert "result" in data
        assert "execution_time_ms" in data


class TestTimeoutProtection:
    """测试超时保护"""
    
    def test_create_timeout_protection(self):
        """测试创建超时保护"""
        protection = TimeoutProtection(
            default_timeout=10.0,
            timeout_strategy="cancel"
        )
        
        assert protection.default_timeout == 10.0
        assert protection.timeout_strategy == "cancel"
    
    @pytest.mark.asyncio
    async def test_execute_success(self):
        """测试成功执行"""
        protection = TimeoutProtection(default_timeout=5.0)
        
        async def quick_task():
            return "success"
        
        result = await protection.execute(quick_task(), timeout=5.0, task_id="test-1")
        
        assert result.is_success()
        assert result.result == "success"
        assert not result.timeout_occurred
    
    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """测试超时"""
        protection = TimeoutProtection(default_timeout=0.5)
        
        async def slow_task():
            await asyncio.sleep(2.0)
            return "done"
        
        result = await protection.execute(slow_task(), timeout=0.5, task_id="test-2")
        
        assert not result.is_success()
        assert result.status == ProtectionStatus.TIMEOUT
        assert result.timeout_occurred


class TestRetryProtection:
    """测试重试保护"""
    
    def test_create_retry_protection(self):
        """测试创建重试保护"""
        protection = RetryProtection(
            max_retries=5,
            base_delay=0.1,
            max_delay=1.0
        )
        
        assert protection.max_retries == 5
        assert protection.base_delay == 0.1
        assert protection.max_delay == 1.0
    
    @pytest.mark.asyncio
    async def test_execute_success_first_try(self):
        """测试首次尝试成功"""
        protection = RetryProtection(max_retries=3)
        
        async def task():
            return "success"
        
        result = await protection.execute(task(), task_id="test-1")
        
        assert result.is_success()
        assert result.result == "success"
        assert result.attempts == 1
        assert result.retry_count == 0
    
    @pytest.mark.asyncio
    async def test_execute_retry_on_failure(self):
        """测试失败后重试"""
        protection = RetryProtection(
            max_retries=3,
            base_delay=0.01,
            retry_on=[ValueError]
        )
        
        attempt_count = 0
        
        async def flaky_task():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = await protection.execute(flaky_task(), task_id="test-2")
        
        assert result.is_success()
        assert result.attempts == 3
        assert result.retry_count == 2
    
    def test_calculate_delay(self):
        """测试延迟计算"""
        protection = RetryProtection(
            base_delay=1.0,
            exponential_base=2.0,
            max_delay=10.0
        )
        
        assert protection._calculate_delay(0) == 1.0
        assert protection._calculate_delay(1) == 2.0
        assert protection._calculate_delay(2) == 4.0
        assert protection._calculate_delay(3) == 8.0
        assert protection._calculate_delay(4) == 10.0  # 不超过 max_delay


class TestResourceProtection:
    """测试资源保护"""
    
    def test_create_resource_protection(self):
        """测试创建资源保护"""
        protection = ResourceProtection(
            max_concurrent_tasks=50,
            max_memory_mb=1024
        )
        
        assert protection.max_concurrent_tasks == 50
        assert protection.max_memory_mb == 1024
    
    @pytest.mark.asyncio
    async def test_execute_success(self):
        """测试成功执行"""
        protection = ResourceProtection(max_concurrent_tasks=100)
        
        async def task():
            return "success"
        
        result = await protection.execute(task(), task_id="test-1")
        
        assert result.is_success()
        assert result.result == "success"


class TestThreeLayerProtection:
    """测试三层防护组合"""
    
    def test_create_combined_protection(self):
        """测试创建组合防护"""
        protection = ThreeLayerProtection(
            timeout=30.0,
            max_retries=3,
            max_concurrent=100
        )
        
        assert protection.timeout_protection.default_timeout == 30.0
        assert protection.retry_protection.max_retries == 3
        assert protection.resource_protection.max_concurrent_tasks == 100
    
    def test_enable_disable_layer(self):
        """测试启用/禁用防护层"""
        protection = ThreeLayerProtection()
        
        protection.disable_layer("timeout")
        assert not protection.enabled_layers["timeout"]
        
        protection.enable_layer("timeout")
        assert protection.enabled_layers["timeout"]
    
    def test_get_stats(self):
        """测试获取统计"""
        protection = ThreeLayerProtection()
        
        stats = protection.get_stats()
        
        assert "enabled_layers" in stats
        assert "timeout_config" in stats
        assert "retry_config" in stats
        assert "resource_config" in stats


class TestCircuitBreaker:
    """测试熔断器"""
    
    def test_create_circuit_breaker(self):
        """测试创建熔断器"""
        cb = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout=60.0
            )
        )
        
        assert cb.name == "test"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.config.failure_threshold == 5
    
    def test_should_allow_request_closed(self):
        """测试关闭状态允许请求"""
        cb = CircuitBreaker(name="test")
        
        assert cb._should_allow_request()
    
    @pytest.mark.asyncio
    async def test_execute_success(self):
        """测试成功执行"""
        cb = CircuitBreaker(name="test")
        
        async def task():
            return "success"
        
        result = await cb.execute(task)
        
        assert result == "success"
        assert cb.stats.successful_calls == 1
        assert cb.stats.consecutive_successes == 1
    
    @pytest.mark.asyncio
    async def test_execute_failure_opens_circuit(self):
        """测试失败打开熔断器"""
        cb = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(failure_threshold=2)
        )
        
        async def failing_task():
            raise ValueError("Test error")
        
        # 第一次失败
        await cb.execute(failing_task)
        assert cb.state == CircuitBreakerState.CLOSED
        
        # 第二次失败
        await cb.execute(failing_task)
        assert cb.state == CircuitBreakerState.OPEN
    
    @pytest.mark.asyncio
    async def test_rejected_when_open(self):
        """测试打开状态拒绝请求"""
        cb = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(failure_threshold=1, timeout=0.1)
        )
        
        # 打开熔断器
        async def failing_task():
            raise ValueError("Test error")
        
        await cb.execute(failing_task)
        assert cb.state == CircuitBreakerState.OPEN
        
        # 应该被拒绝
        with pytest.raises(CircuitBreakerOpenError):
            await cb.execute(failing_task)
        
        assert cb.stats.rejected_calls >= 1
    
    @pytest.mark.asyncio
    async def test_reset_circuit_breaker(self):
        """测试重置熔断器"""
        cb = CircuitBreaker(
            name="test",
            config=CircuitBreakerConfig(failure_threshold=1)
        )
        
        # 打开熔断器
        async def failing_task():
            raise ValueError("Test error")
        
        await cb.execute(failing_task)
        assert cb.state == CircuitBreakerState.OPEN
        
        # 重置
        await cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.stats.total_calls == 0
    
    def test_get_status(self):
        """测试获取状态"""
        cb = CircuitBreaker(name="test")
        
        status = cb.get_status()
        
        assert status["name"] == "test"
        assert status["state"] == "closed"
        assert "stats" in status
        assert "config" in status


class TestCircuitBreakerRegistry:
    """测试熔断器注册表"""
    
    @pytest.mark.asyncio
    async def test_get_or_create(self):
        """测试获取或创建"""
        registry = CircuitBreakerRegistry()
        
        cb1 = await registry.get_or_create("test-breaker")
        cb2 = await registry.get_or_create("test-breaker")
        
        assert cb1 is cb2
        assert cb1.name == "test-breaker"
    
    @pytest.mark.asyncio
    async def test_get_all_status(self):
        """测试获取所有状态"""
        registry = CircuitBreakerRegistry()
        
        await registry.get_or_create("breaker-1")
        await registry.get_or_create("breaker-2")
        
        statuses = await registry.get_all_status()
        
        assert len(statuses) == 2


class TestTaskScheduler:
    """测试任务调度器"""
    
    def test_create_scheduler(self):
        """测试创建调度器"""
        scheduler = TaskScheduler(
            max_workers=10,
            default_timeout=30.0
        )
        
        assert scheduler.max_workers == 10
        assert scheduler.default_timeout == 30.0
        assert not scheduler._running
    
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """测试启动和停止"""
        scheduler = TaskScheduler()
        
        await scheduler.start()
        assert scheduler._running
        assert scheduler._scheduler_task is not None
        
        await scheduler.stop()
        assert not scheduler._running
    
    @pytest.mark.asyncio
    async def test_add_task(self):
        """测试添加任务"""
        scheduler = TaskScheduler()
        await scheduler.start()
        
        async def sample_task():
            return "result"
        
        task_id = await scheduler.add_task(
            task_type="test",
            coro_func=sample_task,
            request_id="req-001",
            tenant_id="tenant-001",
            user_id="user-001",
            config=TaskConfig(priority=5, timeout=5.0)
        )
        
        assert task_id is not None
        assert len(task_id) > 0
        
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_get_task_status(self):
        """测试获取任务状态"""
        scheduler = TaskScheduler()
        await scheduler.start()
        
        async def sample_task():
            await asyncio.sleep(0.01)
            return "result"
        
        task_id = await scheduler.add_task(
            task_type="test",
            coro_func=sample_task,
            request_id="req-001",
            tenant_id="tenant-001",
            user_id="user-001"
        )
        
        # 等待任务完成
        await asyncio.sleep(0.1)
        
        status = scheduler.get_task_status(task_id)
        
        assert status is not None
        assert status.task_id == task_id
        
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """测试取消任务"""
        scheduler = TaskScheduler()
        await scheduler.start()
        
        async def long_task():
            await asyncio.sleep(10.0)
            return "done"
        
        task_id = await scheduler.add_task(
            task_type="test",
            coro_func=long_task,
            request_id="req-001",
            tenant_id="tenant-001",
            user_id="user-001"
        )
        
        # 取消任务
        cancelled = await scheduler.cancel_task(task_id)
        
        assert cancelled
        
        status = scheduler.get_task_status(task_id)
        assert status.status == TaskStatus.CANCELLED
        
        await scheduler.stop()
    
    def test_get_stats(self):
        """测试获取统计"""
        scheduler = TaskScheduler(max_workers=10)
        
        stats = scheduler.get_stats()
        
        assert "scheduler" in stats
        assert "tasks" in stats
        assert "concurrency" in stats
        assert stats["scheduler"]["max_workers"] == 10
    
    def test_priority_queue_order(self):
        """测试优先级队列顺序"""
        scheduler = TaskScheduler()
        
        async def dummy_task():
            pass
        
        # 添加不同优先级的任务
        task1_id = asyncio.run(scheduler.add_task(
            "test", dummy_task, "req-1", "t1", "u1",
            config=TaskConfig(priority=5)
        ))
        task2_id = asyncio.run(scheduler.add_task(
            "test", dummy_task, "req-2", "t1", "u1",
            config=TaskConfig(priority=1)
        ))
        task3_id = asyncio.run(scheduler.add_task(
            "test", dummy_task, "req-3", "t1", "u1",
            config=TaskConfig(priority=10)
        ))
        
        # 优先级1应该先被处理
        assert scheduler._task_queue[0].task_id == task2_id


class TestTaskConfig:
    """测试任务配置"""
    
    def test_create_config(self):
        """测试创建配置"""
        config = TaskConfig(
            priority=3,
            timeout=60.0,
            max_retries=5
        )
        
        assert config.priority == 3
        assert config.timeout == 60.0
        assert config.max_retries == 5
    
    def test_default_config(self):
        """测试默认配置"""
        config = TaskConfig()
        
        assert config.priority == 5
        assert config.timeout == 30.0
        assert config.max_retries == 3


class TestProtectionIntegration:
    """防护机制集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_protection_stack(self):
        """测试完整防护栈"""
        protection = ThreeLayerProtection(
            timeout=1.0,
            max_retries=2,
            max_concurrent=10
        )
        
        attempt_count = 0
        
        async def flaky_task():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = await protection.execute(flaky_task, task_id="integration-test")
        
        assert result.is_success()
        assert result.attempts >= 2
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """测试熔断器集成"""
        cb = CircuitBreaker(
            name="integration-test",
            config=CircuitBreakerConfig(failure_threshold=3)
        )
        
        protection = ThreeLayerProtection(
            timeout=1.0,
            max_retries=1
        )
        
        async def unreliable_task():
            raise ValueError("Service unavailable")
        
        # 触发熔断
        for _ in range(3):
            try:
                await cb.execute(unreliable_task)
            except:
                pass
        
        assert cb.state == CircuitBreakerState.OPEN


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
