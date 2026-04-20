"""
ARQ 任务定义

基于 ARQ 的异步任务队列实现

主要任务类型：
1. AROrchestratorTask - 编排器任务
2. ARSpecialistTask - 专家任务
3. ARRetrievalTask - 检索任务
4. ARGeneratorTask - 生成任务
5. ARReflectionTask - 反思任务

注意：ARQ 是可选依赖，如果未安装则跳过相关功能
"""

from app.utils.json_compat import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

# ARQ 依赖为可选
try:
    from arq.connections import RedisSettings
    from arq.worker import Worker
    ARQ_AVAILABLE = True
except ImportError:
    ARQ_AVAILABLE = False
    RedisSettings = None
    Worker = None

from app.tasks.three_layer_protection import ThreeLayerProtection, ProtectionResult

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """任务类型"""
    ORCHESTRATOR = "orchestrator"
    SPECIALIST = "specialist"
    RETRIEVAL = "retrieval"
    GENERATOR = "generator"
    REFLECTION = "reflection"
    SUMMARIZER = "summarizer"


@dataclass
class TaskMetadata:
    """
    任务元数据
    
    记录任务的所有元信息
    """
    task_id: str
    task_type: TaskType
    request_id: str
    tenant_id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    priority: int = 5
    attempts: int = 0
    max_attempts: int = 3
    timeout: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value if isinstance(self.task_type, TaskType) else self.task_type,
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "priority": self.priority,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "timeout": self.timeout,
            "metadata": self.metadata
        }


