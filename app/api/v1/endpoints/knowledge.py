# app/api/v1/endpoints/knowledge.py

from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db_with_tenant_context,
    get_current_user_from_token,
    get_current_tenant,
    validate_read_access,
    validate_write_access,
    validate_delete_access
)
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.knowledge_base import KnowledgeBase
from app.models import Document, DocumentChunk
from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseOut
from app.services.tenant_security_service import tenant_security
from app.middleware.tenant_middleware import set_tenant_context_for_db

# 引入核心服务
from app.services.file_service import file_service
from app.services.chunk_service import chunk_service
from app.services.embedding_service import embedding_service
from app.services.minio_service import minio_service
from app.services.structured_document_service import structured_document_service

# 引入公共工具函数
from app.utils.file_utils import calculate_md5


router = APIRouter()


@router.get("/bases", response_model=List[KnowledgeBaseOut])
async def get_knowledge_bases(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_read_access)
):
    """
    获取知识库列表（租户隔离）
    
    Args:
        db: 数据库会话（已设置租户上下文）
        current_user: 当前用户
        tenant_id: 当前租户ID（已验证访问权限）
    
    Returns:
        List[KnowledgeBaseOut]: 知识库列表
    """
    try:
        # 查询知识库（自动应用租户隔离）
        result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)
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
        
    except Exception as e:
        # 记录错误
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
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_write_access)
):
    """
    创建知识库（租户隔离）
    
    Args:
        kb_data: 知识库创建数据
        db: 数据库会话（已设置租户上下文）
        current_user: 当前用户
        tenant_id: 当前租户ID（已验证写入权限）
    
    Returns:
        KnowledgeBaseOut: 创建的知识库
    """
    try:
        # 创建知识库
        knowledge_base = KnowledgeBase(
            name=kb_data.name,
            description=kb_data.description,
            tenant_id=tenant_id,
            user_id=current_user.id
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
                "kb_name": knowledge_base.name
            },
            severity="info"
        )
        
        return knowledge_base
        
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
            # 设置租户上下文
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
                # 🌟 使用结构化文档服务解析
                file_bytes = minio_service.download_document(doc.file_path)
                structured_doc = await structured_document_service.parse_document(
                    file_bytes, doc.filename, doc.file_type
                )
                
                # 获取文档统计信息
                doc_stats = structured_document_service.get_document_statistics(structured_doc)
                print(f"📊 文档统计: {doc_stats}")
                
            except Exception as e:
                raise Exception(f"结构化文档解析失败: {str(e)}")

            print(f"✂️ 正在进行智能切分...")
            
            # 🌟 使用结构化切块
            chunk_results = await structured_document_service.chunk_structured_document(
                structured_doc,
                chunk_tokens=500,
                overlap_tokens=50
            )

            if not chunk_results:
                raise Exception("文本切分后为空")

            print(f"🧩 文档被切分为 {len(chunk_results)} 个片段，开始向量化...")
            success_count = 0
            first_error_msg = None

            for idx, chunk_result in enumerate(chunk_results):
                vector = await embedding_service.get_embedding(chunk_result.content)
                if vector:
                    # 构建元数据
                    meta_info = {
                        "chunk_index": idx, 
                        "source": doc.filename
                    }
                    if chunk_result.metadata:
                        meta_info.update(chunk_result.metadata)
                    
                    new_chunk = DocumentChunk(
                        document_id=doc.id,
                        content=chunk_result.content,
                        embedding=vector,
                        chunk_index=idx,
                        meta_info=meta_info,
                        # 🌟 保存新的元数据字段
                        heading_path=chunk_result.heading_path,
                        chunk_start=chunk_result.start,
                        chunk_end=chunk_result.end,
                        token_count=chunk_result.tokens,
                        tenant_id=tenant_id
                    )
                    db.add(new_chunk)
                    success_count += 1
                else:
                    if not first_error_msg:
                        first_error_msg = "AI 接口调用失败"

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

        except Exception as e:
            await db.rollback()
            print(f"❌ [后台任务] 严重错误: {e}")
            async with AsyncSessionLocal() as error_db:
                await set_tenant_context_for_db(error_db, tenant_id)
                error_doc = await error_db.get(Document, doc_id)
                if error_doc:
                    error_doc.status = "failed"
                    error_doc.error_msg = str(e)[:500]
                    await error_db.commit()


