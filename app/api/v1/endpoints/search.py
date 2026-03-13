import time
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.schemas import SearchRequest, SearchResponse
from app.services import search_service
from app.api import deps
from app.models.user import User

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


@router.post("/keywords")
async def keyword_search(
    keywords: List[str],
    kb_id: Optional[str] = None,
    top_k: int = Query(20, ge=1, le=100),
    exact_match: bool = Query(False),
    current_user: User = Depends(deps.get_current_user)
):
    """
    关键词搜索接口
    
    Args:
        keywords: 关键词列表
        kb_id: 知识库ID（可选）
        top_k: 返回结果数量
        exact_match: 是否精确匹配
    """
    try:
        results = await search_service.keyword_search(
            keywords=keywords,
            kb_id=kb_id,
            top_k=top_k,
            exact_match=exact_match
        )
        
        return {
            "success": True,
            "results": results,
            "total": len(results),
            "keywords": keywords,
            "exact_match": exact_match
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关键词搜索失败: {str(e)}")


@router.get("/documents")
async def document_level_search(
    query: str = Query(..., description="搜索查询"),
    kb_id: Optional[str] = Query(None, description="知识库ID"),
    top_k: int = Query(10, ge=1, le=50),
    current_user: User = Depends(deps.get_current_user)
):
    """
    文档级别搜索接口
    
    返回包含关键词的文档列表，而不是文档片段
    """
    try:
        results = await search_service.document_level_search(
            query=query,
            kb_id=kb_id,
            top_k=top_k
        )
        
        return {
            "success": True,
            "documents": results,
            "total": len(results),
            "query": query
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档级搜索失败: {str(e)}")


@router.get("/statistics")
async def search_statistics(
    keyword: str = Query(..., description="统计关键词"),
    kb_id: Optional[str] = Query(None, description="知识库ID"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    搜索统计接口
    
    返回关键词在知识库中的统计信息
    """
    try:
        stats = await search_service.search_statistics(
            keyword=keyword,
            kb_id=kb_id
        )
        
        return {
            "success": True,
            "statistics": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索统计失败: {str(e)}")