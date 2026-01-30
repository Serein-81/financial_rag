# app/api/v1/endpoints/session.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from app.api import deps
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.db import AsyncSessionLocal
from uuid import UUID

router = APIRouter()


@router.get("/")
async def get_my_sessions(current_user: User = Depends(deps.get_current_user)):
    """获取我的所有会话列表 (用于侧边栏)"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == current_user.id)
            .order_by(ChatSession.updated_at.desc())  # 最近聊的排前面
        )
        return result.scalars().all()


@router.get("/{session_id}/messages")
async def get_session_history(session_id: UUID, current_user: User = Depends(deps.get_current_user)):
    """加载某个会话的详细历史记录 (用于点击侧边栏后回显)"""
    async with AsyncSessionLocal() as db:
        # 1. 验证归属
        session = await db.get(ChatSession, session_id)
        if not session or session.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 2. 查消息
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        return result.scalars().all()


@router.delete("/{session_id}")
async def delete_session(session_id: UUID, current_user: User = Depends(deps.get_current_user)):
    """删除会话"""
    async with AsyncSessionLocal() as db:
        stmt = delete(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        result = await db.execute(stmt)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="会话不存在")
        await db.commit()
        return {"msg": "删除成功"}