import json
import time
import uuid
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

# 引入日志装饰器
from app.utils.log_decorators import log_user_action

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


@router.post("/agent_chat_stream")
@log_user_action(
    action_type="CHAT",
    action_name="agent_chat",
    resource_type="chat_session",
    description="Agent智能对话"
)
async def chat_with_agent_stream(
        request: AgentChatRequest,
        current_user: User = Depends(deps.get_current_user)
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
            print(f"🔍 [KB检查] KB不存在")
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

    # 2. 构造流式生成器 (Generator)
    async def event_generator():
        # SSE 标准要求数据以 "data: " 开头，以 "\n\n" 结尾
        
        # 流式输出缓冲配置
        BUFFER_SIZE = 5  # 每积累 N 个字符发送一次（平衡延迟和性能）
        MAX_WAIT_TIME = 0.1  # 最大等待时间（秒），超时后立即发送

        # 先把 session_id 发给前端，让前端知道当前会话的 ID
        init_data = json.dumps({"type": "init", "session_id": session_id})
        yield f"data: {init_data}\n\n"

        # 缓冲区
        text_buffer = ""
        last_send_time = time.time()

        async def flush_buffer():
            nonlocal text_buffer, last_send_time
            if text_buffer:
                chunk_data = json.dumps({"type": "chunk", "content": text_buffer}, ensure_ascii=False)
                yield f"data: {chunk_data}\n\n"
                text_buffer = ""
                last_send_time = time.time()

        try:
            # 🧠 调用集成了记忆系统的流式服务，传入user_id
            async for chunk in agent_service.chat_stream(
                user_input=request.query, 
                kb_id=request.kb_id, 
                session_id=session_id, 
                history=[],  # 空历史，使用记忆系统替代
                user_id=str(current_user.id)  # 🧠 传入user_id
            ):
                # 识别 sources 信息并单独发送
                if chunk.startswith("__SOURCES_EVENT__:"):
                    # 先刷新缓冲区
                    async for data in flush_buffer():
                        yield data
                    
                    sources_json = chunk[len("__SOURCES_EVENT__:"):]
                    try:
                        sources_data = json.loads(sources_json)
                        sources_event = json.dumps({"type": "sources", "sources": sources_data}, ensure_ascii=False)
                        yield f"data: {sources_event}\n\n"
                    except json.JSONDecodeError:
                        print(f"⚠️ [sources解析失败]: {sources_json[:100]}")
                    continue
                
                # 累积到缓冲区
                text_buffer += chunk
                
                # 达到缓冲区大小或超时时发送
                current_time = time.time()
                if len(text_buffer) >= BUFFER_SIZE or (current_time - last_send_time) >= MAX_WAIT_TIME:
                    async for data in flush_buffer():
                        yield data
                    
        except (ValueError, KeyError) as e:
            print(f"⚠️ [流式生成器数据错误]: {e}")
        except (OSError, IOError) as e:
            print(f"⚠️ [流式生成器IO错误]: {e}")
        except (OSError, IOError) as e:
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
        except Exception as e:
            print(f"⚠️ [流式生成器异常]: {e}")
        
        finally:
            # 最后刷新缓冲区
            async for data in flush_buffer():
                yield data

        # 🧠 不再手动存储AI回答，记忆系统会自动处理
        # 移除了手动存储AI回答的代码

        # 告诉前端：我说完了！
        done_data = json.dumps({"type": "done"})
        yield f"data: {done_data}\n\n"

    # 返回 StreamingResponse，指定媒体类型为 text/event-stream
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ==========================================
#  V4: 智能体编排器接口 🚀 新增
#  用于：企业智能体系统的统一入口
#  特点：接待Agent + 意图识别 + 专业Agent协作 + 反思审核
# ==========================================

class OrchestratorChatRequest(BaseModel):
    """编排器对话请求"""
    query: str  # 用户问题
    session_id: Optional[str] = None  # 会话ID
    enable_reflection: bool = True  # 是否启用反思审核
    enable_rag: bool = True  # 是否启用RAG


@router.post("/orchestrator_chat")
@log_user_action(
    action_type="CHAT",
    action_name="orchestrator_chat",
    resource_type="orchestrator_session",
    description="智能体编排器对话"
)
async def chat_with_orchestrator(
        request: OrchestratorChatRequest,
        current_user: User = Depends(deps.get_current_user)
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
    
    try:
        from app.multi_agent_system import AgentOrchestrator, OrchestrationContext
        
        orchestrator = AgentOrchestrator(
            tenant_id=str(current_user.id),
            user_id=str(current_user.id),
            enable_reflection=request.enable_reflection,
            enable_rag=request.enable_rag
        )
        
        await orchestrator.initialize()
        
        context = OrchestrationContext(
            session_id=request.session_id or str(uuid.uuid4()),
            tenant_id=str(current_user.id),
            user_id=str(current_user.id),
            user_query=request.query,
            context={"history": []},
            enable_reflection=request.enable_reflection,
            enable_rag=request.enable_rag
        )
        
        result = await orchestrator.process(context)
        
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
        current_user: User = Depends(deps.get_current_user)
):
    """
    [V4] 智能体编排器流式对话接口
    
    返回SSE流式响应，实时展示处理进度和结果
    """
    print(f"🌊 [编排器流式接口被调用] 用户: {current_user.email} | 问题: {request.query}")
    
    session_id = request.session_id or str(uuid.uuid4())
    
    async def event_generator():
        try:
            from app.multi_agent_system import AgentOrchestrator
            
            init_data = json.dumps({
                "type": "init",
                "session_id": session_id,
                "status": "processing"
            })
            yield f"data: {init_data}\n\n"
            
            orchestrator = AgentOrchestrator(
                tenant_id=str(current_user.id),
                user_id=str(current_user.id),
                enable_reflection=request.enable_reflection,
                enable_rag=request.enable_rag
            )
            
            await orchestrator.initialize()
            
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
        except (OSError, IOError) as e:
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
        except Exception as e:
            error_data = json.dumps({
                "type": "error",
                "error": str(e)
            })
            yield f"data: {error_data}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")