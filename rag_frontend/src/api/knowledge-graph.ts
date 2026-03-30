import { request } from '@/utils/request'

export interface KnowledgeGraphEntity {
  name: string
  type: string
  properties: Record<string, any>
}

export interface KnowledgeGraphRelation {
  source: string
  target: string
  type: string
  properties: Record<string, any>
}

export interface BuildKnowledgeGraphRequest {
  text: string
  user_id?: string
  session_id?: string
  extract_entities?: boolean
  extract_relations?: boolean
}

export interface BuildKnowledgeGraphResponse {
  success: boolean
  entities_count: number
  relations_count: number
  processing_time: number
  entities: KnowledgeGraphEntity[]
  relations: KnowledgeGraphRelation[]
}

export interface KnowledgeGraphSearchRequest {
  query: string
  user_id?: string
  session_id?: string
  top_k?: number
  vector_weight?: number
  graph_weight?: number
  use_graph?: boolean
}

export interface KnowledgeGraphSearchResult {
  content: string
  score: number
  source: 'vector' | 'graph'
  metadata: Record<string, any>
}

export interface KnowledgeGraphSearchResponse {
  success: boolean
  results: KnowledgeGraphSearchResult[]
  vector_results_count: number
  graph_results_count: number
  total_count: number
}

export interface QueryEntityRequest {
  entity_name: string
  max_depth?: number
  limit?: number
}

export interface QueryEntityResponse {
  success: boolean
  entity: KnowledgeGraphEntity
  relations: Array<{
    relation: string
    target: KnowledgeGraphEntity
    properties: Record<string, any>
  }>
}

export const knowledgeGraphApi = {
  // 构建知识图谱
  async build(data: BuildKnowledgeGraphRequest): Promise<BuildKnowledgeGraphResponse> {
    return request<BuildKnowledgeGraphResponse>('/knowledge_graph/build', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  // 混合检索
  async search(data: KnowledgeGraphSearchRequest): Promise<KnowledgeGraphSearchResponse> {
    return request<KnowledgeGraphSearchResponse>('/knowledge_graph/search', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  // 查询实体
  async queryEntity(data: QueryEntityRequest): Promise<QueryEntityResponse> {
    return request<QueryEntityResponse>('/knowledge_graph/query-entity', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },
}
