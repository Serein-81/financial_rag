// Knowledge Base API
import { request, requestForm, getToken } from '@/utils/request'
import type { KnowledgeBase, CreateKnowledgeBaseRequest, Document, UploadResponse, DocumentVisibilityType } from '@/types'

export const knowledgeApi = {
  // Get all knowledge bases
  async getKnowledgeBases(): Promise<KnowledgeBase[]> {
    return request<KnowledgeBase[]>('/knowledge/bases')
  },

  // Create knowledge base
  async createKnowledgeBase(data: CreateKnowledgeBaseRequest): Promise<KnowledgeBase> {
    return request<KnowledgeBase>('/knowledge/bases', {
      method: 'POST',
      data: JSON.stringify(data),
    })
  },

  // Delete knowledge base
  async deleteKnowledgeBase(kb_id: string): Promise<void> {
    return request<void>(`/knowledge/bases/${kb_id}`, {
      method: 'DELETE',
    })
  },

  // Get documents in knowledge base
  async getDocuments(kb_id: string): Promise<Document[]> {
    return request<Document[]>(`/knowledge/bases/${kb_id}/documents`)
  },

  // Upload file to knowledge base
  async uploadFile(
    kb_id: string,
    file: File,
    visibility?: DocumentVisibilityType
  ): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    if (visibility) {
      formData.append('visibility', visibility)
    }

    return requestForm<UploadResponse>(
      `/knowledge/bases/${kb_id}/upload`,
      formData
    )
  },

  // Download document
  async downloadDocument(doc_id: string): Promise<Blob> {
    const token = getToken()
    console.log('downloadDocument - Token:', token ? `${token.substring(0, 20)}...` : 'null')
    const response = await fetch(`/api/v1/knowledge/documents/${doc_id}/download`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })
    if (!response.ok) {
      let errorMsg = 'Download failed'
      try {
        const error = await response.json()
        errorMsg = error.detail || errorMsg
      } catch {
        errorMsg = `Download failed (HTTP ${response.status})`
      }
      throw new Error(errorMsg)
    }
    return response.blob()
  },

  // Delete document
  async deleteDocument(doc_id: string): Promise<void> {
    return request<void>(`/knowledge/documents/${doc_id}`, {
      method: 'DELETE',
    })
  },

  // Pause document processing
  async pauseDocument(doc_id: string): Promise<{ message: string; processing_state: string; processing_progress: number }> {
    return request(`/knowledge/documents/${doc_id}/pause`, {
      method: 'POST',
    })
  },

  // Resume document processing
  async resumeDocument(doc_id: string): Promise<{ message: string; processing_state: string; processing_progress: number }> {
    return request(`/knowledge/documents/${doc_id}/resume`, {
      method: 'POST',
    })
  },

  // Cancel document processing
  async cancelDocument(doc_id: string): Promise<{ message: string; processing_state: string }> {
    return request(`/knowledge/documents/${doc_id}/cancel`, {
      method: 'POST',
    })
  },

  // Get document processing status
  async getProcessingStatus(doc_id: string): Promise<{
    document_id: string;
    processing_state: string;
    processing_progress: number;
    processing_message: string;
    status: string;
    error_msg?: string;
  }> {
    return request(`/knowledge/documents/${doc_id}/processing-status`)
  },
}
