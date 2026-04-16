# app/services/prompt_ab_test.py

"""
Prompt A/B 测试服务

管理 Prompt 模板的 A/B 测试
"""

from typing import List, Dict, Optional, Any
from uuid import UUID
import random
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models.prompt_optimization import PromptABTest, PromptExecution


class PromptABTestManager:
    """Prompt A/B 测试管理器"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ==========================================
    # 测试管理
    # ==========================================
    
    async def create_test(
        self,
        test_name: str,
        template_a_id: UUID,
        template_b_id: UUID,
        traffic_split: float = 0.5,
        description: Optional[str] = None
    ) -> PromptABTest:
        """创建 A/B 测试"""
        test = PromptABTest(
            test_name=test_name,
            description=description,
            template_a_id=template_a_id,
            template_b_id=template_b_id,
            traffic_split=traffic_split,
            status="running"
        )
        
        self.db.add(test)
        await self.db.commit()
        await self.db.refresh(test)
        
        return test
    
    async def get_test(self, test_id: UUID) -> Optional[PromptABTest]:
        """获取测试"""
        result = await self.db.execute(
            select(PromptABTest).where(PromptABTest.id == test_id)
        )
        return result.scalar_one_or_none()
    
    async def get_test_by_name(self, test_name: str) -> Optional[PromptABTest]:
        """根据名称获取测试"""
        result = await self.db.execute(
            select(PromptABTest).where(PromptABTest.test_name == test_name)
        )
        return result.scalar_one_or_none()
    
    async def list_tests(
        self,
        status: Optional[str] = None
    ) -> List[PromptABTest]:
        """列出测试"""
        query = select(PromptABTest)
        
        if status:
            query = query.where(PromptABTest.status == status)
        
        query = query.order_by(desc(PromptABTest.created_at))
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_test_status(
        self,
        test_id: UUID,
        status: str,
        winner_template_id: Optional[UUID] = None
    ) -> Optional[PromptABTest]:
        """更新测试状态"""
        test = await self.get_test(test_id)
        if test:
            test.status = status
            test.updated_at = datetime.utcnow()
            
            if status == "completed":
                test.end_date = datetime.utcnow()
                if winner_template_id:
                    test.winner_template_id = winner_template_id
            
            await self.db.commit()
            await self.db.refresh(test)
        
        return test
    
    # ==========================================
    # 流量分配
    # ==========================================
    
    async def select_template(
        self,
        test_name: str
    ) -> Optional[UUID]:
        """根据流量分配选择模板"""
        test = await self.get_test_by_name(test_name)
        
        if not test or test.status != "running":
            return None
        
        # 根据流量分配随机选择
        if random.random() < test.traffic_split:
            return test.template_a_id
        else:
            return test.template_b_id
    
    async def increment_execution_count(self, test_id: UUID):
        """增加执行计数"""
        test = await self.get_test(test_id)
        if test:
            test.total_executions += 1
            await self.db.commit()
    
    # ==========================================
    # 结果分析
    # ==========================================
    
    async def analyze_test_results(
        self,
        test_id: UUID
    ) -> Dict[str, Any]:
        """分析测试结果"""
        test = await self.get_test(test_id)
        if not test:
            return {"error": "Test not found"}
        
        # 获取两个模板的执行记录
        result_a = await self.db.execute(
            select(PromptExecution)
            .where(
                and_(
                    PromptExecution.template_id == test.template_a_id,
                    PromptExecution.created_at >= test.start_date
                )
            )
        )
        executions_a = result_a.scalars().all()
        
        result_b = await self.db.execute(
            select(PromptExecution)
            .where(
                and_(
                    PromptExecution.template_id == test.template_b_id,
                    PromptExecution.created_at >= test.start_date
                )
            )
        )
        executions_b = result_b.scalars().all()
        
        # 计算统计指标
        stats_a = self._calculate_stats(executions_a)
        stats_b = self._calculate_stats(executions_b)
        
        # 确定获胜者
        winner = self._determine_winner(stats_a, stats_b)
        
        return {
            "test_id": str(test_id),
            "test_name": test.test_name,
            "status": test.status,
            "total_executions": test.total_executions,
            "template_a": {
                "template_id": str(test.template_a_id),
                "executions": len(executions_a),
                "stats": stats_a
            },
            "template_b": {
                "template_id": str(test.template_b_id),
                "executions": len(executions_b),
                "stats": stats_b
            },
            "winner": winner,
            "confidence": self._calculate_confidence(stats_a, stats_b, len(executions_a), len(executions_b))
        }
    
    def _calculate_stats(self, executions: List[PromptExecution]) -> Dict[str, float]:
        """计算统计指标"""
        if not executions:
            return {
                "success_rate": 0.0,
                "avg_execution_time": 0.0,
                "avg_iterations": 0.0,
                "avg_score": 0.0
            }
        
        total = len(executions)
        success_count = sum(1 for e in executions if e.success)
        
        execution_times = [e.execution_time for e in executions if e.execution_time is not None]
        iterations = [e.iterations_count for e in executions if e.iterations_count is not None]
        scores = [e.auto_score for e in executions if e.auto_score is not None]
        
        return {
            "success_rate": success_count / total if total > 0 else 0.0,
            "avg_execution_time": sum(execution_times) / len(execution_times) if execution_times else 0.0,
            "avg_iterations": sum(iterations) / len(iterations) if iterations else 0.0,
            "avg_score": sum(scores) / len(scores) if scores else 0.0
        }
    
    def _determine_winner(self, stats_a: Dict, stats_b: Dict) -> str:
        """确定获胜者"""
        # 综合评分（权重：成功率 40%，评分 30%，执行时间 20%，迭代次数 10%）
        score_a = (
            stats_a["success_rate"] * 0.4 +
            stats_a["avg_score"] * 0.3 +
            (1 / (stats_a["avg_execution_time"] + 1)) * 0.2 +
            (1 / (stats_a["avg_iterations"] + 1)) * 0.1
        )
        
        score_b = (
            stats_b["success_rate"] * 0.4 +
            stats_b["avg_score"] * 0.3 +
            (1 / (stats_b["avg_execution_time"] + 1)) * 0.2 +
            (1 / (stats_b["avg_iterations"] + 1)) * 0.1
        )
        
        if score_a > score_b * 1.05:  # A 显著优于 B（5% 阈值）
            return "template_a"
        elif score_b > score_a * 1.05:  # B 显著优于 A
            return "template_b"
        else:
            return "tie"
    
    def _calculate_confidence(
        self,
        stats_a: Dict,
        stats_b: Dict,
        n_a: int,
        n_b: int
    ) -> float:
        """计算置信度（简化版）"""
        # 基于样本量和差异计算置信度
        if n_a < 10 or n_b < 10:
            return 0.0  # 样本量太小
        
        # 计算差异
        diff = abs(stats_a["success_rate"] - stats_b["success_rate"])
        
        # 简化的置信度计算
        min_samples = min(n_a, n_b)
        confidence = min(diff * min_samples / 10, 1.0)
        
        return confidence
    
    # ==========================================
    # 自动决策
    # ==========================================
    
    async def auto_complete_test(
        self,
        test_id: UUID,
        min_executions: int = 100,
        min_confidence: float = 0.8
    ) -> Optional[Dict[str, Any]]:
        """自动完成测试（如果满足条件）"""
        analysis = await self.analyze_test_results(test_id)
        
        # 检查是否满足完成条件
        if (
            analysis["total_executions"] >= min_executions and
            analysis["confidence"] >= min_confidence and
            analysis["winner"] != "tie"
        ):
            # 确定获胜者
            winner_id = (
                analysis["template_a"]["template_id"]
                if analysis["winner"] == "template_a"
                else analysis["template_b"]["template_id"]
            )
            
            # 更新测试状态
            await self.update_test_status(
                test_id,
                status="completed",
                winner_template_id=UUID(winner_id)
            )
            
            return {
                "completed": True,
                "winner": analysis["winner"],
                "winner_id": winner_id,
                "confidence": analysis["confidence"]
            }
        
        return {
            "completed": False,
            "reason": "Not enough data or confidence",
            "current_executions": analysis["total_executions"],
            "current_confidence": analysis["confidence"]
        }


# 全局实例
def get_ab_test_manager(db: AsyncSession) -> PromptABTestManager:
    """获取 A/B 测试管理器实例"""
    return PromptABTestManager(db)
