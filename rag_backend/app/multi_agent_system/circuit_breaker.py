"""
Specialist Circuit Breaker — 智能体熔断器

追踪每个 specialist 的连续失败次数，超过阈值后自动熔断，
不再调用该 specialist，直接返回降级响应。

设计：
- 每个 specialist 独立追踪（finance / tax / legal）
- 熔断后冷却期内跳过执行，冷却结束后自动恢复
- 熔断期间输出置信度乘以权重，告知下游"此专家不可靠"
"""

import time
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class SpecialistCircuitBreaker:
    """智能体熔断器（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 熔断配置
        self.failure_threshold = 3          # 连续失败 3 次熔断
        self.cooldown_seconds = 300          # 冷却 5 分钟
        self.error_weight = 0.5              # 熔断期置信度乘 0.5

        # 运行时状态
        self._failures: Dict[str, int] = {}
        self._last_failure: Dict[str, float] = {}
        self._cooldown_until: Dict[str, float] = {}
        self._total_calls: Dict[str, int] = {}
        self._total_failures: Dict[str, int] = {}

    # ---- 记录 ----

    def record_success(self, specialist: str):
        """记录一次成功调用，重置连续失败计数"""
        self._failures[specialist] = 0
        self._total_calls[specialist] = self._total_calls.get(specialist, 0) + 1

    def record_failure(self, specialist: str):
        """记录一次失败，超过阈值则熔断"""
        self._failures[specialist] = self._failures.get(specialist, 0) + 1
        self._last_failure[specialist] = time.time()
        self._total_calls[specialist] = self._total_calls.get(specialist, 0) + 1
        self._total_failures[specialist] = self._total_failures.get(specialist, 0) + 1

        if self._failures[specialist] >= self.failure_threshold:
            cooldown_end = time.time() + self.cooldown_seconds
            self._cooldown_until[specialist] = cooldown_end
            logger.warning(
                "⛔ [熔断器] %s 连续失败 %d 次，熔断 %d 秒至 %s",
                specialist,
                self._failures[specialist],
                self.cooldown_seconds,
                time.strftime("%H:%M:%S", time.localtime(cooldown_end)),
            )

    # ---- 查询 ----

    def is_tripped(self, specialist: str) -> bool:
        """检查 specialist 是否处于熔断状态"""
        cooldown_end = self._cooldown_until.get(specialist)
        if cooldown_end is None:
            return False
        if time.time() < cooldown_end:
            return True
        # 冷却结束，自动恢复
        del self._cooldown_until[specialist]
        self._failures[specialist] = 0
        logger.info("✅ [熔断器] %s 冷却结束，已自动恢复", specialist)
        return False

    def get_confidence_multiplier(self, specialist: str) -> float:
        """获取置信度乘数（熔断期 = error_weight，正常 = 1.0）"""
        return self.error_weight if self.is_tripped(specialist) else 1.0

    def get_stats(self, specialist: str) -> dict:
        """获取指定 specialist 的统计信息"""
        return {
            "specialist": specialist,
            "total_calls": self._total_calls.get(specialist, 0),
            "total_failures": self._total_failures.get(specialist, 0),
            "consecutive_failures": self._failures.get(specialist, 0),
            "is_tripped": self.is_tripped(specialist),
            "cooldown_remaining": max(
                0, (self._cooldown_until.get(specialist, 0) - time.time())
            ),
        }

    def get_all_stats(self) -> list:
        """获取所有 specialist 的统计信息"""
        specialists = set(
            list(self._failures.keys())
            + list(self._cooldown_until.keys())
            + list(self._total_calls.keys())
        )
        return [self.get_stats(s) for s in sorted(specialists)]

    def reset(self, specialist: str = None):
        """重置指定（或全部）specialist 的计数"""
        if specialist:
            self._failures.pop(specialist, None)
            self._cooldown_until.pop(specialist, None)
            self._last_failure.pop(specialist, None)
        else:
            self._failures.clear()
            self._cooldown_until.clear()
            self._last_failure.clear()
            self._total_calls.clear()
            self._total_failures.clear()


# 全局单例
circuit_breaker = SpecialistCircuitBreaker()
