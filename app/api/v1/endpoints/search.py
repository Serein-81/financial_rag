import time
from fastapi import APIRouter
from app.schemas import SearchRequest, SearchResponse
from app.services import search_service

router = APIRouter()


@router.post("/query", response_model=SearchResponse)
async def search_knowledge_base(request: SearchRequest):
    """
    RAG 核心接口：语义检索
    输入问题，返回最匹配的文档片段
    """
    t0 = time.time()

    # 调用搜索服务
    results = await search_service.search(request.query, request.top_k)

    total_time = time.time() - t0

    return SearchResponse(
        results=results,
        total_time=total_time
    )