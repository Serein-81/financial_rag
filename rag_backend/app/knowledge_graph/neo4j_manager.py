"""Neo4j 图数据库管理器"""
import json
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
            print("[WARNING] Neo4j 模块未安装，跳过连接")
            self.driver = None
            return
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # 测试连接
            self.driver.verify_connectivity()
            print(f"[OK] Neo4j 连接成功: {self.uri}")
        except Exception as e:
            print(f"[ERROR] Neo4j 连接失败: {e}")
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

            result = session.run("""
                MATCH (s:Entity)
                MATCH (t:Entity)
                WHERE (s.name = $source) AND (t.name = $target)
                  AND (s.tenant_id IS NULL OR s.tenant_id = $tenant_id)
                  AND (t.tenant_id IS NULL OR t.tenant_id = $tenant_id)
                MERGE (s)-[r:RELATED {type: $rel_type}]->(t)
                SET r.weight = $weight,
                    r.updated_at = datetime()
                RETURN id(r) as id
            """, source=source_name, target=target_name,
                rel_type=relation_type, tenant_id=tenant_id, weight=weight)

            record = result.single()
            return {"id": str(record["id"])} if record else None

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