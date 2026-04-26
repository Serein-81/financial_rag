"""
ARQ LangGraph 工作流任务处理器

将 LangGraph 工作流与 ARQ 异步任务队列集成，实现：
1. 后台异步执行 LangGraph 工作流
2. 任务状态持久化和恢复
3. 多专家并行执行协调
4. 任务进度跟踪
"""

import json
import logging
import traceback
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from dataclasses import dataclass, field

from app.utils.json_compat import json
from app.tasks.arq_tasks import (
    ARAbstractTask,
    TaskMetadata,
    TaskType,
    ARQ_AVAILABLE
)
from app.langgraph.postgres_saver import get_postgres_saver
from app.langgraph.graph import MultiAgentWorkflowBuilder
from app.langgraph.state import AgentState, create_initial_state

if ARQ_AVAILABLE:
    from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


@dataclass
class WorkflowProgress:
    """工作流进度"""
    current_node: str
    progress_percent: int
    progress_message: str
    specialist_progress: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    checkpoint_id: Optional[str] = None
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_node": self.current_node,
            "progress_percent": self.progress_percent,
            "progress_message": self.progress_message,
            "specialist_progress": self.specialist_progress,
            "checkpoint_id": self.checkpoint_id,
            "updated_at": self.updated_at.isoformat()
        }


