import { request } from '@/utils/request'

export interface SearchResult {
  chunk_id: string
  document_id: string
  score: number
  content: string
  source_file: string
  page_number: number | null
}

export interface SearchResponse {
  results: SearchResult[]
  total_time: number
}

export interface KeywordSearchRequest {
  keywords: string[]
  kb_id?: string
  top_k?: number
  exact_match?: boolean
}

export interface KeywordSearchResult {
  chunk_id: string
  document_id: string
  content: string
  source_file: string
  match_keywords: string[]
  match_count: number
}

export interface KeywordSearchResponse {
  success: boolean
  results: KeywordSearchResult[]
  total: number
  keywords: string[]
  exact_match: boolean
}

export interface DocumentSearchRequest {
  query: string
  kb_id?: string
  top_k?: number
}

export interface DocumentSearchResult {
  document_id: string
  filename: string
  title: string
  match_score: number
  match_snippets: string[]
  total_chunks: number
  matched_chunks: number
}

export interface DocumentSearchResponse {
  success: boolean
  documents: DocumentSearchResult[]
  total: number
  query: string
}

export interface SearchStatisticsResponse {
  success: boolean
  statistics: {
    keyword: string
    total_occurrences: number
    documents_count: number
    chunks_count: number
    knowledge_bases: Array<{
      kb_id: string
      kb_name: string
      occurrences: number
      documents: number
    }>
    frequency_distribution: {
      high_frequency: number
      medium_frequency: number
      low_frequency: number
    }
  }
}

// 混合搜索请求
export interface HybridSearchRequest {
  query: string
  top_k?: number
  kb_id?: string | null
  enable_web?: boolean
  score_threshold?: number
}

// 同义词混合搜索请求
export interface HybridSynonymSearchRequest {
  query: string
  top_k?: number
  kb_id?: string | null
  enable_synonym?: boolean
  enable_fulltext?: boolean
  vector_weight?: number
  synonym_weight?: number
  fulltext_weight?: number
  score_threshold?: number
}

// Web 搜索结果
export interface WebSearchResult {
  chunk_id: string
  score: number
  content: string
  source_file: string
  title?: string
  source: string
}

// 混合搜索响应
export interface HybridSearchResponse {
  kb_results: SearchResult[]
  web_results: WebSearchResult[]
  total_kb: number
  total_web: number
  search_time: number
  web_available: boolean
}

export const searchApi = {
  // 语义检索
  async semanticSearch(data: {
    query: string
    top_k?: number
    kb_id?: string
  }): Promise<SearchResponse> {
    return request<SearchResponse>('/search/query', {
      method: 'POST',
      data: JSON.stringify(data),
    })
  },

  // 关键词搜索
  async keywordSearch(data: KeywordSearchRequest): Promise<KeywordSearchResponse> {
    return request<KeywordSearchResponse>('/search/keywords', {
      method: 'POST',
      data: JSON.stringify(data),
    })
  },

  // 文档级搜索
  async documentSearch(data: DocumentSearchRequest): Promise<DocumentSearchResponse> {
    const params = new URLSearchParams()
    params.append('query', data.query)
    if (data.kb_id) params.append('kb_id', data.kb_id)
    params.append('top_k', String(data.top_k || 10))

    return request<DocumentSearchResponse>(`/search/documents?${params.toString()}`)
  },

  // 搜索统计
  async getStatistics(keyword: string, kb_id?: string): Promise<SearchStatisticsResponse> {
    const params = new URLSearchParams()
    params.append('keyword', keyword)
    if (kb_id) params.append('kb_id', kb_id)

    return request<SearchStatisticsResponse>(`/search/statistics?${params.toString()}`)
  },

  // 混合搜索（知识库 + Web）
  async hybridSearch(data: HybridSearchRequest): Promise<HybridSearchResponse> {
    return request<HybridSearchResponse>('/search/hybrid', {
      method: 'POST',
      data: JSON.stringify({
        query: data.query,
        top_k: data.top_k ?? 5,
        kb_id: data.kb_id ?? null,
        enable_web: data.enable_web ?? false,
        score_threshold: data.score_threshold ?? 0.3
      }),
    })
  },

  // 混合搜索（知识库 + 同义词扩展）
  async hybridSearchWithSynonym(data: HybridSynonymSearchRequest): Promise<SearchResponse> {
    return request<SearchResponse>('/search/hybrid/synonym', {
      method: 'POST',
      data: JSON.stringify({
        query: data.query,
        top_k: data.top_k ?? 10,
        kb_id: data.kb_id ?? null,
        enable_synonym: data.enable_synonym ?? true,
        enable_fulltext: data.enable_fulltext ?? true,
        vector_weight: data.vector_weight ?? 0.5,
        synonym_weight: data.synonym_weight ?? 0.3,
        fulltext_weight: data.fulltext_weight ?? 0.2,
        score_threshold: data.score_threshold ?? 0.3
      }),
    })
  },
}
