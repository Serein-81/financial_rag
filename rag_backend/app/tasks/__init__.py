"""
异步任务处理模块

基于 ARQ 实现的三层防护异步任务队列系统

功能：
1. ARQ 任务队列集成
2. 三层防护机制（超时、重试、资源限制）
3. 任务优先级管理
4. 任务监控和追踪
5. 失败处理和告警

作者：Senior Python Backend Architect
版本：1.0.0
"""

from app.tasks.arq_tasks import (
    ARAbstractTask,
    AROrchestratorTask,
    ARSpecialistTask,
    ARRetrievalTask,
    ARGeneratorTask,
    ARReflectionTask,
)
from app.tasks.three_layer_protection import (
    ThreeLayerProtection,
    TimeoutProtection,
    RetryProtection,
    ResourceProtection,
    ProtectionResult,
)
from app.tasks.task_scheduler import (
    TaskScheduler,
    TaskConfig,
    TaskMetadata,
)
from app.tasks.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
)

__all__ = [
    # ARQ 任务
    "ARAbstractTask",
    "AROrchestratorTask",
    "ARSpecialistTask",
    "ARRetrievalTask",
    "ARGeneratorTask",
    "ARReflectionTask",
    # 三层防护
    "ThreeLayerProtection",
    "TimeoutProtection",
    "RetryProtection",
    "ResourceProtection",
    "ProtectionResult",
    # 任务调度
    "TaskScheduler",
    "TaskConfig",
    "TaskMetadata",
    # 熔断器
    "CircuitBreaker",
    "CircuitBreakerState",
]
