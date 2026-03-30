"""统一的进度回调机制"""
import asyncio
import logging
from typing import Callable, Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProgressLevel(Enum):
    """进度消息级别"""
    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ProgressStep:
    """进度步骤"""
    name: str
    status: str = "pending"
    message: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None

    @property
    def duration(self) -> float:
        """计算持续时间（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        elif self.start_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0.0


@dataclass
class ProgressStatus:
    """整体进度状态"""
    task_id: str
    start_time: datetime = field(default_factory=datetime.now)
    steps: List[ProgressStep] = field(default_factory=list)
    current_step_index: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def elapsed_seconds(self) -> float:
        """经过的时间（秒）"""
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def completed_steps(self) -> int:
        """完成的步骤数"""
        return sum(1 for s in self.steps if s.status == "completed")

    @property
    def total_steps(self) -> int:
        """总步骤数"""
        return len(self.steps)

    @property
    def progress_percentage(self) -> float:
        """进度百分比"""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "elapsed_seconds": self.elapsed_seconds,
            "completed_steps": self.completed_steps,
            "total_steps": self.total_steps,
            "progress_percentage": self.progress_percentage,
            "current_step": self.steps[self.current_step_index].name if self.steps else "",
            "errors": self.errors,
            "warnings": self.warnings
        }


class ProgressCallback:
    """
    统一的进度回调机制

    融合 RAG 项目的 callback 机制
    提供更友好的用户体验
    """

    def __init__(
        self,
        callback: Optional[Callable] = None,
        task_id: str = "",
        auto_log: bool = True
    ):
        self.callback = callback
        self.task_id = task_id
        self.auto_log = auto_log
        self.start_time = datetime.now()
        self.steps_completed = 0
        self.total_steps = 0
        self.current_step = ""
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def __call__(self, msg: str, level: str = "info"):
        """
        发送进度消息

        Args:
            msg: 消息内容
            level: 消息级别 (info, warning, error, success)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        elapsed = (datetime.now() - self.start_time).total_seconds()

        formatted_msg = f"[{timestamp}] ({elapsed:.1f}s) {msg}"

        if level == "error":
            if self.auto_log:
                logger.error(formatted_msg)
            self.errors.append(msg)
        elif level == "warning":
            if self.auto_log:
                logger.warning(formatted_msg)
            self.warnings.append(msg)
        else:
            if self.auto_log:
                logger.info(formatted_msg)

        if self.callback:
            try:
                self.callback(formatted_msg)
            except Exception as e:
                logger.error(f"回调执行失败: {e}")

        self.current_step = msg
        if level in ["success", "done"]:
            self.steps_completed += 1

    def info(self, msg: str):
        """发送信息消息"""
        self(msg, "info")

    def success(self, msg: str):
        """发送成功消息"""
        self(msg, "success")

    def warning(self, msg: str):
        """发送警告消息"""
        self(msg, "warning")

    def error(self, msg: str):
        """发送错误消息"""
        self(msg, "error")

    def debug(self, msg: str):
        """发送调试消息"""
        self(msg, "debug")

    def progress(self, current: int, total: int, msg: str = ""):
        """
        发送进度消息

        Args:
            current: 当前进度
            total: 总数
            msg: 额外消息
        """
        percentage = (current / total * 100) if total > 0 else 0
        progress_msg = f"进度: {current}/{total} ({percentage:.1f}%)"

        if msg:
            progress_msg += f" - {msg}"

        self(progress_msg, "info")

    def step_start(self, step_name: str, total_steps: int = 0):
        """
        开始一个新步骤

        Args:
            step_name: 步骤名称
            total_steps: 总步骤数（用于计算百分比）
        """
        self.total_steps = total_steps
        self.info(f"🚀 开始: {step_name}")

    def step_complete(self, step_name: str):
        """
        完成一个步骤

        Args:
            step_name: 步骤名称
        """
        self.steps_completed += 1
        if self.total_steps > 0:
            self.success(f"✅ 完成: {step_name} ({self.steps_completed}/{self.total_steps})")
        else:
            self.success(f"✅ 完成: {step_name}")

    def step_error(self, step_name: str, error: str):
        """
        步骤出错

        Args:
            step_name: 步骤名称
            error: 错误信息
        """
        self.error(f"❌ 错误: {step_name} - {error}")

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "task_id": self.task_id,
            "elapsed_seconds": (datetime.now() - self.start_time).total_seconds(),
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps,
            "current_step": self.current_step,
            "error_count": len(self.errors),
            "errors": self.errors,
            "warning_count": len(self.warnings),
            "warnings": self.warnings
        }


