import time
from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import search_service
from app.services.llm_service import llm_service

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