class LangGraphWorkflowTask(ARAbstractTask):
    """
    LangGraph 工作流任务
    
    封装 LangGraph 工作流的 ARQ 任务执行
    """
    
    def __init__(self):
        self._postgres_saver = None
        self._workflow_builder = None
    
    def _get_postgres_saver(self, db_session_factory=None):
        """获取 PostgresSaver"""
        if self._postgres_saver is None:
            self._postgres_saver = get_postgres_saver(db_session_factory)
        return self._postgres_saver
    
    def _get_workflow_builder(self, agents_registry: Dict[str, Any]):
        """获取工作流构建器"""
        if self._workflow_builder is None:
            self._workflow_builder = MultiAgentWorkflowBuilder(
                agents_registry=agents_registry,
                enable_checkpointer=True,
                enable_reflection=True
            )
        return self._workflow_builder
    
    async def _update_task_status(
        self,
        db_session,
        task_id: str,
        status: str,
        **kwargs
    ):
        """更新任务状态"""
        try:
            from app.models.agent_task import AgentTaskStatus
            from sqlalchemy import update
            
            values = {"status": status}
            for key, value in kwargs.items():
                if hasattr(AgentTaskStatus, key):
                    values[key] = value
            
            if status == "running":
                values["started_at"] = datetime.now()
            elif status in ["completed", "failed", "cancelled"]:
                values["completed_at"] = datetime.now()
            
            await db_session.execute(
                update(AgentTaskStatus)
                .where(AgentTaskStatus.task_id == task_id)
                .values(**values)
            )
            await db_session.commit()
            
        except Exception as e:
            logger.error(f"[LangGraph Workflow] 更新任务状态失败: {e}")
    
    async def _create_task_record(
        self,
        db_session,
        task_id: str,
        thread_id: str,
        tenant_id: str,
        user_id: str,
        user_query: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """创建任务记录"""
        try:
            from app.models.agent_task import AgentTaskStatus, TaskStatus, TaskPriority
            
            task_record = AgentTaskStatus(
                task_id=task_id,
                thread_id=thread_id,
                tenant_id=tenant_id,
                user_id=user_id,
                task_type="langgraph_workflow",
                task_name="多智能体工作流",
                status=TaskStatus.PENDING,
                priority=TaskPriority.NORMAL,
                user_query=user_query,
                arq_job_id=metadata.get("arq_job_id") if metadata else None,
                extra_metadata=metadata or {}
            )
            
            db_session.add(task_record)
            await db_session.commit()
            
            logger.info(f"[LangGraph Workflow] 创建任务记录: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"[LangGraph Workflow] 创建任务记录失败: {e}")
            await db_session.rollback()
            return False
    
    async def _log_task_event(
        self,
        db_session,
        task_id: str,
        tenant_id: str,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None,
        node_name: Optional[str] = None,
        message: Optional[str] = None
    ):
        """记录任务事件"""
        try:
            from app.models.agent_task import AgentTaskEvent
            
            event = AgentTaskEvent(
                task_id=task_id,
                tenant_id=tenant_id,
                event_type=event_type,
                event_data=event_data,
                node_name=node_name,
                event_message=message
            )
            
            db_session.add(event)
            await db_session.commit()
            
        except Exception as e:
            logger.error(f"[LangGraph Workflow] 记录任务事件失败: {e}")
    
    async def run(self, ctx: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        执行 LangGraph 工作流任务
        
        Args:
            ctx: ARQ 上下文
            **kwargs: 任务参数
                - task_id: 任务 ID
                - thread_id: 线程 ID（用于 checkpoint）
                - tenant_id: 租户 ID
                - user_id: 用户 ID
                - user_query: 用户查询
                - agents_registry: Agent 注册表
                - db_session_factory: 数据库会话工厂
                - checkpoint_id: 从哪个检查点恢复（可选）
                
        Returns:
            任务结果
        """
        task_id = kwargs.get("task_id", "langgraph_workflow")
        thread_id = kwargs.get("thread_id", task_id)
        tenant_id = kwargs.get("tenant_id", "default")
        user_id = kwargs.get("user_id", "default")
        user_query = kwargs.get("user_query", "")
        agents_registry = kwargs.get("agents_registry", {})
        db_session_factory = kwargs.get("db_session_factory")
        checkpoint_id = kwargs.get("checkpoint_id")
        
        logger.info(f"[LangGraph Workflow] 开始执行: task_id={task_id}, thread_id={thread_id[:8]}...")
        
        start_time = datetime.now()
        
        async def _execute():
            db_session = None
            try:
                if db_session_factory:
                    db_session = await db_session_factory().__aenter__()
                
                await self._update_task_status(db_session, task_id, "running")
                await self._log_task_event(
                    db_session, task_id, tenant_id,
                    "workflow_started",
                    {"thread_id": thread_id, "user_query": user_query[:100]},
                    message="工作流开始执行"
                )
                
                postgres_saver = self._get_postgres_saver(db_session_factory)
                workflow_builder = self._get_workflow_builder(agents_registry)
                
                initial_state = create_initial_state(
                    session_id=thread_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    user_query=user_query
                )
                
                compiled_graph = workflow_builder.compile()
                
                async def progress_callback(node_name: str, state: AgentState):
                    progress = self._calculate_progress(node_name, state)
                    
                    await self._update_task_status(
                        db_session, task_id,
                        "running",
                        current_node=node_name,
                        progress_percent=progress.progress_percent,
                        progress_message=progress.progress_message,
                        specialist_progress=progress.specialist_progress,
                        checkpoint_id=progress.checkpoint_id
                    )
                    
                    await postgres_saver.put_checkpoint(
                        thread_id=thread_id,
                        checkpoint_id=f"{thread_id}_{node_name}_{datetime.now().timestamp()}",
                        checkpoint_data=state,
                        metadata={
                            "task_id": task_id,
                            "node_name": node_name,
                            "progress": progress.to_dict()
                        }
                    )
                
                config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id
                    }
                }
                
                await self._log_task_event(
                    db_session, task_id, tenant_id,
                    "graph_invocation",
                    {"config": str(config)},
                    node_name="graph_invocation",
                    message=f"开始执行 LangGraph"
                )
                
                final_state = None
                async for event in compiled_graph.astream(initial_state, config=config):
                    node_name = list(event.keys())[0] if event else "unknown"
                    node_state = event[node_name] if event else {}
                    
                    progress = self._calculate_progress(node_name, node_state)
                    
                    await postgres_saver.put_checkpoint(
                        thread_id=thread_id,
                        checkpoint_id=f"{thread_id}_{node_name}_{datetime.now().timestamp()}",
                        checkpoint_data=node_state,
                        metadata={
                            "task_id": task_id,
                            "node_name": node_name,
                            "progress": progress.to_dict()
                        }
                    )
                    
                    if node_name == "final_answer" or node_name == "final":
                        final_state = node_state
                
                execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                final_response = final_state.get("final_answer", "") if final_state else ""
                
                await self._update_task_status(
                    db_session, task_id, "completed",
                    final_response=final_response,
                    progress_percent=100,
                    progress_message="工作流执行完成",
                    execution_time_ms=execution_time_ms
                )
                
                await self._log_task_event(
                    db_session, task_id, tenant_id,
                    "workflow_completed",
                    {"execution_time_ms": execution_time_ms, "final_response_length": len(final_response)},
                    message="工作流执行完成"
                )
                
                logger.info(f"[LangGraph Workflow] 执行完成: task_id={task_id}, time={execution_time_ms}ms")
                
                return {
                    "status": "completed",
                    "task_id": task_id,
                    "thread_id": thread_id,
                    "final_response": final_response,
                    "execution_time_ms": execution_time_ms
                }
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[LangGraph Workflow] 执行失败: task_id={task_id}, error={error_msg}")
                logger.error(traceback.format_exc())
                
                if db_session:
                    await self._update_task_status(
                        db_session, task_id, "failed",
                        error_message=error_msg,
                        progress_message=f"执行失败: {error_msg[:200]}"
                    )
                    
                    await self._log_task_event(
                        db_session, task_id, tenant_id,
                        "workflow_failed",
                        {"error": error_msg, "traceback": traceback.format_exc()},
                        message=f"工作流执行失败: {error_msg[:100]}"
                    )
                
                return {
                    "status": "failed",
                    "task_id": task_id,
                    "thread_id": thread_id,
                    "error": error_msg
                }
                
            finally:
                if db_session:
                    await db_session.close()
        
        protection_result = await self.async_task_wrapper(
            ctx,
            _execute(),
            task_id=task_id,
            metadata={
                "timeout": kwargs.get("timeout", 300.0),
                "max_attempts": kwargs.get("max_attempts", 3)
            }
        )
        
        if protection_result.is_success():
            return protection_result.result
        else:
            return {
                "status": "failed",
                "task_id": task_id,
                "error": protection_result.error
            }
    
    def _calculate_progress(self, node_name: str, state: AgentState) -> WorkflowProgress:
        """计算工作流进度"""
        node_progress_map = {
            "receptionist": 5,
            "intent": 10,
            "rag_retrieval": 20,
            "finance_specialist": 40,
            "tax_specialist": 40,
            "legal_specialist": 40,
            "report_specialist": 40,
            "aggregator": 60,
            "reflection": 80,
            "final_answer": 95,
            "final": 95,
            "error_handler": 100,
            "human_review": 100
        }
        
        progress_percent = node_progress_map.get(node_name, 50)
        
        specialist_progress = {}
        for result in state.get("specialist_results", []):
            source = result.get("source", "unknown")
            specialist_progress[source] = {
                "completed": True,
                "confidence": result.get("confidence", 0.0)
            }
        
        specialist_count = len(specialist_progress)
        active_specialists = ["finance", "tax", "legal", "report"]
        in_progress = [s for s in active_specialists if s not in specialist_progress]
        
        if in_progress:
            progress_message = f"正在执行 {in_progress[0]} 专家..."
        elif specialist_count > 0:
            progress_message = f"已完成 {specialist_count}/{len(active_specialists)} 个专家分析"
        else:
            progress_message = f"正在处理: {node_name}"
        
        return WorkflowProgress(
            current_node=node_name,
            progress_percent=progress_percent,
            progress_message=progress_message,
            specialist_progress=specialist_progress
        )


class LangGraphTaskManager:
    """
    LangGraph 任务管理器
    
    负责创建、提交和跟踪 LangGraph 工作流任务
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._workflow_task = LangGraphWorkflowTask()
    
    async def submit_workflow(
        self,
        thread_id: str,
        tenant_id: str,
        user_id: str,
        user_query: str,
        agents_registry: Optional[Dict[str, Any]] = None,
        db_session_factory=None,
        priority: int = 5
    ) -> Dict[str, Any]:
        """
        提交工作流任务到 ARQ 队列
        
        Args:
            thread_id: 线程 ID
            tenant_id: 租户 ID
            user_id: 用户 ID
            user_query: 用户查询
            agents_registry: Agent 注册表
            db_session_factory: 数据库会话工厂
            priority: 任务优先级
            
        Returns:
            任务信息
        """
        import uuid
        
        task_id = f"lgwf_{uuid.uuid4().hex[:16]}"
        
        if db_session_factory:
            db_session = await db_session_factory().__aenter__()
            try:
                await self._workflow_task._create_task_record(
                    db_session, task_id, thread_id, tenant_id, user_id, user_query,
                    {"task_type": "langgraph_workflow", "priority": priority}
                )
            finally:
                await db_session.close()
        
        logger.info(f"[TaskManager] 提交工作流任务: task_id={task_id}, thread_id={thread_id[:8]}...")
        
        return {
            "task_id": task_id,
            "thread_id": thread_id,
            "status": "submitted",
            "message": "任务已提交到队列"
        }
    
    async def get_task_status(
        self,
        task_id: str,
        db_session_factory=None
    ) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务 ID
            db_session_factory: 数据库会话工厂
            
        Returns:
            任务状态信息
        """
        if db_session_factory is None:
            return None
        
        db_session = await db_session_factory().__aenter__()
        try:
            from app.models.agent_task import AgentTaskStatus
            from sqlalchemy import select
            
            result = await db_session.execute(
                select(AgentTaskStatus).where(AgentTaskStatus.task_id == task_id)
            )
            task_record = result.scalar_one_or_none()
            
            if task_record:
                return task_record.to_summary()
            
            return None
            
        finally:
            await db_session.close()
    
    async def get_thread_status(
        self,
        thread_id: str,
        db_session_factory=None
    ) -> Optional[Dict[str, Any]]:
        """
        获取线程状态（用于前端水合）
        
        Args:
            thread_id: 线程 ID
            db_session_factory: 数据库会话工厂
            
        Returns:
            线程状态信息，包括当前进度和已完成的结果
        """
        if db_session_factory is None:
            return None
        
        db_session = await db_session_factory().__aenter__()
        try:
            from app.models.agent_task import AgentTaskStatus, TaskStatus
            from sqlalchemy import select, desc
            
            result = await db_session.execute(
                select(AgentTaskStatus)
                .where(AgentTaskStatus.thread_id == thread_id)
                .order_by(desc(AgentTaskStatus.created_at))
                .limit(1)
            )
            task_record = result.scalar_one_or_none()
            
            if not task_record:
                return None
            
            postgres_saver = get_postgres_saver(db_session_factory)
            checkpoints = await postgres_saver.list_checkpoints(thread_id, limit=10)
            
            status_info = task_record.to_summary()
            status_info["checkpoints"] = checkpoints
            
            return status_info
            
        finally:
            await db_session.close()
    
    async def resume_workflow(
        self,
        thread_id: str,
        db_session_factory=None
    ) -> Optional[Dict[str, Any]]:
        """
        从断点恢复工作流
        
        Args:
            thread_id: 线程 ID
            db_session_factory: 数据库会话工厂
            
        Returns:
            恢复信息
        """
        postgres_saver = get_postgres_saver(db_session_factory)
        latest_checkpoint = await postgres_saver.get_latest_checkpoint_id(thread_id)
        
        if not latest_checkpoint:
            return None
        
        logger.info(f"[TaskManager] 从检查点恢复: thread_id={thread_id[:8]}..., checkpoint={latest_checkpoint[:8]}...")
        
        return {
            "thread_id": thread_id,
            "checkpoint_id": latest_checkpoint,
            "status": "ready_to_resume"
        }


langgraph_task_manager: Optional[LangGraphTaskManager] = None


def get_langgraph_task_manager(redis_url: str = "redis://localhost:6379/0") -> LangGraphTaskManager:
    """获取任务管理器单例"""
    global langgraph_task_manager
    
    if langgraph_task_manager is None:
        langgraph_task_manager = LangGraphTaskManager(redis_url)
    
    return langgraph_task_manager