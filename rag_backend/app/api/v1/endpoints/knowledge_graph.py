"""
知识图谱 API 端点
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.knowledge_graph import (
    GraphBuildRequest, GraphBuildResponse,
    EntityQueryRequest, EntityQueryResponse, RelatedEntity, EntityResponse,
    HybridSearchRequest, HybridSearchResponse,
    GraphStatsResponse, GraphVisualizationResponse, GraphNode, GraphEdge,
    EntityListResponse, EntityTypesResponse
)
from app.services.graph_builder import GraphBuilder
from app.services.hybrid_retriever import HybridRetriever
from app.knowledge_graph.entity_extractor import EntityExtractor
from app.knowledge_graph.relation_extractor import RelationExtractor
from app.knowledge_graph.neo4j_manager import Neo4jManager
from app.agent_framework.llm.factory import LLMAdapterFactory
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# 依赖注入
def get_graph_builder() -> GraphBuilder:
    """获取图构建器"""
    entity_extractor = EntityExtractor()
    relation_extractor = RelationExtractor()
    neo4j_manager = Neo4jManager(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
    return GraphBuilder(entity_extractor, relation_extractor, neo4j_manager)


def get_hybrid_retriever() -> HybridRetriever:
    """获取混合检索器"""
    neo4j_manager = Neo4jManager(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
    return HybridRetriever(neo4j_manager)


def get_neo4j_manager() -> Neo4jManager:
    """获取 Neo4j 管理器"""
    return Neo4jManager(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )


@router.post("/build", response_model=GraphBuildResponse)
async def build_graph(
    request: GraphBuildRequest,
    current_user: User = Depends(get_current_user),
    graph_builder: GraphBuilder = Depends(get_graph_builder)
):
    """
    从文本构建知识图谱
    """
    try:
        result = await graph_builder.build_from_text(
            text=request.text,
            user_id=request.user_id or current_user.id,
            session_id=request.session_id,
            tenant_id=str(current_user.tenant_id),
            extract_entities=request.extract_entities,
            extract_relations=request.extract_relations
        )
        return result
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"构建图谱失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"构建图谱失败: {str(e)}")


@router.post("/search", response_model=HybridSearchResponse)
async def hybrid_search(
    request: HybridSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    retriever: HybridRetriever = Depends(get_hybrid_retriever)
):
    """
    混合检索（向量 + 图）
    """
    try:
        results, stats = await retriever.retrieve(
            query=request.query,
            db=db,
            user_id=request.user_id or current_user.id,
            session_id=request.session_id,
            top_k=request.top_k,
            vector_weight=request.vector_weight,
            graph_weight=request.graph_weight,
            use_graph=request.use_graph
        )
        
        return HybridSearchResponse(
            results=results,
            vector_results_count=stats.get("vector", 0),
            graph_results_count=stats.get("graph", 0),
            total_count=stats.get("total", 0)
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"混合检索失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"混合检索失败: {str(e)}")


@router.post("/query-entity", response_model=EntityQueryResponse)
async def query_entity(
    request: EntityQueryRequest,
    current_user: User = Depends(get_current_user),
    retriever: HybridRetriever = Depends(get_hybrid_retriever),
    neo4j_manager: Neo4jManager = Depends(get_neo4j_manager)
):
    """
    查询实体及其相关实体
    """
    try:
        # 查找相关实体
        related = await retriever.retrieve_by_entity(
            entity_name=request.entity_name,
            max_depth=request.max_depth,
            limit=request.limit
        )
        
        # 获取中心实体信息
        center_entity = None
        for entity in related:
            if entity["name"] == request.entity_name:
                center_entity = EntityResponse(
                    name=entity["name"],
                    type=entity["type"],
                    properties=entity.get("properties", {})
                )
                break
        
        if not center_entity:
            raise HTTPException(status_code=404, detail=f"实体 '{request.entity_name}' 不存在")
        
        # 构建相关实体列表
        related_entities = [
            RelatedEntity(
                name=e["name"],
                type=e["type"],
                distance=e.get("distance", 0)
            )
            for e in related
            if e["name"] != request.entity_name
        ]
        
        return EntityQueryResponse(
            entity=center_entity,
            related_entities=related_entities,
            total_count=len(related_entities)
        )
    except HTTPException:
        raise
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"查询实体失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询实体失败: {str(e)}")


@router.get("/stats", response_model=GraphStatsResponse)
async def get_graph_stats(
    current_user: User = Depends(get_current_user),
    graph_builder: GraphBuilder = Depends(get_graph_builder)
):
    """
    获取图统计信息
    """
    try:
        stats = graph_builder.get_stats()
        return GraphStatsResponse(**stats)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取图统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取图统计失败: {str(e)}")


@router.get("/visualize", response_model=GraphVisualizationResponse)
async def visualize_graph(
    entity_name: Optional[str] = Query(None, description="中心实体名称"),
    max_depth: int = Query(2, ge=1, le=3, description="最大深度"),
    limit: int = Query(50, ge=1, le=200, description="节点数量限制"),
    current_user: User = Depends(get_current_user),
    neo4j_manager: Neo4jManager = Depends(get_neo4j_manager)
):
    """
    获取图可视化数据
    """
    try:
        tenant_id = str(current_user.tenant_id)
        
        # 如果指定了实体，查询其周围的子图
        if entity_name:
            subgraph = neo4j_manager.get_subgraph(
                entity_name=entity_name,
                tenant_id=tenant_id,
                max_depth=max_depth,
                limit=limit
            )
        else:
            # 否则返回整个图的采样
            subgraph = neo4j_manager.get_graph_sample(limit=limit, tenant_id=tenant_id)
        
        # 转换为可视化格式
        nodes = [
            GraphNode(
                id=node["id"],
                label=node["name"],
                type=node["type"],
                properties=node.get("properties", {})
            )
            for node in subgraph.get("nodes", [])
        ]
        
        edges = [
            GraphEdge(
                id=edge["id"],
                source=edge["source"],
                target=edge["target"],
                type=edge["type"],
                properties=edge.get("properties", {})
            )
            for edge in subgraph.get("edges", [])
        ]
        
        return GraphVisualizationResponse(
            nodes=nodes,
            edges=edges,
            center_node=entity_name
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取可视化数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取可视化数据失败: {str(e)}")


@router.get("/entities", response_model=EntityListResponse)
async def list_entities(
    limit: int = Query(200, ge=1, le=500, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    entity_type: Optional[str] = Query(None, description="按类型筛选"),
    current_user: User = Depends(get_current_user),
    neo4j_manager: Neo4jManager = Depends(get_neo4j_manager)
):
    """
    获取当前租户的所有实体列表
    """
    try:
        tenant_id = str(current_user.tenant_id)
        
        result = neo4j_manager.get_all_entities(
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
            entity_type=entity_type
        )
        
        return EntityListResponse(**result)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取实体列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取实体列表失败: {str(e)}")


@router.get("/entity-types", response_model=EntityTypesResponse)
async def list_entity_types(
    current_user: User = Depends(get_current_user),
    neo4j_manager: Neo4jManager = Depends(get_neo4j_manager)
):
    """
    获取当前租户的所有实体类型
    """
    try:
        tenant_id = str(current_user.tenant_id)
        types = neo4j_manager.get_entity_types(tenant_id=tenant_id)
        
        return EntityTypesResponse(types=types)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"数据错误: {str(e)}")
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"IO错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取实体类型失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取实体类型失败: {str(e)}")