@router.delete("/bases/{kb_id}")
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
        # 查询知识库（自动应用租户隔离）
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.tenant_id == tenant_id
            )
        )
        kb = result.scalar_one_or_none()
        
        if not kb:
            raise HTTPException(
                status_code=404,
                detail="Knowledge base not found"
            )
        
        # 删除知识库
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
        kb_result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.tenant_id == tenant_id
            )
        )
        kb = kb_result.scalar_one_or_none()
        
        if not kb:
            raise HTTPException(
                status_code=404,
                detail="Knowledge base not found"
            )
        
        # 查询文档列表（自动应用租户隔离）
        result = await db.execute(
            select(Document)
            .where(
                Document.kb_id == kb_id,
                Document.tenant_id == tenant_id
            )
            .order_by(Document.created_at.desc())
        )
        documents = result.scalars().all()
        
        # 记录访问日志
        await tenant_security.log_security_event(
            event_type="documents_list_access",
            details={
                "user_id": str(current_user.id),
                "tenant_id": tenant_id,
                "kb_id": str(kb_id),
                "count": len(documents)
            },
            severity="info"
        )
        
        return documents
        
    except HTTPException:
        raise
    except Exception as e:
        # 记录错误
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

@router.post("/bases/{kb_id}/upload")
async def upload_document_to_kb(
    kb_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_with_tenant_context),
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_write_access)
):
    """
    上传文件到指定知识库，并触发后台解析（租户隔离）
    
    Args:
        kb_id: 知识库ID
        background_tasks: 后台任务
        file: 上传的文件
        db: 数据库会话（已设置租户上下文）
        current_user: 当前用户
        tenant_id: 当前租户ID（已验证写入权限）
    
    Returns:
        上传结果
    """
    try:
        # 验证知识库存在且属于当前租户
        kb_result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.tenant_id == tenant_id
            )
        )
        kb = kb_result.scalar_one_or_none()
        
        if not kb:
            raise HTTPException(
                status_code=404,
                detail="Knowledge base not found"
            )
        
        # 验证文件类型
        if not file_service.is_supported_type(file.content_type):
            supported_types = file_service.get_supported_types()
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file.content_type}. Supported types: {', '.join(supported_types)}"
            )

        # 计算文件哈希用于查重
        file_hash = calculate_md5(file.file)

        # 查询当前知识库是否已存在此文件
        stmt = select(Document).where(
            Document.hash == file_hash,
            Document.kb_id == kb_id,
            Document.tenant_id == tenant_id
        )
        result = await db.execute(stmt)
        existing_doc = result.scalars().first()

        if existing_doc:
            raise HTTPException(
                status_code=400,
                detail=f"File already exists in knowledge base: {existing_doc.filename}"
            )

        # 读取文件字节并计算大小
        file_bytes = await file.read()
        file_size = len(file_bytes)

        # 构造 MinIO 里的唯一文件名：tenant_id/kb_id/原始文件名
        object_name = f"{tenant_id}/{kb_id}/{file.filename}"

        try:
            # 上传到 MinIO
            file_path = minio_service.upload_document(
                file_bytes=file_bytes,
                object_name=object_name,
                content_type=file.content_type
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to upload file to storage: {str(e)}"
            )

        # 写入数据库记录
        new_doc = Document(
            kb_id=kb_id,
            filename=file.filename,
            file_path=file_path,
            file_type=file.content_type,
            file_size=file_size,
            hash=file_hash,
            status="pending",
            tenant_id=tenant_id
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
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
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
            detail="Failed to upload document"
        )