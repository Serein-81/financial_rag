# app/services/prompt_optimizer.py

"""
Prompt 优化服务

提供 Prompt 模板管理、性能分析和自动优化功能
"""

from typing import List, Dict, Optional, Any
from uuid import UUID
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.models.prompt_optimization import PromptTemplate, PromptExecution
from app.models.agent_trace import AgentTrace


class PromptOptimizer:
    """Prompt 优化器"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ==========================================
    # 模板管理
    # ==========================================
    
    async def create_template(
        self,
        name: str,
        version: str,
        template_text: str,
        agent_type: str,
        use_case: str = "general",
        variables: Optional[Dict] = None,
        description: Optional[str] = None,
        is_baseline: bool = False
    ) -> PromptTemplate:
        """创建新的 Prompt 模板"""
        template = PromptTemplate(
            name=name,
            version=version,
            template_text=template_text,
            agent_type=agent_type,
            use_case=use_case,
            variables=variables,
            description=description,
            is_baseline=is_baseline,
            is_active=True
        )
        
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        
        return template
    
    async def get_template(self, template_id: UUID) -> Optional[PromptTemplate]:
        """获取模板"""
        result = await self.db.execute(
            select(PromptTemplate).where(PromptTemplate.id == template_id)
        )
        return result.scalar_one_or_none()
    
    async def get_active_template(
        self,
        agent_type: str,
        use_case: str = "general"
    ) -> Optional[PromptTemplate]:
        """获取当前激活的模板"""
        result = await self.db.execute(
            select(PromptTemplate)
            .where(
                and_(
                    PromptTemplate.agent_type == agent_type,
                    PromptTemplate.use_case == use_case,
                    PromptTemplate.is_active == True
                )
            )
            .order_by(desc(PromptTemplate.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def list_templates(
        self,
        agent_type: Optional[str] = None,
        use_case: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[PromptTemplate]:
        """列出模板"""
        query = select(PromptTemplate)
        
        conditions = []
        if agent_type:
            conditions.append(PromptTemplate.agent_type == agent_type)
        if use_case:
            conditions.append(PromptTemplate.use_case == use_case)
        if is_active is not None:
            conditions.append(PromptTemplate.is_active == is_active)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(PromptTemplate.created_at))
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_template_status(
        self,
        template_id: UUID,
        is_active: bool
    ) -> Optional[PromptTemplate]:
        """更新模板状态"""
        template = await self.get_template(template_id)
        if template:
            template.is_active = is_active
            template.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(template)
        return template
    
    # ==========================================
    # 执行记录
    # ==========================================
    
    async def record_execution(
        self,
        template_id: UUID,
        user_query: str,
        trace_id: Optional[UUID] = None,
        final_answer: Optional[str] = None,
        execution_time: Optional[float] = None,
        iterations_count: Optional[int] = None,
        tool_calls_count: Optional[int] = None,
        success: bool = True,
        user_feedback: Optional[int] = None,
        auto_score: Optional[float] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> PromptExecution:
        """记录执行结果"""
        execution = PromptExecution(
            template_id=template_id,
            trace_id=trace_id,
            user_query=user_query,
            final_answer=final_answer,
            execution_time=execution_time,
            iterations_count=iterations_count,
            tool_calls_count=tool_calls_count,
            success=success,
            user_feedback=user_feedback,
            auto_score=auto_score,
            error_type=error_type,
            error_message=error_message
        )
        
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)
        
        return execution
    
    async def get_template_executions(
        self,
        template_id: UUID,
        limit: int = 100
    ) -> List[PromptExecution]:
        """获取模板的执行记录"""
        result = await self.db.execute(
            select(PromptExecution)
            .where(PromptExecution.template_id == template_id)
            .order_by(desc(PromptExecution.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    # ==========================================
    # 性能分析
    # ==========================================
    
    async def analyze_template_performance(
        self,
        template_id: UUID,
        days: int = 7
    ) -> Dict[str, Any]:
        """分析模板性能"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # 查询执行记录
        result = await self.db.execute(
            select(PromptExecution)
            .where(
                and_(
                    PromptExecution.template_id == template_id,
                    PromptExecution.created_at >= since_date
                )
            )
        )
        executions = result.scalars().all()
        
        if not executions:
            return {
                "template_id": str(template_id),
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_execution_time": 0.0,
                "avg_iterations": 0.0,
                "avg_tool_calls": 0.0,
                "avg_score": 0.0,
                "error_distribution": {}
            }
        
        # 统计指标
        total = len(executions)
        success_count = sum(1 for e in executions if e.success)
        
        # 平均值（过滤 None）
        execution_times = [e.execution_time for e in executions if e.execution_time is not None]
        iterations = [e.iterations_count for e in executions if e.iterations_count is not None]
        tool_calls = [e.tool_calls_count for e in executions if e.tool_calls_count is not None]
        scores = [e.auto_score for e in executions if e.auto_score is not None]
        
        # 错误分布
        error_types = {}
        for e in executions:
            if not e.success and e.error_type:
                error_types[e.error_type] = error_types.get(e.error_type, 0) + 1
        
        return {
            "template_id": str(template_id),
            "total_executions": total,
            "success_rate": success_count / total if total > 0 else 0.0,
            "avg_execution_time": sum(execution_times) / len(execution_times) if execution_times else 0.0,
            "avg_iterations": sum(iterations) / len(iterations) if iterations else 0.0,
            "avg_tool_calls": sum(tool_calls) / len(tool_calls) if tool_calls else 0.0,
            "avg_score": sum(scores) / len(scores) if scores else 0.0,
            "error_distribution": error_types,
            "period_days": days
        }
    
    async def compare_templates(
        self,
        template_a_id: UUID,
        template_b_id: UUID,
        days: int = 7
    ) -> Dict[str, Any]:
        """比较两个模板的性能"""
        perf_a = await self.analyze_template_performance(template_a_id, days)
        perf_b = await self.analyze_template_performance(template_b_id, days)
        
        # 计算差异
        def calc_diff(a_val, b_val):
            if b_val == 0:
                return 0.0
            return ((a_val - b_val) / b_val) * 100
        
        return {
            "template_a": perf_a,
            "template_b": perf_b,
            "comparison": {
                "success_rate_diff": calc_diff(perf_a["success_rate"], perf_b["success_rate"]),
                "execution_time_diff": calc_diff(perf_a["avg_execution_time"], perf_b["avg_execution_time"]),
                "iterations_diff": calc_diff(perf_a["avg_iterations"], perf_b["avg_iterations"]),
                "score_diff": calc_diff(perf_a["avg_score"], perf_b["avg_score"])
            },
            "winner": self._determine_winner(perf_a, perf_b)
        }
    
    def _determine_winner(self, perf_a: Dict, perf_b: Dict) -> str:
        """确定获胜者（简单规则）"""
        # 权重：成功率 40%，评分 30%，执行时间 20%，迭代次数 10%
        score_a = (
            perf_a["success_rate"] * 0.4 +
            perf_a["avg_score"] * 0.3 +
            (1 / (perf_a["avg_execution_time"] + 1)) * 0.2 +
            (1 / (perf_a["avg_iterations"] + 1)) * 0.1
        )
        
        score_b = (
            perf_b["success_rate"] * 0.4 +
            perf_b["avg_score"] * 0.3 +
            (1 / (perf_b["avg_execution_time"] + 1)) * 0.2 +
            (1 / (perf_b["avg_iterations"] + 1)) * 0.1
        )
        
        if score_a > score_b:
            return "template_a"
        elif score_b > score_a:
            return "template_b"
        else:
            return "tie"
    
    # ==========================================
    # 自动优化建议
    # ==========================================
    
    async def get_optimization_suggestions(
        self,
        template_id: UUID,
        days: int = 7
    ) -> List[Dict[str, str]]:
        """获取优化建议"""
        perf = await self.analyze_template_performance(template_id, days)
        suggestions = []
        
        # 成功率低
        if perf["success_rate"] < 0.8:
            suggestions.append({
                "type": "success_rate",
                "severity": "high",
                "message": f"成功率较低 ({perf['success_rate']:.1%})，建议优化 Prompt 的指令清晰度"
            })
        
        # 执行时间长
        if perf["avg_execution_time"] > 10.0:
            suggestions.append({
                "type": "execution_time",
                "severity": "medium",
                "message": f"平均执行时间较长 ({perf['avg_execution_time']:.1f}s)，建议简化 Prompt 或优化工具调用"
            })
        
        # 迭代次数多
        if perf["avg_iterations"] > 5:
            suggestions.append({
                "type": "iterations",
                "severity": "medium",
                "message": f"平均迭代次数较多 ({perf['avg_iterations']:.1f})，建议增强 Prompt 的决策引导"
            })
        
        # 评分低
        if perf["avg_score"] < 0.7:
            suggestions.append({
                "type": "score",
                "severity": "high",
                "message": f"平均评分较低 ({perf['avg_score']:.2f})，建议改进 Prompt 的输出质量"
            })
        
        # 特定错误类型
        if perf["error_distribution"]:
            for error_type, count in perf["error_distribution"].items():
                if count / perf["total_executions"] > 0.1:  # 超过 10%
                    suggestions.append({
                        "type": "error",
                        "severity": "high",
                        "message": f"频繁出现 {error_type} 错误 ({count} 次)，建议针对性优化"
                    })
        
        return suggestions


# 全局实例（需要在使用时传入 db session）
def get_prompt_optimizer(db: AsyncSession) -> PromptOptimizer:
    """获取 Prompt 优化器实例"""
    return PromptOptimizer(db)
