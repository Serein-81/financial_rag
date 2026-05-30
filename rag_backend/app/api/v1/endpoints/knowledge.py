# app/api/v1/endpoints/knowledge.py

from uuid import UUID
from typing import List, Optional
from urllib.parse import quote
import asyncio

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_, and_, func as sqlalchemy_func, text
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
# Phase 1: 物理切块落库 | Phase 2: 异步充血
# ==========================================
async def process_document_task(doc_id: UUID, tenant_id: str):
    print(f"[Phase 1] 开始处理文档: {doc_id}, 租户: {tenant_id}")

    domain = "general"
    chunks_to_insert = []
    structured_doc = None
    doc_stats = None
    doc_filename = ""
    doc_obj = None

    # ── 初始状态标记（短会话）──
    async with AsyncSessionLocal() as db:
        try:
            if not settings.PGBOUNCER_ENABLED:
                from app.middleware.tenant_middleware import set_tenant_context_for_db
                await set_tenant_context_for_db(db, tenant_id)
            doc = await db.get(Document, doc_id)
            if not doc:
                print(f"文档不存在: {doc_id}")
                return
            await tenant_security.validate_tenant_access(
                target_tenant_id=doc.tenant_id, operation="write", resource_type="document"
            )
            doc.status = "processing"
            doc.processing_state = "chunking"
            doc.processing_progress = 0
            doc.processing_message = "开始解析文件..."
            doc_filename = doc.filename
            doc_obj = doc
            await db.commit()
        except Exception as e:
            print(f"初始状态标记失败: {e}")
            return

    # ── Step 1: 解析文件（无 DB 连接）──
    try:
        file_bytes = await minio_service.download_document_async(doc_obj.file_path)
        structured_doc = await structured_document_service.parse_document(
            file_bytes, doc_filename, doc_obj.file_type,
            tenant_id=tenant_id, document_id=str(doc_id),
        )
        doc_stats = structured_document_service.get_document_statistics(structured_doc)
    except Exception as e:
        async with AsyncSessionLocal() as db:
            if not settings.PGBOUNCER_ENABLED:
                from app.middleware.tenant_middleware import set_tenant_context_for_db
                await set_tenant_context_for_db(db, tenant_id)
            d = await db.get(Document, doc_id)
            if d:
                d.status = "failed"; d.processing_state = "failed"; d.error_msg = f"解析失败: {str(e)[:200]}"
                await db.commit()
        return

    # ── Step 2: 领域检测（无 DB 连接）──
    from app.chunkers import domain_detector
    domain = await domain_detector.detect(
        filename=doc_filename, parsed_doc=structured_doc,
        kb_category=doc_stats.get("domain") if doc_stats else None,
    )

    # 写 domain 到文档 meta_info（短会话）
    async with AsyncSessionLocal() as db:
        try:
            if not settings.PGBOUNCER_ENABLED:
                from app.middleware.tenant_middleware import set_tenant_context_for_db
                await set_tenant_context_for_db(db, tenant_id)
            d = await db.get(Document, doc_id)
            if d:
                meta = d.meta_info or {}
                if doc_stats:
                    meta.update(doc_stats)
                meta["domain"] = domain
                d.meta_info = meta
                await db.commit()
        except Exception as e:
            print(f"写入领域信息失败: {e}")

    # ── Step 2.5: 多模态表格解析 + 用量记录（尽力而为，失败不阻塞主流程）──
    await _record_multimodal_usage(doc_id, tenant_id, structured_doc)

    # ── Step 3-5: 切块 + 元数据注入 + 关系构建（无 DB 连接）──
    from app.chunkers import domain_chunker_factory, metadata_injector, relationship_builder
    chunker = domain_chunker_factory.get_chunker(domain)
    chunk_results = chunker.chunk(structured_doc, chunk_tokens=800, overlap_tokens=80)
    if not chunk_results:
        raise Exception("文本切分后为空")
    chunk_results = metadata_injector.inject(structured_doc, chunk_results)
    chunk_results = relationship_builder.build(chunk_results, domain)

    # 图片引用 map（来自解析阶段）
    _image_map: dict = structured_doc.metadata.extra.get("image_map", {})

    # ── Step 6: 向量化 + 存储（短会话，逐块写入）──
    first_error_msg = None
    for idx, chunk_result in enumerate(chunk_results):
        # 每 5 块检查一次暂停/取消状态（短会话）
        if idx % 5 == 0:
            async with AsyncSessionLocal() as db:
                if not settings.PGBOUNCER_ENABLED:
                    from app.middleware.tenant_middleware import set_tenant_context_for_db
                    await set_tenant_context_for_db(db, tenant_id)
                d = await db.get(Document, doc_id)
                if d and d.processing_state in ["paused", "cancelled"]:
                    if d.processing_state == "paused":
                        while True:
                            await db.refresh(d)
                            if d.processing_state != "paused": break
                            if d.processing_state == "cancelled":
                                return
                            await asyncio.sleep(1)
                    else:
                        return

        vector = await embedding_service.get_embedding(chunk_result.content)
        if vector:
            meta_info = {"chunk_index": idx, "source": doc_filename, "domain": domain}
            if chunk_result.metadata:
                meta_info.update(chunk_result.metadata)
            # 扫描 chunk 内容里的图片 marker，写入 images 引用列表
            if _image_map:
                import re as _re
                found_ids = _re.findall(r"⟦IMG:([a-f0-9]+)⟧", chunk_result.content)
                if found_ids:
                    meta_info["images"] = [
                        _image_map[iid]
                        for iid in found_ids
                        if iid in _image_map
                    ]
                    # 从展示文本中去掉 marker（描述保留）
                    chunk_result.content = _re.sub(
                        r"⟦IMG:[a-f0-9]+⟧\n?", "", chunk_result.content
                    )
            chunk = DocumentChunk(
                document_id=doc_id, content=chunk_result.content, embedding=vector,
                chunk_index=idx, meta_info=meta_info, heading_path=chunk_result.heading_path,
                chunk_start=chunk_result.start, chunk_end=chunk_result.end,
                token_count=chunk_result.tokens, tenant_id=tenant_id,
                domain=domain, node_type=chunk_result.node_type,
                summary=chunk_result.summary, relationships=chunk_result.relationships or {},
            )
            chunks_to_insert.append(chunk)
        else:
            if not first_error_msg: first_error_msg = "向量化接口调用失败"

        # 每 5 块批量写入一次（短会话）
        if chunks_to_insert and (idx + 1) % 5 == 0 or idx == len(chunk_results) - 1:
            async with AsyncSessionLocal() as db:
                if not settings.PGBOUNCER_ENABLED:
                    from app.middleware.tenant_middleware import set_tenant_context_for_db
                    await set_tenant_context_for_db(db, tenant_id)
                db.add_all(chunks_to_insert)
                d = await db.get(Document, doc_id)
                if d:
                    progress = int((idx + 1) / len(chunk_results) * 70) + 10
                    d.processing_progress = progress
                    d.processing_message = f"向量化中... {idx + 1}/{len(chunk_results)}"
                await db.commit()
            chunks_to_insert = []

    # ── 最终状态标记（短会话）──
    async with AsyncSessionLocal() as db:
        try:
            if not settings.PGBOUNCER_ENABLED:
                from app.middleware.tenant_middleware import set_tenant_context_for_db
                await set_tenant_context_for_db(db, tenant_id)
            d = await db.get(Document, doc_id)
            if d:
                if first_error_msg and not chunks_to_insert:
                    d.status = "failed"; d.processing_state = "failed"
                    d.error_msg = first_error_msg; d.processing_message = "向量化失败"
                else:
                    d.status = "ready"; d.processing_state = "ready"
                    d.error_msg = None; d.processing_message = "Phase 1 完成"
                    d.processing_progress = 100
                await db.commit()
        except Exception as e:
            print(f"最终状态标记失败: {e}")

    # Phase 2: 仅 legal 领域异步充血（不阻塞主流程）
    if domain == "legal":
        import asyncio as _asyncio
        _asyncio.ensure_future(_run_phase2_enrichment(doc_id, tenant_id, chunks_to_insert))


