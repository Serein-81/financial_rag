"""
数据库操作 MCP 工具

提供 Agent 可调用的数据库查询工具
包含租户隔离和权限控制

工具类型：本地 STDIO（访问本地数据库）
"""

import logging
from typing import Optional, Dict, Any

from app.mcp.decorators import local_tool

logger = logging.getLogger(__name__)


@local_tool(
    description="执行数据库查询（只读），仅支持 SELECT 语句，不允许 INSERT/UPDATE/DELETE"
)
async def query_database(
    tenant_id: str,
    sql: str,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    执行数据库查询（只读）
    
    用于查询企业数据库中的业务数据，支持基本的 SQL SELECT 查询。
    仅支持 SELECT 语句，不允许执行 INSERT/UPDATE/DELETE 等操作。
    
    Args:
        tenant_id: 租户ID，必填，用于数据隔离
        sql: SELECT 查询语句，必填
        limit: 最大返回记录数，默认100
    
    Returns:
        包含查询结果的字典
    
    Example:
        query_database(tenant_id="xxx", sql="SELECT * FROM users LIMIT 10")
    """
    sql_upper = sql.strip().upper()
    
    if not sql_upper.startswith("SELECT"):
        return {
            "status": "error",
            "error": "只允许执行 SELECT 查询语句",
            "message": "安全限制：禁止执行 INSERT、UPDATE、DELETE 等写操作"
        }
    
    try:
        from app.core.database import async_session_maker
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            result = await session.execute(text(sql))
            rows = result.fetchall()
            
            if not rows:
                return {
                    "status": "success",
                    "data": [],
                    "count": 0,
                    "message": "查询成功，未找到匹配记录"
                }
            
            columns = result.keys()
            data = []
            for i, row in enumerate(rows[:limit]):
                if i >= limit:
                    break
                data.append(dict(zip(columns, row)))
            
            return {
                "status": "success",
                "data": data,
                "count": len(data),
                "total": len(rows),
                "columns": list(columns),
                "message": f"查询成功，返回 {len(data)} 条记录（总计 {len(rows)} 条）"
            }
                
    except Exception as e:
        logger.error(f"数据库查询失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"查询失败: {str(e)}"
        }


@local_tool(
    description="获取数据库表结构，了解表字段、数据类型等信息"
)
async def get_table_schema(
    tenant_id: str,
    table_name: str,
) -> Dict[str, Any]:
    """
    获取数据库表结构
    
    用于查询指定表的字段信息、数据类型等结构信息。
    帮助 Agent 了解可用的数据字段。
    
    Args:
        tenant_id: 租户ID，必填
        table_name: 表名，必填
    
    Returns:
        包含表结构的字典
    
    Example:
        get_table_schema(tenant_id="xxx", table_name="users")
    """
    try:
        from app.core.database import async_session_maker
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            sql = """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = :table_name
                ORDER BY ordinal_position
            """
            
            result = await session.execute(text(sql), {"table_name": table_name})
            rows = result.fetchall()
            
            if not rows:
                return {
                    "status": "error",
                    "error": f"表不存在或无权限访问: {table_name}",
                    "message": f"未找到表 {table_name} 的结构信息"
                }
            
            schema = []
            for row in rows:
                schema.append({
                    "column_name": row[0],
                    "data_type": row[1],
                    "nullable": row[2] == "YES",
                    "default": row[3]
                })
            
            return {
                "status": "success",
                "table_name": table_name,
                "schema": schema,
                "count": len(schema),
                "message": f"表 {table_name} 包含 {len(schema)} 个字段"
            }
                
    except Exception as e:
        logger.error(f"获取表结构失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"获取表结构失败: {str(e)}"
        }


@local_tool(
    description="列出数据库中的表，支持通过模式匹配过滤表名"
)
async def list_tables(
    tenant_id: str,
    pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """
    列出数据库中的表
    
    用于查看当前租户可访问的数据库表列表。
    支持通过模式匹配过滤表名。
    
    Args:
        tenant_id: 租户ID，必填
        pattern: 表名匹配模式（可选），支持 % 作为通配符
    
    Returns:
        包含表列表的字典
    
    Example:
        list_tables(tenant_id="xxx")
        list_tables(tenant_id="xxx", pattern="order%")
    """
    try:
        from app.core.database import async_session_maker
        
        async with async_session_maker() as session:
            from sqlalchemy import text
            
            if pattern:
                sql = """
                    SELECT table_name, table_type
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name LIKE :pattern
                    ORDER BY table_name
                """
                result = await session.execute(text(sql), {"pattern": pattern})
            else:
                sql = """
                    SELECT table_name, table_type
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """
                result = await session.execute(text(sql))
            
            rows = result.fetchall()
            
            tables = [{"name": row[0], "type": row[1]} for row in rows]
            
            return {
                "status": "success",
                "tables": tables,
                "count": len(tables),
                "message": f"找到 {len(tables)} 个表"
            }
                
    except Exception as e:
        logger.error(f"列出表失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"列出表失败: {str(e)}"
        }


def create_database_tools():
    """创建数据库工具列表"""
    return [
        query_database,
        get_table_schema,
        list_tables,
    ]
