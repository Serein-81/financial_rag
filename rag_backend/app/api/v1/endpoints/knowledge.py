# app/api/v1/endpoints/knowledge.py

from uuid import UUID
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_, and_, func as sqlalchemy_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db_with_tenant_context,
    get_current_user_from_token,
    validate_read_access,
    validate_write_access,
    validate_delete_access
)
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.knowledge_base import KnowledgeBase
from app.models import Document, DocumentChunk
from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseOut, DocumentOut
from app.services.tenant_security_service import tenant_security
from app.core.config import settings

# 引入核心服务
from app.services.file_service import file_service
from app.services.embedding_service import embedding_service
from app.services.minio_service import minio_service
from app.services.structured_document_service import structured_document_service

# 引入公共工具函数
from app.utils.file_utils import calculate_md5

# 引入日志装饰器
from app.utils.log_decorators import log_user_action


router = APIRouter()


@router.get("/debug/doc/{doc_id}")
async def debug_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_read_access)
):
    """调试接口：查看文档详情"""
    from app.models.document import Document
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        return {"error": "文档不存在"}
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "file_path": doc.file_path,
        "file_size": doc.file_size,
        "file_type": doc.file_type,
        "status": doc.status,
        "hash": doc.hash,
        "tenant_id": doc.tenant_id,
        "kb_id": str(doc.kb_id)
    }


@router.get("/bases", response_model=List[KnowledgeBaseOut])
async def get_knowledge_bases(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_read_access)
):
    """
    获取知识库列表（租户隔离）
    🔐 可见性过滤：
       - private: 只有创建者可以看到
       - enterprise: 整个租户可以看到

    Args:
        db: 数据库会话（已设置租户上下文）
        current_user: 当前用户
        tenant_id: 当前租户ID（已验证访问权限）

    Returns:
        List[KnowledgeBaseOut]: 知识库列表
    """
    try:
        # 查询知识库（租户隔离 + 可见性过滤）
        # 条件：属于当前租户 AND (是企业知识库 OR 是私人知识库且是创建者)
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.tenant_id == tenant_id,
                or_(
                    KnowledgeBase.visibility == "enterprise",
                    and_(
                        KnowledgeBase.visibility == "private",
                        KnowledgeBase.user_id == current_user.id
                    )
                )
            )
        )
        knowledge_bases = result.scalars().all()

        # 记录访问日志
        await tenant_security.log_security_event(
            event_type="knowledge_base_list_access",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "count": len(knowledge_bases)
            },
            severity="info"
        )

        return knowledge_bases

    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"获取知识库列表数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"获取知识库列表IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        await tenant_security.log_security_event(
            event_type="knowledge_base_access_error",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "error": str(e)
            },
            severity="warning"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve knowledge bases"
        )


@router.post("/bases", response_model=KnowledgeBaseOut)
@log_user_action(
    action_type="KNOWLEDGE",
    action_name="create_knowledge_base",
    resource_type="knowledge_base",
    description="创建知识库"
)
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_write_access)
):
    """
    创建知识库（租户隔离）
    🔐 权限控制：
       - 普通用户：只能创建私人知识库 (visibility='private')
       - 企业管理员：可以创建私人或企业知识库

    Args:
        kb_data: 知识库创建数据
        db: 数据库会话（已设置租户上下文）
        current_user: 当前用户
        tenant_id: 当前租户ID（已验证写入权限）

    Returns:
        KnowledgeBaseOut: 创建的知识库
    """
    try:
        # 验证 visibility 值
        valid_visibility = ["private", "enterprise"]
        if kb_data.visibility not in valid_visibility:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid visibility value. Must be one of: {valid_visibility}"
            )

        # 🔐 权限检查：普通用户只能创建私人知识库
        if kb_data.visibility == "enterprise" and not current_user.is_admin:
            raise HTTPException(
                status_code=403,
                detail="普通用户只能创建私人知识库，只有企业管理员可以创建企业知识库"
            )

        # 创建知识库
        knowledge_base = KnowledgeBase(
            name=kb_data.name,
            description=kb_data.description,
            tenant_id=tenant_id,
            user_id=current_user.id,
            visibility=kb_data.visibility
        )

        db.add(knowledge_base)
        await db.commit()
        await db.refresh(knowledge_base)

        # 记录创建日志
        await tenant_security.log_security_event(
            event_type="knowledge_base_created",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "kb_id": str(knowledge_base.id),
                "kb_name": knowledge_base.name,
                "visibility": knowledge_base.visibility
            },
            severity="info"
        )

        return knowledge_base
        
    except (ValueError, KeyError) as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"创建知识库数据错误: {str(e)}")
    except (OSError, IOError) as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建知识库IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        await db.rollback()
        
        # 记录错误
        await tenant_security.log_security_event(
            event_type="knowledge_base_creation_error",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "error": str(e),
                "kb_name": kb_data.name
            },
            severity="warning"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create knowledge base"
        )


