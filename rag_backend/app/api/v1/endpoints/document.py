import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from app.models.document import Document, DocumentVisibility
from app.models.user import User
from app.api import deps
from app.db import AsyncSessionLocal

router = APIRouter()


@router.get("/")
async def list_documents(
    kb_id: Optional[str] = Query(None, description="Knowledge base ID"),
    visibility: Optional[str] = Query(None, description="Filter by visibility (private/public)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(deps.get_current_user)
):
    """
    List documents with tenant isolation
    """
    async with AsyncSessionLocal() as db:
        query = select(Document).where(Document.tenant_id == str(current_user.tenant_id))
        
        if kb_id:
            query = query.where(Document.kb_id == uuid.UUID(kb_id))
        
        if visibility:
            query = query.where(Document.visibility == visibility)
        
        query = query.offset(skip).limit(limit).order_by(Document.created_at.desc())
        
        result = await db.execute(query)
        documents = result.scalars().all()
        
        return {
            "items": [
                {
                    "id": str(doc.id),
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "file_size": doc.file_size,
                    "status": doc.status,
                    "visibility": doc.visibility,
                    "kb_id": str(doc.kb_id) if doc.kb_id else None,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None
                }
                for doc in documents
            ],
            "total": len(documents),
            "skip": skip,
            "limit": limit
        }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get document by ID with tenant isolation
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                Document.id == uuid.UUID(document_id),
                Document.tenant_id == str(current_user.tenant_id)
            )
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "id": str(doc.id),
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_path": doc.file_path,
            "file_size": doc.file_size,
            "status": doc.status,
            "visibility": doc.visibility,
            "kb_id": str(doc.kb_id) if doc.kb_id else None,
            "user_id": str(doc.user_id) if doc.user_id else None,
            "meta_info": doc.meta_info,
            "created_at": doc.created_at.isoformat() if doc.created_at else None
        }


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Delete document by ID with tenant isolation
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(Document).where(
                Document.id == uuid.UUID(document_id),
                Document.tenant_id == str(current_user.tenant_id)
            )
        )
        await db.commit()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"message": "Document deleted successfully"}


@router.patch("/{document_id}/visibility")
async def update_document_visibility(
    document_id: str,
    visibility: str = Query(..., description="Visibility: private or public"),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Update document visibility
    """
    if visibility not in [DocumentVisibility.PRIVATE, DocumentVisibility.PUBLIC]:
        raise HTTPException(status_code=400, detail="Invalid visibility value")
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                Document.id == uuid.UUID(document_id),
                Document.tenant_id == str(current_user.tenant_id)
            )
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc.visibility = visibility
        await db.commit()
        
        return {"message": "Visibility updated successfully", "visibility": visibility}


@router.get("/{document_id}/processing-status")
async def get_document_processing_status(
    document_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    获取文档处理状态（暂停/进度查询）
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                Document.id == uuid.UUID(document_id),
                Document.tenant_id == str(current_user.tenant_id)
            )
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "document_id": str(doc.id),
            "processing_state": doc.processing_state or "unknown",
            "processing_progress": doc.processing_progress or 0,
            "processing_message": doc.processing_message or "",
            "status": doc.status,
            "error_msg": doc.error_msg
        }


@router.post("/{document_id}/pause")
async def pause_document_processing(
    document_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    暂停文档处理（仅在 processing 状态下有效）
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                Document.id == uuid.UUID(document_id),
                Document.tenant_id == str(current_user.tenant_id)
            )
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if doc.processing_state not in [None, "pending", "processing"]:
            return {
                "message": f"无法暂停：当前状态为 {doc.processing_state}",
                "processing_state": doc.processing_state,
                "processing_progress": doc.processing_progress
            }
        
        doc.processing_state = "paused"
        await db.commit()
        
        return {
            "message": "文档处理已暂停",
            "document_id": str(doc.id),
            "processing_state": "paused",
            "processing_progress": doc.processing_progress
        }


@router.post("/{document_id}/resume")
async def resume_document_processing(
    document_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    恢复文档处理（仅在 paused 状态下有效）
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                Document.id == uuid.UUID(document_id),
                Document.tenant_id == str(current_user.tenant_id)
            )
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if doc.processing_state != "paused":
            return {
                "message": f"无法恢复：当前状态为 {doc.processing_state or 'pending'}，只有暂停状态可以恢复",
                "processing_state": doc.processing_state or "pending"
            }
        
        doc.processing_state = "processing"
        await db.commit()
        
        return {
            "message": "文档处理已恢复",
            "document_id": str(doc.id),
            "processing_state": "processing",
            "processing_progress": doc.processing_progress
        }


@router.post("/{document_id}/cancel")
async def cancel_document_processing(
    document_id: str,
    current_user: User = Depends(deps.get_current_user)
):
    """
    取消文档处理（可取消 paused/processing 状态）
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                Document.id == uuid.UUID(document_id),
                Document.tenant_id == str(current_user.tenant_id)
            )
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if doc.processing_state in ["completed", "failed", "cancelled"]:
            return {
                "message": f"无法取消：当前状态为 {doc.processing_state}",
                "processing_state": doc.processing_state
            }
        
        doc.processing_state = "cancelled"
        doc.processing_message = "用户主动取消"
        await db.commit()
        
        return {
            "message": "文档处理已取消",
            "document_id": str(doc.id),
            "processing_state": "cancelled"
        }
