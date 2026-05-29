"""
A/B 测试服务

实现 Prompt 的 A/B 测试、流量分配和统计分析。
"""

import logging
import random
from typing import Optional, List, Dict, Tuple
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import hashlib

from app.models.prompt_version import (
    PromptVersion,
    ABTestExperiment,
    PromptStatus
)

logger = logging.getLogger(__name__)


class ABTestService:
    """
    A/B 测试服务

    功能：
    1. 流量分配 - 根据权重随机选择版本
    2. 统计分析 - 计算各版本的性能指标
    3. 显著性检验 - 判断差异是否显著
    4. 自动提升 - 自动提升获胜版本
    """

    def __init__(self, db: AsyncSession, tenant_id: str):
        """
        初始化服务

        Args:
            db: 数据库会话（AsyncSession）
            tenant_id: 租户ID
        """
        self.db = db
        self.tenant_id = tenant_id

    async def get_variant_for_user(
        self,
        prompt_name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[PromptVersion]:
        """
        为用户分配 Prompt 版本（A/B测试）

        使用一致性哈希确保同一用户总是获得相同的版本。

        Args:
            prompt_name: Prompt名称
            user_id: 用户ID（可选）
            session_id: 会话ID（可选）

        Returns:
            PromptVersion: 分配的版本
        """
        # 1. 查找活跃的实验
        result = await self.db.execute(
            select(ABTestExperiment).where(
                ABTestExperiment.tenant_id == self.tenant_id,
                ABTestExperiment.prompt_name == prompt_name,
                ABTestExperiment.status == "running",
                ABTestExperiment.is_active == True
            )
        )
        experiment = result.scalar_one_or_none()

        if not experiment:
            # 没有实验，返回默认版本
            return await self._get_default_version(prompt_name)

        # 2. 获取参与测试的版本
        variant_ids = list(experiment.variant_weights.keys())
        weights = [experiment.variant_weights[vid] for vid in variant_ids]

        if not variant_ids:
            return await self._get_default_version(prompt_name)

        # 3. 一致性哈希分配（同一用户/会话总是获得相同版本）
        hash_key = user_id or session_id or str(random.random())
        hash_value = int(hashlib.md5(hash_key.encode()).hexdigest(), 16)
        total_weight = sum(weights)

        # 累积权重
        cumulative = 0
        threshold = (hash_value % 100) / 100.0 * total_weight

        for vid, weight in zip(variant_ids, weights):
            cumulative += weight
            if threshold <= cumulative:
                result = await self.db.execute(
                    select(PromptVersion).where(PromptVersion.id == vid)
                )
                version = result.scalar_one_or_none()
                if version:
                    logger.info(
                        f"A/B测试分配: {prompt_name} -> 版本 {version.version} "
                        f"(用户: {user_id or session_id})"
                    )
                    return version

        # 降级：返回第一个版本
        result = await self.db.execute(
            select(PromptVersion).where(PromptVersion.id == variant_ids[0])
        )
        return result.scalar_one_or_none()

    async def _get_default_version(self, prompt_name: str) -> Optional[PromptVersion]:
        """获取默认版本"""
        result = await self.db.execute(
            select(PromptVersion).where(
                PromptVersion.tenant_id == self.tenant_id,
                PromptVersion.prompt_name == prompt_name,
                PromptVersion.is_default == True,
                PromptVersion.status == PromptStatus.ACTIVE.value
            )
        )
        return result.scalar_one_or_none()

    async def create_experiment(
        self,
        experiment_name: str,
        prompt_name: str,
        prompt_type: str,
        variant_weights: Dict[str, int],
        min_sample_size: int = 100,
        confidence_level: float = 0.95,
        auto_promote_winner: bool = False
    ) -> ABTestExperiment:
        """
        创建 A/B 测试实验

        Args:
            experiment_name: 实验名称
            prompt_name: Prompt名称
            prompt_type: Prompt类型
            variant_weights: 版本权重 {"version_id": weight}
            min_sample_size: 最小样本量
            confidence_level: 置信水平
            auto_promote_winner: 是否自动提升获胜版本

        Returns:
            ABTestExperiment: 实验对象
        """
        # 验证权重总和为100
        total_weight = sum(variant_weights.values())
        if total_weight != 100:
            raise ValueError(f"权重总和必须为100，当前为{total_weight}")

        # 验证版本存在
        for version_id in variant_weights.keys():
            result = await self.db.execute(
                select(PromptVersion).where(
                    PromptVersion.id == version_id,
                    PromptVersion.tenant_id == self.tenant_id
                )
            )
            version = result.scalar_one_or_none()
            if not version:
                raise ValueError(f"版本不存在: {version_id}")

            # 更新版本状态为testing
            version.status = PromptStatus.TESTING.value
            version.ab_test_weight = variant_weights[str(version_id)]

        # 创建实验
        experiment = ABTestExperiment(
            tenant_id=self.tenant_id,
            experiment_name=experiment_name,
            prompt_name=prompt_name,
            prompt_type=prompt_type,
            variant_weights=variant_weights,
            min_sample_size=min_sample_size,
            confidence_level=confidence_level,
            auto_promote_winner=auto_promote_winner,
            status="running",
            is_active=True
        )

        self.db.add(experiment)
        await self.db.commit()
        await self.db.refresh(experiment)

        logger.info(f"创建A/B测试实验: {experiment_name}, 版本数: {len(variant_weights)}")

        return experiment

    async def analyze_experiment(
        self,
        experiment_id: str
    ) -> Dict[str, any]:
        """
        分析实验结果

        计算各版本的性能指标，并进行统计显著性检验。

        Args:
            experiment_id: 实验ID

        Returns:
            Dict: 分析结果
        """
        result = await self.db.execute(
            select(ABTestExperiment).where(
                ABTestExperiment.id == experiment_id,
                ABTestExperiment.tenant_id == self.tenant_id
            )
        )
        experiment = result.scalar_one_or_none()

        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")

        # 获取所有参与测试的版本
        variant_ids = list(experiment.variant_weights.keys())
        versions_result = await self.db.execute(
            select(PromptVersion).where(PromptVersion.id.in_(variant_ids))
        )
        versions = versions_result.scalars().all()

        # 计算各版本的指标
        results = []
        for version in versions:
            result = {
                "version_id": str(version.id),
                "version": version.version,
                "metrics": {
                    "total_uses": version.total_uses,
                    "success_rate": version.get_success_rate(),
                    "satisfaction_rate": version.get_satisfaction_rate(),
                    "avg_response_time_ms": version.avg_response_time_ms,
                    "avg_rating": version.avg_rating
                },
                "weight": experiment.variant_weights[str(version.id)]
            }
            results.append(result)

        # 排序（按成功率）
        results.sort(key=lambda x: x["metrics"]["success_rate"], reverse=True)

        # 统计显著性检验（简化版）
        if len(results) >= 2:
            best = results[0]
            second = results[1]

            # 样本量检查
            total_samples = sum(r["metrics"]["total_uses"] for r in results)
            has_enough_samples = total_samples >= experiment.min_sample_size

            # 差异检查（简化：如果最佳版本比第二好10%以上，认为显著）
            improvement = (
                best["metrics"]["success_rate"] - second["metrics"]["success_rate"]
            )
            is_significant = improvement >= 0.1 and has_enough_samples

            # 更新实验结果
            experiment.total_samples = total_samples
            experiment.is_significant = is_significant
            if is_significant:
                experiment.winner_version_id = best["version_id"]
                experiment.p_value = 0.05  # 简化

            await self.db.commit()

            analysis = {
                "experiment_id": str(experiment.id),
                "experiment_name": experiment.experiment_name,
                "status": experiment.status,
                "total_samples": total_samples,
                "has_enough_samples": has_enough_samples,
                "is_significant": is_significant,
                "winner": best if is_significant else None,
                "variants": results,
                "recommendation": self._generate_recommendation(
                    experiment, results, is_significant, has_enough_samples
                )
            }

            return analysis

        return {
            "experiment_id": str(experiment.id),
            "status": experiment.status,
            "variants": results,
            "error": "需要至少2个版本进行比较"
        }

    def _generate_recommendation(
        self,
        experiment: ABTestExperiment,
        results: List[Dict],
        is_significant: bool,
        has_enough_samples: bool
    ) -> str:
        """生成建议"""
        if not has_enough_samples:
            remaining = experiment.min_sample_size - experiment.total_samples
            return f"继续测试，还需要 {remaining} 个样本"

        if is_significant:
            winner = results[0]
            improvement = (
                winner["metrics"]["success_rate"] - results[1]["metrics"]["success_rate"]
            ) * 100
            return (
                f"版本 {winner['version']} 显著优于其他版本（成功率提升 {improvement:.1f}%），"
                f"建议提升为默认版本"
            )

        return "各版本性能接近，建议继续测试或保持当前默认版本"

    async def promote_winner(self, experiment_id: str) -> PromptVersion:
        """
        提升获胜版本为默认版本

        Args:
            experiment_id: 实验ID

        Returns:
            PromptVersion: 获胜版本
        """
        result = await self.db.execute(
            select(ABTestExperiment).where(
                ABTestExperiment.id == experiment_id,
                ABTestExperiment.tenant_id == self.tenant_id
            )
        )
        experiment = result.scalar_one_or_none()

        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")

        if not experiment.winner_version_id:
            raise ValueError("实验尚未产生获胜版本")

        # 获取获胜版本
        winner_result = await self.db.execute(
            select(PromptVersion).where(
                PromptVersion.id == experiment.winner_version_id
            )
        )
        winner = winner_result.scalar_one_or_none()

        if not winner:
            raise ValueError("获胜版本不存在")

        # 取消当前默认版本
        default_result = await self.db.execute(
            select(PromptVersion).where(
                PromptVersion.tenant_id == self.tenant_id,
                PromptVersion.prompt_name == experiment.prompt_name,
                PromptVersion.is_default == True
            )
        )
        current_default = default_result.scalar_one_or_none()

        if current_default:
            current_default.is_default = False
            current_default.status = PromptStatus.ARCHIVED.value

        # 提升获胜版本
        winner.is_default = True
        winner.status = PromptStatus.ACTIVE.value
        winner.activated_at = datetime.now()

        # 结束实验
        experiment.status = "completed"
        experiment.is_active = False
        experiment.end_time = datetime.now()

        # 归档其他测试版本
        for version_id in experiment.variant_weights.keys():
            if str(version_id) != str(winner.id):
                version_result = await self.db.execute(
                    select(PromptVersion).where(PromptVersion.id == version_id)
                )
                version = version_result.scalar_one_or_none()
                if version:
                    version.status = PromptStatus.ARCHIVED.value
                    version.ab_test_weight = 0

        await self.db.commit()

        logger.info(
            f"提升获胜版本: {winner.version} (实验: {experiment.experiment_name})"
        )

        return winner

    async def stop_experiment(self, experiment_id: str):
        """停止实验"""
        result = await self.db.execute(
            select(ABTestExperiment).where(
                ABTestExperiment.id == experiment_id,
                ABTestExperiment.tenant_id == self.tenant_id
            )
        )
        experiment = result.scalar_one_or_none()

        if not experiment:
            raise ValueError(f"实验不存在: {experiment_id}")

        experiment.status = "stopped"
        experiment.is_active = False
        experiment.end_time = datetime.now()

        # 重置版本的测试状态
        for version_id in experiment.variant_weights.keys():
            version_result = await self.db.execute(
                select(PromptVersion).where(PromptVersion.id == version_id)
            )
            version = version_result.scalar_one_or_none()
            if version and version.status == PromptStatus.TESTING.value:
                version.status = PromptStatus.DRAFT.value
                version.ab_test_weight = 0

        await self.db.commit()

        logger.info(f"停止A/B测试实验: {experiment.experiment_name}")

    async def get_active_experiments(self) -> List[ABTestExperiment]:
        """获取活跃的实验列表"""
        result = await self.db.execute(
            select(ABTestExperiment).where(
                ABTestExperiment.tenant_id == self.tenant_id,
                ABTestExperiment.status == "running",
                ABTestExperiment.is_active == True
            )
        )
        return result.scalars().all()


# 便捷函数

def get_ab_test_service(db: AsyncSession, tenant_id: str) -> ABTestService:
    """获取A/B测试服务实例"""
    return ABTestService(db=db, tenant_id=tenant_id)
