# app/api/v1/endpoints/knowledge.py

import os
import shutil
import hashlib
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

router = APIRouter()


# ==========================================
# 🛠️ 辅助函数：计算文件 MD5
# ==========================================
def calculate_md5(file_obj) -> str:
    """计算文件的 MD5 哈希值，用于查重"""
    md5 = hashlib.md5()
    # 分块读取，防止大文件撑爆内存
    for chunk in iter(lambda: file_obj.read(4096), b""):
        md5.update(chunk)
    # 关键：计算完必须把指针移回开头，否则后续无法保存文件
    file_obj.seek(0)
    return md5.hexdigest()


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
                content = file_service.extract_text(doc.file_path, doc.file_type)
            except Exception as e:
                raise Exception(f"文件解析失败: {str(e)}")

            if not content:
                raise Exception("文件内容为空或无法提取")

            print(f"✂️ 正在进行语义切分...")
            final_chunks = chunk_service.split_text(content)

            if not final_chunks:
                raise Exception("文本切分后为空")

            print(f"🧩 文档被切分为 {len(final_chunks)} 个片段，开始向量化...")
            success_count = 0
            first_error_msg = None

            for idx, chunk_text in enumerate(final_chunks):
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
                        first_error_msg = "AI 接口调用失败"

            if success_count == 0:
                doc.status = "failed"
                doc.error_msg = first_error_msg or "所有切片向量化均失败"
                print(f"❌ [后台任务] 失败：0/{len(final_chunks)} 成功。")
            elif success_count < len(final_chunks):
                doc.status = "completed"
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

    # --- 1. 安全检查：验证文件类型 ---
    ALLOWED_TYPES = [
        "application/pdf",
        "text/plain",
        "application/msword",
        "image/png",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

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

        # --- 3. 确保存储目录存在并保存文件 ---
        upload_dir = f"storage/{kb_id}"
        os.makedirs(upload_dir, exist_ok=True)
        file_location = f"{upload_dir}/{file.filename}"

        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 获取真实的文件大小
        file_size = os.path.getsize(file_location)

        # --- 4. 写入数据库记录 ---
        new_doc = Document(
            kb_id=kb_id,
            filename=file.filename,
            file_path=file_location,
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