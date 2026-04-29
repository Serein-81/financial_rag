import asyncio
import logging
from collections.abc import Awaitable, Coroutine
from typing import Any, Optional


logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Track long-lived background tasks and shut them down cleanly."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        name: str,
        coro: Coroutine[Any, Any, Any] | Awaitable[Any],
    ) -> asyncio.Task[Any]:
        async with self._lock:
            existing = self._tasks.get(name)
            if existing and not existing.done():
                raise RuntimeError(f"Background task already running: {name}")

            task = asyncio.create_task(coro, name=name)
            task.add_done_callback(self._on_task_done)
            self._tasks[name] = task
            logger.info("Started background task: %s", name)
            return task

    def _on_task_done(self, task: asyncio.Task[Any]) -> None:
        name = task.get_name()

        try:
            task.result()
        except asyncio.CancelledError:
            logger.info("Background task cancelled: %s", name)
        except Exception:
            logger.exception("Background task failed: %s", name)

    async def shutdown(self, timeout: float = 10.0) -> None:
        async with self._lock:
            tasks = [task for task in self._tasks.values() if not task.done()]

        if not tasks:
            return

        for task in tasks:
            task.cancel()

        done, pending = await asyncio.wait(tasks, timeout=timeout)

        for task in done:
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Background task failed during shutdown: %s", task.get_name())

        for task in pending:
            logger.warning("Background task did not stop within %.1fs: %s", timeout, task.get_name())

    async def get_status(self) -> dict[str, dict[str, Optional[str] | bool]]:
        async with self._lock:
            return {
                name: {
                    "done": task.done(),
                    "cancelled": task.cancelled(),
                    "exception": None if not task.done() or task.cancelled() else repr(task.exception()),
                }
                for name, task in self._tasks.items()
            }
