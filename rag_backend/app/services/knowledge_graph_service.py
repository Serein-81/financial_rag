"""
轻量级知识图谱服务

基于 PostgreSQL 实现的简单知识图谱
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text
from app.db import AsyncSessionLocal
import json


class KnowledgeGraphService:
    """
    轻量级知识图谱服务
    
    使用 PostgreSQL 存储实体和关系
    """
    
    async def add_entity(self, name: str, entity_type: str, 
                        properties: Dict[str, Any] = None) -> str:
        """添加实体"""
        async with AsyncSessionLocal() as db:
            sql = text("""
                INSERT INTO kg_entities (name, type, properties)
                VALUES (:name, :type, :props)
                RETURNING id
            """)
            result = await db.execute(
                sql,
                {
                    "name": name,
                    "type": entity_type,
                    "props": json.dumps(properties or {})
                }
            )
            await db.commit()
            entity_id = result.scalar()
            return str(entity_id)
    
    async def add_relation(self, subject: str, predicate: str, 
                          object: str) -> None:
        """添加关系（三元组）"""
        async with AsyncSessionLocal() as db:
            # 查找实体ID
            subject_id = await self._get_entity_id(db, subject)
            object_id = await self._get_entity_id(db, object)
            
            if not subject_id or not object_id:
                return
            
            sql = text("""
                INSERT INTO kg_relations (subject_id, predicate, object_id)
                VALUES (:subject, :predicate, :object)
            """)
            await db.execute(
                sql,
                {
                    "subject": subject_id,
                    "predicate": predicate,
                    "object": object_id
                }
            )
            await db.commit()
    
    async def get_neighbors(self, entity_name: str, 
                           relation_type: Optional[str] = None) -> List[Tuple[str, str]]:
        """获取实体的邻居"""
        async with AsyncSessionLocal() as db:
            entity_id = await self._get_entity_id(db, entity_name)
            if not entity_id:
                return []
            
            sql = text("""
                SELECT r.predicate, e2.name
                FROM kg_relations r
                JOIN kg_entities e2 ON r.object_id = e2.id
                WHERE r.subject_id = :entity_id
            """)
            
            if relation_type:
                sql = text("""
                    SELECT r.predicate, e2.name
                    FROM kg_relations r
                    JOIN kg_entities e2 ON r.object_id = e2.id
                    WHERE r.subject_id = :entity_id AND r.predicate = :rel_type
                """)
                result = await db.execute(sql, {"entity_id": entity_id, "rel_type": relation_type})
            else:
                result = await db.execute(sql, {"entity_id": entity_id})
            
            return [(row[0], row[1]) for row in result.fetchall()]
    
    async def query_path(self, start: str, end: str, 
                        max_depth: int = 3) -> List[List[str]]:
        """查询两个实体之间的路径（BFS）"""
        async with AsyncSessionLocal() as db:
            start_id = await self._get_entity_id(db, start)
            end_id = await self._get_entity_id(db, end)
            
            if not start_id or not end_id:
                return []
            
            # 使用递归 CTE 查询路径
            sql = text("""
                WITH RECURSIVE paths AS (
                    SELECT 
                        subject_id,
                        object_id,
                        predicate,
                        ARRAY[subject_id] as path,
                        1 as depth
                    FROM kg_relations
                    WHERE subject_id = :start_id
                    
                    UNION ALL
                    
                    SELECT 
                        r.subject_id,
                        r.object_id,
                        r.predicate,
                        p.path || r.subject_id,
                        p.depth + 1
                    FROM kg_relations r
                    JOIN paths p ON r.subject_id = p.object_id
                    WHERE p.depth < :max_depth
                    AND NOT r.subject_id = ANY(p.path)
                )
                SELECT path || object_id as full_path
                FROM paths
                WHERE object_id = :end_id
                LIMIT 10
            """)
            
            result = await db.execute(
                sql,
                {"start_id": start_id, "end_id": end_id, "max_depth": max_depth}
            )
            
            paths = []
            for row in result.fetchall():
                path_ids = row[0]
                path_names = await self._ids_to_names(db, path_ids)
                paths.append(path_names)
            
            return paths
    
    async def extract_entities_from_text(self, text: str) -> Dict[str, List[Dict]]:
        """从文本提取实体和关系（使用 LLM）"""
        from app.services.llm_service import llm_service
        
        prompt = f"""
从以下文本中提取实体和关系，返回 JSON 格式：

文本：{text}

返回格式：
{{
    "entities": [
        {{"name": "实体名", "type": "类型"}},
        ...
    ],
    "relations": [
        {{"subject": "主体", "predicate": "关系", "object": "客体"}},
        ...
    ]
}}
"""
        
        response = await llm_service.get_answer(prompt, [], [])
        
        try:
            # 提取 JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
        except Exception:
            pass
        
        return {"entities": [], "relations": []}
    
    async def build_graph_from_text(self, text: str) -> Dict[str, int]:
        """从文本构建知识图谱"""
        # 提取实体和关系
        extracted = await self.extract_entities_from_text(text)
        
        # 添加实体
        entity_count = 0
        for entity in extracted.get("entities", []):
            await self.add_entity(
                name=entity["name"],
                entity_type=entity.get("type", "unknown")
            )
            entity_count += 1
        
        # 添加关系
        relation_count = 0
        for relation in extracted.get("relations", []):
            await self.add_relation(
                subject=relation["subject"],
                predicate=relation["predicate"],
                object=relation["object"]
            )
            relation_count += 1
        
        return {
            "entities": entity_count,
            "relations": relation_count
        }
    
    async def _get_entity_id(self, db, name: str) -> Optional[str]:
        """获取实体ID"""
        sql = text("SELECT id FROM kg_entities WHERE name = :name LIMIT 1")
        result = await db.execute(sql, {"name": name})
        row = result.fetchone()
        return str(row[0]) if row else None
    
    async def _ids_to_names(self, db, ids: List[str]) -> List[str]:
        """ID转名称"""
        sql = text("SELECT name FROM kg_entities WHERE id = ANY(:ids)")
        result = await db.execute(sql, {"ids": ids})
        return [row[0] for row in result.fetchall()]


# 全局实例
kg_service = KnowledgeGraphService()
