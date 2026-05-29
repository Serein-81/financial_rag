"""
测试数据集管理

定义测试数据集的结构、加载和管理功能。
"""

import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class DifficultyLevel(str, Enum):
    """难度级别"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionCategory(str, Enum):
    """问题类别"""
    FACTUAL = "factual"  # 事实性问题
    REASONING = "reasoning"  # 推理性问题
    MULTI_HOP = "multi_hop"  # 多跳问题
    COMPARISON = "comparison"  # 比较性问题
    PROCEDURAL = "procedural"  # 流程性问题
    ANALYTICAL = "analytical"  # 分析性问题


@dataclass
class TestCase:
    """
    单个测试用例

    包含查询、期望答案、标准文档等信息。
    """
    id: str
    query: str
    expected_answer: str
    ground_truth_chunks: List[str]  # 标准答案文档 ID 列表
    difficulty: DifficultyLevel
    category: QuestionCategory
    kb_id: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "query": self.query,
            "expected_answer": self.expected_answer,
            "ground_truth_chunks": self.ground_truth_chunks,
            "difficulty": self.difficulty.value if isinstance(self.difficulty, DifficultyLevel) else self.difficulty,
            "category": self.category.value if isinstance(self.category, QuestionCategory) else self.category,
            "kb_id": self.kb_id,
            "metadata": self.metadata,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestCase":
        """从字典创建"""
        return cls(
            id=data["id"],
            query=data["query"],
            expected_answer=data["expected_answer"],
            ground_truth_chunks=data.get("ground_truth_chunks", []),
            difficulty=DifficultyLevel(data.get("difficulty", "medium")),
            category=QuestionCategory(data.get("category", "factual")),
            kb_id=data.get("kb_id", "default"),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", [])
        )


@dataclass
class TestDataset:
    """
    测试数据集

    包含多个测试用例的集合。
    """
    name: str
    version: str
    description: str
    test_cases: List[TestCase]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.test_cases)

    def __getitem__(self, index: int) -> TestCase:
        return self.test_cases[index]

    def filter_by_difficulty(self, difficulty: DifficultyLevel) -> List[TestCase]:
        """按难度过滤"""
        return [tc for tc in self.test_cases if tc.difficulty == difficulty]

    def filter_by_category(self, category: QuestionCategory) -> List[TestCase]:
        """按类别过滤"""
        return [tc for tc in self.test_cases if tc.category == category]

    def filter_by_tags(self, tags: List[str]) -> List[TestCase]:
        """按标签过滤"""
        return [
            tc for tc in self.test_cases
            if any(tag in tc.tags for tag in tags)
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """获取数据集统计信息"""
        stats = {
            "total_cases": len(self.test_cases),
            "by_difficulty": {},
            "by_category": {},
            "avg_query_length": 0,
            "avg_answer_length": 0
        }

        # 按难度统计
        for difficulty in DifficultyLevel:
            count = len(self.filter_by_difficulty(difficulty))
            stats["by_difficulty"][difficulty.value] = count

        # 按类别统计
        for category in QuestionCategory:
            count = len(self.filter_by_category(category))
            stats["by_category"][category.value] = count

        # 平均长度
        if self.test_cases:
            stats["avg_query_length"] = sum(
                len(tc.query) for tc in self.test_cases
            ) / len(self.test_cases)
            stats["avg_answer_length"] = sum(
                len(tc.expected_answer) for tc in self.test_cases
            ) / len(self.test_cases)

        return stats

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestDataset":
        """从字典创建"""
        return cls(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            test_cases=[
                TestCase.from_dict(tc_data)
                for tc_data in data.get("test_cases", [])
            ],
            metadata=data.get("metadata", {})
        )


class DatasetLoader:
    """
    数据集加载器

    支持从 JSON 文件加载测试数据集。
    """

    def __init__(self, datasets_dir: str = "tests/harness/datasets"):
        """
        初始化加载器

        Args:
            datasets_dir: 数据集目录路径
        """
        self.datasets_dir = Path(datasets_dir)
        self.datasets_dir.mkdir(parents=True, exist_ok=True)

    def load(self, dataset_name: str) -> TestDataset:
        """
        加载数据集

        Args:
            dataset_name: 数据集名称（不带扩展名）

        Returns:
            TestDataset: 加载的数据集
        """
        file_path = self.datasets_dir / f"{dataset_name}.json"

        if not file_path.exists():
            raise FileNotFoundError(f"数据集文件不存在: {file_path}")

        logger.info(f"[DatasetLoader] 加载数据集: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        dataset = TestDataset.from_dict(data)

        logger.info(
            f"[DatasetLoader] 数据集加载成功: {dataset.name} v{dataset.version}, "
            f"{len(dataset)} 个测试用例"
        )

        return dataset

    def save(self, dataset: TestDataset, dataset_name: Optional[str] = None):
        """
        保存数据集

        Args:
            dataset: 数据集对象
            dataset_name: 数据集名称（可选，默认使用 dataset.name）
        """
        name = dataset_name or dataset.name
        file_path = self.datasets_dir / f"{name}.json"

        logger.info(f"[DatasetLoader] 保存数据集: {file_path}")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(dataset.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"[DatasetLoader] 数据集保存成功")

    def list_datasets(self) -> List[str]:
        """
        列出所有可用的数据集

        Returns:
            数据集名称列表
        """
        if not self.datasets_dir.exists():
            return []

        datasets = [
            f.stem for f in self.datasets_dir.glob("*.json")
        ]

        return sorted(datasets)


class DatasetBuilder:
    """
    数据集构建器

    帮助快速构建测试数据集。
    """

    def __init__(self, name: str, version: str = "1.0", description: str = ""):
        """
        初始化构建器

        Args:
            name: 数据集名称
            version: 版本号
            description: 描述
        """
        self.name = name
        self.version = version
        self.description = description
        self.test_cases: List[TestCase] = []

    def add_case(
        self,
        case_id: str,
        query: str,
        expected_answer: str,
        ground_truth_chunks: List[str],
        difficulty: DifficultyLevel = DifficultyLevel.MEDIUM,
        category: QuestionCategory = QuestionCategory.FACTUAL,
        kb_id: str = "default",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "DatasetBuilder":
        """
        添加测试用例

        Args:
            case_id: 用例 ID
            query: 查询
            expected_answer: 期望答案
            ground_truth_chunks: 标准文档 ID 列表
            difficulty: 难度级别
            category: 问题类别
            kb_id: 知识库 ID
            tags: 标签列表
            metadata: 元数据

        Returns:
            self（支持链式调用）
        """
        test_case = TestCase(
            id=case_id,
            query=query,
            expected_answer=expected_answer,
            ground_truth_chunks=ground_truth_chunks,
            difficulty=difficulty,
            category=category,
            kb_id=kb_id,
            tags=tags or [],
            metadata=metadata or {}
        )

        self.test_cases.append(test_case)
        return self

    def build(self) -> TestDataset:
        """
        构建数据集

        Returns:
            TestDataset: 构建的数据集
        """
        return TestDataset(
            name=self.name,
            version=self.version,
            description=self.description,
            test_cases=self.test_cases
        )


# 辅助函数

def create_sample_dataset() -> TestDataset:
    """
    创建示例数据集

    Returns:
        TestDataset: 示例数据集
    """
    builder = DatasetBuilder(
        name="tax_qa_sample",
        version="1.0",
        description="税务问答示例数据集"
    )

    # 简单事实性问题
    builder.add_case(
        case_id="tax_001",
        query="企业所得税的标准税率是多少？",
        expected_answer="企业所得税的标准税率为25%。",
        ground_truth_chunks=["doc_tax_rate_001"],
        difficulty=DifficultyLevel.EASY,
        category=QuestionCategory.FACTUAL,
        tags=["企业所得税", "税率"]
    )

    # 中等推理问题
    builder.add_case(
        case_id="tax_002",
        query="小型微利企业享受哪些税收优惠？",
        expected_answer="小型微利企业所得税税率为20%，年应纳税所得额不超过100万元的部分，减按12.5%计入应纳税所得额，实际税负为2.5%；超过100万元但不超过300万元的部分，减按25%计入，实际税负为5%。",
        ground_truth_chunks=["doc_small_enterprise_001", "doc_tax_incentive_001"],
        difficulty=DifficultyLevel.MEDIUM,
        category=QuestionCategory.REASONING,
        tags=["小型微利企业", "税收优惠"]
    )

    # 困难多跳问题
    builder.add_case(
        case_id="tax_003",
        query="为什么高新技术企业能享受15%的优惠税率？",
        expected_answer="高新技术企业享受15%的优惠税率是因为国家鼓励科技创新和技术进步。根据《企业所得税法》规定，国家需要重点扶持的高新技术企业，减按15%的税率征收企业所得税，目的是促进企业加大研发投入，推动产业升级和经济转型。",
        ground_truth_chunks=["doc_high_tech_001", "doc_policy_reason_001", "doc_law_001"],
        difficulty=DifficultyLevel.HARD,
        category=QuestionCategory.MULTI_HOP,
        tags=["高新技术企业", "税收优惠", "政策原因"]
    )

    return builder.build()


def load_dataset(dataset_name: str, datasets_dir: str = "tests/harness/datasets") -> TestDataset:
    """
    加载数据集（快捷函数）

    Args:
        dataset_name: 数据集名称
        datasets_dir: 数据集目录

    Returns:
        TestDataset: 加载的数据集
    """
    loader = DatasetLoader(datasets_dir)
    return loader.load(dataset_name)


def save_dataset(
    dataset: TestDataset,
    dataset_name: Optional[str] = None,
    datasets_dir: str = "tests/harness/datasets"
):
    """
    保存数据集（快捷函数）

    Args:
        dataset: 数据集对象
        dataset_name: 数据集名称
        datasets_dir: 数据集目录
    """
    loader = DatasetLoader(datasets_dir)
    loader.save(dataset, dataset_name)