class BatchProgressTracker:
    """
    批量处理进度追踪器

    用于追踪多个任务的整体进度
    """

    def __init__(
        self,
        total_items: int,
        callback: Optional[Callable] = None,
        task_id: str = ""
    ):
        self.total_items = total_items
        self.completed_items = 0
        self.failed_items = 0
        self.callback = ProgressCallback(callback, task_id)
        self.results: List[Any] = []
        self.start_time = datetime.now()

    def update(
        self,
        item_index: int,
        result: Any = None,
        error: Optional[str] = None
    ):
        """
        更新单个任务的状态

        Args:
            item_index: 任务索引
            result: 任务结果
            error: 错误信息（如果有）
        """
        self.completed_items += 1

        if error:
            self.failed_items += 1
            self.callback.warning(f"任务 {item_index} 失败: {error}")
        else:
            self.results.append(result)
            self.callback.progress(
                self.completed_items,
                self.total_items,
                f"已完成 {item_index}"
            )

    def complete(self):
        """批量处理完成"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.callback.success(
            f"🎉 批量处理完成！"
            f"总任务: {self.total_items}, "
            f"成功: {self.completed_items - self.failed_items}, "
            f"失败: {self.failed_items}, "
            f"耗时: {elapsed:.1f}s"
        )

    def get_summary(self) -> Dict[str, Any]:
        """获取处理摘要"""
        success_rate = (
            (self.total_items - self.failed_items) / self.total_items * 100
            if self.total_items > 0 else 0
        )

        return {
            "total": self.total_items,
            "completed": self.completed_items,
            "failed": self.failed_items,
            "success_rate": f"{success_rate:.1f}%",
            "results_count": len(self.results),
            "elapsed_seconds": (datetime.now() - self.start_time).total_seconds()
        }


class AsyncBatchProcessor:
    """
    异步批量处理器

    支持并发控制和进度追踪
    """

    def __init__(
        self,
        max_concurrency: int = 5,
        callback: Optional[Callable] = None,
        task_id: str = ""
    ):
        self.max_concurrency = max_concurrency
        self.callback = ProgressCallback(callback, task_id)
        self.limiter = asyncio.Semaphore(max_concurrency)

    async def process(
        self,
        items: List[Any],
        process_func: Callable,
        item_name: str = "item"
    ) -> List[Any]:
        """
        批量处理项目

        Args:
            items: 待处理项目列表
            process_func: 处理函数（异步）
            item_name: 项目名称（用于日志）

        Returns:
            处理结果列表
        """
        total = len(items)
        self.callback.info(f"开始批量处理 {total} 个{item_name}（并发度: {self.max_concurrency}）")

        async def worker(item: Any, idx: int):
            async with self.limiter:
                try:
                    result = await process_func(item)
                    self.callback.progress(idx + 1, total, f"处理 {item_name} {idx + 1}")
                    return result
                except Exception as e:
                    self.callback.error(f"处理 {item_name} {idx + 1} 失败: {e}")
                    return None

        tasks = [
            asyncio.create_task(worker(item, i))
            for i, item in enumerate(items)
        ]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            valid_results = [r for r in results if r is not None and not isinstance(r, Exception)]

            self.callback.success(f"批量处理完成！成功: {len(valid_results)}/{total}")

            return valid_results

        except Exception as e:
            self.callback.error(f"批量处理失败: {e}")
            return []
