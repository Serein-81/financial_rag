from app.utils.json_compat import json
import time
import asyncio
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Set, Any
from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import iterate_in_threadpool
from sqlalchemy import select
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from app.models.knowledge_base import KnowledgeBase
from app.models.tenant_settings import TenantSettings
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

# 引入日志装饰器
from app.utils.log_decorators import log_user_action


class OrchestratorChatRequest(BaseModel):
    """编排器对话请求"""
    query: str
    session_id: Optional[str] = None
    enable_reflection: bool = True
    enable_rag: bool = True


router = APIRouter()
logger = logging.getLogger(__name__)

STREAM_USER_ERROR_MESSAGE = "抱歉，AI 服务连接中断或网络不稳定，本次回答没有完整生成。请稍后重试。"


async def persist_chat_message(
    session_id: str,
    role: str,
    content: str,
    tenant_id: Optional[str] = None,
    sources: Optional[list] = None,
    agent_name: Optional[str] = None,
    turn: Optional[int] = None,
) -> Optional[str]:
    """Persist a chat message for session reload/history APIs.

    Returns the persisted message UUID (str) on success, None if skipped.
    Used by G1 so the SSE done event can carry message_id back to the frontend
    for feedback linkage.
    """
    if not content:
        return None

    session_uuid = uuid.UUID(str(session_id))
    async with AsyncSessionLocal() as db:
        message = ChatMessage(
            session_id=session_uuid,
            role=role,
            content=content,
            tenant_id=tenant_id,
            sources=sources,
            agent_name=agent_name,
            turn=turn or 1,
        )
        db.add(message)

        session = await db.get(ChatSession, session_uuid)
        if session:
            session.updated_at = datetime.now()

        await db.commit()
        await db.refresh(message)
        return str(message.id)


def has_stream_error_marker(text: str) -> bool:
    if not text:
        return False
    error_markers = ("DeepSeek 请求失败", "DeepSeek API 错误", "stream_error", "Connection error", "ReadTimeout")
    return any(marker in text for marker in error_markers)


