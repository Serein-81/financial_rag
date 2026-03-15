"""
图构建服务
封装记忆 → 实体 → 关系 → Neo4j 的完整流程
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from app.knowledge_graph.entity_extractor import EntityExtractor
from app.knowledge_graph.relation_extractor import RelationExtractor
from app.knowledge_graph.neo4j_manager import Neo4jManager
from app.schemas.knowledge_graph import (
    EntityResponse, RelationResponse, GraphBuildResponse
)

logger = logging.getLogger(__name__)


class GraphBuilder:
    """图构建器"""
    
    def __init__(
        self,
        entity_extractor: EntityExtractor,
        relation_extractor: RelationExtractor,
        neo4j_manager: Neo4jManager
    ):
        self.entity_extractor = entity_extractor
        self.relation_extractor = relation_extractor
        self.neo4j_manager = neo4j_manager
    
    async def build_from_text(
        self,
        text: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        extract_entities: bool = True,
        extract_relations: bool = True
    ) -> GraphBuildResponse:
        """
        从文本构建知识图谱
        
        Args:
            text: 输入文本
            user_id: 用户 ID
            session_id: 会话 ID
            extract_entities: 是否提取实体
            extract_relations: 是否提取关系
        """
        try:
            entities_data = []
            relations_data = []
            
            # 1. 提取实体
            if extract_entities:
                logger.info(f"开始提取实体，文本长度: {len(text)}")
                entities_data = await self.entity_extractor.extract(text)
                logger.info(f"提取到 {len(entities_data)} 个实体")
            
            # 2. 提取关系
            if extract_relations and entities_data:
                logger.info("开始提取关系")
                relations_data = await self.relation_extractor.extract(
                    text, entities_data
                )
                logger.info(f"提取到 {len(relations_data)} 个关系")
            
            # 3. 批量创建实体到 Neo4j
            created_entities = []
            if entities_data:
                created_entities = await self._batch_create_entities(
                    entities_data, user_id, session_id
                )
            
            # 4. 批量创建关系到 Neo4j
            created_relations = []
            if relations_data:
                created_relations = await self._batch_create_relations(
                    relations_data, user_id, session_id
                )
            
            return GraphBuildResponse(
                entities=[EntityResponse(**e) for e in created_entities],
                relations=[RelationResponse(**r) for r in created_relations],
                success=True,
                message=f"成功创建 {len(created_entities)} 个实体和 {len(created_relations)} 个关系"
            )
            
        except Exception as e:
            logger.error(f"图构建失败: {e}", exc_info=True)
            return GraphBuildResponse(
                success=False,
                message=f"图构建失败: {str(e)}"
            )
    
    async def _batch_create_entities(
        self,
        entities: List[Dict[str, Any]],
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """批量创建实体（支持消歧和置信度）"""
        created = []
        for entity in entities:
            try:
                # 添加元数据
                properties = entity.get("properties", {})
                if user_id:
                    properties["user_id"] = user_id
                if session_id:
                    properties["session_id"] = session_id
                
                # 添加置信度和原始名称
                if "confidence" in entity:
                    properties["confidence"] = entity["confidence"]
                if "original_name" in entity:
                    properties["original_name"] = entity["original_name"]
                
                # 生成唯一标识（用于消歧）
                # 如果有消歧后的名称，使用它；否则使用原名称
                entity_name = entity["name"]
                unique_key = f"{entity_name}_{entity['type']}"
                
                # 如果有原始名称，说明进行了消歧
                if "original_name" in entity:
                    unique_key = f"{entity['original_name']}_{entity_name}_{entity['type']}"
                
                # 创建实体
                result = self.neo4j_manager.create_entity(
                    name=entity_name,
                    entity_type=entity["type"],
                    properties=properties,
                    unique_key=unique_key
                )
                
                if result:
                    created.append({
                        "name": entity_name,
                        "type": entity["type"],
                        "properties": properties,
                        "id": result.get("id"),
                        "confidence": entity.get("confidence", 1.0)
                    })
                    
                    confidence_str = f"(置信度: {entity.get('confidence', 1.0):.2f})" if "confidence" in entity else ""
                    logger.debug(f"✅ 创建实体: {entity_name} ({entity['type']}) {confidence_str}")
                    
            except Exception as e:
                logger.warning(f"创建实体失败 {entity.get('name', 'unknown')}: {e}")
                continue
        
        logger.info(f"批量创建实体完成: {len(created)}/{len(entities)}")
        return created
    
    async def _batch_create_relations(
        self,
        relations: List[Dict[str, Any]],
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """批量创建关系"""
        created = []
        for relation in relations:
            try:
                # 添加元数据
                properties = relation.get("properties", {})
                if user_id:
                    properties["user_id"] = user_id
                if session_id:
                    properties["session_id"] = session_id
                
                # 创建关系
                result = self.neo4j_manager.create_relation(
                    source_name=relation["source"],
                    target_name=relation["target"],
                    relation_type=relation["type"],
                    properties=properties
                )
                
                if result:
                    created.append({
                        "source": relation["source"],
                        "target": relation["target"],
                        "type": relation["type"],
                        "properties": properties,
                        "id": result.get("id")
                    })
                    logger.debug(
                        f"✅ 创建关系: {relation['source']} -[{relation['type']}]-> {relation['target']}"
                    )
                    
            except Exception as e:
                logger.warning(
                    f"创建关系失败 {relation['source']}->{relation['target']}: {e}"
                )
                continue
        
        logger.info(f"批量创建关系完成: {len(created)}/{len(relations)}")
        return created
    
    async def build_from_memory(
        self,
        memory_id: int,
        content: str,
        db: Session
    ) -> GraphBuildResponse:
        """
        从记忆构建图谱（集成到 semantic_memory）
        
        Args:
            memory_id: 记忆 ID
            content: 记忆内容
            db: 数据库会话
        """
        # 获取记忆的用户和会话信息
        from app.models.semantic_memory import SemanticMemory
        memory = db.query(SemanticMemory).filter(
            SemanticMemory.id == memory_id
        ).first()
        
        if not memory:
            return GraphBuildResponse(
                success=False,
                message=f"记忆 {memory_id} 不存在"
            )
        
        # 构建图谱
        return await self.build_from_text(
            text=content,
            user_id=memory.user_id,
            session_id=memory.session_id
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取图统计信息"""
        return self.neo4j_manager.get_graph_stats()