# ==========================================
# 🔧 核心逻辑：后台向量化任务
# ==========================================
async def process_document_task(doc_id: UUID, tenant_id: str):
    """后台任务：提取文本 -> 切片 -> 向量化 -> 存库"""
    print(f"⚙️ [后台任务] 开始处理文档: {doc_id}, 租户: {tenant_id}")

    async with AsyncSessionLocal() as db:
        try:
            if not settings.PGBOUNCER_ENABLED:
                from app.middleware.tenant_middleware import set_tenant_context_for_db
                await set_tenant_context_for_db(db, tenant_id)
            
            doc = await db.get(Document, doc_id)
            if not doc:
                print(f"❌ 文档不存在: {doc_id}")
                return

            # 验证租户访问权限
            await tenant_security.validate_tenant_access(
                target_tenant_id=doc.tenant_id,
                operation="write",
                resource_type="document"
            )

            doc.status = "processing"
            await db.commit()

            print(f"📄 正在解析文件内容: {doc.filename}")
            try:
                # 🌟 使用结构化文档服务解析 - 使用异步版本避免阻塞
                file_bytes = await minio_service.download_document_async(doc.file_path)
                print(f"📥 从MinIO下载文件大小: {len(file_bytes)} bytes, file_path: {doc.file_path}")
                structured_doc = await structured_document_service.parse_document(
                    file_bytes, doc.filename, doc.file_type
                )
                
                # 获取文档统计信息
                doc_stats = structured_document_service.get_document_statistics(structured_doc)
                print(f"📊 文档统计: {doc_stats}")
                
                # 保存统计信息到文档meta_info
                doc.meta_info = doc_stats
                
            except (ValueError, KeyError) as e:
                raise HTTPException(status_code=400, detail=f"结构化文档解析数据错误: {str(e)}")
            except (OSError, IOError) as e:
                raise HTTPException(status_code=500, detail=f"结构化文档解析IO错误: {str(e)}")
            except (OSError, IOError) as e:
                raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"结构化文档解析失败: {str(e)}")

            print("✂️ 正在进行智能切分...")
            
            # 🌟 使用结构化切块
            # 优化参数：增加chunk_tokens减少碎片化，overlap保证上下文连续性
            chunk_results = await structured_document_service.chunk_structured_document(
                structured_doc,
                chunk_tokens=800,  # 增加到800 tokens，减少碎片化
                overlap_tokens=80   # 增加到80 tokens，保证上下文重叠
            )

            if not chunk_results:
                raise Exception("文本切分后为空")

            print(f"🧩 文档被切分为 {len(chunk_results)} 个片段，开始向量化...")
            first_error_msg = None
            
            chunks_to_insert = []
            for idx, chunk_result in enumerate(chunk_results):
                vector = await embedding_service.get_embedding(chunk_result.content)
                if vector:
                    meta_info = {
                        "chunk_index": idx, 
                        "source": doc.filename
                    }
                    if chunk_result.metadata:
                        meta_info.update(chunk_result.metadata)
                    
                    chunk = DocumentChunk(
                        document_id=doc.id,
                        content=chunk_result.content,
                        embedding=vector,
                        chunk_index=idx,
                        meta_info=meta_info,
                        heading_path=chunk_result.heading_path,
                        chunk_start=chunk_result.start,
                        chunk_end=chunk_result.end,
                        token_count=chunk_result.tokens,
                        tenant_id=tenant_id
                    )
                    chunks_to_insert.append(chunk)
                else:
                    if not first_error_msg:
                        first_error_msg = "AI 接口调用失败"
            
            success_count = len(chunks_to_insert)
            
            if chunks_to_insert:
                db.add_all(chunks_to_insert)

            if success_count == 0:
                doc.status = "failed"
                doc.error_msg = first_error_msg or "所有切片向量化均失败"
                print(f"❌ [后台任务] 失败：0/{len(chunk_results)} 成功。")
            elif success_count < len(chunk_results):
                doc.status = "completed"
                doc.error_msg = f"部分成功: {success_count}/{len(chunk_results)}"
                print(f"⚠️ [后台任务] 部分成功：{success_count}/{len(chunk_results)}")
            else:
                doc.status = "completed"
                doc.error_msg = None
                print(f"✅ [后台任务] 处理完全成功！ID: {doc_id}")

            await db.commit()

        except (ValueError, KeyError) as e:
            await db.rollback()
            print(f"❌ [后台任务] 数据错误: {e}")
        except (OSError, IOError) as e:
            await db.rollback()
            print(f"❌ [后台任务] IO错误: {e}")
        except (OSError, IOError) as e:
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
        except Exception as e:
            await db.rollback()
            print(f"❌ [后台任务] 严重错误: {e}")
            async with AsyncSessionLocal() as error_db:
                if not settings.PGBOUNCER_ENABLED:
                    from app.middleware.tenant_middleware import set_tenant_context_for_db
                    await set_tenant_context_for_db(error_db, tenant_id)
                error_doc = await error_db.get(Document, doc_id)
                if error_doc:
                    error_doc.status = "failed"
                    error_doc.error_msg = str(e)[:500]
                    await error_db.commit()


