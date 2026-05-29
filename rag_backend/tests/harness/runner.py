"""
评估运行器

端到端运行 RAG 系统评估。
"""

import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from tests.harness.dataset import TestDataset, TestCase
from tests.harness.evaluators.retrieval_evaluator import (
    RetrievalEvaluator,
    RetrievalMetrics
)
from tests.harness.evaluators.generation_evaluator import (
    GenerationEvaluator,
    GenerationMetrics
)

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """
    单个测试用例的评估结果
    """
    test_case_id: str
    query: str
    difficulty: str
    category: str

    # 检索结果
    retrieved_chunks: List[str]
    retrieval_time_ms: float
    retrieval_metrics: RetrievalMetrics

    # 生成结果
    generated_answer: str
    generation_time_ms: float
    generation_metrics: GenerationMetrics

    # 总体
    total_time_ms: float
    success: bool = True
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "test_case_id": self.test_case_id,
            "query": self.query,
            "difficulty": self.difficulty,
            "category": self.category,
            "retrieved_chunks": self.retrieved_chunks,
            "retrieval_time_ms": self.retrieval_time_ms,
            "retrieval_metrics": self.retrieval_metrics.to_dict(),
            "generated_answer": self.generated_answer,
            "generation_time_ms": self.generation_time_ms,
            "generation_metrics": self.generation_metrics.to_dict(),
            "total_time_ms": self.total_time_ms,
            "success": self.success,
            "error_message": self.error_message
        }


@dataclass
class EvaluationReport:
    """
    评估报告

    包含所有测试用例的评估结果和统计信息。
    """
    dataset_name: str
    dataset_version: str
    evaluation_time: datetime
    total_cases: int
    successful_cases: int
    failed_cases: int

    # 检索评估
    avg_retrieval_metrics: RetrievalMetrics

    # 生成评估
    avg_generation_metrics: GenerationMetrics

    # 性能统计
    avg_retrieval_time_ms: float
    avg_generation_time_ms: float
    avg_total_time_ms: float

    # 按难度统计
    by_difficulty: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 按类别统计
    by_category: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 详细结果
    results: List[EvaluationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "evaluation_time": self.evaluation_time.isoformat(),
            "total_cases": self.total_cases,
            "successful_cases": self.successful_cases,
            "failed_cases": self.failed_cases,
            "avg_retrieval_metrics": self.avg_retrieval_metrics.to_dict(),
            "avg_generation_metrics": self.avg_generation_metrics.to_dict(),
            "avg_retrieval_time_ms": self.avg_retrieval_time_ms,
            "avg_generation_time_ms": self.avg_generation_time_ms,
            "avg_total_time_ms": self.avg_total_time_ms,
            "by_difficulty": self.by_difficulty,
            "by_category": self.by_category,
            "results": [r.to_dict() for r in self.results]
        }


