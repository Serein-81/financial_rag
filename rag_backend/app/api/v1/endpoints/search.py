import time
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from starlette import status
from typing import List, Optional
from app.schemas import SearchRequest, SearchResponse
from app.schemas.search import SearchWithCallbackRequest, HybridSearchResponse, CallbackMessage, HybridSynonymSearchRequest
from app.services import search_service
from app.services.enhanced_search_service import enhanced_search_service
from app.services.hybrid_search_service import HybridSearchService
from app.api import deps
from app.models.user import User

router = APIRouter()


@router.post("/query", response_model=SearchResponse)
async def search_knowledge_base(
    request: SearchRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    RAG 核心接口：语义检索
    输入问题，返回最匹配的文档片段
    🔐 租户隔离：自动从当前用户获取 tenant_id
    🔐 可见性过滤：根据 visibility 过滤私人/企业知识库
    """
    t0 = time.time()

    # 🔐 租户隔离：从当前用户获取租户ID
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="租户隔离失败：用户未绑定租户"
        )

    # 调用搜索服务（传递租户ID和用户ID）
    results = await search_service.search(
        query=request.query,
        top_k=request.top_k,
        kb_id=request.kb_id,
        score_threshold=request.score_threshold,
        tenant_id=str(tenant_id),
        user_id=str(current_user.id)
    )

    # 为含图片的 chunk 签发预签名 URL
    from app.services.multimodal_image_service import sign_result_images
    results = await sign_result_images(results)

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
    🔐 租户隔离：自动从当前用户获取 tenant_id

    Args:
        keywords: 关键词列表
        kb_id: 知识库ID（可选）
        top_k: 返回结果数量
        exact_match: 是否精确匹配
    """
    try:
        # 🔐 租户隔离
        if not current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="租户隔离失败：用户未绑定租户"
            )

        results = await search_service.keyword_search(
            keywords=keywords,
            kb_id=kb_id,
            top_k=top_k,
            exact_match=exact_match,
            tenant_id=str(current_user.tenant_id)
        )
        
        return {
            "success": True,
            "results": results,
            "total": len(results),
            "keywords": keywords,
            "exact_match": exact_match
        }
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"关键词搜索数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"关键词搜索IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
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
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"文档级搜索数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"文档级搜索IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
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
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"搜索统计数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"搜索统计IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索统计失败: {str(e)}")


@router.post("/hybrid", response_model=HybridSearchResponse)
async def hybrid_search(
    request: SearchWithCallbackRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    🆕 混合搜索接口：知识库 + Web 检索
    🔐 租户隔离：自动从当前用户获取 tenant_id

    Args:
        query: 搜索查询
        top_k: 返回结果数量
        kb_id: 知识库ID（可选）
        enable_web: 是否启用Web搜索
        enable_callback: 是否启用回调
        score_threshold: 相似度阈值
    """
    t0 = time.time()

    # 🔐 租户隔离
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="租户隔离失败：用户未绑定租户"
        )

    try:
        # 调用混合搜索服务（传递租户ID和用户ID）
        response = await enhanced_search_service.search_with_callback(
            query=request.query,
            top_k=request.top_k,
            kb_id=request.kb_id,
            score_threshold=request.score_threshold,
            enable_web=request.enable_web,
            callback=None,  # 同步模式不使用回调
            tenant_id=str(current_user.tenant_id),
            user_id=str(current_user.id)
        )

        return response

    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"混合搜索数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"混合搜索IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"混合搜索失败: {str(e)}")


@router.post("/hybrid/stream")
async def hybrid_search_stream(request: SearchWithCallbackRequest):
    """
    🆕 流式混合搜索接口：支持 Server-Sent Events 回调
    
    通过 SSE 实时推送搜索进度
    """
    
    async def event_generator():
        async def callback(data: dict):
            """SSE 回调函数"""
            message = CallbackMessage(**data)
            yield f"data: {message.model_dump_json()}\n\n"
        
        try:
            # 使用异步生成器
            callback_generator = callback
            
            response = await enhanced_search_service.search_with_callback(
                query=request.query,
                top_k=request.top_k,
                kb_id=request.kb_id,
                score_threshold=request.score_threshold,
                enable_web=request.enable_web,
                callback=callback_generator
            )
            
            # 发送最终结果
            yield f"event: final\ndata: {response.model_dump_json()}\n\n"
            
        except (ValueError, KeyError) as e:
            error_msg = CallbackMessage(
                status="error",
                error=f"流式搜索数据错误: {str(e)}"
            )
            yield f"event: error\ndata: {error_msg.model_dump_json()}\n\n"
        except (OSError, IOError) as e:
            error_msg = CallbackMessage(
                status="error",
                error=f"流式搜索IO错误: {str(e)}"
            )
            yield f"event: error\ndata: {error_msg.model_dump_json()}\n\n"
        except (OSError, IOError) as e:
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
        except Exception as e:
            error_msg = CallbackMessage(
                status="error",
                message=f"搜索失败: {str(e)}"
            )
            yield f"event: error\ndata: {error_msg.model_dump_json()}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/hybrid/synonym", response_model=SearchResponse)
async def hybrid_search_with_synonym(
    request: HybridSynonymSearchRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    🆕 混合搜索接口（支持同义词扩展）
    🔐 租户隔离：自动从当前用户获取 tenant_id

    集成三种搜索策略：
    1. 向量搜索（语义相似度）
    2. 同义词扩展搜索
    3. PostgreSQL全文搜索（短语匹配）

    Args:
        request: 包含权重配置的混合搜索请求

    Returns:
        搜索结果列表
    """
    import logging
    logger = logging.getLogger(__name__)

    # 🔐 租户隔离
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="租户隔离失败：用户未绑定租户"
        )

    t0 = time.time()

    try:
        service = HybridSearchService(
            vector_weight=request.vector_weight,
            synonym_weight=request.synonym_weight,
            fulltext_weight=request.fulltext_weight,
            enable_synonym=request.enable_synonym,
            enable_fulltext=request.enable_fulltext
        )

        # 🔐 传递租户ID和用户ID进行隔离和可见性过滤
        results = await service.search(
            query=request.query,
            kb_id=request.kb_id,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            tenant_id=str(current_user.tenant_id),
            user_id=str(current_user.id)
        )

        total_time = time.time() - t0

        return SearchResponse(
            results=results,
            total_time=total_time
        )

    except (ValueError, KeyError) as e:
        logger.error(f"❌ 混合搜索（同义词扩展）数据错误: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"混合搜索数据错误: {str(e)}")
    except (OSError, IOError) as e:
        logger.error(f"❌ 混合搜索（同义词扩展）IO错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"混合搜索IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"❌ 混合搜索（同义词扩展）失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"混合搜索失败: {str(e)}")


