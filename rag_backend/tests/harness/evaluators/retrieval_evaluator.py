"""
检索评估器

评估 RAG 系统的检索质量，计算 Recall@K, Precision@K, MRR, NDCG 等指标。
"""

import logging
import math
from typing import List, Dict, Any, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RetrievalMetrics:
    """
    检索评估指标

    包含各种检索质量指标。
    """
    recall_at_k: Dict[int, float] = field(default_factory=dict)  # Recall@K
    precision_at_k: Dict[int, float] = field(default_factory=dict)  # Precision@K
    mrr: float = 0.0  # Mean Reciprocal Rank
    ndcg_at_k: Dict[int, float] = field(default_factory=dict)  # NDCG@K
    hit_rate: float = 0.0  # 命中率
    avg_precision: float = 0.0  # 平均精确度 (MAP)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "recall_at_k": self.recall_at_k,
            "precision_at_k": self.precision_at_k,
            "mrr": self.mrr,
            "ndcg_at_k": self.ndcg_at_k,
            "hit_rate": self.hit_rate,
            "avg_precision": self.avg_precision
        }


class RetrievalEvaluator:
    """
    检索评估器

    评估检索系统的性能。
    """

    def __init__(self, k_values: List[int] = None):
        """
        初始化评估器

        Args:
            k_values: 要计算的 K 值列表，默认 [1, 3, 5, 10]
        """
        self.k_values = k_values or [1, 3, 5, 10]

    def evaluate(
        self,
        retrieved_docs: List[str],
        ground_truth_docs: List[str]
    ) -> RetrievalMetrics:
        """
        评估单次检索结果

        Args:
            retrieved_docs: 检索到的文档 ID 列表（按相关性排序）
            ground_truth_docs: 标准答案文档 ID 列表

        Returns:
            RetrievalMetrics: 评估指标
        """
        metrics = RetrievalMetrics()

        # 转换为集合以便快速查找
        ground_truth_set = set(ground_truth_docs)

        # 计算各 K 值的指标
        for k in self.k_values:
            # Recall@K
            metrics.recall_at_k[k] = self._calculate_recall_at_k(
                retrieved_docs, ground_truth_set, k
            )

            # Precision@K
            metrics.precision_at_k[k] = self._calculate_precision_at_k(
                retrieved_docs, ground_truth_set, k
            )

            # NDCG@K
            metrics.ndcg_at_k[k] = self._calculate_ndcg_at_k(
                retrieved_docs, ground_truth_docs, k
            )

        # MRR (Mean Reciprocal Rank)
        metrics.mrr = self._calculate_mrr(retrieved_docs, ground_truth_set)

        # Hit Rate
        metrics.hit_rate = self._calculate_hit_rate(retrieved_docs, ground_truth_set)

        # Average Precision
        metrics.avg_precision = self._calculate_average_precision(
            retrieved_docs, ground_truth_set
        )

        return metrics

    def evaluate_batch(
        self,
        batch_results: List[tuple[List[str], List[str]]]
    ) -> RetrievalMetrics:
        """
        批量评估

        Args:
            batch_results: (retrieved_docs, ground_truth_docs) 元组列表

        Returns:
            RetrievalMetrics: 平均评估指标
        """
        if not batch_results:
            return RetrievalMetrics()

        # 评估每个样本
        all_metrics = [
            self.evaluate(retrieved, ground_truth)
            for retrieved, ground_truth in batch_results
        ]

        # 计算平均值
        avg_metrics = RetrievalMetrics()

        # Recall@K
        for k in self.k_values:
            avg_metrics.recall_at_k[k] = sum(
                m.recall_at_k.get(k, 0) for m in all_metrics
            ) / len(all_metrics)

        # Precision@K
        for k in self.k_values:
            avg_metrics.precision_at_k[k] = sum(
                m.precision_at_k.get(k, 0) for m in all_metrics
            ) / len(all_metrics)

        # NDCG@K
        for k in self.k_values:
            avg_metrics.ndcg_at_k[k] = sum(
                m.ndcg_at_k.get(k, 0) for m in all_metrics
            ) / len(all_metrics)

        # MRR
        avg_metrics.mrr = sum(m.mrr for m in all_metrics) / len(all_metrics)

        # Hit Rate
        avg_metrics.hit_rate = sum(
            m.hit_rate for m in all_metrics
        ) / len(all_metrics)

        # Average Precision
        avg_metrics.avg_precision = sum(
            m.avg_precision for m in all_metrics
        ) / len(all_metrics)

        return avg_metrics

    def _calculate_recall_at_k(
        self,
        retrieved_docs: List[str],
        ground_truth_set: Set[str],
        k: int
    ) -> float:
        """
        计算 Recall@K

        Recall@K = |检索到的相关文档 ∩ 标准答案文档| / |标准答案文档|

        Args:
            retrieved_docs: 检索到的文档列表
            ground_truth_set: 标准答案文档集合
            k: Top-K

        Returns:
            Recall@K 值
        """
        if not ground_truth_set:
            return 0.0

        # 取前 K 个检索结果
        top_k_docs = set(retrieved_docs[:k])

        # 计算交集
        relevant_retrieved = top_k_docs & ground_truth_set

        return len(relevant_retrieved) / len(ground_truth_set)

    def _calculate_precision_at_k(
        self,
        retrieved_docs: List[str],
        ground_truth_set: Set[str],
        k: int
    ) -> float:
        """
        计算 Precision@K

        Precision@K = |检索到的相关文档| / K

        Args:
            retrieved_docs: 检索到的文档列表
            ground_truth_set: 标准答案文档集合
            k: Top-K

        Returns:
            Precision@K 值
        """
        if k == 0:
            return 0.0

        # 取前 K 个检索结果
        top_k_docs = retrieved_docs[:k]

        # 计算相关文档数
        relevant_count = sum(1 for doc in top_k_docs if doc in ground_truth_set)

        return relevant_count / k

    def _calculate_mrr(
        self,
        retrieved_docs: List[str],
        ground_truth_set: Set[str]
    ) -> float:
        """
        计算 MRR (Mean Reciprocal Rank)

        MRR = 1 / rank_of_first_relevant_doc

        Args:
            retrieved_docs: 检索到的文档列表
            ground_truth_set: 标准答案文档集合

        Returns:
            MRR 值
        """
        for i, doc in enumerate(retrieved_docs, start=1):
            if doc in ground_truth_set:
                return 1.0 / i

        return 0.0

    def _calculate_ndcg_at_k(
        self,
        retrieved_docs: List[str],
        ground_truth_docs: List[str],
        k: int
    ) -> float:
        """
        计算 NDCG@K (Normalized Discounted Cumulative Gain)

        DCG@K = Σ(rel_i / log2(i + 1))
        NDCG@K = DCG@K / IDCG@K

        Args:
            retrieved_docs: 检索到的文档列表
            ground_truth_docs: 标准答案文档列表（理想排序）
            k: Top-K

        Returns:
            NDCG@K 值
        """
        # 计算 DCG@K
        dcg = self._calculate_dcg(retrieved_docs, ground_truth_docs, k)

        # 计算 IDCG@K (理想情况下的 DCG)
        idcg = self._calculate_dcg(ground_truth_docs, ground_truth_docs, k)

        if idcg == 0:
            return 0.0

        return dcg / idcg

    def _calculate_dcg(
        self,
        retrieved_docs: List[str],
        ground_truth_docs: List[str],
        k: int
    ) -> float:
        """
        计算 DCG (Discounted Cumulative Gain)

        Args:
            retrieved_docs: 检索到的文档列表
            ground_truth_docs: 标准答案文档列表
            k: Top-K

        Returns:
            DCG 值
        """
        dcg = 0.0
        ground_truth_set = set(ground_truth_docs)

        for i, doc in enumerate(retrieved_docs[:k], start=1):
            # 计算相关性得分（在标准答案中 = 1，否则 = 0）
            rel = 1 if doc in ground_truth_set else 0

            # DCG 公式: rel / log2(i + 1)
            dcg += rel / math.log2(i + 1)

        return dcg

    def _calculate_hit_rate(
        self,
        retrieved_docs: List[str],
        ground_truth_set: Set[str]
    ) -> float:
        """
        计算命中率

        Hit Rate = 1 if 至少命中一个相关文档 else 0

        Args:
            retrieved_docs: 检索到的文档列表
            ground_truth_set: 标准答案文档集合

        Returns:
            命中率 (0 或 1)
        """
        for doc in retrieved_docs:
            if doc in ground_truth_set:
                return 1.0

        return 0.0

    def _calculate_average_precision(
        self,
        retrieved_docs: List[str],
        ground_truth_set: Set[str]
    ) -> float:
        """
        计算平均精确度 (Average Precision)

        AP = (Σ Precision@i * rel_i) / |相关文档|

        Args:
            retrieved_docs: 检索到的文档列表
            ground_truth_set: 标准答案文档集合

        Returns:
            AP 值
        """
        if not ground_truth_set:
            return 0.0

        relevant_count = 0
        precision_sum = 0.0

        for i, doc in enumerate(retrieved_docs, start=1):
            if doc in ground_truth_set:
                relevant_count += 1
                precision_at_i = relevant_count / i
                precision_sum += precision_at_i

        if relevant_count == 0:
            return 0.0

        return precision_sum / len(ground_truth_set)

    def print_metrics(self, metrics: RetrievalMetrics, title: str = "检索评估结果"):
        """
        打印评估指标

        Args:
            metrics: 评估指标
            title: 标题
        """
        print(f"\n{'='*60}")
        print(f"{title:^60}")
        print(f"{'='*60}\n")

        print(f"MRR (Mean Reciprocal Rank): {metrics.mrr:.4f}")
        print(f"Hit Rate: {metrics.hit_rate:.4f}")
        print(f"Average Precision (MAP): {metrics.avg_precision:.4f}")
        print()

        print("Recall@K:")
        for k in sorted(metrics.recall_at_k.keys()):
            print(f"  Recall@{k}: {metrics.recall_at_k[k]:.4f}")
        print()

        print("Precision@K:")
        for k in sorted(metrics.precision_at_k.keys()):
            print(f"  Precision@{k}: {metrics.precision_at_k[k]:.4f}")
        print()

        print("NDCG@K:")
        for k in sorted(metrics.ndcg_at_k.keys()):
            print(f"  NDCG@{k}: {metrics.ndcg_at_k[k]:.4f}")

        print(f"\n{'='*60}\n")


# 辅助函数

def evaluate_retrieval(
    retrieved_docs: List[str],
    ground_truth_docs: List[str],
    k_values: List[int] = None
) -> RetrievalMetrics:
    """
    评估检索结果（快捷函数）

    Args:
        retrieved_docs: 检索到的文档 ID 列表
        ground_truth_docs: 标准答案文档 ID 列表
        k_values: K 值列表

    Returns:
        RetrievalMetrics: 评估指标
    """
    evaluator = RetrievalEvaluator(k_values=k_values)
    return evaluator.evaluate(retrieved_docs, ground_truth_docs)
