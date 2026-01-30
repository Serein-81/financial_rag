import json
import time
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool
from sqlalchemy import select
from pydantic import BaseModel
from app.models.knowledge_base import KnowledgeBase

# --- 导入基础服务 ---
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.search_service import search_service
from app.services.llm_service import llm_service

# --- 导入持久化相关依赖 (新增) ---
from app.api import deps  # 鉴权依赖
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.db import AsyncSessionLocal

router = APIRouter()


# ==========================================
#  V1: 无状态接口 (Stateless)
#  用于：API 调试、简单测试、不登录的场景
# ==========================================

@router.post("/completions", response_model=ChatResponse)
async def chat_with_rag(request: ChatRequest):
    """
    [V1] 普通 RAG 对话 (非流式，一次性返回)
    """
    start_time = time.time()

    # 1. 检索
    print(f"🔍 [V1] 正在搜索: {request.query}")
    search_results = await search_service.search(request.query, request.top_k)

    if not search_results:
        return ChatResponse(
            answer="抱歉，知识库中没有找到相关信息。",
            sources=[],
            total_time=time.time() - start_time,
            model_used="None"
        )

    # 2. 上下文
    context_texts = [item.content for item in search_results]

    # 3. 生成
    ai_answer = await llm_service.get_answer(
        query=request.query,
        context_chunks=context_texts,
        history=request.history
    )

    return ChatResponse(
        answer=ai_answer,
        sources=search_results,
        total_time=time.time() - start_time,
        model_used=llm_service.model_name
    )


@router.post("/completions_stream")
async def chat_with_rag_stream(request: ChatRequest):
    """
    [V1] 流式 RAG 对话 (无数据库记录)
    """
    # 1. 检索
    search_results = await search_service.search(request.query, request.top_k)
    context_texts = [item.content for item in search_results] if search_results else []

    # 2. 定义生成器
    async def generate_stream():
        # 发送引用
        sources_data = [
            {"filename": res.source_file, "score": res.score, "content": res.content[:50]}
            for res in search_results
        ]
        yield json.dumps({"type": "sources", "data": sources_data}, ensure_ascii=False) + "\n"

        if not context_texts:
            yield json.dumps({"type": "content", "delta": "抱歉，未找到相关信息。"}, ensure_ascii=False) + "\n"
            return

        # 发送内容
        sync_generator = llm_service.get_answer_stream(request.query, context_texts, request.history)
        async for char in iterate_in_threadpool(sync_generator):
            yield json.dumps({"type": "content", "delta": char}, ensure_ascii=False) + "\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


# ==========================================
#  V2: 持久化接口 (Stateful) 🌟 核心升级
#  用于：正式业务、需要登录、保存历史记录
# ==========================================

# 定义 V2 请求体 (继承自原来的，但增加了 session_id)
class ChatRequestPersistent(ChatRequest):
    session_id: Optional[str] = None  # 如果传了就是继续聊，没传就是新会话


@router.post("/completions_stream_v2")
async def chat_stream_persistent(
        request: ChatRequestPersistent,
        current_user: User = Depends(deps.get_current_user)
):
    async with AsyncSessionLocal() as db:
        # A. 会话管理
        if not request.session_id:
            # 👇👇👇【修复点：必须显式创建 new_session】👇👇👇
            print(f"🆕 用户 {current_user.email} 正在创建新会话...")
            new_session = ChatSession(
                user_id=current_user.id,
                title=request.query[:20]  # 使用问题前20个字作为标题
            )
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)  # 刷新以获取数据库生成的 UUID

            session_id = str(new_session.id)
            history = []
            print(f"✅ 新会话创建成功: {session_id}")
            # 👆👆👆【修复结束】👆👆👆
        else:
            session_id = request.session_id

            # B. 查询历史记录 (Context)
            print(f"🔄 正在查询数据库历史: Session ID {session_id}")
            result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
            )
            messages_objs = result.scalars().all()

            # 转换为 LLM 需要的格式
            history = [
                {"role": m.role, "content": m.content}
                for m in messages_objs
            ]
            print(f"📜 查到历史记录: {len(history)} 条")

        # C. 保存本次【用户】的消息
        user_msg = ChatMessage(session_id=session_id, role="user", content=request.query)
        db.add(user_msg)
        await db.commit()

    # --- 2. 检索 (RAG) ---
    search_results = await search_service.search(
        query=request.query,
        top_k=request.top_k,
        kb_id=request.kb_id  # 👈 确保这行参数存在！
    )
    context_texts = [item.content for item in search_results] if search_results else []

    # --- 3. 流式生成与后处理 ---
    async def generate_save_stream():
        full_answer = ""

        # 1. 发送 Session ID (协议)
        yield json.dumps({"type": "session", "id": session_id}, ensure_ascii=False) + "\n"

        # 2. 发送引用来源 (协议)
        sources_data = [
            {"filename": res.source_file, "score": res.score, "content": res.content[:50] + "..."}
            for res in search_results
        ]
        yield json.dumps({"type": "sources", "data": sources_data}, ensure_ascii=False) + "\n"

        # 3. 如果没找到资料
        if not context_texts:
            # 注意：这里我们让它继续回答，只是告诉 AI 没有资料（由 llm_service 内部 prompt 决定怎么说）
            # 或者你可以选择直接中断。这里为了体验连贯，我们继续调用 LLM，
            # 因为我们在 Prompt 里已经教过 AI "如果不在资料里，尝试用历史回答"。
            pass

            # 4. 发送内容 (LLM 流式)
        # 注意：context_texts 为空时，LLM 会根据 Prompt 指令决定是拒绝还是根据历史回答
        sync_gen = llm_service.get_answer_stream(request.query, context_texts, history)

        async for char in iterate_in_threadpool(sync_gen):
            full_answer += char
            yield json.dumps({"type": "content", "delta": char}, ensure_ascii=False) + "\n"

        # 5. 保存【AI】的消息 (异步存库)
        try:
            async with AsyncSessionLocal() as db:
                ai_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=full_answer,
                    sources=sources_data
                )
                db.add(ai_msg)
                await db.commit()
                print(f"💾 AI 回答已保存 (长度: {len(full_answer)})")
        except Exception as e:
            print(f"❌ 保存 AI 消息失败: {e}")

    return StreamingResponse(
        generate_save_stream(),
        media_type="text/event-stream"
    )