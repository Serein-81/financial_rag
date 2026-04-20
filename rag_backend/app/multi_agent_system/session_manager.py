"""
多智能体会话管理器
提供会话的创建、查询、更新、删除等操作
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.multi_agent_session import (
    MultiAgentSession,
    MultiAgentSpecialistResult,
    MultiAgentIntentAnalysis,
    MultiAgentReflectionRecord
)
from app.models.multi_agent_report import (
    MultiAgentReport
)

logger = logging.getLogger(__name__)


class MultiAgentSessionManager:
    """多智能体会话管理器"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_session(
        self,
        session_id: str,
        tenant_id: str,
        user_id: Optional[str] = None,
        user_query: str = "",
        primary_intent: Optional[str] = None,
        routing_strategy: Optional[str] = None,
        complexity: Optional[str] = None,
        enable_reflection: bool = True,
        confidence_threshold: float = 0.7,
        max_specialists: int = 3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MultiAgentSession:
        """创建新的多智能体会话"""
        session = MultiAgentSession(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=uuid.UUID(user_id) if user_id else None,
            user_query=user_query,
            primary_intent=primary_intent,
            routing_strategy=routing_strategy,
            complexity=complexity,
            enable_reflection=enable_reflection,
            confidence_threshold=confidence_threshold,
            max_specialists=max_specialists,
            status="active",
            extra_metadata=metadata or {}
        )
        
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        
        logger.info(f"创建多智能体会话: {session_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[MultiAgentSession]:
        """获取会话"""
        result = await self.db.execute(
            select(MultiAgentSession)
            .options(
                selectinload(MultiAgentSession.specialist_results),
                selectinload(MultiAgentSession.reports)
            )
            .where(MultiAgentSession.session_id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def get_session_by_tenant(
        self,
        session_id: str,
        tenant_id: str
    ) -> Optional[MultiAgentSession]:
        """根据租户ID获取会话"""
        result = await self.db.execute(
            select(MultiAgentSession)
            .options(
                selectinload(MultiAgentSession.specialist_results),
                selectinload(MultiAgentSession.reports)
            )
            .where(
                MultiAgentSession.session_id == session_id,
                MultiAgentSession.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()
    
    async def update_session_status(
        self,
        session_id: str,
        status: str,
        completed_at: Optional[datetime] = None
    ) -> bool:
        """更新会话状态"""
        update_data = {"status": status}
        if completed_at:
            update_data["completed_at"] = completed_at
        elif status in ["completed", "failed", "cancelled"]:
            update_data["completed_at"] = datetime.now()
        
        result = await self.db.execute(
            update(MultiAgentSession)
            .where(MultiAgentSession.session_id == session_id)
            .values(**update_data)
        )
        await self.db.commit()
        
        return result.rowcount > 0
    
    async def list_sessions(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[MultiAgentSession]:
        """列出会话"""
        query = select(MultiAgentSession).where(MultiAgentSession.tenant_id == tenant_id)
        
        if user_id:
            query = query.where(MultiAgentSession.user_id == uuid.UUID(user_id))
        if status:
            query = query.where(MultiAgentSession.status == status)
        
        query = query.order_by(MultiAgentSession.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def delete_session(self, session_id: str, tenant_id: str) -> bool:
        """删除会话（级联删除相关数据）"""
        result = await self.db.execute(
            delete(MultiAgentSession)
            .where(
                MultiAgentSession.session_id == session_id,
                MultiAgentSession.tenant_id == tenant_id
            )
        )
        await self.db.commit()
        
        if result.rowcount > 0:
            logger.info(f"删除多智能体会话: {session_id}")
            return True
        return False
    
    async def save_specialist_result(
        self,
        session_id: str,
        tenant_id: str,
        specialist_type: str,
        specialist_name: Optional[str] = None,
        query: Optional[str] = None,
        analysis: Optional[Dict[str, Any]] = None,
        raw_response: Optional[str] = None,
        confidence: float = 0.0,
        processing_time: float = 0.0,
        success: bool = True,
        error_message: Optional[str] = None,
        execution_order: int = 0
    ) -> MultiAgentSpecialistResult:
        """保存专家结果"""
        result = MultiAgentSpecialistResult(
            session_id=uuid.UUID(session_id) if session_id else None,
            tenant_id=tenant_id,
            specialist_type=specialist_type,
            specialist_name=specialist_name,
            query=query,
            analysis=analysis,
            raw_response=raw_response,
            confidence=confidence,
            processing_time=processing_time,
            success=success,
            error_message=error_message,
            execution_order=execution_order
        )
        
        self.db.add(result)
        await self.db.commit()
        await self.db.refresh(result)
        
        return result
    
    async def save_intent_analysis(
        self,
        session_id: str,
        tenant_id: str,
        primary_intent: str,
        routing_strategy: str,
        required_specialists: List[str],
        complexity: Optional[str] = None,
        confidence: Optional[float] = None,
        raw_query: Optional[str] = None,
        interpreted_query: Optional[str] = None,
        sub_intents: Optional[List[str]] = None
    ) -> MultiAgentIntentAnalysis:
        """保存意图分析"""
        analysis = MultiAgentIntentAnalysis(
            session_id=uuid.UUID(session_id) if session_id else None,
            tenant_id=tenant_id,
            primary_intent=primary_intent,
            sub_intents=sub_intents,
            routing_strategy=routing_strategy,
            required_specialists=required_specialists,
            complexity=complexity,
            confidence=confidence,
            raw_query=raw_query,
            interpreted_query=interpreted_query
        )
        
        self.db.add(analysis)
        await self.db.commit()
        await self.db.refresh(analysis)
        
        return analysis
    
    async def save_reflection_record(
        self,
        session_id: str,
        tenant_id: str,
        quality_score: float,
        quality_level: str,
        needs_revision: bool,
        suggestions: List[Dict[str, Any]],
        improvement_summary: str,
        revision_reason: Optional[str] = None
    ) -> MultiAgentReflectionRecord:
        """保存反思记录"""
        record = MultiAgentReflectionRecord(
            session_id=uuid.UUID(session_id) if session_id else None,
            tenant_id=tenant_id,
            quality_score=quality_score,
            quality_level=quality_level,
            needs_revision=needs_revision,
            revision_reason=revision_reason,
            suggestions=suggestions,
            improvement_summary=improvement_summary
        )
        
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        
        return record
    
    async def get_session_history(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取会话历史摘要"""
        sessions = await self.list_sessions(
            tenant_id=tenant_id,
            user_id=user_id,
            limit=limit
        )
        
        return [
            {
                "session_id": s.session_id,
                "user_query": s.user_query[:100] + "..." if len(s.user_query) > 100 else s.user_query,
                "primary_intent": s.primary_intent,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "specialist_count": len(s.specialist_results) if s.specialist_results else 0
            }
            for s in sessions
        ]


class MultiAgentReportManager:
    """多智能体报告管理器"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_report(
        self,
        session_id: str,
        tenant_id: str,
        report_type: str,
        format: str = "markdown",
        title: Optional[str] = None,
        summary: Optional[str] = None,
        content: Optional[str] = None,
        sections: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        generated_by: Optional[str] = None,
        generation_time: Optional[float] = None,
        quality_score: Optional[float] = None,
        quality_level: Optional[str] = None
    ) -> MultiAgentReport:
        """创建报告"""
        report = MultiAgentReport(
            session_id=uuid.UUID(session_id) if session_id else None,
            tenant_id=tenant_id,
            user_id=uuid.UUID(user_id) if user_id else None,
            report_type=report_type,
            format=format,
            title=title,
            summary=summary,
            content=content,
            sections=sections or {},
            metadata=metadata or {},
            generated_by=generated_by,
            generation_time=generation_time,
            quality_score=quality_score,
            quality_level=quality_level,
            word_count=len(content.split()) if content else 0
        )
        
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        
        logger.info(f"创建多智能体报告: {report.id}")
        return report
    
    async def get_report(
        self,
        report_id: uuid.UUID,
        tenant_id: str
    ) -> Optional[MultiAgentReport]:
        """获取报告"""
        result = await self.db.execute(
            select(MultiAgentReport)
            .where(
                MultiAgentReport.id == report_id,
                MultiAgentReport.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_latest_report(
        self,
        session_id: str,
        tenant_id: str
    ) -> Optional[MultiAgentReport]:
        """获取会话的最新报告"""
        result = await self.db.execute(
            select(MultiAgentReport)
            .where(
                MultiAgentReport.session_id == uuid.UUID(session_id),
                MultiAgentReport.tenant_id == tenant_id,
                MultiAgentReport.is_latest.is_(True)
            )
        )
        return result.scalar_one_or_none()
    
    async def list_reports(
        self,
        tenant_id: str,
        session_id: Optional[str] = None,
        report_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[MultiAgentReport]:
        """列出报告"""
        query = select(MultiAgentReport).where(MultiAgentReport.tenant_id == tenant_id)
        
        if session_id:
            query = query.where(MultiAgentReport.session_id == uuid.UUID(session_id))
        if report_type:
            query = query.where(MultiAgentReport.report_type == report_type)
        
        query = query.order_by(MultiAgentReport.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_report(
        self,
        report_id: uuid.UUID,
        tenant_id: str,
        content: Optional[str] = None,
        summary: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新报告"""
        update_data = {}
        if content is not None:
            update_data["content"] = content
            update_data["word_count"] = len(content.split())
        if summary is not None:
            update_data["summary"] = summary
        if metadata is not None:
            update_data["metadata"] = metadata
        
        if not update_data:
            return False
        
        result = await self.db.execute(
            update(MultiAgentReport)
            .where(
                MultiAgentReport.id == report_id,
                MultiAgentReport.tenant_id == tenant_id
            )
            .values(**update_data)
        )
        await self.db.commit()
        
        return result.rowcount > 0
    
    async def delete_report(self, report_id: uuid.UUID, tenant_id: str) -> bool:
        """删除报告"""
        result = await self.db.execute(
            delete(MultiAgentReport)
            .where(
                MultiAgentReport.id == report_id,
                MultiAgentReport.tenant_id == tenant_id
            )
        )
        await self.db.commit()
        
        if result.rowcount > 0:
            logger.info(f"删除多智能体报告: {report_id}")
            return True
        return False