class EvaluationRunner:
    """
    评估运行器

    运行端到端的 RAG 系统评估。
    """

    def __init__(
        self,
        rag_system,
        retrieval_evaluator: Optional[RetrievalEvaluator] = None,
        generation_evaluator: Optional[GenerationEvaluator] = None
    ):
        """
        初始化运行器

        Args:
            rag_system: RAG 系统实例
            retrieval_evaluator: 检索评估器（可选）
            generation_evaluator: 生成评估器（可选）
        """
        self.rag_system = rag_system
        self.retrieval_evaluator = retrieval_evaluator or RetrievalEvaluator()
        self.generation_evaluator = generation_evaluator or GenerationEvaluator()

    async def run(
        self,
        dataset: TestDataset,
        verbose: bool = True
    ) -> EvaluationReport:
        """
        运行评估

        Args:
            dataset: 测试数据集
            verbose: 是否打印详细信息

        Returns:
            EvaluationReport: 评估报告
        """
        logger.info(
            f"[EvaluationRunner] 开始评估 - "
            f"数据集: {dataset.name}, 测试用例数: {len(dataset)}"
        )

        results: List[EvaluationResult] = []

        for i, test_case in enumerate(dataset.test_cases, start=1):
            if verbose:
                print(f"\n[{i}/{len(dataset)}] 评估用例: {test_case.id}")
                print(f"查询: {test_case.query}")

            try:
                result = await self._evaluate_single_case(test_case, verbose)
                results.append(result)

                if verbose:
                    print(f"✓ 评估完成 - 总时间: {result.total_time_ms:.0f}ms")

            except Exception as e:
                logger.error(f"[EvaluationRunner] 评估失败 - 用例: {test_case.id}, 错误: {e}")
                # 创建失败结果
                result = EvaluationResult(
                    test_case_id=test_case.id,
                    query=test_case.query,
                    difficulty=test_case.difficulty.value,
                    category=test_case.category.value,
                    retrieved_chunks=[],
                    retrieval_time_ms=0,
                    retrieval_metrics=RetrievalMetrics(),
                    generated_answer="",
                    generation_time_ms=0,
                    generation_metrics=GenerationMetrics(),
                    total_time_ms=0,
                    success=False,
                    error_message=str(e)
                )
                results.append(result)

                if verbose:
                    print(f"✗ 评估失败: {e}")

        # 生成报告
        report = self._generate_report(dataset, results)

        logger.info(
            f"[EvaluationRunner] 评估完成 - "
            f"成功: {report.successful_cases}/{report.total_cases}"
        )

        return report

    async def _evaluate_single_case(
        self,
        test_case: TestCase,
        verbose: bool = False
    ) -> EvaluationResult:
        """
        评估单个测试用例

        Args:
            test_case: 测试用例
            verbose: 是否打印详细信息

        Returns:
            EvaluationResult: 评估结果
        """
        total_start = time.time()

        # 1. 执行检索
        retrieval_start = time.time()
        retrieved_chunks = await self.rag_system.retrieve(
            query=test_case.query,
            kb_id=test_case.kb_id
        )
        retrieval_time = (time.time() - retrieval_start) * 1000

        # 提取文档 ID
        retrieved_doc_ids = [chunk.get("id", "") for chunk in retrieved_chunks]

        # 评估检索
        retrieval_metrics = self.retrieval_evaluator.evaluate(
            retrieved_doc_ids,
            test_case.ground_truth_chunks
        )

        if verbose:
            print(f"  检索: {len(retrieved_doc_ids)} 个文档, Recall@5={retrieval_metrics.recall_at_k.get(5, 0):.2f}")

        # 2. 执行生成
        generation_start = time.time()
        generated_answer = await self.rag_system.generate(
            query=test_case.query,
            context=retrieved_chunks
        )
        generation_time = (time.time() - generation_start) * 1000

        # 评估生成
        context_text = "\n".join(chunk.get("content", "") for chunk in retrieved_chunks)
        generation_metrics = await self.generation_evaluator.evaluate(
            query=test_case.query,
            generated_answer=generated_answer,
            expected_answer=test_case.expected_answer,
            context=context_text
        )

        if verbose:
            print(f"  生成: 综合评分={generation_metrics.overall_score:.2f}/5")

        total_time = (time.time() - total_start) * 1000

        return EvaluationResult(
            test_case_id=test_case.id,
            query=test_case.query,
            difficulty=test_case.difficulty.value,
            category=test_case.category.value,
            retrieved_chunks=retrieved_doc_ids,
            retrieval_time_ms=retrieval_time,
            retrieval_metrics=retrieval_metrics,
            generated_answer=generated_answer,
            generation_time_ms=generation_time,
            generation_metrics=generation_metrics,
            total_time_ms=total_time,
            success=True
        )

    def _generate_report(
        self,
        dataset: TestDataset,
        results: List[EvaluationResult]
    ) -> EvaluationReport:
        """
        生成评估报告

        Args:
            dataset: 测试数据集
            results: 评估结果列表

        Returns:
            EvaluationReport: 评估报告
        """
        # 统计成功/失败
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]

        # 计算平均检索指标
        avg_retrieval_metrics = self.retrieval_evaluator.evaluate_batch([
            (r.retrieved_chunks, r.retrieval_metrics.recall_at_k)
            for r in successful_results
        ]) if successful_results else RetrievalMetrics()

        # 计算平均生成指标
        avg_generation_metrics = self.generation_evaluator.calculate_average_metrics([
            r.generation_metrics for r in successful_results
        ]) if successful_results else GenerationMetrics()

        # 计算性能统计
        avg_retrieval_time = sum(
            r.retrieval_time_ms for r in successful_results
        ) / len(successful_results) if successful_results else 0

        avg_generation_time = sum(
            r.generation_time_ms for r in successful_results
        ) / len(successful_results) if successful_results else 0

        avg_total_time = sum(
            r.total_time_ms for r in successful_results
        ) / len(successful_results) if successful_results else 0

        # 按难度统计
        by_difficulty = self._group_by_attribute(successful_results, "difficulty")

        # 按类别统计
        by_category = self._group_by_attribute(successful_results, "category")

        return EvaluationReport(
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            evaluation_time=datetime.now(),
            total_cases=len(results),
            successful_cases=len(successful_results),
            failed_cases=len(failed_results),
            avg_retrieval_metrics=avg_retrieval_metrics,
            avg_generation_metrics=avg_generation_metrics,
            avg_retrieval_time_ms=avg_retrieval_time,
            avg_generation_time_ms=avg_generation_time,
            avg_total_time_ms=avg_total_time,
            by_difficulty=by_difficulty,
            by_category=by_category,
            results=results
        )

    def _group_by_attribute(
        self,
        results: List[EvaluationResult],
        attribute: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        按属性分组统计

        Args:
            results: 评估结果列表
            attribute: 属性名称 (difficulty / category)

        Returns:
            分组统计结果
        """
        grouped = {}

        for result in results:
            key = getattr(result, attribute)

            if key not in grouped:
                grouped[key] = {
                    "count": 0,
                    "avg_overall_score": 0.0,
                    "avg_recall_at_5": 0.0,
                    "avg_total_time_ms": 0.0
                }

            grouped[key]["count"] += 1
            grouped[key]["avg_overall_score"] += result.generation_metrics.overall_score
            grouped[key]["avg_recall_at_5"] += result.retrieval_metrics.recall_at_k.get(5, 0)
            grouped[key]["avg_total_time_ms"] += result.total_time_ms

        # 计算平均值
        for key in grouped:
            count = grouped[key]["count"]
            grouped[key]["avg_overall_score"] /= count
            grouped[key]["avg_recall_at_5"] /= count
            grouped[key]["avg_total_time_ms"] /= count

        return grouped

    def print_report(self, report: EvaluationReport):
        """
        打印评估报告

        Args:
            report: 评估报告
        """
        print(f"\n{'='*80}")
        print(f"RAG 系统评估报告".center(80))
        print(f"{'='*80}\n")

        print(f"数据集: {report.dataset_name} v{report.dataset_version}")
        print(f"评估时间: {report.evaluation_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试用例: {report.total_cases} 个")
        print(f"成功: {report.successful_cases} 个, 失败: {report.failed_cases} 个")
        print()

        print(f"{'检索评估':-^80}")
        print(f"Recall@5: {report.avg_retrieval_metrics.recall_at_k.get(5, 0):.4f}")
        print(f"Precision@5: {report.avg_retrieval_metrics.precision_at_k.get(5, 0):.4f}")
        print(f"MRR: {report.avg_retrieval_metrics.mrr:.4f}")
        print(f"NDCG@5: {report.avg_retrieval_metrics.ndcg_at_k.get(5, 0):.4f}")
        print()

        print(f"{'生成评估':-^80}")
        print(f"准确性: {report.avg_generation_metrics.accuracy_score:.2f}/5")
        print(f"完整性: {report.avg_generation_metrics.completeness_score:.2f}/5")
        print(f"相关性: {report.avg_generation_metrics.relevance_score:.2f}/5")
        print(f"流畅性: {report.avg_generation_metrics.fluency_score:.2f}/5")
        print(f"综合评分: {report.avg_generation_metrics.overall_score:.2f}/5")
        print()

        print(f"{'性能统计':-^80}")
        print(f"平均检索时间: {report.avg_retrieval_time_ms:.0f} ms")
        print(f"平均生成时间: {report.avg_generation_time_ms:.0f} ms")
        print(f"平均总时间: {report.avg_total_time_ms:.0f} ms")
        print()

        if report.by_difficulty:
            print(f"{'按难度统计':-^80}")
            for difficulty, stats in report.by_difficulty.items():
                print(f"{difficulty}: {stats['count']} 个, "
                      f"综合评分={stats['avg_overall_score']:.2f}/5, "
                      f"Recall@5={stats['avg_recall_at_5']:.2f}")
            print()

        if report.by_category:
            print(f"{'按类别统计':-^80}")
            for category, stats in report.by_category.items():
                print(f"{category}: {stats['count']} 个, "
                      f"综合评分={stats['avg_overall_score']:.2f}/5, "
                      f"Recall@5={stats['avg_recall_at_5']:.2f}")
            print()

        print(f"{'='*80}\n")


# 辅助函数

async def run_evaluation(
    rag_system,
    dataset: TestDataset,
    verbose: bool = True
) -> EvaluationReport:
    """
    运行评估（快捷函数）

    Args:
        rag_system: RAG 系统实例
        dataset: 测试数据集
        verbose: 是否打印详细信息

    Returns:
        EvaluationReport: 评估报告
    """
    runner = EvaluationRunner(rag_system)
    return await runner.run(dataset, verbose=verbose)
