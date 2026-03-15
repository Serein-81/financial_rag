# app/api/v1/endpoints/knowledge.py

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy import select

from app.api import deps
from app.models.user import User
from app.models.knowledge_base import KnowledgeBase
from app.models import Document, DocumentChunk
from app.db import AsyncSessionLocal
from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseOut

# 引入核心服务
from app.services.file_service import file_service
from app.services.chunk_service import chunk_service
from app.services.embedding_service import embedding_service
from app.services.minio_service import minio_service
from app.services.structured_document_service import structured_document_service

# 引入公共工具函数
from app.utils.file_utils import calculate_md5


router = APIRouter()


# ==========================================
# 🔧 核心逻辑：后台向量化任务
# ==========================================
async def process_document_task(doc_id: UUID):
    """后台任务：提取文本 -> 切片 -> 向量化 -> 存库"""
    print(f"⚙️ [后台任务] 开始处理文档: {doc_id}")

    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            return

        try:
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
                        token_count=chunk_result.tokens
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
                error_doc = await error_db.get(Document, doc_id)
                if error_doc:
                    error_doc.status = "failed"
                    error_doc.error_msg = str(e)[:500]
                    await error_db.commit()


# ==========================================
# 📚 知识库管理接口
# ==========================================


# 获取知识库列表 (只查自己的)
@router.get("/bases")
async def list_knowledge_bases(
    current_user: User = Depends(deps.get_current_user)
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == current_user.id) # 👈 核心：数据隔离
        )
        kbs = result.scalars().all()
        return kbs


# 创建知识库 (绑定当前用户)
@router.post("/bases",response_model=KnowledgeBaseOut)
async def create_knowledge_base(
        kb_in: KnowledgeBaseCreate,
        current_user: User = Depends(deps.get_current_user)
):
    """创建新知识库"""
    async with AsyncSessionLocal() as db:
        new_kb = KnowledgeBase(
            user_id=current_user.id,
            name=kb_in.name,
            description=kb_in.description
        )
        db.add(new_kb)
        await db.commit()
        await db.refresh(new_kb)
        return new_kb


@router.delete("/bases/{kb_id}")
async def delete_knowledge_base(kb_id: UUID, current_user: User = Depends(deps.get_current_user)):
    """删除知识库"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == current_user.id))
        kb = result.scalar_one_or_none()
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        await db.delete(kb)
        await db.commit()
        return {"msg": "删除成功"}


# ==========================================
# 📄 文档管理接口
# ==========================================

@router.get("/bases/{kb_id}/documents")
async def list_documents(kb_id: UUID, current_user: User = Depends(deps.get_current_user)):
    """获取指定知识库下的文件列表"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document)
            .where(Document.kb_id == kb_id)
            .order_by(Document.created_at.desc())
        )
        return result.scalars().all()

@router.post("/bases/{kb_id}/upload")
async def upload_document_to_kb(
        kb_id: UUID,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        current_user: User = Depends(deps.get_current_user)
):
    """上传文件到指定知识库，并触发后台解析"""

    # --- 1. 安全检查：验证文件类型（使用工厂模式动态获取支持的类型）---
    if not file_service.is_supported_type(file.content_type):
        supported_types = file_service.get_supported_types()
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件类型: {file.content_type}。支持的类型: {', '.join(supported_types)}"
        )

    # --- 2. 查重逻辑：计算 MD5 ---
    file_hash = calculate_md5(file.file)

    async with AsyncSessionLocal() as db:
        # 查询当前知识库是否已存在此文件
        stmt = select(Document).where(
            Document.hash == file_hash,
            Document.kb_id == kb_id
        )
        result = await db.execute(stmt)
        existing_doc = result.scalars().first()

        if existing_doc:
            raise HTTPException(
                status_code=400,
                detail=f"文件重复：该文件已存在于知识库中 (Filename: {existing_doc.filename})"
            )

        # 👇 修复缩进：必须和 if existing_doc 平级！
        # --- 3. 🌟 全新存储逻辑：存入 MinIO ---
        # 读取文件字节并计算大小
        file_bytes = await file.read()
        file_size = len(file_bytes)

        # 构造 MinIO 里的唯一文件名：kb_id/原始文件名
        object_name = f"{kb_id}/{file.filename}"

        try:
            # 上传到 MinIO
            file_path = minio_service.upload_document(
                file_bytes=file_bytes,
                object_name=object_name,
                content_type=file.content_type
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"文件存储到 MinIO 失败: {str(e)}")


        # --- 4. 写入数据库记录 ---
        new_doc = Document(
            kb_id=kb_id,
            filename=file.filename,
            file_path=file_path,  # 👈 修复变量名：直接使用上面从 MinIO 返回的 file_path
            file_type=file.content_type,
            file_size=file_size,  # 记录文件大小
            hash=file_hash,  # 记录 MD5
            status="pending"
        )
        db.add(new_doc)
        await db.commit()
        await db.refresh(new_doc)

        # --- 5. 触发后台任务 ---
        background_tasks.add_task(process_document_task, new_doc.id)

        return {
            "msg": "上传成功，系统正在后台进行AI向量化处理",
            "doc_id": new_doc.id,
            "status": "pending"
        }