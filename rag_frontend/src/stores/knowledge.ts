// Knowledge Base Store
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { knowledgeApi } from '@/api/knowledge'
import type { KnowledgeBase, Document, VisibilityType, DocumentVisibilityType } from '@/types'

export const useKnowledgeStore = defineStore('knowledge', () => {
  const knowledgeBases = ref<KnowledgeBase[]>([])
  const selectedKnowledgeBaseId = ref<string | null>(null)
  const documents = ref<Record<string, Document[]>>({})
  const isLoading = ref(false)

  const selectedKnowledgeBase = computed(() =>
    knowledgeBases.value.find(kb => kb.id === selectedKnowledgeBaseId.value)
  )

  async function fetchKnowledgeBases() {
    try {
      isLoading.value = true
      knowledgeBases.value = await knowledgeApi.getKnowledgeBases()

      // Auto-select first knowledge base if none selected
      if (!selectedKnowledgeBaseId.value && knowledgeBases.value.length > 0) {
        selectedKnowledgeBaseId.value = knowledgeBases.value[0].id
      }
    } catch (error) {
      console.error('Failed to fetch knowledge bases:', error)
    } finally {
      isLoading.value = false
    }
  }

  async function createKnowledgeBase(
    name: string,
    description?: string,
    visibility: VisibilityType = 'private'
  ) {
    try {
      const newKB = await knowledgeApi.createKnowledgeBase({
        name,
        description,
        visibility
      })
      knowledgeBases.value.push(newKB)
      return newKB
    } catch (error) {
      console.error('Failed to create knowledge base:', error)
      throw error
    }
  }

  async function deleteKnowledgeBase(kb_id: string) {
    try {
      await knowledgeApi.deleteKnowledgeBase(kb_id)
      knowledgeBases.value = knowledgeBases.value.filter(kb => kb.id !== kb_id)

      if (selectedKnowledgeBaseId.value === kb_id) {
        selectedKnowledgeBaseId.value = knowledgeBases.value[0]?.id || null
      }
    } catch (error) {
      console.error('Failed to delete knowledge base:', error)
      throw error
    }
  }

  async function fetchDocuments(kb_id: string) {
    try {
      isLoading.value = true
      documents.value[kb_id] = await knowledgeApi.getDocuments(kb_id)
    } catch (error) {
      console.error('Failed to fetch documents:', error)
    } finally {
      isLoading.value = false
    }
  }

  async function uploadFile(
    kb_id: string,
    file: File,
    visibility?: DocumentVisibilityType
  ) {
    try {
      const result = await knowledgeApi.uploadFile(kb_id, file, visibility)
      // Refresh documents after upload
      await fetchDocuments(kb_id)
      return result
    } catch (error) {
      console.error('Failed to upload file:', error)
      throw error
    }
  }

  function selectKnowledgeBase(kb_id: string | null) {
    selectedKnowledgeBaseId.value = kb_id
  }

  return {
    knowledgeBases,
    selectedKnowledgeBaseId,
    selectedKnowledgeBase,
    documents,
    isLoading,
    fetchKnowledgeBases,
    createKnowledgeBase,
    deleteKnowledgeBase,
    fetchDocuments,
    uploadFile,
    selectKnowledgeBase,
  }
})
