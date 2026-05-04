"""
RAG 检索质量自动化评估 (Golden Dataset Eval)

用法：
    python -m tests.evaluators.test_retrieval_recall [--report report.json]

每次更改切块参数、Embedding 模型或检索策略后运行此脚本。
计算 Recall@K / MRR / NDCG 等指标。
"""

import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Golden Dataset 路径
GOLDEN_DATASET_DIR = Path(__file__).parent / "golden_dataset"
QUERIES_PATH = GOLDEN_DATASET_DIR / "queries.json"

# 支持的指标
METRICS = ["recall@1", "recall@3", "recall@5", "mrr"]


class RAGEvaluator:
    """
    RAG 检索质量自动化评估。

    每次更改切块参数、Embedding 模型或检索策略后，运行此脚本。
    输出评估报告 JSON，对比不同配置下的召回率。
    """

    def __init__(self, queries_path: str = None):
        self.queries_path = queries_path or str(QUERIES_PATH)

    async def evaluate(self, config: Dict[str, Any] = None) -> Dict[str, float]:
        """
        用 Golden Dataset 评估当前配置。

        Args:
            config: 评估配置，如 {"domain": None, "top_k": 5}

        Returns:
            {"recall@1": 0.85, "recall@3": 0.92, "mrr": 0.88, ...}
        """
        config = config or {}

        # 加载测试集
        with open(self.queries_path, "r", encoding="utf-8") as f:
            queries = json.load(f)

        results = {metric: [] for metric in METRICS}

        for q in queries:
            # 执行检索
            hits = await self._retrieve(
                question=q["question"],
                domain=q.get("domain"),
                top_k=config.get("top_k", 5),
            )

            # 计算 Recall@K
            expected = set(str(e) for e in q.get("expected_chunks", []))
            if not expected:
                # 没有预期 chunk，跳过
                continue

            for k in [1, 3, 5]:
                top_k = set(h["chunk_id"] for h in hits[:k])
                recall = len(expected & top_k) / len(expected) if expected else 0
                results[f"recall@{k}"].append(recall)

            # 计算 MRR
            for rank, hit in enumerate(hits, 1):
                if hit["chunk_id"] in expected:
                    results["mrr"].append(1.0 / rank)
                    break
            else:
                results["mrr"].append(0.0)

        # 聚合
        metrics = {}
        for metric, values in results.items():
            if values:
                metrics[metric] = round(sum(values) / len(values), 4)
            else:
                metrics[metric] = 0.0

        return metrics

    async def _retrieve(
        self,
        question: str,
        domain: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        执行向量检索（通过 SearchService）。

        Args:
            question: 查询问题
            domain: 领域过滤（可选）
            top_k: 返回结果数

        Returns:
            检索结果列表，每项含 chunk_id, score, content
        """
        try:
            from app.services.search_service import search_service

            results = await search_service.search(
                query=question,
                top_k=top_k,
                domain=domain,
            )

            return [
                {
                    "chunk_id": r.chunk_id,
                    "score": r.score,
                    "content": r.content[:200],
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"检索失败: {e}")
            return []

    async def compare_configs(
        self,
        configs: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, float]]:
        """
        对比多种配置的评估结果。

        Args:
            configs: 配置列表，如 [
                {"domain": None, "top_k": 5},
                {"domain": "finance", "top_k": 5},
            ]

        Returns:
            {"config_tag": {"recall@1": 0.85, ...}, ...}
        """
        report = {}
        for config in configs:
            tag = (
                f"d_{config.get('domain', 'all')}"
                f"_k{config.get('top_k', 5)}"
            )
            logger.info(f"评估配置: {tag}")
            report[tag] = await self.evaluate(config)
        return report


# ============================================================
# 命令行入口
# ============================================================

async def main():
    """主入口：运行评估并输出报告"""
    import argparse

    parser = argparse.ArgumentParser(description="RAG 检索质量评估")
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="评估报告输出路径（可选，默认输出到控制台）",
    )
    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(level=logging.INFO)

    evaluator = RAGEvaluator()

    # 运行多种配置对比
    configs = [
        {"domain": None, "top_k": 5},
        {"domain": "finance", "top_k": 5},
        {"domain": "tax", "top_k": 5},
        {"domain": "legal", "top_k": 5},
        {"domain": "general", "top_k": 5},
    ]

    report = await evaluator.compare_configs(configs)

    # 输出报告
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print("\n=== RAG 评估报告 ===\n")
    print(output)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n报告已保存到: {args.report}")


if __name__ == "__main__":
    asyncio.run(main())
