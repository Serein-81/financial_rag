# app/api/v1/endpoints/session.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.orm import defer
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.db import AsyncSessionLocal
from app.schemas.chat import ChatMessageSchema, ChatSessionSchema
from app.utils.time_utils import format_datetime
from uuid import UUID

# 引入日志装饰器
from app.utils.log_decorators import log_user_action

router = APIRouter()


@router.get("/")
async def get_my_sessions(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """获取我的所有会话列表 (用于侧边栏)"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    
    return [
        ChatSessionSchema(
            id=str(session.id),
            title=session.title,
            created_at=format_datetime(session.created_at) if session.created_at else None,
            updated_at=format_datetime(session.updated_at) if session.updated_at else (format_datetime(session.created_at) if session.created_at else None)
        )
        for session in sessions
    ]


@router.get("/{session_id}/messages")
async def get_session_history(
    session_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """加载某个会话的详细历史记录 (用于点击侧边栏后回显)"""
    session = await db.get(ChatSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="会话不存在")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    
    return [
        ChatMessageSchema(
            id=str(msg.id),
            session_id=str(msg.session_id),
            role=msg.role,
            content=msg.content,
            sources=msg.sources,
            created_at=format_datetime(msg.created_at) if msg.created_at else None
        )
        for msg in messages
    ]


@router.delete("/{session_id}")
@log_user_action(
    action_type="CHAT",
    action_name="delete_session",
    resource_type="chat_session",
    description="删除聊天会话"
)
async def delete_session(
    session_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
):
    """删除会话"""
    session = await db.get(ChatSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="会话不存在")

    await db.execute(
        delete(ChatMessage).where(ChatMessage.session_id == session_id)
    )

    await db.execute(
        delete(ChatSession).where(ChatSession.id == session_id)
    )

    await db.commit()

    return {"msg": "删除成功"}