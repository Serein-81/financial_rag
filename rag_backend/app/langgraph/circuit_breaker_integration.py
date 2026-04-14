"""
LangGraph 熔断器集成模块

功能：
1. 将熔断器集成到 LangGraph 工作流节点
2. 提供任务中断恢复机制
3. 防止外部服务故障级联传播
"""

import logging
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
from app.multi_agent_system.async_task_scheduler import (
    CircuitBreaker, 
    CircuitBreakerConfig,
    CircuitState,
    TaskResult,
    TaskState
)

logger = logging.getLogger(__name__)


class LangGraphCircuitBreakerManager:
    """
    LangGraph 熔断器管理器
    
    为 LangGraph 工作流提供熔断保护
    """
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = None
    
    async def initialize(self):
        """初始化异步锁"""
        import asyncio
        self._lock = asyncio.Lock()
    
    def register_breaker(
        self, 
        name: str, 
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        注册熔断器
        
        Args:
            name: 熔断器名称（如 agent名称、tool名称）
            config: 熔断器配置
            
        Returns:
            CircuitBreaker: 熔断器实例
        """
        breaker = CircuitBreaker(name, config)
        self._breakers[name] = breaker
        logger.info(f"🔧 [LangGraph CircuitBreaker] 注册熔断器: {name}")
        return breaker
    
    async def execute_with_protection(
        self,
        breaker_name: str,
        func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> TaskResult:
        """
        使用熔断器保护执行异步函数
        
        Args:
            breaker_name: 熔断器名称
            func: 要执行的异步函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            TaskResult: 执行结果
        """
        breaker = self._breakers.get(breaker_name)
        
        if not breaker:
            logger.warning(f"⚠️ 熔断器 {breaker_name} 未注册，使用默认配置")
            breaker = self.register_breaker(breaker_name)
        
        return await breaker.call(func, *args, **kwargs)
    
    def get_breaker_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """获取熔断器状态"""
        breaker = self._breakers.get(name)
        return breaker.get_stats() if breaker else None
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有熔断器状态"""
        return {
            name: breaker.get_stats()
            for name, breaker in self._breakers.items()
        }
    
    async def is_breaker_open(self, name: str) -> bool:
        """检查熔断器是否处于开启状态"""
        breaker = self._breakers.get(name)
        return breaker.state == CircuitState.OPEN if breaker else False


class CircuitBreakerNode:
    """
    熔断器保护节点
    
    用于 LangGraph 工作流中包装需要保护的外部调用
    """
    
    def __init__(
        self,
        manager: LangGraphCircuitBreakerManager,
        breaker_name: str
    ):
        self.manager = manager
        self.breaker_name = breaker_name
    
    async def invoke(
        self,
        state: Dict[str, Any],
        func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行受保护的节点逻辑
        
        Args:
            state: LangGraph 状态
            func: 要执行的函数
            *args, **kwargs: 函数参数
            
        Returns:
            Dict: 更新后的状态
        """
        result = await self.manager.execute_with_protection(
            self.breaker_name,
            func,
            *args,
            **kwargs
        )
        
        if result.state == TaskState.COMPLETED:
            logger.info(f"✅ [{self.breaker_name}] 执行成功")
            return {
                **state,
                "last_result": result.result,
                "circuit_breaker_state": "closed"
            }
        else:
            logger.error(f"❌ [{self.breaker_name}] 执行失败: {result.error}")
            return {
                **state,
                "last_error": result.error,
                "circuit_breaker_state": result.state.value,
                "needs_fallback": True
            }


def create_circuit_breaker_node(
    manager: LangGraphCircuitBreakerManager,
    breaker_name: str
) -> Callable:
    """
    创建熔断器保护节点的工厂函数
    
    Args:
        manager: 熔断器管理器
        breaker_name: 熔断器名称
        
    Returns:
        Callable: LangGraph 节点函数
    """
    node = CircuitBreakerNode(manager, breaker_name)
    
    async def node_func(state: Dict[str, Any]) -> Dict[str, Any]:
        """节点函数"""
        return state
    
    return node.invoke


class WorkflowRecoveryManager:
    """
    工作流中断恢复管理器
    
    利用 LangGraph Checkpointer 实现任务恢复
    """
    
    def __init__(self, checkpointer):
        self.checkpointer = checkpointer
        self._interrupted_workflows: Dict[str, Dict[str, Any]] = {}
    
    async def save_interrupted_state(
        self,
        thread_id: str,
        state: Dict[str, Any],
        node_name: str,
        error: str
    ):
        """
        保存中断的工作流状态
        
        Args:
            thread_id: 线程ID
            state: 当前状态
            node_name: 中断发生的节点
            error: 中断原因
        """
        self._interrupted_workflows[thread_id] = {
            "state": state,
            "interrupted_at": datetime.now(),
            "interrupted_at_node": node_name,
            "error": error,
            "can_retry": True
        }
        logger.warning(
            f"⚠️ [Recovery] 保存中断状态: thread_id={thread_id}, "
            f"node={node_name}, error={error}"
        )
    
    async def get_interrupted_workflow(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取中断的工作流信息"""
        return self._interrupted_workflows.get(thread_id)
    
    async def clear_interrupted_workflow(self, thread_id: str):
        """清除中断的工作流记录"""
        if thread_id in self._interrupted_workflows:
            del self._interrupted_workflows[thread_id]
            logger.info(f"🗑️ [Recovery] 清除中断记录: {thread_id}")
    
    async def retry_interrupted_workflow(
        self,
        thread_id: str,
        workflow_func: Callable,
        **kwargs
    ) -> Any:
        """
        重试中断的工作流
        
        Args:
            thread_id: 线程ID
            workflow_func: 工作流执行函数
            **kwargs: 工作流参数
            
        Returns:
            Any: 工作流执行结果
        """
        workflow_info = await self.get_interrupted_workflow(thread_id)
        
        if not workflow_info:
            raise ValueError(f"未找到中断的工作流: {thread_id}")
        
        if not workflow_info["can_retry"]:
            raise ValueError(f"工作流不可重试: {thread_id}")
        
        logger.info(f"🔄 [Recovery] 重试工作流: {thread_id}")
        
        try:
            result = await workflow_func(
                thread_id=thread_id,
                initial_state=workflow_info["state"],
                **kwargs
            )
            await self.clear_interrupted_workflow(thread_id)
            return result
            
        except Exception as e:
            logger.error(f"❌ [Recovery] 重试失败: {e}")
            self._interrupted_workflows[thread_id]["retry_count"] = \
                self._interrupted_workflows[thread_id].get("retry_count", 0) + 1
            
            if self._interrupted_workflows[thread_id]["retry_count"] >= 3:
                self._interrupted_workflows[thread_id]["can_retry"] = False
            
            raise


class CircuitBreakerMiddleware:
    """
    熔断器中间件
    
    用于自动包装 LangGraph 工作流中的外部调用
    """
    
    def __init__(self, manager: LangGraphCircuitBreakerManager):
        self.manager = manager
        self._protected_calls: Dict[str, int] = {}
    
    def wrap_external_call(
        self,
        service_name: str,
        func: Callable[..., Awaitable[Any]]
    ) -> Callable:
        """
        包装外部服务调用，添加熔断保护
        
        Args:
            service_name: 服务名称（用于熔断器命名）
            func: 原始异步函数
            
        Returns:
            Callable: 包装后的函数
        """
        async def wrapped(*args, **kwargs):
            self._protected_calls[service_name] = \
                self._protected_calls.get(service_name, 0) + 1
            
            result = await self.manager.execute_with_protection(
                service_name,
                func,
                *args,
                **kwargs
            )
            
            if result.state != TaskState.COMPLETED:
                logger.error(
                    f"⚠️ [{service_name}] 调用失败 (第{self._protected_calls[service_name]}次)",
                    extra={"error": result.error}
                )
            
            return result.result if result.state == TaskState.COMPLETED else None
        
        return wrapped
    
    def get_protected_calls_stats(self) -> Dict[str, int]:
        """获取受保护调用的统计"""
        return self._protected_calls.copy()


_global_circuit_breaker_manager: Optional[LangGraphCircuitBreakerManager] = None


def get_circuit_breaker_manager() -> LangGraphCircuitBreakerManager:
    """获取全局熔断器管理器实例"""
    global _global_circuit_breaker_manager
    
    if _global_circuit_breaker_manager is None:
        _global_circuit_breaker_manager = LangGraphCircuitBreakerManager()
    
    return _global_circuit_breaker_manager


async def initialize_circuit_breaker_manager():
    """初始化全局熔断器管理器"""
    manager = get_circuit_breaker_manager()
    await manager.initialize()
    
    manager.register_breaker("llm_service", CircuitBreakerConfig(
        failure_threshold=3,
        timeout=30.0
    ))
    
    manager.register_breaker("external_api", CircuitBreakerConfig(
        failure_threshold=5,
        timeout=60.0
    ))
    
    manager.register_breaker("mcp_tools", CircuitBreakerConfig(
        failure_threshold=3,
        timeout=45.0
    ))
    
    logger.info("✅ [CircuitBreaker] 全局管理器初始化完成")
