"""
断崖截断器 (Cliff Pruner)

不做固定 Top-K 截断。bge-reranker-v2-m3 的得分分布随
领域和查询类型剧烈变化（英文 0.995 vs 中文 0.2093），
固定阈值不可靠。

改用动态断崖检测：
  从第 min_results 条开始，检查相邻条目的得分差。
  如果差值 > cliff_threshold，则判定为断崖，
  断崖后的条目全部抛弃。
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def cliff_prune(
    items: List[Dict[str, Any]],
    score_key: str = "rerank_score",
    min_results: int = 3,
    max_results: int = 20,
    cliff_threshold: float = 0.15,
) -> List[Dict[str, Any]]:
    """
    断崖截断：检测排序得分中的断层，断层后全部抛弃。

    Args:
        items: 按得分降序排列的条目列表
        score_key: 得分字段名
        min_results: 最少保留数
        max_results: 最多保留数
        cliff_threshold: 相邻得分差阈值

    Returns:
        截断后的条目列表
    """
    if not items:
        return []

    sorted_items = sorted(
        items, key=lambda x: x.get(score_key, 0) or 0, reverse=True
    )

    if len(sorted_items) <= min_results:
        return sorted_items[:max_results]

    for i in range(min_results, len(sorted_items)):
        prev_score = sorted_items[i - 1].get(score_key, 0) or 0
        curr_score = sorted_items[i].get(score_key, 0) or 0
        gap = prev_score - curr_score

        if gap > cliff_threshold:
            logger.debug(
                f"[CliffPruner] 断崖: 位置 {i}, "
                f"得分 {prev_score:.4f} -> {curr_score:.4f}, "
                f"Delta={gap:.4f} > {cliff_threshold}, 截断于 {i} 条"
            )
            return sorted_items[:i]

    return sorted_items[:max_results]
