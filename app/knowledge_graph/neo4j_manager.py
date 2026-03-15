"""Neo4j 图数据库管理器"""
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase, Driver
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
    
    def _connect(self):
        """建立连接"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # 测试连接
            self.driver.verify_connectivity()
            print(f"✅ Neo4j 连接成功: {self.uri}")
        except Exception as e:
            print(f"❌ Neo4j 连接失败: {e}")
            self.driver = None
    
    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
    
    def create_memory_node(self, memory_id: str, content: str, 
                          user_id: str, metadata: Dict) -> bool:
        """创建记忆节点"""
        if not self.driver:
            return False
        
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MERGE (m:Memory {id: $id})
                SET m.content = $content,
                    m.user_id = $user_id,
                    m.importance = $importance,
                    m.created_at = datetime()
                RETURN m
            """, id=memory_id, content=content, user_id=user_id,
                importance=metadata.get('importance', 0.5))
            return result.single() is not None

    
    def create_entity(self, name: str, entity_type: str, 
                     properties: Dict = None, unique_key: str = None) -> Optional[str]:
        """
        创建实体节点（支持消歧）
        
        Args:
            name: 实体名称
            entity_type: 实体类型
            properties: 附加属性
            unique_key: 唯一标识（用于消歧，如果不提供则使用 name_type）
        """
        if not self.driver:
            return None
        
        # 生成唯一标识
        if not unique_key:
            unique_key = f"{name}_{entity_type}"
        
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            # 使用 unique_key 作为唯一标识，支持消歧
            if properties:
                result = session.run("""
                    MERGE (e:Entity {unique_key: $unique_key})
                    SET e.name = $name,
                        e.type = $type,
                        e.properties = $properties,
                        e.updated_at = datetime()
                    RETURN e.name as id
                """, unique_key=unique_key, name=name, type=entity_type, properties=properties)
            else:
                result = session.run("""
                    MERGE (e:Entity {unique_key: $unique_key})
                    SET e.name = $name,
                        e.type = $type,
                        e.updated_at = datetime()
                    RETURN e.name as id
                """, unique_key=unique_key, name=name, type=entity_type)
            
            record = result.single()
            return record['id'] if record else None
    
    def create_relation(self, source_name: str, target_name: str,
                       relation_type: str, properties: Dict = None) -> Optional[Dict]:
        """创建实体关系"""
        if not self.driver:
            return None
        
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            # 如果 properties 为空，使用默认权重
            weight = properties.get("weight", 1.0) if properties else 1.0
            
            result = session.run("""
                MATCH (s:Entity {name: $source})
                MATCH (t:Entity {name: $target})
                MERGE (s)-[r:RELATED {type: $rel_type}]->(t)
                SET r.weight = $weight,
                    r.updated_at = datetime()
                RETURN id(r) as id
            """, source=source_name, target=target_name,
                rel_type=relation_type, weight=weight)
            
            record = result.single()
            return {"id": str(record["id"])} if record else None
    
    def link_memory_to_entities(self, memory_id: str, 
                               entity_names: List[str]) -> int:
        """关联记忆和实体"""
        if not self.driver:
            return 0
        
        count = 0
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            for entity_name in entity_names:
                result = session.run("""
                    MATCH (m:Memory {id: $memory_id})
                    MATCH (e:Entity {name: $entity_name})
                    MERGE (m)-[r:CONTAINS]->(e)
                    RETURN r
                """, memory_id=memory_id, entity_name=entity_name)
                if result.single():
                    count += 1
        return count
    
    def find_related_entities(self, entity_name: str, 
                            max_depth: int = 2, limit: int = 20) -> List[Dict]:
        """查找相关实体"""
        if not self.driver:
            return []
        
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH path = (e:Entity {name: $name})-[*1..%d]-(related:Entity)
                RETURN DISTINCT related.name as name, 
                       related.type as type,
                       length(path) as distance
                ORDER BY distance
                LIMIT $limit
            """ % max_depth, name=entity_name, limit=limit)
            
            return [dict(record) for record in result]
    
    def find_memories_by_entity(self, entity_name: str) -> List[str]:
        """通过实体查找记忆"""
        if not self.driver:
            return []
        
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (m:Memory)-[:CONTAINS]->(e:Entity {name: $name})
                RETURN m.id as memory_id
                ORDER BY m.created_at DESC
                LIMIT 10
            """, name=entity_name)
            
            return [record['memory_id'] for record in result]
    
    def get_graph_stats(self) -> Dict[str, int]:
        """获取图统计信息"""
        if not self.driver:
            return {}
        
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (m:Memory) WITH count(m) as memories
                MATCH (e:Entity) WITH memories, count(e) as entities
                MATCH ()-[r:RELATED]->() WITH memories, entities, count(r) as relations
                RETURN memories, entities, relations
            """)
            record = result.single()
            return dict(record) if record else {}
    
    def get_subgraph(self, entity_name: str, max_depth: int = 2, 
                     limit: int = 50) -> Dict[str, List[Dict]]:
        """获取以指定实体为中心的子图"""
        if not self.driver:
            return {"nodes": [], "edges": []}
        
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            # 查询节点和边
            result = session.run("""
                MATCH path = (center:Entity {name: $name})-[*0..%d]-(related:Entity)
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
            """ % (max_depth, limit, limit), name=entity_name)
            
            record = result.single()
            if record:
                return {
                    "nodes": record["nodes"] or [],
                    "edges": record["edges"] or []
                }
            return {"nodes": [], "edges": []}
    
    def get_graph_sample(self, limit: int = 50) -> Dict[str, List[Dict]]:
        """获取图的采样数据"""
        if not self.driver:
            return {"nodes": [], "edges": []}
        
        with self.driver.session(database=settings.NEO4J_DATABASE) as session:
            result = session.run("""
                MATCH (n:Entity)
                WITH n LIMIT $limit
                OPTIONAL MATCH (n)-[r:RELATED]->(m:Entity)
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
            """, limit=limit)
            
            record = result.single()
            if record:
                return {
                    "nodes": record["nodes"] or [],
                    "edges": record["edges"] or []
                }
            return {"nodes": [], "edges": []}


# 全局实例
neo4j_manager = Neo4jManager()