@router.delete("/bases/{kb_id}")
@log_user_action(
    action_type="KNOWLEDGE",
    action_name="delete_knowledge_base",
    resource_type="knowledge_base",
    description="删除知识库"
)
async def delete_knowledge_base(
    kb_id: UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_delete_access)
):
    """
    删除知识库（租户隔离）
    
    Args:
        kb_id: 知识库ID
        db: 数据库会话（已设置租户上下文）
        current_user: 当前用户
        tenant_id: 当前租户ID（已验证删除权限）
    
    Returns:
        删除结果
    """
    try:
        # 查询知识库（租户隔离 + 用户隔离）
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.tenant_id == tenant_id,
                KnowledgeBase.user_id == current_user.id
            )
        )
        kb = result.scalar_one_or_none()
        
        if not kb:
            raise HTTPException(
                status_code=404,
                detail="Knowledge base not found or access denied"
            )
        
        # 删除知识库（租户隔离 + 用户隔离）
        await db.delete(kb)
        await db.commit()
        
        # 记录删除日志
        await tenant_security.log_security_event(
            event_type="knowledge_base_deleted",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "kb_id": str(kb_id),
                "kb_name": kb.name
            },
            severity="info"
        )
        
        return {"msg": "Knowledge base deleted successfully"}
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"更新知识库数据错误: {str(e)}")
    except (OSError, IOError) as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"更新知识库IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        await db.rollback()
        
        # 记录错误
        await tenant_security.log_security_event(
            event_type="knowledge_base_deletion_error",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "kb_id": str(kb_id),
                "error": str(e)
            },
            severity="warning"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete knowledge base"
        )


# ==========================================
# 📄 文档管理接口
# ==========================================

