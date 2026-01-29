import os
import shutil
import uuid
from pydoc import describe

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException,BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models import Document
from app.schemas import DocumentResponse
from app.services import file_service, embedding_service
from app.db import AsyncSessionLocal
from app.models import DocumentChunk
from app.services import chunk_service
from sqlalchemy import select

# 创建路由器实例
router = APIRouter()

# 定义文件保存的根目录
# 在项目根目录下会自动创建一个叫 uploads 的文件夹
UPLOAD_DIR = "uploads"
# 如果目录不存在，自动创建它（避免报错）
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),  # 接收前端上传的文件
        db: AsyncSession = Depends(get_db)  # 获取数据库连接
):
    """
    上传文档接口:
    1. 验证文件类型
    2. 保存文件到本地磁盘
    3. 在数据库创建记录
    """

    # -------------------------------------------------------
    # 1. 安全检查：验证文件类型
    # -------------------------------------------------------
    # 这是一个简单的白名单机制，防止用户上传 .exe 或 .py 脚本攻击服务器
    ALLOWED_TYPES = [
        "application/pdf",
        "text/plain",
        "application/msword",
        "image/png",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]

    # 注意：file.content_type 是前端传来的，虽然可以伪造，但能防君子
    if file.content_type not in ALLOWED_TYPES:
        # 如果你想宽容一点，可以把下面这两行注释掉，只打印警告
        print(f"警告: 用户上传了未验证的类型: {file.content_type}")
        raise HTTPException(status_code=400, detail=r"不支持的文件类型",)

    try:
        # -------------------------------------------------------
        # 2. 保存文件到硬盘 (IO 操作)
        # -------------------------------------------------------
        # 拼接完整的保存路径，例如: uploads/test.pdf
        # 生产环境建议在文件名前加 UUID，防止同名文件覆盖，这里演示简单写法
        file_location = os.path.join(UPLOAD_DIR, file.filename)

        # 使用 shutil 高效复制文件流
        # UploadFile 是一个临时文件，我们需要把它"倒"进我们的目标文件里
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 获取文件真实大小 (字节)
        file_size = os.path.getsize(file_location)

        # -------------------------------------------------------
        # 3. 写入数据库 (DB 操作)
        # -------------------------------------------------------
        # 创建一个 ORM 对象 (还没有存进数据库)
        new_doc = Document(
            filename=file.filename,
            file_path=file_location,
            file_type=file.content_type,
            file_size=file_size,
            status="pending",# 初始状态设为"等待处理"
            kb_id = uuid.UUID("ee9e1032-10e5-41f8-9de7-7f2804a3350f")
        )

        # 将对象添加到数据库会话
        db.add(new_doc)
        # 提交事务 (真正写入数据库)
        await db.commit()
        # 刷新对象 (从数据库重新读取 id 和 created_at 字段)
        await db.refresh(new_doc)

        # ➕ 新增：在后台触发解析任务
        # 当接口返回给用户 "OK" 后，后台会悄悄执行 run_parsing_task
        background_tasks.add_task(run_parsing_task, new_doc.id, new_doc.file_path, new_doc.file_type)

        # 返回结果 (FastAPI 会自动根据 response_model 转换成 JSON)
        return new_doc

    except Exception as e:
        # -------------------------------------------------------
        # 4. 容错处理
        # -------------------------------------------------------
        # 如果保存文件失败，或者数据库写入失败，我们需要回滚
        # 否则数据库里可能会有一条脏数据，但文件其实没存下来
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


# ➕ 新增：后台任务的具体逻辑
async def run_parsing_task(doc_id: uuid.UUID, file_path: str, file_type: str):
    print(f"🔄 [任务开始] 文档 ID: {doc_id}")

    # --- A. 提取文字 ---
    try:
        text_content = file_service.extract_text(file_path, file_type)
        if not text_content:
            print("⚠️ 内容为空，跳过")
            return
    except Exception as e:
        print(f"❌ 提取失败: {e}")
        return

    # --- B. 切分文字 ---
    try:
        # 这里必须用 chunk_service 实例调用 split_text
        chunks_text = chunk_service.split_text(text_content)
        print(f"✅ 切分完成: {len(chunks_text)} 段")
    except Exception as e:
        print(f"❌ 切分失败: {e}")
        return

    # --- C. 向量化 & 入库 ---
    async with AsyncSessionLocal() as db:
        try:
            new_chunks = []
            for index, chunk_text in enumerate(chunks_text):
                # 🌟 核心步骤：生成向量 (await 异步调用)
                vector = await embedding_service.get_embedding(chunk_text)

                new_chunk = DocumentChunk(
                    document_id=doc_id,
                    chunk_index=index,
                    content=chunk_text,
                    meta_info={},
                    embedding=vector  # 👈 把向量列表存进去
                )
                new_chunks.append(new_chunk)

            # 批量保存
            db.add_all(new_chunks)

            # 更新父文档状态
            stmt = select(Document).where(Document.id == doc_id)
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "completed"
                db.add(doc)

            await db.commit()
            print(f"🎉 [任务完成] 向量化完成，数据已入库！")

        except Exception as e:
            print(f"❌ 数据库操作失败: {e}")
            await db.rollback()