def looks_like_incomplete_answer(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    dangling_suffixes = ("如下：", "如下:", "包括：", "包括:", "有：", "有:", "---")
    return len(stripped) < 80 and stripped.endswith(dangling_suffixes)


# ── 后台任务强引用集合 ──
# event_generator 创建的 asyncio.Task 在生成器退出后局部变量丢失，
# 模块级引用确保后台任务不被 GC 回收，直到完成。
_background_tasks: Set[asyncio.Task] = set()


def _safe_put(q: asyncio.Queue, item: tuple) -> None:
    """非阻塞写入队列，满时静默丢弃（后台任务不应被队列阻塞）。"""
    try:
        q.put_nowait(item)
    except asyncio.QueueFull:
        pass


# ── SSE 流缓冲 ──
# 存储每个会话最近的流式 chunk，用于断点续传。
# key = session_id, value = [(seq, type, payload), ...]
# 保留最近 500 条或 5 分钟后清理。
_stream_buffers: Dict[str, list] = {}
_STREAM_BUFFER_MAX_ITEMS = 500
_STREAM_BUFFER_TTL = 300  # 5 分钟


def _add_to_buffer(session_id: str, seq: int, event_type: str, payload: any) -> None:
    """添加 chunk 到会话缓冲"""
    if session_id not in _stream_buffers:
        _stream_buffers[session_id] = []
    buf = _stream_buffers[session_id]
    buf.append((seq, event_type, payload))
    # 超过上限时丢弃最旧的
    if len(buf) > _STREAM_BUFFER_MAX_ITEMS:
        buf[:50] = []  # 一次丢弃 50 条


def _get_buffer_since(session_id: str, last_seq: int) -> list:
    """获取会话缓冲中序号大于 last_seq 的所有条目"""
    buf = _stream_buffers.get(session_id, [])
    return [item for item in buf if item[0] > last_seq]


def _cleanup_buffer(session_id: str) -> None:
    """清理会话缓冲"""
    _stream_buffers.pop(session_id, None)


# ── 短时问答缓存 ──
# 仅用于拦截 30 秒内的完全相同的重复提问（如误触、连点），
# 不做时效性判断（是否有时效性应由 AI 决定，但判断本身需要 LLM 调用，与缓存目的矛盾）。
# 因此全部缓存 + 极短 TTL，长于 TTL 的重复提问走正常 LLM 流程。
_qa_cache: Dict[str, tuple] = {}
_QA_CACHE_TTL = 30  # 30 秒，仅防连点/误触
_QA_CACHE_MAX_ITEMS = 500


def _get_cached_answer(tenant_id: str, query: str, variant: str = "") -> Optional[str]:
    """获取缓存的问答结果。variant 携带检索设置签名，确保不同设置不会命中同一缓存。"""
    _key = f"{tenant_id}:{variant}:{hash(query)}"
    _item = _qa_cache.get(_key)
    if _item is None:
        return None
    _answer, _ts = _item
    if time.time() - _ts > _QA_CACHE_TTL:
        _qa_cache.pop(_key, None)
        return None
    return _answer


def _set_cached_answer(tenant_id: str, query: str, answer: str, variant: str = "") -> None:
    """缓存问答结果。variant 携带检索设置签名，确保不同设置分别缓存。"""
    if len(_qa_cache) >= _QA_CACHE_MAX_ITEMS:
        # 缓存满时清理最旧的 20%
        _keys_to_remove = sorted(_qa_cache.keys(), key=lambda k: _qa_cache[k][1])[:100]
        for _k in _keys_to_remove:
            _qa_cache.pop(_k, None)
    _key = f"{tenant_id}:{variant}:{hash(query)}"
    _qa_cache[_key] = (answer, time.time())


async def ensure_chat_session(session_id: Optional[str], user: User, query: str, tenant_id: Optional[str] = None) -> str:
    """Ensure orchestrator traces point to an existing chat session."""
    async with AsyncSessionLocal() as db:
        if session_id:
            try:
                session_uuid = uuid.UUID(str(session_id))
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的 session_id")

            result = await db.execute(
                select(ChatSession).where(ChatSession.id == session_uuid)
            )
            existing_session = result.scalar_one_or_none()
            if existing_session:
                if existing_session.user_id and existing_session.user_id != user.id:
                    raise HTTPException(status_code=403, detail="无权访问该会话")
                if tenant_id and existing_session.tenant_id and existing_session.tenant_id != tenant_id:
                    raise HTTPException(status_code=403, detail="无权访问该租户会话")
                return str(session_uuid)

            new_session = ChatSession(
                id=session_uuid,
                user_id=user.id,
                tenant_id=tenant_id or str(getattr(user, "tenant_id", "") or ""),
                title=query[:20]
            )
        else:
            new_session = ChatSession(
                user_id=user.id,
                tenant_id=tenant_id or str(getattr(user, "tenant_id", "") or ""),
                title=query[:20]
            )

        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        return str(new_session.id)


async def execute_orchestrator_background(
    task_id: str,
    session_id: str,
    tenant_id: str,
    user_id: str,
    query: str,
    enable_reflection: bool = True,
    enable_rag: bool = True
):
    """后台执行编排器任务，使用独立短生命周期会话更新状态。"""
    from datetime import datetime
    from sqlalchemy import update
    from app.models.agent_task import AgentTaskStatus, TaskStatus
    from app.db.session import AsyncSessionLocal

    async def update_task_status(**values):
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(AgentTaskStatus)
                .where(AgentTaskStatus.task_id == task_id)
                .values(**values)
            )
            await db.commit()

    try:
        await update_task_status(
            status=TaskStatus.RUNNING,
            started_at=datetime.now(),
            current_node="initializing",
            progress_percent=5,
            progress_message="正在初始化..."
        )

        logger.info("[编排器后台] 开始执行: task_id=%s", task_id)

        from app.multi_agent_system import AgentOrchestrator

        orchestrator = AgentOrchestrator(
            tenant_id=tenant_id,
            user_id=user_id,
            enable_reflection=enable_reflection,
            enable_rag=enable_rag
        )
        await orchestrator.initialize()

        await update_task_status(
            current_node="intent",
            progress_percent=30,
            progress_message="正在分析意图..."
        )

        node_progress = {
            "receptionist": 10,
            "intent_router": 30,
            "rag_retrieval": 45,
            "finance_specialist": 60,
            "tax_specialist": 60,
            "legal_specialist": 60,
            "reflection": 80,
            "final": 95,
        }
        node_messages = {
            "receptionist": "正在接收问题...",
            "intent_router": "正在分析意图...",
            "rag_retrieval": "正在检索知识库...",
            "finance_specialist": "财务专家分析中...",
            "tax_specialist": "税务专家分析中...",
            "legal_specialist": "法务专家分析中...",
            "reflection": "正在进行质量审核...",
            "final": "正在生成最终回答...",
        }

        async def persist_progress(node_name, node_state):
            await update_task_status(
                current_node=node_name,
                progress_percent=node_progress.get(node_name, 50),
                progress_message=node_messages.get(node_name, "任务处理中...")
            )

        result_context = await orchestrator.process_user_request(
            user_input=query,
            session_id=session_id,
            history=[],
            progress_callback=persist_progress
        )

        await update_task_status(
            current_node="specialists",
            progress_percent=50,
            progress_message="专家分析中..."
        )

        if result_context.needs_clarification and result_context.clarification_request:
            clarification_dict = result_context.clarification_request
            if hasattr(clarification_dict, "model_dump"):
                clarification_dict = clarification_dict.model_dump()

            intent_dict = None
            if result_context.intent_result:
                intent_dict = {
                    "category": getattr(result_context.intent_result, "intent", None),
                    "confidence": getattr(result_context.intent_result, "confidence", 0),
                    "routing_strategy": getattr(result_context.intent_result, "routing_strategy", None),
                }

            await update_task_status(
                status=TaskStatus.RUNNING,
                current_node="clarification",
                progress_percent=50,
                progress_message="等待用户补充信息",
                needs_clarification=True,
                clarification_request=clarification_dict,
                intent_analysis=intent_dict
            )
            logger.info("[编排器后台] 需要追问，状态已更新: task_id=%s", task_id)
            return

        await update_task_status(
            status=TaskStatus.COMPLETED,
            current_node="response",
            progress_percent=100,
            progress_message="任务完成",
            final_response=result_context.final_response,
            completed_at=datetime.now(),
            execution_time_ms=0.0,
            needs_clarification=False,
            clarification_request=None
        )
        logger.info("[编排器后台] 执行完成: task_id=%s", task_id)

    except Exception as e:
        error_msg = str(e)
        logger.error("[编排器后台] 执行失败: task_id=%s, error=%s", task_id, error_msg, exc_info=True)

        sanitized_error = error_msg
        if any(key in error_msg for key in ["enable_report_generation", "enable_reflection", "enable_rag"]):
            sanitized_error = "系统配置加载失败"
        elif any(key in error_msg for key in ["AttributeError", "object has no attribute", "'NoneType'"]):
            sanitized_error = "智能体初始化失败"
        elif len(error_msg) > 100 or any(key in error_msg for key in ["orchestrator", "AgentOrchestrator", "处理遇到问题"]):
            sanitized_error = "处理过程中遇到问题"

        try:
            await update_task_status(
                status=TaskStatus.FAILED,
                current_node="error",
                progress_percent=0,
                progress_message="任务执行失败",
                final_response=f"提示：{sanitized_error}，请稍后重试或刷新页面",
                error_message=sanitized_error,
                completed_at=datetime.now(),
                needs_clarification=False,
                clarification_request=None
            )
        except Exception as db_error:
            logger.error("[编排器后台] 更新失败状态失败: %s", db_error, exc_info=True)


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
    
    search_results = await search_service.search(
        query=request.query,
        top_k=request.top_k,
        tenant_id=tenant_context['tenant_id']
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
        async for chunk in iterate_in_threadpool(sync_generator):
            if isinstance(chunk, dict):
                if "delta" in chunk:
                    yield json.dumps({"type": "content", "delta": chunk["delta"]}, ensure_ascii=False) + "\n"
                elif "usage" in chunk:
                    yield json.dumps({"type": "usage", "data": chunk["usage"]}, ensure_ascii=False) + "\n"
            else:
                yield json.dumps({"type": "content", "delta": str(chunk)}, ensure_ascii=False) + "\n"

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

        user_msg = ChatMessage(session_id=session_id, role="user", content=request.query)
        db.add(user_msg)
        await db.commit()

        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.role == "assistant")
        )
        turn_count = result.scalars().all()
        current_turn = len(turn_count) + 1

    search_results = await search_service.search(
        query=request.query,
        top_k=request.top_k,
        kb_id=request.kb_id,
        tenant_id=str(current_user.tenant_id),
        user_id=str(current_user.id)
    )
    context_texts = [item.content for item in search_results] if search_results else []

    async def generate_save_stream():
        full_answer = ""
        usage_info = None

        yield json.dumps({"type": "session", "id": session_id}, ensure_ascii=False) + "\n"

        sources_data = [
            {"filename": res.source_file, "score": res.score, "content": res.content[:50] + "..."}
            for res in search_results
        ]
        yield json.dumps({"type": "sources", "data": sources_data}, ensure_ascii=False) + "\n"

        sync_gen = llm_service.get_answer_stream(request.query, context_texts, history)

        async for chunk in iterate_in_threadpool(sync_gen):
            if isinstance(chunk, dict):
                if "delta" in chunk:
                    full_answer += chunk["delta"]
                    yield json.dumps({"type": "content", "delta": chunk["delta"]}, ensure_ascii=False) + "\n"
                elif "usage" in chunk:
                    usage_info = chunk["usage"]
                    yield json.dumps({"type": "usage", "data": usage_info}, ensure_ascii=False) + "\n"
            else:
                full_answer += str(chunk)
                yield json.dumps({"type": "content", "delta": str(chunk)}, ensure_ascii=False) + "\n"

        try:
            async with AsyncSessionLocal() as db:
                total_tokens = usage_info.get("total_tokens") if usage_info else None
                ai_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=full_answer,
                    sources=sources_data,
                    prompt_tokens=usage_info.get("prompt_tokens") if usage_info else None,
                    completion_tokens=usage_info.get("completion_tokens") if usage_info else None,
                    total_tokens=total_tokens,
                    model_name=usage_info.get("model") if usage_info else None,
                    turn=current_turn,
                )
                db.add(ai_msg)
                await db.commit()
                print(f"💾 AI 回答已保存 (长度: {len(full_answer)}, tokens: {total_tokens})")
        except (ValueError, KeyError) as e:
            print(f"❌ 保存 AI 消息数据错误: {e}")
        except (OSError, IOError) as e:
            print(f"❌ 保存 AI 消息IO错误: {e}")
        except (OSError, IOError) as e:
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
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

    # 📝 检索策略相关（G3：前端透传，后端按能力降级使用，缺省保持向后兼容）
    retrieval_method: Optional[str] = None  # simple | graphrag | agentic
    max_iterations: Optional[int] = None  # 1-10，仅 agentic 生效
    top_k: Optional[int] = None  # 引用几段资料，默认 5
    enable_rerank: Optional[bool] = None  # 是否启用重排序
    enable_graph_expansion: Optional[bool] = None  # 是否启用图谱扩展


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
    except (ValueError, KeyError) as e:
        print(f"❌ [Agent 运行数据错误]: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        print(f"❌ [Agent 运行IO错误]: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        print(f"❌ [Agent 运行出错]: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/status/{session_id}")
async def get_chat_task_status(
    session_id: str,
    current_user: User = Depends(deps.get_current_user),
):
    """
    检查会话任务状态。

    前端切回页面时调用此接口区分两种情况：
    - status=completed: AI 已完成，直接 loadSession 拉取全部消息
    - status=generating: AI 仍在后台生成，继续轮询等待
    """
    try:
        _su = uuid.UUID(str(session_id))
        async with AsyncSessionLocal() as _db:
            # 检查会话归属
            _session = await _db.get(ChatSession, _su)
            if not _session or str(_session.user_id) != str(current_user.id):
                raise HTTPException(status_code=404, detail="会话不存在")

            # 检查是否有 assistant 回答
            _result = await _db.execute(
                select(ChatMessage).where(
                    ChatMessage.session_id == _su,
                    ChatMessage.role == "assistant",
                ).order_by(ChatMessage.created_at.desc()).limit(1)
            )
            _msg = _result.scalar_one_or_none()
            return {"status": "completed" if _msg else "generating"}
    except HTTPException:
        raise
    except Exception as _e:
        logger.warning(f"[CHAT] 任务状态查询失败: {_e}")
        return {"status": "unknown", "error": str(_e)}


@router.post("/agent_chat_stream")
@log_user_action(
    action_type="CHAT",
    action_name="agent_chat",
    resource_type="chat_session",
    description="Agent智能对话"
)
async def chat_with_agent_stream(
        request: AgentChatRequest,
        current_user: User = Depends(deps.get_current_user),
        tenant_context: dict = Depends(deps.get_tenant_context)
):
    print(f"🌊 [Agent 流式接口被调用] 用户: {current_user.email} | kb_id: {request.kb_id} | 问题: {request.query}")

    # 1. 越权校验（知识库权限检查）
    async with AsyncSessionLocal() as db:
        print(f"🔍 [KB检查] 查询 KB: kb_id={request.kb_id}")
        kb_check = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == request.kb_id)
        )
        kb = kb_check.scalar_one_or_none()
        print(f"🔍 [KB检查] 查询结果: {kb}, visibility={kb.visibility if kb else None}")

        if not kb:
            print("🔍 [KB检查] KB不存在")
            raise HTTPException(status_code=404, detail="知识库不存在")

        # 权限检查：企业级KB允许同租户所有用户访问，私人KB只有创建者可访问
        if kb.visibility == "enterprise":
            if kb.tenant_id != current_user.tenant_id:
                print(f"🔍 [KB检查] 企业KB但租户不匹配: KB_tenant={kb.tenant_id}, user_tenant={current_user.tenant_id}")
                raise HTTPException(status_code=403, detail="越权访问拦截！")
        else:  # private
            if kb.user_id != current_user.id:
                print(f"🔍 [KB检查] 私人KB但用户不匹配: KB_user={kb.user_id}, current_user={current_user.id}")
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

    # 2. 后台 Agent 任务 — 与 SSE 解耦
    async def _background_agent_stream(
        bg_queue: "asyncio.Queue",
        bg_session_id: str,
        bg_user_query: str,
        bg_kb_id: str,
        bg_user_id: str,
        bg_tenant_id: str,
        bg_persist_tenant_id: str,
        bg_retrieval_method: Optional[str] = None,
        bg_max_iterations: Optional[int] = None,
        bg_top_k: Optional[int] = None,
        bg_enable_rerank: Optional[bool] = None,
        bg_enable_graph_expansion: Optional[bool] = None,
    ) -> None:
        """后台运行 Agent 流式对话，与 SSE 连接生命周期无关。"""
        # 设置当前租户和用户上下文，供 get_enterprise_kb_overview 等工具使用
        if bg_tenant_id:
            from app.tools.agent_tools import set_tool_context
            set_tool_context(bg_tenant_id, bg_user_id)

        # ── 简单问题缓存命中检查 ──
        # 对于无时效性的重复问题，直接返回缓存结果，跳过 LLM 调用
        # 缓存键纳入检索设置签名：切换检索方法/TopK/Rerank/图谱后不会命中旧缓存
        _cache_variant = (
            f"{(bg_retrieval_method or 'simple')}|{bg_top_k}|{bg_enable_rerank}"
            f"|{bg_enable_graph_expansion}|{bg_max_iterations}"
        )
        _cached = _get_cached_answer(bg_tenant_id or "", bg_user_query, _cache_variant)
        if _cached is not None:
            logger.info("[CACHE] 简单问题缓存命中，跳过 LLM | query=%s", bg_user_query[:30])
            _safe_put(bg_queue, ("chunk", _cached, 1))
            # 缓存命中：仍然要透传一个最小 meta 让前端可保存反馈
            _cached_meta = {
                "retrieval_method": "cache",
                "kb_id": bg_kb_id,
                "chunks_used": [],
                "retrieval_history": [],
                "evaluation": None,
                "retrieval_time_ms": 0,
                "generation_time_ms": 0,
                "total_time_ms": 0,
                "token_count": len(_cached),
            }
            _cached_msg_id = await persist_chat_message(
                session_id=bg_session_id, role="assistant",
                content=_cached, tenant_id=bg_persist_tenant_id, agent_name="agent",
            )
            _cached_meta["message_id"] = _cached_msg_id
            _safe_put(bg_queue, ("done", _cached_meta))
            return

        # G1: 计时与元数据收集
        _t_start = time.time()
        _t_first_chunk: Optional[float] = None
        _meta_from_service: Dict[str, Any] = {}

        try:
            full_response = ""
            current_sources = []
            _seq = 0  # SSE 序列号

            async for chunk in agent_service.chat_stream(
                user_input=bg_user_query,
                kb_id=bg_kb_id,
                session_id=bg_session_id,
                history=[],
                user_id=bg_user_id,
                tenant_id=bg_tenant_id,
                retrieval_method=bg_retrieval_method,
                max_iterations=bg_max_iterations,
                top_k=bg_top_k,
                enable_rerank=bg_enable_rerank,
                enable_graph_expansion=bg_enable_graph_expansion,
            ):
                if has_stream_error_marker(chunk):
                    msg = STREAM_USER_ERROR_MESSAGE
                    await persist_chat_message(
                        session_id=bg_session_id, role="assistant",
                        content=msg, tenant_id=bg_persist_tenant_id, agent_name="agent",
                    )
                    _safe_put(bg_queue, ("error", msg))
                    return

                if chunk.startswith("__SOURCES_EVENT__:"):
                    sources_json = chunk[len("__SOURCES_EVENT__:"):]
                    try:
                        sources_data = json.loads(sources_json)
                        current_sources = sources_data if isinstance(sources_data, list) else []
                        _safe_put(bg_queue, ("sources", sources_data))
                    except json.JSONDecodeError:
                        print(f"⚠️ [sources解析失败]: {sources_json[:100]}")
                elif chunk.startswith("__META_EVENT__:"):
                    # G1/G2: 从 agent_service 接收检索元数据
                    meta_json = chunk[len("__META_EVENT__:"):]
                    try:
                        _meta_from_service = json.loads(meta_json) or {}
                    except json.JSONDecodeError:
                        print(f"⚠️ [meta解析失败]: {meta_json[:100]}")
                else:
                    _seq += 1
                    if _t_first_chunk is None:
                        _t_first_chunk = time.time()
                    full_response += chunk
                    # chunk 队列项: (type, payload, seq)
                    _safe_put(bg_queue, ("chunk", chunk, _seq))
                    _add_to_buffer(bg_session_id, _seq, "chunk", chunk)

            # 流式结束 → 保存 AI 回答到 chat_messages
            if not full_response.strip() or looks_like_incomplete_answer(full_response):
                msg = STREAM_USER_ERROR_MESSAGE
                await persist_chat_message(
                    session_id=bg_session_id, role="assistant",
                    content=msg, tenant_id=bg_persist_tenant_id, agent_name="agent",
                )
                _safe_put(bg_queue, ("error", msg))
                return

            _msg_id = await persist_chat_message(
                session_id=bg_session_id, role="assistant",
                content=full_response, tenant_id=bg_persist_tenant_id,
                sources=current_sources or None, agent_name="agent",
            )
            print(f"[CHAT] [后台] AI 回复已保存 | session={bg_session_id[:8]} | length={len(full_response)}")
            # 缓存简单问题的回答，下次重复提问时跳过 LLM
            _set_cached_answer(bg_tenant_id or "", bg_user_query, full_response, _cache_variant)

            # G1+G2: 组装完整 meta 在 done 事件中下发
            _t_end = time.time()
            _t_first = _t_first_chunk or _t_end
            _chunks_used = [
                {
                    "id": s.get("id") or s.get("chunk_id") or s.get("filename"),
                    "filename": s.get("filename"),
                    "score": s.get("score"),
                }
                for s in (current_sources or [])
                if isinstance(s, dict)
            ]
            _final_meta = {
                "message_id": _msg_id,
                "retrieval_method": _meta_from_service.get("retrieval_method")
                                    or bg_retrieval_method or "simple",
                "kb_id": bg_kb_id,
                "chunks_used": _chunks_used,
                "retrieval_time_ms": int(max(0.0, (_t_first - _t_start)) * 1000),
                "generation_time_ms": int(max(0.0, (_t_end - _t_first)) * 1000),
                "total_time_ms": int(max(0.0, (_t_end - _t_start)) * 1000),
                "token_count": len(full_response),  # 粗略估算；底层 usage 待接入后精确化
                # G2: Agentic RAG 步骤透传
                "retrieval_history": _meta_from_service.get("retrieval_history") or [],
                "evaluation": _meta_from_service.get("evaluation"),
                # 回显前端选择，便于调试 / UI 高亮当前模式
                "top_k": _meta_from_service.get("top_k") or bg_top_k,
                "enable_rerank": _meta_from_service.get("enable_rerank"),
                "enable_graph_expansion": _meta_from_service.get("enable_graph_expansion"),
                "max_iterations": _meta_from_service.get("max_iterations") or bg_max_iterations,
            }
            _safe_put(bg_queue, ("done", _final_meta))

        except Exception as e:
            print(f"[CHAT] [后台] 处理异常: {e}")
            _safe_put(bg_queue, ("error", str(e)))

    async def event_generator():
        # 先把 session_id 发给前端
        init_data = json.dumps({"type": "init", "session_id": session_id})
        yield f"data: {init_data}\n\n"

        normalized_query = (request.query or "").strip()
        enterprise_question_keywords = ("哪个企业", "哪個企業", "所属企业", "所屬企業", "当前企业", "當前企業")
        if any(keyword in normalized_query for keyword in enterprise_question_keywords):
            # 企业问题路径：直接回答并保存
            _e_tid = (tenant_context.get("tenant_id") or getattr(current_user, "tenant_id", "") or "").strip()
            _e_company = ""
            async with AsyncSessionLocal() as _edb:
                if _e_tid:
                    _e_tsr = await _edb.execute(select(TenantSettings.company_name).where(TenantSettings.tenant_id == _e_tid))
                    _e_company = (_e_tsr.scalar_one_or_none() or "").strip()
                if not _e_company:
                    _e_company = (getattr(current_user, "company_name", None) or "").strip()
            if _e_company:
                answer = f"你当前所在企业是：{_e_company}。"
            elif _e_tid:
                answer = f"我没有查到企业名称，但你当前所在的企业租户 ID 是：{_e_tid}。"
            else:
                answer = "我没有查到你当前账号绑定的企业信息。"
            await persist_chat_message(session_id=session_id, role="user", content=request.query, tenant_id=_e_tid)
            await persist_chat_message(session_id=session_id, role="assistant", content=answer, tenant_id=_e_tid, agent_name="agent")
            yield f"data: {json.dumps({'type': 'chunk', 'content': answer})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 普通对话：保存用户消息，启动后台任务
        _persist_tenant_id = str(tenant_context.get("tenant_id") or getattr(current_user, "tenant_id", "") or "")
        await persist_chat_message(session_id=session_id, role="user", content=request.query, tenant_id=_persist_tenant_id)

        _queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        _bg_task = asyncio.create_task(
            _background_agent_stream(
                bg_queue=_queue,
                bg_session_id=session_id,
                bg_user_query=request.query,
                bg_kb_id=request.kb_id,
                bg_user_id=str(current_user.id),
                bg_tenant_id=tenant_context.get("tenant_id") or str(getattr(current_user, "tenant_id", "") or ""),
                bg_persist_tenant_id=_persist_tenant_id,
                bg_retrieval_method=request.retrieval_method,
                bg_max_iterations=request.max_iterations,
                bg_top_k=request.top_k,
                bg_enable_rerank=request.enable_rerank,
                bg_enable_graph_expansion=request.enable_graph_expansion,
            )
        )
        _background_tasks.add(_bg_task)
        _bg_task.add_done_callback(_background_tasks.discard)

        _last_meta: Optional[Dict[str, Any]] = None
        try:
            while True:
                item = await _queue.get()
                if item is None:
                    break
                event_type = item[0]

                if event_type == "done":
                    # G1: item[1] 是完整 meta 字典；event_generator 末尾会拼到 done 事件
                    _last_meta = item[1] if len(item) > 1 else None
                    break
                if event_type == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': str(item[1])})}\n\n"
                    break

                if event_type == "chunk":
                    # chunk: (type, payload, seq)
                    _payload, _seq = item[1], item[2]
                    yield f"data: {json.dumps({'type': 'chunk', 'content': _payload, 'seq': _seq})}\n\n"
                elif event_type == "sources":
                    yield f"data: {json.dumps({'type': 'sources', 'sources': item[1]})}\n\n"

            _done_payload: Dict[str, Any] = {'type': 'done'}
            if isinstance(_last_meta, dict):
                _done_payload['meta'] = _last_meta
            yield f"data: {json.dumps(_done_payload, ensure_ascii=False)}\n\n"

        except GeneratorExit:
            print(f"[CHAT] 客户端断开 SSE，后台任务继续 | session={session_id[:8]}")
            _cleanup_buffer(session_id)
            return

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/orchestrator_chat_async")
@log_user_action(
    action_type="CHAT",
    action_name="orchestrator_chat_async",
    resource_type="orchestrator_session",
    description="智能体编排器异步对话（支持页面切换）"
)
async def chat_with_orchestrator_async(
        request: OrchestratorChatRequest,
        current_user: User = Depends(deps.get_current_user),
        tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    [异步版] 智能体编排器对话接口
    
    与 /orchestrator_chat_stream 的区别：
    1. 立即返回 task_id 和 thread_id（不阻塞）
    2. 任务在后台通过 ARQ Worker 执行
    3. 前端通过 GET /api/v1/agent-task/status/{thread_id} 查询进度
    4. 切换页面后通过 GET /api/v1/agent-task/hydrate/{thread_id} 恢复状态
    
    使用流程：
    1. POST /orchestrator_chat_async -> 获得 task_id, thread_id
    2. GET /agent-task/status/{thread_id} -> 轮询获取进度
    3. 页面切换后 GET /agent-task/hydrate/{thread_id} -> 恢复状态
    """
    logger.info("[编排器异步] 接收请求: user=%s, query=%s", current_user.email, request.query[:80])
    
    tenant_id = tenant_context['tenant_id']
    session_id = await ensure_chat_session(request.session_id, current_user, request.query, tenant_id)
    task_id = f"lgwf_{uuid.uuid4().hex[:16]}"
    
    try:
        from app.models.agent_task import AgentTaskStatus, TaskStatus, TaskPriority
        
        task_record = AgentTaskStatus(
            task_id=task_id,
            thread_id=session_id,
            tenant_id=tenant_id,
            user_id=current_user.id,
            task_type="langgraph_workflow",
            task_name="多智能体工作流",
            status=TaskStatus.PENDING,
            priority=TaskPriority.NORMAL,
            user_query=request.query,
            extra_metadata={
                "enable_reflection": request.enable_reflection,
                "enable_rag": request.enable_rag
            }
        )
        
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            db.add(task_record)
            await db.commit()
        
        import asyncio
        from datetime import datetime
        
        asyncio.create_task(
            execute_orchestrator_background(
                task_id=task_id,
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=str(current_user.id),
                query=request.query,
                enable_reflection=request.enable_reflection,
                enable_rag=request.enable_rag
            )
        )
        
        logger.info("[编排器异步] 任务已提交: task_id=%s, session_id=%s", task_id, session_id)
        
        return {
            "task_id": task_id,
            "thread_id": session_id,
            "session_id": session_id,
            "status": "submitted",
            "message": "任务已提交到后台，请轮询获取进度",
            "poll_url": f"/api/v1/agent-task/status/{session_id}",
            "hydrate_url": f"/api/v1/agent-task/hydrate/{session_id}"
        }
        
    except Exception as e:
        logger.error("[编排器异步] 提交任务失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"任务提交失败: {str(e)}")


async def _legacy_execute_orchestrator_background(
    task_id: str,
    session_id: str,
    tenant_id: str,
    user_id: str,
    query: str,
    enable_reflection: bool = True,
    enable_rag: bool = True
):
    """后台执行编排器任务"""
    from app.models.agent_task import AgentTaskStatus, TaskStatus
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import update
    from datetime import datetime
    
    async def update_task_status(**values):
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(AgentTaskStatus)
                .where(AgentTaskStatus.task_id == task_id)
                .values(**values)
            )
            await db.commit()

    try:
        async with AsyncSessionLocal() as db:
        
            await db.execute(
                update(AgentTaskStatus)
                .where(AgentTaskStatus.task_id == task_id)
                .values(
                    status=TaskStatus.RUNNING,
                    started_at=datetime.now(),
                    current_node="initializing",
                    progress_percent=5,
                    progress_message="正在初始化..."
                )
            )
            await db.commit()
        
        logger.info("[编排器后台] 开始执行: task_id=%s", task_id)
        
        from app.multi_agent_system import AgentOrchestrator
        
        orchestrator = AgentOrchestrator(
            tenant_id=tenant_id,
            user_id=user_id,
            enable_reflection=enable_reflection,
            enable_rag=enable_rag
        )
        
        await orchestrator.initialize()
        
        await db.execute(
            update(AgentTaskStatus)
            .where(AgentTaskStatus.task_id == task_id)
            .values(
                current_node="intent",  # 改为前端期望的节点名称
                progress_percent=30,
                progress_message="正在分析意图..."
            )
        )
        await db.commit()
        
        result_context = await orchestrator.process_user_request(
            user_input=query,
            session_id=session_id,
            history=[]
        )
        
        # 在专家处理前更新状态
        await db.execute(
            update(AgentTaskStatus)
            .where(AgentTaskStatus.task_id == task_id)
            .values(
                current_node="specialists",  # 专家处理阶段
                progress_percent=50,
                progress_message="专家分析中..."
            )
        )
        await db.commit()
        
        if result_context.needs_clarification and result_context.clarification_request:
            clarification_dict = result_context.clarification_request
            if hasattr(clarification_dict, 'model_dump'):
                clarification_dict = clarification_dict.model_dump()
            
            intent_dict = None
            if result_context.intent_result:
                intent_dict = {
                    "category": getattr(result_context.intent_result, 'intent', None),
                    "confidence": getattr(result_context.intent_result, 'confidence', 0),
                    "routing_strategy": getattr(result_context.intent_result, 'routing_strategy', None)
                }
            
            await db.execute(
                update(AgentTaskStatus)
                .where(AgentTaskStatus.task_id == task_id)
                .values(
                    status=TaskStatus.RUNNING,
                    current_node="clarification",
                    progress_percent=50,
                    progress_message="等待用户补充信息",
                    needs_clarification=True,
                    clarification_request=clarification_dict,
                    intent_analysis=intent_dict
                )
            )
            await db.commit()
            logger.info("[编排器后台] 需要追问，状态已更新: task_id=%s", task_id)
        else:
            await db.execute(
                update(AgentTaskStatus)
                .where(AgentTaskStatus.task_id == task_id)
                .values(
                    status=TaskStatus.COMPLETED,
                    current_node="response",  # 改为前端期望的节点名称
                    progress_percent=100,
                    progress_message="任务完成",
                    final_response=result_context.final_response,
                    completed_at=datetime.now(),
                    execution_time_ms=0.0
                )
            )
            await db.commit()
        
        logger.info("[编排器后台] 执行完成: task_id=%s", task_id)
        
    except Exception as e:
        error_msg = str(e)
        logger.error("[编排器后台] 执行失败: task_id=%s, error=%s", task_id, error_msg, exc_info=True)
        
        sanitized_error = error_msg
        if "enable_report_generation" in error_msg or "enable_reflection" in error_msg or "enable_rag" in error_msg:
            sanitized_error = "系统配置加载失败"
        elif "AttributeError" in error_msg or "object has no attribute" in error_msg or "'NoneType'" in error_msg:
            sanitized_error = "智能体初始化失败"
        elif len(error_msg) > 100 or any(x in error_msg for x in ["orchestrator", "AgentOrchestrator", "处理遇到问题"]):
            sanitized_error = "处理过程中遇到问题"
        
        try:
            await db.execute(
                update(AgentTaskStatus)
                .where(AgentTaskStatus.task_id == task_id)
                .values(
                    status=TaskStatus.FAILED,
                    current_node="error",
                    progress_percent=0,
                    progress_message="任务执行失败",
                    final_response=f"⚠️ {sanitized_error}，请稍后重试或刷新页面",
                    error_message=sanitized_error,
                    completed_at=datetime.now()
                )
            )
            await db.commit()
        except Exception as db_error:
            logger.error("[编排器后台] 更新失败状态失败: %s", db_error, exc_info=True)
            await db.rollback()


async def _legacy_execute_orchestrator_background(
    task_id: str,
    session_id: str,
    tenant_id: str,
    user_id: str,
    query: str,
    enable_reflection: bool = True,
    enable_rag: bool = True
):
    """Execute the orchestrator task with short-lived DB sessions for status updates."""
    from datetime import datetime
    from sqlalchemy import update
    from app.models.agent_task import AgentTaskStatus, TaskStatus
    from app.db.session import AsyncSessionLocal

    async def update_task_status(**values):
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(AgentTaskStatus)
                .where(AgentTaskStatus.task_id == task_id)
                .values(**values)
            )
            await db.commit()

    try:
        await update_task_status(
            status=TaskStatus.RUNNING,
            started_at=datetime.now(),
            current_node="initializing",
            progress_percent=5,
            progress_message="正在初始化..."
        )

        logger.info("[OrchestratorBackground] started: task_id=%s", task_id)

        from app.multi_agent_system import AgentOrchestrator

        orchestrator = AgentOrchestrator(
            tenant_id=tenant_id,
            user_id=user_id,
            enable_reflection=enable_reflection,
            enable_rag=enable_rag
        )
        await orchestrator.initialize()

        await update_task_status(
            current_node="intent",
            progress_percent=30,
            progress_message="正在分析意图..."
        )

        result_context = await orchestrator.process_user_request(
            user_input=query,
            session_id=session_id,
            history=[]
        )

        await update_task_status(
            current_node="specialists",
            progress_percent=50,
            progress_message="专家分析中..."
        )

        if result_context.needs_clarification and result_context.clarification_request:
            clarification_dict = result_context.clarification_request
            if hasattr(clarification_dict, "model_dump"):
                clarification_dict = clarification_dict.model_dump()

            intent_dict = None
            if result_context.intent_result:
                intent_dict = {
                    "category": getattr(result_context.intent_result, "intent", None),
                    "confidence": getattr(result_context.intent_result, "confidence", 0),
                    "routing_strategy": getattr(result_context.intent_result, "routing_strategy", None),
                }

            await update_task_status(
                status=TaskStatus.RUNNING,
                current_node="clarification",
                progress_percent=50,
                progress_message="等待用户补充信息",
                needs_clarification=True,
                clarification_request=clarification_dict,
                intent_analysis=intent_dict
            )
            logger.info("[OrchestratorBackground] waiting for clarification: task_id=%s", task_id)
            return

        await update_task_status(
            status=TaskStatus.COMPLETED,
            current_node="response",
            progress_percent=100,
            progress_message="任务完成",
            final_response=result_context.final_response,
            completed_at=datetime.now(),
            execution_time_ms=0.0,
            needs_clarification=False,
            clarification_request=None
        )
        logger.info("[OrchestratorBackground] completed: task_id=%s", task_id)

    except Exception as e:
        error_msg = str(e)
        logger.error("[OrchestratorBackground] failed: task_id=%s, error=%s", task_id, error_msg, exc_info=True)

        sanitized_error = error_msg
        if any(key in error_msg for key in ["enable_report_generation", "enable_reflection", "enable_rag"]):
            sanitized_error = "系统配置加载失败"
        elif any(key in error_msg for key in ["AttributeError", "object has no attribute", "'NoneType'"]):
            sanitized_error = "智能体初始化失败"
        elif len(error_msg) > 100 or any(key in error_msg for key in ["orchestrator", "AgentOrchestrator", "处理遇到问题"]):
            sanitized_error = "处理过程中遇到问题"

        try:
            await update_task_status(
                status=TaskStatus.FAILED,
                current_node="error",
                progress_percent=0,
                progress_message="任务执行失败",
                final_response=f"提示：{sanitized_error}，请稍后重试或刷新页面",
                error_message=sanitized_error,
                completed_at=datetime.now(),
                needs_clarification=False,
                clarification_request=None
            )
        except Exception as db_error:
            logger.error("[OrchestratorBackground] failed to persist failure: %s", db_error, exc_info=True)


# ==========================================
#  V4: 智能体编排器接口 🚀 新增
@log_user_action(
    action_type="CHAT",
    action_name="orchestrator_chat",
    resource_type="orchestrator_session",
    description="智能体编排器对话"
)
async def chat_with_orchestrator(
        request: OrchestratorChatRequest,
        current_user: User = Depends(deps.get_current_user),
        tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    [V4] 智能体编排器对话接口
    
    功能：
    1. 接待Agent接收用户输入
    2. 意图识别Agent分析问题类型
    3. 自动路由到合适的专业Agent
    4. 多专家协作处理复杂问题
    5. 反思Agent质量审核
    6. 返回结构化结果
    
    适用场景：
    - 企业智能问答系统
    - 多领域专业咨询
    - 复杂问题协作处理
    - 需要质量审核的关键业务
    """
    print(f"🎭 [编排器接口被调用] 用户: {current_user.email} | 问题: {request.query}")
    
    tenant_id = tenant_context['tenant_id']
    print(f"📋 使用租户ID: {tenant_id}")
    
    try:
        from app.multi_agent_system import AgentOrchestrator, OrchestrationContext
        
        orchestrator = AgentOrchestrator(
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            enable_reflection=request.enable_reflection,
            enable_rag=request.enable_rag
        )
        
        await orchestrator.initialize()
        
        context = OrchestrationContext(
            session_id=request.session_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=str(current_user.id),
            user_query=request.query,
            context={"history": []},
            enable_reflection=request.enable_reflection,
            enable_rag=request.enable_rag
        )
        
        result = await orchestrator.process(context)
        
        if context.needs_clarification and context.clarification_request:
            clarification = context.clarification_request
            return {
                "type": "clarification",
                "status": "needs_clarification",
                "session_id": context.session_id,
                "data": {
                    "question": clarification.question,
                    "suggestions": clarification.suggestions,
                    "reason": clarification.reason,
                    "required": clarification.required,
                    "placeholder": clarification.placeholder,
                    "clarification_type": clarification.type
                }
            }
        
        return {
            "status": "success" if result.final_response else "error",
            "session_id": context.session_id,
            "answer": result.final_response or "",
            "intent": result.intent_result.intent.value if result.intent_result else None,
            "confidence": result.intent_result.confidence if result.intent_result else 0.0,
            "requires_specialists": [r.get('specialist_type', '') for r in result.specialist_results],
            "needs_human_review": result.needs_human_review,
            "processing_time": 0,
            "metadata": {
                "enable_reflection": request.enable_reflection,
                "enable_rag": request.enable_rag
            }
        }
        
    except (ValueError, KeyError) as e:
        print(f"❌ [编排器运行数据错误]: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        print(f"❌ [编排器运行IO错误]: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        print(f"❌ [编排器运行出错]: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orchestrator_chat_stream")
@log_user_action(
    action_type="CHAT",
    action_name="orchestrator_chat_stream",
    resource_type="orchestrator_session",
    description="智能体编排器流式对话"
)
async def chat_with_orchestrator_stream(
        request: OrchestratorChatRequest,
        current_user: User = Depends(deps.get_current_user),
        tenant_context: dict = Depends(deps.get_tenant_context)
):
    """
    [V4] 智能体编排器流式对话接口
    
    使用 LangGraph 状态机进行多智能体协作
    返回SSE流式响应，实时展示处理进度和结果
    """
    print(f"🌊 [编排器流式接口被调用] 用户: {current_user.email} | 问题: {request.query}")
    
    tenant_id = tenant_context['tenant_id']
    print(f"📋 使用租户ID: {tenant_id}")
    
    session_id = await ensure_chat_session(request.session_id, current_user, request.query, tenant_id)
    
    async def event_generator():
        disconnected = False
        
        def mark_disconnected():
            nonlocal disconnected
            disconnected = True
            print("⚠️ [API] 标记客户端已断开")
        
        try:
            from app.multi_agent_system import AgentOrchestrator
            
            init_data = json.dumps({
                "type": "init",
                "session_id": session_id,
                "status": "processing",
                "mode": "langgraph_state_machine",
                "message": "开始处理，请勿切换页面..."
            })
            yield f"data: {init_data}\n\n"
            
            orchestrator = AgentOrchestrator(
                tenant_id=tenant_id,
                user_id=str(current_user.id),
                enable_reflection=request.enable_reflection,
                enable_rag=request.enable_rag
            )
            
            await orchestrator.initialize()
            
            warning_data = json.dumps({
                "type": "warning",
                "message": "⚠️ 请勿切换页面，正在处理中..."
            })
            yield f"data: {warning_data}\n\n"
            
            # 尝试使用新的 LangGraph 状态机
            try:
                print("🚀 [API] 使用 LangGraph 状态机处理...")
                
                # 使用新的状态机启动器
                result_context = await orchestrator.process_user_request(
                    user_input=request.query,
                    session_id=session_id,
                    history=[]
                )
                
                if disconnected:
                    print("⚠️ [API] 客户端已断开，停止发送响应")
                    return
                
                if result_context.needs_clarification and result_context.clarification_request:
                    clarification = result_context.clarification_request
                    if hasattr(clarification, 'model_dump'):
                        clarification_data = clarification.model_dump()
                    else:
                        clarification_data = clarification
                    
                    clarification_event = json.dumps({
                        "type": "clarification",
                        "data": {
                            "question": clarification_data.get('question', ''),
                            "suggestions": clarification_data.get('suggestions', []),
                            "reason": clarification_data.get('reason', ''),
                            "required": clarification_data.get('required', True),
                            "placeholder": clarification_data.get('placeholder', ''),
                            "clarification_type": clarification_data.get('type', 'intent_clarification')
                        }
                    })
                    yield f"data: {clarification_event}\n\n"
                    
                    done_data = json.dumps({
                        "type": "done",
                        "processing_time": 0,
                        "mode": "clarification"
                    })
                    yield f"data: {done_data}\n\n"
                    return
                
                # 发送意图分析阶段
                if result_context.intent_result:
                    # 安全获取意图类别和置信度
                    intent_result = result_context.intent_result
                    if isinstance(intent_result, str):
                        # 如果是字符串（从 LangGraph 状态机返回）
                        category = intent_result
                        confidence = 0.9
                    else:
                        # 如果是对象（IntentAnalysisResult）
                        category = intent_result.intent.value if hasattr(intent_result.intent, 'value') else str(intent_result.intent)
                        confidence = getattr(intent_result, 'confidence', 0.9)
                    
                    intent_data = json.dumps({
                        "type": "stage",
                        "stage": "intent",
                        "category": category,
                        "confidence": confidence,
                        "message": "意图分析完成"
                    })
                    yield f"data: {intent_data}\n\n"
                
                # 发送专家处理阶段
                specialist_data = json.dumps({
                    "type": "stage",
                    "stage": "specialists",
                    "message": "专家分析中..."
                })
                yield f"data: {specialist_data}\n\n"
                
                # 发送反思审核阶段
                reflection_data = json.dumps({
                    "type": "stage",
                    "stage": "reflection",
                    "message": "质量审核中..."
                })
                yield f"data: {reflection_data}\n\n"
                
                # 分行发送最终响应
                if result_context.final_response:
                    for i in range(0, len(result_context.final_response), 100):
                        chunk = result_context.final_response[i:i+100]
                        chunk_data = json.dumps({
                            "type": "text",
                            "content": chunk
                        })
                        yield f"data: {chunk_data}\n\n"
                        await asyncio.sleep(0.01)  # 模拟打字效果
                
                # 发送完成事件
                done_data = json.dumps({
                    "type": "done",
                    "processing_time": 0,
                    "mode": "langgraph_state_machine"
                })
                yield f"data: {done_data}\n\n"
                
                print(f"✅ [API] LangGraph 状态机处理完成")
                
            except Exception as langgraph_error:
                print(f"⚠️ [API] LangGraph 状态机失败，回退到流式处理: {langgraph_error}")
                
                # 回退到旧的流式处理
                async for event_json in orchestrator.stream_process(
                    user_input=request.query,
                    session_id=session_id,
                    history=[]
                ):
                    yield f"data: {event_json}\n\n"
            
        except (ValueError, KeyError) as e:
            error_data = json.dumps({
                "type": "error",
                "error": f"数据错误: {str(e)}"
            })
            yield f"data: {error_data}\n\n"
        except (OSError, IOError) as e:
            error_data = json.dumps({
                "type": "error",
                "error": f"IO错误: {str(e)}"
            })
            yield f"data: {error_data}\n\n"
        except GeneratorExit:
            print("⚠️ [API] 客户端断开连接 (GeneratorExit)")
            mark_disconnected()
            return
        except Exception as e:
            error_data = json.dumps({
                "type": "error",
                "error": str(e)
            })
            yield f"data: {error_data}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
