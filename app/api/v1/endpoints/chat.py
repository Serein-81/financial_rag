import json
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import iterate_in_threadpool
from sqlalchemy import select
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from app.models.knowledge_base import KnowledgeBase
# --- 导入基础服务 ---
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.search_service import search_service
from app.services.llm_service import llm_service

# 👇 🌟 新增：导入我们刚刚打造的 Agent 超级大脑
from app.services.agent_service import agent_service
# 移除 LangChain 消息类型依赖，使用标准字典格式
# --- 导入持久化相关依赖 ---
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
async def chat_with_rag(
    request: ChatRequest,
    tenant_context: dict = Depends(deps.get_tenant_context),
    db_session = Depends(deps.get_tenant_db)
):
    """
    [V1] 普通 RAG 对话 (非流式，一次性返回) - 支持租户隔离
    """
    start_time = time.time()

    print(f"🔍 [V1] 租户 {tenant_context['tenant_id']} 正在搜索: {request.query}")
    
    # 添加租户过滤器
    search_results = await search_service.search(
        request.query, 
        request.top_k,
        filters={'tenant_id': tenant_context['tenant_id']}  # 🔒 租户隔离
    )

    if not search_results:
        return ChatResponse(
            answer="抱歉，知识库中没有找到相关信息。",
            sources=[],
            total_time=time.time() - start_time,
            model_used="None",
            tenant_id=tenant_context['tenant_id']
        )

    context_texts = [item.content for item in search_results]

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
    search_results = await search_service.search(request.query, request.top_k)
    context_texts = [item.content for item in search_results] if search_results else []

    async def generate_stream():
        sources_data = [
            {"filename": res.source_file, "score": res.score, "content": res.content[:50]}
            for res in search_results
        ]
        yield json.dumps({"type": "sources", "data": sources_data}, ensure_ascii=False) + "\n"

        if not context_texts:
            yield json.dumps({"type": "content", "delta": "抱歉，未找到相关信息。"}, ensure_ascii=False) + "\n"
            return

        sync_generator = llm_service.get_answer_stream(request.query, context_texts, request.history)
        async for char in iterate_in_threadpool(sync_generator):
            yield json.dumps({"type": "content", "delta": char}, ensure_ascii=False) + "\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


# ==========================================
#  V2: 持久化接口 (Stateful)
#  用于：正式业务、需要登录、保存历史记录 (普通 RAG)
# ==========================================

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
            print(f"🆕 用户 {current_user.email} 正在创建新会话...")
            new_session = ChatSession(
                user_id=current_user.id,
                title=request.query[:20]
            )
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)

            session_id = str(new_session.id)
            history = []
            print(f"✅ 新会话创建成功: {session_id}")
        else:
            session_id = request.session_id

            print(f"🔄 正在查询数据库历史: Session ID {session_id}")
            result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
            )
            messages_objs = result.scalars().all()

            history = [
                {"role": m.role, "content": m.content}
                for m in messages_objs
            ]
            print(f"📜 查到历史记录: {len(history)} 条")

        # C. 保存本次【用户】的消息
        user_msg = ChatMessage(session_id=session_id, role="user", content=request.query)
        db.add(user_msg)
        await db.commit()

    search_results = await search_service.search(
        query=request.query,
        top_k=request.top_k,
        kb_id=request.kb_id
    )
    context_texts = [item.content for item in search_results] if search_results else []

    async def generate_save_stream():
        full_answer = ""

        yield json.dumps({"type": "session", "id": session_id}, ensure_ascii=False) + "\n"

        sources_data = [
            {"filename": res.source_file, "score": res.score, "content": res.content[:50] + "..."}
            for res in search_results
        ]
        yield json.dumps({"type": "sources", "data": sources_data}, ensure_ascii=False) + "\n"

        sync_gen = llm_service.get_answer_stream(request.query, context_texts, history)

        async for char in iterate_in_threadpool(sync_gen):
            full_answer += char
            yield json.dumps({"type": "content", "delta": char}, ensure_ascii=False) + "\n"

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


# ==========================================
#  V3: Agent 智能体接口 🚀 最新加入
#  用于：让大模型自主决定是否查库、如何查库
# ==========================================

class AgentChatRequest(BaseModel):
    kb_id: str  # 必须指定知识库ID，做数据隔离
    query: str  # 用户问题
    session_id: Optional[str] = None  # 会话持久化ID


# app/api/v1/endpoints/chat.py 中的 chat_with_agent 函数

