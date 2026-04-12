#!/usr/bin/env python3
"""
诊断文档上传问题
检查数据库中的文档记录是否与实际文件匹配
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.document import Document


async def diagnose_documents():
    """诊断所有文档"""
    print("🔍 诊断文档上传问题...\n")

    async with AsyncSessionLocal() as db:
        # 查询所有文档
        stmt = select(Document).order_by(Document.created_at.desc()).limit(20)
        result = await db.execute(stmt)
        documents = result.scalars().all()

        print(f"📊 找到 {len(documents)} 个文档\n")
        print("=" * 80)

        for i, doc in enumerate(documents, 1):
            print(f"\n📄 文档 #{i}")
            print(f"  ID: {doc.id}")
            print(f"  文件名: {doc.filename}")
            print(f"  文件类型: {doc.file_type}")
            print(f"  文件大小: {doc.file_size} bytes ({doc.file_size / 1024:.2f} KB)")
            print(f"  文件路径: {doc.file_path}")
            print(f"  状态: {doc.status}")
            print(f"  创建时间: {doc.created_at}")

            # 检查文件类型是否合理
            file_type_lower = (doc.file_type or '').lower()
            filename_lower = (doc.filename or '').lower()

            if 'html' in file_type_lower or 'html' in filename_lower:
                print(f"  ⚠️  警告: 文件类型是 HTML，可能有问题！")
            elif 'word' in file_type_lower or 'docx' in filename_lower:
                print(f"  ✅ 文件类型是 Word")
            elif doc.file_size > 0 and doc.file_size < 1000:
                print(f"  ⚠️  警告: 文件大小异常小，可能有问题！")
            elif doc.file_size == 0:
                print(f"  ❌ 错误: 文件大小为 0！")

        print("\n" + "=" * 80)

        # 检查是否有 HTML 相关的文档
        html_docs = [d for d in documents if 'html' in (d.file_type or '').lower() or 'html' in (d.filename or '').lower()]
        if html_docs:
            print(f"\n⚠️  警告: 发现 {len(html_docs)} 个 HTML 文档：")
            for doc in html_docs:
                print(f"  - {doc.filename} (类型: {doc.file_type})")


async def check_file_content():
    """尝试检查 MinIO 中的文件内容"""
    print("\n\n🔍 检查 MinIO 文件...\n")

    try:
        from app.services.minio_service import minio_service
        from app.database import async_session
        from sqlalchemy import select
        from app.models.document import Document

        minio_service._ensure_initialized()

        async with AsyncSessionLocal() as db:
            # 获取最新的几个文档
            stmt = select(Document).order_by(Document.created_at.desc()).limit(5)
            result = await db.execute(stmt)
            documents = result.scalars().all()

            for doc in documents:
                print(f"\n📄 检查: {doc.filename}")
                print(f"   路径: {doc.file_path}")

                try:
                    # 尝试下载文件
                    file_bytes = minio_service.download_document(doc.file_path)
                    print(f"   大小: {len(file_bytes)} bytes")

                    # 检查文件内容的前 200 字节
                    content_start = file_bytes[:200]
                    try:
                        text_preview = content_start.decode('utf-8', errors='ignore')
                        print(f"   内容预览: {repr(text_preview[:100])}")
                    except:
                        print(f"   内容预览: (二进制文件)")

                    # 检查是否是 HTML
                    if b'<!DOCTYPE html' in file_bytes[:200] or b'<html' in file_bytes[:200]:
                        print(f"   ⚠️  这是 HTML 文件，不是原始文件！")
                    elif b'PK' in file_bytes[:10]:  # ZIP/Word 签名
                        print(f"   ✅ 这是 Word 文件 (ZIP 格式)")

                except Exception as e:
                    print(f"   ❌ 错误: {e}")

    except ImportError as e:
        print(f"⚠️  无法导入 MinIO 服务: {e}")
    except Exception as e:
        print(f"❌ 检查失败: {e}")


if __name__ == "__main__":
    print("=" * 80)
    print("📋 文档诊断工具")
    print("=" * 80)

    asyncio.run(diagnose_documents())
    asyncio.run(check_file_content())

    print("\n" + "=" * 80)
    print("💡 建议:")
    print("  1. 如果发现 HTML 文件出现在文档列表中，请删除它")
    print("  2. 重新上传正确的 Word 文件")
    print("  3. 确保上传前选择的是正确的文件")
    print("=" * 80)
