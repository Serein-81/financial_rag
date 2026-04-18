import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document, DocumentVisibility
from app.models.user import User
from app.api import deps
from app.db import AsyncSessionLocal
import hashlib
import io

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
