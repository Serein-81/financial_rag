"""
追问建议 API

提供追问建议的生成和管理功能
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from app.services.suggestion_service import suggestion_service, SuggestionType
from app.api import deps
from app.models.user import User

router = APIRouter(prefix="/suggestions", tags=["Suggestion"])


class GenerateSuggestionsRequest(BaseModel):
    """生成追问建议请求"""
    messages: List[Dict[str, Any]] = Field(..., description="消息列表")
    current_answer: Optional[str] = Field(None, description="当前答案")
    count: int = Field(5, description="生成数量")
    suggestion_types: Optional[List[str]] = Field(None, description="指定的建议类型")


class QuickSuggestRequest(BaseModel):
    """快速建议请求"""
    topic: str = Field(..., description="主题")


@router.post("/generate")
async def generate_suggestions(
    request: GenerateSuggestionsRequest,
    current_user: User = Depends(deps.get_current_user)
) -> List[Dict[str, Any]]:
    """
    生成追问建议
    
    Args:
        request: 生成请求
        
    Returns:
        List[Dict]: 建议列表
    """
    # 解析建议类型
    suggestion_types = None
    if request.suggestion_types:
        try:
            suggestion_types = [SuggestionType(t) for t in request.suggestion_types]
        except ValueError:
            suggestion_types = None
    
    # 分析上下文
    context = await suggestion_service.analyze_context(
        messages=request.messages,
        current_answer=request.current_answer
    )
    
    # 生成建议
    suggestions = await suggestion_service.generate_suggestions(
        context=context,
        current_answer=request.current_answer,
        suggestion_types=suggestion_types,
        count=request.count
    )
    
    return [s.to_dict() for s in suggestions]


@router.get("/session/{session_id}")
async def get_session_suggestions(
    session_id: str,
    count: int = Query(5, description="生成数量"),
    current_user: User = Depends(deps.get_current_user)
) -> List[Dict[str, Any]]:
    """
    根据会话生成追问建议
    
    Args:
        session_id: 会话ID
        count: 生成数量
        
    Returns:
        List[Dict]: 建议列表
    """
    from app.models.chat import ChatMessage
    from app.db import AsyncSessionLocal
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as db:
        # 获取会话消息
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        messages_db = result.scalars().all()
        
        # 转换为字典
        messages = [
            {
                "role": msg.role,
                "content": msg.content,
            }
            for msg in messages_db
        ]
        
        if not messages:
            return []
        
        # 获取最后一个AI回答
        current_answer = None
        for msg in reversed(messages_db):
            if msg.role == "assistant":
                current_answer = msg.content
                break
        
        # 生成建议
        suggestions = await suggestion_service.generate_from_chat_history(
            messages=messages,
            current_answer=current_answer,
            count=count
        )
        
        return suggestions


@router.post("/quick")
async def quick_suggest(
    request: QuickSuggestRequest,
    count: int = Query(3, description="生成数量")
) -> List[Dict[str, Any]]:
    """
    生成快速建议（无需认证）
    
    Args:
        request: 快速建议请求
        count: 生成数量
        
    Returns:
        List[Dict]: 建议列表
    """
    suggestions = await suggestion_service.generate_quick_suggestions(
        topic=request.topic,
        count=count
    )
    
    return suggestions


@router.get("/types")
async def get_suggestion_types() -> List[Dict[str, str]]:
    """
    获取所有建议类型
    
    Returns:
        List[Dict]: 建议类型列表
    """
    types = []
    for stype in SuggestionType:
        types.append({
            "value": stype.value,
            "name": _get_type_name(stype),
            "description": _get_type_description(stype),
        })
    
    return types


@router.get("/stats")
async def get_suggestion_stats() -> Dict[str, Any]:
    """
    获取建议统计
    
    Returns:
        Dict: 统计信息
    """
    return suggestion_service.get_stats()


def _get_type_name(stype: SuggestionType) -> str:
    """获取类型名称"""
    names = {
        SuggestionType.DEEPEN: "深入追问",
        SuggestionType.EXPAND: "扩展追问",
        SuggestionType.COMPARE: "对比追问",
        SuggestionType.EXAMPLE: "举例追问",
        SuggestionType.CONSEQUENCE: "后果追问",
        SuggestionType.CAUSE: "原因追问",
        SuggestionType.DIFFERENCE: "区别追问",
        SuggestionType.SUMMARY: "总结追问",
    }
    return names.get(stype, stype.value)


def _get_type_description(stype: SuggestionType) -> str:
    """获取类型描述"""
    descriptions = {
        SuggestionType.DEEPEN: "深入探讨当前话题的细节和原理",
        SuggestionType.EXPAND: "扩展到相关的话题和应用场景",
        SuggestionType.COMPARE: "与其他事物进行对比分析",
        SuggestionType.EXAMPLE: "请求具体的实例和应用案例",
        SuggestionType.CONSEQUENCE: "探讨某个选择的结果和影响",
        SuggestionType.CAUSE: "探讨某个现象的原因和背景",
        SuggestionType.DIFFERENCE: "探讨两个事物的主要区别",
        SuggestionType.SUMMARY: "请求对内容的总结和概括",
    }
    return descriptions.get(stype, "")