@router.get("/bases/{kb_id}/documents")
async def list_documents(
    kb_id: UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_read_access)
):
    """
    获取指定知识库下的文件列表（租户隔离）
    
    Args:
        kb_id: 知识库ID
        db: 数据库会话（已设置租户上下文）
        current_user: 当前用户
        tenant_id: 当前租户ID（已验证读取权限）
    
    Returns:
        文档列表
    """
    try:
        # 验证知识库存在且属于当前租户
        # 🔐 可见性过滤：企业KB任何租户用户可访问，私人KB只有创建者可访问
        kb_result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.tenant_id == tenant_id,
                or_(
                    KnowledgeBase.visibility == "enterprise",
                    and_(
                        KnowledgeBase.visibility == "private",
                        KnowledgeBase.user_id == current_user.id
                    )
                )
            )
        )
        kb = kb_result.scalar_one_or_none()
        
        if not kb:
            raise HTTPException(
                status_code=404,
                detail="Knowledge base not found or access denied"
            )
        
        # 查询文档列表（可见性过滤）
        # 🔐 文档可见性：公开文档全租户可见，私人文档上传者可见
        result = await db.execute(
            select(Document)
            .where(
                Document.kb_id == kb_id,
                Document.tenant_id == tenant_id,
                or_(
                    Document.visibility == "public",
                    and_(
                        Document.visibility == "private",
                        Document.user_id == current_user.id
                    )
                )
            )
            .order_by(Document.created_at.desc())
        )
        documents = result.scalars().all()

        if not documents:
            return []

        doc_ids = [doc.id for doc in documents]
        chunk_count_result = await db.execute(
            select(DocumentChunk.document_id, sqlalchemy_func.count(DocumentChunk.id))
            .where(DocumentChunk.document_id.in_(doc_ids))
            .group_by(DocumentChunk.document_id)
        )
        chunk_counts = {row[0]: row[1] for row in chunk_count_result.all()}

        document_outs = []
        for doc in documents:
            doc_dict = {
                "id": doc.id,
                "kb_id": doc.kb_id,
                "user_id": doc.user_id,
                "filename": doc.filename,
                "file_path": doc.file_path,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "hash": doc.hash,
                "status": doc.status,
                "error_msg": doc.error_msg,
                "visibility": doc.visibility,
                "meta_info": doc.meta_info or {},
                "created_at": doc.created_at,
                "chunk_count": chunk_counts.get(doc.id, 0)
            }
            document_outs.append(DocumentOut(**doc_dict))
        
        # 记录访问日志
        await tenant_security.log_security_event(
            event_type="documents_list_access",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "kb_id": str(kb_id),
                "count": len(document_outs)
            },
            severity="info"
        )
        
        return document_outs
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"删除知识库数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"删除知识库IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        await tenant_security.log_security_event(
            event_type="documents_list_error",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "kb_id": str(kb_id),
                "error": str(e)
            },
            severity="warning"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve documents"
        )


