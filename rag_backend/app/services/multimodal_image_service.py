"""
多模态图片处理公共 helper

职责：
  1. 调用 VLM 生成图片描述（Word/PDF 共用）
  2. 将原始图片字节存入 MinIO（租户隔离路径）
  3. 返回稳定的 object_path 和 chunk 内联 marker 文本
  4. 顺手记录一条用量日志（降级：失败不影响主流程）

调用方：StructuredWordParser、StructuredPdfParser
"""

import hashlib
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# marker 模板，内嵌于 markdown 文本随切块流动
_MARKER_TEMPLATE = "⟦IMG:{img_id}⟧"


def _img_marker(img_id: str) -> str:
    return _MARKER_TEMPLATE.format(img_id=img_id)


def _detect_ext(image_bytes: bytes) -> str:
    """通过文件头推断图片扩展名，默认 png。"""
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "jpg"
    if image_bytes[:4] == b"\x89PNG":
        return "png"
    if image_bytes[:4] in (b"GIF8", b"GIF9"):
        return "gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "webp"
    return "png"


def _content_type(ext: str) -> str:
    return {
        "jpg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "image/png")


async def process_and_store_image(
    image_bytes: bytes,
    tenant_id: str,
    document_id: str,
    caption: Optional[str] = None,
    page: Optional[int] = None,
) -> dict:
    """
    处理单张图片：VLM 描述 + 存 MinIO + 返回引用信息。

    Returns:
        {
          "img_id":      str,           # 图片唯一 id（内容 hash 前 12 位）
          "object_path": str,           # MinIO 存储路径（稳定，不过期）
          "description": str,           # VLM 描述文本（空则为空串）
          "marker":      str,           # 内联到 markdown 的 marker
          "marker_block":str,           # marker + 描述的完整 markdown 块
          "ext":         str,
          "page":        int | None,
          "stored":      bool,          # 是否成功存入 MinIO
        }
    """
    from app.services.minio_service import minio_service
    from app.services.vlm_service import vlm_service

    # ── 计算唯一 id ──
    img_hash = hashlib.sha1(image_bytes).hexdigest()[:12]
    ext = _detect_ext(image_bytes)
    img_id = img_hash
    object_path = f"{tenant_id}/multimodal/{document_id}/{img_id}.{ext}"

    # ── VLM 描述 ──
    description = ""
    try:
        if vlm_service.is_enabled:
            description = await vlm_service.describe_image(image_bytes)
    except Exception as e:
        logger.warning(f"[图片处理] VLM 描述失败 img_id={img_id}: {e}")

    # ── 存 MinIO ──
    stored = False
    try:
        await minio_service.upload_document_async(
            file_bytes=image_bytes,
            object_name=object_path,
            content_type=_content_type(ext),
            tenant_id=None,  # 路径已含 tenant，_resolve_path 不再重复前缀
        )
        stored = True
        logger.info(f"[图片处理] 已存 MinIO: {object_path}")
    except Exception as e:
        logger.warning(f"[图片处理] MinIO 存储失败 img_id={img_id}: {e}")

    # ── 用量日志（降级：失败不影响主流程）──
    _record_image_usage_fire_and_forget(tenant_id, document_id, img_id, description)

    # ── 构造 marker_block ──
    marker = _img_marker(img_id)
    desc_text = description or (caption or "")
    marker_block = f"\n\n{marker}\n[图片内容说明]:\n{desc_text}\n\n" if desc_text else f"\n\n{marker}\n\n"

    return {
        "img_id": img_id,
        "object_path": object_path,
        "description": description,
        "marker": marker,
        "marker_block": marker_block,
        "ext": ext,
        "page": page,
        "stored": stored,
    }


def _record_image_usage_fire_and_forget(
    tenant_id: str,
    document_id: str,
    img_id: str,
    description: str,
) -> None:
    """异步写用量日志，失败静默。在事件循环中以 task 方式运行。"""
    import asyncio

    async def _write():
        try:
            from app.db.session import AsyncSessionLocal
            from app.models.user_multimodal_config import UserMultiModalUsageLog

            async with AsyncSessionLocal() as db:
                log = UserMultiModalUsageLog(
                    tenant_id=tenant_id,
                    document_id=document_id,
                    content_type="image",
                    parse_mode="ai_enhanced" if description else "basic",
                    model_used=None,
                    total_tokens=0,
                    success=bool(description),
                )
                db.add(log)
                await db.commit()
        except Exception as e:
            logger.debug(f"[图片处理] 用量日志写入失败（已忽略）: {e}")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_write())
    except RuntimeError:
        pass  # 不在异步上下文中，跳过


async def sign_result_images(results: list) -> list:
    """
    对检索结果列表中每个 item 的 images 列表签发预签名 URL。
    失败时静默降级（item.images 保留 object_path，url=None）。
    search endpoint 和 chat endpoint 共用。
    """
    from app.schemas.search import SearchResultImage

    for item in results:
        raw_images = getattr(item, "images", None)
        if not raw_images:
            continue
        signed: list = []
        for img in raw_images:
            # img 可能是 dict（来自 JSONB）或 SearchResultImage 实例
            if isinstance(img, dict):
                obj_path = img.get("object_path", "")
                desc = img.get("description", "")
                page = img.get("page")
            else:
                obj_path = getattr(img, "object_path", "")
                desc = getattr(img, "description", "")
                page = getattr(img, "page", None)
            url = await resolve_image_url(obj_path) if obj_path else None
            signed.append(SearchResultImage(
                object_path=obj_path,
                url=url,
                description=desc,
                page=page,
            ))
        item.images = signed
    return results


async def resolve_image_url(object_path: str, expires: int = 3600) -> Optional[str]:
    """
    将稳定的 object_path 转换为即时预签名 URL（检索响应时调用）。
    失败返回 None，调用方需降级处理（不展示图片而非报错）。
    """
    try:
        from app.services.minio_service import minio_service
        return await minio_service.get_presigned_url_async(
            object_name=object_path,
            expires=expires,
            tenant_id=None,  # 路径已含 tenant
        )
    except Exception as e:
        logger.warning(f"[图片处理] 预签名 URL 生成失败 path={object_path}: {e}")
        return None
