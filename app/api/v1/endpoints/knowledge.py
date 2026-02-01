# app/api/v1/endpoints/knowledge.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy import select
from app.api import deps
from app.models.user import User
# 👇 从新文件导入
from app.models.knowledge_base import KnowledgeBase
from app.models import Document, DocumentChunk
from app.db import AsyncSessionLocal
from app.services.embedding_service import embedding_service
from app.schemas.knowledge import KnowledgeBaseCreate
from uuid import UUID
import shutil
import os
import re  # 👈 引入正则模块，这是核心

router = APIRouter()


# ==========================================
# 🔧 核心逻辑：后台向量化任务 (V6 智能正则切分版)
# ==========================================
async def process_document_task(doc_id: UUID):
    """
    后台任务：基于语义符(句号/换行)智能切片 -> 向量化 -> 存库
    """
    print(f"⚙️ [后台任务] 开始处理文档: {doc_id}")

    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, doc_id)
        if not doc:
            return

        try:
            doc.status = "processing"
            await db.commit()

            content = ""
            if doc.file_path.endswith(".txt"):
                with open(doc.file_path, "r", encoding="utf-8") as f:
                    content = f.read()

            # 👇👇👇 V6 核心修改：正则智能切分 👇👇👇
            # 目标：根据 句号(。.)、感叹号(！!)、问号(？?)、换行(\n) 进行切分
            # 优先句号，兼顾换行。

            # 1. 定义切分正则模式
            # pattern 解释：
            # [。？！.?!]  -> 匹配中文或英文的句号、问号、感叹号
            # |           -> 或
            # [\n\r]+     -> 匹配一个或多个换行符
            # ()          -> 保留分隔符本身 (为了把句号拼回去)
            pattern = r'([。？！.?!]|[\n\r]+)'

            # 2. 使用正则切分
            parts = re.split(pattern, content)

            chunks = []
            current_sentence = ""

            # 3. 重新组合 (因为 re.split 会把分隔符单独切出来)
            # 逻辑：内容 + 分隔符 = 完整句子
            for part in parts:
                # 如果是分隔符 (句号/换行)，把它拼到上一个句子后面，然后结束当前句子
                if re.match(pattern, part):
                    if current_sentence:
                        # 如果是换行符，且当前句子已经很短，可能不拼入换行符更好，但为了格式保留，我们拼进去
                        # 这里做一个小优化：如果是纯换行，就直接作为分割结束
                        if part.strip() == "":  # 是换行符
                            chunks.append(current_sentence.strip())
                        else:  # 是标点符号
                            chunks.append(current_sentence + part)

                        current_sentence = ""  # 重置
                else:
                    # 如果是文本内容，拼接到当前句子
                    current_sentence += part

            # 处理最后可能剩余的部分
            if current_sentence.strip():
                chunks.append(current_sentence.strip())

            # 4. 二次清洗 (去除空块和极短的块)
            final_chunks = []
            for c in chunks:
                c = c.strip()
                if len(c) >= 2:  # 至少2个字才算有效信息
                    final_chunks.append(c)

            # 👆👆👆 修改结束 👆👆👆

            print(f"📄 文档被正则切分为 {len(final_chunks)} 个语义片段，开始向量化...")

            # 👇👇👇 修复点：增加计数器 👇👇👇
            success_count = 0
            first_error_msg = None

            for idx, chunk_text in enumerate(final_chunks):
                # 调用 Embedding 服务
                # 注意：这里 embedding_service 内部捕获了异常返回 None，但打印了日志
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
                    success_count += 1  # 成功 +1
                else:
                    # 记录一下失败原因 (虽然 service 里打印了，但这里记录给数据库用)
                    if not first_error_msg:
                        first_error_msg = "AI 接口调用失败 (余额不足或网络错误)"

            # 👇👇👇 核心修复逻辑：根据成功数量判断最终状态 👇👇👇
            if success_count == 0:
                # 一个都没成，那就是失败
                doc.status = "failed"
                doc.error_msg = first_error_msg or "所有切片向量化均失败"
                print(f"❌ [后台任务] 文档处理失败：0/{len(final_chunks)} 个片段成功。")
            elif success_count < len(final_chunks):
                # 部分成功 (可选逻辑，看你业务需求，通常算 completed 或 partial)
                doc.status = "completed"
                doc.error_msg = f"部分成功: {success_count}/{len(final_chunks)} (有丢包)"
                print(f"⚠️ [后台任务] 文档处理部分成功：{success_count}/{len(final_chunks)}")
            else:
                # 全部成功
                doc.status = "completed"
                doc.error_msg = None
                print(f"✅ [后台任务] 文档处理完全成功！ID: {doc_id}")

            await db.commit()

        except Exception as e:
            await db.rollback()
            print(f"❌ [后台任务] 处理失败: {e}")
            doc.status = "failed"
            doc.error_msg = str(e)[:200]
            await db.commit()


# ==========================================
# 📚 知识库管理接口 (Knowledge Base)
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
        # 1. 使用 schema 接收 JSON Body
        kb_in: KnowledgeBaseCreate,
        current_user: User = Depends(deps.get_current_user)
):
    """创建新知识库"""
    async with AsyncSessionLocal() as db:
        # 2. 取值时使用对象属性访问 (kb_in.name)
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
        # 验证归属权
        result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == current_user.id))
        kb = result.scalar_one_or_none()
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        await db.delete(kb)
        await db.commit()
        return {"msg": "删除成功"}


# ==========================================
# 📄 文档管理接口 (Document)
# ==========================================

@router.get("/bases/{kb_id}/documents")
async def list_documents(kb_id: UUID, current_user: User = Depends(deps.get_current_user)):
    """获取指定知识库下的文件列表"""
    async with AsyncSessionLocal() as db:
        # 简单归属权校验
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
    file_location = f"storage/{file.filename}"
    os.makedirs("storage", exist_ok=True)
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    async with AsyncSessionLocal() as db:
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

        background_tasks.add_task(process_document_task, new_doc.id)

        return {
            "msg": "上传成功，系统正在后台进行AI向量化处理",
            "doc_id": new_doc.id,
            "status": "pending"
        }