"""
知识图谱相关的 Pydantic 模型
用于 API 请求/响应的数据验证
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


# ============ 实体相关 ============
class EntityBase(BaseModel):
    """实体基础模型"""
    name: str = Field(..., description="实体名称")
    type: str = Field(..., description="实体类型: PERSON, LOCATION, ORGANIZATION, CONCEPT")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="实体属性")


class EntityCreate(EntityBase):
    """创建实体请求"""
    pass


class EntityResponse(EntityBase):
    """实体响应"""
    id: Optional[str] = Field(None, description="Neo4j 节点 ID")
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(
        from_attributes=True
    )


# ============ 关系相关 ============
class RelationBase(BaseModel):
    """关系基础模型"""
    source: str = Field(..., description="源实体名称")
    target: str = Field(..., description="目标实体名称")
    type: str = Field(..., description="关系类型")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="关系属性")


class RelationCreate(RelationBase):
    """创建关系请求"""
    pass


class RelationResponse(RelationBase):
    """关系响应"""
    id: Optional[str] = Field(None, description="Neo4j 关系 ID")
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(
        from_attributes=True
    )


# ============ 图构建相关 ============
class EntityUpdate(BaseModel):
    """Update an existing entity by graph node id."""
    name: str = Field(..., min_length=1, description="实体名称")
    type: str = Field(..., min_length=1, description="实体类型")
    properties: Dict[str, Any] = Field(default_factory=dict, description="实体属性")


class RelationUpdate(BaseModel):
    """Update an existing relation by graph relationship id."""
    source: Optional[str] = Field(None, description="源实体名称")
    target: Optional[str] = Field(None, description="目标实体名称")
    type: str = Field(..., min_length=1, description="关系类型")
    properties: Dict[str, Any] = Field(default_factory=dict, description="关系属性")


class GraphBuildRequest(BaseModel):
    """图构建请求"""
    text: str = Field(..., description="待处理文本")
    user_id: Optional[int] = Field(None, description="用户 ID")
    session_id: Optional[str] = Field(None, description="会话 ID")
    extract_entities: bool = Field(True, description="是否提取实体")
    extract_relations: bool = Field(True, description="是否提取关系")


class GraphBuildResponse(BaseModel):
    """图构建响应"""
    entities: List[EntityResponse] = Field(default_factory=list)
    relations: List[RelationResponse] = Field(default_factory=list)
    success: bool = True
    message: Optional[str] = None


# ============ 图查询相关 ============
class EntityQueryRequest(BaseModel):
    """实体查询请求"""
    entity_name: str = Field(..., description="实体名称")
    max_depth: int = Field(2, ge=1, le=5, description="最大查询深度")
    limit: int = Field(10, ge=1, le=100, description="返回结果数量限制")


class RelatedEntity(BaseModel):
    """相关实体"""
    name: str
    type: str
    distance: int = Field(..., description="距离（跳数）")
    relation_path: Optional[List[str]] = Field(None, description="关系路径")


class EntityQueryResponse(BaseModel):
    """实体查询响应"""
    entity: EntityResponse
    related_entities: List[RelatedEntity] = Field(default_factory=list)
    total_count: int = 0


# ============ 混合检索相关 ============
class HybridSearchRequest(BaseModel):
    """混合检索请求"""
    query: str = Field(..., description="查询文本")
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    top_k: int = Field(5, ge=1, le=20, description="返回结果数量")
    vector_weight: float = Field(0.7, ge=0, le=1, description="向量检索权重")
    graph_weight: float = Field(0.3, ge=0, le=1, description="图检索权重")
    use_graph: bool = Field(True, description="是否使用图检索")


class SearchResult(BaseModel):
    """检索结果"""
    content: str
    score: float
    source: str = Field(..., description="来源: vector, graph, hybrid")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class HybridSearchResponse(BaseModel):
    """混合检索响应"""
    results: List[SearchResult] = Field(default_factory=list)
    vector_results_count: int = 0
    graph_results_count: int = 0
    total_count: int = 0


# ============ 图统计相关 ============
class GraphStatsResponse(BaseModel):
    """图统计响应"""
    total_entities: int = 0
    total_relations: int = 0
    entity_types: Dict[str, int] = Field(default_factory=dict)
    relation_types: Dict[str, int] = Field(default_factory=dict)


# ============ 图可视化相关 ============
class GraphNode(BaseModel):
    """图节点（用于可视化）"""
    id: str
    label: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """图边（用于可视化）"""
    id: str
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = Field(None, description="关系语义描述")


class GraphVisualizationResponse(BaseModel):
    """图可视化响应"""
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    center_node: Optional[str] = None


class GraphImportRequest(BaseModel):
    """Persist an edited graph snapshot without removing unrelated graph data."""
    nodes: List[GraphNode] = Field(default_factory=list, description="要保存的节点")
    edges: List[GraphEdge] = Field(default_factory=list, description="要保存的关系")
    deleted_node_ids: List[str] = Field(default_factory=list, description="要删除的节点 ID")
    deleted_edge_ids: List[str] = Field(default_factory=list, description="要删除的关系 ID")


class GraphImportResponse(BaseModel):
    """Graph editor save/import result."""
    success: bool = True
    nodes_saved: int = 0
    edges_saved: int = 0
    nodes_deleted: int = 0
    edges_deleted: int = 0
    errors: List[str] = Field(default_factory=list)


class EntityListItem(BaseModel):
    """实体列表项"""
    id: str = Field(..., description="Neo4j 节点 ID")
    name: str = Field(..., description="实体名称")
    type: str = Field(..., description="实体类型")
    properties: Dict[str, Any] = Field(default_factory=dict, description="实体属性")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class EntityListResponse(BaseModel):
    """实体列表响应"""
    entities: List[EntityListItem] = Field(default_factory=list)
    total: int = Field(0, description="总数")
    limit: int = Field(200, description="每页数量")
    offset: int = Field(0, description="偏移量")


class EntityTypesResponse(BaseModel):
    """实体类型列表响应"""
    types: List[str] = Field(default_factory=list)


# ============ 路径查询相关 ============
class PathRequest(BaseModel):
    """路径查询请求"""
    source: str = Field(..., min_length=1, description="源实体名称")
    target: str = Field(..., min_length=1, description="目标实体名称")
    max_depth: int = Field(4, ge=1, le=6, description="最大路径深度")


class PathEntity(BaseModel):
    """路径中的实体"""
    name: str
    type: str


class PathResult(BaseModel):
    """路径查询结果（一条路径）"""
    entities: List[PathEntity] = Field(..., description="路径上的实体列表（有序）")
    relations: List[str] = Field(..., description="路径上的关系类型列表（有序）")
    hops: int = Field(..., description="跳数")


class PathResponse(BaseModel):
    """路径查询响应"""
    source: str
    target: str
    paths: List[PathResult] = Field(default_factory=list)
    total_paths: int = 0