@router.post("/agent_chat")
async def chat_with_agent(
        request: AgentChatRequest,
        current_user: User = Depends(deps.get_current_user)
):
    print(f"🤖 [Agent 接口被调用] 用户: {current_user.email} | 问题: {request.query}")

    try:
        async with AsyncSessionLocal() as db:
            # ==========================================
            # 🚨 核心拦截：多租户越权校验 (防水平越权)
            # ==========================================

            kb_check = await db.execute(
                select(KnowledgeBase)
                .where(KnowledgeBase.id == request.kb_id)
                .where(KnowledgeBase.user_id == current_user.id)  # 必须同时满足 kb_id 正确且归属当前用户
            )
            kb = kb_check.scalar_one_or_none()

            if not kb:
                # 查不到说明该知识库不存在，或属于其他租户，直接拦截！
                raise HTTPException(
                    status_code=403,
                    detail="越权访问拦截：该知识库不存在或不属于当前用户！"
                )
            # ==========================================

            if not request.session_id:
                # 新会话
                new_session = ChatSession(user_id=current_user.id, title=request.query[:20])
                db.add(new_session)
                await db.commit()
                await db.refresh(new_session)
                session_id = str(new_session.id)
            else:
                session_id = request.session_id

            # 🧠 不再手动查询和存储历史记录，改用记忆系统
            # 移除了手动历史查询和存储代码，记忆系统会自动管理

        # --- 2. 召唤 Agent (使用记忆系统) ---
        ai_answer = await agent_service.chat(
            user_input=request.query,
            kb_id=request.kb_id,
            session_id=session_id,
            history=[],  # 空历史，使用记忆系统替代
            user_id=str(current_user.id)  # 🧠 传入user_id
        )

        # 🧠 不再手动保存AI回答，记忆系统会自动处理
        # 移除了手动保存AI回答的代码

        return {
            "session_id": session_id,
            "answer": ai_answer,
            "status": "success",
            "mode": "agent_with_memory"  # 标识使用了记忆系统
        }

    except HTTPException:
        # 拦截上面主动抛出的 403 等 HTTP 异常，直接向上抛出，避免变成 500
        raise
    except Exception as e:
        print(f"❌ [Agent 运行出错]: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent_chat_stream")
async def chat_with_agent_stream(
        request: AgentChatRequest,
        current_user: User = Depends(deps.get_current_user)
):
    print(f"🌊 [Agent 流式接口被调用] 用户: {current_user.email} | 问题: {request.query}")

    # 1. 越权校验（保留知识库权限检查）
    async with AsyncSessionLocal() as db:
        # 校验多租户知识库权限
        kb_check = await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.id == request.kb_id)
            .where(KnowledgeBase.user_id == current_user.id)
        )
        if not kb_check.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="越权访问拦截！")

        # 处理session_id
        if not request.session_id:
            new_session = ChatSession(user_id=current_user.id, title=request.query[:20])
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)
            session_id = str(new_session.id)
        else:
            session_id = request.session_id

        # 🧠 不再手动查询历史记录，改用记忆系统
        # 移除了手动历史查询代码，记忆系统会自动管理对话历史

        # 🧠 不再手动存储用户消息，记忆系统会自动处理
        # 移除了手动存储用户消息的代码

    # 2. 构造流式生成器 (Generator)
    async def event_generator():
        # SSE 标准要求数据以 "data: " 开头，以 "\n\n" 结尾

        # 先把 session_id 发给前端，让前端知道当前会话的 ID
        init_data = json.dumps({"type": "init", "session_id": session_id})
        yield f"data: {init_data}\n\n"

        # 🧠 调用集成了记忆系统的流式服务，传入user_id
        async for chunk in agent_service.chat_stream(
            user_input=request.query, 
            kb_id=request.kb_id, 
            session_id=session_id, 
            history=[],  # 空历史，使用记忆系统替代
            user_id=str(current_user.id)  # 🧠 传入user_id
        ):
            # 将每个文字片段转为 JSON 发送
            chunk_data = json.dumps({"type": "chunk", "content": chunk}, ensure_ascii=False)
            yield f"data: {chunk_data}\n\n"

        # 🧠 不再手动存储AI回答，记忆系统会自动处理
        # 移除了手动存储AI回答的代码

        # 告诉前端：我说完了！
        done_data = json.dumps({"type": "done"})
        yield f"data: {done_data}\n\n"

    # 返回 StreamingResponse，指定媒体类型为 text/event-stream
    return StreamingResponse(event_generator(), media_type="text/event-stream")