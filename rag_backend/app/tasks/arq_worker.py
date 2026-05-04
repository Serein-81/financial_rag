"""
ARQ Worker 启动脚本

用于后台执行 LangGraph 工作流任务

启动方式：
    # 方式1: 直接运行
    python -m app.tasks.arq_worker
    
    # 方式2: 使用 uvicorn 的后台任务（推荐用于开发）
    # 在 main.py 中自动启动
    
    # 方式3: 使用独立的 Worker 进程
    arq app.tasks.arq_worker.WorkerSettings
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _serialize_clarification_request(clarification_request):
    """Convert clarification payloads to JSON-safe dicts for task polling APIs."""
    if clarification_request is None:
        return None
    if hasattr(clarification_request, "model_dump"):
        return clarification_request.model_dump(mode="json")
    if isinstance(clarification_request, dict):
        return clarification_request
    return {
        "question": getattr(clarification_request, "question", "请详细描述您的问题"),
        "suggestions": getattr(clarification_request, "suggestions", []),
        "reason": getattr(clarification_request, "reason", "您的输入需要更多信息来帮助您"),
        "required": getattr(clarification_request, "required", True),
        "placeholder": getattr(clarification_request, "placeholder", ""),
        "type": getattr(clarification_request, "type", "intent_clarification"),
    }


class ARQWorker:
    """
    ARQ Worker - 从 Redis 队列中消费任务并执行
    
    这是一个简化的 ARQ 实现，不依赖额外的 arq 库
    任务通过 Redis List 结构存储
    """
    
    QUEUE_NAME = "arq:default"
    POLL_INTERVAL = 1  # 轮询间隔（秒）
    
    def __init__(self):
        self.running = False
        self.redis_service = None
        
    async def initialize(self):
        """初始化 Worker"""
        from app.services.redis_service import get_redis_service
        self.redis_service = get_redis_service()  # 同步获取
        
        if not self.redis_service.client:
            logger.warning("[ARQ Worker] Redis 未连接，Worker 将以简化模式运行")
            logger.info("[ARQ Worker] 任务将通过 asyncio.create_task 直接后台执行")
        
        logger.info("[ARQ Worker] 初始化完成")
        logger.info(f"[ARQ Worker] 监听队列: {self.QUEUE_NAME}")
    
    async def process_task(self, task_data: dict) -> bool:
        """
        处理任务
        
        Args:
            task_data: 任务数据
            
        Returns:
            是否成功
        """
        task_type = task_data.get("task_type", "unknown")
        task_id = task_data.get("task_id", "unknown")
        
        logger.info(f"[ARQ Worker] 处理任务: task_type={task_type}, task_id={task_id}")
        
        try:
            if task_type == "langgraph_workflow" or "run_langgraph_workflow" in str(task_data):
                return await self._run_langgraph_workflow(task_data)
            else:
                logger.warning(f"[ARQ Worker] 未知任务类型: {task_type}")
                return False
                
        except Exception as e:
            logger.error(f"[ARQ Worker] 任务执行失败: {e}")
            await self._update_task_status(task_id, "failed", error=str(e))
            return False
    
    async def _run_langgraph_workflow(self, task_data: dict) -> bool:
        """执行 LangGraph 工作流任务"""
        from app.db.session import AsyncSessionLocal
        from app.models.agent_task import AgentTaskStatus, TaskStatus
        
        task_id = task_data.get("task_id")
        thread_id = task_data.get("thread_id")
        tenant_id = task_data.get("tenant_id")
        user_id = task_data.get("user_id")
        user_query = task_data.get("user_query")
        
        logger.info(f"[ARQ Worker] 开始执行工作流: task_id={task_id}")
        
        try:
            async with AsyncSessionLocal() as db:
                await self._update_task_status(
                    db, task_id, "running",
                    current_node="initializing",
                    progress_percent=5,
                    progress_message="正在初始化..."
                )
                
                from app.multi_agent_system import AgentOrchestrator
                from app.multi_agent_system.orchestrator import OrchestrationContext
                
                orch = AgentOrchestrator(tenant_id=tenant_id, user_id=user_id)
                await orch.initialize()
                
                await self._update_task_status(
                    db, task_id, "running",
                    current_node="intent_analysis",
                    progress_percent=10,
                    progress_message="正在分析意图..."
                )
                
                context = OrchestrationContext(
                    session_id=thread_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    user_query=user_query,
                    context=task_data.get("context", {}),
                    enable_reflection=task_data.get("enable_reflection", True),
                    confidence_threshold=task_data.get("confidence_threshold", 0.7),
                    max_specialists=task_data.get("max_specialists", 3)
                )
                
                await self._update_task_status(
                    db, task_id, "running",
                    current_node="executing",
                    progress_percent=50,
                    progress_message="正在执行专家分析..."
                )
                
                result = await orch.process(context)
                
                clarification_request = _serialize_clarification_request(result.clarification_request)
                needs_clarification = bool(result.needs_clarification and clarification_request)
                final_response = None if needs_clarification else (result.final_response or "处理完成")
                
                await self._update_task_status(
                    db, task_id, "completed",
                    final_response=final_response,
                    needs_clarification=needs_clarification,
                    clarification_request=clarification_request,
                    progress_percent=100,
                    progress_message="需要补充信息" if needs_clarification else "任务完成",
                    completed_at=datetime.now()
                )
                
                logger.info(f"[ARQ Worker] 工作流执行完成: task_id={task_id}")
                return True
            
        except Exception as e:
            logger.error(f"[ARQ Worker] 工作流执行失败: {e}")
            return False
    
    async def _update_task_status(
        self,
        db,
        task_id: str,
        status: str,
        current_node: str = None,
        progress_percent: int = None,
        progress_message: str = None,
        final_response: str = None,
        error_message: str = None,
        completed_at: datetime = None,
        needs_clarification: bool = None,
        clarification_request: dict = None,
        intent_analysis: dict = None
    ):
        """更新任务状态"""
        try:
            from app.models.agent_task import AgentTaskStatus, TaskStatus
            from sqlalchemy import update
            
            values = {"status": status}
            
            if current_node is not None:
                values["current_node"] = current_node
            if progress_percent is not None:
                values["progress_percent"] = progress_percent
            if progress_message is not None:
                values["progress_message"] = progress_message
            if final_response is not None:
                values["final_response"] = final_response
            if error_message is not None:
                values["error_message"] = error_message
            if completed_at is not None:
                values["completed_at"] = completed_at
            if needs_clarification is not None:
                values["needs_clarification"] = needs_clarification
            if clarification_request is not None:
                values["clarification_request"] = clarification_request
            if intent_analysis is not None:
                values["intent_analysis"] = intent_analysis
                
            await db.execute(
                update(AgentTaskStatus)
                .where(AgentTaskStatus.task_id == task_id)
                .values(**values)
            )
            await db.commit()
            
        except Exception as e:
            logger.error(f"[ARQ Worker] 更新任务状态失败: {e}")
    
    async def run(self):
        """运行 Worker（主循环）"""
        self.running = True
        logger.info("[ARQ Worker] Worker 已启动，等待任务...")
        
        while self.running:
            try:
                loop = asyncio.get_event_loop()
                task_data = await loop.run_in_executor(
                    None,
                    self.redis_service.dequeue_task,
                    self.QUEUE_NAME,
                    self.POLL_INTERVAL
                )
                
                if task_data:
                    await self.process_task(task_data)
                    
            except Exception as e:
                logger.error(f"[ARQ Worker] 处理循环异常: {e}")
                await asyncio.sleep(5)
    
    def stop(self):
        """停止 Worker"""
        logger.info("[ARQ Worker] 正在停止...")
        self.running = False


async def start_worker():
    """启动 Worker"""
    worker = ARQWorker()
    
    try:
        await worker.initialize()
        
        loop = asyncio.get_event_loop()
        
        def signal_handler(sig, frame):
            logger.info(f"[ARQ Worker] 收到信号 {sig}，正在停止...")
            worker.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        await worker.run()
        
    except KeyboardInterrupt:
        logger.info("[ARQ Worker] 收到键盘中断，正在停止...")
        worker.stop()
    except Exception as e:
        logger.error(f"[ARQ Worker] 启动失败: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logger.info("=" * 50)
    logger.info("ARQ Worker 启动中...")
    logger.info("=" * 50)
    
    asyncio.run(start_worker())
