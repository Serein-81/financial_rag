"""
流式稳定性增强 API

提供流式响应的断点续传、进度查询等功能
"""

from app.utils.json_compat import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.responses import StreamingResponse
from app.schemas.chat import ChatRequest
from app.services.streaming_service import streaming_service
from app.services.search_service import search_service
from app.services.llm_service import llm_service
from app.api import deps
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.db import AsyncSessionLocal
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/streaming", tags=["Streaming Enhancement"])


@router.post("/chat")
async def streaming_chat_with_stability(
    request: ChatRequest,
    session_id: Optional[str] = Query(None, description="会话ID，不传则创建新会话"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    带稳定性保障的流式聊天
    
    功能：
    1. 增量保存 - 定期保存已生成内容
    2. 断点续传 - 支持从上次保存的位置恢复
    3. 进度追踪 - 实时返回流式进度
    """
    async with AsyncSessionLocal() as db:
        # 处理会话
        if not session_id:
            new_session = ChatSession(
                user_id=current_user.id,
                title=request.query[:20]
            )
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)
            session_id = str(new_session.id)
        
        # 创建流
        stream_id = await streaming_service.create_stream(
            session_id=session_id,
            metadata={
                "user_id": str(current_user.id),
                "query": request.query,
                "top_k": request.top_k,
            }
        )
        
        # 保存用户消息
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=request.query
        )
        db.add(user_msg)
        await db.commit()
    
    async def generate_stream():
        full_answer = ""
        
        try:
            # 开始流
            await streaming_service.start_stream(stream_id)
            
            yield json.dumps({
                "type": "stream_start",
                "stream_id": stream_id,
                "session_id": session_id,
            }, ensure_ascii=False) + "\n"
            
            # 搜索
            search_results = await search_service.search(
                request.query,
                request.top_k,
                kb_id=request.kb_id
            )
            context_texts = [item.content for item in search_results] if search_results else []
            
            # 返回源文档
            sources_data = [
                {
                    "filename": res.source_file,
                    "score": res.score,
                    "content": res.content[:100] + "..."
                }
                for res in search_results
            ]
            yield json.dumps({
                "type": "sources",
                "data": sources_data
            }, ensure_ascii=False) + "\n"
            
            # 创建保存回调
            async def save_callback(stream_id: str, content: str, chunk_index: int, token_count: int):
                try:
                    async with AsyncSessionLocal() as db:
                        # 保存当前进度到数据库
                        result = await db.execute(
                            select(ChatMessage)
                            .where(ChatMessage.session_id == session_id)
                            .where(ChatMessage.role == "assistant")
                            .order_by(ChatMessage.created_at.desc())
                        )
                        latest_msg = result.scalar_one_or_none()
                        
                        if latest_msg:
                            metadata = latest_msg.metadata or {}
                            metadata.update({
                                "stream_id": stream_id,
                                "chunk_index": chunk_index,
                                "token_count": token_count,
                                "last_save": "streaming_checkpoint"
                            })
                            latest_msg.content = content
                            latest_msg.metadata = metadata
                            await db.commit()
                except (ValueError, KeyError) as e:
                    logger.error(f"保存流式进度数据错误: {e}")
                except (OSError, IOError) as e:
                    logger.error(f"保存流式进度IO错误: {e}")
                except (OSError, IOError) as e:
                    raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
                except Exception as e:
                    logger.error(f"保存流式进度失败: {e}")
            
            # 流式生成
            stream_factory, _ = await llm_service.stream_answer_with_usage(
                request.query,
                context_texts,
                request.history or [],
            )
            
            async def async_generator():
                async for chunk in stream_factory():
                    if isinstance(chunk, dict):
                        if "delta" in chunk:
                            yield chunk["delta"]
                    else:
                        yield str(chunk)
            
            # 使用带保存功能的流
            buffer = []
            chunk_count = 0
            
            async for chunk in streaming_service.stream_with_save(
                stream_id,
                async_generator(),
                save_callback
            ):
                full_answer += chunk
                buffer.append(chunk)
                chunk_count += 1
                
                # 发送进度
                progress = await streaming_service.get_progress(stream_id)
                yield json.dumps({
                    "type": "progress",
                    "stream_id": stream_id,
                    "progress": progress,
                }, ensure_ascii=False) + "\n"
                
                # 发送内容
                yield json.dumps({
                    "type": "content",
                    "delta": chunk,
                }, ensure_ascii=False) + "\n"
            
            # 保存最终消息
            async with AsyncSessionLocal() as db:
                ai_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=full_answer,
                    sources=sources_data,
                )
                db.add(ai_msg)
                await db.commit()
            
            # 发送完成
            yield json.dumps({
                "type": "complete",
                "stream_id": stream_id,
                "total_content": len(full_answer),
                "total_chunks": chunk_count,
            }, ensure_ascii=False) + "\n"
            
        except (ValueError, KeyError) as e:
            logger.error(f"流式聊天数据错误: {e}")
            yield json.dumps({
                "type": "error",
                "error": f"流式聊天数据错误: {str(e)}"
            }, ensure_ascii=False) + "\n"
        except (OSError, IOError) as e:
            logger.error(f"流式聊天IO错误: {e}")
            yield json.dumps({
                "type": "error",
                "error": f"流式聊天IO错误: {str(e)}"
            }, ensure_ascii=False) + "\n"
        except (OSError, IOError) as e:
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
        except Exception as e:
            logger.error(f"流式聊天异常: {e}")
            yield json.dumps({
                "type": "error",
                "stream_id": stream_id,
                "error": str(e),
            }, ensure_ascii=False) + "\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )


@router.get("/progress/{stream_id}")
async def get_stream_progress(
    stream_id: str,
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    获取流式进度
    
    Args:
        stream_id: 流ID
        
    Returns:
        Dict: 进度信息
    """
    progress = await streaming_service.get_progress(stream_id)
    
    if not progress:
        raise HTTPException(status_code=404, detail="流不存在或已过期")
    
    return progress


@router.post("/resume/{stream_id}")
async def resume_stream(
    stream_id: str,
    request: ChatRequest,
    current_user: User = Depends(deps.get_current_user)
):
    """
    恢复流式响应
    
    Args:
        stream_id: 流ID
        request: 聊天请求
        
    Returns:
        StreamingResponse: 恢复的流式响应
    """
    # 获取断点
    checkpoint = await streaming_service.get_checkpoint(stream_id)
    
    if not checkpoint:
        raise HTTPException(status_code=404, detail="断点不存在或已过期")
    
    async def generate_resume_stream():
        full_answer = checkpoint.content
        
        try:
            yield json.dumps({
                "type": "stream_resume",
                "stream_id": stream_id,
                "session_id": checkpoint.session_id,
                "resume_from": len(checkpoint.content),
                "resume_from_chunk": checkpoint.chunk_index,
            }, ensure_ascii=False) + "\n"
            
            # 继续生成
            search_results = await search_service.search(
                request.query,
                request.top_k,
                kb_id=request.kb_id
            )
            context_texts = [item.content for item in search_results] if search_results else []
            
            stream_factory, _ = await llm_service.stream_answer_with_usage(
                request.query,
                context_texts,
                request.history or [],
            )
            
            async def async_generator():
                async for chunk in stream_factory():
                    if isinstance(chunk, dict):
                        if "delta" in chunk:
                            yield chunk["delta"]
                    else:
                        yield str(chunk)
            
            async for chunk in streaming_service.stream_with_save(stream_id, async_generator()):
                full_answer += chunk
                yield json.dumps({
                    "type": "content",
                    "delta": chunk,
                }, ensure_ascii=False) + "\n"
            
            yield json.dumps({
                "type": "complete",
                "stream_id": stream_id,
                "total_content": len(full_answer),
            }, ensure_ascii=False) + "\n"
            
        except (ValueError, KeyError) as e:
            logger.error(f"恢复流数据错误: {e}")
            yield json.dumps({
                "type": "error",
                "error": f"恢复流数据错误: {str(e)}"
            }, ensure_ascii=False) + "\n"
        except (OSError, IOError) as e:
            logger.error(f"恢复流IO错误: {e}")
            yield json.dumps({
                "type": "error",
                "error": f"恢复流IO错误: {str(e)}"
            }, ensure_ascii=False) + "\n"
        except (OSError, IOError) as e:
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
        except Exception as e:
            logger.error(f"恢复流异常: {e}")
            yield json.dumps({
                "type": "error",
                "stream_id": stream_id,
                "error": str(e),
            }, ensure_ascii=False) + "\n"
    
    return StreamingResponse(
        generate_resume_stream(),
        media_type="text/event-stream"
    )


@router.get("/active")
async def list_active_streams(
    session_id: Optional[str] = Query(None, description="按会话ID过滤"),
    current_user: User = Depends(deps.get_current_user)
) -> List[Dict[str, Any]]:
    """
    列出活跃流
    
    Args:
        session_id: 可选，按会话ID过滤
        
    Returns:
        List[Dict]: 活跃流列表
    """
    return await streaming_service.list_active_streams(session_id)


@router.post("/{stream_id}/cancel")
async def cancel_stream(
    stream_id: str,
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, str]:
    """
    取消流式响应
    
    Args:
        stream_id: 流ID
        
    Returns:
        Dict: 操作结果
    """
    await streaming_service.cancel_stream(stream_id)
    
    return {
        "status": "success",
        "message": f"流 {stream_id} 已取消",
        "stream_id": stream_id,
    }


@router.post("/cleanup")
async def cleanup_expired_streams(
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    清理过期的流和检查点
    
    Returns:
        Dict: 清理结果
    """
    await streaming_service.cleanup_expired()
    
    return {
        "status": "success",
        "message": "过期的流和检查点已清理",
    }


@router.get("/stats")
async def get_streaming_stats(
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    获取流式服务统计
    
    Returns:
        Dict: 统计信息
    """
    return streaming_service.get_stats()
