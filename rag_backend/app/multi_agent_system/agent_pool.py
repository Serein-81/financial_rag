"""
智能体池化系统 (Agent Pool)
智能体的生命周期管理，支持实例池化、负载均衡和故障恢复
"""

import asyncio
import uuid
import time
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import deque
import logging

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """智能体状态"""
    IDLE = "idle"                    # 空闲可用
    BUSY = "busy"                    # 忙碌中
    INITIALIZING = "initializing"    # 初始化中
    FAILED = "failed"                # 故障
    RECOVERING = "recovering"        # 恢复中


@dataclass
class AgentInstance:
    """
    智能体实例
    
    代表池中的一个智能体实例
    """
    instance_id: str
    agent_type: str
    agent: Any                      # 实际的智能体对象
    status: AgentStatus = AgentStatus.IDLE
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = None
    task_count: int = 0
    total_processing_time: float = 0.0
    error_count: int = 0
    max_errors: int = 3
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def mark_busy(self):
        """标记为忙碌"""
        self.status = AgentStatus.BUSY
    
    def mark_idle(self):
        """标记为空闲"""
        self.status = AgentStatus.IDLE
        self.last_used_at = datetime.now()
    
    def mark_failed(self, error: str = ""):
        """标记为故障"""
        self.status = AgentStatus.FAILED
        self.error_count += 1
        self.metadata['last_error'] = error
        self.metadata['last_error_time'] = datetime.now().isoformat()
    
    def mark_recovering(self):
        """标记为恢复中"""
        self.status = AgentStatus.RECOVERING
    
    def should_recover(self) -> bool:
        """判断是否可以恢复"""
        if self.status == AgentStatus.FAILED and self.error_count <= self.max_errors:
            return True
        return False
    
    def get_avg_response_time(self) -> float:
        """获取平均响应时间"""
        if self.task_count == 0:
            return 0.0
        return self.total_processing_time / self.task_count
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "instance_id": self.instance_id,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "task_count": self.task_count,
            "avg_response_time": self.get_avg_response_time(),
            "error_count": self.error_count,
            "version": self.version
        }


@dataclass
class PoolConfig:
    """池配置"""
    min_size: int = 1                    # 最小实例数
    max_size: int = 5                    # 最大实例数
    max_idle_time: int = 300             # 最大空闲时间（秒）
    max_task_time: int = 60              # 最大任务时间（秒）
    health_check_interval: int = 30      # 健康检查间隔（秒）
    auto_scaling: bool = True            # 是否自动扩缩容
    scale_up_threshold: float = 0.8      # 扩容阈值
    scale_down_threshold: float = 0.2    # 缩容阈值


