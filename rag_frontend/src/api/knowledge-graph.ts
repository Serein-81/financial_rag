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
  message?: string
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

export interface GraphVisualizationNode {
  id: string
  label: string
  type: string
  properties: Record<string, any>
}

export interface GraphVisualizationEdge {
  id: string
  source: string
  target: string
  type: string
  properties: Record<string, any>
  description?: string
}

export interface GraphVisualizationResponse {
  nodes: GraphVisualizationNode[]
  edges: GraphVisualizationEdge[]
  center_node: string | null
}

export interface GraphImportRequest {
  nodes: GraphVisualizationNode[]
  edges: GraphVisualizationEdge[]
  deleted_node_ids?: string[]
  deleted_edge_ids?: string[]
}

export interface GraphImportResponse {
  success: boolean
  nodes_saved: number
  edges_saved: number
  nodes_deleted: number
  edges_deleted: number
  errors: string[]
}

export interface VisualizeRequest {
  entity_name?: string
  max_depth?: number
  limit?: number
}

export interface EntityListItem {
  id: string
  name: string
  type: string
  properties: Record<string, any>
  created_at: string | null
  updated_at: string | null
}

export interface EntityListResponse {
  entities: EntityListItem[]
  total: number
  limit: number
  offset: number
}

export interface EntityTypesResponse {
  types: string[]
}

export const knowledgeGraphApi = {
  // 构建知识图谱（增加超时到5分钟，因为LLM提取需要时间）
  async build(data: BuildKnowledgeGraphRequest): Promise<BuildKnowledgeGraphResponse> {
    return request<BuildKnowledgeGraphResponse>('/knowledge_graph/build', {
      method: 'POST',
      data: JSON.stringify(data),
      timeout: 300000,
    })
  },

  // 混合检索
  async search(data: KnowledgeGraphSearchRequest): Promise<KnowledgeGraphSearchResponse> {
    return request<KnowledgeGraphSearchResponse>('/knowledge_graph/search', {
      method: 'POST',
      data: JSON.stringify(data),
    })
  },

  // 查询实体
  async queryEntity(data: QueryEntityRequest): Promise<QueryEntityResponse> {
    return request<QueryEntityResponse>('/knowledge_graph/query-entity', {
      method: 'POST',
      data: JSON.stringify(data),
    })
  },

  // 可视化图谱
  async visualize(data: VisualizeRequest): Promise<GraphVisualizationResponse> {
    const params = new URLSearchParams()
    if (data.entity_name) params.append('entity_name', data.entity_name)
    if (data.max_depth !== undefined) params.append('max_depth', String(data.max_depth))
    if (data.limit !== undefined) params.append('limit', String(data.limit))
    
    return request<GraphVisualizationResponse>(`/knowledge_graph/visualize?${params.toString()}`, {
      method: 'GET',
    })
  },

  // 获取实体列表
  async importGraph(data: GraphImportRequest): Promise<GraphImportResponse> {
    return request<GraphImportResponse>('/knowledge_graph/import', {
      method: 'POST',
      data: JSON.stringify(data),
    })
  },

  async listEntities(params?: {
    limit?: number
    offset?: number
    entity_type?: string
  }): Promise<EntityListResponse> {
    const queryParams = new URLSearchParams()
    if (params?.limit !== undefined) queryParams.append('limit', String(params.limit))
    if (params?.offset !== undefined) queryParams.append('offset', String(params.offset))
    if (params?.entity_type) queryParams.append('entity_type', params.entity_type)
    
    return request<EntityListResponse>(`/knowledge_graph/entities?${queryParams.toString()}`, {
      method: 'GET',
    })
  },

  // 获取实体类型列表
  async listEntityTypes(): Promise<EntityTypesResponse> {
    return request<EntityTypesResponse>('/knowledge_graph/entity-types', {
      method: 'GET',
    })
  },
}
