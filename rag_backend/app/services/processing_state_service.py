from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document
from typing import Optional
import asyncio


class ProcessingStateChecker:
    @staticmethod
    async def get_state(db: AsyncSession, document_id: str) -> Optional[str]:
        result = await db.execute(
            select(Document.processing_state).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_progress(
        db: AsyncSession, 
        document_id: str, 
        progress: int, 
        message: str = ""
    ):
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if doc:
            doc.processing_progress = progress
            if message:
                doc.processing_message = message
            await db.commit()
    
    @staticmethod
    async def should_pause(db: AsyncSession, document_id: str) -> bool:
        state = await ProcessingStateChecker.get_state(db, document_id)
        return state in ["paused", "cancelled"]
    
    @staticmethod
    async def should_cancel(db: AsyncSession, document_id: str) -> bool:
        state = await ProcessingStateChecker.get_state(db, document_id)
        return state == "cancelled"
    
    @staticmethod
    async def wait_if_paused(db: AsyncSession, document_id: str, check_interval: float = 1.0):
        """等待直到不再暂停或被取消"""
        while True:
            state = await ProcessingStateChecker.get_state(db, document_id)
            if state != "paused":
                break
            await asyncio.sleep(check_interval)


processing_state_checker = ProcessingStateChecker()