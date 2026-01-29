import asyncio
import json
import time
from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from fastapi.responses import StreamingResponse # 👈 导入 StreamingResponse
from app.services import search_service
from app.services.llm_service import llm_service
from starlette.concurrency import iterate_in_threadpool # 👈 1. 必须导入这个神器

router = APIRouter()


@router.post("/completions", response_model=ChatResponse)
async def chat_with_rag(request: ChatRequest):
    """
    RAG 对话接口 (Search + Generate)
    """
    start_time = time.time()

    # --- 1. 检索阶段 (Retrieval) ---
    print(f"🔍 正在搜索: {request.query}")
    search_results = await search_service.search(request.query, request.top_k)

    # 如果没搜到东西，就不浪费 Token 去问 AI 了
    if not search_results:
        return ChatResponse(
            answer="抱歉，知识库中没有找到相关信息，无法回答您的问题。",
            sources=[],
            total_time=time.time() - start_time,
            model_used="None"
        )

    # --- 2. 准备上下文 (Context) ---
    # 提取所有结果的文字内容
    context_texts = [item.content for item in search_results]

    # --- 3. 生成阶段 (Generation) ---
    print(f"🤖 正在调用模型: {llm_service.model_name}")
    ai_answer = await llm_service.get_answer(
        query=request.query,
        context_chunks=context_texts,
        history=request.history  # ✅ 把历史传进去
    )

    total_time = time.time() - start_time

    return ChatResponse(
        answer=ai_answer,
        sources=search_results,  # 把引用来源也返回给前端
        total_time=total_time,
        model_used=llm_service.model_name
    )


# 👇 新增流式接口
@router.post("/completions_stream")
async def chat_with_rag_stream(request: ChatRequest):
    """
    流式 RAG 对话接口
    """

    # 1. 检索 (Search) - 这里本来就是 async 的，没问题
    search_results = await search_service.search(request.query, request.top_k)

    # 2. 准备上下文
    context_texts = [item.content for item in search_results] if search_results else []

    # 3. 定义异步生成器
    async def generate_stream():
        # --- 阶段一：发送引用来源 ---
        sources_data = [
            {
                "filename": res.source_file,
                "score": res.score,
                "content": res.content[:50] + "..."
            }
            for res in search_results
        ]
        yield json.dumps({"type": "sources", "data": sources_data}, ensure_ascii=False) + "\n"

        if not context_texts:
            yield json.dumps({"type": "content", "delta": "抱歉，未找到相关信息。"}, ensure_ascii=False) + "\n"
            return

        # --- 阶段二：发送内容 (核心修改点) ---

        # ❌ 原来的写法 (会阻塞):
        # for char in llm_service.get_answer_stream(...):
        #     yield ...

        # ✅ 现在的写法 (非阻塞):
        # 使用 iterate_in_threadpool 把同步生成器包装成异步迭代器
        sync_generator = llm_service.get_answer_stream(request.query, context_texts, request.history)

        async for char in iterate_in_threadpool(sync_generator):
            yield json.dumps({"type": "content", "delta": char}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )