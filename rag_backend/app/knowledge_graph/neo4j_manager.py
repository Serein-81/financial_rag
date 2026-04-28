"""Neo4j 图数据库管理器"""
import json
import logging
from typing import List, Dict, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from neo4j import GraphDatabase, Driver, Query

try:
    from neo4j import GraphDatabase, Driver, Query
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None
    Driver = None
    Query = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class Neo4jManager:
    """Neo4j 连接和操作管理"""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.driver: Optional[Driver] = None
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD

        if settings.ENABLE_KNOWLEDGE_GRAPH:
            self._connect()

    def _serialize_value(self, value: Any) -> Any:
        """将 Neo4j 类型序列化为 JSON 兼容的类型"""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        return str(value)

    def _connect(self):
        """建立连接"""
        if not NEO4J_AVAILABLE:
            logger.warning("Neo4j package is not installed; skipping connection")
            self.driver = None
            return
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # 测试连接
            self.driver.verify_connectivity()
            logger.debug("Neo4j connected: %s", self.uri)
        except Exception as e:
            logger.error("Neo4j connection failed: %s", e)
            self.driver = None

    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()

    def create_memory_node(self, memory_id: str, content: str,
                          user_id: str, tenant_id: str, metadata: Dict) -> bool:
        """创建记忆节点（增加租户隔离）"""
        if not self.driver:
            return False

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MERGE (m:Memory {id: $id})
                SET m.content = $content,
                    m.user_id = $user_id,
                    m.tenant_id = $tenant_id,
                    m.importance = $importance,
                    m.created_at = datetime()
                RETURN m
            """, id=memory_id, content=content, user_id=user_id,
                tenant_id=tenant_id, importance=metadata.get('importance', 0.5))
            return result.single() is not None

    def create_entity(self, name: str, entity_type: str, tenant_id: str,
                     properties: Dict = None, unique_key: str = None) -> Optional[str]:
        """
        创建实体节点（支持消歧与严格多租户隔离）
        """
        if not self.driver:
            return None

        tenant_id = str(tenant_id) if tenant_id else None

        if not unique_key:
            unique_key = f"{tenant_id}_{name}_{entity_type}"

        properties_json = json.dumps(properties) if properties else None

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            if properties_json:
                result = session.run("""
                    MERGE (e:Entity {unique_key: $unique_key})
                    SET e.name = $name,
                        e.type = $type,
                        e.tenant_id = $tenant_id,
                        e.properties = $properties,
                        e.updated_at = datetime()
                    RETURN e.unique_key as id
                """, unique_key=unique_key, name=name, type=entity_type, tenant_id=tenant_id, properties=properties_json)
            else:
                result = session.run("""
                    MERGE (e:Entity {unique_key: $unique_key})
                    SET e.name = $name,
                        e.type = $type,
                        e.tenant_id = $tenant_id,
                        e.updated_at = datetime()
                    RETURN e.unique_key as id
                """, unique_key=unique_key, name=name, type=entity_type, tenant_id=tenant_id)

            record = result.single()
            return record['id'] if record else None

    def create_relation(self, source_name: str, target_name: str,
                       relation_type: str, tenant_id: str, properties: Dict = None) -> Optional[Dict]:
        """创建实体关系（基于租户隔离）"""
        if not self.driver:
            return None

        tenant_id = str(tenant_id) if tenant_id else None

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            weight = properties.get("weight", 1.0) if properties else 1.0
            editor_id = properties.get("editor_id") if properties else None

            result = session.run("""
                MATCH (s:Entity)
                MATCH (t:Entity)
                WHERE (s.name = $source) AND (t.name = $target)
                  AND (s.tenant_id IS NULL OR s.tenant_id = $tenant_id)
                  AND (t.tenant_id IS NULL OR t.tenant_id = $tenant_id)
                MERGE (s)-[r:RELATED {type: $rel_type}]->(t)
                SET r.weight = $weight,
                    r.editor_id = coalesce(r.editor_id, $editor_id),
                    r.updated_at = datetime()
                RETURN id(r) as id
            """, source=source_name, target=target_name,
                rel_type=relation_type, tenant_id=tenant_id, weight=weight, editor_id=editor_id)

            record = result.single()
            return {"id": str(record["id"])} if record else None

    def update_entity_by_id(self, entity_id: str, name: str, entity_type: str,
                            tenant_id: str, properties: Dict = None) -> Optional[Dict]:
        """Update an existing entity by Neo4j internal id."""
        if not self.driver:
            return None

        try:
            graph_id = int(entity_id)
        except (TypeError, ValueError):
            return None

        tenant_id = str(tenant_id) if tenant_id else None
        properties_json = json.dumps(properties or {})

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (e:Entity)
                WHERE id(e) = $entity_id AND (e.tenant_id IS NULL OR e.tenant_id = $tenant_id)
                SET e.name = $name,
                    e.type = $type,
                    e.tenant_id = coalesce(e.tenant_id, $tenant_id),
                    e.properties = $properties,
                    e.unique_key = coalesce(e.unique_key, $unique_key),
                    e.updated_at = datetime()
                RETURN id(e) as id, e.name as name, e.type as type, e.properties as properties
            """, entity_id=graph_id, name=name, type=entity_type, tenant_id=tenant_id,
                unique_key=f"{tenant_id}_{name}_{entity_type}", properties=properties_json)

            record = result.single()
            if not record:
                return None
            properties_value = record["properties"] or {}
            if isinstance(properties_value, str):
                properties_value = json.loads(properties_value)
            return {
                "id": str(record["id"]),
                "name": record["name"],
                "type": record["type"],
                "properties": self._serialize_value(properties_value)
            }

    def delete_entity_by_id(self, entity_id: str, tenant_id: str) -> bool:
        """Delete an entity and its relationships by Neo4j internal id."""
        if not self.driver:
            return False

        tenant_id = str(tenant_id) if tenant_id else None
        try:
            graph_id = int(entity_id)
        except (TypeError, ValueError):
            graph_id = None

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (e:Entity)
                WHERE (id(e) = $graph_id OR e.unique_key IN $unique_keys)
                  AND (e.tenant_id IS NULL OR e.tenant_id = $tenant_id)
                WITH e, count(e) as deleted
                DETACH DELETE e
                RETURN deleted
            """, graph_id=graph_id, unique_keys=[entity_id, f"{tenant_id}_{entity_id}"], tenant_id=tenant_id)
            record = result.single()
            return bool(record and record["deleted"] > 0)

    def delete_relation_by_id(self, relation_id: str, tenant_id: str) -> bool:
        """Delete a relation by Neo4j internal id."""
        if not self.driver:
            return False

        tenant_id = str(tenant_id) if tenant_id else None
        try:
            graph_id = int(relation_id)
        except (TypeError, ValueError):
            graph_id = None

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (s:Entity)-[r:RELATED]->(t:Entity)
                WHERE (id(r) = $graph_id OR r.editor_id = $relation_id)
                  AND (s.tenant_id IS NULL OR s.tenant_id = $tenant_id)
                  AND (t.tenant_id IS NULL OR t.tenant_id = $tenant_id)
                WITH r, count(r) as deleted
                DELETE r
                RETURN deleted
            """, graph_id=graph_id, relation_id=relation_id, tenant_id=tenant_id)
            record = result.single()
            return bool(record and record["deleted"] > 0)

    def save_graph_snapshot(self, nodes: List[Dict], edges: List[Dict], tenant_id: str,
                            deleted_node_ids: List[str] = None,
                            deleted_edge_ids: List[str] = None) -> Dict[str, Any]:
        """Persist editor changes while leaving unrelated graph data untouched."""
        result = {
            "success": bool(self.driver),
            "nodes_saved": 0,
            "edges_saved": 0,
            "nodes_deleted": 0,
            "edges_deleted": 0,
            "errors": []
        }
        if not self.driver:
            result["errors"].append("Neo4j is not available")
            return result

        tenant_id = str(tenant_id) if tenant_id else None

        for relation_id in deleted_edge_ids or []:
            if self.delete_relation_by_id(relation_id, tenant_id):
                result["edges_deleted"] += 1

        for entity_id in deleted_node_ids or []:
            if self.delete_entity_by_id(entity_id, tenant_id):
                result["nodes_deleted"] += 1

        node_name_by_id = {}
        for node in nodes:
            node_id = str(node.get("id", ""))
            name = (node.get("label") or node.get("name") or "").strip()
            entity_type = (node.get("type") or "Entity").strip()
            properties = node.get("properties") or {}
            if not name:
                result["errors"].append(f"Skipped node with empty name: {node_id}")
                continue

            saved = None
            if node_id.isdigit():
                saved = self.update_entity_by_id(node_id, name, entity_type, tenant_id, properties)
            if not saved:
                created_id = self.create_entity(
                    name=name,
                    entity_type=entity_type,
                    tenant_id=tenant_id,
                    properties=properties,
                    unique_key=f"{tenant_id}_{node_id}" if node_id else None
                )
                saved = {"id": created_id, "name": name, "type": entity_type} if created_id else None

            if saved:
                result["nodes_saved"] += 1
                node_name_by_id[node_id] = name
            else:
                result["errors"].append(f"Failed to save node: {name}")

        for edge in edges:
            source_ref = str(edge.get("source", ""))
            target_ref = str(edge.get("target", ""))
            source_name = node_name_by_id.get(source_ref, source_ref)
            target_name = node_name_by_id.get(target_ref, target_ref)
            relation_type = (edge.get("type") or "related_to").strip()

            if not source_name or not target_name:
                result["errors"].append(f"Skipped edge with empty endpoint: {edge.get('id')}")
                continue

            saved = self.create_relation(
                source_name=source_name,
                target_name=target_name,
                relation_type=relation_type,
                tenant_id=tenant_id,
                properties={**(edge.get("properties") or {}), "editor_id": edge.get("id")}
            )
            if saved:
                result["edges_saved"] += 1
            else:
                result["errors"].append(f"Failed to save edge: {source_name} -> {target_name}")

        result["success"] = len(result["errors"]) == 0
        return result

    def link_memory_to_entities(self, memory_id: str,
                               entity_names: List[str], tenant_id: str) -> int:
        """关联记忆和实体（支持 tenant_id 为 null 的数据）"""
        if not self.driver:
            return 0

        tenant_id = str(tenant_id) if tenant_id else None
        count = 0
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            for entity_name in entity_names:
                result = session.run("""
                    MATCH (m:Memory {id: $memory_id, tenant_id: $tenant_id})
                    MATCH (e:Entity)
                    WHERE (e.name = $entity_name) AND (e.tenant_id IS NULL OR e.tenant_id = $tenant_id)
                    MERGE (m)-[r:CONTAINS]->(e)
                    RETURN r
                """, memory_id=memory_id, entity_name=entity_name, tenant_id=tenant_id)
                if result.single():
                    count += 1
        return count

    def find_related_entities(self, entity_name: str, tenant_id: str,
                            max_depth: int = 2, limit: int = 20) -> List[Dict]:
        """查找相关实体（支持 tenant_id 为 null 的数据）"""
        if not self.driver:
            return []

        tenant_id = str(tenant_id) if tenant_id else None

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            query = Query("""
                MATCH path = (e:Entity)-[*0..%d]-(related:Entity)
                WHERE (e.name = $name) AND (e.tenant_id IS NULL OR e.tenant_id = $tenant_id)
                  AND (related.tenant_id IS NULL OR related.tenant_id = $tenant_id)
                RETURN DISTINCT related.name as name, 
                       related.type as type,
                       related.properties as properties,
                       length(path) as distance
                ORDER BY distance
                LIMIT $limit
            """ % max_depth)

            result = session.run(query, name=entity_name, tenant_id=tenant_id, limit=limit)
            entities = []
            for record in result:
                entity = dict(record)
                entity["properties"] = entity.get("properties") or {}
                entities.append(entity)
            return entities

    def find_memories_by_entity(self, entity_name: str, tenant_id: str) -> List[str]:
        """通过实体查找记忆"""
        if not self.driver:
            return []

        tenant_id = str(tenant_id) if tenant_id else None

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (m:Memory {tenant_id: $tenant_id})-[:CONTAINS]->(e:Entity)
                WHERE (e.name = $name) AND (e.tenant_id IS NULL OR e.tenant_id = $tenant_id)
                RETURN m.id as memory_id
                ORDER BY m.created_at DESC
                LIMIT 10
            """, name=entity_name, tenant_id=tenant_id)

            return [record['memory_id'] for record in result]

    def get_graph_stats(self, tenant_id: str) -> Dict[str, int]:
        """获取指定租户的图统计信息"""
        if not self.driver:
            return {}

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (m:Memory {tenant_id: $tenant_id}) WITH count(m) as memories
                MATCH (e:Entity {tenant_id: $tenant_id}) WITH memories, count(e) as entities
                MATCH (:Entity {tenant_id: $tenant_id})-[r:RELATED]->(:Entity {tenant_id: $tenant_id}) 
                WITH memories, entities, count(r) as relations
                RETURN memories, entities, relations
            """, tenant_id=tenant_id)
            record = result.single()
            return dict(record) if record else {}

    def get_subgraph(self, entity_name: str, tenant_id: str, max_depth: int = 2,
                     limit: int = 50) -> Dict[str, List[Dict]]:
        """获取以指定实体为中心的子图（支持 tenant_id 为 null 的数据）"""
        if not self.driver:
            return {"nodes": [], "edges": []}

        tenant_id = str(tenant_id) if tenant_id else None

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            query = Query("""
                MATCH path = (center:Entity)-[*0..%d]-(related:Entity)
                WHERE (center.name = $name) AND (center.tenant_id IS NULL OR center.tenant_id = $tenant_id)
                  AND (related.tenant_id IS NULL OR related.tenant_id = $tenant_id)
                WITH nodes(path) as nodes, relationships(path) as rels
                UNWIND nodes as node
                WITH collect(DISTINCT {
                    id: id(node),
                    name: node.name,
                    type: node.type,
                    properties: node.properties
                }) as all_nodes, rels
                UNWIND rels as rel
                WITH all_nodes, collect(DISTINCT {
                    id: id(rel),
                    source: id(startNode(rel)),
                    target: id(endNode(rel)),
                    type: rel.type,
                    properties: properties(rel)
                }) as all_edges
                RETURN all_nodes[0..%d] as nodes, all_edges[0..%d] as edges
            """ % (max_depth, limit, limit))

            result = session.run(query, name=entity_name, tenant_id=tenant_id)
            record = result.single()

            if record:
                nodes = record["nodes"] or []
                edges = record["edges"] or []
                for node in nodes:
                    node["id"] = str(node["id"])
                    if isinstance(node.get("properties"), str):
                        node["properties"] = json.loads(node["properties"])
                    if node.get("properties") is None:
                        node["properties"] = {}
                    node["properties"] = self._serialize_value(node.get("properties"))
                for edge in edges:
                    edge["id"] = str(edge["id"])
                    edge["source"] = str(edge["source"])
                    edge["target"] = str(edge["target"])
                    if edge.get("type") is None:
                        edge["type"] = "RELATED"
                    if isinstance(edge.get("properties"), str):
                        edge["properties"] = json.loads(edge["properties"])
                    if edge.get("properties") is None:
                        edge["properties"] = {}
                    edge["properties"] = self._serialize_value(edge.get("properties"))
                return {"nodes": nodes, "edges": edges}
            return {"nodes": [], "edges": []}

    def get_graph_sample(self, tenant_id: str, limit: int = 50) -> Dict[str, List[Dict]]:
        """获取当前租户图的采样数据（支持 tenant_id 为 null 的数据）"""
        if not self.driver:
            return {"nodes": [], "edges": []}

        tenant_id = str(tenant_id) if tenant_id else None

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (n:Entity)
                WHERE (n.tenant_id IS NULL OR n.tenant_id = $tenant_id)
                WITH n LIMIT $limit
                OPTIONAL MATCH (n)-[r:RELATED]->(m:Entity)
                WHERE (m.tenant_id IS NULL OR m.tenant_id = $tenant_id)
                WITH collect(DISTINCT {
                    id: id(n),
                    name: n.name,
                    type: n.type,
                    properties: n.properties
                }) as nodes,
                collect(DISTINCT {
                    id: id(r),
                    source: id(startNode(r)),
                    target: id(endNode(r)),
                    type: r.type,
                    properties: properties(r)
                }) as edges
                RETURN nodes, edges
            """, tenant_id=tenant_id, limit=limit)

            record = result.single()
            if record:
                nodes = record["nodes"] or []
                edges = record["edges"] or []
                for node in nodes:
                    node["id"] = str(node["id"])
                    if isinstance(node.get("properties"), str):
                        node["properties"] = json.loads(node["properties"])
                    if node.get("properties") is None:
                        node["properties"] = {}
                    node["properties"] = self._serialize_value(node.get("properties"))
                for edge in edges:
                    edge["id"] = str(edge["id"])
                    edge["source"] = str(edge["source"])
                    edge["target"] = str(edge["target"])
                    if edge.get("type") is None:
                        edge["type"] = "RELATED"
                    if isinstance(edge.get("properties"), str):
                        edge["properties"] = json.loads(edge["properties"])
                    if edge.get("properties") is None:
                        edge["properties"] = {}
                    edge["properties"] = self._serialize_value(edge.get("properties"))
                return {"nodes": nodes, "edges": edges}
            return {"nodes": [], "edges": []}

    def get_all_entities(self, tenant_id: str, limit: int = 200, 
                        offset: int = 0, entity_type: str = None) -> Dict[str, Any]:
        """获取当前租户的所有实体列表（支持 tenant_id 为 null 的数据）"""
        if not self.driver:
            return {"entities": [], "total": 0}

        tenant_id = str(tenant_id) if tenant_id else None

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            if entity_type:
                count_result = session.run("""
                    MATCH (e:Entity)
                    WHERE (e.tenant_id IS NULL OR e.tenant_id = $tenant_id) AND e.type = $type
                    RETURN count(e) as total
                """, tenant_id=tenant_id, type=entity_type)
                
                result = session.run("""
                    MATCH (e:Entity)
                    WHERE (e.tenant_id IS NULL OR e.tenant_id = $tenant_id) AND e.type = $type
                    RETURN id(e) as id,
                           e.name as name,
                           e.type as type,
                           e.properties as properties,
                           e.created_at as created_at,
                           e.updated_at as updated_at
                    ORDER BY e.updated_at DESC
                    SKIP $offset
                    LIMIT $limit
                """, tenant_id=tenant_id, type=entity_type, offset=offset, limit=limit)
            else:
                count_result = session.run("""
                    MATCH (e:Entity)
                    WHERE (e.tenant_id IS NULL OR e.tenant_id = $tenant_id)
                    RETURN count(e) as total
                """, tenant_id=tenant_id)
                
                result = session.run("""
                    MATCH (e:Entity)
                    WHERE (e.tenant_id IS NULL OR e.tenant_id = $tenant_id)
                    RETURN id(e) as id,
                           e.name as name,
                           e.type as type,
                           e.properties as properties,
                           e.created_at as created_at,
                           e.updated_at as updated_at
                    ORDER BY e.updated_at DESC
                    SKIP $offset
                    LIMIT $limit
                """, tenant_id=tenant_id, offset=offset, limit=limit)

            count_record = count_result.single()
            total = count_record["total"] if count_record else 0
            
            entities = []
            for record in result:
                entities.append({
                    "id": str(record["id"]),
                    "name": record["name"],
                    "type": record["type"],
                    "properties": dict(record["properties"]) if record["properties"] else {},
                    "created_at": record["created_at"].isoformat() if record["created_at"] else None,
                    "updated_at": record["updated_at"].isoformat() if record["updated_at"] else None
                })
            
            return {
                "entities": entities,
                "total": total,
                "limit": limit,
                "offset": offset
            }

    def get_entity_types(self, tenant_id: str) -> List[str]:
        """获取当前租户的所有实体类型（支持 tenant_id 为 null 的数据）"""
        if not self.driver:
            return []

        tenant_id = str(tenant_id) if tenant_id else None

        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (e:Entity)
                WHERE (e.tenant_id IS NULL OR e.tenant_id = $tenant_id)
                RETURN collect(distinct e.type) as types
            """, tenant_id=tenant_id)
            
            record = result.single()
            return record["types"] if record and record["types"] else []


# 全局实例
neo4j_manager = Neo4jManager()