async def _record_multimodal_usage(doc_id: UUID, tenant_id: str, structured_doc) -> None:
    """将解析出的表格块送入 MultiModalService，使多模态解析与用量统计在入库时真实发生。

    尽力而为：此处任何失败都不得中断主入库流程。
    图片/图表块当前未在 StructuredDocument 中保留原始字节，暂不接入 parse_chart。
    """
    if structured_doc is None:
        return

    from app.models.structured_document import BlockType
    table_blocks = [
        b for b in (structured_doc.raw_blocks or [])
        if b.type == BlockType.TABLE and b.table_data and b.table_data.rows
    ]
    if not table_blocks:
        return

    try:
        from app.services.multimodal_service import get_multimodal_service
        async with AsyncSessionLocal() as db:
            if not settings.PGBOUNCER_ENABLED:
                from app.middleware.tenant_middleware import set_tenant_context_for_db
                await set_tenant_context_for_db(db, tenant_id)
            service = await get_multimodal_service(db, tenant_id)
            for block in table_blocks:
                td = block.table_data
                try:
                    await service.parse_table(
                        [td.headers] + td.rows,
                        caption=td.caption,
                        document_id=doc_id,
                    )
                except Exception as e:
                    print(f"[多模态] 表格用量记录失败 doc={doc_id}: {e}")
    except Exception as e:
        print(f"[多模态] 用量记录初始化失败 doc={doc_id}: {e}")