class AgentPool:
    """
    智能体池管理器
    
    管理智能体实例的生命周期，支持：
    - 实例预热和懒加载
    - 负载均衡
    - 自动扩缩容
    - 健康检查
    - 故障恢复
    
    使用示例：
        pool = AgentPool(
            agent_type="finance",
            factory=create_finance_agent,
            config=PoolConfig(min_size=2, max_size=5)
        )
        
        # 获取实例
        instance = await pool.acquire()
        try:
            result = await instance.agent.process(query)
        finally:
            await pool.release(instance)
    """
    
    def __init__(
        self,
        agent_type: str,
        factory: Callable[[], Awaitable[Any]],
        config: Optional[PoolConfig] = None
    ):
        """
        初始化智能体池
        
        Args:
            agent_type: 智能体类型
            factory: 智能体工厂函数
            config: 池配置
        """
        self.agent_type = agent_type
        self.factory = factory
        self.config = config or PoolConfig()
        
        self._instances: Dict[str, AgentInstance] = {}
        self._available: deque = deque()  # 可用实例队列
        self._locks: Dict[str, asyncio.Lock] = {}  # 每个实例的锁
        self._pool_lock = asyncio.Lock()
        
        self._total_tasks = 0
        self._total_errors = 0
        self._total_wait_time = 0.0
        self._scale_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"🏊 [智能体池] 创建池: {agent_type}, 配置: {self.config}")
    
    async def initialize(self):
        """初始化池（预热）"""
        async with self._pool_lock:
            if self._instances:
                return
            
            logger.info(f"🔥 [智能体池] 预热 {self.agent_type}: 创建 {self.config.min_size} 个实例")
            
            for i in range(self.config.min_size):
                instance = await self._create_instance()
                if instance:
                    self._instances[instance.instance_id] = instance
                    self._available.append(instance.instance_id)
                    self._locks[instance.instance_id] = asyncio.Lock()
            
            self._running = True
            self._start_background_tasks()
    
    async def _create_instance(self) -> Optional[AgentInstance]:
        """创建新的智能体实例"""
        try:
            agent = await asyncio.wait_for(
                self.factory(),
                timeout=self.config.max_task_time
            )
            
            instance = AgentInstance(
                instance_id=f"{self.agent_type}_{uuid.uuid4().hex[:8]}",
                agent_type=self.agent_type,
                agent=agent,
                status=AgentStatus.IDLE
            )
            
            logger.info(f"✅ [智能体池] 创建实例: {instance.instance_id}")
            return instance
            
        except asyncio.TimeoutError:
            logger.error(f"⏱️ [智能体池] 创建实例超时: {self.agent_type}")
            return None
        except Exception as e:
            logger.error(f"❌ [智能体池] 创建实例失败: {self.agent_type}, {e}")
            return None
    
    async def acquire(self, timeout: float = 30.0) -> Optional[AgentInstance]:
        """
        获取可用实例
        
        Args:
            timeout: 获取超时时间
            
        Returns:
            智能体实例，如果超时则返回 None
        """
        start_time = time.time()
        
        while True:
            async with self._pool_lock:
                # 1. 先尝试获取空闲实例
                while self._available:
                    instance_id = self._available.popleft()
                    instance = self._instances.get(instance_id)
                    
                    if instance and instance.status == AgentStatus.IDLE:
                        instance.mark_busy()
                        self._total_tasks += 1
                        logger.debug(f"🎯 [智能体池] 获取实例: {instance_id}")
                        return instance
                
                # 2. 如果池未满，尝试创建新实例
                if len(self._instances) < self.config.max_size:
                    logger.info(f"📈 [智能体池] 扩容: {self.agent_type}, 当前: {len(self._instances)}")
                    new_instance = await self._create_instance()
                    if new_instance:
                        self._instances[new_instance.instance_id] = new_instance
                        self._locks[new_instance.instance_id] = asyncio.Lock()
                        new_instance.mark_busy()
                        self._total_tasks += 1
                        return new_instance
            
            # 3. 等待可用实例
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.warning(f"⏰ [智能体池] 获取实例超时: {self.agent_type}")
                return None
            
            wait_time = min(0.5, timeout - elapsed)
            await asyncio.sleep(wait_time)
    
    async def release(self, instance: AgentInstance):
        """
        释放实例回池
        
        Args:
            instance: 要释放的实例
        """
        async with self._pool_lock:
            if instance.instance_id not in self._instances:
                return
            
            if instance.status == AgentStatus.FAILED:
                # 故障实例移出
                logger.warning(f"⚠️ [智能体池] 移除故障实例: {instance.instance_id}")
                del self._instances[instance.instance_id]
                del self._locks[instance.instance_id]
                
                # 尝试补充实例
                if len(self._instances) < self.config.min_size:
                    new_instance = await self._create_instance()
                    if new_instance:
                        self._instances[new_instance.instance_id] = new_instance
                        self._locks[new_instance.instance_id] = asyncio.Lock()
            else:
                instance.mark_idle()
                self._available.append(instance.instance_id)
                logger.debug(f"🔓 [智能体池] 释放实例: {instance.instance_id}")
    
    async def execute(
        self,
        task: Callable[[Any], Awaitable[Any]],
        timeout: Optional[float] = None
    ) -> Any:
        """
        执行任务（自动获取和释放实例）
        
        Args:
            task: 任务函数
            timeout: 任务超时时间
            
        Returns:
            任务结果
        """
        instance = await self.acquire(timeout=timeout or self.config.max_task_time)
        if not instance:
            raise TimeoutError(f"获取 {self.agent_type} 实例超时")
        
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                task(instance.agent),
                timeout=timeout or self.config.max_task_time
            )
            instance.total_processing_time += time.time() - start_time
            instance.task_count += 1
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ [智能体池] 任务超时: {instance.instance_id}")
            instance.mark_failed("任务执行超时")
            self._total_errors += 1
            raise
            
        except Exception as e:
            logger.error(f"❌ [智能体池] 任务执行失败: {instance.instance_id}, {e}")
            instance.mark_failed(str(e))
            self._total_errors += 1
            raise
            
        finally:
            await self.release(instance)
    
    def _start_background_tasks(self):
        """启动后台任务"""
        if self._scale_task is None:
            self._scale_task = asyncio.create_task(self._auto_scale_loop())
        
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def _auto_scale_loop(self):
        """自动扩缩容循环"""
        while self._running:
            try:
                await asyncio.sleep(10)  # 每10秒检查一次
                
                if not self.config.auto_scaling:
                    continue
                
                total = len(self._instances)
                busy = sum(1 for i in self._instances.values() if i.status == AgentStatus.BUSY)
                
                if total == 0:
                    continue
                
                utilization = busy / total
                
                # 扩容
                if utilization >= self.config.scale_up_threshold and total < self.config.max_size:
                    logger.info(f"📈 [智能体池] 自动扩容: {self.agent_type}")
                    new_instance = await self._create_instance()
                    if new_instance:
                        async with self._pool_lock:
                            self._instances[new_instance.instance_id] = new_instance
                            self._locks[new_instance.instance_id] = asyncio.Lock()
                
                # 缩容
                elif utilization <= self.config.scale_down_threshold and total > self.config.min_size:
                    # 找到最久未使用的空闲实例
                    idle_instances = [
                        (iid, inst) for iid, inst in self._instances.items()
                        if inst.status == AgentStatus.IDLE
                    ]
                    
                    if idle_instances:
                        oldest = min(idle_instances, key=lambda x: x[1].last_used_at or datetime.min)
                        iid, inst = oldest
                        
                        # 检查是否超时
                        if inst.last_used_at:
                            idle_time = (datetime.now() - inst.last_used_at).total_seconds()
                            if idle_time > self.config.max_idle_time:
                                logger.info(f"📉 [智能体池] 自动缩容: {iid}")
                                async with self._pool_lock:
                                    del self._instances[iid]
                                    del self._locks[iid]
                                    if iid in self._available:
                                        self._available.remove(iid)
                                
            except Exception as e:
                logger.error(f"❌ [智能体池] 自动扩缩容异常: {e}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                for instance_id, instance in list(self._instances.items()):
                    # 检查是否需要恢复
                    if instance.should_recover():
                        logger.info(f"🔄 [智能体池] 尝试恢复实例: {instance_id}")
                        await self._recover_instance(instance)
                    
                    # 检查空闲超时
                    elif instance.status == AgentStatus.IDLE and instance.last_used_at:
                        idle_time = (datetime.now() - instance.last_used_at).total_seconds()
                        if idle_time > self.config.max_idle_time:
                            logger.info(f"⏰ [智能体池] 移除超时实例: {instance_id}")
                            async with self._pool_lock:
                                del self._instances[instance_id]
                                del self._locks[instance_id]
                                if instance_id in self._available:
                                    self._available.remove(instance_id)
                                    
            except Exception as e:
                logger.error(f"❌ [智能体池] 健康检查异常: {e}")
    
    async def _recover_instance(self, instance: AgentInstance):
        """恢复故障实例"""
        instance.mark_recovering()
        
        try:
            # 重新创建智能体
            new_agent = await asyncio.wait_for(
                self.factory(),
                timeout=self.config.max_task_time
            )
            
            instance.agent = new_agent
            instance.error_count = 0
            instance.status = AgentStatus.IDLE
            self._available.append(instance.instance_id)
            
            logger.info(f"✅ [智能体池] 实例恢复成功: {instance.instance_id}")
            
        except Exception as e:
            logger.error(f"❌ [智能体池] 实例恢复失败: {instance.instance_id}, {e}")
            instance.mark_failed(str(e))
    
    async def shutdown(self):
        """关闭池"""
        self._running = False
        
        if self._scale_task:
            self._scale_task.cancel()
            try:
                await self._scale_task
            except asyncio.CancelledError:
                pass
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"🛑 [智能体池] 关闭: {self.agent_type}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取池统计信息"""
        instances = list(self._instances.values())
        
        return {
            "agent_type": self.agent_type,
            "total_instances": len(instances),
            "idle_instances": sum(1 for i in instances if i.status == AgentStatus.IDLE),
            "busy_instances": sum(1 for i in instances if i.status == AgentStatus.BUSY),
            "failed_instances": sum(1 for i in instances if i.status == AgentStatus.FAILED),
            "total_tasks": self._total_tasks,
            "total_errors": self._total_errors,
            "error_rate": self._total_errors / max(self._total_tasks, 1),
            "avg_wait_time": self._total_wait_time / max(self._total_tasks, 1),
            "utilization": sum(1 for i in instances if i.status == AgentStatus.BUSY) / max(len(instances), 1),
            "config": {
                "min_size": self.config.min_size,
                "max_size": self.config.max_size,
                "auto_scaling": self.config.auto_scaling
            }
        }


class AgentPoolManager:
    """
    智能体池管理器
    
    管理多个类型的智能体池
    """
    
    def __init__(self):
        self._pools: Dict[str, AgentPool] = {}
        self._lock = asyncio.Lock()
        logger.info("🏗️ [池管理器] 初始化完成")
    
    async def create_pool(
        self,
        agent_type: str,
        factory: Callable[[], Awaitable[Any]],
        config: Optional[PoolConfig] = None
    ) -> AgentPool:
        """创建或获取池"""
        async with self._lock:
            if agent_type not in self._pools:
                pool = AgentPool(agent_type, factory, config)
                await pool.initialize()
                self._pools[agent_type] = pool
                logger.info(f"✅ [池管理器] 创建池: {agent_type}")
            
            return self._pools[agent_type]
    
    async def get_pool(self, agent_type: str) -> Optional[AgentPool]:
        """获取池"""
        return self._pools.get(agent_type)
    
    async def remove_pool(self, agent_type: str):
        """移除池"""
        async with self._lock:
            if agent_type in self._pools:
                await self._pools[agent_type].shutdown()
                del self._pools[agent_type]
                logger.info(f"🗑️ [池管理器] 移除池: {agent_type}")
    
    async def shutdown_all(self):
        """关闭所有池"""
        for pool in self._pools.values():
            await pool.shutdown()
        self._pools.clear()
        logger.info("🛑 [池管理器] 全部池已关闭")
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """获取所有池的统计"""
        return {
            agent_type: pool.get_statistics()
            for agent_type, pool in self._pools.items()
        }


# 全局池管理器
_pool_manager: Optional[AgentPoolManager] = None


def get_pool_manager() -> AgentPoolManager:
    """获取全局池管理器"""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = AgentPoolManager()
    return _pool_manager