@router.get("/documents/{doc_id}/download")
async def download_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_read_access)
):
    """
    下载文档源文件
    
    Args:
        doc_id: 文档ID
        db: 数据库会话
        current_user: 当前用户
        tenant_id: 当前租户ID
    
    Returns:
        文件流
    """
    try:
        # 查询文档
        doc_result = await db.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = doc_result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # 验证租户
        if doc.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # 🔐 可见性检查：私人文档只有上传者可下载
        if doc.visibility == "private" and doc.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # 查询知识库验证可见性
        kb_result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == doc.kb_id)
        )
        kb = kb_result.scalar_one_or_none()
        
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        
        # 🔐 知识库可见性检查
        if kb.visibility == "private" and kb.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not doc.file_path:
            raise HTTPException(status_code=404, detail="File path not found")
        
        # 从 MinIO 获取文件 - 使用异步版本避免阻塞
        try:
            file_bytes = await minio_service.download_document_async(doc.file_path)
        except (ValueError, KeyError) as e:
            print(f"❌ MinIO download data error: {e}")
            raise HTTPException(status_code=400, detail=f"下载数据错误: {str(e)}")
        except (OSError, IOError) as e:
            print(f"❌ MinIO download IO error: {e}")
            raise HTTPException(status_code=500, detail=f"下载IO错误: {str(e)}")
        except (OSError, IOError) as e:
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
        except Exception as e:
            print(f"❌ MinIO download error: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to download from storage: {str(e)}")
        
        # 确定文件名，使用 RFC 5987 编码支持中文
        filename = doc.filename or "document"
        encoded_filename = quote(filename)
        
        # 返回文件流
        from io import BytesIO
        return StreamingResponse(
            BytesIO(file_bytes),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename*=UTF-8\'\'{encoded_filename}'
            }
        )
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.delete("/documents/{doc_id}")
@log_user_action(
    action_type="DOCUMENT",
    action_name="delete_document",
    resource_type="document",
    description="删除文档"
)
async def delete_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_delete_access)
):
    """
    删除文档（租户隔离）
    🔐 权限控制：
       - 企业知识库文档：任何租户用户可删除
       - 私人知识库文档：只有创建者可删除
       - 私人文档：只有上传者可删除
    
    Args:
        doc_id: 文档ID
        db: 数据库会话
        current_user: 当前用户
        tenant_id: 当前租户ID
    
    Returns:
        删除成功消息
    """
    try:
        doc_result = await db.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = doc_result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if doc.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Document not found")
        
        kb_result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == doc.kb_id)
        )
        kb = kb_result.scalar_one_or_none()
        
        if kb and kb.visibility == "private" and kb.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if doc.visibility == "private" and doc.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if doc.file_path:
            try:
                await minio_service.delete_document_async(doc.file_path)
            except (ValueError, KeyError) as e:
                print(f"⚠️ MinIO delete data error: {e}")
            except (OSError, IOError) as e:
                print(f"⚠️ MinIO delete IO error: {e}")
                raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
            except Exception as e:
                print(f"⚠️ MinIO delete warning: {e}")
        
        await db.delete(doc)
        await db.commit()
        
        await tenant_security.log_security_event(
            event_type="document_deleted",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "doc_id": str(doc_id),
                "filename": doc.filename
            },
            severity="info"
        )
        
        return {"msg": "Document deleted successfully", "doc_id": str(doc_id)}
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.post("/bases/{kb_id}/upload")
@log_user_action(
    action_type="DOCUMENT",
    action_name="upload_document",
    resource_type="document",
    description="上传文档到知识库"
)
async def upload_document_to_kb(
    kb_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    visibility: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_write_access)
):
    """
    上传文件到指定知识库，并触发后台解析（租户隔离）
    🔐 可见性过滤：
       - enterprise: 任何属于该租户的用户都可以上传
       - private: 只有创建者可以上传
    🔐 文档可见性：
       - 企业知识库：可选 private 或 public，默认 public
       - 私人知识库：强制 private

    Args:
        kb_id: 知识库ID
        background_tasks: 后台任务
        file: 上传的文件
        visibility: 文档可见性（private/public），企业知识库可选，私人知识库强制 private
        db: 数据库会话（已设置租户上下文）
        current_user: 当前用户
        tenant_id: 当前租户ID（已验证写入权限）

    Returns:
        上传结果
    """
    try:
        # 验证知识库存在且属于当前租户
        # 🔐 可见性过滤：企业知识库任何租户用户可访问，私人知识库只有创建者可访问
        kb_result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.tenant_id == tenant_id,
                or_(
                    KnowledgeBase.visibility == "enterprise",
                    and_(
                        KnowledgeBase.visibility == "private",
                        KnowledgeBase.user_id == current_user.id
                    )
                )
            )
        )
        kb = kb_result.scalar_one_or_none()

        if not kb:
            raise HTTPException(
                status_code=404,
                detail="Knowledge base not found or access denied"
            )
        
        # 验证文件类型
        print(f"📄 上传文件: {file.filename}, 类型: {file.content_type}")
        if not file_service.is_supported_type(file.content_type):
            supported_types = file_service.get_supported_types()
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file.content_type}. Supported types: {', '.join(supported_types)}"
            )
        print("✅ 文件类型支持")

        # 🔐 文档可见性逻辑（提前确定，用于重复检查）
        # - 私人知识库：强制私人（只有上传者可见）
        # - 企业知识库：如果传入了 visibility 参数，使用传入的值；否则默认公开
        if kb.visibility == "private":
            document_visibility = "private"
        else:
            if visibility and visibility in ["private", "public"]:
                document_visibility = visibility
            else:
                document_visibility = "public"
        print(f"📋 文档可见性: {document_visibility}")

        # 计算文件哈希用于查重
        print("🔢 计算文件哈希...")
        file_hash = calculate_md5(file.file)
        print(f"✅ 文件哈希: {file_hash}")

        # 🔍 检查重复文件
        # 🔐 重复检查逻辑（根据文档可见性决定检查范围）：
        # - 私人知识库：检查整个租户内的重复
        # - 企业知识库：
        #   - 上传公开文档：检查所有公开的有没有重复
        #   - 上传私人文档：检查同一用户有没有重复
        duplicate_conditions = [
            Document.hash == file_hash,
            Document.kb_id == kb_id,
        ]
        
        if kb.visibility == "private":
            # 私人知识库：检查整个租户内的重复
            duplicate_conditions.append(Document.tenant_id == tenant_id)
            error_msg = "File already exists in knowledge base: {{filename}}"
        elif document_visibility == "public":
            # 企业知识库 + 公开文档：检查所有公开的有没有重复
            duplicate_conditions.append(Document.visibility == "public")
            error_msg = "Public file already exists in this knowledge base: {{filename}}"
        else:
            # 企业知识库 + 私人文档：检查同一用户有没有重复
            duplicate_conditions.append(Document.user_id == current_user.id)
            error_msg = "You have already uploaded this file: {{filename}}"
        
        print(f"🔍 检查重复文件，条件: {duplicate_conditions}")
        stmt = select(Document).where(*duplicate_conditions)
        result = await db.execute(stmt)
        existing_doc = result.scalars().first()

        if existing_doc:
            actual_error_msg = error_msg.replace("{{filename}}", existing_doc.filename)
            raise HTTPException(
                status_code=400,
                detail=actual_error_msg
            )
        print("✅ 不是重复文件")

        # 读取文件字节并计算大小
        print("📖 读取文件内容...")
        file_bytes = await file.read()
        file_size = len(file_bytes)
        print(f"✅ 文件大小: {file_size} bytes")
        
        if file_size == 0:
            raise HTTPException(
                status_code=400,
                detail=f"文件为空，请确保您选择了正确的文件。文件名: {file.filename}"
            )

        # 构造 MinIO 里的唯一文件名：tenant_id/user_id/knowledge/kb_id/原始文件名
        user_id = str(current_user.id)
        object_name = f"{tenant_id}/{user_id}/knowledge/{kb_id}/{file.filename}"
        print(f"📦 MinIO object_name: {object_name}")

        try:
            # 上传到 MinIO - 使用异步版本避免阻塞
            print(f"☁️ 开始上传到 MinIO, 文件大小: {file_size} bytes")
            file_path = await minio_service.upload_document_async(
                file_bytes=file_bytes,
                object_name=object_name,
                content_type=file.content_type
            )
            print(f"✅ MinIO 上传成功: {file_path}, 实际文件大小: {file_size} bytes")
        except (ValueError, KeyError) as e:
            print(f"❌ MinIO 上传数据错误: {e}")
            raise HTTPException(status_code=400, detail=f"上传数据错误: {str(e)}")
        except (OSError, IOError) as e:
            print(f"❌ MinIO 上传IO错误: {e}")
            raise HTTPException(status_code=500, detail=f"上传IO错误: {str(e)}")
        except (OSError, IOError) as e:
            raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
        except Exception as e:
            print(f"❌ MinIO 上传失败: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to upload file to storage: {str(e)}"
            )

        # 写入数据库记录（document_visibility 已在前面确定）
        new_doc = Document(
            kb_id=kb_id,
            user_id=current_user.id,
            filename=file.filename,
            file_path=file_path,
            file_type=file.content_type,
            file_size=file_size,
            hash=file_hash,
            status="pending",
            tenant_id=tenant_id,
            visibility=document_visibility
        )
        db.add(new_doc)
        await db.commit()
        await db.refresh(new_doc)

        # 记录上传日志
        await tenant_security.log_security_event(
            event_type="document_uploaded",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "kb_id": str(kb_id),
                "doc_id": str(new_doc.id),
                "filename": file.filename,
                "file_size": file_size
            },
            severity="info"
        )

        # 触发后台任务
        background_tasks.add_task(process_document_task, new_doc.id, tenant_id)

        return {
            "msg": "File uploaded successfully, processing in background",
            "doc_id": new_doc.id,
            "status": "pending",
            "chunk_count": 0
        }
        
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        import traceback
        print(f"❌ 上传文档数据错误: {e}")
        raise HTTPException(status_code=400, detail=f"上传文档数据错误: {str(e)}")
    except (OSError, IOError) as e:
        import traceback
        print(f"❌ 上传文档IO错误: {e}")
        raise HTTPException(status_code=500, detail=f"上传文档IO错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        import traceback
        print(f"❌ 上传文档时发生错误: {e}")
        traceback.print_exc()
        await db.rollback()
        
        # 记录错误
        await tenant_security.log_security_event(
            event_type="document_upload_error",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "kb_id": str(kb_id),
                "filename": file.filename if file else "unknown",
                "error": str(e)
            },
            severity="warning"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload document: {str(e)}"
        )