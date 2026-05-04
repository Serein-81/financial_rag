"""
上下文优化器 (Context Optimizer)

在 LLM chat() 调用前压缩消息列表，防止多轮工具调用后 context window 溢出。

三级压缩策略:
  Level 1 — 删除冗余（零成本，始终执行）
    移除 content 为空的消息、连续的重复 system 内容

  Level 2 — JSON 工具结果 → 单行摘要（低成本，始终执行）
    将 tool result 的完整 JSON 压缩为 key:value 摘要

  Level 3 — 滚动摘要（触发式，仅 token 超阈值时执行）
    将最早的 N 轮 (assistant + tool) 压缩为一条 system(summary)

用法:
    optimizer = ContextOptimizer()
    messages = optimizer.optimize(messages)
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ContextOptimizer:
    """上下文优化器"""

    # 不同模型的上下文窗口上限 token（留 20% 余量给生成）
    MODEL_WINDOWS: Dict[str, int] = {
        "deepseek/deepseek-v4-flash": 100_000,   # 原生 128K，留 28K
        "deepseek/deepseek-chat": 100_000,
        "default": 80_000,
    }

    # 等级 3 触发后，目标压缩到的 token 数
    TARGET_TOKENS = 60_000

    def __init__(
        self,
        model_name: str = "default",
        llm_adapter: Any = None,
    ):
        self.token_limit = self.MODEL_WINDOWS.get(model_name, self.MODEL_WINDOWS["default"])
        self.llm_adapter = llm_adapter  # 等级 3 摘要需要调 LLM
        self._stats = {"level1_count": 0, "level2_count": 0, "level3_count": 0}

    # =====================================================================
    # 公开入口
    # =====================================================================

    def optimize(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对消息列表执行三级压缩。

        Args:
            messages: 消息列表 [{"role":..., "content":...}, ...]

        Returns:
            压缩后的消息列表（可能返回新列表，不会原地修改）
        """
        if not messages:
            return messages

        original_tokens = self._estimate_tokens(messages)
        if original_tokens < self.token_limit:
            return messages  # 没超阈值，不压缩

        logger.info(
            "[ContextOptimizer] 触发压缩: %d tokens > %d limit",
            original_tokens, self.token_limit,
        )

        result = self._level1_deduplicate(messages)

        result = self._level2_compress_tool_results(result)

        if self._estimate_tokens(result) < self.token_limit:
            return result

        result = self._level3_rollup(result)

        after_tokens = self._estimate_tokens(result)
        logger.info(
            "[ContextOptimizer] 压缩完成: %d → %d tokens (%.0f%%)",
            original_tokens, after_tokens,
            (1 - after_tokens / original_tokens) * 100 if original_tokens > 0 else 0,
        )
        return result

    # =====================================================================
    # Token 估算（中文 ~0.25 token/字，英文 ~0.3 token/字）
    # =====================================================================

    @staticmethod
    def _estimate_tokens(messages: List[Dict[str, Any]]) -> int:
        """估算消息列表总 token 数"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                # 中文每个字约 0.25 token，英文每个字符约 0.1 token
                cjk = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
                total += int(cjk * 0.5 + (len(content) - cjk) * 0.15)
            # 每条消息的 role + 结构开销
            total += 5

            tool_calls = msg.get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    total += 30  # tool_calls 结构开销
                    func = tc.get("function", {})
                    total += len(func.get("name", "")) * 0.15
                    total += len(func.get("arguments", "")) * 0.15
        return total

    # =====================================================================
    # Level 1: 删除冗余
    # =====================================================================

    @staticmethod
    def _level1_deduplicate(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        等级 1 压缩：删除冗余消息。

        - 删除 content 为空（且无 tool_calls）的 assistant 消息
        - 合并连续的 system 消息
        """
        if not messages:
            return messages

        result = []

        # 标记需要保留的索引
        skip_indices = set()

        # 找到 system prompt 的起止位置，保留第一个 system
        first_system_idx = None
        last_user_idx = None

        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            content = msg.get("content", "")

            # 跳过空消息（非 tool 且有 content）
            if role == "assistant" and not content and not msg.get("tool_calls"):
                skip_indices.add(i)
                continue
            if role == "tool" and not content:
                skip_indices.add(i)
                continue

            if role == "system" and first_system_idx is None:
                first_system_idx = i

        # 构建结果
        for i, msg in enumerate(messages):
            if i in skip_indices:
                continue
            result.append(msg)

        removed = len(messages) - len(result)
        if removed > 0:
            logger.debug("[ContextOptimizer] Level 1: 移除 %d 条冗余消息", removed)

        return result

    # =====================================================================
    # Level 2: JSON → 单行摘要
    # =====================================================================

    @staticmethod
    def _level2_compress_tool_results(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        等级 2 压缩：将 tool result 的 JSON 压缩为单行文本摘要。

        策略:
        - 保留 status、summary 中的关键指标
        - 删除 data（详细记录）、message（空消息）
        - 提取 fiscal_year、total_revenue、total_profit 等高价值字段
        """
        result = []
        compressed_count = 0

        for msg in messages:
            if msg.get("role") != "tool":
                result.append(msg)
                continue

            content = msg.get("content", "")
            if not content:
                result.append(msg)
                continue

            # 尝试解析 JSON
            try:
                data = json.loads(content) if isinstance(content, str) else content
            except (json.JSONDecodeError, TypeError):
                result.append(msg)
                continue

            if not isinstance(data, dict):
                result.append(msg)
                continue

            # 提取关键字段
            parts = []

            # 工具名称（从 tool_call_id 的前缀推断，不可靠）
            # 直接从 content 中提取有用信息
            status = data.get("status", "")

            # 从 summary 或 data 中提取
            summary = data.get("summary") or {}
            raw_data = data.get("data") or {}
            fiscal_year = data.get("fiscal_year") or summary.get("fiscal_year")

            if status:
                parts.append(f"status={status}")

            if fiscal_year:
                parts.append(f"fy={fiscal_year}")

            # 提取常见财务指标
            financial_keys = [
                ("total_revenue", "营收"),
                ("total_profit", "利润"),
                ("total_expenses", "总支出"),
                ("total_cost", "总成本"),
                ("avg_profit_margin", "利润率"),
                ("net_income", "净利润"),
                ("gross_profit", "毛利润"),
                ("operating_profit", "营业利润"),
            ]

            for eng_key, cn_key in financial_keys:
                val = summary.get(eng_key) or raw_data.get(eng_key)
                if val is not None:
                    if isinstance(val, float):
                        parts.append(f"{cn_key}={val:,.2f}")
                    else:
                        parts.append(f"{cn_key}={val}")

            # 提取 error 信息
            error = data.get("error") or data.get("message")
            if error and isinstance(error, str) and error != "null":
                parts.append(f"error={error[:80]}")

            # 构建压缩后的内容
            if parts:
                compressed = " | ".join(parts)
                compressed_count += 1
                original_len = len(content)
                logger.debug(
                    "[ContextOptimizer] Level 2: %d → %d 字符 (%.0f%%)",
                    original_len, len(compressed),
                    (1 - len(compressed) / original_len) * 100 if original_len > 0 else 0,
                )
                result.append({"role": "tool", "tool_call_id": msg.get("tool_call_id", ""), "content": compressed})
            else:
                result.append(msg)

        if compressed_count > 0:
            logger.debug("[ContextOptimizer] Level 2: 压缩 %d 条 tool result", compressed_count)

        return result

    # =====================================================================
    # Level 3: 多轮滚动摘要
    # =====================================================================

    def _level3_rollup(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        等级 3 压缩：将最早的 N 轮 (assistant + tool) 压缩为一条 system(summary)。

        选择策略：
        - 跳过第一个 system（系统提示词）和最后一个 user（用户查询）
        - 从最早的消息开始，每遇到 assistant + 后续的 tool 算一轮
        - 将连续的整轮打包为摘要文本
        """
        # 始终使用纯文本拼接（不依赖 LLM 摘要，避免引入额外 token 开销）
        # 找到第一个 user 消息的位置（保留它和它之后的所有消息）
        first_user_idx = None
        for i, msg in enumerate(messages):
            if msg.get("role") == "user":
                first_user_idx = i
                break

        if first_user_idx is None or first_user_idx <= 1:
            # 只有 user 消息或更少，无法压缩
            return messages

        # 要压缩的部分：第一个 system 之后 ~ first_user_idx 之前
        # （保留第一个 system 和最后一个 user）
        preserved = messages[:1]  # 第一个 system
        to_compress = messages[1:first_user_idx]
        tail = messages[first_user_idx:]

        if not to_compress:
            return messages

        # 将历史轮次打包成文本
        round_texts = []
        current_round = []

        for msg in to_compress:
            role = msg.get("role", "")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls")

            if role == "assistant":
                if current_round:
                    round_texts.append(self._format_round(current_round))
                current_round = [msg]
            elif role == "tool" and current_round:
                current_round.append(msg)
            else:
                if current_round:
                    round_texts.append(self._format_round(current_round))
                    current_round = []
                if content:
                    round_texts.append(f"[{role}]: {content[:200]}")

        if current_round:
            round_texts.append(self._format_round(current_round))

        if not round_texts:
            return messages

        history_text = "\n".join(round_texts)

        # 如果文本太长，截断
        if len(history_text) > 2000:
            history_text = history_text[:2000] + "\n... (截断)"

        summary = f"以下为之前的历史交互摘要：\n{history_text}"

        preserved.append({"role": "system", "content": summary})
        preserved.extend(tail)

        self._stats["level3_count"] += 1
        logger.debug("[ContextOptimizer] Level 3: %d 条消息 → 1 条摘要", len(to_compress))

        return preserved

    @staticmethod
    def _format_round(round_msgs: List[Dict[str, Any]]) -> str:
        """将一轮 (assistant + tool) 格式化为文本"""
        parts = []
        for msg in round_msgs:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "assistant":
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    names = []
                    for tc in tool_calls:
                        func = tc.get("function", {})
                        n = func.get("name", "")
                        args = func.get("arguments", "")
                        names.append(f"{n}({args[:60]})")
                    # 对 content 截断
                    content_preview = content[:100] if content else ""
                    parts.append(f"助手调用工具: {', '.join(names)} {content_preview}")
                else:
                    parts.append(f"助手: {content[:200]}")
            elif role == "tool":
                parts.append(f"工具返回: {content[:200]}")

        return "\n".join(parts)

    # =====================================================================
    # 统计信息
    # =====================================================================

    def get_stats(self) -> Dict[str, int]:
        return dict(self._stats)
