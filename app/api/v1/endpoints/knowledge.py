# app/api/v1/endpoints/knowledge.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy import select
from app.api import deps
from app.models.user import User
from app.models.knowledge_base import KnowledgeBase
from app.models import Document, DocumentChunk
from app.db import AsyncSessionLocal
from app.schemas.knowledge import KnowledgeBaseCreate
from uuid import UUID
import shutil
import os

# 👇 1. 引入核心服务 (Service Layer)
# 这样就把“怎么读文件”和“怎么切文件”的复杂逻辑剥离出去了
from app.services.file_service import file_service
from app.services.chunk_service import chunk_service
from app.services.embedding_service import embedding_service

router = APIRouter()


# ==========================================
# 🔧 核心逻辑：后台向量化任务 (V7 Service 调用版)
# ==========================================
async def process_document_task(doc_id: UUID):
    """
    后台任务：调用 file_service 提取文本 -> chunk_service 切片 -> embedding_service 向量化 -> 存库
    """
    print(f"⚙️ [后台任务] 开始处理文档: {doc_id}")

    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            return

        try:
            # --- 1. 更新状态为处理中 ---
            doc.status = "processing"
            await db.commit()

            # --- 2. 提取文本 (使用 file_service) ---
            # ✅ 改进：支持 PDF, DOCX, TXT, MD 等多种格式，不再局限于 txt
            print(f"📄 正在解析文件内容: {doc.filename}")
            try:
                content = file_service.extract_text(doc.file_path, doc.file_type)
            except Exception as e:
                raise Exception(f"文件解析失败: {str(e)}")

            if not content:
                raise Exception("文件内容为空或无法提取")

            # --- 3. 文本切片 (使用 chunk_service) ---
            # ✅ 改进：调用 LangChain 递归分割器，保持语义完整性
            print(f"✂️ 正在进行语义切分...")
            final_chunks = chunk_service.split_text(content)

            if not final_chunks:
                raise Exception("文本切分后为空")

            print(f"🧩 文档被切分为 {len(final_chunks)} 个片段，开始向量化...")

            # --- 4. 向量化与存储 ---
            success_count = 0
            first_error_msg = None

            for idx, chunk_text in enumerate(final_chunks):
                # 调用 Embedding 服务
                vector = await embedding_service.get_embedding(chunk_text)

                if vector:
                    new_chunk = DocumentChunk(
                        document_id=doc.id,
                        content=chunk_text,
                        embedding=vector,
                        chunk_index=idx,
                        meta_info={"chunk_index": idx, "source": doc.filename}
                    )
                    db.add(new_chunk)
                    success_count += 1
                else:
                    if not first_error_msg:
                        first_error_msg = "AI 接口调用失败 (余额不足或网络错误)"

            # --- 5. 更新最终状态 ---
            if success_count == 0:
                doc.status = "failed"
                doc.error_msg = first_error_msg or "所有切片向量化均失败"
                print(f"❌ [后台任务] 失败：0/{len(final_chunks)} 成功。")
            elif success_count < len(final_chunks):
                doc.status = "completed"  # 或者 "partial"
                doc.error_msg = f"部分成功: {success_count}/{len(final_chunks)}"
                print(f"⚠️ [后台任务] 部分成功：{success_count}/{len(final_chunks)}")
            else:
                doc.status = "completed"
                doc.error_msg = None
                print(f"✅ [后台任务] 处理完全成功！ID: {doc_id}")

            await db.commit()

        except Exception as e:
            await db.rollback()
            print(f"❌ [后台任务] 严重错误: {e}")
            # 重新获取 doc 以防 session 问题，更新错误状态
            async with AsyncSessionLocal() as error_db:
                error_doc = await error_db.get(Document, doc_id)
                if error_doc:
                    error_doc.status = "failed"
                    error_doc.error_msg = str(e)[:500]
                    await error_db.commit()


# ==========================================
# 📚 知识库管理接口
# ==========================================

@router.get("/bases")
async def list_knowledge_bases(current_user: User = Depends(deps.get_current_user)):
    """获取我的所有知识库"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == current_user.id)
            .order_by(KnowledgeBase.created_at.desc())
        )
        return result.scalars().all()


@router.post("/bases")
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
    # 1. 确保目录存在
    # 建议：按 KB ID 分隔文件夹，避免所有文件混在一起
    upload_dir = f"storage/{kb_id}"
    os.makedirs(upload_dir, exist_ok=True)

    file_location = f"{upload_dir}/{file.filename}"

    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    async with AsyncSessionLocal() as db:
        # 2. 写入数据库记录
        new_doc = Document(
            kb_id=kb_id,
            filename=file.filename,
            file_path=file_location,
            file_type=file.content_type,
            status="pending"
        )
        db.add(new_doc)
        await db.commit()
        await db.refresh(new_doc)

        # 3. 触发后台任务
        background_tasks.add_task(process_document_task, new_doc.id)

        return {
            "msg": "上传成功，系统正在后台进行AI向量化处理",
            "doc_id": new_doc.id,
            "status": "pending"
        }