async def _run_phase2_enrichment(doc_id: UUID, tenant_id: str, chunks: list):
    """
    Phase 2 异步充血：后台执行实体替换 + 摘要生成。
    不阻塞 process_document_task 的主流程，通过 asyncio.create_task 调度。
    """
    from app.models.document_enrichment_job import EnrichmentJob
    print(f"[Phase 2] 开始 legal 文档充血: {doc_id}")

    # 收集 PARENT chunk ID
    parent_chunk_ids = [
        str(c.id) for c in chunks
        if hasattr(c, 'node_type') and c.node_type == 'parent'
    ]

    # 创建任务记录
    job_ids = []
    async with AsyncSessionLocal() as db:
        if not settings.PGBOUNCER_ENABLED:
            from app.middleware.tenant_middleware import set_tenant_context_for_db
            await set_tenant_context_for_db(db, tenant_id)
        try:
            resolve_job = EnrichmentJob(
                document_id=doc_id, job_type="entity_resolve",
                domain="legal", status="running",
                payload={"chunk_count": len(chunks)}, max_retries=5,
            )
            db.add(resolve_job)
            await db.commit()
            await db.refresh(resolve_job)
            job_ids.append(resolve_job.id)
        except Exception as e:
            print(f"[Phase 2] 任务记录创建失败: {e}")
            return

    # ── 执行实体替换（无需重新解析 PDF，从 DB chunks 构建 preamble）──
    print(f"[Phase 2] 开始实体替换: {doc_id}")
    try:
        from app.chunkers.entity_resolver import entity_resolver
        from app.chunkers.base_chunker import ChunkResult as CR3
        from app.models.chunk import DocumentChunk
        from app.models.structured_document import StructuredDocument, DocumentBlock, BlockType, DocumentMetadata
        from sqlalchemy import select, update

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc_id)
                .order_by(DocumentChunk.chunk_index)
            )
            db_chunks = result.scalars().all()

            if not db_chunks:
                print(f"[Phase 2] 无 chunk 需要处理: {doc_id}")
            else:
                # 从已有 chunk 构建 preamble（前 3000 字符）
                preamble_text = ""
                for c in db_chunks[:5]:
                    preamble_text += (c.content or "") + "\n"
                preamble_text = preamble_text[:3000]

                # 构建简化的 StructuredDocument（仅含 preamble）
                simple_doc = StructuredDocument(
                    title="",
                    metadata=DocumentMetadata(),
                )
                if preamble_text:
                    simple_doc.add_raw_block(DocumentBlock(
                        type=BlockType.PARAGRAPH,
                        content=preamble_text,
                    ))

                # 将 db chunks 转成 ChunkResult 列表
                chunk_results = []
                for db_chunk in db_chunks:
                    cr = CR3(
                        content=db_chunk.content or "",
                        start=db_chunk.chunk_start or 0,
                        end=db_chunk.chunk_end or len(db_chunk.content or ""),
                        tokens=db_chunk.token_count or 0,
                        heading_path=db_chunk.heading_path,
                        chunk_index=db_chunk.chunk_index,
                        domain="legal",
                        node_type=db_chunk.node_type or "leaf",
                        relationships=db_chunk.relationships or {},
                    )
                    chunk_results.append(cr)

                resolved = await entity_resolver.resolve(simple_doc, chunk_results)
                for cr in resolved:
                    if cr.chunk_index < len(db_chunks) and cr.content != db_chunks[cr.chunk_index].content:
                        await db.execute(
                            update(DocumentChunk)
                            .where(DocumentChunk.id == db_chunks[cr.chunk_index].id)
                            .values(content=cr.content)
                        )
                await db.commit()
                print(f"[Phase 2] 实体替换完成: {doc_id}")
    except Exception as e:
        print(f"[Phase 2] 实体替换失败: {e}")
        import traceback; traceback.print_exc()

    # ── 执行摘要生成 ──
    if parent_chunk_ids:
        print(f"[Phase 2] 开始摘要生成: {doc_id}, {len(parent_chunk_ids)} 个 PARENT")
        try:
            from app.chunkers.summary_generator import summary_generator, ChunkResult as CR2
            from app.models.chunk import DocumentChunk
            from sqlalchemy import select, update

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(DocumentChunk).where(
                        DocumentChunk.id.in_([__import__("uuid").UUID(pid) for pid in parent_chunk_ids])
                    )
                )
                parent_db = result.scalars().all()
                parent_results = []
                for pchunk in parent_db:
                    cr = CR2(
                        content=pchunk.content,
                        start=pchunk.chunk_start or 0,
                        end=pchunk.chunk_end or len(pchunk.content or ""),
                        tokens=pchunk.token_count or 0,
                        chunk_index=pchunk.chunk_index,
                        domain="legal", node_type="parent",
                    )
                    parent_results.append(cr)

                await summary_generator.generate_for_all(parent_results)

                for cr in parent_results:
                    if cr.summary:
                        await db.execute(
                            update(DocumentChunk)
                            .where(DocumentChunk.id == parent_chunk_ids[cr.chunk_index])
                            .values(summary=cr.summary)
                        )
                await db.commit()
                print(f"[Phase 2] 摘要生成完成: {doc_id}")
        except Exception as e:
            print(f"[Phase 2] 摘要生成失败: {e}")
            import traceback; traceback.print_exc()

    # 标记任务完成
    for jid in job_ids:
        async with AsyncSessionLocal() as db:
            job = await db.get(EnrichmentJob, jid)
            if job:
                job.status = "completed"
                await db.commit()
    print(f"[Phase 2] 全部完成: {doc_id}")


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
        
        # 如果文档正在处理，先暂停再删除
        if doc.processing_state in [None, "pending", "processing"]:
            doc.processing_state = "cancelled"
            doc.processing_message = "用户删除，停止处理"
            doc.status = "failed"
            await db.commit()
            
            import asyncio
            await asyncio.sleep(1)
        
        # 删除文档的 chunks
        from app.models import DocumentChunk
        chunks_result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        )
        chunks = chunks_result.scalars().all()
        for chunk in chunks:
            await db.delete(chunk)
        
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
    # G6: 分块策略参数（前端透传，后台 process_document_task 按 doc.meta_info 读取）
    chunking_method: Optional[str] = Form(
        None, description="分块方法: fixed | adaptive（默认按 .env / domain router）"
    ),
    min_chunk_size: Optional[int] = Form(None, description="最小块大小（字符）"),
    max_chunk_size: Optional[int] = Form(None, description="最大块大小（字符）"),
    enable_llm_boundary: Optional[bool] = Form(
        None, description="自适应分块时是否启用 LLM 边界识别"
    ),
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
        chunking_method: 分块方法（fixed/adaptive），传入则覆盖默认
        min_chunk_size: 自适应分块最小块大小（字符）
        max_chunk_size: 自适应分块最大块大小（字符）
        enable_llm_boundary: 自适应分块是否启用 LLM 边界识别
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

        # G6: 把分块策略持久化到 meta_info.chunking，供后台 process_document_task 读取
        _chunking_meta = {
            k: v for k, v in {
                "method": chunking_method,
                "min_chunk_size": min_chunk_size,
                "max_chunk_size": max_chunk_size,
                "enable_llm_boundary": enable_llm_boundary,
            }.items() if v is not None
        }
        _doc_meta = {"chunking": _chunking_meta} if _chunking_meta else {}

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
            visibility=document_visibility,
            meta_info=_doc_meta,
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