class ARAbstractTask:
    """
    ARQ 任务基类
    
    所有 ARQ 任务都应该继承此类
    """
    
    # 类级别的三层防护
    protection = ThreeLayerProtection(
        timeout=30.0,
        max_retries=3,
        max_concurrent=100,
        max_memory_mb=512
    )
    
    @staticmethod
    async def async_task_wrapper(
        ctx: Dict[str, Any],
        coro_func,
        task_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProtectionResult:
        """
        任务包装器
        
        为所有任务提供统一的执行包装，包括：
        1. 三层防护执行
        2. 日志记录
        3. 错误处理
        4. 指标收集
        
        Args:
            ctx: ARQ 上下文
            coro_func: 协程函数
            task_id: 任务 ID
            metadata: 任务元数据
            
        Returns:
            防护结果
        """
        metadata = metadata or {}
        task_id = task_id or "unknown"
        
        logger.info(
            f"[ARQ-Task] 开始执行: task_id={task_id}, "
            f"job_id={ctx.get('job_id')}"
        )
        
        try:
            result = await ARAbstractTask.protection.execute(
                coro_func,
                task_id=task_id,
                config={
                    "timeout": metadata.get("timeout", 30.0),
                    "max_attempts": metadata.get("max_attempts", 3)
                }
            )
            
            if result.is_success():
                logger.info(
                    f"[ARQ-Task] 执行成功: task_id={task_id}, "
                    f"time={result.execution_time_ms}ms"
                )
            else:
                logger.error(
                    f"[ARQ-Task] 执行失败: task_id={task_id}, "
                    f"status={result.status}, error={result.error}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"[ARQ-Task] 执行异常: task_id={task_id}, error={e}")
            return ProtectionResult(
                status=ProtectionResult.status.ERROR,
                error=str(e)
            )
    
    @staticmethod
    async def serialize_state(state: Dict[str, Any]) -> str:
        """序列化状态"""
        return json.dumps(state, default=str)
    
    @staticmethod
    async def deserialize_state(state_str: str) -> Dict[str, Any]:
        """反序列化状态"""
        return json.loads(state_str)


class AROrchestratorTask(ARAbstractTask):
    """
    编排器任务
    
    负责协调整个多智能体工作流
    """
    
    async def run(self, ctx: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        执行编排器任务
        
        Args:
            ctx: ARQ 上下文
            **kwargs: 任务参数
            
        Returns:
            任务结果
        """
        task_id = kwargs.get("task_id", "orchestrator")
        
        async def _execute():
            # 模拟编排器执行
            logger.info(f"[Orchestrator] 执行编排: {task_id}")
            
            # TODO: 实际的编排逻辑
            result = {
                "status": "completed",
                "next_phase": "specialist"
            }
            
            return result
        
        protection_result = await self.async_task_wrapper(
            ctx,
            _execute(),
            task_id=task_id,
            metadata=kwargs.get("metadata", {})
        )
        
        if protection_result.is_success():
            return protection_result.result
        else:
            raise Exception(protection_result.error)


class ARSpecialistTask(ARAbstractTask):
    """
    专家任务
    
    负责执行特定领域专家的分析
    """
    
    async def run(self, ctx: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        执行专家任务
        
        Args:
            ctx: ARQ 上下文
            **kwargs: 任务参数
            
        Returns:
            任务结果
        """
        task_id = kwargs.get("task_id", "specialist")
        specialist_type = kwargs.get("specialist_type", "finance")
        
        async def _execute():
            logger.info(
                f"[Specialist] 执行专家分析: task_id={task_id}, "
                f"type={specialist_type}"
            )
            
            # TODO: 实际的专家分析逻辑
            result = {
                "status": "completed",
                "specialist_type": specialist_type,
                "analysis": f"专家 {specialist_type} 的分析结果"
            }
            
            return result
        
        protection_result = await self.async_task_wrapper(
            ctx,
            _execute(),
            task_id=task_id,
            metadata=kwargs.get("metadata", {})
        )
        
        if protection_result.is_success():
            return protection_result.result
        else:
            raise Exception(protection_result.error)


class ARRetrievalTask(ARAbstractTask):
    """
    RAG 检索任务
    
    负责从向量数据库检索相关文档
    """
    
    async def run(self, ctx: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        执行检索任务
        
        Args:
            ctx: ARQ 上下文
            **kwargs: 任务参数
            
        Returns:
            任务结果
        """
        task_id = kwargs.get("task_id", "retrieval")
        query = kwargs.get("query", "")
        top_k = kwargs.get("top_k", 5)
        
        async def _execute():
            logger.info(
                f"[Retrieval] 执行检索: task_id={task_id}, "
                f"query={query}, top_k={top_k}"
            )
            
            # TODO: 实际的 RAG 检索逻辑
            result = {
                "status": "completed",
                "query": query,
                "documents": [],
                "count": 0
            }
            
            return result
        
        protection_result = await self.async_task_wrapper(
            ctx,
            _execute(),
            task_id=task_id,
            metadata=kwargs.get("metadata", {})
        )
        
        if protection_result.is_success():
            return protection_result.result
        else:
            raise Exception(protection_result.error)


class ARGeneratorTask(ARAbstractTask):
    """
    响应生成任务
    
    负责生成最终响应
    """
    
    async def run(self, ctx: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        执行生成任务
        
        Args:
            ctx: ARQ 上下文
            **kwargs: 任务参数
            
        Returns:
            任务结果
        """
        task_id = kwargs.get("task_id", "generator")
        
        async def _execute():
            logger.info(f"[Generator] 生成响应: task_id={task_id}")
            
            # TODO: 实际的生成逻辑
            result = {
                "status": "completed",
                "response": "生成的响应内容"
            }
            
            return result
        
        protection_result = await self.async_task_wrapper(
            ctx,
            _execute(),
            task_id=task_id,
            metadata=kwargs.get("metadata", {})
        )
        
        if protection_result.is_success():
            return protection_result.result
        else:
            raise Exception(protection_result.error)


class ARReflectionTask(ARAbstractTask):
    """
    反思任务
    
    负责质量审核和反思
    """
    
    async def run(self, ctx: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        执行反思任务
        
        Args:
            ctx: ARQ 上下文
            **kwargs: 任务参数
            
        Returns:
            任务结果
        """
        task_id = kwargs.get("task_id", "reflection")
        
        async def _execute():
            logger.info(f"[Reflection] 执行反思: task_id={task_id}")
            
            # TODO: 实际的反思逻辑
            result = {
                "status": "completed",
                "quality": "acceptable",
                "needs_improvement": False
            }
            
            return result
        
        protection_result = await self.async_task_wrapper(
            ctx,
            _execute(),
            task_id=task_id,
            metadata=kwargs.get("metadata", {})
        )
        
        if protection_result.is_success():
            return protection_result.result
        else:
            raise Exception(protection_result.error)


# ARQ Worker 配置
async def run_worker():
    """运行 ARQ Worker"""
    if not ARQ_AVAILABLE:
        logger.error("[ARQ-Worker] ARQ 未安装，无法启动 Worker")
        raise ImportError("需要安装 arq: pip install arq")
    
    async def startup(ctx: Dict[str, Any]):
        """Worker 启动时的初始化"""
        logger.info("[ARQ-Worker] Worker 启动")
        from arq import arq_redis_from_url
        ctx['redis'] = await arq_redis_from_url('redis://localhost')
    
    async def shutdown(ctx: Dict[str, Any]):
        """Worker 关闭时的清理"""
        logger.info("[ARQ-Worker] Worker 关闭")
        await ctx['redis'].close()
    
    worker = Worker(
        functions=[
            AROrchestratorTask(),
            ARSpecialistTask(),
            ARRetrievalTask(),
            ARGeneratorTask(),
            ARReflectionTask(),
        ],
        redis_settings=RedisSettings.from_url('redis://localhost'),
        max_jobs=100,
        job_timeout=300,
        keep_result=3600,
        startup=startup,
        shutdown=shutdown,
    )
    
    await worker.run()


# 便捷的入队函数
async def enqueue_task(
    redis_url: str,
    task_class: str,
    **kwargs
) -> str:
    """
    入队任务
    
    Args:
        redis_url: Redis URL
        task_class: 任务类名
        **kwargs: 任务参数
        
    Returns:
        任务 ID
    """
    from arq import create_pool
    from arq.connections import RedisSettings
    
    pool = await create_pool(RedisSettings.from_url(redis_url))
    
    job = await pool.enqueue_job(
        task_class,
        **kwargs
    )
    
    await pool.close()
    
    return job.job_id


# 注册任务映射
TASK_MAPPING = {
    "orchestrator": AROrchestratorTask,
    "specialist": ARSpecialistTask,
    "retrieval": ARRetrievalTask,
    "generator": ARGeneratorTask,
    "reflection": ARReflectionTask,
}
